import re
from flask import abort, request

TOKEN_REGEX = re.compile(r"^\d+:[A-Za-z0-9_-]{30,}$")

def validate_bot_token(token: str) -> bool:
    return bool(TOKEN_REGEX.match(token))


def verify_telegram_secret(expected_secret: str):
    header_secret = request.headers.get(
        "X-Telegram-Bot-Api-Secret-Token"
    )
    if header_secret != expected_secret:
        abort(403)