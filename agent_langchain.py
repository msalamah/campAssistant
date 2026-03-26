"""LangChain ChatOpenAI + tool loop (reads + propose-only writes)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_openai import ChatOpenAI

MODEL = "gpt-4o-mini"
MAX_TOOL_ROUNDS = 12

SYSTEM_PROMPT = """You are a summer camp registration assistant for parents.

Your job:
- Help parents browse camps, review registrations, register a child, cancel a registration, and update registration status.
- Be concise, clear, and friendly.

Tool and fact rules:
- Use `get_camps`, `get_kids`, `get_registrations`, and `get_waitlist` as the source of truth for facts.
- Never invent camp, kid, registration, status, availability, or waitlist details.
- Before answering factual questions, use the read tools unless the answer is already in the current tool results for this turn.
- When summarizing camps, reflect tool data accurately. Camps with status `cancelled` are not open for signup. If you mention them, label them clearly.

Ambiguity and IDs:
- If a tool returns an ambiguity result, ask the user to clarify using human-friendly names only.
- Do not show internal ids in chat unless the user explicitly asks for them.
- Use ids only inside tool arguments, and only after they came from tool results.

Write safety:
- Never perform or queue a write from a guess.
- To register, cancel, or update a registration, first gather the exact ids with read tools when needed.
- Then call the matching `propose_*` tool.
- A successful `propose_*` call only queues the action. It does not save anything yet.
- After a successful proposal, ask for explicit confirmation before any write happens.
- If required details are missing, ask a focused follow-up question instead of proposing a write.

Business behavior:
- If a tool reports an error, explain it briefly and suggest the next useful step.
- If a camp is full, a new registration becomes `waitlisted`. Say that clearly when asking for confirmation.
- After cancelling a pending or confirmed registration, if the tool result shows `released_spot`, use `get_waitlist` for that `camp_id` to see who is next in FIFO order.
- If the user wants to move someone from `waitlisted` to `confirmed`, use `propose_update_registration_status` only when tool results show which registration should be updated.

Response style:
- Keep replies short and easy to understand.
- When asking for confirmation, summarize the exact change in plain language.
- Do not claim a write succeeded unless the write tool has actually succeeded after confirmation."""

OPENAI_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_camps",
            "description": "Read camp facts from the database. Use this before answering questions about camps, availability, schedules, prices, age ranges, or status. Filter by exact camp_id or by name_query, or omit both for all camps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "camp_id": {"type": "string", "description": "Exact camp id, e.g. camp-1."},
                    "name_query": {"type": "string", "description": "Substring or name to search."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_kids",
            "description": "Read child facts from the database. Use this to identify the correct child before any registration change. Filter by exact kid_id or by name_query, or omit both for all kids.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kid_id": {"type": "string", "description": "Exact kid id, e.g. kid-1."},
                    "name_query": {"type": "string", "description": "Substring or name to search."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_registrations",
            "description": "Read registration facts from the database. Use this before cancelling or changing status if you need to find the exact registration. Optionally filter by registration_id, kid_id, and/or camp_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "registration_id": {"type": "string"},
                    "kid_id": {"type": "string"},
                    "camp_id": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_waitlist",
            "description": "Read the waitlist for one camp in FIFO order (earliest registered first). Use this after a seat opens or when the user asks who is next on the waitlist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "camp_id": {"type": "string", "description": "Exact camp id, e.g. camp-2."},
                },
                "required": ["camp_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_register",
            "description": "Queue a registration change only after you know the exact kid_id and camp_id from tool results. This does not save yet. If the camp is full, the eventual write creates a waitlisted registration instead of a pending one.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kid_id": {"type": "string"},
                    "camp_id": {"type": "string"},
                },
                "required": ["kid_id", "camp_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_cancel_registration",
            "description": "Queue cancelling a registration only after you know the exact registration_id from tool results. This does not save yet; ask for confirmation after this succeeds.",
            "parameters": {
                "type": "object",
                "properties": {"registration_id": {"type": "string"}},
                "required": ["registration_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_update_registration_status",
            "description": "Queue a registration status change only after you know the exact registration_id from tool results. This does not save yet; ask for confirmation after this succeeds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "registration_id": {"type": "string"},
                    "new_status": {
                        "type": "string",
                        "enum": ["pending", "confirmed", "waitlisted", "cancelled"],
                    },
                },
                "required": ["registration_id", "new_status"],
            },
        },
    },
]


def build_llm() -> BaseChatModel:
    return ChatOpenAI(model=MODEL, temperature=0).bind_tools(OPENAI_TOOLS)


def run_tool_loop(
    llm: BaseChatModel,
    messages: list[BaseMessage],
    dispatch: Callable[[str, dict[str, Any]], dict[str, Any]],
) -> tuple[str, bool]:
    proposal_made = False
    for _ in range(MAX_TOOL_ROUNDS):
        response = llm.invoke(messages)
        if not isinstance(response, AIMessage):
            response = AIMessage(content=str(response))
        messages.append(response)
        if not response.tool_calls:
            return (response.content or "").strip(), proposal_made
        for tc in response.tool_calls:
            name, args = _tool_call_name_args(tc)
            out = dispatch(name, args)
            if name.startswith("propose_") and isinstance(out, dict) and out.get("status") == "proposed":
                proposal_made = True
            tid = _tool_call_id(tc)
            messages.append(
                ToolMessage(content=json.dumps(out, ensure_ascii=False), tool_call_id=tid)
            )
    return "I hit the tool-call limit; please narrow your request.", proposal_made


def _tool_call_name_args(tc: Any) -> tuple[str, dict[str, Any]]:
    if isinstance(tc, dict):
        return tc["name"], tc.get("args") or {}
    name = getattr(tc, "name", "") or ""
    args = getattr(tc, "args", None)
    if args is None:
        args = {}
    if not isinstance(args, dict):
        args = {}
    return name, args


def _tool_call_id(tc: Any) -> str:
    if isinstance(tc, dict):
        return str(tc.get("id", ""))
    return str(getattr(tc, "id", "") or "")
