from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .judgment_engine import EngineDecision, SYSTEM_INSTRUCTION, effective_reliability
from .models import (
    AIPosition,
    Case,
    Evidence,
    HistoryEvent,
    HistoryEventType,
    Judgment,
    JudgmentConclusion,
    JudgmentOrigin,
    ReevaluationTrigger,
    ReliabilityAssessment,
    SourceVerification,
    SourceVerificationStatus,
    SupportAssessment,
)
from .reliability_engine import MetadataReliabilityProvider, ReliabilityDecision
from .source_verification import SourceVerificationDecision
from .schemas import JudgmentCreate
from .support_engine import SupportDecision


DECISION_SNAPSHOT_SCHEMA_VERSION = "decision-snapshot-v1"


def append_history(
    db: Session,
    *,
    case_id: int,
    event_type: HistoryEventType,
    entity_type: str,
    entity_id: int | None,
    actor: str,
    payload: dict,
) -> HistoryEvent:
    event = HistoryEvent(
        case_id=case_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        actor=actor,
        payload=payload,
    )
    db.add(event)
    return event


def ai_position_for(conclusion: JudgmentConclusion) -> AIPosition:
    if conclusion == JudgmentConclusion.SUPPORTED:
        return AIPosition.AGREE
    if conclusion == JudgmentConclusion.CONTRADICTED:
        return AIPosition.DISAGREE
    return AIPosition.UNSURE


def judgment_create_from_engine(decision: EngineDecision) -> JudgmentCreate:
    return JudgmentCreate(
        conclusion=decision.conclusion,
        ai_position=ai_position_for(decision.conclusion),
        confidence=decision.confidence,
        resolution_state=decision.resolution_state,
        position_text=decision.position_text,
        reasoning_summary=decision.reasoning_summary,
        unresolved_reason=decision.unresolved_reason,
        waiting_for=decision.waiting_for,
        evidence_assessments=[item.model_dump(mode="json") for item in decision.evidence_assessments],
    )


def _snapshot_evidence(item: Evidence) -> dict[str, Any]:
    return {
        "id": item.id,
        "content": item.content,
        "claimed_source_type": item.claimed_source_type.value,
        "claimed_is_primary_source": item.claimed_is_primary_source,
        "source_verification_status": item.source_verification_status.value,
        "verified_source_type": item.verified_source_type.value if item.verified_source_type else None,
        "verified_is_primary_source": item.verified_is_primary_source,
        "source_url": item.source_url,
        "source_published_at": item.source_published_at.isoformat() if item.source_published_at else None,
        "reliability_score": item.reliability_score,
        "reliability_source": item.reliability_source,
        "effective_reliability": effective_reliability(item),
    }


def build_decision_snapshot(
    *,
    case: Case,
    evidence: list[Evidence],
    provider_name: str,
    model_name: str | None,
) -> dict[str, Any]:
    """Freeze the exact decision context that mattered at judgment time.

    The snapshot is deliberately human-readable JSON so a future reviewer can
    see what the system believed it was evaluating without consulting mutable
    current rows.
    """

    prompt_version = os.getenv("JUDGMENT_PROMPT_VERSION", "judgment-prompt-v1")
    judgment_rule_version = os.getenv("JUDGMENT_RULE_VERSION", "judgment-rules-v1")
    reliability_rule_version = os.getenv(
        "RELIABILITY_RULE_VERSION", MetadataReliabilityProvider.method_version
    )

    return {
        "schema_version": DECISION_SNAPSHOT_SCHEMA_VERSION,
        "case": {
            "id": case.id,
            "original_input": case.original_input,
        },
        "evidence": [
            _snapshot_evidence(item)
            for item in sorted(evidence, key=lambda item: (item.created_at, item.id))
        ],
        "provider": {
            "name": provider_name,
            "model": model_name,
        },
        "rules": {
            "prompt_version": prompt_version,
            "judgment_rule_version": judgment_rule_version,
            "reliability_rule_version": reliability_rule_version,
            "system_instruction": SYSTEM_INSTRUCTION.strip(),
        },
        "model_options": {
            "structured_output": "EngineDecision",
            "store": False,
            "max_output_tokens": int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "1800")),
            "reasoning_effort": os.getenv("OPENAI_REASONING_EFFORT", "low").strip().lower(),
        },
    }


def decision_fingerprint(snapshot: dict[str, Any]) -> str:
    canonical = json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _verification_only_trigger(
    previous_evidence: list[dict[str, Any]], current_evidence: list[dict[str, Any]]
) -> ReevaluationTrigger | None:
    if [item.get("id") for item in previous_evidence] != [item.get("id") for item in current_evidence]:
        return None

    verification_keys = {
        "source_verification_status",
        "verified_source_type",
        "verified_is_primary_source",
        # Reliability is re-assessed locally after source verification. These
        # derived values may change even though the reevaluation cause is still
        # SOURCE_VERIFIED / SOURCE_DISPROVED rather than NEW_EVIDENCE.
        "reliability_score",
        "reliability_source",
        "effective_reliability",
    }

    changed = False
    saw_verified = False
    saw_disputed = False

    for before, after in zip(previous_evidence, current_evidence, strict=True):
        before_without_verification = {
            key: value for key, value in before.items() if key not in verification_keys
        }
        after_without_verification = {
            key: value for key, value in after.items() if key not in verification_keys
        }
        if before_without_verification != after_without_verification:
            return None

        if any(before.get(key) != after.get(key) for key in verification_keys):
            changed = True
            after_status = after.get("source_verification_status")
            if after_status == SourceVerificationStatus.VERIFIED.value:
                saw_verified = True
            if after_status in {
                SourceVerificationStatus.DISPUTED.value,
                SourceVerificationStatus.INVALID.value,
            }:
                saw_disputed = True

    if not changed:
        return None
    if saw_disputed:
        return ReevaluationTrigger.SOURCE_DISPROVED
    if saw_verified:
        return ReevaluationTrigger.SOURCE_VERIFIED
    return ReevaluationTrigger.SOURCE_REVIEWED


def infer_reevaluation_trigger(
    previous: Judgment | None,
    current_snapshot: dict[str, Any],
) -> ReevaluationTrigger:
    if previous is None:
        return ReevaluationTrigger.INITIAL

    previous_snapshot = previous.decision_snapshot or {}
    if not previous_snapshot:
        return ReevaluationTrigger.USER_REQUEST

    if previous_snapshot.get("case") != current_snapshot.get("case"):
        return ReevaluationTrigger.INPUT_CHANGED

    previous_provider = previous_snapshot.get("provider", {})
    current_provider = current_snapshot.get("provider", {})
    if previous_provider != current_provider:
        return ReevaluationTrigger.MODEL_CHANGED

    if previous_snapshot.get("model_options", {}) != current_snapshot.get("model_options", {}):
        return ReevaluationTrigger.MODEL_CHANGED

    previous_rules = previous_snapshot.get("rules", {})
    current_rules = current_snapshot.get("rules", {})
    if previous_rules != current_rules:
        return ReevaluationTrigger.RULE_CHANGED

    previous_evidence = previous_snapshot.get("evidence", [])
    current_evidence = current_snapshot.get("evidence", [])
    if previous_evidence != current_evidence:
        verification_trigger = _verification_only_trigger(previous_evidence, current_evidence)
        if verification_trigger is not None:
            return verification_trigger
        return ReevaluationTrigger.NEW_EVIDENCE

    return ReevaluationTrigger.USER_REQUEST


def _judgment_state_changed(previous: Judgment, payload: JudgmentCreate) -> bool:
    """Return True only when the user-visible judgment state materially changes.

    Explanation wording/evidence rationale may evolve while the actual position stays the same;
    that is a reaffirmation, not a revision.
    """
    return any(
        (
            previous.conclusion != payload.conclusion,
            previous.ai_position != ai_position_for(payload.conclusion),
            abs(previous.confidence - payload.confidence) > 1e-9,
            previous.resolution_state != payload.resolution_state,
            previous.unresolved_reason != payload.unresolved_reason,
            previous.waiting_for != payload.waiting_for,
        )
    )


def _reliability_changed(previous: ReliabilityAssessment, decision: ReliabilityDecision) -> bool:
    numeric_pairs = (
        (previous.authority_score, decision.authority_score),
        (previous.originality_score, decision.originality_score),
        (previous.directness_score, decision.directness_score),
        (previous.recency_score, decision.recency_score),
        (previous.corroboration_score, decision.corroboration_score),
        (previous.final_score, decision.final_score),
    )
    if previous.method_version != decision.method_version:
        return True
    return any(abs(before - after) > 1e-9 for before, after in numeric_pairs)


def create_judgment(
    db: Session,
    *,
    case_id: int,
    payload: JudgmentCreate,
    origin: JudgmentOrigin = JudgmentOrigin.MANUAL,
    actor: str = "USER",
    reevaluation_trigger: ReevaluationTrigger | None = None,
    decision_snapshot: dict[str, Any] | None = None,
    decision_fingerprint_value: str | None = None,
) -> Judgment:
    previous = db.scalar(
        select(Judgment)
        .where(Judgment.case_id == case_id)
        .order_by(Judgment.revision_no.desc())
        .limit(1)
    )

    trigger = reevaluation_trigger or (
        ReevaluationTrigger.INITIAL if previous is None else ReevaluationTrigger.USER_REQUEST
    )

    if previous is not None:
        append_history(
            db,
            case_id=case_id,
            event_type=HistoryEventType.REEVALUATION_STARTED,
            entity_type="JUDGMENT",
            entity_id=previous.id,
            actor=actor,
            payload={
                "previous_judgment_id": previous.id,
                "previous_revision_no": previous.revision_no,
                "trigger": trigger.value,
            },
        )

    judgment = Judgment(
        case_id=case_id,
        previous_judgment_id=previous.id if previous else None,
        revision_no=(previous.revision_no + 1) if previous else 1,
        conclusion=payload.conclusion,
        ai_position=ai_position_for(payload.conclusion),
        confidence=payload.confidence,
        resolution_state=payload.resolution_state,
        position_text=payload.position_text,
        reasoning_summary=payload.reasoning_summary,
        unresolved_reason=payload.unresolved_reason,
        waiting_for=payload.waiting_for,
        evidence_assessments=payload.evidence_assessments,
        origin=origin,
        actor=actor,
        reevaluation_trigger=trigger,
        decision_snapshot=decision_snapshot,
        decision_fingerprint=decision_fingerprint_value,
    )
    db.add(judgment)
    db.flush()

    state_changed = previous is not None and _judgment_state_changed(previous, payload)

    append_history(
        db,
        case_id=case_id,
        event_type=(
            HistoryEventType.JUDGMENT_CREATED
            if previous is None
            else (
                HistoryEventType.JUDGMENT_REVISED
                if state_changed
                else HistoryEventType.JUDGMENT_REAFFIRMED
            )
        ),
        entity_type="JUDGMENT",
        entity_id=judgment.id,
        actor=actor,
        payload={
            "revision_no": judgment.revision_no,
            "previous_judgment_id": judgment.previous_judgment_id,
            "conclusion": judgment.conclusion.value,
            "ai_position": judgment.ai_position.value,
            "confidence": judgment.confidence,
            "resolution_state": judgment.resolution_state.value,
            "position_text": judgment.position_text,
            "unresolved_reason": judgment.unresolved_reason,
            "waiting_for": judgment.waiting_for,
            "evidence_assessments": judgment.evidence_assessments,
            "origin": judgment.origin.value,
            "actor": judgment.actor,
            "trigger": trigger.value,
            "decision_fingerprint": judgment.decision_fingerprint,
            "snapshot_schema_version": (
                decision_snapshot.get("schema_version") if decision_snapshot else None
            ),
        },
    )

    if previous is not None:
        append_history(
            db,
            case_id=case_id,
            event_type=HistoryEventType.REEVALUATION_COMPLETED,
            entity_type="JUDGMENT",
            entity_id=judgment.id,
            actor=actor,
            payload={
                "from_judgment_id": previous.id,
                "to_judgment_id": judgment.id,
                "from_conclusion": previous.conclusion.value,
                "to_conclusion": judgment.conclusion.value,
                "state_changed": state_changed,
                "trigger": trigger.value,
            },
        )

    return judgment


def create_support_assessment(
    db: Session, *, case_id: int, source_text: str, decision: SupportDecision
) -> SupportAssessment:
    assessment = SupportAssessment(
        case_id=case_id,
        source_text=source_text,
        expression_summary=decision.expression_summary,
        affect_signals=[item.model_dump(mode="json") for item in decision.affect_signals],
        context_mode=decision.context_mode,
        context_rationale=decision.context_rationale,
        nudge_level=decision.nudge_level,
        delivery_style=decision.delivery_style,
        recommendation_text=decision.recommendation_text,
        rationale_summary=decision.rationale_summary,
    )
    db.add(assessment)
    db.flush()

    append_history(
        db,
        case_id=case_id,
        event_type=HistoryEventType.CONTEXT_ASSESSED,
        entity_type="SUPPORT_ASSESSMENT",
        entity_id=assessment.id,
        actor="AI",
        payload={
            "context_mode": assessment.context_mode.value,
            "expression_summary": assessment.expression_summary,
            "affect_signals": assessment.affect_signals,
            "nudge_level": assessment.nudge_level.value,
            "delivery_style": assessment.delivery_style.value,
        },
    )

    if assessment.recommendation_text:
        append_history(
            db,
            case_id=case_id,
            event_type=HistoryEventType.NUDGE_GENERATED,
            entity_type="SUPPORT_ASSESSMENT",
            entity_id=assessment.id,
            actor="AI",
            payload={
                "nudge_level": assessment.nudge_level.value,
                "delivery_style": assessment.delivery_style.value,
                "recommendation_text": assessment.recommendation_text,
            },
        )

    return assessment


def _source_verification_changed(
    previous: SourceVerification, decision: SourceVerificationDecision
) -> bool:
    return any(
        (
            previous.status != decision.status,
            previous.verified_source_type != decision.verified_source_type,
            previous.verified_is_primary_source != decision.verified_is_primary_source,
        )
    )


def create_source_verification(
    db: Session,
    *,
    evidence: Evidence,
    decision: SourceVerificationDecision,
    actor: str = "SYSTEM",
) -> SourceVerification:
    previous = db.scalar(
        select(SourceVerification)
        .where(SourceVerification.evidence_id == evidence.id)
        .order_by(SourceVerification.revision_no.desc())
        .limit(1)
    )

    changed = previous is None or _source_verification_changed(previous, decision)
    verification = SourceVerification(
        case_id=evidence.case_id,
        evidence_id=evidence.id,
        revision_no=(previous.revision_no + 1) if previous else 1,
        status=decision.status,
        verified_source_type=decision.verified_source_type,
        verified_is_primary_source=decision.verified_is_primary_source,
        rationale=decision.rationale,
        checks=decision.checks,
        method_version=decision.method_version,
        actor=actor,
    )
    db.add(verification)
    db.flush()

    before_status = evidence.source_verification_status
    evidence.source_verification_status = decision.status
    if decision.status == SourceVerificationStatus.VERIFIED:
        evidence.verified_source_type = decision.verified_source_type
        evidence.verified_is_primary_source = decision.verified_is_primary_source
    else:
        # Partial/failed checks must never leave stale verified metadata behind.
        evidence.verified_source_type = None
        evidence.verified_is_primary_source = None

    append_history(
        db,
        case_id=evidence.case_id,
        event_type=(
            HistoryEventType.SOURCE_VERIFICATION_ASSESSED
            if previous is None
            else (
                HistoryEventType.SOURCE_VERIFICATION_REVISED
                if changed
                else HistoryEventType.SOURCE_VERIFICATION_REAFFIRMED
            )
        ),
        entity_type="EVIDENCE",
        entity_id=evidence.id,
        actor=actor,
        payload={
            "verification_id": verification.id,
            "revision_no": verification.revision_no,
            "before_status": before_status.value,
            "final_status": verification.status.value,
            "verified_source_type": (
                verification.verified_source_type.value
                if verification.verified_source_type
                else None
            ),
            "verified_is_primary_source": verification.verified_is_primary_source,
            "method_version": verification.method_version,
            "state_changed": changed,
            "rationale": verification.rationale,
            "checks": verification.checks,
        },
    )
    return verification


def create_reliability_assessment(
    db: Session,
    *,
    evidence,
    decision: ReliabilityDecision,
    actor: str = "SYSTEM",
) -> ReliabilityAssessment:
    previous = db.scalar(
        select(ReliabilityAssessment)
        .where(ReliabilityAssessment.evidence_id == evidence.id)
        .order_by(ReliabilityAssessment.revision_no.desc())
        .limit(1)
    )

    assessment = ReliabilityAssessment(
        case_id=evidence.case_id,
        evidence_id=evidence.id,
        revision_no=(previous.revision_no + 1) if previous else 1,
        authority_score=decision.authority_score,
        originality_score=decision.originality_score,
        directness_score=decision.directness_score,
        recency_score=decision.recency_score,
        corroboration_score=decision.corroboration_score,
        conflict_penalty=0.0,  # legacy DB column; no longer used in scoring
        final_score=decision.final_score,
        rationale=decision.rationale,
        method_version=decision.method_version,
    )
    db.add(assessment)
    db.flush()

    before_score = evidence.reliability_score
    before_source = evidence.reliability_source
    evidence.reliability_score = decision.final_score
    evidence.reliability_source = decision.method_version

    append_history(
        db,
        case_id=evidence.case_id,
        event_type=(
            HistoryEventType.RELIABILITY_ASSESSED
            if previous is None
            else (
                HistoryEventType.RELIABILITY_REVISED
                if _reliability_changed(previous, decision)
                else HistoryEventType.RELIABILITY_REAFFIRMED
            )
        ),
        entity_type="EVIDENCE",
        entity_id=evidence.id,
        actor=actor,
        payload={
            "assessment_id": assessment.id,
            "revision_no": assessment.revision_no,
            "method_version": assessment.method_version,
            "before_score": before_score,
            "before_source": before_source,
            "final_score": assessment.final_score,
            "state_changed": (True if previous is None else _reliability_changed(previous, decision)),
            "components": {
                "authority": assessment.authority_score,
                "originality": assessment.originality_score,
                "directness": assessment.directness_score,
                "recency": assessment.recency_score,
                "corroboration": assessment.corroboration_score,
            },
        },
    )
    return assessment
