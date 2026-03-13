# src/bots/ardayda_bot/rate_limiter.py
"""
SQLite-based rate limiting for Ardayda Bot
- Admins have no limits
- Upload: 100 per day
- Search: 50 per 12 hours
- Tracks usage per user
"""

import sqlite3
import time
import logging
from datetime import datetime, timedelta
from src.config import ARDAYDA_DB_PATH
from src.bots.ardayda_bot import database  # Added missing import

logger = logging.getLogger(__name__)

# Rate limit constants
UPLOAD_LIMIT = 100
UPLOAD_WINDOW = 86400  # 24 hours in seconds

SEARCH_LIMIT = 50
SEARCH_WINDOW = 43200  # 12 hours in seconds

# Admin IDs (can also check from database)
SUPER_ADMINS = [2094426161]  # Add your super admin IDs here


class RateLimiter:
    """SQLite-based rate limiter with admin bypass"""
    
    def __init__(self):
        self._init_db()
    
    def _init_db(self):
        """Create rate limits table if not exists"""
        try:
            with sqlite3.connect(ARDAYDA_DB_PATH, timeout=5) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS ardayda_rate_limits (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        action_type TEXT NOT NULL,  -- 'upload' or 'search'
                        count INTEGER DEFAULT 0,
                        window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, action_type)
                    )
                """)
                
                # Index for faster lookups
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_rate_limits_user 
                    ON ardayda_rate_limits(user_id, action_type)
                """)
                
                conn.commit()
                logger.debug("Rate limiter database initialized")
        except Exception as e:
            logger.error(f"Failed to init rate limiter DB: {e}")
    
    def is_admin(self, user_id):
        """Check if user is admin (bypasses limits)"""
        # Check super admins first
        if user_id in SUPER_ADMINS:
            return True
        
        # Check database for admin status
        try:
            user = database.get_user(user_id)
            return user and user.get('is_admin', 0) == 1
        except Exception as e:
            logger.error(f"Error checking admin status: {e}")
            return False
    
    def can_perform(self, user_id, action_type):
        """
        Check if user can perform action
        
        Args:
            user_id: Telegram user ID
            action_type: 'upload' or 'search'
        
        Returns:
            (can_perform: bool, remaining: int, message: str)
        """
        # Admins have no limits
        if self.is_admin(user_id):
            return True, float('inf'), "Admin access - no limits"
        
        # Get limits for action
        if action_type == 'upload':
            limit = UPLOAD_LIMIT
            window = UPLOAD_WINDOW
            action_name = "uploads"
        elif action_type == 'search':
            limit = SEARCH_LIMIT
            window = SEARCH_WINDOW
            action_name = "searches"
        else:
            return False, 0, f"Unknown action: {action_type}"
        
        try:
            with sqlite3.connect(ARDAYDA_DB_PATH, timeout=5) as conn:
                # Get current record
                cursor = conn.execute("""
                    SELECT count, window_start 
                    FROM ardayda_rate_limits 
                    WHERE user_id = ? AND action_type = ?
                """, (user_id, action_type))
                
                row = cursor.fetchone()
                
                if not row:
                    # No record - first time
                    return True, limit, f"You have {limit} {action_name} remaining today"
                
                count = row[0]
                window_start_str = row[1]
                
                # Parse timestamp
                try:
                    window_start = datetime.fromisoformat(window_start_str)
                except:
                    window_start = datetime.now() - timedelta(days=1)
                
                # Check if window has expired
                window_age = datetime.now() - window_start
                if window_age.total_seconds() > window:
                    # Reset window
                    conn.execute("""
                        UPDATE ardayda_rate_limits 
                        SET count = 0, window_start = CURRENT_TIMESTAMP
                        WHERE user_id = ? AND action_type = ?
                    """, (user_id, action_type))
                    conn.commit()
                    return True, limit, f"New window started. You have {limit} {action_name} remaining"
                
                # Check if under limit
                if count < limit:
                    remaining = limit - count
                    return True, remaining, f"You have {remaining} {action_name} remaining"
                else:
                    # Calculate when window resets
                    reset_time = window_start + timedelta(seconds=window)
                    hours_left = (reset_time - datetime.now()).total_seconds() / 3600
                    return False, 0, f"Limit reached. Try again in {hours_left:.1f} hours"
                    
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            # Fail open (allow) to prevent blocking users due to errors
            return True, limit, "Rate limit check failed - allowed temporarily"
    
    def increment_count(self, user_id, action_type):
        """
        Increment usage count for user
        
        Args:
            user_id: Telegram user ID
            action_type: 'upload' or 'search'
        
        Returns:
            bool: Success or failure
        """
        # Don't count for admins
        if self.is_admin(user_id):
            return True
        
        try:
            with sqlite3.connect(ARDAYDA_DB_PATH, timeout=5) as conn:
                # Check if record exists
                cursor = conn.execute("""
                    SELECT id FROM ardayda_rate_limits 
                    WHERE user_id = ? AND action_type = ?
                """, (user_id, action_type))
                
                if cursor.fetchone():
                    # Update existing
                    conn.execute("""
                        UPDATE ardayda_rate_limits 
                        SET count = count + 1 
                        WHERE user_id = ? AND action_type = ?
                    """, (user_id, action_type))
                else:
                    # Insert new
                    conn.execute("""
                        INSERT INTO ardayda_rate_limits (user_id, action_type, count)
                        VALUES (?, ?, 1)
                    """, (user_id, action_type))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error incrementing rate limit: {e}")
            return False
    
    def get_usage_stats(self, user_id=None):
        """Get usage statistics (for admin panel)"""
        try:
            with sqlite3.connect(ARDAYDA_DB_PATH, timeout=5) as conn:
                if user_id:
                    # Get specific user
                    cursor = conn.execute("""
                        SELECT user_id, action_type, count, window_start
                        FROM ardayda_rate_limits
                        WHERE user_id = ?
                        ORDER BY action_type
                    """, (user_id,))
                else:
                    # Get all users (admin only)
                    cursor = conn.execute("""
                        SELECT user_id, action_type, count, window_start
                        FROM ardayda_rate_limits
                        ORDER BY user_id, action_type
                        LIMIT 100
                    """)
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        'user_id': row[0],
                        'action_type': row[1],
                        'count': row[2],
                        'window_start': row[3]
                    })
                
                return results
        except Exception as e:
            logger.error(f"Error getting usage stats: {e}")
            return []
    
    def reset_user_limits(self, user_id, action_type=None):
        """Reset limits for a user (admin only)"""
        try:
            with sqlite3.connect(ARDAYDA_DB_PATH, timeout=5) as conn:
                if action_type:
                    conn.execute("""
                        DELETE FROM ardayda_rate_limits
                        WHERE user_id = ? AND action_type = ?
                    """, (user_id, action_type))
                else:
                    conn.execute("""
                        DELETE FROM ardayda_rate_limits
                        WHERE user_id = ?
                    """, (user_id,))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error resetting limits: {e}")
            return False


# Singleton instance
_rate_limiter = None

def get_rate_limiter():
    """Get or create global rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


# Convenience functions
def can_upload(user_id):
    """Check if user can upload"""
    return get_rate_limiter().can_perform(user_id, 'upload')

def can_search(user_id):
    """Check if user can search"""
    return get_rate_limiter().can_perform(user_id, 'search')

def increment_upload(user_id):
    """Increment upload count"""
    return get_rate_limiter().increment_count(user_id, 'upload')

def increment_search(user_id):
    """Increment search count"""
    return get_rate_limiter().increment_count(user_id, 'search')