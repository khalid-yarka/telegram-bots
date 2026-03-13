# bots/ardayda_bot/cache.py

import time
import json
import threading
from typing import Dict, Any, Optional, Union, List
import logging
from datetime import datetime, timedelta

# Set up logger
logger = logging.getLogger(__name__)

class MemoryCache:
    """
    Simple in-memory cache with automatic expiration for Telegram bot temporary data.
    
    Features:
    - Store any Python object with TTL (Time To Live)
    - Auto-expiration of old data
    - Manual cleanup option
    - User-specific data clearing
    - Cache statistics
    - Thread-safe operations
    """
    
    def __init__(self, default_ttl: int = 3600, cleanup_interval: int = 300):
        """
        Initialize the cache.
        
        Args:
            default_ttl: Default time to live in seconds (default: 1 hour)
            cleanup_interval: How often to run cleanup in seconds (default: 5 minutes)
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl
        self.lock = threading.RLock()  # For thread safety
        self.hits = 0
        self.misses = 0
        self.expired = 0
        
        logger.info(f"🚀 Cache initialized with default TTL: {default_ttl}s, cleanup interval: {cleanup_interval}s")
        
        # Start background cleanup thread if interval > 0
        if cleanup_interval > 0:
            self._start_cleanup_thread(cleanup_interval)
    
    def _start_cleanup_thread(self, interval: int):
        """Start background thread to clean expired items"""
        def cleanup_worker():
            while True:
                time.sleep(interval)
                try:
                    cleaned = self.cleanup_expired()
                    if cleaned > 0:
                        logger.debug(f"🧹 Background cleanup removed {cleaned} expired items")
                except Exception as e:
                    logger.error(f"Error in cleanup thread: {e}")
        
        thread = threading.Thread(target=cleanup_worker, daemon=True)
        thread.start()
        logger.debug(f"Background cleanup thread started (interval: {interval}s)")
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Store data in cache.
        
        Args:
            key: Unique identifier (e.g., "upload:123456789")
            value: Any Python object you want to store
            ttl: Time to live in seconds (optional, uses default_ttl if None)
        """
        with self.lock:
            expires_at = time.time() + (ttl or self.default_ttl)
            
            self.cache[key] = {
                'data': value,
                'expires': expires_at,
                'created': time.time(),
                'ttl': ttl or self.default_ttl
            }
            
            logger.debug(f"📝 Cache SET: {key} (expires in {ttl or self.default_ttl}s)")
    
    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve data from cache.
        
        Args:
            key: The cache key to retrieve
            
        Returns:
            The stored value if exists and not expired, None otherwise
        """
        with self.lock:
            item = self.cache.get(key)
            
            if item:
                if time.time() < item['expires']:
                    self.hits += 1
                    logger.debug(f"✅ Cache HIT: {key}")
                    return item['data']
                else:
                    # Auto-clean expired items
                    self.expired += 1
                    logger.debug(f"⏰ Cache EXPIRED: {key}")
                    del self.cache[key]
                    return None
            
            self.misses += 1
            logger.debug(f"❌ Cache MISS: {key}")
            return None
    
    def get_with_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve data along with metadata.
        
        Args:
            key: The cache key to retrieve
            
        Returns:
            Dict with 'data', 'expires', 'created', 'ttl' if exists, None otherwise
        """
        with self.lock:
            item = self.cache.get(key)
            
            if item and time.time() < item['expires']:
                return item
            elif item:
                del self.cache[key]
            
            return None
    
    def delete(self, key: str) -> bool:
        """
        Remove item from cache.
        
        Args:
            key: The cache key to delete
            
        Returns:
            True if item was deleted, False if it didn't exist
        """
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                logger.debug(f"🗑️ Cache DELETE: {key}")
                return True
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists and is not expired"""
        with self.lock:
            item = self.cache.get(key)
            if item and time.time() < item['expires']:
                return True
            return False
    
    def clear_user_data(self, user_id: Union[int, str]) -> int:
        """
        Clear all cache entries for a specific user.
        
        Args:
            user_id: The user ID to clear data for
            
        Returns:
            Number of items cleared
        """
        user_id_str = str(user_id)
        keys_to_delete = []
        
        with self.lock:
            for key in list(self.cache.keys()):
                # Match patterns like "upload:123456" or "search:123456" or "123456:something"
                if f":{user_id_str}" in key or key.startswith(f"{user_id_str}:"):
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del self.cache[key]
        
        if keys_to_delete:
            logger.info(f"🧹 Cleared {len(keys_to_delete)} cache entries for user {user_id}")
        
        return len(keys_to_delete)
    
    def clear_by_prefix(self, prefix: str) -> int:
        """
        Clear all cache entries with a given prefix.
        
        Args:
            prefix: The prefix to match (e.g., "upload:")
            
        Returns:
            Number of items cleared
        """
        keys_to_delete = []
        
        with self.lock:
            for key in list(self.cache.keys()):
                if key.startswith(prefix):
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del self.cache[key]
        
        if keys_to_delete:
            logger.info(f"🧹 Cleared {len(keys_to_delete)} cache entries with prefix '{prefix}'")
        
        return len(keys_to_delete)
    
    def cleanup_expired(self) -> int:
        """Remove all expired items from cache."""
        now = time.time()
        expired_keys = []
        
        with self.lock:
            for key, item in list(self.cache.items()):
                if now >= item['expires']:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.cache[key]
                self.expired += 1
        
        if expired_keys:
            logger.debug(f"🧹 Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            now = time.time()
            active = 0
            expired_count = 0
            
            for item in self.cache.values():
                if now < item['expires']:
                    active += 1
                else:
                    expired_count += 1
            
            # Calculate memory usage estimate (rough)
            import sys
            total_size = sum(sys.getsizeof(str(k)) + sys.getsizeof(str(v)) 
                            for k, v in self.cache.items())
            
            return {
                'total_entries': len(self.cache),
                'active': active,
                'expired_in_cache': expired_count,
                'total_expired_since_start': self.expired,
                'hits': self.hits,
                'misses': self.misses,
                'hit_ratio': self.hits / (self.hits + self.misses) if (self.hits + self.misses) > 0 else 0,
                'memory_estimate_bytes': total_size,
                'memory_estimate_mb': total_size / (1024 * 1024),
                'keys': list(self.cache.keys()),
                'default_ttl': self.default_ttl
            }
    
    def get_all_user_data(self, user_id: Union[int, str]) -> Dict[str, Any]:
        """
        Get all cache data for a specific user.
        
        Args:
            user_id: The user ID to get data for
            
        Returns:
            Dictionary of cache keys and their values for this user
        """
        user_id_str = str(user_id)
        user_data = {}
        
        with self.lock:
            for key, item in self.cache.items():
                if f":{user_id_str}" in key or key.startswith(f"{user_id_str}:"):
                    if time.time() < item['expires']:
                        user_data[key] = item['data']
        
        return user_data
    
    def update_ttl(self, key: str, ttl: int) -> bool:
        """
        Update TTL for an existing cache entry.
        
        Args:
            key: The cache key
            ttl: New TTL in seconds
            
        Returns:
            True if updated, False if key doesn't exist
        """
        with self.lock:
            if key in self.cache:
                self.cache[key]['expires'] = time.time() + ttl
                self.cache[key]['ttl'] = ttl
                logger.debug(f"⏱️ Updated TTL for {key} to {ttl}s")
                return True
            return False
    
    def get_ttl(self, key: str) -> Optional[int]:
        """
        Get remaining TTL for a cache entry.
        
        Args:
            key: The cache key
            
        Returns:
            Remaining seconds until expiry, or None if key doesn't exist/expired
        """
        with self.lock:
            item = self.cache.get(key)
            if item:
                remaining = item['expires'] - time.time()
                if remaining > 0:
                    return int(remaining)
            return None


# ==================== Helper Functions ====================

def generate_key(flow_type: str, user_id: Union[int, str]) -> str:
    """Generate a standard cache key for user flows"""
    return f"{flow_type}:{user_id}"


def generate_temp_key(prefix: str, identifier: Union[int, str]) -> str:
    """Generate a temporary cache key with prefix"""
    return f"temp:{prefix}:{identifier}"


# ==================== Create Global Cache Instance ====================

# Create a global cache instance for the entire bot
# This will be shared across all modules
temp_cache = MemoryCache(
    default_ttl=3600,      # 1 hour default
    cleanup_interval=300    # Clean up every 5 minutes
)


# ==================== Convenience Functions ====================

def save_temp(flow_type: str, user_id: Union[int, str], data: Any, ttl: Optional[int] = None) -> None:
    """Convenience function to save temporary data"""
    key = generate_key(flow_type, user_id)
    temp_cache.set(key, data, ttl)


def get_temp(flow_type: str, user_id: Union[int, str]) -> Optional[Any]:
    """Convenience function to get temporary data"""
    key = generate_key(flow_type, user_id)
    return temp_cache.get(key)


def clear_temp(flow_type: str, user_id: Union[int, str]) -> bool:
    """Convenience function to clear temporary data"""
    key = generate_key(flow_type, user_id)
    return temp_cache.delete(key)


def clear_user_all_temp(user_id: Union[int, str]) -> int:
    """Clear all temporary data for a user"""
    return temp_cache.clear_user_data(user_id)


# ==================== Decorator for Caching Functions ====================

def cached(ttl: int = 300):
    """
    Decorator to cache function results.
    
    Example:
        @cached(ttl=600)
        def get_expensive_data(param):
            # expensive operation
            return result
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Create a cache key from function name and arguments
            key = f"func:{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Try to get from cache
            result = temp_cache.get(key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            temp_cache.set(key, result, ttl)
            return result
        return wrapper
    return decorator


# ==================== Test Function ====================

if __name__ == "__main__":
    # Simple test
    print("Testing cache...")
    
    # Set up logging for test
    logging.basicConfig(level=logging.DEBUG)
    
    # Create test cache
    test_cache = MemoryCache(default_ttl=5)  # 5 second TTL for testing
    
    # Test set and get
    test_cache.set("test:1", {"name": "Test User", "data": "Some value"})
    result = test_cache.get("test:1")
    print(f"Get result: {result}")
    
    # Test exists
    print(f"Exists: {test_cache.exists('test:1')}")
    
    # Test metadata
    meta = test_cache.get_with_metadata("test:1")
    print(f"Metadata: {meta}")
    
    # Test wait for expiration
    print("Waiting for expiration (5 seconds)...")
    time.sleep(6)
    result = test_cache.get("test:1")
    print(f"After expiration: {result}")
    
    # Test stats
    stats = test_cache.get_stats()
    print(f"Stats: {stats}")
    
    print("Cache test complete!")