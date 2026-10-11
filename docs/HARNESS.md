# Kintsugi Harness: spec

> **2026-10-11:** background research from before the rules were published. For today, PLAN.md §3 (module
> contracts), §5 (evals, chart A–D) and §9 (MUST/BOOST/LATER) override the priorities and the τ² ablation below.

Our own harness, no agent framework. Goal: **a cheap model inside our harness matches or beats a
frontier model inside a vanilla harness**, measured on held-out tasks (see §4). Model-agnostic:
any OpenRouter model (Claude, GPT, Gemini, open weights) by config.

## 1. Why a harness can beat a bigger model (evidence)
- **ACE, Agentic Context Engineering** (arXiv 2510.04618, ICLR 2026): an evolving "playbook" of
  strategies/error patterns in context gave double-digit gains on AppWorld; reported to let open
  DeepSeek-V3.1 match IBM CUGA (GPT-4.1, top of the leaderboard), and beat it on the challenge split.
  Key lesson: **incremental deltas, never wholesale rewrites** (a rewrite collapsed 18k tokens/66.7% → 122 tokens/57.1%).
- Small models mostly fail on: malformed tool calls, losing the thread in long contexts, skipping
  policy checks, picking the wrong tool among many. Each has a harness fix (below).
- Frontier harnesses (Claude Code, ChatGPT/Dots, Muse, OpenClaw) learn facts at best, with no tests,
  no provenance, no undo, and are locked to their own models. That gap is our product.

## 2. Feature matrix (Mastra inventory → ours)
P0 = must ship · P1 = should · P2 = stretch · ✗ = skip (doesn't serve demo or proof)

| Area | Feature | Pri | Our twist |
|---|---|---|---|
| Models | Provider router (OpenRouter, OpenAI-compatible) + fallback chain + retries | P0 | one client for Claude/GPT/Gemini/open |
| Models | Prompt caching + per-call token/cost meter + hard budget cap | P0 | cost/task is a first-class metric |
| Models | **Cascade**: cheap first, escalate to frontier when verifier fails | P1 | near-frontier accuracy at near-cheap cost |
| Agent | Loop, streaming events, structured output, parallel tool calls | P0 | events feed Telegram, dashboard, traces |
| Agent | **Tool-call repair**: validate args vs schema, targeted error, retry | P0 | #1 cheap-model failure mode |
| Agent | **Verifier**: pre-flight check before write tools / final answer | P1 | policy checks small models skip |
| Agent | Planning (todo list) for multi-step tasks | P1 | |
| Agent | Subagents (isolated context): research agent on Exa | P1 | returns summary + citations only |
| Tools | Typed tools (type hints/pydantic → JSON schema), risk levels read/write/dangerous | P0 | |
| Tools | MCP client (Gmail, Calendar) via official `mcp` SDK | P1 | |
| Tools | **Dynamic tool + skill exposure** (only relevant ones shown) | P1 | fewer distractions for small models |
| Skills | Skills index in prompt, body loaded on demand (`load_skill`) | P0 | **skills are learned, gated, revocable** |
| Memory | Threads/history, working memory (profile doc) | P0 | provenance + trust on every edit |
| Memory | Semantic recall: hybrid `$rankFusion` (Voyage vectors + text) | P0 | |
| Memory | Observational memory: extract facts from interactions | P1 | stranger-derived facts → quarantine |
| Memory | Memory processors: token-budgeted context, compaction, tool-output truncation | P0 | "context engine" |
| Memory | Rerank (Voyage rerank) | P2 | |
| Guardrails | Input processor: trust tagging; guard model on untrusted content | P0 / P1 | |
| Guardrails | Output processor: secret/PII leak check when replying to strangers | P1 | |
| Guardrails | Pre-tool hooks: policy check; HITL approval for dangerous tools | P0 / P1 | approvals = training signal |
| Durability | Checkpoint per step in Mongo, resume after crash | P1 | |
| Durability | Idempotency keys for write tools (unique index) | P2 | exactly-once side effects |
| Background | Heartbeat, schedules, reminders | P0 | always-on proof |
| Background | **Goals**: recurring background objectives (Dots-style) | P1 | failures feed the learner |
| Evals | Datasets (`cases`, `cases_heldout`), rule checks + LLM-judge scorers | P0 | |
| Evals | **Gate** (no-regression verdicts) + recorded tool replay ("time travel") | P0 | the thesis |
| Evals | Multi-turn evals (τ² user simulator), experiments/ablations runner | P1 | the proof slide |
| Observability | Spans (model/tool/memory/gate) with tokens + cost → `traces`; metrics time-series; feedback (👎) | P0 | dashboard reads it live |
| Versioning | Genomes = versioned harness config, auto-written by learner, revertible | P0 | Mastra Editor, but self-edited |
| Learning | Signals → lessons → gate → commit; lineage blame/revoke; RSI playbook | P0 / P1 | **nobody else has this** |
| Channels | Telegram · dashboard chat · MCP server (Brain + skills) | P0 / P1 / P1 | any device, any agent |
| Server | FastAPI + SSE; bearer token on API/MCP | P0 / P1 | |
| Voice | TTS replies (ElevenLabs) | P2 | |
| ✗ | Code mode, workflow DSL/control flow, agent networks, A2A/ACP, sandboxes/browser/computer/LSP, auth providers, deployers, OTel exporters, GraphRAG, chunkers | ✗ | agent loop + jobs + lineage cover what we need |

## 3. Modules (one package, fewest files)
```
kintsugi/
  config.py    env, model ids, budget
  db.py        Atlas client, collections, indexes
  models.py    Model protocol → OpenRouterModel (fallbacks, retries, caching, cost) + ScriptedModel (tests)
  tools.py     @tool → JSON schema, risk levels, registry, MCP toolsets
  context.py   context engine: genome + working memory + skills index + recall + history, budget, compaction
  memory.py    brain docs + memories + hybrid search + provenance/trust + lineage ($graphLookup)
  agent.py     loop: processors, tool repair, verifier, cascade, approvals, checkpoints, events
  trace.py     spans + metrics
  jobs.py      heartbeat, schedules, reminders, goals
  learner.py   signals → failures → proposals → commit; playbook (RSI)
  gate.py      cases, scorers, replay runner, verdicts, ablation runner
  telegram.py  channel
  api.py       FastAPI: SSE, dashboard, chat, revoke/why, MCP server mount
  main.py      one process
```

## 4. The proof: ablation table (same frozen held-out split, same user simulator, 2 trials)
| Config | Model | pass^1 | $/task | % escalated |
|---|---|---|---|---|
| A vanilla loop | cheap (e.g. Haiku 5.5) | | | |
| B + context engine + tool repair | cheap | | | |
| C + verifier | cheap | | | |
| D + learned skills (after evolution on train) | cheap | | | |
| E + cascade | cheap → frontier on demand | | | |
| R vanilla loop (reference) | frontier (Sonnet/Opus 5.5) | | | |
Benchmark: τ² airline/retail or τ³ banking_knowledge (telecom is saturated, ~99%), picked by Spike 2.
R comes from the public leaderboard when the model is listed, else a small-slice run (or AWS Bedrock credits on Sunday).
Only measured numbers go on the slide (CLAUDE.md rule 2).
