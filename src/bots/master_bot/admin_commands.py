# src/bots/master_bot/admin_commands.py
"""
Lightweight admin commands for Master Bot
- Only essential functions
- Minimal database queries
"""

import logging
from telebot import types

from src.utils.permissions import is_super_admin
from src.master_db.operations import (
    get_all_bots, get_recent_logs, get_system_stats,
    add_log_entry, cleanup_old_logs
)

logger = logging.getLogger(__name__)


def show_admin_panel(bot_instance, message):
    """Show admin panel"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if not is_super_admin(user_id):
        bot_instance.safe_send(chat_id, "❌ Super admin access required.")
        return
    
    text = (
        "👑 **Admin Panel**\n\n"
        "• /admin_stats - System stats\n"
        "• /admin_logs - View logs\n"
        "• /admin_cleanup - Clean old logs"
    )
    
    # Simple inline keyboard
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
        types.InlineKeyboardButton("📋 Logs", callback_data="admin_logs:1")
    )
    markup.add(types.InlineKeyboardButton(
        "🔙 Main Menu",
        callback_data="back_to_menu"
    ))
    
    bot_instance.safe_send(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    add_log_entry(bot_instance.bot_token, 'admin_panel', user_id)


def admin_stats(bot_instance, message):
    """Show system statistics"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if not is_super_admin(user_id):
        bot_instance.safe_send(chat_id, "❌ Super admin access required.")
        return
    
    # Get stats (single query)
    stats = get_system_stats()
    
    text = "📊 **System Statistics**\n\n"
    text += f"• Total Bots: {stats.get('total_bots', 0)}\n"
    text += f"• Active Bots: {stats.get('active_bots', 0)}\n"
    
    if 'bots_by_type' in stats:
        text += "\n**By Type:**\n"
        for bot_type, count in stats['bots_by_type'].items():
            text += f"  • {bot_type}: {count}\n"
    
    text += f"\n• Total Logs: {stats.get('total_logs', 0)}\n"
    text += f"• Logs (24h): {stats.get('logs_24h', 0)}\n"
    text += f"• Total Users: {stats.get('total_users', 0)}"
    
    bot_instance.safe_send(chat_id, text, parse_mode="Markdown")
    add_log_entry(bot_instance.bot_token, 'admin_stats', user_id)


def admin_logs(bot_instance, message):
    """Show recent logs"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if not is_super_admin(user_id):
        bot_instance.safe_send(chat_id, "❌ Super admin access required.")
        return
    
    # Get limit from command
    parts = message.text.split()
    limit = 10
    if len(parts) > 1:
        try:
            limit = min(int(parts[1]), 50)
        except:
            pass
    
    logs = get_recent_logs(limit=limit)
    
    if not logs:
        bot_instance.safe_send(chat_id, "📭 No logs found.")
        return
    
    text = f"📋 **Recent Logs** (last {len(logs)})\n\n"
    
    for log in logs[:10]:  # Show first 10
        timestamp = log.get('timestamp', '')
        if timestamp:
            # Show only time
            time_str = str(timestamp)[11:19] if len(str(timestamp)) > 19 else str(timestamp)
        else:
            time_str = "??:??:??"
        
        action = log.get('action_type', 'unknown')[:15]
        user = log.get('user_id', 'system')
        
        text += f"🕒 {time_str} | 👤 {user} | 📝 {action}\n"
    
    if len(logs) > 10:
        text += f"\n... and {len(logs) - 10} more"
    
    bot_instance.safe_send(chat_id, text, parse_mode="Markdown")
    add_log_entry(bot_instance.bot_token, 'admin_logs', user_id)


def admin_cleanup(bot_instance, message):
    """Clean up old logs"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if not is_super_admin(user_id):
        bot_instance.safe_send(chat_id, "❌ Super admin access required.")
        return
    
    # Get days from src.config
    from src.config import config
    days = config.LOG_RETENTION_DAYS
    
    deleted = cleanup_old_logs(days=days)
    
    text = f"🧹 **Cleanup Complete**\n\n"
    text += f"• Deleted {deleted} old logs\n"
    text += f"• Retention: {days} days"
    
    bot_instance.safe_send(chat_id, text, parse_mode="Markdown")
    add_log_entry(bot_instance.bot_token, 'admin_cleanup', user_id, f"deleted {deleted}")


# Register command handlers (to be called from main bot)
def register_admin_commands(bot_instance):
    """Register admin command handlers"""
    
    @bot_instance.bot.message_handler(commands=['admin'])
    def handle_admin(message):
        show_admin_panel(bot_instance, message)
    
    @bot_instance.bot.message_handler(commands=['admin_stats'])
    def handle_admin_stats(message):
        admin_stats(bot_instance, message)
    
    @bot_instance.bot.message_handler(commands=['admin_logs'])
    def handle_admin_logs(message):
        admin_logs(bot_instance, message)
    
    @bot_instance.bot.message_handler(commands=['admin_cleanup'])
    def handle_admin_cleanup(message):
        admin_cleanup(bot_instance, message)