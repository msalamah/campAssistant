# Submission checklist

Use this list before you share your solution (zip or git link). Check items off as you go.

---

## What not to submit

- [ ] **`tasks.md` is not in the submission.** The assignment brief file is listed in `.gitignore` so it is not committed by default. If you already committed it earlier, remove it from the repo before submitting:  
  `git rm --cached tasks.md`  
  then commit, and keep `tasks.md` only on your machine if you still need it.
- [ ] **No secrets:** `.env` / API keys are not committed (`.gitignore` covers `.env` and `.env.local`; `.env.example` is safe to commit).

---

## Understanding and data

- [x] README explains setup (`uv sync`), run (`uv run python agent.py`), and how evaluation works.
- [x] `mock_db.json` is the source of truth for camps, kids, and registrations; tool reads ground the model.
- [x] Business rules are implemented in code: age range, capacity, cancelled camps, duplicate active registration, schedule overlap, ambiguous name resolution, registration status transitions, **waitlist when full**, **promoting waitlisted → confirmed** only when a seat exists (`CAMP_FULL` otherwise).

---

## Architecture

- [x] Clear split: **tool / DB layer** (`tool_schemas.py`, `tool_helpers.py`, `db_store.py`) vs **conversation / agent layer** (`agent.py`, `agent_langchain.py`, `agent_langgraph.py`).
- [x] Documented in **`ARCHITECTURE.md`**: deterministic validations vs LLM wording; explicit **`AssistantState`** + LangGraph pause for confirmation; two-layer state coordination.
- [x] **Context window note** in README: structured state and tool results for facts, not only chat history.

---

## Tool layer

- [x] **Reads:** `get_camps`, `get_kids`, `get_registrations`, **`get_waitlist`** (FIFO queue for a camp).
- [x] **Writes:** `register_kid`, `cancel_registration`, `update_registration_status` with validations in Python (not prompt-only).
- [x] **Full camp:** new registration becomes **`waitlisted`**; `enrolled` is not increased until someone holds a pending/confirmed seat.
- [x] **Cancel:** cancelling **pending** or **confirmed** decrements camp `enrolled`; success payload can include **`released_spot`**, **`camp_id`**, **`enrolled_after`**, **`capacity`**.
- [x] Structured **`success` / `error_code` / `details`** (see `tool_result.py`); validation order defined in code (e.g. duplicate and schedule conflict before placement).
- [x] **Unit tests** in `tests/test_tool_layer.py` (and related): reads, writes, waitlist, cancel, status updates, `validate_register_proposal`, edge cases.

---

## Agent (`CampAssistant.chat`)

- [x] Tools invoked via LangChain + LangGraph; **`SYSTEM_PROMPT`** and tool descriptions match policy (facts from tools, confirmation before writes, waitlist + promotion guidance).
- [x] **Multi-turn:** user can add details across messages; graph continues with checkpointed thread.
- [x] **Confirmation before every write:** `propose_*` queues `PendingAction`; real writes run only after explicit confirm (`yes` / Gradio Confirm / resume path).
- [x] **Graceful failures:** tool errors surfaced; guardrails block stale or incomplete pending writes (`guardrails.py`, tests in `tests/test_guardrails.py`).

---

## Guardrails

- [x] Facts from tools, not invented (prompt instructs; code enforces writes).
- [x] Ambiguity → clarify with candidates, no silent id guess in user-facing text.
- [x] Business rules enforced in tool code.
- [x] Failures explained briefly; optional user-facing hints via `user_message_for_tool_failure`.

---

## Evals

- [x] **Tool-level:** deterministic pytest (`tests/test_*.py` on a copied DB).
- [x] **Agent-level:** scripted E2E in `tests/e2e/` with **`ScriptedChatModel`** (no API key required for default CI).
- [x] **Scenarios** include: happy path, duplicate, full camp / waitlist, **waitlist promotion after cancel** (`get_waitlist` + status update), age, schedule conflict, cancelled camp, ambiguous name, cancel registration, update status, greeting, vague user; optional **live LLM** tests behind `--e2e-live`.
- [x] **Metrics** table in README names scenario completion, confirmation-before-write, etc.; assertions encode the important ones.
- [x] **Manual UI:** `MANUAL_UI_SCENARIOS.md` + Gradio **Test Scenario** dropdown (including waitlist and promotion flows where data allows).

---

## Prompting

- [x] System prompt and tool definitions are checked into the repo and aligned with behavior (`agent_langchain.py`).

---

## Repo and run

- [ ] **Reviewer check:** `uv sync` then `uv run python agent.py` launches the Gradio UI (requires `OPENAI_API_KEY` in `.env` for a live model).
- [ ] **Reviewer check:** `uv run pytest tests/ -q` passes in a clean environment.

---

## Polish and story

- [x] Code organized into small modules; naming and types are consistent enough for review.
- [x] Interview-ready line: **the model handles language and steps; Python holds rules, safety, and all database writes.**

---

## Files worth pointing reviewers to

| File | Why |
| --- | --- |
| `README.md` | Setup, evaluation plan, metrics |
| `ARCHITECTURE.md` | Layers, LangGraph, guardrails, waitlist behavior |
| `MANUAL_UI_SCENARIOS.md` | Hands-on UI tests |
| `SUBMISSION_CHECKLIST.md` | This list |
| `tests/e2e/test_agent_e2e.py` | Scripted agent flows including waitlist promotion |
