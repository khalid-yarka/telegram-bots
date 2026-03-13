# src/bots/dhalinyaro_bot/bot.py
"""
Dhalinyaro Bot - Simple Broadcast Group
- Users join with /start
- ANY message (text, photo, video, file) is forwarded to ALL users
- Shows who sent it
- Simple ban/unban for admins
"""

import telebot
import logging
import sqlite3
from telebot.types import Update, Message
from src.config import DHALINYARO_DB_PATH

logger = logging.getLogger(__name__)

# Admin IDs
ADMIN_IDS = [2094426161]  # Your Telegram ID

# Database setup
def init_database():
    with sqlite3.connect(DHALINYARO_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                name TEXT,
                username TEXT,
                banned INTEGER DEFAULT 0
            )
        """)
init_database()


class DhalinyaroBot:
    def __init__(self, token: str):
        self.bot = telebot.TeleBot(token, threaded=False)
        self._register_handlers()
        logger.info("Dhalinyaro bot started")
    
    def _register_handlers(self):
        @self.bot.message_handler(commands=['start'])
        def start(message: Message):
            user = message.from_user
            name = user.first_name or "User"
            
            # Save user
            with sqlite3.connect(DHALINYARO_DB_PATH) as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO users (user_id, name, username) VALUES (?, ?, ?)",
                    (user.id, name, user.username)
                )
            
            self.bot.reply_to(
                message,
                f"✅ Welcome {name}! You're now in the broadcast group.\nAny message you send will be seen by everyone."
            )
            logger.info(f"User joined: {user.id} - {name}")
        
        @self.bot.message_handler(commands=['ban'])
        def ban(message: Message):
            user_id = message.from_user.id
            if user_id not in ADMIN_IDS:
                return
            
            parts = message.text.split()
            if len(parts) != 2:
                self.bot.reply_to(message, "Usage: /ban 123456789")
                return
            
            try:
                target = int(parts[1])
                with sqlite3.connect(DHALINYARO_DB_PATH) as conn:
                    conn.execute("UPDATE users SET banned = 1 WHERE user_id = ?", (target,))
                self.bot.reply_to(message, f"✅ User {target} banned")
                logger.info(f"Admin {user_id} banned {target}")
            except:
                self.bot.reply_to(message, "❌ Invalid user ID")
        
        @self.bot.message_handler(commands=['unban'])
        def unban(message: Message):
            user_id = message.from_user.id
            if user_id not in ADMIN_IDS:
                return
            
            parts = message.text.split()
            if len(parts) != 2:
                self.bot.reply_to(message, "Usage: /unban 123456789")
                return
            
            try:
                target = int(parts[1])
                with sqlite3.connect(DHALINYARO_DB_PATH) as conn:
                    conn.execute("UPDATE users SET banned = 0 WHERE user_id = ?", (target,))
                self.bot.reply_to(message, f"✅ User {target} unbanned")
                logger.info(f"Admin {user_id} unbanned {target}")
            except:
                self.bot.reply_to(message, "❌ Invalid user ID")
        
        @self.bot.message_handler(commands=['users'])
        def users(message: Message):
            user_id = message.from_user.id
            if user_id not in ADMIN_IDS:
                return
            
            with sqlite3.connect(DHALINYARO_DB_PATH) as conn:
                cursor = conn.execute("SELECT user_id, name, username, banned FROM users")
                rows = cursor.fetchall()
            
            text = f"📊 **Total Users: {len(rows)}**\n\n"
            for uid, name, username, banned in rows[:10]:
                status = "🚫" if banned else "✅"
                user_display = f"@{username}" if username else name
                text += f"{status} {user_display} (`{uid}`)\n"
            
            self.bot.reply_to(message, text, parse_mode="Markdown")
        
        # Handle ALL message types - forward to everyone
        @self.bot.message_handler(func=lambda m: True, content_types=[
            'text', 'audio', 'document', 'photo', 'sticker', 'video',
            'voice', 'location', 'contact', 'venue'
        ])
        def broadcast(message: Message):
            sender = message.from_user
            sender_id = sender.id
            sender_name = sender.first_name or "User"
            sender_username = f"@{sender.username}" if sender.username else sender_name
            
            # Check if sender is banned
            with sqlite3.connect(DHALINYARO_DB_PATH) as conn:
                cursor = conn.execute(
                    "SELECT banned FROM users WHERE user_id = ?",
                    (sender_id,)
                )
                row = cursor.fetchone()
                
                if not row:
                    # Auto-add if not in database
                    conn.execute(
                        "INSERT INTO users (user_id, name, username) VALUES (?, ?, ?)",
                        (sender_id, sender_name, sender.username)
                    )
                elif row[0] == 1:
                    self.bot.reply_to(
                        message,
                        "🚫 You are banned from broadcasting."
                    )
                    return
            
            # Get all active users
            with sqlite3.connect(DHALINYARO_DB_PATH) as conn:
                cursor = conn.execute(
                    "SELECT user_id FROM users WHERE banned = 0"
                )
                users = cursor.fetchall()
            
            # Forward message to everyone
            sent = 0
            failed = 0
            
            for (uid,) in users:
                if uid == sender_id:
                    continue  # Don't send to self
                
                try:
                    # Copy message with sender info
                    caption = f"💬 **{sender_username}:**"
                    if message.caption:
                        caption = f"💬 **{sender_username}:** {message.caption}"
                    
                    self.bot.copy_message(
                        chat_id=uid,
                        from_chat_id=message.chat.id,
                        message_id=message.message_id,
                        caption=caption,
                        parse_mode="Markdown"
                    )
                    sent += 1
                except Exception as e:
                    failed += 1
                    logger.debug(f"Failed to send to {uid}: {e}")
            
            # Confirm to sender
            self.bot.reply_to(
                message,
                f"✅ Sent to {sent} users" + (f" ({failed} failed)" if failed else "")
            )
            
            logger.info(f"User {sender_id} broadcast to {sent} users")
    
    def process_update(self, update_json):
        update = Update.de_json(update_json)
        self.bot.process_new_updates([update])
        return True


# ==================== WEBHOOK ENTRY ====================

_active_bots = {}

def process_dhalinyaro_update(bot_token, update_json):
    if bot_token not in _active_bots:
        _active_bots[bot_token] = DhalinyaroBot(bot_token)
    
    # Keep cache small
    if len(_active_bots) > 3:
        oldest = next(iter(_active_bots))
        del _active_bots[oldest]
    
    return _active_bots[bot_token].process_update(update_json)