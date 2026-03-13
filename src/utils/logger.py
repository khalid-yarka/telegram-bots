import logging
import sys
from datetime import datetime

def setup_logger(name=__name__, level=logging.INFO):
    """
    Setup logger with console and file handlers

    Args:
        name: Logger name
        level: Logging level

    Returns:
        logging.Logger: Configured logger
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent adding multiple handlers
    if logger.handlers:
        return logger

    # Create formatters
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(console_format)

    # File handler (optional - for PythonAnywhere)
    try:
        log_file = f"logs/telegram_bots_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    except:
        pass  # Skip file handler if can't create

    logger.addHandler(console_handler)

    return logger

def log_webhook_request(bot_token, update_id, user_id=None, chat_id=None):
    """Log webhook request"""
    logger = setup_logger('webhook')
    logger.info(f"Bot: {bot_token[:10]}..., Update: {update_id}, User: {user_id}, Chat: {chat_id}")

def log_command(bot_token, user_id, command, success=True):
    """Log command execution"""
    logger = setup_logger('command')
    status = "✅" if success else "❌"
    logger.info(f"{status} Bot: {bot_token[:10]}..., User: {user_id}, Command: {command}")

def log_error(bot_token, error_message, user_id=None):
    """Log error"""
    logger = setup_logger('error')
    logger.error(f"Bot: {bot_token[:10]}..., User: {user_id}, Error: {error_message}")

def log_bot_action(action, bot_token, user_id, details=None):
    """Log bot management action"""
    logger = setup_logger('bot_action')
    log_msg = f"Action: {action}, Bot: {bot_token[:10]}..., User: {user_id}"
    if details:
        log_msg += f", Details: {details}"
    logger.info(log_msg)

# Create default logger
logger = setup_logger()