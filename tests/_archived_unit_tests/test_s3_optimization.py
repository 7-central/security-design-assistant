"""
Tests for S3 storage optimization features.
"""

import time
from unittest.mock import Mock, patch

import pytest

from src.storage.aws_storage import AWSStorage


class TestS3Optimization:
    """Test S3 optimization features."""

    @pytest.fixture
    def aws_storage(self):
        """Create AWSStorage instance with mocked AWS clients."""
        with patch('boto3.client'), patch('boto3.resource'):
            storage = AWSStorage()
            storage.s3_client = Mock()
            storage.jobs_table = Mock()
            return storage

    def test_intelligent_tiering_applied_on_upload(self, aws_storage):
        """Test that Intelligent Tiering is applied when saving files."""
        import asyncio

        async def run_test():
            await aws_storage.save_file('test-key', b'test content', {'test': 'metadata'})

            # Verify put_object was called with INTELLIGENT_TIERING
            aws_storage.s3_client.put_object.assert_called_once()
            call_args = aws_storage.s3_client.put_object.call_args

            assert call_args[1]['StorageClass'] == 'INTELLIGENT_TIERING'
            assert call_args[1]['Key'] == 'test-key'
            assert call_args[1]['Body'] == b'test content'

        asyncio.run(run_test())

    def test_metadata_caching(self, aws_storage):
        """Test S3 metadata caching functionality."""
        # Test caching metadata
        test_metadata = {'content_length': 100, 'last_modified': 'test-date'}
        aws_storage._cache_metadata('test-key', test_metadata)

        # Verify metadata was cached
        cached = aws_storage._get_cached_metadata('test-key')
        assert cached == test_metadata

    def test_metadata_cache_expiration(self, aws_storage):
        """Test that cached metadata expires after TTL."""
        test_metadata = {'content_length': 100}

        # Cache metadata
        aws_storage._cache_metadata('test-key', test_metadata)

        # Verify it's cached
        assert aws_storage._get_cached_metadata('test-key') == test_metadata

        # Mock time to simulate expiration
        with patch('time.time', return_value=time.time() + 400):  # 400 seconds later
            # Should be expired (TTL is 300 seconds)
            assert aws_storage._get_cached_metadata('test-key') is None

    def test_get_object_metadata_with_cache_hit(self, aws_storage):
        """Test getting object metadata with cache hit."""
        import asyncio

        async def run_test():
            # Pre-cache some metadata
            cached_metadata = {'content_length': 100, 'cached': True}
            aws_storage._cache_metadata('test-key', cached_metadata)

            # Get metadata should return cached version
            result = await aws_storage.get_object_metadata('test-key')
            assert result == cached_metadata

            # S3 client should not have been called
            aws_storage.s3_client.head_object.assert_not_called()

        asyncio.run(run_test())

    def test_get_object_metadata_with_cache_miss(self, aws_storage):
        """Test getting object metadata with cache miss."""
        import asyncio
        from datetime import datetime

        async def run_test():
            # Mock S3 response
            s3_response = {
                'ContentLength': 150,
                'LastModified': datetime.now(),
                'ETag': '"abc123"',
                'ContentType': 'application/pdf',
                'Metadata': {'custom': 'value'},
                'StorageClass': 'INTELLIGENT_TIERING'
            }
            aws_storage.s3_client.head_object.return_value = s3_response

            # Get metadata should fetch from S3 and cache it
            result = await aws_storage.get_object_metadata('test-key')

            # Verify S3 was called
            aws_storage.s3_client.head_object.assert_called_once_with(
                Bucket=aws_storage.s3_bucket,
                Key='test-key'
            )

            # Verify response format
            assert result['content_length'] == 150
            assert result['storage_class'] == 'INTELLIGENT_TIERING'
            assert result['metadata'] == {'custom': 'value'}

            # Verify it was cached
            cached = aws_storage._get_cached_metadata('test-key')
            assert cached == result

        asyncio.run(run_test())

    def test_get_object_metadata_not_found(self, aws_storage):
        """Test getting metadata for non-existent object."""
        import asyncio

        from botocore.exceptions import ClientError

        async def run_test():
            # Mock 404 error
            error = ClientError(
                {'Error': {'Code': '404', 'Message': 'Not Found'}},
                'HeadObject'
            )
            aws_storage.s3_client.head_object.side_effect = error

            # Should return None for 404
            result = await aws_storage.get_object_metadata('non-existent-key')
            assert result is None

        asyncio.run(run_test())

    def test_cache_stats(self, aws_storage):
        """Test cache statistics functionality."""
        # Start with empty cache
        stats = aws_storage.get_cache_stats()
        assert stats['total_entries'] == 0
        assert stats['active_entries'] == 0
        assert stats['expired_entries'] == 0
        assert stats['cache_ttl_seconds'] == 300

        # Add some cached entries
        aws_storage._cache_metadata('key1', {'test': 'data1'})
        aws_storage._cache_metadata('key2', {'test': 'data2'})

        stats = aws_storage.get_cache_stats()
        assert stats['total_entries'] == 2
        assert stats['active_entries'] == 2
        assert stats['expired_entries'] == 0

        # Simulate expired entry
        old_time = time.time() - 400  # 400 seconds ago
        aws_storage._metadata_cache['key1']['timestamp'] = old_time

        stats = aws_storage.get_cache_stats()
        assert stats['total_entries'] == 2
        assert stats['active_entries'] == 1
        assert stats['expired_entries'] == 1

    def test_clear_metadata_cache(self, aws_storage):
        """Test clearing the metadata cache."""
        # Add some cached entries
        aws_storage._cache_metadata('key1', {'test': 'data1'})
        aws_storage._cache_metadata('key2', {'test': 'data2'})

        # Verify cache has entries
        assert len(aws_storage._metadata_cache) == 2

        # Clear cache
        aws_storage.clear_metadata_cache()

        # Verify cache is empty
        assert len(aws_storage._metadata_cache) == 0
        stats = aws_storage.get_cache_stats()
        assert stats['total_entries'] == 0

    def test_presigned_url_default_expiration(self, aws_storage):
        """Test that presigned URLs expire after 1 hour by default."""
        import asyncio

        async def run_test():
            aws_storage.s3_client.generate_presigned_url.return_value = 'https://test-url'

            await aws_storage.generate_presigned_url('test-key')

            # Verify default expiration is 1 hour (3600 seconds)
            aws_storage.s3_client.generate_presigned_url.assert_called_once_with(
                'get_object',
                Params={'Bucket': aws_storage.s3_bucket, 'Key': 'test-key'},
                ExpiresIn=3600
            )

        asyncio.run(run_test())

    def test_metadata_caching_on_file_save(self, aws_storage):
        """Test that metadata is cached when saving files."""
        import asyncio

        async def run_test():
            metadata = {'job_id': 'test-123', 'type': 'pdf'}

            await aws_storage.save_file('test-key', b'content', metadata)

            # Verify metadata was cached during save
            cached = aws_storage._get_cached_metadata('test-key')
            assert cached == metadata

        asyncio.run(run_test())


class TestS3TemplateConfiguration:
    """Test S3 configuration in CloudFormation template."""

    def test_s3_intelligent_tiering_configured(self):
        """Test that S3 bucket has Intelligent Tiering configured."""
        # Read template as text to check configuration
        with open('/Users/leehayton/Cursor Projects/7central/security_and_design/infrastructure/template.yaml') as f:
            template_content = f.read()

        # Check for Intelligent Tiering configuration
        assert 'IntelligentTieringConfigurations:' in template_content
        assert 'IntelligentTieringConfig' in template_content
        assert 'Status: Enabled' in template_content

    def test_s3_transfer_acceleration_enabled(self):
        """Test that S3 Transfer Acceleration is enabled."""
        with open('/Users/leehayton/Cursor Projects/7central/security_and_design/infrastructure/template.yaml') as f:
            template_content = f.read()

        # Check for Transfer Acceleration
        assert 'AccelerateConfiguration:' in template_content
        assert 'AccelerationStatus: Enabled' in template_content

    def test_s3_lifecycle_30_day_expiration(self):
        """Test that S3 lifecycle rule deletes files after 30 days."""
        with open('/Users/leehayton/Cursor Projects/7central/security_and_design/infrastructure/template.yaml') as f:
            template_content = f.read()

        # Check for 30-day expiration
        assert 'ExpirationInDays: 30' in template_content

    def test_sqs_long_polling_enabled(self):
        """Test that SQS long polling is enabled."""
        with open('/Users/leehayton/Cursor Projects/7central/security_and_design/infrastructure/template.yaml') as f:
            template_content = f.read()

        # Check for long polling configuration
        assert 'ReceiveMessageWaitTimeSeconds: 20' in template_content
