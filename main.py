import os
import asyncio
import logging
from threading import Thread

import uvicorn
from fastapi import FastAPI
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from ai_employee_engine import ai_employee_reply

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

web_app = FastAPI()


@web_app.get("/")
def health_check():
    return {
        "status": "ok",
        "service": "Vyapar AI Telegram Bot"
    }


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Namaste 🙏 Ma Vyapar AI employee ho. Hajurlai k help garna sakchu?"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    message = update.message.text

    try:
        reply = ai_employee_reply(user_id=user_id, message=message)
        await update.message.reply_text(reply)
    except Exception as e:
        logger.exception("AI reply error")
        await update.message.reply_text(
            "Maile bujhna sakina 😅 Ek choti feri pathaidinus."
        )


def run_health_server():
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(web_app, host="0.0.0.0", port=port)


def run_bot():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Starting Vyapar AI Telegram Bot...")
    app.run_polling()


if __name__ == "__main__":
    Thread(target=run_health_server, daemon=True).start()
    run_bot()
