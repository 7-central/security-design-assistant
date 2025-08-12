"""
Lambda environment variable caching utility for performance optimization.
"""

import logging
import os
import time
from functools import lru_cache
from typing import Any, Optional

logger = logging.getLogger(__name__)


class EnvironmentCache:
    """Cache for environment variables and configuration values."""

    def __init__(self, ttl: int = 300):
        """Initialize environment cache.

        Args:
            ttl: Cache time-to-live in seconds (default: 5 minutes)
        """
        self.ttl = ttl
        self._cache = {}
        self._cache_timestamps = {}

        # Pre-cache common environment variables
        self._precache_common_vars()

    def _precache_common_vars(self) -> None:
        """Pre-cache commonly used environment variables."""
        common_vars = [
            'ENVIRONMENT',
            'S3_BUCKET',
            'DYNAMODB_TABLE',
            'SQS_QUEUE_URL',
            'GEMINI_API_KEY_PARAMETER',
            'SNS_ALERT_TOPIC_ARN',
            'STACK_NAME',
            'AWS_REGION',
            'STORAGE_MODE'
        ]

        for var in common_vars:
            value = os.getenv(var)
            if value is not None:
                self._cache[var] = value
                self._cache_timestamps[var] = time.time()
                logger.debug(f"Pre-cached environment variable: {var}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get environment variable with caching.

        Args:
            key: Environment variable name
            default: Default value if not found

        Returns:
            Environment variable value or default
        """
        current_time = time.time()

        # Check if value is cached and not expired
        if key in self._cache:
            cache_age = current_time - self._cache_timestamps.get(key, 0)
            if cache_age < self.ttl:
                logger.debug(f"Cache hit for environment variable: {key}")
                return self._cache[key]
            else:
                # Cache expired, remove it
                del self._cache[key]
                del self._cache_timestamps[key]
                logger.debug(f"Cache expired for environment variable: {key}")

        # Cache miss, get from environment
        value = os.getenv(key, default)

        # Cache the value
        self._cache[key] = value
        self._cache_timestamps[key] = current_time

        logger.debug(f"Cached new environment variable: {key}")
        return value

    def get_int(self, key: str, default: int = 0) -> int:
        """Get integer environment variable with caching.

        Args:
            key: Environment variable name
            default: Default integer value

        Returns:
            Integer value from environment or default
        """
        value = self.get(key, str(default))
        try:
            return int(value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid integer value for {key}: {value}, using default: {default}")
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean environment variable with caching.

        Args:
            key: Environment variable name
            default: Default boolean value

        Returns:
            Boolean value from environment or default
        """
        value = self.get(key, str(default).lower())
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')

        return bool(value)

    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get float environment variable with caching.

        Args:
            key: Environment variable name
            default: Default float value

        Returns:
            Float value from environment or default
        """
        value = self.get(key, str(default))
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid float value for {key}: {value}, using default: {default}")
            return default

    def refresh(self, key: str) -> Any:
        """Force refresh a specific environment variable.

        Args:
            key: Environment variable name to refresh

        Returns:
            Refreshed value
        """
        if key in self._cache:
            del self._cache[key]
            del self._cache_timestamps[key]

        return self.get(key)

    def clear_cache(self) -> None:
        """Clear all cached environment variables."""
        self._cache.clear()
        self._cache_timestamps.clear()
        logger.info("Environment variable cache cleared")

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Cache statistics
        """
        current_time = time.time()
        active_entries = 0
        expired_entries = 0

        for key, timestamp in self._cache_timestamps.items():
            cache_age = current_time - timestamp
            if cache_age < self.ttl:
                active_entries += 1
            else:
                expired_entries += 1

        return {
            'total_entries': len(self._cache),
            'active_entries': active_entries,
            'expired_entries': expired_entries,
            'cache_ttl_seconds': self.ttl
        }

    def get_all_cached(self) -> dict[str, Any]:
        """Get all currently cached values (for debugging).

        Returns:
            Dictionary of all cached environment variables
        """
        current_time = time.time()
        active_cache = {}

        for key, value in self._cache.items():
            timestamp = self._cache_timestamps.get(key, 0)
            cache_age = current_time - timestamp

            if cache_age < self.ttl:
                active_cache[key] = {
                    'value': value,
                    'cached_at': timestamp,
                    'age_seconds': cache_age
                }

        return active_cache


# Global environment cache instance
_env_cache = None


def get_env_cache() -> EnvironmentCache:
    """Get the global environment cache instance.

    Returns:
        Global EnvironmentCache instance
    """
    global _env_cache
    if _env_cache is None:
        _env_cache = EnvironmentCache()
        logger.info("Initialized global environment cache")
    return _env_cache


# Convenience functions
def cached_getenv(key: str, default: Any = None) -> Any:
    """Get environment variable with caching (convenience function).

    Args:
        key: Environment variable name
        default: Default value if not found

    Returns:
        Environment variable value or default
    """
    return get_env_cache().get(key, default)


def cached_getenv_int(key: str, default: int = 0) -> int:
    """Get integer environment variable with caching.

    Args:
        key: Environment variable name
        default: Default integer value

    Returns:
        Integer value from environment or default
    """
    return get_env_cache().get_int(key, default)


def cached_getenv_bool(key: str, default: bool = False) -> bool:
    """Get boolean environment variable with caching.

    Args:
        key: Environment variable name
        default: Default boolean value

    Returns:
        Boolean value from environment or default
    """
    return get_env_cache().get_bool(key, default)


@lru_cache(maxsize=128)
def get_static_config(config_key: str) -> Optional[str]:
    """Get static configuration values that never change during Lambda execution.

    Uses LRU cache for maximum performance on truly static values.

    Args:
        config_key: Configuration key name

    Returns:
        Configuration value or None
    """
    static_configs = {
        'aws_region': os.getenv('AWS_REGION', 'us-east-1'),
        'function_name': os.getenv('AWS_LAMBDA_FUNCTION_NAME'),
        'function_version': os.getenv('AWS_LAMBDA_FUNCTION_VERSION'),
        'log_group': os.getenv('AWS_LAMBDA_LOG_GROUP_NAME'),
        'memory_size': os.getenv('AWS_LAMBDA_FUNCTION_MEMORY_SIZE'),
        'runtime': 'python3.11',  # Static for our deployment
        'architecture': 'arm64'   # Static for our deployment
    }

    return static_configs.get(config_key)


def warm_env_cache() -> None:
    """Warm up the environment cache with common variables.

    This function can be called during Lambda initialization to pre-populate
    the cache and reduce cold start impact.
    """
    cache = get_env_cache()

    # Common variables to pre-warm
    common_vars = [
        'ENVIRONMENT',
        'STORAGE_MODE',
        'S3_BUCKET',
        'DYNAMODB_TABLE',
        'SQS_QUEUE_URL',
        'GEMINI_API_KEY_PARAMETER',
        'SNS_ALERT_TOPIC_ARN'
    ]

    for var in common_vars:
        cache.get(var)

    logger.info(f"Environment cache warmed with {len(common_vars)} variables")


def get_cache_headers(max_age: int = 300) -> dict[str, str]:
    """Get HTTP cache headers for API responses.

    Args:
        max_age: Cache max age in seconds

    Returns:
        Dictionary of cache headers
    """
    return {
        'Cache-Control': f'public, max-age={max_age}',
        'Expires': str(int(time.time() + max_age)),
        'ETag': f'"{hash(str(time.time()))}"'  # Simple ETag generation
    }
