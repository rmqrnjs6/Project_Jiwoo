import os

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def create_case(title: str = "permission test") -> int:
    response = client.post(
        "/cases",
        json={"title": title, "original_input": "A가 사실이라고 생각한다."},
    )
    assert response.status_code == 201
    return response.json()["id"]


def add_resolved_judgment(case_id: int, *, text: str = "현재 근거 기준으로 판단 가능") -> dict:
    response = client.post(
        f"/cases/{case_id}/judgments",
        json={
            "conclusion": "SUPPORTED",
            "ai_position": "AGREE",
            "confidence": 0.9,
            "resolution_state": "RESOLVED",
            "position_text": text,
            "reasoning_summary": "테스트용 해결된 판단",
            "evidence_assessments": [],
        },
    )
    assert response.status_code == 201
    return response.json()


def add_pending_judgment(case_id: int) -> dict:
    response = client.post(
        f"/cases/{case_id}/judgments",
        json={
            "conclusion": "INSUFFICIENT_EVIDENCE",
            "ai_position": "UNSURE",
            "confidence": 0.35,
            "resolution_state": "PENDING",
            "position_text": "아직 기다려야 한다.",
            "reasoning_summary": "공식 발표 전이라 판단을 보류한다.",
            "waiting_for": "공식 발표",
            "evidence_assessments": [],
        },
    )
    assert response.status_code == 201
    return response.json()


def set_permission(case_id: int, *, can_execute: bool, allowed_actions: list[str]) -> dict:
    response = client.put(
        f"/cases/{case_id}/permission",
        json={"can_execute": can_execute, "allowed_actions": allowed_actions},
    )
    assert response.status_code == 200
    return response.json()


def run_action(case_id: int, judgment_id: int, action_type: str, parameters: dict) -> dict:
    response = client.post(
        f"/cases/{case_id}/actions",
        json={
            "judgment_id": judgment_id,
            "action_type": action_type,
            "parameters": parameters,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_v1_locks_permission_action_feature_and_records_history():
    os.environ["RELEASE_PROFILE"] = "V1"
    case_id = create_case()

    response = client.get(f"/cases/{case_id}/permission")
    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "FEATURE_LOCKED"
    assert detail["feature"] == "PERMISSION_ACTION"

    history = client.get(f"/cases/{case_id}/history").json()
    assert history[-1]["event_type"] == "FEATURE_ACCESS_BLOCKED"
    assert history[-1]["payload"]["feature"] == "PERMISSION_ACTION"


def test_v15_default_policy_blocks_execution_and_preserves_case():
    os.environ["RELEASE_PROFILE"] = "V1_5"
    case_id = create_case()
    judgment = add_resolved_judgment(case_id)

    action = run_action(
        case_id,
        judgment["id"],
        "SET_CASE_STATUS",
        {"status": "CLOSED"},
    )
    assert action["status"] == "BLOCKED"
    assert action["blocked_reason"] == "EXECUTION_DISABLED"
    assert client.get(f"/cases/{case_id}").json()["status"] == "OPEN"

    history = client.get(f"/cases/{case_id}/history").json()
    assert history[-2]["event_type"] == "ACTION_ATTEMPTED"
    assert history[-1]["event_type"] == "ACTION_BLOCKED"
    assert history[-1]["payload"]["reason"] == "EXECUTION_DISABLED"


def test_scope_denied_even_when_execution_is_enabled():
    os.environ["RELEASE_PROFILE"] = "V1_5"
    case_id = create_case()
    judgment = add_resolved_judgment(case_id)
    policy = set_permission(case_id, can_execute=True, allowed_actions=["SET_CASE_TITLE"])
    assert policy["can_execute"] is True

    action = run_action(
        case_id,
        judgment["id"],
        "SET_CASE_STATUS",
        {"status": "CLOSED"},
    )
    assert action["status"] == "BLOCKED"
    assert action["blocked_reason"] == "SCOPE_DENIED"
    assert client.get(f"/cases/{case_id}").json()["status"] == "OPEN"


def test_allowed_latest_resolved_action_executes_and_is_audited():
    os.environ["RELEASE_PROFILE"] = "V1_5"
    case_id = create_case()
    judgment = add_resolved_judgment(case_id)
    set_permission(case_id, can_execute=True, allowed_actions=["SET_CASE_STATUS"])

    action = run_action(
        case_id,
        judgment["id"],
        "SET_CASE_STATUS",
        {"status": "CLOSED"},
    )
    assert action["status"] == "COMPLETED"
    assert action["blocked_reason"] is None
    assert action["result"]["before"]["status"] == "OPEN"
    assert action["result"]["after"]["status"] == "CLOSED"
    assert client.get(f"/cases/{case_id}").json()["status"] == "CLOSED"

    history = client.get(f"/cases/{case_id}/history").json()
    event_types = [item["event_type"] for item in history]
    assert "PERMISSION_CHANGED" in event_types
    assert event_types[-2:] == ["ACTION_ATTEMPTED", "ACTION_COMPLETED"]

    actions = client.get(f"/cases/{case_id}/actions")
    assert actions.status_code == 200
    assert actions.json()[-1]["status"] == "COMPLETED"


def test_stale_judgment_cannot_execute_even_with_permission():
    os.environ["RELEASE_PROFILE"] = "V1_5"
    case_id = create_case()
    old = add_resolved_judgment(case_id, text="첫 판단")
    newest = add_resolved_judgment(case_id, text="재판단")
    assert newest["revision_no"] == 2
    set_permission(case_id, can_execute=True, allowed_actions=["SET_CASE_STATUS"])

    action = run_action(
        case_id,
        old["id"],
        "SET_CASE_STATUS",
        {"status": "CLOSED"},
    )
    assert action["status"] == "BLOCKED"
    assert action["blocked_reason"] == "STALE_JUDGMENT"
    assert client.get(f"/cases/{case_id}").json()["status"] == "OPEN"


def test_pending_judgment_cannot_execute_even_with_permission_and_scope():
    os.environ["RELEASE_PROFILE"] = "V1_5"
    case_id = create_case()
    judgment = add_pending_judgment(case_id)
    set_permission(case_id, can_execute=True, allowed_actions=["SET_CASE_STATUS"])

    action = run_action(
        case_id,
        judgment["id"],
        "SET_CASE_STATUS",
        {"status": "CLOSED"},
    )
    assert action["status"] == "BLOCKED"
    assert action["blocked_reason"] == "JUDGMENT_NOT_RESOLVED"
    assert client.get(f"/cases/{case_id}").json()["status"] == "OPEN"


def test_invalid_parameters_are_blocked_without_side_effect():
    os.environ["RELEASE_PROFILE"] = "V1_5"
    case_id = create_case()
    judgment = add_resolved_judgment(case_id)
    set_permission(case_id, can_execute=True, allowed_actions=["SET_CASE_STATUS"])

    action = run_action(
        case_id,
        judgment["id"],
        "SET_CASE_STATUS",
        {"status": "MAYBE"},
    )
    assert action["status"] == "BLOCKED"
    assert action["blocked_reason"] == "INVALID_PARAMETERS"
    assert client.get(f"/cases/{case_id}").json()["status"] == "OPEN"
