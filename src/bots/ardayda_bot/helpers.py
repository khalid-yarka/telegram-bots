# bots/ardayda_bot/helpers.py (create this file)

import logging
from telebot.types import Message

logger = logging.getLogger(__name__)

def safe_edit_message(bot, chat_id, message_id, text, reply_markup=None, parse_mode=None):
    """
    Safely edit a message, falling back to sending a new one if edit fails
    """
    try:
        return bot.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    except Exception as e:
        logger.warning(f"Edit failed, sending new message: {e}")
        return bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )