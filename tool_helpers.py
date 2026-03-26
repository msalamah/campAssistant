"""Pure helpers: name resolution, schedule overlap, enrollment counts."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

ACTIVE_REGISTRATION_STATUSES = frozenset({"pending", "confirmed", "waitlisted"})
KNOWN_REGISTRATION_STATUSES = frozenset({"pending", "confirmed", "waitlisted", "cancelled"})


def normalize_name_query(query: str) -> str:
    return " ".join(query.strip().lower().split())


def entity_matches_name_field(entity: dict[str, Any], name_field: str, query_norm: str) -> bool:
    name = normalize_name_query(entity[name_field])
    if not query_norm:
        return False
    if name == query_norm:
        return True
    if query_norm in name:
        return True
    first = name.split()[0] if name else ""
    return first == query_norm


def resolve_entities_by_name(
    entities: list[dict[str, Any]],
    name_field: str,
    name_query: str,
    ambiguous_code: str,
) -> tuple[str | None, list[dict[str, Any]]]:
    """Returns (error_code or None, list of 0, 1, or many matches)."""
    q = normalize_name_query(name_query)
    if not q:
        return "VALIDATION_ERROR", []

    exact = [e for e in entities if normalize_name_query(e[name_field]) == q]
    if len(exact) == 1:
        return None, exact
    if len(exact) > 1:
        return ambiguous_code, exact[:10]

    matches = [e for e in entities if entity_matches_name_field(e, name_field, q)]
    if len(matches) == 0:
        return "NOT_FOUND", []
    if len(matches) == 1:
        return None, matches
    return ambiguous_code, matches[:10]


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


def parse_time_slot(time_slot: str) -> tuple[int, int]:
    start_s, end_s = time_slot.split("-", 1)
    start_h, start_m = start_s.strip().split(":")
    end_h, end_m = end_s.strip().split(":")
    return int(start_h) * 60 + int(start_m), int(end_h) * 60 + int(end_m)


def date_ranges_overlap(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    return max(a_start, b_start) <= min(a_end, b_end)


def time_intervals_overlap(a_lo: int, a_hi: int, b_lo: int, b_hi: int) -> bool:
    return a_hi > b_lo and b_hi > a_lo


def camps_schedule_conflict(camp_a: dict[str, Any], camp_b: dict[str, Any]) -> bool:
    da_s = parse_iso_date(camp_a["start_date"])
    da_e = parse_iso_date(camp_a["end_date"])
    db_s = parse_iso_date(camp_b["start_date"])
    db_e = parse_iso_date(camp_b["end_date"])
    if not date_ranges_overlap(da_s, da_e, db_s, db_e):
        return False
    a_lo, a_hi = parse_time_slot(camp_a["time_slot"])
    b_lo, b_hi = parse_time_slot(camp_b["time_slot"])
    return time_intervals_overlap(a_lo, a_hi, b_lo, b_hi)


def camp_by_id(db: dict[str, list], camp_id: str) -> dict[str, Any] | None:
    for c in db["camps"]:
        if c["camp_id"] == camp_id:
            return c
    return None


def kid_by_id(db: dict[str, list], kid_id: str) -> dict[str, Any] | None:
    for k in db["kids"]:
        if k["kid_id"] == kid_id:
            return k
    return None


def registration_by_id(db: dict[str, list], registration_id: str) -> dict[str, Any] | None:
    for r in db["registrations"]:
        if r["registration_id"] == registration_id:
            return r
    return None


def active_registration_for_kid_camp(db: dict[str, list], kid_id: str, camp_id: str) -> dict[str, Any] | None:
    for r in db["registrations"]:
        if r["kid_id"] == kid_id and r["camp_id"] == camp_id and r["status"] in ACTIVE_REGISTRATION_STATUSES:
            return r
    return None


def next_registration_id(registrations: list[dict[str, Any]]) -> str:
    highest = 0
    for r in registrations:
        rid = r.get("registration_id", "")
        if not rid.startswith("reg-"):
            continue
        try:
            highest = max(highest, int(rid.split("-", 1)[1]))
        except (IndexError, ValueError):
            continue
    return f"reg-{highest + 1}"


def registered_at_now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def has_schedule_conflict(
    db: dict[str, list],
    kid_id: str,
    new_camp_id: str,
    ignore_registration_id: str | None = None,
) -> tuple[bool, list[dict[str, Any]]]:
    new_camp = camp_by_id(db, new_camp_id)
    if not new_camp:
        return False, []
    conflicts: list[dict[str, Any]] = []
    for r in db["registrations"]:
        if r["kid_id"] != kid_id:
            continue
        if r["status"] not in ACTIVE_REGISTRATION_STATUSES:
            continue
        if ignore_registration_id and r["registration_id"] == ignore_registration_id:
            continue
        if r["camp_id"] == new_camp_id:
            continue
        other = camp_by_id(db, r["camp_id"])
        if other and camps_schedule_conflict(new_camp, other):
            conflicts.append(r)
    return len(conflicts) > 0, conflicts


def allowed_status_transition(from_status: str, to_status: str) -> bool:
    if from_status == "cancelled":
        return False
    if to_status not in KNOWN_REGISTRATION_STATUSES:
        return False
    if from_status == "pending":
        return to_status in {"confirmed", "cancelled"}
    if from_status == "confirmed":
        return to_status == "cancelled"
    if from_status == "waitlisted":
        return to_status in {"confirmed", "cancelled"}
    return False
