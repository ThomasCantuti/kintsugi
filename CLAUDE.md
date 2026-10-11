# Kintsugi / Tsugi

**Tsugi**: always-on Telegram agent doing real tasks on Atlas data. **Kintsugi**: its harness, where each
mistake becomes a gated, traceable, revocable lesson that edits rules, context policies, guardrails, tool access.
Built solo at the MongoDB SF hackathon, Sun 2026-10-11, 10:30–17:00. **No project code before 10:30.**

- Plan: @PLAN.md · Tasks: @TODO.md · Harness spec: `docs/HARNESS.md` · Research and API notes: `docs/RESEARCH.md`
- Facts, decisions, measured numbers: @MEMORY.md

## Rules
1. **Demo first.** Every task serves the 3-minute demo (PLAN.md §6) or the numbers behind it. If it doesn't, it's BOOST or LATER (PLAN.md §9).
2. **Honest numbers.** Never invent, round up, or cherry-pick metrics. Every number in the pitch comes from a stored run in `runs`/`metrics` with n and model. Failed runs are reported, not hidden.
3. **Held-out isolation.** Held-out cases never influence a decision: learner and gate use `cases("train")` only (a test enforces it). Only the eval CLI reads held-out.
4. **Budget.** Cheap models by default, small eval slices, respect `BUDGET_USD`. Ask before any run likely > $5.
5. **Lean.** One language, one process, fewest files. Stdlib → installed deps → new dep. No speculative abstractions.
6. **Gate and lineage are never cut.** They are the thesis.
7. Keep TODO.md checkboxes current. Log decisions and gotchas in MEMORY.md (dated).

## Stack
Python 3.12 · uv · **own harness, no agent framework** · `openai` SDK → `LLM_BASE_URL` (OpenRouter or NVIDIA) ·
FastAPI · python-telegram-bot · pymongo (async) · **Atlas Sandbox = operational DB + Vector Search** (change streams, `$graphLookup`, transactions, `$vectorSearch`/`$rankFusion`) · Atlas CLI ·
static `web/index.html`. Module contracts: PLAN.md §3.
Tests: `ScriptedModel` (deterministic, no tokens) behind the same Model protocol.

## Layout (planned; update when real)
```
kintsugi/   config · db · models · tools · genome · agent · evals · learner · gate · evolve · telegram · api · __main__
evals/      cases.json (hand-written; held-out frozen before the first learning run)
web/        index.html
tests/      one test per non-trivial loop (ScriptedModel)
```

## Commands (update when real)
- `uv sync` · `uv run python -m kintsugi` (bot + API + live view on :8000)
- `uv run python -m kintsugi.evals --label A --split heldout` (`--raw` = A0, `--naive` = D, `--model` = C, `--judge`)
- `uv run python -m kintsugi.evolve --rounds 2 --measure` (learn from failing train cases, held-out curve)
- Local dev DB: `atlas local` deployment `kintsugi-dev` (empty `MONGODB_URI`)
- `uv run pytest -q`

## Conventions
- Async everywhere (`AsyncMongoClient`). Config from env via `kintsugi/config.py`; secrets only in `.env`.
- Every learnable artifact writes a `lineage` node with `parents[]` and `trust`.
- Model ids live in config (`AGENT_MODEL`, `AGENT_FALLBACK_MODELS`, `SUPERVISOR_MODEL`, `FRONTIER_MODEL`), never hardcoded.
- Library/API questions: fetch current docs (ctx7) before coding against them.

## Project agents (`.claude/agents/`)
- `judge-panel`: critique the project/pitch as the 4 judges would
- `mongo-expert`: schema, indexes, aggregation, change streams, transactions
- `red-team`: attack Tsugi, turn successes into test cases
- `eval-runner`: run gate/held-out evals within budget and report faithfully
