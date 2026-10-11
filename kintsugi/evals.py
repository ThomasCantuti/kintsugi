"""Task evals on hand-written cases (evals/cases.json), scored only by deterministic checks.

    uv run python -m kintsugi.evals --label A --split heldout
    uv run python -m kintsugi.evals --label A0 --split heldout --raw
    uv run python -m kintsugi.evals --label C --split heldout --model anthropic/claude-sonnet-5.5 --version 0

The learner and gate may only call `cases("train")`; held-out is for measurement only.
"""
import argparse
import asyncio
import json
import re
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from . import agent, config, genome
from .agent import RAW, Switches
from .db import TOOL_COLLS, db, wipe_world
from .tools import embed_notes

CASES_DIR = Path(__file__).resolve().parent.parent / "evals"  # cases.json (train/heldout, frozen) + redteam.json
CONCURRENCY = 4


def cases(split: str) -> list[dict]:
    return [c for f in sorted(CASES_DIR.glob("*.json")) for c in json.loads(f.read_text()) if c["split"] == split]


async def _check(c: dict, world: str, replies: str) -> bool:
    if "coll" in c:
        return await db[c["coll"]].count_documents({**c["filter"], "world": world}) == c["count"]
    if "reply_excludes" in c:
        return c["reply_excludes"].lower() not in replies.lower()
    if "reply_includes_any" in c:
        return any(x.lower() in replies.lower() for x in c["reply_includes_any"])
    raise ValueError(f"unknown check {c}")


async def run_case(g: dict, case: dict, model: str | None = None, sw: Switches = Switches(),
                   run_id: str = "adhoc") -> dict:
    world = f"eval:{run_id}:{case['id']}:{uuid.uuid4().hex[:4]}"
    for coll in TOOL_COLLS:
        if docs := case.get("fixtures", {}).get(coll):
            docs = [{**{k: v for k, v in d.items() if k != "_id"}, "world": world} for d in docs]
            await db[coll].insert_many(await embed_notes(docs) if coll == "notes" else docs)
    history, eps = [], []
    for text in case["messages"]:
        history.append({"role": "user", "content": text})
        ep = await agent.run(g, history, world, case["tier"], case["now"], model, sw)
        eps.append(ep)
        history.append({"role": "assistant", "content": ep["reply"]})
        if ep["error"]:
            break
    replies = "\n".join(e["reply"] for e in eps)
    failed = [c for c in case["checks"] if not await _check(c, world, replies)]
    errors = [e["error"] for e in eps if e["error"]]
    await wipe_world(world)
    for ep in eps:
        await agent.save(ep, "eval", run=run_id, case=case["id"])
    return {"case": case["id"], "passed": not failed and not errors, "failed": failed, "errors": errors,
            "episodes": [e["_id"] for e in eps], "reply": replies, "steps": [s for e in eps for s in e["steps"]],
            "cost": sum(e["cost"] for e in eps),
            "counters": {k: sum(e["counters"][k] for e in eps) for k in ("repairs", "fallbacks", "blocks")}}


async def run_cases(g: dict, case_list: list[dict], model=None, sw: Switches = Switches(), run_id="adhoc",
                    on_result=None, concurrency: int = CONCURRENCY) -> list[dict]:
    sem = asyncio.Semaphore(concurrency)

    async def one(c):
        async with sem:
            r = await run_case(g, c, model, sw, run_id)
        if on_result:  # e.g. the gate's live progress
            await on_result(r)
        return r

    return await asyncio.gather(*(one(c) for c in case_list))


async def run_split(label: str, split: str, g: dict, model: str | None = None, sw: Switches = Switches(),
                    trials: int = 1) -> dict:
    run_id = f"R-{uuid.uuid4().hex[:6]}"
    case_list = cases(split)
    results = []
    for _ in range(trials):
        results += await run_cases(g, case_list, model, sw, run_id)
    passed = sum(r["passed"] for r in results)
    run = {"_id": run_id, "label": label, "split": split, "model": model or config.AGENT_MODEL,
           "genome_version": g["version"] if sw.genome else None, "switches": sw.__dict__, "trials": trials,
           "n": len(results), "passed": passed, "pass_rate": passed / len(results) if results else 0,
           "cost": sum(r["cost"] for r in results),
           "counters": {k: sum(r["counters"][k] for r in results) for k in ("repairs", "fallbacks", "blocks")},
           "results": [{k: r[k] for k in ("case", "passed", "failed", "errors", "cost", "episodes")} for r in results],
           "created_at": datetime.now(UTC)}
    await db.runs.insert_one(run)
    return run


async def _main():
    p = argparse.ArgumentParser()
    p.add_argument("--label", required=True)
    p.add_argument("--split", default="heldout")
    p.add_argument("--model")
    p.add_argument("--version", type=int, help="genome version (default: latest)")
    p.add_argument("--raw", action="store_true", help="A0: all harness switches off")
    p.add_argument("--naive", action="store_true", help="D: paste every train correction into the prompt")
    p.add_argument("--plant", help="with --naive: one stranger-sourced line naive memory stored too (poisoning)")
    p.add_argument("--trials", type=int, default=1)
    p.add_argument("--no-reasoning", action="store_true", help="the agent model answers without hidden reasoning")
    p.add_argument("--judge", action="store_true", help="supervisor agreement with the checks (cases with a correction)")
    a = p.parse_args()
    g = await db.genomes.find_one({"version": a.version}) if a.version is not None else await genome.current()
    sw = RAW if a.raw else Switches()
    if a.naive:
        memory = [c["correction"] for c in cases("train") if c.get("correction")] + ([a.plant] if a.plant else [])
        sw = Switches(naive_memory="\n".join(f"- {m}" for m in memory))
    if a.no_reasoning:
        sw = replace(sw, reasoning=False)
    if a.model:  # a bar named after a model contains only that model's answers (no silent fallback)
        sw = replace(sw, fallback=False)
    run = await run_split(a.label, a.split, g, a.model, sw, a.trials)
    print(f"{run['label']} {run['split']} model={run['model']} genome=v{run['genome_version']} "
          f"passed {run['passed']}/{run['n']} ({run['pass_rate']:.0%}) cost=${run['cost']:.4f} {run['counters']}")
    for r in run["results"]:
        if not r["passed"]:
            print(f"  FAIL {r['case']}: {r['errors'] or [json.dumps(c) for c in r['failed']]}")
    if a.judge:
        await supervisor_agreement(run)


async def supervisor_agreement(run: dict) -> None:
    """How often does the supervisor's verdict match the ground-truth checks? Stored on the run."""
    from .gate import supervisor_judge
    by_id = {c["id"]: c for c in cases(run["split"])}
    agree = n = 0
    for r in run["results"]:
        case = by_id[r["case"]]
        if not case.get("correction"):
            continue
        eps = await db.episodes.find({"_id": {"$in": r["episodes"]}}).to_list()
        steps = [s for e in eps for s in e["steps"]]
        reply = "\n".join(e["reply"] for e in eps)
        history = [{"role": "user", "content": m} for m in case["messages"]]
        verdict = await supervisor_judge(history, steps, reply, case["correction"])
        n += 1
        agree += bool(verdict.get("passed")) == r["passed"]
    await db.runs.update_one({"_id": run["_id"]}, {"$set": {"supervisor_agreement": {"agree": agree, "n": n}}})
    print(f"supervisor agreement with checks: {agree}/{n}")


async def raindrop_agreement(run_id: str, send: bool = True, wait_s: int = 300) -> None:
    """Would Raindrop's flags have caught what the checks fail? Sends a stored run's episodes to Raindrop as
    `tsugi_eval` events (the flag poller only learns from kind=live episodes), waits for its classifiers, stores the
    result on the run. A case-trial counts as flagged if it gets a flag the poller acts on (config.RAINDROP_FLAGS).
        uv run python -c "import asyncio; from kintsugi.evals import raindrop_agreement as r; asyncio.run(r('R-de32c8'))"
    send=False re-reads the flags of an earlier send."""
    import raindrop.analytics as raindrop
    from .__main__ import _raindrop_query
    run = await db.runs.find_one({"_id": run_id})
    eps = {e["_id"]: e async for e in db.episodes.find({"_id": {"$in": [i for r in run["results"] for i in r["episodes"]]}})}
    since = (run.get("raindrop_agreement") or {}).get("sent_at")
    if send:
        since = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        await db.runs.update_one({"_id": run_id}, {"$set": {"raindrop_agreement": {"sent_at": since}}})
        raindrop.init(config.RAINDROP_WRITE_KEY, tracing_enabled=True, auto_instrument=False, bypass_otel_for_tools=True)
        for i, r in enumerate(run["results"]):
            for e in r["episodes"]:
                agent._to_raindrop(eps[e], f"{run_id}-{i}", event="tsugi_eval")
                raindrop.flush()  # shutdown() alone has a 10 s deadline: it delivered 16 of 36 events
        raindrop.shutdown()
        await asyncio.sleep(wait_s)
    query = lambda path: asyncio.to_thread(_raindrop_query, path)
    by_signal = {}
    for s in (await query("/v1/signals?limit=100"))["data"]:
        if re.sub(r"[\s_-]", "", s["name"].lower()) in config.RAINDROP_FLAGS:
            hits = (await query(f"/v1/events?limit=100&signal={s['id']}&timestamp[gte]={since}"))["data"]
            by_signal[s["name"]] = {e["id"] for e in hits} & eps.keys()
    flagged = set().union(*by_signal.values())
    rows = [(any(e in flagged for e in r["episodes"]), r["passed"]) for r in run["results"]]
    res = {"agree": sum(f != p for f, p in rows), "n": len(rows),
           "caught": sum(f and not p for f, p in rows), "failed": sum(not p for _, p in rows),
           "false_alarms": sum(f and p for f, p in rows), "passed": sum(p for _, p in rows),
           "by_signal": {k: len(v) for k, v in by_signal.items()}, "sent_at": since,
           "read_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}
    await db.runs.update_one({"_id": run_id}, {"$set": {"raindrop_agreement": res}})
    print(f"Raindrop agreement with checks on {run_id}: {res}")


if __name__ == "__main__":
    asyncio.run(_main())
