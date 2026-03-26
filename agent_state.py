"""Explicit assistant state (not only chat history)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Intent = Literal["register", "cancel", "update_status", "lookup"] | None

PendingKind = Literal["register", "cancel_registration", "update_registration_status"]


@dataclass
class PendingAction:
    kind: PendingKind
    kid_id: str | None = None
    camp_id: str | None = None
    registration_id: str | None = None
    new_status: str | None = None


@dataclass
class AssistantState:
    intent: Intent = None
    selected_kid_id: str | None = None
    selected_camp_id: str | None = None
    selected_registration_id: str | None = None
    candidate_kids: list[dict[str, str]] = field(default_factory=list)
    candidate_camps: list[dict[str, str]] = field(default_factory=list)
    awaiting_confirmation: bool = False
    pending_action: PendingAction | None = None
    last_tool_result: dict[str, Any] | None = None


def clear_confirmation(state: AssistantState) -> None:
    state.awaiting_confirmation = False
    state.pending_action = None


def clear_ambiguity(state: AssistantState) -> None:
    state.candidate_kids = []
    state.candidate_camps = []


def reset_transaction_slots(state: AssistantState) -> None:
    state.selected_kid_id = None
    state.selected_camp_id = None
    state.selected_registration_id = None
    clear_ambiguity(state)
    clear_confirmation(state)


def new_assistant_state() -> AssistantState:
    return AssistantState()
