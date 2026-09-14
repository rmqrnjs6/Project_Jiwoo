from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    ActionAttempt,
    ActionBlockReason,
    ActionStatus,
    ActionType,
    Case,
    CaseStatus,
    HistoryEventType,
    Judgment,
    PermissionPolicy,
    ResolutionState,
)
from .services import append_history


def get_or_create_permission(db: Session, *, case_id: int) -> PermissionPolicy:
    policy = db.scalar(select(PermissionPolicy).where(PermissionPolicy.case_id == case_id))
    if policy is None:
        policy = PermissionPolicy(case_id=case_id, can_execute=False, allowed_actions=[])
        db.add(policy)
        db.flush()
    return policy


def set_permission(
    db: Session,
    *,
    case_id: int,
    can_execute: bool,
    allowed_actions: list[ActionType],
    actor: str = "USER",
) -> PermissionPolicy:
    policy = get_or_create_permission(db, case_id=case_id)
    before = {
        "can_execute": policy.can_execute,
        "allowed_actions": list(policy.allowed_actions),
    }
    policy.can_execute = can_execute
    policy.allowed_actions = [item.value for item in allowed_actions]
    db.flush()
    append_history(
        db,
        case_id=case_id,
        event_type=HistoryEventType.PERMISSION_CHANGED,
        entity_type="PERMISSION_POLICY",
        entity_id=policy.id,
        actor=actor,
        payload={
            "before": before,
            "after": {
                "can_execute": policy.can_execute,
                "allowed_actions": list(policy.allowed_actions),
            },
        },
    )
    return policy


def _block(
    db: Session,
    *,
    action: ActionAttempt,
    reason: ActionBlockReason,
    detail: str,
) -> ActionAttempt:
    action.status = ActionStatus.BLOCKED
    action.blocked_reason = reason
    action.result = {"detail": detail}
    db.flush()
    append_history(
        db,
        case_id=action.case_id,
        event_type=HistoryEventType.ACTION_BLOCKED,
        entity_type="ACTION",
        entity_id=action.id,
        actor="SYSTEM",
        payload={
            "action_type": action.action_type.value,
            "judgment_id": action.judgment_id,
            "reason": reason.value,
            "detail": detail,
        },
    )
    return action


def _execute_internal_action(*, case: Case, action_type: ActionType, parameters: dict) -> dict:
    if action_type == ActionType.SET_CASE_STATUS:
        raw = parameters.get("status")
        try:
            new_status = CaseStatus(raw)
        except (ValueError, TypeError) as exc:
            raise ValueError("SET_CASE_STATUS requires status=OPEN or CLOSED") from exc
        before = case.status.value
        case.status = new_status
        return {"before": {"status": before}, "after": {"status": new_status.value}}

    if action_type == ActionType.SET_CASE_TITLE:
        title = parameters.get("title")
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 200:
            raise ValueError("SET_CASE_TITLE requires a non-empty title up to 200 characters")
        before = case.title
        case.title = title.strip()
        return {"before": {"title": before}, "after": {"title": case.title}}

    raise ValueError(f"Unsupported action type: {action_type.value}")


def execute_action(
    db: Session,
    *,
    case: Case,
    judgment: Judgment,
    action_type: ActionType,
    parameters: dict,
) -> ActionAttempt:
    action = ActionAttempt(
        case_id=case.id,
        judgment_id=judgment.id,
        action_type=action_type,
        parameters=parameters,
        status=ActionStatus.ATTEMPTED,
        result={},
        actor="AI",
    )
    db.add(action)
    db.flush()

    append_history(
        db,
        case_id=case.id,
        event_type=HistoryEventType.ACTION_ATTEMPTED,
        entity_type="ACTION",
        entity_id=action.id,
        actor="AI",
        payload={
            "action_type": action_type.value,
            "judgment_id": judgment.id,
            "parameters": parameters,
        },
    )

    latest = db.scalar(
        select(Judgment)
        .where(Judgment.case_id == case.id)
        .order_by(Judgment.revision_no.desc())
        .limit(1)
    )
    if latest is None or latest.id != judgment.id:
        return _block(
            db,
            action=action,
            reason=ActionBlockReason.STALE_JUDGMENT,
            detail="Only the latest judgment can authorize an action.",
        )

    if judgment.resolution_state != ResolutionState.RESOLVED:
        return _block(
            db,
            action=action,
            reason=ActionBlockReason.JUDGMENT_NOT_RESOLVED,
            detail="PENDING or UNRESOLVED judgments cannot execute actions.",
        )

    policy = get_or_create_permission(db, case_id=case.id)
    if not policy.can_execute:
        return _block(
            db,
            action=action,
            reason=ActionBlockReason.EXECUTION_DISABLED,
            detail="Execution permission is disabled for this case.",
        )

    if action_type.value not in policy.allowed_actions:
        return _block(
            db,
            action=action,
            reason=ActionBlockReason.SCOPE_DENIED,
            detail="The requested action is outside the allowed execution scope.",
        )

    try:
        result = _execute_internal_action(case=case, action_type=action_type, parameters=parameters)
    except ValueError as exc:
        return _block(
            db,
            action=action,
            reason=ActionBlockReason.INVALID_PARAMETERS,
            detail=str(exc),
        )
    except Exception as exc:
        action.status = ActionStatus.FAILED
        action.result = {"detail": str(exc)}
        db.flush()
        append_history(
            db,
            case_id=case.id,
            event_type=HistoryEventType.ACTION_FAILED,
            entity_type="ACTION",
            entity_id=action.id,
            actor="SYSTEM",
            payload={
                "action_type": action_type.value,
                "judgment_id": judgment.id,
                "detail": str(exc),
            },
        )
        return action

    action.status = ActionStatus.COMPLETED
    action.result = result
    db.flush()
    append_history(
        db,
        case_id=case.id,
        event_type=HistoryEventType.ACTION_COMPLETED,
        entity_type="ACTION",
        entity_id=action.id,
        actor="SYSTEM",
        payload={
            "action_type": action_type.value,
            "judgment_id": judgment.id,
            "result": result,
        },
    )
    return action
