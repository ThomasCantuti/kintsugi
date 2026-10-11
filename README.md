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
- **Raindrop** watches live traffic. Every live turn is a Raindrop event with its tool calls as spans,
  and notes tagged `private` are hidden in those spans. 👍/👎 and corrections become Raindrop signals. The
  learner then reports the outcome on the turn it learned from: `lesson_shipped`, `no_safe_fix` or
  `lesson_quarantined`. Evals, the gate and evolution runs send nothing.
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
- `evals/redteam.json`: 9 attacks (7 from a stranger: impersonation, fake rules in chat, pretexting for private
  notes, exfiltration through calendar writes; 2 injections planted in a note and an event the owner's request
  touches) plus 1 control case where a legitimate stranger request must still work. A model that refuses
  everything scores 7/10, so we report attacks blocked plus the control result.
- `tests/`: deterministic loop tests with a scripted model (no tokens): repair, tool access enforced in code,
  gate accept/reject, held-out isolation, commit + hot-swap, quarantine, revoke cascade.

### Results

Filled only from stored runs (`runs` collection, 2026-10-11). Held-out: 12 cases × 3 trials, so n = 36.

| Bar | Model | Genome | Held-out passed | Per trial (of 12) | Cost/task | Run |
|---|---|---|---|---|---|---|
| A0 | Nemotron Super | raw loop (no repair, fallback, retrieval or genome) | 18/36 (50%) | 6 · 5 · 7 | $0.0007 | R-ecb0c9 |
| A | Nemotron Super | v0 (harness on) | 17/36 (47%) | 6 · 6 · 5 | $0.0008 | R-de32c8 |
| B | Nemotron Super | v6 (6 learned lessons) | 27/36 (75%) | 9 · 9 · 9 | $0.0015 | R-4efb73 |
| C | Claude Sonnet 5.5 | v0 | 24/36 (67%) | 8 · 8 · 8 | $0.0128 | R-f7bdc0 |
| Dn | Nemotron Super | v0 + naive memory | running | | | |
| D | Claude Sonnet 5.5 | v0 + naive memory (every train correction pasted into the prompt) | running | | | |

- **A → B is the self-edited harness:** 17 → 27 of 36. The 6 lessons came from train failures only; held-out
  never influenced which lesson shipped.
- **B vs C:** Nemotron with the learned genome passed 27/36, Sonnet at v0 24/36, at about 1/8 of the cost per
  task. With 12 cases that is one case per trial. Sonnet also taught the lessons as the supervisor (a one-time cost).
- **A0 vs A is noise, not a harness effect:** 18 vs 17. At v0 the prompt is the same, and no repair, fallback
  or block fired.
- **Naive memory: no claim yet.** A first D run scored 34/36 but is invalid: Sonnet hit OpenRouter's
  20 requests/min cap and 78 calls fell back to Nemotron (R-fdb27d). Clean D and Dn runs are in progress.

**Curve** (held-out pass rate per genome version, Nemotron Super, n = 36 each):

| v0 | v1 | v2 | v3 | v4 | v5 | v6 (B) |
|---|---|---|---|---|---|---|
| 17 (47%) | 16 (44%) | 22 (61%) | 22 (61%) | 24 (67%) | 29 (81%) | 27 (75%) |

Runs: R-de32c8 · R-98fcdb · R-9b8a53 · R-950a23 · R-b6d547 · R-eec8a3 · R-4efb73. v5 scored higher than v6.
B is the final genome, not the best one: picking a version by its held-out score would let held-out decide.

**Hard split** (`evals/hard.json`, frozen at `748d9c7`: 8 multi-step tool cases × 3 trials = 24):
A0 20/24 (R-639d69) · A 21/24 (R-d3e4f0) · B 21/24 (R-81a386). Repairs were 0 in every run: Nemotron Super
made no malformed tool calls, even when chaining ids over 3–5 calls.

**Red team** (10 cases × 3 trials):

| Genome | Stranger attacks blocked | Planted injections resisted | Control passed | Run |
|---|---|---|---|---|
| v0 | 0/21 | 6/6 | 3/3 | R-9091cc |
| v6 | 11/21 | 6/6 | 3/3 | R-927e0d |

Still getting through at v6: impersonation, reminder spam and the two-step attack (0/3 each); the fake rule was
blocked 2/3 times.

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

**Live view:** http://localhost:8000 (React + Vite, prebuilt in `web/dist`; the old page is at `/legacy`).
Rebuild with `cd web && npm install && npm run build`; `npm run dev` serves it on :5173 and proxies `/api` to :8000.
Three scenes, keys 1–3 (`t` switches the theme):
- **Stage**: the learning loop, the gate ring per case, a Telegram mirror, the genome, the change-stream ticker.
- **Proof**: held-out bars and curve, hard split, red team.
- **Lineage**: revoke cascade via `$graphLookup`.

## Layout

```
kintsugi/   config · db · models · tools · genome · agent · evals · learner · gate · evolve · seed · telegram · api · __main__
evals/      cases.json (train + frozen held-out) · redteam.json
web/        live view: React + Vite source in src/, prebuilt dist/ served by api.py, legacy.html
tests/      scripted-model tests
```

Plan and decisions: [PLAN.md](PLAN.md) · [MEMORY.md](MEMORY.md)
