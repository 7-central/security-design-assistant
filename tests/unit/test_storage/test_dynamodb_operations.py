import json
import os
import time
from unittest.mock import MagicMock, patch

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_dynamodb, mock_s3

from src.storage.aws_storage import AWSStorage


@pytest.mark.unit
class TestAWSStorageDynamoDBOperations:
    """Test cases for AWS storage DynamoDB operations."""

    @pytest.fixture
    def aws_storage(self, mock_dynamodb_table, mock_s3_bucket):
        """Create AWSStorage instance with mocked AWS services."""
        with patch.dict('os.environ', {
            'S3_BUCKET': 'test-bucket',
            'DYNAMODB_TABLE': 'test-jobs-table',
            'AWS_ACCESS_KEY_ID': 'testing',
            'AWS_SECRET_ACCESS_KEY': 'testing',
            'AWS_DEFAULT_REGION': 'us-east-1'
        }):
            return AWSStorage()

    @pytest.fixture
    def sample_job_data(self):
        """Sample job data for testing."""
        return {
            'job_id': 'job_1234567890',
            'company_client_job': '7central#test_client#job_1234567890',
            'status': 'processing',
            'client_name': 'Test Client',
            'project_name': 'Test Project',
            'created_at': int(time.time()),
            'metadata': {
                'file_name': 'drawing.pdf',
                'file_size_mb': 2.5
            },
            'processing_results': {
                'schedule_agent': {
                    'completed': True,
                    'components': []
                }
            }
        }

    @pytest.mark.asyncio
    async def test_save_job_status_success(self, aws_storage, sample_job_data):
        """Test successful job status save to DynamoDB."""
        
        # Act
        await aws_storage.save_job_status(sample_job_data['job_id'], sample_job_data)
        
        # Assert - retrieve the item directly from DynamoDB to verify
        response = aws_storage.jobs_table.get_item(
            Key={'company#client#job': sample_job_data['company_client_job']}
        )
        
        assert 'Item' in response
        item = response['Item']
        assert item['job_id'] == sample_job_data['job_id']
        assert item['status'] == sample_job_data['status']
        assert item['client_name'] == sample_job_data['client_name']
        assert 'ttl' in item  # TTL should be set
        assert 'updated_at' in item  # Should be added during save

    @pytest.mark.asyncio
    async def test_save_job_status_with_date_bucket(self, aws_storage):
        """Test job status save with date bucket creation for GSI3."""
        
        # Arrange
        job_data = {
            'job_id': 'job_test',
            'company_client_job': '7central#client#job_test',
            'status': 'queued',
            'client_name': 'Test Client',
            'created_at': 1640995200  # 2022-01-01 00:00:00 UTC
        }
        
        # Act
        await aws_storage.save_job_status(job_data['job_id'], job_data)
        
        # Assert
        response = aws_storage.jobs_table.get_item(
            Key={'company#client#job': job_data['company_client_job']}
        )
        
        item = response['Item']
        assert item['date_bucket'] == '2022-01'  # YYYY-MM format

    @pytest.mark.asyncio
    async def test_get_job_status_success(self, aws_storage, sample_job_data):
        """Test successful job status retrieval."""
        
        # Arrange - save job first
        await aws_storage.save_job_status(sample_job_data['job_id'], sample_job_data)
        
        # Act
        result = await aws_storage.get_job_status(sample_job_data['job_id'])
        
        # Assert
        assert result is not None
        assert result['job_id'] == sample_job_data['job_id']
        assert result['status'] == sample_job_data['status']
        assert result['client_name'] == sample_job_data['client_name']

    @pytest.mark.asyncio
    async def test_get_job_status_not_found(self, aws_storage):
        """Test job status retrieval for non-existent job."""
        
        # Act
        result = await aws_storage.get_job_status('non_existent_job')
        
        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_job_by_composite_key_success(self, aws_storage, sample_job_data):
        """Test retrieval by composite key."""
        
        # Arrange
        await aws_storage.save_job_status(sample_job_data['job_id'], sample_job_data)
        
        # Act
        result = await aws_storage.get_job_by_composite_key(sample_job_data['company_client_job'])
        
        # Assert
        assert result is not None
        assert result['job_id'] == sample_job_data['job_id']
        assert result['status'] == sample_job_data['status']

    @pytest.mark.asyncio
    async def test_get_job_by_composite_key_not_found(self, aws_storage):
        """Test composite key retrieval for non-existent job."""
        
        # Act
        result = await aws_storage.get_job_by_composite_key('7central#nonexistent#job_999')
        
        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_query_jobs_by_status(self, aws_storage):
        """Test querying jobs by status using GSI1."""
        
        # Arrange - create multiple jobs with different statuses
        jobs = [
            {
                'job_id': 'job_001',
                'company_client_job': '7central#client1#job_001',
                'status': 'completed',
                'client_name': 'Client 1',
                'created_at': int(time.time()) - 100
            },
            {
                'job_id': 'job_002',
                'company_client_job': '7central#client2#job_002',
                'status': 'completed',
                'client_name': 'Client 2',
                'created_at': int(time.time()) - 50
            },
            {
                'job_id': 'job_003',
                'company_client_job': '7central#client3#job_003',
                'status': 'processing',
                'client_name': 'Client 3',
                'created_at': int(time.time())
            }
        ]
        
        for job in jobs:
            await aws_storage.save_job_status(job['job_id'], job)
        
        # Act
        completed_jobs = await aws_storage.query_jobs_by_status('completed')
        processing_jobs = await aws_storage.query_jobs_by_status('processing')
        
        # Assert
        assert len(completed_jobs) == 2
        assert len(processing_jobs) == 1
        
        # Verify ordering (should be descending by created_at)
        assert completed_jobs[0]['job_id'] == 'job_002'  # More recent
        assert completed_jobs[1]['job_id'] == 'job_001'  # Older

    @pytest.mark.asyncio
    async def test_query_jobs_by_client(self, aws_storage):
        """Test querying jobs by client using GSI2."""
        
        # Arrange
        jobs = [
            {
                'job_id': 'job_001',
                'company_client_job': '7central#test_client#job_001',
                'status': 'completed',
                'client_name': 'test_client',
                'created_at': int(time.time()) - 100
            },
            {
                'job_id': 'job_002',
                'company_client_job': '7central#test_client#job_002',
                'status': 'processing',
                'client_name': 'test_client',
                'created_at': int(time.time()) - 50
            },
            {
                'job_id': 'job_003',
                'company_client_job': '7central#other_client#job_003',
                'status': 'completed',
                'client_name': 'other_client',
                'created_at': int(time.time())
            }
        ]
        
        for job in jobs:
            await aws_storage.save_job_status(job['job_id'], job)
        
        # Act
        test_client_jobs = await aws_storage.query_jobs_by_client('test_client')
        other_client_jobs = await aws_storage.query_jobs_by_client('other_client')
        
        # Assert
        assert len(test_client_jobs) == 2
        assert len(other_client_jobs) == 1
        
        # Verify all jobs belong to the correct client
        for job in test_client_jobs:
            assert job['client_name'] == 'test_client'

    @pytest.mark.asyncio
    async def test_query_jobs_by_date_range(self, aws_storage):
        """Test querying jobs by date range using GSI3."""
        
        # Arrange
        jobs = [
            {
                'job_id': 'job_jan',
                'company_client_job': '7central#client#job_jan',
                'status': 'completed',
                'client_name': 'client',
                'created_at': 1640995200  # 2022-01-01
            },
            {
                'job_id': 'job_feb',
                'company_client_job': '7central#client#job_feb',
                'status': 'completed',
                'client_name': 'client',
                'created_at': 1643673600  # 2022-02-01
            }
        ]
        
        for job in jobs:
            await aws_storage.save_job_status(job['job_id'], job)
        
        # Act
        jan_jobs = await aws_storage.query_jobs_by_date_range('2022-01')
        feb_jobs = await aws_storage.query_jobs_by_date_range('2022-02')
        march_jobs = await aws_storage.query_jobs_by_date_range('2022-03')
        
        # Assert
        assert len(jan_jobs) == 1
        assert len(feb_jobs) == 1
        assert len(march_jobs) == 0
        
        assert jan_jobs[0]['job_id'] == 'job_jan'
        assert feb_jobs[0]['job_id'] == 'job_feb'

    @pytest.mark.asyncio
    async def test_ttl_automatic_setting(self, aws_storage):
        """Test that TTL is automatically set for 30 days."""
        
        # Arrange
        job_data = {
            'job_id': 'job_ttl_test',
            'company_client_job': '7central#client#job_ttl_test',
            'status': 'queued'
        }
        
        save_time = int(time.time())
        
        # Act
        await aws_storage.save_job_status(job_data['job_id'], job_data)
        
        # Assert
        response = aws_storage.jobs_table.get_item(
            Key={'company#client#job': job_data['company_client_job']}
        )
        
        item = response['Item']
        ttl_value = item['ttl']
        
        # TTL should be approximately 30 days from now (allowing some variance)
        expected_ttl = save_time + (30 * 24 * 60 * 60)
        assert abs(ttl_value - expected_ttl) < 60  # Within 1 minute

    @pytest.mark.asyncio
    async def test_custom_ttl_preserved(self, aws_storage):
        """Test that custom TTL values are preserved."""
        
        # Arrange
        custom_ttl = int(time.time()) + (7 * 24 * 60 * 60)  # 7 days
        job_data = {
            'job_id': 'job_custom_ttl',
            'company_client_job': '7central#client#job_custom_ttl',
            'status': 'queued',
            'ttl': custom_ttl
        }
        
        # Act
        await aws_storage.save_job_status(job_data['job_id'], job_data)
        
        # Assert
        response = aws_storage.jobs_table.get_item(
            Key={'company#client#job': job_data['company_client_job']}
        )
        
        item = response['Item']
        assert item['ttl'] == custom_ttl

    @pytest.mark.asyncio
    async def test_error_handling_dynamodb_failure(self, aws_storage):
        """Test error handling when DynamoDB operations fail."""
        
        # Arrange - mock table to raise exception
        aws_storage.jobs_table.put_item = MagicMock(
            side_effect=ClientError(
                error_response={'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}},
                operation_name='PutItem'
            )
        )
        
        job_data = {
            'job_id': 'job_error_test',
            'company_client_job': '7central#client#job_error_test',
            'status': 'queued'
        }
        
        # Act & Assert
        with pytest.raises(ClientError):
            await aws_storage.save_job_status(job_data['job_id'], job_data)

    @pytest.mark.asyncio
    async def test_updated_at_timestamp_set(self, aws_storage):
        """Test that updated_at timestamp is automatically set."""
        
        # Arrange
        job_data = {
            'job_id': 'job_timestamp_test',
            'company_client_job': '7central#client#job_timestamp_test',
            'status': 'queued'
        }
        
        save_time = int(time.time())
        
        # Act
        await aws_storage.save_job_status(job_data['job_id'], job_data)
        
        # Assert
        response = aws_storage.jobs_table.get_item(
            Key={'company#client#job': job_data['company_client_job']}
        )
        
        item = response['Item']
        updated_at = item['updated_at']
        
        # Should be close to current time
        assert abs(updated_at - save_time) < 5  # Within 5 seconds

    @pytest.mark.asyncio
    async def test_query_with_limit(self, aws_storage):
        """Test query operations respect the limit parameter."""
        
        # Arrange - create more jobs than the limit
        for i in range(5):
            job_data = {
                'job_id': f'job_{i:03d}',
                'company_client_job': f'7central#client#job_{i:03d}',
                'status': 'completed',
                'client_name': 'client',
                'created_at': int(time.time()) - (100 - i)  # Different timestamps
            }
            await aws_storage.save_job_status(job_data['job_id'], job_data)
        
        # Act
        limited_results = await aws_storage.query_jobs_by_status('completed', limit=3)
        
        # Assert
        assert len(limited_results) == 3

    @pytest.mark.asyncio
    async def test_date_bucket_with_iso_string(self, aws_storage):
        """Test date bucket creation with ISO string timestamp."""
        
        # Arrange
        job_data = {
            'job_id': 'job_iso_test',
            'company_client_job': '7central#client#job_iso_test',
            'status': 'queued',
            'created_at': '2022-03-15T10:30:00Z'  # ISO string
        }
        
        # Act
        await aws_storage.save_job_status(job_data['job_id'], job_data)
        
        # Assert
        response = aws_storage.jobs_table.get_item(
            Key={'company#client#job': job_data['company_client_job']}
        )
        
        item = response['Item']
        assert item['date_bucket'] == '2022-03'  # First 7 characters