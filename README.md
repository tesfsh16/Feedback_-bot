# ደ/ማ/ዩ/ግ/ጉባኤ Feedback Bot

A Telegram bot that collects feedback and comments from channel members
and forwards them to the admin group.

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Get your Group Chat ID
Since you have the bot token, the easiest way is:
1. Add your bot to the private group (make it an admin)
2. Run the bot: `python bot.py`
3. Go to the group in Telegram and send: `/chatid`
4. The bot will reply with the group's Chat ID (e.g. `-1001234567890`)
5. Copy that ID into your `.env` file as `GROUP_CHAT_ID`
6. Restart the bot

### 3. Update `.env`
```
BOT_TOKEN=your_token_here
GROUP_CHAT_ID=-1001234567890
```

### 4. Run the bot
```bash
python bot.py
```

---

## Bot Commands
| Command   | Description                        |
|-----------|------------------------------------|
| /start    | Show welcome message & departments |
| /cancel   | Cancel current feedback session    |
| /chatid   | Show current chat's ID (for setup) |

---

## Feedback Flow
1. User sends `/start`
2. Bot shows welcome message in Amharic
3. User selects a department from inline buttons
4. User types their feedback freely (Amharic or English)
5. Bot forwards the feedback to the admin group with user info
6. Bot thanks the user

---

## Departments
- 📚 ለትምህርት ክፍል
- 🎵 ለመዝሙር ክፍል
- 💼 ለሙያ ክፍል
- 🤝 ለባች ማስተባበሪያ ክፍል
- 🌱 ለልማት ክፍል
- ❤️ ለአባላት እንክብካቤ ክፍል
- 🗣️ ቋንቋ ክፍል
- 🏛️ ለዋናው ጽ/ቤት
