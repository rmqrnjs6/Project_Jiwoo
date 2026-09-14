from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import JSON, CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CaseStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class EvidenceSourceType(str, Enum):
    PRIMARY = "PRIMARY"
    OFFICIAL = "OFFICIAL"
    INSTITUTIONAL = "INSTITUTIONAL"
    NEWS = "NEWS"
    WEB = "WEB"
    USER = "USER"
    AI = "AI"
    UNKNOWN = "UNKNOWN"


class SourceVerificationStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    VERIFIED = "VERIFIED"
    DISPUTED = "DISPUTED"
    INVALID = "INVALID"


class JudgmentOrigin(str, Enum):
    MANUAL = "MANUAL"
    AI_ENGINE = "AI_ENGINE"


class ReevaluationTrigger(str, Enum):
    INITIAL = "INITIAL"
    USER_REQUEST = "USER_REQUEST"
    INPUT_CHANGED = "INPUT_CHANGED"
    NEW_EVIDENCE = "NEW_EVIDENCE"
    SOURCE_REVIEWED = "SOURCE_REVIEWED"
    SOURCE_VERIFIED = "SOURCE_VERIFIED"
    SOURCE_DISPROVED = "SOURCE_DISPROVED"
    RULE_CHANGED = "RULE_CHANGED"
    MODEL_CHANGED = "MODEL_CHANGED"
    GRACE_PERIOD_EXPIRED = "GRACE_PERIOD_EXPIRED"


class JudgmentConclusion(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNCERTAIN = "UNCERTAIN"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class AIPosition(str, Enum):
    AGREE = "AGREE"
    DISAGREE = "DISAGREE"
    UNSURE = "UNSURE"


class ResolutionState(str, Enum):
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"
    PENDING = "PENDING"


class ContextMode(str, Enum):
    DECLARED_PERSONAL = "DECLARED_PERSONAL"
    ROLEPLAY_DECLARED = "ROLEPLAY_DECLARED"
    FICTION_DECLARED = "FICTION_DECLARED"
    QUOTED_CONTENT = "QUOTED_CONTENT"
    AMBIGUOUS_CONTEXT = "AMBIGUOUS_CONTEXT"


class NudgeLevel(str, Enum):
    NONE = "NONE"
    SOFT = "SOFT"
    EXPLICIT = "EXPLICIT"
    SAFETY = "SAFETY"


class DeliveryStyle(str, Enum):
    NONE = "NONE"
    SUBTLE = "SUBTLE"
    CLEAR = "CLEAR"
    DIRECT_SAFETY = "DIRECT_SAFETY"


class ActionType(str, Enum):
    SET_CASE_STATUS = "SET_CASE_STATUS"
    SET_CASE_TITLE = "SET_CASE_TITLE"


class ActionStatus(str, Enum):
    ATTEMPTED = "ATTEMPTED"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ActionBlockReason(str, Enum):
    EXECUTION_DISABLED = "EXECUTION_DISABLED"
    SCOPE_DENIED = "SCOPE_DENIED"
    STALE_JUDGMENT = "STALE_JUDGMENT"
    JUDGMENT_NOT_RESOLVED = "JUDGMENT_NOT_RESOLVED"
    INVALID_PARAMETERS = "INVALID_PARAMETERS"


class HistoryEventType(str, Enum):
    INPUT_CREATED = "INPUT_CREATED"
    INPUT_UPDATED = "INPUT_UPDATED"
    EVIDENCE_ADDED = "EVIDENCE_ADDED"
    EVIDENCE_REJECTED = "EVIDENCE_REJECTED"
    EVIDENCE_CANDIDATES_DISCOVERED = "EVIDENCE_CANDIDATES_DISCOVERED"
    EVIDENCE_CANDIDATE_ADOPTED = "EVIDENCE_CANDIDATE_ADOPTED"
    REPRESENTATIVE_EVIDENCE_SELECTED = "REPRESENTATIVE_EVIDENCE_SELECTED"
    DUPLICATE_EVIDENCE_DETECTED = "DUPLICATE_EVIDENCE_DETECTED"
    JUDGMENT_CREATED = "JUDGMENT_CREATED"
    JUDGMENT_REVISED = "JUDGMENT_REVISED"
    JUDGMENT_REAFFIRMED = "JUDGMENT_REAFFIRMED"
    JUDGMENT_FAILED = "JUDGMENT_FAILED"
    CONTEXT_ASSESSED = "CONTEXT_ASSESSED"
    NUDGE_GENERATED = "NUDGE_GENERATED"
    FEATURE_ACCESS_BLOCKED = "FEATURE_ACCESS_BLOCKED"
    RESPONSE_COMPOSED = "RESPONSE_COMPOSED"
    PERMISSION_CHANGED = "PERMISSION_CHANGED"
    ACTION_ATTEMPTED = "ACTION_ATTEMPTED"
    ACTION_BLOCKED = "ACTION_BLOCKED"
    ACTION_COMPLETED = "ACTION_COMPLETED"
    ACTION_FAILED = "ACTION_FAILED"
    RELIABILITY_ASSESSED = "RELIABILITY_ASSESSED"
    RELIABILITY_REVISED = "RELIABILITY_REVISED"
    RELIABILITY_REAFFIRMED = "RELIABILITY_REAFFIRMED"
    SOURCE_VERIFICATION_ASSESSED = "SOURCE_VERIFICATION_ASSESSED"
    SOURCE_VERIFICATION_REVISED = "SOURCE_VERIFICATION_REVISED"
    SOURCE_VERIFICATION_REAFFIRMED = "SOURCE_VERIFICATION_REAFFIRMED"
    REEVALUATION_STARTED = "REEVALUATION_STARTED"
    REEVALUATION_COMPLETED = "REEVALUATION_COMPLETED"
    AI_CALL_SKIPPED = "AI_CALL_SKIPPED"


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    original_input: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[CaseStatus] = mapped_column(SAEnum(CaseStatus), default=CaseStatus.OPEN, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    evidence: Mapped[list["Evidence"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    evidence_candidates: Mapped[list["EvidenceCandidate"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    judgments: Mapped[list["Judgment"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        foreign_keys="Judgment.case_id",
    )
    support_assessments: Mapped[list["SupportAssessment"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    history: Mapped[list["HistoryEvent"]] = relationship(back_populates="case", passive_deletes=True)
    permission_policy: Mapped["PermissionPolicy | None"] = relationship(
        back_populates="case", cascade="all, delete-orphan", uselist=False
    )
    actions: Mapped[list["ActionAttempt"]] = relationship(back_populates="case", cascade="all, delete-orphan")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Source metadata supplied at ingestion is a CLAIM until independently verified.
    claimed_source_type: Mapped[EvidenceSourceType] = mapped_column(
        "source_type", SAEnum(EvidenceSourceType), nullable=False
    )
    claimed_is_primary_source: Mapped[bool] = mapped_column(
        "is_primary_source", default=False, nullable=False
    )
    source_verification_status: Mapped[SourceVerificationStatus] = mapped_column(
        SAEnum(SourceVerificationStatus), default=SourceVerificationStatus.UNVERIFIED, nullable=False
    )
    verified_source_type: Mapped[EvidenceSourceType | None] = mapped_column(
        SAEnum(EvidenceSourceType), nullable=True
    )
    verified_is_primary_source: Mapped[bool | None] = mapped_column(nullable=True)

    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    reliability_score: Mapped[float | None] = mapped_column(nullable=True)
    reliability_source: Mapped[str] = mapped_column(String(50), default="UNASSESSED", nullable=False)
    source_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    @property
    def effective_source_type(self) -> EvidenceSourceType:
        if (
            self.source_verification_status == SourceVerificationStatus.VERIFIED
            and self.verified_source_type is not None
        ):
            return self.verified_source_type
        return self.claimed_source_type

    @property
    def effective_is_primary_source(self) -> bool:
        if (
            self.source_verification_status == SourceVerificationStatus.VERIFIED
            and self.verified_is_primary_source is not None
        ):
            return self.verified_is_primary_source
        return self.claimed_is_primary_source

    case: Mapped[Case] = relationship(back_populates="evidence")
    reliability_assessments: Mapped[list["ReliabilityAssessment"]] = relationship(
        back_populates="evidence", cascade="all, delete-orphan"
    )
    source_verifications: Mapped[list["SourceVerification"]] = relationship(
        back_populates="evidence", cascade="all, delete-orphan"
    )


class EvidenceCandidate(Base):
    """Temporary, reviewable evidence discovered before the user adopts it.

    Candidates are deliberately separate from Evidence. A discovered web result does
    not become judgment evidence until the user explicitly adopts it.
    """

    __tablename__ = "evidence_candidates"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    source_type: Mapped[EvidenceSourceType] = mapped_column(SAEnum(EvidenceSourceType), nullable=False)
    source_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    relation_to_claim: Mapped[str] = mapped_column(String(32), default="UNKNOWN", nullable=False)
    reliability_score: Mapped[float] = mapped_column(nullable=False)
    score_components: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    source_verification_status: Mapped[SourceVerificationStatus] = mapped_column(
        SAEnum(SourceVerificationStatus), default=SourceVerificationStatus.PARTIALLY_VERIFIED, nullable=False
    )
    is_representative: Mapped[bool] = mapped_column(default=False, nullable=False)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    origin: Mapped[str] = mapped_column(String(40), default="WEB_SEARCH", nullable=False)
    adopted_evidence_id: Mapped[int | None] = mapped_column(
        ForeignKey("evidence.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    case: Mapped[Case] = relationship(back_populates="evidence_candidates")
    adopted_evidence: Mapped[Evidence | None] = relationship(foreign_keys=[adopted_evidence_id])


class SourceVerification(Base):
    __tablename__ = "source_verifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), index=True, nullable=False)
    revision_no: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[SourceVerificationStatus] = mapped_column(SAEnum(SourceVerificationStatus), nullable=False)
    verified_source_type: Mapped[EvidenceSourceType | None] = mapped_column(SAEnum(EvidenceSourceType), nullable=True)
    verified_is_primary_source: Mapped[bool | None] = mapped_column(nullable=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    checks: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    method_version: Mapped[str] = mapped_column(String(80), nullable=False)
    actor: Mapped[str] = mapped_column(String(50), default="SYSTEM", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    evidence: Mapped[Evidence] = relationship(back_populates="source_verifications")


class ReliabilityAssessment(Base):
    __tablename__ = "reliability_assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), index=True, nullable=False)
    revision_no: Mapped[int] = mapped_column(nullable=False)
    authority_score: Mapped[float] = mapped_column(nullable=False)
    originality_score: Mapped[float] = mapped_column(nullable=False)
    directness_score: Mapped[float] = mapped_column(nullable=False)
    recency_score: Mapped[float] = mapped_column(nullable=False)
    corroboration_score: Mapped[float] = mapped_column(nullable=False)
    conflict_penalty: Mapped[float] = mapped_column(nullable=False)
    final_score: Mapped[float] = mapped_column(nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    method_version: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    evidence: Mapped[Evidence] = relationship(back_populates="reliability_assessments")


class Judgment(Base):
    __tablename__ = "judgments"
    __table_args__ = (
        CheckConstraint(
            "(conclusion = 'SUPPORTED' AND ai_position = 'AGREE') OR "
            "(conclusion = 'CONTRADICTED' AND ai_position = 'DISAGREE') OR "
            "(conclusion IN ('UNCERTAIN', 'INSUFFICIENT_EVIDENCE') AND ai_position = 'UNSURE')",
            name="ck_judgment_position_consistency",
        ),
        CheckConstraint(
            "(resolution_state = 'RESOLVED' AND conclusion IN ('SUPPORTED', 'CONTRADICTED')) OR "
            "(resolution_state IN ('UNRESOLVED', 'PENDING') AND conclusion IN ('UNCERTAIN', 'INSUFFICIENT_EVIDENCE'))",
            name="ck_judgment_resolution_consistency",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False)
    previous_judgment_id: Mapped[int | None] = mapped_column(ForeignKey("judgments.id"), nullable=True)
    revision_no: Mapped[int] = mapped_column(nullable=False)

    conclusion: Mapped[JudgmentConclusion] = mapped_column(SAEnum(JudgmentConclusion), nullable=False)
    ai_position: Mapped[AIPosition] = mapped_column(SAEnum(AIPosition), nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    resolution_state: Mapped[ResolutionState] = mapped_column(SAEnum(ResolutionState), nullable=False)

    position_text: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning_summary: Mapped[str] = mapped_column(Text, nullable=False)
    unresolved_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    waiting_for: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_assessments: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    origin: Mapped[JudgmentOrigin] = mapped_column(SAEnum(JudgmentOrigin), nullable=False)
    actor: Mapped[str] = mapped_column(String(50), nullable=False)
    reevaluation_trigger: Mapped[ReevaluationTrigger | None] = mapped_column(
        SAEnum(ReevaluationTrigger), nullable=True
    )
    decision_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    decision_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    case: Mapped[Case] = relationship(back_populates="judgments", foreign_keys=[case_id])
    previous_judgment: Mapped["Judgment | None"] = relationship(remote_side=[id], foreign_keys=[previous_judgment_id])


class SupportAssessment(Base):
    __tablename__ = "support_assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    expression_summary: Mapped[str] = mapped_column(Text, nullable=False)
    affect_signals: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    context_mode: Mapped[ContextMode] = mapped_column(SAEnum(ContextMode), nullable=False)
    context_rationale: Mapped[str] = mapped_column(Text, nullable=False)
    nudge_level: Mapped[NudgeLevel] = mapped_column(SAEnum(NudgeLevel), nullable=False)
    delivery_style: Mapped[DeliveryStyle] = mapped_column(SAEnum(DeliveryStyle), nullable=False)
    recommendation_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale_summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    case: Mapped[Case] = relationship(back_populates="support_assessments")


class PermissionPolicy(Base):
    __tablename__ = "permission_policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    can_execute: Mapped[bool] = mapped_column(default=False, nullable=False)
    allowed_actions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    case: Mapped[Case] = relationship(back_populates="permission_policy")


class ActionAttempt(Base):
    __tablename__ = "action_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False
    )
    judgment_id: Mapped[int] = mapped_column(ForeignKey("judgments.id"), index=True, nullable=False)
    action_type: Mapped[ActionType] = mapped_column(SAEnum(ActionType), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[ActionStatus] = mapped_column(SAEnum(ActionStatus), nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    blocked_reason: Mapped[ActionBlockReason | None] = mapped_column(SAEnum(ActionBlockReason), nullable=True)
    actor: Mapped[str] = mapped_column(String(50), default="AI", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    case: Mapped[Case] = relationship(back_populates="actions")
    judgment: Mapped[Judgment] = relationship(foreign_keys=[judgment_id])


class HistoryEvent(Base):
    __tablename__ = "history_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="RESTRICT"), index=True, nullable=False)
    event_type: Mapped[HistoryEventType] = mapped_column(SAEnum(HistoryEventType), index=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(nullable=True)
    actor: Mapped[str] = mapped_column(String(50), default="SYSTEM", nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    case: Mapped[Case] = relationship(back_populates="history")


# History is preservation-oriented: corrections are appended as new events.
# ORM updates/deletes of existing history rows are rejected.
@event.listens_for(HistoryEvent, "before_update")
def _prevent_history_update(mapper, connection, target):
    raise RuntimeError("HistoryEvent is append-only; record a new correction event instead")


@event.listens_for(HistoryEvent, "before_delete")
def _prevent_history_delete(mapper, connection, target):
    raise RuntimeError("HistoryEvent cannot be deleted through the ORM")
