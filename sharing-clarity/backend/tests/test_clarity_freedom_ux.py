from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_frontend_centers_current_clarity_and_lower_information_load():
    page = client.get("/")
    assert page.status_code == 200
    assert "현재 확인된 핵심" in page.text
    assert "아직 확인이 필요한 부분" in page.text
    assert "확인에 쓰는 시간을 줄이고, 살아가는 데 쓰는 시간을 늘립니다." in page.text
    assert "공유용 요약 복사" in page.text
    assert "헷갈렸던 이야기, 같이 정리해볼까요?" in page.text


def test_frontend_builds_shareable_summary_without_new_api_call():
    js = client.get("/static/app.js")
    assert js.status_code == 200
    assert "function buildShareSummary()" in js.text
    assert "navigator.clipboard" in js.text
    assert "새로운 근거가 나오면 내용이 달라질 수 있습니다." in js.text
    assert "현재 확인 가능한 범위는 여기까지예요." in js.text
