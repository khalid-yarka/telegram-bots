import logging
from telebot import types

from src.master_db.operations import get_bot_by_token
from src.master_db.connection import get_db_connection
from src.utils.permissions import can_manage_bot, is_super_admin
from src.bots.master_bot.keyboards import get_bot_details_keyboard

logger = logging.getLogger(__name__)

def register_edit_bot_flow(bot_instance):
    """Register handlers for edit bot flow"""

    @bot_instance.bot.message_handler(
        func=lambda msg: bot_instance.state_manager.get_state(msg.chat.id) == 'edit_bot_name'
    )
    def handle_edit_name_input(message):
        process_edit_bot_name(bot_instance, message)

    @bot_instance.bot.callback_query_handler(func=lambda call: call.data.startswith('edit_name:'))
    def handle_edit_name_start(call):
        bot_token = call.data.split(':')[1]
        start_edit_bot_name(bot_instance, call, bot_token)


def start_edit_bot_name(bot_instance, call, bot_token):
    """Start bot name editing flow"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    # Check permission
    if not (is_super_admin(user_id) or can_manage_bot(bot_token, user_id)):
        bot_instance.safe_answer_callback(call.id, "❌ No permission", show_alert=True)
        return

    # Get bot info
    bot_info = get_bot_by_token(bot_token)
    if not bot_info:
        bot_instance.safe_answer_callback(call.id, "❌ Bot not found", show_alert=True)
        return

    current_name = bot_info.get('bot_name', 'Unnamed')

    # Set user state
    bot_instance.state_manager.set_state(chat_id, 'edit_bot_name', {'bot_token': bot_token})

    # Create cancel button
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data=f"view_bot:{bot_token}"))

    bot_instance.safe_edit(
        chat_id,
        message_id,
        f"✏️ **Edit Bot Name**\n\n"
        f"Current name: **{current_name}**\n\n"
        f"Send me the new name for this bot:",
        parse_mode='Markdown',
        reply_markup=markup
    )

    bot_instance.safe_answer_callback(call.id, "Enter new name")


def process_edit_bot_name(bot_instance, message):
    """Process bot name edit"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    new_name = message.text.strip()

    # Get state data
    data = bot_instance.state_manager.get_data(chat_id)

    if not data or 'bot_token' not in data:
        bot_instance.safe_send(
            chat_id,
            "❌ Session expired. Please go back to bot details."
        )
        bot_instance.state_manager.clear_state(chat_id)
        return

    bot_token = data['bot_token']

    # Validate name
    if len(new_name) < 3 or len(new_name) > 100:
        bot_instance.safe_send(
            chat_id,
            "❌ Name must be between 3 and 100 characters. Try again:"
        )
        return

    # Update in database
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE system_bots SET bot_name = %s WHERE bot_token = %s",
                (new_name, bot_token)
            )
            conn.commit()

            bot_instance.safe_send(
                chat_id,
                f"✅ Bot name updated to: **{new_name}**",
                parse_mode='Markdown'
            )

            bot_instance.log_action(user_id, 'edit_bot', f"Renamed bot to {new_name}")

            # Show updated bot details
            fake_call = type('Call', (), {
                'from_user': message.from_user,
                'message': message,
                'id': 'fake'
            })

            # Import here to avoid circular import
            from src.bots.master_bot.callbacks import handle_view_bot
            handle_view_bot(bot_instance, fake_call, bot_token)

        except Exception as e:
            logger.error(f"Error updating bot name: {e}")
            bot_instance.safe_send(chat_id, "❌ Failed to update name")
        finally:
            cursor.close()

    # Clear state
    bot_instance.state_manager.clear_state(chat_id)