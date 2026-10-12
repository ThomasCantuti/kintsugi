"""FastAPI: live view, SSE fed by one Atlas change stream (which also hot-swaps the genome), revoke, quarantine, chat."""
import asyncio
import json
import secrets
from collections import deque
from pathlib import Path

import raindrop.analytics as raindrop
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import agent, config, genome, learner, telegram
from .db import db

app = FastAPI(title="Kintsugi")
WEB = Path(__file__).resolve().parent.parent / "web"
DIST = WEB / "dist"  # the React live view, built by `npm run build` in web/ (committed)
EVENT_TYPES = {"lessons": "lesson", "genomes": "genome", "episodes": "episode", "gates": "gate", "runs": "run"}
subscribers: set[asyncio.Queue] = set()
recent: deque = deque(maxlen=40)  # replayed to each new page, so the ticker isn't blank after a reload
web_turns: dict[str, list[dict]] = {"owner": [], "stranger": []}  # live-view chats (owner only in the sandbox)
used = {"chat": 0, "teach": 0}  # sandbox spend so far (this process)
running: set[asyncio.Task] = set()  # live-view chat turns in flight (asyncio keeps only weak refs to tasks)
bot = None  # the Telegram bot, set by __main__: a quarantine from the live view reaches the owner's phone too


async def watch() -> None:
    """One change stream on the database: hot-swap new genome versions, fan events out to the live view."""
    pipeline = [{"$match": {"operationType": {"$in": ["insert", "update", "replace"]}, "$or": [
        {"ns.coll": {"$in": ["lessons", "genomes", "gates", "runs"]}},
        {"ns.coll": "episodes", "fullDocument.kind": "live"}]}}]
    while True:
        try:
            async with await db.watch(pipeline) as stream:
                async for ch in stream:
                    coll = ch["ns"]["coll"]
                    if coll == "genomes" and ch.get("fullDocument"):
                        genome.hot_swap(ch["fullDocument"])
                    evt = {"type": EVENT_TYPES[coll], "coll": coll, "id": str(ch["documentKey"]["_id"]),
                           "op": ch["operationType"], "note": _note(coll, ch)}
                    recent.append(evt)
                    for q in list(subscribers):
                        q.put_nowait(evt)
        except Exception as e:  # network blip: reopen the stream
            print("change stream error, retrying:", repr(e))
            await asyncio.sleep(2)


def _note(coll: str, ch: dict) -> str:
    """A few words per change event for the live view's ticker."""
    doc = ch.get("fullDocument") or {}
    upd = (ch.get("updateDescription") or {}).get("updatedFields") or {}
    for k, v in upd.items():
        if k.startswith("progress"):  # a gate case result ($push onto the gates doc)
            p = v[-1] if isinstance(v, list) else v
            return f"{p.get('case', 'plan')} {'' if 'passed' not in p else 'pass' if p['passed'] else 'fail'}".strip()
    if "status" in upd:
        return str(upd["status"])
    if coll == "genomes":
        return f"v{doc.get('version')}"
    if coll == "runs":
        return f"{doc.get('label')} {doc.get('passed')}/{doc.get('n')}"
    return str(doc.get("status") or doc.get("tier") or "")


@app.get("/")
async def index():
    built = DIST / "index.html"
    return FileResponse(built if built.exists() else WEB / "legacy.html")


@app.get("/legacy")
async def legacy():
    return FileResponse(WEB / "legacy.html")


app.mount("/assets", StaticFiles(directory=DIST / "assets", check_dir=False), name="assets")


@app.get("/api/events")
async def events():
    q: asyncio.Queue = asyncio.Queue()
    subscribers.add(q)
    backlog = list(recent)  # taken with the subscribe, no await between: nothing is sent twice

    async def stream():
        try:
            yield ": connected\n\n"
            for e in backlog:
                yield f"data: {json.dumps({**e, 'replay': True})}\n\n"
            while True:
                try:
                    yield f"data: {json.dumps(await asyncio.wait_for(q.get(), 15))}\n\n"
                except TimeoutError:
                    yield ": ping\n\n"
        finally:
            subscribers.discard(q)

    return StreamingResponse(stream(), media_type="text/event-stream")


def _curve(runs: list[dict]) -> list[dict]:
    """Held-out pass rate per genome version (agent model, full harness, no naive memory)."""
    by_version = {}
    for r in runs:
        sw = r.get("switches") or {}
        if (r["split"] == "heldout" and r.get("genome_version") is not None and r["model"] == config.AGENT_MODEL
                and sw.get("genome", True) and not sw.get("naive_memory")):
            by_version[r["genome_version"]] = {"version": r["genome_version"], "pass_rate": r["pass_rate"], "n": r["n"]}
    return [by_version[v] for v in sorted(by_version)]


@app.get("/api/state")
async def state():
    g = await genome.current()
    lessons = await db.lessons.find({}, {"embedding": 0, "failure.history": 0, "failure.steps": 0, "failure.reply": 0,
                                         "failure.case": 0}).sort("created_at", -1).to_list(80)
    agg = await (await db.episodes.aggregate([{"$group": {
        "_id": None, "episodes": {"$sum": 1}, "repairs": {"$sum": "$counters.repairs"},
        "fallbacks": {"$sum": "$counters.fallbacks"}, "blocks": {"$sum": "$counters.blocks"}, "cost": {"$sum": "$cost"}}}])).to_list()
    counters = {k: (agg[0][k] if agg else 0) for k in ("episodes", "repairs", "fallbacks", "blocks", "cost")}
    runs = await db.runs.find({"invalid": {"$exists": False}}, {"results.failed": 0, "results.errors": 0, "results.cost": 0, "results.episodes": 0}) \
        .sort("created_at", 1).to_list(500)
    for r in runs:  # pass count per trial (results are concatenated trial after trial)
        res, t = r.pop("results", []), r.get("trials") or 1
        per = len(res) // t
        r["trial_passed"] = [sum(x["passed"] for x in res[i * per:(i + 1) * per]) for i in range(t)] if per else []
    episodes = await db.episodes.find({"kind": "live"}, {"tier": 1, "input": {"$slice": -1}, "steps": 1, "reply": 1, "error": 1,
                                                          "genome_version": 1, "created_at": 1}).sort("created_at", -1).to_list(24)
    commits = await db.genomes.find({"cause.op": "commit"}, {"version": 1, "cause": 1}).to_list(500)
    return jsonable_encoder({
        "genome": {"version": g["version"], "tool_access": g["tool_access"], "cause": g.get("cause"), "created_at": g.get("created_at"),
                   **{s: [i["text"] for i in g[s]] for s in ("rules", "context_policies", "guardrails")}},
        "genome_items": {s: g[s] for s in ("rules", "context_policies", "guardrails")},
        "lessons": lessons, "counters": counters, "runs": runs, "curve": _curve(runs),
        "gate_running": await db.gates.count_documents({"status": "running"}) > 0,
        "episodes": episodes,  # live turns, newest first
        "cycle": await db.gates.find_one({}, sort=[("created_at", -1)]),  # the latest learning cycle
        "versions": {c["cause"]["lesson"]: c["version"] for c in commits},  # lesson id -> genome version that shipped it
        "sandbox": config.SANDBOX,
    })


@app.get("/api/lineage")
async def lineage_all():
    nodes = await db.lineage.find({}, {"type": 1, "status": 1, "label": 1, "parents": 1, "flags": 1, "flag_latency_s": 1}).to_list(500)
    return {"nodes": [{"_id": n["_id"], "type": n.get("type", ""), "status": n.get("status", ""), "label": n.get("label", ""),
                       "parents": n.get("parents", []), **{k: n[k] for k in ("flags", "flag_latency_s") if k in n}}
                      for n in nodes]}


@app.get("/api/raindrop")
async def raindrop_flagged():
    """Live turns Raindrop flagged, newest first: what Tsugi did, the flag, the learning cycles it started, their lessons.
    Private notes are blanked out of the reply here (the page is shown on stage); Raindrop itself saw the real reply."""
    out = []
    for n in await db.lineage.find({"type": "raindrop"}).to_list(50):
        ep = await db.episodes.find_one({"_id": n["_id"]}, {"input": 1, "steps.tool": 1, "reply": 1, "tier": 1,
                                                            "genome_version": 1, "created_at": 1, "world": 1}) or {}
        private = [d["text"] for d in await db.notes.find({"world": ep.get("world"), "tags": "private"}, {"text": 1}).to_list()]
        reply = ep.get("reply") or ""
        hidden = reply
        for t in private:
            hidden = hidden.replace(t, "[private note]")
        out.append({
            "_id": n["_id"], "flags": n.get("flags", []), "flag_latency_s": n.get("flag_latency_s"),
            "tier": ep.get("tier"), "genome_version": ep.get("genome_version"), "created_at": ep.get("created_at"),
            "message": next((m["content"] for m in reversed(ep.get("input", [])) if m["role"] == "user"), n.get("label", "")),
            "tools": [s["tool"] for s in ep.get("steps", [])], "reply": hidden, "leaked_private": sum(t in reply for t in private),
            "cycles": await db.gates.find({"kind": "raindrop", "source": n["_id"]}, {"progress": 0}).sort("created_at", 1).to_list(),
            "lessons": await db.lessons.find({"parents": n["_id"]}, {"title": 1, "text": 1, "section": 1, "status": 1, "gate": 1,
                                                                    "created_at": 1}).sort("created_at", 1).to_list(),
            "scar": await db.scars.count_documents({"_id": n["_id"]}) > 0,  # replayed by every later gate (D39)
        })
    out.sort(key=lambda r: str(r["created_at"]), reverse=True)
    # one held-out run re-sent to Raindrop on purpose: how its flags compare with the ground-truth checks
    run = await db.runs.find_one({"raindrop_agreement": {"$exists": True}}, {"raindrop_agreement": 1, "label": 1, "split": 1,
                                 "model": 1, "genome_version": 1}, sort=[("created_at", -1)])
    return jsonable_encoder({"flagged": out, "agreement": run})


@app.get("/api/lineage/{node_id}")
async def lineage(node_id: str):
    up = await (await db.lineage.aggregate([
        {"$match": {"_id": node_id}},
        {"$graphLookup": {"from": "lineage", "startWith": "$parents", "connectFromField": "parents",
                          "connectToField": "_id", "as": "up"}}])).to_list()
    if not up:
        raise HTTPException(404, "unknown node")
    ids = {node_id, *(d["_id"] for d in up[0]["up"]), *await genome.descendants(node_id)}
    nodes = await db.lineage.find({"_id": {"$in": list(ids)}}).to_list()
    return {"nodes": [{"_id": n["_id"], "type": n["type"], "status": n["status"], "label": n.get("label", "")} for n in nodes],
            "edges": [{"from": p, "to": n["_id"]} for n in nodes for p in n.get("parents", []) if p in ids]}


def owner(x_owner_key: str = Header("")) -> None:
    """On the public server, revoke and quarantine decisions are Thomas's: the live view sends its ?key=… here."""
    if config.OWNER_WEB_KEY and not secrets.compare_digest(x_owner_key.encode(), config.OWNER_WEB_KEY.encode()):
        raise HTTPException(403, "Only Thomas can do this.")


@app.post("/api/revoke/{node_id}", dependencies=[Depends(owner)])
async def revoke(node_id: str):
    try:
        return await genome.revoke(node_id)
    except LookupError:
        raise HTTPException(404, "Nothing live to revoke there.")


@app.post("/api/quarantine/{lesson_id}/{decision}", dependencies=[Depends(owner)])
async def quarantine(lesson_id: str, decision: str, bg: BackgroundTasks):
    if decision == "approve":
        bg.add_task(learner.approve, lesson_id)  # still has to pass the gate
    elif decision == "reject":
        await learner.reject(lesson_id)
    else:
        raise HTTPException(400, "approve or reject")
    return {"ok": True}


def _tier(tier: str) -> str:
    return "owner" if config.SANDBOX and tier == "owner" else "stranger"


def _cap(kind: str) -> None:
    """The sandbox and the public prod server: cap their turns and learning cycles (~$2 at most) until the next restart."""
    if config.SANDBOX or config.OWNER_WEB_KEY:
        used[kind] += 1
        if used[kind] > (config.SANDBOX_TURNS if kind == "chat" else config.SANDBOX_TEACHES):
            raise HTTPException(429, "Tsugi reached its public spend cap. Ask Thomas to reset it.")


class Chat(BaseModel):
    text: str
    tier: str = "stranger"


@app.post("/api/chat")
async def chat(body: Chat):
    """Chat from the live view: unauthenticated, so stranger tier only, except in the judges' sandbox (owner too).
    Streams NDJSON: {"step": {tool, status}} per tool call as it happens, then {"reply", "episode_id"} or {"error"}."""
    tier = _tier(body.tier)
    _cap("chat")
    turns = web_turns[tier]
    turns.append({"role": "user", "content": body.text})
    q: asyncio.Queue = asyncio.Queue()

    async def step(s: dict) -> None:  # tool name and outcome only: results (notes, contacts) stay on the server
        r = s["result"]
        await q.put({"step": {"tool": s["tool"], "status": "denied" if r.startswith("DENIED")
                              else "error" if r.startswith("ERROR") else "ok"}})

    async def turn() -> None:  # finishes and saves even if the browser goes away
        try:
            ep = await agent.run(await genome.current(), turns[-8:], "live", tier, on_step=step)
            await agent.save(ep, "live", chat=f"web-{tier}")
            turns.append({"role": "assistant", "content": ep["reply"]})
            await q.put({"reply": ep["reply"] or ep["error"] or "…", "episode_id": ep["_id"]})
            await telegram.tell_owner(bot, ep, "live view")
        except Exception as e:
            await q.put({"error": repr(e)[:200]})

    t = asyncio.create_task(turn())
    running.add(t)
    t.add_done_callback(running.discard)

    async def lines():
        while True:
            m = await q.get()
            yield json.dumps(m) + "\n"
            if "step" not in m:
                return
    return StreamingResponse(lines(), media_type="application/x-ndjson")


class Teach(BaseModel):
    text: str
    tier: str = "stranger"


@app.post("/api/teach")
async def teach(body: Teach, bg: BackgroundTasks):
    """Teach from the live view: a stranger's lesson is always quarantined for the owner. In the judges' sandbox the
    visitor can also be the owner (👎 + correction on the last reply, straight to the gate)."""
    tier = _tier(body.tier)
    last = await db.episodes.find_one({"chat": f"web-{tier}"}, sort=[("created_at", -1)])
    if not last:
        raise HTTPException(400, "chat first")
    _cap("teach")
    raindrop.track_signal(event_id=last["_id"], name="correction", signal_type="edit", after=body.text,
                          properties={"tier": tier})
    f = {"source_id": last["_id"], "kind": "telegram", "tier": tier, "history": last["input"], "steps": last["steps"],
         "reply": last["reply"], "correction": body.text}

    async def job():
        result = await learner.learn(f)
        if result["status"] == "quarantined" and bot:
            await telegram.ask_owner(bot, result["lessons"], "🔒 <b>A stranger taught me</b> (live view)")
    bg.add_task(job)
    return {"ok": True}
