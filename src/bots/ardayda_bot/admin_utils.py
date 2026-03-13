# bots/ardayda_bot/admin_utils.py
"""Utility functions for admin checks to avoid circular imports"""

from src.bots.ardayda_bot import database
import logging

logger = logging.getLogger(__name__)

def is_admin(user_id: int) -> bool:
    """Check if user is an Ardayda bot admin"""
    try:
        user = database.get_user(user_id)
        return user and user.get('is_admin', False)
    except Exception as e:
        logger.error(f"Error checking admin status for {user_id}: {e}")
        return False