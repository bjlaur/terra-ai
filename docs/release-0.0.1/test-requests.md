# Manual Testing Results — 0.0.1

## Legend

- [x] = passed
- [ ] = not tested yet
- **FAIL** = broken, needs fix

## Column rules

- **Harness** — `[x]` if test harness can verify, `[ ]` if not
- **Manual** — `[x]` if verified manually, `[ ]` if not
- **Why no harness?** — brief explanation or `—`
- **Dev notes** — Leave BLANK for human developer
- **Agent notes** — agent writes fixes/results here

---

## Round 1 — Core Plugin

| # | Test | Harness | Manual | Why no harness? | Dev notes | Agent notes |
|---|------|---------|--------|-----------------|-----------|-------------|
| 1 | Bot loads without errors | [x] | [ ] | — | | |
| 2 | `.optin` responds correctly | [x] | [ ] | — | | |
| 3 | `.optout` blocks AI responses | [x] | [ ] | — | | |
| 4 | `.addprompt` creates prompt | [x] | [ ] | — | | |
| 5 | `.listprompts` shows prompts | [x] | [ ] | — | | |
| 6 | `.rmprompt` removes prompt | [x] | [ ] | — | | |
| 7 | Custom prompt match bypasses AI | [x] | [ ] | — | | |
| 8 | `.ai` sends without history | [x] | [ ] | — | | |
| 9 | `.help` shows commands | [x] | [ ] | — | | |
| 10 | `.effort` changes effort level | [x] | [ ] | — | | |
| 11 | Messages without trigger ignored | [x] | [ ] | — | | |
| 12 | Management commands never reach AI | [x] | [ ] | — | | |
| 13 | Provider fallback on failure | [ ] | [ ] | No fallback in 0.0.1 | | |
| 14 | `.setlocation` hybrid behavior | [x] | [ ] | — | | |

## Summary

**Passed (harness):** 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14

**Not tested (manual):** All

**Skipped:** 13 (no fallback in 0.0.1)
