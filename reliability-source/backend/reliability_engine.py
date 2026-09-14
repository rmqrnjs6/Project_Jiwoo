from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from .models import Case, Evidence, EvidenceSourceType, SourceVerificationStatus


AUTHORITY_SCORE: dict[EvidenceSourceType, float] = {
    EvidenceSourceType.PRIMARY: 1.00,
    EvidenceSourceType.OFFICIAL: 0.95,
    EvidenceSourceType.INSTITUTIONAL: 0.88,
    EvidenceSourceType.NEWS: 0.75,
    EvidenceSourceType.WEB: 0.55,
    EvidenceSourceType.USER: 0.45,
    EvidenceSourceType.AI: 0.35,
    EvidenceSourceType.UNKNOWN: 0.20,
}

DIRECTNESS_BASE: dict[EvidenceSourceType, float] = {
    EvidenceSourceType.PRIMARY: 0.95,
    EvidenceSourceType.OFFICIAL: 0.90,
    EvidenceSourceType.INSTITUTIONAL: 0.80,
    EvidenceSourceType.NEWS: 0.65,
    EvidenceSourceType.WEB: 0.50,
    EvidenceSourceType.USER: 0.45,
    EvidenceSourceType.AI: 0.35,
    EvidenceSourceType.UNKNOWN: 0.30,
}


class ReliabilityDecision(BaseModel):
    authority_score: float = Field(ge=0.0, le=1.0)
    originality_score: float = Field(ge=0.0, le=1.0)
    directness_score: float = Field(ge=0.0, le=1.0)
    recency_score: float = Field(ge=0.0, le=1.0)
    corroboration_score: float = Field(ge=0.0, le=1.0)
    final_score: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1)
    method_version: str = Field(min_length=1)


class ReliabilityProvider(ABC):
    @abstractmethod
    def assess(
        self,
        *,
        case: Case,
        evidence: Evidence,
        peer_evidence: list[Evidence],
    ) -> ReliabilityDecision:
        raise NotImplementedError


def _recency_score(published_at: datetime | None) -> float:
    if published_at is None:
        return 0.50

    now = datetime.now(timezone.utc)
    published = published_at
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)

    age_days = (now - published).total_seconds() / 86400
    if age_days < -1:
        # Future-dated evidence is suspicious metadata, not "more recent" evidence.
        return 0.20
    if age_days <= 30:
        return 1.00
    if age_days <= 180:
        return 0.90
    if age_days <= 365:
        return 0.80
    if age_days <= 1095:
        return 0.65
    return 0.50


def _weighted_score(
    *,
    authority: float,
    originality: float,
    directness: float,
    recency: float,
    corroboration: float,
) -> float:
    base = (
        authority * 0.35
        + originality * 0.20
        + directness * 0.20
        + recency * 0.10
        + corroboration * 0.15
    )
    return round(max(0.0, min(1.0, base)), 4)


class MetadataReliabilityProvider(ReliabilityProvider):
    """Deterministic V1 reliability estimator.

    This provider deliberately does not pretend to semantically prove agreement or
    contradiction between sources. Cross-source corroboration is left neutral until
    a semantic provider is connected. That limitation is exposed in the rationale.
    """

    method_version = "metadata-v3"

    def assess(
        self,
        *,
        case: Case,
        evidence: Evidence,
        peer_evidence: list[Evidence],
    ) -> ReliabilityDecision:
        effective_type = evidence.effective_source_type
        effective_primary = evidence.effective_is_primary_source
        verified = evidence.source_verification_status == SourceVerificationStatus.VERIFIED

        authority = AUTHORITY_SCORE[effective_type]
        originality = 1.0 if (
            effective_primary or effective_type == EvidenceSourceType.PRIMARY
        ) else 0.45
        directness = max(
            DIRECTNESS_BASE[effective_type],
            0.90 if effective_primary else 0.0,
        )

        # Claimed source metadata is useful context, not proof. Until verification,
        # keep metadata-derived authority/originality/directness from dominating.
        if not verified:
            authority = min(authority, 0.70)
            originality = min(originality, 0.60)
            directness = min(directness, 0.70)
        recency = _recency_score(evidence.source_published_at)

        # Cross-source corroboration is intentionally neutral in metadata-v3.
        corroboration = 0.50
        final_score = _weighted_score(
            authority=authority,
            originality=originality,
            directness=directness,
            recency=recency,
            corroboration=corroboration,
        )

        rationale = (
            f"claimed_source_type={evidence.claimed_source_type.value}, "
            f"verification={evidence.source_verification_status.value}, "
            f"effective_source_type={effective_type.value}, primary={effective_primary}; "
            "metadata-v3 scores authority/originality/directness/recency and caps "
            "unverified source claims. "
            "Cross-source semantic corroboration is not yet inferred, "
            "so corroboration remains neutral."
        )

        return ReliabilityDecision(
            authority_score=authority,
            originality_score=originality,
            directness_score=directness,
            recency_score=recency,
            corroboration_score=corroboration,
            final_score=final_score,
            rationale=rationale,
            method_version=self.method_version,
        )


def get_reliability_provider() -> ReliabilityProvider:
    return MetadataReliabilityProvider()
