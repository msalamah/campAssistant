"""
Summer Camp Registration Assistant

Implement your conversational agent here.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from collections.abc import Sequence
from typing import Any

import gradio as gr
from dotenv import load_dotenv
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from agent_langchain import SYSTEM_PROMPT
from agent_langgraph import build_camp_graph, graph_is_paused, last_ai_text, resume_graph
from agent_state import AssistantState, PendingAction, clear_confirmation, new_assistant_state
from confirmation import is_confirmation, is_rejection
from guardrails import can_execute_pending_write, user_message_for_tool_failure, validate_propose_tool
from db_store import DEFAULT_DB_PATH
from tool_schemas import (
    cancel_registration,
    get_camps,
    get_kids,
    get_registrations,
    get_waitlist,
    register_kid,
    update_registration_status,
    validate_register_proposal,
)

load_dotenv()


class CampAssistant:
    def __init__(
        self,
        db_path: Path | None = None,
        llm: BaseChatModel | None = None,
        trace_callbacks: Sequence[BaseCallbackHandler] | None = None,
    ) -> None:
        self.db_path = db_path or DEFAULT_DB_PATH
        self._llm = llm
        self._trace_callbacks: list[BaseCallbackHandler] = (
            list(trace_callbacks) if trace_callbacks else []
        )
        self.state: AssistantState = new_assistant_state()
        self._messages: list[dict[str, str]] = []
        self._lc_messages: list[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
        self._thread_id = str(uuid.uuid4())
        self._graph = build_camp_graph(self, llm=llm)

    def reset_conversation(self) -> None:
        if self._llm is not None and hasattr(self._llm, "reset_script"):
            self._llm.reset_script()
        self.state = new_assistant_state()
        self._messages.clear()
        self._lc_messages = [SystemMessage(content=SYSTEM_PROMPT)]
        self._thread_id = str(uuid.uuid4())
        self._graph = build_camp_graph(self, llm=self._llm)

    def confirm_pending_write(self) -> str:
        if not self.state.awaiting_confirmation:
            return "Nothing to confirm right now."
        return self.chat("yes")

    def reject_pending_write(self) -> str:
        if not self.state.awaiting_confirmation:
            return "Nothing to cancel right now."
        return self.chat("no")

    def _run_langgraph_agent_turn(self) -> tuple[str, bool]:
        cfg: dict[str, Any] = {"configurable": {"thread_id": self._thread_id}}
        if self._trace_callbacks:
            cfg["callbacks"] = self._trace_callbacks
        result = self._graph.invoke(
            {"messages": self._lc_messages, "proposal_pending": False},
            cfg,
        )
        self._lc_messages = list(result["messages"])
        reply = last_ai_text(self._lc_messages)
        awaiting = graph_is_paused(self._graph, self._thread_id)
        return reply, awaiting

    def chat(self, user_message: str) -> str:
        if self._llm is None and not os.getenv("OPENAI_API_KEY"):
            return "Set OPENAI_API_KEY in your .env file."
        text = user_message.strip()
        if not text:
            return ""

        if self.state.awaiting_confirmation:
            self._lc_messages.append(HumanMessage(content=text))
            if is_confirmation(text):
                resume_graph(self._graph, self._thread_id, self._trace_callbacks or None)
                reply = self._execute_pending_and_format()
                self._lc_messages.append(AIMessage(content=reply))
                self._messages.append({"role": "user", "content": text})
                self._messages.append({"role": "assistant", "content": reply})
                return reply
            if is_rejection(text):
                clear_confirmation(self.state)
                resume_graph(self._graph, self._thread_id, self._trace_callbacks or None)
                reply = "Okay — I won't make that change."
                self._lc_messages.append(AIMessage(content=reply))
                self._messages.append({"role": "user", "content": text})
                self._messages.append({"role": "assistant", "content": reply})
                return reply
            clear_confirmation(self.state)
            resume_graph(self._graph, self._thread_id, self._trace_callbacks or None)
            reply, awaiting = self._run_langgraph_agent_turn()
            self.state.awaiting_confirmation = awaiting
            self._messages.append({"role": "user", "content": text})
            self._messages.append({"role": "assistant", "content": reply})
            return reply

        self._lc_messages.append(HumanMessage(content=text))
        reply, awaiting = self._run_langgraph_agent_turn()
        self.state.awaiting_confirmation = awaiting
        self._messages.append({"role": "user", "content": text})
        self._messages.append({"role": "assistant", "content": reply})
        return reply

    def _dispatch_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "get_camps":
            r = get_camps(
                camp_id=self._opt(args.get("camp_id")),
                name_query=self._opt(args.get("name_query")),
                db_path=self.db_path,
            )
            return self._maybe_enrich_tool_error(r)
        if name == "get_kids":
            r = get_kids(
                kid_id=self._opt(args.get("kid_id")),
                name_query=self._opt(args.get("name_query")),
                db_path=self.db_path,
            )
            return self._maybe_enrich_tool_error(r)
        if name == "get_registrations":
            r = get_registrations(
                registration_id=self._opt(args.get("registration_id")),
                kid_id=self._opt(args.get("kid_id")),
                camp_id=self._opt(args.get("camp_id")),
                db_path=self.db_path,
            )
            return self._maybe_enrich_tool_error(r)
        if name == "get_waitlist":
            r = get_waitlist(camp_id=str(args.get("camp_id") or ""), db_path=self.db_path)
            return self._maybe_enrich_tool_error(r)
        if name == "propose_register":
            ok, err = validate_propose_tool(name, args)
            if not ok:
                return {"success": False, "error_code": "VALIDATION_ERROR", "message": err}
            pre = validate_register_proposal(
                str(args.get("kid_id")),
                str(args.get("camp_id")),
                db_path=self.db_path,
            )
            if not pre.get("success"):
                return self._maybe_enrich_tool_error(pre)
            self.state.pending_action = PendingAction(
                kind="register",
                kid_id=args.get("kid_id"),
                camp_id=args.get("camp_id"),
            )
            return {"status": "proposed", "message": "Queued; ask the user to confirm."}
        if name == "propose_cancel_registration":
            ok, err = validate_propose_tool(name, args)
            if not ok:
                return {"success": False, "error_code": "VALIDATION_ERROR", "message": err}
            self.state.pending_action = PendingAction(
                kind="cancel_registration",
                registration_id=args.get("registration_id"),
            )
            return {"status": "proposed", "message": "Queued; ask the user to confirm."}
        if name == "propose_update_registration_status":
            ok, err = validate_propose_tool(name, args)
            if not ok:
                return {"success": False, "error_code": "VALIDATION_ERROR", "message": err}
            self.state.pending_action = PendingAction(
                kind="update_registration_status",
                registration_id=args.get("registration_id"),
                new_status=args.get("new_status"),
            )
            return {"status": "proposed", "message": "Queued; ask the user to confirm."}
        return {"success": False, "error_code": "VALIDATION_ERROR", "message": f"Unknown tool {name!r}."}

    @staticmethod
    def _maybe_enrich_tool_error(r: dict[str, Any]) -> dict[str, Any]:
        if r.get("success"):
            return r
        merged = user_message_for_tool_failure(r)
        if merged:
            return {**r, "message": merged}
        return r

    @staticmethod
    def _opt(value: Any) -> str | None:
        if value is None or value == "":
            return None
        return str(value)

    def _execute_pending_and_format(self) -> str:
        ok, err = can_execute_pending_write(self.state)
        if not ok:
            clear_confirmation(self.state)
            return err
        pa = self.state.pending_action
        if not pa:
            clear_confirmation(self.state)
            return "Nothing was queued to confirm."
        if pa.kind == "register":
            r = register_kid(pa.kid_id or "", pa.camp_id or "", db_path=self.db_path)
        elif pa.kind == "cancel_registration":
            r = cancel_registration(pa.registration_id or "", db_path=self.db_path)
        elif pa.kind == "update_registration_status":
            r = update_registration_status(
                pa.registration_id or "", pa.new_status or "", db_path=self.db_path
            )
        else:
            clear_confirmation(self.state)
            return "Unknown pending action."
        self.state.last_tool_result = r
        clear_confirmation(self.state)
        return self._format_write_result(r)

    @staticmethod
    def _format_write_result(r: dict[str, Any]) -> str:
        if r["success"]:
            if r.get("message"):
                return r["message"]
            details = r.get("details") or {}
            if "registration_id" in details and "status" in details:
                return (
                    f"Registration {details['registration_id']} is now {details['status']}."
                )
            if "registration_id" in details:
                return f"Updated registration {details['registration_id']}."
            return "Done."
        return f"Could not complete that: {r['message']}"


# =============================================================================
# Debug UI - Run with: uv run python agent.py
# =============================================================================


def _confirm_panel_visible(agent: CampAssistant) -> gr.Update:
    return gr.update(visible=agent.state.awaiting_confirmation)


def create_debug_ui(agent_class):
    agent = agent_class()
    history = []

    def chat_fn(message, chat_history):
        if not message.strip():
            return chat_history, "", gr.update(visible=agent.state.awaiting_confirmation)
        try:
            response = agent.chat(message)
        except Exception as e:
            response = f"Error: {e}"

        chat_history.append({"role": "user", "content": message})
        chat_history.append({"role": "assistant", "content": response})
        history.append({"user": message, "assistant": response})
        return chat_history, "", _confirm_panel_visible(agent)

    def confirm_fn(chat_history):
        try:
            response = agent.confirm_pending_write()
        except Exception as e:
            response = f"Error: {e}"
        chat_history.append({"role": "user", "content": "✓ Confirm"})
        chat_history.append({"role": "assistant", "content": response})
        return chat_history, _confirm_panel_visible(agent)

    def cancel_fn(chat_history):
        try:
            response = agent.reject_pending_write()
        except Exception as e:
            response = f"Error: {e}"
        chat_history.append({"role": "user", "content": "✗ Cancel"})
        chat_history.append({"role": "assistant", "content": response})
        return chat_history, _confirm_panel_visible(agent)

    def reset_fn():
        nonlocal agent, history
        agent = agent_class()
        history.clear()
        return [], "", gr.update(visible=False)

    def load_scenario(scenario):
        scenarios = {
            "Happy Path": "Register Mia Chen for Soccer Stars",
            "Ambiguous Name": "Register Emma for Soccer Stars",
            "Waitlist (full camp)": "Sign up Liam Chen for Art Adventure",
            "Waitlist promotion": "Cancel Emma Wilson's Science Explorers registration",
            "Age Restriction": "Register Ethan Davis for Swimming Basics",
            "Schedule Conflict": "Register Emma Thompson for Science Explorers",
            "Cancelled Camp": "Register Sophia Lee for Drama Club",
            "Sibling Registration": "Register both Chen kids for Soccer Stars",
            "Multi-Turn: Change Mind": "I want to register my kid for a camp",
        }
        return scenarios.get(scenario, "")

    with gr.Blocks(title="Camp Assistant") as demo:
        gr.Markdown("# Camp Registration Assistant")

        with gr.Row():
            with gr.Column():
                chatbot = gr.Chatbot(height=450)
                with gr.Column(visible=False) as confirm_panel:
                    gr.Markdown("**Pending change** — confirm or cancel (or type yes / no in the chat).")
                    with gr.Row():
                        btn_confirm = gr.Button("Confirm", variant="primary")
                        btn_cancel = gr.Button("Cancel", variant="stop")
                with gr.Row():
                    msg = gr.Textbox(placeholder="Message...", scale=4)
                    send = gr.Button("Send", variant="primary")
                with gr.Row():
                    reset = gr.Button("Reset")
                    scenario = gr.Dropdown(
                        [
                            "Happy Path",
                            "Ambiguous Name",
                            "Waitlist (full camp)",
                            "Waitlist promotion",
                            "Age Restriction",
                            "Schedule Conflict",
                            "Cancelled Camp",
                            "Sibling Registration",
                            "Multi-Turn: Change Mind",
                        ],
                        label="Test Scenario",
                    )
                    load = gr.Button("Load")

        send.click(chat_fn, [msg, chatbot], [chatbot, msg, confirm_panel])
        msg.submit(chat_fn, [msg, chatbot], [chatbot, msg, confirm_panel])
        btn_confirm.click(confirm_fn, [chatbot], [chatbot, confirm_panel])
        btn_cancel.click(cancel_fn, [chatbot], [chatbot, confirm_panel])
        reset.click(reset_fn, outputs=[chatbot, msg, confirm_panel])
        load.click(load_scenario, [scenario], [msg])

    return demo


if __name__ == "__main__":
    create_debug_ui(CampAssistant).launch()
