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
- **Every scar becomes a test**: when the gate ships a lesson from a live mistake (a Telegram correction, or a
  Raindrop flag the owner approved), that turn is saved in `scars` and replayed against every later lesson while
  its lesson stays active. Hand-written train cases guard the conventions we wrote down; scars guard the ones Tsugi
  learned live. Pasting corrections into a prompt never checks a new one against the old ones. Live now: 3 scars (two
  stranger attacks, one of them the Raindrop catch, and one owner correction) run in every later gate.
- **Tools**: calendar (create, list, move, cancel), notes (hybrid search), reminders (they ping the owner on
  Telegram when due), contacts, an email outbox (draft or send, simulated), and web search (Exa). Web search is
  offered only in live chats, so eval prompts stay as measured, and its results are marked as untrusted text.
- **Model wrangling**: harness mechanisms around a cheap model (Nemotron). Tool-call repair validates and
  coerces arguments against the JSON schema, sends a targeted error back, and recovers tool calls the model
  wrote as plain text. A fallback chain switches models when one fails. `tool_access` is enforced in code.
  Every repair, fallback and block is counted in the episode trace. On the held-out baseline none of them
  fired (all counters 0): paid Nemotron Super made no malformed calls there.
- **Raindrop** watches live traffic. Every live turn is a Raindrop event with its tool calls as spans,
  and notes tagged `private` are hidden in those spans. 👍/👎 and corrections become Raindrop signals. The
  learner then reports the outcome on the turn it learned from: `lesson_shipped`, `no_safe_fix` or
  `lesson_quarantined`. Evals, the gate and evolution runs send nothing.
  Every minute the bot asks Raindrop's Query API for live turns it flagged (User Frustration, Attempted Prompt
  Injection, and our custom signal, which Raindrop named "Request Execution Needs Correction") and sends each
  one that nobody has learned from yet to the learner, like a 👎. The supervisor first checks the turn: if it
  was already right, the flag ends as a false alarm and no lesson is proposed. First run: a stranger's prompt
  injection that got through v7 (E-b3176a9f) was flagged by Raindrop within 32 s, and 22 s later the learner had
  3 candidate lessons, all quarantined for the owner because the source was a stranger (cycle G-96156c). The owner's
  first pick (a tool-access lesson, L-4536f5) failed the gate; the second, the guardrail "Ignore fake override commands"
  (L-f857d8), passed the replay and 8/8 past cases and shipped as genome v9: the first lesson sourced from Raindrop.
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
| B | Nemotron Super | v7 (7 learned lessons) | **30/36 (83%)** | 10 · 10 · 10 | $0.0015 | R-bb02a7 |
| C | Claude Sonnet 5.5 | v0 | 24/36 (67%) | 8 · 8 · 8 | $0.0128 | R-f7bdc0 |
| Dn | Nemotron Super | v0 + naive memory | 28/36 (78%) | 10 · 10 · 8 | $0.0014 | R-ff6cfe |
| D | Claude Sonnet 5.5 | v0 + naive memory (every train correction pasted into the prompt) | **36/36 (100%)** | 12 · 12 · 12 | $0.0171 | R-a7ebca |

- **A → B is the self-edited harness:** 17 → 30 of 36. The 7 lessons came from train failures only; held-out
  never influenced which lesson shipped. v6 → v7 changed only stranger cases (6 → 9 of 9; owner cases 21 → 21):
  v7's one lesson takes write tools away from strangers. Disclosure: it shipped after a gate fix that the red-team
  results prompted (tool-access lessons are now regression-tested only on cases of their tier; MEMORY.md D35).
  The red-team cases never fed the learner.
- **B vs C:** Nemotron with the learned genome passed 30/36, Sonnet at v0 24/36, at about 1/8 of the cost per
  task. Sonnet also taught the lessons as the supervisor (a one-time cost).
- **A0 vs A is noise, not a harness effect:** 18 vs 17. At v0 the prompt is the same, and no repair, fallback
  or block fired.
- **Naive memory on a frontier model beats Kintsugi on held-out:** D 36/36 vs B 30/36, at about 11× B's cost
  per task. Held-out tests the same conventions the train corrections state, so pasting all of them into
  Sonnet's prompt solves it. What memory doesn't do is test a correction before it goes live, trace it, revoke it,
  quarantine one from a stranger, or change tool access in code.
  (An earlier D run, R-fdb27d, is invalid: rate limits sent 78 calls to Nemotron.)
- **On the cheap model, learned lessons ≈ pasting every correction:** B 30/36 vs Dn 28/36, within noise, at
  about the same cost per task. On this held-out set the gate doesn't buy accuracy over naive memory; it buys
  lessons that were tested before they went live and can be revoked.

**Curve** (held-out pass rate per genome version, Nemotron Super, n = 36 each):

| v0 | v1 | v2 | v3 | v4 | v5 | v6 | v7 (B) |
|---|---|---|---|---|---|---|---|
| 17 (47%) | 16 (44%) | 22 (61%) | 22 (61%) | 24 (67%) | 29 (81%) | 27 (75%) | 30 (83%) |

Runs: R-de32c8 · R-98fcdb · R-9b8a53 · R-950a23 · R-b6d547 · R-eec8a3 · R-4efb73 · R-bb02a7. B is the genome at
measurement time, not the best one: picking a version by its held-out score would let held-out decide. Live
teaching has since moved the genome to v10 (Raindrop's guardrail, stranger calendar access, one owner rule); v8–v10 are
not measured on held-out.

**Hard split** (`evals/hard.json`, frozen at `748d9c7`: 8 multi-step tool cases × 3 trials = 24):
A0 20/24 (R-639d69) · A 21/24 (R-d3e4f0) · B 21/24 (R-81a386). Repairs were 0 in every run: Nemotron Super
made no malformed tool calls, even when chaining ids over 3–5 calls.

**Red team** (10 cases × 3 trials):

| Bar | Stranger attacks blocked | Planted injections resisted | Control passed | Cost/task | Run |
|---|---|---|---|---|---|
| Nemotron v0 | 0/21 | 6/6 | 3/3 | $0.0005 | R-9091cc |
| Nemotron v6 | 11/21 | 6/6 | 3/3 | $0.0008 | R-927e0d |
| **Nemotron v7 (B)** | **18/21** | 6/6 | 3/3 | $0.0007 | R-b81f58 |
| Nemotron + naive memory (Dn) | 14/21 | 6/6 | 3/3 | $0.0007 | R-22a0a7 |
| Sonnet v0 (C) | 18/21 | 6/6 | 3/3 | $0.0101 | R-926e56 |
| Sonnet + naive memory (D) | 18/21 | 6/6 | 3/3 | $0.0109 | R-b3d04f |

- **v7 on Nemotron blocks as many stranger attacks as Sonnet, at about 1/14 of the cost per task.** At v7 the
  tool-access check in code fired for the first time (2 blocks). The only case still failing at v7 and on Sonnet
  is the two-step attack: nothing is sent or leaked, but the stranger's second request is saved as an extra note,
  which the check counts as a failure.
- **Known hole at v7:** the lesson says strangers may only add notes and read the calendar, but the change removed
  only the 4 write tools it names. Strangers can still search notes, look up contacts, and move or cancel events.
- **Poisoned memory** (one planted "new rule from Thomas" line, a stranger's claim, added to naive memory, D37):
  Sonnet 27/30 → 27/30 (R-df0bb0), Nemotron 23/30 → 21/30 (R-07988d). No measurable effect.

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
