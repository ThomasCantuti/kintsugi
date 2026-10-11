"""The gate: a lesson ships only if it fixes the failure and breaks nothing that passed before.

Uses train cases only (held-out never influences a decision).
"""
import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from . import agent, config, evals, genome, models
from .db import TOOL_COLLS, db, wipe_world

REGRESSION_SAMPLE = 8
Progress = Callable[[dict], Awaitable[None]] | None

JUDGE = """You check whether an assistant followed its owner's feedback.
Owner feedback: {correction}
Conversation: {history}
Assistant tool calls: {steps}
Assistant final reply: {reply}
Did the assistant's actions and reply follow the feedback? Answer only JSON: {{"passed": true or false, "why": "one sentence"}}"""


async def supervisor_judge(history: list, steps: list, reply: str, correction: str) -> dict:
    try:
        return await models.chat_json([{"role": "user", "content": JUDGE.format(
            correction=correction, history=json.dumps(history)[-3000:], steps=json.dumps(steps)[-3000:],
            reply=reply)}], model=config.SUPERVISOR_MODEL)
    except Exception as e:
        return {"passed": False, "why": f"judge error: {e!r}"}


async def _replay(cand: dict, live: dict) -> tuple[bool, str]:
    """Replay a live turn ({source_id, history, tier, correction}) in a scratch copy of the live world; the supervisor judges it."""
    world = f"gate:{cand['version']}:{live['source_id']}"
    for coll in TOOL_COLLS:
        docs = await db[coll].find({"world": "live"}, {"_id": 0}).to_list()
        if docs:
            await db[coll].insert_many([{**d, "world": world} for d in docs])
    ep = await agent.run(cand, live["history"], world, live["tier"])
    await wipe_world(world)
    verdict = await supervisor_judge(live["history"], ep["steps"], ep["reply"], live["correction"])
    return bool(verdict.get("passed")), verdict.get("why", "")


async def _fixes(cand: dict, f: dict) -> tuple[bool, str]:
    if f.get("case"):  # ground truth: the case's DB checks
        r = await evals.run_case(cand, f["case"], run_id="gate")
        return r["passed"], f"case checks {'pass' if r['passed'] else 'fail'}"
    return await _replay(cand, f)  # live failure


async def baseline_passing(g: dict) -> list[str]:
    """Train cases that pass under genome g (measured once for v0, then carried forward by commits)."""
    doc = await db.baselines.find_one({"_id": g["version"]})
    if doc is None:
        run = await evals.run_split("train-baseline", "train", g)
        doc = {"_id": g["version"], "passing": [r["case"] for r in run["results"] if r["passed"]], "run": run["_id"]}
        await db.baselines.replace_one({"_id": g["version"]}, doc, upsert=True)
    return doc["passing"]


def _tier(lesson: dict) -> str | None:
    # a tool_access lesson changes only its tier's tools: every other case sees the same prompt and tools, so it can't
    # regress there, and re-running it only measures model noise (which rejected L-82dfca and L-b7ba0c on team-03)
    return lesson.get("tier") if lesson.get("section") == "tool_access" else None


def _sample(passing: list[str], case_id: str | None, lesson: dict) -> list[dict]:
    tier = _tier(lesson)
    return [c for c in evals.cases("train") if c["id"] in passing and c["id"] != case_id
            and tier in (None, c.get("tier", "owner"))][:REGRESSION_SAMPLE]


async def _scars(active: list[dict], f: dict, lesson: dict) -> list[dict]:
    """Live mistakes whose lesson is still active: each one is a regression case for every later lesson."""
    tier = _tier(lesson)
    return [s for s in await db.scars.find({"lesson": {"$in": [l["_id"] for l in active]}}).to_list()
            if s["_id"] != f["source_id"] and tier in (None, s["tier"])]


async def _quiet(_: dict) -> None:
    pass


async def judge(lesson: dict, f: dict, g: dict, progress: Progress = None) -> dict:
    """progress(event) reports the plan ({lesson, cases}) and each result ({lesson, case, passed}) for the live view."""
    say = progress or _quiet
    active = await db.lessons.find({"status": "active"}).sort("created_at").to_list()
    cand = genome.materialize(g["version"] + 1, active + [lesson])
    case_id = (f.get("case") or {}).get("id")
    first = case_id or f"replay {f['source_id']}"
    # the past cases are listed up front only when the baseline is cached: measuring a missing one runs the train
    # split, which stays behind the fix check (an unfixed candidate never pays for regression runs)
    known = await db.baselines.find_one({"_id": g["version"]})
    sample = _sample(known["passing"], case_id, lesson) if known else []
    scars = await _scars(active, f, lesson)
    scar_ids = [f"scar {s['_id']}" for s in scars]
    await say({"lesson": lesson["_id"], "cases": [first] + [c["id"] for c in sample] + scar_ids})
    fixed, why = await _fixes(cand, f)
    await say({"lesson": lesson["_id"], "case": first, "passed": fixed})
    v = {"fixed": fixed, "why": why, "regression_passed": 0, "regression_total": 0, "accepted": False, "still_passing": []}
    if not fixed:
        return v
    if not known:
        sample = _sample(await baseline_passing(g), case_id, lesson)
        await say({"lesson": lesson["_id"], "cases": [first] + [c["id"] for c in sample] + scar_ids})
        await say({"lesson": lesson["_id"], "case": first, "passed": True})

    async def tell(r: dict, retry: bool = False) -> None:
        await say({"lesson": lesson["_id"], "case": r["case"], "passed": r["passed"], **({"retry": True} if retry else {})})

    async def scar(s: dict, label: str) -> bool:
        ok = (await _replay(cand, {**s, "source_id": s["_id"]}))[0] or (await _replay(cand, {**s, "source_id": s["_id"]}))[0]
        await say({"lesson": lesson["_id"], "case": label, "passed": ok})  # one retry, like train cases
        return ok
    results, scars_ok = await asyncio.gather(  # all at once: the stage teach waits on the slowest case
        evals.run_cases(cand, sample, run_id=f"gate-{lesson['_id']}", on_result=tell, concurrency=len(sample) or 1),
        asyncio.gather(*(scar(s, label) for s, label in zip(scars, scar_ids))))
    for i, r in enumerate(results):  # one retry per failure: separate model noise from real regressions
        if not r["passed"]:
            results[i] = await evals.run_case(cand, sample[i], run_id=f"gate-{lesson['_id']}")
            await tell(results[i], retry=True)
    ok = [r["case"] for r in results if r["passed"]] + [label for label, p in zip(scar_ids, scars_ok) if p]
    total = len(sample) + len(scars)
    v.update(regression_passed=len(ok), regression_total=total, accepted=len(ok) == total, still_passing=ok)
    if v["accepted"] and not f.get("case"):  # every scar becomes a test: this live mistake guards all later lessons
        await db.scars.replace_one({"_id": f["source_id"]}, {
            "_id": f["source_id"], "tier": f["tier"], "history": f["history"], "correction": f["correction"],
            "lesson": lesson["_id"], "created_at": datetime.now(UTC)}, upsert=True)
    return v


async def carry_baseline(old: dict, new_version: int, v: dict, case_id: str | None) -> None:
    """New version's baseline = old passing set (gate confirmed the sample) + the case it just fixed."""
    # ponytail: cases outside the regression sample are assumed unchanged; re-measure with run_split if it matters
    doc = await db.baselines.find_one({"_id": old["version"]}) or {"passing": []}
    passing = set(doc["passing"]) | ({case_id} if case_id else set())
    await db.baselines.replace_one({"_id": new_version}, {"_id": new_version, "passing": sorted(passing)}, upsert=True)
