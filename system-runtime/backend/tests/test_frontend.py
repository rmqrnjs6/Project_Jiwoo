from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_frontend_index_and_assets_are_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "AI Judgment System" in response.text
    assert "판단이 어떻게 변하는지" in response.text

    css = client.get("/static/styles.css")
    assert css.status_code == 200
    assert ".timeline-item" in css.text

    js = client.get("/static/app.js")
    assert js.status_code == 200
    assert "saved_paid_call" not in js.text
    assert "달라진 내용이 없어 이전 판단을 그대로 이어갑니다" in js.text


def test_case_list_endpoint_supports_frontend_navigation():
    created = client.post(
        "/cases",
        json={"title": "UI 목록 테스트", "original_input": "이 Case는 목록에 보여야 한다."},
    )
    assert created.status_code == 201
    case_id = created.json()["id"]

    response = client.get("/cases")
    assert response.status_code == 200
    items = response.json()
    item = next(entry for entry in items if entry["id"] == case_id)
    assert item["title"] == "UI 목록 테스트"
    assert item["status"] == "OPEN"
    assert "original_input" not in item


def test_app_alias_serves_same_frontend():
    response = client.get("/app")
    assert response.status_code == 200
    assert "AI Judgment System" in response.text
