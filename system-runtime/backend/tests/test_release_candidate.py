import os
import subprocess
import sys
from pathlib import Path

TEST_DB = Path(__file__).with_name("test_step14.db")
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
)
from app.main import app
from app.models import JudgmentConclusion, ResolutionState

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
client = TestClient(app)


class CapturingResponses:
    def __init__(self, output):
        self.output = output
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return type("R", (), {"output_parsed": self.output, "_request_id": "req14"})()


class FakeClient:
    def __init__(self, output):
        self.responses = CapturingResponses(output)


def test_ready_checks_database_without_requiring_ai_configuration():
    os.environ.pop("OPENAI_API_KEY", None)
    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["database"]["ready"] is True
    assert body["database"]["backend"] == "sqlite"
    assert body["ai"]["required_for_core_readiness"] is False


def test_system_status_is_safe_and_does_not_claim_paid_live_check():
    os.environ.pop("OPENAI_API_KEY", None)
    response = client.get("/system/status")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "1.0.0-rc6"
    assert body["database_backend"] == "sqlite"
    assert body["paid_live_check_performed"] is False
    assert "OPENAI_API_KEY" not in response.text


def test_openai_request_has_cost_caps_and_storage_disabled():
    decision = EngineDecision(
        conclusion=JudgmentConclusion.SUPPORTED,
        confidence=0.8,
        resolution_state=ResolutionState.RESOLVED,
        position_text="현재 근거 기준으로는 맞다고 생각해.",
        reasoning_summary="근거가 주장을 지지한다.",
        evidence_assessments=[
            EvidenceAssessment(
                evidence_id=1,
                stance=EvidenceStance.SUPPORT,
                relevance=1.0,
                reliability=0.7,
                rationale="직접 지지한다.",
            )
        ],
    )
    fake = FakeClient(decision)
    provider = OpenAIJudgmentProvider(
        model="gpt-5.6-luna",
        client=fake,
        max_output_tokens=900,
        reasoning_effort="low",
    )

    from app.models import Case, Evidence, EvidenceSourceType, SourceVerificationStatus

    case = Case(id=1, title="test", original_input="A다.")
    evidence = Evidence(
        id=1,
        case_id=1,
        content="A라고 명시되어 있다.",
        claimed_source_type=EvidenceSourceType.PRIMARY,
        claimed_is_primary_source=True,
        source_verification_status=SourceVerificationStatus.UNVERIFIED,
        reliability_score=0.7,
        reliability_source="SYSTEM_TEST",
    )
    provider.judge(case=case, evidence=[evidence])
    call = fake.responses.calls[0]
    assert call["store"] is False
    assert call["max_output_tokens"] == 900
    assert call["reasoning"] == {"effort": "low"}


def test_paid_live_smoke_script_is_disabled_by_default():
    env = os.environ.copy()
    env.pop("RUN_PAID_OPENAI_SMOKE_TEST", None)
    env.pop("OPENAI_API_KEY", None)
    script = Path(__file__).resolve().parents[1] / "scripts" / "live_openai_smoke_test.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0
    assert "SKIPPED" in result.stdout
    assert "exactly one paid" not in result.stdout.lower()


def test_invalid_reasoning_effort_is_rejected_before_any_request():
    fake = FakeClient(None)
    try:
        OpenAIJudgmentProvider(client=fake, reasoning_effort="turbo")
    except ValueError as exc:
        assert "OPENAI_REASONING_EFFORT" in str(exc)
    else:
        raise AssertionError("invalid reasoning effort should be rejected")
    assert fake.responses.calls == []


def test_decision_snapshot_includes_cost_sensitive_model_options(monkeypatch):
    from app.models import Case, Evidence, EvidenceSourceType, SourceVerificationStatus
    from app.services import build_decision_snapshot

    monkeypatch.setenv("OPENAI_MAX_OUTPUT_TOKENS", "777")
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "minimal")
    case = Case(id=7, title="snapshot", original_input="A다.")
    evidence = Evidence(
        id=9,
        case_id=7,
        content="A다.",
        claimed_source_type=EvidenceSourceType.WEB,
        claimed_is_primary_source=False,
        source_verification_status=SourceVerificationStatus.UNVERIFIED,
        reliability_score=0.5,
        reliability_source="SYSTEM_TEST",
    )
    snapshot = build_decision_snapshot(
        case=case,
        evidence=[evidence],
        provider_name="openai",
        model_name="gpt-5.6-luna",
    )
    assert snapshot["model_options"]["max_output_tokens"] == 777
    assert snapshot["model_options"]["reasoning_effort"] == "minimal"


def test_oversized_ai_input_is_blocked_before_paid_request():
    from app.judgment_engine import JudgmentProviderError
    from app.models import Case, Evidence, EvidenceSourceType, SourceVerificationStatus

    fake = FakeClient(None)
    provider = OpenAIJudgmentProvider(
        client=fake,
        max_input_chars=1000,
        max_evidence_items=2,
    )
    case = Case(id=1, title="budget", original_input="A" * 600)
    evidence = Evidence(
        id=1,
        case_id=1,
        content="B" * 600,
        claimed_source_type=EvidenceSourceType.WEB,
        claimed_is_primary_source=False,
        source_verification_status=SourceVerificationStatus.UNVERIFIED,
        reliability_score=0.5,
        reliability_source="SYSTEM_TEST",
    )
    try:
        provider.judge(case=case, evidence=[evidence])
    except JudgmentProviderError as exc:
        assert exc.code == "OPENAI_INPUT_BUDGET_EXCEEDED"
        assert exc.http_status == 413
        assert exc.retryable is False
    else:
        raise AssertionError("oversized input should be blocked")
    assert fake.responses.calls == []
