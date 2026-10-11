"""Atlas client: one cluster is both the operational DB and the vector DB."""
import re

from pymongo import ASCENDING, DESCENDING, AsyncMongoClient
from pymongo.operations import SearchIndexModel

from . import config

client = AsyncMongoClient(config.MONGODB_URI)
db = client[config.DB_NAME]

# Tool data; every doc carries `world` ("live" or "eval:<run>:<case>")
TOOL_COLLS = ["events", "notes", "reminders", "contacts", "outbox"]
VECTOR_INDEX = "lessons_vec"


async def setup() -> None:
    for c in TOOL_COLLS:
        await db[c].create_index("world")
    await db.episodes.create_index([("created_at", DESCENDING)])
    await db.lessons.create_index("status")
    await db.lineage.create_index("parents")
    await db.genomes.create_index([("version", DESCENDING)], unique=True)
    await db.runs.create_index([("created_at", ASCENDING)])


async def ensure_vector_index(dims: int) -> None:
    """Vector index on lesson embeddings (created once we know the embedding size)."""
    existing = [i["name"] async for i in await db.lessons.list_search_indexes()]
    if VECTOR_INDEX in existing:
        return
    await db.lessons.create_search_index(SearchIndexModel(
        name=VECTOR_INDEX, type="vectorSearch",
        definition={"fields": [
            {"type": "vector", "path": "embedding", "numDimensions": dims, "similarity": "cosine"},
            {"type": "filter", "path": "status"},
        ]},
    ))


async def wipe_world(world_prefix: str) -> None:
    for c in TOOL_COLLS:
        await db[c].delete_many({"world": {"$regex": "^" + re.escape(world_prefix)}})
