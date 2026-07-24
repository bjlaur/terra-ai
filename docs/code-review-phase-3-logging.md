# Phase 3: Logging and Observability

Phase 3 replaces TerraAI's borrowed SOPEL handler with owned, rotating,
correlated logging. It also consolidates the automated and manual SOPEL test
artifacts under one sortable run directory.

## Runtime logging

TerraAI now owns three reload-safe handlers while sharing SOPEL's stderr
stream:

- `terra-ai.log` receives DEBUG, INFO, WARNING, ERROR, and CRITICAL records.
  TRACE records are excluded.
- `openrouter-trace.jsonl` receives only OpenRouter TRACE records containing the
  complete request JSON and response body for every provider round.
- SOPEL stderr receives INFO, WARNING, ERROR, and CRITICAL TerraAI records.
  DEBUG and TRACE remain file-only even when SOPEL itself runs at DEBUG.

Both files rotate independently. Defaults are 10 MiB with five backups for
`terra-ai.log`, and 25 MiB with two backups for `openrouter-trace.jsonl`. The
default `log_dir = data/logs` is resolved relative to SOPEL's configuration
home by `FilenameAttribute`; an absolute path can be configured when desired.
Setup rejects empty paths or non-positive rotation settings before creating
files.

Setup removes only handlers owned by TerraAI before reinstalling them, which
prevents duplicated records after plugin reload. Shutdown records failures
with their traceback, closes application state, emits the unload lifecycle
record, and closes its handlers. Setup failures are likewise traced before
the partially installed logging state is removed.

## Correlation and error visibility

The Phase 2 event-scoped eight-character correlation ID is injected into every
TerraAI handler record. It therefore follows one inbound event through plugin
routing, context composition, provider rounds, tools, concise retries, error
handling, and the final response without adding IDs manually at each call
site. ERROR records outside an inbound event receive a standalone ID;
non-error lifecycle records outside an event use `--------`.

Every formatted record includes its logging source file and line. Translated
exception records additionally include the original traceback source, preserve
exception chaining, and include the complete traceback. Terminal IRC error
formatting and the dedicated recoverable-error path remain owned by the Phase
2 error boundary.

## Levels and payloads

INFO is now restricted to meaningful lifecycle events plus the model-visible
user prompt and final accepted AI response. Prompt and response text use
single-line JSON string escaping and carry the same event ID. Provider rounds,
routing decisions, tool timing, geocoding, HTTP timing, and concise retry
details moved to DEBUG. Exact OpenRouter wire payloads moved from DEBUG to the
TRACE-only logger.

Opted-out and self-authored messages are rejected before any content-bearing
routing record. The existing ordinary-channel privacy invariant remains: an
unaddressed channel message never reaches AI handling or a content-bearing
TerraAI log call.

## API-key safeguard

OpenRouter authorization headers are not supplied to logging. As a small final
safeguard, the formatter replaces the configured provider API key if it occurs
in rendered output, including an exception traceback. This intentionally is
not a general-purpose secret classifier or recursive redaction framework.
Trace records may contain private conversation and tool data by design.

## Test artifacts

`test.sh` now creates one UTC-sortable directory per invocation:

```text
/tmp/terraai-tests/YYYYMMDD-HHMMSS-FRACTION-MODE-PID/
```

Pytest output and progress, SOPEL stdout/stderr, SOPEL's own logs, and both
TerraAI logs live beneath that directory. Automated and manual SOPEL configs
explicitly point both logging systems there. Legacy ignored files under
`config/logs/` were removed with explicit user approval.

## Verification

- Focused logging, provider, plugin-contract, setup, shutdown, rotation,
  redaction, and correlation tests passed.
- Complete offline gate: **171 passed, 22 skipped**.
- Real-service gate: all **16 scenarios passed**. The runner environment ended
  after 14 successful scenarios with `fatal library error, lookup self`; the
  two not-yet-run nodes were selected directly and both passed. No test case
  failed in the unrestricted run.
- Ergo/SOPEL gate: **21 passed, 1 expected xfail** in 56.18 seconds. The xfail
  remains the live model's unreliable production of a response over 450 bytes;
  deterministic plugin E2E covers the actual rewrite and byte-safe fallback.
- Live Ergo artifact inspection found 111 DEBUG and 21 INFO operational
  records, no TRACE in `terra-ai.log`, 22 TRACE-only wire records, no TerraAI
  DEBUG/TRACE on stderr, nine correlated live prompt/response pairs, and no
  configured API key in operational, trace, or stderr output.
- The live bad-provider process produced one correlated ERROR record containing
  the complete chained traceback, and its TerraAI files contained no configured
  API key.

Phase 4 provider-neutral refactoring has not started.
