# src/bots/ardayda_bot/conflict_manager.py
"""
Updated conflict manager using SQLite state management
- No more in-memory storage
- Persistent across webhooks
- Admin broadcast capabilities
"""

import logging
import time
from telebot.types import Message
from src.bots.ardayda_bot import database, buttons
from src.bots.ardayda_bot.state_manager import (
    get_state_manager,
    get_user_status,
    set_last_message,
    get_last_message,
    clear_temp_data
)

logger = logging.getLogger(__name__)

# Status constants (match database)
STATUS_MENU_HOME = "menu:home"
STATUS_UPLOAD = "upload"
STATUS_SEARCH = "search"
STATUS_REG = "reg"


def check_and_resolve_conflict(bot, user_id, chat_id, new_operation):
    """
    Check if user is in another operation and resolve conflicts
    Uses SQLite state manager for persistence
    
    Returns: (can_proceed, message_to_send)
    """
    # Get current status from state manager (persistent)
    current_status = get_user_status(user_id)
    
    # If no status or at main menu, no conflict
    if not current_status or current_status == STATUS_MENU_HOME:
        return True, None
    
    # Extract operation from status (e.g., "upload:wait_pdf" -> "upload")
    current_op = current_status.split(':')[0] if ':' in current_status else current_status
    
    # Check if trying to start same operation
    if current_op == new_operation:
        # Already in this operation
        return False, f"⚠️ You're already in {new_operation} mode. Please finish or cancel it first."
    
    # Different operation conflict
    conflict_messages = {
        'upload': "📤 You're currently uploading a PDF. Please finish or cancel it first.",
        'search': "🔍 You're currently searching. Please finish or cancel it first.",
        'reg': "📝 Please complete your registration first."
    }
    
    for op, msg in conflict_messages.items():
        if current_op == op:
            return False, msg
    
    # Unknown operation - allow
    return True, None


def clear_previous_operation(bot, user_id, chat_id):
    """
    Clean up previous operation data and messages
    Uses SQLite for persistence
    """
    state_manager = get_state_manager()
    
    # Clear temp data for this user
    clear_temp_data(user_id)
    
    # Try to delete last operation message if exists
    last_msg_id = get_last_message(user_id)
    if last_msg_id:
        try:
            bot.delete_message(chat_id, last_msg_id)
            logger.debug(f"Deleted previous message {last_msg_id} for user {user_id}")
        except Exception as e:
            logger.debug(f"Could not delete message {last_msg_id}: {e}")
        finally:
            # Clear the stored message ID regardless
            state_manager.clear_last_message(user_id)


def save_message_id(user_id, message_id):
    """Save last message ID for cleanup (persistent)"""
    set_last_message(user_id, message_id)
    logger.debug(f"Saved message {message_id} for user {user_id}")


def operation_ended(bot, user_id, chat_id, final_message_id=None):
    """Call this when an operation ends"""
    state_manager = get_state_manager()
    
    # Clear status (back to main menu)
    from src.bots.ardayda_bot.state_manager import clear_user_status
    clear_user_status(user_id)
    
    # Clean up temp data
    clear_temp_data(user_id)
    
    # Delete the last operation message if different from final
    last_msg_id = get_last_message(user_id)
    if last_msg_id and final_message_id and last_msg_id != final_message_id:
        try:
            bot.delete_message(chat_id, last_msg_id)
            logger.debug(f"Deleted operation message {last_msg_id}")
        except:
            pass
    
    # Clear the stored message ID
    state_manager.clear_last_message(user_id)
    
    logger.info(f"Operation ended for user {user_id}")


# ==================== ADMIN BROADCAST FUNCTIONS ====================

def is_admin(user_id):
    """Check if user is admin (uses database)"""
    return database.is_admin(user_id)


def broadcast_to_users(bot, admin_id, message_text, filter_type='all', filter_value=None):
    """
    Send broadcast message to users
    
    Args:
        bot: TeleBot instance
        admin_id: Admin user ID (for logging)
        message_text: Message to send
        filter_type: 'all', 'region', 'school', 'class', 'active', 'inactive'
        filter_value: Value for filter (e.g., region name)
    
    Returns:
        dict: Stats about broadcast
    """
    if not is_admin(admin_id):
        return {'success': False, 'error': 'Admin access required'}
    
    # Get users based on filter
    users = database.get_users_for_broadcast(filter_type, filter_value)
    
    if not users:
        return {'success': False, 'error': 'No users match the filter'}
    
    stats = {
        'total': len(users),
        'sent': 0,
        'failed': 0,
        'blocked': 0
    }
    
    # Send messages (with rate limiting to avoid flood)
    for i, user in enumerate(users):
        user_id = user['user_id']
        
        # Skip every 30th message to avoid rate limits
        if i > 0 and i % 30 == 0:
            time.sleep(1)  # Small delay
        
        try:
            bot.send_message(
                user_id,
                f"📢 *Admin Announcement*\n\n{message_text}",
                parse_mode="Markdown"
            )
            stats['sent'] += 1
            
        except Exception as e:
            error_str = str(e)
            if "blocked" in error_str.lower():
                stats['blocked'] += 1
                logger.info(f"User {user_id} has blocked the bot")
            else:
                stats['failed'] += 1
                logger.error(f"Failed to send to {user_id}: {e}")
    
    # Log admin action and broadcast
    database.log_admin_action(
        admin_id,
        'broadcast',
        'users',
        0,
        f"Filter: {filter_type}, Sent: {stats['sent']}, Total: {stats['total']}"
    )
    
    # Log broadcast to history
    database.log_broadcast(admin_id, filter_type, filter_value, message_text, stats['sent'])
    
    return stats


def send_direct_message(bot, admin_id, target_user_id, message_text):
    """Send direct message to specific user"""
    if not is_admin(admin_id):
        return {'success': False, 'error': 'Admin access required'}
    
    try:
        bot.send_message(
            target_user_id,
            f"📨 *Message from Admin*\n\n{message_text}",
            parse_mode="Markdown"
        )
        
        # Log admin action
        database.log_admin_action(
            admin_id,
            'direct_message',
            'user',
            target_user_id,
            f"Message sent"
        )
        
        return {'success': True, 'message': 'Message sent successfully'}
        
    except Exception as e:
        error_str = str(e)
        if "blocked" in error_str.lower():
            return {'success': False, 'error': 'User has blocked the bot'}
        else:
            logger.error(f"Failed to send direct message: {e}")
            return {'success': False, 'error': str(e)}


def get_user_list_for_admin(admin_id, page=1, per_page=10, filter_type=None):
    """Get paginated list of users for admin panel"""
    if not is_admin(admin_id):
        return {'success': False, 'error': 'Admin access required'}
    
    users, total_pages = database.get_all_users_for_admin(page, per_page, filter_type)
    
    return {
        'success': True,
        'users': users,
        'page': page,
        'total_pages': total_pages,
        'total_users': len(users) if users else 0
    }


def notify_user(bot, user_id, notification_type, message):
    """Send notification to a user (warning, info, etc.)"""
    icons = {
        'warning': '⚠️',
        'info': 'ℹ️',
        'success': '✅',
        'error': '❌'
    }
    
    icon = icons.get(notification_type, '📢')
    
    try:
        bot.send_message(
            user_id,
            f"{icon} *Notification*\n\n{message}",
            parse_mode="Markdown"
        )
        return True
    except Exception as e:
        logger.error(f"Failed to notify user {user_id}: {e}")
        return False


def warn_user(bot, admin_id, user_id, reason):
    """Warn a user"""
    if not is_admin(admin_id):
        return {'success': False, 'error': 'Admin access required'}
    
    # Send warning to user
    warning_message = f"You have received a warning from admin.\n\nReason: {reason}"
    success = notify_user(bot, user_id, 'warning', warning_message)
    
    # Log admin action
    database.log_admin_action(
        admin_id,
        'warn_user',
        'user',
        user_id,
        f"Reason: {reason}"
    )
    
    # Store warning in database
    database.add_warning(user_id, admin_id, reason)
    
    return {
        'success': success,
        'message': 'Warning sent to user' if success else 'Failed to send warning'
    }


# ==================== ADMIN STATISTICS ====================

def get_system_stats(admin_id):
    """Get detailed system statistics for admin"""
    if not is_admin(admin_id):
        return {'success': False, 'error': 'Admin access required'}
    
    from src.bots.ardayda_bot.state_manager import get_state_manager
    
    stats = {
        'users': database.get_user_stats(),
        'pdfs': database.get_pdf_stats(),
        'states': get_state_manager().get_stats(),
        'rate_limits': {}  # Will be filled by rate_limiter
    }
    
    # Add rate limit stats if available
    try:
        from src.bots.ardayda_bot.rate_limiter import get_rate_limiter
        rate_stats = get_rate_limiter().get_usage_stats()
        stats['rate_limits']['total_entries'] = len(rate_stats)
    except:
        pass
    
    return {'success': True, 'stats': stats}