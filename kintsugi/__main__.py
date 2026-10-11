"""One process: Telegram bot + API/live view + change-stream watcher.  `uv run python -m kintsugi`"""
import asyncio

import uvicorn
from telegram import Update

from . import api, config, db, genome, seed, telegram


async def main() -> None:
    await db.setup()
    await seed.seed()
    g = await genome.current()
    server = uvicorn.Server(uvicorn.Config(api.app, host="0.0.0.0", port=config.PORT, log_level="warning"))
    bot = telegram.build()
    if bot:
        await bot.initialize()
        await bot.start()
        await bot.updater.start_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    print(f"Tsugi up · http://localhost:{config.PORT} · telegram {'on' if bot else 'off (no token)'} · genome v{g['version']}",
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


if __name__ == "__main__":
    asyncio.run(main())
