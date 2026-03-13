# src/bots/master_bot/keyboards.py
"""
Simplified keyboards for Master Bot
- Minimal memory usage
- Fewer buttons per keyboard
- Faster rendering
"""

from telebot import types


def main_menu_keyboard(user_id):
    """
    Main menu reply keyboard - 2 rows max
    """
    from src.utils.permissions import is_super_admin
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    # Row 1: Core functions
    markup.row(
        types.KeyboardButton("🤖 My Bots"),
        types.KeyboardButton("➕ Add Bot")
    )
    
    # Row 2: Secondary functions
    markup.row(
        types.KeyboardButton("🌐 Webhooks"),
        types.KeyboardButton("📊 Statistics")
    )
    
    # Row 3: Admin (if super admin)
    if is_super_admin(user_id):
        markup.row(types.KeyboardButton("👑 Admin Panel"))
    
    # Help is always available via command
    return markup


def simple_bot_list_keyboard(bots, max_buttons=3):
    """
    Simple inline keyboard for bot list
    Returns: (text, markup)
    """
    if not bots:
        text = "🤷 No bots found."
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(
            "➕ Add Bot",
            callback_data="add_bot_start"
        ))
        return text, markup
    
    text = f"🤖 **Your Bots** ({len(bots)} total)\n\n"
    
    # Show first few bots
    for i, bot in enumerate(bots[:max_buttons], 1):
        name = bot.get('bot_name', 'Unnamed')
        status = "🟢" if bot.get('is_active') else "🔴"
        text += f"{status} **{name}**\n"
    
    if len(bots) > max_buttons:
        text += f"\n... and {len(bots) - max_buttons} more"
    
    # Create keyboard
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # Add bot buttons
    for bot in bots[:max_buttons]:
        name = bot.get('bot_name', 'Unnamed')[:20]
        markup.add(types.InlineKeyboardButton(
            f"📋 {name}",
            callback_data=f"view_bot:{bot['bot_token']}"
        ))
    
    # Action row
    action_row = []
    action_row.append(types.InlineKeyboardButton(
        "➕ Add",
        callback_data="add_bot_start"
    ))
    
    if len(bots) > max_buttons:
        action_row.append(types.InlineKeyboardButton(
            "📋 View All",
            callback_data="back_to_bots"
        ))
    
    markup.row(*action_row)
    
    # Back to menu
    markup.add(types.InlineKeyboardButton(
        "🔙 Main Menu",
        callback_data="back_to_menu"
    ))
    
    return text, markup


def bot_details_keyboard(bot_token, user_id):
    """
    Minimal bot details keyboard
    """
    from src.utils.permissions import can_manage_bot
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Row 1: Basic actions
    markup.add(
        types.InlineKeyboardButton("🌐 Webhook", callback_data=f"webhook:{bot_token}"),
        types.InlineKeyboardButton("✏️ Edit", callback_data=f"edit_name:{bot_token}")
    )
    
    # Row 2: Delete (if allowed)
    if can_manage_bot(bot_token, user_id):
        markup.add(types.InlineKeyboardButton(
            "🗑️ Delete",
            callback_data=f"delete_confirm:{bot_token}"
        ))
    
    # Row 3: Navigation
    markup.row(
        types.InlineKeyboardButton("🔙 Back", callback_data="back_to_bots"),
        types.InlineKeyboardButton("🏠 Menu", callback_data="back_to_menu")
    )
    
    return markup


def confirmation_keyboard(action, bot_token, cancel_action="back_to_bots"):
    """
    Simple yes/no confirmation keyboard
    """
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.add(
        types.InlineKeyboardButton("✅ Yes", callback_data=f"{action}:{bot_token}"),
        types.InlineKeyboardButton("❌ No", callback_data=cancel_action)
    )
    
    return markup


def webhook_keyboard(bot_token):
    """
    Simple webhook keyboard
    """
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.add(
        types.InlineKeyboardButton("🔄 Check", callback_data=f"webhook:{bot_token}"),
        types.InlineKeyboardButton("🔙 Back", callback_data=f"view_bot:{bot_token}")
    )
    
    return markup


def admin_quick_keyboard():
    """
    Quick admin panel keyboard
    """
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.add(
        types.InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
        types.InlineKeyboardButton("📋 Logs", callback_data="admin_logs:1")
    )
    
    markup.add(types.InlineKeyboardButton(
        "🔙 Main Menu",
        callback_data="back_to_menu"
    ))
    
    return markup


def cancel_only_keyboard():
    """
    Simple cancel button for flows
    """
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        "❌ Cancel",
        callback_data="add_bot_cancel"
    ))
    return markup