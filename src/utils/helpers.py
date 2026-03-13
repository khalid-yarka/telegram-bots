import time
import json
from datetime import datetime, timedelta

def get_current_time():
    """Get current datetime as string"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def format_time_delta(dt):
    """Format time delta to human readable"""
    if not dt:
        return "Never"

    now = datetime.now()
    diff = now - dt

    if diff.days > 365:
        return f"{diff.days // 365} year(s) ago"
    elif diff.days > 30:
        return f"{diff.days // 30} month(s) ago"
    elif diff.days > 0:
        return f"{diff.days} day(s) ago"
    elif diff.seconds > 3600:
        return f"{diff.seconds // 3600} hour(s) ago"
    elif diff.seconds > 60:
        return f"{diff.seconds // 60} minute(s) ago"
    else:
        return "Just now"

def safe_json_parse(json_str, default=None):
    """Safely parse JSON string"""
    try:
        return json.loads(json_str)
    except:
        return default

def truncate_text(text, max_length=100):
    """Truncate text with ellipsis"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def is_valid_telegram_token(token):
    """Check if token looks like a valid Telegram bot token"""
    if not token or ':' not in token:
        return False
    parts = token.split(':')
    if len(parts) != 2:
        return False
    # Token format: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz123456
    return len(parts[0]) >= 8 and len(parts[1]) >= 30

def extract_command(text):
    """Extract command from message text"""
    if not text or not text.startswith('/'):
        return None
    # Remove bot username if present: /start@bot_username -> /start
    command = text.split()[0].split('@')[0]
    return command

def clean_username(username):
    """Clean telegram username"""
    if not username:
        return None
    # Remove @ if present
    if username.startswith('@'):
        username = username[1:]
    # Remove special characters
    username = ''.join(c for c in username if c.isalnum() or c == '_')
    return username.lower() if username else None

def generate_random_code(length=6):
    """Generate random code for verification"""
    import random
    import string
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def format_bytes(size):
    """Format bytes to human readable size"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"

def dict_to_str(data_dict, max_items=5):
    """Convert dict to readable string"""
    if not data_dict:
        return "Empty"

    items = []
    for i, (key, value) in enumerate(data_dict.items()):
        if i >= max_items:
            items.append("...")
            break
        items.append(f"{key}: {value}")

    return "; ".join(items)