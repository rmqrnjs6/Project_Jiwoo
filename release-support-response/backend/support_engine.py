from __future__ import annotations

import os
from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import Case, ContextMode, DeliveryStyle, NudgeLevel


class AffectSignalType(str, Enum):
    DESPAIR_LANGUAGE = "DESPAIR_LANGUAGE"
    DISTRESS_LANGUAGE = "DISTRESS_LANGUAGE"
    SELF_BLAME_LANGUAGE = "SELF_BLAME_LANGUAGE"
    ANGER_LANGUAGE = "ANGER_LANGUAGE"
    ANXIETY_LANGUAGE = "ANXIETY_LANGUAGE"
    CONFUSION_LANGUAGE = "CONFUSION_LANGUAGE"
    NEUTRAL_OR_UNCLEAR = "NEUTRAL_OR_UNCLEAR"
    OTHER = "OTHER"


class AffectSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal: AffectSignalType
    intensity: float = Field(ge=0.0, le=1.0)
    textual_basis: str = Field(min_length=1)


class SupportDecision(BaseModel):
    """A text-observation decision, not a diagnosis of the author."""

    model_config = ConfigDict(extra="forbid")

    expression_summary: str = Field(min_length=1)
    affect_signals: list[AffectSignal] = Field(default_factory=list)
    context_mode: ContextMode
    context_rationale: str = Field(min_length=1)
    nudge_level: NudgeLevel
    delivery_style: DeliveryStyle
    recommendation_text: str | None = None
    rationale_summary: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_nudge_contract(self):
        expected_style = {
            NudgeLevel.NONE: DeliveryStyle.NONE,
            NudgeLevel.SOFT: DeliveryStyle.SUBTLE,
            NudgeLevel.EXPLICIT: DeliveryStyle.CLEAR,
            NudgeLevel.SAFETY: DeliveryStyle.DIRECT_SAFETY,
        }[self.nudge_level]

        if self.delivery_style != expected_style:
            raise ValueError(
                f"{self.nudge_level.value} requires delivery_style={expected_style.value}"
            )

        if self.nudge_level == NudgeLevel.NONE and self.recommendation_text:
            raise ValueError("NONE nudge must not include recommendation_text")

        if self.nudge_level != NudgeLevel.NONE and not self.recommendation_text:
            raise ValueError(f"{self.nudge_level.value} requires recommendation_text")

        return self


class SupportProvider(ABC):
    @abstractmethod
    def assess(self, *, case: Case) -> SupportDecision:
        raise NotImplementedError


SYSTEM_INSTRUCTION = """
You are the contextual support layer for a text-based AI system.

Analyze ONLY what is observable in the supplied text and explicit conversation
context. This is not a mental-health diagnosis and not a personality profiler.

Hard rules:
1. Describe expressed language, not the author's hidden mental state.
2. Never infer or label depression, psychopathy, sociopathy, personality
   disorders, neurodivergence, talent/giftedness, criminality, profession,
   deception, or whether the author is "really" feeling an emotion.
3. Do not claim to detect acting, lying, roleplay, or authenticity from style.
4. Context modes must be based on explicit textual context:
   - DECLARED_PERSONAL only when the text explicitly frames itself as the
     author's real personal experience.
   - ROLEPLAY_DECLARED only when roleplay/performance is explicit.
   - FICTION_DECLARED only when fiction/creative writing is explicit.
   - QUOTED_CONTENT only when the content is explicitly quoted/reported.
   - otherwise AMBIGUOUS_CONTEXT.
5. affect_signals describe textual signals only. The signal is not a diagnosis.
6. Use SOFT for a low-intensity, non-urgent suggestion that can be woven into
   normal conversation.
7. Use EXPLICIT when a clearer recommendation is warranted.
8. Use SAFETY only when the text itself contains a direct, concrete safety
   concern. SAFETY must be direct, never hidden or merely suggestive.
9. Use NONE when no support recommendation is warranted.
10. Do not manufacture concern from emotionally neutral or ambiguous text.
11. recommendation_text must match the selected delivery style and must not
    state or imply a diagnosis.
""".strip()


class OpenAISupportProvider(SupportProvider):
    def __init__(self, *, model: str | None = None):
        from openai import OpenAI

        self.client = OpenAI()
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.6-luna")

    def assess(self, *, case: Case) -> SupportDecision:
        response = self.client.responses.parse(
            model=self.model,
            instructions=SYSTEM_INSTRUCTION,
            input=case.original_input,
            text_format=SupportDecision,
        )
        decision = response.output_parsed
        if decision is None:
            raise RuntimeError("The model did not return a parsed support assessment")
        return decision


class UnavailableSupportProvider(SupportProvider):
    def assess(self, *, case: Case) -> SupportDecision:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured. Automatic contextual support assessment is unavailable."
        )


def get_support_provider() -> SupportProvider:
    if not os.getenv("OPENAI_API_KEY"):
        return UnavailableSupportProvider()
    return OpenAISupportProvider()
