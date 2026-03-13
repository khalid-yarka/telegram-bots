import logging
from telebot import types

from src.master_db.operations import delete_bot, get_bot_by_token
from src.utils.webhook_manager import delete_webhook
from src.utils.permissions import can_manage_bot, is_super_admin
from src.bots.master_bot.keyboards import get_confirmation_keyboard

logger = logging.getLogger(__name__)

def register_delete_bot_flow(bot_instance):
    """Register handlers for delete bot flow"""

    @bot_instance.bot.callback_query_handler(func=lambda call: call.data.startswith('delete_confirm:'))
    def handle_delete_confirm(call):
        bot_token = call.data.split(':')[1]
        confirm_delete_bot(bot_instance, call, bot_token)

    @bot_instance.bot.callback_query_handler(func=lambda call: call.data.startswith('delete_bot:'))
    def handle_delete_execute(call):
        bot_token = call.data.split(':')[1]
        execute_delete_bot(bot_instance, call, bot_token)


def confirm_delete_bot(bot_instance, call, bot_token):
    """Show delete confirmation dialog"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    # Get bot info
    bot_info = get_bot_by_token(bot_token)
    if not bot_info:
        bot_instance.safe_answer_callback(call.id, "❌ Bot not found", show_alert=True)
        return

    # Check permission
    if not (is_super_admin(user_id) or can_manage_bot(bot_token, user_id)):
        bot_instance.safe_answer_callback(call.id, "❌ You don't have permission to delete this bot", show_alert=True)
        return

    bot_name = bot_info.get('bot_name', 'Unnamed')

    # Create confirmation message
    text = f"⚠️ **Delete Bot: {bot_name}**\n\n"
    text += "Are you sure you want to delete this bot?\n"
    text += "This action **CANNOT** be undone!\n\n"
    text += "• All bot data will be permanently removed\n"
    text += "• Webhook will be disabled\n"
    text += "• Users will lose access\n"
    text += "• Settings will be lost"

    # Use confirmation keyboard
    markup = get_confirmation_keyboard('delete_bot', bot_token, f"view_bot:{bot_token}")

    bot_instance.safe_edit(
        chat_id,
        message_id,
        text,
        reply_markup=markup,
        parse_mode='Markdown'
    )

    bot_instance.safe_answer_callback(call.id, "Confirm deletion")


def execute_delete_bot(bot_instance, call, bot_token):
    """Execute bot deletion"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    # Get bot info before deletion
    bot_info = get_bot_by_token(bot_token)
    if not bot_info:
        bot_instance.safe_answer_callback(call.id, "❌ Bot not found", show_alert=True)
        return

    bot_name = bot_info.get('bot_name', 'Unnamed')

    # Double-check permission
    if not (is_super_admin(user_id) or can_manage_bot(bot_token, user_id)):
        bot_instance.safe_answer_callback(call.id, "❌ Permission denied", show_alert=True)
        return

    # Show processing message
    bot_instance.safe_edit(
        chat_id,
        message_id,
        "🗑️ Deleting bot... Please wait.",
        reply_markup=None
    )

    # Delete webhook first
    webhook_deleted = delete_webhook(bot_token)

    # Delete from database
    success = delete_bot(bot_token, user_id)

    if success:
        text = f"✅ **Bot Deleted Successfully**\n\n"
        text += f"Bot '{bot_name}' has been permanently removed.\n"
        if webhook_deleted:
            text += "🌐 Webhook was also deleted."
        else:
            text += "⚠️ Webhook may still exist (delete manually if needed)."

        # Create return keyboard
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("📊 My Bots", callback_data="back_to_bots"),
            types.InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_menu")
        )

        bot_instance.safe_edit(
            chat_id,
            message_id,
            text,
            reply_markup=markup,
            parse_mode='Markdown'
        )

        bot_instance.log_action(user_id, 'delete_bot', f"Deleted bot: {bot_name}")
        bot_instance.safe_answer_callback(call.id, "✅ Bot deleted")

    else:
        bot_instance.safe_edit(
            chat_id,
            message_id,
            f"❌ Failed to delete bot '{bot_name}'.\nPlease try again or check logs.",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("🔙 Back to Bot", callback_data=f"view_bot:{bot_token}")
            )
        )
        bot_instance.safe_answer_callback(call.id, "❌ Deletion failed", show_alert=True)