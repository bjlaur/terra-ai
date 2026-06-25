# 0.0.2 — Deferred Testing (test tool)

Tests here have been deferred from the main [testing-agent2.md](testing-agent2.md).
Each item has a reason and a target release (TBD unless noted).

---

| #    | Test                                                       | Reason deferred                  | Target   |
| ---- | ---------------------------------------------------------- | -------------------------------- | -------- |
| 15   | `.addprompt wea sunny` → "Added wea."                      | Needs DB-based test (direct prompts-table check) | TBD |
| 17   | `.listprompts` → lists prompts                             | Low priority, harness passes     | TBD |
| 18   | `.rmprompt 1` → removes prompt                             | Needs DB-based test              | TBD |
| 19   | `.addprompt wea sunny` (dup) → error                       | Needs DB-based test              | TBD |
| 20   | `.rmprompt 999` → "No such prompt"                         | Needs DB-based test              | TBD |
| 21   | `.compact` → compacts history                              | Manual check only needed         | TBD |
| 24   | AI remembers previous message (history)                    | Manual check only needed         | TBD |
| 25   | AI forgets after `.compact`                                 | Manual check only needed         | TBD |
| 26   | Long message wraps correctly                               | Blocked by #27 (resize bug)      | TBD (after resize fix) |
| 28   | Empty input (just enter) → no crash                        | Manual check only needed         | TBD |
| 29   | Special characters `!@#$%^&*()`                            | Low priority                     | TBD |
| 30   | Unicode `héllo wörld 日本語`                                  | Low priority                     | TBD |
| 31   | `.stats` from non-admin nick                               | Needs admin-gate decision        | TBD |
| 32   | `.compact` from non-admin nick                             | **RESOLVED** — gated to admin   | 0.0.2 |

---

## Prompts table (deferred items `.addprompt` / `.rmprompt` / `.listprompts`)

These all touch the `prompts` table directly. Instead of testing via
`.send_message()` (which routes through the whole bot pipeline), write
pytest tests that:

1. Create a TerraAI instance with a temp DB
2. Call `.addprompt wea sunny` via `handle_management`
3. `SELECT * FROM prompts WHERE trigger = '.wea'` and verify the row
4. Call `.rmprompt 1` and verify the row is gone
5. Test edge cases: duplicate trigger, non-existent index

This lets the human developer verify by querying the DB after each step.
See [TODO.md](../../.agentic/TODO.md) item: "Write DB-based tests for .addprompt / .rmprompt".

---

## Admin gating decision (#31, #32)

- **`.compact`** — **RESOLVED** — gated to admin only (Round 4 #33)
- **`.stats`** — still needs decision (any user can currently run it)
