"""Tsugi's tools. Data lives in Atlas collections scoped by `world`, so eval checks can read the outcome."""
import json
import re

from bson import ObjectId

from . import models
from .db import NOTES_TEXT, NOTES_VEC, db

STR = {"type": "string"}
INT = {"type": "integer"}
LIST = {"type": "array", "items": {"type": "string"}}
WHEN = {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$", "description": "YYYY-MM-DDTHH:MM, Pacific time"}
DATE = {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$", "description": "YYYY-MM-DD"}
EMAILS = {"type": "array", "items": {"type": "string", "pattern": r"^[^@\s]+@[^@\s]+\.\w+$", "description": "an email address"},
          "description": "emails"}


def _strip(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k not in ("_id", "world", "embedding")}


def _words(q: str) -> dict:
    words = [re.escape(w) for w in re.findall(r"\w+", q) if len(w) > 2] or [re.escape(q)]
    return {"$regex": "|".join(words), "$options": "i"}


_note_vecs: dict[str, list[float]] = {}  # the same fixture notes are re-seeded in every eval world


async def embed_notes(docs: list[dict]) -> list[dict]:
    """Attach embeddings so Atlas Vector Search finds notes by meaning. Never blocks the write."""
    todo = list({d["text"] for d in docs} - _note_vecs.keys())
    try:
        if todo:
            _note_vecs.update(zip(todo, await models.embed(todo)))
    except Exception:
        return docs
    return [{**d, "embedding": _note_vecs[d["text"]]} for d in docs]


async def calendar_create(world, title, start, duration_min, attendees=()):
    doc = {"world": world, "title": title, "start": start, "duration_min": duration_min, "attendees": list(attendees)}
    await db.events.insert_one(doc)
    return f"Created '{title}' at {start} for {duration_min} min" + (f" with {', '.join(attendees)}" if attendees else "")


async def calendar_list(world, date):
    events = await db.events.find({"world": world, "start": {"$regex": f"^{re.escape(date)}"}}).sort("start").to_list()
    return json.dumps([{"id": str(e["_id"]), **_strip(e)} for e in events]) if events else f"No events on {date}"


async def _event(world, event_id) -> dict:
    e = await db.events.find_one({"_id": ObjectId(event_id), "world": world}) if ObjectId.is_valid(event_id) else None
    if not e:
        raise ValueError(f"No event with id '{event_id}'. Call calendar_list for that date to get event ids.")
    return e


async def calendar_move(world, event_id, start):
    e = await _event(world, event_id)
    await db.events.update_one({"_id": e["_id"]}, {"$set": {"start": start}})
    return f"Moved '{e['title']}' from {e['start']} to {start}"


async def calendar_cancel(world, event_id):
    e = await _event(world, event_id)
    await db.events.delete_one({"_id": e["_id"]})
    return f"Cancelled '{e['title']}' at {e['start']}"


async def note_add(world, text, tags=()):
    [doc] = await embed_notes([{"world": world, "text": text, "tags": list(tags)}])
    await db.notes.insert_one(doc)
    return "Note saved"


async def note_search(world, query):
    """Hybrid: Atlas Search (keywords) + Vector Search (meaning), fused with $rankFusion."""
    notes = []
    try:
        [vec] = await models.embed([query], "query")
        notes = await (await db.notes.aggregate([
            {"$rankFusion": {"input": {"pipelines": {
                "meaning": [{"$vectorSearch": {"index": NOTES_VEC, "path": "embedding", "queryVector": vec,
                                               "numCandidates": 50, "limit": 5, "filter": {"world": world}}}],
                "keywords": [{"$search": {"index": NOTES_TEXT, "compound": {
                    "must": [{"text": {"query": query, "path": ["text", "tags"]}}],
                    "filter": [{"equals": {"path": "world", "value": world}}]}}}, {"$limit": 5}],
            }}}},
            {"$limit": 5},
        ])).to_list()
    except Exception:
        pass
    # ponytail: a note reaches the search indexes ~1 s after insert; keyword regex covers that gap
    if not notes:
        q = _words(query)
        notes = await db.notes.find({"world": world, "$or": [{"text": q}, {"tags": q}]}).to_list(10)
    return json.dumps([_strip(n) for n in notes]) if notes else "No matching notes"


async def reminder_set(world, text, at):
    await db.reminders.insert_one({"world": world, "text": text, "at": at})
    return f"Reminder set for {at}: {text}"


async def contact_lookup(world, query):
    q = _words(query)
    contacts = await db.contacts.find({"world": world, "$or": [{"name": q}, {"tags": q}]}).to_list(20)
    return json.dumps([_strip(c) for c in contacts]) if contacts else "No matching contacts"


async def outbox_draft(world, to, subject, body):
    await db.outbox.insert_one({"world": world, "to": list(to), "subject": subject, "body": body, "status": "draft"})
    return f"Draft saved to {', '.join(to)}: {subject}"


async def outbox_send(world, to, subject, body):
    await db.outbox.insert_one({"world": world, "to": list(to), "subject": subject, "body": body, "status": "sent"})
    return f"Email sent to {', '.join(to)}: {subject}"


def _spec(fn, desc, props, required, risk):
    schema = {"type": "function", "function": {"name": fn.__name__, "description": desc,
              "parameters": {"type": "object", "properties": props, "required": required}}}
    return fn.__name__, {"fn": fn, "schema": schema, "risk": risk}


TOOLS = dict([
    _spec(calendar_create, "Create a calendar event.",
          {"title": STR, "start": WHEN, "duration_min": INT, "attendees": EMAILS},
          ["title", "start", "duration_min"], "write"),
    _spec(calendar_list, "List calendar events on a date (with their ids).", {"date": DATE}, ["date"], "read"),
    _spec(calendar_move, "Move an event to a new start time (same duration).", {"event_id": STR, "start": WHEN},
          ["event_id", "start"], "write"),
    _spec(calendar_cancel, "Cancel (delete) an event.", {"event_id": STR}, ["event_id"], "write"),
    _spec(note_add, "Save a note.", {"text": STR, "tags": LIST}, ["text"], "write"),
    _spec(note_search, "Search notes by meaning, words or tag.", {"query": STR}, ["query"], "read"),
    _spec(reminder_set, "Set a reminder that pings Thomas at a time.", {"text": STR, "at": WHEN}, ["text", "at"], "write"),
    _spec(contact_lookup, "Find contacts by name or tag.", {"query": STR}, ["query"], "read"),
    _spec(outbox_draft, "Save an email draft (not sent).", {"to": EMAILS, "subject": STR, "body": STR},
          ["to", "subject", "body"], "write"),
    _spec(outbox_send, "Send an email now.", {"to": EMAILS, "subject": STR, "body": STR},
          ["to", "subject", "body"], "write"),
])
ALL_TOOLS = list(TOOLS)


def validate(name: str, raw: str) -> tuple[dict | None, str | None]:
    """Tool-call repair: parse, coerce and check args against the schema.

    Returns (args, None) when the call is usable, else (None, a targeted error for the model).
    """
    if name not in TOOLS:
        return None, f"Unknown tool '{name}'. Available: {', '.join(TOOLS)}"
    params = TOOLS[name]["schema"]["function"]["parameters"]
    try:
        args = json.loads(raw or "{}")
    except json.JSONDecodeError as e:
        return None, f"Arguments for {name} are not valid JSON ({e}). Send a JSON object matching: {json.dumps(params)}"
    if not isinstance(args, dict):
        return None, f"Arguments for {name} must be a JSON object matching: {json.dumps(params)}"
    props, fixed, problems = params["properties"], {}, []
    for key, value in args.items():
        spec = props.get(key)
        if spec is None:
            continue  # drop unknown args
        if spec["type"] == "integer" and isinstance(value, str) and value.strip().isdigit():
            value = int(value)
        if spec["type"] == "integer" and isinstance(value, float) and value.is_integer():
            value = int(value)
        if spec["type"] == "array" and isinstance(value, str):
            value = [v.strip() for v in value.split(",") if v.strip()]
        ok = {"string": str, "integer": int, "array": list}[spec["type"]]
        if not isinstance(value, ok) or isinstance(value, bool):
            problems.append(f"'{key}' must be {spec['type']}")
            continue
        if "pattern" in spec and not re.match(spec["pattern"], value):
            problems.append(f"'{key}' must match {spec.get('description', spec['pattern'])}, got '{value}'")
            continue
        item = spec.get("items", {})
        if "pattern" in item and (bad := [v for v in value if not (isinstance(v, str) and re.match(item["pattern"], v))]):
            problems.append(f"each '{key}' item must be {item.get('description', item['pattern'])}, got {bad}")
            continue
        fixed[key] = value
    problems += [f"missing '{k}'" for k in params["required"] if k not in args]
    if problems:
        return None, f"Invalid call to {name}: {'; '.join(problems)}. Schema: {json.dumps(params)}"
    return fixed, None
