import os
from pathlib import Path

TEST_DB = Path(__file__).with_name("test_step12.db")
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.judgment_engine import (
    EngineDecision,
    EvidenceAssessment,
    EvidenceStance,
    JudgmentProvider,
    get_judgment_provider,
)
from app.main import app
from app.models import EvidenceSourceType, JudgmentConclusion, ResolutionState, SourceVerificationStatus
from app.source_verification import (
    SourceVerificationDecision,
    SourceVerificationProvider,
    get_source_verification_provider,
)

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
client = TestClient(app)


def make_case(*, source_url="https://example.com/report", reliability_score=0.99):
    case = client.post(
        "/cases",
        json={"title": "출처 검증 테스트", "original_input": "A가 사실이다."},
    )
    assert case.status_code == 201
    case_id = case.json()["id"]
    evidence = client.post(
        f"/cases/{case_id}/evidence",
        json={
            "content": "A를 지지한다고 주장하는 자료",
            "source_type": "PRIMARY",
            "source_url": source_url,
            "is_primary_source": True,
            "reliability_score": reliability_score,
        },
    )
    assert evidence.status_code == 201
    return case_id, evidence.json()["id"]


def get_evidence(case_id, evidence_id):
    case = client.get(f"/cases/{case_id}")
    assert case.status_code == 200
    return next(item for item in case.json()["evidence"] if item["id"] == evidence_id)


def test_local_source_check_never_promotes_public_url_to_verified():
    case_id, evidence_id = make_case()

    response = client.post(f"/cases/{case_id}/evidence/{evidence_id}/verify-source")
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "PARTIALLY_VERIFIED"
    assert body["verified_source_type"] is None
    assert body["verified_is_primary_source"] is None
    assert body["checks"]["network_request_performed"] is False
    assert body["checks"]["host_is_public"] is True

    stored = get_evidence(case_id, evidence_id)
    assert stored["source_verification_status"] == "PARTIALLY_VERIFIED"
    # A local URL shape check is not authority verification, so the unverified cap remains.
    assert stored["reliability_score"] <= 0.70


def test_rechecking_same_source_is_reaffirmed_not_revised():
    case_id, evidence_id = make_case()
    assert client.post(f"/cases/{case_id}/evidence/{evidence_id}/verify-source").status_code == 201
    assert client.post(f"/cases/{case_id}/evidence/{evidence_id}/verify-source").status_code == 201

    history = client.get(f"/cases/{case_id}/history").json()
    source_events = [
        item["event_type"] for item in history if item["event_type"].startswith("SOURCE_VERIFICATION")
    ]
    assert source_events == ["SOURCE_VERIFICATION_ASSESSED", "SOURCE_VERIFICATION_REAFFIRMED"]

    reliability_events = [
        item["event_type"] for item in history if item["event_type"].startswith("RELIABILITY")
    ]
    assert reliability_events[-1] == "RELIABILITY_REAFFIRMED"


def test_private_or_local_url_is_invalidated_without_network_access():
    case_id, evidence_id = make_case(source_url="http://127.0.0.1/internal")
    response = client.post(f"/cases/{case_id}/evidence/{evidence_id}/verify-source")
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "INVALID"
    assert body["checks"]["host_is_public"] is False
    assert body["checks"]["network_request_performed"] is False


class VerifiedProvider(SourceVerificationProvider):
    provider_name = "trusted-test-verifier"
    method_version = "trusted-test-v1"

    def verify(self, *, evidence):
        return SourceVerificationDecision(
            status=SourceVerificationStatus.VERIFIED,
            verified_source_type=EvidenceSourceType.OFFICIAL,
            verified_is_primary_source=True,
            rationale="Test verifier independently confirmed the official primary source.",
            checks={"independent_confirmation": True, "network_request_performed": False},
            method_version=self.method_version,
        )


class CountingJudgmentProvider(JudgmentProvider):
    provider_name = "test-judgment"
    model_name = "test-model"

    def __init__(self):
        self.calls = 0

    def judge(self, *, case, evidence):
        self.calls += 1
        return EngineDecision(
            conclusion=JudgmentConclusion.SUPPORTED,
            confidence=0.85,
            resolution_state=ResolutionState.RESOLVED,
            position_text="현재 근거 기준으로는 맞다고 본다.",
            reasoning_summary="현재 근거가 입력을 지지한다.",
            evidence_assessments=[
                EvidenceAssessment(
                    evidence_id=item.id,
                    stance=EvidenceStance.SUPPORT,
                    relevance=1.0,
                    reliability=item.reliability_score or 0.5,
                    rationale="입력을 지지한다.",
                )
                for item in evidence
            ],
        )


def test_verified_source_lifts_metadata_cap_and_next_judgment_uses_source_verified_trigger():
    case_id, evidence_id = make_case()
    judgment_provider = CountingJudgmentProvider()
    app.dependency_overrides[get_judgment_provider] = lambda: judgment_provider
    try:
        first = client.post(f"/cases/{case_id}/judge")
        assert first.status_code == 201
        assert first.json()["reevaluation_trigger"] == "INITIAL"

        app.dependency_overrides[get_source_verification_provider] = lambda: VerifiedProvider()
        verification = client.post(f"/cases/{case_id}/evidence/{evidence_id}/verify-source")
        assert verification.status_code == 201
        assert verification.json()["status"] == "VERIFIED"

        stored = get_evidence(case_id, evidence_id)
        assert stored["verified_source_type"] == "OFFICIAL"
        assert stored["verified_is_primary_source"] is True
        assert stored["reliability_source"] == "metadata-v3"
        assert stored["reliability_score"] > 0.80

        second = client.post(f"/cases/{case_id}/judge")
        assert second.status_code == 201
        assert second.json()["reevaluation_trigger"] == "SOURCE_VERIFIED"
        assert judgment_provider.calls == 2
    finally:
        app.dependency_overrides.clear()


def test_source_verification_history_is_queryable():
    case_id, evidence_id = make_case()
    client.post(f"/cases/{case_id}/evidence/{evidence_id}/verify-source")
    history = client.get(f"/cases/{case_id}/evidence/{evidence_id}/source-verifications")
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["revision_no"] == 1
    assert history.json()[0]["method_version"] == "local-metadata-v1"


def test_partial_source_review_causes_source_reviewed_not_new_evidence_trigger():
    case_id, evidence_id = make_case()
    judgment_provider = CountingJudgmentProvider()
    app.dependency_overrides[get_judgment_provider] = lambda: judgment_provider
    try:
        first = client.post(f"/cases/{case_id}/judge")
        assert first.status_code == 201

        review = client.post(f"/cases/{case_id}/evidence/{evidence_id}/verify-source")
        assert review.status_code == 201
        assert review.json()["status"] == "PARTIALLY_VERIFIED"

        second = client.post(f"/cases/{case_id}/judge")
        assert second.status_code == 201
        assert second.json()["reevaluation_trigger"] == "SOURCE_REVIEWED"
    finally:
        app.dependency_overrides.clear()
