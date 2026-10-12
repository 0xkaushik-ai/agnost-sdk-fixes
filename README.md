# Agnost SDK: bugs found and fixed

I integrated [Agnost AI](https://agnost.ai) into a test agent the way a new customer would,
then read the published SDK source and tested each suspicion. I found **16 issues**
(2 high, 6 medium, 8 low) and fixed the Python SDK's worst ones.

**Result, on a flaky network (1 in 7 requests fails):**

| | `agnost` 0.1.13 | Fixed |
|---|---|---|
| Events delivered | 26 / 30 | **30 / 30** |
| Events out of order | 1–5 per run | **0** |
| Slowest `track()` call | 39–81 ms (blocks your app) | **< 10 ms** |
| Client timestamp sent | No | **Yes** |

Full report with all 16 issues: [`agnost_bug_report.pdf`](agnost_bug_report.pdf)

## Top problems and fixes

### 1. `flush()` reorders a conversation's events (High)
**Problem:** `flush()` sends queued events from the caller's thread while the background
worker is still sending. Two senders race, so turns reach the API out of order. The docs
recommend calling `flush()` before a script exits, so following the docs triggers it.
Seen live: a 3-turn conversation showed its *last* message first.

**Fix:** only the worker sends; `flush()` waits for the queue to drain.

### 2. Any network blip drops data (High)
**Problem:** every send error is caught, logged and dropped, with no retry. If session
creation fails, the conversation is still cached as created, so its events are orphaned.

**Fix:** retry network errors and 5xx with exponential backoff; cache a conversation
only after it is queued successfully.

### 3. `track()` blocks your request handler (Medium)
**Problem:** the first event of each conversation makes a synchronous HTTP call
(10 s timeout) in the caller's thread. I measured 312 ms, and 2.2 s on a cold connection.

**Fix:** session creation goes through the same background queue as events, which
also guarantees the session arrives before its events.

### 4. Timestamps are never sent (Medium)
**Problem:** `track(timestamp=...)` is accepted but dropped, so the server stamps events
on arrival. Late events get the wrong time and order, and backfills are impossible.

**Fix:** send an ISO-8601 UTC `timestamp` with every event.

### 5. TS SDK kills your app on Ctrl+C / SIGTERM (Medium)
**Problem:** `agnostai` installs SIGINT/SIGTERM handlers that call `process.exit(0)`. The
app's own cleanup never finishes, and the exit code hides the signal (0 instead of 143).

**Fix:** don't install signal handlers (or make it opt-in); flush on `beforeExit`.

### 6. Wrong org ID loses data silently (Medium)
**Problem:** the ingestion API returns `202` for a non-existent org ID and an empty body.
A typo in the ID means no data and no error.

**Fix:** validate the org ID and return `401`/`404`; return `400` for invalid bodies.

Also fixed: `debug=True` printed no debug logs, and properties were sent as Python
`str()` (e.g. `{'plan': 'pro'}`) instead of JSON.

## Reproduce

```bash
pip install requests
python benchmark/compare.py
```

This downloads `agnost` 0.1.13 from PyPI, then runs it and the fixed SDK five times each
against a local server with 20–80 ms latency and a 503 on every 7th request. It sends
nothing to Agnost.

The live tests in `live-tests/` need your own org ID:

```bash
pip install agnost
AGNOST_ORG_ID=<your-org-id> python live-tests/bug_tests.py
```

## Layout

```
agnost_bug_report.pdf   all 16 issues: severity, evidence, suggested fix
sdk/agnost/             agnost 0.1.13 (MIT) with the fixes applied
patch/                  the same fixes as one diff against 0.1.13
benchmark/compare.py    mock-API benchmark (table above)
live-tests/             scripts used against the real API with a free account
```

Each fix is its own commit on top of the unmodified 0.1.13 source, so
`git log -p sdk/` shows them one at a time.

## Notes

- Tested `agnost` 0.1.13 (PyPI) and `agnostai` 0.2.0 (npm), October 2026.
- Everything here comes from the public, MIT-licensed SDK packages and black-box tests
  against my own free workspace using synthetic data.
- The server side may already handle some of these; happy to be corrected.

Kaushik · [github.com/0xkaushik-ai](https://github.com/0xkaushik-ai)
