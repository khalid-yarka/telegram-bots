# src/bots/ardayda_bot/bot.py
"""
Updated Ardayda Bot with:
- SQLite state management
- Rate limiting
- Admin broadcast capabilities
- Request timing
- Lazy loading
"""

import telebot
import logging
import time
from telebot.types import Update, Message, CallbackQuery

# Local imports
from src.bots.ardayda_bot import (
    database,
    handlers,
    registration,
    upload_flow,
    search_flow,
    profile
)

# Initialize database on module load
database.init_database()

logger = logging.getLogger(__name__)

# Cache for bot instances (minimal)
_active_bots = {}


class ArdaydaBot:
    """
    Optimized Ardayda Bot with:
    - Request timing
    - Lazy module loading
    - SQLite state management
    - Rate limiting
    """
    
    def __init__(self, token: str):
        self.bot_token = token
        self.bot = telebot.TeleBot(token, threaded=False)
        self._register_handlers()
        logger.info(f"Ardayda bot initialized with token: {token[:10]}...")
    
    def _register_handlers(self):
        """Register message handlers (lightweight routing)"""
        
        # ==================== MESSAGE HANDLERS ====================
        
        @self.bot.message_handler(
            func=lambda m: not database.user_exists(m.from_user.id),
            content_types=["text", "document"]
        )
        def first_message_handler(message: Message):
            """New user - start registration"""
            start_time = time.time()
            try:
                handlers.handle_first_message(self.bot, message)
                
                elapsed = time.time() - start_time
                if elapsed > 1:
                    logger.warning(f"Slow first message handling: {elapsed:.2f}s")
            except Exception as e:
                logger.error(f"Error in first message handler: {e}", exc_info=True)
                self._safe_reply(message, "❌ An error occurred. Please try again.")

        @self.bot.message_handler(content_types=["text"])
        def text_message_handler(message: Message):
            """Handle all text messages"""
            start_time = time.time()
            try:
                handlers.handle_message(self.bot, message)
                
                elapsed = time.time() - start_time
                if elapsed > 1:
                    logger.warning(f"Slow text message handling: {elapsed:.2f}s for user {message.from_user.id}")
            except Exception as e:
                logger.error(f"Error in text handler: {e}", exc_info=True)
                self._safe_reply(message, "❌ An error occurred. Please try again.")

        @self.bot.message_handler(content_types=["document"])
        def document_handler(message: Message):
            """Handle document (PDF) uploads"""
            start_time = time.time()
            try:
                handlers.handle_document(self.bot, message)
                
                elapsed = time.time() - start_time
                if elapsed > 2:  # PDF processing can take longer
                    logger.warning(f"Slow document handling: {elapsed:.2f}s for user {message.from_user.id}")
            except Exception as e:
                logger.error(f"Error in document handler: {e}", exc_info=True)
                self._safe_reply(message, "❌ Error processing PDF. Please try again.")

        # ==================== CALLBACK HANDLERS ====================
        
        @self.bot.callback_query_handler(func=lambda call: True)
        def callback_handler(call: CallbackQuery):
            """Handle all callback queries"""
            start_time = time.time()
            try:
                handlers.handle_callback(self.bot, call)
                
                elapsed = time.time() - start_time
                if elapsed > 1:
                    logger.warning(f"Slow callback handling: {elapsed:.2f}s for user {call.from_user.id}")
            except Exception as e:
                logger.error(f"Error in callback handler: {e}", exc_info=True)
                try:
                    self.bot.answer_callback_query(
                        call.id,
                        "❌ An error occurred",
                        show_alert=True
                    )
                except:
                    pass
    
    # ==================== SAFE SEND METHODS ====================
    
    def _safe_reply(self, message: Message, text: str, reply_markup=None, parse_mode=None):
        """Safely reply to a message"""
        try:
            return self.bot.send_message(
                message.chat.id,
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return None
    
    def _safe_edit(self, chat_id, message_id, text, reply_markup=None, parse_mode=None):
        """Safely edit a message"""
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
            logger.debug(f"Edit failed (normal if unchanged): {e}")
            return False
    
    def _safe_answer_callback(self, callback_id, text=None, show_alert=False):
        """Safely answer a callback query"""
        try:
            self.bot.answer_callback_query(callback_id, text=text, show_alert=show_alert)
        except Exception as e:
            logger.debug(f"Answer callback failed: {e}")
    
    # ==================== ADMIN BROADCAST METHODS ====================
    
    def broadcast_to_users(self, admin_id, filter_type, filter_value, message_text):
        """Send broadcast message to filtered users"""
        from src.bots.ardayda_bot.conflict_manager import broadcast_to_users
        
        start_time = time.time()
        try:
            result = broadcast_to_users(self.bot, admin_id, message_text, filter_type, filter_value)
            
            elapsed = time.time() - start_time
            logger.info(f"Broadcast completed in {elapsed:.2f}s: {result}")
            
            return result
        except Exception as e:
            logger.error(f"Broadcast error: {e}")
            return {'success': False, 'error': str(e)}
    
    def send_direct_message(self, admin_id, target_user_id, message_text):
        """Send direct message to a specific user"""
        from src.bots.ardayda_bot.conflict_manager import send_direct_message
        
        try:
            return send_direct_message(self.bot, admin_id, target_user_id, message_text)
        except Exception as e:
            logger.error(f"Direct message error: {e}")
            return {'success': False, 'error': str(e)}
    
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
            update = Update.de_json(update_json)
            
            # Process with telebot
            self.bot.process_new_updates([update])
            
            # Log if slow
            elapsed = time.time() - start_time
            if elapsed > 2:
                logger.warning(f"Slow update processing: {elapsed:.2f}s")
            
            return True
            
        except Exception as e:
            logger.error(f"Update processing error: {e}", exc_info=True)
            
            # Try to log error
            try:
                if update_json and 'message' in update_json:
                    user_id = update_json['message']['from']['id']
                    database.log_admin_action(0, 'bot_error', 'user', user_id, str(e))
            except:
                pass
            
            return False
    
    # ==================== STATISTICS ====================
    
    def get_bot_stats(self):
        """Get bot statistics"""
        return {
            'type': 'ardayda',
            'token_preview': self.bot_token[:10] + '...',
            'handlers': len(self.bot.message_handlers) + len(self.bot.callback_query_handlers)
        }


# ==================== FACTORY FUNCTION ====================

def get_bot_instance(bot_token):
    """Get or create bot instance (cached)"""
    if bot_token not in _active_bots:
        _active_bots[bot_token] = ArdaydaBot(bot_token)
        logger.info(f"Created new Ardayda bot instance for {bot_token[:10]}...")
    
    # Keep cache small (max 3 instances)
    if len(_active_bots) > 3:
        # Remove oldest
        oldest = next(iter(_active_bots))
        del _active_bots[oldest]
        logger.info(f"Removed oldest bot from cache: {oldest[:10]}...")
    
    return _active_bots[bot_token]


# ==================== WEBHOOK ENTRY POINT ====================

def process_ardayda_update(bot_token, update_json):
    """
    Main entry point for webhook
    Called from app.py
    """
    try:
        bot = get_bot_instance(bot_token)
        return bot.process_update(update_json)
    except Exception as e:
        logger.error(f"Fatal error in process_ardayda_update: {e}", exc_info=True)
        return False


# ==================== ADMIN COMMANDS (for external use) ====================

def broadcast(admin_token, admin_id, filter_type, filter_value, message):
    """External broadcast function (can be called from master bot)"""
    try:
        bot = get_bot_instance(admin_token)
        return bot.broadcast_to_users(admin_id, filter_type, filter_value, message)
    except Exception as e:
        logger.error(f"External broadcast error: {e}")
        return {'success': False, 'error': str(e)}


def send_message(admin_token, admin_id, target_user_id, message):
    """External direct message function"""
    try:
        bot = get_bot_instance(admin_token)
        return bot.send_direct_message(admin_id, target_user_id, message)
    except Exception as e:
        logger.error(f"External DM error: {e}")
        return {'success': False, 'error': str(e)}