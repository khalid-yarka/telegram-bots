import logging
import re
from telebot import types

from src.master_db.operations import add_bot, get_bot_by_token
from src.utils.webhook_manager import set_webhook
from src.utils.permissions import can_add_bot

logger = logging.getLogger(__name__)

# Token validation regex
TOKEN_REGEX = re.compile(r'^\d+:[A-Za-z0-9_-]{30,}$')

def register_add_bot_flow(bot_instance):
    """Register handlers for add bot flow"""

    @bot_instance.bot.message_handler(
        func=lambda msg: bot_instance.state_manager.get_state(msg.chat.id) == 'add_bot_token'
    )
    def handle_token_input(message):
        process_token_input(bot_instance, message)

    @bot_instance.bot.message_handler(
        func=lambda msg: bot_instance.state_manager.get_state(msg.chat.id) == 'add_bot_name'
    )
    def handle_name_input(message):
        process_name_input(bot_instance, message)

    # NEW: Handler for any message during add_bot_type state
    @bot_instance.bot.message_handler(
        func=lambda msg: bot_instance.state_manager.get_state(msg.chat.id) == 'add_bot_type'
    )
    def handle_type_state_message(message):
        """Handle messages when waiting for bot type selection"""
        chat_id = message.chat.id
        
        bot_instance.safe_send(
            chat_id,
            "⚠️ Please select a bot type using the buttons above.\n"
            "Click one of: Master, Ardayda, or Dhalinyaro"
        )


def start_add_bot_flow(bot_instance, message):
    """Start the add bot flow"""
    user_id = message.from_user.id
    chat_id = message.chat.id

    # Check if user can add more bots
    if not can_add_bot(user_id):
        bot_instance.safe_send(
            chat_id,
            "❌ You've reached the maximum number of bots allowed."
        )
        return

    # Clear any existing state
    bot_instance.state_manager.clear_state(chat_id)
    
    # Set state
    bot_instance.state_manager.set_state(chat_id, 'add_bot_token', {})

    # Create cancel button
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="add_bot_cancel"))

    bot_instance.safe_send(
        chat_id,
        "🔑 **Add New Bot - Step 1/3**\n\n"
        "Please send me your bot's token from @BotFather.\n"
        "Format: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`\n\n"
        "Example: `7234567890:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw`",
        parse_mode='Markdown',
        reply_markup=markup
    )

    bot_instance.log_action(user_id, 'start_add_bot')


def process_token_input(bot_instance, message):
    """Process bot token input"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    token = message.text.strip()

    # Validate token format
    if not TOKEN_REGEX.match(token):
        bot_instance.safe_send(
            chat_id,
            "❌ Invalid token format. Please check and try again.\n"
            "Format: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`",
            parse_mode='Markdown'
        )
        return

    # Check if token already exists
    if get_bot_by_token(token):
        bot_instance.safe_send(
            chat_id,
            "❌ This bot token is already registered in the system."
        )
        return

    # Store token in state
    bot_instance.state_manager.update_state(chat_id, {'bot_token': token})
    bot_instance.state_manager.set_state(chat_id, 'add_bot_type', None)

    # Show bot type selection
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🤖 Master", callback_data="add_bot_type:master"),
        types.InlineKeyboardButton("📚 Ardayda", callback_data="add_bot_type:ardayda"),
        types.InlineKeyboardButton("👥 Dhalinyaro", callback_data="add_bot_type:dhalinyaro"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="add_bot_cancel")
    )

    bot_instance.safe_send(
        chat_id,
        "✅ Token validated!\n\n"
        "**Step 2/3 - Select Bot Type:**\n"
        "Choose the type of bot you're adding:",
        parse_mode='Markdown',
        reply_markup=markup
    )


def handle_add_bot_type(bot_instance, call, bot_type):
    """Handle bot type selection from inline button"""
    chat_id = call.message.chat.id
    user_id = call.from_user.id

    # Get state
    current_state = bot_instance.state_manager.get_state(chat_id)
    
    # Check if we're in the correct state
    if current_state != 'add_bot_type':
        bot_instance.safe_answer_callback(
            call.id, 
            "Session expired. Please start over with /addbot",
            show_alert=True
        )
        bot_instance.state_manager.clear_state(chat_id)
        return

    # Get data from state
    data = bot_instance.state_manager.get_data(chat_id)
    if not data or 'bot_token' not in data:
        bot_instance.safe_answer_callback(call.id, "Session expired. Start over.", show_alert=True)
        bot_instance.state_manager.clear_state(chat_id)
        return

    # Add bot type to data
    data['bot_type'] = bot_type

    # Update state
    bot_instance.state_manager.set_state(chat_id, 'add_bot_name', data)

    # Type display names
    type_names = {
        'master': '🤖 Master Controller',
        'ardayda': '📚 Ardayda Student',
        'dhalinyaro': '👥 Dhalinyaro Youth'
    }

    # Create cancel button
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="add_bot_cancel"))

    # Edit the message
    bot_instance.safe_edit(
        chat_id,
        call.message.message_id,
        f"✅ Type selected: {type_names.get(bot_type, bot_type)}\n\n"
        f"**Step 3/3 - Enter Bot Name:**\n"
        f"Send me a friendly name for this bot:",
        parse_mode='Markdown',
        reply_markup=markup
    )

    bot_instance.safe_answer_callback(call.id, f"Selected {bot_type}")


def process_name_input(bot_instance, message):
    """Process bot name input and complete addition"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    bot_name = message.text.strip()

    # Get state data
    current_state = bot_instance.state_manager.get_state(chat_id)
    data = bot_instance.state_manager.get_data(chat_id)

    # Validate state
    if current_state != 'add_bot_name' or not data:
        bot_instance.safe_send(
            chat_id,
            "❌ Session expired. Please start over with /addbot"
        )
        bot_instance.state_manager.clear_state(chat_id)
        return

    if 'bot_token' not in data or 'bot_type' not in data:
        bot_instance.safe_send(
            chat_id,
            "❌ Missing information. Please start over with /addbot"
        )
        bot_instance.state_manager.clear_state(chat_id)
        return

    # Validate name
    if len(bot_name) < 3 or len(bot_name) > 100:
        bot_instance.safe_send(
            chat_id,
            "❌ Name must be between 3 and 100 characters. Try again:"
        )
        return

    bot_token = data['bot_token']
    bot_type = data['bot_type']

    # Add bot to database
    success = add_bot(bot_token, bot_name, bot_type, user_id)

    if success:
        # Setup webhook
        webhook_success = set_webhook(bot_token, bot_type)

        # Success message
        text = f"✅ **Bot Added Successfully!**\n\n"
        text += f"Name: {bot_name}\n"
        text += f"Type: {bot_type}\n"
        text += f"Token: `{bot_token[:10]}...{bot_token[-5:]}`\n\n"

        if webhook_success:
            text += "🌐 Webhook configured automatically!"
        else:
            text += "⚠️ Webhook setup failed. You can configure it manually."

        # Create action buttons
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📋 View Bot", callback_data=f"view_bot:{bot_token}"),
            types.InlineKeyboardButton("🌐 Check Webhook", callback_data=f"webhook:{bot_token}")
        )
        markup.add(
            types.InlineKeyboardButton("📊 All Bots", callback_data="back_to_bots"),
            types.InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_menu")
        )

        bot_instance.safe_send(
            chat_id,
            text,
            parse_mode='Markdown',
            reply_markup=markup
        )

        bot_instance.log_action(user_id, 'add_bot', f"Added {bot_type} bot: {bot_name}")
    else:
        bot_instance.safe_send(
            chat_id,
            "❌ Failed to add bot. Please check the token and try again."
        )

    # Clear state
    bot_instance.state_manager.clear_state(chat_id)