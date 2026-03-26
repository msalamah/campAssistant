"""Deterministic chat model for end-to-end agent tests (no OpenAI)."""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

class ScriptedChatModel(BaseChatModel):
    """Returns each ``AIMessage`` in order on ``invoke`` (tool calls included)."""

    steps: list[Any]
    i: int = 0

    def bind_tools(self, tools: Any, **kwargs: Any) -> ScriptedChatModel:
        return self

    def reset_script(self) -> None:
        self.i = 0

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        if self.i >= len(self.steps):
            raise RuntimeError(
                f"ScriptedChatModel exhausted {len(self.steps)} steps; need more AIMessages."
            )
        raw = self.steps[self.i]
        self.i += 1
        msg = AIMessage(content=raw) if isinstance(raw, str) else raw
        return ChatResult(generations=[ChatGeneration(message=msg)])

    @property
    def _llm_type(self) -> str:
        return "scripted-e2e"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"n_steps": len(self.steps)}


def tc(name: str, args: dict[str, Any], tid: str) -> dict[str, Any]:
    return {"name": name, "args": args, "id": tid, "type": "tool_call"}


def ai_tools(content: str, calls: list[dict[str, Any]]) -> AIMessage:
    return AIMessage(content=content, tool_calls=calls)
