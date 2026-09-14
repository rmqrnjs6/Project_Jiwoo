from __future__ import annotations

from dataclasses import dataclass

from .models import DeliveryStyle, Judgment, NudgeLevel, SupportAssessment


@dataclass(frozen=True)
class ComposedResponse:
    text: str
    judgment_text: str
    nudge_text: str | None
    change_notice: str | None
    delivery_style: DeliveryStyle


def _change_notice(judgment: Judgment) -> str | None:
    previous = judgment.previous_judgment
    if previous is None:
        return None

    state_changed = any(
        (
            previous.conclusion != judgment.conclusion,
            previous.ai_position != judgment.ai_position,
            abs(previous.confidence - judgment.confidence) > 1e-9,
            previous.resolution_state != judgment.resolution_state,
            previous.unresolved_reason != judgment.unresolved_reason,
            previous.waiting_for != judgment.waiting_for,
        )
    )
    if state_changed:
        return "새로운 근거를 반영해 이전 판단을 다시 검토했고, 현재 판단이 갱신되었습니다."
    return "이전 판단을 다시 검토했지만, 현재 판단을 유지했습니다."


def compose_response(
    *,
    judgment: Judgment,
    support: SupportAssessment | None,
) -> ComposedResponse:
    judgment_text = judgment.position_text.strip()
    change_notice = _change_notice(judgment)

    if support is None or support.nudge_level == NudgeLevel.NONE:
        parts = [part for part in (change_notice, judgment_text) if part]
        return ComposedResponse(
            text="\n\n".join(parts),
            judgment_text=judgment_text,
            nudge_text=None,
            change_notice=change_notice,
            delivery_style=DeliveryStyle.NONE,
        )

    nudge_text = (support.recommendation_text or "").strip()

    if support.nudge_level == NudgeLevel.SOFT:
        # SOFT is intentionally woven into the normal answer.
        body = " ".join(part for part in (judgment_text, nudge_text) if part)
        parts = [part for part in (change_notice, body) if part]
    elif support.nudge_level == NudgeLevel.EXPLICIT:
        # EXPLICIT remains a clearly separate paragraph.
        parts = [part for part in (change_notice, judgment_text, nudge_text) if part]
    else:
        # SAFETY must never be hidden inside ordinary prose.
        parts = [part for part in (nudge_text, change_notice, judgment_text) if part]

    return ComposedResponse(
        text="\n\n".join(parts),
        judgment_text=judgment_text,
        nudge_text=nudge_text or None,
        change_notice=change_notice,
        delivery_style=support.delivery_style,
    )
