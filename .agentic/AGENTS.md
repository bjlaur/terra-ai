# AGENTS.md — TerraAI Agent Notes

## Project Shape

- TerraAI is a SOPEL plugin that turns an IRC bot into a provider-agnostic AI assistant.
- Package name: **terra-ai** (config files, directories)
- Class name: **TerraAI** (Python classes)
- Default provider: **OpenRouter (OWL)**
- Trigger character in production: `-` (`.` used in docs)
- SOPEL plugin API: `@plugin.command()`, `@plugin.rule()` (NOT `@sopel.module`)
- Admin gating: `@plugin.require_admin` / `trigger.admin` (NOT config-driven `admin_nicks`)
- Command handlers: `ManagementCommands` (was `AdminCommands`) in `commands/management.py`

## User and Environment

- **OS:** Arch Linux / CachyOS
- **Active shell:** zsh (for interactive use)
- **SOPEL:** Not yet installed; only in AUR (chaotic-aur). Build via yay in Containerfile.
- **AUR helper:** yay
- **chaotic-aur:** enabled and available
- **Agent name:** OWL
- **Prefer practical changes and concise explanations.**
- **Prefer Arch-style package commands when mentioning system packages.**
- **Do not `pip install` into system Python.** Dependencies in `Containerfile` + `PACKAGES.md`.

## Doc Update Rules

- **Update every commit or every few commits:** `TODO.md`, `CHANGELOG.md`, `docs/release-X.Y.Z/`
- **Only update when the plan itself changes:** `.agentic/plan.md` (long-term plan, not per-commit)

## Runtime Files

- Real config: `config/terraai.yaml` (gitignored)
- Example config: `config/terraai.yaml.example`
- Test config: `config/terraai-test.yaml.example` (gitignored: `config/terraai-test.yaml`)
- State: `data/` (gitignored) — terraai.db, terraai.log
- Containerfile uses Arch Linux base + chaotic-aur

## Git Identity

- user.email: `owl@terra-ai`
- user.name: `OWL`
- agent name: `agent1` (OWL) / `agent2` (this agent)

## Parallel Work

When working alongside another agent, follow `parallel-work.md`.
