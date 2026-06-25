# Parallel Work Instructions

When multiple agents work on the same repo simultaneously, follow this workflow to avoid conflicts.

---

## Setup (Before Starting Work)

### 1. Check If You Need a Feature Branch

- **Ask the user** if you should create a feature branch or work directly on the current branch.
- If a feature branch is needed, create one with a name relevant to your work.

### 2. Confirm Your Agent Name

- **Do not start work if you aren't confident in your agent name.**
- Use a consistent, recognizable name for all your branches and commits.

### 3. Create Your Workspace

- **Each agent works in a cloned repo**, not directly in origin.
- Clone to `~/agentic-repos/terra-ai-{agent-name}/`.
- Each agent gets its own test channel when running integration tests (e.g., `agent1/#terra-ai`).
- Each agent has its own SQLite DB (separate `data/` directory) to avoid conflicts.
- WAL mode enabled for concurrent access within a single agent's work.

### Agent Names

- OWL = `agent1` (primary agent, works in `~/agentic-repos/terra-ai-agent1/`)

---

## Working

- **All changes go in `/home/agent/git/terra-ai`**.
- Run test harnesses before every commit:
  ```bash
  python -m py_compile terraai/<file>.py
  pytest tests/
  ```
- **READ ALL QUESTIONS/PROMPTS before acting** — not just the latest one.
- **NEVER use AskUserQuestion** — print questions as plain text.
- Sign your documentation changes with your agent name.

---

## Pushing / Merging

- **ALWAYS ask before pushing** to any remote.
- **ALWAYS ask before committing** — no silent commits.
- When asked to push:
  ```bash
  git push origin {your-branch-name}
  ```

---

## Database Notes

- Shared SQLite DB at `data/terraai.db` with WAL mode enabled.
- Every table has a `server` column for multi-server support.
- Use `(server, nick)` and `(server, channel)` lookups, not just `nick` or `channel`.
- Each agent uses its own test channel to avoid stepping on each other.
