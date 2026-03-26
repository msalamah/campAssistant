"""Scripted LLM steps for E2E scenarios (aligned with mock_db.json)."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from tests.e2e.scripted_llm import ai_tools, tc


def steps_register_mia_soccer() -> list[Any]:
    return [
        ai_tools("", [tc("get_kids", {"name_query": "Mia Chen"}, "s1")]),
        ai_tools("", [tc("get_camps", {"name_query": "Soccer"}, "s2")]),
        ai_tools(
            "",
            [tc("propose_register", {"kid_id": "kid-10", "camp_id": "camp-1"}, "s3")],
        ),
        AIMessage(content="Please confirm this registration."),
    ]


def steps_duplicate_liam_swimming() -> list[Any]:
    return [
        ai_tools("", [tc("get_kids", {"kid_id": "kid-2"}, "d1")]),
        ai_tools("", [tc("get_camps", {"camp_id": "camp-4"}, "d2")]),
        ai_tools(
            "",
            [tc("propose_register", {"kid_id": "kid-2", "camp_id": "camp-4"}, "d3")],
        ),
        AIMessage(content="Liam already has that registration."),
    ]


def steps_waitlist_olivia_art() -> list[Any]:
    return [
        ai_tools("", [tc("get_kids", {"kid_id": "kid-5"}, "f1")]),
        ai_tools("", [tc("get_camps", {"camp_id": "camp-2"}, "f2")]),
        ai_tools(
            "",
            [tc("propose_register", {"kid_id": "kid-5", "camp_id": "camp-2"}, "f3")],
        ),
        AIMessage(
            content="Art Adventure is full — I can add Olivia to the waitlist. Please confirm."
        ),
    ]


def steps_age_ethan_swimming() -> list[Any]:
    return [
        ai_tools("", [tc("get_kids", {"kid_id": "kid-6"}, "a1")]),
        ai_tools("", [tc("get_camps", {"camp_id": "camp-4"}, "a2")]),
        ai_tools(
            "",
            [tc("propose_register", {"kid_id": "kid-6", "camp_id": "camp-4"}, "a3")],
        ),
        AIMessage(content="Ethan is outside the age range for that camp."),
    ]


def steps_conflict_emma_science() -> list[Any]:
    return [
        ai_tools("", [tc("get_kids", {"kid_id": "kid-1"}, "x1")]),
        ai_tools("", [tc("get_camps", {"camp_id": "camp-6"}, "x2")]),
        ai_tools(
            "",
            [tc("propose_register", {"kid_id": "kid-1", "camp_id": "camp-6"}, "x3")],
        ),
        AIMessage(content="That overlaps with another camp week."),
    ]


def steps_cancelled_sophia_drama() -> list[Any]:
    return [
        ai_tools("", [tc("get_kids", {"kid_id": "kid-7"}, "z1")]),
        ai_tools("", [tc("get_camps", {"camp_id": "camp-5"}, "z2")]),
        ai_tools(
            "",
            [tc("propose_register", {"kid_id": "kid-7", "camp_id": "camp-5"}, "z3")],
        ),
        AIMessage(content="That camp is not open."),
    ]


def steps_ambiguous_emma() -> list[Any]:
    return [
        ai_tools("", [tc("get_kids", {"name_query": "Emma"}, "m1")]),
        AIMessage(content="Which Emma do you mean—please say the full name."),
    ]


def steps_cancel_reg2() -> list[Any]:
    return [
        ai_tools("", [tc("get_registrations", {"registration_id": "reg-2"}, "u1")]),
        ai_tools(
            "",
            [tc("propose_cancel_registration", {"registration_id": "reg-2"}, "u2")],
        ),
        AIMessage(content="Confirm to cancel Liam's swimming registration."),
    ]


def steps_waitlist_promote_after_cancel() -> list[Any]:
    return [
        ai_tools("", [tc("get_registrations", {"registration_id": "reg-7"}, "w1")]),
        ai_tools(
            "",
            [tc("propose_cancel_registration", {"registration_id": "reg-7"}, "w2")],
        ),
        AIMessage(content="Confirm to cancel Emma Wilson's Science Explorers registration."),
        ai_tools("", [tc("get_waitlist", {"camp_id": "camp-6"}, "w3")]),
        ai_tools(
            "",
            [
                tc(
                    "propose_update_registration_status",
                    {"registration_id": "reg-6", "new_status": "confirmed"},
                    "w4",
                )
            ],
        ),
        AIMessage(content="Confirm promoting the waitlisted registration to confirmed."),
    ]


def steps_confirm_reg4() -> list[Any]:
    return [
        ai_tools("", [tc("get_registrations", {"registration_id": "reg-4"}, "v1")]),
        ai_tools(
            "",
            [
                tc(
                    "propose_update_registration_status",
                    {"registration_id": "reg-4", "new_status": "confirmed"},
                    "v2",
                )
            ],
        ),
        AIMessage(content="Confirm updating that registration to confirmed."),
    ]


def steps_greeting_only() -> list[Any]:
    return [
        AIMessage(
            content="Hi! I can help you browse camps, kids, and registrations. What would you like to do?"
        ),
    ]


def steps_vague_then_clarify() -> list[Any]:
    return [
        AIMessage(
            content="Which child and which camp should I look up? I can search by name."
        ),
    ]
