import logging
import os
import time
from decimal import Decimal
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from src.storage.interface import StorageInterface

logger = logging.getLogger(__name__)


class AWSStorage(StorageInterface):
    """AWS S3 and DynamoDB implementation of storage interface."""

    def __init__(self):
        """Initialize AWS storage with S3 and DynamoDB clients with connection pooling."""
        # Configure connection pooling for better performance
        config = Config(
            max_pool_connections=50,  # Increase connection pool size
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'  # Use adaptive retry mode
            }
        )

        self.s3_client = boto3.client('s3', config=config)
        self.dynamodb = boto3.resource('dynamodb', config=config)

        # S3 metadata cache for performance optimization
        self._metadata_cache = {}
        self._cache_ttl = 300  # 5 minutes cache TTL

        # S3 batch processor for request consolidation
        self._batch_processor = None

        self.s3_bucket = os.getenv('S3_BUCKET', 'security-assistant-files')
        self.dynamodb_table_name = os.getenv('DYNAMODB_TABLE', 'security-assistant-jobs')

        # Initialize DynamoDB table reference
        try:
            self.jobs_table = self.dynamodb.Table(self.dynamodb_table_name)
        except Exception as e:
            logger.error(f"Failed to initialize DynamoDB table {self.dynamodb_table_name}: {e}")
            raise

    async def save_file(self, key: str, content: bytes, metadata: dict[str, Any] | None = None) -> str:
        """
        Save a file to S3.

        Args:
            key: S3 object key
            content: File content as bytes
            metadata: Optional metadata to store with the file

        Returns:
            S3 object URL
        """
        try:
            extra_args = {}
            if metadata:
                extra_args['Metadata'] = {k: str(v) for k, v in metadata.items()}

            # Use Intelligent Tiering for cost optimization
            extra_args['StorageClass'] = 'INTELLIGENT_TIERING'

            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=key,
                Body=content,
                **extra_args
            )

            # Cache metadata for performance
            if metadata:
                self._cache_metadata(key, metadata)

            logger.info(f"Successfully uploaded file to S3: s3://{self.s3_bucket}/{key}")
            return f"s3://{self.s3_bucket}/{key}"

        except ClientError as e:
            logger.error(f"Failed to upload file to S3: {e}")
            raise

    async def get_file(self, key: str) -> bytes:
        """
        Retrieve a file from S3.

        Args:
            key: S3 object key

        Returns:
            File content as bytes
        """
        try:
            response = self.s3_client.get_object(
                Bucket=self.s3_bucket,
                Key=key
            )
            content = response['Body'].read()
            logger.info(f"Successfully retrieved file from S3: s3://{self.s3_bucket}/{key}")
            return content

        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                raise FileNotFoundError(f"File not found: {key}")
            logger.error(f"Failed to retrieve file from S3: {e}")
            raise

    async def file_exists(self, key: str) -> bool:
        """
        Check if a file exists in S3.

        Args:
            key: S3 object key

        Returns:
            True if file exists, False otherwise
        """
        try:
            self.s3_client.head_object(
                Bucket=self.s3_bucket,
                Key=key
            )
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            logger.error(f"Error checking file existence in S3: {e}")
            raise

    async def delete_file(self, key: str) -> bool:
        """
        Delete a file from S3.

        Args:
            key: S3 object key

        Returns:
            True if file was deleted, False if it didn't exist
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.s3_bucket,
                Key=key
            )
            logger.info(f"Successfully deleted file from S3: s3://{self.s3_bucket}/{key}")
            return True

        except ClientError as e:
            logger.error(f"Failed to delete file from S3: {e}")
            raise

    def _convert_floats_to_decimal(self, obj: Any) -> Any:
        """Convert floats to Decimal for DynamoDB compatibility.

        Args:
            obj: Object to convert

        Returns:
            Object with floats converted to Decimal
        """
        if isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, dict):
            return {k: self._convert_floats_to_decimal(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_floats_to_decimal(v) for v in obj]
        return obj

    async def save_job_status(self, job_id: str, status_data: dict[str, Any]) -> None:
        """
        Save job status to DynamoDB.

        Args:
            job_id: Unique job identifier
            status_data: Job status data to store
        """
        try:
            # Create the composite key for the job
            company_client_job = status_data.get('company_client_job', f"7central#unknown#{job_id}")

            # Prepare the item for DynamoDB
            item = {
                'company#client#job': company_client_job,
                'job_id': job_id,
                'updated_at': int(time.time()),
                **status_data
            }

            # Convert floats to Decimal for DynamoDB compatibility
            item = self._convert_floats_to_decimal(item)

            # Set TTL for 30 days (30 * 24 * 60 * 60 seconds)
            if 'ttl' not in item:
                item['ttl'] = int(time.time()) + (30 * 24 * 60 * 60)

            # Create date bucket for GSI3 (YYYY-MM format)
            if 'created_at' in status_data:
                created_timestamp = status_data['created_at']
                if isinstance(created_timestamp, (int, float)):
                    # Convert timestamp to YYYY-MM format
                    import datetime
                    date_obj = datetime.datetime.fromtimestamp(created_timestamp)
                    item['date_bucket'] = date_obj.strftime('%Y-%m')
                elif isinstance(created_timestamp, str):
                    # Assume ISO format, extract YYYY-MM
                    item['date_bucket'] = created_timestamp[:7]

            self.jobs_table.put_item(Item=item)
            logger.info(f"Successfully saved job status to DynamoDB: {job_id}")

        except Exception as e:
            logger.error(f"Failed to save job status to DynamoDB: {e}")
            raise

    async def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """
        Retrieve job status from DynamoDB.

        Args:
            job_id: Unique job identifier

        Returns:
            Job status data if found, None otherwise
        """
        try:
            # Since we need the full composite key, we'll use a GSI query instead
            # Query the StatusDateIndex to find the job by job_id
            response = self.jobs_table.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr('job_id').eq(job_id),
                Limit=1
            )

            items = response.get('Items', [])
            if not items:
                return None

            item = items[0]
            logger.info(f"Successfully retrieved job status from DynamoDB: {job_id}")
            return dict(item)

        except Exception as e:
            logger.error(f"Failed to retrieve job status from DynamoDB: {e}")
            raise

    async def get_job_by_composite_key(self, company_client_job: str) -> dict[str, Any] | None:
        """
        Retrieve job status using the composite key directly.

        Args:
            company_client_job: The composite key (company#client#job format)

        Returns:
            Job status data if found, None otherwise
        """
        try:
            response = self.jobs_table.get_item(
                Key={'company#client#job': company_client_job}
            )

            item = response.get('Item')
            if item:
                logger.info(f"Successfully retrieved job by composite key: {company_client_job}")
                return dict(item)
            return None

        except Exception as e:
            logger.error(f"Failed to retrieve job by composite key: {e}")
            raise

    async def generate_presigned_url(self, key: str, expiration: int = 3600) -> str:
        """
        Generate a presigned URL for S3 object access.

        Args:
            key: S3 object key
            expiration: URL expiration time in seconds (default: 1 hour)

        Returns:
            Presigned URL for file access
        """
        try:
            response = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.s3_bucket, 'Key': key},
                ExpiresIn=expiration
            )
            logger.info(f"Generated presigned URL for: s3://{self.s3_bucket}/{key}")
            return response

        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise

    async def query_jobs_by_status(self, status: str, limit: int = 100) -> list[dict[str, Any]]:
        """
        Query jobs by status using GSI1.

        Args:
            status: Job status to filter by
            limit: Maximum number of results to return

        Returns:
            List of job status records
        """
        try:
            response = self.jobs_table.query(
                IndexName='StatusDateIndex',
                KeyConditionExpression=boto3.dynamodb.conditions.Key('status').eq(status),
                ScanIndexForward=False,  # Sort by created_at descending
                Limit=limit
            )

            items = response.get('Items', [])
            logger.info(f"Retrieved {len(items)} jobs with status: {status}")
            return [dict(item) for item in items]

        except Exception as e:
            logger.error(f"Failed to query jobs by status: {e}")
            raise

    async def query_jobs_by_client(self, client_name: str, limit: int = 100) -> list[dict[str, Any]]:
        """
        Query jobs by client using GSI2.

        Args:
            client_name: Client name to filter by
            limit: Maximum number of results to return

        Returns:
            List of job status records
        """
        try:
            response = self.jobs_table.query(
                IndexName='ClientProjectIndex',
                KeyConditionExpression=boto3.dynamodb.conditions.Key('client_name').eq(client_name),
                ScanIndexForward=False,  # Sort by created_at descending
                Limit=limit
            )

            items = response.get('Items', [])
            logger.info(f"Retrieved {len(items)} jobs for client: {client_name}")
            return [dict(item) for item in items]

        except Exception as e:
            logger.error(f"Failed to query jobs by client: {e}")
            raise

    async def query_jobs_by_date_range(self, date_bucket: str, limit: int = 100) -> list[dict[str, Any]]:
        """
        Query jobs by date range using GSI3.

        Args:
            date_bucket: Date bucket in YYYY-MM format
            limit: Maximum number of results to return

        Returns:
            List of job status records
        """
        try:
            response = self.jobs_table.query(
                IndexName='DateRangeIndex',
                KeyConditionExpression=boto3.dynamodb.conditions.Key('date_bucket').eq(date_bucket),
                ScanIndexForward=False,  # Sort by created_at descending
                Limit=limit
            )

            items = response.get('Items', [])
            logger.info(f"Retrieved {len(items)} jobs for date bucket: {date_bucket}")
            return [dict(item) for item in items]

        except Exception as e:
            logger.error(f"Failed to query jobs by date range: {e}")
            raise

    async def update_job_stage_progress(
        self,
        job_id: str,
        current_stage: str,
        stages_completed: list[str],
        additional_data: dict[str, Any] | None = None
    ) -> None:
        """
        Update job progress with stage-based tracking.

        Args:
            job_id: Unique job identifier
            current_stage: Current processing stage
            stages_completed: List of completed stages
            additional_data: Optional additional data to update
        """
        try:
            # Get current job data
            current_job = await self.get_job_status(job_id)
            if not current_job:
                logger.warning(f"Job {job_id} not found when updating stage progress")
                return

            # Update stage progress
            update_data = {
                "current_stage": current_stage,
                "stages_completed": stages_completed,
                "last_checkpoint": int(time.time()),
                "updated_at": int(time.time())
            }

            if additional_data:
                update_data.update(additional_data)

            # Merge with current job data
            current_job.update(update_data)

            # Save updated job data
            await self.save_job_status(job_id, current_job)
            logger.info(f"Updated stage progress for job {job_id}: {current_stage}")

        except Exception as e:
            logger.error(f"Failed to update job stage progress: {e}")
            raise

    async def get_jobs_by_stage(self, stage: str, limit: int = 100) -> list[dict[str, Any]]:
        """
        Query jobs by current processing stage.

        Args:
            stage: Processing stage to filter by
            limit: Maximum number of results to return

        Returns:
            List of job records in the specified stage
        """
        try:
            response = self.jobs_table.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr('current_stage').eq(stage),
                Limit=limit
            )

            items = response.get('Items', [])
            logger.info(f"Retrieved {len(items)} jobs in stage: {stage}")
            return [dict(item) for item in items]

        except Exception as e:
            logger.error(f"Failed to query jobs by stage: {e}")
            raise

    async def get_interrupted_jobs(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Query jobs that were interrupted (have timeout_detected flag).

        Args:
            limit: Maximum number of results to return

        Returns:
            List of interrupted job records
        """
        try:
            response = self.jobs_table.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr('timeout_detected').eq(True),
                Limit=limit
            )

            items = response.get('Items', [])
            logger.info(f"Retrieved {len(items)} interrupted jobs")
            return [dict(item) for item in items]

        except Exception as e:
            logger.error(f"Failed to query interrupted jobs: {e}")
            raise

    async def cleanup_expired_jobs(self, days_old: int = 30) -> int:
        """
        Clean up jobs older than specified days.

        Args:
            days_old: Number of days to keep jobs

        Returns:
            Number of jobs cleaned up
        """
        try:
            cutoff_time = int(time.time()) - (days_old * 24 * 60 * 60)

            # Query jobs older than cutoff time
            response = self.jobs_table.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr('created_at').lt(cutoff_time),
                ProjectionExpression='#ccj',
                ExpressionAttributeNames={'#ccj': 'company#client#job'}
            )

            items = response.get('Items', [])
            cleanup_count = 0

            # Delete old job records
            for item in items:
                try:
                    self.jobs_table.delete_item(
                        Key={'company#client#job': item['company#client#job']}
                    )
                    cleanup_count += 1
                except Exception as e:
                    logger.error(f"Failed to delete job record {item['company#client#job']}: {e}")

            logger.info(f"Cleaned up {cleanup_count} expired jobs older than {days_old} days")
            return cleanup_count

        except Exception as e:
            logger.error(f"Failed to cleanup expired jobs: {e}")
            raise

    def _cache_metadata(self, key: str, metadata: dict[str, Any]) -> None:
        """Cache S3 object metadata for performance optimization.

        Args:
            key: S3 object key
            metadata: Metadata to cache
        """
        cache_entry = {
            'metadata': metadata,
            'timestamp': time.time(),
            'key': key
        }
        self._metadata_cache[key] = cache_entry
        logger.debug(f"Cached metadata for S3 object: {key}")

    def _get_cached_metadata(self, key: str) -> dict[str, Any] | None:
        """Retrieve cached metadata if available and not expired.

        Args:
            key: S3 object key

        Returns:
            Cached metadata if available, None otherwise
        """
        if key not in self._metadata_cache:
            return None

        cache_entry = self._metadata_cache[key]
        cache_age = time.time() - cache_entry['timestamp']

        if cache_age > self._cache_ttl:
            # Cache expired, remove it
            del self._metadata_cache[key]
            logger.debug(f"Cache expired for S3 object: {key}")
            return None

        logger.debug(f"Cache hit for S3 object metadata: {key}")
        return cache_entry['metadata']

    async def get_object_metadata(self, key: str, use_cache: bool = True) -> dict[str, Any] | None:
        """Get S3 object metadata with optional caching.

        Args:
            key: S3 object key
            use_cache: Whether to use cached metadata

        Returns:
            Object metadata if available, None otherwise
        """
        # Check cache first if enabled
        if use_cache:
            cached_metadata = self._get_cached_metadata(key)
            if cached_metadata is not None:
                return cached_metadata

        try:
            response = self.s3_client.head_object(
                Bucket=self.s3_bucket,
                Key=key
            )

            metadata = {
                'content_length': response['ContentLength'],
                'last_modified': response['LastModified'],
                'etag': response['ETag'],
                'content_type': response.get('ContentType', 'application/octet-stream'),
                'metadata': response.get('Metadata', {}),
                'storage_class': response.get('StorageClass', 'STANDARD')
            }

            # Cache the metadata
            if use_cache:
                self._cache_metadata(key, metadata)

            logger.info(f"Retrieved metadata for S3 object: {key}")
            return metadata

        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.warning(f"S3 object not found: {key}")
                return None
            logger.error(f"Failed to get S3 object metadata: {e}")
            raise

    def clear_metadata_cache(self) -> None:
        """Clear the metadata cache."""
        self._metadata_cache.clear()
        logger.info("S3 metadata cache cleared")

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics for monitoring.

        Returns:
            Cache statistics
        """
        current_time = time.time()
        active_entries = 0
        expired_entries = 0

        for cache_entry in self._metadata_cache.values():
            cache_age = current_time - cache_entry['timestamp']
            if cache_age <= self._cache_ttl:
                active_entries += 1
            else:
                expired_entries += 1

        return {
            'total_entries': len(self._metadata_cache),
            'active_entries': active_entries,
            'expired_entries': expired_entries,
            'cache_ttl_seconds': self._cache_ttl
        }

    def _get_batch_processor(self):
        """Get or create S3 batch processor for request consolidation."""
        if self._batch_processor is None:
            from src.utils.s3_batch_operations import S3BatchProcessor
            self._batch_processor = S3BatchProcessor(
                self.s3_client,
                batch_size=15,  # Optimize batch size for Lambda
                flush_interval=2.0  # Shorter interval for Lambda execution
            )
        return self._batch_processor

    async def batch_check_files_exist(self, keys: list[str]) -> dict[str, bool]:
        """Check if multiple files exist using batch operations for cost optimization.

        Args:
            keys: List of S3 object keys to check

        Returns:
            Dictionary mapping keys to existence status
        """
        from src.utils.s3_batch_operations import batch_check_objects_exist

        try:
            existence_map = await batch_check_objects_exist(
                self.s3_client,
                self.s3_bucket,
                keys,
                batch_size=20  # Higher batch size for HEAD operations
            )

            logger.info(f"Batch checked existence of {len(keys)} files")
            return existence_map

        except Exception as e:
            logger.error(f"Failed to batch check file existence: {e}")
            raise

    async def batch_get_files(self, keys: list[str]) -> list[dict[str, Any]]:
        """Get multiple files using batch operations for cost optimization.

        Args:
            keys: List of S3 object keys to retrieve

        Returns:
            List of file retrieval results
        """
        from src.utils.s3_batch_operations import batch_get_objects

        try:
            results = await batch_get_objects(
                self.s3_client,
                self.s3_bucket,
                keys,
                batch_size=10  # Conservative batch size for GET operations
            )

            logger.info(f"Batch retrieved {len(keys)} files")
            return results

        except Exception as e:
            logger.error(f"Failed to batch get files: {e}")
            raise

    async def get_batch_stats(self) -> dict[str, Any]:
        """Get S3 batch operation statistics.

        Returns:
            Batch operation statistics
        """
        if self._batch_processor is None:
            return {
                'batch_processor_initialized': False,
                'total_operations': 0,
                'batches_processed': 0,
                'api_calls_saved': 0,
                'efficiency_percent': 0
            }

        stats = self._batch_processor.get_stats()
        stats['batch_processor_initialized'] = True
        return stats
