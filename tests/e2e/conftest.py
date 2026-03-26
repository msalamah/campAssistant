"""E2E-only fixtures (see ``tests/conftest.py`` for ``--e2e-live`` and env loading)."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import pytest

from agent import CampAssistant
from langchain_core.callbacks.base import BaseCallbackHandler
from tests.e2e.instrumentation import attach_tool_recorder
from tests.e2e.scripted_llm import ScriptedChatModel


@pytest.fixture
def live_camp_assistant(
    db_path: Any,
    e2e_live_enabled: bool,
) -> tuple[CampAssistant, list]:
    """``CampAssistant`` with ``build_llm()`` when live mode is on; otherwise skips."""
    if not e2e_live_enabled:
        pytest.skip("Enable with --e2e-live or E2E_USE_REAL_LLM=1")
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY required for live E2E")
    from agent_langchain import build_llm

    agent = CampAssistant(
        db_path=db_path,
        llm=build_llm(),
    )
    records = attach_tool_recorder(agent)
    return agent, records


@pytest.fixture
def make_e2e_agent(db_path: Any) -> Callable[..., tuple[CampAssistant, list]]:
    """Returns ``(agent, tool_records)`` with ``_dispatch_tool`` instrumented."""

    def _make(
        script: list[Any],
        trace_callbacks: list[BaseCallbackHandler] | None = None,
    ) -> tuple[CampAssistant, list]:
        llm = ScriptedChatModel(steps=script)
        agent = CampAssistant(
            db_path=db_path,
            llm=llm,
            trace_callbacks=trace_callbacks,
        )
        records = attach_tool_recorder(agent)
        return agent, records

    return _make
