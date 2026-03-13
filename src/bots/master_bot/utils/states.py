import time
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class UserStateManager:
    """Manage user states for multi-step flows"""

    def __init__(self, timeout=300):  # 5 minutes timeout
        self.states = {}  # {chat_id: {'state': state, 'data': data, 'timestamp': time}}
        self.timeout = timeout

    def set_state(self, chat_id: int, state: str, data: Dict[str, Any] = None):
        """Set user state"""
        self.states[chat_id] = {
            'state': state,
            'data': data or {},
            'timestamp': time.time()
        }
        logger.debug(f"State set for {chat_id}: {state}")

    def get_state(self, chat_id: int) -> Optional[str]:
        """Get user current state"""
        self._cleanup_expired()

        if chat_id in self.states:
            return self.states[chat_id]['state']
        return None

    def get_data(self, chat_id: int) -> Optional[Dict]:
        """Get user state data"""
        self._cleanup_expired()

        if chat_id in self.states:
            return self.states[chat_id]['data']
        return None

    def update_state(self, chat_id: int, data: Dict[str, Any]):
        """Update state data"""
        if chat_id in self.states:
            self.states[chat_id]['data'].update(data)
            self.states[chat_id]['timestamp'] = time.time()

    def clear_state(self, chat_id: int):
        """Clear user state"""
        if chat_id in self.states:
            del self.states[chat_id]
            logger.debug(f"State cleared for {chat_id}")

    def _cleanup_expired(self):
        """Remove expired states"""
        current_time = time.time()
        expired = [
            chat_id for chat_id, state in self.states.items()
            if current_time - state['timestamp'] > self.timeout
        ]

        for chat_id in expired:
            del self.states[chat_id]
            logger.debug(f"Expired state removed for {chat_id}")