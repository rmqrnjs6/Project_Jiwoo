import os
from pathlib import Path

TEST_DB = Path(__file__).with_name("test_engine.db")
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.judgment_engine import (
    EngineDecision,
    EvidenceAssessment,
    EvidenceStance,
    JudgmentProvider,
    get_judgment_provider,
)
from app.main import app
from app.models import JudgmentConclusion, ResolutionState


class FakePendingProvider(JudgmentProvider):
    def judge(self, *, case, evidence):
        return EngineDecision(
            conclusion=JudgmentConclusion.INSUFFICIENT_EVIDENCE,
            confidence=0.35,
            resolution_state=ResolutionState.PENDING,
            position_text="아직은 잘 모르겠어. 공식 발표를 기다려야 해.",
            reasoning_summary="현재 근거는 공식 발표 전이라는 사실만 알려준다.",
            waiting_for="공식 발표",
            evidence_assessments=[
                EvidenceAssessment(
                    evidence_id=evidence[0].id,
                    stance=EvidenceStance.NEUTRAL,
                    relevance=0.90,
                    reliability=0.95,
                    rationale="주장의 참/거짓보다 아직 발표 전임을 보여준다.",
                )
            ],
        )


class FakeContradictProvider(JudgmentProvider):
    def judge(self, *, case, evidence):
        newest = evidence[-1]
        return EngineDecision(
            conclusion=JudgmentConclusion.CONTRADICTED,
            confidence=0.93,
            resolution_state=ResolutionState.RESOLVED,
            position_text="이건 아닌 것 같아. 새 공식 자료가 입력과 직접 충돌해.",
            reasoning_summary="가장 최신의 공식 1차 자료가 원래 주장을 직접 반박한다.",
            evidence_assessments=[
                EvidenceAssessment(
                    evidence_id=item.id,
                    stance=(
                        EvidenceStance.CONTRADICT
                        if item.id == newest.id
                        else EvidenceStance.NEUTRAL
                    ),
                    relevance=1.0 if item.id == newest.id else 0.7,
                    reliability=0.95,
                    rationale=(
                        "원래 주장을 직접 반박한다."
                        if item.id == newest.id
                        else "판단 시점을 설명하지만 주장 자체를 확정하지 않는다."
                    ),
                )
                for item in evidence
            ],
        )


Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
client = TestClient(app)


def make_case_with_evidence():
    case = client.post(
        "/cases",
        json={"title": "자동 판단", "original_input": "A가 사실이라고 생각한다."},
    )
    assert case.status_code == 201
    case_id = case.json()["id"]

    evidence = client.post(
        f"/cases/{case_id}/evidence",
        json={
            "content": "현재 공식 발표 전이다.",
            "source_type": "OFFICIAL",
            "is_primary_source": True,
            "reliability_score": 0.95,
        },
    )
    assert evidence.status_code == 201
    return case_id, evidence.json()["id"]


def test_automatic_judgment_creates_pending_position_and_evidence_trace():
    app.dependency_overrides[get_judgment_provider] = lambda: FakePendingProvider()
    try:
        case_id, evidence_id = make_case_with_evidence()
        response = client.post(f"/cases/{case_id}/judge")
        assert response.status_code == 201
        body = response.json()

        assert body["conclusion"] == "INSUFFICIENT_EVIDENCE"
        assert body["ai_position"] == "UNSURE"
        assert body["resolution_state"] == "PENDING"
        assert body["waiting_for"] == "공식 발표"
        assert body["revision_no"] == 1
        assert body["evidence_assessments"][0]["evidence_id"] == evidence_id
        assert body["evidence_assessments"][0]["stance"] == "NEUTRAL"
    finally:
        app.dependency_overrides.clear()


def test_rejudgment_changes_position_and_links_previous_judgment():
    case_id, _ = make_case_with_evidence()

    app.dependency_overrides[get_judgment_provider] = lambda: FakePendingProvider()
    first = client.post(f"/cases/{case_id}/judge")
    assert first.status_code == 201

    new_evidence = client.post(
        f"/cases/{case_id}/evidence",
        json={
            "content": "공식 발표에서 A는 사실이 아니라고 확인했다.",
            "source_type": "PRIMARY",
            "is_primary_source": True,
            "reliability_score": 1.0,
        },
    )
    assert new_evidence.status_code == 201

    app.dependency_overrides[get_judgment_provider] = lambda: FakeContradictProvider()
    try:
        second = client.post(f"/cases/{case_id}/judge")
        assert second.status_code == 201
        body = second.json()

        assert body["conclusion"] == "CONTRADICTED"
        assert body["ai_position"] == "DISAGREE"
        assert body["resolution_state"] == "RESOLVED"
        assert body["revision_no"] == 2
        assert body["previous_judgment_id"] == first.json()["id"]

        history = client.get(f"/cases/{case_id}/history")
        event_types = [event["event_type"] for event in history.json()]
        assert event_types[-3:] == [
            "REEVALUATION_STARTED",
            "JUDGMENT_REVISED",
            "REEVALUATION_COMPLETED",
        ]
    finally:
        app.dependency_overrides.clear()


def test_engine_rejects_inconsistent_resolved_state():
    try:
        EngineDecision(
            conclusion=JudgmentConclusion.UNCERTAIN,
            confidence=0.6,
            resolution_state=ResolutionState.RESOLVED,
            position_text="결론났다.",
            reasoning_summary="테스트",
        )
        assert False, "Expected validation error"
    except ValueError:
        pass


def test_real_provider_path_without_api_key_returns_503():
    app.dependency_overrides.clear()
    os.environ.pop("OPENAI_API_KEY", None)
    case_id, _ = make_case_with_evidence()
    response = client.post(f"/cases/{case_id}/judge")
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "OPENAI_NOT_CONFIGURED"
    assert "OPENAI_API_KEY" in detail["message"]
    assert detail["retryable"] is False
