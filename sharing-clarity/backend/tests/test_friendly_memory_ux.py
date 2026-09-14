from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_frontend_uses_calm_human_language_and_memory_oriented_timeline():
    page = client.get("/")
    assert page.status_code == 200
    assert "함께 확인한 과정을 남깁니다" in page.text
    assert "헷갈렸던 이야기, 같이 정리해볼까요?" in page.text
    assert "함께 볼 근거" in page.text
    assert "아직 결론을 서두르지 않았어요." in page.text
    assert "지금 가장 믿을 만한 근거" in page.text
    assert "함께 확인한 기록" in page.text

    js = client.get("/static/app.js")
    assert js.status_code == 200
    assert "왜 이렇게 평가했나요?" in js.text
    assert "달라진 것이 없다면 이전 판단을 그대로 이어갑니다" in js.text
    assert "현재 확인 결과를 새로 정리했어요." in js.text


def test_timeline_case_creation_is_human_readable():
    created = client.post(
        "/cases",
        json={"title": "친근한 타임라인", "original_input": "이 문장은 확인이 필요하다."},
    )
    assert created.status_code == 201
    case_id = created.json()["id"]

    timeline = client.get(f"/cases/{case_id}/timeline")
    assert timeline.status_code == 200
    items = timeline.json()
    assert items
    assert items[0]["title"] == "처음 확인을 시작했어요"
    assert "함께 남깁니다" in items[0]["summary"]
