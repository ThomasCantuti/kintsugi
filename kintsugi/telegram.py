"""Telegram channel. 👍/👎 under every reply; 👎 asks for a correction, which goes to the learner.
Owner = OWNER_TELEGRAM_ID, everyone else is a stranger (their lessons are quarantined for the owner).
"""
import raindrop.analytics as raindrop
from telegram import ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from . import agent, config, genome, learner

HISTORY_TURNS = 8
history: dict[int, list[dict]] = {}  # chat id → recent messages
episodes: dict[str, dict] = {}       # episode id → {ep, history, tier}
awaiting: dict[int, str] = {}        # chat id → episode id waiting for a correction


def tier_of(update: Update) -> str:
    return "owner" if update.effective_user and update.effective_user.id == config.OWNER_TELEGRAM_ID else "stranger"


def feedback_buttons(ep_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("👍", callback_data=f"up:{ep_id}"),
                                  InlineKeyboardButton("👎", callback_data=f"down:{ep_id}")]])


LABEL = {"rules": "rule", "context_policies": "context policy", "guardrails": "guardrail", "tool_access": "tool access"}


def describe(result: dict) -> str:
    s = result["status"]
    if s == "accepted":
        l, v = result["lesson"], result["lesson"]["gate"]
        return (f"✨ New {LABEL[l['section']]} · genome v{result['version']}\n{l['text']}\n"
                f"✓ fixed, {v['regression_passed']}/{v['regression_total']} past cases pass")
    if s == "quarantined":
        return "🔒 Thanks! Waiting for my owner's OK."
    if s == "duplicate":
        return "I already know this one. 🌱"
    if s == "false_alarm":
        return f"🌦️ False alarm: that turn was already right. {learner.clip(result['why'], 160)}"
    n = len(result.get("lessons", []))
    return f"No safe fix: {n} candidate{'s' if n != 1 else ''} failed the gate. Nothing changed."


async def on_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    g = await genome.current()
    await update.message.reply_text(f"Hi, I'm Tsugi 🌱 genome v{g['version']}, {len(g['lessons'])} lessons.\n"
                                    "I plan, note, remind and email. 👎 a mistake and I'll learn.")


async def on_genome(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    g = await genome.current()
    lines = [f"Genome v{g['version']} (✨ = learned)"]
    for s, title in (("rules", "Rules"), ("context_policies", "Context policies"), ("guardrails", "Guardrails")):
        lines += [f"\n{title}"] + [f"{'✨' if i['lesson'] else '·'} {learner.clip(i['text'], 120)}" for i in g[s]]
    lines += ["\nTool access"] + [f"· {tier}: {', '.join(tools)}" for tier, tools in g["tool_access"].items()]
    await update.message.reply_text("\n".join(lines)[:4000])


async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat, text, tier = update.effective_chat.id, update.message.text, tier_of(update)
    if chat in awaiting:  # this message is the correction for a 👎
        await learn_from(update, ctx, awaiting.pop(chat), text)
        return
    turns = history.setdefault(chat, [])
    turns.append({"role": "user", "content": text})
    await ctx.bot.send_chat_action(chat, ChatAction.TYPING)
    ep = await agent.run(await genome.current(), turns[-HISTORY_TURNS:], "live", tier)
    await agent.save(ep, "live", chat=chat)
    reply = ep["reply"] or (f"⚠️ {ep['error']}" if ep["error"] else "…")
    turns.append({"role": "assistant", "content": ep["reply"]})
    episodes[ep["_id"]] = {"ep": ep, "history": list(turns[-HISTORY_TURNS - 1:-1]), "tier": tier}
    await update.message.reply_text(reply[:4000], reply_markup=feedback_buttons(ep["_id"]))


async def learn_from(update: Update, ctx: ContextTypes.DEFAULT_TYPE, ep_id: str, correction: str):
    item = episodes.get(ep_id)
    if not item:
        await update.message.reply_text("I lost that conversation, sorry. Try again?")
        return
    ep = item["ep"]
    notify = progress(await update.message.reply_text("🌱 Learning…"))
    f = {"source_id": ep_id, "kind": "telegram", "tier": item["tier"], "history": item["history"],
         "steps": ep["steps"], "reply": ep["reply"], "correction": correction}
    raindrop.track_signal(event_id=ep_id, name="correction", signal_type="edit", after=correction,
                          properties={"tier": item["tier"]})

    async def job():
        result = await learner.learn(f, notify)
        await update.message.reply_text(describe(result))
        if result["status"] == "quarantined":
            await ask_owner(ctx.bot, result["lessons"], "A stranger taught me")

    ctx.application.create_task(job())


def progress(status):
    """A learner `notify` that keeps one Telegram message updated as the gate works."""
    lines = [status.text]

    async def notify(text: str):
        lines.append(text)
        try:
            await status.edit_text("\n".join(lines)[-4000:])
        except Exception:
            pass
    return notify


async def ask_owner(bot, lessons: list[dict], why: str) -> None:
    """Quarantined lessons go to the owner for ✅/❌ (they still have to pass the gate)."""
    for l in lessons if config.OWNER_TELEGRAM_ID else []:
        await bot.send_message(
            config.OWNER_TELEGRAM_ID, f"🔒 {why}:\n{l['text']}\nAllow it? The gate still tests it.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve", callback_data=f"ok:{l['_id']}"),
                                                InlineKeyboardButton("❌ Reject", callback_data=f"no:{l['_id']}")]]))


async def heal_flag(bot, ep: dict, flags: list[str]) -> dict:
    """A live turn Raindrop flagged and nobody corrected: learn from it like a 👎 (the supervisor writes the correction)."""
    f = {"source_id": ep["_id"], "kind": "raindrop", "tier": ep["tier"], "history": ep["input"], "steps": ep["steps"],
         "reply": ep["reply"], "failed": [f"Raindrop flagged this turn: {', '.join(flags)}"]}
    if not (bot and config.OWNER_TELEGRAM_ID):
        return await learner.learn(f)
    status = await bot.send_message(config.OWNER_TELEGRAM_ID, f"🌧️ Raindrop flagged a {ep['tier']} turn ({', '.join(flags)}):\n"
                                    f"“{learner.clip(ep['input'][-1]['content'], 120)}”\n🌱 Learning…")
    result = await learner.learn(f, progress(status))
    if result["status"] == "quarantined":
        await ask_owner(bot, result["lessons"], "Raindrop flagged a stranger's turn. I'd learn")
    else:
        await bot.send_message(config.OWNER_TELEGRAM_ID, describe(result))
    return result


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    action, ref = q.data.split(":", 1)
    if action == "up":
        raindrop.track_signal(event_id=ref, name="thumbs_up", signal_type="feedback", comment="👍", sentiment="POSITIVE")
        await q.answer("Thanks! 🌱")
    elif action == "down":
        raindrop.track_signal(event_id=ref, name="thumbs_down", signal_type="feedback", comment="👎", sentiment="NEGATIVE")
        await q.answer()
        awaiting[q.message.chat.id] = ref
        await q.message.reply_text("What should I have done?", reply_markup=ForceReply(selective=True))
    elif action in ("ok", "no"):
        if update.effective_user.id != config.OWNER_TELEGRAM_ID:
            await q.answer("Only my owner can decide.")
            return
        await q.answer()
        await q.edit_message_reply_markup(None)
        if action == "no":
            await learner.reject(ref)
            await q.message.reply_text("❌ Rejected. Nothing changed.")
            return
        await q.message.reply_text("✅ Approved. Running the gate…")
        ctx.application.create_task(_approve(q, ref))


async def _approve(q, lesson_id: str):
    await q.message.reply_text(describe(await learner.approve(lesson_id)))


def build() -> Application | None:
    if not config.TELEGRAM_BOT_TOKEN:
        return None
    # 5 s defaults lost a reply to a venue Wi-Fi connect stall (12:10, httpcore.ConnectTimeout on sendMessage)
    app = (Application.builder().token(config.TELEGRAM_BOT_TOKEN).concurrent_updates(True)
           .connect_timeout(20).read_timeout(20).write_timeout(20).build())
    app.add_handler(CommandHandler("start", on_start))
    app.add_handler(CommandHandler("genome", on_genome))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    return app
