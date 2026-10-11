"""One process: Telegram bot + API/live view + change-stream watcher.  `uv run python -m kintsugi`"""
import asyncio
import logging

import raindrop.analytics as raindrop
import uvicorn
from telegram import Update

from . import api, config, db, genome, models, seed, telegram


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
    if bot:
        await bot.initialize()
        await bot.start()
        await bot.updater.start_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    print(f"Tsugi up · http://localhost:{config.PORT} · telegram {'on' if bot else 'off (no token)'} · "
          f"raindrop {'on' if config.RAINDROP_WRITE_KEY else 'off'} · genome v{g['version']}",
          flush=True)
    tasks = [asyncio.create_task(server.serve()), asyncio.create_task(api.watch())]
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
