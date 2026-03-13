# src/bots/master_bot/utils/states_sqlite.py
"""
SQLite-based state management for multi-step flows
Persists across webhook requests - essential for PythonAnywhere
"""

import sqlite3
import json
import time
import logging
from typing import Optional, Dict, Any
from src.config import MASTER_DB_PATH

logger = logging.getLogger(__name__)

class SQLiteStateManager:
    """
    Persistent state management using SQLite
    States survive server restarts and webhook timeouts
    """
    
    def __init__(self, cleanup_hours=24):
        """
        Initialize state manager with automatic cleanup
        
        Args:
            cleanup_hours: Remove states older than this many hours
        """
        self.cleanup_hours = cleanup_hours
        self._init_db()
        self._cleanup_old()  # Clean on startup
    
    def _init_db(self):
        """Create states table if not exists"""
        try:
            with sqlite3.connect(MASTER_DB_PATH, timeout=5) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_states (
                        chat_id INTEGER PRIMARY KEY,
                        state TEXT NOT NULL,
                        data TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Add index for faster cleanup
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_states_updated 
                    ON user_states(updated_at)
                """)
                
                conn.commit()
                logger.debug("State manager database initialized")
        except Exception as e:
            logger.error(f"Failed to init state DB: {e}")
    
    def _cleanup_old(self):
        """Remove states older than cleanup_hours"""
        try:
            with sqlite3.connect(MASTER_DB_PATH, timeout=5) as conn:
                cursor = conn.execute(
                    "DELETE FROM user_states WHERE updated_at < datetime('now', ?)",
                    (f'-{self.cleanup_hours} hours',)
                )
                deleted = cursor.rowcount
                if deleted:
                    logger.info(f"Cleaned up {deleted} expired states")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
    
    def set_state(self, chat_id: int, state: str, data: Dict[str, Any] = None) -> None:
        """
        Set user state and data
        
        Args:
            chat_id: Telegram chat ID
            state: State string (e.g., 'add_bot_token')
            data: Optional dictionary of state data
        """
        try:
            data_json = json.dumps(data or {}, default=str)
            
            with sqlite3.connect(MASTER_DB_PATH, timeout=5) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO user_states 
                    (chat_id, state, data, updated_at) 
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (chat_id, state, data_json))
                
                conn.commit()
                logger.debug(f"State set for {chat_id}: {state}")
        except Exception as e:
            logger.error(f"Failed to set state for {chat_id}: {e}")
    
    def get_state(self, chat_id: int) -> Optional[str]:
        """
        Get current state for user
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            State string or None if not found/expired
        """
        try:
            with sqlite3.connect(MASTER_DB_PATH, timeout=5) as conn:
                cursor = conn.execute(
                    "SELECT state FROM user_states WHERE chat_id = ?",
                    (chat_id,)
                )
                row = cursor.fetchone()
                
                if row:
                    # Update timestamp on access
                    conn.execute(
                        "UPDATE user_states SET updated_at = CURRENT_TIMESTAMP WHERE chat_id = ?",
                        (chat_id,)
                    )
                    return row[0]
                
                return None
        except Exception as e:
            logger.error(f"Failed to get state for {chat_id}: {e}")
            return None
    
    def get_data(self, chat_id: int) -> Dict[str, Any]:
        """
        Get state data for user
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            Dictionary of state data (empty if none)
        """
        try:
            with sqlite3.connect(MASTER_DB_PATH, timeout=5) as conn:
                cursor = conn.execute(
                    "SELECT data FROM user_states WHERE chat_id = ?",
                    (chat_id,)
                )
                row = cursor.fetchone()
                
                if row:
                    # Update timestamp on access
                    conn.execute(
                        "UPDATE user_states SET updated_at = CURRENT_TIMESTAMP WHERE chat_id = ?",
                        (chat_id,)
                    )
                    return json.loads(row[0])
                
                return {}
        except Exception as e:
            logger.error(f"Failed to get data for {chat_id}: {e}")
            return {}
    
    def update_state(self, chat_id: int, data: Dict[str, Any]) -> bool:
        """
        Update state data (merge with existing)
        
        Args:
            chat_id: Telegram chat ID
            data: New data to merge
            
        Returns:
            True if successful, False otherwise
        """
        try:
            current = self.get_data(chat_id)
            current.update(data)
            
            with sqlite3.connect(MASTER_DB_PATH, timeout=5) as conn:
                conn.execute("""
                    UPDATE user_states 
                    SET data = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE chat_id = ?
                """, (json.dumps(current, default=str), chat_id))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to update state for {chat_id}: {e}")
            return False
    
    def clear_state(self, chat_id: int) -> bool:
        """
        Clear user state
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            True if cleared, False if not found
        """
        try:
            with sqlite3.connect(MASTER_DB_PATH, timeout=5) as conn:
                cursor = conn.execute(
                    "DELETE FROM user_states WHERE chat_id = ?",
                    (chat_id,)
                )
                conn.commit()
                
                if cursor.rowcount:
                    logger.debug(f"State cleared for {chat_id}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to clear state for {chat_id}: {e}")
            return False
    
    def clear_all_user_states(self, user_id: int) -> int:
        """
        Clear all states for a user (across multiple chats)
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Number of states cleared
        """
        try:
            # Note: This assumes chat_id contains user_id (often true for private chats)
            # For groups, this might not work perfectly
            with sqlite3.connect(MASTER_DB_PATH, timeout=5) as conn:
                cursor = conn.execute(
                    "DELETE FROM user_states WHERE chat_id = ?",
                    (user_id,)
                )
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Failed to clear user {user_id} states: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get state manager statistics"""
        try:
            with sqlite3.connect(MASTER_DB_PATH, timeout=5) as conn:
                # Total states
                cursor = conn.execute("SELECT COUNT(*) FROM user_states")
                total = cursor.fetchone()[0]
                
                # Oldest state
                cursor = conn.execute(
                    "SELECT MIN(updated_at) FROM user_states"
                )
                oldest = cursor.fetchone()[0]
                
                # States by state type
                cursor = conn.execute("""
                    SELECT state, COUNT(*) 
                    FROM user_states 
                    GROUP BY state 
                    ORDER BY COUNT(*) DESC 
                    LIMIT 5
                """)
                top_states = dict(cursor.fetchall())
                
                return {
                    'total_states': total,
                    'oldest_state': oldest,
                    'top_states': top_states,
                    'cleanup_hours': self.cleanup_hours
                }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {'error': str(e)}


# Singleton instance for global use
_state_manager = None

def get_state_manager():
    """Get or create the global state manager instance"""
    global _state_manager
    if _state_manager is None:
        _state_manager = SQLiteStateManager()
    return _state_manager


# Convenience functions (for backward compatibility)
def set_state(chat_id, state, data=None):
    return get_state_manager().set_state(chat_id, state, data)

def get_state(chat_id):
    return get_state_manager().get_state(chat_id)

def get_data(chat_id):
    return get_state_manager().get_data(chat_id)

def update_state(chat_id, data):
    return get_state_manager().update_state(chat_id, data)

def clear_state(chat_id):
    return get_state_manager().clear_state(chat_id)