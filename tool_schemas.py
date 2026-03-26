"""Tool functions for the camp registration assistant (deterministic layer)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from db_store import load_db, save_db
from tool_result import fail as _fail
from tool_result import ok as _ok
from tool_helpers import (
    KNOWN_REGISTRATION_STATUSES,
    active_registration_for_kid_camp,
    allowed_status_transition,
    camp_by_id,
    has_schedule_conflict,
    kid_by_id,
    next_registration_id,
    registration_by_id,
    registered_at_now,
    resolve_entities_by_name,
)


def _candidate_rows(entities: list[dict[str, Any]], id_key: str, name_key: str) -> list[dict[str, str]]:
    return [{id_key: e[id_key], name_key: e[name_key]} for e in entities]


def get_camps(
    camp_id: str | None = None,
    name_query: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    db = load_db(db_path)
    camps = db["camps"]
    if camp_id and name_query:
        return _fail("VALIDATION_ERROR", "Pass only one of camp_id or name_query.")
    if camp_id:
        camp = camp_by_id(db, camp_id)
        if not camp:
            return _fail("NOT_FOUND", f"No camp with id {camp_id!r}.")
        return _ok({"camps": [camp]})
    if name_query:
        err, matches = resolve_entities_by_name(camps, "name", name_query, "AMBIGUOUS_CAMP")
        if err == "NOT_FOUND":
            return _fail("NOT_FOUND", f"No camp matches {name_query!r}.")
        if err == "VALIDATION_ERROR":
            return _fail("VALIDATION_ERROR", "name_query must be non-empty.")
        if err == "AMBIGUOUS_CAMP":
            return _fail(
                "AMBIGUOUS_CAMP",
                "Multiple camps match that name. Pick one.",
                {"candidates": _candidate_rows(matches, "camp_id", "name")},
            )
        return _ok({"camps": matches})
    return _ok({"camps": camps})


def get_kids(
    kid_id: str | None = None,
    name_query: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    db = load_db(db_path)
    kids = db["kids"]
    if kid_id and name_query:
        return _fail("VALIDATION_ERROR", "Pass only one of kid_id or name_query.")
    if kid_id:
        kid = kid_by_id(db, kid_id)
        if not kid:
            return _fail("NOT_FOUND", f"No kid with id {kid_id!r}.")
        return _ok({"kids": [kid]})
    if name_query:
        err, matches = resolve_entities_by_name(kids, "name", name_query, "AMBIGUOUS_KID")
        if err == "NOT_FOUND":
            return _fail("NOT_FOUND", f"No kid matches {name_query!r}.")
        if err == "VALIDATION_ERROR":
            return _fail("VALIDATION_ERROR", "name_query must be non-empty.")
        if err == "AMBIGUOUS_KID":
            return _fail(
                "AMBIGUOUS_KID",
                "Multiple kids match that name. Pick one.",
                {"candidates": _candidate_rows(matches, "kid_id", "name")},
            )
        return _ok({"kids": matches})
    return _ok({"kids": kids})


def _register_eligibility_failure(
    db: dict[str, Any],
    kid_id: str,
    camp_id: str,
) -> dict[str, Any] | None:
    kid = kid_by_id(db, kid_id)
    if not kid:
        return _fail("NOT_FOUND", f"No kid with id {kid_id!r}.")
    camp = camp_by_id(db, camp_id)
    if not camp:
        return _fail("NOT_FOUND", f"No camp with id {camp_id!r}.")
    if camp["status"] != "open":
        return _fail("CAMP_CANCELLED", f"{camp['name']} is not open for registration.")
    age = kid["age"]
    if age < camp["min_age"] or age > camp["max_age"]:
        return _fail(
            "AGE_RESTRICTION",
            f"{kid['name']} is {age}, but {camp['name']} accepts ages {camp['min_age']}-{camp['max_age']}.",
            {"kid_id": kid_id, "camp_id": camp_id},
        )
    if active_registration_for_kid_camp(db, kid_id, camp_id) is not None:
        return _fail(
            "DUPLICATE_REGISTRATION",
            f"{kid['name']} already has an active registration for {camp['name']}.",
            {"kid_id": kid_id, "camp_id": camp_id},
        )
    conflict, rows = has_schedule_conflict(db, kid_id, camp_id)
    if conflict:
        other = camp_by_id(db, rows[0]["camp_id"])
        return _fail(
            "SCHEDULE_CONFLICT",
            f"{kid['name']} already has an overlapping registration ({other['name'] if other else rows[0]['camp_id']}).",
            {"conflicts": rows},
        )
    return None


def validate_register_proposal(
    kid_id: str,
    camp_id: str,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Same business rules as register_kid, without mutating the DB. Use before queueing propose_register."""
    if not kid_id or not camp_id:
        return _fail("VALIDATION_ERROR", "kid_id and camp_id are required.")
    db = load_db(db_path)
    failure = _register_eligibility_failure(db, kid_id, camp_id)
    if failure is not None:
        return failure
    return _ok({})


def get_registrations(
    registration_id: str | None = None,
    kid_id: str | None = None,
    camp_id: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    db = load_db(db_path)
    rows = list(db["registrations"])
    if registration_id:
        reg = registration_by_id(db, registration_id)
        if not reg:
            return _fail("NOT_FOUND", f"No registration with id {registration_id!r}.")
        return _ok({"registrations": [reg]})
    if kid_id:
        rows = [r for r in rows if r["kid_id"] == kid_id]
    if camp_id:
        rows = [r for r in rows if r["camp_id"] == camp_id]
    return _ok({"registrations": rows})


def get_waitlist(camp_id: str, db_path: Path | None = None) -> dict[str, Any]:
    if not camp_id:
        return _fail("VALIDATION_ERROR", "camp_id is required.")
    db = load_db(db_path)
    camp = camp_by_id(db, camp_id)
    if not camp:
        return _fail("NOT_FOUND", f"No camp with id {camp_id!r}.")
    rows = [r for r in db["registrations"] if r["camp_id"] == camp_id and r["status"] == "waitlisted"]
    rows.sort(key=lambda r: r["registered_at"])
    waitlist = []
    for position, r in enumerate(rows, start=1):
        kid = kid_by_id(db, r["kid_id"])
        waitlist.append(
            {
                "queue_position": position,
                "registration_id": r["registration_id"],
                "kid_id": r["kid_id"],
                "kid_name": kid["name"] if kid else r["kid_id"],
                "registered_at": r["registered_at"],
            }
        )
    return _ok({"camp_id": camp_id, "waitlist": waitlist, "count": len(waitlist)})


def register_kid(
    kid_id: str,
    camp_id: str,
    db_path: Path | None = None,
) -> dict[str, Any]:
    if not kid_id or not camp_id:
        return _fail("VALIDATION_ERROR", "kid_id and camp_id are required.")
    db = load_db(db_path)
    failure = _register_eligibility_failure(db, kid_id, camp_id)
    if failure is not None:
        return failure
    camp = camp_by_id(db, camp_id)
    if not camp:
        return _fail("NOT_FOUND", f"No camp with id {camp_id!r}.")
    rid = next_registration_id(db["registrations"])
    if camp["enrolled"] >= camp["capacity"]:
        status = "waitlisted"
        db["registrations"].append(
            {
                "registration_id": rid,
                "kid_id": kid_id,
                "camp_id": camp_id,
                "status": status,
                "registered_at": registered_at_now(),
            }
        )
    else:
        status = "pending"
        db["registrations"].append(
            {
                "registration_id": rid,
                "kid_id": kid_id,
                "camp_id": camp_id,
                "status": status,
                "registered_at": registered_at_now(),
            }
        )
        camp["enrolled"] += 1
    save_db(db, db_path)
    return _ok({"registration_id": rid, "status": status})


def cancel_registration(registration_id: str, db_path: Path | None = None) -> dict[str, Any]:
    if not registration_id:
        return _fail("VALIDATION_ERROR", "registration_id is required.")
    db = load_db(db_path)
    reg = registration_by_id(db, registration_id)
    if not reg:
        return _fail("NOT_FOUND", f"No registration with id {registration_id!r}.")
    if reg["status"] == "cancelled":
        return _fail("INVALID_TRANSITION", "Registration is already cancelled.")
    prev_status = reg["status"]
    camp = camp_by_id(db, reg["camp_id"])
    if camp and prev_status in ("pending", "confirmed"):
        camp["enrolled"] -= 1
    reg["status"] = "cancelled"
    save_db(db, db_path)
    details: dict[str, Any] = {"registration_id": registration_id, "status": "cancelled"}
    if camp:
        details["camp_id"] = camp["camp_id"]
        details["enrolled_after"] = camp["enrolled"]
        details["capacity"] = camp["capacity"]
    if prev_status in ("pending", "confirmed") and camp:
        details["released_spot"] = True
    return _ok(details)


def update_registration_status(
    registration_id: str,
    new_status: str,
    db_path: Path | None = None,
) -> dict[str, Any]:
    if not registration_id or not new_status:
        return _fail("VALIDATION_ERROR", "registration_id and new_status are required.")
    if new_status not in KNOWN_REGISTRATION_STATUSES:
        return _fail("INVALID_STATUS", f"Unknown status {new_status!r}.")
    db = load_db(db_path)
    reg = registration_by_id(db, registration_id)
    if not reg:
        return _fail("NOT_FOUND", f"No registration with id {registration_id!r}.")
    current = reg["status"]
    if not allowed_status_transition(current, new_status):
        return _fail(
            "INVALID_TRANSITION",
            f"Cannot move registration from {current!r} to {new_status!r}.",
        )
    camp = camp_by_id(db, reg["camp_id"])
    if new_status == "confirmed" and current == "waitlisted":
        if not camp:
            return _fail("NOT_FOUND", "Camp missing for registration.")
        if camp["enrolled"] >= camp["capacity"]:
            return _fail("CAMP_FULL", f"{camp['name']} is full.", {"camp_id": camp["camp_id"]})
        camp["enrolled"] += 1
    elif new_status == "cancelled" and current in ("pending", "confirmed"):
        if camp:
            camp["enrolled"] -= 1
    reg["status"] = new_status
    save_db(db, db_path)
    return _ok({"registration_id": registration_id, "status": new_status})
