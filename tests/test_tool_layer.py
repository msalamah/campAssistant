"""Tool-layer tests: names mirror `error_code` values in ARCHITECTURE.md."""

from __future__ import annotations

from pathlib import Path

import pytest

from db_store import load_db, save_db
from tool_schemas import (
    cancel_registration,
    get_camps,
    get_kids,
    get_registrations,
    get_waitlist,
    register_kid,
    update_registration_status,
    validate_register_proposal,
)


def test_not_found_unknown_kid_id(db_path: Path) -> None:
    r = get_kids(kid_id="kid-999", db_path=db_path)
    assert r["success"] is False
    assert r["error_code"] == "NOT_FOUND"


def test_not_found_unknown_camp_id(db_path: Path) -> None:
    r = get_camps(camp_id="camp-999", db_path=db_path)
    assert r["success"] is False
    assert r["error_code"] == "NOT_FOUND"


def test_not_found_unknown_registration_id(db_path: Path) -> None:
    r = get_registrations(registration_id="reg-999", db_path=db_path)
    assert r["success"] is False
    assert r["error_code"] == "NOT_FOUND"


def test_not_found_name_search_zero_kids(db_path: Path) -> None:
    r = get_kids(name_query="zzznope", db_path=db_path)
    assert r["success"] is False
    assert r["error_code"] == "NOT_FOUND"


def test_not_found_name_search_zero_camps(db_path: Path) -> None:
    r = get_camps(name_query="zzznope", db_path=db_path)
    assert r["success"] is False
    assert r["error_code"] == "NOT_FOUND"


def test_ambiguous_kid_emma_two_matches(db_path: Path) -> None:
    r = get_kids(name_query="Emma", db_path=db_path)
    assert r["success"] is False
    assert r["error_code"] == "AMBIGUOUS_KID"
    assert len(r["details"]["candidates"]) >= 2


def test_ambiguous_camp_substring_matches_multiple_camps(db_path: Path) -> None:
    r = get_camps(name_query="ar", db_path=db_path)
    assert r["success"] is False
    assert r["error_code"] == "AMBIGUOUS_CAMP"
    assert len(r["details"]["candidates"]) >= 2


def test_camp_cancelled_register_drama_club(db_path: Path) -> None:
    r = register_kid("kid-7", "camp-5", db_path=db_path)
    assert r["success"] is False
    assert r["error_code"] == "CAMP_CANCELLED"


def test_register_kid_waitlist_when_camp_full_art_adventure(db_path: Path) -> None:
    snap = get_camps(camp_id="camp-2", db_path=db_path)
    assert snap["success"] is True
    enrolled_before = snap["details"]["camps"][0]["enrolled"]
    assert enrolled_before >= snap["details"]["camps"][0]["capacity"]
    r = register_kid("kid-5", "camp-2", db_path=db_path)
    assert r["success"] is True
    assert r["details"]["status"] == "waitlisted"
    after = get_camps(camp_id="camp-2", db_path=db_path)
    assert after["details"]["camps"][0]["enrolled"] == enrolled_before


def test_age_restriction_ethan_swimming_basics(db_path: Path) -> None:
    r = register_kid("kid-6", "camp-4", db_path=db_path)
    assert r["success"] is False
    assert r["error_code"] == "AGE_RESTRICTION"


def test_duplicate_registration_same_kid_and_camp(db_path: Path) -> None:
    r = register_kid("kid-1", "camp-1", db_path=db_path)
    assert r["success"] is False
    assert r["error_code"] == "DUPLICATE_REGISTRATION"


def test_validate_register_proposal_matches_register_kid_rules(db_path: Path) -> None:
    dup = validate_register_proposal("kid-2", "camp-4", db_path=db_path)
    assert dup["success"] is False
    assert dup["error_code"] == "DUPLICATE_REGISTRATION"
    ok = validate_register_proposal("kid-10", "camp-1", db_path=db_path)
    assert ok["success"] is True
    waitlist_ok = validate_register_proposal("kid-5", "camp-2", db_path=db_path)
    assert waitlist_ok["success"] is True


def test_schedule_conflict_emma_soccer_and_science_explorers(db_path: Path) -> None:
    r = register_kid("kid-1", "camp-6", db_path=db_path)
    assert r["success"] is False
    assert r["error_code"] == "SCHEDULE_CONFLICT"


def test_update_registration_invalid_target_status(db_path: Path) -> None:
    r = update_registration_status("reg-4", "bogus", db_path=db_path)
    assert r["success"] is False
    assert r["error_code"] == "INVALID_STATUS"


def test_update_registration_disallowed_transition_from_cancelled(db_path: Path) -> None:
    cancel_registration("reg-1", db_path=db_path)
    r = update_registration_status("reg-1", "confirmed", db_path=db_path)
    assert r["success"] is False
    assert r["error_code"] == "INVALID_TRANSITION"


def test_malformed_input_validation_error(db_path: Path) -> None:
    r = register_kid("", "camp-1", db_path=db_path)
    assert r["success"] is False
    assert r["error_code"] == "VALIDATION_ERROR"


def test_register_kid_success_happy_path(db_path: Path) -> None:
    r = register_kid("kid-8", "camp-3", db_path=db_path)
    assert r["success"] is True
    assert r["details"]["status"] == "pending"
    assert "registration_id" in r["details"]


def test_cancel_registration_success(db_path: Path) -> None:
    r = cancel_registration("reg-4", db_path=db_path)
    assert r["success"] is True
    d = r["details"]
    assert d["status"] == "cancelled"
    assert d["released_spot"] is True
    assert d["camp_id"] == "camp-3"


def test_get_waitlist_fifo_and_single_seed_entry(db_path: Path) -> None:
    r = get_waitlist("camp-6", db_path=db_path)
    assert r["success"] is True
    assert r["details"]["count"] == 1
    assert r["details"]["waitlist"][0]["registration_id"] == "reg-6"
    assert r["details"]["waitlist"][0]["queue_position"] == 1

    db = load_db(db_path)
    db["registrations"].extend(
        [
            {
                "registration_id": "reg-w2",
                "kid_id": "kid-2",
                "camp_id": "camp-6",
                "status": "waitlisted",
                "registered_at": "2026-06-01T10:00:00",
            },
            {
                "registration_id": "reg-w1",
                "kid_id": "kid-3",
                "camp_id": "camp-6",
                "status": "waitlisted",
                "registered_at": "2026-06-01T09:00:00",
            },
        ]
    )
    save_db(db, db_path)
    r2 = get_waitlist("camp-6", db_path=db_path)
    wl = r2["details"]["waitlist"]
    assert [x["registration_id"] for x in wl] == ["reg-w1", "reg-w2", "reg-6"]


def test_get_waitlist_unknown_camp(db_path: Path) -> None:
    r = get_waitlist("camp-999", db_path=db_path)
    assert r["success"] is False
    assert r["error_code"] == "NOT_FOUND"


def test_update_registration_status_pending_to_confirmed(db_path: Path) -> None:
    created = register_kid("kid-8", "camp-3", db_path=db_path)
    assert created["success"] is True
    rid = created["details"]["registration_id"]
    r = update_registration_status(rid, "confirmed", db_path=db_path)
    assert r["success"] is True
    assert r["details"]["status"] == "confirmed"


def test_find_kid_exact_full_name_single_match(db_path: Path) -> None:
    r = get_kids(name_query="Emma Thompson", db_path=db_path)
    assert r["success"] is True
    assert len(r["details"]["kids"]) == 1
    assert r["details"]["kids"][0]["kid_id"] == "kid-1"


def test_find_camp_by_substring_single_match(db_path: Path) -> None:
    r = get_camps(name_query="Soccer", db_path=db_path)
    assert r["success"] is True
    assert len(r["details"]["camps"]) == 1
    assert r["details"]["camps"][0]["camp_id"] == "camp-1"


def test_waitlisted_to_confirmed_when_camp_full_returns_camp_full(db_path: Path) -> None:
    db = load_db(db_path)
    for camp in db["camps"]:
        if camp["camp_id"] == "camp-6":
            camp["enrolled"] = camp["capacity"]
            break
    save_db(db, db_path)
    r = update_registration_status("reg-6", "confirmed", db_path=db_path)
    assert r["success"] is False
    assert r["error_code"] == "CAMP_FULL"


def test_cancel_registration_twice_second_call_invalid_transition(db_path: Path) -> None:
    first = cancel_registration("reg-4", db_path=db_path)
    assert first["success"] is True
    second = cancel_registration("reg-4", db_path=db_path)
    assert second["success"] is False
    assert second["error_code"] == "INVALID_TRANSITION"


def test_cancel_waitlisted_registration_leaves_enrolled_unchanged(db_path: Path) -> None:
    snapshot = get_camps(camp_id="camp-6", db_path=db_path)
    assert snapshot["success"] is True
    enrolled_before = snapshot["details"]["camps"][0]["enrolled"]
    out = cancel_registration("reg-6", db_path=db_path)
    assert out["success"] is True
    after = get_camps(camp_id="camp-6", db_path=db_path)
    assert after["details"]["camps"][0]["enrolled"] == enrolled_before
