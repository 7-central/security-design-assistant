"""
S3 batch operations utility for request consolidation and cost optimization.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class BatchOperation:
    """Represents a batch S3 operation."""
    operation_type: str  # 'get', 'put', 'delete', 'head'
    bucket: str
    key: str
    data: Optional[bytes] = None
    metadata: Optional[dict[str, Any]] = None
    callback: Optional[callable] = None
    priority: int = 0  # Higher number = higher priority
    timestamp: datetime = field(default_factory=datetime.now)


class S3BatchProcessor:
    """Processes S3 operations in batches to minimize API calls and costs."""

    def __init__(self, s3_client: Any, batch_size: int = 10, flush_interval: float = 5.0):
        """Initialize the batch processor.

        Args:
            s3_client: Boto3 S3 client
            batch_size: Maximum operations per batch
            flush_interval: Seconds to wait before auto-flushing
        """
        self.s3_client = s3_client
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        # Queue for pending operations
        self._pending_operations: list[BatchOperation] = []
        self._last_flush = datetime.now()

        # Statistics
        self.stats = {
            'total_operations': 0,
            'batches_processed': 0,
            'api_calls_saved': 0,
            'total_api_calls': 0
        }

    async def add_operation(self, operation: BatchOperation) -> Any:
        """Add an operation to the batch queue.

        Args:
            operation: The batch operation to queue

        Returns:
            Operation result when batch is processed
        """
        self._pending_operations.append(operation)
        self.stats['total_operations'] += 1

        # Check if we should flush
        should_flush = (
            len(self._pending_operations) >= self.batch_size or
            (datetime.now() - self._last_flush).total_seconds() >= self.flush_interval
        )

        if should_flush:
            await self._flush_batch()

        logger.debug(f"Added {operation.operation_type} operation for {operation.key}")

    async def _flush_batch(self) -> list[Any]:
        """Process all pending operations in optimized batches.

        Returns:
            List of operation results
        """
        if not self._pending_operations:
            return []

        logger.info(f"Processing batch of {len(self._pending_operations)} operations")

        # Sort by priority and group by operation type
        self._pending_operations.sort(key=lambda x: (-x.priority, x.timestamp))

        results = []

        # Group operations by type for better batching
        get_operations = [op for op in self._pending_operations if op.operation_type == 'get']
        put_operations = [op for op in self._pending_operations if op.operation_type == 'put']
        head_operations = [op for op in self._pending_operations if op.operation_type == 'head']
        delete_operations = [op for op in self._pending_operations if op.operation_type == 'delete']

        # Process each type of operation
        if get_operations:
            get_results = await self._process_get_batch(get_operations)
            results.extend(get_results)

        if put_operations:
            put_results = await self._process_put_batch(put_operations)
            results.extend(put_results)

        if head_operations:
            head_results = await self._process_head_batch(head_operations)
            results.extend(head_results)

        if delete_operations:
            delete_results = await self._process_delete_batch(delete_operations)
            results.extend(delete_results)

        # Clear processed operations
        processed_count = len(self._pending_operations)
        self._pending_operations.clear()
        self._last_flush = datetime.now()

        # Update statistics
        self.stats['batches_processed'] += 1
        api_calls_made = len(get_operations) + len(put_operations) + len(head_operations)
        if delete_operations:
            api_calls_made += 1  # Delete can be batched into single call

        self.stats['total_api_calls'] += api_calls_made
        self.stats['api_calls_saved'] += max(0, processed_count - api_calls_made)

        logger.info(f"Batch processed: {processed_count} operations, {api_calls_made} API calls")

        return results

    async def _process_get_batch(self, operations: list[BatchOperation]) -> list[Any]:
        """Process GET operations concurrently."""
        results = []

        # Process GET operations concurrently to reduce total time
        async def get_single_object(operation: BatchOperation):
            try:
                response = self.s3_client.get_object(
                    Bucket=operation.bucket,
                    Key=operation.key
                )
                result = {
                    'operation': operation,
                    'success': True,
                    'data': response['Body'].read(),
                    'metadata': response.get('Metadata', {})
                }

                if operation.callback:
                    await operation.callback(result)

                return result

            except ClientError as e:
                error_result = {
                    'operation': operation,
                    'success': False,
                    'error': str(e)
                }

                if operation.callback:
                    await operation.callback(error_result)

                return error_result

        # Execute GET operations concurrently
        tasks = [get_single_object(op) for op in operations]
        if tasks:
            concurrent_results = await asyncio.gather(*tasks, return_exceptions=True)
            results.extend(concurrent_results)

        return results

    async def _process_put_batch(self, operations: list[BatchOperation]) -> list[Any]:
        """Process PUT operations with optimizations."""
        results = []

        for operation in operations:
            try:
                put_kwargs = {
                    'Bucket': operation.bucket,
                    'Key': operation.key,
                    'Body': operation.data,
                    'StorageClass': 'INTELLIGENT_TIERING'  # Cost optimization
                }

                if operation.metadata:
                    put_kwargs['Metadata'] = {k: str(v) for k, v in operation.metadata.items()}

                self.s3_client.put_object(**put_kwargs)

                result = {
                    'operation': operation,
                    'success': True,
                    'key': operation.key
                }

                if operation.callback:
                    await operation.callback(result)

                results.append(result)

            except ClientError as e:
                error_result = {
                    'operation': operation,
                    'success': False,
                    'error': str(e)
                }

                if operation.callback:
                    await operation.callback(error_result)

                results.append(error_result)

        return results

    async def _process_head_batch(self, operations: list[BatchOperation]) -> list[Any]:
        """Process HEAD operations concurrently."""
        results = []

        async def head_single_object(operation: BatchOperation):
            try:
                response = self.s3_client.head_object(
                    Bucket=operation.bucket,
                    Key=operation.key
                )

                result = {
                    'operation': operation,
                    'success': True,
                    'metadata': {
                        'content_length': response['ContentLength'],
                        'last_modified': response['LastModified'],
                        'etag': response['ETag'],
                        'content_type': response.get('ContentType', 'application/octet-stream'),
                        'custom_metadata': response.get('Metadata', {}),
                        'storage_class': response.get('StorageClass', 'STANDARD')
                    }
                }

                if operation.callback:
                    await operation.callback(result)

                return result

            except ClientError as e:
                error_result = {
                    'operation': operation,
                    'success': False,
                    'error': str(e)
                }

                if operation.callback:
                    await operation.callback(error_result)

                return error_result

        # Execute HEAD operations concurrently
        tasks = [head_single_object(op) for op in operations]
        if tasks:
            concurrent_results = await asyncio.gather(*tasks, return_exceptions=True)
            results.extend(concurrent_results)

        return results

    async def _process_delete_batch(self, operations: list[BatchOperation]) -> list[Any]:
        """Process DELETE operations using batch delete API."""
        if not operations:
            return []

        # Group by bucket for batch delete
        buckets = {}
        for operation in operations:
            if operation.bucket not in buckets:
                buckets[operation.bucket] = []
            buckets[operation.bucket].append(operation)

        results = []

        for bucket, bucket_operations in buckets.items():
            try:
                # Use S3 batch delete API for efficiency
                delete_keys = [{'Key': op.key} for op in bucket_operations]

                response = self.s3_client.delete_objects(
                    Bucket=bucket,
                    Delete={'Objects': delete_keys}
                )

                # Process successful deletions
                deleted_keys = {obj['Key'] for obj in response.get('Deleted', [])}

                for operation in bucket_operations:
                    success = operation.key in deleted_keys
                    result = {
                        'operation': operation,
                        'success': success,
                        'key': operation.key
                    }

                    if not success:
                        # Check if there was an error for this specific key
                        errors = response.get('Errors', [])
                        error_for_key = next(
                            (err for err in errors if err.get('Key') == operation.key),
                            None
                        )
                        if error_for_key:
                            result['error'] = error_for_key.get('Message', 'Unknown error')

                    if operation.callback:
                        await operation.callback(result)

                    results.append(result)

            except ClientError as e:
                # If batch delete fails, mark all operations as failed
                for operation in bucket_operations:
                    error_result = {
                        'operation': operation,
                        'success': False,
                        'error': str(e)
                    }

                    if operation.callback:
                        await operation.callback(error_result)

                    results.append(error_result)

        return results

    async def force_flush(self) -> list[Any]:
        """Force processing of all pending operations.

        Returns:
            List of operation results
        """
        return await self._flush_batch()

    def get_stats(self) -> dict[str, Any]:
        """Get batch processing statistics.

        Returns:
            Statistics about batch operations
        """
        efficiency = 0
        if self.stats['total_operations'] > 0:
            efficiency = (self.stats['api_calls_saved'] / self.stats['total_operations']) * 100

        return {
            **self.stats,
            'pending_operations': len(self._pending_operations),
            'efficiency_percent': round(efficiency, 2),
            'avg_operations_per_batch': (
                self.stats['total_operations'] / max(1, self.stats['batches_processed'])
            )
        }

    async def cleanup(self) -> None:
        """Cleanup and process any remaining operations."""
        if self._pending_operations:
            await self.force_flush()

        logger.info(f"Batch processor cleanup complete. Final stats: {self.get_stats()}")


# Convenience functions for common use cases
async def batch_get_objects(
    s3_client: Any,
    bucket: str,
    keys: list[str],
    batch_size: int = 10
) -> list[dict[str, Any]]:
    """Batch get multiple S3 objects efficiently.

    Args:
        s3_client: Boto3 S3 client
        bucket: S3 bucket name
        keys: List of object keys to retrieve
        batch_size: Maximum concurrent operations

    Returns:
        List of operation results
    """
    processor = S3BatchProcessor(s3_client, batch_size)

    operations = [
        BatchOperation(
            operation_type='get',
            bucket=bucket,
            key=key
        )
        for key in keys
    ]

    for operation in operations:
        await processor.add_operation(operation)

    results = await processor.force_flush()
    await processor.cleanup()

    return results


async def batch_check_objects_exist(
    s3_client: Any,
    bucket: str,
    keys: list[str],
    batch_size: int = 20
) -> dict[str, bool]:
    """Batch check if multiple S3 objects exist.

    Args:
        s3_client: Boto3 S3 client
        bucket: S3 bucket name
        keys: List of object keys to check
        batch_size: Maximum concurrent operations

    Returns:
        Dictionary mapping keys to existence status
    """
    processor = S3BatchProcessor(s3_client, batch_size)

    operations = [
        BatchOperation(
            operation_type='head',
            bucket=bucket,
            key=key
        )
        for key in keys
    ]

    for operation in operations:
        await processor.add_operation(operation)

    results = await processor.force_flush()
    await processor.cleanup()

    # Convert results to existence map
    existence_map = {}
    for result in results:
        if isinstance(result, dict) and 'operation' in result:
            key = result['operation'].key
            exists = result['success'] and result.get('error', '') != '404'
            existence_map[key] = exists

    return existence_map
