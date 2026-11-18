"""
ደ/ማ/ዩ/ግ/ጉባኤ Feedback Bot
- Users submit feedback per department
- Admin can manage departments, heads, and view stats
- Department heads can reply to comments
- Replies are delivered back to the original commenter
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
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
BOT_TOKEN   = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")
ADMIN_ID    = int(os.getenv("ADMIN_ID", "5887687211"))

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Data file ─────────────────────────────────────────────────────────────────
DATA_FILE = "data.json"

# ── Conversation states ───────────────────────────────────────────────────────
# User flow
SELECT_DEPARTMENT, WRITE_FEEDBACK = range(2)
# Admin flow
ADMIN_MENU, ADMIN_ADD_DEPT, ADMIN_ADD_DEPT_ID, ADMIN_DELETE_DEPT, ADMIN_SET_HEAD_DEPT, ADMIN_SET_HEAD_ID = range(10, 16)
# Head reply flow
HEAD_REPLY_TEXT = 20


# ══════════════════════════════════════════════════════════════════════════════
# DATA LAYER
# ══════════════════════════════════════════════════════════════════════════════

def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    # Default data structure
    return {
        "departments": [
            {"name": "ትምህርት ክፍል",        "emoji": "📚", "head_id": 9223739160},
            {"name": "መዝሙር ክፍል",         "emoji": "🎵", "head_id": None},
            {"name": "ሙያ ክፍል",           "emoji": "💼", "head_id": None},
            {"name": "ባች ማስተባበሪያ ክፍል",  "emoji": "🤝", "head_id": None},
            {"name": "ልማት ክፍል",          "emoji": "🌱", "head_id": None},
            {"name": "አባላት እንክብካቤ ክፍል", "emoji": "❤️", "head_id": None},
            {"name": "ቋንቋ ክፍል",          "emoji": "🗣️", "head_id": None},
            {"name": "ትምህርታዊ ስነ-ጽሑፍ",   "emoji": "📖", "head_id": None},
            {"name": "ነገረ ሃይማኖት",        "emoji": "✝️", "head_id": None},
            {"name": "ዋናው ጽ/ቤት",         "emoji": "🏛️", "head_id": 5586249161},
        ],
        "comments": {}
    }


def save_data(data: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_departments(data: dict) -> list:
    return data.get("departments", [])


def get_department_by_name(data: dict, name: str) -> dict | None:
    for d in data["departments"]:
        if d["name"] == name:
            return d
    return None


def save_comment(data: dict, comment_id: str, user_id: int, user_name: str,
                 department: str, text: str) -> None:
    data["comments"][comment_id] = {
        "user_id":    user_id,
        "user_name":  user_name,
        "department": department,
        "text":       text,
        "timestamp":  datetime.now().isoformat(),
        "answered":   False,
        "reply":      None,
    }
    save_data(data)


def mark_answered(data: dict, comment_id: str, reply_text: str) -> None:
    if comment_id in data["comments"]:
        data["comments"][comment_id]["answered"] = True
        data["comments"][comment_id]["reply"] = reply_text
        save_data(data)


# ══════════════════════════════════════════════════════════════════════════════
# KEYBOARDS
# ══════════════════════════════════════════════════════════════════════════════

def build_department_keyboard(data: dict) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            f"{d['emoji']} ለ{d['name']}",
            callback_data=f"dept:{d['name']}"
        )
        for d in get_departments(data)
    ]
    keyboard = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(keyboard)


def build_start_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["🕊️ ጀምር / Start"]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def build_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ ክፍል ጨምር",          callback_data="admin:add_dept")],
        [InlineKeyboardButton("🗑️ ክፍል ሰርዝ",          callback_data="admin:del_dept")],
        [InlineKeyboardButton("👤 የክፍል ሃላፊ ለመቀየር",   callback_data="admin:set_head")],
        [InlineKeyboardButton("📊 ስታቲስቲክስ",           callback_data="admin:stats")],
        [InlineKeyboardButton("📋 ሪፖርት",              callback_data="admin:report")],
        [InlineKeyboardButton("❌ ዝጋ",                callback_data="admin:close")],
    ])


def build_reply_keyboard(comment_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("↩️ ምላሽ ስጥ", callback_data=f"reply:{comment_id}")
    ]])


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def user_display(user) -> str:
    name = user.full_name or "ስም የለም"
    username = f" (@{user.username})" if user.username else ""
    return f"{name}{username}"


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def is_dept_head(user_id: int, data: dict) -> bool:
    """Check if user is any department head."""
    for d in data["departments"]:
        if d.get("head_id") == user_id:
            return True
    return False


def get_main_office_head_id(data: dict) -> int | None:
    """Return the head_id of ዋናው ጽ/ቤት."""
    for d in data["departments"]:
        if d["name"] == "ዋናው ጽ/ቤት":
            return d.get("head_id")
    return None


# ══════════════════════════════════════════════════════════════════════════════
# USER FLOW
# ══════════════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    data = load_data()
    await update.message.reply_text(
        "🕊️ እንኳን ወደ ደ/ማ/ዩ/ግ/ጉባኤ በደህና መጣችሁ!\n\n"
        "ለስራችን ግብዓት ይሆነን ዘንድ ማንኛውንም ሃሳብ፣ አስተያየት እንዲሁም "
        "ጥያቄ ማቅረብ ትችላላችሁ።\n\n"
        "👇 እባክዎ አስተያየትዎን ለየትኛው ክፍል እንደሆነ ይምረጡ፦",
        reply_markup=build_department_keyboard(data),
    )
    return SELECT_DEPARTMENT


async def select_department(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    department = query.data.replace("dept:", "")
    context.user_data["department"] = department
    await query.edit_message_text(
        f"የመረጡት ክፍል፡ *{department}* ነው\n\n"
        f"እባክዎትን ያለዎትን ሃሳብ፣ አስተያየት ወይም ጥያቄ ይጻፉ።\n"
        f"✍️ መልዕክትዎ ለሚመለከተው አካል የሚደርስ ይሆናል።\n\n"
        f"_(ወደ ክፍል ምርጫ ለመመለስ /start ይጫኑ)_",
        parse_mode="Markdown",
    )
    return WRITE_FEEDBACK


async def receive_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user       = update.effective_user
    department = context.user_data.get("department", "ያልተገለጸ ክፍል")
    text       = update.message.text or "(ጽሑፍ አልተላከም)"
    data       = load_data()

    # Generate unique comment ID
    comment_id = str(uuid.uuid4())[:8]
    save_comment(data, comment_id, user.id, user_display(user), department, text)

    # Message for admin group (full info)
    group_msg = (
        f"📨 *አዲስ አስተያየት* `#{comment_id}`\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *ከ:* {user_display(user)}\n"
        f"🆔 *User ID:* `{user.id}`\n"
        f"📂 *ክፍል:* {department}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💬 *አስተያየት:*\n{text}"
    )

    # Message for department head (no sender info)
    head_msg = (
        f"📨 *አዲስ አስተያየት* `#{comment_id}`\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📂 *ክፍል:* {department}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💬 *አስተያየት:*\n{text}"
    )

    # Send to admin group
    if GROUP_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=int(GROUP_CHAT_ID),
                text=group_msg,
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Failed to send to group: {e}")

    # Send to department head with reply button
    dept_obj = get_department_by_name(data, department)
    if dept_obj and dept_obj.get("head_id"):
        try:
            await context.bot.send_message(
                chat_id=dept_obj["head_id"],
                text=head_msg,
                parse_mode="Markdown",
                reply_markup=build_reply_keyboard(comment_id),
            )
            logger.info(f"Forwarded #{comment_id} to head {dept_obj['head_id']}")
        except Exception as e:
            logger.error(f"Failed to send to head: {e}")

    # Also notify ዋናው ጽ/ቤት head about every comment (no reply button, read-only)
    main_office_id = get_main_office_head_id(data)
    if main_office_id and (not dept_obj or dept_obj.get("head_id") != main_office_id):
        try:
            office_keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("📋 ሪፖርት ይመልከቱ", callback_data="mainoffice:report")
            ]])
            await context.bot.send_message(
                chat_id=main_office_id,
                text=head_msg,
                parse_mode="Markdown",
                reply_markup=office_keyboard,
            )
        except Exception as e:
            logger.error(f"Failed to notify main office: {e}")

    await update.message.reply_text(
        "ሃሳብዎን ስላካፈሉን እናመሰግናለን! 🙏\n"
        "ምላሽ የምንሰጥዎት ይሆናል፣ እባክዎን በትዕግስት ይጠብቁን።\n\n"
        "ሌላ አስተያየት ለማስገባት 👉 /start ይጫኑ።",
        reply_markup=build_start_keyboard(),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "❌ ተሰርዟል። እንደገና ለመጀመር /start ይጫኑ።",
        reply_markup=build_start_keyboard(),
    )
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════════════════
# DEPARTMENT HEAD REPLY FLOW
# ══════════════════════════════════════════════════════════════════════════════

async def reply_button_pressed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Department head taps the ↩️ ምላሽ ስጥ button."""
    query = update.callback_query
    await query.answer()
    comment_id = query.data.replace("reply:", "")
    context.user_data["replying_to"] = comment_id

    await query.message.reply_text(
        f"✍️ ለ `#{comment_id}` ምላሽዎን ይጻፉ፦",
        parse_mode="Markdown",
    )
    return HEAD_REPLY_TEXT


async def receive_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive the reply text and deliver it to the original commenter."""
    reply_text = update.message.text
    comment_id = context.user_data.get("replying_to")
    data       = load_data()

    if not comment_id or comment_id not in data["comments"]:
        await update.message.reply_text("⚠️ አስተያየቱ አልተገኘም።")
        return ConversationHandler.END

    comment    = data["comments"][comment_id]
    department = comment["department"]
    commenter_id = comment["user_id"]

    # Mark as answered
    mark_answered(data, comment_id, reply_text)

    # Deliver reply to the original commenter
    reply_msg = (
        f"📩 *ከ{department} የተላከ ምላሽ*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💬 {reply_text}"
    )
    try:
        await context.bot.send_message(
            chat_id=commenter_id,
            text=reply_msg,
            parse_mode="Markdown",
        )
        await update.message.reply_text("✅ ምላሹ ለተጠቃሚው ተልኳል!")
        logger.info(f"Reply to #{comment_id} delivered to user {commenter_id}")
    except Exception as e:
        logger.error(f"Failed to deliver reply: {e}")
        await update.message.reply_text("⚠️ ምላሹ ለተጠቃሚው መላክ አልተቻለም።")

    context.user_data.clear()
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN FLOW
# ══════════════════════════════════════════════════════════════════════════════

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ እርስዎ አስተዳዳሪ አይደሉም።")
        return ConversationHandler.END
    await update.message.reply_text(
        "🔧 *የአስተዳዳሪ ፓናል*\nምን ማድረግ ይፈልጋሉ?",
        parse_mode="Markdown",
        reply_markup=build_admin_keyboard(),
    )
    return ADMIN_MENU


async def admin_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    action = query.data.replace("admin:", "")
    data   = load_data()

    if action == "close":
        await query.edit_message_text("✅ ተዘግቷል።")
        return ConversationHandler.END

    elif action == "stats":
        comments = data.get("comments", {})
        dept_stats = {}
        for c in comments.values():
            d = c["department"]
            if d not in dept_stats:
                dept_stats[d] = {"total": 0, "answered": 0}
            dept_stats[d]["total"] += 1
            if c["answered"]:
                dept_stats[d]["answered"] += 1

        if not dept_stats:
            await query.edit_message_text(
                "📊 *ስታቲስቲክስ*\n\nገና አስተያየት አልደረሰም።",
                parse_mode="Markdown",
                reply_markup=build_admin_keyboard(),
            )
            return ADMIN_MENU

        total_all    = sum(v["total"]    for v in dept_stats.values())
        answered_all = sum(v["answered"] for v in dept_stats.values())

        lines = ["📊 *ስታቲስቲክስ በክፍል*\n━━━━━━━━━━━━━━━━━━━"]
        for dept, s in dept_stats.items():
            unanswered = s["total"] - s["answered"]
            lines.append(
                f"📂 *{dept}*\n"
                f"   ጠቅላላ: {s['total']} | ✅ {s['answered']} | ⏳ {unanswered}"
            )
        lines.append(f"━━━━━━━━━━━━━━━━━━━")
        lines.append(f"🔢 ጠቅላላ: {total_all} | ✅ {answered_all} | ⏳ {total_all - answered_all}")

        await query.edit_message_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=build_admin_keyboard(),
        )
        return ADMIN_MENU

    elif action == "report":
        await admin_menu_handler_report(query, data)
        return ADMIN_MENU

    elif action == "add_dept":
        await query.edit_message_text(
            "➕ *አዲስ ክፍል ጨምር*\n\nየክፍሉን ስም ይጻፉ፦\n_(ለምሳሌ: ወጣቶች ክፍል)_\n_(ለመሰረዝ /cancel)_",
            parse_mode="Markdown",
        )
        return ADMIN_ADD_DEPT

    elif action == "del_dept":
        depts = get_departments(data)
        if not depts:
            await query.edit_message_text("⚠️ ምንም ክፍል የለም።", reply_markup=build_admin_keyboard())
            return ADMIN_MENU
        buttons = [
            [InlineKeyboardButton(f"{d['emoji']} {d['name']}", callback_data=f"delconfirm:{d['name']}")]
            for d in depts
        ]
        buttons.append([InlineKeyboardButton("🔙 ተመለስ", callback_data="admin:back")])
        await query.edit_message_text(
            "🗑️ *የትኛውን ክፍል መሰረዝ ይፈልጋሉ?*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return ADMIN_DELETE_DEPT

    elif action == "set_head":
        depts = get_departments(data)
        buttons = [
            [InlineKeyboardButton(f"{d['emoji']} {d['name']}", callback_data=f"setheaddept:{d['name']}")]
            for d in depts
        ]
        buttons.append([InlineKeyboardButton("🔙 ተመለስ", callback_data="admin:back")])
        await query.edit_message_text(
            "👤 *ሃላፊ ለየትኛው ክፍል ይሾሙ?*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return ADMIN_SET_HEAD_DEPT

    elif action == "back":
        await query.edit_message_text(
            "🔧 *የአስተዳዳሪ ፓናል*\nምን ማድረግ ይፈልጋሉ?",
            parse_mode="Markdown",
            reply_markup=build_admin_keyboard(),
        )
        return ADMIN_MENU

    return ADMIN_MENU


async def admin_add_dept(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    data = load_data()
    if get_department_by_name(data, name):
        await update.message.reply_text(f"⚠️ '{name}' ቀድሞ አለ። ሌላ ስም ይጻፉ፦")
        return ADMIN_ADD_DEPT
    context.user_data["new_dept_name"] = name
    await update.message.reply_text(
        f"✅ ስም ተመዝግቧል: *{name}*\n\n"
        f"👤 የዚህ ክፍል ሃላፊ Telegram ID ይጻፉ፦\n"
        f"_(ID ከሌለ 0 ይጻፉ)_",
        parse_mode="Markdown",
    )
    return ADMIN_ADD_DEPT_ID


async def admin_add_dept_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    name = context.user_data.get("new_dept_name")
    data = load_data()

    try:
        head_id = int(text)
        head_id = None if head_id == 0 else head_id
    except ValueError:
        await update.message.reply_text("⚠️ የተሳሳተ ID። ቁጥር ብቻ ይጻፉ (ID ከሌለ 0)፦")
        return ADMIN_ADD_DEPT_ID

    data["departments"].append({"name": name, "emoji": "📂", "head_id": head_id})
    save_data(data)
    head_info = f"`{head_id}`" if head_id else "አልተወሰነም"
    await update.message.reply_text(
        f"✅ *{name}* ተጨምሯል!\n👤 ሃላፊ ID: {head_info}",
        parse_mode="Markdown",
        reply_markup=build_admin_keyboard(),
    )
    context.user_data.clear()
    return ADMIN_MENU


async def admin_delete_dept(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "admin:back":
        await query.edit_message_text(
            "🔧 *የአስተዳዳሪ ፓናል*",
            parse_mode="Markdown",
            reply_markup=build_admin_keyboard(),
        )
        return ADMIN_MENU

    name = query.data.replace("delconfirm:", "")
    data = load_data()
    data["departments"] = [d for d in data["departments"] if d["name"] != name]
    save_data(data)
    await query.edit_message_text(
        f"✅ *{name}* ተሰርዟል!",
        parse_mode="Markdown",
        reply_markup=build_admin_keyboard(),
    )
    return ADMIN_MENU


async def admin_set_head_dept(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "admin:back":
        await query.edit_message_text(
            "🔧 *የአስተዳዳሪ ፓናል*",
            parse_mode="Markdown",
            reply_markup=build_admin_keyboard(),
        )
        return ADMIN_MENU

    dept_name = query.data.replace("setheaddept:", "")
    context.user_data["setting_head_for"] = dept_name
    await query.edit_message_text(
        f"👤 *{dept_name}* ሃላፊ Telegram ID ይጻፉ፦\n_(ለምሳሌ: 123456789)_\n_(ለመሰረዝ /cancel)_",
        parse_mode="Markdown",
    )
    return ADMIN_SET_HEAD_ID


async def admin_set_head_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text      = update.message.text.strip()
    dept_name = context.user_data.get("setting_head_for")
    data      = load_data()

    try:
        head_id = int(text)
    except ValueError:
        await update.message.reply_text("⚠️ የተሳሳተ ID። ቁጥር ብቻ ይጻፉ፦")
        return ADMIN_SET_HEAD_ID

    for d in data["departments"]:
        if d["name"] == dept_name:
            d["head_id"] = head_id
            break
    save_data(data)

    await update.message.reply_text(
        f"✅ *{dept_name}* ሃላፊ ID `{head_id}` ተመዝግቧል!",
        parse_mode="Markdown",
        reply_markup=build_admin_keyboard(),
    )
    context.user_data.clear()
    return ADMIN_MENU


# ══════════════════════════════════════════════════════════════════════════════
# UTILITY HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

async def main_office_report_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the 📋 ሪፖርት ይመልከቱ button for ዋናው ጽ/ቤት head."""
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data    = load_data()
    main_office_id = get_main_office_head_id(data)

    if not (is_admin(user_id) or user_id == main_office_id):
        await query.answer("⛔ ፈቃድ የለዎትም።", show_alert=True)
        return

    await send_report(query.message, data)


async def chatid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    await update.message.reply_text(
        f"🆔 *Chat ID:* `{chat.id}`\n"
        f"📛 *ስም:* {chat.title or update.effective_user.full_name}\n"
        f"📋 *አይነት:* {chat.type}",
        parse_mode="Markdown",
    )


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Full comment report for ዋናው ጽ/ቤት head and admin."""
    user_id = update.effective_user.id
    data    = load_data()
    main_office_id = get_main_office_head_id(data)

    if not (is_admin(user_id) or user_id == main_office_id):
        await update.message.reply_text("⛔ ይህን ትዕዛዝ የመጠቀም ፈቃድ የለዎትም።")
        return

    await send_report(update.message, data)


async def admin_menu_handler_report(query, data: dict) -> None:
    """Send report as a new message when admin taps the 📋 Report button."""
    comments = data.get("comments", {})
    if not comments:
        await query.message.reply_text("📊 ገና አስተያየት አልደረሰም።")
        return
    await send_report(query.message, data)


async def send_report(message, data: dict) -> None:
    """Build and send the formatted report."""
    comments = data.get("comments", {})
    if not comments:
        await message.reply_text("📊 ገና አስተያየት አልደረሰም።")
        return

    # Aggregate per-department stats
    dept_stats: dict = {}
    for cid, c in comments.items():
        d = c["department"]
        if d not in dept_stats:
            dept_stats[d] = {"total": 0, "answered": 0, "unanswered": []}
        dept_stats[d]["total"] += 1
        if c["answered"]:
            dept_stats[d]["answered"] += 1
        else:
            dept_stats[d]["unanswered"].append((cid, c["text"][:40]))

    total_all    = sum(v["total"]    for v in dept_stats.values())
    answered_all = sum(v["answered"] for v in dept_stats.values())
    pending_all  = total_all - answered_all

    # Column widths
    col1 = 22   # department name
    col2 = 7    # total
    col3 = 7    # answered
    col4 = 7    # unanswered

    header  = f"{'ክፍል':<{col1}} {'ጠቅላላ':>{col2}} {'✅':>{col3}} {'⏳':>{col4}}"
    divider = "─" * (col1 + col2 + col3 + col4 + 3)

    rows = [header, divider]
    for dept, s in dept_stats.items():
        name = dept[:col1]
        rows.append(
            f"{name:<{col1}} {s['total']:>{col2}} {s['answered']:>{col3}} {len(s['unanswered']):>{col4}}"
        )

    rows.append(divider)
    rows.append(
        f"{'ጠቅላላ':<{col1}} {total_all:>{col2}} {answered_all:>{col3}} {pending_all:>{col4}}"
    )

    table = "```\n" + "\n".join(rows) + "\n```"

    # Unanswered previews
    unanswered_lines = []
    for dept, s in dept_stats.items():
        if s["unanswered"]:
            unanswered_lines.append(f"\n*{dept}* — ያልተመለሱ:")
            for cid, preview in s["unanswered"][:3]:
                unanswered_lines.append(f"  • `#{cid}`: {preview}…")
            if len(s["unanswered"]) > 3:
                unanswered_lines.append(f"  _...እና {len(s['unanswered']) - 3} ተጨማሪ_")

    full_text = f"� *ሪፖርት*\n{table}"
    if unanswered_lines:
        full_text += "\n\n⏳ *ያልተመለሱ አስተያየቶች:*\n" + "\n".join(unanswered_lines)

    await message.reply_text(full_text, parse_mode="Markdown")


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "❓ ያልታወቀ ትዕዛዝ። ለመጀመር /start ይጫኑ።",
        reply_markup=build_start_keyboard(),
    )


async def unexpected_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "⚠️ እባክዎ መጀመሪያ ክፍል ይምረጡ።\n"
        "ለመጀመር 👇 ከታች ያለውን Start ይጫኑ።",
        reply_markup=build_start_keyboard(),
    )


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

async def run_bot() -> None:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set!")

    application = Application.builder().token(BOT_TOKEN).build()

    # ── User feedback conversation ──────────────────────────────────────────
    user_conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex(r"^🕊️ ጀምር / Start$"), start),
        ],
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

    # ── Department head reply conversation ──────────────────────────────────
    reply_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(reply_button_pressed, pattern=r"^reply:"),
        ],
        states={
            HEAD_REPLY_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_reply),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        per_message=False,
    )

    # ── Admin conversation ──────────────────────────────────────────────────
    admin_conv = ConversationHandler(
        entry_points=[CommandHandler("admin", admin)],
        states={
            ADMIN_MENU: [
                CallbackQueryHandler(admin_menu_handler, pattern=r"^admin:"),
                CallbackQueryHandler(admin_delete_dept,  pattern=r"^delconfirm:"),
                CallbackQueryHandler(admin_set_head_dept, pattern=r"^setheaddept:"),
            ],
            ADMIN_ADD_DEPT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_dept),
            ],
            ADMIN_ADD_DEPT_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_dept_id),
            ],
            ADMIN_DELETE_DEPT: [
                CallbackQueryHandler(admin_delete_dept,  pattern=r"^delconfirm:"),
                CallbackQueryHandler(admin_menu_handler, pattern=r"^admin:"),
            ],
            ADMIN_SET_HEAD_DEPT: [
                CallbackQueryHandler(admin_set_head_dept, pattern=r"^setheaddept:"),
                CallbackQueryHandler(admin_menu_handler,  pattern=r"^admin:"),
            ],
            ADMIN_SET_HEAD_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_head_id),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        per_message=False,
    )

    application.add_handler(user_conv)
    application.add_handler(reply_conv)
    application.add_handler(admin_conv)
    application.add_handler(CallbackQueryHandler(main_office_report_button, pattern=r"^mainoffice:report$"))
    application.add_handler(CommandHandler("chatid", chatid))
    application.add_handler(CommandHandler("report", report))
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unexpected_message))

    logger.info("✅ Bot is running...")

    async with application:
        await application.start()
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await asyncio.Event().wait()
        await application.updater.stop()
        await application.stop()


if __name__ == "__main__":
    asyncio.run(run_bot())
