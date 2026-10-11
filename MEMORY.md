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

## Open questions
- Held-out freeze
- Modelence: Python / custom start command? External Atlas URI? Do credits cover anything besides hosting? (ask at the venue) commit hash: —

## Numbers (fill only with measured values, with date + n)
- Held-out (n=?): A0 Nemotron raw loop — · A Nemotron v0 — · B Nemotron vN — · C frontier v0 — · D frontier + naive memory — (trials, $/task)
- Curve: held-out pass rate per genome version —
- Supervisor agreement with ground-truth checks: — / n
- Live: episodes — · lessons accepted/rejected/quarantined — · revokes —
- RSI: improver acceptance rate per playbook version —

## Learnings
- (append gotchas here: API quirks, M0 limits hit, things that broke)
