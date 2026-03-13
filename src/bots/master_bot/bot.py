# src/bots/master_bot/bot.py
"""
Optimized Master Bot for PythonAnywhere
- Lazy loading of modules
- Request timing
- SQLite state management
"""

import telebot
import logging
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Lazy imports (will be loaded when needed)
from src.master_db.operations import (
    add_log_entry,
    get_bot_by_token
)

from src.bots.master_bot.utils import get_state_manager

logger = logging.getLogger(__name__)

# Cache for bot instances (minimal)
_active_bots = {}


class MasterBot:
    """
    Optimized Master Bot with:
    - Request timing
    - Lazy module loading
    - SQLite state management
    """
    
    def __init__(self, bot_token):
        self.bot_token = bot_token
        self.bot = telebot.TeleBot(bot_token, threaded=False)
        self.state_manager = get_state_manager()
        
        # Register handlers (lightweight - just sets up routing)
        self._register_handlers()
    
    def _register_handlers(self):
        """Register message handlers (minimal - just routing)"""
        
        @self.bot.message_handler(commands=['start', 'help', 'menu'])
        def handle_start(message):
            # Lazy import inside handler
            from src.bots.master_bot.handlers import handle_start_command
            handle_start_command(self, message)
        
        @self.bot.message_handler(commands=['mybots', 'bots'])
        def handle_mybots(message):
            from src.bots.master_bot.handlers import handle_mybots
            handle_mybots(self, message)
        
        @self.bot.message_handler(commands=['addbot'])
        def handle_addbot(message):
            from src.bots.master_bot.handlers import handle_addbot_command
            handle_addbot_command(self, message)
        
        @self.bot.message_handler(commands=['webhook'])
        def handle_webhook(message):
            from src.bots.master_bot.handlers import handle_webhook_command
            handle_webhook_command(self, message)
        
        @self.bot.message_handler(commands=['stats'])
        def handle_stats(message):
            from src.bots.master_bot.handlers import handle_stats_command
            handle_stats_command(self, message)
        
        @self.bot.message_handler(func=lambda msg: True)
        def handle_all_messages(message):
            from src.bots.master_bot.handlers import handle_message
            handle_message(self, message)
        
        @self.bot.callback_query_handler(func=lambda call: True)
        def handle_callback(call):
            from src.bots.master_bot.callbacks import process_callback
            process_callback(self, call)
    
    # ==================== SAFE SEND METHODS ====================
    
    def safe_send(self, chat_id, text, reply_markup=None, parse_mode=None):
        """Send message with error handling"""
        try:
            return self.bot.send_message(
                chat_id, text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        except Exception as e:
            logger.error(f"Send failed to {chat_id}: {e}")
            return None
    
    def safe_edit(self, chat_id, message_id, text, reply_markup=None, parse_mode=None):
        """Edit message with error handling"""
        try:
            self.bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
            return True
        except Exception as e:
            logger.debug(f"Edit failed (normal if message unchanged): {e}")
            return False
    
    def safe_answer_callback(self, callback_id, text=None, show_alert=False):
        """Answer callback query with error handling"""
        try:
            self.bot.answer_callback_query(
                callback_id,
                text=text,
                show_alert=show_alert
            )
        except Exception as e:
            logger.debug(f"Answer callback failed: {e}")
    
    def log_action(self, user_id, action, details=None):
        """Log user action (lightweight)"""
        add_log_entry(
            self.bot_token,
            action,
            user_id,
            details
        )
    
    # ==================== PROCESS UPDATE ====================
    
    def process_update(self, update_json):
        """
        Process incoming webhook update with timing
        
        Returns:
            bool: True if processed successfully
        """
        start_time = time.time()
        
        try:
            # Parse update
            update = telebot.types.Update.de_json(update_json)
            
            # Process with telebot
            self.bot.process_new_updates([update])
            
            # Log if slow (over 2 seconds)
            elapsed = time.time() - start_time
            if elapsed > 2:
                logger.warning(f"Slow update processing: {elapsed:.2f}s")
            
            return True
            
        except Exception as e:
            logger.error(f"Update processing error: {e}", exc_info=True)
            
            # Log error
            try:
                add_log_entry(self.bot_token, 'error', None, str(e))
            except:
                pass
            
            return False


# ==================== FACTORY FUNCTION ====================

def get_bot_instance(bot_token):
    """Get or create bot instance (cached)"""
    if bot_token not in _active_bots:
        _active_bots[bot_token] = MasterBot(bot_token)
    
    # Keep cache small (max 5 instances)
    if len(_active_bots) > 5:
        # Remove oldest (simple LRU)
        oldest = next(iter(_active_bots))
        del _active_bots[oldest]
        logger.info(f"Removed oldest bot from cache: {oldest[:10]}...")
    
    return _active_bots[bot_token]


# ==================== WEBHOOK ENTRY POINT ====================

def process_master_update(bot_token, update_json):
    """
    Main entry point for webhook
    Called from app.py
    """
    try:
        bot = get_bot_instance(bot_token)
        return bot.process_update(update_json)
    except Exception as e:
        logger.error(f"Fatal error in process_master_update: {e}")
        return False