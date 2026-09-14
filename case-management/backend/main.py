from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .database import Base, engine, get_db, check_database_ready, database_backend_name
from .action_engine import execute_action, get_or_create_permission, set_permission
from .evidence_discovery import (
    EvidenceDiscoveryProvider,
    candidate_components,
    candidate_score,
    get_demo_evidence_discovery_provider,
    get_evidence_discovery_provider,
)
from .judgment_engine import JudgmentProvider, JudgmentProviderError, get_judgment_provider
from .reliability_engine import ReliabilityProvider, get_reliability_provider
from .source_verification import SourceVerificationProvider, get_source_verification_provider
from .models import (
    ActionAttempt,
    Case,
    Evidence,
    EvidenceCandidate,
    HistoryEvent,
    HistoryEventType,
    Judgment,
    JudgmentOrigin,
    ReevaluationTrigger,
    ReliabilityAssessment,
    SourceVerification,
    SupportAssessment,
    SourceVerificationStatus,
)
from .release import Feature, feature_enabled, release_snapshot
from .response_composer import compose_response
from .schemas import (
    ActionExecuteRequest,
    ActionRead,
    CaseCreate,
    CaseRead,
    CaseSummaryRead,
    EvidenceCreate,
    EvidenceCandidateBatchRead,
    EvidenceCandidateRead,
    EvidenceDiscoveryRequest,
    EvidenceRead,
    HistoryRead,
    JudgmentCreate,
    JudgmentRead,
    PermissionRead,
    PermissionUpdate,
    ReliabilityAssessmentRead,
    SourceVerificationRead,
    SupportAssessmentRead,
    TimelineItemRead,
    ReleaseRead,
    ResponseCompositionRead,
)
from .services import (
    append_history,
    build_decision_snapshot,
    create_judgment,
    create_reliability_assessment,
    create_source_verification,
    create_support_assessment,
    decision_fingerprint,
    infer_reevaluation_trigger,
    judgment_create_from_engine,
)
from .support_engine import SupportProvider, get_support_provider
from .timeline import build_user_timeline

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Judgment API", version="1.0.0-rc6")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/", include_in_schema=False)
def web_app():
    index = FRONTEND_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="Frontend not installed")
    return FileResponse(index)


@app.get("/app", include_in_schema=False)
def web_app_alias():
    return web_app()


def require_feature(
    db: Session,
    *,
    case_id: int,
    feature: Feature,
) -> None:
    if feature_enabled(feature):
        return

    snapshot = release_snapshot()
    append_history(
        db,
        case_id=case_id,
        event_type=HistoryEventType.FEATURE_ACCESS_BLOCKED,
        entity_type="FEATURE",
        entity_id=None,
        actor="SYSTEM",
        payload={
            "feature": feature.value,
            "release_profile": snapshot["profile"],
        },
    )
    db.commit()
    raise HTTPException(
        status_code=403,
        detail={
            "code": "FEATURE_LOCKED",
            "feature": feature.value,
            "release_profile": snapshot["profile"],
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}




@app.get("/ready")
def readiness(provider: JudgmentProvider = Depends(get_judgment_provider)):
    db_ready, db_error = check_database_ready()
    payload = {
        "ready": db_ready,
        "database": {"ready": db_ready, "backend": database_backend_name()},
        "ai": {
            "configured": provider.configured,
            "provider": provider.provider_name,
            "model": provider.model_name,
            "required_for_core_readiness": False,
        },
    }
    if db_error:
        payload["database"]["error_code"] = db_error
    if not db_ready:
        raise HTTPException(status_code=503, detail=payload)
    return payload


@app.get("/system/status")
def system_status(provider: JudgmentProvider = Depends(get_judgment_provider)) -> dict:
    release = release_snapshot()
    return {
        "version": app.version,
        "release_profile": release["profile"],
        "database_backend": database_backend_name(),
        "ai_provider": provider.provider_name,
        "ai_configured": provider.configured,
        "ai_model": provider.model_name,
        "paid_live_check_performed": False,
    }


@app.get("/ai/status")
def ai_status(provider: JudgmentProvider = Depends(get_judgment_provider)) -> dict:
    return {
        "provider": provider.provider_name,
        "configured": provider.configured,
        "model": provider.model_name,
        "live_check_performed": False,
    }


@app.get("/cases", response_model=list[CaseSummaryRead])
def list_cases(db: Session = Depends(get_db)) -> list[Case]:
    stmt = select(Case).order_by(Case.created_at.desc(), Case.id.desc())
    return list(db.scalars(stmt).all())


@app.post("/cases", response_model=CaseRead, status_code=status.HTTP_201_CREATED)
def create_case(payload: CaseCreate, db: Session = Depends(get_db)) -> Case:
    case = Case(title=payload.title, original_input=payload.original_input)
    db.add(case)
    db.flush()

    append_history(
        db,
        case_id=case.id,
        event_type=HistoryEventType.INPUT_CREATED,
        entity_type="CASE",
        entity_id=case.id,
        actor="USER",
        payload={"title": case.title, "original_input": case.original_input},
    )

    db.commit()
    return get_case(case.id, db)


@app.get("/cases/{case_id}", response_model=CaseRead)
def get_case(case_id: int, db: Session = Depends(get_db)) -> CaseRead:
    stmt = (
        select(Case)
        .options(
            selectinload(Case.evidence),
            selectinload(Case.judgments),
            selectinload(Case.support_assessments),
        )
        .where(Case.id == case_id)
    )
    case = db.scalar(stmt)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    result = CaseRead.model_validate(case)
    if not feature_enabled(Feature.CONTEXTUAL_NUDGE):
        result.support_assessments = []
    return result



def _active_evidence_candidates(db: Session, case_id: int) -> list[EvidenceCandidate]:
    stmt = (
        select(EvidenceCandidate)
        .where(EvidenceCandidate.case_id == case_id, EvidenceCandidate.active.is_(True))
        .order_by(
            EvidenceCandidate.is_representative.desc(),
            EvidenceCandidate.reliability_score.desc(),
            EvidenceCandidate.id.asc(),
        )
    )
    return list(db.scalars(stmt).all())


def _persist_evidence_candidate_batch(
    db: Session,
    *,
    case: Case,
    drafts,
    origin: str,
) -> list[EvidenceCandidate]:
    # Candidate recommendations are review material, not permanent Evidence.
    # A new discovery batch deactivates the previous review set while preserving
    # already adopted Evidence as normal case history.
    previous = list(
        db.scalars(
            select(EvidenceCandidate).where(
                EvidenceCandidate.case_id == case.id,
                EvidenceCandidate.active.is_(True),
            )
        ).all()
    )
    for item in previous:
        item.active = False
        item.is_representative = False

    unique = []
    seen_urls: set[str] = set()
    for draft in drafts:
        url = str(draft.source_url)
        key = url.strip().casefold()
        if key in seen_urls:
            continue
        seen_urls.add(key)
        unique.append((draft, candidate_score(draft)))

    if not unique:
        raise HTTPException(status_code=502, detail="No usable evidence candidates were returned")

    unique.sort(key=lambda pair: pair[1], reverse=True)
    created: list[EvidenceCandidate] = []
    for index, (draft, score) in enumerate(unique):
        item = EvidenceCandidate(
            case_id=case.id,
            title=draft.title,
            summary=draft.summary,
            source_name=draft.source_name,
            source_url=str(draft.source_url),
            source_type=draft.source_type,
            source_published_at=draft.source_published_at,
            relation_to_claim=draft.relation_to_claim,
            reliability_score=score,
            score_components=candidate_components(draft),
            rationale=draft.rationale,
            source_verification_status=(
                SourceVerificationStatus.UNVERIFIED
                if origin == "DEMO"
                else SourceVerificationStatus.PARTIALLY_VERIFIED
            ),
            is_representative=(index == 0),
            active=True,
            origin=origin,
        )
        db.add(item)
        created.append(item)

    db.flush()
    representative = created[0]
    append_history(
        db,
        case_id=case.id,
        event_type=HistoryEventType.EVIDENCE_CANDIDATES_DISCOVERED,
        entity_type="EVIDENCE_CANDIDATE",
        entity_id=representative.id,
        actor="AI" if origin == "WEB_SEARCH" else "SYSTEM",
        payload={
            "count": len(created),
            "origin": origin,
            "representative_candidate_id": representative.id,
            "representative_score": representative.reliability_score,
        },
    )
    append_history(
        db,
        case_id=case.id,
        event_type=HistoryEventType.REPRESENTATIVE_EVIDENCE_SELECTED,
        entity_type="EVIDENCE_CANDIDATE",
        entity_id=representative.id,
        actor="SYSTEM",
        payload={
            "candidate_id": representative.id,
            "title": representative.title,
            "source_name": representative.source_name,
            "score": representative.reliability_score,
            "origin": origin,
            "note": "Representative means strongest current candidate, not guaranteed truth.",
        },
    )
    db.commit()
    for item in created:
        db.refresh(item)
    return created


@app.get(
    "/cases/{case_id}/evidence-candidates",
    response_model=EvidenceCandidateBatchRead,
)
def list_evidence_candidates(case_id: int, db: Session = Depends(get_db)) -> dict:
    if db.get(Case, case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    items = _active_evidence_candidates(db, case_id)
    representative = next((item for item in items if item.is_representative), None)
    origin = items[0].origin if items else "NONE"
    return {
        "candidates": items,
        "representative_id": representative.id if representative else None,
        "origin": origin,
        "disclaimer": (
            "이 신뢰도는 사실일 확률이 아니라, 현재 확인된 출처·원본성·직접성·최신성·교차검토 기준의 평가값입니다."
        ),
    }


@app.post(
    "/cases/{case_id}/evidence-candidates/discover",
    response_model=EvidenceCandidateBatchRead,
    status_code=status.HTTP_201_CREATED,
)
def discover_evidence_candidates(
    case_id: int,
    payload: EvidenceDiscoveryRequest,
    db: Session = Depends(get_db),
    provider: EvidenceDiscoveryProvider = Depends(get_evidence_discovery_provider),
) -> dict:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    try:
        drafts = provider.discover(case=case, limit=payload.limit)
    except JudgmentProviderError as exc:
        raise HTTPException(status_code=exc.http_status, detail=exc.as_detail()) from exc

    items = _persist_evidence_candidate_batch(
        db,
        case=case,
        drafts=drafts,
        origin="WEB_SEARCH",
    )
    representative = next((item for item in items if item.is_representative), None)
    return {
        "candidates": items,
        "representative_id": representative.id if representative else None,
        "origin": "WEB_SEARCH",
        "disclaimer": (
            "추천 결과와 신뢰도는 검수 보조 정보입니다. 대표 근거는 현재 후보 중 가장 강한 하나일 뿐 절대적인 사실을 의미하지 않습니다."
        ),
    }


@app.post(
    "/cases/{case_id}/evidence-candidates/demo",
    response_model=EvidenceCandidateBatchRead,
    status_code=status.HTTP_201_CREATED,
)
def demo_evidence_candidates(
    case_id: int,
    payload: EvidenceDiscoveryRequest,
    db: Session = Depends(get_db),
    provider: EvidenceDiscoveryProvider = Depends(get_demo_evidence_discovery_provider),
) -> dict:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    drafts = provider.discover(case=case, limit=payload.limit)
    items = _persist_evidence_candidate_batch(
        db,
        case=case,
        drafts=drafts,
        origin="DEMO",
    )
    representative = next((item for item in items if item.is_representative), None)
    return {
        "candidates": items,
        "representative_id": representative.id if representative else None,
        "origin": "DEMO",
        "disclaimer": (
            "현재 목록은 UI 테스트용 데모 데이터입니다. 실제 출처나 사실 검증 결과가 아니며 AI 판단에 사용하면 안 됩니다."
        ),
    }


@app.post(
    "/cases/{case_id}/evidence-candidates/{candidate_id}/adopt",
    response_model=EvidenceRead,
    status_code=status.HTTP_201_CREATED,
)
def adopt_evidence_candidate(
    case_id: int,
    candidate_id: int,
    response: Response,
    db: Session = Depends(get_db),
) -> Evidence:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    candidate = db.get(EvidenceCandidate, candidate_id)
    if candidate is None or candidate.case_id != case_id:
        raise HTTPException(status_code=404, detail="Evidence candidate not found for this case")
    if not candidate.active:
        raise HTTPException(status_code=409, detail="This evidence candidate is no longer in the active review set")

    if candidate.adopted_evidence_id is not None:
        existing = db.get(Evidence, candidate.adopted_evidence_id)
        if existing is not None:
            response.status_code = status.HTTP_200_OK
            return existing

    same_source = db.scalar(
        select(Evidence)
        .where(Evidence.case_id == case_id, Evidence.source_url == candidate.source_url)
        .order_by(Evidence.id.asc())
        .limit(1)
    )
    if same_source is not None:
        candidate.adopted_evidence_id = same_source.id
        db.commit()
        db.refresh(same_source)
        response.status_code = status.HTTP_200_OK
        return same_source

    is_demo = candidate.origin == "DEMO"
    content = candidate.summary
    if is_demo:
        content = "[DEMO - 실제 근거 아님] " + content

    evidence = Evidence(
        case_id=case_id,
        content=content,
        claimed_source_type=(candidate.source_type if not is_demo else candidate.source_type),
        claimed_is_primary_source=(candidate.source_type.value in {"PRIMARY", "OFFICIAL"}),
        source_verification_status=(
            SourceVerificationStatus.UNVERIFIED
            if is_demo
            else SourceVerificationStatus.PARTIALLY_VERIFIED
        ),
        source_url=candidate.source_url,
        source_published_at=candidate.source_published_at,
        reliability_score=(min(candidate.reliability_score, 0.30) if is_demo else candidate.reliability_score),
        reliability_source=("DEMO_CANDIDATE" if is_demo else "candidate-ranking-v1"),
    )
    db.add(evidence)
    db.flush()
    candidate.adopted_evidence_id = evidence.id

    append_history(
        db,
        case_id=case_id,
        event_type=HistoryEventType.EVIDENCE_CANDIDATE_ADOPTED,
        entity_type="EVIDENCE",
        entity_id=evidence.id,
        actor="USER",
        payload={
            "candidate_id": candidate.id,
            "candidate_origin": candidate.origin,
            "source_name": candidate.source_name,
            "source_url": candidate.source_url,
            "candidate_score": candidate.reliability_score,
            "representative": candidate.is_representative,
        },
    )
    append_history(
        db,
        case_id=case_id,
        event_type=HistoryEventType.EVIDENCE_ADDED,
        entity_type="EVIDENCE",
        entity_id=evidence.id,
        actor="USER",
        payload={
            "claimed_source_type": evidence.claimed_source_type.value,
            "source_verification_status": evidence.source_verification_status.value,
            "source_url": evidence.source_url,
            "claimed_is_primary_source": evidence.claimed_is_primary_source,
            "reliability_score": evidence.reliability_score,
            "reliability_source": evidence.reliability_source,
            "candidate_id": candidate.id,
            "candidate_origin": candidate.origin,
            "source_published_at": (
                evidence.source_published_at.isoformat() if evidence.source_published_at else None
            ),
        },
    )
    db.commit()
    db.refresh(evidence)
    return evidence


@app.post(
    "/cases/{case_id}/evidence",
    response_model=EvidenceRead,
    status_code=status.HTTP_201_CREATED,
)
def add_evidence(case_id: int, payload: EvidenceCreate, db: Session = Depends(get_db)) -> Evidence:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    normalized_content = " ".join(payload.content.split()).casefold()
    normalized_url = str(payload.source_url) if payload.source_url else None
    existing_evidence = list(
        db.scalars(select(Evidence).where(Evidence.case_id == case_id)).all()
    )
    duplicate = next(
        (
            item
            for item in existing_evidence
            if " ".join(item.content.split()).casefold() == normalized_content
            and item.source_url == normalized_url
        ),
        None,
    )
    if duplicate is not None:
        append_history(
            db,
            case_id=case_id,
            event_type=HistoryEventType.DUPLICATE_EVIDENCE_DETECTED,
            entity_type="EVIDENCE",
            entity_id=duplicate.id,
            actor="USER",
            payload={
                "existing_evidence_id": duplicate.id,
                "attempted_content": payload.content,
                "attempted_source_url": normalized_url,
                "claimed_source_type": payload.source_type.value,
            },
        )
        db.commit()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "DUPLICATE_EVIDENCE",
                "existing_evidence_id": duplicate.id,
            },
        )

    evidence = Evidence(
        case_id=case_id,
        content=payload.content,
        claimed_source_type=payload.source_type,
        source_url=str(payload.source_url) if payload.source_url else None,
        claimed_is_primary_source=payload.is_primary_source,
        reliability_score=payload.reliability_score,
        reliability_source=("USER_PROVIDED" if payload.reliability_score is not None else "UNASSESSED"),
        source_published_at=payload.source_published_at,
    )
    db.add(evidence)
    db.flush()

    append_history(
        db,
        case_id=case_id,
        event_type=HistoryEventType.EVIDENCE_ADDED,
        entity_type="EVIDENCE",
        entity_id=evidence.id,
        actor="USER",
        payload={
            "claimed_source_type": evidence.claimed_source_type.value,
            "source_verification_status": evidence.source_verification_status.value,
            "source_url": evidence.source_url,
            "claimed_is_primary_source": evidence.claimed_is_primary_source,
            "reliability_score": evidence.reliability_score,
            "reliability_source": evidence.reliability_source,
            "source_published_at": (
                evidence.source_published_at.isoformat() if evidence.source_published_at else None
            ),
        },
    )

    db.commit()
    db.refresh(evidence)
    return evidence


@app.post(
    "/cases/{case_id}/evidence/{evidence_id}/verify-source",
    response_model=SourceVerificationRead,
    status_code=status.HTTP_201_CREATED,
)
def verify_evidence_source(
    case_id: int,
    evidence_id: int,
    db: Session = Depends(get_db),
    provider: SourceVerificationProvider = Depends(get_source_verification_provider),
    reliability_provider: ReliabilityProvider = Depends(get_reliability_provider),
) -> SourceVerification:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    evidence = db.get(Evidence, evidence_id)
    if evidence is None or evidence.case_id != case_id:
        raise HTTPException(status_code=404, detail="Evidence not found for this case")

    decision = provider.verify(evidence=evidence)
    verification = create_source_verification(
        db, evidence=evidence, decision=decision, actor=provider.provider_name
    )

    # Source verification can change how much weight this evidence deserves.
    # Re-score locally now, but do not trigger a paid AI judgment automatically.
    peers = list(
        db.scalars(
            select(Evidence)
            .where(Evidence.case_id == case_id, Evidence.id != evidence_id)
            .order_by(Evidence.created_at.asc(), Evidence.id.asc())
        ).all()
    )
    reliability_decision = reliability_provider.assess(
        case=case, evidence=evidence, peer_evidence=peers
    )
    create_reliability_assessment(
        db, evidence=evidence, decision=reliability_decision, actor="SYSTEM"
    )

    db.commit()
    db.refresh(verification)
    return verification


@app.get(
    "/cases/{case_id}/evidence/{evidence_id}/source-verifications",
    response_model=list[SourceVerificationRead],
)
def get_source_verification_history(
    case_id: int, evidence_id: int, db: Session = Depends(get_db)
) -> list[SourceVerification]:
    if db.get(Case, case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    evidence = db.get(Evidence, evidence_id)
    if evidence is None or evidence.case_id != case_id:
        raise HTTPException(status_code=404, detail="Evidence not found for this case")

    stmt = (
        select(SourceVerification)
        .where(SourceVerification.evidence_id == evidence_id)
        .order_by(SourceVerification.revision_no.asc())
    )
    return list(db.scalars(stmt).all())


@app.post(
    "/cases/{case_id}/evidence/{evidence_id}/assess-reliability",
    response_model=ReliabilityAssessmentRead,
    status_code=status.HTTP_201_CREATED,
)
def assess_evidence_reliability(
    case_id: int,
    evidence_id: int,
    db: Session = Depends(get_db),
    provider: ReliabilityProvider = Depends(get_reliability_provider),
) -> ReliabilityAssessment:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    evidence = db.get(Evidence, evidence_id)
    if evidence is None or evidence.case_id != case_id:
        raise HTTPException(status_code=404, detail="Evidence not found for this case")

    peers = list(
        db.scalars(
            select(Evidence)
            .where(Evidence.case_id == case_id, Evidence.id != evidence_id)
            .order_by(Evidence.created_at.asc(), Evidence.id.asc())
        ).all()
    )

    decision = provider.assess(case=case, evidence=evidence, peer_evidence=peers)
    assessment = create_reliability_assessment(
        db, evidence=evidence, decision=decision, actor="SYSTEM"
    )
    db.commit()
    db.refresh(assessment)
    return assessment


@app.post(
    "/cases/{case_id}/assess-reliability",
    response_model=list[ReliabilityAssessmentRead],
    status_code=status.HTTP_201_CREATED,
)
def assess_case_reliability(
    case_id: int,
    db: Session = Depends(get_db),
    provider: ReliabilityProvider = Depends(get_reliability_provider),
) -> list[ReliabilityAssessment]:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    evidence_items = list(
        db.scalars(
            select(Evidence)
            .where(Evidence.case_id == case_id)
            .order_by(Evidence.created_at.asc(), Evidence.id.asc())
        ).all()
    )
    if not evidence_items:
        raise HTTPException(status_code=409, detail="Cannot assess reliability without evidence")

    assessments: list[ReliabilityAssessment] = []
    for evidence in evidence_items:
        peers = [item for item in evidence_items if item.id != evidence.id]
        decision = provider.assess(case=case, evidence=evidence, peer_evidence=peers)
        assessments.append(
            create_reliability_assessment(
                db, evidence=evidence, decision=decision, actor="SYSTEM"
            )
        )

    db.commit()
    for assessment in assessments:
        db.refresh(assessment)
    return assessments


@app.get(
    "/cases/{case_id}/evidence/{evidence_id}/reliability",
    response_model=list[ReliabilityAssessmentRead],
)
def get_evidence_reliability_history(
    case_id: int, evidence_id: int, db: Session = Depends(get_db)
) -> list[ReliabilityAssessment]:
    if db.get(Case, case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    evidence = db.get(Evidence, evidence_id)
    if evidence is None or evidence.case_id != case_id:
        raise HTTPException(status_code=404, detail="Evidence not found for this case")

    stmt = (
        select(ReliabilityAssessment)
        .where(ReliabilityAssessment.evidence_id == evidence_id)
        .order_by(ReliabilityAssessment.revision_no.asc())
    )
    return list(db.scalars(stmt).all())


@app.post(
    "/cases/{case_id}/judgments",
    response_model=JudgmentRead,
    status_code=status.HTTP_201_CREATED,
)
def add_judgment(case_id: int, payload: JudgmentCreate, db: Session = Depends(get_db)) -> Judgment:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    evidence = list(
        db.scalars(
            select(Evidence)
            .where(Evidence.case_id == case_id)
            .order_by(Evidence.created_at.asc(), Evidence.id.asc())
        ).all()
    )
    snapshot = build_decision_snapshot(
        case=case,
        evidence=evidence,
        provider_name="manual",
        model_name=None,
    )
    fingerprint = decision_fingerprint(snapshot)

    judgment = create_judgment(
        db,
        case_id=case_id,
        payload=payload,
        origin=JudgmentOrigin.MANUAL,
        actor="USER",
        decision_snapshot=snapshot,
        decision_fingerprint_value=fingerprint,
    )
    db.commit()
    db.refresh(judgment)
    return judgment


@app.post(
    "/cases/{case_id}/judge",
    response_model=JudgmentRead,
    status_code=status.HTTP_201_CREATED,
)
def judge_case(
    case_id: int,
    response: Response,
    force: bool = False,
    db: Session = Depends(get_db),
    provider: JudgmentProvider = Depends(get_judgment_provider),
) -> Judgment:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    evidence = list(
        db.scalars(
            select(Evidence)
            .where(Evidence.case_id == case_id)
            .order_by(Evidence.created_at.asc(), Evidence.id.asc())
        ).all()
    )

    if not evidence:
        raise HTTPException(status_code=409, detail="Cannot judge a case without evidence")

    if any(item.reliability_source == "DEMO_CANDIDATE" for item in evidence):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "DEMO_EVIDENCE_NOT_ALLOWED",
                "message": "UI demo candidates cannot be used for an AI judgment. Use real evidence instead.",
            },
        )

    previous = db.scalar(
        select(Judgment)
        .where(Judgment.case_id == case_id)
        .order_by(Judgment.revision_no.desc())
        .limit(1)
    )

    snapshot = build_decision_snapshot(
        case=case,
        evidence=evidence,
        provider_name=provider.provider_name,
        model_name=provider.model_name,
    )
    fingerprint = decision_fingerprint(snapshot)

    # Cost guard: if nothing relevant changed, reuse the existing AI judgment.
    if (
        not force
        and previous is not None
        and previous.origin == JudgmentOrigin.AI_ENGINE
        and previous.decision_fingerprint == fingerprint
    ):
        append_history(
            db,
            case_id=case_id,
            event_type=HistoryEventType.AI_CALL_SKIPPED,
            entity_type="JUDGMENT",
            entity_id=previous.id,
            actor="SYSTEM",
            payload={
                "reason": "NO_RELEVANT_CHANGE",
                "reused_judgment_id": previous.id,
                "decision_fingerprint": fingerprint,
                "provider": provider.provider_name,
                "model": provider.model_name,
                "saved_paid_call": True,
            },
        )
        db.commit()
        response.status_code = status.HTTP_200_OK
        return previous

    if force or (previous is not None and previous.origin == JudgmentOrigin.MANUAL):
        trigger = ReevaluationTrigger.USER_REQUEST if previous is not None else ReevaluationTrigger.INITIAL
    else:
        trigger = infer_reevaluation_trigger(previous, snapshot)

    try:
        decision = provider.judge(case=case, evidence=evidence)
    except JudgmentProviderError as exc:
        append_history(
            db,
            case_id=case_id,
            event_type=HistoryEventType.JUDGMENT_FAILED,
            entity_type="JUDGMENT",
            entity_id=None,
            actor="AI",
            payload={
                "provider": provider.provider_name,
                "model": provider.model_name,
                "error_code": exc.code,
                "retryable": exc.retryable,
                "request_id": exc.request_id,
                "trigger": trigger.value,
                "decision_fingerprint": fingerprint,
            },
        )
        db.commit()
        raise HTTPException(status_code=exc.http_status, detail=exc.as_detail()) from exc

    payload = judgment_create_from_engine(decision)
    judgment = create_judgment(
        db,
        case_id=case_id,
        payload=payload,
        origin=JudgmentOrigin.AI_ENGINE,
        actor="AI",
        reevaluation_trigger=trigger,
        decision_snapshot=snapshot,
        decision_fingerprint_value=fingerprint,
    )
    db.commit()
    db.refresh(judgment)
    return judgment


@app.post(
    "/cases/{case_id}/support-assess",
    response_model=SupportAssessmentRead,
    status_code=status.HTTP_201_CREATED,
)
def assess_support_context(
    case_id: int,
    db: Session = Depends(get_db),
    provider: SupportProvider = Depends(get_support_provider),
) -> SupportAssessment:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    require_feature(db, case_id=case_id, feature=Feature.CONTEXTUAL_NUDGE)

    try:
        decision = provider.assess(case=case)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    assessment = create_support_assessment(
        db,
        case_id=case_id,
        source_text=case.original_input,
        decision=decision,
    )
    db.commit()
    db.refresh(assessment)
    return assessment


@app.get("/cases/{case_id}/support-assessments", response_model=list[SupportAssessmentRead])
def get_support_assessments(case_id: int, db: Session = Depends(get_db)) -> list[SupportAssessment]:
    if db.get(Case, case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")

    require_feature(db, case_id=case_id, feature=Feature.CONTEXTUAL_NUDGE)

    stmt = (
        select(SupportAssessment)
        .where(SupportAssessment.case_id == case_id)
        .order_by(SupportAssessment.created_at.asc(), SupportAssessment.id.asc())
    )
    return list(db.scalars(stmt).all())


@app.get("/cases/{case_id}/judgments", response_model=list[JudgmentRead])
def get_judgments(case_id: int, db: Session = Depends(get_db)) -> list[Judgment]:
    if db.get(Case, case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")

    stmt = (
        select(Judgment)
        .where(Judgment.case_id == case_id)
        .order_by(Judgment.revision_no.asc())
    )
    return list(db.scalars(stmt).all())


@app.get("/release", response_model=ReleaseRead)
def get_release() -> dict:
    return release_snapshot()


@app.post("/cases/{case_id}/compose-response", response_model=ResponseCompositionRead)
def compose_case_response(case_id: int, db: Session = Depends(get_db)) -> dict:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    require_feature(db, case_id=case_id, feature=Feature.RESPONSE_COMPOSER)

    judgment = db.scalar(
        select(Judgment)
        .where(Judgment.case_id == case_id)
        .order_by(Judgment.revision_no.desc())
        .limit(1)
    )
    if judgment is None:
        raise HTTPException(status_code=409, detail="Cannot compose a response without a judgment")

    support = db.scalar(
        select(SupportAssessment)
        .where(SupportAssessment.case_id == case_id)
        .order_by(SupportAssessment.created_at.desc(), SupportAssessment.id.desc())
        .limit(1)
    )

    composed = compose_response(judgment=judgment, support=support)
    append_history(
        db,
        case_id=case_id,
        event_type=HistoryEventType.RESPONSE_COMPOSED,
        entity_type="JUDGMENT",
        entity_id=judgment.id,
        actor="SYSTEM",
        payload={
            "judgment_id": judgment.id,
            "support_assessment_id": support.id if support else None,
            "delivery_style": composed.delivery_style.value,
            "change_notice": composed.change_notice,
            "nudge_included": composed.nudge_text is not None,
        },
    )
    db.commit()

    return {
        "case_id": case_id,
        "judgment_id": judgment.id,
        "support_assessment_id": support.id if support else None,
        "text": composed.text,
        "judgment_text": composed.judgment_text,
        "nudge_text": composed.nudge_text,
        "change_notice": composed.change_notice,
        "delivery_style": composed.delivery_style,
    }


@app.get("/cases/{case_id}/permission", response_model=PermissionRead)
def get_case_permission(case_id: int, db: Session = Depends(get_db)):
    if db.get(Case, case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")

    require_feature(db, case_id=case_id, feature=Feature.PERMISSION_ACTION)
    policy = get_or_create_permission(db, case_id=case_id)
    db.commit()
    db.refresh(policy)
    return policy


@app.put("/cases/{case_id}/permission", response_model=PermissionRead)
def update_case_permission(
    case_id: int, payload: PermissionUpdate, db: Session = Depends(get_db)
):
    if db.get(Case, case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")

    require_feature(db, case_id=case_id, feature=Feature.PERMISSION_ACTION)
    policy = set_permission(
        db,
        case_id=case_id,
        can_execute=payload.can_execute,
        allowed_actions=payload.allowed_actions,
        actor="USER",
    )
    db.commit()
    db.refresh(policy)
    return policy


@app.post(
    "/cases/{case_id}/actions",
    response_model=ActionRead,
    status_code=status.HTTP_201_CREATED,
)
def run_case_action(
    case_id: int, payload: ActionExecuteRequest, db: Session = Depends(get_db)
) -> ActionAttempt:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    require_feature(db, case_id=case_id, feature=Feature.PERMISSION_ACTION)

    judgment = db.get(Judgment, payload.judgment_id)
    if judgment is None or judgment.case_id != case_id:
        raise HTTPException(status_code=404, detail="Judgment not found for this case")

    action = execute_action(
        db,
        case=case,
        judgment=judgment,
        action_type=payload.action_type,
        parameters=payload.parameters,
    )
    db.commit()
    db.refresh(action)
    return action


@app.get("/cases/{case_id}/actions", response_model=list[ActionRead])
def get_case_actions(case_id: int, db: Session = Depends(get_db)) -> list[ActionAttempt]:
    if db.get(Case, case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")

    require_feature(db, case_id=case_id, feature=Feature.PERMISSION_ACTION)
    stmt = (
        select(ActionAttempt)
        .where(ActionAttempt.case_id == case_id)
        .order_by(ActionAttempt.created_at.asc(), ActionAttempt.id.asc())
    )
    return list(db.scalars(stmt).all())


@app.get("/cases/{case_id}/history", response_model=list[HistoryRead])
def get_history(case_id: int, db: Session = Depends(get_db)) -> list[HistoryEvent]:
    if db.get(Case, case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")

    stmt = (
        select(HistoryEvent)
        .where(HistoryEvent.case_id == case_id)
        .order_by(HistoryEvent.created_at.asc(), HistoryEvent.id.asc())
    )
    return list(db.scalars(stmt).all())


@app.get("/cases/{case_id}/timeline", response_model=list[TimelineItemRead])
def get_timeline(case_id: int, db: Session = Depends(get_db)):
    if db.get(Case, case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")

    events = list(
        db.scalars(
            select(HistoryEvent)
            .where(HistoryEvent.case_id == case_id)
            .order_by(HistoryEvent.created_at.asc(), HistoryEvent.id.asc())
        ).all()
    )
    return build_user_timeline(events)
