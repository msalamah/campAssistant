"""Pytest fixtures."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
SEED_DB = ROOT / "mock_db.json"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--e2e-live",
        action="store_true",
        default=False,
        help="Run optional E2E tests against real OpenAI (needs OPENAI_API_KEY).",
    )


def _e2e_live_enabled(config: pytest.Config | None) -> bool:
    if config is not None and config.getoption("--e2e-live", default=False):
        return True
    return os.getenv("E2E_USE_REAL_LLM", "").lower() in ("1", "true", "yes")


@pytest.fixture
def e2e_live_enabled(request: pytest.FixtureRequest) -> bool:
    return _e2e_live_enabled(request.config)


def pytest_configure(config: pytest.Config) -> None:
    load_dotenv(ROOT / ".env")
    if os.getenv("LANGCHAIN_TRACING_V2", "").lower() in ("1", "true"):
        os.environ.setdefault("LANGCHAIN_PROJECT", "camp-assistant-e2e")


def pytest_report_header(config: pytest.Config) -> str | None:
    lines: list[str] = []
    if os.getenv("LANGCHAIN_TRACING_V2", "").lower() in ("1", "true"):
        proj = os.getenv("LANGCHAIN_PROJECT", "default")
        lines.append(f"langsmith: enabled (project={proj}) — https://smith.langchain.com")
    else:
        lines.append(
            "langsmith: disabled — set LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY "
            "for traces (graph + LLM + tools appear automatically)"
        )
    if _e2e_live_enabled(config):
        lines.append("e2e live LLM: ON (--e2e-live or E2E_USE_REAL_LLM)")
    else:
        lines.append(
            "e2e live LLM: OFF (pass --e2e-live or E2E_USE_REAL_LLM=1 for OpenAI tests)"
        )
    return "\n".join(lines)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    dst = tmp_path / "mock_db.json"
    shutil.copy(SEED_DB, dst)
    return dst
