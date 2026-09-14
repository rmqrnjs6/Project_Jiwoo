from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator

from .judgment_engine import JudgmentProviderError, _translate_openai_exception
from .models import Case, EvidenceSourceType


class DiscoveryCandidateDraft(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    summary: str = Field(min_length=10, max_length=1200)
    source_name: str = Field(min_length=2, max_length=200)
    source_url: HttpUrl
    source_type: EvidenceSourceType
    source_published_at: datetime | None = None
    relation_to_claim: str = Field(pattern=r"^(SUPPORT|CONTRADICT|CONTEXT|UNKNOWN)$")
    authority_score: float = Field(ge=0.0, le=1.0)
    originality_score: float = Field(ge=0.0, le=1.0)
    directness_score: float = Field(ge=0.0, le=1.0)
    recency_score: float = Field(ge=0.0, le=1.0)
    corroboration_score: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=5, max_length=1200)

    @field_validator("title", "summary", "source_name", "rationale", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class DiscoveryResult(BaseModel):
    candidates: list[DiscoveryCandidateDraft] = Field(min_length=5, max_length=10)


class EvidenceDiscoveryProvider(ABC):
    provider_name = "unknown"
    model_name: str | None = None
    configured = True

    @abstractmethod
    def discover(self, *, case: Case, limit: int) -> list[DiscoveryCandidateDraft]:
        raise NotImplementedError


DISCOVERY_INSTRUCTIONS = """
You find public evidence candidates for an evidence-review system.

The user's case input is a CLAIM TO CHECK, not evidence.
Search the public web and return a compact set of source candidates that a human can inspect.

Rules:
1. Return 5 to 10 candidates, aiming for the requested count.
2. Prefer original/primary/official sources when available, then strong institutional or reputable news sources.
3. Avoid duplicates, mirrors, syndicated copies, SEO pages, and sources that all trace back to the same origin when alternatives exist.
4. Each source_url must be the actual page used for that candidate, not a search result page.
5. summary must be a short PARAPHRASE of the source content relevant to the claim. Do not reproduce long quotations.
6. relation_to_claim is SUPPORT, CONTRADICT, CONTEXT, or UNKNOWN.
7. Scores are evidence-quality factors, not probabilities that the claim is true.
8. authority_score: authority of the source for this specific claim.
9. originality_score: closeness to the original/primary source.
10. directness_score: how directly the source addresses the claim.
11. recency_score: how suitable the publication date is for this claim; newer is not always automatically better.
12. corroboration_score: degree of meaningful support from independent sources in the returned set.
13. If a date is unavailable, source_published_at must be null.
14. Be conservative. A credible-looking domain alone is not enough for a near-perfect score.
15. Use Korean for title, summary, and rationale when the claim is Korean.
""".strip()


def candidate_score(candidate: DiscoveryCandidateDraft) -> float:
    """Transparent candidate ranking score.

    This is intentionally not called 'truth probability'. The top candidate is simply
    the currently strongest candidate under the visible scoring rule.
    """
    base = (
        candidate.authority_score * 0.30
        + candidate.originality_score * 0.22
        + candidate.directness_score * 0.22
        + candidate.recency_score * 0.08
        + candidate.corroboration_score * 0.18
    )
    return round(max(0.0, min(0.99, base)), 4)


def candidate_components(candidate: DiscoveryCandidateDraft) -> dict[str, float]:
    return {
        "authority": round(candidate.authority_score, 4),
        "originality": round(candidate.originality_score, 4),
        "directness": round(candidate.directness_score, 4),
        "recency": round(candidate.recency_score, 4),
        "corroboration": round(candidate.corroboration_score, 4),
    }


class OpenAIWebEvidenceDiscoveryProvider(EvidenceDiscoveryProvider):
    provider_name = "openai-web-search"

    def __init__(
        self,
        *,
        model: str | None = None,
        client: Any | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        max_output_tokens: int | None = None,
    ):
        self.model = model or os.getenv(
            "OPENAI_EVIDENCE_MODEL", os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
        )
        self.model_name = self.model
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30"))
        )
        self.max_retries = (
            max_retries if max_retries is not None else int(os.getenv("OPENAI_MAX_RETRIES", "1"))
        )
        self.max_output_tokens = (
            max_output_tokens
            if max_output_tokens is not None
            else int(os.getenv("OPENAI_EVIDENCE_MAX_OUTPUT_TOKENS", "3600"))
        )
        if self.max_output_tokens < 700:
            raise ValueError("OPENAI_EVIDENCE_MAX_OUTPUT_TOKENS must be at least 700")

        if client is None:
            from openai import OpenAI

            client = OpenAI(timeout=self.timeout_seconds, max_retries=self.max_retries)
        self.client = client

    def discover(self, *, case: Case, limit: int) -> list[DiscoveryCandidateDraft]:
        payload = {
            "claim": case.original_input,
            "case_title": case.title,
            "requested_candidate_count": limit,
        }
        try:
            response = self.client.responses.parse(
                model=self.model,
                instructions=DISCOVERY_INSTRUCTIONS,
                input=json.dumps(payload, ensure_ascii=False),
                tools=[{"type": "web_search", "search_context_size": "medium"}],
                text_format=DiscoveryResult,
                max_output_tokens=self.max_output_tokens,
                reasoning={"effort": "low"},
                store=False,
            )
        except JudgmentProviderError:
            raise
        except Exception as exc:
            raise _translate_openai_exception(exc) from exc

        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise JudgmentProviderError(
                code="OPENAI_INVALID_RESPONSE",
                message="The AI provider returned no structured evidence candidates.",
                http_status=502,
                retryable=True,
                request_id=getattr(response, "_request_id", None),
            )

        try:
            result = parsed if isinstance(parsed, DiscoveryResult) else DiscoveryResult.model_validate(parsed)
        except Exception as exc:
            raise JudgmentProviderError(
                code="OPENAI_INVALID_RESPONSE",
                message="The AI provider returned evidence candidates that failed schema validation.",
                http_status=502,
                retryable=True,
                request_id=getattr(response, "_request_id", None),
            ) from exc

        # Keep the provider bounded even if the model returns more than requested.
        return result.candidates[:limit]


class UnavailableEvidenceDiscoveryProvider(EvidenceDiscoveryProvider):
    provider_name = "openai-web-search"
    model_name = os.getenv("OPENAI_EVIDENCE_MODEL", os.getenv("OPENAI_MODEL", "gpt-5.6-luna"))
    configured = False

    def discover(self, *, case: Case, limit: int) -> list[DiscoveryCandidateDraft]:
        raise JudgmentProviderError(
            code="OPENAI_NOT_CONFIGURED",
            message="OPENAI_API_KEY is not configured. Web evidence discovery is unavailable.",
            http_status=503,
            retryable=False,
        )


class DemoEvidenceDiscoveryProvider(EvidenceDiscoveryProvider):
    """Deterministic UX-only candidates. They are never presented as real evidence."""

    provider_name = "demo-local"
    model_name = None

    def discover(self, *, case: Case, limit: int) -> list[DiscoveryCandidateDraft]:
        now = datetime.now(timezone.utc)
        rows = [
            (
                "[데모] 공식 발표 자료",
                "실제 웹 검색 없이 추천 근거 화면의 동작을 확인하기 위한 데모 요약입니다. 공식 1차 자료가 있을 때 어떤 식으로 최상위 후보로 표시되는지를 보여줍니다.",
                "Demo Government",
                "https://example.com/demo/official",
                EvidenceSourceType.OFFICIAL,
                "SUPPORT",
                (0.98, 0.98, 0.96, 0.90, 0.90),
            ),
            (
                "[데모] 공공기관 보도자료",
                "공공기관 성격의 1차·준1차 자료가 추천 목록에서 어떻게 비교되는지 확인하기 위한 데모 후보입니다.",
                "Demo Institution",
                "https://example.com/demo/institution",
                EvidenceSourceType.INSTITUTIONAL,
                "SUPPORT",
                (0.90, 0.88, 0.88, 0.86, 0.84),
            ),
            (
                "[데모] 주요 언론 보도",
                "독립적인 언론 보도가 공식 자료를 해설하는 상황을 표현한 데모 후보입니다. 실제 기사 내용을 의미하지 않습니다.",
                "Demo News A",
                "https://example.com/demo/news-a",
                EvidenceSourceType.NEWS,
                "CONTEXT",
                (0.82, 0.58, 0.80, 0.82, 0.80),
            ),
            (
                "[데모] 산업 분석 자료",
                "전문 분석 자료가 직접성은 다소 낮지만 맥락을 보강하는 경우를 표현한 데모 후보입니다.",
                "Demo Research",
                "https://example.com/demo/research",
                EvidenceSourceType.INSTITUTIONAL,
                "CONTEXT",
                (0.84, 0.66, 0.68, 0.74, 0.72),
            ),
            (
                "[데모] 2차 웹 요약",
                "원출처에서 멀어진 2차 웹 문서가 상대적으로 낮은 신뢰도로 표시되는지 확인하기 위한 데모 후보입니다.",
                "Demo Web",
                "https://example.com/demo/web",
                EvidenceSourceType.WEB,
                "UNKNOWN",
                (0.56, 0.40, 0.56, 0.70, 0.56),
            ),
            (
                "[데모] 출처 불명 게시물",
                "출처와 원본성이 불명확한 자료를 낮은 신뢰도로 표현하는 UX 데모입니다. 실제 근거로 사용하면 안 됩니다.",
                "Demo Community",
                "https://example.com/demo/community",
                EvidenceSourceType.UNKNOWN,
                "UNKNOWN",
                (0.30, 0.24, 0.42, 0.64, 0.36),
            ),
            (
                "[데모] 반대 방향 보도",
                "반대 방향의 자료도 별도 후보로 유지해 사용자가 함께 비교할 수 있음을 보여주는 데모 후보입니다.",
                "Demo News B",
                "https://example.com/demo/news-b",
                EvidenceSourceType.NEWS,
                "CONTRADICT",
                (0.78, 0.60, 0.76, 0.76, 0.42),
            ),
            (
                "[데모] 오래된 참고 자료",
                "출처 자체는 나쁘지 않지만 시점이 오래되어 최신 판단의 대표 근거로는 불리한 상황을 보여주는 데모 후보입니다.",
                "Demo Archive",
                "https://example.com/demo/archive",
                EvidenceSourceType.INSTITUTIONAL,
                "CONTEXT",
                (0.80, 0.72, 0.60, 0.35, 0.62),
            ),
        ]
        result: list[DiscoveryCandidateDraft] = []
        for idx, row in enumerate(rows[:limit]):
            title, summary, source_name, url, source_type, relation, scores = row
            authority, originality, directness, recency, corroboration = scores
            result.append(
                DiscoveryCandidateDraft(
                    title=title,
                    summary=summary,
                    source_name=source_name,
                    source_url=url,
                    source_type=source_type,
                    source_published_at=now - timedelta(days=30 * (idx + 1)),
                    relation_to_claim=relation,
                    authority_score=authority,
                    originality_score=originality,
                    directness_score=directness,
                    recency_score=recency,
                    corroboration_score=corroboration,
                    rationale=(
                        "UX 테스트용 데모 데이터입니다. 점수 구성, 대표 근거 강조, 상세 펼침, "
                        "채택 흐름을 확인하기 위한 값이며 실제 사실 검증 결과가 아닙니다."
                    ),
                )
            )
        return result


def get_evidence_discovery_provider() -> EvidenceDiscoveryProvider:
    if not os.getenv("OPENAI_API_KEY"):
        return UnavailableEvidenceDiscoveryProvider()
    return OpenAIWebEvidenceDiscoveryProvider()


def get_demo_evidence_discovery_provider() -> EvidenceDiscoveryProvider:
    return DemoEvidenceDiscoveryProvider()
