import os
from pathlib import Path
from types import SimpleNamespace

TEST_DB = Path(__file__).with_name("test_step10.db")
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.judgment_engine import (
    EngineDecision,
    EvidenceAssessment,
    EvidenceStance,
    OpenAIJudgmentProvider,
    get_judgment_provider,
)
from app.main import app
from app.models import JudgmentConclusion, ResolutionState


Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
client = TestClient(app)


def make_case_with_evidence():
    case = client.post(
        "/cases",
        json={"title": "Step 10", "original_input": "A가 사실이다."},
    )
    assert case.status_code == 201
    case_id = case.json()["id"]
    evidence = client.post(
        f"/cases/{case_id}/evidence",
        json={
            "content": "공식 문서는 A를 지지한다.",
            "source_type": "OFFICIAL",
            "is_primary_source": True,
            "reliability_score": 0.8,
        },
    )
    assert evidence.status_code == 201
    return case_id, evidence.json()["id"]


def valid_decision(evidence_id: int):
    return EngineDecision(
        conclusion=JudgmentConclusion.SUPPORTED,
        confidence=0.82,
        resolution_state=ResolutionState.RESOLVED,
        position_text="현재 근거 기준으로는 맞다고 생각해.",
        reasoning_summary="제공된 근거가 주장을 직접 지지한다.",
        evidence_assessments=[
            EvidenceAssessment(
                evidence_id=evidence_id,
                stance=EvidenceStance.SUPPORT,
                relevance=1.0,
                reliability=0.6,
                rationale="주장을 직접 지지한다.",
            )
        ],
    )


class FakeResponses:
    def __init__(self, *, output=None, error=None, request_id="req_test"):
        self.output = output
        self.error = error
        self.request_id = request_id
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(output_parsed=self.output, _request_id=self.request_id)


class FakeOpenAIClient:
    def __init__(self, responses):
        self.responses = responses


def provider_with(*, output=None, error=None):
    responses = FakeResponses(output=output, error=error)
    provider = OpenAIJudgmentProvider(
        model="gpt-5.6-luna",
        client=FakeOpenAIClient(responses),
        timeout_seconds=7,
        max_retries=0,
    )
    return provider, responses


def test_ai_status_does_not_perform_live_network_check_without_key():
    app.dependency_overrides.clear()
    os.environ.pop("OPENAI_API_KEY", None)
    response = client.get("/ai/status")
    assert response.status_code == 200
    assert response.json() == {
        "provider": "openai",
        "configured": False,
        "model": os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
        "live_check_performed": False,
    }


def test_openai_structured_response_path_creates_judgment_and_disables_storage():
    case_id, evidence_id = make_case_with_evidence()
    provider, responses = provider_with(output=valid_decision(evidence_id))
    app.dependency_overrides[get_judgment_provider] = lambda: provider
    try:
        response = client.post(f"/cases/{case_id}/judge")
        assert response.status_code == 201
        assert response.json()["conclusion"] == "SUPPORTED"
        assert len(responses.calls) == 1
        call = responses.calls[0]
        assert call["model"] == "gpt-5.6-luna"
        assert call["text_format"] is EngineDecision
        assert call["store"] is False
        assert call["max_output_tokens"] == 1800
        assert call["reasoning"] == {"effort": "low"}
    finally:
        app.dependency_overrides.clear()


def test_timeout_is_504_retryable_and_preserved_in_history():
    case_id, _ = make_case_with_evidence()
    timeout_error = type("APITimeoutError", (Exception,), {})()
    provider, _ = provider_with(error=timeout_error)
    app.dependency_overrides[get_judgment_provider] = lambda: provider
    try:
        response = client.post(f"/cases/{case_id}/judge")
        assert response.status_code == 504
        detail = response.json()["detail"]
        assert detail == {
            "code": "OPENAI_TIMEOUT",
            "message": "The AI provider timed out before returning a judgment.",
            "retryable": True,
        }
        history = client.get(f"/cases/{case_id}/history").json()
        assert history[-1]["event_type"] == "JUDGMENT_FAILED"
        assert history[-1]["payload"]["error_code"] == "OPENAI_TIMEOUT"
        assert history[-1]["payload"]["retryable"] is True
    finally:
        app.dependency_overrides.clear()


def test_rate_limit_is_exposed_as_429_without_raw_exception_text():
    case_id, _ = make_case_with_evidence()
    error_type = type("RateLimitError", (Exception,), {})
    rate_error = error_type("SECRET RAW PROVIDER MESSAGE")
    setattr(rate_error, "status_code", 429)
    setattr(rate_error, "request_id", "req_rate")
    provider, _ = provider_with(error=rate_error)
    app.dependency_overrides[get_judgment_provider] = lambda: provider
    try:
        response = client.post(f"/cases/{case_id}/judge")
        assert response.status_code == 429
        detail = response.json()["detail"]
        assert detail["code"] == "OPENAI_RATE_LIMITED"
        assert detail["retryable"] is True
        assert detail["request_id"] == "req_rate"
        assert "SECRET" not in response.text
    finally:
        app.dependency_overrides.clear()


def test_model_cannot_omit_or_invent_evidence_assessment_ids():
    case_id, evidence_id = make_case_with_evidence()
    decision = valid_decision(evidence_id)
    decision.evidence_assessments[0].evidence_id = evidence_id + 999
    provider, _ = provider_with(output=decision)
    app.dependency_overrides[get_judgment_provider] = lambda: provider
    try:
        response = client.post(f"/cases/{case_id}/judge")
        assert response.status_code == 502
        assert response.json()["detail"]["code"] == "OPENAI_INVALID_RESPONSE"
        history = client.get(f"/cases/{case_id}/history").json()
        assert history[-1]["event_type"] == "JUDGMENT_FAILED"
    finally:
        app.dependency_overrides.clear()


def test_missing_structured_output_is_invalid_response():
    case_id, _ = make_case_with_evidence()
    provider, _ = provider_with(output=None)
    app.dependency_overrides[get_judgment_provider] = lambda: provider
    try:
        response = client.post(f"/cases/{case_id}/judge")
        assert response.status_code == 502
        detail = response.json()["detail"]
        assert detail["code"] == "OPENAI_INVALID_RESPONSE"
        assert detail["retryable"] is True
    finally:
        app.dependency_overrides.clear()
