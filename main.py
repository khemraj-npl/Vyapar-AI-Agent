# main.py

import os
import logging
from fastapi import FastAPI
from threading import Thread

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from ai_employee_engine import ai_employee_reply

# ---------------- LOGGING ----------------

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# ---------------- FASTAPI ----------------

app = FastAPI()

@app.get("/")
def home():
    return {"status": "Vyapar AI Employee is running"}

# ---------------- TELEGRAM BOT ----------------

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")

# ---------------- COMMANDS ----------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Namaste 🙏 Ma Vyapar AI Employee ho.\nTapailai k help garna sakchu?"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Malai business, products, customer support, sales ra marketing ko question sodhna saknuhuncha."
    )

# ---------------- MESSAGE HANDLER ----------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_message = update.message.text
    user_id = str(update.effective_user.id)

    logger.info(f"Message from {user_id}: {user_message}")

    try:
        ai_response = ai_employee_reply(user_id, user_message)

        await update.message.reply_text(ai_response)

    except Exception as e:
        logger.error(f"Error: {e}")

        await update.message.reply_text(
            "Sorry 😅 Ahile system ma issue aayo. Kripaya feri try garnus."
        )

# ---------------- RUN BOT ----------------

def run_bot():

    logger.info("Starting Vyapar AI Employee Bot...")

    telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    telegram_app.add_handler(CommandHandler("start", start_command))
    telegram_app.add_handler(CommandHandler("help", help_command))

    telegram_app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    logger.info("Bot is running...")

    telegram_app.run_polling(drop_pending_updates=True)

# ---------------- START THREAD ----------------

bot_thread = Thread(target=run_bot)
bot_thread.start()
