import os
from pathlib import Path

TEST_DB = Path(__file__).with_name("test.db")
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
client = TestClient(app)


def test_case_evidence_judgment_and_history_flow():
    case_response = client.post(
        "/cases",
        json={"title": "검증", "original_input": "A가 사실이라고 생각한다."},
    )
    assert case_response.status_code == 201
    case_id = case_response.json()["id"]

    evidence_response = client.post(
        f"/cases/{case_id}/evidence",
        json={
            "content": "현재 공식 발표 전이다.",
            "source_type": "OFFICIAL",
            "is_primary_source": True,
            "reliability_score": 0.95,
        },
    )
    assert evidence_response.status_code == 201

    pending = client.post(
        f"/cases/{case_id}/judgments",
        json={
            "conclusion": "INSUFFICIENT_EVIDENCE",
            "ai_position": "UNSURE",
            "confidence": 0.35,
            "resolution_state": "PENDING",
            "position_text": "아직은 잘 모르겠어. 공식 발표를 기다려야 해.",
            "reasoning_summary": "현재 자료만으로 확정하기 어렵다.",
            "waiting_for": "공식 발표",
        },
    )
    assert pending.status_code == 201
    assert pending.json()["revision_no"] == 1
    assert pending.json()["resolution_state"] == "PENDING"

    revised = client.post(
        f"/cases/{case_id}/judgments",
        json={
            "conclusion": "CONTRADICTED",
            "ai_position": "DISAGREE",
            "confidence": 0.93,
            "resolution_state": "RESOLVED",
            "position_text": "이건 아닌 것 같아. 새 공식 자료와 충돌해.",
            "reasoning_summary": "새 공식 자료가 기존 입력을 직접 반박한다.",
        },
    )
    assert revised.status_code == 201
    assert revised.json()["revision_no"] == 2
    assert revised.json()["previous_judgment_id"] == pending.json()["id"]

    history = client.get(f"/cases/{case_id}/history")
    assert history.status_code == 200
    event_types = [event["event_type"] for event in history.json()]
    assert event_types == [
        "INPUT_CREATED",
        "EVIDENCE_ADDED",
        "JUDGMENT_CREATED",
        "REEVALUATION_STARTED",
        "JUDGMENT_REVISED",
        "REEVALUATION_COMPLETED",
    ]


def test_pending_requires_waiting_for():
    case_response = client.post(
        "/cases",
        json={"title": "대기 조건 검증", "original_input": "B가 사실이다."},
    )
    case_id = case_response.json()["id"]

    response = client.post(
        f"/cases/{case_id}/judgments",
        json={
            "conclusion": "UNCERTAIN",
            "ai_position": "UNSURE",
            "confidence": 0.4,
            "resolution_state": "PENDING",
            "position_text": "아직 판단할 수 없다.",
            "reasoning_summary": "추가 자료가 필요하다."
        },
    )
    assert response.status_code == 422
