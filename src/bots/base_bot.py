import logging
from abc import ABC, abstractmethod
import telebot

logger = logging.getLogger(__name__)

class BaseBot(ABC):
    """Base class for all Telegram bots"""

    def __init__(self, bot_token, bot_type):
        self.bot_token = bot_token
        self.bot_type = bot_type
        self.bot = telebot.TeleBot(bot_token, threaded=False)
        self.logger = logging.getLogger(f"bot.{bot_type}")

    @abstractmethod
    def process_update(self, update):
        """Process incoming update"""
        pass

    @abstractmethod
    def register_handlers(self):
        """Register command handlers"""
        pass

    def send_message(self, chat_id, text, **kwargs):
        """Send message with error handling"""
        try:
            return self.bot.send_message(chat_id, text, **kwargs)
        except Exception as e:
            self.logger.error(f"Failed to send message: {str(e)}")
            return None

    def reply_to(self, message, text, **kwargs):
        """Reply to a message"""
        try:
            return self.bot.reply_to(message, text, **kwargs)
        except Exception as e:
            self.logger.error(f"Failed to reply: {str(e)}")
            return None

    def log_command(self, user_id, command, success=True):
        """Log command execution"""
        status = "✅" if success else "❌"
        self.logger.info(f"{status} User: {user_id}, Command: {command}")

    def get_user_info(self, message):
        """Extract user info from message"""
        user = message.from_user
        return {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name
        }