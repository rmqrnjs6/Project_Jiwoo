import os
from pathlib import Path

TEST_DB = Path(__file__).with_name("test_step15.db")
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.evidence_discovery import (
    DiscoveryCandidateDraft,
    DiscoveryResult,
    OpenAIWebEvidenceDiscoveryProvider,
    candidate_score,
)
from app.main import app
from app.models import EvidenceSourceType

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
client = TestClient(app)


def create_case(title="Step15 UI", claim="A라는 주장의 사실 여부를 확인한다."):
    response = client.post("/cases", json={"title": title, "original_input": claim})
    assert response.status_code == 201
    return response.json()["id"]


def test_frontend_exposes_recommended_evidence_workspace():
    response = client.get("/")
    assert response.status_code == 200
    assert "함께 볼 근거" in response.text
    assert "지금 가장 믿을 만한 근거" in response.text
    assert "예시 보기" in response.text
    assert "직접 근거 추가" in response.text

    js = client.get("/static/app.js")
    assert js.status_code == 200
    assert "왜 이렇게 평가했나요?" in js.text
    assert "핵심 내용" in js.text
    assert "원문 보기" in js.text
    assert "출처 형식 확인" not in response.text
    assert "출처 형식 확인 결과" not in js.text
    assert "매우 높음" in js.text
    assert "다시 확인" in js.text


def test_demo_candidate_batch_has_exactly_one_representative_and_visible_scores():
    case_id = create_case()
    response = client.post(
        f"/cases/{case_id}/evidence-candidates/demo",
        json={"limit": 6},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["origin"] == "DEMO"
    assert len(body["candidates"]) == 6
    representatives = [item for item in body["candidates"] if item["is_representative"]]
    assert len(representatives) == 1
    assert body["representative_id"] == representatives[0]["id"]
    assert 0 < representatives[0]["reliability_score"] < 1
    assert "사실" in body["disclaimer"]
    assert set(representatives[0]["score_components"]) == {
        "authority",
        "originality",
        "directness",
        "recency",
        "corroboration",
    }


def test_candidate_adoption_is_idempotent_and_demo_is_blocked_from_real_judgment():
    case_id = create_case(title="Demo adoption")
    batch = client.post(
        f"/cases/{case_id}/evidence-candidates/demo",
        json={"limit": 5},
    ).json()
    candidate_id = batch["representative_id"]

    adopted = client.post(f"/cases/{case_id}/evidence-candidates/{candidate_id}/adopt")
    assert adopted.status_code == 201
    evidence_id = adopted.json()["id"]
    assert adopted.json()["reliability_source"] == "DEMO_CANDIDATE"

    again = client.post(f"/cases/{case_id}/evidence-candidates/{candidate_id}/adopt")
    assert again.status_code == 200
    assert again.json()["id"] == evidence_id

    judged = client.post(f"/cases/{case_id}/judge")
    assert judged.status_code == 409
    assert judged.json()["detail"]["code"] == "DEMO_EVIDENCE_NOT_ALLOWED"


def test_real_discovery_requires_api_key_when_not_configured(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    case_id = create_case(title="No API key")
    response = client.post(
        f"/cases/{case_id}/evidence-candidates/discover",
        json={"limit": 6},
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "OPENAI_NOT_CONFIGURED"


class CapturingResponses:
    def __init__(self, output):
        self.output = output
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return type("R", (), {"output_parsed": self.output, "_request_id": "req-step15"})()


class FakeClient:
    def __init__(self, output):
        self.responses = CapturingResponses(output)


def _draft(index: int) -> DiscoveryCandidateDraft:
    return DiscoveryCandidateDraft(
        title=f"후보 {index}",
        summary=f"이 문장은 후보 {index}의 관련 내용을 짧게 요약한 테스트 문장입니다.",
        source_name=f"출처 {index}",
        source_url=f"https://example.org/source/{index}",
        source_type=EvidenceSourceType.INSTITUTIONAL,
        source_published_at=None,
        relation_to_claim="SUPPORT",
        authority_score=0.8,
        originality_score=0.7,
        directness_score=0.9,
        recency_score=0.7,
        corroboration_score=0.8,
        rationale="테스트용 평가 이유입니다.",
    )


def test_openai_discovery_provider_uses_web_search_and_does_not_store_response():
    result = DiscoveryResult(candidates=[_draft(i) for i in range(1, 6)])
    fake = FakeClient(result)
    provider = OpenAIWebEvidenceDiscoveryProvider(
        model="gpt-5.6-luna",
        client=fake,
        max_output_tokens=1800,
    )
    from app.models import Case

    case = Case(id=1, title="검색 테스트", original_input="A는 사실이다.")
    candidates = provider.discover(case=case, limit=5)
    assert len(candidates) == 5
    call = fake.responses.calls[0]
    assert call["tools"] == [{"type": "web_search", "search_context_size": "medium"}]
    assert call["store"] is False
    assert call["text_format"] is DiscoveryResult


def test_candidate_score_is_bounded_below_one():
    draft = _draft(1).model_copy(
        update={
            "authority_score": 1.0,
            "originality_score": 1.0,
            "directness_score": 1.0,
            "recency_score": 1.0,
            "corroboration_score": 1.0,
        }
    )
    assert candidate_score(draft) == 0.99
