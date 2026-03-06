# CREDIT - @RASHIK_69
# OFFICIAL CHANNEL - https://t.me/+R2YXWeznLcIwZDM1

import os
import re
import json
import time
import uuid
import html
import random
import sqlite3
import requests
from datetime import datetime, timedelta
from fastapi import FastAPI, Request

TOKEN = os.getenv("BOT_TOKEN", "BOT_TOKEN").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "6321618547"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()

if not TOKEN or TOKEN == "BOT_TOKEN":
    raise RuntimeError("BOT_TOKEN environment variable is missing.")

BOT_API = f"https://api.telegram.org/bot{TOKEN}"
DB_PATH = os.getenv("SQLITE_PATH", "channels.db")

app = FastAPI()

print("Bot Started ✅")

# ================= DATABASE =================

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS channels (user_id INTEGER, channel_id TEXT, title TEXT)")

cursor.execute("""
CREATE TABLE IF NOT EXISTS giveaways (
    gw_id TEXT PRIMARY KEY,
    creator_id INTEGER,
    channels TEXT,
    title TEXT,
    description TEXT,
    image_file_id TEXT,
    duration_text TEXT,
    end_time TEXT,
    winners INTEGER,
    winner_type TEXT,
    prizes TEXT,
    must_join TEXT,
    ended INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    first_name TEXT,
    username TEXT,
    join_date TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT,
    title TEXT,
    description TEXT,
    image_file_id TEXT,
    winners INTEGER,
    winner_type TEXT,
    duration TEXT,
    prizes TEXT
)
""")
conn.commit()

try:
    cursor.execute("ALTER TABLE templates ADD COLUMN must_join TEXT")
    conn.commit()
except:
    pass

cursor.execute("""
CREATE TABLE IF NOT EXISTS participants (
    gw_id TEXT,
    user_id INTEGER,
    join_time TEXT,
    UNIQUE(gw_id, user_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS giveaway_messages (
    gw_id TEXT,
    channel_id TEXT,
    message_id INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS sessions (
    user_id INTEGER,
    kind TEXT,
    data TEXT,
    PRIMARY KEY (user_id, kind)
)
""")
conn.commit()

# ================= SESSION STORAGE =================

def save_session(user_id: int, kind: str, data: dict):
    cursor.execute(
        "REPLACE INTO sessions (user_id, kind, data) VALUES (?, ?, ?)",
        (user_id, kind, json.dumps(data, ensure_ascii=False))
    )
    conn.commit()

def load_session(user_id: int, kind: str):
    cursor.execute("SELECT data FROM sessions WHERE user_id=? AND kind=?", (user_id, kind))
    row = cursor.fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except:
        return None

def delete_session(user_id: int, kind: str):
    cursor.execute("DELETE FROM sessions WHERE user_id=? AND kind=?", (user_id, kind))
    conn.commit()

def clear_all_sessions(user_id: int):
    cursor.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    conn.commit()

# ================= TELEGRAM API =================

def tg_post(method: str, payload=None):
    payload = payload or {}
    try:
        r = requests.post(f"{BOT_API}/{method}", json=payload, timeout=30)
        return r.json()
    except Exception as e:
        print(f"Telegram API error [{method}]:", e)
        return {"ok": False, "description": str(e)}

def send_message(chat_id, text, reply_markup=None, reply_to_message_id=None, disable_web_page_preview=True):
    payload = {
        "chat_id": chat_id,
        "text": truncate_text(text),
        "parse_mode": "HTML",
        "disable_web_page_preview": disable_web_page_preview
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id
    return tg_post("sendMessage", payload)

def send_photo(chat_id, photo, caption=None, reply_markup=None, reply_to_message_id=None):
    payload = {
        "chat_id": chat_id,
        "photo": photo,
        "parse_mode": "HTML"
    }
    if caption:
        payload["caption"] = truncate_text(caption, 1020)
    if reply_markup:
        payload["reply_markup"] = reply_markup
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id
    return tg_post("sendPhoto", payload)

def edit_message_text(chat_id, message_id, text, reply_markup=None, disable_web_page_preview=True):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": truncate_text(text),
        "parse_mode": "HTML",
        "disable_web_page_preview": disable_web_page_preview
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return tg_post("editMessageText", payload)

def edit_message_caption(chat_id, message_id, caption, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "caption": truncate_text(caption, 1020),
        "parse_mode": "HTML"
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return tg_post("editMessageCaption", payload)

def edit_message_reply_markup(chat_id, message_id, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return tg_post("editMessageReplyMarkup", payload)

def answer_callback_query(callback_query_id, text=None, show_alert=False):
    payload = {
        "callback_query_id": callback_query_id,
        "show_alert": show_alert
    }
    if text:
        payload["text"] = text
    return tg_post("answerCallbackQuery", payload)

def get_chat(chat_id):
    return tg_post("getChat", {"chat_id": chat_id})

def get_chat_member(chat_id, user_id):
    return tg_post("getChatMember", {"chat_id": chat_id, "user_id": user_id})

def get_me():
    return tg_post("getMe", {})

def send_chat_action(chat_id, action="typing"):
    return tg_post("sendChatAction", {"chat_id": chat_id, "action": action})

def forward_message(chat_id, from_chat_id, message_id):
    return tg_post("forwardMessage", {
        "chat_id": chat_id,
        "from_chat_id": from_chat_id,
        "message_id": message_id
    })

def delete_message(chat_id, message_id):
    return tg_post("deleteMessage", {"chat_id": chat_id, "message_id": message_id})

# ================= MENUS =================

def main_menu():
    return {
        "keyboard": [
            [{"text": "➕ Add Channel"}, {"text": "🗂️ Manage Channels"}],
            [{"text": "🎁 Create Giveaway"}, {"text": "📊 Dashboard"}],
            [{"text": "📝 Templates"}, {"text": "❓ Help & Support"}],
            [{"text": "ℹ️ About"}]
        ],
        "resize_keyboard": True
    }

def manage_menu():
    return {
        "keyboard": [
            [{"text": "🔎 View All Channels"}, {"text": "❌ Remove Channel"}],
            [{"text": "↩️ Back to Main Menu"}]
        ],
        "resize_keyboard": True
    }

def cancel_inline():
    return {
        "inline_keyboard": [
            [{"text": "❌ Cancel", "callback_data": "cancel"}]
        ]
    }

# ================= TEXT =================

WELCOME_TEXT = """This bot helps you create and manage
giveaways in your Telegram channels.

<b>Main Features:</b>
➕ Add and manage your channels
🎁 Create engaging giveaways
📊 Track analytics and results
🏆 Automatic winner selection

Choose an option from the menu
below to get started.
"""

ADD_CHANNEL_TEXT = """📢 <b>Add a New Channel</b>

Send the Channel ID or @username.

Make sure the bot is an admin in that
channel with proper permissions.

📋 <b>Format Example:</b>
• -1001234567890

💡 <b>How to find Chat ID:</b>
🤖 Use the @username_to_id_bot to
get chat ID
"""

HELP_TEXT = """🚀 <b>Quick Guide</b>
━━━━━━━━━━━━━━━━━━

1️⃣ <b>Add Channel</b>
• Click ➕ Add Channel
• Send channel ID or @username
• Bot must be admin (Post/Edit/Delete)

2️⃣ <b>Create Giveaway</b>
• Click 🎁 Create Giveaway
• Follow steps (title, time, winners, prize)

3️⃣ <b>Monitor</b>
• 📊 Dashboard → active & ended giveaways

📋 <b>Tips</b>
• Time: 5m | 1h | 2d
• Single prize = one line
• Multiple prizes = one per line
• Subscriptions are optional

🔧 <b>Common Issues</b>
• Channel not linked → bot/user not admin
• Missing permissions → allow Post/Edit/Delete
• Channel not found → check ID/username

📞 <b>Support:</b> @RASHIK_69
"""

ABOUT_TEXT = """ℹ️ <b>About</b>
━━━━━━━━━━━━━━━━━━

<b>Name:</b> Give Flow  
<b>Version:</b> v2.0 (Beta) 🛠️

👨‍💻 <b>Development Team:</b>
- Creator: <a href="https://t.me/RASHIK_69">RASHIK 69</a> 👨‍💻

⚙️ <b>Technical Stack:</b>
- Language: Python 🐍
- Library: PyTelegramBotAPI 📚
- Database: SQLite 🗄️

📌 <b>About:</b>
Automated giveaway management
for Telegram channels.
"""

# ================= HELPERS =================

def truncate_text(text: str, limit: int = 4096):
    text = str(text)
    if len(text) <= limit:
        return text
    return text[:limit - 25] + "\n\n... [Message Truncated]"

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def parse_end_time(end_time_str: str) -> datetime:
    return datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")

def format_remaining_full(end_time: datetime) -> str:
    now = datetime.now().replace(microsecond=0)
    diff = end_time - now
    sec = int(diff.total_seconds())

    if sec <= 0:
        return "Ended"

    d = sec // 86400
    sec %= 86400
    h = sec // 3600
    sec %= 3600
    m = sec // 60
    s = sec % 60

    parts = []
    if d:
        parts.append(f"{d} days")
    if h:
        parts.append(f"{h} hours")
    if m:
        parts.append(f"{m} minutes")
    parts.append(f"{s} seconds")

    return ", ".join(parts)

def get_prize_type(prizes):
    if not prizes:
        return "Unknown"
    sample = prizes[0].strip()
    if sample.startswith("http://") or sample.startswith("https://"):
        return "Access Link"
    if ":" in sample and "@" in sample:
        return "Email:Password"
    if ":" in sample:
        return "User:Password"
    return "Code/Key"

def tg_link_from_channel(ch: str):
    ch = ch.strip()
    if ch.startswith("@"):
        return f"https://t.me/{ch[1:]}"
    return None

def is_member_of_required(user_id: int, must_join_list):
    for ch in must_join_list:
        ch = ch.strip()
        if not ch:
            continue
        try:
            member = get_chat_member(ch, user_id)
            if not member.get("ok"):
                return False, ch
            status = member["result"]["status"]
            if status not in ("member", "administrator", "creator"):
                return False, ch
        except:
            return False, ch
    return True, None

def bot_is_admin_in_channel(channel):
    try:
        me = get_me()
        if not me.get("ok"):
            return False
        me_id = me["result"]["id"]
        m = get_chat_member(channel, me_id)
        if not m.get("ok"):
            return False
        return m["result"]["status"] in ("administrator", "creator")
    except:
        return False

def show_preview(chat_id, user_id):
    data = load_session(user_id, "giveaway") or {}

    required_list = data.get("must_join", [])
    required = len(required_list)

    prize_type = get_prize_type(data.get("prizes", []))

    preview_text = f"""📋 <b>Giveaway Preview</b>

🎁 <b>Title:</b> {data.get("title")}
📝 <b>Description:</b> {data.get("description")}
🏆 <b>Prize:</b> {prize_type}
⏳ <b>Duration:</b> Set
👥 <b>Winners:</b> {data.get("winners")}
🎯 <b>Winner Type:</b> {data.get("winner_type")}
📢 <b>Required Subs:</b> {required}
"""

    markup = {
        "inline_keyboard": [
            [{"text": "✅ Confirm", "callback_data": "publish_gw"}],
            [{"text": "❌ Cancel", "callback_data": "cancel_gw_final"}]
        ]
    }

    send_message(chat_id, preview_text, reply_markup=markup)

def safe_edit_any(chat_id, message_id, text, reply_markup=None):
    try:
        r = edit_message_caption(chat_id, message_id, text, reply_markup=reply_markup)
        if r.get("ok"):
            return True
    except:
        pass

    try:
        r = edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
        if r.get("ok"):
            return True
    except Exception as e:
        print("Edit failed:", e)

    return False

def parse_duration_to_end(duration_text: str):
    duration_text = duration_text.lower().strip()
    match = re.match(r"^(\d+)([mhd])$", duration_text)
    if not match:
        return None

    value = int(match.group(1))
    unit = match.group(2)

    if unit == "m":
        delta = timedelta(minutes=value)
    elif unit == "h":
        delta = timedelta(hours=value)
    else:
        delta = timedelta(days=value)

    return datetime.now() + delta

# ================= BROADCAST =================

def start_broadcast(message, forward=False, text=None):
    status = send_message(message["chat"]["id"], "🚀 Broadcast started...\n\n0%")
    if not status.get("ok"):
        return

    status_message_id = status["result"]["message_id"]

    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()

    total = len(users)
    sent = 0
    failed = 0

    for i, row in enumerate(users, start=1):
        user_id = row[0]

        try:
            if forward:
                forward_message(
                    user_id,
                    message["chat"]["id"],
                    message["reply_to_message"]["message_id"]
                )
            else:
                send_message(user_id, text)

            sent += 1
        except:
            failed += 1

        if i % 10 == 0 or i == total:
            percent = int((i / total) * 100) if total else 100
            progress_bar = "█" * (percent // 10) + "░" * (10 - (percent // 10))

            edit_message_text(
                message["chat"]["id"],
                status_message_id,
                f"""🚀 <b>Broadcast Progress</b>

[{progress_bar}] {percent}%

👥 Total: {total}
✅ Sent: {sent}
❌ Failed: {failed}"""
            )

        time.sleep(0.05)

    edit_message_text(
        message["chat"]["id"],
        status_message_id,
        f"""✅ <b>Broadcast Completed</b>

👥 Total Users: {total}
✅ Sent: {sent}
❌ Failed: {failed}"""
    )

# ================= ROUTERS =================

def handle_start(message):
    user_id = message["from"]["id"]
    first_name = message["from"].get("first_name", "No Name")
    username = message["from"].get("username", "NoUsername")

    cursor.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
    exists = cursor.fetchone()

    if not exists:
        cursor.execute(
            "INSERT INTO users VALUES (?,?,?,?)",
            (user_id, first_name, username, now_str())
        )
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]

        try:
            send_message(
                ADMIN_ID,
                f"""🚀 <b>New User Started Bot!</b>

👤 Name: {first_name}
🆔 ID: <code>{user_id}</code>
🔗 Username: @{username}

📊 Total Users: {total_users}"""
            )
        except:
            pass

    text = message.get("text", "")
    if text.startswith("/start join_"):
        gw_id = text.split("join_")[1].strip()

        cursor.execute("SELECT title, must_join, end_time, ended FROM giveaways WHERE gw_id=?", (gw_id,))
        row = cursor.fetchone()
        if not row:
            send_message(message["chat"]["id"], "❌ Giveaway not found or already ended.")
            return

        title, must_join_raw, end_time_str, ended = row

        if int(ended) == 1:
            send_message(message["chat"]["id"], "❌ This giveaway already ended.")
            return

        end_time = parse_end_time(end_time_str)
        if datetime.now() >= end_time:
            send_message(message["chat"]["id"], "❌ This giveaway already ended.")
            return

        must_join_list = [x.strip() for x in (must_join_raw or "").split(",") if x.strip()]
        if must_join_list:
            ok, missing = is_member_of_required(user_id, must_join_list)
            if not ok:
                send_message(message["chat"]["id"], "❌ You must join required channels first.")
                return

        cursor.execute("SELECT 1 FROM participants WHERE gw_id=? AND user_id=?", (gw_id, user_id))
        if cursor.fetchone():
            send_message(message["chat"]["id"], "✅ Already Joined!\n\nYou're already participating in: {titel}.")
            return

        cursor.execute("INSERT INTO participants VALUES (?, ?, ?)", (gw_id, user_id, now_str()))
        conn.commit()

        send_message(
            message["chat"]["id"],
            f"""🎉 <b>Successfully Joined!</b>

You're now participating in: <b>{title}</b>

Good luck! Winners will be announced automatically when the giveaway ends."""
        )
        return

    send_message(message["chat"]["id"], WELCOME_TEXT, reply_markup=main_menu())

def show_dashboard(chat_id):
    kb = {
        "keyboard": [
            [{"text": "🟢 Active Giveaways"}],
            [{"text": "⚫ Expired Giveaways"}],
            [{"text": "📈 Analytics"}],
            [{"text": "↩️ Back to Main Menu"}]
        ],
        "resize_keyboard": True
    }

    send_message(
        chat_id,
        "📊 <b>Dashboard</b>\n\nChoose an option:",
        reply_markup=kb
    )

def active_giveaways(chat_id):
    cursor.execute("""
        SELECT gw_id, title, end_time
        FROM giveaways
        WHERE ended=0
        ORDER BY end_time ASC
    """)
    rows = cursor.fetchall()

    if not rows:
        send_message(chat_id, "❌ No active giveaways.")
        return

    text = "🟢 <b>Active Giveaways:</b>\n\n"

    for gw_id, title, end_time_str in rows:
        end_time = parse_end_time(end_time_str)
        remaining = format_remaining_full(end_time)

        text += f"🎁 <b>{title}</b>\n"
        text += f"🆔 <code>{gw_id}</code>\n"
        text += f"⏳ {remaining}\n\n"

    send_message(chat_id, text)

def expired_giveaways(chat_id):
    cursor.execute("""
        SELECT gw_id, title, end_time
        FROM giveaways
        WHERE ended=1
        ORDER BY end_time DESC
    """)
    rows = cursor.fetchall()

    if not rows:
        send_message(chat_id, "❌ No expired giveaways.")
        return

    text = "⚫ <b>Expired Giveaways:</b>\n\n"

    for gw_id, title, end_time_str in rows:
        text += f"🎁 <b>{title}</b>\n"
        text += f"🆔 <code>{gw_id}</code>\n"
        text += f"📅 Ended At: {end_time_str}\n\n"

    send_message(chat_id, text)

def analytics(chat_id):
    cursor.execute("SELECT COUNT(*) FROM giveaways")
    total_gw = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM giveaways WHERE ended=0")
    active = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM giveaways WHERE ended=1")
    expired = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM participants")
    total_participants = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    send_message(
        chat_id,
        f"""📊 <b>Analytics Report</b>

👥 Total Users: {total_users}
🎁 Total Giveaways: {total_gw}
🟢 Active: {active}
⚫ Expired: {expired}
👥 Current Participants: {total_participants}
"""
    )

def template_menu(chat_id):
    kb = {
        "keyboard": [
            [{"text": "📋 View Templates"}],
            [{"text": "➕ Create Template"}],
            [{"text": "↩️ Back to Main Menu"}]
        ],
        "resize_keyboard": True
    }

    send_message(
        chat_id,
        """📝 <b>Template Manager</b>

Templates help you quickly create giveaways
with pre-configured settings.

Choose an option:""",
        reply_markup=kb
    )

def back_to_main(chat_id, user_id):
    clear_all_sessions(user_id)
    send_message(chat_id, "🏠 <b>Main Menu</b>", reply_markup=main_menu())

# ================= MESSAGE HANDLERS =================

def handle_add_channel(message):
    send_message(message["chat"]["id"], ADD_CHANNEL_TEXT, reply_markup=cancel_inline())

def handle_help(message):
    send_message(message["chat"]["id"], HELP_TEXT, reply_markup=main_menu())

def handle_about(message):
    send_message(message["chat"]["id"], ABOUT_TEXT, reply_markup=main_menu())

def handle_manage_channels(message):
    send_message(
        message["chat"]["id"],
        "🗂️ <b>Manage Channels</b>\n\nChoose an action:",
        reply_markup=manage_menu()
    )

def handle_link_channel(message):
    channel_id = message["text"].strip()
    user_id = message["from"]["id"]

    try:
        chat = get_chat(channel_id)
        if not chat.get("ok"):
            raise Exception("invalid channel")

        chat_data = chat["result"]

        cursor.execute("SELECT 1 FROM channels WHERE channel_id=? AND user_id=?", (channel_id, user_id))
        if cursor.fetchone():
            send_message(message["chat"]["id"], "⚠️ Channel already added.")
            return

        cursor.execute("INSERT INTO channels VALUES (?, ?, ?)", (user_id, channel_id, chat_data.get("title", channel_id)))
        conn.commit()

        username = f"(@{chat_data.get('username')})" if chat_data.get("username") else ""

        send_message(
            message["chat"]["id"],
            f"""✅ <b>Channel Linked Successfully!</b>

📢 <b>{chat_data.get('title', channel_id)}</b> {username}
🆔 Channel ID: <code>{channel_id}</code>

You can now create giveaways in this channel.
""",
            reply_markup=main_menu()
        )
    except:
        send_message(message["chat"]["id"], "❌ Failed to link channel.\nMake sure bot is admin & ID is correct.")

def handle_view_channels(message):
    cursor.execute("SELECT title, channel_id FROM channels WHERE user_id=?", (message["from"]["id"],))
    rows = cursor.fetchall()

    if not rows:
        send_message(message["chat"]["id"], "⚠️ No channels added yet.")
        return

    text = "📋 <b>Your Channels:</b>\n\n"
    for i, (title, cid) in enumerate(rows, start=1):
        try:
            chat = get_chat(cid)
            username = f"(@{chat['result'].get('username')})" if chat.get("ok") and chat["result"].get("username") else ""
        except:
            username = ""

        default_tag = " 🏷 (Default)" if i == 1 else ""
        text += f"{i}. ✅ <b>{title}</b> {username}{default_tag}\n"
        text += f"🆔 ID: <code>{cid}</code>\n\n"

    send_message(message["chat"]["id"], text)

def handle_remove_channel_list(message):
    cursor.execute("SELECT title, channel_id FROM channels WHERE user_id=?", (message["from"]["id"],))
    rows = cursor.fetchall()

    if not rows:
        send_message(message["chat"]["id"], "⚠️ No channels to remove.")
        return

    kb = {"inline_keyboard": []}
    for title, cid in rows:
        kb["inline_keyboard"].append([{"text": f"❌ {title}", "callback_data": f"del_channel_{cid}"}])

    send_message(message["chat"]["id"], "Select channel to remove:", reply_markup=kb)

def handle_create_template(message):
    save_session(message["from"]["id"], "template", {"step": "name"})
    send_message(message["chat"]["id"], "📝 Enter Template Name:\n\nSend /cancel to abort.")

def handle_template_steps(message):
    user_id = message["from"]["id"]
    chat_id = message["chat"]["id"]
    session = load_session(user_id, "template")
    if not session:
        return False

    text = message.get("text", "")

    if text == "/cancel":
        delete_session(user_id, "template")
        send_message(chat_id, "❌ Template creation cancelled.", reply_markup=main_menu())
        return True

    if text in ["↩️ Back to Main Menu", "Back to Main Menu"]:
        delete_session(user_id, "template")
        send_message(chat_id, "🏠 <b>Main Menu</b>", reply_markup=main_menu())
        return True

    step = session.get("step")

    if step == "name":
        session["name"] = text
        session["step"] = "title"
        save_session(user_id, "template", session)
        send_message(chat_id, "🎁 Enter Giveaway Title:\n\nSend /cancel to abort.")
        return True

    if step == "title":
        session["title"] = text
        session["step"] = "description"
        save_session(user_id, "template", session)
        send_message(chat_id, "📝 Enter Description:\n\nSend /cancel to abort.")
        return True

    if step == "description":
        session["description"] = text
        session["step"] = "duration"
        save_session(user_id, "template", session)
        send_message(chat_id, "⏳ Enter Duration (5m / 1h / 2d):")
        return True

    if step == "duration":
        session["duration"] = text
        session["step"] = "winners"
        save_session(user_id, "template", session)
        send_message(chat_id, "🏆 Enter Number of Winners:")
        return True

    if step == "edit_required":
        text = text.strip()

        if text == "0":
            cursor.execute(
                "UPDATE templates SET must_join=NULL WHERE id=?",
                (session["tid"],)
            )
            conn.commit()
            delete_session(user_id, "template")
            send_message(chat_id, "✅ Required subs cleared.", reply_markup=main_menu())
            return True

        channels = text.replace("\n", " ").split()
        valid = []

        for ch in channels:
            try:
                chat = get_chat(ch)
                if not chat.get("ok"):
                    send_message(chat_id, f"❌ Invalid channel: {ch}")
                    return True
                if not bot_is_admin_in_channel(chat["result"]["id"]):
                    send_message(chat_id, f"❌ Bot not admin in {ch}")
                    return True
                valid.append(ch)
            except:
                send_message(chat_id, f"❌ Invalid channel: {ch}")
                return True

        cursor.execute(
            "UPDATE templates SET must_join=? WHERE id=?",
            (",".join(valid), session["tid"])
        )
        conn.commit()

        delete_session(user_id, "template")
        send_message(chat_id, f"✅ Required subscriptions updated ({len(valid)} channels).", reply_markup=main_menu())
        return True

    if step == "winners":
        if not text.isdigit():
            send_message(chat_id, "❌ Enter valid number.")
            return True

        session["winners"] = int(text)
        session["step"] = "winner_type"
        save_session(user_id, "template", session)

        kb = {
            "keyboard": [
                [{"text": "🎲 Random"}, {"text": "🏃 First X"}]
            ],
            "resize_keyboard": True
        }
        send_message(chat_id, "Select Winner Type:", reply_markup=kb)
        return True

    if step == "winner_type":
        session["winner_type"] = text
        session["step"] = "prizes"
        save_session(user_id, "template", session)
        send_message(chat_id, "🎁 Enter Prizes (one per line):")
        return True

    if step == "prizes":
        prizes = text.strip()
        cursor.execute("""
            INSERT INTO templates
            (user_id, name, title, description, image_file_id, winners, winner_type, duration, prizes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            session["name"],
            session["title"],
            session["description"],
            session.get("image"),
            session["winners"],
            session["winner_type"],
            session["duration"],
            prizes
        ))
        conn.commit()

        delete_session(user_id, "template")
        send_message(chat_id, "✅ Template Saved Successfully!", reply_markup=main_menu())
        return True

    if step == "edit_duration":
        cursor.execute(
            "UPDATE templates SET duration=? WHERE id=?",
            (text, session["tid"])
        )
        conn.commit()
        delete_session(user_id, "template")
        send_message(chat_id, "✅ Duration updated.", reply_markup=main_menu())
        return True

    if step == "edit_prizes":
        cursor.execute(
            "UPDATE templates SET prizes=? WHERE id=?",
            (text, session["tid"])
        )
        conn.commit()
        delete_session(user_id, "template")
        send_message(chat_id, "✅ Prizes updated.", reply_markup=main_menu())
        return True

    return False

def handle_view_templates(message):
    cursor.execute("SELECT id, name FROM templates WHERE user_id=?", (message["from"]["id"],))
    rows = cursor.fetchall()

    if not rows:
        send_message(message["chat"]["id"], "❌ No templates found.")
        return

    kb = {"inline_keyboard": []}
    for tid, name in rows:
        kb["inline_keyboard"].append([{"text": f"📄 {name}", "callback_data": f"view_tpl_{tid}"}])

    send_message(message["chat"]["id"], "📋 Your Templates:", reply_markup=kb)

def handle_create_giveaway(message):
    cursor.execute("SELECT channel_id, title FROM channels WHERE user_id=?", (message["from"]["id"],))
    rows = cursor.fetchall()

    if not rows:
        send_message(message["chat"]["id"], "⚠️ No channels added.")
        return

    save_session(message["from"]["id"], "selection", {"channels": []})

    markup = {"inline_keyboard": []}
    for cid, title in rows:
        markup["inline_keyboard"].append([{"text": f"☑ {title}", "callback_data": f"toggle_{cid}"}])

    markup["inline_keyboard"].append([{"text": "✅ Confirm Selection", "callback_data": "confirm_channels"}])
    markup["inline_keyboard"].append([{"text": "❌ Cancel", "callback_data": "cancel_gw"}])

    send_message(
        message["chat"]["id"],
        """🎁 <b>Create Giveaway</b>

Step 1/8: Select one or more channels for this giveaway.

Tap to toggle selection, then confirm.""",
        reply_markup=markup
    )

def handle_giveaway_steps(message):
    user_id = message["from"]["id"]
    chat_id = message["chat"]["id"]
    session = load_session(user_id, "giveaway")
    if not session:
        return False

    text = message.get("text", "")
    step = session.get("step")

    if step == "title":
        session["title"] = text
        session["step"] = "description"
        save_session(user_id, "giveaway", session)
        send_message(chat_id, "📝 <b>Step 4/8:</b> Enter a short description.")
        return True

    if step == "description":
        session["description"] = text
        session["step"] = "duration"
        save_session(user_id, "giveaway", session)
        send_message(
            chat_id,
            """⏳ <b>Step 5/8:</b> Enter giveaway duration.

Format: <code>5m</code>, <code>1h</code>, <code>2d</code> (m=minutes, h=hours, d=days)"""
        )
        return True

    if step == "duration":
        duration_text = text.lower().strip()
        match = re.match(r"^(\d+)([mhd])$", duration_text)
        if not match:
            send_message(
                chat_id,
                "❌ Invalid format.\n\nUse: <code>5m</code>, <code>1h</code>, <code>2d</code>"
            )
            return True

        end_time = parse_duration_to_end(duration_text)
        session["duration"] = duration_text
        session["end_time"] = end_time.strftime("%Y-%m-%d %H:%M:%S")
        session["step"] = "winners"
        save_session(user_id, "giveaway", session)

        send_message(chat_id, "🏆 <b>Step 6/8:</b> Enter number of winners.")
        return True

    if step == "winners":
        if not text.isdigit():
            send_message(chat_id, "❌ Enter a valid number.")
            return True

        winners = int(text)
        if winners < 1 or winners > 50:
            send_message(chat_id, "❌ Winners must be between 1-50.")
            return True

        session["winners"] = winners
        session["step"] = "waiting_winner_type"
        save_session(user_id, "giveaway", session)

        markup = {
            "inline_keyboard": [
                [{"text": "🎲 Random", "callback_data": "winner_random"}],
                [{"text": "🏃 First X Participants", "callback_data": "winner_first"}]
            ]
        }

        send_message(
            chat_id,
            "🏆 <b>Step 7/8:</b> Choose winner selection type:",
            reply_markup=markup
        )
        return True

    if step == "prize":
        prizes = [p.strip() for p in text.strip().splitlines() if p.strip()]

        if not prizes:
            send_message(chat_id, "❌ Please send at least one prize.")
            return True

        session["prizes"] = prizes
        session["step"] = "join_channels"
        save_session(user_id, "giveaway", session)

        prize_type = get_prize_type(prizes)

        markup = {
            "inline_keyboard": [
                [{"text": "⏭ Skip", "callback_data": "skip_join"}]
            ]
        }

        send_message(
            chat_id,
            f"""✅ <b>Prize Received!</b>

🎁 <b>Detected Prize Type:</b> {prize_type}
📦 <b>Total Items:</b> {len(prizes)}

<b>Step 7/8:</b> Send one or more channel IDs or @usernames that participants must join (optional).

You can separate multiple channels with spaces or newlines.""",
            reply_markup=markup
        )
        return True

    if step == "join_channels":
        raw = text.strip()
        if not raw:
            session["must_join"] = []
            session["step"] = "preview"
            save_session(user_id, "giveaway", session)
            show_preview(chat_id, user_id)
            return True

        channels = raw.replace("\n", " ").split()
        valid_channels = []

        for ch in channels:
            try:
                chat = get_chat(ch)
                if not chat.get("ok"):
                    send_message(chat_id, f"❌ Invalid channel: {ch}")
                    return True
                if not bot_is_admin_in_channel(chat["result"]["id"]):
                    send_message(chat_id, f"❌ Bot is not admin in {ch}")
                    return True
                valid_channels.append(ch)
            except:
                send_message(chat_id, f"❌ Invalid channel: {ch}")
                return True

        session["must_join"] = valid_channels
        session["step"] = "preview"
        save_session(user_id, "giveaway", session)
        show_preview(chat_id, user_id)
        return True

    return False

def handle_photo_message(message):
    user_id = message["from"]["id"]
    chat_id = message["chat"]["id"]

    template_session = load_session(user_id, "template")
    if template_session and template_session.get("step") == "edit_image":
        file_id = message["photo"][-1]["file_id"]
        cursor.execute(
            "UPDATE templates SET image_file_id=? WHERE id=?",
            (file_id, template_session["tid"])
        )
        conn.commit()

        delete_session(user_id, "template")
        send_message(chat_id, "✅ Template image updated.", reply_markup=main_menu())
        return True

    giveaway_session = load_session(user_id, "giveaway")
    if giveaway_session and giveaway_session.get("step") == "image":
        giveaway_session["image"] = message["photo"][-1]["file_id"]
        giveaway_session["step"] = "title"
        save_session(user_id, "giveaway", giveaway_session)

        send_message(
            chat_id,
            """✅ Image uploaded!

<b>Step 3/8:</b> Enter the giveaway title.

Send /cancel to abort."""
        )
        return True

    return False

def handle_text_message(message):
    text = message.get("text", "")
    user_id = message["from"]["id"]
    chat_id = message["chat"]["id"]

    if text.startswith("/start"):
        handle_start(message)
        return

    if text == "🗂️ Manage Channels":
        handle_manage_channels(message)
        return

    if text == "📊 Dashboard":
        show_dashboard(chat_id)
        return

    if text == "🟢 Active Giveaways":
        active_giveaways(chat_id)
        return

    if text == "⚫ Expired Giveaways":
        expired_giveaways(chat_id)
        return

    if text == "📈 Analytics":
        analytics(chat_id)
        return

    if text == "📝 Templates" or text == "Templates":
        template_menu(chat_id)
        return

    if text == "➕ Create Template":
        handle_create_template(message)
        return

    if handle_template_steps(message):
        return

    if text == "📋 View Templates":
        handle_view_templates(message)
        return

    if text in ["↩️ Back to Main Menu", "Back to Main Menu"]:
        back_to_main(chat_id, user_id)
        return

    if text.startswith("/broadcast"):
        if user_id != ADMIN_ID:
            return

        if message.get("reply_to_message"):
            start_broadcast(message, forward=True)
            return

        parts = text.split(" ", 1)
        if len(parts) < 2:
            send_message(
                chat_id,
                "❌ Use:\n\nReply to a message and type /broadcast\nOR\n/broadcast your text here"
            )
            return

        start_broadcast(message, forward=False, text=parts[1])
        return

    if text == "➕ Add Channel":
        handle_add_channel(message)
        return

    if text == "❓ Help & Support":
        handle_help(message)
        return

    if text == "ℹ️ About":
        handle_about(message)
        return

    if text == "/cancel":
        clear_all_sessions(user_id)
        send_message(chat_id, "❌ Process cancelled.", reply_markup=main_menu())
        return

    if text.startswith("-100"):
        handle_link_channel(message)
        return

    if text == "🔎 View All Channels":
        handle_view_channels(message)
        return

    if text == "❌ Remove Channel":
        handle_remove_channel_list(message)
        return

    if text == "🎁 Create Giveaway":
        handle_create_giveaway(message)
        return

    if text == "/resetdb":
        if user_id != ADMIN_ID:
            return

        cursor.execute("DELETE FROM giveaways")
        cursor.execute("DELETE FROM participants")
        cursor.execute("DELETE FROM giveaway_messages")
        cursor.execute("DELETE FROM templates")
        cursor.execute("DELETE FROM channels")
        cursor.execute("DELETE FROM users")
        cursor.execute("DELETE FROM sessions")
        conn.commit()

        send_message(chat_id, "✅ Database Cleared.")
        return

    if handle_giveaway_steps(message):
        return

# ================= CALLBACK HANDLERS =================

def handle_callback(call):
    data = call.get("data", "")
    user_id = call["from"]["id"]
    chat_id = call["message"]["chat"]["id"]
    message_id = call["message"]["message_id"]

    if data == "cancel":
        edit_message_reply_markup(chat_id, message_id, reply_markup={"inline_keyboard": []})
        send_message(chat_id, "🏠 <b>Main Menu</b>", reply_markup=main_menu())
        answer_callback_query(call["id"])
        return

    if data == "cancel_gw_final":
        delete_session(user_id, "giveaway")
        delete_session(user_id, "selection")
        edit_message_text(chat_id, message_id, "❌ Giveaway cancelled.")
        answer_callback_query(call["id"])
        return

    if data == "cancel_gw":
        delete_session(user_id, "giveaway")
        delete_session(user_id, "selection")
        edit_message_text(chat_id, message_id, "❌ Cancelled.")
        answer_callback_query(call["id"])
        return

    if data.startswith("del_channel_"):
        cid = data.replace("del_channel_", "")
        cursor.execute("DELETE FROM channels WHERE channel_id=? AND user_id=?", (cid, user_id))
        conn.commit()
        edit_message_text(chat_id, message_id, "✅ Channel removed successfully.")
        answer_callback_query(call["id"])
        return

    if data.startswith("del_tpl_"):
        tid = data.replace("del_tpl_", "")
        cursor.execute("DELETE FROM templates WHERE id=? AND user_id=?", (tid, user_id))
        conn.commit()

        edit_message_text(
            chat_id,
            message_id,
            "🗑 Template deleted successfully."
        )
        answer_callback_query(call["id"])
        return

    if data.startswith("view_tpl_"):
        tid = data.split("_")[-1]

        cursor.execute("""
            SELECT name, title, description, image_file_id,
                   winners, winner_type, duration, prizes, must_join
            FROM templates WHERE id=?
        """, (tid,))
        row = cursor.fetchone()

        if not row:
            answer_callback_query(call["id"], "Template not found.")
            return

        name, title, desc, image, winners, wtype, duration, prizes, must_join = row

        required_list = [x.strip() for x in (must_join or "").split(",") if x.strip()]
        required_count = len(required_list)

        img_status = "✅ Added" if image else "❌ None"

        text = f"""📄 <b>{name}</b>

🎁 Title: {title}
📝 Description: {desc}
🖼 Image: {img_status}
🏆 Winners: {winners}
🎲 Type: {wtype}
⏳ Duration: {duration}
📢 Required Subs: {required_count}

🎁 Prizes:
{prizes}
"""

        kb = {
            "inline_keyboard": [
                [
                    {"text": "🚀 Use Template", "callback_data": f"use_tpl_{tid}"},
                    {"text": "✏ Edit Template", "callback_data": f"edit_tpl_{tid}"}
                ],
                [
                    {"text": "🗑 Delete", "callback_data": f"del_tpl_{tid}"}
                ]
            ]
        }

        edit_message_text(chat_id, message_id, text, reply_markup=kb)
        answer_callback_query(call["id"])
        return

    if data.startswith("edit_tpl_"):
        tid = data.split("_")[-1]

        kb = {
            "inline_keyboard": [
                [
                    {"text": "🖼 Edit Image", "callback_data": f"tpl_edit_img_{tid}"},
                    {"text": "❌ Delete Image", "callback_data": f"tpl_del_img_{tid}"}
                ],
                [
                    {"text": "⏳ Edit Duration", "callback_data": f"tpl_edit_dur_{tid}"},
                    {"text": "🎁 Edit Prizes", "callback_data": f"tpl_edit_prize_{tid}"}
                ],
                [
                    {"text": "🏆 Edit Winners", "callback_data": f"tpl_edit_win_{tid}"},
                    {"text": "🎲 Edit Winner Type", "callback_data": f"tpl_edit_type_{tid}"}
                ],
                [
                    {"text": "📢 Edit Required Subs", "callback_data": f"tpl_edit_req_{tid}"}
                ],
                [
                    {"text": "↩ Back", "callback_data": f"view_tpl_{tid}"}
                ]
            ]
        }

        edit_message_text(
            chat_id,
            message_id,
            "✏ <b>Edit Template</b>\n\nSelect what you want to modify:",
            reply_markup=kb
        )
        answer_callback_query(call["id"])
        return

    if data.startswith("tpl_edit_dur_"):
        tid = data.split("_")[-1]
        save_session(user_id, "template", {"step": "edit_duration", "tid": tid})
        send_message(user_id, "⏳ Enter new duration (5m / 1h / 2d):")
        answer_callback_query(call["id"])
        return

    if data.startswith("tpl_edit_prize_"):
        tid = data.split("_")[-1]
        save_session(user_id, "template", {"step": "edit_prizes", "tid": tid})
        send_message(user_id, "🎁 Send new prizes (one per line):")
        answer_callback_query(call["id"])
        return

    if data.startswith("tpl_edit_img_"):
        tid = data.split("_")[-1]
        save_session(user_id, "template", {"step": "edit_image", "tid": tid})
        send_message(user_id, "🖼 Send new image:")
        answer_callback_query(call["id"])
        return

    if data.startswith("tpl_del_img_"):
        tid = data.split("_")[-1]
        cursor.execute("UPDATE templates SET image_file_id=NULL WHERE id=?", (tid,))
        conn.commit()
        answer_callback_query(call["id"], "Image deleted ✅")
        return

    if data.startswith("tpl_edit_req_"):
        tid = data.split("_")[-1]
        save_session(user_id, "template", {"step": "edit_required", "tid": tid})
        send_message(
            user_id,
            """📢 Send required channels (optional)

Send:
-1001234567890
@channelusername

Separate multiple with space or newline.
Send 0 to clear."""
        )
        answer_callback_query(call["id"])
        return

    if data.startswith("use_tpl_"):
        tid = data.split("_")[-1]

        cursor.execute("""
            SELECT title, description, image_file_id, winners,
                   winner_type, duration, prizes, must_join
            FROM templates WHERE id=? AND user_id=?
        """, (tid, user_id))
        row = cursor.fetchone()

        if not row:
            answer_callback_query(call["id"], "Template not found.")
            return

        title, desc, image, winners, wtype, duration, prizes, must_join = row

        cursor.execute("SELECT channel_id, title FROM channels WHERE user_id=?", (user_id,))
        rows = cursor.fetchall()

        if not rows:
            answer_callback_query(call["id"], "No channels added.")
            return

        save_session(user_id, "selection", {"channels": []})
        save_session(user_id, "giveaway", {
            "title": title,
            "description": desc,
            "winners": winners,
            "winner_type": wtype,
            "duration": duration,
            "prizes": prizes.split("\n"),
            "image": image,
            "must_join": [x.strip() for x in (must_join or "").split(",") if x.strip()],
            "step": "template_channel_select"
        })

        markup = {"inline_keyboard": []}
        for cid, cname in rows:
            markup["inline_keyboard"].append([{"text": f"☑ {cname}", "callback_data": f"tpl_toggle_{cid}"}])

        markup["inline_keyboard"].append([{"text": "✅ Confirm Channels", "callback_data": "tpl_confirm_channels"}])
        markup["inline_keyboard"].append([{"text": "❌ Cancel", "callback_data": "cancel_gw"}])

        edit_message_text(
            chat_id,
            message_id,
            """🚀 <b>Create Giveaway from Template</b>

Select one or more channels to publish:""",
            reply_markup=markup
        )
        answer_callback_query(call["id"])
        return

    if data.startswith("tpl_toggle_"):
        cid = data.replace("tpl_toggle_", "")
        selection = load_session(user_id, "selection") or {"channels": []}

        if cid in selection["channels"]:
            selection["channels"].remove(cid)
        else:
            selection["channels"].append(cid)

        save_session(user_id, "selection", selection)

        cursor.execute("SELECT channel_id, title FROM channels WHERE user_id=?", (user_id,))
        rows = cursor.fetchall()

        markup = {"inline_keyboard": []}
        for channel_id, title in rows:
            text = f"✅ {title}" if channel_id in selection["channels"] else f"☑ {title}"
            markup["inline_keyboard"].append([{"text": text, "callback_data": f"tpl_toggle_{channel_id}"}])

        markup["inline_keyboard"].append([{"text": "✅ Confirm Channels", "callback_data": "tpl_confirm_channels"}])
        markup["inline_keyboard"].append([{"text": "❌ Cancel", "callback_data": "cancel_gw"}])

        edit_message_reply_markup(chat_id, message_id, reply_markup=markup)
        answer_callback_query(call["id"])
        return

    if data == "tpl_confirm_channels":
        selection = load_session(user_id, "selection") or {"channels": []}
        if not selection["channels"]:
            answer_callback_query(call["id"], "Select at least one channel!")
            return

        giveaway = load_session(user_id, "giveaway") or {}
        giveaway["channels"] = selection["channels"]
        save_session(user_id, "giveaway", giveaway)

        fake_call = dict(call)
        fake_call["data"] = "publish_gw"
        handle_callback(fake_call)
        return

    if data == "confirm_channels":
        selection = load_session(user_id, "selection") or {"channels": []}

        if not selection["channels"]:
            answer_callback_query(call["id"], "Select at least one channel!")
            return

        save_session(user_id, "giveaway", {
            "channels": selection["channels"],
            "image": None,
            "step": "image"
        })

        markup = {
            "inline_keyboard": [
                [{"text": "⏭ Skip", "callback_data": "skip_image"}]
            ]
        }

        edit_message_text(
            chat_id,
            message_id,
            """🖼 <b>Step 2/8:</b> Send a giveaway image (Optional)

📸 Upload an image for your giveaway post.

Send /cancel to abort.""",
            reply_markup=markup
        )
        answer_callback_query(call["id"])
        return

    if data.startswith("toggle_"):
        cid = data.replace("toggle_", "")
        selection = load_session(user_id, "selection") or {"channels": []}

        if cid in selection["channels"]:
            selection["channels"].remove(cid)
        else:
            selection["channels"].append(cid)

        save_session(user_id, "selection", selection)

        cursor.execute("SELECT channel_id, title FROM channels WHERE user_id=?", (user_id,))
        rows = cursor.fetchall()

        markup = {"inline_keyboard": []}
        for channel_id, title in rows:
            text = f"✅ {title}" if channel_id in selection["channels"] else f"☑ {title}"
            markup["inline_keyboard"].append([{"text": text, "callback_data": f"toggle_{channel_id}"}])

        markup["inline_keyboard"].append([{"text": "✅ Confirm Selection", "callback_data": "confirm_channels"}])
        markup["inline_keyboard"].append([{"text": "❌ Cancel", "callback_data": "cancel_gw"}])

        edit_message_reply_markup(chat_id, message_id, reply_markup=markup)
        answer_callback_query(call["id"])
        return

    if data == "skip_image":
        giveaway = load_session(user_id, "giveaway")
        if not giveaway:
            answer_callback_query(call["id"])
            return

        giveaway["image"] = None
        giveaway["step"] = "title"
        save_session(user_id, "giveaway", giveaway)

        edit_message_text(
            chat_id,
            message_id,
            """⏭ Image skipped.

<b>Step 3/8:</b> Enter the giveaway title.

Send /cancel to abort."""
        )
        answer_callback_query(call["id"])
        return

    if data in ["winner_random", "winner_first"]:
        giveaway = load_session(user_id, "giveaway")
        if not giveaway:
            answer_callback_query(call["id"])
            return

        if giveaway.get("step") != "waiting_winner_type":
            answer_callback_query(call["id"])
            return

        giveaway["winner_type"] = "Random Selection" if data == "winner_random" else "First X Participants"
        giveaway["step"] = "prize"
        save_session(user_id, "giveaway", giveaway)

        edit_message_text(
            chat_id,
            message_id,
            """🎁 <b>Step 8/8:</b> Send the giveaway prize details
━━━━━━━━━━━━━━━━━━

<b>Prize Formats:</b>
• user:pass → johndoe:12345
• email:pass → test@gmail.com:1234
• code/key → ABC1-DEF2-GHI3

📌 Note: One prize per line. Auto-detected."""
        )
        answer_callback_query(call["id"])
        return

    if data.startswith("delete_gw_"):
        gw_id = data.replace("delete_gw_", "")

        kb = {
            "inline_keyboard": [
                [{"text": "✅ Yes, Delete", "callback_data": f"confirm_delete_{gw_id}"}],
                [{"text": "❌ No", "callback_data": "cancel_delete"}]
            ]
        }

        edit_message_reply_markup(chat_id, message_id, reply_markup=kb)
        answer_callback_query(call["id"])
        return

    if data == "cancel_delete":
        answer_callback_query(call["id"], "Cancelled ❌")
        return

    if data.startswith("confirm_delete_"):
        gw_id = data.replace("confirm_delete_", "")

        cursor.execute(
            "SELECT channel_id, message_id FROM giveaway_messages WHERE gw_id=?",
            (gw_id,)
        )
        rows = cursor.fetchall()

        for ch_id, msg_id in rows:
            try:
                delete_message(ch_id, msg_id)
            except:
                pass

        cursor.execute("DELETE FROM giveaways WHERE gw_id=?", (gw_id,))
        cursor.execute("DELETE FROM participants WHERE gw_id=?", (gw_id,))
        cursor.execute("DELETE FROM giveaway_messages WHERE gw_id=?", (gw_id,))
        conn.commit()

        edit_message_text(
            chat_id,
            message_id,
            "❌ <b>Giveaway Cancelled Successfully.</b>\n\nAll giveaway data removed."
        )

        answer_callback_query(call["id"], "Giveaway Deleted ❌")
        return

    if data == "skip_join":
        giveaway = load_session(user_id, "giveaway")
        if not giveaway:
            answer_callback_query(call["id"])
            return

        giveaway["must_join"] = []
        giveaway["step"] = "preview"
        save_session(user_id, "giveaway", giveaway)
        show_preview(chat_id, user_id)
        answer_callback_query(call["id"])
        return

    if data == "publish_gw":
        giveaway = load_session(user_id, "giveaway")
        if not giveaway:
            answer_callback_query(call["id"])
            return

        gw_id = str(uuid.uuid4())[:8]
        duration_text = giveaway.get("duration", "5m")
        match = re.search(r"(\d+)([mhd])", duration_text)

        if not match:
            answer_callback_query(call["id"], "❌ Invalid duration format! Use 5m / 1h / 2d")
            return

        value = int(match.group(1))
        unit = match.group(2)

        if unit == "m":
            delta = timedelta(minutes=value)
        elif unit == "h":
            delta = timedelta(hours=value)
        else:
            delta = timedelta(days=value)

        publish_time = datetime.now().replace(microsecond=0)
        end_time = publish_time + delta

        required_list = giveaway.get("must_join", [])
        if isinstance(required_list, str):
            required_list = [x.strip() for x in required_list.split(",") if x.strip()]

        required_text = ""
        if required_list:
            required_text = "\n\n📢 Required Channels:\n"
            for ch in required_list:
                required_text += f"• {ch}\n"

        prize_type = get_prize_type(giveaway.get("prizes", []))

        caption = f"""✅ <b>GIVEAWAY STARTED</b>

🎁 <b>{giveaway['title']}</b>

📝 <b>Description:</b>
{giveaway['description']}{required_text}

🏆 <b>Prize:</b> {prize_type}
⏳ <b>Deadline:</b> {format_remaining_full(end_time)} remaining
🎲 <b>Selection Type:</b> {giveaway['winner_type']}
👥 <b>Total Participants:</b> 0
👑 <b>Total Winners:</b> {giveaway['winners']}

🎯 Tap below to participate!
"""

        me = get_me()
        bot_username = me["result"]["username"] if me.get("ok") else ""

        kb = {
            "inline_keyboard": [
                [{"text": "🎉 Join Giveaway", "url": f"https://t.me/{bot_username}?start=join_{gw_id}"}],
                [{"text": "🔄 Reload Status", "callback_data": f"reload_{gw_id}"}]
            ]
        }

        posted_names = []
        message_ids = {}

        for channel in giveaway["channels"]:
            try:
                if giveaway.get("image"):
                    msg = send_photo(channel, giveaway["image"], caption=caption, reply_markup=kb)
                else:
                    msg = send_message(channel, caption, reply_markup=kb, disable_web_page_preview=True)

                if msg.get("ok"):
                    message_ids[str(channel)] = int(msg["result"]["message_id"])

                try:
                    ch = get_chat(channel)
                    if ch.get("ok"):
                        posted_names.append(ch["result"].get("title", str(channel)))
                    else:
                        posted_names.append(str(channel))
                except:
                    posted_names.append(str(channel))
            except Exception as e:
                print("Post failed:", e)

        cursor.execute(
            "INSERT INTO giveaways VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                gw_id,
                user_id,
                ",".join([str(x) for x in giveaway["channels"]]),
                giveaway.get("title", ""),
                giveaway.get("description", ""),
                giveaway["image"] if giveaway.get("image") else "",
                giveaway.get("duration", ""),
                end_time.strftime("%Y-%m-%d %H:%M:%S"),
                int(giveaway.get("winners", 1)),
                giveaway.get("winner_type", "Random Selection"),
                "\n".join(giveaway.get("prizes", [])),
                ",".join(required_list),
                0
            )
        )

        for ch_id, msg_id in message_ids.items():
            cursor.execute("INSERT INTO giveaway_messages VALUES (?,?,?)", (gw_id, ch_id, msg_id))

        conn.commit()

        delete_session(user_id, "giveaway")
        delete_session(user_id, "selection")

        posted_lines = "\n".join([f"• {n}" for n in posted_names]) if posted_names else "• (none)"

        success_kb = {
            "inline_keyboard": [
                [{"text": "🗑 Delete Giveaway", "callback_data": f"delete_gw_{gw_id}"}]
            ]
        }

        edit_message_text(
            chat_id,
            message_id,
            f"""✅ <b>Giveaway Created Successfully!</b>

🎉 Your giveaway has been posted to:
{posted_lines}

📊 Winners will be selected automatically when the deadline is reached.""",
            reply_markup=success_kb
        )
        answer_callback_query(call["id"])
        return

    if data.startswith("reload_"):
        gw_id = data.replace("reload_", "").strip()

        cursor.execute("SELECT title, description, end_time, winners, winner_type, must_join, ended FROM giveaways WHERE gw_id=?", (gw_id,))
        row = cursor.fetchone()
        if not row:
            answer_callback_query(call["id"], "Not found / ended.")
            return

        title, description, end_time_str, winners, winner_type, must_join_raw, ended = row
        end_time = parse_end_time(end_time_str)

        cursor.execute("SELECT COUNT(*) FROM participants WHERE gw_id=?", (gw_id,))
        total = cursor.fetchone()[0]

        must_list = [x.strip() for x in (must_join_raw or "").split(",") if x.strip()]
        required_text = ""
        if must_list:
            required_text = "\n\n📢 <b>Required Subscriptions:</b>\n" + "\n".join([f"- {x}" for x in must_list])

        if int(ended) == 1 or datetime.now() >= end_time:
            answer_callback_query(call["id"], "Giveaway ended.")
            return

        me = get_me()
        bot_username = me["result"]["username"] if me.get("ok") else ""

        caption = f"""✅ <b>GIVEAWAY STARTED</b>

🎁 <b>{title}</b>

📝 <b>Description:</b>
{description}{required_text}

⏳ <b>Deadline:</b> {format_remaining_full(end_time)} remaining
🎲 <b>Selection Type:</b> {winner_type}
👥 <b>Total Participants:</b> {total}
👑 <b>Total Winners:</b> {winners}

🎯 Tap below to participate!
"""

        kb = {
            "inline_keyboard": [
                [{"text": "🎉 Join Giveaway", "url": f"https://t.me/{bot_username}?start=join_{gw_id}"}],
                [{"text": "🔄 Reload Status", "callback_data": f"reload_{gw_id}"}]
            ]
        }

        safe_edit_any(chat_id, message_id, caption, reply_markup=kb)
        answer_callback_query(call["id"], "Updated ✅")
        return

    if data.startswith("tpl_edit_win_"):
        answer_callback_query(call["id"], "This button is not configured yet.")
        return

    if data.startswith("tpl_edit_type_"):
        answer_callback_query(call["id"], "This button is not configured yet.")
        return

# ================= AUTO WINNER SELECTOR =================

def check_giveaways_once():
    try:
        cursor.execute("""
            SELECT gw_id, channels, title, description, end_time,
                   winners, winner_type, prizes, ended
            FROM giveaways
        """)
        rows = cursor.fetchall()

        for row in rows:
            gw_id, channels_raw, title, description, end_time_str, winners, winner_type, prizes_raw, ended = row

            if int(ended) == 1:
                continue

            end_time = parse_end_time(end_time_str)
            remaining_seconds = (end_time - datetime.now()).total_seconds()

            if remaining_seconds > 0:
                continue

            cursor.execute("UPDATE giveaways SET ended=1 WHERE gw_id=?", (gw_id,))
            conn.commit()

            cursor.execute(
                "SELECT user_id FROM participants WHERE gw_id=? ORDER BY join_time ASC",
                (gw_id,)
            )
            users = [u[0] for u in cursor.fetchall()]

            prizes = [p.strip() for p in (prizes_raw or "").split("\n") if p.strip()]
            total_participants = len(users)

            winners = int(winners)
            selected = []

            if users:
                if winner_type == "First X Participants":
                    selected = users[:min(winners, len(users))]
                else:
                    selected = random.sample(users, k=min(winners, len(users)))

            if total_participants == 0:
                ended_text = f"""🏁 <b>GIVEAWAY ENDED</b>

🎁 {title}

📝 {description}

👥 Total Participants: 0
🎲 Selection Type: {winner_type}

❌ No participants joined this giveaway."""
            else:
                winner_lines = []
                for i, uid in enumerate(selected, start=1):
                    winner_lines.append(f"{i}. <a href='tg://user?id={uid}'>Winner</a>")

                ended_text = f"""🏁 <b>GIVEAWAY ENDED</b>

🎁 {title}

📝 {description}

👥 Total Participants: {total_participants}
🎲 Selection Type: {winner_type}
🏆 Total Winners: {len(selected)}

🏅 <b>Winners:</b>
{chr(10).join(winner_lines)}

🎉 Congratulations to all winners!"""

            cursor.execute(
                "SELECT channel_id, message_id FROM giveaway_messages WHERE gw_id=?",
                (gw_id,)
            )
            msg_rows = cursor.fetchall()

            for ch_id, msg_id in msg_rows:
                try:
                    safe_edit_any(ch_id, int(msg_id), ended_text, reply_markup=None)
                except:
                    pass

            if selected and prizes:
                for i, uid in enumerate(selected):
                    prize = prizes[i] if i < len(prizes) else prizes[-1]
                    try:
                        send_message(
                            uid,
                            f"""🎉🎉🎉 <b>CONGRATULATIONS!</b> 🎉🎉🎉

🏆 You are a WINNER of the giveaway:
<b>{title}</b>

🎁 <b>Your Prize:</b>

<code>{html.escape(prize)}</code>

✨ Please share a screenshot in the giveaway chat!

💝 Enjoy your reward!"""
                        )
                    except:
                        pass

            cursor.execute("DELETE FROM participants WHERE gw_id=?", (gw_id,))
            cursor.execute("DELETE FROM giveaway_messages WHERE gw_id=?", (gw_id,))
            conn.commit()

    except Exception as e:
        print("Winner check error:", e)

# ================= FASTAPI ROUTES =================

@app.get("/")
def home():
    return {"ok": True, "message": "Give Flow webhook bot is running."}

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/cron/check-giveaways")
def cron_check(secret: str = ""):
    if WEBHOOK_SECRET and secret != WEBHOOK_SECRET:
        return {"ok": False, "error": "unauthorized"}

    check_giveaways_once()
    return {"ok": True, "message": "checked"}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    if WEBHOOK_SECRET:
        header_secret = request.headers.get("x-telegram-bot-api-secret-token", "")
        if header_secret != WEBHOOK_SECRET:
            return {"ok": False, "error": "unauthorized"}

    update = await request.json()
    print("Webhook received")

    try:
        if "message" in update:
            message = update["message"]

            if "photo" in message:
                handled = handle_photo_message(message)
                if handled:
                    return {"ok": True}

            if "text" in message:
                handle_text_message(message)
                return {"ok": True}

        elif "callback_query" in update:
            handle_callback(update["callback_query"])
            return {"ok": True}

    except Exception as e:
        print("Webhook error:", e)

    return {"ok": True}
