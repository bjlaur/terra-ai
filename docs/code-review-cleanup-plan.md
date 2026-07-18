# Full Code Review and Provider-Neutral Cleanup

## Summary

Deliver the cleanup as gated phases grouped into two broad passes:

1. Make tests deterministic and trustworthy, then fix confirmed correctness issues.
2. Once green, refactor architectural and general code smells.

OpenRouter remains the only configured production provider. The provider interface will remain suitable for future Gemini, OpenAI, Ollama, or local/in-process LLM implementations. Error details remain transparent in IRC because this is a private deployment.

## Key Changes

### Test foundation and routing

- Make every end-to-end test enter through `plugin.py` and SOPEL dispatch in both fast and `--real` modes.
- Fast E2E tests exercise the real plugin, `TerraAI`, provider tool loop, executor, and response routing while mocking only external HTTP transports.
- `--real` runs equivalent plugin-routed scenarios against actual OpenRouter and Open-Meteo services.
- Fast and real variants share one scenario/test body. A fixture or mode parameter selects scripted versus actual external transports; do not maintain parallel `_mock` and `_real` copies of the same routing assertion. Keep any unavoidable live-output assertion differences in small mode-aware assertion helpers.
- Keep direct internal calls only in clearly named unit/component tests; never recreate production routing or tool-loop behavior inside tests.
- Make default `pytest` fully offline and centralize real-test marker/credential handling.
- Inject fixtures into `TerraAITestClient`; stop each test client from creating a hidden database/provider and parsing `.env`.
- Profile and remove console/screenshot stalls, duplicated setup, leaked resources, and unnecessary global mutation.

### Provider-neutral core

- Define a shared provider contract with public `name`, `model`, configuration/readiness state, `chat(...)`, and explicit capabilities required by the active feature set, currently local tools and native search. Reasoning/effort controls are deferred.
- Keep transport, authentication, API keys, wire formats, and network assumptions inside providers so a local LLM can implement the same interface.
- Remove core access to OpenRouter private fields and move OpenRouter construction outside core message handling.
- Pass provider-neutral local tools from `TerraAI`; let OpenRouter add its native web-search tool exactly once.
- Generate capability-aware prompts so unavailable tools or search are not advertised.
- Do not repair the unused standalone Gemini adapter. Its deletion during the provider-cleanup phase is explicitly approved; keep the provider interface intact. This approval covers the adapter, its dedicated tests, dependencies, configuration, and active documentation claims, but does not cover OpenRouter's ability to route to Gemini-hosted models. Align any retained experimental adapters cheaply by adding only the public properties/capability declarations required by active features and rejecting unsupported active options explicitly, without implementing tool calling, search, effort/reasoning controls, provider selection, or feature parity.
- Keep runtime selection OpenRouter-only; provider configuration and feature parity remain follow-up work.

### Correctness, errors, and general cleanup

- Categorize configuration, authentication, rate-limit, timeout, transport, malformed-response, tool, and capability errors so each layer handles only failures it owns.
- Preserve transparent IRC error replies using the underlying exception text, such as `Error: <details>`. Continue logging full tracebacks for operator diagnosis.
- Do not add sanitization or generic replacement messages in this pass; avoid only accidental inclusion of secrets that are not normally part of an exception.
- Make every model-facing tool outcome structured JSON, including invalid arguments, unknown tools, location failures, and service failures.
- Validate weather presets and day/hour ranges; handle geocoding and forecast transport failures consistently.
- Make ordinary conversation exchanges and concise-rewrite history transactional. Defer `.clear` and `.compact` semantics rather than defining unfinished features during cleanup.
- Close database and HTTP resources during fixture teardown and plugin shutdown.
- Use the persisted user store for noisy mode instead of a contradictory in-memory set.
- Fix malformed/empty provider responses. Defer prompt-management and statistics behavior rather than repairing those unfinished features piecemeal.
- Make concise retries accumulate correctly and apply a deterministic UTF-8-safe final limit when the model still exceeds IRC constraints.
- Consolidate duplicated plugin response/noisy-callback routing and replace hardcoded command lists with SOPEL registration where possible.
- Remove the discarded `_KNOWN_NICK_COMMANDS` suppression path and the README claim that management commands have addressed/nickname aliases. Management commands exist only through SOPEL's configured command prefix.
- Remove duplicate imports/logging, stale comments, misleading names, unused locals, unnecessary broad catches, and similar low-risk junk across production and console code.
- Retain the provider interface and unregistered Open-Meteo schemas. Remove the standalone Gemini adapter during the provider phase under the recorded approval, without removing OpenRouter model compatibility. Clearly document the status of retained experimental adapters and future schemas.

## Confirmed Review Findings

These issues are observed in the current code and must be assigned to an implementation phase or explicit deferral.

- The core offline subset passes, but the mocked console suite fails without an API key because every `TerraAITestClient` constructs a second real `TerraAI` before tests overwrite its `.terra` attribute.
- Weather tests described as unit/component tests use real HTTP by default, while their end-to-end classes bypass `plugin.py` by constructing providers and tool schemas directly.
- Pytest documentation, markers, and behavior disagree: some real tests are unmarked, import-time credential checks are brittle, and documented `--real` behavior is not consistently enforced.
- `TerraAI.handle_ai_message()` and `OpenRouterProvider.chat()` are oversized orchestration functions mixing provider calls, private-field access, persistence, retries, tools, logging, and error policy.
- OpenRouter native web search is present in the global tools list and independently added by the provider, allowing duplicate provider-native tool configuration.
- The OpenRouter loop can execute a tool on its final allowed iteration without making the follow-up request that could consume that result.
- Tool execution uses structured JSON for ordinary results but plain strings for invalid JSON, unknown tools, and unexpected failures. Non-object arguments can reach handlers that assume `.get()` exists.
- Provider response parsing assumes the complete success shape and turns malformed responses into incidental indexing errors without useful context.
- `AIProvider.chat()` lacks OpenRouter's callback argument, core code reads `_model`, and retained adapters silently ignore unsupported tools/options. The standalone Gemini adapter also drops system messages; it should not be repaired, and its later deletion is explicitly approved. Effort/reasoning behavior is unfinished and explicitly deferred rather than normalized in this cleanup.
- `Database.transaction()` and `DB_VERSION` are unused. Stores commit independently, multi-row operations are not atomic, and one `check_same_thread=False` connection is shared without explicit cross-thread serialization.
- Session creation is duplicated. Compact/clear do not establish a session when none exists, but those command semantics are deferred. Performance records store the literal session ID `active`, but stats/telemetry semantics are also deferred.
- `.clear` claims to wipe conversation history but only rotates the session identifier, while `.compact` also behaves as session rotation rather than actual compaction. Their intended behavior is unfinished and explicitly deferred rather than defined by this cleanup.
- Noisy state has persisted database methods and a contradictory in-memory set; runtime commands use only the in-memory state.
- Prompt removal inspects the post-removal list, but prompt management is deferred. Several fixtures unlink SQLite files without first closing connections. Statistics format nullable token averages as numbers, but stats behavior is likewise deferred.
- Prompt insertion catches every exception and returns `False`, causing callers to label unrelated database failures as duplicate triggers; a second broad catch in management code is therefore ineffective.
- `setlocation` intentionally remains AI-driven, but opted-out users can invoke it and reach the provider. Its persistence redesign belongs to deferred prompt management.
- Prompt storage still carries the obsolete `trigger`/`response` representation even though prompts are intended as persistent admin/user system context. This redesign is explicitly deferred.
- `_KNOWN_NICK_COMMANDS` is a discarded workaround with no owning nickname-command handlers. It silently drops some explicitly addressed prompts based on their first word and inconsistently lets others reach AI; remove it rather than implementing a second command syntax.
- Channel/PM detection sometimes relies on a leading `#` rather than SOPEL trigger semantics, which is incorrect for other IRC channel prefixes and weakens fail-closed routing.
- The typed `TerraAISection` is not registered by plugin lifecycle code, so its defaults and validation are bypassed while runtime accesses a raw section. Active examples also contain removed fields. Configuration needs a real SOPEL-level test instead of only `SimpleNamespace` substitutes.
- Logging setup borrows root handlers, INFO contains branch-by-branch diagnostics, trace captures only request bodies, and reload/teardown ownership is unclear.
- Performance-stat persistence occurs on the critical response path, so a telemetry write failure can replace an already successful AI answer with an error. Nonessential diagnostics must not invalidate completed user work.
- Unknown-prefixed channel routing and PM catch-all handlers perform synchronous provider work under `thread(False)`, which can block SOPEL's dispatcher; routing order and execution concurrency need characterization before changing decorators.
- Provider registry fallback is advertised but runtime construction prevents meaningful fallback configuration, and selection only checks preflight availability rather than recovering from a failed chat call. This remains outside current feature scope but must not be advertised as functional.
- Confirmed cleanup debris includes unused imports/constants, duplicate comments and log calls, misleading future-tool package docs, redundant provider tests, and responsibility-heavy functions/modules.
- `CommandStats` is tested but unused in runtime, while `PerformanceStats` is bypassed by raw SQL in `TerraAI`. Whether these features, schemas, and abstractions should be wired, redesigned, or removed is explicitly deferred.

## Interface Changes

- `AIProvider` gains public model/capability/configuration access and one callback-aware chat signature.
- `TerraAI` consumes an injected provider or registry instead of constructing or inspecting OpenRouter directly.
- Provider-native tools are separated from the local tool registry.
- Test clients accept injected application state instead of constructing duplicate instances.
- Tool execution always returns one serialized result shape.
- Existing OpenRouter configuration remains backward compatible; no provider-selection setting is added.

## TerraAI Behavioral Contract

These rules are the source of truth for review and refactoring decisions. If existing code or tests disagree with them, fix the code or test rather than introducing another routing path.

1. **`plugin.py` owns ingress and IRC routing.** Channel messages, PMs, commands, addressed messages, and unknown-prefixed prompts enter through SOPEL-decorated handlers. Test and console entry points dispatch through those handlers rather than reproducing their decisions.
2. **Ordinary channel traffic is ignored as a privacy invariant.** TerraAI responds in a channel only when addressed by nick, invoked through a registered command, or given an unknown prefixed prompt that is intentionally routed to AI. Routing must fail closed: ambiguous matches, malformed triggers, unrelated messages, and internal routing errors must never forward ordinary channel text to a provider. No ordinary channel text may enter AI context, history, provider payloads, tool calls, prompt/response logs, or trace logs. Fast and real plugin-level regression tests must prove both silence and absence of downstream processing.
3. **PMs are conversational by default.** Bare PM text routes to AI. Registered PM commands execute once as commands; unknown prefixed PM text routes to AI once without the prefix.
4. **Management commands remain deterministic and prefix-only.** Active management commands such as opt-in/out, noisy mode, tool controls, and help are handled locally only when invoked through SOPEL's configured command prefix; they must not also reach the model or produce duplicate replies. Prompt management, history management, effort, and statistics are deferred features: if their current commands remain during stabilization, the same prefix-only and no-duplicate-routing rule applies, but their current behavior is not thereby accepted as a supported contract. There are no addressed/nickname aliases for management commands. `setlocation` is the explicit prefixed hybrid command: perform its current persistence action, then make one AI call for its conversational response.
5. **Opt-out and self-message guards apply consistently.** Opted-out users receive no AI responses except that they can still opt back in. TerraAI never responds to its own nick.
6. **User identity is added exactly once.** `TerraAI` prefixes model-visible user turns with `<nick>` at one chokepoint. Plugin handlers, tests, and the console pass bare user text and never synthesize a second identity prefix.
7. **History matches what the model saw.** Persist model-visible user text and final assistant responses in order, isolate histories by server/channel/session, and perform exchange/session mutations atomically. Context-free commands do not read or write conversational history.
8. **Provider-neutral core, provider-specific adapters.** Core logic deals only in shared messages, local tools, capabilities, and responses. Authentication, transport, wire formats, native search, and local-vs-remote execution stay inside provider implementations. Any future reasoning controls also belong behind this boundary, but are not part of the current cleanup contract.
9. **Capabilities are explicit.** A provider must declare whether it supports active optional features such as local function tools and native search. TerraAI advertises and sends only supported features; providers never silently ignore requested active capabilities. Effort/reasoning capability design is deferred.
10. **OpenRouter owns OpenRouter-native search.** Provider-side web search is added once inside the OpenRouter adapter. Local weather tools remain provider-neutral function tools and are never duplicated in provider-native configuration.
11. **Tools return one structured contract.** Every local tool execution returns serialized `ToolResult` data for success, validation errors, unknown tools, missing locations, and service failures. Tests exercise the real executor rather than recreating tool behavior.
12. **Error handling follows one explicit decision table.** An error is caught at the nearest boundary that can genuinely recover or add useful context; translated exceptions preserve their original cause.

    - Every exception is logged with a full stack trace, including expected and recovered exceptions.
    - An expected, recoverable exception is handled and logged but produces no direct IRC error message. A tool may return its normal structured failure to the model so the model can recover or ask the user for information.
    - An unexpected but recoverable exception is handled, logged with its full stack trace, and emitted to IRC as a separate `Error:` message. Normal processing may continue only when state is known to remain valid.
    - An unrecoverable exception is logged with its full stack trace and always emits exactly one `Error:` message to IRC. Processing for that event then stops.
    - IRC error messages include the correlation ID, exception type/text, and originating source location in a compact form such as `Error [a1b2c3d4 bot.py:225]: ValueError: details`. They are UTF-8-safe and obey the 450-byte response limit. Full tracebacks remain in logs rather than being truncated into IRC.
    - Each exception has one reporting owner. Lower layers either handle it completely or re-raise it with chaining; they do not emit an IRC error and then allow an outer layer to emit the same error again.
    - Recovery is atomic: validate before side effects, roll back partial database state, close resources, and never continue with invalid or partially written data.
    - Broad catches must not disguise programming defects as ordinary operational failures. The plugin boundary is the final safeguard for otherwise unhandled exceptions.
    - Invalid user/model input that is anticipated by the interface is a validation outcome, not an exceptional crash. Return the documented usage message or structured tool failure without manufacturing a traceback.

13. **Errors are transparent for this private deployment.** IRC error messages retain useful underlying details instead of vague generic replacements. Error reporting must still avoid accidentally printing configured secrets.
14. **IRC output remains deliverable.** Final replies respect the configured UTF-8 byte budget. Concise rewrites are bounded, retain the relevant conversation, and have a deterministic final fallback.
15. **Fast and real E2E tests are the same scenarios on the same path.** Both enter through `plugin.py` and use one shared test body per behavior. A fixture or mode parameter selects deterministic external HTTP transports for fast mode or actual configured services for `--real`; do not duplicate tests by appending `_mock` and `_real`. Small mode-specific output validators are allowed when live model wording cannot be deterministic. Default tests never use DNS or the network.
16. **There is one implementation of each decision.** Tests, console helpers, providers, and command wrappers may adapt inputs or capture outputs, but must not duplicate routing, history, capability, tool-loop, or command semantics.
17. **Logging is correlated, levelled, and intentionally routed.** Assign one unique correlation ID when an inbound IRC event begins and propagate it through plugin routing, `TerraAI`, provider calls, tool calls, retries, errors, and the final response.

    - INFO is concise operational output sent through SOPEL's stderr handler. For each AI exchange it records the model-visible prompt sent and the final AI response, with the same correlation ID. Plugin startup/shutdown and genuinely important lifecycle events may also remain INFO.
    - DEBUG contains routing decisions, capability selection, tool choice and duration, provider rounds, HTTP timing, geocoding decisions, retry decisions, and other diagnostic metadata. Existing branch-by-branch INFO messages move to DEBUG unless an operator normally needs them.
    - TRACE is a custom level below DEBUG used for complete provider wire payloads. OpenRouter request and response JSON are recorded at TRACE with correlation IDs, never at INFO or DEBUG.
    - DEBUG and all higher-severity TerraAI records go to a dedicated rotating `terraai.log`, making it the complete operational log: DEBUG, INFO, WARNING, ERROR, and full stack traces. OpenRouter TRACE records go to a separate rotating `openrouter-trace.log`; TRACE is filtered out of `terraai.log`.
    - INFO, WARNING, and ERROR remain visible through SOPEL stderr. DEBUG and TRACE are file-only during normal operation. Every logged exception includes `exc_info=True` so `terraai.log` contains the complete stack trace.
    - Log files have bounded rotation/retention and are safe under concurrent handler threads. Their paths and rotation defaults are explicit configuration, with practical defaults under `data/`.
    - Trace payloads may contain private conversation and tool data because this is a private diagnostic mode, but authorization headers, API keys, and configured secrets are never logged. Apply one central secret-redaction filter before any record reaches a handler.
    - Correlation context is established and cleared with event scope so concurrent IRC events cannot inherit or overwrite one another's IDs. Code outside an event receives a generated standalone ID when it logs an error.

## Deferred Prompt-Management Contract

Prompt management is a separate follow-up after the current feature set is stabilized. The obsolete trigger/response representation must not be mistaken for command-trigger or canned-response behavior and must not be used as the basis for cleanup decisions.

- **Admin system prompts** are persistent authoritative model instructions. Admin-only prompt commands manage them. They are not command triggers and do not produce canned replies; exact add/list/edit/remove behavior is deferred.
- **User system prompts** are persistent user-specific instructions or memories, keyed by server and user and injected with an explicit `<nick>` prefix so the model understands their provenance.
- `setlocation` remains AI-driven. Its eventual persistence belongs in the user-system-prompt/memory layer rather than the legacy server-wide `trigger`/`response` record.
- Conversation history remains chronological dialogue and must not double as durable prompt or memory storage.
- Admin and user system prompts may share one prompts table, distinguished by an explicit scope/type column and user ownership metadata where applicable. They remain semantically separate from conversation history. Exact columns, ordering, editing behavior, and migration details are deferred to that follow-up.
- The current `trigger`/`response` representation, `trigger -> response` context formatting, and add/remove/list command behavior are legacy implementation details to replace during that follow-up.
- Do not partially redesign prompt storage in unrelated phases. If legacy prompt code obstructs stabilization, first propose the exact commands, code, tests, documentation, or schema elements to remove and obtain explicit user permission before deleting them. A permitted removal should leave a concise reimplementation note rather than spending effort repairing behavior that has no accepted contract.

## Test Plan

- Unit tests for active provider capabilities, error propagation, structured tool results, weather validation, session lifecycle, noisy persistence, and UTF-8 limiting. Tests for deferred prompt, statistics, history-management, and effort behavior characterize retained code only; they are not requirements to repair unfinished implementations.
- Component tests with mock HTTP transports that run actual OpenRouter request construction and tool-loop code.
- Fast plugin E2E tests for channel messages, PMs, management commands, opt-in/out, noisy notices, weather calls, web-search availability, disabled tools, visible errors, history, and concise rewrites.
- `--real` plugin E2E tests for chat, current-information search, weather/geographic disambiguation, noisy progress, and external-service errors.
- Preserve Ergo/SOPEL process tests as the optional highest-level system E2E suite. Ergo always uses real APIs and never has a mocked mode; overlap with in-process tests is allowed when it proves the distinct IRC/server/process boundary.
- Run compilation checks, the complete offline suite with duration reporting, and then the credential-backed real suite. Offline tests must make no network calls and must eliminate the current multi-minute stalls.

## Assumptions

- Detailed exception text in IRC is intentional for this private deployment and may be sanitized later.
- OpenRouter is the only supported runtime provider for now.
- Provider neutrality preserves the option of future remote or local LLMs without claiming dormant providers are production-ready.
- Unregistered Open-Meteo schemas remain planned placeholders.
- Active README/configuration/test documentation is corrected; historical planning documents remain unchanged.
- Deferred code is not automatically entitled to preservation or repair. If removing it would simplify stabilization, present the exact proposed deletion and its reimplementation note for user approval first. Do not delete deferred commands, modules, tests, documentation, or schema merely because they are unfinished.
- SQLite compatibility is not mandatory, but it may be broken only after obtaining explicit user permission for the specific schema/reset change. Never delete, overwrite, migrate destructively, or instruct automatic recreation merely because a cleaner design is possible. Until permission is granted, preserve existing files and use compatible changes. Any approved reset must identify the exact files affected, document recovery/backup implications, and keep file deletion as a separate deliberate action.

## Deferred Effort/Reasoning Controls

The current effort feature is not part of the stabilized feature set. Do not spend cleanup time making its model mappings, command behavior, persistence, authorization, or provider parity work.

- A later design must decide whether effort is global, per-user, per-request, or admin-controlled; how it persists; and how unsupported providers/models report the limitation.
- Provider neutrality must leave room for a future reasoning control without requiring every remote or local provider to implement one.
- If current effort code complicates an active cleanup phase, propose the exact removal—including affected commands, state, mappings, tests, and documentation—and obtain explicit user permission before deleting it. Record what must be reconsidered when the feature is reimplemented.
