# main.py
# Telegram bot entry point.
# Routes all messages through the AI commerce employee engine.

import os
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Commerce engine — replaces simple ai_engine for all message handling
from ai_employee_engine import ai_employee_reply, clear_memory

# Prompts / UI messages
from prompts import WELCOME_MESSAGE, THINKING_MESSAGE, ERROR_MESSAGE

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ── Command Handlers ──────────────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Greets new users and shows what the bot can do."""
    user = update.effective_user
    logger.info(f"User started: {user.id} ({user.first_name})")
    await update.message.reply_text(WELCOME_MESSAGE)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows available commands and usage tips."""
    help_text = (
        "📚 *AI Sales Assistant — Help*\n\n"
        "*Commands:*\n"
        "/start — Bot सुरु गर्नुस्\n"
        "/help — यो help message\n"
        "/reset — Conversation clear गर्नुस्\n"
        "/about — Bot बारे जान्नुस्\n\n"
        "*के सोध्न सक्नुहुन्छ?*\n"
        "• Product price र details\n"
        "• Delivery time र charge\n"
        "• COD available छ?\n"
        "• Exchange / Return policy\n"
        "• Discount negotiate गर्न\n\n"
        "_Nepali, English, वा Nepanglish — सबै OK छ!_"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clears the user's conversation memory and starts fresh."""
    user_id = update.effective_user.id
    clear_memory(user_id)
    await update.message.reply_text("✅ Conversation reset भयो! नयाँ कुरा सुरु गर्नुस् 🙏")


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows info about the bot."""
    about_text = (
        "🤖 *AI Commerce Employee Bot*\n\n"
        "*Powered by:* Google Gemini AI\n"
        "*Language:* Nepali · English · Nepanglish\n"
        "*Speciality:* eCommerce sales, negotiation, delivery, COD, returns\n\n"
        "Nepal का online businesses लाई smart AI employee दिन बनाइएको हो।"
    )
    await update.message.reply_text(about_text, parse_mode="Markdown")


# ── Main Message Handler ──────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles all incoming text messages.

    Shows a thinking indicator while the engine processes,
    then replaces it with the AI response.
    """
    user = update.effective_user
    user_message = update.message.text

    logger.info(f"Msg from {user.id} ({user.first_name}): {user_message[:60]}")

    # Show thinking indicator immediately so user knows bot is working
    thinking_msg = await update.message.reply_text(THINKING_MESSAGE)

    try:
        # Route through the commerce AI engine
        reply = await ai_employee_reply(user.id, user_message)

        await thinking_msg.delete()
        await update.message.reply_text(reply)

    except Exception as e:
        logger.error(f"Handler error for user {user.id}: {e}")
        await thinking_msg.edit_text(ERROR_MESSAGE)


# ── Bot Startup ───────────────────────────────────────────────────────────────

def main() -> None:
    """Initializes and starts the Telegram bot in polling mode."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN is not set. "
            "Add it in Replit Secrets. Get it from @BotFather on Telegram."
        )

    logger.info("Starting AI Commerce Employee Bot...")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("about", about_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is running. Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

