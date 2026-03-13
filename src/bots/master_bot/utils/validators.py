import re

# Token validation regex
TOKEN_REGEX = re.compile(r'^\d+:[A-Za-z0-9_-]{30,}$')

def is_valid_bot_token(token: str) -> bool:
    """Validate Telegram bot token format"""
    return bool(TOKEN_REGEX.match(token))

def is_valid_bot_name(name: str) -> bool:
    """Validate bot name"""
    return 3 <= len(name) <= 100

def is_valid_command(command: str) -> bool:
    """Validate command format"""
    return command.startswith('/') and 2 <= len(command) <= 50

def sanitize_input(text: str, max_length: int = 1000) -> str:
    """Sanitize user input"""
    if not text:
        return ""

    # Remove excessive whitespace
    text = ' '.join(text.split())

    # Truncate
    if len(text) > max_length:
        text = text[:max_length] + "..."

    return text