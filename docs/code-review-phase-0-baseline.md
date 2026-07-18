# Phase 0 Baseline and Safety Rails

Date: 2026-07-18

Branch: `cleanup`

Starting commit: `a6f668d` (`Document phased code cleanup plan`)

This report records behavior before the test-harness and architectural work in later phases. Phase 0 changed one production path: it added the missing opt-out guard to `setlocation` because the new privacy test proved that an opted-out user could still persist data and call AI. The broader command and prompt-persistence design remains deferred.

## Test Inventory and Results

### Starting collection

- The repository initially contained 177 collected tests.
- Default marker selection chose 162 and deselected 15 `real` tests.
- There are 15 explicitly marked `real` tests, but only the 9 console cases enter through `plugin.py` and SOPEL dispatch.
- The other marked-real cases call `TerraAI` or providers directly, or only inspect rule metadata.
- `tests/test_weather.py` contains 18 unmarked tests. Thirteen perform live Open-Meteo or OpenRouter traffic, including two classes described as E2E that call the provider directly instead of entering through `plugin.py`.
- No current test uses the declared `slow` or `broken` markers. Ergo uses a module-level `skipif` and probes localhost during collection.

### Commands and observed results

| Scope | Result | Meaning |
| --- | --- | --- |
| `pytest --collect-only -q` before Phase 0 tests | 162 selected, 15 deselected | Default selection wrongly includes live weather traffic. |
| Default `pytest -q --durations=25` without credentials/network | 85 passed, 22 skipped, 15 deselected, 38 failed, 17 errors in 27.74s | The default suite is neither offline nor green. |
| Offline core excluding console UI and live weather modules | 80 passed, 22 skipped, 6 deselected in 12.76s | The genuinely offline existing core is stable. |
| New plugin contract suite | 15 passed, 1 xfailed in 4.37s | Routing/privacy characterization is green; the strict xfail is the clearly named pending Phase 2 correlation/source-location contract. |
| Existing real console subset with authorized dev key | 9 passed, 27 deselected in 25.67s | Current plugin-routed real OpenRouter paths work, but duplicate mock/real test bodies must be consolidated in Phase 1. |
| Full Ergo/Sopel system suite with authorized dev key | 21 passed, 1 xfailed in 46.72s | Actual IRC, Sopel subprocess, plugin routing, real OpenRouter/Open-Meteo, and bad-provider paths work. The xfail is the live-model auto-concise trigger described below. |
| Console plus screenshot suite with a key available | Stalled after 20 tests in two attempts; no pytest summary | Reproduces the console/TUI lifecycle stall assigned to Phase 1. Extending the timeout would only hide leaked work or teardown failure. |

The 55 failures/errors in the default run divide cleanly:

- 42 console/TUI failures or setup errors occur because each `TerraAITestClient()` constructs a hidden second `TerraAI` with an empty key before the test overwrites `client.terra`.
- 13 weather failures or setup errors occur because unmarked tests attempt real DNS/HTTP in the default suite.

The focused offline core and real console subset completed normally. The combined console/TUI regression reproducibly stopped making progress after 20 tests and remained alive beyond the expected completion window. Phase 1 must identify the exact test boundary and leaked worker/resource instead of increasing timeouts. The slowest offline test was the unbounded-history test at roughly one second. Completed real console timings ranged from roughly 1.7 seconds to 6.3 seconds per provider-backed case.

## Safety Characterization

`tests/test_plugin_contract.py` uses `plugin.dispatch_line`, SOPEL's rule manager, and the actual plugin handlers. It currently proves:

- ordinary channel traffic produces no IRC output and reaches no `TerraAI` handler, provider, context composition, history write, prompt seed, tool executor, or TerraAI log record containing the message;
- addressed channel prompts, unknown-prefixed channel prompts, bare PMs, and unknown-prefixed PMs route exactly once;
- registered management commands do not also route to AI;
- opt-out applies to addressed messages, unknown-prefixed messages, PMs, and the hybrid `setlocation` command;
- self-messages do not reach AI;
- user identity is added once and model-visible history matches the actual provider input;
- context-free `-ai` neither reads nor writes conversational history;
- an unhandled handler exception records a traceback and produces one IRC reply under the current behavior;
- an oversized response that succeeds on concise rewrite is not emitted before it fits.

Correlation/source-location behavior remains assigned to Phase 2. A clearly named strict-xfail contract test is retained now so the agreed error format and shared log/IRC correlation cannot be lost before implementation.

The pre-existing Ergo test `test_auto_concise_rewrite_fires` is separately marked xfail because it depends on a live model choosing to violate the 450-byte instruction. That is not evidence of a production defect: the model may correctly return a short first response, leaving no rewrite to observe. The new plugin suite deterministically forces an over-450-byte first response and proves that the rewrite branch fires, returns a short reply, and persists that final reply. Phase 1 should preserve this deterministic coverage through the scripted transport and stop treating live-model verbosity as a reliable test precondition.

The full Ergo run passed ordinary-channel silence, addressed and unknown-prefixed routing, PM routing, opt-in/out, noisy progress, real web search, real weather-tool execution, response identity, and the bad-provider error path. Reviewing the harness itself found additional Phase 1 work:

- Ergo tests are not marked as system/real tests. If Ergo happens to be listening during default pytest, the suite can start Sopel and call real services unexpectedly.
- `ERGO_AVAILABLE` performs a localhost socket probe at module import and freezes the skip decision during collection. Starting Ergo afterward cannot enable an already collected suite.
- `startergo.sh` reports readiness after backgrounding Ergo but does not reliably own a persistent server process in non-interactive execution environments.
- The auto-concise xfail can leave its IRC socket connected when an assertion exits early and contains a duplicate `_irc_quit(sock)` call.
- Readiness polling falls through after timeout instead of failing with the Sopel logs. Temporary process, config, socket, and log ownership also needs explicit cleanup and secret-safe permissions.
- Ergo is the highest-level system E2E suite and always uses real APIs; it has no mocked mode. Repeating critical scenarios from the in-process suite is intentional because Ergo proves the separate raw-IRC, server, Sopel-process, plugin, real-service, and IRC-reply boundaries. Remove only redundancy within the Ergo suite itself, not coverage merely because an in-process test exercises similar behavior.

## Network and Marker Baseline

- Default pytest must eventually block all network access and provide deterministic OpenRouter and Open-Meteo transports.
- `--real` does not itself override pytest.ini's default `-m "not slow and not real and not broken"`; callers currently also need an explicit marker expression. Existing documentation claiming that `pytest --real` runs everything is false.
- Fast and real E2E behavior must use the same scenario bodies. A fixture selects scripted or live transports; paired `_mock` and `_real` test copies are cleanup targets.
- Real-service access using the local development key is explicitly authorized. The key is never printed or committed.
- The existing direct-provider weather and web-search tests are not accepted as E2E coverage. Phase 1 replaces or narrows them after equivalent plugin-routed scenarios exist.

## Finding Ownership

Every confirmed review finding is assigned below. A later phase may discover more, but it must add them to this ownership model rather than silently expanding scope.

### Phase 1: Deterministic test harness

- Hidden `TerraAITestClient` construction, `.env` parsing, duplicate databases/providers, and resource leaks.
- Unmarked real weather traffic and direct-provider E2E tests.
- Marker/`--real` behavior and inaccurate test documentation.
- Duplicated mock/real scenarios and redundant lower-value provider tests.
- Console/screenshot setup overhead, global mutation, cleanup, and any reproduced stalls.
- A network-deny fixture that makes accidental default DNS/HTTP a test failure.
- Explicit Ergo/system selection with no import-time socket probe or accidental default API use, plus deterministic Ergo/Sopel startup, readiness failure, temporary-file ownership, socket cleanup, and teardown.
- Audit duplication within Ergo itself, but preserve its real-service system scenarios even when an in-process E2E test covers similar behavior. Never add a mocked Ergo mode.

### Phase 2: Correctness and error infrastructure

- Error taxonomy, full-stack logging ownership, exactly-once IRC reporting, correlation IDs, source locations, chaining, and UTF-8-safe error limits.
- Structured tool failures, object-argument validation, contextual provider-response validation, and weather validation/error consistency.
- OpenRouter tool-round termination and consistent tool-result consumption.
- Atomic exchange/concise-history writes, SQLite serialization, transaction ownership, and shutdown/fixture resource closure.
- Persisted noisy-mode ownership, malformed/empty responses, concise retry correctness, and deterministic final byte limiting.
- Typed SOPEL configuration registration and validation.
- Telemetry failures must not replace successful AI work; telemetry semantics remain deferred.
- The `setlocation` opt-out privacy defect was pulled forward and fixed in Phase 0 because privacy failures block the gate. Persistence remains deferred.

### Phase 3: Logging and observability

- Correlated level routing, INFO prompt/response lifecycle records, DEBUG diagnostics, and TRACE wire payloads.
- Dedicated rotating `terraai.log` and `openrouter-trace.log`, redaction, private permissions, concurrency, and reload-safe handler ownership.
- Replacement of borrowed root handlers and noisy INFO branch logging.

### Phase 4: Provider-neutral refactor

- Public provider identity/model/configuration/capabilities and one shared chat contract.
- Remove OpenRouter construction/private-field access from core and inject the provider boundary.
- Separate provider-neutral local tools from OpenRouter-native search and prevent duplicate search schemas.
- Remove the standalone Gemini adapter under the recorded permission; retain OpenRouter compatibility with Gemini-hosted model identifiers.
- Cheap explicit conformance for any retained experimental adapters, without provider selection, fallback, effort, or parity work.

### Phase 5: Routing and general cleanup

- Remove `_KNOWN_NICK_COMMANDS` and nonexistent addressed-management behavior.
- Replace leading-`#` channel inference with SOPEL trigger semantics.
- Characterize and remove synchronous provider work from non-threaded dispatcher paths without weakening routing precedence.
- Consolidate repeated response/noisy-callback routing and shrink responsibility-heavy functions/modules.
- Remove unused imports/constants, duplicate logs/comments, misleading names, broad catches without ownership, and other low-risk debris.
- Correct active README/configuration/test claims affected by implemented behavior. Historical plans and the unimplemented container plan remain deferred.

### Explicitly deferred

- Prompt-management schema and command redesign, including user-system memories and `setlocation` persistence.
- `-clear` and `-compact` semantics.
- Statistics/telemetry feature semantics and schema ownership, beyond isolating nonessential failures.
- Effort/reasoning controls.
- Provider selection/fallback and dormant-provider feature parity.
- Container/package implementation and historical planning cleanup.
- Future Open-Meteo schemas/tools.

Deferred code may be proposed for deletion when it obstructs active cleanup, but deletion still requires specific permission. The standalone Gemini provider is the only currently pre-approved deferred deletion.

## Phase 0 Gate

- Plugin-level privacy and routing characterization: **pass**.
- Ordinary-channel downstream/log silence: **pass**.
- Known privacy failure discovered in `setlocation`: **fixed and covered**.
- Baseline results and external prerequisites: **documented**.
- Full Ergo/Sopel system baseline: **21 passed, 1 expected live-model xfail**.
- Finding ownership: **complete**.
- Full default suite: **known red by Phase 1 harness defects; not treated as a Phase 0 product regression**.

Phase 0 is ready for review. Do not begin Phase 1 until the user approves this gate.
