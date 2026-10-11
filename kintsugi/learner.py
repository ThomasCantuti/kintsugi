"""Kintsugi learner: failure → supervisor proposes ≤3 delta lessons → dedup → trust → gate → commit.

Never touches held-out cases (only `evals.cases("train")`, via the gate).
"""
import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import raindrop.analytics as raindrop

from . import config, gate, genome, models
from .db import db
from .genome import SECTIONS
from .tools import ALL_TOOLS

MAX_CANDIDATES = 3
Notify = Callable[[str], Awaitable[None]] | None

PROPOSE = """You improve the harness ("genome") of Tsugi, a personal-assistant agent for its owner Thomas.
The genome has four sections:
- rules: conventions for HOW to do things (formats, defaults, durations, naming)
- context_policies: what to look up or check BEFORE acting (e.g. look up contacts, check the calendar)
- guardrails: things Tsugi must NEVER do
- tool_access: which tools a tier ("owner" or "stranger") may use (set "tier", "tools", "allow")

Current genome:
{genome}

Tools: {tools}

A failure happened.
Conversation: {history}
Tool calls Tsugi made: {steps}
Tsugi's reply: {reply}
Feedback: {correction}

Propose up to {n} ALTERNATIVE lessons that would fix this kind of failure. Each lesson is a small delta to ONE
section, written as one general imperative sentence that also helps with similar future requests (not only
this exact one). The gate tests each alternative ALONE, so each one must cover EVERY part of the feedback by
itself. Don't repeat what the genome already says. Best lesson first.
Answer only JSON:
{{"lessons": [{{"section": "rules|context_policies|guardrails|tool_access", "text": "...",
"tier": "stranger", "tools": ["tool_name"], "allow": false,
"prediction": "what will change in Tsugi's behaviour"}}]}}
("tier", "tools", "allow" only for tool_access.)"""

CORRECTION = """A test case failed. Write the feedback Thomas would give, in one or two sentences, stating the
general convention that was broken (not just this case's answer).
Request: {history}
Tool calls: {steps}
Reply: {reply}
Failed checks (MongoDB filters on the resulting data, or reply checks): {failed}
Answer only JSON: {{"correction": "..."}}"""


def _genome_text(g: dict) -> str:
    return json.dumps({s: g[s] if s == "tool_access" else [i["text"] for i in g[s]] for s in SECTIONS}, indent=1)


async def write_correction(f: dict) -> str:
    """Supervisor as teacher: feedback for a failed case that has no hand-written correction."""
    r = await models.chat_json([{"role": "user", "content": CORRECTION.format(
        history=json.dumps(f["history"]), steps=json.dumps(f["steps"])[-3000:], reply=f["reply"],
        failed=json.dumps(f.get("failed", [])))}], model=config.SUPERVISOR_MODEL)
    return r.get("correction", "")


async def propose(f: dict, g: dict) -> list[dict]:
    r = await models.chat_json([{"role": "user", "content": PROPOSE.format(
        genome=_genome_text(g), tools=", ".join(ALL_TOOLS), history=json.dumps(f["history"]),
        steps=json.dumps(f["steps"])[-3000:], reply=f["reply"], correction=f["correction"], n=MAX_CANDIDATES)}],
        model=config.SUPERVISOR_MODEL)
    now = datetime.now(UTC)
    out = []
    for p in r.get("lessons", [])[:MAX_CANDIDATES]:
        section, text = p.get("section"), (p.get("text") or "").strip()
        if section not in SECTIONS or not text:
            continue
        lesson = {"_id": f"L-{uuid.uuid4().hex[:6]}", "section": section, "text": text,
                  "prediction": p.get("prediction", ""), "status": "candidate", "created_at": now,
                  "parents": [f["source_id"]], "gate": None,
                  "source": {"kind": f["kind"], "tier": f["tier"], "ref": f["source_id"]},
                  "failure": {k: f.get(k) for k in ("source_id", "kind", "tier", "history", "steps", "reply",
                                                     "correction", "case")}}
        if section == "tool_access":
            lesson.update(tier=p.get("tier") if p.get("tier") in ("owner", "stranger") else "stranger",
                          tools=[t for t in p.get("tools", []) if t in ALL_TOOLS], allow=bool(p.get("allow")))
            if not lesson["tools"]:
                continue
        out.append(lesson)
    return out


async def _say(notify: Notify, text: str) -> None:
    if notify:
        await notify(text)


async def _gate_and_commit(candidates: list[dict], f: dict, notify: Notify = None) -> dict:
    g = await genome.current()
    gate_id = f.get("gate_id") or f"G-{uuid.uuid4().hex[:6]}"  # learn() opened the cycle doc; approve() starts one here
    await db.gates.update_one({"_id": gate_id}, {"$set": {"status": "running"}, "$setOnInsert": {
        "lessons": [l["_id"] for l in candidates], "source": f["source_id"], "kind": f.get("kind"), "tier": f.get("tier"),
        "correction": f.get("correction"), "created_at": datetime.now(UTC)}}, upsert=True)

    async def progress(e: dict) -> None:  # each gate case lands on the cycle doc; the change stream shows it live
        await db.gates.update_one({"_id": gate_id}, {"$push": {"progress": e}})
    result = {"status": "rejected", "lessons": candidates}
    for n, lesson in enumerate(candidates, 1):
        await _say(notify, f"🧪 Testing #{n}: does it fix the failure without breaking past cases?")
        v = await gate.judge(lesson, f, g, progress)
        await _say(notify, f"   #{n} " + (
            f"✓ fixed · {v['regression_passed']}/{v['regression_total']} past cases still pass → shipping" if v["accepted"]
            else f"✗ fixed it but broke {v['regression_total'] - v['regression_passed']} past case(s)" if v["fixed"]
            else "✗ didn't fix the failure"))
        await db.lessons.update_one({"_id": lesson["_id"]}, {"$set": {"gate": v}})
        if v["accepted"]:
            new = await genome.commit({**lesson, "gate": v}, lesson["parents"])
            await gate.carry_baseline(g, new["version"], v, (f.get("case") or {}).get("id"))
            result = {"status": "accepted", "lesson": {**lesson, "gate": v}, "version": new["version"]}
            await db.lessons.update_many({"_id": {"$in": [l["_id"] for l in candidates[n:]]}},  # untested alternatives
                                         {"$set": {"status": "skipped"}})
            break
        await db.lessons.update_one({"_id": lesson["_id"]}, {"$set": {"status": "rejected"}})
    await db.gates.update_one({"_id": gate_id}, {"$set": {"status": result["status"], "ended_at": datetime.now(UTC),
                                                          "version": result.get("version")}})
    if f["kind"] in ("telegram", "raindrop"):  # live source: its Raindrop event shows what Kintsugi did about it
        l = result.get("lesson")
        raindrop.track_signal(
            event_id=f["source_id"], name="lesson_shipped" if l else "no_safe_fix", sentiment="POSITIVE" if l else "NEGATIVE",
            properties={"lesson": l["_id"], "section": l["section"], "text": l["text"], "genome_version": result["version"],
                        "past_cases_passing": f"{l['gate']['regression_passed']}/{l['gate']['regression_total']}"}
            if l else {"candidates_rejected": len(candidates)})
    return result


async def learn(f: dict, notify: Notify = None) -> dict:
    """f: {source_id, kind (telegram|raindrop|case|redteam), tier, history, steps, reply, correction?, case?, failed?}"""
    await db.lineage.update_one({"_id": f["source_id"]}, {"$setOnInsert": {
        "type": f["kind"], "parents": [], "status": "active", "trust": f["tier"],
        "label": (f["history"][-1]["content"] if f["history"] else "")[:80]}}, upsert=True)
    f["gate_id"] = f"G-{uuid.uuid4().hex[:6]}"  # one doc per learning cycle in `gates`: the live view follows it
    await db.gates.insert_one({"_id": f["gate_id"], "status": "proposing", "source": f["source_id"], "kind": f["kind"],
                               "tier": f["tier"], "correction": f.get("correction"), "lessons": [], "created_at": datetime.now(UTC)})
    if not f.get("correction"):
        f["correction"] = await write_correction(f)
        await db.gates.update_one({"_id": f["gate_id"]}, {"$set": {"correction": f["correction"]}})
    g = await genome.current()
    candidates = []
    for lesson in await propose(f, g):
        await genome.embed_lesson(lesson)
        similar = await genome.similar_lessons(lesson["text"], k=3) or []
        if similar and similar[0]["score"] >= 0.95:  # Vector Search dedup: we already know this
            lesson.update(status="duplicate", duplicate_of=similar[0]["_id"])
        lesson["parents"] += [s["_id"] for s in similar if s["score"] >= 0.85 and s["_id"] not in lesson["parents"]]
        lesson["similar"] = [{"_id": s["_id"], "score": round(s["score"], 3)} for s in similar]
        candidates.append(lesson)
    if candidates:
        await db.lessons.insert_many(candidates)
        # ponytail: Atlas Search indexes new docs in ~1.1 s (measured); the gate's retrieval must see them.
        # Poll similar_lessons(ids=...) instead if this ever flakes.
        await asyncio.sleep(2)
    await db.gates.update_one({"_id": f["gate_id"]}, {"$set": {"lessons": [l["_id"] for l in candidates]}})
    live = [l for l in candidates if l["status"] == "candidate"]
    await _say(notify, f"💡 {len(live)} candidate lesson(s):\n" + "\n".join(
        f"#{n} [{l['section']}] {l['text']}" for n, l in enumerate(live, 1)))
    if not live:
        status = "no_candidates" if not candidates else "duplicate"
        await db.gates.update_one({"_id": f["gate_id"]}, {"$set": {"status": status, "ended_at": datetime.now(UTC)}})
        return {"status": status, "lessons": candidates}
    if f["tier"] != "owner":  # every source untrusted → owner decides
        await db.lessons.update_many({"_id": {"$in": [l["_id"] for l in live]}}, {"$set": {"status": "quarantined"}})
        await db.gates.update_one({"_id": f["gate_id"]}, {"$set": {"status": "quarantined", "ended_at": datetime.now(UTC)}})
        if f["kind"] in ("telegram", "raindrop"):
            raindrop.track_signal(event_id=f["source_id"], name="lesson_quarantined", properties={"candidates": len(live)})
        return {"status": "quarantined", "lessons": live}
    return await _gate_and_commit(live, f, notify)


async def approve(lesson_id: str, notify: Notify = None) -> dict:
    """Owner approved a quarantined lesson: it still has to pass the gate."""
    lesson = await db.lessons.find_one({"_id": lesson_id, "status": "quarantined"})
    if not lesson:
        return {"status": "not_found"}
    await db.lessons.update_one({"_id": lesson_id}, {"$set": {"status": "candidate", "approved_by": "owner"}})
    return await _gate_and_commit([lesson], lesson["failure"], notify)


async def reject(lesson_id: str) -> dict:
    await db.lessons.update_one({"_id": lesson_id, "status": "quarantined"}, {"$set": {"status": "rejected"}})
    return {"status": "rejected"}
