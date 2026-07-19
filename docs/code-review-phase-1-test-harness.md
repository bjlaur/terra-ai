# Phase 1 Result: Deterministic Test Harness

## Outcome

Phase 1 is complete and stops at its review gate. The default test suite is
deterministic and offline, real-service scenarios share the same plugin-routed
test bodies, and Ergo remains a separate always-real system boundary.

The Textual developer console, UI tests, screenshot tests, and Textual-only
dependency were deleted with explicit user permission. The useful part was
retained as small test-only SOPEL support with no hidden application,
database, provider, environment-loading, logging, thread, or UI state. The
removed console remains recoverable from repository history.

## Harness Changes

- `conftest.py` owns one `TerraAI` instance, one SQLite connection, plugin
  global state, and teardown for each applicable test.
- Fast plugin E2E tests replace only external HTTP using `httpx.MockTransport`.
  They execute the production OpenRouter request builder, tool-call loop,
  executor, Open-Meteo clients, normalization, persistence, and plugin reply.
- The fast and real modes use 16 shared plugin E2E cases: addressed channel
  chat, unknown-prefixed chat, bare PM chat, current-information chat, weather
  with noisy progress, ordinary-channel silence, four opt-out entry routes,
  self-message suppression, registered-command precedence, tool-management
  state, history composition, context-free history exclusion, and disabled
  weather-tool filtering. Passthrough spies observe exact routing/provider
  boundaries without replacing the live implementation.
- Three additional full-stack E2E cases are deliberately fast-only because
  their preconditions must be deterministic: provider HTTP failure, a weather
  tool failure completing the real tool loop, and an oversized response using
  the real OpenRouter request/rewrite path. These script only external HTTP;
  they do not replace `provider.chat()`.
- Direct provider tests previously described as E2E were removed after their
  useful behavior was covered through `plugin.py`. Open-Meteo component tests
  now use deterministic HTTP instead of unmarked live traffic.
- Offline tests fail immediately on an attempted socket connection. They use
  deterministic model/config values and do not read `.env`.
- Ergo has explicit `--ergo` selection and no collection-time socket probe.
  Its SOPEL process, readiness, private key-bearing temporary config, sockets,
  files, and teardown have explicit owners.
- `test.sh` is the supported entrypoint: `fast`, `real`, `ergo`, `manual`, and
  `all`. Real modes source the repository `.env` without printing it. Fast
  mode never sources it.
- `manual` starts the same Ergo/SOPEL configuration used by the system suite
  for irssi testing and removes its private temporary configuration on exit.

## Removed Console Coverage Audit

Routing, privacy, opt-out, identity, history, error, concise-rewrite, tool
management, noisy progress, PM, weather, and external-process behavior remain
covered by plugin or Ergo tests. The deliberately removed assertions were UI
implementation details: Textual launch/exit, tabs, input history, completion,
widget rendering, and screenshot artifacts that did not validate rendered
chat content.

Deferred `-clear`, `-compact`, effort, prompt-management, and `setlocation`
persistence semantics were not promoted into stabilized feature contracts.

## Defects Exposed and Fixed

- The former console client constructed hidden databases/providers and parsed
  `.env`; removal eliminated the stalled workers and duplicate state.
- Local database fixtures leaked SQLite connections. They now close their
  owned connections, and the complete offline suite passes with warnings
  promoted to errors.
- The concise-rewrite Ergo xfail leaked its socket when the expected assertion
  failed. It now has unconditional finalization.
- The Ergo shell failure path initially used an out-of-scope local variable;
  cleanup ownership is now process-wide and verified.
- SOPEL temporary configs containing the development key use mode `0600` and
  are deleted during fixture/manual teardown.

## Validation

- `./test.sh fast -q -W error`: **131 passed, 22 skipped, 1 xfailed** in about
  15 seconds. This includes **19 full plugin E2E cases**; the 22 skips are the
  explicitly unselected Ergo system tests.
- `./test.sh real -q -W error`: **16 passed, 138 deselected** using real
  OpenRouter and Open-Meteo services through the same plugin E2E bodies.
  This is optional extended coverage; the deterministic fast gate remains the
  required everyday regression suite.
- `./test.sh ergo -q -W error`: **21 passed, 1 xfailed** using raw IRC, Ergo,
  a SOPEL subprocess, `plugin.py`, and real services. The script stopped the
  Ergo process it started.
- `./test.sh manual`: smoke-tested through SOPEL joining
  `#terra-ai-agent1`; Ctrl+C removed SOPEL, Ergo, PID state, and the private
  temporary configuration.
- `compileall`, shell syntax checks, and `git diff --check` pass.

At the Phase 1 gate, the remaining plugin strict-xfail was the agreed Phase 2
correlated error format/source-location contract; Phase 2 subsequently
implemented it. The separate Ergo xfail remains the live
model's non-deterministic willingness to produce an initially overlong reply;
the deterministic plugin test covers the rewrite branch.

Explicit web-search selection instead of Open-Meteo is deferred in the phased
plan. The current Ergo test with “web search” in its name does not prove which
tool ran and is not counted as that coverage.
