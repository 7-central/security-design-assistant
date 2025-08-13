import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.lambda_functions.get_job_status import handler


class TestGetJobStatusLambda:
    """Test cases for the get_job_status Lambda function."""

    @pytest.fixture
    def valid_get_event(self):
        """Create a valid API Gateway GET request event."""
        return {
            'httpMethod': 'GET',
            'pathParameters': {
                'job_id': 'job_1234567890'
            },
            'headers': {},
            'queryStringParameters': None
        }

    @pytest.fixture
    def completed_job_data(self):
        """Mock completed job data from DynamoDB."""
        return {
            'job_id': 'job_1234567890',
            'status': 'completed',
            'created_at': 1640995200,
            'updated_at': 1640995500,
            'total_processing_time_seconds': 180.5,
            'current_stage': 'completed',
            'stages_completed': ['pdf_processing', 'context_processing', 'component_extraction', 'excel_generation', 'evaluation'],
            'metadata': {
                'client_name': 'Test Client',
                'project_name': 'Test Project',
                'file_name': 'drawing.pdf',
                'file_size_mb': 2.5,
                'excel_file_path': 'path/to/excel.xlsx'
            },
            'input_files': {
                'drawing': 'path/to/drawing.pdf',
                'context': None
            },
            'processing_results': {
                'schedule_agent': {
                    'completed': True,
                    'components': {
                        'pages': [
                            {'components': [{'type': 'door', 'id': 'D1'}]}
                        ]
                    },
                    'flattened_components': [{'type': 'door', 'id': 'D1'}]
                },
                'excel_generation': {
                    'completed': True,
                    'file_path': 'path/to/excel.xlsx',
                    'summary': {'total_components': 1}
                },
                'evaluation': {
                    'overall_assessment': 'Good',
                    'completeness': 85.0,
                    'correctness': 90.0,
                    'improvement_suggestions': ['Add more details']
                }
            }
        }

    @pytest.fixture
    def queued_job_data(self):
        """Mock queued job data."""
        return {
            'job_id': 'job_1234567890',
            'status': 'queued',
            'created_at': 1640995200,
            'updated_at': 1640995200,
            'metadata': {
                'client_name': 'Test Client',
                'project_name': 'Test Project',
                'file_name': 'drawing.pdf'
            }
        }

    @pytest.fixture
    def processing_job_data(self):
        """Mock processing job data."""
        return {
            'job_id': 'job_1234567890',
            'status': 'processing',
            'created_at': 1640995200,
            'updated_at': 1640995300,
            'current_stage': 'component_extraction',
            'stages_completed': ['pdf_processing', 'context_processing'],
            'metadata': {
                'client_name': 'Test Client',
                'project_name': 'Test Project',
                'file_name': 'drawing.pdf'
            }
        }

    @pytest.fixture
    def failed_job_data(self):
        """Mock failed job data."""
        return {
            'job_id': 'job_1234567890',
            'status': 'failed',
            'created_at': 1640995200,
            'updated_at': 1640995250,
            'error': 'PDF is corrupted',
            'failed_at': 1640995250,
            'current_stage': 'pdf_processing',
            'metadata': {
                'client_name': 'Test Client',
                'project_name': 'Test Project',
                'file_name': 'drawing.pdf'
            }
        }

    @patch('src.lambda_functions.get_job_status.StorageManager')
    def test_successful_completed_job_status(self, mock_storage_manager, valid_get_event, completed_job_data):
        """Test getting status for a completed job."""
        
        # Arrange
        mock_storage = AsyncMock()
        mock_storage_manager.get_storage.return_value = mock_storage
        mock_storage.get_job_status.return_value = completed_job_data
        mock_storage.generate_presigned_url.return_value = 'https://presigned-url.com/file'
        
        # Act
        result = handler(valid_get_event, {})
        
        # Assert
        assert result['statusCode'] == 200
        
        response_body = json.loads(result['body'])
        assert response_body['job_id'] == 'job_1234567890'
        assert response_body['status'] == 'completed'
        assert response_body['progress']['percentage'] == 100
        assert response_body['progress']['current_step'] == 'Completed'
        
        # Check files section
        assert 'files' in response_body
        assert 'excel' in response_body['files']
        assert response_body['files']['excel']['download_url'] == 'https://presigned-url.com/file'
        assert 'components' in response_body['files']
        
        # Check summary
        assert 'summary' in response_body
        assert response_body['summary']['total_components_found'] == 1
        assert response_body['summary']['excel_generated'] is True
        
        # Check evaluation
        assert 'evaluation' in response_body
        assert response_body['evaluation']['overall_assessment'] == 'Good'

    @patch('src.lambda_functions.get_job_status.StorageManager')
    def test_queued_job_status(self, mock_storage_manager, valid_get_event, queued_job_data):
        """Test getting status for a queued job."""
        
        # Arrange
        mock_storage = AsyncMock()
        mock_storage_manager.get_storage.return_value = mock_storage
        mock_storage.get_job_status.return_value = queued_job_data
        
        # Act
        result = handler(valid_get_event, {})
        
        # Assert
        assert result['statusCode'] == 200
        
        response_body = json.loads(result['body'])
        assert response_body['status'] == 'queued'
        assert response_body['progress']['percentage'] == 0
        assert response_body['progress']['current_step'] == 'Waiting in queue'
        assert response_body['progress']['estimated_time_remaining_seconds'] == 300

    @patch('src.lambda_functions.get_job_status.StorageManager')
    def test_processing_job_status(self, mock_storage_manager, valid_get_event, processing_job_data):
        """Test getting status for a job in progress."""
        
        # Arrange
        mock_storage = AsyncMock()
        mock_storage_manager.get_storage.return_value = mock_storage
        mock_storage.get_job_status.return_value = processing_job_data
        
        # Act
        result = handler(valid_get_event, {})
        
        # Assert
        assert result['statusCode'] == 200
        
        response_body = json.loads(result['body'])
        assert response_body['status'] == 'processing'
        assert response_body['progress']['percentage'] > 0
        assert response_body['progress']['percentage'] < 100
        assert response_body['progress']['current_step'] == 'Extracting components'
        assert response_body['progress']['stages_completed'] == ['pdf_processing', 'context_processing']

    @patch('src.lambda_functions.get_job_status.StorageManager')
    def test_failed_job_status(self, mock_storage_manager, valid_get_event, failed_job_data):
        """Test getting status for a failed job."""
        
        # Arrange
        mock_storage = AsyncMock()
        mock_storage_manager.get_storage.return_value = mock_storage
        mock_storage.get_job_status.return_value = failed_job_data
        
        # Act
        result = handler(valid_get_event, {})
        
        # Assert
        assert result['statusCode'] == 200
        
        response_body = json.loads(result['body'])
        assert response_body['status'] == 'failed'
        assert response_body['progress']['percentage'] == 0
        assert response_body['progress']['current_step'] == 'Failed'
        
        # Check error information
        assert 'error' in response_body
        assert response_body['error']['message'] == 'PDF is corrupted'
        assert response_body['error']['stage'] == 'pdf_processing'

    @patch('src.lambda_functions.get_job_status.StorageManager')
    def test_job_not_found(self, mock_storage_manager, valid_get_event):
        """Test handling of non-existent job ID."""
        
        # Arrange
        mock_storage = AsyncMock()
        mock_storage_manager.get_storage.return_value = mock_storage
        mock_storage.get_job_status.return_value = None
        
        # Act
        result = handler(valid_get_event, {})
        
        # Assert
        assert result['statusCode'] == 404
        
        response_body = json.loads(result['body'])
        assert 'error' in response_body
        assert 'not found' in response_body['error'].lower()

    def test_invalid_http_method(self):
        """Test error handling for invalid HTTP method."""
        
        # Arrange
        event = {
            'httpMethod': 'POST',
            'pathParameters': {'job_id': 'job_123'},
            'headers': {}
        }
        
        # Act
        result = handler(event, {})
        
        # Assert
        assert result['statusCode'] == 405
        response_body = json.loads(result['body'])
        assert 'Method not allowed' in response_body['error']

    def test_missing_job_id_parameter(self):
        """Test error handling for missing job_id path parameter."""
        
        # Arrange
        event = {
            'httpMethod': 'GET',
            'pathParameters': {},  # Missing job_id
            'headers': {}
        }
        
        # Act
        result = handler(event, {})
        
        # Assert
        assert result['statusCode'] == 400
        response_body = json.loads(result['body'])
        assert 'Missing job_id' in response_body['error']

    def test_empty_job_id_parameter(self):
        """Test error handling for empty job_id parameter."""
        
        # Arrange
        event = {
            'httpMethod': 'GET',
            'pathParameters': {'job_id': ''},
            'headers': {}
        }
        
        # Act
        result = handler(event, {})
        
        # Assert
        assert result['statusCode'] == 400
        response_body = json.loads(result['body'])
        assert 'cannot be empty' in response_body['error']

    def test_no_path_parameters(self):
        """Test error handling when pathParameters is None."""
        
        # Arrange
        event = {
            'httpMethod': 'GET',
            'pathParameters': None,
            'headers': {}
        }
        
        # Act
        result = handler(event, {})
        
        # Assert
        assert result['statusCode'] == 400

    @patch('src.lambda_functions.get_job_status.StorageManager')
    def test_timeout_detected_job(self, mock_storage_manager, valid_get_event):
        """Test handling of job with timeout detection."""
        
        # Arrange
        timeout_job_data = {
            'job_id': 'job_1234567890',
            'status': 'processing',
            'timeout_detected': True,
            'processing_interrupted': True,
            'stages_completed': ['pdf_processing', 'context_processing'],
            'current_stage': 'component_extraction'
        }
        
        mock_storage = AsyncMock()
        mock_storage_manager.get_storage.return_value = mock_storage
        mock_storage.get_job_status.return_value = timeout_job_data
        
        # Act
        result = handler(valid_get_event, {})
        
        # Assert
        assert result['statusCode'] == 200
        
        response_body = json.loads(result['body'])
        assert 'timeout_info' in response_body
        assert response_body['timeout_info']['detected'] is True
        assert 'interrupted due to Lambda timeout' in response_body['timeout_info']['message']

    @patch('src.lambda_functions.get_job_status.StorageManager')
    def test_legacy_excel_path_handling(self, mock_storage_manager, valid_get_event):
        """Test backward compatibility with legacy Excel file path storage."""
        
        # Arrange
        legacy_job_data = {
            'job_id': 'job_1234567890',
            'status': 'completed',
            'metadata': {
                'excel_file_path': 'legacy/path/to/excel.xlsx'  # Legacy path
            },
            'processing_results': {
                'excel_generation': {
                    'completed': False  # No new-style Excel generation data
                }
            }
        }
        
        mock_storage = AsyncMock()
        mock_storage_manager.get_storage.return_value = mock_storage
        mock_storage.get_job_status.return_value = legacy_job_data
        mock_storage.generate_presigned_url.return_value = 'https://legacy-url.com/file'
        
        # Act
        result = handler(valid_get_event, {})
        
        # Assert
        assert result['statusCode'] == 200
        
        response_body = json.loads(result['body'])
        assert 'files' in response_body
        assert 'excel' in response_body['files']
        assert response_body['files']['excel']['download_url'] == 'https://legacy-url.com/file'

    @patch('src.lambda_functions.get_job_status.StorageManager')
    def test_storage_error_handling(self, mock_storage_manager, valid_get_event):
        """Test handling of storage operation errors."""
        
        # Arrange
        mock_storage = AsyncMock()
        mock_storage_manager.get_storage.return_value = mock_storage
        mock_storage.get_job_status.side_effect = Exception("Database connection failed")
        
        # Act
        result = handler(valid_get_event, {})
        
        # Assert
        assert result['statusCode'] == 500
        
        response_body = json.loads(result['body'])
        assert 'Internal server error' in response_body['error']

    @patch('src.lambda_functions.get_job_status.StorageManager')
    def test_cors_headers(self, mock_storage_manager, valid_get_event, completed_job_data):
        """Test that CORS headers are properly set."""
        
        # Arrange
        mock_storage = AsyncMock()
        mock_storage_manager.get_storage.return_value = mock_storage
        mock_storage.get_job_status.return_value = completed_job_data
        mock_storage.generate_presigned_url.return_value = 'https://test-url.com'
        
        # Act
        result = handler(valid_get_event, {})
        
        # Assert
        headers = result['headers']
        assert headers['Access-Control-Allow-Origin'] == '*'
        assert 'Access-Control-Allow-Headers' in headers
        assert 'Access-Control-Allow-Methods' in headers

    @patch('src.lambda_functions.get_job_status.StorageManager')
    def test_timestamp_formatting(self, mock_storage_manager, valid_get_event):
        """Test timestamp formatting in responses."""
        
        # Arrange
        job_data_with_timestamps = {
            'job_id': 'job_1234567890',
            'status': 'completed',
            'created_at': 1640995200,  # Unix timestamp
            'updated_at': '2022-01-01T00:05:00Z',  # ISO string
            'failed_at': None  # None value
        }
        
        mock_storage = AsyncMock()
        mock_storage_manager.get_storage.return_value = mock_storage
        mock_storage.get_job_status.return_value = job_data_with_timestamps
        
        # Act
        result = handler(valid_get_event, {})
        
        # Assert
        assert result['statusCode'] == 200
        
        response_body = json.loads(result['body'])
        
        # Unix timestamp should be converted to ISO format
        assert response_body['created_at'] == '2022-01-01T00:00:00+00:00'
        
        # ISO string should be preserved
        assert response_body['updated_at'] == '2022-01-01T00:05:00Z'

    @patch('src.lambda_functions.get_job_status.StorageManager')
    def test_components_inline_data(self, mock_storage_manager, valid_get_event, completed_job_data):
        """Test that components data is included inline for JSON files."""
        
        # Arrange
        mock_storage = AsyncMock()
        mock_storage_manager.get_storage.return_value = mock_storage
        mock_storage.get_job_status.return_value = completed_job_data
        mock_storage.generate_presigned_url.return_value = 'https://test-url.com'
        
        # Act
        result = handler(valid_get_event, {})
        
        # Assert
        assert result['statusCode'] == 200
        
        response_body = json.loads(result['body'])
        assert 'files' in response_body
        assert 'components' in response_body['files']
        assert 'data' in response_body['files']['components']
        assert response_body['files']['components']['type'] == 'json'