from datetime import datetime

class Bot:
    """Bot model for system_bots table"""

    def __init__(self, bot_token, bot_name, bot_type, owner_id,
                 bot_username=None, is_active=True, notes=None):
        self.bot_token = bot_token
        self.bot_name = bot_name
        self.bot_username = bot_username
        self.bot_type = bot_type
        self.owner_id = owner_id
        self.created_at = datetime.now()
        self.is_active = is_active
        self.last_seen = None
        self.total_users = 0
        self.total_messages = 0
        self.notes = notes

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'bot_token': self.bot_token,
            'bot_name': self.bot_name,
            'bot_username': self.bot_username,
            'bot_type': self.bot_type,
            'owner_id': self.owner_id,
            'created_at': self.created_at,
            'is_active': self.is_active,
            'last_seen': self.last_seen,
            'total_users': self.total_users,
            'total_messages': self.total_messages,
            'notes': self.notes
        }

class BotPermission:
    """Bot permission model"""

    def __init__(self, bot_token, user_id, permission='user', notes=None):
        self.bot_token = bot_token
        self.user_id = user_id
        self.permission = permission
        self.granted_at = datetime.now()
        self.notes = notes

    def to_dict(self):
        return {
            'bot_token': self.bot_token,
            'user_id': self.user_id,
            'permission': self.permission,
            'granted_at': self.granted_at,
            'notes': self.notes
        }

class SystemLog:
    """System log model"""

    def __init__(self, bot_token, action_type, user_id=None, details=None):
        self.timestamp = datetime.now()
        self.bot_token = bot_token
        self.user_id = user_id
        self.action_type = action_type
        self.details = details