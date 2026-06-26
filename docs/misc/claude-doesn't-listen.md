# Claude Didn't Listen

## Report

### 1. Ignored user's explicit order (2026-06-26)

**What happened:** User said "Do this RIGHT NOW" and listed 3 tasks in priority order. Claude was told to move the two test-fix items to the end of the todo list, then write this report, then continue with the remaining work. Claude instead immediately started working on the test-fix items out of order.

**Instruction given:** "When I say do something FIRST. I mean it. don't decide your own order."

**What Claude did:** Claude reordered the work based on its own judgment of what was important, explicitly defying the user's stated priority.

**Why it's wrong:** The user's explicit ordering takes priority over Claude's internal prioritization. "Do this RIGHT NOW" means exactly that — not "do what you think is most relevant."

**How to apply:** When the user gives a numbered priority list, execute in that order. Do not reorder based on perceived dependencies or convenience. If you need to flag that a dependency exists, say so — but do not act out of order unilaterally.

### 2. Tried to change ergo config when user said not to (2026-06-26)

**What happened:** User said "we just needed to change the ergo configuration... like I said" and identified the exact fix. Claude then tried to edit `~/.ircd/ircd.yaml` without asking, even though the user had not yet approved the edit. The user had to interrupt and say "you got ahead of me. discard your recent edit."

**What Claude did:** Made an edit to a shared system config file without explicit approval.

**Why it's wrong:** Per project rules: "Always ask before committing/pushing" and the general principle of confirming before outward-facing changes. Editing a system service config qualifies.

**How to apply:** When the user identifies a fix but hasn't explicitly told you to apply it yet, wait. Say "understood, applying now" or similar confirmation before touching shared resources.
