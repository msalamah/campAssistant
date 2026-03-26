"""Optional E2E tests using real OpenAI (non-deterministic). Enable with --e2e-live or E2E_USE_REAL_LLM=1."""

from __future__ import annotations

import pytest


@pytest.mark.e2e_live
def test_live_llm_short_reply(live_camp_assistant) -> None:
    agent, _rec = live_camp_assistant
    reply = agent.chat("Reply with exactly one word: OK")
    assert len(reply.strip()) >= 2
    assert "Set OPENAI_API_KEY" not in reply


@pytest.mark.e2e_live
def test_live_llm_uses_read_tool_for_camps(live_camp_assistant) -> None:
    agent, rec = live_camp_assistant
    reply = agent.chat(
        "What camps exist in the system? You must call get_camps to answer; "
        "then name one camp from the result."
    )
    assert len(reply) > 20
    tool_names = [x.name for x in rec]
    assert "get_camps" in tool_names, f"expected get_camps in {tool_names}; reply={reply[:200]!r}"
