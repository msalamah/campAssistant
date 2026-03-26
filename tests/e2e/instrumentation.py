"""Local tool-call + latency recording for E2E tests (complements LangSmith tracing)."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from agent import CampAssistant


@dataclass
class ToolCallRecord:
    name: str
    args: dict[str, Any]
    duration_ms: float
    output: dict[str, Any] = field(default_factory=dict)


def attach_tool_recorder(agent: CampAssistant) -> list[ToolCallRecord]:
    """Wrap ``_dispatch_tool``; returns the list that is appended on each call."""
    records: list[ToolCallRecord] = []
    original = agent._dispatch_tool

    def wrapped(name: str, args: dict[str, Any]) -> dict[str, Any]:
        t0 = perf_counter()
        out = original(name, args)
        payload = out if isinstance(out, dict) else {"value": out}
        records.append(
            ToolCallRecord(
                name=name,
                args=dict(args),
                duration_ms=(perf_counter() - t0) * 1000.0,
                output=dict(payload),
            )
        )
        return out

    agent._dispatch_tool = wrapped  # type: ignore[method-assign]
    return records


def format_tool_report(records: list[ToolCallRecord]) -> str:
    lines = [f"tools={len(records)}"]
    for i, r in enumerate(records, 1):
        lines.append(f"  {i}. {r.name} ({r.duration_ms:.2f}ms) args={r.args}")
    return "\n".join(lines)
