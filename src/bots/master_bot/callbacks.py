# src/bots/master_bot/callbacks.py
"""
Optimized callback handler for Master Bot
- Uses handler mapping for O(1) lookup
- Lazy imports
- Minimal processing
"""

import logging
from telebot import types

# Lazy imports
from src.master_db.operations import (
    get_bot_by_token, get_user_bots, get_bot_users,
    get_webhook_status, add_log_entry
)
from src.utils.permissions import is_super_admin, can_manage_bot
from src.bots.master_bot.keyboards import main_menu_keyboard

logger = logging.getLogger(__name__)


# ==================== HANDLER MAPPING ====================
# Maps callback data prefixes to handler functions
# This is faster than if/elif chains

CALLBACK_HANDLERS = {}


def register_handler(prefix):
    """Decorator to register callback handlers"""
    def decorator(func):
        CALLBACK_HANDLERS[prefix] = func
        return func
    return decorator


# ==================== PROCESS CALLBACK ====================

def process_callback(bot_instance, call):
    """
    Main callback processor - uses mapping for O(1) lookup
    """
    user_id = call.from_user.id
    data = call.data
    
    try:
        # Log callback (lightweight)
        logger.debug(f"Callback from {user_id}: {data[:50]}")
        
        # Find matching handler
        for prefix, handler in CALLBACK_HANDLERS.items():
            if data.startswith(prefix):
                # Extract parameter if needed
                param = data[len(prefix):] if len(data) > len(prefix) else None
                handler(bot_instance, call, param)
                return
        
        # No handler found
        logger.warning(f"Unhandled callback: {data}")
        bot_instance.safe_answer_callback(
            call.id,
            "Unknown action",
            show_alert=True
        )
        
    except Exception as e:
        logger.error(f"Callback error: {e}", exc_info=True)
        bot_instance.safe_answer_callback(
            call.id,
            "❌ An error occurred",
            show_alert=True
        )


# ==================== NAVIGATION HANDLERS ====================

@register_handler("back_to_menu")
def handle_back_to_menu(bot_instance, call, _):
    """Return to main menu"""
    user_id = call.from_user.id
    
    bot_instance.safe_edit(
        call.message.chat.id,
        call.message.message_id,
        "🔙 Returning to main menu...",
        reply_markup=None
    )
    
    bot_instance.safe_send(
        call.message.chat.id,
        "👋 Main Menu:",
        reply_markup=main_menu_keyboard(user_id)
    )
    
    bot_instance.safe_answer_callback(call.id, "Main menu")


@register_handler("back_to_bots")
def handle_back_to_bots(bot_instance, call, _):
    """Return to bots list"""
    user_id = call.from_user.id
    
    # Get user's bots
    bots = get_user_bots(user_id)
    
    # Create simple list
    text = f"🤖 **Your Bots** ({len(bots)} total)\n\n"
    
    for i, bot in enumerate(bots[:5], 1):
        name = bot.get('bot_name', 'Unnamed')[:25]
        text += f"{i}. {name}\n"
    
    if len(bots) > 5:
        text += f"\n... and {len(bots) - 5} more"
    
    # Create keyboard
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # Add first 5 bots
    for bot in bots[:5]:
        name = bot.get('bot_name', 'Unnamed')[:20]
        markup.add(types.InlineKeyboardButton(
            f"📋 {name}",
            callback_data=f"view_bot:{bot['bot_token']}"
        ))
    
    markup.add(types.InlineKeyboardButton(
        "➕ Add New Bot",
        callback_data="add_bot_start"
    ))
    markup.add(types.InlineKeyboardButton(
        "🔙 Main Menu",
        callback_data="back_to_menu"
    ))
    
    bot_instance.safe_edit(
        call.message.chat.id,
        call.message.message_id,
        text,
        reply_markup=markup,
        parse_mode="Markdown"
    )
    
    bot_instance.safe_answer_callback(call.id, "Bots list")


# ==================== BOT DETAILS ====================

@register_handler("view_bot:")
def handle_view_bot(bot_instance, call, bot_token):
    """View bot details"""
    user_id = call.from_user.id
    
    if not bot_token:
        bot_instance.safe_answer_callback(call.id, "Invalid bot", show_alert=True)
        return
    
    # Check permission (fast check)
    if not (is_super_admin(user_id) or can_manage_bot(bot_token, user_id)):
        bot_instance.safe_answer_callback(call.id, "❌ No permission", show_alert=True)
        return
    
    # Get bot info
    bot_info = get_bot_by_token(bot_token)
    if not bot_info:
        bot_instance.safe_answer_callback(call.id, "❌ Bot not found", show_alert=True)
        return
    
    # Get webhook status (lightweight)
    webhook = get_webhook_status(bot_token)
    
    # Format message
    name = bot_info.get('bot_name', 'Unnamed')
    bot_type = bot_info.get('bot_type', 'unknown')
    status = "🟢 Active" if bot_info.get('is_active') else "🔴 Inactive"
    webhook_status = "✅ Active" if webhook and webhook.get('status') == 'active' else "❌ Inactive"
    
    text = f"📋 **{name}**\n\n"
    text += f"**Type:** {bot_type}\n"
    text += f"**Status:** {status}\n"
    text += f"**Webhook:** {webhook_status}\n"
    text += f"**Token:** `{bot_token[:8]}...`"
    
    # Create simple keyboard
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.add(
        types.InlineKeyboardButton("🌐 Webhook", callback_data=f"webhook:{bot_token}"),
        types.InlineKeyboardButton("✏️ Edit Name", callback_data=f"edit_name:{bot_token}")
    )
    
    if can_manage_bot(bot_token, user_id):
        markup.add(
            types.InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_confirm:{bot_token}")
        )
    
    markup.add(
        types.InlineKeyboardButton("🔙 Back", callback_data="back_to_bots")
    )
    
    bot_instance.safe_edit(
        call.message.chat.id,
        call.message.message_id,
        text,
        reply_markup=markup,
        parse_mode="Markdown"
    )
    
    bot_instance.safe_answer_callback(call.id, f"Viewing {name}")


# ==================== ADD BOT FLOW ====================

@register_handler("add_bot_start")
def handle_add_bot_start(bot_instance, call, _):
    """Start add bot flow"""
    from src.bots.master_bot.flows.add_bot_flow import start_add_bot_flow
    
    # Convert callback to message-like object
    class FakeMessage:
        def __init__(self, chat, from_user):
            self.chat = chat
            self.from_user = from_user
            self.text = "/addbot"
    
    fake_msg = FakeMessage(call.message.chat, call.from_user)
    start_add_bot_flow(bot_instance, fake_msg)
    bot_instance.safe_answer_callback(call.id, "Starting...")


@register_handler("add_bot_cancel")
def handle_add_bot_cancel(bot_instance, call, _):
    """Cancel add bot flow"""
    chat_id = call.message.chat.id
    
    bot_instance.state_manager.clear_state(chat_id)
    
    bot_instance.safe_edit(
        chat_id,
        call.message.message_id,
        "❌ Bot addition cancelled.",
        reply_markup=None
    )
    
    bot_instance.safe_send(
        chat_id,
        "👋 Main Menu:",
        reply_markup=main_menu_keyboard(call.from_user.id)
    )
    
    bot_instance.safe_answer_callback(call.id, "Cancelled")


# ==================== EDIT BOT ====================

@register_handler("edit_name:")
def handle_edit_name(bot_instance, call, bot_token):
    """Start edit bot name flow"""
    from src.bots.master_bot.flows.edit_bot_flow import start_edit_bot_name
    start_edit_bot_name(bot_instance, call, bot_token)


# ==================== DELETE BOT ====================

@register_handler("delete_confirm:")
def handle_delete_confirm(bot_instance, call, bot_token):
    """Confirm bot deletion"""
    from src.bots.master_bot.flows.delete_bot_flow import confirm_delete_bot
    confirm_delete_bot(bot_instance, call, bot_token)


@register_handler("delete_bot:")
def handle_delete_bot(bot_instance, call, bot_token):
    """Execute bot deletion"""
    from src.bots.master_bot.flows.delete_bot_flow import execute_delete_bot
    execute_delete_bot(bot_instance, call, bot_token)


# ==================== WEBHOOK HANDLERS ====================

@register_handler("webhook:")
def handle_webhook_details(bot_instance, call, bot_token):
    """Show webhook details"""
    user_id = call.from_user.id
    
    if not bot_token:
        bot_instance.safe_answer_callback(call.id, "Invalid bot", show_alert=True)
        return
    
    # Check permission
    if not (is_super_admin(user_id) or can_manage_bot(bot_token, user_id)):
        bot_instance.safe_answer_callback(call.id, "❌ No permission", show_alert=True)
        return
    
    # Get webhook info
    from src.utils.webhook_manager import check_webhook
    result = check_webhook(bot_token)
    
    if result.get('success'):
        status = result.get('status', 'unknown')
        url = result.get('url', 'Not set')
        
        if status == 'active':
            text = f"✅ **Webhook Active**\n\n🔗 `{url}`"
        else:
            text = f"❌ **Webhook Inactive**\n\nStatus: {status}"
            
        if result.get('last_error'):
            text += f"\n\n⚠️ Last error: {result['last_error']}"
    else:
        text = f"❌ Failed to check webhook: {result.get('error', 'Unknown')}"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🔄 Check Again", callback_data=f"webhook:{bot_token}"),
        types.InlineKeyboardButton("🔙 Back", callback_data=f"view_bot:{bot_token}")
    )
    
    bot_instance.safe_edit(
        call.message.chat.id,
        call.message.message_id,
        text,
        reply_markup=markup,
        parse_mode="Markdown"
    )
    
    bot_instance.safe_answer_callback(call.id, "Webhook info")


# ==================== STATISTICS ====================

@register_handler("refresh_stats")
def handle_refresh_stats(bot_instance, call, _):
    """Refresh statistics"""
    from src.bots.master_bot.handlers import handle_stats_command
    handle_stats_command(bot_instance, call.message)
    bot_instance.safe_answer_callback(call.id, "Refreshed")


# ==================== NOOP (Placeholder) ====================

@register_handler("noop")
def handle_noop(bot_instance, call, _):
    """Handle no-operation buttons"""
    bot_instance.safe_answer_callback(call.id)


# ==================== ADMIN HANDLERS (Simple) ====================

@register_handler("admin_stats")
def handle_admin_stats(bot_instance, call, _):
    """Admin stats - quick view"""
    user_id = call.from_user.id
    
    if not is_super_admin(user_id):
        bot_instance.safe_answer_callback(call.id, "❌ No permission", show_alert=True)
        return
    
    from src.master_db.operations import get_system_stats
    stats = get_system_stats()
    
    text = "👑 **Admin Quick Stats**\n\n"
    text += f"• Total Bots: {stats.get('total_bots', 0)}\n"
    text += f"• Active: {stats.get('active_bots', 0)}\n"
    text += f"• Logs (24h): {stats.get('logs_24h', 0)}\n"
    text += f"• Users: {stats.get('total_users', 0)}"
    
    bot_instance.safe_edit(
        call.message.chat.id,
        call.message.message_id,
        text,
        parse_mode="Markdown"
    )
    
    bot_instance.safe_answer_callback(call.id, "Stats")


# ==================== EXPORT HANDLERS ====================

def show_webhook_menu(bot_instance, message):
    """Show webhook management menu (called from handlers)"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    from src.master_db.operations import get_user_bots
    bots = get_user_bots(user_id)
    
    if not bots:
        bot_instance.safe_send(
            chat_id,
            "🤷 No bots to manage.\nAdd a bot first with /addbot",
            reply_markup=main_menu_keyboard(user_id)
        )
        return
    
    text = "🌐 **Webhook Management**\n\nSelect a bot:"
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for bot in bots[:5]:
        name = bot.get('bot_name', 'Unnamed')[:20]
        markup.add(types.InlineKeyboardButton(
            f"🌐 {name}",
            callback_data=f"webhook:{bot['bot_token']}"
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