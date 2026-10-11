"""Reset the judges' sandbox: copy the live Tsugi (genomes, lessons, lineage, runs, live world) into its own database.
`DB_NAME=kintsugi_sandbox uv run python -m kintsugi.sandbox`, then restart the sandbox server (it caches the genome)."""
import asyncio

from . import config, db as dbm

SOURCE = "kintsugi"  # the live bot's database: read only


async def reset() -> None:
    assert config.DB_NAME.startswith("kintsugi_") and config.DB_NAME != SOURCE, "set DB_NAME to the sandbox's database"
    src = dbm.client[SOURCE]
    await dbm.client.drop_database(config.DB_NAME)
    for c in ["genomes", "lessons", "baselines", "lineage", "gates", "scars", "episodes", "runs", *dbm.TOOL_COLLS]:
        q = {"world": "live"} if c in dbm.TOOL_COLLS else {"kind": "live"} if c == "episodes" else {}
        docs = await src[c].find(q).to_list()
        if docs:
            await dbm.db[c].insert_many(docs)
        print(c, len(docs), flush=True)
    await dbm.setup()
    await dbm.ensure_search_indexes(1024)
    while True:  # Atlas builds search indexes in the background (~45 s)
        idx = [i for c in ("lessons", "notes", "episodes") for i in await (await dbm.db[c].list_search_indexes()).to_list()]
        if idx and all(i.get("queryable") for i in idx):
            break
        await asyncio.sleep(5)
    print(f"{config.DB_NAME} ready: {[i['name'] for i in idx]}", flush=True)


if __name__ == "__main__":
    asyncio.run(reset())
