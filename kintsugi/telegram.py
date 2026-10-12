"""Telegram channel. 👍/👎 under every reply; 👎 asks for a correction, which goes to the learner.
Owner = OWNER_TELEGRAM_ID, everyone else is a stranger (their lessons are quarantined for the owner).
Every message is HTML (bot default): escape anything that comes from a user, the model or the DB.
"""
import re
from datetime import UTC, datetime
from html import escape as _escape
from zoneinfo import ZoneInfo

import raindrop.analytics as raindrop
from telegram import ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, Defaults, MessageHandler, filters

from . import agent, config, genome, learner, models
from .db import EPISODES_VEC, db

HISTORY_TURNS = 8
RECALL_K = 3                         # long memory: past owner turns recalled per message
history: dict[int, list[dict]] = {}  # chat id → recent messages (short memory, rebuilt from Atlas after a restart)
episodes: dict[str, dict] = {}       # episode id → {ep, history, tier}
awaiting: dict[int, str] = {}        # chat id → episode id waiting for a correction


def tier_of(update: Update) -> str:
    return "owner" if update.effective_user and update.effective_user.id == config.OWNER_TELEGRAM_ID else "stranger"


async def recent_turns(chat: int) -> list[dict]:
    """Short memory that survives a restart: the chat's last turns, rebuilt from its live episodes."""
    eps = await db.episodes.find({"kind": "live", "chat": chat}, {"input": {"$slice": -1}, "reply": 1}) \
        .sort("created_at", -1).limit(HISTORY_TURNS // 2).to_list()
    return [m for e in reversed(eps) for m in (e["input"][-1], {"role": "assistant", "content": e["reply"] or ""})]


async def remember(ep: dict) -> None:
    """Long memory (second brain): embed an owner turn so later turns can recall it by meaning."""
    text = f"Thomas: {ep['input'][-1]['content'][:500]}\nTsugi: {ep['reply'][:1000]}"
    try:
        [vec] = await models.embed([text])
        await db.episodes.update_one({"_id": ep["_id"]}, {"$set": {"memory": text, "embedding": vec}})
    except Exception as e:  # memory must never break a turn
        print(f"remember: {e!r}")


async def recall(chat: int, query: str) -> list[dict]:
    """The owner's past turns closest in meaning to this message ($vectorSearch), as one system message."""
    try:
        [vec] = await models.embed([query], "query")
        hits = await (await db.episodes.aggregate([
            {"$vectorSearch": {"index": EPISODES_VEC, "path": "embedding", "queryVector": vec,
                               "numCandidates": 100, "limit": RECALL_K, "filter": {"chat": chat}}},
            {"$project": {"memory": 1, "created_at": 1}}])).to_list()
    except Exception:  # index not built yet, or embeddings down: answer without long memory
        return []
    # ponytail: no score threshold, the top-k are always recalled; add one if unrelated memories confuse replies
    tz = ZoneInfo(config.TIMEZONE)
    lines = [f"[{h['created_at'].astimezone(tz):%a %b %d %H:%M}]\n{h['memory']}" for h in hits]
    return [{"role": "system", "content": "Earlier conversations with Thomas (your memory; may be outdated):\n\n"
             + "\n\n".join(lines)}] if lines else []


def feedback_buttons(ep_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("👍", callback_data=f"up:{ep_id}"),
                                  InlineKeyboardButton("👎", callback_data=f"down:{ep_id}")]])


LABEL = {"rules": "rule", "context_policies": "context policy", "guardrails": "guardrail", "tool_access": "tool access"}


def escape(text: str) -> str:
    return _escape(text, quote=False)  # Telegram HTML knows only &lt; &gt; &amp; (quotes stay literal)


def quote(text: str) -> str:
    return f"<blockquote>{escape(text)}</blockquote>"


def describe(result: dict) -> str:
    s = result["status"]
    if s == "accepted":
        l, v = result["lesson"], result["lesson"]["gate"]
        return (f"✨ <b>Seam {result['version']} · {escape(l.get('title') or LABEL[l['section']])}</b>\n"
                f"<blockquote expandable>{escape(l['text'])}</blockquote>\n"
                f"Gate: fixed, {v['regression_passed']}/{v['regression_total']} past cases pass")
    if s == "quarantined":
        return "🔒 Thanks! Waiting for my owner's OK."
    if s == "duplicate":
        return "🌱 I already know this one."
    if s == "false_alarm":
        return f"🌦️ <b>False alarm</b>: that turn was already right.\n<i>{escape(learner.clip(result['why'], 160))}</i>"
    n = len(result.get("lessons", []))
    return f"🚫 <b>No safe fix</b>: {n} candidate{'s' if n != 1 else ''} failed the gate. Nothing changed."


def reply_html(text: str) -> str:
    """The model writes markdown **bold**; Telegram shows it raw unless it becomes <b>."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escape(text))


async def on_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    g = await genome.current()
    await update.message.reply_text(f"Hi, I'm <b>Tsugi</b> 🌱\n<i>genome v{g['version']} · {len(g['lessons'])} lessons</i>\n\n"
                                    "I plan, note, remind and email. 👎 a mistake and I'll learn.")


async def on_genome(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    g = await genome.current()
    lines = [f"🧬 <b>Genome v{g['version']}</b> · ✨ = learned"]
    for s, title in (("rules", "Rules"), ("context_policies", "Context policies"), ("guardrails", "Guardrails")):
        items = "\n".join(f"{'✨' if i['lesson'] else '·'} {escape(learner.clip(i['text'], 120))}" for i in g[s]) or "empty"
        lines += [f"\n<b>{title}</b> ({len(g[s])})", f"<blockquote expandable>{items}</blockquote>"]
    lines += ["\n<b>Tool access</b>"] + [f"<code>{tier}</code> {', '.join(tools)}" for tier, tools in g["tool_access"].items()]
    # ponytail: no length cap (a cut would break the HTML); items are clipped, so this fits until ~30 lessons
    await update.message.reply_text("\n".join(lines))


async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat, text, tier = update.effective_chat.id, update.message.text, tier_of(update)
    if chat in awaiting:  # this message is the correction for a 👎
        await learn_from(update, ctx, awaiting.pop(chat), text)
        return
    if chat not in history:
        history[chat] = await recent_turns(chat)
    turns = history[chat]
    turns.append({"role": "user", "content": text})
    await ctx.bot.send_chat_action(chat, ChatAction.TYPING)
    memory = await recall(chat, text) if tier == "owner" else []  # long memory is the owner's only
    ep = await agent.run(await genome.current(), memory + turns[-HISTORY_TURNS:], "live", tier)
    await agent.save(ep, "live", chat=chat)
    reply = reply_html(ep["reply"]) if ep["reply"] else f"⚠️ {escape(ep['error'])}" if ep["error"] else "…"
    turns.append({"role": "assistant", "content": ep["reply"]})
    episodes[ep["_id"]] = {"ep": ep, "history": list(turns[-HISTORY_TURNS - 1:-1]), "tier": tier}
    await update.message.reply_text(reply[:4000], reply_markup=feedback_buttons(ep["_id"]))
    who = update.effective_user
    await tell_owner(ctx.bot, ep, f"Telegram · {who.full_name if who else 'unknown'}")
    if tier == "owner" and ep["reply"]:
        await remember(ep)


async def learn_from(update: Update, ctx: ContextTypes.DEFAULT_TYPE, ep_id: str, correction: str):
    item = episodes.get(ep_id)
    if not item:
        await update.message.reply_text("I lost that conversation, sorry. Try again?")
        return
    ep = item["ep"]
    notify = progress(await update.message.reply_text("🌱 <b>Learning</b> from your correction…"))
    f = {"source_id": ep_id, "kind": "telegram", "tier": item["tier"], "history": item["history"],
         "steps": ep["steps"], "reply": ep["reply"], "correction": correction}
    raindrop.track_signal(event_id=ep_id, name="correction", signal_type="edit", after=correction,
                          properties={"tier": item["tier"]})

    async def job():
        result = await learner.learn(f, notify)
        await update.message.reply_text(describe(result))
        if result["status"] == "quarantined":
            await ask_owner(ctx.bot, result["lessons"], "🔒 <b>A stranger taught me</b>")

    ctx.application.create_task(job())


def progress(status):
    """A learner `notify` that keeps one Telegram message updated as the gate works (a result replaces its 'testing' line)."""
    lines = [status.text_html]

    async def notify(text: str):
        if lines[-1].startswith("🧪"):
            lines.pop()
        lines.append(text)
        try:
            await status.edit_text("\n".join(lines))
        except Exception:
            pass
    return notify


async def tell_owner(bot, ep: dict, where: str) -> None:
    """A stranger's request that Tsugi saved for Thomas also reaches his phone right away, in the stranger's own words."""
    if not (bot and config.OWNER_TELEGRAM_ID and ep["tier"] == "stranger"
            and any(s["tool"] == "note_add" and s["result"].startswith("Note saved") for s in ep["steps"])):
        return
    try:
        await bot.send_message(config.OWNER_TELEGRAM_ID, f"📝 <b>A stranger left you a message</b> ({escape(where)})\n"
                               f"{quote(ep['input'][-1]['content'][:1000])}Tsugi's reply: {escape(ep['reply'][:300])}")
    except Exception as e:  # Telegram hiccup: the note is saved anyway
        print(f"tell_owner: {e!r}", flush=True)


async def ask_owner(bot, lessons: list[dict], header: str) -> None:
    """One card per quarantine: the owner picks one candidate (it still has to pass the gate) or none.
    Callback data: ok:<id> · no:<all ids> (ids are ~8 chars, 3 fit in Telegram's 64 bytes)."""
    if not (lessons and config.OWNER_TELEGRAM_ID):
        return
    ids = [l["_id"] for l in lessons]
    lines = [f"{header} · Pick a fix. The gate still tests it."] + [
        f"<b>{chr(65 + i)}</b> · {escape(l.get('title') or learner.clip(l['text'], 60))} <i>[{LABEL[l['section']]}]</i>"
        for i, l in enumerate(lessons)]
    buttons = [InlineKeyboardButton(f"✅ {chr(65 + i)}", callback_data=f"ok:{l['_id']}") for i, l in enumerate(lessons)] + [InlineKeyboardButton("❌ None", callback_data="no:" + ",".join(ids))]
    await bot.send_message(config.OWNER_TELEGRAM_ID, "\n".join(lines), reply_markup=InlineKeyboardMarkup([buttons]))


async def heal_flag(bot, ep: dict, flags: list[str]) -> dict:
    """A live turn Raindrop flagged and nobody corrected: learn from it like a 👎 (the supervisor writes the correction)."""
    f = {"source_id": ep["_id"], "kind": "raindrop", "tier": ep["tier"], "history": ep["input"], "steps": ep["steps"],
         "reply": ep["reply"], "failed": [f"Raindrop flagged this turn: {', '.join(flags)}"], "flags": flags}
    if ep.get("created_at"):  # Raindrop gives no signal time: turn → Kintsugi saw the flag (includes the poll interval)
        f["flag_latency_s"] = int((datetime.now(UTC) - ep["created_at"]).total_seconds())
    if not (bot and config.OWNER_TELEGRAM_ID):
        return await learner.learn(f)
    status = await bot.send_message(config.OWNER_TELEGRAM_ID, f"🌧️ <b>Raindrop flagged</b> a {ep['tier']} turn · {escape(', '.join(flags))}\n"
                                    f"{quote(learner.clip(ep['input'][-1]['content'], 120))}\n🌱 <b>Learning</b>…")
    result = await learner.learn(f, progress(status))
    if result["status"] == "quarantined":
        caught = f", caught in {f['flag_latency_s']} s" if "flag_latency_s" in f else ""  # turn → our poller saw the flag
        await ask_owner(bot, result["lessons"], f"🌧️ <b>Raindrop flagged a stranger's turn</b> ({escape(', '.join(flags))}{caught})")
    else:
        await bot.send_message(config.OWNER_TELEGRAM_ID, describe(result))
    return result


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    action, ref = q.data.split(":", 1)
    if action == "up":
        raindrop.track_signal(event_id=ref, name="thumbs_up", signal_type="feedback", comment="👍", sentiment="POSITIVE")
        await q.answer("Thanks! 🌱")
        await q.edit_message_reply_markup(None)  # one vote per reply, and the chat stays clean
    elif action == "down":
        raindrop.track_signal(event_id=ref, name="thumbs_down", signal_type="feedback", comment="👎", sentiment="NEGATIVE")
        await q.answer()
        await q.edit_message_reply_markup(None)
        awaiting[q.message.chat.id] = ref
        await q.message.reply_text("What should I have done?", reply_markup=ForceReply(selective=True))
    elif action in ("ok", "no"):
        if update.effective_user.id != config.OWNER_TELEGRAM_ID:
            await q.answer("Only my owner can decide.")
            return
        await q.answer()
        # the decision is written on the card itself (this also removes the buttons)
        picked = ref.partition(":")[0]  # older cards also carry ":<others>" (ignored now)
        if action == "no":
            for lesson_id in picked.split(","):
                await learner.reject(lesson_id)
            await q.edit_message_text(f"{q.message.text_html}\n\n❌ <b>None</b>. Nothing changed.")
            return
        label = next((b.text for row in q.message.reply_markup.inline_keyboard for b in row if b.callback_data == q.data), "✅")
        await q.edit_message_text(f"{q.message.text_html}\n\n{label} <b>approved</b>. Running the gate…")
        ctx.application.create_task(_approve(q, picked))


async def _approve(q, lesson_id: str):
    result = await learner.approve(lesson_id)
    await q.message.reply_text(describe(result))
    if result.get("left"):  # the pick failed the gate: offer the alternatives again
        await ask_owner(q.get_bot(), result["left"], "🔒 <b>That fix failed the gate</b>")


def build() -> Application | None:
    if not config.TELEGRAM_BOT_TOKEN:
        return None
    # 5 s defaults lost a reply to a venue Wi-Fi connect stall (12:10, httpcore.ConnectTimeout on sendMessage)
    app = (Application.builder().token(config.TELEGRAM_BOT_TOKEN).concurrent_updates(True)
           .connect_timeout(20).read_timeout(20).write_timeout(20).defaults(Defaults(parse_mode=ParseMode.HTML)).build())
    app.add_handler(CommandHandler("start", on_start))
    app.add_handler(CommandHandler("genome", on_genome))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    return app
