---
name: project-conventions
description: Rules and conventions for working in the terra-ai repo(s)
metadata:
  type: project
---

## Project conventions

- Agent name: OWL, git identity owl@terra-ai
- Two repos: shared origin `/home/agent/git/terra-ai` (GitHub), agent workspace `/home/agent/agentic-repos/terra-ai-agent1/`
- **Always work in agent1 workspace** when doing agent1 work. The shared repo is for merging/pushing only.
- Branches: main, release-0.0.1 (merged), release-0.0.2 (current base), agent1/carry-over-0.0.2 (agent1 work)
- Using "release" lightly — more like implementation waves
- Not ready to merge release-0.0.2 into master

**Why:** Confused agent2 sandbox (which works directly in /home/agent/git/terra-ai) with agent1 proper workspace. Agent1 always works in ~/agentic-repos/terra-ai-agent1/.

**How to apply:** When user says "work on terra-ai" or "run tests", default to ~/agentic-repos/terra-ai-agent1/. Use full git path only for fetch/push/merge operations.
