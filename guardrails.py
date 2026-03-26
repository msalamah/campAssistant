"""Deterministic guardrails for pending writes and propose-tool validation."""

from __future__ import annotations

from typing import Any

from agent_state import AssistantState


def can_execute_pending_write(state: AssistantState) -> tuple[bool, str]:
    if not state.awaiting_confirmation:
        return False, "Not awaiting confirmation."
    pa = state.pending_action
    if not pa:
        return False, "No pending action to execute."
    if pa.kind == "register":
        if not pa.kid_id or not pa.camp_id:
            return False, "Pending registration is incomplete (missing kid or camp id)."
    elif pa.kind == "cancel_registration":
        if not pa.registration_id:
            return False, "Pending cancellation is incomplete (missing registration id)."
    elif pa.kind == "update_registration_status":
        if not pa.registration_id or not pa.new_status:
            return False, "Pending status update is incomplete."
    else:
        return False, "Unknown pending action kind."
    return True, ""


def validate_propose_tool(name: str, args: dict[str, Any]) -> tuple[bool, str]:
    if name == "propose_register":
        if not args.get("kid_id") or not args.get("camp_id"):
            return False, "propose_register requires kid_id and camp_id."
    elif name == "propose_cancel_registration":
        if not args.get("registration_id"):
            return False, "propose_cancel_registration requires registration_id."
    elif name == "propose_update_registration_status":
        if not args.get("registration_id") or not args.get("new_status"):
            return False, "propose_update_registration_status requires registration_id and new_status."
    return True, ""


def user_message_for_tool_failure(result: dict[str, Any]) -> str:
    if result.get("success"):
        return ""
    code = result.get("error_code") or "ERROR"
    msg = result.get("message") or "Something went wrong."
    hint = _hint_for_error_code(code)
    if hint:
        return f"{msg} {hint}"
    return msg


def _hint_for_error_code(code: str) -> str:
    if code in ("AMBIGUOUS_KID", "AMBIGUOUS_CAMP"):
        return "Ask which child or camp they mean using full names (or other details they give you). Do not pick for them."
    if code == "NOT_FOUND":
        return "Try a different spelling or name, or ask to see camps or their children on file."
    if code in ("CAMP_FULL", "AGE_RESTRICTION", "SCHEDULE_CONFLICT", "DUPLICATE_REGISTRATION"):
        return "Tell me if you want to try a different camp or child."
    return ""
