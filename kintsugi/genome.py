"""The genome: Tsugi's versioned harness config, the part Kintsugi rewrites.

Four sections (Problem Statement 1): rules · context_policies · guardrails · tool_access.
Every version is a document. Lessons add to it; commits are transactions; revoke walks lineage
with $graphLookup. The agent keeps the latest version in memory and a change stream hot-swaps it.
"""
from datetime import UTC, datetime

from . import config, models
from .db import VECTOR_INDEX, client, db, ensure_search_indexes
from .tools import ALL_TOOLS

BASE = {
    "rules": [
        "You are Tsugi, Thomas's personal assistant on Telegram. Be brief and friendly.",
        "Act with tools; never claim something is done unless a tool confirmed it.",
        "When details are missing, pick sensible defaults and act, then say what you assumed. Don't ask first.",
    ],
    "context_policies": [],
    "guardrails": [],
    "tool_access": {"owner": ALL_TOOLS, "stranger": ALL_TOOLS},
}
SECTIONS = ("rules", "context_policies", "guardrails", "tool_access")


def materialize(version: int, lessons: list[dict], cause: dict | None = None) -> dict:
    g = {
        "version": version,
        "rules": [{"text": t, "lesson": None} for t in BASE["rules"]],
        "context_policies": [{"text": t, "lesson": None} for t in BASE["context_policies"]],
        "guardrails": [{"text": t, "lesson": None} for t in BASE["guardrails"]],
        "tool_access": {tier: list(tools) for tier, tools in BASE["tool_access"].items()},
        "lessons": [l["_id"] for l in lessons],
        "tools_known": list(ALL_TOOLS),
        "cause": cause or {"op": "init"},
        "created_at": datetime.now(UTC),
    }
    for l in lessons:
        if l["section"] == "tool_access":
            allowed = g["tool_access"].setdefault(l["tier"], [])
            for t in l.get("tools", []):
                if l.get("allow") and t not in allowed:
                    allowed.append(t)
                elif not l.get("allow") and t in allowed:
                    allowed.remove(t)
        else:
            g[l["section"]].append({"text": l["text"], "lesson": l["_id"]})
    return g


def allowed_tools(g: dict, tier: str) -> list[str]:
    """Tools genome g lets `tier` use. Tools added to the registry after g was built get BASE access
    (stored versions snapshot their tool lists); tools a lesson removed stay removed."""
    known = set(g.get("tools_known") or [t for tools in g["tool_access"].values() for t in tools])
    return [t for t in ALL_TOOLS if t in g["tool_access"].get(tier, [])
            or (t not in known and t in BASE["tool_access"].get(tier, []))]


_current: dict | None = None


async def current() -> dict:
    global _current
    if _current is None:
        _current = await db.genomes.find_one(sort=[("version", -1)])
        if _current is None:
            _current = materialize(0, [])
            await db.genomes.insert_one(_current)
    return _current


def hot_swap(g: dict) -> None:
    """Called by the change-stream watcher when a new genome version is committed."""
    global _current
    if _current is None or g["version"] > _current["version"]:
        _current = g


async def _rebuild(session, cause: dict) -> dict:
    last = await db.genomes.find_one(sort=[("version", -1)], session=session)
    active = await db.lessons.find({"status": "active"}, session=session).sort("created_at").to_list()
    g = materialize((last["version"] if last else 0) + 1, active, cause)
    await db.genomes.insert_one(g, session=session)
    return g


async def commit(lesson: dict, parents: list[str]) -> dict:
    """Activate a lesson: lesson + lineage node + genome vN+1, all or nothing."""
    lesson = {**lesson, "status": "active", "parents": parents}

    async def txn(s):
        await db.lessons.replace_one({"_id": lesson["_id"]}, lesson, upsert=True, session=s)
        await db.lineage.update_one({"_id": lesson["_id"]}, {"$set": {
            "type": "lesson", "parents": parents, "status": "active", "label": lesson["text"],
            "trust": lesson["source"]["tier"]}}, upsert=True, session=s)
        return await _rebuild(s, {"op": "commit", "lesson": lesson["_id"]})

    async with client.start_session() as s:
        g = await s.with_transaction(txn)
    hot_swap(g)
    return g


async def descendants(node_id: str) -> list[str]:
    docs = await (await db.lineage.aggregate([
        {"$match": {"_id": node_id}},
        {"$graphLookup": {"from": "lineage", "startWith": "$_id", "connectFromField": "_id",
                          "connectToField": "parents", "as": "down"}},
    ])).to_list()
    return [d["_id"] for d in docs[0]["down"]] if docs else []


async def revoke(node_id: str) -> dict:
    """Revoke a lesson or a source (episode/case) and everything learned from it."""
    ids = [node_id] + await descendants(node_id)

    async def txn(s):
        await db.lessons.update_many({"_id": {"$in": ids}, "status": {"$in": ["active", "quarantined"]}},
                                     {"$set": {"status": "revoked", "revoked_at": datetime.now(UTC)}}, session=s)
        await db.lineage.update_many({"_id": {"$in": ids}}, {"$set": {"status": "revoked"}}, session=s)
        return await _rebuild(s, {"op": "revoke", "node": node_id, "revoked": ids})

    async with client.start_session() as s:
        g = await s.with_transaction(txn)
    hot_swap(g)
    return {"revoked": ids, "version": g["version"]}


async def embed_lesson(lesson: dict) -> None:
    """Store the lesson's embedding (Atlas Vector Search indexes it for retrieval and dedup)."""
    try:
        [vec] = await models.embed([lesson["text"]])
    except Exception:
        return  # retrieval falls back to "all lessons"; never block learning on embeddings
    lesson["embedding"] = vec
    await ensure_search_indexes(len(vec))


async def similar_lessons(text: str, k: int = config.LESSONS_TOP_K, statuses=("active",),
                          ids: list[str] | None = None) -> list[dict] | None:
    """Top-k lessons by meaning ($vectorSearch), among `ids` (a genome's lessons) or else by status.
    None if vector search isn't available yet."""
    try:
        [vec] = await models.embed([text], "query")
        return await (await db.lessons.aggregate([
            {"$vectorSearch": {"index": VECTOR_INDEX, "path": "embedding", "queryVector": vec,
                               "numCandidates": max(50, k * 10), "limit": k,
                               "filter": {"_id": {"$in": ids}} if ids is not None else {"status": {"$in": list(statuses)}}}},
            {"$project": {"text": 1, "section": 1, "score": {"$meta": "vectorSearchScore"}}},
        ])).to_list()
    except Exception:
        return None
