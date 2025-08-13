import json
from unittest.mock import AsyncMock, patch

import pytest

from src.lambda_functions.process_drawing_api import handler


class TestProcessDrawingApiLambda:
    """Test cases for the process_drawing_api Lambda function."""

    @pytest.fixture
    def valid_multipart_event(self):
        """Create a valid API Gateway multipart form event."""
        # This is a simplified representation - in reality, multipart parsing is complex
        return {
            'httpMethod': 'POST',
            'headers': {
                'content-type': 'multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW'
            },
            'body': 'mock_multipart_body',
            'isBase64Encoded': False,
            'pathParameters': None,
            'queryStringParameters': None
        }

    @pytest.fixture
    def mock_pdf_content(self):
        """Mock PDF file content."""
        return b'%PDF-1.4\n%mock PDF content\n%%EOF'

    @pytest.fixture
    def mock_multipart_data(self, mock_pdf_content):
        """Mock parsed multipart form data."""
        return {
            'drawing_file': {
                'filename': 'test_drawing.pdf',
                'content_type': 'application/pdf',
                'content': mock_pdf_content
            },
            'client_name': 'Test Client',
            'project_name': 'Test Project'
        }

    @patch('src.lambda_functions.process_drawing_api.StorageManager')
    @patch('src.lambda_functions.process_drawing_api.sqs_client')
    @patch('src.lambda_functions.process_drawing_api.generate_job_id')
    @patch('src.lambda_functions.process_drawing_api.parse_multipart_request')
    @patch('src.lambda_functions.process_drawing_api.validate_file_size')
    @patch('src.lambda_functions.process_drawing_api.validate_pdf_file')
    def test_successful_job_creation(
        self,
        mock_validate_pdf,
        mock_validate_size,
        mock_parse_multipart,
        mock_generate_job_id,
        mock_sqs_client,
        mock_storage_manager,
        valid_multipart_event,
        mock_multipart_data,
        mock_pdf_content
    ):
        """Test successful job creation and SQS message sending."""

        # Arrange
        mock_job_id = "job_1234567890"
        mock_generate_job_id.return_value = mock_job_id

        mock_parse_multipart.return_value = mock_multipart_data
        mock_validate_size.return_value = (True, "")
        mock_validate_pdf.return_value = (True, "")

        mock_storage = AsyncMock()
        mock_storage.save_file.return_value = "s3://bucket/path/file.pdf"
        mock_storage_manager.get_storage.return_value = mock_storage

        mock_sqs_response = {
            'MessageId': 'test-message-id',
            'MD5OfBody': 'test-md5'
        }
        mock_sqs_client.send_message.return_value = mock_sqs_response

        # Act
        with patch('src.lambda.process_drawing_api.settings') as mock_settings:
            mock_settings.SQS_QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/123456789/test-queue'

            result = handler(valid_multipart_event, {})

        # Assert
        assert result['statusCode'] == 202

        response_body = json.loads(result['body'])
        assert response_body['job_id'] == mock_job_id
        assert response_body['status'] == 'queued'
        assert response_body['estimated_time_seconds'] == 300

        # Verify storage operations
        assert mock_storage.save_file.call_count >= 1  # At least drawing file
        mock_storage.save_job_status.assert_called_once()

        # Verify SQS message sent
        mock_sqs_client.send_message.assert_called_once()
        sqs_call_args = mock_sqs_client.send_message.call_args[1]
        assert sqs_call_args['QueueUrl'] == mock_settings.SQS_QUEUE_URL

        message_body = json.loads(sqs_call_args['MessageBody'])
        assert message_body['job_id'] == mock_job_id
        assert message_body['client_name'] == 'Test Client'
        assert message_body['project_name'] == 'Test Project'

    def test_invalid_http_method(self):
        """Test error handling for invalid HTTP method."""

        # Arrange
        event = {
            'httpMethod': 'GET',
            'headers': {},
            'body': '',
            'pathParameters': None
        }

        # Act
        result = handler(event, {})

        # Assert
        assert result['statusCode'] == 405
        response_body = json.loads(result['body'])
        assert 'error' in response_body

    @patch('src.lambda_functions.process_drawing_api.parse_multipart_request')
    def test_missing_required_fields(self, mock_parse_multipart):
        """Test error handling for missing required fields."""

        # Arrange
        event = {
            'httpMethod': 'POST',
            'headers': {'content-type': 'multipart/form-data'},
            'body': 'test'
        }

        mock_parse_multipart.return_value = {
            'drawing_file': {
                'filename': 'test.pdf',
                'content': b'%PDF-1.4\n%test\n%%EOF'
            }
            # Missing client_name and project_name
        }

        # Act
        result = handler(event, {})

        # Assert
        assert result['statusCode'] == 400
        response_body = json.loads(result['body'])
        assert 'client_name and project_name are required' in response_body['error']

    @patch('src.lambda_functions.process_drawing_api.parse_multipart_request')
    @patch('src.lambda_functions.process_drawing_api.validate_file_size')
    def test_file_size_validation_error(self, mock_validate_size, mock_parse_multipart, mock_multipart_data):
        """Test file size validation error handling."""

        # Arrange
        event = {'httpMethod': 'POST', 'headers': {'content-type': 'multipart/form-data'}}
        mock_parse_multipart.return_value = mock_multipart_data
        mock_validate_size.return_value = (False, "File exceeds maximum size")

        # Act
        result = handler(event, {})

        # Assert
        assert result['statusCode'] == 413
        response_body = json.loads(result['body'])
        assert 'exceeds maximum size' in response_body['error']

    @patch('src.lambda_functions.process_drawing_api.parse_multipart_request')
    @patch('src.lambda_functions.process_drawing_api.validate_file_size')
    @patch('src.lambda_functions.process_drawing_api.validate_pdf_file')
    def test_pdf_validation_error(
        self,
        mock_validate_pdf,
        mock_validate_size,
        mock_parse_multipart,
        mock_multipart_data
    ):
        """Test PDF validation error handling."""

        # Arrange
        event = {'httpMethod': 'POST', 'headers': {'content-type': 'multipart/form-data'}}
        mock_parse_multipart.return_value = mock_multipart_data
        mock_validate_size.return_value = (True, "")
        mock_validate_pdf.return_value = (False, "Invalid PDF format")

        # Act
        result = handler(event, {})

        # Assert
        assert result['statusCode'] == 422
        response_body = json.loads(result['body'])
        assert 'Invalid PDF format' in response_body['error']

    @patch('src.lambda_functions.process_drawing_api.StorageManager')
    @patch('src.lambda_functions.process_drawing_api.generate_job_id')
    @patch('src.lambda_functions.process_drawing_api.parse_multipart_request')
    @patch('src.lambda_functions.process_drawing_api.validate_file_size')
    @patch('src.lambda_functions.process_drawing_api.validate_pdf_file')
    def test_sqs_queue_url_missing(
        self,
        mock_validate_pdf,
        mock_validate_size,
        mock_parse_multipart,
        mock_generate_job_id,
        mock_storage_manager,
        mock_multipart_data
    ):
        """Test error handling when SQS queue URL is not configured."""

        # Arrange
        mock_parse_multipart.return_value = mock_multipart_data
        mock_validate_size.return_value = (True, "")
        mock_validate_pdf.return_value = (True, "")
        mock_generate_job_id.return_value = "job_123"

        mock_storage = AsyncMock()
        mock_storage_manager.get_storage.return_value = mock_storage

        # Act
        with patch('src.lambda.process_drawing_api.settings') as mock_settings:
            mock_settings.SQS_QUEUE_URL = None  # Missing queue URL

            result = handler({'httpMethod': 'POST', 'headers': {'content-type': 'multipart/form-data'}}, {})

        # Assert
        assert result['statusCode'] == 500
        response_body = json.loads(result['body'])
        assert 'Queue configuration error' in response_body['error']

    @patch('src.lambda_functions.process_drawing_api.StorageManager')
    @patch('src.lambda_functions.process_drawing_api.sqs_client')
    @patch('src.lambda_functions.process_drawing_api.generate_job_id')
    @patch('src.lambda_functions.process_drawing_api.parse_multipart_request')
    @patch('src.lambda_functions.process_drawing_api.validate_file_size')
    @patch('src.lambda_functions.process_drawing_api.validate_pdf_file')
    def test_sqs_send_message_failure(
        self,
        mock_validate_pdf,
        mock_validate_size,
        mock_parse_multipart,
        mock_generate_job_id,
        mock_sqs_client,
        mock_storage_manager,
        mock_multipart_data
    ):
        """Test error handling when SQS message sending fails."""

        # Arrange
        mock_parse_multipart.return_value = mock_multipart_data
        mock_validate_size.return_value = (True, "")
        mock_validate_pdf.return_value = (True, "")
        mock_generate_job_id.return_value = "job_123"

        mock_storage = AsyncMock()
        mock_storage_manager.get_storage.return_value = mock_storage

        from botocore.exceptions import ClientError
        mock_sqs_client.send_message.side_effect = ClientError(
            error_response={'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            operation_name='SendMessage'
        )

        # Act
        with patch('src.lambda.process_drawing_api.settings') as mock_settings:
            mock_settings.SQS_QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/123456789/test-queue'

            result = handler({'httpMethod': 'POST', 'headers': {'content-type': 'multipart/form-data'}}, {})

        # Assert
        assert result['statusCode'] == 500
        response_body = json.loads(result['body'])
        assert 'Failed to queue processing job' in response_body['error']

    def test_parse_multipart_request_error(self):
        """Test multipart parsing error handling."""

        # Arrange
        event = {
            'httpMethod': 'POST',
            'headers': {'content-type': 'multipart/form-data; boundary=invalid'},
            'body': 'invalid multipart data'
        }

        # Act
        result = handler(event, {})

        # Assert
        assert result['statusCode'] == 400
        response_body = json.loads(result['body'])
        assert 'error' in response_body

    @patch('src.lambda_functions.process_drawing_api.StorageManager')
    @patch('src.lambda_functions.process_drawing_api.sqs_client')
    @patch('src.lambda_functions.process_drawing_api.generate_job_id')
    @patch('src.lambda_functions.process_drawing_api.parse_multipart_request')
    @patch('src.lambda_functions.process_drawing_api.validate_file_size')
    @patch('src.lambda_functions.process_drawing_api.validate_pdf_file')
    def test_context_file_handling(
        self,
        mock_validate_pdf,
        mock_validate_size,
        mock_parse_multipart,
        mock_generate_job_id,
        mock_sqs_client,
        mock_storage_manager,
        mock_pdf_content
    ):
        """Test handling of optional context file."""

        # Arrange
        multipart_data_with_context = {
            'drawing_file': {
                'filename': 'test_drawing.pdf',
                'content_type': 'application/pdf',
                'content': mock_pdf_content
            },
            'client_name': 'Test Client',
            'project_name': 'Test Project',
            'context_file': {
                'filename': 'context.docx',
                'content_type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'content': b'mock docx content'
            }
        }

        mock_parse_multipart.return_value = multipart_data_with_context
        mock_validate_size.return_value = (True, "")
        mock_validate_pdf.return_value = (True, "")
        mock_generate_job_id.return_value = "job_123"

        mock_storage = AsyncMock()
        mock_storage_manager.get_storage.return_value = mock_storage
        mock_sqs_client.send_message.return_value = {'MessageId': 'test-id'}

        # Act
        with patch('src.lambda.process_drawing_api.settings') as mock_settings:
            mock_settings.SQS_QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/123456789/test-queue'

            result = handler({'httpMethod': 'POST', 'headers': {'content-type': 'multipart/form-data'}}, {})

        # Assert
        assert result['statusCode'] == 202

        # Verify both drawing and context files were saved
        assert mock_storage.save_file.call_count == 2

        # Verify SQS message includes context file
        sqs_call_args = mock_sqs_client.send_message.call_args[1]
        message_body = json.loads(sqs_call_args['MessageBody'])
        assert message_body['context_s3_key'] is not None
