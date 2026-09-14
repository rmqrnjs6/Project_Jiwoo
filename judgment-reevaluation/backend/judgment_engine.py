from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Iterable

from pydantic import BaseModel, Field, model_validator

from .models import (
    Case,
    Evidence,
    EvidenceSourceType,
    JudgmentConclusion,
    ResolutionState,
    SourceVerificationStatus,
)


DEFAULT_RELIABILITY: dict[EvidenceSourceType, float] = {
    EvidenceSourceType.PRIMARY: 1.00,
    EvidenceSourceType.OFFICIAL: 0.95,
    EvidenceSourceType.INSTITUTIONAL: 0.90,
    EvidenceSourceType.NEWS: 0.80,
    EvidenceSourceType.WEB: 0.60,
    EvidenceSourceType.USER: 0.50,
    EvidenceSourceType.AI: 0.40,
    EvidenceSourceType.UNKNOWN: 0.20,
}


class EvidenceStance(str, Enum):
    SUPPORT = "SUPPORT"
    CONTRADICT = "CONTRADICT"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


class EvidenceAssessment(BaseModel):
    evidence_id: int
    stance: EvidenceStance
    relevance: float = Field(ge=0.0, le=1.0)
    reliability: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1)


class EngineDecision(BaseModel):
    conclusion: JudgmentConclusion
    confidence: float = Field(ge=0.0, le=1.0)
    resolution_state: ResolutionState
    position_text: str = Field(min_length=1)
    reasoning_summary: str = Field(min_length=1)
    unresolved_reason: str | None = None
    waiting_for: str | None = None
    evidence_assessments: list[EvidenceAssessment] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_state(self):
        if self.resolution_state == ResolutionState.PENDING:
            if not self.waiting_for:
                raise ValueError("PENDING requires waiting_for")
            if self.conclusion not in {
                JudgmentConclusion.UNCERTAIN,
                JudgmentConclusion.INSUFFICIENT_EVIDENCE,
            }:
                raise ValueError("PENDING cannot be a resolved conclusion")

        if self.resolution_state == ResolutionState.UNRESOLVED:
            if not self.unresolved_reason:
                raise ValueError("UNRESOLVED requires unresolved_reason")
            if self.conclusion not in {
                JudgmentConclusion.UNCERTAIN,
                JudgmentConclusion.INSUFFICIENT_EVIDENCE,
            }:
                raise ValueError("UNRESOLVED cannot be a resolved conclusion")

        if self.resolution_state == ResolutionState.RESOLVED:
            if self.waiting_for:
                raise ValueError("RESOLVED cannot have waiting_for")
            if self.conclusion not in {
                JudgmentConclusion.SUPPORTED,
                JudgmentConclusion.CONTRADICTED,
            }:
                raise ValueError("RESOLVED requires SUPPORTED or CONTRADICTED")

        return self


class JudgmentProviderError(RuntimeError):
    """Sanitized provider failure that is safe to expose through the API."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        http_status: int,
        retryable: bool,
        request_id: str | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.retryable = retryable
        self.request_id = request_id

    def as_detail(self) -> dict[str, Any]:
        detail: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
        }
        if self.request_id:
            detail["request_id"] = self.request_id
        return detail


def _translate_openai_exception(exc: Exception) -> JudgmentProviderError:
    """Translate official SDK failures without leaking raw provider details.

    The official SDK exposes typed exceptions such as APITimeoutError,
    APIConnectionError, RateLimitError and APIStatusError subclasses. We use
    both the public class name and status_code so this remains testable without
    importing the external SDK in unit tests.
    """

    name = type(exc).__name__
    status_code = getattr(exc, "status_code", None)
    request_id = getattr(exc, "request_id", None)

    if name == "APITimeoutError":
        return JudgmentProviderError(
            code="OPENAI_TIMEOUT",
            message="The AI provider timed out before returning a judgment.",
            http_status=504,
            retryable=True,
            request_id=request_id,
        )
    if name == "APIConnectionError":
        return JudgmentProviderError(
            code="OPENAI_CONNECTION_ERROR",
            message="The AI provider could not be reached.",
            http_status=503,
            retryable=True,
            request_id=request_id,
        )
    if name == "RateLimitError" or status_code == 429:
        return JudgmentProviderError(
            code="OPENAI_RATE_LIMITED",
            message="The AI provider rate limit was reached.",
            http_status=429,
            retryable=True,
            request_id=request_id,
        )
    if name == "AuthenticationError" or status_code == 401:
        return JudgmentProviderError(
            code="OPENAI_AUTHENTICATION_ERROR",
            message="The AI provider credentials are not valid.",
            http_status=503,
            retryable=False,
            request_id=request_id,
        )
    if name == "PermissionDeniedError" or status_code == 403:
        return JudgmentProviderError(
            code="OPENAI_PERMISSION_DENIED",
            message="The configured AI provider credentials cannot use this resource.",
            http_status=503,
            retryable=False,
            request_id=request_id,
        )
    if name in {"BadRequestError", "UnprocessableEntityError", "NotFoundError"} or status_code in {400, 404, 422}:
        return JudgmentProviderError(
            code="OPENAI_REQUEST_REJECTED",
            message="The AI provider rejected the configured judgment request.",
            http_status=502,
            retryable=False,
            request_id=request_id,
        )
    if name == "InternalServerError" or (isinstance(status_code, int) and status_code >= 500):
        return JudgmentProviderError(
            code="OPENAI_SERVER_ERROR",
            message="The AI provider returned a server error.",
            http_status=503,
            retryable=True,
            request_id=request_id,
        )

    return JudgmentProviderError(
        code="OPENAI_PROVIDER_ERROR",
        message="The AI provider failed to produce a judgment.",
        http_status=502,
        retryable=False,
        request_id=request_id,
    )


def _validate_decision_evidence(decision: EngineDecision, evidence: list[Evidence]) -> None:
    expected = [item.id for item in evidence]
    actual = [item.evidence_id for item in decision.evidence_assessments]

    if len(actual) != len(set(actual)):
        raise JudgmentProviderError(
            code="OPENAI_INVALID_RESPONSE",
            message="The AI judgment contained duplicate evidence assessments.",
            http_status=502,
            retryable=True,
        )

    if set(actual) != set(expected):
        raise JudgmentProviderError(
            code="OPENAI_INVALID_RESPONSE",
            message="The AI judgment did not assess exactly the evidence supplied to it.",
            http_status=502,
            retryable=True,
        )


class JudgmentProvider(ABC):
    provider_name = "unknown"
    model_name: str | None = None
    configured = True

    @abstractmethod
    def judge(self, *, case: Case, evidence: list[Evidence]) -> EngineDecision:
        raise NotImplementedError


def effective_reliability(evidence: Evidence) -> float:
    # A user-provided score is preserved as provenance, but is not treated as
    # independently verified confidence. Until the system assesses it, cap it.
    if evidence.reliability_score is not None:
        if evidence.reliability_source == "USER_PROVIDED":
            return min(evidence.reliability_score, 0.60)
        return evidence.reliability_score

    baseline = DEFAULT_RELIABILITY[evidence.effective_source_type]
    if evidence.source_verification_status != SourceVerificationStatus.VERIFIED:
        return min(baseline, 0.60)
    return baseline


def _serialize_evidence(evidence: Iterable[Evidence]) -> list[dict]:
    return [
        {
            "evidence_id": item.id,
            "content": item.content,
            "claimed_source_type": item.claimed_source_type.value,
            "source_verification_status": item.source_verification_status.value,
            "verified_source_type": (
                item.verified_source_type.value if item.verified_source_type else None
            ),
            "effective_source_type": item.effective_source_type.value,
            "source_url": item.source_url,
            "claimed_is_primary_source": item.claimed_is_primary_source,
            "effective_is_primary_source": item.effective_is_primary_source,
            "reliability": effective_reliability(item),
        }
        for item in evidence
    ]


SYSTEM_INSTRUCTION = """
You are the judgment engine for an evidence-tracking system.

Your job is NOT to declare eternal truth. Your job is to form the best CURRENT
position from the case input and the evidence supplied in this request.

Rules:
1. Treat the user's original input as the CLAIM TO EVALUATE, not as evidence.
2. Use only the evidence supplied in the request as factual support for the
   judgment. Do not silently use model memory as evidence.
3. Evaluate every evidence item for stance, relevance, and reliability.
4. Prefer primary/original and official evidence over derivative evidence when
   they conflict, but do not treat source type alone as proof.
5. SUPPORTED means the currently available evidence materially supports the
   original input.
6. CONTRADICTED means the currently available evidence materially contradicts
   the original input.
7. UNCERTAIN means meaningful evidence conflicts or points in incompatible
   directions.
8. INSUFFICIENT_EVIDENCE means there is not enough relevant evidence to decide.
9. RESOLVED is only for SUPPORTED or CONTRADICTED at the current point in time.
10. UNRESOLVED means the matter cannot currently be resolved and there is no
    specific future event that is known to unlock the judgment.
11. PENDING means a specific future event/data source is known and should be
    awaited before re-evaluation. Populate waiting_for precisely.
12. Never manufacture a future event merely to choose PENDING.
13. position_text should sound like an AI taking a clear but revisable stance:
    agree, disagree, or admit uncertainty. Do not overclaim certainty.
14. reasoning_summary must explain the decision using the supplied evidence.
""".strip()


class OpenAIJudgmentProvider(JudgmentProvider):
    """Production OpenAI Responses API provider with structured output."""

    provider_name = "openai"

    def __init__(
        self,
        *,
        model: str | None = None,
        client: Any | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        max_output_tokens: int | None = None,
        reasoning_effort: str | None = None,
        max_input_chars: int | None = None,
        max_evidence_items: int | None = None,
    ):
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
        self.model_name = self.model
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30"))
        )
        self.max_retries = (
            max_retries
            if max_retries is not None
            else int(os.getenv("OPENAI_MAX_RETRIES", "1"))
        )
        self.max_output_tokens = (
            max_output_tokens
            if max_output_tokens is not None
            else int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "1800"))
        )
        self.reasoning_effort = (
            reasoning_effort
            if reasoning_effort is not None
            else os.getenv("OPENAI_REASONING_EFFORT", "low").strip().lower()
        )
        allowed_efforts = {"none", "minimal", "low", "medium", "high", "xhigh", "max"}
        if self.reasoning_effort not in allowed_efforts:
            raise ValueError("OPENAI_REASONING_EFFORT is not a supported value")
        if self.max_output_tokens < 256:
            raise ValueError("OPENAI_MAX_OUTPUT_TOKENS must be at least 256")
        self.max_input_chars = (
            max_input_chars
            if max_input_chars is not None
            else int(os.getenv("OPENAI_MAX_INPUT_CHARS", "50000"))
        )
        self.max_evidence_items = (
            max_evidence_items
            if max_evidence_items is not None
            else int(os.getenv("OPENAI_MAX_EVIDENCE_ITEMS", "25"))
        )
        if self.max_input_chars < 1000:
            raise ValueError("OPENAI_MAX_INPUT_CHARS must be at least 1000")
        if self.max_evidence_items < 1:
            raise ValueError("OPENAI_MAX_EVIDENCE_ITEMS must be at least 1")

        if client is None:
            from openai import OpenAI

            client = OpenAI(
                timeout=self.timeout_seconds,
                max_retries=self.max_retries,
            )
        self.client = client

    def judge(self, *, case: Case, evidence: list[Evidence]) -> EngineDecision:
        if len(evidence) > self.max_evidence_items:
            raise JudgmentProviderError(
                code="OPENAI_INPUT_BUDGET_EXCEEDED",
                message="The case contains more evidence items than the configured AI-call budget allows.",
                http_status=413,
                retryable=False,
            )

        input_chars = len(case.original_input) + sum(len(item.content) for item in evidence)
        if input_chars > self.max_input_chars:
            raise JudgmentProviderError(
                code="OPENAI_INPUT_BUDGET_EXCEEDED",
                message="The case input is larger than the configured AI-call budget allows.",
                http_status=413,
                retryable=False,
            )

        input_payload = {
            "original_input": case.original_input,
            "evidence": _serialize_evidence(evidence),
        }

        try:
            response = self.client.responses.parse(
                model=self.model,
                instructions=SYSTEM_INSTRUCTION,
                input=json.dumps(input_payload, ensure_ascii=False),
                text_format=EngineDecision,
                max_output_tokens=self.max_output_tokens,
                reasoning={"effort": self.reasoning_effort},
                store=False,
            )
        except JudgmentProviderError:
            raise
        except Exception as exc:
            raise _translate_openai_exception(exc) from exc

        decision = getattr(response, "output_parsed", None)
        if decision is None:
            raise JudgmentProviderError(
                code="OPENAI_INVALID_RESPONSE",
                message="The AI provider returned no structured judgment.",
                http_status=502,
                retryable=True,
                request_id=getattr(response, "_request_id", None),
            )

        try:
            if not isinstance(decision, EngineDecision):
                decision = EngineDecision.model_validate(decision)
        except Exception as exc:
            raise JudgmentProviderError(
                code="OPENAI_INVALID_RESPONSE",
                message="The AI provider returned a judgment that failed schema validation.",
                http_status=502,
                retryable=True,
                request_id=getattr(response, "_request_id", None),
            ) from exc

        _validate_decision_evidence(decision, evidence)
        return decision


class UnavailableJudgmentProvider(JudgmentProvider):
    provider_name = "openai"
    model_name = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
    configured = False

    def judge(self, *, case: Case, evidence: list[Evidence]) -> EngineDecision:
        raise JudgmentProviderError(
            code="OPENAI_NOT_CONFIGURED",
            message="OPENAI_API_KEY is not configured. Automatic AI judgment is unavailable.",
            http_status=503,
            retryable=False,
        )


def get_judgment_provider() -> JudgmentProvider:
    if not os.getenv("OPENAI_API_KEY"):
        return UnavailableJudgmentProvider()
    return OpenAIJudgmentProvider()
