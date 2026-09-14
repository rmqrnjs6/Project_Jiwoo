from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .models import HistoryEvent, HistoryEventType


@dataclass
class TimelineItem:
    event_id: int
    event_type: HistoryEventType
    category: str
    title: str
    summary: str
    entity_type: str
    entity_id: int | None
    occurred_at: datetime
    event_count: int = 1


def _score(value) -> str:
    return "확인 전" if value is None else f"{round(float(value) * 100)}%"


def _to_item(event: HistoryEvent) -> TimelineItem | None:
    p = event.payload or {}
    et = event.event_type

    # These are useful in the raw audit log, but too noisy for a human timeline.
    if et in {HistoryEventType.REEVALUATION_STARTED, HistoryEventType.REEVALUATION_COMPLETED}:
        return None

    if et == HistoryEventType.INPUT_CREATED:
        return TimelineItem(event.id, et, "case", "처음 확인을 시작했어요", "확인할 주장을 기록했습니다. 여기서부터 변화 과정을 함께 남깁니다.", event.entity_type, event.entity_id, event.created_at)
    if et == HistoryEventType.EVIDENCE_CANDIDATES_DISCOVERED:
        count = p.get("count", 0)
        origin = p.get("origin", "UNKNOWN")
        label = "실제 웹 검색" if origin == "WEB_SEARCH" else "UI 데모"
        return TimelineItem(event.id, et, "evidence", "함께 볼 근거를 찾았어요", f"{label}으로 확인할 만한 근거 {count}개를 준비했습니다.", event.entity_type, event.entity_id, event.created_at)
    if et == HistoryEventType.REPRESENTATIVE_EVIDENCE_SELECTED:
        score = round(float(p.get("score", 0)) * 100)
        return TimelineItem(event.id, et, "evidence", "지금 가장 믿을 만한 근거를 골랐어요", f"현재 후보 가운데 가장 신뢰도가 높은 근거를 먼저 보여드립니다. 신뢰도 {score}%.", event.entity_type, event.entity_id, event.created_at)
    if et == HistoryEventType.EVIDENCE_CANDIDATE_ADOPTED:
        return TimelineItem(event.id, et, "evidence", "판단에 사용할 근거를 골랐어요", f"{p.get('source_name', '출처 미상')} 자료를 현재 판단에 사용하기로 했습니다.", event.entity_type, event.entity_id, event.created_at)
    if et == HistoryEventType.EVIDENCE_ADDED:
        source = p.get("claimed_source_type", "UNKNOWN")
        status = p.get("source_verification_status", "UNVERIFIED")
        return TimelineItem(event.id, et, "evidence", "직접 준비한 근거를 추가했어요", f"출처 유형 {source}, 현재 출처 상태 {status}로 기록했습니다.", event.entity_type, event.entity_id, event.created_at)
    if et == HistoryEventType.DUPLICATE_EVIDENCE_DETECTED:
        return TimelineItem(event.id, et, "evidence", "같은 근거는 한 번만 반영했어요", "이미 같은 내용이 있어 중복으로 세지 않았습니다.", event.entity_type, event.entity_id, event.created_at)
    if et == HistoryEventType.RELIABILITY_ASSESSED:
        return TimelineItem(event.id, et, "reliability", "근거의 신뢰도를 살펴봤어요", f"현재 기준의 신뢰도는 {_score(p.get('final_score'))}입니다.", event.entity_type, event.entity_id, event.created_at)
    if et == HistoryEventType.RELIABILITY_REVISED:
        return TimelineItem(event.id, et, "reliability", "근거 평가가 달라졌어요", f"다시 확인한 결과 신뢰도가 {_score(p.get('before_score'))}에서 {_score(p.get('final_score'))}로 바뀌었습니다.", event.entity_type, event.entity_id, event.created_at)
    if et == HistoryEventType.RELIABILITY_REAFFIRMED:
        return TimelineItem(event.id, et, "reliability", "다시 봐도 평가는 같았어요", f"근거를 다시 확인했지만 신뢰도는 {_score(p.get('final_score'))}로 유지됐습니다.", event.entity_type, event.entity_id, event.created_at)
    if et == HistoryEventType.SOURCE_VERIFICATION_ASSESSED:
        return TimelineItem(event.id, et, "source", "출처를 확인했어요", f"현재 출처 확인 상태는 {p.get('final_status', 'UNVERIFIED')}입니다.", event.entity_type, event.entity_id, event.created_at)
    if et == HistoryEventType.SOURCE_VERIFICATION_REVISED:
        return TimelineItem(event.id, et, "source", "출처 상태가 달라졌어요", f"다시 확인한 결과 {p.get('before_status', 'UNKNOWN')}에서 {p.get('final_status', 'UNKNOWN')}로 바뀌었습니다.", event.entity_type, event.entity_id, event.created_at)
    if et == HistoryEventType.SOURCE_VERIFICATION_REAFFIRMED:
        return TimelineItem(event.id, et, "source", "출처 상태는 그대로예요", f"출처를 다시 확인했지만 {p.get('final_status', 'UNKNOWN')} 상태로 유지됐습니다.", event.entity_type, event.entity_id, event.created_at)
    if et == HistoryEventType.JUDGMENT_CREATED:
        return TimelineItem(event.id, et, "judgment", "첫 판단을 정리했어요", f"현재 결론은 {p.get('conclusion', 'UNKNOWN')}이며 신뢰 수준은 {_score(p.get('confidence'))}입니다.", event.entity_type, event.entity_id, event.created_at)
    if et == HistoryEventType.JUDGMENT_REVISED:
        trigger = p.get("trigger", "UNKNOWN")
        return TimelineItem(event.id, et, "judgment", "새 근거를 보고 판단이 바뀌었어요", f"{trigger} 이후 다시 확인한 결과 결론을 {p.get('conclusion', 'UNKNOWN')}로 수정했습니다.", event.entity_type, event.entity_id, event.created_at)
    if et == HistoryEventType.JUDGMENT_REAFFIRMED:
        trigger = p.get("trigger", "UNKNOWN")
        return TimelineItem(event.id, et, "judgment", "다시 확인했지만 판단은 같아요", f"{trigger} 이후 다시 살펴봤지만 현재 결론을 유지했습니다.", event.entity_type, event.entity_id, event.created_at)
    if et == HistoryEventType.JUDGMENT_FAILED:
        return TimelineItem(event.id, et, "judgment", "이번 판단은 마치지 못했어요", f"AI 요청 과정에서 문제가 생겨 판단을 완료하지 못했습니다. ({p.get('error_code', 'UNKNOWN_ERROR')})", event.entity_type, event.entity_id, event.created_at)
    if et == HistoryEventType.AI_CALL_SKIPPED:
        return TimelineItem(event.id, et, "cost", "달라진 게 없어 이전 판단을 이어갔어요", "판단에 영향을 줄 변화가 없어 기존 결과를 재사용했고, 새 유료 AI 호출은 하지 않았습니다.", event.entity_type, event.entity_id, event.created_at)
    if et == HistoryEventType.PERMISSION_CHANGED:
        return TimelineItem(event.id, et, "permission", "행동 권한이 바뀌었어요", "이 판단에서 허용할 행동 범위를 새로 정했습니다.", event.entity_type, event.entity_id, event.created_at)
    if et == HistoryEventType.ACTION_COMPLETED:
        return TimelineItem(event.id, et, "action", "허용된 행동을 마쳤어요", f"{p.get('action_type', '행동')} 실행을 완료했습니다.", event.entity_type, event.entity_id, event.created_at)
    if et == HistoryEventType.ACTION_BLOCKED:
        return TimelineItem(event.id, et, "action", "행동은 실행하지 않았어요", f"현재 조건에서는 실행하면 안 된다고 판단해 멈췄습니다. 사유: {p.get('blocked_reason', 'UNKNOWN')}.", event.entity_type, event.entity_id, event.created_at)
    if et == HistoryEventType.ACTION_FAILED:
        return TimelineItem(event.id, et, "action", "행동을 끝내지 못했어요", "허용된 행동을 시도했지만 완료되지 않았습니다.", event.entity_type, event.entity_id, event.created_at)
    if et == HistoryEventType.CONTEXT_ASSESSED:
        return TimelineItem(event.id, et, "support", "맥락을 한 번 더 살펴봤어요", "답변에 추가적인 배려가 필요한지 현재 맥락을 확인했습니다.", event.entity_type, event.entity_id, event.created_at)
    if et == HistoryEventType.NUDGE_GENERATED:
        return TimelineItem(event.id, et, "support", "도움이 될 만한 안내를 준비했어요", f"현재 상황에 맞춰 {p.get('nudge_level', 'support')} 수준의 안내를 준비했습니다.", event.entity_type, event.entity_id, event.created_at)

    # Keep uncommon audit events visible rather than silently losing them.
    return TimelineItem(event.id, et, "system", et.value.replace("_", " ").title(), "시스템에서 중요한 변화 하나를 기록했습니다.", event.entity_type, event.entity_id, event.created_at)


def build_user_timeline(events: list[HistoryEvent]) -> list[TimelineItem]:
    items: list[TimelineItem] = []
    for event in events:
        item = _to_item(event)
        if item is None:
            continue

        if items:
            previous = items[-1]
            if (
                previous.event_type == item.event_type
                and previous.entity_type == item.entity_type
                and previous.entity_id == item.entity_id
                and previous.summary == item.summary
            ):
                previous.event_id = item.event_id
                previous.occurred_at = item.occurred_at
                previous.event_count += 1
                continue
        items.append(item)
    return items
