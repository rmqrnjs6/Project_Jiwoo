import os
from pathlib import Path

TEST_DB = Path(__file__).with_name("test_step11.db")
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.judgment_engine import (
    EngineDecision,
    EvidenceAssessment,
    EvidenceStance,
    JudgmentProvider,
    get_judgment_provider,
)
from app.main import app
from app.models import JudgmentConclusion, ResolutionState


Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
client = TestClient(app)


class CountingProvider(JudgmentProvider):
    provider_name = "test-provider"
    model_name = "test-model-v1"

    def __init__(self):
        self.calls = 0

    def judge(self, *, case, evidence):
        self.calls += 1
        return EngineDecision(
            conclusion=JudgmentConclusion.SUPPORTED,
            confidence=0.81,
            resolution_state=ResolutionState.RESOLVED,
            position_text="현재 근거 기준으로는 맞다고 생각해.",
            reasoning_summary="현재 제공된 근거가 입력을 지지한다.",
            evidence_assessments=[
                EvidenceAssessment(
                    evidence_id=item.id,
                    stance=EvidenceStance.SUPPORT,
                    relevance=1.0,
                    reliability=0.6,
                    rationale="현재 입력을 지지한다.",
                )
                for item in evidence
            ],
        )


def make_case():
    case = client.post(
        "/cases",
        json={"title": "건강성 테스트", "original_input": "A가 사실이다."},
    )
    assert case.status_code == 201
    case_id = case.json()["id"]
    evidence = client.post(
        f"/cases/{case_id}/evidence",
        json={
            "content": "자료 A는 입력을 지지한다.",
            "source_type": "OFFICIAL",
            "is_primary_source": True,
            "reliability_score": 0.8,
        },
    )
    assert evidence.status_code == 201
    return case_id, evidence.json()["id"]


def test_decision_snapshot_records_what_was_seen():
    case_id, evidence_id = make_case()
    provider = CountingProvider()
    app.dependency_overrides[get_judgment_provider] = lambda: provider
    try:
        response = client.post(f"/cases/{case_id}/judge")
        assert response.status_code == 201
        body = response.json()
        assert body["reevaluation_trigger"] == "INITIAL"
        assert len(body["decision_fingerprint"]) == 64

        assert "decision_snapshot" not in body  # kept internally; normal API responses stay small
        with SessionLocal() as db:
            from app.models import Judgment

            stored = db.get(Judgment, body["id"])
            snapshot = stored.decision_snapshot
            assert snapshot["schema_version"] == "decision-snapshot-v1"
            assert snapshot["case"]["original_input"] == "A가 사실이다."
            assert snapshot["provider"] == {"name": "test-provider", "model": "test-model-v1"}
            assert snapshot["evidence"][0]["id"] == evidence_id
            assert snapshot["evidence"][0]["content"] == "자료 A는 입력을 지지한다."
            assert snapshot["rules"]["judgment_rule_version"]
            assert snapshot["rules"]["system_instruction"]
    finally:
        app.dependency_overrides.clear()


def test_same_decision_context_reuses_existing_judgment_without_second_ai_call():
    case_id, _ = make_case()
    provider = CountingProvider()
    app.dependency_overrides[get_judgment_provider] = lambda: provider
    try:
        first = client.post(f"/cases/{case_id}/judge")
        assert first.status_code == 201
        second = client.post(f"/cases/{case_id}/judge")

        assert second.status_code == 200
        assert second.json()["id"] == first.json()["id"]
        assert provider.calls == 1

        history = client.get(f"/cases/{case_id}/history").json()
        assert history[-1]["event_type"] == "AI_CALL_SKIPPED"
        assert history[-1]["payload"]["reason"] == "NO_RELEVANT_CHANGE"
        assert history[-1]["payload"]["saved_paid_call"] is True
    finally:
        app.dependency_overrides.clear()


def test_new_evidence_changes_fingerprint_and_triggers_real_reevaluation():
    case_id, _ = make_case()
    provider = CountingProvider()
    app.dependency_overrides[get_judgment_provider] = lambda: provider
    try:
        first = client.post(f"/cases/{case_id}/judge")
        assert first.status_code == 201

        added = client.post(
            f"/cases/{case_id}/evidence",
            json={
                "content": "새로운 독립 자료도 A를 지지한다.",
                "source_type": "NEWS",
                "is_primary_source": False,
            },
        )
        assert added.status_code == 201

        second = client.post(f"/cases/{case_id}/judge")
        assert second.status_code == 201
        assert second.json()["id"] != first.json()["id"]
        assert second.json()["decision_fingerprint"] != first.json()["decision_fingerprint"]
        assert second.json()["reevaluation_trigger"] == "NEW_EVIDENCE"
        assert provider.calls == 2
    finally:
        app.dependency_overrides.clear()


def test_rule_version_change_forces_reevaluation_even_when_evidence_is_same(monkeypatch):
    case_id, _ = make_case()
    provider = CountingProvider()
    app.dependency_overrides[get_judgment_provider] = lambda: provider
    try:
        first = client.post(f"/cases/{case_id}/judge")
        assert first.status_code == 201

        monkeypatch.setenv("JUDGMENT_RULE_VERSION", "judgment-rules-v2-test")
        second = client.post(f"/cases/{case_id}/judge")
        assert second.status_code == 201
        assert second.json()["reevaluation_trigger"] == "RULE_CHANGED"
        assert provider.calls == 2
    finally:
        app.dependency_overrides.clear()



def test_model_change_forces_reevaluation_without_evidence_change():
    case_id, _ = make_case()
    provider_v1 = CountingProvider()
    app.dependency_overrides[get_judgment_provider] = lambda: provider_v1
    first = client.post(f"/cases/{case_id}/judge")
    assert first.status_code == 201

    provider_v2 = CountingProvider()
    provider_v2.model_name = "test-model-v2"
    app.dependency_overrides[get_judgment_provider] = lambda: provider_v2
    try:
        second = client.post(f"/cases/{case_id}/judge")
        assert second.status_code == 201
        assert second.json()["reevaluation_trigger"] == "MODEL_CHANGED"
        assert provider_v2.calls == 1
    finally:
        app.dependency_overrides.clear()

def test_force_true_allows_user_requested_recheck_even_without_change():
    case_id, _ = make_case()
    provider = CountingProvider()
    app.dependency_overrides[get_judgment_provider] = lambda: provider
    try:
        first = client.post(f"/cases/{case_id}/judge")
        assert first.status_code == 201
        second = client.post(f"/cases/{case_id}/judge?force=true")
        assert second.status_code == 201
        assert second.json()["id"] != first.json()["id"]
        assert second.json()["reevaluation_trigger"] == "USER_REQUEST"
        assert provider.calls == 2
    finally:
        app.dependency_overrides.clear()


def test_user_timeline_hides_internal_reevaluation_noise_and_explains_saved_call():
    case_id, _ = make_case()
    provider = CountingProvider()
    app.dependency_overrides[get_judgment_provider] = lambda: provider
    try:
        assert client.post(f"/cases/{case_id}/judge").status_code == 201
        assert client.post(f"/cases/{case_id}/judge?force=true").status_code == 201
        assert client.post(f"/cases/{case_id}/judge").status_code == 200

        raw = client.get(f"/cases/{case_id}/history").json()
        assert any(item["event_type"] == "REEVALUATION_STARTED" for item in raw)
        assert any(item["event_type"] == "REEVALUATION_COMPLETED" for item in raw)

        timeline = client.get(f"/cases/{case_id}/timeline")
        assert timeline.status_code == 200
        body = timeline.json()
        event_types = [item["event_type"] for item in body]
        assert "REEVALUATION_STARTED" not in event_types
        assert "REEVALUATION_COMPLETED" not in event_types
        assert "JUDGMENT_REAFFIRMED" in event_types
        assert "AI_CALL_SKIPPED" in event_types
        skipped = next(item for item in body if item["event_type"] == "AI_CALL_SKIPPED")
        assert "새 유료 AI 호출은 하지 않았습니다" in skipped["summary"]
    finally:
        app.dependency_overrides.clear()
