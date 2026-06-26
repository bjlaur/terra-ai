# HTTPX Hang in Curses + PTY Subprocess: Analysis and Recommended Fix

**Date:** 2026-06-26  
**Status:** Workaround is valid; root cause still unresolved  
**Affected area:** TerraAI test tool interactive mode, especially `test_tool/chat.py` when AI/API calls are made from a curses TUI launched through a PTY-backed subprocess.

---

## Summary

The current workaround — running the AI call synchronously in the curses subprocess main thread — is reasonable for tests. It avoids the hang and lets the pytest flow complete.

However, the current root-cause theory should be softened. The issue is probably not simply “HTTPX uses AnyIO and AnyIO event-loop detection deadlocks.” That may be version-dependent and is likely not the best primary explanation.

The stronger conclusion is:

> The HTTPX sync request reaches the point where response headers have been received, but `client.post()` never returns to user code. The hang likely occurs while HTTPX is reading the response body, finalizing the response, closing/releasing the connection, or handling some interaction between response consumption and the PTY/curses/threaded subprocess environment.

The failure appears to require the combination of:

1. A subprocess launched through `pty.openpty()`.
2. A curses UI running in that subprocess.
3. The HTTP/API call running in a background daemon thread.
4. HTTPX doing the request from that thread.

If the API call is made synchronously in the subprocess main thread, it works. If HTTPX is run in a simple subprocess without curses/threading/PTTY complications, it also works.

---

## Key Observation

The HTTPX log shows something like:

```text
HTTP Request: POST https://openrouter.ai/api/v1/chat/completions "HTTP/1.1 200 OK"
```

This is an important clue, but it does **not** necessarily mean `client.post()` has fully returned.

For normal non-streaming HTTPX calls, `client.post()` still needs to fully read the response before returning the `Response` object to user code. So it is possible for HTTPX to log that it received the response status line/headers, but then hang before user code continues.

That means the hang is probably **after the request is sent and after response headers arrive**, but **before the response has been fully consumed and returned to the caller**.

Likely locations:

- reading the response body
- waiting for EOF / connection close
- decompression
- connection pool release
- socket state weirdness caused by PTY/curses/threading
- interaction with daemon-thread shutdown or inherited process state

---

## Correction to the Existing Root Cause Section

The current note says, in effect:

> HTTPX sync uses HTTPCore, which uses AnyIO for connection pooling and DNS resolution. AnyIO event-loop detection likely gets confused by PTY/curses state.

That should be changed.

A safer version:

> The exact root cause is unresolved. The hang appears to be caused by the interaction between PTY-backed stdio, curses terminal mode, and an HTTPX request running in a background thread inside the curses subprocess. The request reaches response headers, but `client.post()` never returns, suggesting the hang occurs while reading or finalizing the response rather than while connecting or sending the request.
>
> Avoid claiming that AnyIO event-loop detection is the root cause unless a traceback or dependency-level reproduction proves it. In current HTTPX/HTTPCore versions, the sync transport path primarily uses synchronous socket/SSL code, while AnyIO is more directly involved in the async backend path.

---

## Recommended Production Fix

Do **not** use a background thread inside the curses process for the AI/network call.

Instead, keep curses in the main process/thread and move the AI call into a separate spawned worker process. The curses UI can poll a queue for completion.

This avoids mixing:

- curses terminal state
- PTY-backed stdin/stdout
- background daemon threads
- HTTPX/network stack state
- test subprocess lifecycle issues

### Worker process sketch

```python
from multiprocessing import get_context
from queue import Empty


def _ai_worker(input_q, output_q, config):
    # Import inside the worker so the child process starts cleaner.
    from terra_ai import TerraAI

    ai = TerraAI(config)

    while True:
        job = input_q.get()
        if job is None:
            return

        job_id, text, is_pm = job
        try:
            result = ai.handle_ai_message(text, is_pm=is_pm)
            output_q.put((job_id, "ok", result))
        except BaseException as e:
            output_q.put((job_id, "err", repr(e)))


def start_ai_worker(config):
    ctx = get_context("spawn")  # Important: fresh interpreter, not forked curses state.
    input_q = ctx.Queue()
    output_q = ctx.Queue()

    proc = ctx.Process(
        target=_ai_worker,
        args=(input_q, output_q, config),
        daemon=True,
    )
    proc.start()
    return proc, input_q, output_q
```

### Curses loop sketch

```python
# Submit a job.
job_id += 1
input_q.put((job_id, text, is_pm))
pending_job = job_id
status = "AI thinking..."

# Poll each UI tick.
try:
    done_job_id, kind, payload = output_q.get_nowait()
except Empty:
    pass
else:
    if done_job_id == pending_job:
        if kind == "ok":
            show_response(payload)
        else:
            show_error(payload)
        pending_job = None
```

---

## Why Not `ThreadPoolExecutor`?

`ThreadPoolExecutor` may change timing, but it does not remove the core risk.

The known failure condition is already:

> HTTPX from a background thread inside a curses + PTY subprocess.

A thread pool is still a background thread inside that same process. It might appear to fix the issue by accident, but it does not isolate the network call from curses/PTY state.

A separate spawned worker process gives much cleaner isolation.

---

## Good Short-Term Workaround

For tests, the current workaround is acceptable:

```python
# BEFORE: hangs in curses + PTY subprocess
thread = threading.Thread(target=do_ai_call, args=(text, is_pm))
thread.daemon = True
thread.start()

# AFTER: works, but freezes UI briefly
do_ai_call(text, is_pm)
maybe_finish_call()
```

Trade-off:

- Good for tests.
- Bad for production interactive UX if calls take more than a moment.
- Still useful because it proves the API provider and credentials are not the underlying problem.

---

## Recommended Debug Instrumentation

Add `faulthandler` so that when the test hangs, Python dumps every thread stack. This is the fastest way to stop guessing.

```python
import faulthandler
import sys
import threading
import time

faulthandler.enable(file=sys.stderr)


def dump_later(seconds=10):
    def _dump():
        time.sleep(seconds)
        faulthandler.dump_traceback(file=sys.stderr, all_threads=True)

    threading.Thread(target=_dump, daemon=True).start()
```

Then wrap the HTTPX call:

```python
import httpx


def post_debug(url, payload, headers):
    dump_later(10)

    def on_request(request):
        print(
            "HTTPX hook: request prepared",
            request.method,
            request.url,
            file=sys.stderr,
        )

    def on_response(response):
        print(
            "HTTPX hook: response headers received",
            response.status_code,
            file=sys.stderr,
        )

    timeout = httpx.Timeout(
        30.0,
        connect=10.0,
        read=30.0,
        write=10.0,
        pool=10.0,
    )

    with httpx.Client(
        timeout=timeout,
        http2=False,
        trust_env=False,
        headers={"Connection": "close"},
        event_hooks={
            "request": [on_request],
            "response": [on_response],
        },
    ) as client:
        print("before post", file=sys.stderr)
        response = client.post(url, json=payload, headers=headers)
        print("after post before raise", file=sys.stderr)
        response.raise_for_status()
        print("after raise before json", file=sys.stderr)
        data = response.json()
        print("after json", file=sys.stderr)
        return data
```

Expected interpretation:

- If `on_response` prints but `after post before raise` does not, the hang is inside `client.post()` after response headers are received.
- If the thread dump shows HTTPX/HTTPCore stuck in response-body read, the body-read theory is confirmed.
- If the thread dump shows locks or condition variables, investigate connection pool release or cross-thread state.

---

## HTTPX Options Worth Testing

These may not solve the root cause, but they are cheap probes:

```python
httpx.Client(
    timeout=httpx.Timeout(30.0, connect=10.0, read=30.0, write=10.0, pool=10.0),
    http2=False,
    trust_env=False,
    headers={"Connection": "close"},
)
```

Why each helps:

- `http2=False`: removes HTTP/2 state as a variable.
- `trust_env=False`: avoids proxy/env/cert behavior from inherited test environment.
- `Connection: close`: avoids persistent connection reuse/pool weirdness.
- explicit `Timeout`: ensures all timeout phases are set, not just default total behavior.

If this fixes the hang, it narrows the issue. If it does not, the worker-process architecture is still the better fix.

---

## About Switching to `urllib.request`

Using `urllib.request` may be a good temporary workaround because it has fewer dependencies and less connection-pooling machinery.

But it should not be considered the best production fix unless the goal is simply to avoid HTTPX in the test tool.

Pros:

- simpler stack
- no HTTPX connection pool
- may avoid the hang completely

Cons:

- hides the actual interaction bug
- creates a separate code path from the production provider
- less useful for debugging the real provider behavior

If the goal is stable tests only, `urllib.request` is acceptable. If the goal is a clean interactive architecture, prefer a spawned AI worker process.

---

## Suggested Updated Root-Cause Text

Use this in the issue note:

```markdown
## Root Cause Analysis

The exact root cause is unresolved.

The failure requires the combination of:

1. A subprocess launched through `pty.openpty()`.
2. A curses TUI running in that subprocess.
3. The AI/API call running in a background daemon thread.
4. HTTPX performing the HTTP request from that thread.

The HTTPX log shows that response headers are received (`HTTP/1.1 200 OK`), but user code never continues past `client.post()`. This suggests the request is not hanging while connecting or sending. It is more likely hanging while HTTPX is reading the response body, finalizing the response, closing/releasing the connection, or interacting badly with the PTY/curses/threaded subprocess environment.

Avoid attributing this specifically to AnyIO event-loop detection unless a thread dump or lower-level reproduction proves that. The safer conclusion is that HTTPX sync calls from a background thread inside a curses + PTY subprocess are unsafe in this test harness.
```

---

## Suggested Updated Fix Section

```markdown
## Recommended Fix

For tests, the current synchronous workaround is acceptable:

- run `do_ai_call()` directly in the curses subprocess main thread
- accept that the UI freezes briefly
- write results to `data/interactive_result.txt` for test verification

For production-quality interactive mode, avoid background HTTPX calls inside the curses process. Instead, move AI/API calls to a separate spawned worker process and have the curses UI poll a queue for completion.

This keeps curses terminal state isolated from the network stack and avoids the known failure condition: HTTPX running in a background thread inside a PTY-backed curses subprocess.
```

---

## Final Recommendation

Keep the current synchronous workaround for the immediate test fix.

Then, if interactive mode needs to become production-quality, implement a spawned worker process for AI calls. That is cleaner and more robust than trying to make HTTPX behave inside a background thread in a curses + PTY subprocess.

Also add `faulthandler.dump_traceback(all_threads=True)` before changing much else. The next hang should produce a useful stack trace instead of another mystery timeout.
