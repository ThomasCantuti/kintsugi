"""One process: Telegram bot + API/live view + change-stream watcher.  `uv run python -m kintsugi`"""
import asyncio
import json
import logging
import re
import urllib.request
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import raindrop.analytics as raindrop
import uvicorn
from telegram import Update

from . import api, config, db, genome, models, seed, telegram


def _raindrop_query(path: str) -> dict:
    req = urllib.request.Request("https://query.raindrop.ai" + path,
                                 headers={"Authorization": f"Bearer {config.RAINDROP_QUERY_API_KEY}"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


async def heal_flagged(bot) -> None:
    """Raindrop → Kintsugi: live turns from the last 2 h that Raindrop flagged and nobody learned from yet → learner."""
    since = (datetime.now(UTC) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    events = (await asyncio.to_thread(_raindrop_query, f"/v1/events?limit=100&timestamp[gte]={since}"))["data"]
    # classifier signals come back on events as {"id": uuid, "name": uuid}: the real names live in /v1/signals
    names = {s["id"]: s["name"] for s in (await asyncio.to_thread(_raindrop_query, "/v1/signals?limit=100"))["data"]}
    for e in events:
        flags = [names.get(s["id"], s["name"]) for s in e.get("signals") or []]
        flags = [n for n in flags if re.sub(r"[\s_-]", "", n.lower()) in config.RAINDROP_FLAGS]
        ep = flags and await db.db.episodes.find_one({"_id": e["id"], "kind": "live"})
        if ep and not await db.db.lineage.find_one({"_id": e["id"]}):  # no 👎 correction or earlier flag learned from it
            await telegram.heal_flag(bot, ep, flags)


async def raindrop_flags(bot) -> None:
    while True:
        await asyncio.sleep(60)
        try:
            await heal_flagged(bot)
        except Exception as e:  # Raindrop or network down: try again next minute
            print(f"raindrop flags: {e!r}", flush=True)


async def ring_due(bot, now: datetime) -> None:
    """Ping the owner for live reminders due in the last 10 min (older ones fell due while the bot was down)."""
    fmt = "%Y-%m-%dT%H:%M"  # reminder_set stores Pacific wall-clock strings in this format
    due = {"world": "live", "sent": {"$exists": False},
           "at": {"$lte": now.strftime(fmt), "$gt": (now - timedelta(minutes=10)).strftime(fmt)}}
    async for r in db.db.reminders.find(due):
        await bot.send_message(config.OWNER_TELEGRAM_ID, f"⏰ {telegram.escape(r['text'])}")
        await db.db.reminders.update_one({"_id": r["_id"]}, {"$set": {"sent": now}})


async def reminders(bot) -> None:
    while True:
        try:
            await ring_due(bot, datetime.now(ZoneInfo(config.TIMEZONE)))
        except Exception as e:  # Telegram or Atlas hiccup: try again next tick
            print(f"reminders: {e!r}", flush=True)
        await asyncio.sleep(20)


async def main() -> None:
    if config.RAINDROP_WRITE_KEY:  # live turns only; tool spans sent directly, no auto-instrumentation of eval/gate calls
        raindrop.init(config.RAINDROP_WRITE_KEY, tracing_enabled=True, auto_instrument=False, bypass_otel_for_tools=True)
        logging.getLogger("raindrop").addHandler(logging.StreamHandler())  # the SDK logs to a NullHandler: failed sends were silent
    await db.setup()
    try:  # build the search indexes now, so the first live lesson doesn't wait ~45 s for Atlas
        await db.ensure_search_indexes(len((await models.embed(["probe"]))[0]))
    except Exception as e:
        print(f"vector search off: {e}")
    await seed.seed()
    g = await genome.current()
    server = uvicorn.Server(uvicorn.Config(api.app, host="0.0.0.0", port=config.PORT, log_level="warning"))
    bot = telegram.build()
    api.bot = bot.bot if bot else None
    if bot:
        await bot.initialize()
        await bot.start()
        await bot.updater.start_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    print(f"Tsugi up · http://localhost:{config.PORT} · telegram {'on' if bot else 'off (no token)'} · "
          f"raindrop {'on' if config.RAINDROP_WRITE_KEY else 'off'}{' + flags → learner' if config.RAINDROP_QUERY_API_KEY else ''} · "
          f"genome v{g['version']}",
          flush=True)
    tasks = [asyncio.create_task(server.serve()), asyncio.create_task(api.watch())]
    if config.RAINDROP_QUERY_API_KEY:
        tasks.append(asyncio.create_task(raindrop_flags(bot.bot if bot else None)))
    if bot and config.OWNER_TELEGRAM_ID:
        tasks.append(asyncio.create_task(reminders(bot.bot)))
    try:  # uvicorn handles SIGINT/SIGTERM (and a busy port) by returning: then everything stops
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for t in tasks:
            t.cancel()
        if bot:
            await bot.updater.stop()
            await bot.stop()
            await bot.shutdown()
        if config.RAINDROP_WRITE_KEY:
            raindrop.shutdown()  # flush buffered events and open interactions


if __name__ == "__main__":
    asyncio.run(main())
