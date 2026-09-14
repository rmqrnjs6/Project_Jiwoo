import os
from pathlib import Path

TEST_DB = Path(__file__).with_name("test_step9.db")
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
client = TestClient(app)


def create_case():
    response = client.post(
        "/cases",
        json={"title": "수동 검증 Case", "original_input": "A가 사실이라고 생각한다."},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_duplicate_evidence_is_detected_without_adding_second_evidence():
    case_id = create_case()
    payload = {
        "content": "동일한 근거 문장",
        "source_type": "WEB",
        "source_url": "https://example.com/source",
        "is_primary_source": False,
    }
    first = client.post(f"/cases/{case_id}/evidence", json=payload)
    assert first.status_code == 201

    duplicate_payload = dict(payload)
    duplicate_payload["content"] = "  동일한   근거 문장  "
    second = client.post(f"/cases/{case_id}/evidence", json=duplicate_payload)
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "DUPLICATE_EVIDENCE"
    assert second.json()["detail"]["existing_evidence_id"] == first.json()["id"]

    case = client.get(f"/cases/{case_id}").json()
    assert len(case["evidence"]) == 1

    history = client.get(f"/cases/{case_id}/history").json()
    assert history[-1]["event_type"] == "DUPLICATE_EVIDENCE_DETECTED"
    assert history[-1]["payload"]["existing_evidence_id"] == first.json()["id"]


def test_identical_judgment_is_reaffirmed_not_revised():
    case_id = create_case()
    payload = {
        "conclusion": "INSUFFICIENT_EVIDENCE",
        "ai_position": "UNSURE",
        "confidence": 0.35,
        "resolution_state": "PENDING",
        "position_text": "아직은 잘 모르겠다.",
        "reasoning_summary": "현재 근거가 부족하다.",
        "waiting_for": "공식 자료",
        "evidence_assessments": [],
    }
    assert client.post(f"/cases/{case_id}/judgments", json=payload).status_code == 201
    payload["reasoning_summary"] = "다시 검토했지만 현재 근거가 여전히 부족하다."
    assert client.post(f"/cases/{case_id}/judgments", json=payload).status_code == 201

    history = client.get(f"/cases/{case_id}/history").json()
    event_types = [event["event_type"] for event in history]
    assert "JUDGMENT_REAFFIRMED" in event_types
    assert "JUDGMENT_REVISED" not in event_types
    completed = [event for event in history if event["event_type"] == "REEVALUATION_COMPLETED"][-1]
    assert completed["payload"]["state_changed"] is False


def test_case_and_history_response_datetimes_are_explicit_utc():
    case_id = create_case()
    case = client.get(f"/cases/{case_id}").json()
    history = client.get(f"/cases/{case_id}/history").json()

    assert case["created_at"].endswith("Z") or case["created_at"].endswith("+00:00")
    assert history[0]["created_at"].endswith("Z") or history[0]["created_at"].endswith("+00:00")


def test_whitespace_only_case_and_evidence_are_rejected():
    bad_case = client.post("/cases", json={"title": "   ", "original_input": "   "})
    assert bad_case.status_code == 422

    case_id = create_case()
    bad_evidence = client.post(
        f"/cases/{case_id}/evidence",
        json={"content": "   ", "source_type": "WEB"},
    )
    assert bad_evidence.status_code == 422


def test_changed_reliability_is_revised_not_reaffirmed():
    from app.reliability_engine import ReliabilityDecision, ReliabilityProvider, get_reliability_provider

    class ChangingProvider(ReliabilityProvider):
        def __init__(self):
            self.calls = 0

        def assess(self, *, case, evidence, peer_evidence):
            self.calls += 1
            score = 0.50 if self.calls == 1 else 0.75
            return ReliabilityDecision(
                authority_score=score,
                originality_score=0.50,
                directness_score=0.50,
                recency_score=0.50,
                corroboration_score=0.50,
                        final_score=score,
                rationale="변경 여부 테스트",
                method_version="changing-test-v1",
            )

    provider = ChangingProvider()
    app.dependency_overrides[get_reliability_provider] = lambda: provider
    try:
        case_id = create_case()
        evidence = client.post(
            f"/cases/{case_id}/evidence",
            json={"content": "변경되는 신뢰도 근거", "source_type": "WEB"},
        ).json()
        first = client.post(f"/cases/{case_id}/evidence/{evidence['id']}/assess-reliability")
        second = client.post(f"/cases/{case_id}/evidence/{evidence['id']}/assess-reliability")
        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["final_score"] == 0.50
        assert second.json()["final_score"] == 0.75

        history = client.get(f"/cases/{case_id}/history").json()
        events = [event["event_type"] for event in history]
        assert "RELIABILITY_ASSESSED" in events
        assert "RELIABILITY_REVISED" in events
        assert "RELIABILITY_REAFFIRMED" not in events
    finally:
        app.dependency_overrides.clear()
