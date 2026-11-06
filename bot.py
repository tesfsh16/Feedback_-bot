"""
ደ/ማ/ዩ/ግ/ጉባኤ Feedback Bot
Collects feedback from users and forwards it to the admin group.
"""

import asyncio
import logging
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# ── Load environment variables ────────────────────────────────────────────────
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Conversation states ───────────────────────────────────────────────────────
SELECT_DEPARTMENT, WRITE_FEEDBACK = range(2)

# ── Departments ───────────────────────────────────────────────────────────────
DEPARTMENTS = [
    ("📚 ለትምህርት ክፍል",          "ትምህርት ክፍል"),
    ("🎵 ለመዝሙር ክፍል",          "መዝሙር ክፍል"),
    ("💼 ለሙያ ክፍል",            "ሙያ ክፍል"),
    ("🤝 ለባች ማስተባበሪያ ክፍል",   "ባች ማስተባበሪያ ክፍል"),
    ("🌱 ለልማት ክፍል",          "ልማት ክፍል"),
    ("❤️ ለአባላት እንክብካቤ ክፍል",  "አባላት እንክብካቤ ክፍል"),
    ("🗣️ ቋንቋ ክፍል",           "ቋንቋ ክፍል"),
    ("🏛️ ለዋናው ጽ/ቤት",         "ዋናው ጽ/ቤት"),
]

# ── Text constants ────────────────────────────────────────────────────────────
WELCOME_TEXT = (
    "🕊️ እንኳን ወደ ደ/ማ/ዩ/ግ/ጉባኤ በደህና መጣችሁ!\n\n"
    "ልስራችን ግብዓት ይሆነን ዘንድ ማንኛውንም ሃሳብ፣ አስተያየት እንዲሁም "
    "ጥያቄ ማቅረብ ትችላላችሁ።\n\n"
    "👇 እባክዎ አስተያየትዎን ለየትኛው ክፍል እንደሆነ ይምረጡ፦"
)

WRITE_TEXT = (
    "✍️ ሃሳብዎን፣ አስተያየትዎን ወይም ጥያቄዎን ይጻፉ።\n\n"
    "_(ወደ ክፍል ምርጫ ለመመለስ /start ይጫኑ)_"
)

CANCEL_TEXT = "❌ ተሰርዟል። እንደገና ለመጀመር /start ይጫኑ።"

THANKS_TEXT = (
    "✅ አስተያየትዎ ደርሷል! እናመሰግናለን 🙏\n\n"
    "ሌላ አስተያየት ለማስገባት 👉 /start ይጫኑ።"
)

NO_GROUP_TEXT = (
    "⚠️ Admin: GROUP_CHAT_ID is not set.\n"
    "Add the bot to your group, send /chatid, "
    "then set GROUP_CHAT_ID in your environment variables."
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def build_department_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(label, callback_data=f"dept:{value}")
        for label, value in DEPARTMENTS
    ]
    keyboard = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(keyboard)


def user_display(user) -> str:
    name = user.full_name or "ስም የለም"
    username = f" (@{user.username})" if user.username else ""
    return f"{name}{username}"


# ── Handlers ──────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        WELCOME_TEXT,
        reply_markup=build_department_keyboard(),
    )
    return SELECT_DEPARTMENT


async def select_department(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    department = query.data.replace("dept:", "")
    context.user_data["department"] = department
    await query.edit_message_text(
        f"✅ መረጡ: *{department}*\n\n{WRITE_TEXT}",
        parse_mode="Markdown",
    )
    return WRITE_FEEDBACK


async def receive_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    department = context.user_data.get("department", "ያልተገለጸ ክፍል")
    message_text = update.message.text or "(ጽሑፍ አልተላከም)"

    if not GROUP_CHAT_ID:
        await update.message.reply_text(NO_GROUP_TEXT)
        return ConversationHandler.END

    forward_msg = (
        f"📨 *አዲስ አስተያየት*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *ከ:* {user_display(user)}\n"
        f"🆔 *User ID:* `{user.id}`\n"
        f"📂 *ክፍል:* {department}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💬 *አስተያየት:*\n{message_text}"
    )

    try:
        await context.bot.send_message(
            chat_id=int(GROUP_CHAT_ID),
            text=forward_msg,
            parse_mode="Markdown",
        )
        logger.info(f"Feedback from {user.id} ({department}) forwarded.")
    except Exception as e:
        logger.error(f"Failed to forward feedback: {e}")
        await update.message.reply_text(
            "⚠️ አስተያየትዎ መላክ አልተቻለም። እባክዎ ቆይተው እንደገና ይሞክሩ።"
        )
        return ConversationHandler.END

    await update.message.reply_text(THANKS_TEXT)
    context.user_data.clear()
    return ConversationHandler.END


async def chatid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    await update.message.reply_text(
        f"🆔 *Chat ID:* `{chat.id}`\n"
        f"📛 *ስም:* {chat.title or update.effective_user.full_name}\n"
        f"📋 *አይነት:* {chat.type}",
        parse_mode="Markdown",
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(CANCEL_TEXT)
    return ConversationHandler.END


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "❓ ያልታወቀ ትዕዛዝ። ለመጀመር /start ይጫኑ።"
    )


# ── Main ──────────────────────────────────────────────────────────────────────

async def run_bot() -> None:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set!")

    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_DEPARTMENT: [
                CallbackQueryHandler(select_department, pattern=r"^dept:"),
            ],
            WRITE_FEEDBACK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_feedback),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        per_message=False,
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("chatid", chatid))
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    logger.info("✅ Bot is running...")

    async with application:
        await application.start()
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await asyncio.Event().wait()
        await application.updater.stop()
        await application.stop()


if __name__ == "__main__":
    asyncio.run(run_bot())
