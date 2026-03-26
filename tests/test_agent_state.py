"""Unit tests for assistant state helpers (task 5)."""

from __future__ import annotations

from agent_state import (
    PendingAction,
    clear_ambiguity,
    clear_confirmation,
    new_assistant_state,
    reset_transaction_slots,
)


def test_new_state_is_empty() -> None:
    s = new_assistant_state()
    assert s.intent is None
    assert s.selected_kid_id is None
    assert s.awaiting_confirmation is False
    assert s.pending_action is None
    assert s.candidate_kids == []
    assert s.last_tool_result is None


def test_clear_confirmation() -> None:
    s = new_assistant_state()
    s.awaiting_confirmation = True
    s.pending_action = PendingAction(kind="register", kid_id="kid-1", camp_id="camp-1")
    clear_confirmation(s)
    assert s.awaiting_confirmation is False
    assert s.pending_action is None


def test_clear_ambiguity() -> None:
    s = new_assistant_state()
    s.candidate_kids = [{"kid_id": "kid-1", "name": "A"}]
    s.candidate_camps = [{"camp_id": "camp-1", "name": "B"}]
    clear_ambiguity(s)
    assert s.candidate_kids == []
    assert s.candidate_camps == []


def test_reset_transaction_slots() -> None:
    s = new_assistant_state()
    s.selected_kid_id = "kid-1"
    s.selected_camp_id = "camp-1"
    s.selected_registration_id = "reg-1"
    s.candidate_kids = [{"kid_id": "kid-1", "name": "A"}]
    s.awaiting_confirmation = True
    s.pending_action = PendingAction(kind="register")
    reset_transaction_slots(s)
    assert s.selected_kid_id is None
    assert s.selected_camp_id is None
    assert s.selected_registration_id is None
    assert s.candidate_kids == []
    assert s.awaiting_confirmation is False
    assert s.pending_action is None
