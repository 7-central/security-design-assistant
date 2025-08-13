"""
Tests for S3 batch operations utility.
"""

import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

import pytest

from src.utils.s3_batch_operations import (
    BatchOperation,
    S3BatchProcessor,
    batch_get_objects,
    batch_check_objects_exist
)


class TestBatchOperation:
    """Test BatchOperation dataclass."""

    def test_batch_operation_creation(self):
        """Test creating a BatchOperation."""
        operation = BatchOperation(
            operation_type='get',
            bucket='test-bucket',
            key='test-key',
            data=b'test-data',
            metadata={'custom': 'value'},
            priority=5
        )
        
        assert operation.operation_type == 'get'
        assert operation.bucket == 'test-bucket'
        assert operation.key == 'test-key'
        assert operation.data == b'test-data'
        assert operation.metadata == {'custom': 'value'}
        assert operation.priority == 5
        assert isinstance(operation.timestamp, datetime)

    def test_batch_operation_defaults(self):
        """Test BatchOperation with default values."""
        operation = BatchOperation(
            operation_type='put',
            bucket='test-bucket',
            key='test-key'
        )
        
        assert operation.data is None
        assert operation.metadata is None
        assert operation.callback is None
        assert operation.priority == 0
        assert isinstance(operation.timestamp, datetime)


class TestS3BatchProcessor:
    """Test S3BatchProcessor functionality."""

    @pytest.fixture
    def mock_s3_client(self):
        """Create mock S3 client."""
        client = Mock()
        client.get_object.return_value = {
            'Body': Mock(),
            'Metadata': {'test': 'value'}
        }
        client.get_object.return_value['Body'].read.return_value = b'test content'
        
        client.put_object.return_value = {'ETag': '"abc123"'}
        
        client.head_object.return_value = {
            'ContentLength': 100,
            'LastModified': datetime.now(),
            'ETag': '"abc123"',
            'ContentType': 'application/pdf',
            'Metadata': {'custom': 'value'},
            'StorageClass': 'INTELLIGENT_TIERING'
        }
        
        client.delete_objects.return_value = {
            'Deleted': [{'Key': 'test-key-1'}, {'Key': 'test-key-2'}],
            'Errors': []
        }
        
        return client

    @pytest.fixture
    def batch_processor(self, mock_s3_client):
        """Create S3BatchProcessor with mock client."""
        return S3BatchProcessor(mock_s3_client, batch_size=3, flush_interval=1.0)

    def test_initialization(self, mock_s3_client):
        """Test batch processor initialization."""
        processor = S3BatchProcessor(mock_s3_client, batch_size=5, flush_interval=2.0)
        
        assert processor.s3_client == mock_s3_client
        assert processor.batch_size == 5
        assert processor.flush_interval == 2.0
        assert len(processor._pending_operations) == 0
        assert processor.stats['total_operations'] == 0

    @pytest.mark.asyncio
    async def test_add_operation(self, batch_processor):
        """Test adding operations to the batch."""
        operation = BatchOperation(
            operation_type='get',
            bucket='test-bucket',
            key='test-key'
        )
        
        await batch_processor.add_operation(operation)
        
        assert batch_processor.stats['total_operations'] == 1
        # Should not flush yet (batch_size is 3)
        assert len(batch_processor._pending_operations) == 1

    @pytest.mark.asyncio
    async def test_auto_flush_on_batch_size(self, batch_processor):
        """Test automatic flushing when batch size is reached."""
        operations = [
            BatchOperation('get', 'test-bucket', f'key-{i}')
            for i in range(3)
        ]
        
        for operation in operations:
            await batch_processor.add_operation(operation)
        
        # Should have flushed after 3 operations
        assert batch_processor.stats['batches_processed'] == 1
        assert len(batch_processor._pending_operations) == 0

    @pytest.mark.asyncio
    async def test_process_get_batch(self, batch_processor):
        """Test processing GET operations."""
        operations = [
            BatchOperation('get', 'test-bucket', 'key-1'),
            BatchOperation('get', 'test-bucket', 'key-2')
        ]
        
        results = await batch_processor._process_get_batch(operations)
        
        assert len(results) == 2
        for result in results:
            assert result['success'] is True
            assert result['data'] == b'test content'
            assert 'metadata' in result

    @pytest.mark.asyncio
    async def test_process_put_batch(self, batch_processor):
        """Test processing PUT operations."""
        operations = [
            BatchOperation(
                'put', 
                'test-bucket', 
                'key-1', 
                data=b'content1',
                metadata={'type': 'pdf'}
            ),
            BatchOperation('put', 'test-bucket', 'key-2', data=b'content2')
        ]
        
        results = await batch_processor._process_put_batch(operations)
        
        assert len(results) == 2
        for result in results:
            assert result['success'] is True
            assert 'key' in result
        
        # Verify S3 calls were made with correct parameters
        assert batch_processor.s3_client.put_object.call_count == 2
        
        # Check that INTELLIGENT_TIERING was set
        calls = batch_processor.s3_client.put_object.call_args_list
        for call in calls:
            assert call[1]['StorageClass'] == 'INTELLIGENT_TIERING'

    @pytest.mark.asyncio
    async def test_process_head_batch(self, batch_processor):
        """Test processing HEAD operations."""
        operations = [
            BatchOperation('head', 'test-bucket', 'key-1'),
            BatchOperation('head', 'test-bucket', 'key-2')
        ]
        
        results = await batch_processor._process_head_batch(operations)
        
        assert len(results) == 2
        for result in results:
            assert result['success'] is True
            assert 'metadata' in result
            assert result['metadata']['content_length'] == 100

    @pytest.mark.asyncio
    async def test_process_delete_batch(self, batch_processor):
        """Test processing DELETE operations using batch API."""
        operations = [
            BatchOperation('delete', 'test-bucket', 'test-key-1'),
            BatchOperation('delete', 'test-bucket', 'test-key-2')
        ]
        
        results = await batch_processor._process_delete_batch(operations)
        
        assert len(results) == 2
        for result in results:
            assert result['success'] is True
        
        # Verify batch delete was called
        batch_processor.s3_client.delete_objects.assert_called_once()
        call_args = batch_processor.s3_client.delete_objects.call_args
        assert call_args[1]['Bucket'] == 'test-bucket'
        assert len(call_args[1]['Delete']['Objects']) == 2

    @pytest.mark.asyncio
    async def test_priority_sorting(self, batch_processor):
        """Test that operations are processed by priority."""
        callback_order = []
        
        async def priority_callback(result):
            callback_order.append(result['operation'].priority)
        
        operations = [
            BatchOperation('get', 'test-bucket', 'key-1', priority=1, callback=priority_callback),
            BatchOperation('get', 'test-bucket', 'key-2', priority=5, callback=priority_callback),
            BatchOperation('get', 'test-bucket', 'key-3', priority=3, callback=priority_callback)
        ]
        
        for operation in operations:
            await batch_processor.add_operation(operation)
        
        # Should be processed in priority order: 5, 3, 1
        assert callback_order == [5, 3, 1]

    def test_get_stats(self, batch_processor):
        """Test getting batch processor statistics."""
        # Add some test data to stats
        batch_processor.stats.update({
            'total_operations': 10,
            'batches_processed': 2,
            'api_calls_saved': 5,
            'total_api_calls': 8
        })
        
        stats = batch_processor.get_stats()
        
        assert stats['total_operations'] == 10
        assert stats['batches_processed'] == 2
        assert stats['api_calls_saved'] == 5
        assert stats['efficiency_percent'] == 50.0  # 5/10 * 100
        assert stats['avg_operations_per_batch'] == 5.0  # 10/2

    @pytest.mark.asyncio
    async def test_force_flush(self, batch_processor):
        """Test forcing a flush of pending operations."""
        operations = [
            BatchOperation('get', 'test-bucket', 'key-1'),
            BatchOperation('get', 'test-bucket', 'key-2')
        ]
        
        # Add operations without auto-flushing
        batch_processor._pending_operations.extend(operations)
        batch_processor.stats['total_operations'] += len(operations)
        
        results = await batch_processor.force_flush()
        
        assert len(results) == 2
        assert len(batch_processor._pending_operations) == 0
        assert batch_processor.stats['batches_processed'] == 1

    @pytest.mark.asyncio
    async def test_cleanup(self, batch_processor):
        """Test cleanup processing of remaining operations."""
        operations = [
            BatchOperation('get', 'test-bucket', 'key-1')
        ]
        
        batch_processor._pending_operations.extend(operations)
        batch_processor.stats['total_operations'] += len(operations)
        
        await batch_processor.cleanup()
        
        assert len(batch_processor._pending_operations) == 0
        assert batch_processor.stats['batches_processed'] == 1


class TestBatchUtilityFunctions:
    """Test utility functions for batch operations."""

    @pytest.fixture
    def mock_s3_client(self):
        """Create mock S3 client for utility functions."""
        client = Mock()
        client.get_object.return_value = {
            'Body': Mock(),
            'Metadata': {'test': 'value'}
        }
        client.get_object.return_value['Body'].read.return_value = b'test content'
        
        client.head_object.return_value = {
            'ContentLength': 100,
            'LastModified': datetime.now(),
            'ETag': '"abc123"'
        }
        
        return client

    @pytest.mark.asyncio
    async def test_batch_get_objects(self, mock_s3_client):
        """Test batch get objects utility function."""
        keys = ['key-1', 'key-2', 'key-3']
        
        results = await batch_get_objects(mock_s3_client, 'test-bucket', keys)
        
        assert len(results) == 3
        assert mock_s3_client.get_object.call_count == 3
        
        for result in results:
            assert result['success'] is True
            assert result['data'] == b'test content'

    @pytest.mark.asyncio
    async def test_batch_check_objects_exist(self, mock_s3_client):
        """Test batch check objects exist utility function."""
        keys = ['key-1', 'key-2', 'key-3']
        
        existence_map = await batch_check_objects_exist(mock_s3_client, 'test-bucket', keys)
        
        assert len(existence_map) == 3
        assert mock_s3_client.head_object.call_count == 3
        
        for key in keys:
            assert key in existence_map
            assert existence_map[key] is True


class TestErrorHandling:
    """Test error handling in batch operations."""

    @pytest.mark.asyncio
    async def test_get_operation_error_handling(self):
        """Test error handling in GET operations."""
        from botocore.exceptions import ClientError
        
        mock_client = Mock()
        mock_client.get_object.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchKey', 'Message': 'Not Found'}},
            'GetObject'
        )
        
        processor = S3BatchProcessor(mock_client)
        operations = [BatchOperation('get', 'test-bucket', 'missing-key')]
        
        results = await processor._process_get_batch(operations)
        
        assert len(results) == 1
        assert results[0]['success'] is False
        assert 'error' in results[0]

    @pytest.mark.asyncio
    async def test_callback_error_handling(self):
        """Test that callbacks are called even on errors."""
        from botocore.exceptions import ClientError
        
        callback_called = []
        
        async def error_callback(result):
            callback_called.append(result['success'])
        
        mock_client = Mock()
        mock_client.head_object.side_effect = ClientError(
            {'Error': {'Code': '404', 'Message': 'Not Found'}},
            'HeadObject'
        )
        
        processor = S3BatchProcessor(mock_client)
        operation = BatchOperation(
            'head', 
            'test-bucket', 
            'missing-key',
            callback=error_callback
        )
        
        await processor._process_head_batch([operation])
        
        assert len(callback_called) == 1
        assert callback_called[0] is False