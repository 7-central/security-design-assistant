"""
Unit tests for DLQ processor Lambda function.
"""

import json
import time
from unittest.mock import AsyncMock, Mock, patch
import pytest

from src.lambda_functions.dlq_processor import (
    handler,
    process_failed_job,
    analyze_failure,
    classify_failure_type,
    generate_error_summary,
    is_critical_failure,
    update_failed_job_status,
    send_critical_failure_alert
)
from src.models.job import JobStatus


class TestDLQProcessorHandler:
    """Test DLQ processor Lambda handler."""
    
    @patch('src.lambda_functions.dlq_processor.StorageManager')
    @patch('src.lambda_functions.dlq_processor.boto3')
    def test_handler_success(self, mock_boto3, mock_storage_manager):
        """Test successful DLQ message processing."""
        # Mock storage
        mock_storage = Mock()
        mock_storage_manager.get_storage.return_value = mock_storage
        
        # Mock SNS client
        mock_sns_client = Mock()
        mock_boto3.client.return_value = mock_sns_client
        
        # Mock event with SQS records
        event = {
            'Records': [
                {
                    'body': json.dumps({
                        'job_id': 'job_123',
                        'company_client_job': '7central#client#job_123'
                    }),
                    'attributes': {
                        'ApproximateReceiveCount': '3',
                        'SentTimestamp': str(int(time.time() - 300) * 1000),
                        'ApproximateFirstReceiveTimestamp': str(int(time.time() - 280) * 1000)
                    }
                }
            ]
        }
        
        mock_context = Mock()
        
        with patch('src.lambda_functions.dlq_processor.await_sync') as mock_await_sync:
            mock_await_sync.return_value = {
                'job_id': 'job_123',
                'action': 'logged',
                'failure_type': 'processing_failure'
            }
            
            response = handler(event, mock_context)
        
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['processed_records'] == 1
        assert len(body['results']) == 1
        assert body['results'][0]['job_id'] == 'job_123'
        assert body['results'][0]['status'] == 'processed'
    
    @patch('src.lambda_functions.dlq_processor.StorageManager')
    @patch('src.lambda_functions.dlq_processor.boto3')
    def test_handler_with_processing_error(self, mock_boto3, mock_storage_manager):
        """Test DLQ handler with processing errors."""
        # Mock storage
        mock_storage = Mock()
        mock_storage_manager.get_storage.return_value = mock_storage
        
        # Mock SNS client
        mock_sns_client = Mock()
        mock_boto3.client.return_value = mock_sns_client
        
        # Event with malformed JSON
        event = {
            'Records': [
                {
                    'body': 'invalid json',
                    'attributes': {}
                }
            ]
        }
        
        mock_context = Mock()
        response = handler(event, mock_context)
        
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['processed_records'] == 1
        assert body['results'][0]['status'] == 'error'


class TestFailureAnalysis:
    """Test failure analysis functions."""
    
    def test_analyze_failure_basic(self):
        """Test basic failure analysis."""
        sqs_record = {
            'attributes': {
                'ApproximateReceiveCount': '3',
                'SentTimestamp': str(int((time.time() - 600) * 1000)),  # 10 minutes ago
                'ApproximateFirstReceiveTimestamp': str(int((time.time() - 580) * 1000))  # 9:40 ago
            },
            'messageAttributes': {
                'job_id': {'stringValue': 'job_123'}
            }
        }
        
        message_body = {
            'job_id': 'job_123',
            'client_name': 'test_client'
        }
        
        analysis = analyze_failure(sqs_record, message_body)
        
        assert analysis['failure_type'] in ['processing_failure', 'temporary_failure']
        assert analysis['receive_count'] == 3
        assert analysis['processing_duration_seconds'] == 20  # 600 - 580
        assert 'error_summary' in analysis
        assert 'original_message' in analysis
    
    def test_classify_failure_type_timeout(self):
        """Test classification of timeout failures."""
        failure_type = classify_failure_type(
            receive_count=1,
            processing_duration=880.0,  # Close to 15-minute limit
            message_body={'job_id': 'job_123'}
        )
        
        assert failure_type == 'lambda_timeout'
    
    def test_classify_failure_type_rate_limit(self):
        """Test classification of rate limit failures."""
        failure_type = classify_failure_type(
            receive_count=2,
            processing_duration=450.0,  # 7.5 minutes - suggests rate limiting
            message_body={'job_id': 'job_123'}
        )
        
        assert failure_type == 'rate_limit_exhausted'
    
    def test_classify_failure_type_resource_exhausted(self):
        """Test classification of resource exhaustion."""
        failure_type = classify_failure_type(
            receive_count=3,
            processing_duration=30.0,  # Quick failure after retries
            message_body={'job_id': 'job_123'}
        )
        
        assert failure_type == 'resource_exhausted'
    
    def test_classify_failure_type_input_validation(self):
        """Test classification of input validation failures."""
        failure_type = classify_failure_type(
            receive_count=2,
            processing_duration=60.0,
            message_body={'job_id': 'job_123', 'client_name': 'test_client'}
        )
        
        assert failure_type == 'input_validation_failure'
    
    def test_generate_error_summary(self):
        """Test error summary generation."""
        summary = generate_error_summary('lambda_timeout', 1, 850.0)
        assert 'timeout limit' in summary.lower()
        assert '850.0s' in summary
        
        summary = generate_error_summary('rate_limit_exhausted', 3, 300.0)
        assert 'rate limit exhausted' in summary.lower()
        assert '3 attempts' in summary
    
    def test_is_critical_failure(self):
        """Test critical failure detection."""
        # Infrastructure failure should be critical
        critical_analysis = {
            'failure_type': 'infrastructure_failure',
            'receive_count': 1
        }
        assert is_critical_failure(critical_analysis) is True
        
        # High retry count should be critical
        high_retry_analysis = {
            'failure_type': 'processing_failure',
            'receive_count': 3
        }
        assert is_critical_failure(high_retry_analysis) is True
        
        # Temporary failure should not be critical
        temp_analysis = {
            'failure_type': 'temporary_failure',
            'receive_count': 1
        }
        assert is_critical_failure(temp_analysis) is False


class TestJobStatusUpdate:
    """Test job status update functionality."""
    
    @pytest.mark.asyncio
    async def test_update_failed_job_status_success(self):
        """Test successful job status update to failed."""
        mock_storage = Mock()
        current_job = {
            'job_id': 'job_123',
            'status': 'processing',
            'stages_completed': ['pdf_processing'],
            'current_stage': 'drawing_analysis'
        }
        mock_storage.get_job_status = AsyncMock(return_value=current_job)
        mock_storage.save_job_status = AsyncMock()
        
        failure_analysis = {
            'failure_type': 'lambda_timeout',
            'error_summary': 'Job exceeded timeout',
            'timestamp': int(time.time())
        }
        
        await update_failed_job_status(
            mock_storage,
            'job_123',
            failure_analysis,
            'corr_123'
        )
        
        # Verify save_job_status was called
        mock_storage.save_job_status.assert_called_once()
        
        # Check the updated job data
        call_args = mock_storage.save_job_status.call_args
        updated_job = call_args[0][1]  # Second argument is the job data
        
        assert updated_job['status'] == JobStatus.FAILED.value
        assert updated_job['dlq_processed'] is True
        assert updated_job['failure_details'] == failure_analysis
        assert updated_job['correlation_id'] == 'corr_123'
        assert updated_job['failed_stage'] == 'drawing_analysis'
        assert updated_job['current_stage'] is None
        assert updated_job['stages_completed'] == ['pdf_processing']
    
    @pytest.mark.asyncio
    async def test_update_failed_job_status_job_not_found(self):
        """Test job status update when job is not found."""
        mock_storage = Mock()
        mock_storage.get_job_status = AsyncMock(return_value=None)
        mock_storage.save_job_status = AsyncMock()
        
        failure_analysis = {'failure_type': 'processing_failure'}
        
        # Should not raise exception
        await update_failed_job_status(
            mock_storage,
            'nonexistent_job',
            failure_analysis,
            'corr_123'
        )
        
        # Should not attempt to save
        mock_storage.save_job_status.assert_not_called()


class TestSNSAlerts:
    """Test SNS alert functionality."""
    
    @pytest.mark.asyncio
    @patch('src.lambda_functions.dlq_processor.os')
    async def test_send_critical_failure_alert_success(self, mock_os):
        """Test successful SNS alert sending."""
        mock_os.getenv.return_value = 'arn:aws:sns:us-east-1:123456789012:alerts'
        
        mock_sns_client = Mock()
        mock_sns_client.publish.return_value = {'MessageId': 'msg_123'}
        
        failure_analysis = {
            'failure_type': 'infrastructure_failure',
            'error_summary': 'AWS infrastructure failure',
            'receive_count': 1,
            'processing_duration_seconds': 15.0
        }
        
        await send_critical_failure_alert(
            mock_sns_client,
            'job_123',
            failure_analysis,
            'corr_123'
        )
        
        # Verify SNS publish was called
        mock_sns_client.publish.assert_called_once()
        
        call_args = mock_sns_client.publish.call_args
        assert 'Critical job failure detected' in call_args[1]['Message']
        assert call_args[1]['Subject'].startswith('Security Design Assistant - Critical Job Failure')
        
        # Check message attributes
        msg_attrs = call_args[1]['MessageAttributes']
        assert msg_attrs['alert_type']['StringValue'] == 'critical_job_failure'
        assert msg_attrs['job_id']['StringValue'] == 'job_123'
        assert msg_attrs['failure_type']['StringValue'] == 'infrastructure_failure'
        assert msg_attrs['correlation_id']['StringValue'] == 'corr_123'
    
    @pytest.mark.asyncio
    @patch('src.lambda_functions.dlq_processor.os')
    async def test_send_critical_failure_alert_no_topic(self, mock_os):
        """Test SNS alert when topic ARN is not configured."""
        mock_os.getenv.return_value = None  # No SNS topic configured
        
        mock_sns_client = Mock()
        failure_analysis = {'failure_type': 'infrastructure_failure'}
        
        # Should not raise exception and not call publish
        await send_critical_failure_alert(
            mock_sns_client,
            'job_123',
            failure_analysis,
            'corr_123'
        )
        
        mock_sns_client.publish.assert_not_called()
    
    @pytest.mark.asyncio
    @patch('src.lambda_functions.dlq_processor.os')
    async def test_send_critical_failure_alert_sns_error(self, mock_os):
        """Test SNS alert with SNS client error."""
        mock_os.getenv.return_value = 'arn:aws:sns:us-east-1:123456789012:alerts'
        
        from botocore.exceptions import ClientError
        mock_sns_client = Mock()
        mock_sns_client.publish.side_effect = ClientError(
            {'Error': {'Code': 'InvalidParameter', 'Message': 'Invalid topic'}},
            'Publish'
        )
        
        failure_analysis = {'failure_type': 'infrastructure_failure'}
        
        # Should not raise exception (error is logged internally)
        await send_critical_failure_alert(
            mock_sns_client,
            'job_123',
            failure_analysis,
            'corr_123'
        )
        
        mock_sns_client.publish.assert_called_once()


class TestProcessFailedJob:
    """Test end-to-end failed job processing."""
    
    @pytest.mark.asyncio
    async def test_process_failed_job_with_alert(self):
        """Test processing a failed job that triggers an alert."""
        mock_storage = Mock()
        current_job = {'job_id': 'job_123', 'status': 'processing'}
        mock_storage.get_job_status = AsyncMock(return_value=current_job)
        mock_storage.save_job_status = AsyncMock()
        
        mock_sns_client = Mock()
        mock_sns_client.publish.return_value = {'MessageId': 'msg_123'}
        
        # SQS record indicating infrastructure failure
        sqs_record = {
            'attributes': {
                'ApproximateReceiveCount': '1',
                'SentTimestamp': str(int(time.time() * 1000)),
                'ApproximateFirstReceiveTimestamp': str(int((time.time() + 15) * 1000))  # Quick failure
            },
            'messageAttributes': {}
        }
        
        message_body = {
            'job_id': 'job_123',
            'company_client_job': '7central#client#job_123'
        }
        
        with patch('src.lambda_functions.dlq_processor.os.getenv', return_value='arn:aws:sns:topic'):
            result = await process_failed_job(
                mock_storage,
                mock_sns_client,
                message_body,
                sqs_record,
                'corr_123'
            )
        
        assert result['job_id'] == 'job_123'
        assert result['action'] == 'alerted'
        assert result['failure_type'] == 'infrastructure_failure'
        
        # Verify job status was updated
        mock_storage.save_job_status.assert_called()
        
        # Verify SNS alert was sent
        mock_sns_client.publish.assert_called()
    
    @pytest.mark.asyncio
    async def test_process_failed_job_without_alert(self):
        """Test processing a failed job that doesn't require an alert."""
        mock_storage = Mock()
        current_job = {'job_id': 'job_123', 'status': 'processing'}
        mock_storage.get_job_status = AsyncMock(return_value=current_job)
        mock_storage.save_job_status = AsyncMock()
        
        mock_sns_client = Mock()
        
        # SQS record indicating temporary failure
        sqs_record = {
            'attributes': {
                'ApproximateReceiveCount': '1',
                'SentTimestamp': str(int(time.time() * 1000)),
                'ApproximateFirstReceiveTimestamp': str(int((time.time() + 120) * 1000))  # 2-minute processing
            },
            'messageAttributes': {}
        }
        
        message_body = {
            'job_id': 'job_123',
            'company_client_job': '7central#client#job_123'
        }
        
        result = await process_failed_job(
            mock_storage,
            mock_sns_client,
            message_body,
            sqs_record,
            'corr_123'
        )
        
        assert result['action'] == 'logged'
        assert result['failure_type'] == 'temporary_failure'
        
        # Verify job status was updated
        mock_storage.save_job_status.assert_called()
        
        # Verify no SNS alert was sent
        mock_sns_client.publish.assert_not_called()


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_complete_dlq_processing_flow(self):
        """Test complete DLQ processing flow with realistic data."""
        # Create realistic SQS record for a job that exceeded Lambda timeout
        timestamp_now = int(time.time())
        sqs_record = {
            'body': json.dumps({
                'job_id': 'job_complex_drawing_001',
                'company_client_job': '7central#manufacturing_corp#job_complex_drawing_001',
                'drawing_s3_key': '7central/manufacturing_corp/project_alpha/job_001/complex_drawing.pdf',
                'client_name': 'manufacturing_corp',
                'project_name': 'project_alpha'
            }),
            'attributes': {
                'ApproximateReceiveCount': '3',
                'SentTimestamp': str((timestamp_now - 900) * 1000),  # 15 minutes ago
                'ApproximateFirstReceiveTimestamp': str((timestamp_now - 880) * 1000)  # Started 14:40 ago
            },
            'messageAttributes': {
                'job_id': {'stringValue': 'job_complex_drawing_001'},
                'client_name': {'stringValue': 'manufacturing_corp'}
            }
        }
        
        # Mock storage with realistic job data
        mock_storage = Mock()
        current_job = {
            'job_id': 'job_complex_drawing_001',
            'status': 'processing',
            'stages_completed': ['pdf_processing', 'context_processing'],
            'current_stage': 'drawing_analysis',
            'created_at': timestamp_now - 900,
            'metadata': {
                'client_name': 'manufacturing_corp',
                'project_name': 'project_alpha',
                'file_name': 'complex_drawing.pdf',
                'file_size_mb': 25.4
            }
        }
        mock_storage.get_job_status = AsyncMock(return_value=current_job)
        mock_storage.save_job_status = AsyncMock()
        
        # Mock SNS client
        mock_sns_client = Mock()
        mock_sns_client.publish.return_value = {'MessageId': 'alert_msg_001'}
        
        # Process the failed job
        with patch('src.lambda_functions.dlq_processor.os.getenv', return_value='arn:aws:sns:alerts'):
            result = await process_failed_job(
                mock_storage,
                mock_sns_client,
                json.loads(sqs_record['body']),
                sqs_record,
                'corr_dlq_001'
            )
        
        # Verify results
        assert result['job_id'] == 'job_complex_drawing_001'
        assert result['failure_type'] == 'lambda_timeout'  # Should detect timeout based on duration
        assert result['action'] == 'alerted'  # Should alert due to multiple retries
        
        # Verify job status update
        mock_storage.save_job_status.assert_called_once()
        updated_job_call = mock_storage.save_job_status.call_args[0][1]
        
        assert updated_job_call['status'] == JobStatus.FAILED.value
        assert updated_job_call['dlq_processed'] is True
        assert updated_job_call['failed_stage'] == 'drawing_analysis'
        assert updated_job_call['stages_completed'] == ['pdf_processing', 'context_processing']
        assert 'failure_details' in updated_job_call
        
        # Verify SNS alert
        mock_sns_client.publish.assert_called_once()
        alert_call = mock_sns_client.publish.call_args[1]
        assert 'job_complex_drawing_001' in alert_call['Message']
        assert 'lambda_timeout' in alert_call['Message']