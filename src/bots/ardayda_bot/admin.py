# src/bots/ardayda_bot/admin.py
"""
Updated admin module with:
- Rate limit management
- Broadcast functions
- Warning system
- User management enhancements
- Statistics dashboard
"""

from datetime import datetime, timedelta
import logging
from typing import List, Dict, Any, Optional, Tuple

from src.bots.ardayda_bot import database
from src.bots.ardayda_bot.admin_utils import is_admin
from src.bots.ardayda_bot.rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)

# Constants
USERS_PER_PAGE = 5
PDFS_PER_PAGE = 5
LOGS_PER_PAGE = 5


# ==================== Admin Verification ====================

def get_admin_status(user_id: int) -> bool:
    """Alias for is_admin - maintained for backward compatibility"""
    return is_admin(user_id)


def require_admin(func):
    """Decorator to require admin privileges"""
    def wrapper(bot, call, *args, **kwargs):
        user_id = call.from_user.id
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "⛔ Admin access required!")
            return
        return func(bot, call, *args, **kwargs)
    return wrapper


# ==================== Admin Actions Logging ====================

def log_admin_action(admin_id: int, action: str, target_type: str, target_id: int, details: str = ""):
    """Log an admin action"""
    database.log_admin_action(admin_id, action, target_type, target_id, details)
    logger.info(f"Admin log: {admin_id} - {action} - {target_type}:{target_id}")


# ==================== User Management ====================

def get_all_users(page: int = 1, per_page: int = USERS_PER_PAGE) -> Tuple[List[Dict], int]:
    """Get paginated list of all users"""
    try:
        users, total_pages = database.get_all_users_for_admin(page, per_page)
        return users, total_pages
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return [], 1


def get_user_details(user_id: int) -> Optional[Dict]:
    """Get detailed user info including PDF count and warnings"""
    try:
        user = database.get_user(user_id)
        if user:
            # Convert Row to dict if needed
            if not isinstance(user, dict):
                user = dict(user)
            
            user['pdf_count'] = database.get_user_pdfs_count(user_id)
            user['warnings'] = database.get_user_warnings(user_id)
            
            # Get rate limit info
            rate_limiter = get_rate_limiter()
            upload_can, upload_remaining, _ = rate_limiter.can_perform(user_id, 'upload')
            search_can, search_remaining, _ = rate_limiter.can_perform(user_id, 'search')
            
            user['upload_remaining'] = upload_remaining if upload_remaining != float('inf') else 'Unlimited'
            user['search_remaining'] = search_remaining if search_remaining != float('inf') else 'Unlimited'
            
        return user
    except Exception as e:
        logger.error(f"Error getting user details: {e}")
        return None


def get_user_pdfs(user_id: int, page: int = 1, per_page: int = PDFS_PER_PAGE) -> Tuple[List[Dict], int]:
    """Get paginated list of PDFs uploaded by a user"""
    try:
        with database.get_db_connection() as conn:
            # Get total count
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM pdfs WHERE uploader_id = ?",
                (user_id,)
            )
            total = cursor.fetchone()['count']
            total_pages = (total + per_page - 1) // per_page
            
            # Get paginated PDFs
            offset = (page - 1) * per_page
            cursor = conn.execute("""
                SELECT id, file_id, name, subject, created_at, downloads 
                FROM pdfs 
                WHERE uploader_id = ? 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """, (user_id, per_page, offset))
            
            pdfs = [dict(row) for row in cursor.fetchall()]
            
            # Get tags for each PDF
            for pdf in pdfs:
                pdf['tags'] = database.get_pdf_tags(pdf['id'])
            
            return pdfs, total_pages
    except Exception as e:
        logger.error(f"Error getting user PDFs: {e}")
        return [], 1


def suspend_user(admin_id: int, user_id: int) -> bool:
    """Suspend a user"""
    try:
        with database.get_db_connection() as conn:
            conn.execute(
                "UPDATE users SET suspended = 1 WHERE user_id = ?",
                (user_id,)
            )
        
        log_admin_action(admin_id, 'suspend_user', 'user', user_id)
        logger.info(f"User {user_id} suspended by admin {admin_id}")
        return True
    except Exception as e:
        logger.error(f"Error suspending user: {e}")
        return False


def unsuspend_user(admin_id: int, user_id: int) -> bool:
    """Unsuspend a user"""
    try:
        with database.get_db_connection() as conn:
            conn.execute(
                "UPDATE users SET suspended = 0 WHERE user_id = ?",
                (user_id,)
            )
        
        log_admin_action(admin_id, 'unsuspend_user', 'user', user_id)
        logger.info(f"User {user_id} unsuspended by admin {admin_id}")
        return True
    except Exception as e:
        logger.error(f"Error unsuspending user: {e}")
        return False


def make_admin(admin_id: int, user_id: int) -> bool:
    """Make a user admin"""
    try:
        with database.get_db_connection() as conn:
            conn.execute(
                "UPDATE users SET is_admin = 1 WHERE user_id = ?",
                (user_id,)
            )
        
        log_admin_action(admin_id, 'make_admin', 'user', user_id)
        logger.info(f"User {user_id} made admin by {admin_id}")
        return True
    except Exception as e:
        logger.error(f"Error making admin: {e}")
        return False


def remove_admin(admin_id: int, user_id: int) -> bool:
    """Remove admin privileges"""
    try:
        with database.get_db_connection() as conn:
            conn.execute(
                "UPDATE users SET is_admin = 0 WHERE user_id = ?",
                (user_id,)
            )
        
        log_admin_action(admin_id, 'remove_admin', 'user', user_id)
        logger.info(f"Admin privileges removed from {user_id} by {admin_id}")
        return True
    except Exception as e:
        logger.error(f"Error removing admin: {e}")
        return False


def warn_user(admin_id: int, user_id: int, reason: str) -> bool:
    """Issue a warning to a user"""
    try:
        database.add_warning(user_id, admin_id, reason)
        log_admin_action(admin_id, 'warn_user', 'user', user_id, reason)
        logger.info(f"User {user_id} warned by {admin_id}: {reason}")
        return True
    except Exception as e:
        logger.error(f"Error warning user: {e}")
        return False


def get_user_warnings(user_id: int) -> List[Dict]:
    """Get all warnings for a user"""
    return database.get_user_warnings(user_id)


# ==================== Rate Limit Management ====================

def reset_user_upload_limit(admin_id: int, user_id: int) -> bool:
    """Reset upload limits for a user"""
    try:
        rate_limiter = get_rate_limiter()
        success = rate_limiter.reset_user_limits(user_id, 'upload')
        
        if success:
            log_admin_action(admin_id, 'reset_upload_limit', 'user', user_id)
            logger.info(f"Upload limit reset for user {user_id} by admin {admin_id}")
        
        return success
    except Exception as e:
        logger.error(f"Error resetting upload limit: {e}")
        return False


def reset_user_search_limit(admin_id: int, user_id: int) -> bool:
    """Reset search limits for a user"""
    try:
        rate_limiter = get_rate_limiter()
        success = rate_limiter.reset_user_limits(user_id, 'search')
        
        if success:
            log_admin_action(admin_id, 'reset_search_limit', 'user', user_id)
            logger.info(f"Search limit reset for user {user_id} by admin {admin_id}")
        
        return success
    except Exception as e:
        logger.error(f"Error resetting search limit: {e}")
        return False


def get_rate_limit_stats(admin_id: int) -> Dict:
    """Get rate limit statistics"""
    if not is_admin(admin_id):
        return {'error': 'Admin access required'}
    
    try:
        rate_limiter = get_rate_limiter()
        usage_stats = rate_limiter.get_usage_stats()
        
        # Group by action type
        upload_counts = [u for u in usage_stats if u['action_type'] == 'upload']
        search_counts = [u for u in usage_stats if u['action_type'] == 'search']
        
        return {
            'total_tracked_users': len(usage_stats),
            'upload_users': len(upload_counts),
            'search_users': len(search_counts),
            'total_uploads_today': sum(u['count'] for u in upload_counts),
            'total_searches_today': sum(u['count'] for u in search_counts),
            'details': usage_stats[:20]  # First 20 for preview
        }
    except Exception as e:
        logger.error(f"Error getting rate limit stats: {e}")
        return {'error': str(e)}


# ==================== Broadcast Management ====================

def send_broadcast(admin_id: int, filter_type: str, filter_value: str, message: str) -> Dict:
    """Send broadcast message to filtered users"""
    from src.bots.ardayda_bot.conflict_manager import broadcast_to_users
    
    if not is_admin(admin_id):
        return {'success': False, 'error': 'Admin access required'}
    
    # This function will be called from the bot instance
    # The actual sending happens in conflict_manager with bot instance
    return {
        'success': True,
        'filter_type': filter_type,
        'filter_value': filter_value,
        'message': message,
        'admin_id': admin_id
    }


def get_broadcast_history(admin_id: int, limit: int = 20) -> List[Dict]:
    """Get history of broadcasts"""
    if not is_admin(admin_id):
        return []
    
    try:
        with database.get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM ardayda_broadcasts 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting broadcast history: {e}")
        return []


# ==================== PDF Management ====================

def get_all_pdfs(page: int = 1, per_page: int = PDFS_PER_PAGE) -> Tuple[List[Dict], int]:
    """Get paginated list of all PDFs"""
    try:
        with database.get_db_connection() as conn:
            # Get total count
            cursor = conn.execute("SELECT COUNT(*) as count FROM pdfs")
            total = cursor.fetchone()['count']
            total_pages = (total + per_page - 1) // per_page
            
            # Get paginated PDFs
            offset = (page - 1) * per_page
            cursor = conn.execute("""
                SELECT p.*, u.name as uploader_name 
                FROM pdfs p
                LEFT JOIN users u ON p.uploader_id = u.user_id
                ORDER BY p.created_at DESC 
                LIMIT ? OFFSET ?
            """, (per_page, offset))
            
            pdfs = [dict(row) for row in cursor.fetchall()]
            
            # Add tags
            for pdf in pdfs:
                pdf['tags'] = database.get_pdf_tags(pdf['id'])
            
            return pdfs, total_pages
    except Exception as e:
        logger.error(f"Error getting PDFs: {e}")
        return [], 1


def get_pdf_details(pdf_id: int) -> Optional[Dict]:
    """Get detailed PDF info with uploader and tags"""
    try:
        pdf = database.get_pdf_by_id(pdf_id)
        if pdf:
            pdf['tags'] = database.get_pdf_tags(pdf_id)
            uploader = database.get_user(pdf['uploader_id'])
            pdf['uploader_name'] = uploader.get('name') if uploader else 'Unknown'
            pdf['uploader_info'] = uploader
        return pdf
    except Exception as e:
        logger.error(f"Error getting PDF details: {e}")
        return None


def delete_pdf(admin_id: int, pdf_id: int) -> bool:
    """Delete a PDF and its tags"""
    try:
        with database.get_db_connection() as conn:
            # Delete tags first (foreign key should handle this, but just in case)
            conn.execute("DELETE FROM pdf_tags WHERE pdf_id = ?", (pdf_id,))
            
            # Delete PDF
            conn.execute("DELETE FROM pdfs WHERE id = ?", (pdf_id,))
        
        log_admin_action(admin_id, 'delete_pdf', 'pdf', pdf_id)
        logger.info(f"PDF {pdf_id} deleted by admin {admin_id}")
        return True
    except Exception as e:
        logger.error(f"Error deleting PDF: {e}")
        return False


# ==================== Statistics ====================

def get_user_stats() -> Dict:
    """Get user statistics"""
    return database.get_user_stats()


def get_pdf_stats() -> Dict:
    """Get PDF statistics"""
    return database.get_pdf_stats()


def get_system_stats(admin_id: int) -> Dict:
    """Get comprehensive system statistics"""
    if not is_admin(admin_id):
        return {'error': 'Admin access required'}
    
    try:
        stats = database.get_system_stats()
        stats['rate_limits'] = get_rate_limit_stats(admin_id)
        stats['broadcasts'] = len(get_broadcast_history(admin_id, 5))
        
        return stats
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        return {'error': str(e)}


# ==================== Admin Logs ====================

def get_admin_logs(page: int = 1, per_page: int = LOGS_PER_PAGE) -> Tuple[List[Dict], int]:
    """Get paginated admin logs"""
    try:
        with database.get_db_connection() as conn:
            # Get total count
            cursor = conn.execute("SELECT COUNT(*) as count FROM ardayda_admin_logs")
            total = cursor.fetchone()['count']
            total_pages = (total + per_page - 1) // per_page
            
            # Get paginated logs
            offset = (page - 1) * per_page
            cursor = conn.execute("""
                SELECT * FROM ardayda_admin_logs 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """, (per_page, offset))
            
            logs = [dict(row) for row in cursor.fetchall()]
            return logs, total_pages
    except Exception as e:
        logger.error(f"Error getting admin logs: {e}")
        return [], 1


def clear_admin_logs(admin_id: int) -> bool:
    """Clear all admin logs (super admin only)"""
    try:
        with database.get_db_connection() as conn:
            conn.execute("DELETE FROM ardayda_admin_logs")
        
        log_admin_action(admin_id, 'clear_logs', 'system', 0)
        logger.info(f"Admin logs cleared by {admin_id}")
        return True
    except Exception as e:
        logger.error(f"Error clearing logs: {e}")
        return False


# ==================== Search/Filter Functions ====================

def search_users(query: str) -> List[Dict]:
    """Search users by name or ID"""
    try:
        with database.get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM users 
                WHERE name LIKE ? OR CAST(user_id AS TEXT) LIKE ?
                ORDER BY created_at DESC
                LIMIT 20
            """, (f'%{query}%', f'%{query}%'))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error searching users: {e}")
        return []


def search_pdfs_admin(query: str) -> List[Dict]:
    """Search PDFs by name, subject, or uploader"""
    try:
        with database.get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT p.*, u.name as uploader_name
                FROM pdfs p
                LEFT JOIN users u ON p.uploader_id = u.user_id
                WHERE p.name LIKE ? 
                   OR p.subject LIKE ?
                   OR u.name LIKE ?
                ORDER BY p.created_at DESC
                LIMIT 20
            """, (f'%{query}%', f'%{query}%', f'%{query}%'))
            
            pdfs = [dict(row) for row in cursor.fetchall()]
            
            # Add tags
            for pdf in pdfs:
                pdf['tags'] = database.get_pdf_tags(pdf['id'])
            
            return pdfs
    except Exception as e:
        logger.error(f"Error searching PDFs: {e}")
        return []