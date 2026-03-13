# src/master_db/operations.py
"""
Optimized database operations for PythonAnywhere
Uses connection decorator to reduce code duplication
"""

import logging
import re
from datetime import datetime
from functools import wraps
from src.master_db.connection import get_db_connection
from src.config import config

logger = logging.getLogger(__name__)

# Regex to validate Telegram bot tokens
TOKEN_REGEX = re.compile(r"^\d+:[A-Za-z0-9_-]{30,}$")


# ==================== CONNECTION DECORATOR ====================

def with_db(func):
    """
    Decorator to handle database connection automatically
    
    Usage:
        @with_db
        def my_function(conn, arg1, arg2):
            # conn is already opened
            cursor = conn.cursor()
            # ... do work
            return result
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        with get_db_connection() as conn:
            # Pass connection as first argument
            return func(conn, *args, **kwargs)
    return wrapper


# ==================== BOT OPERATIONS ====================

@with_db
def bot_exists(conn, bot_token):
    """Check if bot exists in database"""
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT bot_token FROM system_bots WHERE bot_token = ?",
            (bot_token,)
        )
        return cursor.fetchone() is not None
    finally:
        cursor.close()


@with_db
def get_bot_by_token(conn, bot_token):
    """Get bot information by token"""
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM system_bots WHERE bot_token = ?",
            (bot_token,)
        )
        row = cursor.fetchone()
        
        if not row:
            logger.debug(f"Bot not found: {bot_token[:10]}...")
            return None
            
        return dict(row)
    finally:
        cursor.close()


@with_db
def add_bot(conn, bot_token, bot_name, bot_type, owner_id, bot_username=None):
    """Add new bot with token validation"""
    # Validate token format
    if not TOKEN_REGEX.match(bot_token):
        logger.warning(f"Invalid bot token format: {bot_token[:10]}...")
        return False, "Invalid token format"

    # Check if token already exists
    if bot_exists(bot_token):
        logger.warning(f"Bot token already exists: {bot_token[:10]}...")
        return False, "Bot token already registered"

    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO system_bots
            (bot_token, bot_name, bot_username, bot_type, owner_id, created_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            bot_token, bot_name, bot_username, bot_type,
            owner_id, datetime.now(), 1
        ))
        
        logger.info(f"Bot {bot_name} added by owner {owner_id}")
        return True, "Bot added successfully"
    except Exception as e:
        logger.error(f"Error adding bot: {str(e)}")
        return False, f"Database error: {str(e)}"
    finally:
        cursor.close()


@with_db
def get_all_bots(conn, include_inactive=False):
    """Get all bots (optionally including inactive)"""
    cursor = conn.cursor()
    try:
        if include_inactive:
            query = "SELECT * FROM system_bots ORDER BY created_at DESC"
            cursor.execute(query)
        else:
            query = "SELECT * FROM system_bots WHERE is_active = 1 ORDER BY created_at DESC"
            cursor.execute(query)
            
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()


@with_db
def update_bot_activity(conn, bot_token):
    """Update bot's last seen timestamp"""
    if not TOKEN_REGEX.match(bot_token):
        logger.debug(f"Skipping activity update for invalid token")
        return False

    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE system_bots SET last_seen = ? WHERE bot_token = ?",
            (datetime.now(), bot_token)
        )
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error updating activity: {e}")
        return False
    finally:
        cursor.close()


@with_db
def delete_bot(conn, bot_token, requester_id):
    """Delete bot if requester is owner or super admin"""
    # First get bot info to check ownership
    bot = get_bot_by_token(bot_token)
    if not bot:
        return False, "Bot not found"

    # Check permission
    if bot['owner_id'] != requester_id and requester_id not in config.SUPER_ADMINS:
        logger.warning(f"Unauthorized delete attempt by {requester_id}")
        return False, "Permission denied"

    cursor = conn.cursor()
    try:
        # Delete bot (permissions and logs will cascade due to foreign keys)
        cursor.execute(
            "DELETE FROM system_bots WHERE bot_token = ?",
            (bot_token,)
        )
        
        logger.info(f"Bot {bot_token[:10]}... deleted by {requester_id}")
        return True, "Bot deleted successfully"
    except Exception as e:
        logger.error(f"Error deleting bot: {str(e)}")
        return False, f"Delete failed: {str(e)}"
    finally:
        cursor.close()


@with_db
def update_bot_name(conn, bot_token, new_name, user_id):
    """Update bot name (with permission check)"""
    # Check if user has permission
    if not can_manage_bot(bot_token, user_id):
        return False, "Permission denied"
    
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE system_bots SET bot_name = ? WHERE bot_token = ?",
            (new_name, bot_token)
        )
        return cursor.rowcount > 0, "Name updated successfully"
    except Exception as e:
        logger.error(f"Error updating bot name: {e}")
        return False, f"Update failed: {str(e)}"
    finally:
        cursor.close()


@with_db
def toggle_bot_status(conn, bot_token, user_id, active=True):
    """Activate or deactivate a bot"""
    if not can_manage_bot(bot_token, user_id):
        return False, "Permission denied"
    
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE system_bots SET is_active = ? WHERE bot_token = ?",
            (1 if active else 0, bot_token)
        )
        status = "activated" if active else "deactivated"
        return cursor.rowcount > 0, f"Bot {status}"
    except Exception as e:
        logger.error(f"Error toggling bot status: {e}")
        return False, f"Update failed: {str(e)}"
    finally:
        cursor.close()


# ==================== PERMISSION OPERATIONS ====================

@with_db
def check_permission(conn, bot_token, user_id):
    """Check user permission for a bot"""
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT permission_level FROM bot_permissions WHERE bot_token = ? AND user_id = ?",
            (bot_token, user_id)
        )
        row = cursor.fetchone()
        return row['permission_level'] if row else None
    finally:
        cursor.close()


@with_db
def can_manage_bot(conn, bot_token, user_id):
    """Check if user can manage bot (owner/admin/super admin)"""
    # Super admins can manage any bot
    if user_id in config.SUPER_ADMINS:
        return True

    permission = check_permission(bot_token, user_id)
    return permission in ['owner', 'admin']


@with_db
def add_permission(conn, bot_token, user_id, permission='user', granted_by=None, notes=None):
    """Add or update user permission"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO bot_permissions 
            (bot_token, user_id, permission_level, granted_at, granted_by, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            bot_token, user_id, permission, datetime.now(), granted_by, notes
        ))
        return True
    except Exception as e:
        logger.error(f"Error adding permission: {str(e)}")
        return False
    finally:
        cursor.close()


@with_db
def remove_permission(conn, bot_token, user_id):
    """Remove user permission for a bot"""
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM bot_permissions WHERE bot_token = ? AND user_id = ?",
            (bot_token, user_id)
        )
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error removing permission: {str(e)}")
        return False
    finally:
        cursor.close()


# ==================== LOG OPERATIONS ====================

@with_db
def add_log_entry(conn, bot_token, action_type, user_id=None, details=None):
    """Add entry to system logs"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO system_logs (timestamp, bot_token, user_id, action_type, details)
            VALUES (?, ?, ?, ?, ?)
        """, (datetime.now(), bot_token, user_id, action_type, details))
        
        # Also update bot activity (lightweight)
        update_bot_activity(bot_token)
        
        return True
    except Exception as e:
        logger.error(f"Error adding log: {str(e)}")
        return False
    finally:
        cursor.close()


@with_db
def get_recent_logs(conn, bot_token=None, limit=50):
    """Get recent system logs"""
    cursor = conn.cursor()
    try:
        if bot_token:
            cursor.execute("""
                SELECT * FROM system_logs
                WHERE bot_token = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (bot_token, limit))
        else:
            cursor.execute("""
                SELECT * FROM system_logs
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
        
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()


@with_db
def get_logs_count(conn, bot_token=None):
    """Get total number of logs"""
    cursor = conn.cursor()
    try:
        if bot_token:
            cursor.execute(
                "SELECT COUNT(*) as count FROM system_logs WHERE bot_token = ?",
                (bot_token,)
            )
        else:
            cursor.execute("SELECT COUNT(*) as count FROM system_logs")
        
        row = cursor.fetchone()
        return row['count'] if row else 0
    finally:
        cursor.close()


@with_db
def cleanup_old_logs(conn, days=30):
    """Delete logs older than specified days"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            DELETE FROM system_logs
            WHERE timestamp < datetime('now', ?)
        """, (f'-{days} days',))
        
        deleted = cursor.rowcount
        logger.info(f"Cleaned up {deleted} old logs")
        return deleted
    except Exception as e:
        logger.error(f"Error cleaning logs: {e}")
        return 0
    finally:
        cursor.close()


# ==================== USER BOT OPERATIONS ====================

@with_db
def get_user_bots(conn, user_id):
    """Get all bots a user has access to"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT b.*, bp.permission_level as permission
            FROM system_bots b
            JOIN bot_permissions bp ON b.bot_token = bp.bot_token
            WHERE bp.user_id = ? AND b.is_active = 1
            ORDER BY b.created_at DESC
        """, (user_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()


@with_db
def get_bot_users(conn, bot_token):
    """Get all users with access to a bot"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT * FROM bot_permissions
            WHERE bot_token = ?
            ORDER BY 
                CASE permission_level
                    WHEN 'owner' THEN 1
                    WHEN 'admin' THEN 2
                    WHEN 'user' THEN 3
                    WHEN 'banned' THEN 4
                    ELSE 5
                END,
                granted_at DESC
        """, (bot_token,))
        
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()


@with_db
def get_bot_count(conn, user_id=None):
    """Get count of bots (optionally for a specific user)"""
    cursor = conn.cursor()
    try:
        if user_id:
            cursor.execute("""
                SELECT COUNT(*) as count FROM system_bots b
                JOIN bot_permissions bp ON b.bot_token = bp.bot_token
                WHERE bp.user_id = ? AND bp.permission_level = 'owner'
            """, (user_id,))
        else:
            cursor.execute("SELECT COUNT(*) as count FROM system_bots")
        
        row = cursor.fetchone()
        return row['count'] if row else 0
    finally:
        cursor.close()


# ==================== SUPER ADMIN OPERATIONS ====================

def is_super_admin(user_id):
    """Check if user is super admin (no DB needed)"""
    return user_id in config.SUPER_ADMINS


@with_db
def get_system_stats(conn):
    """Get system statistics (for admin panel)"""
    cursor = conn.cursor()
    try:
        stats = {}
        
        # Total bots
        cursor.execute("SELECT COUNT(*) as count FROM system_bots")
        stats['total_bots'] = cursor.fetchone()['count']
        
        # Active bots
        cursor.execute("SELECT COUNT(*) as count FROM system_bots WHERE is_active = 1")
        stats['active_bots'] = cursor.fetchone()['count']
        
        # Bots by type
        cursor.execute("""
            SELECT bot_type, COUNT(*) as count 
            FROM system_bots 
            GROUP BY bot_type
        """)
        stats['bots_by_type'] = dict(cursor.fetchall())
        
        # Total logs
        cursor.execute("SELECT COUNT(*) as count FROM system_logs")
        stats['total_logs'] = cursor.fetchone()['count']
        
        # Logs in last 24h
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM system_logs 
            WHERE timestamp > datetime('now', '-1 day')
        """)
        stats['logs_24h'] = cursor.fetchone()['count']
        
        # Total users with permissions
        cursor.execute("SELECT COUNT(DISTINCT user_id) as count FROM bot_permissions")
        stats['total_users'] = cursor.fetchone()['count']
        
        return stats
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        return {'error': str(e)}
    finally:
        cursor.close()