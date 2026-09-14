from __future__ import annotations

import ipaddress
from abc import ABC, abstractmethod
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, model_validator

from .models import Evidence, EvidenceSourceType, SourceVerificationStatus


class SourceVerificationDecision(BaseModel):
    status: SourceVerificationStatus
    verified_source_type: EvidenceSourceType | None = None
    verified_is_primary_source: bool | None = None
    rationale: str = Field(min_length=1)
    checks: dict = Field(default_factory=dict)
    method_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_verified_fields(self):
        if self.status == SourceVerificationStatus.VERIFIED:
            if self.verified_source_type is None:
                raise ValueError("VERIFIED source requires verified_source_type")
            if self.verified_is_primary_source is None:
                raise ValueError("VERIFIED source requires verified_is_primary_source")
        elif self.verified_source_type is not None or self.verified_is_primary_source is not None:
            raise ValueError("Only VERIFIED sources may carry verified source metadata")
        return self


class SourceVerificationProvider(ABC):
    provider_name = "unknown"
    method_version = "unknown"

    @abstractmethod
    def verify(self, *, evidence: Evidence) -> SourceVerificationDecision:
        raise NotImplementedError


def _is_public_host(host: str | None) -> bool:
    if not host:
        return False
    normalized = host.rstrip(".").casefold()
    if normalized == "localhost" or normalized.endswith(".localhost") or normalized.endswith(".local"):
        return False

    try:
        ip = ipaddress.ip_address(normalized)
    except ValueError:
        # A normal DNS hostname is only structurally plausible here. We deliberately
        # do not resolve it or make a network request in the local verifier.
        return True

    return not any(
        (
            ip.is_private,
            ip.is_loopback,
            ip.is_link_local,
            ip.is_multicast,
            ip.is_reserved,
            ip.is_unspecified,
        )
    )


class LocalMetadataVerificationProvider(SourceVerificationProvider):
    """No-network source metadata check.

    This provider can reject obviously unsafe/local URLs or mark a public-looking
    URL as PARTIALLY_VERIFIED. It never claims that a source is truly official,
    primary, or authentic because that requires stronger external verification.
    """

    provider_name = "local-metadata"
    method_version = "local-metadata-v1"

    def verify(self, *, evidence: Evidence) -> SourceVerificationDecision:
        if not evidence.source_url:
            return SourceVerificationDecision(
                status=SourceVerificationStatus.UNVERIFIED,
                rationale=(
                    "No source URL is available. The source claim remains unverified; "
                    "no external request was made."
                ),
                checks={
                    "url_present": False,
                    "network_request_performed": False,
                },
                method_version=self.method_version,
            )

        parsed = urlsplit(evidence.source_url)
        host_public = _is_public_host(parsed.hostname)
        scheme_supported = parsed.scheme in {"http", "https"}
        has_credentials = parsed.username is not None or parsed.password is not None

        checks = {
            "url_present": True,
            "scheme": parsed.scheme,
            "scheme_supported": scheme_supported,
            "https": parsed.scheme == "https",
            "host_present": bool(parsed.hostname),
            "host_is_public": host_public,
            "embedded_credentials": has_credentials,
            "network_request_performed": False,
        }

        if not scheme_supported or not parsed.hostname or not host_public or has_credentials:
            return SourceVerificationDecision(
                status=SourceVerificationStatus.INVALID,
                rationale=(
                    "The stored source URL failed local safety/structure checks. "
                    "This does not judge the claim itself, but the URL should not be trusted as a source locator."
                ),
                checks=checks,
                method_version=self.method_version,
            )

        return SourceVerificationDecision(
            status=SourceVerificationStatus.PARTIALLY_VERIFIED,
            rationale=(
                "The URL is structurally plausible and points to a public-looking host. "
                "The domain owner, document authenticity, source authority, and content were not independently verified."
            ),
            checks=checks,
            method_version=self.method_version,
        )


def get_source_verification_provider() -> SourceVerificationProvider:
    return LocalMetadataVerificationProvider()
