"""LangGraph: agent → (optional) human_approve with interrupt_before for HITL.

What LangGraph does (short):
- You define a **graph**: nodes (steps) and edges (what runs next).
- **State** is checkpointed so runs can pause and resume.
- **interrupt_before=["human_approve"]** stops execution *before* that node runs when the
  graph would enter it — e.g. after a propose_* tool queued a write. The UI or user can
  then approve (resume) or reject (resume without executing DB writes in our design).
- **Command(resume=...)** continues from the interrupt. We pair this with CampAssistant’s
  deterministic execute/reject of pending writes.

See: https://langchain-ai.github.io/langgraph/
"""

from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from agent_langchain import OPENAI_TOOLS, build_llm, run_tool_loop


class CampGraphState(TypedDict):
    messages: list[BaseMessage]
    proposal_pending: bool


def build_camp_graph(assistant: object, llm: BaseChatModel | None = None):
    """Compile graph with closure over assistant (for _dispatch_tool).

    Pass ``llm`` in tests with a scripted fake model; production uses ``build_llm()``.
    """
    model = build_llm() if llm is None else llm.bind_tools(OPENAI_TOOLS)

    def agent_node(state: CampGraphState) -> CampGraphState:
        msgs = list(state["messages"])
        _, proposal = run_tool_loop(model, msgs, assistant._dispatch_tool)
        return {"messages": msgs, "proposal_pending": proposal}

    def human_approve(_state: CampGraphState) -> dict:
        return {}

    def route_after_agent(state: CampGraphState) -> str:
        return "human_approve" if state.get("proposal_pending") else END

    builder = StateGraph(CampGraphState)
    builder.add_node("agent", agent_node)
    builder.add_node("human_approve", human_approve)
    builder.add_edge(START, "agent")
    builder.add_conditional_edges(
        "agent",
        route_after_agent,
        {"human_approve": "human_approve", END: END},
    )
    builder.add_edge("human_approve", END)
    return builder.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["human_approve"],
    )


def last_ai_text(messages: list[BaseMessage]) -> str:
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            c = m.content
            if isinstance(c, str) and c.strip():
                return c.strip()
    return ""


def graph_is_paused(graph: object, thread_id: str) -> bool:
    snap = graph.get_state({"configurable": {"thread_id": thread_id}})
    return bool(snap.next)


def resume_graph(
    graph: object,
    thread_id: str,
    callbacks: list | None = None,
) -> None:
    if not graph_is_paused(graph, thread_id):
        return
    cfg: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
    if callbacks:
        cfg["callbacks"] = callbacks
    graph.invoke(Command(resume=True), cfg)
