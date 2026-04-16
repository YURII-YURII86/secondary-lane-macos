---
name: gpts-mac-autopilot
description: Autonomously deploy the macOS Second Lane project from a near-clean beginner Mac: verify or install Python 3.13 and ngrok, guide human-only ngrok and ChatGPT sign-in steps, fill .env, launch the local agent, verify the ngrok tunnel and openapi.gpts.yaml update, then walk the user through creating and testing the GPT with Actions. Use when the user wants Codex to do as much of the macOS setup as possible by itself, while pausing only for true human-only steps such as registration, login, email verification, captcha, payment, or macOS system permissions.
---

# Second Lane Mac Autopilot

Use this skill when the user wants a near-fully-automated macOS setup of the Second Lane project for a beginner.

## Mandatory start

Before doing substantial work:

1. open `ENTRYPOINT.md`
2. open `references/01-human-gates.md`
3. open `references/02-browser-protocol.md`
4. open `references/03-state-machine.md`
5. open `references/04-gpt-builder-map.md`
6. open `references/05-verification-checklist.md`
7. open `references/07-scripted-mode.md`
8. open `references/08-master-prompt.md`
9. open `references/13-adaptive-project-detection.md`
10. open `references/14-adaptive-artifact-detection.md`
11. choose the closest runbook from `references/09-runbook-clean-mac.md`, `references/10-runbook-existing-python-ngrok.md`, `references/11-runbook-panel-ok-gpt-not-built.md`, `references/12-runbook-gpt-exists-but-broken.md`
12. open `references/06-recovery-playbook.md` only if the flow breaks

Do not replace this with a broad repository review.

The main idea:

- the agent does everything it can itself
- the user is interrupted only at true human-only gates
- every step is verified before moving forward
- comments to the user must sound like a helpful friend, not a system manual

## What this skill is for

This skill is specifically for the macOS branch of the Second Lane project where the final goal is:

1. prepare the local project on macOS
2. install or verify Python 3.13
3. install or verify `ngrok`
4. help the user complete `ngrok` account steps
5. generate and save `.env`
6. launch the macOS panel
7. verify the local daemon and public tunnel
8. verify `openapi.gpts.yaml` now contains the real tunnel URL
9. help the user create the GPT in ChatGPT
10. help the user connect `Actions`
11. help the user test the GPT end to end

## Autonomy contract

The agent should do directly:

- inspect the project files
- check whether required files already exist
- run local commands
- create or update `.env`
- generate `AGENT_TOKEN`
- open URLs and local files when useful
- launch the macOS panel or helper scripts
- verify the tunnel and OpenAPI file
- extract text from local project files for the GPT builder
- guide the user through the GPT builder with very explicit small steps

The agent should pause only for true human-only gates:

- account registration
- login to `ngrok`
- login to ChatGPT
- email verification
- captcha
- payment or plan upgrade
- browser permission that the agent cannot safely bypass
- macOS security dialog that requires explicit user consent

Everything else should be done by the agent unless blocked by missing tooling.

## Communication style

While using this skill:

- explain every step in plain Russian unless the user clearly wants another language
- avoid jargon, or explain it immediately in simple words
- keep updates short and practical
- after each important action, say what was done and what happens next
- when pausing for a human gate, say exactly what the user must do and how the agent will continue after that

## Required local context to inspect first

Before doing large actions, inspect the real project state.

Prefer `scripts/inspect_mac_gpts.py` for the first factual pass.
If the expected macOS branch is missing or renamed, use `references/13-adaptive-project-detection.md` and `scripts/discover_secondarylane_layout.py` before declaring the structure broken.
If the branch root is known but important files moved, use `references/14-adaptive-artifact-detection.md` and `scripts/discover_secondarylane_artifacts.py` before declaring those roles missing.

Prioritize these files if they exist:

- `Версия для Мак/Запустить Second Lane.command`
- `Версия для Мак/.env.example`
- `Версия для Мак/gpts_agent_control.py`
- `Версия для Мак/openapi.gpts.yaml`
- `Версия для Мак/gpts/system_instructions.txt`
- `Версия для Мак/gpts/knowledge/`
- `Версия для Мак/docs/MAC_FIRST_START.md`

## Operating rules

### 1. Action-first

Do not begin with a broad code review.
If a runbook clearly matches the situation, follow that runbook instead of improvising a new high-level flow.

Start by discovering the real current setup state:

1. does the macOS project folder exist
2. is `.env` already present
3. is Python 3.13 callable
4. is `ngrok` callable
5. is the panel already running
6. does `openapi.gpts.yaml` still have a template URL or already a real one

### 2. Verify before asking

Never ask the user for something that can be discovered locally.

### 3. One safe default path

If the user has not chosen a custom macOS path, prefer:

- `/Users/<user>/SecondLane`

When discussing project location with a beginner, explain that this is simply the main project folder in their home directory.

### 4. Do not hand-edit generated project files unless required

The user may edit:

- `.env`
- ChatGPT GPT-builder fields

Do not tell the user to manually rewrite:

- `openapi.gpts.yaml`
- Python source files
- tests

### 5. Browser assistance

If local browser/UI control exists in the current environment, use it.

If it does not:

- open the correct URL with `open` when possible
- tell the user exactly what page was opened
- tell them exactly what one human action is needed
- resume immediately after the user confirms completion

### 6. Never skip the sequence

Always enforce this order:

1. project path
2. Python
3. `ngrok`
4. `ngrok` account token
5. `ngrok` domain
6. `.env`
7. panel launch
8. tunnel verification
9. OpenAPI verification
10. GPT builder
11. `Actions`
12. auth token in GPT
13. preview test
14. final GPT test

## State machine summary

S0. Detect current reality
S1. Prepare the project folder
S2. Verify or install Python 3.13
S3. Verify or install ngrok
S4. Complete ngrok human gate
S5. Generate `.env`
S6. Launch the macOS panel
S7. Verify `openapi.gpts.yaml`
S8. Prepare GPT builder materials
S9. Complete ChatGPT human gate
S10. Guide GPT creation
S11. Configure auth correctly
S12. Test before declaring success
S13. Final handoff

## Success definition

This skill succeeds only when all of the following are true:

1. macOS project folder is ready
2. Python 3.13 works
3. `ngrok` works
4. `.env` is filled correctly
5. panel launches
6. tunnel is live
7. `openapi.gpts.yaml` contains the real public URL
8. GPT is created
9. `Actions` are configured
10. auth works
11. a simple action call succeeds

If any item is not verified, report the exact remaining blocker in one short beginner-friendly sentence.
