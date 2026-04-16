# Second Lane Mac Autopilot Entrypoint

Use this file at the start of every run.

## Mission

Get a beginner macOS user from “project not set up” to “working GPT with Actions” while doing everything possible autonomously.

## First-run load order

Open these files in this order:

1. `SKILL.md`
2. `references/01-human-gates.md`
3. `references/02-browser-protocol.md`
4. `references/03-state-machine.md`
5. `references/04-gpt-builder-map.md`
6. `references/05-verification-checklist.md`
7. `references/07-scripted-mode.md`
8. `references/08-master-prompt.md`
9. `references/13-adaptive-project-detection.md`
10. `references/14-adaptive-artifact-detection.md`

Open `references/06-recovery-playbook.md` only if something broke or the user returns after an interruption.

Then choose the closest runbook if one clearly matches:

- `references/09-runbook-clean-mac.md`
- `references/10-runbook-existing-python-ngrok.md`
- `references/11-runbook-panel-ok-gpt-not-built.md`
- `references/12-runbook-gpt-exists-but-broken.md`

## First reply rule

The first reply should be short, practical, and action-first.

Good example:

- `Сначала проверю, что уже готово на Mac: проект, Python 3.13, ngrok и .env. Потом либо быстро продолжу, либо остановлюсь только там, где без твоего логина реально нельзя.`

## Non-negotiable sequence

Never skip this order:

1. project folder
2. Python 3.13
3. ngrok installed
4. ngrok account gate
5. `.env`
6. panel launch
7. tunnel verification
8. `openapi.gpts.yaml` verification
9. ChatGPT gate
10. GPT builder
11. Actions
12. auth
13. preview test
14. final test

## Success definition

The task is not complete until:

- the panel is working
- the tunnel is live
- `openapi.gpts.yaml` has the real public URL
- the GPT exists
- the GPT can successfully call an action
