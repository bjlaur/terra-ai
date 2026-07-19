# Phase 2 Result: Correctness and Error Infrastructure

## Outcome

Phase 2 is complete and stops at its review gate. Active plugin failures now
have one event-scoped correlation context, terminal failures produce exactly
one compact and locatable IRC diagnostic, and unexpected recoverable failures
use a separate narrow “report, then continue” path. Provider, tool, weather,
history, SQLite concurrency, configuration, and shutdown behavior were
corrected without changing the database schema or resetting any SQLite file.

Phase 3 still owns final logging handlers, file routing, TRACE, redaction,
rotation, and level cleanup. This phase establishes the correlation and error
semantics that those handlers will consume.

## Error Infrastructure

- Each plugin event receives an eight-character correlation ID that is shared
  by all TerraAI handlers triggered from the same SOPEL pre-trigger.
- Terminal exceptions are logged once with their complete traceback and emit
  one IRC message containing the correlation ID, exception type/text, and the
  originating filename and line number.
- IRC error formatting is UTF-8-safe and always fits the 450-byte payload
  budget.
- `report_recoverable_error()` is the single distinct boundary for unexpected
  failures after which valid processing may continue. It logs the complete
  traceback, emits a separate IRC diagnostic when an event output exists, and
  does not pass through terminal handler reporting. Its visibility is not yet
  configurable; the narrow boundary intentionally leaves that for later.
- Expected recoverable service failures are logged with complete tracebacks
  but remain silent on IRC. Anticipated invalid input remains a validation
  result and does not manufacture an exception.
- Core AI orchestration no longer converts arbitrary exceptions into ordinary
  `Error:` response strings. The plugin is the final reporting owner.
- Duplicate prompt insertion now catches only SQLite integrity failures.
  Unrelated prompt-storage defects propagate to the plugin boundary instead
  of being mislabeled as duplicates.

## Provider, Tool, and Weather Correctness

- Every local tool outcome is serialized `ToolResult` JSON, including invalid
  JSON, non-object arguments, missing names, unknown tools, validation
  failures, expected service failures, and unexpected execution failures.
- Unexpected tool failures use the recoverable-error reporter, return a
  structured result to the model, and allow the real provider loop to produce
  a final answer only while state remains valid.
- OpenRouter validates the top-level response, choices, message, final text,
  tool-call collection, call IDs, function objects, names, and argument types
  with contextual exceptions instead of incidental indexing failures.
- Tool-round limits are checked before execution. Every executed tool result
  is consumed by a follow-up provider request; the model cannot request a tool
  on the final allowed boundary and leave its result unused.
- HTTP and invalid-JSON provider failures retain their original cause through
  exception chaining.
- Malformed optional OpenRouter usage metadata is reported as recoverable and
  cannot replace an otherwise valid answer.
- Weather validates object arguments, location type, registered presets,
  forecast days (1–16), and forecast hours (1–168). Unknown presets no longer
  silently use basic request variables while claiming a different preset.
- Open-Meteo transport, explicit API-error, malformed JSON/shape, geocoding,
  and empty forecast-data failures have contextual structured behavior.

## Persistence and Lifecycle

- `Database` owns a re-entrant lock around its one cross-thread SQLite
  connection. Reads are fetched under the lock and all production writes use
  the transaction owner.
- Nested operations participate in the outer transaction and mark it for
  rollback if an inner operation fails, even if an intermediate caller catches
  that failure.
- Opt-out state and history deletion are atomic.
- User/assistant history rows are written as one transaction and use one
  resolved session ID. A failed assistant insert rolls back the user row.
- Concise rewrites keep their retry conversation in provider context but do
  not persist rejected overlong drafts or correction instructions. Only the
  original user turn and final delivered answer are stored.
- If two model rewrite attempts still exceed the IRC limit, TerraAI applies a
  deterministic UTF-8-safe fallback before persistence and delivery.
- Noisy mode now uses the existing persisted user field instead of a
  contradictory process-local set, and its toggle is atomic.
- Nonessential performance-stat persistence failure uses the recoverable
  reporter and cannot discard an already completed answer.
- SOPEL setup registers and validates `TerraAISection`; configuration is
  validated before database creation. Shutdown closes the owned database
  exactly once.
- The obsolete `trigger_phrase` field was removed from the active SOPEL test
  example. No schema migration or SQLite reset occurred.

## Harness Corrections During Validation

- `test.sh` now writes ordinary output and independent per-test
  START/PASS/FAIL/SKIP progress under `/tmp/terraai-tests/`, so quiet live runs
  remain observable.
- Explicit Ergo test paths/node IDs now replace the default test file instead
  of being unioned with it.
- The unrelated network-updating SOPEL `safety` plugin was removed from the
  TerraAI Ergo harness after it blocked bot readiness during an unstable
  connection. It was not involved in any TerraAI contract scenario.

## Deferred Scope Preserved

Prompt-management representation and `setlocation` persistence, statistics
semantics, `.clear`/`.compact`, effort/reasoning design, provider selection,
container/package implementation, and the web-search-over-weather scenario
remain deferred. The standalone Gemini deletion remains approved for Phase 4
and was not started. The discarded `_KNOWN_NICK_COMMANDS` workaround and the
broader SOPEL/module-ownership audit remain Phase 5 work.

## Validation

- `./test.sh fast -q -W error`: **156 passed, 22 skipped** in 16.54 seconds.
  The skips are the explicitly unselected Ergo system tests.
- `./test.sh real -q -W error`: **16 passed, 161 deselected** in 64.86 seconds
  through `plugin.py` and real OpenRouter/Open-Meteo services.
- `./test.sh ergo -q -W error`: **21 passed, 1 xfailed** in 51.19 seconds
  through raw IRC, Ergo, SOPEL, `plugin.py`, and real services after removing
  the unrelated safety-plugin startup dependency.
- The remaining xfail is the agreed live-model concise-response case: a model
  that obeys the limit on its first answer cannot reliably be forced into the
  rewrite branch. Deterministic plugin E2E coverage executes that branch and
  the byte-safe final fallback.
- `compileall`, shell syntax checks, and `git diff --check` pass. No Ergo,
  SOPEL, or pytest process remained after validation.
