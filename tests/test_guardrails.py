"""Tests for guardrails.py."""

from __future__ import annotations

import pytest

from agent_state import AssistantState, PendingAction, new_assistant_state
from guardrails import (
    can_execute_pending_write,
    user_message_for_tool_failure,
    validate_propose_tool,
)


def _state_awaiting(pa: PendingAction | None) -> AssistantState:
    s = new_assistant_state()
    s.awaiting_confirmation = True
    s.pending_action = pa
    return s


def test_can_execute_requires_confirmation_and_complete_payload() -> None:
    s = new_assistant_state()
    s.awaiting_confirmation = False
    ok, err = can_execute_pending_write(s)
    assert ok is False
    assert "Not awaiting" in err

    s = _state_awaiting(None)
    ok, err = can_execute_pending_write(s)
    assert ok is False
    assert "No pending" in err

    s = _state_awaiting(PendingAction(kind="register", kid_id="k", camp_id=None))
    ok, err = can_execute_pending_write(s)
    assert ok is False
    assert "incomplete" in err.lower()

    s = _state_awaiting(PendingAction(kind="register", kid_id="kid-1", camp_id="camp-1"))
    ok, err = can_execute_pending_write(s)
    assert ok is True
    assert err == ""

    s = _state_awaiting(PendingAction(kind="cancel_registration", registration_id="r-1"))
    ok, err = can_execute_pending_write(s)
    assert ok is True

    s = _state_awaiting(
        PendingAction(
            kind="update_registration_status",
            registration_id="r-1",
            new_status="confirmed",
        )
    )
    ok, err = can_execute_pending_write(s)
    assert ok is True


@pytest.mark.parametrize(
    ("name", "args", "expect_ok"),
    [
        ("propose_register", {}, False),
        ("propose_register", {"kid_id": "k"}, False),
        ("propose_register", {"kid_id": "k", "camp_id": "c"}, True),
        ("propose_cancel_registration", {}, False),
        ("propose_cancel_registration", {"registration_id": "r"}, True),
        ("propose_update_registration_status", {"registration_id": "r"}, False),
        (
            "propose_update_registration_status",
            {"registration_id": "r", "new_status": "confirmed"},
            True,
        ),
    ],
)
def test_validate_propose_tool(name: str, args: dict, expect_ok: bool) -> None:
    ok, err = validate_propose_tool(name, args)
    assert ok is expect_ok
    if not expect_ok:
        assert err


def test_user_message_for_tool_failure_adds_hint() -> None:
    base = {"success": False, "error_code": "AMBIGUOUS_KID", "message": "Pick a kid."}
    out = user_message_for_tool_failure(base)
    assert "Pick a kid." in out
    assert "listed" in out.lower() or "pick" in out.lower()

    nf = {"success": False, "error_code": "NOT_FOUND", "message": "Missing."}
    out_nf = user_message_for_tool_failure(nf)
    assert "Missing." in out_nf

    ok_row = {"success": True, "message": "fine"}
    assert user_message_for_tool_failure(ok_row) == ""
