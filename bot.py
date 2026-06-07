import logging
import os
import re

from dotenv import load_dotenv
load_dotenv()

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import db

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = int(os.environ["TELEGRAM_CHAT_ID"])
DIGEST_HOUR = 21  # 9pm

VAULTS = {"trip"}
DEFAULT_VAULT = "trip"
QUICK_AMOUNTS = [5, 10, 15, 20]

logging.basicConfig(level=logging.INFO)


def _quick_keyboard():
    buttons = [InlineKeyboardButton(f"${a}", callback_data=str(a)) for a in QUICK_AMOUNTS]
    return InlineKeyboardMarkup([buttons])


def _totals_text(totals: dict) -> str:
    if not totals:
        return "Nothing saved yet."
    lines = [f"  {vault}: ${amount:.2f}" for vault, amount in sorted(totals.items())]
    return "\n".join(lines)


async def _save_and_reply(amount: float, reply_fn):
    db.add_entry(DEFAULT_VAULT, amount)
    totals = db.get_totals()
    running = totals.get(DEFAULT_VAULT, 0)
    await reply_fn(
        f"+${amount:.2f} → {DEFAULT_VAULT}\nRunning total: ${running:.2f}",
        reply_markup=_quick_keyboard(),
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "How much did you save?",
        reply_markup=_quick_keyboard(),
    )


async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your chat ID: `{update.effective_user.id}`", parse_mode="Markdown")


async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    totals = db.get_totals()
    await update.message.reply_text(
        f"Pending transfers:\n{_totals_text(totals)}",
        reply_markup=_quick_keyboard(),
    )


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = db.get_history(7)
    if not rows:
        await update.message.reply_text("No entries in last 7 days.", reply_markup=_quick_keyboard())
        return
    lines = [
        f"{r['date']} | ${r['amount']:.2f}" + (f" — {r['note']}" if r['note'] else "")
        for r in rows
    ]
    await update.message.reply_text("Last 7 days:\n" + "\n".join(lines), reply_markup=_quick_keyboard())


async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    totals = db.get_totals()
    amount = totals.get(DEFAULT_VAULT, 0)
    db.mark_transferred(DEFAULT_VAULT)
    await update.message.reply_text(
        f"Marked ${amount:.2f} → {DEFAULT_VAULT} as transferred. Balance reset.",
        reply_markup=_quick_keyboard(),
    )


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    amount = float(query.data)
    await _save_and_reply(amount, query.edit_message_text)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # accept plain number or number with optional note
    match = re.match(r"^(\d+(?:\.\d+)?)\s*(.*)?$", text)
    if not match:
        await update.message.reply_text(
            "Send a number (e.g. 20) or tap a button.",
            reply_markup=_quick_keyboard(),
        )
        return

    amount = float(match.group(1))
    note = match.group(2).strip() or None
    db.add_entry(DEFAULT_VAULT, amount, note)
    totals = db.get_totals()
    running = totals.get(DEFAULT_VAULT, 0)
    await update.message.reply_text(
        f"+${amount:.2f} → {DEFAULT_VAULT}\nRunning total: ${running:.2f}",
        reply_markup=_quick_keyboard(),
    )


async def send_digest(context: ContextTypes.DEFAULT_TYPE):
    totals = db.get_totals()
    if not totals:
        return
    text = f"Daily digest — transfer these to SoFi vaults:\n{_totals_text(totals)}\n\nReply /done to reset after transferring."
    await context.bot.send_message(chat_id=CHAT_ID, text=text, reply_markup=_quick_keyboard())


def main():
    db.init_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("myid", cmd_myid))
    app.add_handler(CommandHandler("summary", cmd_summary))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("done", cmd_done))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.job_queue.run_daily(send_digest, time=__import__("datetime").time(DIGEST_HOUR, 0, 0))

    app.run_polling()


if __name__ == "__main__":
    main()
