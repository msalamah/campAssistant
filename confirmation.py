"""Deterministic confirmation detection (no LLM)."""

from __future__ import annotations

_CONFIRM = frozenset(
    {
        "yes",
        "y",
        "yeah",
        "confirm",
        "confirmed",
        "go ahead",
        "ok",
        "okay",
        "sure",
        "please do",
        "do it",
    }
)
_REJECT = frozenset({"no", "nope", "wait", "cancel", "stop", "don't", "dont", "abort", "never mind"})


def normalize_reply(text: str) -> str:
    return " ".join(text.strip().lower().split())


def is_confirmation(text: str) -> bool:
    n = normalize_reply(text)
    if not n:
        return False
    if n in _CONFIRM:
        return True
    first = n.split()[0]
    return first in _CONFIRM


def is_rejection(text: str) -> bool:
    n = normalize_reply(text)
    if not n:
        return False
    if n in _REJECT:
        return True
    first = n.split()[0]
    return first in _REJECT
