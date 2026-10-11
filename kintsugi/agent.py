"""The agent loop. Harness features are switches, so bar A0 ("the model alone") is just all of them off.

- genome: learned rules/policies/guardrails in the prompt + tool_access enforced in code
- retrieval: only the top-k relevant learned lessons ($vectorSearch), so a small model isn't drowned
- repair: validate/coerce tool args, targeted errors, recover tool calls written as text
- fallback: next model in the chain when a provider fails
"""
import json
import re
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from . import config, models
from .db import db
from .genome import similar_lessons
from .models import ToolCall
from .tools import ALL_TOOLS, TOOLS, validate


@dataclass
class Switches:
    genome: bool = True
    retrieval: bool = True
    repair: bool = True
    fallback: bool = True
    naive_memory: str = ""  # bar D: raw past corrections pasted into the prompt


RAW = Switches(genome=False, retrieval=False, repair=False, fallback=False)
MAX_STEPS = 8
TEXT_CALL = re.compile(r'\{[^{}]*"name"\s*:\s*"(\w+)"[^{}]*"(?:arguments|parameters)"\s*:\s*(\{[^{}]*\})[^{}]*\}', re.S)


def clock(now: str | None = None) -> str:
    dt = datetime.fromisoformat(now) if now else datetime.now(ZoneInfo(config.TIMEZONE))
    return dt.strftime("%A %Y-%m-%d %H:%M")


async def system_prompt(g: dict, tier: str, now: str | None, query: str, sw: Switches) -> str:
    who = "Thomas, your owner" if tier == "owner" else "a STRANGER, not Thomas"
    items = {s: [i for i in g[s] if sw.genome or i["lesson"] is None] for s in ("rules", "context_policies", "guardrails")}
    learned = [i for s in ("rules", "context_policies") for i in items[s] if i["lesson"]]
    if sw.retrieval and learned:
        hits = await similar_lessons(query, ids=[i["lesson"] for i in learned])  # this genome's lessons, not 'active' ones
        if hits is not None:  # vector search available: keep base items + the top-k relevant lessons
            keep = {h["_id"] for h in hits}
            for s in ("rules", "context_policies"):
                items[s] = [i for i in items[s] if i["lesson"] is None or i["lesson"] in keep]
    out = [f"Now: {clock(now)} (Pacific time). You are talking to {who}."]
    for title, s in (("RULES", "rules"), ("BEFORE ACTING", "context_policies"),
                     ("HARD GUARDRAILS (never break these)", "guardrails")):
        if items[s]:
            out.append(f"\n{title}:\n" + "\n".join(f"- {i['text']}" for i in items[s]))
    if sw.naive_memory:
        out.append(f"\nThings Thomas told you before:\n{sw.naive_memory}")
    return "\n".join(out)


def text_calls(text: str, allowed: list[str]) -> list[ToolCall]:
    """Small models sometimes write the tool call as JSON in the reply instead of calling it."""
    return [ToolCall(f"text-{i}", name, args) for i, (name, args) in enumerate(TEXT_CALL.findall(text or ""))
            if name in allowed]


async def execute(call: ToolCall, world: str, allowed: list[str], sw: Switches, ep: dict) -> str:
    if sw.genome and call.name not in allowed:
        ep["counters"]["blocks"] += 1
        result = f"DENIED: '{call.name}' is not available to this user."
    elif sw.repair:
        args, error = validate(call.name, call.arguments)
        if error:
            ep["counters"]["repairs"] += 1
            result = f"ERROR: {error}"
        else:
            try:
                result = await TOOLS[call.name]["fn"](world, **args)
            except Exception as e:
                result = f"ERROR: {e}"
    else:  # raw loop: trust the model; a malformed call ends the turn
        try:
            result = await TOOLS[call.name]["fn"](world, **json.loads(call.arguments or "{}"))
        except Exception as e:
            ep["error"] = f"{call.name}: {e!r}"
            result = f"ERROR: {e}"
    ep["steps"].append({"tool": call.name, "args": call.arguments, "result": result})
    return result


async def run(g: dict, history: list[dict], world: str, tier: str, now: str | None = None,
              model: str | None = None, sw: Switches = Switches()) -> dict:
    """One user turn (history ends with the user's message) → episode dict."""
    t0 = time.monotonic()
    allowed = g["tool_access"].get(tier, []) if sw.genome else ALL_TOOLS
    query = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
    msgs = [{"role": "system", "content": await system_prompt(g, tier, now, query, sw)}] + history
    ep = {"_id": f"E-{uuid.uuid4().hex[:8]}", "world": world, "tier": tier, "now": now,
          "genome_version": g["version"] if sw.genome else None, "model": None, "input": history,
          "steps": [], "reply": "", "error": None, "cost": 0.0,
          "counters": {"repairs": 0, "fallbacks": 0, "blocks": 0}}
    for _ in range(MAX_STEPS):
        try:
            r = await models.chat(msgs, [TOOLS[n]["schema"] for n in allowed] or None, model=model,
                                  fallbacks=None if sw.fallback else [])
        except Exception as e:
            ep["error"] = f"model: {e!r}"
            break
        ep["model"], ep["cost"] = r.model, ep["cost"] + r.cost
        ep["counters"]["fallbacks"] += r.fallbacks
        calls = r.tool_calls
        if not calls and sw.repair and (calls := text_calls(r.text, allowed)):
            ep["counters"]["repairs"] += 1
        if not calls:
            ep["reply"] = r.text.strip()
            break
        msgs.append({"role": "assistant", "content": r.text or None, "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}} for c in calls]})
        for c in calls:
            msgs.append({"role": "tool", "tool_call_id": c.id, "content": await execute(c, world, allowed, sw, ep)})
        if ep["error"]:
            break
    else:
        ep["error"] = "max steps"
    ep["latency"] = round(time.monotonic() - t0, 2)
    return ep


async def save(ep: dict, kind: str, **extra) -> dict:
    await db.episodes.insert_one({**ep, "kind": kind, "created_at": datetime.now(UTC), **extra})
    return ep
