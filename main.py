import logging
import os
from threading import Thread

from dotenv import load_dotenv
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from ai_employee_engine import ai_employee_reply

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

web_app = Flask(__name__)


@web_app.route("/")
def home():
    return "Vyapar AI is running"


@web_app.route("/health")
def health():
    return {"status": "ok", "service": "Vyapar AI"}


def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Namaste 🙏 Ma Vyapar AI ho. Hajurlai k ma help garna sakchu?"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text

    reply = await ai_employee_reply(
        user_text=user_message,
        user_id=update.effective_user.id,
    )

    await update.message.reply_text(reply)


def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")

    Thread(target=run_web_server, daemon=True).start()

    logger.info("Starting Vyapar AI Telegram Bot...")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is running...")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
