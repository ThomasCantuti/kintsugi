# Kintsugi: an agent that gets stronger where it breaks

**Tsugi** is an always-on agent on Telegram that does real tasks (calendar, notes, reminders, contacts,
email outbox) on data in MongoDB Atlas. **Kintsugi** is its harness. Every mistake becomes a lesson that
edits the harness itself: **rules, context policies, guardrails, tool access**. A lesson ships only if it
fixes the failing case without breaking any train case that passed before. Every lesson is traced in a
lineage graph and can be revoked, together with everything built on it.

Built solo at the MongoDB **Harness Engineering & Model Wrangling** hackathon (#SFTechWeek, 2026-10-11),
Problem Statement 1: **Recursive Harnessing**.

> **What was built when:** the planning docs (`PLAN.md`, `TODO.md`, `MEMORY.md`, `docs/`, `.claude/agents/`)
> were committed before the event (`d07e6eb`, 10:26 PT). All code was written during the hackathon,
> starting 10:30 PT on 2026-10-11. See the commit history.

## How it works

```
Telegram (owner / stranger) ─► agent.run(genome vN, messages, world, tier)
                                 prompt = base rules + top-k learned lessons ($vectorSearch)
                                 tools filtered by tool_access[tier] · guardrail check before writes · tool-call repair
                                      │ episode ─► episodes
         👎 + correction ─────────────┤
                                      ▼
            dedup ($vectorSearch over past lessons) → learner proposes ≤ 3 delta lessons {section, delta, prediction}
            stranger-only source → quarantine → owner ✅ / ❌ in Telegram
                                      ▼
            gate: candidate genome on the failing case + up to 8 train cases that passed before
                  accept iff the case is fixed and nothing regresses (held-out never used)
                                      ▼
   transaction: genome vN+1 + lesson + lineage node ─► change stream ─► agent hot-swaps · live view (SSE)
   revoke(id): $graphLookup descendants → revoked → genome rebuilt without them → commit
```

- **Owner** = the Telegram id in `OWNER_TELEGRAM_ID`. Everyone else is a **stranger**, and lessons that
  come only from strangers are quarantined until the owner approves them.
- **Genome**: one versioned document with four sections: `rules`, `context_policies`, `guardrails`,
  `tool_access{owner, stranger}`. Lessons are deltas on top of a fixed base, never rewrites.
- **Model wrangling**: harness mechanisms around a cheap model (Nemotron). Tool-call repair validates and
  coerces arguments against the JSON schema, sends a targeted error back, and recovers tool calls the model
  wrote as plain text. A fallback chain switches models when one fails. `tool_access` is enforced in code.
  Every repair, fallback and block is counted in the episode trace. On the held-out baseline none of them
  fired (all counters 0): paid Nemotron Super made no malformed calls there.
- **Supervisor**: a stronger model reviews failed episodes and proposes lessons. Its critique is only a
  signal: the gate decides, and the chart is scored only by deterministic DB-state checks.

## Why MongoDB Atlas

One Atlas cluster is both the operational database and the vector database:

| Feature | Used for |
|---|---|
| Transactions | genome vN+1 + lesson + lineage node commit atomically |
| Change streams | the agent hot-swaps the genome; the live view updates over SSE |
| `$graphLookup` | revoke walks the lineage graph and removes every descendant lesson |
| Vector Search (`$vectorSearch`) | only the top-k relevant lessons go into the prompt (a small model isn't drowned in rules); new lessons are deduplicated against past ones and linked as lineage parents |
| `$rankFusion` (Atlas Search + Vector Search) | `note_search` is a hybrid of keyword and meaning matches |
| Per-`world` documents | eval cases run on seeded fixtures in their own world, in the same cluster |

Embeddings: Voyage `voyage-4-lite` through the Atlas model API.

## Evals

- `evals/cases.json`: 31 cases (19 train / 12 held-out) with DB-state checks (e.g. "one event, 90 min, not on
  a Friday"). They were drafted with Claude from Thomas's conventions (PLAN.md §5), and the held-out split was
  **frozen at commit `11c8ce0`** (blob `0b4dbc5`) before any learning run. The learner and the gate only
  read train; a test enforces it.
- `evals/redteam.json`: 10 stranger attacks (impersonation, fake rules in chat, pretexting for private notes,
  exfiltration through calendar writes, injections planted in notes and events) plus 1 control case where a
  legitimate stranger request must still work. A model that refuses everything scores 7/10, so we report
  attacks blocked plus the control result.
- `tests/`: deterministic loop tests with a scripted model (no tokens): repair, tool access enforced in code,
  gate accept/reject, held-out isolation, commit + hot-swap, quarantine, revoke cascade.

### Results

Filled only from stored runs (`runs` collection). Held-out: 12 cases × 2 trials, so n = 24.

| Bar | Model | Genome | Held-out passed (n) | Cost/task | Run |
|---|---|---|---|---|---|
| A0 | Nemotron Super | raw loop (no repair, fallback, retrieval or genome) | 8/24 (33%) | $0.0006 | R-ef7a04 |
| A | Nemotron Super | v0 (harness on) | 11/24 (46%) | $0.0006 | R-de79ec |
| B | Nemotron Super | vN (learned) | — | — | |
| C | Claude Sonnet 5.5 | v0 | — | — | |
| D | Claude Sonnet 5.5 | v0 + naive memory (every train correction pasted into the prompt) | — | — | |

**A0 vs A is noise, not a harness effect.** A0 scored 4/12 in both trials. A scored 4/12 on the same cases
in trial 1 and 7/12 in trial 2. At v0 the prompt is the same, and no repair, fallback or block fired.

## Run it

```bash
uv sync
cp .env.example .env        # MONGODB_URI, TELEGRAM_BOT_TOKEN, OWNER_TELEGRAM_ID, LLM_API_KEY, EMBED_API_KEY, …
uv run python -m kintsugi   # Telegram bot + API + live view on http://localhost:8000 (run only one instance)

uv run python -m kintsugi.evals --label A --split heldout           # --raw = A0 · --naive = D · --model … = C
uv run python -m kintsugi.evals --label RT --split redteam
uv run python -m kintsugi.evolve --rounds 2 --measure               # learn from failing train cases, held-out curve
uv run pytest -q
```

Any OpenAI-compatible endpoint works (`LLM_BASE_URL`: OpenRouter or NVIDIA). Model ids live in `.env`.

## Layout

```
kintsugi/   config · db · models · tools · genome · agent · evals · learner · gate · evolve · seed · telegram · api · __main__
evals/      cases.json (train + frozen held-out) · redteam.json
web/        index.html (live view: Tsugi, lineage, chart)
tests/      scripted-model tests
```

Plan and decisions: [PLAN.md](PLAN.md) · [MEMORY.md](MEMORY.md)
