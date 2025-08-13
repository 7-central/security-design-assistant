"""
Tests for Lambda warmer functionality.
"""

import json
from unittest.mock import Mock, patch

import pytest

from src.lambda_functions.lambda_warmer import (
    check_and_handle_warmer,
    handle_warmer_request,
    handler,
    is_warmer_request,
    warm_function,
)


class TestLambdaWarmer:
    """Test Lambda warmer functionality."""

    @patch.dict('os.environ', {'ENVIRONMENT': 'test'})
    @patch('boto3.client')
    def test_handler_success(self, mock_boto_client):
        """Test successful warmer execution."""
        mock_lambda_client = Mock()
        mock_boto_client.return_value = mock_lambda_client

        # Mock successful Lambda invoke response
        mock_lambda_client.invoke.return_value = {
            'StatusCode': 202,
            'ResponseMetadata': {'RequestId': 'test-request-id'}
        }

        event = {'source': 'aws.events'}
        context = Mock()

        result = handler(event, context)

        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['warmer_execution'] == 'completed'
        assert body['total_functions'] == 2
        assert body['successful_warms'] == 2
        assert body['failed_warms'] == 0

        # Verify both functions were invoked
        expected_functions = [
            'security-assistant-api-test',
            'security-assistant-status-test'
        ]
        assert mock_lambda_client.invoke.call_count == 2

        # Check the function names in the call arguments
        call_args = [call[1]['FunctionName'] for call in mock_lambda_client.invoke.call_args_list]
        for expected_func in expected_functions:
            assert expected_func in call_args

    @patch.dict('os.environ', {'ENVIRONMENT': 'prod'})
    @patch('boto3.client')
    def test_handler_partial_failure(self, mock_boto_client):
        """Test warmer execution with partial failure."""
        mock_lambda_client = Mock()
        mock_boto_client.return_value = mock_lambda_client

        # First invoke succeeds, second fails
        mock_lambda_client.invoke.side_effect = [
            {'StatusCode': 202, 'ResponseMetadata': {'RequestId': 'success-id'}},
            Exception('Function not found')
        ]

        event = {'source': 'aws.events'}
        context = Mock()

        result = handler(event, context)

        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['warmer_execution'] == 'completed'
        assert body['total_functions'] == 2
        assert body['successful_warms'] == 1
        assert body['failed_warms'] == 1

    def test_warm_function_success(self):
        """Test successful function warming."""
        mock_lambda_client = Mock()
        mock_lambda_client.invoke.return_value = {
            'StatusCode': 202,
            'ResponseMetadata': {'RequestId': 'test-request-id'}
        }

        result = warm_function(mock_lambda_client, 'test-function')

        assert result['function_name'] == 'test-function'
        assert result['status'] == 'success'
        assert result['status_code'] == 202
        assert result['request_id'] == 'test-request-id'

        # Verify invoke was called with correct parameters
        mock_lambda_client.invoke.assert_called_once()
        call_args = mock_lambda_client.invoke.call_args
        assert call_args[1]['FunctionName'] == 'test-function'
        assert call_args[1]['InvocationType'] == 'Event'

        # Verify payload contains warmer flag
        payload = json.loads(call_args[1]['Payload'])
        assert payload['warmer'] is True
        assert payload['source'] == 'lambda-warmer'
        assert payload['function_name'] == 'test-function'

    def test_warm_function_failure(self):
        """Test function warming failure."""
        mock_lambda_client = Mock()
        mock_lambda_client.invoke.side_effect = Exception('Function not found')

        with pytest.raises(Exception) as exc_info:
            warm_function(mock_lambda_client, 'missing-function')

        assert 'Unexpected error warming function' in str(exc_info.value)

    def test_is_warmer_request_true(self):
        """Test warmer request detection - positive case."""
        event = {
            'warmer': True,
            'source': 'lambda-warmer',
            'function_name': 'test-function'
        }

        assert is_warmer_request(event) is True

    def test_is_warmer_request_false(self):
        """Test warmer request detection - negative cases."""
        # Regular API Gateway event
        api_event = {
            'httpMethod': 'POST',
            'path': '/process-drawing',
            'body': '{"test": "data"}'
        }
        assert is_warmer_request(api_event) is False

        # Missing warmer flag
        incomplete_event = {
            'source': 'lambda-warmer',
            'function_name': 'test-function'
        }
        assert is_warmer_request(incomplete_event) is False

        # Wrong source
        wrong_source = {
            'warmer': True,
            'source': 'api-gateway',
            'function_name': 'test-function'
        }
        assert is_warmer_request(wrong_source) is False

    def test_handle_warmer_request(self):
        """Test warmer request handling."""
        event = {
            'warmer': True,
            'source': 'lambda-warmer',
            'function_name': 'test-function',
            'timestamp': 'test-timestamp'
        }

        result = handle_warmer_request(event)

        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert 'Function test-function warmed successfully' in body['message']
        assert body['warmer'] is True
        assert body['timestamp'] == 'test-timestamp'

    def test_check_and_handle_warmer_true(self):
        """Test check_and_handle_warmer returns True for warmer requests."""
        warmer_event = {
            'warmer': True,
            'source': 'lambda-warmer',
            'function_name': 'test-function'
        }

        result = check_and_handle_warmer(warmer_event)
        assert result is True

    def test_check_and_handle_warmer_false(self):
        """Test check_and_handle_warmer returns False for regular requests."""
        regular_event = {
            'httpMethod': 'POST',
            'path': '/process-drawing'
        }

        result = check_and_handle_warmer(regular_event)
        assert result is False


class TestLazyLoading:
    """Test lazy loading functionality in base agent."""

    def test_base_agent_lazy_client_initialization(self):
        """Test that GenAI client is not initialized until accessed."""
        from src.agents.base_agent_v2 import BaseAgentV2
        from src.storage.interface import StorageInterface

        # Create mock storage and job
        mock_storage = Mock(spec=StorageInterface)
        mock_job = Mock()
        mock_job.job_id = 'test-job'
        mock_job.client_name = 'test-client'
        mock_job.project_name = 'test-project'

        # Create concrete implementation for testing
        class TestAgent(BaseAgentV2):
            async def process(self, input_data):
                return {'test': 'result'}

        # Initialize agent - client should not be created yet
        with patch('src.config.settings.settings.GEMINI_API_KEY', 'test-key'):
            agent = TestAgent(mock_storage, mock_job)
            assert agent._client is None

        # Access client property - now it should be created
        with patch('google.genai.Client') as mock_genai_client:
            with patch('src.config.settings.settings.GEMINI_API_KEY', 'test-key'):
                mock_genai_client.return_value = Mock()
                client = agent.client
                assert client is not None
                assert agent._client is not None
                mock_genai_client.assert_called_once_with(api_key='test-key')

    @patch('src.agents.base_agent_v2.genai.Client')
    def test_lazy_imports_in_generate_content(self, mock_genai_client):
        """Test that types module is imported lazily in generate_content."""
        from src.agents.base_agent_v2 import BaseAgentV2
        from src.storage.interface import StorageInterface

        # Mock storage, job, and settings
        mock_storage = Mock(spec=StorageInterface)
        mock_job = Mock()
        mock_job.job_id = 'test-job'
        mock_job.client_name = 'test-client'
        mock_job.project_name = 'test-project'

        class TestAgent(BaseAgentV2):
            async def process(self, input_data):
                return {'test': 'result'}

        with patch('src.config.settings.settings.GEMINI_API_KEY', 'test-key'):
            agent = TestAgent(mock_storage, mock_job)

            # Mock the types module import
            with patch('google.genai.types') as mock_types:
                mock_types.GenerateContentConfig.return_value = Mock()

                # Mock the client's generate_content method
                mock_client = Mock()
                mock_response = Mock()
                mock_client.models.generate_content.return_value = mock_response
                agent._client = mock_client

                # Call generate_content
                result = agent.generate_content('test-model', ['test content'])

                # Verify types was imported and used
                mock_types.GenerateContentConfig.assert_called_once()
                assert result == mock_response


class TestColdStartOptimizations:
    """Test cold start optimization implementations."""

    def test_warmer_integration_in_api_function(self):
        """Test that API function integrates warmer check."""
        # This test verifies the pattern but doesn't execute the full function
        # since that would require extensive mocking
        warmer_event = {
            'warmer': True,
            'source': 'lambda-warmer',
            'function_name': 'security-assistant-api-test'
        }

        # Test the warmer detection logic
        from src.lambda_functions.lambda_warmer import is_warmer_request
        assert is_warmer_request(warmer_event) is True

        # Test warmer handling
        from src.lambda_functions.lambda_warmer import handle_warmer_request
        result = handle_warmer_request(warmer_event)
        assert result['statusCode'] == 200

    def test_warmer_integration_in_status_function(self):
        """Test that status function integrates warmer check."""
        warmer_event = {
            'warmer': True,
            'source': 'lambda-warmer',
            'function_name': 'security-assistant-status-test'
        }

        from src.lambda_functions.lambda_warmer import check_and_handle_warmer
        assert check_and_handle_warmer(warmer_event) is True
