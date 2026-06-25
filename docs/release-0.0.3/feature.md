# 0.0.3 Feature — Reliability + Testing

OWL — Created 2026-06-25

## What We're Building

0.0.3 is a reliability-focused release. It doesn't add new user-facing features so much as harden the ones we have: preventing unbounded growth, cleaning up edge cases in provider failures, and adding confidence via automated dogfooding.

## Scope

### In 0.0.3
- **Conversation TTL** — auto-prune history older than N days (configurable, default off)
- **Opt-in default config flag** — choose whether unseen nicks start opted-in or opted-out
- **Better provider error handling** — retries with backoff on transient failures, clearer error messages to users when a provider is down
- **Automated dogfooding** — e2e test sequences through the test tool that exercise realistic bot interactions and assert responses

### Architecture additions
- TTL enforcement in `terraai/database.py` (periodic cleanup + on-write pruning)
- Config field `default_optin` in `config/terraai.yaml.example` and `config.py`
- Provider retry logic in `terraai/providers/base.py` + `registry.py`
- New tests: `tests/test_dogfood.py`, `tests/test_ttl.py`, `tests/test_errors.md`
