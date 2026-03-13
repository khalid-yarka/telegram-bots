# src/bots/master_bot/handlers.py
"""
Optimized message handlers for Master Bot
- Lazy imports to reduce memory
- Simplified routing
- Minimal processing
"""

import logging
from telebot import types

# Lazy imports (will be loaded when needed)
from src.master_db.operations import get_user_bots, add_log_entry
from src.utils.permissions import is_super_admin
from src.bots.master_bot.keyboards import main_menu_keyboard

logger = logging.getLogger(__name__)


# ==================== COMMAND HANDLERS ====================

def handle_start_command(bot_instance, message):
    """Handle /start, /help, /menu commands"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    username = message.from_user.first_name or "User"
    
    # Clear any stale state
    bot_instance.state_manager.clear_state(chat_id)
    
    welcome = (
        f"👋 Welcome {username} to Master Bot Controller!\n\n"
        f"**What can I do?**\n"
        f"• Manage multiple Telegram bots\n"
        f"• Monitor webhooks\n"
        f"• Track bot activity\n\n"
        f"Use the buttons below or type:\n"
        f"• /mybots - List your bots\n"
        f"• /addbot - Add new bot\n"
        f"• /webhook - Check webhooks"
    )
    
    bot_instance.safe_send(
        chat_id,
        welcome,
        reply_markup=main_menu_keyboard(user_id),
        parse_mode="Markdown"
    )
    
    # Log action (lightweight)
    try:
        add_log_entry(bot_instance.bot_token, 'start', user_id)
    except:
        pass


def handle_mybots(bot_instance, message):
    """Handle /mybots command - list user's bots"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Get user's bots (fast query)
    bots = get_user_bots(user_id)
    
    if not bots:
        # No bots - simple message with add button
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(
            "➕ Add Your First Bot",
            callback_data="add_bot_start"
        ))
        
        bot_instance.safe_send(
            chat_id,
            "🤷 You don't have any bots yet.\nClick below to add your first bot!",
            reply_markup=markup
        )
        return
    
    # Create simple list (first 5 only)
    text = f"🤖 **Your Bots** ({len(bots)} total)\n\n"
    
    # Show first 5 bots
    for i, bot in enumerate(bots[:5], 1):
        name = bot.get('bot_name', 'Unnamed')
        bot_type = bot.get('bot_type', 'unknown')
        status = "🟢" if bot.get('is_active') else "🔴"
        
        text += f"{status} **{name}** ({bot_type})\n"
    
    if len(bots) > 5:
        text += f"\n... and {len(bots) - 5} more bots"
    
    # Create simple inline keyboard
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # Add first 3 bots as quick buttons
    for bot in bots[:3]:
        name = bot.get('bot_name', 'Unnamed')[:20]
        markup.add(types.InlineKeyboardButton(
            f"📋 {name}",
            callback_data=f"view_bot:{bot['bot_token']}"
        ))
    
    # Navigation row
    nav_row = []
    nav_row.append(types.InlineKeyboardButton(
        "➕ Add",
        callback_data="add_bot_start"
    ))
    
    if len(bots) > 3:
        nav_row.append(types.InlineKeyboardButton(
            "📋 View All",
            callback_data="back_to_bots"
        ))
    
    markup.row(*nav_row)
    
    # Back to menu
    markup.add(types.InlineKeyboardButton(
        "🔙 Main Menu",
        callback_data="back_to_menu"
    ))
    
    bot_instance.safe_send(
        chat_id,
        text,
        reply_markup=markup,
        parse_mode="Markdown"
    )
    
    bot_instance.log_action(user_id, 'list_bots', f"{len(bots)} bots")


def handle_addbot_command(bot_instance, message):
    """Handle /addbot command - start add bot flow"""
    # Lazy import inside function
    from src.bots.master_bot.flows.add_bot_flow import start_add_bot_flow
    start_add_bot_flow(bot_instance, message)


def handle_webhook_command(bot_instance, message):
    """Handle /webhook command"""
    # Lazy import
    from src.bots.master_bot.callbacks import show_webhook_menu
    show_webhook_menu(bot_instance, message)


def handle_stats_command(bot_instance, message):
    """Handle /stats command"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Get basic stats (fast)
    from src.master_db.operations import get_bot_count, get_system_stats
    
    if is_super_admin(user_id):
        # Super admin sees system stats
        stats = get_system_stats()
        
        text = "📊 **System Statistics**\n\n"
        text += f"• Total Bots: {stats.get('total_bots', 0)}\n"
        text += f"• Active Bots: {stats.get('active_bots', 0)}\n"
        text += f"• Total Logs: {stats.get('total_logs', 0)}\n"
        text += f"• Users: {stats.get('total_users', 0)}"
        
    else:
        # Regular user sees their stats
        bot_count = get_bot_count(user_id)
        
        text = f"📊 **Your Statistics**\n\n"
        text += f"• Your Bots: {bot_count}\n"
        text += f"• Max Bots: 10"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        "🔄 Refresh",
        callback_data="refresh_stats"
    ))
    markup.add(types.InlineKeyboardButton(
        "🔙 Main Menu",
        callback_data="back_to_menu"
    ))
    
    bot_instance.safe_send(
        chat_id,
        text,
        reply_markup=markup,
        parse_mode="Markdown"
    )
    
    bot_instance.log_action(user_id, 'stats')


# ==================== MESSAGE HANDLER ====================

def handle_message(bot_instance, message):
    """Handle all text messages (including reply keyboard)"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text.strip()
    
    # Check if user is in a flow
    current_state = bot_instance.state_manager.get_state(chat_id)
    
    if current_state:
        # User is in a flow - route to appropriate handler
        if current_state.startswith('add_bot_'):
            from src.bots.master_bot.flows.add_bot_flow import handle_flow_message
            handle_flow_message(bot_instance, message)
        elif current_state.startswith('edit_'):
            from src.bots.master_bot.flows.edit_bot_flow import handle_flow_message
            handle_flow_message(bot_instance, message)
        else:
            # Unknown state - clear it
            bot_instance.state_manager.clear_state(chat_id)
            bot_instance.safe_send(
                chat_id,
                "🔄 Session reset. Please try again.",
                reply_markup=main_menu_keyboard(user_id)
            )
        return
    
    # No active flow - handle menu buttons
    menu_actions = {
        "🤖 My Bots": handle_mybots,
        "➕ Add Bot": handle_addbot_command,
        "🌐 Webhooks": handle_webhook_command,
        "📊 Statistics": handle_stats_command,
        "👑 Admin": _handle_admin_panel,
    }
    
    if text in menu_actions:
        menu_actions[text](bot_instance, message)
    elif text == "❓ Help":
        handle_start_command(bot_instance, message)
    elif text == "❌ Cancel":
        _handle_cancel(bot_instance, message)
    else:
        # Unknown input - show menu
        bot_instance.safe_send(
            chat_id,
            "Please use the buttons below:",
            reply_markup=main_menu_keyboard(user_id)
        )


# ==================== PRIVATE HELPERS ====================

def _handle_admin_panel(bot_instance, message):
    """Handle admin panel button"""
    user_id = message.from_user.id
    
    if not is_super_admin(user_id):
        bot_instance.safe_send(
            message.chat.id,
            "❌ This area is for super admins only."
        )
        return
    
    # Lazy import admin commands
    from src.bots.master_bot.admin_commands import show_admin_panel
    show_admin_panel(bot_instance, message)


def _handle_cancel(bot_instance, message):
    """Handle cancel command"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Clear any state
    bot_instance.state_manager.clear_state(chat_id)
    
    bot_instance.safe_send(
        chat_id,
        "❌ Operation cancelled.\n\nBack to main menu:",
        reply_markup=main_menu_keyboard(user_id)
    )
    
    bot_instance.log_action(user_id, 'cancel')