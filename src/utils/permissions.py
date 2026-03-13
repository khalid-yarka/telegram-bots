import logging
from src.master_db.operations import check_permission, can_manage_bot, is_super_admin

logger = logging.getLogger(__name__)

def check_user_permission(bot_token, user_id, required_level='user'):
    """
    Check if user has required permission level for a bot

    Args:
        bot_token: Bot token
        user_id: Telegram user ID
        required_level: 'banned', 'user', 'admin', 'owner', 'super_admin'

    Returns:
        bool: True if user has permission
    """
    try:
        # SUPER ADMINS CAN DO ANYTHING
        if is_super_admin(user_id):
            return True

        # Get user's permission for this bot
        user_permission = check_permission(bot_token, user_id)

        if not user_permission:
            return False

        # Define permission hierarchy
        permission_levels = {
            'banned': 0,
            'user': 1,
            'admin': 2,
            'owner': 3,
            'super_admin': 4
        }

        # Check if user's permission meets required level
        user_level = permission_levels.get(user_permission, 0)
        required_level_value = permission_levels.get(required_level, 0)

        return user_level >= required_level_value

    except Exception as e:
        logger.error(f"Permission check error: {str(e)}")
        return False

def can_add_bot(user_id):
    """Check if user can add new bot"""
    try:
        from src.master_db.operations import get_user_bots
        from src.config import config

        # Super admins can always add
        if is_super_admin(user_id):
            return True

        # Check how many bots user already has
        user_bots = get_user_bots(user_id)

        # Count only bots where user is owner
        owned_bots = [bot for bot in user_bots if bot.get('permission') == 'owner']

        return len(owned_bots) < config.MAX_BOTS_PER_USER

    except Exception as e:
        logger.error(f"Error checking add bot permission: {str(e)}")
        return False

def can_delete_bot(bot_token, user_id):
    """Check if user can delete a bot"""
    try:
        from src.master_db.operations import get_bot_by_token

        # Super admins can delete any bot
        if is_super_admin(user_id):
            return True

        # Get bot info
        bot = get_bot_by_token(bot_token)
        if not bot:
            return False

        # Only bot owner can delete
        return bot['owner_id'] == user_id

    except Exception as e:
        logger.error(f"Error checking delete permission: {str(e)}")
        return False

def can_modify_bot_settings(bot_token, user_id):
    """Check if user can modify bot settings"""
    return can_manage_bot(bot_token, user_id)

def can_view_bot_logs(bot_token, user_id):
    """Check if user can view bot logs"""
    return check_user_permission(bot_token, user_id, 'admin')

def can_manage_users(bot_token, user_id):
    """Check if user can manage other users for a bot"""
    return check_user_permission(bot_token, user_id, 'admin')

def get_user_role(bot_token, user_id):
    """Get user's role for a bot"""
    try:
        if is_super_admin(user_id):
            return 'super_admin'

        permission = check_permission(bot_token, user_id)
        return permission or 'no_access'

    except Exception as e:
        logger.error(f"Error getting user role: {str(e)}")
        return 'no_access'

def require_permission(required_level='user'):
    """Decorator to check permission before executing function"""
    def decorator(func):
        def wrapper(bot_token, user_id, *args, **kwargs):
            if check_user_permission(bot_token, user_id, required_level):
                return func(bot_token, user_id, *args, **kwargs)
            else:
                logger.warning(f"User {user_id} lacks {required_level} permission for bot {bot_token[:10]}...")
                return {
                    'success': False,
                    'error': f"Insufficient permissions. Required: {required_level}"
                }
        return wrapper
    return decorator