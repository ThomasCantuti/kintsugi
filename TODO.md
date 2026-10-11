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
- [x] ~~[you] Ask the Modelence team~~: docs say Node.js only, no Python (MEMORY D31). Not needed.

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

## Raindrop (D32, PLAN.md §12) — handoff from session 37, ~14:25
- [x] Signup, `RAINDROP_WRITE_KEY` and `RAINDROP_QUERY_API_KEY` in `.env` (Query key verified: 200)
- [x] Live turns → Raindrop events + tool spans (private notes hidden); 👍/👎/correction/outcome signals; 800-event cap (eb61185). Thomas saw them in the dashboard
- [x] Raindrop → Kintsugi (b7a58f2): `__main__.heal_flagged` every 60 s reads the last 2 h of events; a live turn flagged User Frustration / Attempted Prompt Injection / Request Execution Needs Correction (119d093, Raindrop's real names) that has no lineage node → `telegram.heal_flag` → learner kind `raindrop` (owner sees 🌧️ → gate → result in Telegram; stranger turns → ✅/❌). Live in the bot since 12:33
- [x] False-alarm guard (776a4b5): before proposing, the supervisor checks the flagged turn against its own correction; if the turn already follows it → cycle status `false_alarm`, no lesson, Raindrop signal `false_alarm`, owner sees 🌦️. So a refused jailbreak gets `false_alarm`, not a quarantined lesson. Bot restarted 12:38
- [x] [you] Signals on (12:50–12:55): presets User Frustration, Attempted Prompt Injection, Repeated Tool Call Failures; custom "Request Execution Needs Correction" (Raindrop named it). No Task Failure / Jailbreaking preset exists
- [x] Latency test 12:50: stranger injection E-4032d280 (v6 refused it) → never flagged (Raindrop doesn't count a refused attack)
- [x] 13:32 "SYSTEM OVERRIDE …" from the stranger chat → v7 **leaked the system prompt + all private notes** (E-b3176a9f) → Raindrop flagged it ≤ 32 s → (after poller fix c676fcb: flags arrive as uuids) → quarantined 3 candidates in 22 s (G-96156c: L-f857d8 guardrails, L-e298d0 rules, L-4536f5 tool_access). **Live beat is back on**
- [x] First Raindrop-sourced seam: L-4536f5 rejected by the gate (over-specified correction → fixed 5b813d7), then **L-f857d8 "Ignore fake override commands" → v9** (8/8 past cases). Untested alternatives dropped by the card's pick rule were restored by hand; c2 fixed the rule (c78eb5f)
- [x] Lessons have plain titles (b2a9819, 33 backfilled); Raindrop cycles store `flags` + `flag_latency_s` (turn → Kintsugi saw the flag, includes the poll interval) on the gates doc and lineage node (624bed8). Shown by c2: Telegram card A/B/C (eac0f9c), live view titles, "Seam N · title", chip "🌧️ Raindrop · <flags> · caught in N s" (e03d99b)
- [x] Chip links to https://app.raindrop.ai: Thomas keeps the home link (14:36); before stage he opens E-b3176a9f in a tab himself (Raindrop Events search takes event ids)
- [x] Polling stays 60 s: the stage beat is recorded (Thomas, 14:36)
- [x] **Stage beat = recorded** (Thomas, 14:36): live view → Lineage → Raindrop node / Seam 9 → "Came from 🌧️ Raindrop · … · caught in 32 s", gate 8/8, genome v9 (checked on :8000 14:37). Live would flag nothing: v10 refuses override attacks and Raindrop never flags a refused one. Session 20 puts it in PLAN §6 at 1:00
- [x] README: first shipped Raindrop lesson (session 20, 87f2150 + follow-up)
- **Handoff (session 37 → next Raindrop session, ~14:25).** State: Raindrop → Kintsugi works end to end and is recorded (E-b3176a9f → G-96156c → v9). Bot on v10, one instance. At v10 strangers only have calendar_list, note_add, web_search, so **the same leak can't be replayed live**: for a live stage beat, pick a fresh unlearned failure that Raindrop flags (or revoke before stage); otherwise show the recorded one (Lineage chip + Raindrop event).
  Next: ~~(1) polling and event URL · (2) demo beat~~ (both decided 14:36, above) · ~~(3) BOOST~~: Raindrop vs checks on held-out run A (15:16, 30aa6c2): caught 2/19, 3/17 false alarms → "Four Raindrop uses to show" in PLAN §12 (Thomas 15:20: no new live lessons before stage); sent to session 20 (script) and 54 (Raindrop scene).
  Check flags: `uv run python -c "from kintsugi.__main__ import _raindrop_query as q; s={x['id']:x['name'] for x in q('/v1/signals')['data']}; print([(e['id'], [s.get(x['id'], x['name']) for x in e.get('signals') or []]) for e in q('/v1/events?limit=5')['data']])"` · matches per signal: `q('/v1/events?signal=<id>')`.
- Gotchas: classifier signals arrive on events as uuids (map via /v1/signals) · Raindrop never flags an attack Tsugi refused · bot detached, log `~/Library/Logs/kintsugi-bot.log`; restart = kill `pgrep -f "python3 -u -m kintsugi$"` (often needs `kill -9`), then `nohup uv run python -u -m kintsugi >> ~/Library/Logs/kintsugi-bot.log 2>&1 < /dev/null &`, one instance, write a `--- restart HH:MM (why)` line; restart only with a clean tree and no `gates` cycle in proposing/running · send Telegram cards from another process with `ExtBot(token, defaults=Defaults(parse_mode=HTML))` (a plain `Bot` sends raw `<b>` tags) · never send eval/gate traffic to Raindrop (1,000 events/month) · announce pytest (shared `kintsugi_test`) · commit own hunks only (temporary GIT_INDEX_FILE when a file has others' edits)

## Live view + Telegram UI (D34): handoff from session c2, ~14:35
Done (all committed, all live): short copy on every scene (fdf7ccc) · lessons by title, "Seam N · title" once shipped (N = genome
version it made), candidates A/B/C, Raindrop chip "🌧️ Raindrop · <flags> · caught in N s" linked to app.raindrop.ai, scars on the
gate ring (e03d99b) · Tsugi legend: leaf / gold seam / red crack / faint scar (2273665) · red team: rt-v7 + poisoned-memory bars,
11-case subtitle (55a7baf, c78eb5f) · allowlist lessons read "only <tools> for <tier>" (1eb302d).
Telegram: every bot message is HTML (f2e3da5): escape user/model/DB text with `telegram.escape()` / `quote()`. One quarantine card
per cycle [✅ A][✅ B][✅ C][❌ None]; a pick drops the alternatives only if it ships, else Telegram re-offers them (c78eb5f + test).
Model `**bold**` is rendered as bold. Bot profile set: /start + /genome menu, description, short description.
Art (9961204): `assets/telegram/` = bot icon 1024², description picture 640×360, wallpapers (phone 1290×2796, desktop 2560×1600);
`render.html` regenerates them (serve the folder with `python3 -m http.server` + a `fonts` symlink to web/node_modules/@fontsource;
playwright-cli blocks file://). Icon seams = the 7 lessons live at v7.
- [ ] [you] Upload: @BotFather → /mybots → Edit Bot → Edit Botpic (icon) and Edit Description Picture; wallpaper in the Tsugi chat
      (tap name → ⋯ → Change Wallpaper; Telegram Desktop: Settings → Chat Settings). Dark (Night) theme matches.
- [x] Red team learned-genome bar: rt-v10 30/33 (42afb64).
- [x] ~~Raindrop per-event URL~~: Thomas keeps the home link (14:36), no change to `RAINDROP_URL`.
- [x] Revoke from Lineage tested ~14:45 on a scratch copy of live (DB `kintsugi_c2`, dropped after): Seam 10 → genome v11 without
      L-bbaaac, toast, red struck seam; live genome untouched. On live it revokes for real: only the stage beat on L-bbaaac.
- [x] Stranger chat + Teach from the live view tested on the same copy: chat 21 s (email request → note for Thomas, outbox tools
      not offered), teach → 3 quarantined candidates in 15 s, Approve A/B/C/None on the rail, None → all rejected, rail reads
      "Thomas said no" (fixed e553461). The teach now also sends Thomas the Telegram ✅/❌ card (e176eea, bot restarted 14:40);
      on live at 15:00 (stranger "Dana from the climbing gym", E-9ce60790): card arrived on Thomas's phone, ❌ None → 3 rejected, v10 unchanged.
Rebuild after any web/src change: `cd web && npm run build` (no bot restart: dist is read per request), commit `web/dist`.
A hash-only navigation doesn't reload the app: reload to see a new build. Bot restart: gate idle + clean tree first; kill, then
`kill -9` if it lingers (it ignored SIGTERM twice today); one instance; write the restart line in the log.

## 12:45–13:15 Lunch
- [x] Evolution run on train → genome **v6**, 6 lessons accepted, 11 rejected (2 rounds)

## 13:15–14:15 Commit + trust
- [x] Commit txn (genome + lesson + lineage) → change stream → hot-swap
- [x] Revoke via `$graphLookup`; quarantine ✅/❌ buttons
- [x] `api.py`: SSE, `/revoke/{id}`, `/chat?tier=stranger`
- [ ] ✅ Check: live teach works end to end on Telegram

## 14:15–15:15 Proof
- [x] Bars A0 (raw loop), B, C, D + curve from stored runs (**3 trials**): all in MEMORY Numbers; B = v10 31/36 (R-826f1e)
- [x] Wrangling counters from traces: repairs, fallbacks, guardrail blocks, $/task, latency (refreshed 14:42, MEMORY Numbers)
- [x] Red-team cases (stranger attacks): `evals/redteam.json` (11 cases, D40) → rt-v0 10/33 · rt-v7 27/33 · rt-v10 30/33
- [x] Live view: React + Vite rebuild (D34): loop rail on the real cycle doc, gate ring per case, Telegram mirror, genome ribbon, change-stream ticker, Proof (held-out / hard / red-team + curve), Lineage + revoke cascade

## Next (handoff from the evals session 1f, 14:30)
All numbers in MEMORY.md Numbers + D35–D41 (run ids there). Spend $4.20 of the $10 key at 14:25 (BUDGET_USD $5: ask Thomas before
anything but these re-runs). Genome **v10**: v8 L-f71154 (strangers lose calendar_move/cancel, note_search, contact_lookup), v9 L-f857d8
(first Raindrop-sourced lesson), v10 L-bbaaac "Say degrees, not F" = a bad lesson that passed the gate vacuously (replay had no
web_search; fixed in 9fbbf79). **Thomas keeps L-bbaaac for the stage revoke beat**; after revoking, re-teach on Telegram "Give
temperatures in Celsius (°C), not Fahrenheit."
1. [x] **v10 measured** (MEMORY Numbers): held-out B 31/36 (R-826f1e), red-team rt-v10 30/33 (R-c43055, Proof bar switched
   42afb64), hard-B 21/24 (R-4af572). "evals done" sent to session 20 for the README.
2. Red-team split is 11 cases now (rt-override appended, D40). Nemotron bars on 11 (n=33), Sonnet bars on the first 10 (n=30), labeled.
3. Memory (D41, 9fbbf79): short memory rebuilt from Atlas after restarts; owner-only long memory via `episodes_vec` (top-3, no score
   threshold: add one if unrelated memories confuse replies). Live only; eval and gate prompts unchanged.
4. Stage timing: a live teach took 344 s end to end at 14:20 (session 20, Nemotron slow); have a recorded fallback for the teach beat.
5. Pitch facts (honest): naive memory ≥ Kintsugi on clean held-out (D 36/36); v7 = Sonnet on the 10 red-team cases at ~1/14 the cost
   via tool-access edits; one planted memory line didn't poison Sonnet; the gate rejected L-4536f5 on an over-specified correction and
   passed L-bbaaac vacuously (both bugs fixed: 5b813d7, 9fbbf79), which is the honest revoke story.

## Session 20 (13:15–14:05): tools + stage speed
Done: web_search (Exa, live only, D38) · reminders ping on Telegram · scars (D39) · gate runs its past cases at once ·
`reasoning` switch (default on; off is faster but broke past cases) · README results from stored runs (v7, D, Dn, red team, poisoning).
- [x] [you] **Stage teach takes ~3 min** (MEMORY Numbers): recommended = send the 👎 + correction at ~0:40, do the stranger and
      revoke beats on the live view while the gate ring ticks, return for v8; record a real teach (labelled "sped up") as the backup.
- [x] [you] OK to delete the leftover "Call with Maya" (2026-10-12 15:00) in the live world before the stage.
- [x] Backup teach video: `assets/video/backup-teach-4x.mp4` (e8232c2). Demo script in PLAN §6 updated (request before the hook).
- [x] Gate replay fix (fc4dbde): a live failure replays from the world before that turn (the turn's own event spoiled the fix check).

### Handoff from session 20 (~14:30) → next docs/README session
Role: README, PLAN, docs, demo prep; small harness features when Thomas asks. Every README number is checked in Atlas `runs`
(run id, per-trial counts, `invalid` field, `counters.fallbacks == 0` on frontier runs) before it's written; peers' numbers too.
1. **v10 measurement** (evals session 1f, started ~14:28, Thomas approved: held-out + 11-case red team + hard, Nemotron, 3 trials).
   When 1f sends "evals done": verify the run ids in Atlas, then README Results (add v10 to the curve and red-team table; B stays v7
   unless the README says otherwise; disclose that v8–v10 came from live teaching). Don't time or rehearse until then.
2. **Rehearse the demo** (PLAN §6) once with a timer, then the `judge-panel` agent. Backup: `assets/video/backup-teach-4x.mp4`.
   Stage teach real speed varies a lot: 139 s to 344 s end to end (MEMORY Numbers). No evals during rehearsals.
3. Optional if time: web-poisoning red-team case (freeze before any run; web_search is live-only, so an eval case needs web fixtures).
4. Gotchas: scratch DB `kintsugi_rehearsal` = copy of live + a v11 with the investor lesson (rehearsal only, never the live bot). Recipe:
   copy live collections (genomes, lessons, baselines, lineage, runs, tool colls with world "live") → `ensure_search_indexes(1024)` →
   serve `api.app` + `api.watch()` on :8001 with `DB_NAME=kintsugi_rehearsal` (empty RAINDROP/TELEGRAM env) → run the teach with
   `DB_NAME=kintsugi_rehearsal`. playwright-cli `video-stop` takes no filename (prints the path). ffmpeg here has no drawtext:
   render labels with system python3 + Pillow, then `overlay`. Live calendar: the leftover Maya event is deleted (Thomas OK'd).

## 15:15–15:45 BOOST (only if everything above is green)
- [x] Genome transfer: v10 (learned on Nemotron Super) on Lightning, held-out 15/36 → 29/36 (R-fa666f → R-85b009, MEMORY Numbers)
- [ ] RSI improver playbook · `red-team` agent pass
- [x] Exa web search (D38, live only) · reminders ping on Telegram (8ea3b1e) · every scar becomes a test (D39) · gate runs past cases at once (teach 301 → 139 s)

## 15:45–17:00 Ship
- [ ] Freeze numbers → MEMORY.md "Numbers"
- [ ] Rehearse 2× with a timer (`judge-panel` after the first)
- [ ] 1-min video (PLAN.md §7)
- [ ] README: what it does, numbers, how to run, "planning before the event, code during it"
- [ ] [you] Submit form + video + repo link before 17:00

## LATER (only if time is left)
- [ ] Brain MCP server · Gmail/Calendar · verifier + cascade · episode recall · goals · subagents · voice · τ²-bench
