"""Atlas client: one cluster is both the operational DB and the vector DB."""
import re

from pymongo import ASCENDING, DESCENDING, AsyncMongoClient
from pymongo.operations import SearchIndexModel

from . import config

client = AsyncMongoClient(config.MONGODB_URI, tz_aware=True)
db = client[config.DB_NAME]

# Tool data; every doc carries `world` ("live" or "eval:<run>:<case>")
TOOL_COLLS = ["events", "notes", "reminders", "contacts", "outbox"]
VECTOR_INDEX = "lessons_vec"
NOTES_VEC, NOTES_TEXT = "notes_vec", "notes_text"
EPISODES_VEC = "episodes_vec"  # long memory: the owner's past live turns, recalled by meaning


async def setup() -> None:
    for c in TOOL_COLLS:
        await db[c].create_index("world")
    await db.episodes.create_index([("created_at", DESCENDING)])
    await db.lessons.create_index("status")
    await db.lineage.create_index("parents")
    await db.genomes.create_index([("version", DESCENDING)], unique=True)
    await db.runs.create_index([("created_at", ASCENDING)])


async def ensure_search_indexes(dims: int) -> None:
    """Vector indexes on lesson and note embeddings + a keyword index on notes (fused by $rankFusion).
    Created once we know the embedding size; Atlas takes ~45 s to build them."""
    want = {
        ("lessons", VECTOR_INDEX): {"fields": [
            {"type": "vector", "path": "embedding", "numDimensions": dims, "similarity": "cosine"},
            {"type": "filter", "path": "status"}, {"type": "filter", "path": "_id"}]},
        ("notes", NOTES_VEC): {"fields": [
            {"type": "vector", "path": "embedding", "numDimensions": dims, "similarity": "cosine"},
            {"type": "filter", "path": "world"}]},
        ("episodes", EPISODES_VEC): {"fields": [
            {"type": "vector", "path": "embedding", "numDimensions": dims, "similarity": "cosine"},
            {"type": "filter", "path": "chat"}]},
        ("notes", NOTES_TEXT): {"analyzer": "lucene.english", "mappings": {"dynamic": False, "fields": {
            "text": {"type": "string"}, "tags": {"type": "string"}, "world": {"type": "token"}}}},
    }
    for (coll, name), definition in want.items():
        if name not in [i["name"] async for i in await db[coll].list_search_indexes()]:
            await db[coll].create_search_index(SearchIndexModel(
                name=name, definition=definition, type="search" if name == NOTES_TEXT else "vectorSearch"))


async def wipe_world(world_prefix: str) -> None:
    for c in TOOL_COLLS:
        await db[c].delete_many({"world": {"$regex": "^" + re.escape(world_prefix)}})
