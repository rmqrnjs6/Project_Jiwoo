from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.judgment_engine import effective_reliability
from app.main import app
from app.models import Case, Evidence, HistoryEvent, Judgment


client = TestClient(app)


def create_case(title: str) -> int:
    response = client.post(
        "/cases",
        json={"title": title, "original_input": "A가 사실이라고 생각한다."},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_manual_judgment_rejects_position_contradiction_and_records_origin():
    case_id = create_case("판단 일관성")

    bad = client.post(
        f"/cases/{case_id}/judgments",
        json={
            "conclusion": "CONTRADICTED",
            "ai_position": "AGREE",
            "confidence": 0.9,
            "resolution_state": "RESOLVED",
            "position_text": "모순된 테스트",
            "reasoning_summary": "의도적으로 모순을 넣는다.",
        },
    )
    assert bad.status_code == 422

    good = client.post(
        f"/cases/{case_id}/judgments",
        json={
            "conclusion": "CONTRADICTED",
            "ai_position": "DISAGREE",
            "confidence": 0.9,
            "resolution_state": "RESOLVED",
            "position_text": "현재 근거와 충돌한다.",
            "reasoning_summary": "일관된 수동 판단",
        },
    )
    assert good.status_code == 201
    assert good.json()["origin"] == "MANUAL"
    assert good.json()["actor"] == "USER"


def test_database_constraint_rejects_invalid_judgment_even_if_service_is_bypassed():
    case_id = create_case("DB 불변식")
    db = SessionLocal()
    try:
        invalid = Judgment(
            case_id=case_id,
            previous_judgment_id=None,
            revision_no=1,
            conclusion="CONTRADICTED",
            ai_position="AGREE",
            confidence=0.99,
            resolution_state="RESOLVED",
            position_text="DB 우회",
            reasoning_summary="서비스를 거치지 않는다.",
            unresolved_reason=None,
            waiting_for=None,
            evidence_assessments=[],
            origin="MANUAL",
            actor="USER",
        )
        db.add(invalid)
        try:
            db.commit()
            raise AssertionError("invalid judgment unexpectedly committed")
        except IntegrityError:
            db.rollback()
    finally:
        db.close()


def test_source_claim_is_explicitly_unverified_and_capped_until_assessed():
    case_id = create_case("출처 주장 분리")
    response = client.post(
        f"/cases/{case_id}/evidence",
        json={
            "content": "검증되지 않은 자료이지만 공식 원문이라고 주장한다.",
            "source_type": "PRIMARY",
            "is_primary_source": True,
            "reliability_score": 0.99,
        },
    )
    assert response.status_code == 201
    evidence = response.json()
    assert evidence["claimed_source_type"] == "PRIMARY"
    assert evidence["claimed_is_primary_source"] is True
    assert evidence["source_verification_status"] == "UNVERIFIED"
    assert evidence["verified_source_type"] is None
    assert evidence["reliability_source"] == "USER_PROVIDED"

    db = SessionLocal()
    try:
        stored = db.get(Evidence, evidence["id"])
        assert stored is not None
        # The claim is preserved, but a user-provided 0.99 is not consumed as 0.99
        # by the judgment engine before independent assessment.
        assert effective_reliability(stored) == 0.60
    finally:
        db.close()

    assessed = client.post(
        f"/cases/{case_id}/evidence/{evidence['id']}/assess-reliability"
    )
    assert assessed.status_code == 201
    assert assessed.json()["method_version"] == "metadata-v3"
    assert assessed.json()["authority_score"] <= 0.70
    assert assessed.json()["originality_score"] <= 0.60


def test_history_rows_cannot_be_updated_or_deleted_through_orm():
    case_id = create_case("History 보존")
    db = SessionLocal()
    try:
        event = db.scalar(
            select(HistoryEvent)
            .where(HistoryEvent.case_id == case_id)
            .order_by(HistoryEvent.id.asc())
            .limit(1)
        )
        assert event is not None

        event.actor = "TAMPER"
        try:
            db.commit()
            raise AssertionError("history update unexpectedly committed")
        except RuntimeError as exc:
            assert "append-only" in str(exc)
            db.rollback()

        event = db.get(HistoryEvent, event.id)
        assert event is not None
        db.delete(event)
        try:
            db.commit()
            raise AssertionError("history delete unexpectedly committed")
        except RuntimeError as exc:
            assert "cannot be deleted" in str(exc)
            db.rollback()
    finally:
        db.close()


def test_case_delete_is_restricted_while_history_exists():
    case_id = create_case("Case 삭제 보존")
    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        assert case is not None
        db.delete(case)
        try:
            db.commit()
            raise AssertionError("case with history unexpectedly deleted")
        except IntegrityError:
            db.rollback()

        assert db.get(Case, case_id) is not None
        assert db.scalar(select(HistoryEvent).where(HistoryEvent.case_id == case_id)) is not None
    finally:
        db.close()
