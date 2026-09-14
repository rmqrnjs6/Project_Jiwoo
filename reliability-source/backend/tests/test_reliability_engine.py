import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

TEST_DB = Path(__file__).with_name("test_reliability.db")
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
from app.reliability_engine import (
    ReliabilityDecision,
    ReliabilityProvider,
    get_reliability_provider,
)


Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
client = TestClient(app)


def create_case(title="신뢰도 테스트"):
    response = client.post(
        "/cases",
        json={"title": title, "original_input": "A가 사실이라고 생각한다."},
    )
    assert response.status_code == 201
    return response.json()["id"]


def add_evidence(case_id, *, content, source_type, primary=False, published_at=None, score=None):
    payload = {
        "content": content,
        "source_type": source_type,
        "is_primary_source": primary,
    }
    if published_at is not None:
        payload["source_published_at"] = published_at
    if score is not None:
        payload["reliability_score"] = score
    response = client.post(f"/cases/{case_id}/evidence", json=payload)
    assert response.status_code == 201
    return response.json()


def test_metadata_reliability_scores_primary_official_above_ai_unknown():
    case_id = create_case()
    recent = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()

    primary = add_evidence(
        case_id,
        content="공식 1차 원문",
        source_type="PRIMARY",
        primary=True,
        published_at=recent,
    )
    ai = add_evidence(
        case_id,
        content="출처 불명 AI 요약",
        source_type="AI",
        primary=False,
    )

    response = client.post(f"/cases/{case_id}/assess-reliability")
    assert response.status_code == 201
    assessments = {item["evidence_id"]: item for item in response.json()}

    assert assessments[primary["id"]]["final_score"] > assessments[ai["id"]]["final_score"]
    assert assessments[primary["id"]]["authority_score"] == 0.7
    assert assessments[primary["id"]]["originality_score"] == 0.6
    assert assessments[primary["id"]]["method_version"] == "metadata-v3"

    case = client.get(f"/cases/{case_id}").json()
    evidence = {item["id"]: item for item in case["evidence"]}
    assert evidence[primary["id"]]["reliability_source"] == "metadata-v3"
    assert evidence[ai["id"]]["reliability_source"] == "metadata-v3"


def test_reliability_reassessment_is_append_only_and_identical_result_is_reaffirmed():
    case_id = create_case("재평가 이력")
    evidence = add_evidence(
        case_id,
        content="기관 자료",
        source_type="INSTITUTIONAL",
        primary=False,
        score=0.99,
    )
    assert evidence["reliability_source"] == "USER_PROVIDED"

    first = client.post(f"/cases/{case_id}/evidence/{evidence['id']}/assess-reliability")
    second = client.post(f"/cases/{case_id}/evidence/{evidence['id']}/assess-reliability")
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["revision_no"] == 1
    assert second.json()["revision_no"] == 2

    history_response = client.get(f"/cases/{case_id}/evidence/{evidence['id']}/reliability")
    assert history_response.status_code == 200
    revisions = history_response.json()
    assert [item["revision_no"] for item in revisions] == [1, 2]

    history = client.get(f"/cases/{case_id}/history").json()
    events = [event["event_type"] for event in history]
    assert "RELIABILITY_ASSESSED" in events
    assert "RELIABILITY_REAFFIRMED" in events

    case = client.get(f"/cases/{case_id}").json()
    stored = next(item for item in case["evidence"] if item["id"] == evidence["id"])
    assert stored["reliability_source"] == "metadata-v3"
    assert stored["reliability_score"] == second.json()["final_score"]


class SemanticFakeReliabilityProvider(ReliabilityProvider):
    def assess(self, *, case, evidence, peer_evidence):
        if "반박" in evidence.content:
            return ReliabilityDecision(
                authority_score=1.0,
                originality_score=1.0,
                directness_score=1.0,
                recency_score=1.0,
                corroboration_score=0.9,
                        final_score=0.98,
                rationale="공식 1차 반박 근거이며 주장에 직접 대응한다.",
                method_version="semantic-test-v1",
            )
        return ReliabilityDecision(
            authority_score=0.55,
            originality_score=0.45,
            directness_score=0.60,
            recency_score=0.80,
            corroboration_score=0.50,
                final_score=0.58,
            rationale="파생 웹 근거로 직접성과 권위가 제한적이다.",
            method_version="semantic-test-v1",
        )


class ReliabilityWeightedJudgmentProvider(JudgmentProvider):
    def judge(self, *, case, evidence):
        strongest = max(evidence, key=lambda item: item.reliability_score or 0.0)
        contradicted = "반박" in strongest.content
        conclusion = (
            JudgmentConclusion.CONTRADICTED
            if contradicted
            else JudgmentConclusion.SUPPORTED
        )
        stance = EvidenceStance.CONTRADICT if contradicted else EvidenceStance.SUPPORT
        return EngineDecision(
            conclusion=conclusion,
            confidence=strongest.reliability_score or 0.5,
            resolution_state=ResolutionState.RESOLVED,
            position_text=(
                "더 강한 새 근거를 보면 기존 입력과 충돌해."
                if contradicted
                else "현재 가장 강한 근거는 입력을 지지해."
            ),
            reasoning_summary="현재 가장 높은 신뢰도 점수를 가진 근거를 우선했다.",
            evidence_assessments=[
                EvidenceAssessment(
                    evidence_id=item.id,
                    stance=(
                        stance if item.id == strongest.id else EvidenceStance.NEUTRAL
                    ),
                    relevance=1.0 if item.id == strongest.id else 0.5,
                    reliability=item.reliability_score or 0.0,
                    rationale="신뢰도 엔진이 저장한 점수를 사용했다.",
                )
                for item in evidence
            ],
        )


def test_higher_reliability_new_evidence_can_drive_rejudgment_reversal():
    app.dependency_overrides[get_reliability_provider] = lambda: SemanticFakeReliabilityProvider()
    app.dependency_overrides[get_judgment_provider] = lambda: ReliabilityWeightedJudgmentProvider()
    try:
        case_id = create_case("더 강한 근거로 재판단")
        support = add_evidence(
            case_id,
            content="A를 지지하는 파생 웹 자료",
            source_type="WEB",
        )
        assessed_support = client.post(
            f"/cases/{case_id}/evidence/{support['id']}/assess-reliability"
        )
        assert assessed_support.status_code == 201
        assert assessed_support.json()["final_score"] == 0.58

        first = client.post(f"/cases/{case_id}/judge")
        assert first.status_code == 201
        assert first.json()["conclusion"] == "SUPPORTED"

        contradict = add_evidence(
            case_id,
            content="A를 직접 반박하는 공식 1차 자료",
            source_type="PRIMARY",
            primary=True,
        )
        assessed_contradict = client.post(
            f"/cases/{case_id}/evidence/{contradict['id']}/assess-reliability"
        )
        assert assessed_contradict.status_code == 201
        assert assessed_contradict.json()["final_score"] == 0.98

        second = client.post(f"/cases/{case_id}/judge")
        assert second.status_code == 201
        assert second.json()["conclusion"] == "CONTRADICTED"
        assert second.json()["previous_judgment_id"] == first.json()["id"]
        assert second.json()["confidence"] == 0.98

        history = client.get(f"/cases/{case_id}/history").json()
        event_types = [event["event_type"] for event in history]
        assert event_types.count("RELIABILITY_ASSESSED") == 2
        assert "JUDGMENT_REVISED" in event_types
        assert "REEVALUATION_COMPLETED" in event_types
    finally:
        app.dependency_overrides.clear()
