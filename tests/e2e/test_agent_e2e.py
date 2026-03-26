"""End-to-end agent tests: scripted LLM + graph + tools + optional LangSmith."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent import CampAssistant
from db_store import load_db, save_db
from tests.e2e import scenarios as sc
from tests.e2e.instrumentation import format_tool_report
from tests.e2e.scripted_llm import ScriptedChatModel


def _reg_status(db: dict, registration_id: str) -> str | None:
    for row in db["registrations"]:
        if row["registration_id"] == registration_id:
            return row["status"]
    return None


def _seed_reg7_confirmed_science_for_waitlist_promotion(db_path: Path) -> None:
    db = load_db(db_path)
    for c in db["camps"]:
        if c["camp_id"] == "camp-6":
            c["enrolled"] += 1
            break
    db["registrations"].append(
        {
            "registration_id": "reg-7",
            "kid_id": "kid-3",
            "camp_id": "camp-6",
            "status": "confirmed",
            "registered_at": "2026-06-01T08:00:00",
        }
    )
    save_db(db, db_path)


def _has_active_registration(db: dict, kid_id: str, camp_id: str) -> bool:
    active = {"pending", "confirmed", "waitlisted"}
    for r in db["registrations"]:
        if r["kid_id"] == kid_id and r["camp_id"] == camp_id and r["status"] in active:
            return True
    return False


def test_e2e_register_mia_soccer_confirm_writes_db(
    db_path: Path,
    make_e2e_agent,
) -> None:
    agent, rec = make_e2e_agent(sc.steps_register_mia_soccer())
    before = load_db(db_path)
    assert not _has_active_registration(before, "kid-10", "camp-1")

    r1 = agent.chat("Register Mia Chen for Soccer Stars")
    assert agent.state.awaiting_confirmation
    assert "confirm" in r1.lower()
    names = [x.name for x in rec]
    assert names == ["get_kids", "get_camps", "propose_register"]

    r2 = agent.chat("yes")
    assert agent.state.awaiting_confirmation is False
    assert "could not" not in r2.lower()
    after = load_db(db_path)
    assert _has_active_registration(after, "kid-10", "camp-1")


def test_e2e_waitlist_full_camp_confirm(db_path: Path, make_e2e_agent) -> None:
    agent, rec = make_e2e_agent(sc.steps_waitlist_olivia_art())
    before = load_db(db_path)
    n_reg = len(before["registrations"])
    r1 = agent.chat("Put Olivia in Art Adventure")
    assert agent.state.awaiting_confirmation
    assert "waitlist" in r1.lower() or "full" in r1.lower()
    assert any(x.name == "propose_register" for x in rec)
    r2 = agent.chat("yes")
    assert agent.state.awaiting_confirmation is False
    assert "could not" not in r2.lower()
    after = load_db(db_path)
    assert len(after["registrations"]) == n_reg + 1
    last = after["registrations"][-1]
    assert last["kid_id"] == "kid-5" and last["camp_id"] == "camp-2"
    assert last["status"] == "waitlisted"


def test_e2e_duplicate_proposal_no_confirm_pause(db_path: Path, make_e2e_agent) -> None:
    agent, rec = make_e2e_agent(sc.steps_duplicate_liam_swimming())
    r = agent.chat("Register Liam for swimming")
    assert agent.state.awaiting_confirmation is False
    assert "duplicate" in r.lower() or "already" in r.lower()
    assert any(x.name == "propose_register" for x in rec)


@pytest.mark.parametrize(
    ("factory", "prompt", "needles"),
    [
        (sc.steps_age_ethan_swimming, "Ethan for swimming basics", ("age",)),
        (sc.steps_conflict_emma_science, "Emma Thompson for Science Explorers", ("overlap",)),
        (sc.steps_cancelled_sophia_drama, "Sophia in Drama Club", ("open", "cancel")),
        (sc.steps_ambiguous_emma, "Register Emma for soccer", ("which", "name")),
    ],
)
def test_e2e_register_edge_cases_blocked(
    db_path: Path,
    make_e2e_agent,
    factory,
    prompt: str,
    needles: tuple[str, ...],
) -> None:
    agent, _ = make_e2e_agent(factory())
    r = agent.chat(prompt).lower()
    assert agent.state.awaiting_confirmation is False
    assert any(n in r for n in needles), r


def test_e2e_cancel_registration_confirm(db_path: Path, make_e2e_agent) -> None:
    assert _reg_status(load_db(db_path), "reg-2") != "cancelled"
    agent, rec = make_e2e_agent(sc.steps_cancel_reg2())
    r1 = agent.chat("Cancel Liam's swimming registration")
    assert agent.state.awaiting_confirmation
    assert "confirm" in r1.lower()
    assert any(x.name == "propose_cancel_registration" for x in rec)

    r2 = agent.chat("yes")
    assert "could not" not in r2.lower()
    assert _reg_status(load_db(db_path), "reg-2") == "cancelled"


def test_e2e_waitlist_promote_after_cancel(db_path: Path, make_e2e_agent) -> None:
    _seed_reg7_confirmed_science_for_waitlist_promotion(db_path)
    assert _reg_status(load_db(db_path), "reg-6") == "waitlisted"
    assert _reg_status(load_db(db_path), "reg-7") == "confirmed"

    agent, rec = make_e2e_agent(sc.steps_waitlist_promote_after_cancel())
    r1 = agent.chat("Cancel Emma Wilson's Science Explorers registration")
    assert agent.state.awaiting_confirmation
    assert any(x.name == "propose_cancel_registration" for x in rec)

    r2 = agent.chat("yes")
    assert "could not" not in r2.lower()
    assert _reg_status(load_db(db_path), "reg-7") == "cancelled"
    assert _reg_status(load_db(db_path), "reg-6") == "waitlisted"

    r3 = agent.chat("Promote the next person on the waitlist for Science Explorers")
    assert agent.state.awaiting_confirmation
    assert any(x.name == "get_waitlist" for x in rec)
    assert any(x.name == "propose_update_registration_status" for x in rec)
    assert "confirm" in r3.lower()

    r4 = agent.chat("yes")
    assert "could not" not in r4.lower()
    assert _reg_status(load_db(db_path), "reg-6") == "confirmed"


def test_e2e_update_registration_status_confirm(db_path: Path, make_e2e_agent) -> None:
    assert _reg_status(load_db(db_path), "reg-4") == "pending"
    agent, rec = make_e2e_agent(sc.steps_confirm_reg4())
    r1 = agent.chat("Confirm Emma's coding registration")
    assert agent.state.awaiting_confirmation
    assert any(x.name == "propose_update_registration_status" for x in rec)

    r2 = agent.chat("yes")
    assert "could not" not in r2.lower()
    assert _reg_status(load_db(db_path), "reg-4") == "confirmed"


def test_e2e_greeting_and_vague_user(db_path: Path, make_e2e_agent) -> None:
    a1, r1 = make_e2e_agent(sc.steps_greeting_only())
    out1 = a1.chat("Hello")
    assert "camp" in out1.lower() or "help" in out1.lower()
    assert len(r1) == 0

    a2, r2 = make_e2e_agent(sc.steps_vague_then_clarify())
    out2 = a2.chat("I need something")
    assert "which" in out2.lower() or "name" in out2.lower()
    assert len(r2) == 0


def test_e2e_empty_message_skips_tools(db_path: Path) -> None:
    agent = CampAssistant(
        db_path=db_path,
        llm=ScriptedChatModel(steps=[]),
    )
    assert agent.chat("") == ""
    assert agent.chat("   ") == ""


def test_e2e_long_user_message(db_path: Path, make_e2e_agent) -> None:
    agent, _ = make_e2e_agent(sc.steps_greeting_only())
    msg = "Please help me register " + "word " * 200
    out = agent.chat(msg)
    assert len(out) > 0


def test_tool_report_includes_latency(db_path: Path, make_e2e_agent) -> None:
    agent, rec = make_e2e_agent(sc.steps_register_mia_soccer())
    agent.chat("Register Mia Chen for Soccer Stars")
    text = format_tool_report(rec)
    assert "get_kids" in text
    assert "ms)" in text
