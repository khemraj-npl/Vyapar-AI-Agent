import asyncio
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
import uvicorn
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from ai_employee_engine import ai_employee_reply
from memory_db import init_db

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

web_app = FastAPI()


@web_app.get("/")
async def home():
    return {"status": "ok", "service": "Vyapar AI is running"}


@web_app.get("/health")
async def health():
    return {"status": "healthy"}


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Namaste 🙏 Ma Vyapar AI ho. Hajurlai k ma help garna sakchu?"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_message = update.message.text
        user_id = update.effective_user.id if update.effective_user else "unknown"

        logger.info("Received Telegram message from user_id=%s text=%s", user_id, user_message)

        reply = await ai_employee_reply(
            user_text=user_message,
            user_id=user_id,
        )

        await update.message.reply_text(reply)

    except Exception:
        logger.exception("Telegram message handling failed")

        await update.message.reply_text(
            "🙏 Vyapar AI अहिले temporary issue मा छ। कृपया केही समयपछि फेरि प्रयास गर्नुहोस्।"
        )


async def run_telegram_bot():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")

    logger.info("Starting Vyapar AI Telegram Bot...")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    logger.info("Telegram bot polling started.")

    while True:
        await asyncio.sleep(3600)


async def run_web_server():
    port = int(os.environ.get("PORT", 10000))

    config = uvicorn.Config(
        web_app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )

    server = uvicorn.Server(config)

    logger.info("Starting web server on port %s...", port)
    await server.serve()


async def main():
    init_db()
    logger.info("Memory database initialized.")

    await asyncio.gather(
        run_web_server(),
        run_telegram_bot(),
    )


if __name__ == "__main__":
    asyncio.run(main())
