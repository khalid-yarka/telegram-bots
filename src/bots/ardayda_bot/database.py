# src/bots/ardayda_bot/database.py
"""
Updated database module with:
- Rate limit tables
- Admin broadcast functions
- User management functions
- All missing functions added
- Fixed MySQL syntax for SQLite
- Somalia time conversion
"""

import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta
from src.config import ARDAYDA_DB_PATH

logger = logging.getLogger(__name__)

# Status constants
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


# ==================== CONNECTION MANAGEMENT ====================

@contextmanager
def get_db_connection():
    """
    Context manager for database connections
    Usage:
        with get_db_connection() as conn:
            cursor = conn.execute(...)
    """
    conn = None
    try:
        conn = sqlite3.connect(ARDAYDA_DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()


def init_database():
    """Initialize all database tables (called on startup)"""
    try:
        with get_db_connection() as conn:
            # Users table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    name TEXT,
                    region TEXT,
                    school TEXT,
                    class TEXT,
                    status TEXT DEFAULT 'menu:home',
                    is_admin INTEGER DEFAULT 0,
                    suspended INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # PDFs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pdfs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT NOT NULL,
                    file_unique_id TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    uploader_id INTEGER NOT NULL,
                    downloads INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (uploader_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)
            
            # PDF tags table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pdf_tags (
                    pdf_id INTEGER NOT NULL,
                    tag TEXT NOT NULL,
                    PRIMARY KEY (pdf_id, tag),
                    FOREIGN KEY (pdf_id) REFERENCES pdfs(id) ON DELETE CASCADE
                )
            """)
            
            # Admin logs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ardayda_admin_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id INTEGER NOT NULL,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Rate limits table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ardayda_rate_limits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    count INTEGER DEFAULT 0,
                    window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, action_type)
                )
            """)
            
            # Warnings table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ardayda_warnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    admin_id INTEGER NOT NULL,
                    reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)
            
            # Broadcast history table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ardayda_broadcasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER NOT NULL,
                    filter_type TEXT,
                    filter_value TEXT,
                    message TEXT NOT NULL,
                    recipients_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_status ON users(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_is_admin ON users(is_admin)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pdfs_subject ON pdfs(subject)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pdfs_uploader ON pdfs(uploader_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pdfs_unique ON pdfs(file_unique_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tags_pdf ON pdf_tags(pdf_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rate_limits_user ON ardayda_rate_limits(user_id, action_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_warnings_user ON ardayda_warnings(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_broadcasts_admin ON ardayda_broadcasts(admin_id)")
            
            logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")


# ==================== USER OPERATIONS ====================

def user_exists(user_id):
    """Check if user exists in database"""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone() is not None


def add_user(user_id):
    """Add a new user to database"""
    with get_db_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, status) VALUES (?, ?)",
            (user_id, STATUS_MENU_HOME)
        )
        logger.info(f"User {user_id} added to database")


def get_user(user_id):
    """Get user data by ID"""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_user_suspended(user_id):
    """Check if user is suspended"""
    user = get_user(user_id)
    return user and user.get('suspended', 0) == 1


def set_user_name(user_id, name):
    """Set user's name"""
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE users SET name = ?, last_active = CURRENT_TIMESTAMP WHERE user_id = ?",
            (name, user_id)
        )


def set_user_region(user_id, region):
    """Set user's region"""
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE users SET region = ?, last_active = CURRENT_TIMESTAMP WHERE user_id = ?",
            (region, user_id)
        )


def set_user_school(user_id, school):
    """Set user's school"""
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE users SET school = ?, last_active = CURRENT_TIMESTAMP WHERE user_id = ?",
            (school, user_id)
        )


def set_user_class(user_id, user_class):
    """Set user's class"""
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE users SET class = ?, last_active = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user_class, user_id)
        )


def set_user_status(user_id, status):
    """Set user's current status"""
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE users SET status = ?, last_active = CURRENT_TIMESTAMP WHERE user_id = ?",
            (status, user_id)
        )


def get_user_status(user_id):
    """Get user's current status"""
    user = get_user(user_id)
    return user.get('status') if user else None


def update_last_active(user_id):
    """Update user's last active timestamp"""
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user_id,)
        )


# ==================== PDF OPERATIONS ====================

def pdf_exists(file_unique_id):
    """Check if PDF with given unique ID exists"""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT 1 FROM pdfs WHERE file_unique_id = ?",
            (file_unique_id,)
        )
        return cursor.fetchone() is not None


def insert_pdf(file_id, file_unique_id, name, subject, uploader_id):
    """Insert new PDF and return its ID"""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO pdfs (file_id, file_unique_id, name, subject, uploader_id)
            VALUES (?, ?, ?, ?, ?)
        """, (file_id, file_unique_id, name, subject, uploader_id))
        return cursor.lastrowid


def get_pdf_by_id(pdf_id):
    """Get PDF by ID"""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM pdfs WHERE id = ?", (pdf_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_pdf_by_unique_id(file_unique_id):
    """Get PDF by unique ID"""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM pdfs WHERE file_unique_id = ?", (file_unique_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def search_pdfs(subject, tags=None):
    """
    Search PDFs by subject and optional tags
    Returns list of PDFs with their tags
    """
    with get_db_connection() as conn:
        if tags and len(tags) > 0:
            # Search with tags
            placeholders = ','.join(['?'] * len(tags))
            query = f"""
                SELECT DISTINCT p.* FROM pdfs p
                LEFT JOIN pdf_tags t ON p.id = t.pdf_id
                WHERE p.subject = ? 
                AND (t.tag IN ({placeholders}) OR t.tag IS NULL)
                ORDER BY p.created_at DESC
            """
            params = [subject] + tags
            cursor = conn.execute(query, params)
        else:
            # Search without tags
            cursor = conn.execute("""
                SELECT * FROM pdfs 
                WHERE subject = ? 
                ORDER BY created_at DESC
            """, (subject,))
        
        results = [dict(row) for row in cursor.fetchall()]
        
        # Add tags to each result
        for pdf in results:
            pdf['tags'] = get_pdf_tags(pdf['id'])
        
        return results


def get_user_pdfs_count(user_id):
    """Get number of PDFs uploaded by user"""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM pdfs WHERE uploader_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        return row['count'] if row else 0


def increment_download_count(pdf_id):
    """Increment download count for PDF"""
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE pdfs SET downloads = downloads + 1 WHERE id = ?",
            (pdf_id,)
        )


# ==================== TAG OPERATIONS ====================

def add_pdf_tags(pdf_id, tags):
    """Add tags to a PDF"""
    with get_db_connection() as conn:
        for tag in tags:
            conn.execute(
                "INSERT OR IGNORE INTO pdf_tags (pdf_id, tag) VALUES (?, ?)",
                (pdf_id, tag)
            )


def add_pdf_tags_bulk(pdf_id, tags):
    """Add multiple tags to a PDF efficiently"""
    with get_db_connection() as conn:
        for tag in tags:
            conn.execute(
                "INSERT OR IGNORE INTO pdf_tags (pdf_id, tag) VALUES (?, ?)",
                (pdf_id, tag)
            )


def get_pdf_tags(pdf_id):
    """Get all tags for a PDF"""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT tag FROM pdf_tags WHERE pdf_id = ? ORDER BY tag",
            (pdf_id,)
        )
        return [row['tag'] for row in cursor.fetchall()]


def get_all_tags():
    """Get all unique tags in the system"""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT DISTINCT tag FROM pdf_tags ORDER BY tag")
        return [row['tag'] for row in cursor.fetchall()]


# ==================== ADMIN FUNCTIONS ====================

def is_admin(user_id):
    """Check if user is an admin"""
    user = get_user(user_id)
    return user and user.get('is_admin', 0) == 1


def get_all_users_for_admin(page=1, per_page=10, filter_type=None):
    """
    Get paginated list of all users for admin panel
    Returns: (users_list, total_pages)
    """
    with get_db_connection() as conn:
        # Build query based on filter
        if filter_type == 'admins':
            query = "SELECT * FROM users WHERE is_admin = 1"
        elif filter_type == 'suspended':
            query = "SELECT * FROM users WHERE suspended = 1"
        elif filter_type == 'active':
            query = "SELECT * FROM users WHERE last_active > datetime('now', '-7 days')"
        else:
            query = "SELECT * FROM users"
        
        # Get total count
        count_query = f"SELECT COUNT(*) as count FROM ({query})"
        cursor = conn.execute(count_query)
        total = cursor.fetchone()['count']
        total_pages = (total + per_page - 1) // per_page
        
        # Get paginated results
        offset = (page - 1) * per_page
        cursor = conn.execute(
            f"{query} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (per_page, offset)
        )
        
        users = [dict(row) for row in cursor.fetchall()]
        
        # Add PDF counts
        for user in users:
            user['pdf_count'] = get_user_pdfs_count(user['user_id'])
        
        return users, total_pages


def get_users_for_broadcast(filter_type='all', filter_value=None):
    """
    Get users for broadcast based on filter
    Returns list of user dicts
    """
    with get_db_connection() as conn:
        if filter_type == 'all':
            cursor = conn.execute("SELECT user_id FROM users WHERE suspended = 0")
        
        elif filter_type == 'region' and filter_value:
            cursor = conn.execute(
                "SELECT user_id FROM users WHERE region = ? AND suspended = 0",
                (filter_value,)
            )
        
        elif filter_type == 'school' and filter_value:
            cursor = conn.execute(
                "SELECT user_id FROM users WHERE school = ? AND suspended = 0",
                (filter_value,)
            )
        
        elif filter_type == 'class' and filter_value:
            cursor = conn.execute(
                "SELECT user_id FROM users WHERE class = ? AND suspended = 0",
                (filter_value,)
            )
        
        elif filter_type == 'active':
            cursor = conn.execute("""
                SELECT user_id FROM users 
                WHERE last_active > datetime('now', '-7 days') 
                AND suspended = 0
            """)
        
        elif filter_type == 'admins':
            cursor = conn.execute(
                "SELECT user_id FROM users WHERE is_admin = 1 AND suspended = 0"
            )
        
        else:
            return []
        
        return [dict(row) for row in cursor.fetchall()]


def log_admin_action(admin_id, action, target_type, target_id, details=None):
    """Log an admin action"""
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO ardayda_admin_logs 
            (admin_id, action, target_type, target_id, details)
            VALUES (?, ?, ?, ?, ?)
        """, (admin_id, action, target_type, target_id, details))


def get_admin_logs(limit=100):
    """Get recent admin logs"""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM ardayda_admin_logs 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]


def add_warning(user_id, admin_id, reason):
    """Add a warning to a user"""
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO ardayda_warnings (user_id, admin_id, reason)
            VALUES (?, ?, ?)
        """, (user_id, admin_id, reason))


def get_user_warnings(user_id):
    """Get all warnings for a user"""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM ardayda_warnings 
            WHERE user_id = ? 
            ORDER BY created_at DESC
        """, (user_id,))
        return [dict(row) for row in cursor.fetchall()]


def log_broadcast(admin_id, filter_type, filter_value, message, recipients_count):
    """Log a broadcast message"""
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO ardayda_broadcasts 
            (admin_id, filter_type, filter_value, message, recipients_count)
            VALUES (?, ?, ?, ?, ?)
        """, (admin_id, filter_type, filter_value, message, recipients_count))


# ==================== STATISTICS FUNCTIONS ====================

def get_user_stats():
    """Get user statistics"""
    with get_db_connection() as conn:
        stats = {}
        
        # Total users
        cursor = conn.execute("SELECT COUNT(*) as count FROM users")
        stats['total_users'] = cursor.fetchone()['count']
        
        # Users joined today
        cursor = conn.execute("""
            SELECT COUNT(*) as count FROM users 
            WHERE DATE(created_at) = DATE('now')
        """)
        stats['today_users'] = cursor.fetchone()['count']
        
        # Users joined this week
        cursor = conn.execute("""
            SELECT COUNT(*) as count FROM users 
            WHERE created_at >= datetime('now', '-7 days')
        """)
        stats['week_users'] = cursor.fetchone()['count']
        
        # Active users (last 7 days)
        cursor = conn.execute("""
            SELECT COUNT(*) as count FROM users 
            WHERE last_active >= datetime('now', '-7 days')
        """)
        stats['active_users'] = cursor.fetchone()['count']
        
        # Admins count
        cursor = conn.execute("SELECT COUNT(*) as count FROM users WHERE is_admin = 1")
        stats['admin_count'] = cursor.fetchone()['count']
        
        # Suspended users
        cursor = conn.execute("SELECT COUNT(*) as count FROM users WHERE suspended = 1")
        stats['suspended_count'] = cursor.fetchone()['count']
        
        return stats


def get_pdf_stats():
    """Get PDF statistics"""
    with get_db_connection() as conn:
        stats = {}
        
        # Total PDFs
        cursor = conn.execute("SELECT COUNT(*) as count FROM pdfs")
        stats['total_pdfs'] = cursor.fetchone()['count']
        
        # PDFs uploaded today
        cursor = conn.execute("""
            SELECT COUNT(*) as count FROM pdfs 
            WHERE DATE(created_at) = DATE('now')
        """)
        stats['today_pdfs'] = cursor.fetchone()['count']
        
        # Total downloads
        cursor = conn.execute("SELECT SUM(downloads) as total FROM pdfs")
        stats['total_downloads'] = cursor.fetchone()['total'] or 0
        
        # Most popular subjects
        cursor = conn.execute("""
            SELECT subject, COUNT(*) as count, SUM(downloads) as downloads
            FROM pdfs
            GROUP BY subject
            ORDER BY count DESC
            LIMIT 5
        """)
        stats['top_subjects'] = [dict(row) for row in cursor.fetchall()]
        
        # Top uploaders
        cursor = conn.execute("""
            SELECT u.name, u.user_id, COUNT(p.id) as count, SUM(p.downloads) as downloads
            FROM users u
            JOIN pdfs p ON u.user_id = p.uploader_id
            GROUP BY u.user_id
            ORDER BY count DESC
            LIMIT 5
        """)
        stats['top_uploaders'] = [dict(row) for row in cursor.fetchall()]
        
        return stats


def get_system_stats():
    """Get comprehensive system statistics"""
    stats = {
        'users': get_user_stats(),
        'pdfs': get_pdf_stats()
    }
    
    # Get recent activity
    with get_db_connection() as conn:
        # Recent uploads
        cursor = conn.execute("""
            SELECT p.name, u.name as uploader_name, p.created_at
            FROM pdfs p
            JOIN users u ON p.uploader_id = u.user_id
            ORDER BY p.created_at DESC
            LIMIT 5
        """)
        stats['recent_uploads'] = [dict(row) for row in cursor.fetchall()]
        
        # Recent user joins
        cursor = conn.execute("""
            SELECT name, user_id, created_at
            FROM users
            ORDER BY created_at DESC
            LIMIT 5
        """)
        stats['recent_users'] = [dict(row) for row in cursor.fetchall()]
    
    return stats


# ==================== RATE LIMIT FUNCTIONS ====================

def get_rate_limit(user_id, action_type):
    """Get rate limit record for user"""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM ardayda_rate_limits 
            WHERE user_id = ? AND action_type = ?
        """, (user_id, action_type))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_rate_limit(user_id, action_type, count):
    """Update rate limit count"""
    with get_db_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO ardayda_rate_limits 
            (user_id, action_type, count, window_start)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (user_id, action_type, count))


def reset_rate_limit(user_id, action_type=None):
    """Reset rate limit for user"""
    with get_db_connection() as conn:
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


def get_all_rate_limits(limit=100):
    """Get all rate limit records (for admin)"""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM ardayda_rate_limits 
            ORDER BY user_id, action_type
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]


# ==================== TIME CONVERSION ====================

def utc_to_somalia(utc_time):
    """Convert UTC time to Somalia time (UTC+3)"""
    if not utc_time:
        return None
    
    # If it's a string, convert to datetime
    if isinstance(utc_time, str):
        try:
            from datetime import datetime
            utc_time = datetime.fromisoformat(utc_time.replace('Z', '+00:00'))
        except:
            return utc_time
    
    # Add 3 hours
    return utc_time + timedelta(hours=3)


# Initialize database when module loads
init_database()
