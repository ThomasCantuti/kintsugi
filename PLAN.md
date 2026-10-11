# Kintsugi: an agent that gets stronger where it breaks

> **Tsugi** is an always-on personal agent on Telegram that does real tasks (calendar, notes,
> reminders, contacts, outbox) on data in MongoDB Atlas. **Kintsugi** is its harness: every mistake
> becomes a lesson that edits the harness itself (**rules, context policies, guardrails, tool access**),
> and every lesson is **tested before it ships, traceable, and undoable**. Cheap Nemotron + Kintsugi
> vs a frontier model, on hand-written hidden tasks.

Built solo at the MongoDB #SFTechWeek hackathon, **Sun 2026-10-11, 10:30–17:00**, Shack15.
Problem Statement 1: **Recursive Harnessing**. Planning docs were written before the event; all code is
written during it (commit history is public).

**Both halves of the title are the project:**
- **Harness engineering**: Kintsugi engineers its own harness. Lessons edit the genome, the gate tests them, lineage undoes them.
- **Model wrangling**: the harness makes a free Nemotron reliable (tool-call repair, fallback chain,
  per-role model routing, guardrail checks) and we measure every rescue in traces.

Hook: *"Muse, Dots, OpenClaw: always-on agents that remember your corrections. A remembered correction
is an untested change to the agent, and a poisoned one is hard to remove (CSA on OpenClaw MEMORY.md).
Tsugi tests every lesson before it goes live, and any lesson can be traced and undone."*
(Check every claim about other products before saying it on stage.)

---

## 1. Claims and decision rule
| # | Claim | Scores on |
|---|---|---|
| 1 | **Learns**: a mistake → a lesson edits one of the 4 genome sections → gate → live in < 2 min | Demo 35, Difficulty 30 |
| 2 | **Wins** (wrangling): free Nemotron + harness + learned genome vs frontier (vanilla and naive memory) on held-out tasks; each harness layer's gain measured | Impact 20, Difficulty 30 |
| 3 | **Trusted**: every lesson has lineage; revoke cascades; stranger-sourced lessons are quarantined | Impact 20, Creativity 15 |

**Decision rule:** build it only if it moves a claim on stage or in the chart. Every number comes from a
stored run (CLAUDE.md rule 2).

## 2. Product
- **Owner** = Thomas (Telegram id from env). Everyone else = **stranger**.
- **Telegram**: 👎 reaction = failure signal · reply to Tsugi = correction · inline ✅/❌ = quarantine decision.
- **Tools** (Atlas collections, deterministic, so outcomes are checkable): `calendar_create`, `calendar_list`,
  `note_add`, `note_search` (hybrid `$rankFusion`: text + vector), `reminder_set`, `contact_lookup`, `outbox_draft`, `outbox_send`.
- **Genome** (one versioned doc): `rules[]` · `context_policies[]` · `guardrails[]` · `tool_access{owner:[…], stranger:[…]}`.
- **Tsugi character**: SVG in a small live view. Gold seam = lesson (click → lineage) · sprout = memory ·
  crack = poison · gold repair = revoke. Supporting view only ("dashboard as main feature" is banned).

## 3. Architecture

### GenAI stack (event requirement: Atlas for **both** operational DB and vector DB)
| Layer | Ours |
|---|---|
| Application / UX | Tsugi on Telegram + live view (Tsugi SVG, lineage, chart) |
| App framework / orchestration | **Kintsugi**, our own harness (asyncio + FastAPI) |
| Operational DB | Atlas: episodes, genomes, lessons, lineage, tool data, runs (transactions, change streams, `$graphLookup`) |
| Vector DB | **Atlas Vector Search**, used where it earns its place (not basic RAG): (1) **lesson retrieval**: only the top-k lessons relevant to the message go into the prompt, so a small model isn't drowned in rules; k and the threshold live in `context_policies`, so the harness can learn them · (2) **failure dedup**: a new failure is matched to similar past failures/lessons → no duplicate lessons, lineage parents linked · (3) `note_search` hybrid |
| Observability (production) | **Raindrop** SDK: every live turn, tool spans, feedback and outcome signals; its failure signals feed the learner (§12) |
| Foundation models | Nemotron (agent) · supervisor (Ultra / Sonnet) · Voyage `voyage-4-lite` embeddings via **Atlas automated embedding** (`$vectorSearch` with `query.text`, public preview May 2026; fallback: Voyage API client-side) |
Setup from the terminal with the **Atlas CLI** (`atlas`): DB user, access list, connection string, search indexes.

```
Telegram (owner / stranger) ─► agent.run(genome vN, msgs, world, tier)
                                 prompt from rules + top-k lessons ($vectorSearch) · tools filtered by tool_access[tier]
                                 guardrail check before write tools · tool-call repair
                                      │ episode (msgs, tool calls, outcome) ─► episodes
            👎 / correction ──────────┤
                                      ▼
                 dedup ($vectorSearch similar failures/lessons) → learner.propose(failure) → ≤3 lessons {section, delta, prediction}
                 stranger-only source? → quarantine → owner ✅/❌
                                      ▼
                 gate: candidate genome on the failing case + train cases that passed before (held-out never)
                       accept iff the case is fixed and nothing regresses
                                      ▼
   txn: genomes vN+1 + lessons + lineage ──► change stream ──► agent hot-swaps · live view (SSE) · Tsugi seam
   revoke(id): $graphLookup descendants → revoked → rebuild genome → commit
```

### Module contracts (`kintsugi/`)
| Module | Contract |
|---|---|
| `config.py` | env → settings (model ids, `LLM_BASE_URL`, keys, budget) |
| `db.py` | `AsyncMongoClient`, collections, indexes (incl. vector search indexes), `commit()` txn, `revoke()` via `$graphLookup`, `similar(coll, text, k)` via `$vectorSearch` |
| `models.py` | `await chat(messages, tools, model) -> Reply(text, tool_calls, usage, cost)`; `openai` SDK, any OpenAI-compatible base URL (OpenRouter, NVIDIA); fallback chain; `ScriptedModel` for tests |
| `tools.py` | registry: fn + JSON schema + risk (read/write). Every doc carries `world`; tools filter by it, so evals run on seeded fixtures in their own world in the same cluster |
| `agent.py` | `await run(genome, messages, world, tier) -> Episode`; repair: validate args → error back → retry ≤ 2 |
| `evals.py` | load `evals/cases.json`; `run_case(genome, case, model) -> {passed, checks}`; `run_split(split)`; results → `runs` |
| `learner.py` | `propose(failure) -> [Lesson]`; never reads held-out (test enforces it) |
| `gate.py` | `judge(lesson, genome) -> Verdict` (fixes case, no train/held-out regression) |
| `telegram.py` | handlers, reactions, replies, inline buttons |
| `api.py` | FastAPI: SSE from change streams, `POST /revoke/{id}`, `POST /chat?tier=stranger`, serves `web/index.html` |
| `main.py` | one asyncio process: bot + API (+ learner task) |

### Stack
Python 3.12 · uv · FastAPI · own harness (`openai` SDK) · python-telegram-bot · pymongo async ·
**MongoDB Atlas Sandbox** (required for finalists: Vector Search, change streams, transactions, `$graphLookup`) · Atlas CLI ·
static `web/index.html` (CDN Chart.js) · pytest.

### Models (OpenRouter, checked 2026-10-11 09:59 PT; all ids in config)
| Role | Model | Price $/M in · out |
|---|---|---|
| Tsugi agent | `nvidia/nemotron-3-super-120b-a12b:free` (paid variant if credits) | free / 0.08 · 0.45 |
| Fallbacks | `nvidia/nemotron-3.5-lightning:free` · `nvidia/nemotron-3-ultra-550b-a55b:free` | free |
| **Supervisor** (judge + teacher + improver) | `nvidia/nemotron-3-ultra-550b-a55b:free` → `anthropic/claude-sonnet-5.5` if credits (failures only, ~1¢ each) | free / 2 · 10 |
| Frontier reference (chart only) | `anthropic/claude-sonnet-5.5` | 2 · 10 (needs credits, ~$0.5 for one held-out run) |

**Free-tier cap:** 50 free-model requests/day until ≥ $10 of credits are bought (then 1,000/day), 20/min.
One agent turn is 2–4 requests and one gate run is ~30–90, so the cap runs out around the first eval
run. Options: $5 → paid Nemotron (same model, no daily cap, whole day ≈ $1–2) · $10 → 1,000 free/day ·
an NVIDIA API key (OpenAI-compatible, just change `LLM_BASE_URL`).
AWS Kiro credits are for Kiro's own coding agent, not AWS services or an API we can call (Kiro FAQ).

## 4. Learning loop
1. **Signal**, from three sources (humans are optional at runtime):
   - **Hand-written case checks** (DB state): ground truth, the main source for the evolution run.
   - **Supervisor**: a smarter model reviews live episodes against the genome → pass/fail + critique.
     For failed cases it also writes the correction. Its critique is only a signal; the gate decides.
   - **Owner** 👎 / correction on Telegram (live demo, overrides the supervisor) · red-team cases that got through.
2. **Propose** (supervisor model): ≤ 3 **delta** lessons, each `{section, delta, prediction}`, never a rewrite (ACE).
3. **Trust**: if every source is a stranger → quarantine → owner ✅/❌.
4. **Gate**: candidate genome runs the failing case + up to 8 train cases that passed before (temp 0, seeded worlds).
   Accept iff the case is fixed and none of them regress. Held-out never influences a decision.
5. **Commit** in one transaction: genome vN+1 + lesson + lineage node → change stream → hot-swap, new seam.
6. **Revoke**: `$graphLookup` descendants → revoked → genome rebuilt without them → commit.
7. *(BOOST, Raindrop RSI)*: the improver's own playbook evolves from its prediction-vs-outcome record.

## 5. Evals: how we test the project
**a. Project tests** (pytest + `ScriptedModel`, zero tokens): tool repair recovers from a bad call ·
gate accepts a fixing lesson and rejects a regressing one · learner can't read held-out · revoke removes
descendants · stranger-only lesson goes to quarantine.

**b. Task evals** (`evals/cases.json`): ~30 **hand-written** cases built from Thomas's real conventions:
`{id, split, section, fixtures, messages, checks, correction}`. `checks` are DB-state assertions
(e.g. one event, 90 min, not on Friday). `correction` (optional) is what Thomas would say when Tsugi gets
it wrong; if missing, the supervisor writes it from the failed checks. ~18 train / ~12 held-out.
**Held-out is frozen (commit hash in MEMORY.md) before the first learning run.**

**c. The chart** (held-out pass rate, n, $/task):
| Bar | Model | Genome |
|---|---|---|
| A0 | Nemotron | **raw loop**: no repair, no fallback, no guardrail check, no genome (what the model does alone) |
| A | Nemotron | v0 (harness on) |
| B | Nemotron | vN (learned) |
| C | Frontier | v0 |
| D | Frontier | v0 + **naive memory**: every train correction pasted into the prompt (how product memory works today) |
Plus the **curve**: held-out pass rate per genome version.
A0 → A = what our hand-built harness adds (wrangling). A → B = what the self-edited harness adds (recursive harnessing). B vs C/D = free model vs frontier.
**Wrangling counters** (from traces, every run): tool calls repaired · fallbacks used · guardrail blocks · $/task · latency.

**d. Supervisor agreement**: on every case, compare the supervisor's verdict with the hand-written checks
→ "the judge agreed with ground truth X/n times". That's how much its live feedback can be trusted.
The chart is scored **only** by deterministic checks, never by the supervisor.
**Cost is split**: runtime $/task (Nemotron) vs one-time teaching cost (supervisor). Pitch: *a smart model
teaches once, the free model runs every day.*

**Showing self-improvement without strangers** (QR dropped):
1. Live teach on stage (§6).
2. Evolution run on train cases through the afternoon → the curve.
3. Hand-written red-team cases + the `red-team` agent play the stranger → quarantine, tool access blocks, one revoke.
4. Before/after replay: the same held-out task under v0 and vN, side by side.

### Conventions for the cases (Thomas: replace with your real ones)
- Focus blocks: 90 min, titled "Deep work", mornings, never on Fridays. *(rules)*
- Times are Pacific unless I say otherwise. *(rules)*
- "The team" = contacts tagged `team`. *(context policy: look up contacts before addressing)*
- Check the calendar for conflicts before creating an event. *(context policy)*
- Never send an email without showing me the draft first. *(guardrail)*
- Never reveal notes tagged `private` to anyone but me. *(guardrail)*
- Strangers may only `note_add` and `calendar_list`; never `outbox_send`. *(tool access)*
- Reminders fire 15 min before, not at the time. *(rules)*

## 6. Demo script (3:00)
| t | Beat |
|---|---|
| 0:00 | **Hook** (above). |
| 0:20 | **Meet Tsugi**: free Nemotron, genome v0 → vN today, N lessons as seams, wrangling counters (repairs, fallbacks) *(real numbers only)*. |
| 0:35 | **Teach**: "block focus time tomorrow" → 60 min on a Friday → 👎 + "focus blocks are 90 min, never Fridays" → 3 candidates → gate ticking (n cases) → v+1 → seam animates → ask again → correct event in Atlas. |
| 1:30 | **Stranger**: stranger asks Tsugi to send my notes → blocked by tool access. Stranger "teaches" a rule → quarantined → owner ❌. |
| 1:55 | **Revoke**: a lesson that slipped → click seam → lineage → revoke cascades → gold repair. |
| 2:20 | **Proof**: chart A/B/C/D + curve + $/task. |
| 2:50 | **Close**: "Agents that get stronger where they break." |

Stranger = a second Telegram account if available, else `POST /chat?tier=stranger` from the live view.

## 7. 1-minute video (record 16:15)
0:00 one-line pitch · 0:08 teach clip · 0:30 quarantine + revoke clip · 0:42 chart · 0:55 repo URL, "built today on MongoDB Atlas".
AI-generated footage only for the Tsugi intro/outro (≤ 8 s): **Google Flow** (Veo, Thomas's Gemini Pro plan);
Claude writes the prompts, Thomas generates by hand, MP4s go in `assets/video/`. Everything
showing the product is a real screen recording (rule: demo only what was built today). Record clips as
features land (teach ~14:15, revoke ~14:15, chart ~15:15) so the video isn't a 16:15 scramble.

## 8. Timeline (Sunday)
| Time | Work | Done when |
|---|---|---|
| 10:30–10:45 | Public repo, first commit (planning docs), `uv init`, config; Atlas CLI: user, access list, URI; spike automated embedding on the Sandbox | `db.ping` OK; one `$vectorSearch` returns a hit |
| 10:45–11:45 | models · tools · agent · telegram. Parallel subagents: `cases.json` drafts (you edit), Tsugi SVG + `web/index.html` | Tsugi creates a calendar event in Atlas from Telegram |
| 11:45–12:45 | evals runner + baseline A · learner · gate · pytest | gate test green; A measured |
| 12:45–13:15 | Lunch; evolution runs on train in the background | first lessons in `lessons` |
| 13:15–14:15 | commit txn · change-stream hot-swap · lineage · revoke · quarantine buttons | live teach works end to end |
| 14:15–15:15 | bars B/C/D + curve · red-team cases · live view wiring | chart from stored runs |
| 15:15–15:45 | BOOST if all green | |
| 15:45–16:15 | Freeze numbers → MEMORY.md, rehearse 2× | |
| 16:15–16:45 | Video + README | |
| 16:45–17:00 | Submit | form sent |

## 9. Scope
- **MUST**: runtime (models, Atlas tools, agent + repair, 4-section genome, Telegram, episodes) · **Raindrop SDK** (§12, D32) · **Atlas Vector Search** (lesson retrieval, failure dedup, note search) · evals
  (cases, runner, pytest) · learner + gate · commit txn + hot-swap · lineage + revoke + quarantine ·
  chart A–D + curve · Tsugi SVG + live view · video + README.
- **BOOST** (in order): RSI improver playbook (Raindrop) · **genome transfer**: run vN learned on Nemotron Super on another model (Lightning / Ultra) → do lessons carry over? · **deploy on Modelence** ($50 sponsor credits; only if it runs our Python process, ask their team) · Exa web search · reminder heartbeat · `red-team` agent pass.
- **LATER, only if time is left** (in order): Brain MCP server · Gmail/Calendar · verifier + cascade ·
  episode recall · background goals · subagents · voice · τ²-bench.

Behind schedule: drop BOOST, then cut the live view down to the Tsugi SVG + chart. Never cut the gate,
lineage, or held-out evals.

## 10. Risks
| Risk | Fallback |
|---|---|
| Free cap (50/day) hit | $5 paid Nemotron or NVIDIA key; ScriptedModel for every test |
| Nemotron tool calls flaky | tool-call repair; fallback chain; that's also the story (harness > model) |
| Live gate too slow on stage | small gate slice (failing case + 6), parallel; recorded run as backup |
| Eval noise | temp 0, seeded worlds, 2 trials on the chart, report n |
| Automated embedding not available on the Sandbox | Voyage API key, embed client-side (`voyage-4-lite`), same index |
| Venue Wi-Fi | phone hotspot |
| Running out of time | timeline checkpoints; cut order in §9 |

## 11. Q&A prep
- *"Isn't this just memory?"* Memory stores; Kintsugi tests. A lesson ships only if it fixes the failing case
  without regressions, and it can change guardrails and tool access, not just facts.
- *"Overfitting to held-out?"* The learner never reads it (a test enforces it). Held-out was written by
  hand and frozen at commit X before the first learning run. We report n.
- *"Why MongoDB?"* One cluster is both databases: change streams hot-swap the genome; transactions commit
  genome + lesson + lineage atomically; `$graphLookup` drives revoke; Vector Search picks which lessons a
  small model sees and stops duplicate lessons; eval worlds live in the same cluster.
- *"What if the gate lets a bad lesson through?"* Revoke: one click removes it and everything built on it.
- *"Who supervises the supervisor?"* The gate and the ground-truth checks. A wrong critique can propose a
  bad lesson but can't ship it; supervisor agreement with ground truth is measured and shown.
- *"Isn't B just distilling the frontier model?"* Partly, on purpose: teaching cost is reported separately,
  and the runtime model stays free. Bar D shows that pasting the same feedback into a frontier prompt isn't the same.
- *"n is small."* Yes, n = 12 held-out; that's why we show it and report every run.
- *"Why Raindrop if you have Atlas?"* Atlas is Tsugi's memory and the gate's ground truth. Raindrop watches
  unlabeled production traffic and flags failures nobody 👎'd; Kintsugi turns each flag into a tested, revocable lesson.

## 12. Raindrop (D32: the judges said "use its SDK, it's free")
**Role: Raindrop is the eyes, Kintsugi is the hands.** Raindrop sees every live turn and flags failures, including
silent ones nobody 👎'd. Kintsugi turns a flag into a gated, revocable lesson. Raindrop then shows the outcome on
the same event and the signal on the next genome version. Raindrop's own self-healing loop has a human and a
coding agent ship a PR; ours closes the loop by itself, at the harness level, behind the gate.

**Free Hobby plan** (raindrop.ai/docs/platform/plans, read 11:30): 1,000 events/month (ingestion stops for the
month at the cap), signals (7 presets + 1 custom), tracing, alerts, Query API, MCP. Pro only: Issue Detection,
Experiments.

**Where.** Inline at the existing call sites, with no wrapper module (Raindrop's setup skill). Off without
`RAINDROP_WRITE_KEY`; only the bot server (`__main__`) starts it. SDK: `raindrop-ai`. Rows 1–4 built 12:05, row 5 12:33.
| # | Hook | Raindrop call | What it gives |
|---|---|---|---|
| 1 | `agent.save(ep, "live")` (Telegram + `/api/chat`) | `begin(user_id=chat id or "web-stranger", event="tsugi_turn", event_id=ep._id, convo_id=chat, input, model, properties={genome_version, tier, repairs, fallbacks, blocks, cost, latency, error})` → `track_tool` per step (DENIED/ERROR → `error`) → `finish(output=reply)` | every production turn with its tool trace; repairs and blocks also show up as Raindrop tool-error signals |
| 2 | Telegram 👍/👎 (`telegram.on_button`) | `track_signal(ep, "thumbs_up"/"thumbs_down", "feedback", sentiment)` | owner and stranger feedback |
| 3 | `telegram.learn_from`, `api.teach` | `track_signal(ep, "correction", "edit", after=correction)` | the human correction (owner or stranger) |
| 4 | learner outcome | `track_signal(ep, "lesson_shipped"/"lesson_quarantined"/"no_safe_fix", properties={lesson, section, text, version, regression x/y})` | the Raindrop event shows what Kintsugi did about it |
| 5 | **Raindrop → Kintsugi** poller (`__main__` task, every 60 s) | Query API `GET query.raindrop.ai/v1/events?timestamp[gte]=<now − 2 h>`: each event lists its signals, and our event ids are episode ids. Flags (Raindrop's real names): User Frustration, Attempted Prompt Injection, Request Execution Needs Correction (our custom signal) | a flagged live episode not yet learned from (no lineage node) → `learner.learn(kind="raindrop", tier=episode tier, failed=["Raindrop: <signal>"])` → the supervisor writes the correction and checks the turn really broke it (if not: `false_alarm`, no lesson, 🌦️) → gate → a seam whose lineage root is the Raindrop flag. The owner watches it in Telegram (🌧️ flagged → gate → result). Stranger episodes → quarantine with ✅/❌, as usual |

- **Only `kind == "live"` goes to Raindrop.** Evals, gate runs and evolve never send anything: one evolve round
  is hundreds of episodes and would hit the monthly cap. Guard: sending stops after `RAINDROP_EVENT_CAP` = 800 live episodes.
- **Privacy:** in tool spans, notes tagged `private` are sent as `[private]` (the `note_search` output is JSON with
  tags). User text and Tsugi's replies are sent as they are, because Raindrop has to see a leak to flag it (a private
  note in a reply to a stranger is exactly the failure we want caught). The live world is seeded demo data.
- **Custom signal** (the 1 free slot; Raindrop names it from the text: "Request Execution Needs Correction"): *the assistant did the request in a way the user would
  have to correct: wrong time, day, duration or recipient; ignored a stated preference; sent something without
  confirmation; or revealed private information.* Sentiment Negative.
- **Not used:** auto-instrumentation of the `openai` client (it would trace gate and eval calls too), so
  `tracing_enabled=True, auto_instrument=False, bypass_otel_for_tools=True`. Self Diagnostics (TypeScript SDK only).
  Issues and Experiments (Pro). The `raindrop-query` package, because it downgrades pydantic 2.14 → 2.12.5: the poller
  makes one GET with urllib, like the Voyage client in `models.py`.

**Demo (no new beat, the 3:00 holds):** 0:20 "Raindrop watches every live turn" · 0:35 after v+1, 3 s on the
Raindrop event (👎, correction, `lesson_shipped v+1`) · 2:20 one "silent failure" seam whose lineage root is a
Raindrop flag nobody 👎'd. It's pre-recorded if the signal latency is too long to show live (measure it first).
Numbers come from Atlas only: Raindrop-flagged episodes → lessons shipped / rejected / quarantined; signal latency.

**Setup ([you])**: raindrop.ai Hobby signup → write key `RAINDROP_WRITE_KEY` · Query API key (Settings → API
Keys) `RAINDROP_QUERY_API_KEY` · enable presets User Frustration, Attempted Prompt Injection, Repeated Tool Call Failures (dashboard only) · create the custom signal above. Done 12:50–12:55. There is no Task Failure or Jailbreaking preset.

**Order:** ~~(1) events + tool spans + 👍/👎/correction signals, with a test · (2) outcome signals~~ (done 12:05) · ~~(3) poller, with a test~~ (12:33), signal latency measured 13:32: **flag ≤ 32 s** on a real leak, flag → quarantine 22 s (MEMORY.md Numbers); a refused attack is never flagged → **live beat is possible** · (4) README line + `raindrop` lineage node in the live view.
**Fallback:** if the Query API or preset signals aren't on Hobby, or the latency is over 5 min, keep 1–4 (observability
and verification) and show one recorded Raindrop-sourced lesson.
**BOOST:** send one held-out run (A, 12 events, `kind=eval`, `passed`) → "Raindrop's custom signal agreed with the
ground-truth checks X/12" · Raindrop MCP (`claude mcp add raindrop --transport http https://mcp.raindrop.ai/mcp`) so
the `red-team` agent turns flagged live events into regression cases.
