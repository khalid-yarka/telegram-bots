# src/bots/ardayda_bot/state_manager.py
"""
SQLite-based state management for Ardayda Bot flows
- Persistent across webhook requests
- Tracks user status (registration, upload, search)
- Stores temporary flow data
- Auto-cleanup of old states
"""

import sqlite3
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from src.config import ARDAYDA_DB_PATH

logger = logging.getLogger(__name__)

# Status constants (match existing database.STATUS_* values)
STATUS_MENU_HOME = "menu:home"
STATUS_REG_NAME = "reg:name"
STATUS_REG_REGION = "reg:region"
STATUS_REG_SCHOOL = "reg:school"
STATUS_REG_CLASS = "reg:class"
STATUS_UPLOAD_WAIT_PDF = "upload:wait_pdf"
STATUS_UPLOAD_SUBJECT = "upload:subject"
STATUS_UPLOAD_TAGS = "upload:tags"
STATUS_SEARCH_SUBJECT = "search:subject"
STATUS_SEARCH_TAGS = "search:tags"


class ArdaydaStateManager:
    """
    Persistent state management using SQLite
    Replaces in-memory states in conflict_manager and registration
    """
    
    def __init__(self, cleanup_hours=24):
        """
        Initialize state manager
        
        Args:
            cleanup_hours: Remove states older than this many hours
        """
        self.cleanup_hours = cleanup_hours
        self._init_db()
        self._cleanup_old()
    
    def _init_db(self):
        """Create states table if not exists"""
        try:
            with sqlite3.connect(ARDAYDA_DB_PATH, timeout=5) as conn:
                # Main user states table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS ardayda_user_states (
                        user_id INTEGER PRIMARY KEY,
                        status TEXT NOT NULL,
                        flow_data TEXT NOT NULL,  -- JSON data for current flow
                        temp_data TEXT,            -- Temporary data (upload/search)
                        page INTEGER DEFAULT 0,    -- For pagination
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Flow data table (for multi-step flows)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS ardayda_flow_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        flow_type TEXT NOT NULL,  -- 'upload', 'search', 'registration'
                        data_key TEXT NOT NULL,
                        data_value TEXT,
                        expires_at TIMESTAMP,
                        UNIQUE(user_id, flow_type, data_key)
                    )
                """)
                
                # Indexes
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_ardayda_states_updated 
                    ON ardayda_user_states(updated_at)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_ardayda_flow_expires 
                    ON ardayda_flow_data(expires_at)
                """)
                
                conn.commit()
                logger.debug("Ardayda state manager database initialized")
        except Exception as e:
            logger.error(f"Failed to init state DB: {e}")
    
    def _cleanup_old(self):
        """Remove states older than cleanup_hours"""
        try:
            with sqlite3.connect(ARDAYDA_DB_PATH, timeout=5) as conn:
                # Clean old user states
                cursor = conn.execute("""
                    DELETE FROM ardayda_user_states 
                    WHERE updated_at < datetime('now', ?)
                """, (f'-{self.cleanup_hours} hours',))
                
                user_states_cleaned = cursor.rowcount
                
                # Clean expired flow data
                cursor = conn.execute("""
                    DELETE FROM ardayda_flow_data 
                    WHERE expires_at < datetime('now')
                """)
                
                flow_data_cleaned = cursor.rowcount
                
                if user_states_cleaned or flow_data_cleaned:
                    logger.info(f"Cleaned up {user_states_cleaned} states, {flow_data_cleaned} flow data")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
    
    # ==================== USER STATUS ====================
    
    def set_status(self, user_id: int, status: str, flow_data: Dict = None):
        """Set user status and optional flow data"""
        try:
            flow_json = json.dumps(flow_data or {}, default=str)
            
            with sqlite3.connect(ARDAYDA_DB_PATH, timeout=5) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO ardayda_user_states 
                    (user_id, status, flow_data, updated_at) 
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (user_id, status, flow_json))
                
                conn.commit()
                logger.debug(f"Status set for user {user_id}: {status}")
        except Exception as e:
            logger.error(f"Failed to set status for {user_id}: {e}")
    
    def get_status(self, user_id: int) -> Optional[str]:
        """Get user's current status"""
        try:
            with sqlite3.connect(ARDAYDA_DB_PATH, timeout=5) as conn:
                cursor = conn.execute("""
                    SELECT status FROM ardayda_user_states 
                    WHERE user_id = ?
                """, (user_id,))
                
                row = cursor.fetchone()
                
                if row:
                    # Update timestamp on access
                    conn.execute("""
                        UPDATE ardayda_user_states 
                        SET updated_at = CURRENT_TIMESTAMP 
                        WHERE user_id = ?
                    """, (user_id,))
                    
                    return row[0]
                
                return None
        except Exception as e:
            logger.error(f"Failed to get status for {user_id}: {e}")
            return None
    
    def get_flow_data(self, user_id: int) -> Dict:
        """Get flow data for user"""
        try:
            with sqlite3.connect(ARDAYDA_DB_PATH, timeout=5) as conn:
                cursor = conn.execute("""
                    SELECT flow_data FROM ardayda_user_states 
                    WHERE user_id = ?
                """, (user_id,))
                
                row = cursor.fetchone()
                
                if row and row[0]:
                    return json.loads(row[0])
                
                return {}
        except Exception as e:
            logger.error(f"Failed to get flow data for {user_id}: {e}")
            return {}
    
    def update_flow_data(self, user_id: int, data: Dict) -> bool:
        """Update flow data (merge with existing)"""
        try:
            current = self.get_flow_data(user_id)
            current.update(data)
            
            with sqlite3.connect(ARDAYDA_DB_PATH, timeout=5) as conn:
                conn.execute("""
                    UPDATE ardayda_user_states 
                    SET flow_data = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE user_id = ?
                """, (json.dumps(current, default=str), user_id))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to update flow data for {user_id}: {e}")
            return False
    
    def clear_status(self, user_id: int) -> bool:
        """Clear user status (back to menu)"""
        try:
            with sqlite3.connect(ARDAYDA_DB_PATH, timeout=5) as conn:
                cursor = conn.execute("""
                    DELETE FROM ardayda_user_states 
                    WHERE user_id = ?
                """, (user_id,))
                
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to clear status for {user_id}: {e}")
            return False
    
    # ==================== PAGINATION (for registration) ====================
    
    def set_page(self, user_id: int, page: int):
        """Set current pagination page"""
        try:
            with sqlite3.connect(ARDAYDA_DB_PATH, timeout=5) as conn:
                # Check if user exists
                cursor = conn.execute("""
                    SELECT 1 FROM ardayda_user_states WHERE user_id = ?
                """, (user_id,))
                
                if cursor.fetchone():
                    conn.execute("""
                        UPDATE ardayda_user_states 
                        SET page = ?, updated_at = CURRENT_TIMESTAMP 
                        WHERE user_id = ?
                    """, (page, user_id))
                else:
                    # Create with default status
                    conn.execute("""
                        INSERT INTO ardayda_user_states 
                        (user_id, status, flow_data, page) 
                        VALUES (?, ?, ?, ?)
                    """, (user_id, STATUS_MENU_HOME, '{}', page))
                
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to set page for {user_id}: {e}")
    
    def get_page(self, user_id: int) -> int:
        """Get current pagination page"""
        try:
            with sqlite3.connect(ARDAYDA_DB_PATH, timeout=5) as conn:
                cursor = conn.execute("""
                    SELECT page FROM ardayda_user_states 
                    WHERE user_id = ?
                """, (user_id,))
                
                row = cursor.fetchone()
                return row[0] if row else 0
        except Exception as e:
            logger.error(f"Failed to get page for {user_id}: {e}")
            return 0
    
    # ==================== TEMPORARY DATA (for upload/search) ====================
    
    def set_temp_data(self, user_id: int, flow_type: str, key: str, value: Any, ttl: int = 3600):
        """Store temporary data with expiration"""
        try:
            expires = datetime.now() + timedelta(seconds=ttl)
            value_json = json.dumps(value, default=str)
            
            with sqlite3.connect(ARDAYDA_DB_PATH, timeout=5) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO ardayda_flow_data 
                    (user_id, flow_type, data_key, data_value, expires_at) 
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, flow_type, key, value_json, expires))
                
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to set temp data: {e}")
    
    def get_temp_data(self, user_id: int, flow_type: str, key: str) -> Optional[Any]:
        """Get temporary data"""
        try:
            with sqlite3.connect(ARDAYDA_DB_PATH, timeout=5) as conn:
                cursor = conn.execute("""
                    SELECT data_value FROM ardayda_flow_data 
                    WHERE user_id = ? AND flow_type = ? AND data_key = ?
                    AND expires_at > datetime('now')
                """, (user_id, flow_type, key))
                
                row = cursor.fetchone()
                
                if row and row[0]:
                    return json.loads(row[0])
                
                return None
        except Exception as e:
            logger.error(f"Failed to get temp data: {e}")
            return None
    
    def get_all_temp_data(self, user_id: int, flow_type: str) -> Dict:
        """Get all temporary data for a flow type"""
        try:
            with sqlite3.connect(ARDAYDA_DB_PATH, timeout=5) as conn:
                cursor = conn.execute("""
                    SELECT data_key, data_value FROM ardayda_flow_data 
                    WHERE user_id = ? AND flow_type = ?
                    AND expires_at > datetime('now')
                """, (user_id, flow_type))
                
                result = {}
                for row in cursor.fetchall():
                    result[row[0]] = json.loads(row[1])
                
                return result
        except Exception as e:
            logger.error(f"Failed to get all temp data: {e}")
            return {}
    
    def clear_temp_data(self, user_id: int, flow_type: str = None):
        """Clear temporary data (optionally by flow type)"""
        try:
            with sqlite3.connect(ARDAYDA_DB_PATH, timeout=5) as conn:
                if flow_type:
                    conn.execute("""
                        DELETE FROM ardayda_flow_data 
                        WHERE user_id = ? AND flow_type = ?
                    """, (user_id, flow_type))
                else:
                    conn.execute("""
                        DELETE FROM ardayda_flow_data 
                        WHERE user_id = ?
                    """, (user_id,))
                
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to clear temp data: {e}")
    
    # ==================== MESSAGE TRACKING (for conflict_manager) ====================
    
    def set_last_message(self, user_id: int, message_id: int):
        """Store last message ID for cleanup"""
        self.set_temp_data(user_id, 'system', 'last_message', message_id, ttl=86400)
    
    def get_last_message(self, user_id: int) -> Optional[int]:
        """Get last message ID"""
        return self.get_temp_data(user_id, 'system', 'last_message')
    
    def clear_last_message(self, user_id: int):
        """Clear last message ID"""
        self.set_temp_data(user_id, 'system', 'last_message', None, ttl=1)  # Expire immediately
    
    # ==================== STATISTICS ====================
    
    def get_stats(self) -> Dict:
        """Get state manager statistics"""
        try:
            with sqlite3.connect(ARDAYDA_DB_PATH, timeout=5) as conn:
                stats = {}
                
                # Total active states
                cursor = conn.execute("SELECT COUNT(*) FROM ardayda_user_states")
                stats['active_states'] = cursor.fetchone()[0]
                
                # States by status
                cursor = conn.execute("""
                    SELECT status, COUNT(*) 
                    FROM ardayda_user_states 
                    GROUP BY status
                """)
                stats['by_status'] = dict(cursor.fetchall())
                
                # Total flow data entries
                cursor = conn.execute("SELECT COUNT(*) FROM ardayda_flow_data")
                stats['flow_entries'] = cursor.fetchone()[0]
                
                # Oldest state
                cursor = conn.execute("SELECT MIN(updated_at) FROM ardayda_user_states")
                stats['oldest_state'] = cursor.fetchone()[0]
                
                return stats
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {'error': str(e)}


# ==================== Singleton Instance ====================

_state_manager = None

def get_state_manager():
    """Get or create global state manager instance"""
    global _state_manager
    if _state_manager is None:
        _state_manager = ArdaydaStateManager()
    return _state_manager


# ==================== Convenience Functions ====================

def set_user_status(user_id, status, data=None):
    return get_state_manager().set_status(user_id, status, data)

def get_user_status(user_id):
    return get_state_manager().get_status(user_id)

def get_user_flow_data(user_id):
    return get_state_manager().get_flow_data(user_id)

def update_user_flow_data(user_id, data):
    return get_state_manager().update_flow_data(user_id, data)

def clear_user_status(user_id):
    return get_state_manager().clear_status(user_id)

def set_user_page(user_id, page):
    return get_state_manager().set_page(user_id, page)

def get_user_page(user_id):
    return get_state_manager().get_page(user_id)

def set_temp_data(user_id, flow_type, key, value, ttl=3600):
    return get_state_manager().set_temp_data(user_id, flow_type, key, value, ttl)

def get_temp_data(user_id, flow_type, key):
    return get_state_manager().get_temp_data(user_id, flow_type, key)

def clear_temp_data(user_id, flow_type=None):
    return get_state_manager().clear_temp_data(user_id, flow_type)

def set_last_message(user_id, message_id):
    return get_state_manager().set_last_message(user_id, message_id)

def get_last_message(user_id):
    return get_state_manager().get_last_message(user_id)