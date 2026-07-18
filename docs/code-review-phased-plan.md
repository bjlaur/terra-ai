# TerraAI Code Review: Phased Execution Plan

This document sequences the work defined in [`code-review-cleanup-plan.md`](code-review-cleanup-plan.md). Its behavioral contract is authoritative throughout every phase.

Each phase is independently reviewed and must finish green before the next begins. Do not bundle later architectural work into an earlier stabilization phase.

## Implementation Checkpoint

This is the handoff state immediately before implementation begins:

- Production code has not yet been changed for this review. The most recent completed code change is commit `95e9821` (`Fix history limits and location disambiguation`).
- The next action is Phase 0 only. Stop for review at its gate before beginning Phase 1.
- The initial genuinely offline core subset passed with `76 passed, 4 deselected`. The mocked console subset exposed 22 failures because `TerraAITestClient` creates an unintended real `TerraAI` instance before tests replace it; this is a test-harness defect assigned to Phase 1, not a production regression baseline.
- The ignored local environment contains a development OpenRouter key. Its presence is acknowledged and the user plans to rotate it later; do not print, edit, delete, or move it during cleanup.
- The development key is explicitly authorized for credential-backed OpenRouter and Open-Meteo end-to-end tests when the applicable phase calls for them. Never print or commit it; default and fast suites remain offline, while real-service tests remain explicitly selected with `--real`.
- `setlocation` is intentionally AI-driven. Stabilization must enforce opt-out before its AI call, but its persistence belongs to the deferred prompt-management redesign.
- Prompt management, statistics/telemetry semantics, `-clear`/`-compact`, effort/reasoning controls, provider selection/fallback, container/package implementation, and future Open-Meteo tools are deferred.
- Deleting deferred code always requires a specific proposal and user permission. The only pre-approved deferred deletion is the standalone Gemini provider scope documented under Implementation Permissions.
- The two review documents are currently untracked and should be included in the first appropriate phase-scoped documentation commit unless the user directs otherwise.

## Phase 0: Baseline and Safety Rails

### Work

- Record the current test inventory, marker behavior, execution time, network use, and known failures without changing production behavior.
- Run the existing Ergo/Sopel suite when its local prerequisites are available, and review the harness itself rather than treating skipped collection as system coverage.
- Add focused characterization tests for the highest-risk existing behavior: ordinary channel silence, addressed messages, commands, PM routing, opt-out, identity prefixing, history, tool dispatch, visible errors, and response length.
- Prove ordinary channel messages never reach `TerraAI`, providers, tools, history, or any prompt/trace log.
- Establish correlation-ID and logging tests before changing logging implementation.
- Inventory broad exception handlers, raw SQL transaction boundaries, duplicated routing, provider-specific coupling, resource ownership, and stale documentation.
- Assign every item in the confirmed-findings register to a phase or explicit deferral so cleanup discoveries are not lost behind broad wording.

### Gate

- Characterization tests pass through `plugin.py`.
- Privacy failures are treated as blocking failures, not expected test drift.
- Baseline results and known external prerequisites are documented.
- The Ergo/Sopel suite has a recorded result or a concrete prerequisite blocker; an import-time skip alone is not accepted as execution.

Phase 0 implementation results are recorded in [`code-review-phase-0-baseline.md`](code-review-phase-0-baseline.md). Stop for user review at this gate.

## Phase 1: Deterministic Test Harness

Implementation note: removal of the Textual developer console, its UI and
screenshot tests, and its dedicated dependency was explicitly approved during
Phase 1. The fake SOPEL rule-manager support is retained as test-only code.
Deleted non-UI scenarios must be covered by plugin-routed tests or, where they
prove the external IRC/process boundary, by the always-real Ergo suite. The
console remains recoverable from repository history; no replacement UI is
planned.

### Work

- Remove the approved Textual console and retain only a minimal test-only fake SOPEL bot/client with no hidden `TerraAI`, provider, database, environment, or logging state.
- Centralize fixtures for temporary databases, plugin global state, fake SOPEL dispatch, provider transports, and Open-Meteo transports.
- Make all fast E2E tests traverse `plugin.py` while mocking only external service boundaries.
- Consolidate paired mock/real copies into one scenario body whose fixture selects scripted or live external transports. Keep shared routing and contract assertions in that body; isolate only unavoidable live-output validation differences in small helpers.
- Script OpenRouter HTTP responses so tests execute the real request builder, tool-call loop, executor, and final plugin response without reproducing that logic.
- Replace real Open-Meteo calls in the default suite with deterministic response fixtures.
- Normalize pytest markers: default runs are offline; `--real` enables credential-backed in-process service tests through the same plugin route; Ergo remains an explicitly selected system dependency and always uses real APIs.
- Give Ergo an explicit system-test selection path with no import-time socket probe or accidental default API use. Own Ergo/Sopel startup, readiness failure, temporary configs/logs, sockets, and teardown deterministically.
- Keep Ergo as a real-service-only system E2E suite. Never add a mocked Ergo mode or fold it into the in-process fast/real fixture. Similar scenarios may exist at both tiers because Ergo proves the distinct IRC/server/Sopel-process boundary; remove only duplication within Ergo that proves no additional behavior.
- Remove duplicate tests that assert the same behavior through less complete paths, while retaining narrow unit tests for pure logic.
- Diagnose and remove console/screenshot stalls and leaked workers/resources.

### Gate

- Default `pytest` performs no DNS or network access.
- Fast E2E coverage enters through `plugin.py` and verifies downstream calls rather than recreating decisions.
- Every behavior shared by fast and real E2E modes has one scenario/test body rather than parallel mock/real copies.
- Tests close databases, clients, workers, and plugin globals reliably.
- The complete offline suite passes with duration reporting and no multi-minute unexplained stalls.

## Phase 2: Correctness and Error Infrastructure

### Work

- Implement the error decision table from the behavioral contract, including event-scoped correlation context, full-stack logging, exactly-once IRC reporting, traceback-origin locations, and UTF-8-safe 450-byte error messages. Phase 3 takes ownership of final handler/file routing rather than recreating correlation.
- Distinguish validation outcomes from exceptions and make all model-facing tool failures structured `ToolResult` JSON.
- Fix OpenRouter tool-round termination so each executed result is consumed by a follow-up model request or the call is rejected before execution at the configured limit.
- Validate tool names and arguments as objects before dispatch, and validate provider response shapes with contextual errors rather than incidental indexing failures.
- Validate weather presets and day/hour bounds; unify geocoding and forecast failure behavior.
- Make ordinary exchange persistence and concise-rewrite history atomic and internally consistent. Do not redefine `.clear` or `.compact` in this phase.
- Serialize the shared SQLite connection across SOPEL handler threads and route multi-statement operations through one transaction owner instead of per-row commits.
- Fix noisy-mode persistence and malformed/empty provider responses. Do not redesign or repair prompt-management, `.clear`, `.compact`, or stats semantics in this phase.
- Keep nonessential telemetry failures from replacing a successful AI response; report/log them according to the recoverable-unexpected error rule while preserving the answer.
- Correct the concise-rewrite conversation and add a deterministic final byte-safe fallback.
- Add explicit database/plugin shutdown and fixture teardown.
- Enforce the opt-out guard before the intentional hybrid `setlocation` command can call AI. Do not redesign its persistence in this phase.
- Register and validate typed SOPEL configuration through the actual plugin lifecycle; remove obsolete active config fields without implementing the deferred container plan.
- Preserve SQLite compatibility unless a concrete improvement requires breaking it. If so, stop and request explicit permission describing the exact schema and files before proceeding.

### Gate

- Focused unit and plugin E2E tests cover every corrected failure mode.
- Injected failures prove rollback, exactly-once reporting, source-location references, and continued processing only for valid recoverable states.
- Existing SQLite files remain usable unless an explicitly approved reset has occurred.
- Full offline and focused real-service tests pass.

## Phase 3: Logging and Observability

### Work

- Route the Phase 2 correlation context through the final logging handlers and verify propagation across plugin routing, `TerraAI`, provider calls, tools, retries, errors, and final responses.
- Configure `terraai.log` as the rotating complete operational log at DEBUG and above.
- Keep INFO, WARNING, and ERROR on SOPEL stderr; move routine routing/provider detail from INFO to DEBUG.
- Add a custom TRACE level and a separate rotating `openrouter-trace.log` containing complete OpenRouter request and response JSON.
- Keep TRACE out of `terraai.log` and keep DEBUG/TRACE off normal SOPEL stderr.
- Add central recursive secret redaction, private file permissions, independent retention, and reload-safe handler setup/teardown.
- Log model-visible prompt and final response at INFO with matching correlation IDs and single-line escaped formatting.

### Gate

- Tests prove correct level routing, correlation propagation, redaction, source locations, private file setup, handler deduplication, and trace separation.
- Every exception path records a full traceback in `terraai.log`.
- OpenRouter headers/API keys never appear in either file.
- INFO stderr is limited to prompt/response and meaningful operational lifecycle records.

## Phase 4: Provider-Neutral Refactor

### Work

- Define the shared provider contract with public name/model/configuration state and explicit capabilities required by active features, currently local tools and native search. Defer effort/reasoning capability design.
- Inject a provider or registry into `TerraAI`; remove OpenRouter construction and private-field access from core logic.
- Separate local function tools from provider-native tools. OpenRouter adds its native web-search schema exactly once.
- Make context prompts capability-aware so unsupported features are not advertised.
- Remove the unused standalone Gemini adapter rather than repairing its dropped-system-message behavior. Explicit user permission for this deletion is recorded in the implementation notes below. Preserve the neutral interface so Gemini or another provider can be added cleanly later, and do not remove OpenRouter's ability to route to Gemini-hosted models.
- Align retained experimental adapters cheaply only where required by the active shared contract: implement public properties/capability declarations and reject unsupported active options explicitly. Do not implement selection, local tools, search, effort/reasoning controls, or feature parity.
- Ensure the contract makes no assumptions about API keys, HTTP, remote health checks, OpenAI wire formats, or network transport so a future local/in-process LLM fits naturally.

### Gate

- Core tests run against a provider-neutral fake without OpenRouter-specific attributes.
- OpenRouter plugin E2E behavior remains unchanged.
- Experimental providers satisfy contract tests and explicitly reject unsupported capabilities.
- No provider-selection or dormant-provider feature work has entered scope.

## Phase 5: Routing and General Cleanup

### Work

- Consolidate repeated plugin AI-response/noisy-callback handling without creating a second router.
- Remove blocking provider work from SOPEL's non-threaded dispatcher path without weakening command precedence, duplicate prevention, or ordinary-channel privacy.
- Audit the plugin against SOPEL's public lifecycle, configuration, rule and command precedence, trigger parsing, nickname addressing, permission checks, threading model, and output APIs. Remove home-grown equivalents or bypasses unless TerraAI has a documented domain-specific requirement that SOPEL does not provide.
- Audit module and layer ownership across plugin, core, commands, prompts/context, providers, tools, database, configuration, and test support. Flag behavior implemented in the wrong module, provider or SOPEL details leaking across boundaries, convenience imports that invert dependencies, and modules with mixed reasons to change. Move code only when it establishes a clearer owner or removes coupling; do not reshuffle files for cosmetic architecture.
- Remove `_KNOWN_NICK_COMMANDS`, its addressed-command suppression, and documentation/tests for nonexistent addressed management aliases. Keep management commands prefix-only.
- Preserve prefixed `setlocation` as the single documented hybrid command.
- Remove duplicated imports/logs, unused state, misleading names, stale comments, unnecessary broad catches, and redundant tests/helpers.
- Review every production module and retained test helper for validation, ownership, side effects, concurrency assumptions, SOPEL emulation, and dead or contradictory paths.
- Keep unregistered Open-Meteo schemas and retained experimental provider modules unless a specific removal is separately proposed and approved; clearly label their status in the meantime.
- Correct active README sections affected by implemented behavior, configuration examples, test commands, architecture descriptions, and logging documentation. Leave historical plans and the unimplemented container/package plan for a future iteration.

### Gate

- The behavioral contract has explicit plugin-level coverage.
- Ordinary channel privacy tests remain green after all routing cleanup.
- Compilation, complete offline tests, focused `--real` plugin tests, and optional Ergo tests pass as applicable.
- Final diff review finds no duplicated routing/tool-loop logic, accidental network use in fast tests, unapproved database reset, or unsupported feature claim.

## Execution Rules

- Stop after each phase for review; do not begin the next phase merely because tests pass.
- Keep commits phase-scoped so a phase can be reviewed or reverted independently.
- Fix a newly exposed correctness or privacy defect in the current phase before continuing.
- Do not weaken a behavioral-contract test to accommodate a refactor unless the contract itself is explicitly revised first.
- Deferred code has no automatic preservation or repair requirement. If it obstructs an active phase, propose deleting the exact commands, modules, tests, documentation, or schema elements and explain the reimplementation note that will replace them. Obtain explicit user permission before performing that deletion; do not treat this plan as blanket approval.
- After an approved deferred-code deletion, remove misleading active documentation and tests that claim the feature works, and retain a concise deferred-design note. Do not quietly replace the deleted feature with a partially redesigned one.
- Never delete or reset a SQLite file, introduce a destructive migration, or drop compatibility without fresh explicit permission for that exact action.

## Implementation Permissions

- **Standalone Gemini provider removal is approved.** During Phase 4, deletion may include `terra_ai/providers/gemini.py` plus Gemini-adapter-only tests, dependencies, configuration, exports/registration, and active documentation claims.
- This approval does not authorize deleting generic provider abstractions, historical planning records, or OpenRouter support for model identifiers hosted by Google/Gemini.
- This is authorization for the Phase 4 implementation, not an instruction to perform the deletion before that phase begins.

## Deferred Follow-Up: Prompt Management Redesign

Begin this only after the stabilization and cleanup phases above are green and reviewed.

- Replace the obsolete trigger/response representation with the prompt-management contract in `code-review-cleanup-plan.md`; do not implement command-trigger or canned-response behavior.
- Provide admin-only management of persistent authoritative system prompts.
- Support persistent user-system prompts/memories keyed by server and nick, with `<nick>` provenance added when composing model context. Admin and user prompts may share one table using an explicit scope/type discriminator and ownership columns.
- Move `setlocation` persistence into the user memory layer while preserving its AI-driven conversational behavior.
- Keep durable prompts/memories separate from chronological conversation history.
- Design the schema and command interface as its own reviewed plan. If implementation would break SQLite compatibility or require a reset, request explicit permission for that exact change before proceeding.

## Deferred Follow-Up: Container and Packaging

- Treat the current Containerfile and package inventory as an unimplemented plan, not a supported deployment surface.
- Reconcile obsolete YAML entry points, unused DuckDuckGo-era dependencies, machine-specific examples, package metadata, and versioning only when container/package implementation is intentionally resumed.
- Do not mix these changes into the current stabilization phases.

## Deferred Follow-Up: Statistics and Telemetry

- Audit whether command statistics and performance statistics are useful features before preserving their current schema or APIs.
- Decide whether to wire, redesign, or remove `CommandStats`, `PerformanceStats`, token fields, session attribution, and the `-stats` command as one coherent change.
- During stabilization, do not let a telemetry write failure replace an otherwise successful AI response, but otherwise avoid piecemeal stats fixes.
- If the eventual decision requires destructive schema changes or a database reset, request explicit permission for that exact change first.

## Deferred Follow-Up: History Management Commands

- Decide the intended user-visible and storage semantics of `-clear` and `-compact` before changing either command.
- Determine whether clear deletes rows, rotates sessions, or offers both behaviors, and whether compact summarizes, archives, trims, or merely rotates context.
- Align command messages, persistence, privacy expectations, and plugin-level tests only after that behavior is explicitly chosen.
- Do not let stabilization work accidentally bless the current session-rotation implementation as the feature contract.
- Request explicit permission before any eventual destructive migration or database-wide cleanup outside a user's deliberate command action.

## Deferred Follow-Up: Effort and Reasoning Controls

- Treat `-effort`, its stored state, model-specific reasoning mappings, authorization, and provider behavior as unfinished and outside stabilization scope.
- Later decide whether effort is global, per-user, per-request, or admin-controlled; how it persists; and what happens when a provider or model does not support it.
- Preserve the provider-neutral possibility of reasoning controls without adding it to the current provider contract or repairing dormant adapters for it.
- If effort code makes an active cleanup materially harder, propose the precise code, commands, tests, state, and documentation to delete and request explicit permission first. After approval, leave a concise reimplementation note rather than maintaining a misleading partial feature.

## Deferred Follow-Up: Explicit Web Search Instead of Weather Tool

- Define how a user explicitly requests provider-native web search instead of
  the local Open-Meteo weather tool for a weather question.
- Add one shared plugin-routed fast/real scenario that proves web search ran,
  no local weather tool ran, and the final reply was returned normally. Fast
  mode should script OpenRouter's server-tool usage metadata; real mode should
  observe actual provider usage rather than infer it from response wording.
- Extend the always-real Ergo suite only if the IRC/SOPEL boundary adds useful
  coverage, using noisy notices or correlated logs to distinguish
  `Searching web...` from `Fetching weather...`.
- The existing Ergo test named `test_bot_uses_web_search_for_weather` does not
  establish this behavior: it only checks for weather-related reply text and
  may pass after Open-Meteo use. Rename or replace it when this deferred item
  is implemented; do not treat it as web-search selection coverage now.
