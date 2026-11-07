"""Characterize metadata-v3; these tests do not establish factual accuracy."""
from types import SimpleNamespace

import pytest

from app import reliability_engine
from app.models import EvidenceSourceType, SourceVerificationStatus


def assess(monkeypatch, peers):
    monkeypatch.setattr(reliability_engine, "_recency_score", lambda _: 0.5)
    evidence = SimpleNamespace(
        effective_source_type=EvidenceSourceType.OFFICIAL,
        effective_is_primary_source=True,
        claimed_source_type=EvidenceSourceType.OFFICIAL,
        source_verification_status=SourceVerificationStatus.UNVERIFIED,
        source_published_at=None,
    )
    return reliability_engine.MetadataReliabilityProvider().assess(
        case=SimpleNamespace(), evidence=evidence, peer_evidence=peers
    )


def test_neutral_corroboration_contributes_seven_point_five_percentage_points(monkeypatch):
    result = assess(monkeypatch, [])
    assert result.corroboration_score == 0.5
    assert result.final_score == pytest.approx(0.63)
    # All other inputs are identical; remove only the corroboration contribution.
    without = reliability_engine._weighted_score(
        authority=0.7, originality=0.6, directness=0.7,
        recency=0.5, corroboration=0.0,
    )
    assert result.final_score - without == pytest.approx(0.075)
    assert result.method_version == "metadata-v3"
    assert "not yet inferred" in result.rationale


def test_peer_agreement_and_contradiction_are_not_semantically_evaluated(monkeypatch):
    empty = assess(monkeypatch, [])
    supporting = assess(monkeypatch, [SimpleNamespace(content="claim supported")])
    contradicting = assess(monkeypatch, [SimpleNamespace(content="claim contradicted")])
    assert empty == supporting == contradicting
