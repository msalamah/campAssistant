# Summer Camp Registration Assistant

## Overview

This project implements a conversational assistant for summer camp registration.

The assistant can:
- answer questions about camps, kids, registrations, and waitlists
- register a child for a camp
- cancel a registration
- update registration status
- handle ambiguous names, invalid requests, and multi-turn follow-up
- require confirmation before every write

The system uses a local mock database in `mock_db.json`. Facts come from tools, not from free-form model memory.

For a deeper explanation of the system design, state model, confirmation flow, and waitlist behavior, see `ARCHITECTURE.md`.

---

## Setup

1. Copy `.env.example` to `.env`.
2. Install dependencies.
3. Run the app.

"""bash
cp .env.example .env
uv sync
uv run python agent.py
"""

The app starts a Gradio debug UI in the browser.

**Model:** `gpt-4o-mini`

**Important:** `.env` is gitignored. Do not commit or push your API key.

## Environment Variables

Create a local `.env` file from `.env.example`.

| Variable | Required | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | Yes for the Gradio app and live OpenAI tests | Used by `ChatOpenAI` in the assistant |
| `LANGCHAIN_TRACING_V2` | No | Enables LangSmith / LangChain tracing when set to `true` |
| `LANGCHAIN_PROJECT` | No | Sets the LangSmith project name; defaults to `camp-assistant-e2e` in test flows when tracing is enabled |
| `LANGCHAIN_API_KEY` | No | Auth token for LangSmith tracing |
| `LANGSMITH_API_KEY` | No | Alternative auth variable for LangSmith tracing |
| `E2E_USE_REAL_LLM` | No | Enables optional live OpenAI E2E tests when set to `1`, `true`, or `yes` |

Minimal `.env` for local app use:

```bash
OPENAI_API_KEY="your-openai-api-key"
```

Optional tracing and live E2E example:

```bash
OPENAI_API_KEY="your-openai-api-key"
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT="camp-assistant-e2e"
LANGCHAIN_API_KEY="your-langsmith-api-key"
E2E_USE_REAL_LLM=false
```

---

## What Is Implemented

### Data layer

The tool layer reads and writes `mock_db.json` through deterministic Python code. It owns:
- input validation
- name matching
- age checks
- cancelled-camp checks
- duplicate-registration checks
- schedule-conflict checks
- waitlist logic
- registration status transitions

### Conversation layer

The agent layer handles:
- natural language understanding
- tool selection
- follow-up questions
- confirmation wording
- multi-turn flow
- Gradio UI integration

The model helps with wording and next-step choice. Python code enforces rules and writes.

---

## Tools

The LLM can call the following tools through LangChain tool calling.

### Read tools

| Tool | Purpose | Notes |
| --- | --- | --- |
| `get_camps` | Read camp facts | Supports `camp_id` or `name_query`; returns schedule, price, age range, status, capacity, enrolled count |
| `get_kids` | Read child facts | Supports `kid_id` or `name_query`; used to resolve the right child before writes |
| `get_registrations` | Read registration facts | Supports `registration_id`, `kid_id`, and `camp_id` filters |
| `get_waitlist` | Read waitlist order for one camp | Returns FIFO queue with `queue_position`, `registration_id`, `kid_name`, and `registered_at` |

### Propose tools

These are the tools exposed to the model for write flows. They do **not** write to the database directly.

| Tool | Purpose | Notes |
| --- | --- | --- |
| `propose_register` | Queue a registration | Requires exact `kid_id` and `camp_id`; if the camp is full, the real write becomes `waitlisted` |
| `propose_cancel_registration` | Queue a cancellation | Requires exact `registration_id` |
| `propose_update_registration_status` | Queue a status change | Requires exact `registration_id` and `new_status` |

### Deterministic write functions

These functions are not called by the model directly. They run only after confirmation.

| Function | What it does |
| --- | --- |
| `register_kid` | Creates a `pending` registration when a seat is open, or a `waitlisted` registration when the camp is full |
| `cancel_registration` | Cancels a registration and decrements `enrolled` if the previous status held a seat |
| `update_registration_status` | Updates a registration status, including `waitlisted -> confirmed` when capacity allows |
| `validate_register_proposal` | Runs the same business checks as `register_kid` without mutating the DB |

### Tool result shape

All tool functions return structured results in the same shape:
- `success`
- `error_code`
- `message`
- `details`

This makes it easier to test rules and turn tool outcomes into clear chat replies.

---

## Business Rules

The current implementation enforces these rules in Python:

- a camp must exist
- a child must exist
- a camp must be `open` to accept a new registration
- the child must be inside the camp age range
- the child cannot have another active registration for the same camp
- the child cannot have an overlapping active registration in the same time window
- a full camp creates a `waitlisted` registration instead of rejecting the signup
- a `waitlisted` registration can move to `confirmed` only when a seat is free
- `cancelled` registrations are terminal for normal update flows

### Waitlist behavior

The project includes waitlist support.

- If `enrolled >= capacity`, `register_kid` creates a new row with `status: waitlisted`.
- Waitlisted signups do **not** increase `camp["enrolled"]`.
- When a `pending` or `confirmed` registration is cancelled, `cancel_registration` may return `released_spot: true`.
- After a seat opens, the agent can call `get_waitlist(camp_id)` to inspect the FIFO queue.
- The next waitlisted registration can be promoted through `propose_update_registration_status(..., new_status="confirmed")`.
- If the camp is still full at promotion time, the write returns `CAMP_FULL`.

---

## Guardrails

The project uses both prompt-level and code-level guardrails.

| Guardrail | How it works |
| --- | --- |
| Tool-based source of truth | Facts come from `get_camps`, `get_kids`, `get_registrations`, and `get_waitlist` |
| No guessing on ambiguity | Ambiguous searches return candidates; the assistant asks the user to clarify instead of picking silently |
| No raw-id dependence in chat | The assistant uses human-friendly names in replies; ids stay inside tool arguments unless the user asks for ids |
| Confirmation before writes | Every write goes through a `propose_*` step and then explicit confirmation |
| Deterministic pending-write gate | `can_execute_pending_write()` blocks incomplete or invalid queued actions |
| Deterministic propose validation | `validate_propose_tool()` checks that required arguments exist before queueing |
| Safe error handling | `_maybe_enrich_tool_error()` and `user_message_for_tool_failure()` turn tool failures into clearer replies |
| Business rules in code | Validation lives in `tool_schemas.py` and `tool_helpers.py`, not only in the prompt |

### Error codes

The tool layer uses stable error codes such as:
- `NOT_FOUND`
- `AMBIGUOUS_KID`
- `AMBIGUOUS_CAMP`
- `CAMP_CANCELLED`
- `CAMP_FULL`
- `AGE_RESTRICTION`
- `DUPLICATE_REGISTRATION`
- `SCHEDULE_CONFLICT`
- `INVALID_STATUS`
- `INVALID_TRANSITION`
- `VALIDATION_ERROR`

These codes are covered by tests and make failures easier to explain and assert.

---

## Agent Architecture

The system has two main layers.

| Layer | Responsibility | Main files |
| --- | --- | --- |
| Tool / DB layer | Read and write the mock DB, enforce business rules, return structured results | `tool_schemas.py`, `tool_helpers.py`, `db_store.py` |
| Conversation / agent layer | Run the LLM, dispatch tools, hold state, manage confirmation, expose the Gradio UI | `agent.py`, `agent_langchain.py`, `agent_langgraph.py`, `agent_state.py`, `guardrails.py` |

### Core flow

1. The user sends a message to `CampAssistant.chat()`.
2. The message is added to the LangChain message list.
3. LangGraph runs the `agent` node.
4. The LLM decides whether to answer directly or call tools.
5. `_dispatch_tool()` routes tool calls to deterministic Python functions.
6. If the LLM calls a `propose_*` tool successfully, the assistant stores a `PendingAction`.
7. LangGraph pauses before `human_approve`, and the UI shows the confirm panel.
8. If the user confirms, the assistant runs the real write function and formats the final result.
9. If the user rejects, the assistant clears the pending action and does not write.

### State model

There are two state stores in the current design.

- `CampGraphState` in LangGraph holds `messages` and `proposal_pending`
- `AssistantState` on `CampAssistant` holds transactional data such as:
  - `intent`
  - `selected_kid_id`
  - `selected_camp_id`
  - `selected_registration_id`
  - `candidate_kids`
  - `candidate_camps`
  - `awaiting_confirmation`
  - `pending_action`
  - `last_tool_result`

This split keeps the graph simple, while still giving the assistant explicit state for transactions.

More implementation detail is documented in `ARCHITECTURE.md`.

### Why the agent does not rely only on chat history

The assistant does not trust the full conversation alone for facts that matter to writes.

| Information | Where it is kept |
| --- | --- |
| Current child or camp for the flow | `AssistantState` and fresh tool reads |
| Ambiguous candidates | Tool payloads and state candidate lists |
| Queued write before confirmation | `pending_action` and `awaiting_confirmation` |
| Latest write outcome | `last_tool_result` |

This makes the assistant more reliable when a conversation gets long.

### Prompt design

The system prompt in `agent_langchain.py` is intentionally general.

It tells the model to:
- use read tools for facts
- avoid guessing
- ask for clarification on ambiguity
- queue writes with `propose_*`
- ask for confirmation before writes
- explain waitlist behavior clearly
- keep replies short and friendly

Tool descriptions reinforce when each tool should be used.

---

## Confirmation UX

Confirmation is supported in two ways:

- type a confirmation reply such as `yes`, `confirm`, or `okay`
- click the **Confirm** button in the Gradio UI

Rejection is also supported in two ways:

- type `no`, `cancel`, `stop`, or `never mind`
- click the **Cancel** button in the Gradio UI

The button flow and typed flow use the same deterministic confirmation logic from `confirmation.py`.

---

## Testing And Evaluation

The project has three levels of evaluation.

### 1. Tool-level tests

These tests check deterministic business rules on a copy of the database.

| Area | Tests |
| --- | --- |
| Reads, ambiguity, not found | `tests/test_tool_layer.py` |
| Register, cancel, update status | `tests/test_tool_layer.py` |
| Proposal validation | `validate_register_proposal` in `tests/test_tool_layer.py` |
| Confirmation phrase parsing | `tests/test_confirmation.py` |
| Assistant state helpers | `tests/test_agent_state.py` |
| Guardrails | `tests/test_guardrails.py` |

Run all tests:

"""bash
uv run pytest tests/ -q
"""

### 2. Scripted end-to-end tests

`tests/e2e/` runs the real assistant, graph, and tool dispatch with a scripted fake LLM.

This gives deterministic end-to-end coverage for flows such as:
- happy path registration
- ambiguous child name
- duplicate registration
- full camp / waitlist
- waitlist promotion after cancellation
- age restriction
- schedule conflict
- cancelled camp
- cancel registration
- update registration status

### 3. Optional live model checks

The project also supports optional live OpenAI E2E tests and manual testing in Gradio.

Run live E2E:

"""bash
uv run pytest tests/e2e/ -v --e2e-live
"""

Run the app for manual testing:

"""bash
uv run python agent.py
"""

### LangSmith support

LangSmith tracing is supported for the graph, model, and tool calls.

Set tracing variables if you want live traces:

"""bash
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=...
export LANGCHAIN_PROJECT=camp-assistant-e2e
"""

### Review metrics

Useful review metrics for this project are:
- scenario completion rate
- writes only after confirmation
- invalid write prevention rate
- ambiguity resolution success
- turns needed to finish a valid flow

---

## Debug UI

The Gradio UI in `agent.py` is a development tool for local testing.

It includes:
- a chat window
- a hidden confirm panel that appears when `awaiting_confirmation` is `True`
- **Confirm** and **Cancel** buttons
- a **Reset** button
- a **Test Scenario** dropdown for quick manual checks

Manual scenarios are documented in `MANUAL_UI_SCENARIOS.md`.

---

## Security And Privacy

This project is a local prototype, not a production system.

What is already handled:
- API keys stay in `.env`
- `.env` is gitignored
- `tasks.md` is gitignored for submission cleanliness
- writes require explicit confirmation
- facts come from tools instead of the model inventing data

What a production system would still need:
- authentication
- authorization
- stronger secret management
- audit logs
- PII minimization and masking
- access controls around parent and child contact details
- data retention and deletion policy

This matters because the mock data includes child information and parent contact details.

---

## Files

| File | Purpose |
| --- | --- |
| `mock_db.json` | Mock database with camps, kids, and registrations |
| `tool_schemas.py` | Public tool API and deterministic write functions |
| `tool_helpers.py` | Name matching, schedule conflict checks, status transitions |
| `agent.py` | `CampAssistant`, tool routing, confirmation execution, Gradio UI |
| `agent_langchain.py` | System prompt, tool definitions, tool loop |
| `agent_langgraph.py` | LangGraph setup and pause / resume logic |
| `agent_state.py` | Explicit assistant state and pending actions |
| `guardrails.py` | Pending-write gate, propose validation, tool-failure hints |
| `MANUAL_UI_SCENARIOS.md` | Manual browser test scenarios |
| `ARCHITECTURE.md` | Detailed architecture and implementation notes |
| `SUBMISSION_CHECKLIST.md` | Pre-submit checklist |
| `tests/` | Unit, integration, and E2E tests |