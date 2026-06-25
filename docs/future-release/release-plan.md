# Next Release Plan — Post-0.0.1

## Context

0.0.1 is a minimal viable SOPEL plugin with one provider and basic commands. This plan covers features deferred from 0.0.1 and new capabilities for subsequent releases.

---

## Release Candidates (Prioritized)

### 1. Additional Providers + Fallback Chain
**Priority**: HIGH
**Effort**: Small

Add Gemini, OpenAI, and Ollama providers. Implement fallback chain in ProviderRegistry.

**Files**: `terraai/providers/gemini.py`, `terraai/providers/openai.py`, `terraai/providers/ollama.py`, `terraai/providers/registry.py`

---

### 2. Web Search
**Priority**: HIGH
**Effort**: Medium

Two-tier approach:
- Provider-native: Gemini grounding, OpenRouter plugins
- Fallback: DuckDuckGo API + web scrape

**Files**: `terraai/providers/base.py` (add search tool), new `terraai/tools/web_search.py`

---

### 3. Test Tool (Textual)
**Priority**: MEDIUM (right after 0.0.1)
**Effort**: Medium

irssi-like terminal UI using Textual for interactive testing. Single channel view, scrollable history, input line.

Inspiration: `/mnt/jbrowse/tools/svg_screenshot_poc.py` — uses `app.run_test()` + `pilot.press()` + `settle()` pattern. We can use a similar approach without SVG export — just verify bot responses.

**Test the test tool**: The test tool itself needs automated tests. Use Textual's `run_test()` + `pilot` to simulate user input and verify bot responses. **Screenshots + visual inspection** — export SVGs and look at them to verify the UI looks right. This is how jbrowse does it (`/mnt/jbrowse/tools/svg_screenshot_poc.py`).

**Files**: `test_tool/chat.py`, `tests/test_tool.py`

---

### 4. ergo Integration Testing
**Priority**: MEDIUM
**Effort**: Medium

Set up ergo IRC server for real-world integration testing. Each agent gets its own test channel.

**Files**: `tests/test_ergo_integration.py`, `config/terraai-test.yaml.example`

---

### 5. Context Compaction
**Priority**: MEDIUM
**Effort**: Medium

`.compact` command with AI-driven pruning, session_id rotation, revert support. Add `sessions` and `compactions` tables.

**Files**: `terraai/database.py`, `terraai/commands/admin.py`

---

### 6. User Experience Commands
**Priority**: MEDIUM
**Effort**: Small

- `.noisy` — toggle status notices
- `.setlocation` — hybrid: store prompt + forward to AI
- `.help` — show available commands

**Files**: `terraai/commands/user.py`

---

### 7. Performance Stats
**Priority**: LOW
**Effort**: Small

`performance_stats` table + `.stats` command. Track token counts, latency, response sizes.

**Files**: `terraai/database.py`, `terraai/commands/admin.py`

---

### 8. Multi-Server Support
**Priority**: LOW
**Effort**: Small

Add `server` column to all tables. Scope all queries by server.

**Files**: `terraai/database.py`, all managers

---

### 9. Rate Limiting
**Priority**: LOW
**Effort**: Small

Configurable per-nick sliding window. Default off.

**Files**: `terraai/bot.py`

---

### 10. Containerfile Polish
**Priority**: LOW
**Effort**: Small

Based on user's run script pattern. NOPASSWD yay build, then remove NOPASSWD.

**Files**: `Containerfile`

---

## Recommended Execution Order

1. Additional providers + fallback chain (unblocks real-world use)
2. Web search (critical for weather etc.)
3. Test tool (enables better testing)
4. ergo integration testing
5. Context compaction (needed for long-running bots)
6. UX commands (.noisy, .setlocation, .help)
7. Performance stats
8. Multi-server support
9. Rate limiting
10. Containerfile polish

## Done (moved to 0.0.1)

- SOPEL plugin entry point
- OpenRouter provider
- SQLite persistence (3 tables)
- Fake conversation injection
- Commands: .optin, .optout, .ai, .addprompt, .rmprompt, .listprompts
- pytest suite
