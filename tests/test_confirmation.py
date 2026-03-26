"""Tests for deterministic confirmation parsing."""

from __future__ import annotations

from confirmation import is_confirmation, is_rejection


def test_confirmation_yes_ok() -> None:
    assert is_confirmation("yes") is True
    assert is_confirmation("OK") is True
    assert is_confirmation("  go ahead  ") is True


def test_rejection_no_cancel() -> None:
    assert is_rejection("no") is True
    assert is_rejection("cancel") is True


def test_confirmation_not_rejection() -> None:
    assert is_rejection("yes") is False
    assert is_confirmation("no") is False
