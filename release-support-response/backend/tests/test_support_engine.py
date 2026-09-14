import os
from pathlib import Path

TEST_DB = Path(__file__).with_name("test_support.db")
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["RELEASE_PROFILE"] = "V2"

from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from app.database import Base, engine
from app.main import app
from app.models import ContextMode, DeliveryStyle, NudgeLevel
from app.support_engine import (
    AffectSignal,
    AffectSignalType,
    SupportDecision,
    SupportProvider,
    get_support_provider,
)


@pytest.fixture(autouse=True)
def _enable_v2_release(monkeypatch):
    monkeypatch.setenv("RELEASE_PROFILE", "V2")


class FakeAmbiguousSoftProvider(SupportProvider):
    def assess(self, *, case):
        return SupportDecision(
            expression_summary="텍스트에는 강한 피로와 혼란을 나타내는 표현이 있다.",
            affect_signals=[
                AffectSignal(
                    signal=AffectSignalType.DISTRESS_LANGUAGE,
                    intensity=0.72,
                    textual_basis="지쳤고 더는 모르겠다는 표현이 반복된다.",
                )
            ],
            context_mode=ContextMode.AMBIGUOUS_CONTEXT,
            context_rationale="실제 경험인지 연기·창작인지 명시되어 있지 않다.",
            nudge_level=NudgeLevel.SOFT,
            delivery_style=DeliveryStyle.SUBTLE,
            recommendation_text="이 상태가 계속된다면 혼자 결론내리기보다 잠깐 다른 사람과 같이 정리해보는 것도 괜찮아 보여.",
            rationale_summary="명확한 진단 없이 현재 표현의 부담감에만 반응한다.",
        )


class FakeRoleplayProvider(SupportProvider):
    def assess(self, *, case):
        return SupportDecision(
            expression_summary="절망을 표현하는 대사지만 역할극임이 명시되어 있다.",
            affect_signals=[
                AffectSignal(
                    signal=AffectSignalType.DESPAIR_LANGUAGE,
                    intensity=0.9,
                    textual_basis="모든 게 끝났다는 극적인 대사가 포함된다.",
                )
            ],
            context_mode=ContextMode.ROLEPLAY_DECLARED,
            context_rationale="입력에 오디션 대사라고 명시되어 있다.",
            nudge_level=NudgeLevel.NONE,
            delivery_style=DeliveryStyle.NONE,
            recommendation_text=None,
            rationale_summary="표현은 강하지만 실제 개인 상태로 해석할 근거가 없다.",
        )


Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
client = TestClient(app)


def create_case(text: str) -> int:
    response = client.post("/cases", json={"title": "context test", "original_input": text})
    assert response.status_code == 201
    return response.json()["id"]


def test_ambiguous_emotional_text_generates_soft_nudge_and_history():
    app.dependency_overrides[get_support_provider] = lambda: FakeAmbiguousSoftProvider()
    try:
        case_id = create_case("요즘 너무 지쳤고 뭘 해야 할지 잘 모르겠다.")
        response = client.post(f"/cases/{case_id}/support-assess")
        assert response.status_code == 201
        body = response.json()

        assert body["context_mode"] == "AMBIGUOUS_CONTEXT"
        assert body["nudge_level"] == "SOFT"
        assert body["delivery_style"] == "SUBTLE"
        assert body["recommendation_text"]
        assert body["affect_signals"][0]["signal"] == "DISTRESS_LANGUAGE"

        history = client.get(f"/cases/{case_id}/history").json()
        assert [item["event_type"] for item in history][-2:] == [
            "CONTEXT_ASSESSED",
            "NUDGE_GENERATED",
        ]
    finally:
        app.dependency_overrides.clear()


def test_declared_roleplay_is_not_treated_as_personal_state():
    app.dependency_overrides[get_support_provider] = lambda: FakeRoleplayProvider()
    try:
        case_id = create_case("배우 오디션 대사야: 모든 게 끝났어. 아무 의미도 없어.")
        response = client.post(f"/cases/{case_id}/support-assess")
        assert response.status_code == 201
        body = response.json()
        assert body["context_mode"] == "ROLEPLAY_DECLARED"
        assert body["nudge_level"] == "NONE"
        assert body["recommendation_text"] is None
    finally:
        app.dependency_overrides.clear()


def test_safety_nudge_cannot_be_subtle():
    try:
        SupportDecision(
            expression_summary="직접적인 안전 우려 표현",
            affect_signals=[],
            context_mode=ContextMode.AMBIGUOUS_CONTEXT,
            context_rationale="맥락 불명",
            nudge_level=NudgeLevel.SAFETY,
            delivery_style=DeliveryStyle.SUBTLE,
            recommendation_text="넌지시 권고",
            rationale_summary="테스트",
        )
        assert False, "Expected validation failure"
    except ValidationError:
        pass


def test_support_schema_rejects_diagnosis_field():
    try:
        SupportDecision(
            expression_summary="표현 관찰",
            affect_signals=[],
            context_mode=ContextMode.AMBIGUOUS_CONTEXT,
            context_rationale="명시 맥락 없음",
            nudge_level=NudgeLevel.NONE,
            delivery_style=DeliveryStyle.NONE,
            recommendation_text=None,
            rationale_summary="진단하지 않음",
            diagnosis="depression",
        )
        assert False, "Expected extra field rejection"
    except ValidationError:
        pass


def test_real_support_provider_without_api_key_returns_503():
    app.dependency_overrides.clear()
    os.environ.pop("OPENAI_API_KEY", None)
    case_id = create_case("그냥 평범한 문장이다.")
    response = client.post(f"/cases/{case_id}/support-assess")
    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]
