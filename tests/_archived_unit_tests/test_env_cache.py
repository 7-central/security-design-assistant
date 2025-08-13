"""
Tests for environment variable caching utility.
"""

import os
import time
from unittest.mock import patch

import pytest

from src.utils.env_cache import (
    EnvironmentCache,
    cached_getenv,
    cached_getenv_bool,
    cached_getenv_int,
    get_cache_headers,
    get_env_cache,
    get_static_config,
    warm_env_cache,
)


class TestEnvironmentCache:
    """Test EnvironmentCache functionality."""

    @pytest.fixture
    def env_cache(self):
        """Create a fresh EnvironmentCache instance for testing."""
        return EnvironmentCache(ttl=60)  # 1 minute TTL for testing

    def test_initialization(self, env_cache):
        """Test EnvironmentCache initialization."""
        assert env_cache.ttl == 60
        assert isinstance(env_cache._cache, dict)
        assert isinstance(env_cache._cache_timestamps, dict)

    @patch.dict(os.environ, {'TEST_VAR': 'test_value'})
    def test_get_environment_variable(self, env_cache):
        """Test getting environment variable with caching."""
        # First call should cache the value
        result1 = env_cache.get('TEST_VAR')
        assert result1 == 'test_value'
        assert 'TEST_VAR' in env_cache._cache

        # Second call should use cached value
        result2 = env_cache.get('TEST_VAR')
        assert result2 == 'test_value'

    def test_get_with_default(self, env_cache):
        """Test getting non-existent environment variable with default."""
        result = env_cache.get('NON_EXISTENT_VAR', 'default_value')
        assert result == 'default_value'
        assert env_cache._cache['NON_EXISTENT_VAR'] == 'default_value'

    @patch.dict(os.environ, {'TEST_INT': '123'})
    def test_get_int(self, env_cache):
        """Test getting integer environment variable."""
        result = env_cache.get_int('TEST_INT')
        assert result == 123
        assert isinstance(result, int)

    def test_get_int_invalid_value(self, env_cache):
        """Test getting invalid integer environment variable."""
        with patch.dict(os.environ, {'TEST_INT': 'not_a_number'}):
            result = env_cache.get_int('TEST_INT', default=42)
            assert result == 42

    @patch.dict(os.environ, {'TEST_BOOL_TRUE': 'true', 'TEST_BOOL_FALSE': 'false'})
    def test_get_bool(self, env_cache):
        """Test getting boolean environment variable."""
        assert env_cache.get_bool('TEST_BOOL_TRUE') is True
        assert env_cache.get_bool('TEST_BOOL_FALSE') is False

        # Test various true values
        with patch.dict(os.environ, {'TEST_BOOL': '1'}):
            assert env_cache.get_bool('TEST_BOOL') is True

        with patch.dict(os.environ, {'TEST_BOOL': 'yes'}):
            assert env_cache.get_bool('TEST_BOOL') is True

    @patch.dict(os.environ, {'TEST_FLOAT': '3.14'})
    def test_get_float(self, env_cache):
        """Test getting float environment variable."""
        result = env_cache.get_float('TEST_FLOAT')
        assert result == 3.14
        assert isinstance(result, float)

    def test_get_float_invalid_value(self, env_cache):
        """Test getting invalid float environment variable."""
        with patch.dict(os.environ, {'TEST_FLOAT': 'not_a_float'}):
            result = env_cache.get_float('TEST_FLOAT', default=2.5)
            assert result == 2.5

    def test_cache_expiration(self, env_cache):
        """Test that cached values expire after TTL."""
        env_cache.ttl = 1  # 1 second TTL

        with patch.dict(os.environ, {'TEST_VAR': 'initial_value'}):
            # Cache initial value
            result1 = env_cache.get('TEST_VAR')
            assert result1 == 'initial_value'

            # Wait for cache to expire
            time.sleep(1.1)

            # Change environment variable
            with patch.dict(os.environ, {'TEST_VAR': 'new_value'}):
                result2 = env_cache.get('TEST_VAR')
                assert result2 == 'new_value'

    @patch.dict(os.environ, {'TEST_VAR': 'value1'})
    def test_refresh(self, env_cache):
        """Test forcing refresh of cached variable."""
        # Cache initial value
        result1 = env_cache.get('TEST_VAR')
        assert result1 == 'value1'

        # Change environment variable
        with patch.dict(os.environ, {'TEST_VAR': 'value2'}):
            # Get cached value (should still be old)
            result2 = env_cache.get('TEST_VAR')
            assert result2 == 'value1'

            # Force refresh
            result3 = env_cache.refresh('TEST_VAR')
            assert result3 == 'value2'

    def test_clear_cache(self, env_cache):
        """Test clearing all cached values."""
        # Clear any pre-cached values first
        env_cache.clear_cache()

        with patch.dict(os.environ, {'VAR1': 'value1', 'VAR2': 'value2'}):
            env_cache.get('VAR1')
            env_cache.get('VAR2')

            assert len(env_cache._cache) == 2

            env_cache.clear_cache()

            assert len(env_cache._cache) == 0
            assert len(env_cache._cache_timestamps) == 0

    def test_get_cache_stats(self, env_cache):
        """Test getting cache statistics."""
        env_cache.clear_cache()

        with patch.dict(os.environ, {'VAR1': 'value1', 'VAR2': 'value2'}):
            env_cache.get('VAR1')
            env_cache.get('VAR2')

            stats = env_cache.get_cache_stats()

            assert stats['total_entries'] == 2
            assert stats['active_entries'] == 2
            assert stats['expired_entries'] == 0
            assert stats['cache_ttl_seconds'] == env_cache.ttl

    def test_get_all_cached(self, env_cache):
        """Test getting all cached values for debugging."""
        env_cache.clear_cache()

        with patch.dict(os.environ, {'VAR1': 'value1', 'VAR2': 'value2'}):
            env_cache.get('VAR1')
            env_cache.get('VAR2')

            cached_values = env_cache.get_all_cached()

            assert len(cached_values) == 2
            assert 'VAR1' in cached_values
            assert 'VAR2' in cached_values
            assert cached_values['VAR1']['value'] == 'value1'
            assert 'age_seconds' in cached_values['VAR1']


class TestGlobalCache:
    """Test global cache functions."""

    def test_get_env_cache_singleton(self):
        """Test that get_env_cache returns the same instance."""
        cache1 = get_env_cache()
        cache2 = get_env_cache()

        assert cache1 is cache2

    @patch.dict(os.environ, {'GLOBAL_VAR': 'global_value'})
    def test_cached_getenv(self):
        """Test cached_getenv convenience function."""
        result = cached_getenv('GLOBAL_VAR', 'default')
        assert result == 'global_value'

    @patch.dict(os.environ, {'GLOBAL_INT': '456'})
    def test_cached_getenv_int(self):
        """Test cached_getenv_int convenience function."""
        result = cached_getenv_int('GLOBAL_INT', 0)
        assert result == 456

    @patch.dict(os.environ, {'GLOBAL_BOOL': 'true'})
    def test_cached_getenv_bool(self):
        """Test cached_getenv_bool convenience function."""
        result = cached_getenv_bool('GLOBAL_BOOL', False)
        assert result is True


class TestStaticConfig:
    """Test static configuration functionality."""

    @patch.dict(os.environ, {'AWS_REGION': 'us-west-2'})
    def test_get_static_config(self):
        """Test getting static configuration values."""
        result = get_static_config('aws_region')
        assert result == 'us-west-2'

    def test_get_static_config_nonexistent(self):
        """Test getting non-existent static config."""
        result = get_static_config('non_existent_config')
        assert result is None

    @patch.dict(os.environ, {'AWS_LAMBDA_FUNCTION_NAME': 'test-function'})
    def test_get_static_config_function_name(self):
        """Test getting Lambda function name from static config."""
        result = get_static_config('function_name')
        assert result == 'test-function'

    def test_get_static_config_caching(self):
        """Test that static config uses LRU cache."""
        # Call multiple times - should use cache
        result1 = get_static_config('runtime')
        result2 = get_static_config('runtime')

        assert result1 == result2 == 'python3.11'


class TestWarmCache:
    """Test cache warming functionality."""

    @patch.dict(os.environ, {
        'ENVIRONMENT': 'test',
        'STORAGE_MODE': 'aws',
        'S3_BUCKET': 'test-bucket'
    })
    def test_warm_env_cache(self):
        """Test warming the environment cache."""
        # Clear any existing cache
        cache = get_env_cache()
        cache.clear_cache()

        # Warm the cache
        warm_env_cache()

        # Verify common variables are cached
        stats = cache.get_cache_stats()
        assert stats['total_entries'] > 0

        # Verify specific variables are accessible
        assert cached_getenv('ENVIRONMENT') == 'test'
        assert cached_getenv('STORAGE_MODE') == 'aws'


class TestCacheHeaders:
    """Test HTTP cache headers functionality."""

    def test_get_cache_headers_default(self):
        """Test getting cache headers with default max_age."""
        headers = get_cache_headers()

        assert 'Cache-Control' in headers
        assert 'max-age=300' in headers['Cache-Control']
        assert 'public' in headers['Cache-Control']
        assert 'Expires' in headers
        assert 'ETag' in headers

    def test_get_cache_headers_custom_age(self):
        """Test getting cache headers with custom max_age."""
        headers = get_cache_headers(max_age=3600)

        assert 'max-age=3600' in headers['Cache-Control']

        # Verify expires header is set correctly
        expires_time = int(headers['Expires'])
        current_time = int(time.time())

        # Should expire approximately 1 hour from now
        assert 3500 < (expires_time - current_time) < 3700

    def test_cache_headers_structure(self):
        """Test that cache headers have correct structure."""
        headers = get_cache_headers(max_age=1800)

        expected_keys = ['Cache-Control', 'Expires', 'ETag']
        for key in expected_keys:
            assert key in headers

        assert isinstance(headers['Cache-Control'], str)
        assert isinstance(headers['Expires'], str)
        assert isinstance(headers['ETag'], str)
        assert headers['ETag'].startswith('"') and headers['ETag'].endswith('"')


class TestCacheIntegration:
    """Test cache integration with settings."""

    @patch('src.utils.env_cache._env_cache', None)  # Reset global cache
    def test_settings_use_cached_env(self):
        """Test that Settings class uses cached environment variables."""
        from src.config.settings import Settings

        with patch.dict(os.environ, {'STORAGE_MODE': 'cached_aws'}, clear=False):
            settings = Settings()

            # First access should cache the value
            storage_mode1 = settings.STORAGE_MODE
            assert storage_mode1 == 'cached_aws'

            # Second access should use cache
            storage_mode2 = settings.STORAGE_MODE
            assert storage_mode2 == 'cached_aws'

    @patch('src.utils.env_cache._env_cache', None)  # Reset global cache
    def test_settings_aws_properties(self):
        """Test AWS-specific cached properties."""
        from src.config.settings import Settings

        with patch.dict(os.environ, {
            'S3_BUCKET': 'test-cached-bucket',
            'DYNAMODB_TABLE': 'test-cached-table'
        }, clear=False):
            settings = Settings()

            assert settings.S3_BUCKET == 'test-cached-bucket'
            assert settings.DYNAMODB_TABLE == 'test-cached-table'

    def test_settings_static_config(self):
        """Test settings using static configuration."""
        from src.config.settings import Settings

        settings = Settings()

        # These should come from static config
        assert settings.ARCHITECTURE == 'arm64'
        assert settings.AWS_REGION  # Should have a default value
