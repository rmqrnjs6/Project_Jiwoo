import os

from fastapi.testclient import TestClient

from app.main import app
from app.models import ContextMode, DeliveryStyle, NudgeLevel
from app.support_engine import AffectSignal, AffectSignalType, SupportDecision, SupportProvider, get_support_provider


client = TestClient(app)


class FakeSoftProvider(SupportProvider):
    def assess(self, *, case):
        return SupportDecision(
            expression_summary="지침과 혼란을 표현하는 문장이 있다.",
            affect_signals=[
                AffectSignal(
                    signal=AffectSignalType.DISTRESS_LANGUAGE,
                    intensity=0.55,
                    textual_basis="너무 지쳤고 잘 모르겠다는 표현",
                )
            ],
            context_mode=ContextMode.AMBIGUOUS_CONTEXT,
            context_rationale="실제 경험인지 별도 맥락이 명시되지 않았다.",
            nudge_level=NudgeLevel.SOFT,
            delivery_style=DeliveryStyle.SUBTLE,
            recommendation_text="이 상태가 계속된다면 혼자만 정리하지 않는 것도 방법이야.",
            rationale_summary="텍스트의 부담감에만 가볍게 반응한다.",
        )


def create_case(text="A가 사실이라고 생각한다.") -> int:
    response = client.post("/cases", json={"title": "release test", "original_input": text})
    assert response.status_code == 201
    return response.json()["id"]


def create_manual_judgment(case_id: int, *, revised: bool = False) -> dict:
    payload = {
        "conclusion": "SUPPORTED",
        "ai_position": "AGREE",
        "confidence": 0.8,
        "resolution_state": "RESOLVED",
        "position_text": "현재 근거 기준으로는 맞다고 생각해.",
        "reasoning_summary": "테스트용 수동 판단",
        "evidence_assessments": [],
    }
    first = client.post(f"/cases/{case_id}/judgments", json=payload)
    assert first.status_code == 201
    if not revised:
        return first.json()

    payload["confidence"] = 0.9
    payload["position_text"] = "새 근거를 반영해도 현재는 맞다고 생각해."
    second = client.post(f"/cases/{case_id}/judgments", json=payload)
    assert second.status_code == 201
    return second.json()


def test_v1_release_locks_contextual_nudge_and_records_block():
    os.environ["RELEASE_PROFILE"] = "V1"
    app.dependency_overrides[get_support_provider] = lambda: FakeSoftProvider()
    try:
        case_id = create_case("요즘 너무 지쳤고 잘 모르겠다.")
        response = client.post(f"/cases/{case_id}/support-assess")
        assert response.status_code == 403
        detail = response.json()["detail"]
        assert detail["code"] == "FEATURE_LOCKED"
        assert detail["feature"] == "CONTEXTUAL_NUDGE"
        assert detail["release_profile"] == "V1"

        history = client.get(f"/cases/{case_id}/history").json()
        assert history[-1]["event_type"] == "FEATURE_ACCESS_BLOCKED"
        assert history[-1]["payload"]["feature"] == "CONTEXTUAL_NUDGE"
    finally:
        app.dependency_overrides.clear()


def test_release_endpoint_exposes_profile_and_feature_snapshot():
    os.environ["RELEASE_PROFILE"] = "V1"
    body = client.get("/release").json()
    assert body["profile"] == "V1"
    assert body["features"]["CORE_JUDGMENT"] is True
    assert body["features"]["REEVALUATION"] is True
    assert body["features"]["CONTEXTUAL_NUDGE"] is False
    assert body["features"]["RESPONSE_COMPOSER"] is False


def test_v2_unlocks_soft_nudge_and_composer_weaves_it_inline():
    os.environ["RELEASE_PROFILE"] = "V2"
    app.dependency_overrides[get_support_provider] = lambda: FakeSoftProvider()
    try:
        case_id = create_case("요즘 너무 지쳤고 잘 모르겠다.")
        create_manual_judgment(case_id)
        support = client.post(f"/cases/{case_id}/support-assess")
        assert support.status_code == 201

        response = client.post(f"/cases/{case_id}/compose-response")
        assert response.status_code == 200
        body = response.json()
        assert body["delivery_style"] == "SUBTLE"
        assert body["nudge_text"] in body["text"]
        assert body["judgment_text"] in body["text"]
        assert body["change_notice"] is None
        assert "\n\n" not in body["text"]

        history = client.get(f"/cases/{case_id}/history").json()
        assert history[-1]["event_type"] == "RESPONSE_COMPOSED"
        assert history[-1]["payload"]["nudge_included"] is True
    finally:
        app.dependency_overrides.clear()


def test_composer_exposes_reevaluation_notice_after_revision():
    os.environ["RELEASE_PROFILE"] = "V2"
    case_id = create_case()
    revised = create_manual_judgment(case_id, revised=True)

    response = client.post(f"/cases/{case_id}/compose-response")
    assert response.status_code == 200
    body = response.json()
    assert revised["revision_no"] == 2
    assert body["change_notice"] is not None
    assert "다시 검토" in body["change_notice"]
    assert body["text"].startswith(body["change_notice"])


def test_v1_locks_response_composer_even_when_internal_code_exists():
    os.environ["RELEASE_PROFILE"] = "V1"
    case_id = create_case()
    create_manual_judgment(case_id)

    response = client.post(f"/cases/{case_id}/compose-response")
    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["feature"] == "RESPONSE_COMPOSER"


def test_locked_v2_data_is_not_exposed_through_case_read():
    os.environ["RELEASE_PROFILE"] = "V2"
    app.dependency_overrides[get_support_provider] = lambda: FakeSoftProvider()
    try:
        case_id = create_case("요즘 너무 지쳤고 잘 모르겠다.")
        support = client.post(f"/cases/{case_id}/support-assess")
        assert support.status_code == 201
        assert len(client.get(f"/cases/{case_id}").json()["support_assessments"]) == 1

        os.environ["RELEASE_PROFILE"] = "V1"
        case_body = client.get(f"/cases/{case_id}").json()
        assert case_body["support_assessments"] == []

        locked_list = client.get(f"/cases/{case_id}/support-assessments")
        assert locked_list.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_composer_says_reaffirmed_when_reevaluation_keeps_same_state():
    os.environ["RELEASE_PROFILE"] = "V2"
    case_id = create_case()
    payload = {
        "conclusion": "SUPPORTED",
        "ai_position": "AGREE",
        "confidence": 0.8,
        "resolution_state": "RESOLVED",
        "position_text": "현재 근거 기준으로는 맞다고 생각해.",
        "reasoning_summary": "첫 판단",
        "evidence_assessments": [],
    }
    first = client.post(f"/cases/{case_id}/judgments", json=payload)
    assert first.status_code == 201

    payload["reasoning_summary"] = "다시 검토했지만 핵심 판단은 같다."
    second = client.post(f"/cases/{case_id}/judgments", json=payload)
    assert second.status_code == 201

    history = client.get(f"/cases/{case_id}/history").json()
    assert "JUDGMENT_REAFFIRMED" in [event["event_type"] for event in history]
    completed = [event for event in history if event["event_type"] == "REEVALUATION_COMPLETED"][-1]
    assert completed["payload"]["state_changed"] is False

    response = client.post(f"/cases/{case_id}/compose-response")
    assert response.status_code == 200
    assert "판단을 유지" in response.json()["change_notice"]
