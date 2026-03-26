# Manual UI scenarios (Gradio)

Use this list when you test the assistant yourself in the browser. Start the app from the project root:

```bash
uv sync
uv run python agent.py
```

Put `OPENAI_API_KEY` in `.env`. Open the URL shown in the terminal (often `http://127.0.0.1:7860`).

**Tips**

- Use **Reset** between scenarios so state stays clean.
- When the assistant asks to confirm a write, use **Confirm** / **Cancel** or type **yes** / **no** in the chat.
- The **Test Scenario** dropdown only fills the message box — press **Load**, then **Send** (or edit the text first).

---

## Quick smoke

| Step | You type or click | What to check |
| --- | --- | --- |
| 1 | `Hello` | Short friendly reply; no crash. |
| 2 | `What camps are available?` | Assistant uses tools and mentions real camp names from the data (e.g. Soccer Stars, Swimming Basics). |

---

## Same prompts as the UI dropdown (after Load → Send)

| Label in dropdown | What to watch for |
| --- | --- |
| **Happy Path** | Resolves Mia + Soccer Stars; asks to confirm; after **yes**, success (new or updated registration in line with your DB copy). |
| **Ambiguous Name** | “Emma” matches two kids; assistant asks which child (by full name), does not guess an id in chat. |
| **Camp Full** | Art Adventure is full; assistant should offer a **waitlist** and confirm before saving. After confirm, registration status is **waitlisted** (does not use a seat until promoted). |
| **Waitlist promotion** | Loads the first line of a two-step flow (see **H** below). You add a confirmed Science Explorers seat in your DB copy first, or use the scripted E2E seed pattern. |
| **Age Restriction** | Ethan is too old for Swimming Basics; clear age message, no silent success. |
| **Schedule Conflict** | Emma already has Soccer that week; Science Explorers overlaps time; conflict explained, no bad write. |
| **Cancelled Camp** | Drama Club is cancelled; assistant explains camp not open for signup. |
| **Sibling Registration** | Assistant clarifies both children or handles in steps; may need follow-up turns. |
| **Multi-Turn: Change Mind** | You add kid/camp across messages; if a confirm is pending, **Cancel** or change request clears or updates sensibly. |

---

## Extra flows (type yourself)

### A. Register with confirmation

1. `Register Mia Chen for Soccer Stars` (if she is not already registered for that camp in your session).
2. Wait for summary + confirm prompt.
3. Click **Confirm** or type `yes`.
4. Expect a success-style message; optional: check `mock_db.json` if you are using the default file in place (not a temp copy).

### B. Reject a pending write

1. Trigger any successful **propose** (e.g. Happy Path until confirm appears).
2. Click **Cancel** or type `no`.
3. Expect no write; assistant acknowledges cancellation.

### C. Duplicate registration

1. `Register Liam Chen for Swimming Basics`  
   Liam already has that camp in the seed data.
2. Expect duplicate / already registered message **before** you should need to confirm (or no pointless confirm for an impossible write).

### D. Cancel a registration (if the model proposes it)

1. `Cancel Liam Chen's registration for swimming` or similar.
2. If the assistant proposes cancel, **confirm** when asked.
3. Expect cancelled status in the story the assistant tells; DB should show cancelled if you use the real file.

### E. Update status (if the model proposes it)

1. `Confirm Emma Thompson's pending registration for Coding Kids` or `Update registration to confirmed` after the assistant finds `reg-4` or the right row.
2. Confirm when prompted.
3. Expect status change explained clearly.

### F. Ambiguity follow-up

1. `Register Emma for Soccer Stars`.
2. When two Emmas appear, answer with `Emma Thompson` or the full name you want.
3. Assistant continues with tools and then confirm for register if appropriate.

### G. Off-topic or vague

1. `I want to register my kid` only.
2. Assistant should ask which child and/or which camp, not invent names.

### H. Waitlist promotion after a seat opens (multi-turn)

The default `mock_db.json` has **Sophia Lee** (`kid-7`) **waitlisted** on **Science Explorers** (`reg-6`). There is no extra confirmed seat on that camp in the seed file, so for a realistic promotion test you add one confirmed registration on `camp-6` (and bump that camp’s `enrolled` by one), then reload or use a copy of the DB the app reads.

1. Add a row such as **Emma Wilson** (`kid-3`) **confirmed** on Science Explorers (`camp-6`), and set that camp’s `enrolled` to match (seed has `reg-6` waitlisted only; adjust counts consistently).
2. `Cancel Emma Wilson's Science Explorers registration` — confirm when asked.
3. `Promote the next person on the waitlist for Science Explorers` (or ask who is next, then confirm **waitlisted → confirmed** for `reg-6`).
4. Expect **`get_waitlist`** (or equivalent facts) and a **propose update** to confirmed; after **yes**, Sophia’s registration is **confirmed** and enrollment reflects a filled seat.

Automated coverage: `tests/e2e/test_agent_e2e.py::test_e2e_waitlist_promote_after_cancel` seeds `reg-7` and walks cancel → `get_waitlist` → promote.

---

## Seed data cheat sheet (from `mock_db.json`)

- **Kids (examples):** Emma Thompson `kid-1`, Liam Chen `kid-2`, Emma Wilson `kid-3`, Ethan Davis `kid-6` (age 14), Sophia Lee `kid-7`, Mia Chen `kid-10`.
- **Camps (examples):** Soccer Stars `camp-1`, Art Adventure `camp-2` (often full), Swimming Basics `camp-4`, Drama Club `camp-5` (cancelled), Science Explorers `camp-6`.

Use this when you want to craft your own messages or check whether the assistant’s facts match the file.

---

## If something looks wrong

- Empty or error about API key: check `.env` and restart the app.
- Stuck after confirm: try **Reset** and repeat.
- For repeatable tool-level checks without the UI, run `uv run pytest tests/ -q`.
