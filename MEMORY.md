# Project memory

Living facts and decisions. Append; don't rewrite history. Date every entry.

## Event
- **The Harness Engineering & Model Wrangling #SFTechWeek Hackathon**, host MongoDB, via Cerebral Valley.
- **Sun 2026-10-11**, San Francisco, in person, 9:00 → 20:00 (Partiful) / 22:00 (CV page). Teams ≤4.
- Theme: memory, persistence, self-evolving systems; harnesses that "adapt, remember, and operate reliably in production"; "go beyond the demo and get to deployment".
- Written requirement: "impactful projects built with **MongoDB Atlas**". Nothing else is mandatory.
- Prizes: 1st $7k + ElevenLabs Scale 3mo · 2nd $5k + Pro 3mo · 3rd $3k + Pro 3mo · **Raindrop RSI (Recursive Self Improvement) $3k**.
- Judges: Jackson Ferrigno (Raindrop), Bosco Albuquerque (AWS), Steffan Mejia (MongoDB), Aram S. (Modelence).
- Links: https://cerebralvalley.ai/e/mongodb-sftw-hackathon · https://partiful.com/e/SLKAGzRbpQ3d3TGM8pAU

## Official participant guide (read 2026-10-10)
- Venue: Shack15, 1 Ferry Building Suite 201, SF. Doors 9:00, kickoff 10:00, **hacking 10:30 → submissions due 17:00**, round 1 judging 17:00–18:45, finals 19:00–20:00, winners 20:15. Bring photo ID.
- **Problem statements** (must build ≥1): **1. Recursive Harnessing**: self-improving harness that evolves its own architecture (rules, context policies, guardrails, tool access) to fit a specific user/task. 2. Long Horizon Engineering: coherent memory over very long sessions, optimize long-term goals, learn from hard metric signals.
- **Rules:** finalists must build on the **MongoDB Atlas Sandbox** (email invite), else ineligible · **repos must be public** · solo allowed · **New work only**: demo only what was built during the hackathon; judges must clearly see what was made at the event, else disqualification.
- **Anti-projects (banned):** basic RAG, Streamlit apps, **dashboard as main feature**, AI mental-health advisor, personality analyzers, image analyzers, education chatbots, job screeners, nutrition/sports coaches, medical advice.
- **Submission:** form + **1-minute demo video** of what was built during the event + public repo.
- **Judging round 1** (~3 min live demo + 1–2 min Q&A): Impact 20% · **Technical Demo 35%** · Creativity 15% · **Implementation Difficulty 30%**. Round 2: top 6 on stage, same criteria, equal weights.
- Discord: https://discord.gg/YnZj6RDSX (#rules has on-day rules). Contact: gina@cerebralvalley.ai. (Wi-Fi creds in the guide; never commit them, the repo is public.)

## Constraints
- Solo (Thomas + Claude Code). Application approved.
- Tight budget: cheapest viable models, small eval slices, hard spend cap.
- No sponsor credits before Sunday. Don't force sponsor products; Atlas only.
- (2026-10-11, Thomas) **Atlas must be used as both operational DB and vector DB.** Required GenAI stack: application/UX · app framework/orchestration · operational DB + vector DB · foundation model LLM. Atlas is reachable from the Atlas CLI.

## Decisions
- 2026-10-09 D1 Concept: **Kintsugi**, the learning layer, inside **Kin**, an always-on Telegram claw. Bank voice agent dropped in favor of always-on personal agent (continuous real traffic).
- 2026-10-09 D2 Python 3.12 + uv, single asyncio process (bot + heartbeat/learner + FastAPI).
- 2026-10-09 D3 Telegram long polling (reactions = 👎 signal, inline buttons = quarantine approval).
- 2026-10-09 D4 Atlas M0 free tier; Voyage embeddings; litellm for models.
- 2026-10-09 D5 τ²-bench held-out split as the public exam (domain chosen by Spike 2).
- 2026-10-09 D6 Dashboard = static HTML + CDN libs served by FastAPI, no frontend build.
- 2026-10-09 D7 Start building now (user's call). Rules on pre-written code are silent; ask organizers.
- 2026-10-09 D8 No OpenClaw/NemoClaw dependency: own small claw in Python (we must own the loop to replay/gate). Ecosystem reach via Brain MCP server instead.
- 2026-10-09 D9 Framework: **Pydantic AI v2** (not Mastra: TS, and its memory/evals overlap our differentiator). Replaces litellm in D4.
- 2026-10-09 D10 **Second brain** in Atlas (`brain` collection) = foundation, exposed via FastMCP for any device/agent. Headline stays "learns skills safely".
- 2026-10-09 D11 Real tools via MCP: Gmail + Calendar on a dedicated test Google account. Gate uses recorded tool replay.
- 2026-10-09 D12 Models via OpenRouter: Kin = inkling:free (+fallbacks); gate/τ² = paid nemotron-3-super (cents); guard = nemotron-3.5-content-safety:free. Buy $10 credits. *(superseded by D14)*
- 2026-10-09 D13 **Own harness, no agent framework** (supersedes D9/Pydantic AI). `openai` SDK → OpenRouter + official `mcp` SDK. Mastra-inspired feature matrix, prioritized: docs/HARNESS.md.
- 2026-10-09 D14 Models: Kin = paid `claude-haiku-5.5` ($0.10/$0.50, candidate #1; bake-off vs GLM-5.3 Flash, Qwen3.8 Flash, Inkling free); cascade/reference = `claude-sonnet-5.5`; background/improver = `inkling:free`; guard = `nemotron-3.5-content-safety:free`.
- 2026-10-09 D15 Web search = Exa (Thomas has credits).
- 2026-10-09 D16 Cute companion character whose body shows learning state (concept pending pick). Hook: Meta Muse + OpenAI Dots (always-on cute agents, Sep 2026).
- 2026-10-10 D18 Companion = **Tsugi**: original porcelain spirit, gold seams = gated lessons (clickable → lineage), **sprout in its chest = memory rooted in MongoDB** (leaf per memory growth, glows on recall), wilting/crack = poison, gold repair = revoke. Not EVE (Disney IP, originality).
- 2026-10-09 D17 Proof = harness ablation table on τ² / τ³ (cheap + harness vs frontier vanilla). τ²-telecom excluded (saturated ~99%). *(superseded by D20)*
- 2026-10-11 D19 Official rules override: **no project code before 10:30 Sun** (supersedes D7); **Atlas Sandbox**, not M0 (supersedes D4); no 24/7 hosting, "alive since Friday" dropped. Plan rewritten for a 6.5h build (PLAN.md).
- 2026-10-11 D20 Proof = **hand-written cases** (`evals/cases.json`, ~18 train / ~12 held-out, DB-state checks, `correction` per case) + chart A/B/C/D (Nemotron v0, Nemotron vN, frontier v0, frontier + naive memory) + curve. τ² moved to LATER.
- 2026-10-11 D21 No "Break Tsugi" QR in Discord (Thomas's call). Self-improvement shown via live teach, afternoon evolution curve, red-team cases as the stranger, before/after replay.
- 2026-10-11 D22 Models: **Nemotron** (Thomas: only free model that worked at another hackathon). Agent `nemotron-3-super-120b-a12b:free`, fallbacks lightning/ultra free, improver ultra free; frontier reference Sonnet 5.5 only for bar C/D. `LLM_BASE_URL` configurable (OpenRouter or NVIDIA). $5 decision when the free cap (50/day) bites. Supersedes D14.
- 2026-10-11 D23 Cut items go to **LATER** (kept, built only if time is left): Brain MCP server, Gmail/Calendar, verifier + cascade, vector recall, goals, subagents, voice, τ². No Voyage, no guard model.
- 2026-10-11 D24 AWS Kiro: credits are for Kiro's coding agent only, not AWS services or a model API (Kiro FAQ in Discord). Not used.
- 2026-10-11 D25 Title = **Harness Engineering & Model Wrangling**: pitch both halves. Harness engineering = the genome edits itself, gated + revocable. Model wrangling = harness makes free Nemotron reliable; measured via bar A0 (raw loop) vs A (harness) and per-run wrangling counters (repairs, fallbacks, guardrail blocks, $/task, latency). BOOST: genome transfer across models.
- 2026-10-11 D26 **Supervisor model** (Thomas's idea): a smarter model judges live episodes, writes corrections for failed cases (hand-written `correction` becomes optional), and proposes lessons. Default Nemotron Ultra free → Sonnet 5.5 if credits. Rules: its critique is a signal only, the gate decides; chart scored only by deterministic checks; supervisor agreement vs ground truth measured; teaching cost reported separately from runtime $/task.
- 2026-10-11 D27 **Atlas Vector Search is MUST** (supersedes "vector recall" in LATER, D23): lesson retrieval (top-k lessons per message; k/threshold in `context_policies`, learnable), failure dedup (lineage parents), `note_search` hybrid `$rankFusion`. Embeddings: Atlas automated embedding with `voyage-4-lite` (public preview May 2026; verify on the Sandbox), fallback Voyage client-side. Setup via Atlas CLI.
- 2026-10-11 D28 **Modelence** ($50 sponsor credits): a hosting platform for backends, databases and scheduled jobs on AWS, built around its own TypeScript + React + MongoDB framework. The site doesn't mention LLM inference or Python support, so the credits don't pay for models. Use only to deploy Tsugi always-on (BOOST) **if** it runs a Python process with a custom start command and our Atlas Sandbox URI; ask the Modelence team at the venue. Judge Aram S. is from Modelence.
- 2026-10-11 D29 Video intro/outro footage = **Google Flow** (Veo, included in Thomas's Gemini Pro plan), generated by hand from Claude's prompts. Higgsfield dropped and uninstalled: refunds only within 7 days with zero credits used, renewals non-refundable, user reports of blocked cancellations. No browser automation of Flow (no official API; automation may break Google ToS) and no Veo via Gemini API (billed separately).

- 2026-10-11 D30 **Held-out frozen** (Thomas, ~11:30 PT) as drafted, not hand-edited: `evals/cases.json` at commit **11c8ce0**, blob `0b4dbc523e2eb47c73b460e09194017db8c3c9ab` (12 held-out / 19 train). Verify with `git hash-object evals/cases.json`. Before the freeze: only train runs (smoke, R-762ceb train-baseline), lessons = 0, held-out never read.
- 2026-10-11 D32 **Use Raindrop's SDK** (Thomas asked the judges ~11:40; they said "definitely use its SDK, it's free"). Supersedes "Raindrop optional" (docs/RESEARCH.md) and the don't-force-sponsors default, for Raindrop only. Free Hobby plan: 1,000 events/month (ingestion stops for the month at the cap), signals (7 presets + 1 custom), tracing, Query API, MCP; Issue Detection and Experiments are Pro only ($299/mo, 14-day trial). Python SDK `raindrop-ai` 0.0.75 adds 74 packages (traceloop/OTel), no downgrades; `raindrop-query` 0.1.14 would downgrade pydantic 2.14 → 2.12.5, so the poller calls `query.raindrop.ai/v1` with urllib. Role, hooks, demo: PLAN.md §12.
- 2026-10-11 D33 **Hard split frozen** (tool handling, for A0 vs A): `evals/hard.json` at commit **748d9c7**, blob `0efeda6f3a3adb9623464d42abffe2a4daf80dbf` (8 owner cases, 16 events Oct 15–21, 10 contacts; move or cancel by description via calendar_list ids, invites and emails by name via contact_lookup, two 2-turn cases). Checks cover only what each request asks, never learnable conventions. Verified without tokens: a scripted correct tool sequence passes all 8, a refusing model fails all 8. Frozen before any model run on it.
- 2026-10-11 D34 **Live view rebuilt in React + Vite** (Thomas approved the prototype https://claude.ai/artifact/JMwZ6ocNfWh41j12H5VkLi; dark "lacquer" theme default). Supersedes D6 (no frontend build) and relaxes CLAUDE.md rule 5 for `web/` only: React 19.3, Vite 8.3, Motion 14.1, TypeScript, fonts self-hosted (@fontsource, no CDN at runtime). `web/dist` is committed so `uv run python -m kintsugi` needs no Node; old page at `/legacy`. Backend for it: one `gates` doc per learning cycle (status proposing → running → accepted | rejected | quarantined | duplicate | no_candidates, with correction/tier/kind, `progress[]` per gate case, `version`); lessons keep `similar` scores from the Vector Search dedup; untested alternatives become `skipped`; `/api/state` adds live episodes, the latest cycle, lesson → version, per-trial pass counts, and skips runs that carry an `invalid` field; `GET /api/lineage` lists every node. Tailwind skipped: the prototype's CSS was ported as is.

## Open questions
- Modelence: Python / custom start command? External Atlas URI? Do credits cover anything besides hosting? (ask at the venue)
- **Live teach convention** (Thomas): v6 already knows the focus rule, so the demo teach needs an unlearned convention. Recommended:
  a fresh personal one (e.g. "investor calls are 30 min, titled 'Investor: …'", "never book over lunch 12–1"); alternative: revoke the
  focus lesson before stage and re-teach. Also: learning cycle 66–95 s vs ~55 s teach beat → time and speed up the gate.
- **Wrangling framing** (Thomas): data says Nemotron Super makes 0 malformed tool calls (held-out, hard split); weaker models fail on
  reasoning, not call format; provider 429s are real (Lightning). Recommended pitch: lead with recursive harnessing (A → B → curve),
  state the wrangling finding honestly, report counters only where non-zero.


## Numbers (fill only with measured values, with date + n)
- Held-out (n=12 cases × 2 trials = 24, model `nvidia/nemotron-3-super-120b-a12b` paid, 2026-10-11 ~11:40 PT): **A0 raw loop 8/24 (33%)** $0.0153 · **A v0 11/24 (46%)** $0.0152 · B vN — · C frontier v0 — · D frontier + naive memory —. Per trial: A0 (R-ef7a04) 4/12 + 4/12 · A (R-de79ec) 4/12 + 7/12; same 4 cases pass in every trial (draft-h2, private-h2, stranger-h2, generic-h1), A trial 2 adds tz-h1, remind-h1, team-h1. **A0 vs A: no measurable harness effect at v0; the difference is one trial (4/12 vs 7/12).** At v0 the prompt is identical in both modes (base items stay with genome=False, no lessons, strangers have all tools) and repairs/fallbacks/blocks are 0 in both. Trials vary even at temperature 0 → B vs A needs ≥2 trials (ideally 3), reported per trial.
- Held-out, **current tools** (10 tools, after a76ec33/4d44a85), 12 cases × 3 trials = 36, paid Nemotron Super, 2026-10-11 ~12:00–12:15 PT:
  **A0 18/36** (R-ecb0c9, per trial 6/5/7) · **A v0 17/36** (R-de32c8, 6/6/5). No harness effect at v0; repairs/fallbacks/blocks 0.
  (R-a0f9e8 A 18/36 ran with the stale v0 tool list; superseded by R-de32c8.)
- Hard split (D33, 8 cases × 3 trials = 24, v0, paid Nemotron Super): **A0 20/24** (R-639d69, per trial 6/7/7) · **A 21/24**
  (R-d3e4f0, 7/7/7). Repairs 0 in both: Nemotron Super makes no malformed tool calls even chaining ids over 3–5 calls.
  **R-25c209 (hard-A 9/24) is INVALID**: stale genome tool list hid calendar_move/cancel (bug fixed in 4d44a85).
- Weaker models on hard (1 trial each, n=8, v0): Nemotron Nano 30B A0 1/8 (R-461a5a) vs A 3/8 (R-c08570); Lightning A0 5/8 (R-50e0f9)
  vs A 7/8 (R-113b12). Repairs 0 everywhere: failures are reasoning (wrong time, max steps), not malformed calls; gaps are within noise.
  Lightning A0 lost 2 cases to `429 rate-limited upstream` (no fallback in the raw loop); no 429 hit the A run, so no rescue measured.
- Curve: evolution run (1 trial per version, old 8-tool registry, labels v1–v6 written by `evolve --measure`): v1 8/12 · v2 6/12 ·
  v3 7/12 · v4 9/12 · v5 10/12 · v6 9/12. **Superseded by the 3-trial batch** (labels v1–v5 + B at v6) launched ~12:40.
- **Curve, 3 trials per version** (held-out n=36, paid Nemotron Super, current tools, 0 repairs/fallbacks/blocks, ~12:20–12:30 PT):
  v0 17/36 47% (A, R-de32c8) · v1 16/36 44% (R-98fcdb, 5/5/6) · v2 22/36 61% (R-9b8a53, 8/7/7) · v3 22/36 61% (R-950a23, 8/7/7) ·
  v4 24/36 67% (R-b6d547, 9/8/7) · v5 **29/36 81%** (R-eec8a3, 10/9/10) · v6 = **B 27/36 75%** (R-4efb73, 9/9/9). $0.03–0.06 per run.
- Red-team (10 cases × 3 trials = 30): **v0 9/30** (R-9091cc, 3/3/3) → **v6 20/30** (R-927e0d, 6/7/7). Hard split at v6: 21/24 (R-81a386, 7/7/7) = same as v0, no regression.
- **INVALID frontier runs** (do not chart): R-e37e9a "C" 18/36 and R-fdb27d "D" 34/36: Sonnet hit OpenRouter's **new-account cap of
  20 req/min per model** and 73/78 calls fell back to free Nemotron (so R-fdb27d is mostly Nemotron + naive memory). R-6cd9fc "C" 8/36:
  fallback off, trial 1 = 8/12 on Sonnet, trials 2–3 all 429 errors. Fixes: `--model` disables fallback; models.chat waits out 429s.
- Evolution (2 rounds on train, Sonnet supervisor, paid Nemotron): genome v0 → **v6**, 6 lessons accepted, 11 rejected by the gate,
  10 untested alternatives marked `skipped`. Lessons: focus blocks (rules), reminders 15 min before (rules), check calendar for
  conflicts (context_policies), draft unless "send it now" (guardrails), never reveal private notes (guardrails), strangers → take a
  message (rules). Spend by ~12:40: $0.55 of $10.
- Supervisor agreement with ground-truth checks: **19/19** (Sonnet 5.5 on train run R-762ceb, v0, n=19 cases with a hand-written correction, $0.041). Held-out has no `correction` field, so `--judge` on held-out gives 0/0.
- Train v0 (n=19, 1 trial, paid Nemotron): 7/19 pass, $0.0082 (run R-762ceb, the gate's v0 baseline).
- Costs measured: Nemotron Super paid ≈ $0.0002/request (~1.2k in / 200 out tokens); one learning cycle (Sonnet propose + gate) ≈ $0.015.
- Live: episodes — · lessons accepted/rejected/quarantined — · revokes —
- RSI: improver acceptance rate per playbook version —

## Learnings
- (append gotchas here: API quirks, M0 limits hit, things that broke)
- 2026-10-11 Sandbox = project "thomas.cantuti@gmail.com's Sandbox Project" (6acbc97224b62b0067006c45), Cluster0 **M10 AWS us-west-1**, MongoDB 8.0. Venue IP 12.94.170.82 added to the access list (hotspot = new IP → `atlas accessLists create <ip> --projectId …`).
- 2026-10-11 Only ONE `python -m kintsugi` may run: two instances → Telegram `Conflict: terminated by other getUpdates request`. An orphan ignored SIGTERM; needed `kill -9`.
- 2026-10-11 OpenRouter `/api/v1/key` shows `free_model_daily_requests` (50/day on free tier). Voyage via `https://ai.mongodb.com/v1` works (voyage-4-lite, 1024 dims). Nemotron embed on OpenRouter = 2048 dims.
- 2026-10-11 v0 baseline behaviour (Nemotron Super free): asks clarifying questions unless told to assume defaults (added to BASE rules); books 2h focus on Friday; sends email without a draft.
- 2026-10-11 Vector Search verified on the Sandbox (8.0.34): `lessons_vec`, `notes_vec` (1024 dims, voyage-4-lite) + `notes_text` (Atlas Search, lucene.english). **`$rankFusion` works on 8.0.34.** Index build ≈ 45 s, so `__main__` creates them at startup. A freshly inserted note takes ~1 s to become searchable, so `note_search` falls back to keyword regex when hybrid returns nothing (eval worlds are seeded right before the agent runs). Hybrid returns up to 5 notes for any query (6-note worlds → most notes, incl. private).
- 2026-10-11 **Gate bug fixed**: lesson retrieval filtered `$vectorSearch` by `status: active`, so a candidate under test (status `candidate`) was dropped from the prompt → the gate could never accept a rules/context_policies lesson (guardrails skip retrieval). Now retrieval filters by the running genome's lesson ids (`_id` added as a filter field on `lessons_vec`). Also correct for `--version N` runs.
- 2026-10-11 Propose prompt: alternatives must each cover EVERY part of the feedback (the gate tests each alone). Before: focus-01's feedback (Deep work 90 min mornings + never Fridays) was split across 3 lessons, each fixing half → all rejected. After: first try accepted → v1 (7/7 regression).
- 2026-10-11 Switched to paid models with $10 OpenRouter credits (key hard limit $10): agent `nemotron-3-super-120b-a12b` (paid; free super + lightning as fallbacks), supervisor `claude-sonnet-5.5`. Free tier = 50 req/day and 20/min, too tight for the gate (16–20 requests per burst).
- 2026-10-11 **Stored genomes snapshot their tool lists**: v0–v3 denied tools added later (calendar_move/cancel) to every tier, so the harness scored 9/24 on hard vs the raw loop's 20/24. Fix (4d44a85): `genome.allowed_tools()` gives registry tools a genome never knew BASE access; new versions store `tools_known`. Rule: adding a tool must not need a genome migration.
- 2026-10-11 Lightning (`nemotron-3.5-lightning`, paid) returned `429 temporarily rate-limited upstream` (CoreWeave shared pool) on 2 of 8 raw-loop cases ~12:16 PT.
- 2026-10-11 Shell gotcha: zsh doesn't word-split `$E` (`E="uv run …"; $E args` → command not found). Use a bash script or a function for batches.
- 2026-10-11 Several Claude sessions share this working tree and the `kintsugi_test` DB: concurrent pytest runs drop each other's DB mid-test (spurious failures). Announce pytest runs; stage only your own hunks.
- 2026-10-11 Raindrop: the `event_id` we pass (the episode id) is kept, so Query API events map straight back to episodes. `GET query.raindrop.ai/v1/events` (Bearer Query key, `timestamp[gte]=`) lists each event's signals and tool calls. A signal exists in the project only once it is used or enabled (only "Thumbs up" until the presets are switched on). The Python SDK logs to a NullHandler (failed sends were silent until we attached a handler), and `track_tool` needs `tracing_enabled=True` (`bypass_otel_for_tools=True` posts spans directly). python-telegram-bot's 5 s connect timeout lost a reply on venue Wi-Fi → 20 s.
- 2026-10-11 Several Claude sessions share this tree: commit only your own hunks through a temporary index (`GIT_INDEX_FILE=… git read-tree HEAD`, `git update-index --cacheinfo`), announce pytest (shared `kintsugi_test` DB, overlapping runs fail at random) and send "pytest done". Mark bad runs `invalid` in Atlas instead of relying on "latest run wins" (the live view skips them).
- 2026-10-11 The gate lists the past cases up front only when the genome version's baseline is cached; a missing baseline is still measured after the fix check, so an unfixed candidate never pays for regression runs.
