"""Evolution: run the train cases, learn from every failure, repeat. Optionally measure held-out per version.

    uv run python -m kintsugi.evolve --rounds 2 --measure

Cases are written by Thomas, so lessons learned from them are owner-trusted (no quarantine),
even when the case plays a stranger.
"""
import argparse
import asyncio

from . import evals, gate, genome, learner


async def measure(label_prefix: str = "v") -> None:
    g = await genome.current()
    run = await evals.run_split(f"{label_prefix}{g['version']}", "heldout", g)
    print(f"  held-out @ v{g['version']}: {run['passed']}/{run['n']} ({run['pass_rate']:.0%})")


async def main(rounds: int, measure_heldout: bool) -> None:
    if measure_heldout:
        await measure()
    for rnd in range(1, rounds + 1):
        g = await genome.current()
        passing = set(await gate.baseline_passing(g))
        failing = [c for c in evals.cases("train") if c["id"] not in passing]
        print(f"round {rnd}: genome v{g['version']}, {len(failing)} failing train cases")
        if not failing:
            break
        for case in failing:
            g = await genome.current()
            res = await evals.run_case(g, case, run_id="evolve")  # an earlier lesson may already fix it
            if res["passed"]:
                print(f"  {case['id']}: already fixed")
                continue
            result = await learner.learn({
                "source_id": f"case:{case['id']}", "kind": "case", "tier": "owner",
                "history": [{"role": "user", "content": m} for m in case["messages"]],
                "steps": res["steps"], "reply": res["reply"], "correction": case.get("correction"),
                "case": case, "failed": res["failed"]})
            lesson = result.get("lesson") or {}
            print(f"  {case['id']}: {result['status']}" + (f" → v{result['version']} [{lesson['section']}] {lesson['text']}"
                                                           if result["status"] == "accepted" else ""))
            if result["status"] == "accepted" and measure_heldout:
                await measure()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--rounds", type=int, default=1)
    p.add_argument("--measure", action="store_true", help="run held-out after each accepted lesson (curve)")
    a = p.parse_args()
    asyncio.run(main(a.rounds, a.measure))
