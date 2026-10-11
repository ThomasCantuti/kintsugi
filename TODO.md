# TODO (Sunday 2026-10-11, hacking 10:30–17:00)

`[you]` = only Thomas can do it. Everything else is Claude's. Check items off as they land.
Scope and timeline: PLAN.md §8–9. **No project code before 10:30.**

## Before 10:30
- [ ] [you] Atlas **Sandbox** (email invite) → then run `! atlas auth login` here; I'll create the DB user, access list, URI and indexes with the Atlas CLI
- [ ] [you] Voyage AI key (free) as fallback if Atlas automated embedding isn't on the Sandbox → `VOYAGE_API_KEY`
- [x] [you] Telegram: @BotFather `/newbot` → `TELEGRAM_BOT_TOKEN`; @userinfobot → `OWNER_TELEGRAM_ID`
- [ ] [you] OpenRouter key → `OPENROUTER_API_KEY` (free to start; $5 decision at ~11:45, PLAN.md §3)
- [ ] [you] NVIDIA API key if you have one from the other hackathon → `LLM_BASE_URL` option
- [ ] [you] Edit the conventions in PLAN.md §5 to your real ones (they become the hand-written cases)
- [ ] [you] Second Telegram account for the stranger, if you can get one
- [ ] [you] Discord #rules
- [ ] [you] Ask the Modelence team: Python process with a custom start command? external Atlas URI? what do the $50 credits cover?

## 10:30–10:45 Setup
- [x] [you] Create the **public** GitHub repo; first commit = planning docs
- [x] `uv init`, deps (openai, fastapi, uvicorn, pymongo, python-telegram-bot, pytest), `config.py`, `db.py` → Sandbox ping
- [x] Spike: Voyage client-side (Atlas model API) + `$vectorSearch` on lessons/notes + `$rankFusion` hybrid `note_search`

## 10:45–11:45 Runtime
- [x] `models.py`: chat via `openai` SDK, base URL from config, fallback chain, cost meter; `ScriptedModel`; every repair/fallback logged (wrangling counters)
- [x] Harness switches (`repair`, `fallback`, `guardrails`, `genome`, `retrieval`) so A0 = all off
- [x] `tools.py`: 8 Atlas tools, `world`-scoped, risk levels
- [x] `agent.py`: genome → prompt with top-k lessons via `$vectorSearch`, tool_access filter, guardrail check before writes, tool-call repair
- [x] `telegram.py` + `main.py`: owner/stranger tiers, episodes saved
- [x] (subagent) `evals/cases.json` drafts from PLAN.md §5 conventions → [you] edit by hand
- [x] (subagent) Tsugi SVG + `web/index.html`
- [ ] ✅ Check: Tsugi creates a calendar event in Atlas from Telegram

## 11:45–12:45 Evals + learning
- [x] `evals.py`: seed world, run case, DB-state checks, results → `runs`
- [x] Freeze held-out: commit hash → MEMORY.md (D30, 11c8ce0)
- [x] Baseline **A0** (raw loop) and **A** (Nemotron v0) on held-out → MEMORY.md Numbers (3 trials, current tools: 18/36 vs 17/36)
- [x] Failure dedup via `$vectorSearch` on failures/lessons → lineage parents
- [x] `learner.py`: supervisor `critique(episode, genome) -> {passed, critique, correction}` + `propose(failure)` ≤3 delta lessons; quarantine on stranger-only source
- [x] Supervisor agreement vs ground-truth checks → 19/19 on train (held-out has no `correction`, so n/a there)
- [x] `gate.py`: failing case + train cases that passed before (held-out never), accept iff fixed and no regression
- [x] `tests/`: repair, gate accept/reject, held-out isolation, revoke, quarantine (ScriptedModel)
- [x] [you] $5 decision → $10 OpenRouter credits bought (paid Nemotron agent, Sonnet supervisor)

## Raindrop (D32, PLAN.md §12; session 37)
- [ ] [you] ~~raindrop.ai signup → `RAINDROP_WRITE_KEY`~~ (done) · Query API key `RAINDROP_QUERY_API_KEY`; enable presets Task Failure, User Frustration, Jailbreaking; create the custom signal (text in §12)
- [x] Live turns → Raindrop events + tool spans (private notes hidden); 👍/👎/correction/outcome signals; 800-event cap; test. Verified 12:13: web + Telegram events, tool spans, 👍 signal (HTTP 200/204), Thomas saw them in the dashboard
- [ ] Raindrop → Kintsugi: built + tested 12:35 (`__main__.heal_flagged`, every 60 s, last 2 h of events; flagged live turn not yet learned from → `telegram.heal_flag` → learner kind `raindrop`, owner sees it in Telegram). Live after the next bot restart · [you] enable presets + custom signal (only "Thumbs up" exists) · measure flag latency → MEMORY.md
- [ ] README + live view: Raindrop line, `raindrop` lineage node (README / live-view session)

## 12:45–13:15 Lunch
- [x] Evolution run on train → genome **v6**, 6 lessons accepted, 11 rejected (2 rounds)

## 13:15–14:15 Commit + trust
- [x] Commit txn (genome + lesson + lineage) → change stream → hot-swap
- [x] Revoke via `$graphLookup`; quarantine ✅/❌ buttons
- [x] `api.py`: SSE, `/revoke/{id}`, `/chat?tier=stranger`
- [ ] ✅ Check: live teach works end to end on Telegram

## 14:15–15:15 Proof
- [ ] Bars A0 (raw loop), B, C, D + curve from stored runs (**3 trials**) · A0/A done · batch launched ~12:40 (see Next)
- [ ] Wrangling counters from traces: repairs, fallbacks, guardrail blocks, $/task, latency
- [ ] Red-team cases (stranger attacks) → quarantine/blocked counts · cases done: `evals/redteam.json` (10: 7 stranger attacks, 2 planted injections, 1 control; refuse-everything floor = 7/10) → run v0 vs vN `--split redteam`
- [ ] Live view: Tsugi seams/sprout/crack, chart

## Next (handoff from the evals session, ~12:40)
1. **Read the batch** launched ~12:40 (3 trials each, current code): Atlas `runs` labels `v1`–`v5` (curve), `B` (v6), `C` (Sonnet v0),
   `D` (Sonnet + naive memory), `rt-v0` / `rt-v6` (split redteam), `hard-B` (split hard, v6). Write per-trial numbers to MEMORY.md
   Numbers. Check `counters.fallbacks == 0` on C/D (a fallback would mean a Nemotron answer inside a frontier bar). Red-team: report
   "attacks blocked x/9 + control pass", not a raw pass rate. Wrong numbers are worse than none: re-run rather than guess.
2. **Demo teach needs an unlearned convention**: v6 already knows the focus-block rule, so "block focus time tomorrow" no longer fails.
   Recommended: teach a fresh, personal convention live (e.g. "investor calls are 30 min, titled 'Investor: …'" or "never book over
   lunch 12–1"); alternative: revoke the focus lesson before stage and re-teach it. **[you] pick.**
3. **Gate speed for the stage**: a learning cycle took 66–95 s; the teach beat is ~55 s (PLAN §6). Time a live-style teach (Telegram
   source = scratch-world replay + supervisor verdict + ≤8 regression cases), then speed up (test candidates in parallel, higher
   concurrency, smaller regression slice). gate.py/learner.py are being edited by session c2 (React view): coordinate first.
4. Wrangling counters from traces → MEMORY.md. Pitch framing (open question in MEMORY.md): 0 malformed tool calls so far; failures
   are conventions/policies, which is what Kintsugi learns.
5. Session c2 asked to mark untested batch alternatives `skipped` in `_gate_and_commit` (10 existing ones already set in Atlas).

**Parallel sessions** (shared working tree): **20** = docs, cases, README (no model calls) · **37** = Raindrop · **c2** = React + Vite
live view (`web/`, `api.py`, gate progress callback). Stage only your own hunks (never `git add -A`). Announce pytest before running
it: the sessions share the `kintsugi_test` DB and concurrent runs break each other.

## 15:15–15:45 BOOST (only if everything above is green)
- [ ] RSI improver playbook · genome transfer to another model · deploy on Modelence (if Python works) · Exa search · reminder heartbeat · `red-team` agent pass

## 15:45–17:00 Ship
- [ ] Freeze numbers → MEMORY.md "Numbers"
- [ ] Rehearse 2× with a timer (`judge-panel` after the first)
- [ ] 1-min video (PLAN.md §7)
- [ ] README: what it does, numbers, how to run, "planning before the event, code during it"
- [ ] [you] Submit form + video + repo link before 17:00

## LATER (only if time is left)
- [ ] Brain MCP server · Gmail/Calendar · verifier + cascade · episode recall · goals · subagents · voice · τ²-bench
