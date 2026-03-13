import os

# ============ BASE PATHS ============
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
MASTER_DB_PATH = os.path.join(DATA_DIR, 'master.db')
ARDAYDA_DB_PATH = os.path.join(DATA_DIR, 'ardayda.db')
DHALINYARO_DB_PATH = os.path.join(DATA_DIR, 'dhalinyaro.db')

class Config:
    """
    Telegram Bots Platform Configuration
    Using SQLite database
    """

    # ============ SUPER ADMIN ============
    SUPER_ADMINS = [
        2094426161,  # Your Telegram ID
    ]

    # ============ SQLITE DATABASE ============
    DATABASE_PATHS = {
        'master': MASTER_DB_PATH,
        'ardayda': ARDAYDA_DB_PATH,
        'dhalinyaro': DHALINYARO_DB_PATH
    }

    # ============ WEBHOOK SETTINGS ============
    WEBHOOK_URL_BASE = 'https://Zabots1.pythonanywhere.com'

    # ============ FLASK SETTINGS ============
    SECRET_KEY = 'telegram-bots-platform-secret-key-2024-change-this'
    DEBUG = False

    # ============ APPLICATION SETTINGS ============
    MAX_BOTS_PER_USER = 10
    LOG_RETENTION_DAYS = 30
    TELEGRAM_API_URL = 'https://api.telegram.org/bot'

    # ============ PATHS ============
    TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
    STATIC_DIR = os.path.join(BASE_DIR, 'static')

    # ============ BOT SPECIFIC SETTINGS ============
    MASTER_BOT_TOKEN = None

    ARDAYDA_SETTINGS = {
        'welcome_message': 'Welcome to Ardayda Bot! 📚',
        'max_posts_per_day': 5,
        'default_language': 'so',
    }

    DHALINYARO_SETTINGS = {
        'welcome_message': 'Welcome to Dhalinyaro Bot! 🎉',
        'min_age': 16,
        'max_group_members': 100,
    }

config = Config()