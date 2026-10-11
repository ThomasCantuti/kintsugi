"""Task evals on hand-written cases (evals/cases.json), scored only by deterministic checks.

    uv run python -m kintsugi.evals --label A --split heldout
    uv run python -m kintsugi.evals --label A0 --split heldout --raw
    uv run python -m kintsugi.evals --label C --split heldout --model anthropic/claude-sonnet-5.5 --version 0

The learner and gate may only call `cases("train")`; held-out is for measurement only.
"""
import argparse
import asyncio
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from . import agent, config, genome
from .agent import RAW, Switches
from .db import TOOL_COLLS, db, wipe_world

CASES_FILE = Path(__file__).resolve().parent.parent / "evals" / "cases.json"
CONCURRENCY = 4


def cases(split: str) -> list[dict]:
    return [c for c in json.loads(CASES_FILE.read_text()) if c["split"] == split]


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
            await db[coll].insert_many([{**{k: v for k, v in d.items() if k != "_id"}, "world": world} for d in docs])
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


async def run_cases(g: dict, case_list: list[dict], model=None, sw: Switches = Switches(), run_id="adhoc") -> list[dict]:
    sem = asyncio.Semaphore(CONCURRENCY)

    async def one(c):
        async with sem:
            return await run_case(g, c, model, sw, run_id)

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
    p.add_argument("--trials", type=int, default=1)
    a = p.parse_args()
    g = await db.genomes.find_one({"version": a.version}) if a.version is not None else await genome.current()
    sw = RAW if a.raw else Switches()
    if a.naive:
        sw = Switches(naive_memory="\n".join(f"- {c['correction']}" for c in cases("train") if c.get("correction")))
    run = await run_split(a.label, a.split, g, a.model, sw, a.trials)
    print(f"{run['label']} {run['split']} model={run['model']} genome=v{run['genome_version']} "
          f"passed {run['passed']}/{run['n']} ({run['pass_rate']:.0%}) cost=${run['cost']:.4f} {run['counters']}")
    for r in run["results"]:
        if not r["passed"]:
            print(f"  FAIL {r['case']}: {r['errors'] or [json.dumps(c) for c in r['failed']]}")


if __name__ == "__main__":
    asyncio.run(_main())
