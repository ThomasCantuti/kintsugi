# Research notes (2026-10-09)

Reference material. Verify APIs against current docs before coding (they're previews and move fast).

## NYC edition (same hackathon, 2026-09-26): what won
Gallery: https://cerebralvalley.ai/e/mongodb-nyc-hackathon/hackathon/gallery.md (98 projects, most were "self-improving harness").
- **1st Ripple**: circuit boards from plain English; hidden checker the agents never read; harness revises itself; "0/4 → 3/4 on held-out specs with the same model". Next.js UI + worker. https://github.com/jovianw/ripple
- **2nd Offload**: "an agent harness that sleeps". REM = Replay·Evolve·Merge; day: durable runs, checkpoints, exactly-once effects ledger; night: merge memories, distill skills, evolve harness on held-out gym with no-regression gate; morning: one "ask" for new authority. Heavy Mongo: Vector Search + autoEmbed (voyage-4), `$rankFusion`, change streams → SSE, TTL, time-series, unique indexes, transactions. README admits fixtures, not real Gmail. https://github.com/SpectrrT/MongoDB_HarnessHack
- **3rd Morgadarsha**: local-first computer use; verify outcomes; policy changes must pass deterministic evals; Mongo as shared memory.
- Finalists: Da Vinci (recursive CAD), CyclopsDiary (Meta glasses → factory memory), Sightline (learns context for a fast model; tested on an unseen storm; Mongo hides answers so it can't cheat).
- Pattern: verifiable domain + hidden held-out checks + same-model improvement number + visual demo.
- Non-placing security entries: Antibody, Crucible, Immune-Harness, Recall Gate. Security alone didn't win, so our safety angle rides on top of measured capability gains.

## Always-on claws
- **OpenClaw** (ex Clawdbot/Moltbot): always-on personal agent in messaging apps; memory = MEMORY.md/SOUL.md files.
  Memory plugins own `plugins.slots.memory` (e.g. `@openclaw/memory-lancedb`); hooks like `before_prompt_build`;
  slot claimed via `api.registerMemoryCapability(...)` (third-party README; verify). → P2 adapter path.
- **NemoClaw** (NVIDIA, GTC 2026-03-16): OpenClaw + OpenShell sandbox/policy; alpha.
- **Security hook for the pitch**: CSA research note (Jun 2026): no boundary between trusted config and untrusted content;
  poisoned SOUL.md/MEMORY.md persists across restarts and "resists simple file-revert remediation". Palo Alto: time-shifted
  injection / memory poisoning / logic bombs. Reported 21k+ exposed instances, malicious ClawHub skills.
  https://labs.cloudsecurityalliance.org/research/csa-research-note-openclaw-indirect-prompt-injection/

## τ²-bench / τ³-bench (Sierra)
- Repo: https://github.com/sierra-research/tau2-bench (v1.0 = τ³: adds voice + `banking_knowledge`). Python 3.12–<3.14, `uv`.
- Domains/base sizes: airline 50 · retail 114 · telecom 114. `split_tasks.json` holds train/test splits.
- Grading: expected actions / final DB state (`evaluation_criteria`, `reward_basis`). CLI: `tau2 run --domain airline --agent-llm … --user-llm … --num-trials … --num-tasks …`.
- Gym API (drive it with our own harness):
  ```python
  register_gym_agent()
  env = gym.make(TAU_BENCH_ENV_ID, domain="airline", task_id=task_id)  # user simulator plays the customer
  obs, info = env.reset()            # info: tools, policy
  obs, reward, terminated, truncated, info = env.step(action)  # action = text or tool call
  ```
- Leaderboard (pass^1): τ² top ≈ 85–88% (Qwen3.5-397B, Gemini 3.0 Pro, Opus 4.5); τ³-Banking top 55.2% (Opus 5: 48.7%).
- **tau2-bench-verified** by Amazon AGI (fixed tasks): https://github.com/amazon-agi/tau2-bench-verified (nice nod to the AWS judge).

## MongoDB Atlas M0 (free) limits
- 0.5 GB storage · 100 ops/s (throttled, not rejected) · 500 connections · 50-stage pipelines · 500 collections · 1 free cluster/project.
- Change streams supported (namespace filters: strings/regex only). No dedicated search nodes. Vector Search on M0: verify in Spike 1.

## Atlas Agent Engine (public preview, ~2026-10-09): optional
- Runtime + memory + governance on Atlas (AWS). CLI: `agentengine create --template hello-world-agent` → `agentengine dev up` → `init/secret set/build/deploy`. Templates in Python + TS: https://github.com/mongodb/agent-engine-examples
- Memory SDK (Python):
  ```python
  from agentic_platform_memory import Memory, MemoryRequestContext
  chat = Memory(api_key=..., project_id=...).bind(MemoryRequestContext(user_id="u1", session_id="t1"))
  chat.save_semantic(label=..., text=...); chat.search_semantic(q)
  chat.save_episode(title=..., content=...); chat.search_episodes(q)
  chat.save_procedure(procedure=..., description=..., content=...); chat.discover_procedures(q)
  chat.save_taxonomic(domain=..., term=..., definition=...); chat.search_taxonomic(q, domain=...)
  chat.build_context(query=..., enabled_sources={"episodic","semantic","procedural"})
  ```
  Extraction is async; service-account invocations share one memory user scope. No metadata field shown → lineage stays in our own collections.

## Raindrop: optional (RSI prize judge)
- Production agent monitoring: signals, issues, experiments, trajectories; TS/Python SDKs + HTTP API; hosted MCP; `raindrop cloud setup` writes `RAINDROP_WRITE_KEY`.
- Raindrop 2.0 (2026-06-03) "Self-Healing Agents": detect failure → coding agent fixes → failure becomes eval. Our loop is that, autonomous and recursive.

## Judges → what they likely reward
- Raindrop: production failures caught and fixed automatically; real RSI with evidence.
- MongoDB: Atlas as the agent's brain, used idiomatically (Vector Search, change streams, `$graphLookup`, txns); Agent Engine if cheap.
- AWS: deployable, secure, governed; runs in production.
- Modelence (TS+Mongo framework for coding agents): solid engineering, schema discipline, shipping fast.

## LLMs on OpenRouter (checked 2026-10-09 via /api/v1/models + /endpoints)
19 free models. Candidates with tools support (free uptime last 24h · cheapest paid in/out per M):
| Model | Free uptime | Paid | Notes |
|---|---|---|---|
| thinkingmachines/inkling (975B MoE, 41B active, Apache 2.0) | 100% | $0.95 / $4.05 | MCP Atlas 74.1% (Decrypt), SWE-bench V 77.6%; best Western open-weights tool use; GLM 5.2 / Kimi K2.6 still lead some evals |
| thinkingmachines/inkling-small | 100% | $0.45 / $1.20 | lighter fallback |
| nvidia/nemotron-3-ultra-550b-a55b | **56%** | $0.50 / $2.20 | τ²-telecom 83.3% (Artificial Analysis); free endpoint unreliable |
| nvidia/nemotron-3-super-120b-a12b | 100% | $0.08 / $0.40 | cents-cheap workhorse for gate/τ² |
| nvidia/nemotron-3.5-lightning | 100% | $0.02 / $0.12 | quality unknown |
| google/gemma-4-31b-it | 100% | $0.09 / $0.34 | weaker agentic scores reported |
| nvidia/nemotron-3.5-content-safety | free | n/a | guard model, no tools; use as untrusted-content screen |
Free limits: 20 req/min; 50 req/day (<$10 credits ever) or 1,000 req/day (≥$10). 429 on excess.
Free tiers may log/train on prompts; keep personal data out.
Other free APIs are unstable in 2026 (Gemini free tier Flash-only since Apr; Groq/Cerebras free catalogs shrank).

## Pydantic AI v2 (ctx7 /pydantic/pydantic-ai/v2.0.0)
```python
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset            # built on fastmcp
toolset = MCPToolset('http://localhost:8000/mcp')  # or MCPToolset(StdioTransport(command=..., args=[...]))
agent = Agent('<provider:model>', toolsets=[toolset])
result = await agent.run('...')                   # result.output, message history for replay

# token-free tests / gate dry-runs
from pydantic_ai.models.function import FunctionModel, AgentInfo
from pydantic_ai.models.test import TestModel
with agent.override(model=FunctionModel(fn)):     # fn(messages, info) -> ModelResponse(parts=[ToolCallPart|TextPart])
    ...
```
Also: `/pydantic/pydantic-ai-harness` (official capability library: tools, hooks, sub-agents). Verify the OpenRouter model string and fallback API when coding.

## Cute always-on agents (Sep 2026): the pitch hook
- **Meta Muse** (Connect, Sep 2026): personal agent across phone + Meta Glasses; doll-like avatars, default "Jolly" (cream, beady eyes, smile), customizable; Muse Charm keychain ships Dec 2026. Critique: "It's cute. It's cuddly. And it wants all your data."
- **OpenAI Dots** (DevDay 2026-09-29): always-on agents pursuing goals in the background; blobby mascots (triangle with bow tie, bunny with headphones, cloud with beret); "start with your primary dot, give it a name"; runs on GPT-6 Astra ($5/$25 per M); Pro rollout.
- Sources: https://techcrunch.com/2026/09/29/openai-launches-dots-its-bubbly-agentic-avatar/ · https://www.fastcompany.com/91615068/openai-dots-agent-crew-of-friendly-mascots · https://www.creativebloq.com/ai/metas-new-ai-avatar-is-making-me-feel-infantilised · https://www.dexerto.com/entertainment/meta-reveals-pocket-sized-ai-companion-that-looks-like-a-tamagotchi-3412049/

## Paid models on OpenRouter (2026-10-09, $/M in · out · cache read)
Cheap: claude-haiku-5.5 0.10·0.50·0.01 · glm-5.3-flash 0.04·0.50·0.012 · qwen3.8-flash 0.15·0.47·0.016 · mimo-v2.6-flash 0.14·0.28 · mimo-v2.6-pro 0.43·0.87·0.004 · step-3.5-flash 0.10·0.30 · deepseek-v4.1-flash 0.30·1.20 · minimax-m3 0.30·1.20 · kimi-k2.6 0.46·2.45 · nemotron-3-super 0.08·0.45
Frontier: claude-sonnet-5.5 2·10·0.10 · claude-opus-5.5 4·20·0.20 · gpt-6.1-sol 2·10 · gpt-6-astra 5·25 · gemini-3.8-flash 0.75·3.75 · grok-4.7 2·6
τ²-telecom is saturated (GLM-5.2 ~99.1%) and marked legacy by Artificial Analysis → use airline/retail or τ³ banking_knowledge (top 55%).
No independent benchmark scores found for Haiku 5.5 / GLM-5.3 Flash / Qwen3.8 Flash → measure in Spike 2.

## Harness evidence
- ACE (arXiv 2510.04618, ICLR 2026): evolving playbook (Generator/Reflector/Curator), incremental deltas; double-digit AppWorld gains; reported open DeepSeek-V3.1 matching IBM CUGA (GPT-4.1). Verify tables before quoting exact numbers.
- Mastra feature inventory (mastra.ai/llms.txt, 2026-10-09): agents/tools/structured output/HITL/guardrails/processors/code mode/subagents/skills/channels · memory (history, working, semantic recall, observational, processors, multi-user threads) · workflows (control flow, snapshots, suspend/resume, time travel, schedules) · networks/supervisor · harness (durable agents, background tasks, goals, schedules, signals) · evals (scorers, gates, multi-turn, datasets, experiments) · observability (tracing, metrics, feedback, exporters) · MCP/A2A/ACP · voice · RAG · model router · server · studio/editor/versioning · auth · sandboxes · storage. Our prioritized subset: docs/HARNESS.md.
