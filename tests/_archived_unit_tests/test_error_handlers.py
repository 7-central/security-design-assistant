"""
Unit tests for centralized error handling utilities.
"""

import json
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.utils.error_handlers import (
    LambdaError,
    MemoryExhaustedError,
    ProcessingStageError,
    TimeoutApproachingError,
    check_lambda_timeout,
    check_memory_usage,
    create_api_error_response,
    create_correlation_id,
    handle_processing_stage,
    log_lambda_metrics,
    log_structured_error,
)


class TestLambdaErrors:
    """Test Lambda-specific error classes."""

    def test_lambda_error_creation(self):
        """Test basic LambdaError creation."""
        error = LambdaError("Test error", "TEST_ERROR", {"key": "value"})

        assert error.message == "Test error"
        assert error.error_code == "TEST_ERROR"
        assert error.details == {"key": "value"}
        assert isinstance(error.timestamp, int)
        assert isinstance(error.correlation_id, str)

    def test_timeout_approaching_error(self):
        """Test TimeoutApproachingError creation."""
        error = TimeoutApproachingError(30.5)

        assert error.error_code == "LAMBDA_TIMEOUT_APPROACHING"
        assert "30.5s remaining" in error.message
        assert error.details["remaining_time"] == 30.5

    def test_memory_exhausted_error(self):
        """Test MemoryExhaustedError creation."""
        error = MemoryExhaustedError(2048, 2560)

        assert error.error_code == "LAMBDA_MEMORY_EXHAUSTED"
        assert "usage: 2048MB, limit: 2560MB" in error.message
        assert error.details["current_usage_mb"] == 2048
        assert error.details["limit_mb"] == 2560

    def test_processing_stage_error(self):
        """Test ProcessingStageError creation."""
        original_error = ValueError("Original error")
        error = ProcessingStageError("pdf_processing", original_error, "job_123")

        assert error.error_code == "PROCESSING_STAGE_FAILED"
        assert "pdf_processing" in error.message
        assert "job_123" in error.message
        assert error.details["stage"] == "pdf_processing"
        assert error.details["job_id"] == "job_123"
        assert error.details["original_error_type"] == "ValueError"


class TestCorrelationId:
    """Test correlation ID generation."""

    def test_create_correlation_id_without_job_id(self):
        """Test correlation ID creation without job ID."""
        correlation_id = create_correlation_id()

        assert correlation_id.startswith("req_")
        assert len(correlation_id.split("_")) == 3  # req_timestamp_uuid

    def test_create_correlation_id_with_job_id(self):
        """Test correlation ID creation with job ID."""
        correlation_id = create_correlation_id("job_123")

        assert correlation_id.startswith("job_job_123_")
        assert len(correlation_id.split("_")) == 5  # job_job_123_timestamp_uuid (job_123 has underscore)


class TestStructuredErrorLogging:
    """Test structured error logging."""

    @patch('src.utils.error_handlers.logger')
    def test_log_structured_error_basic(self, mock_logger):
        """Test basic structured error logging."""
        error = ValueError("Test error")
        context = {"key": "value"}

        log_structured_error(error, context, "corr_123", "job_456")

        mock_logger.error.assert_called_once()
        logged_data = json.loads(mock_logger.error.call_args[0][0])

        assert logged_data["event_type"] == "error"
        assert logged_data["correlation_id"] == "corr_123"
        assert logged_data["job_id"] == "job_456"
        assert logged_data["error"]["type"] == "ValueError"
        assert logged_data["error"]["message"] == "Test error"
        assert logged_data["context"] == context

    @patch('src.utils.error_handlers.logger')
    def test_log_structured_error_lambda_error(self, mock_logger):
        """Test structured logging of Lambda-specific errors."""
        error = TimeoutApproachingError(30.0)
        context = {"stage": "processing"}

        log_structured_error(error, context)

        mock_logger.error.assert_called_once()
        logged_data = json.loads(mock_logger.error.call_args[0][0])

        assert logged_data["error"]["lambda_error"] is True
        assert logged_data["error"]["error_code"] == "LAMBDA_TIMEOUT_APPROACHING"
        assert logged_data["error"]["details"]["remaining_time"] == 30.0


class TestTimeoutChecking:
    """Test Lambda timeout checking."""

    def test_check_lambda_timeout_with_context(self):
        """Test timeout checking with Lambda context."""
        mock_context = Mock()
        mock_context.get_remaining_time_in_millis.return_value = 120000  # 2 minutes

        start_time = time.time()

        # Should not raise with plenty of time remaining
        check_lambda_timeout(mock_context, start_time, 60)

        # Should raise with little time remaining
        mock_context.get_remaining_time_in_millis.return_value = 30000  # 30 seconds

        with pytest.raises(TimeoutApproachingError):
            check_lambda_timeout(mock_context, start_time, 60)

    def test_check_lambda_timeout_without_context(self):
        """Test timeout checking without Lambda context (fallback)."""
        start_time = time.time() - 850  # 850 seconds ago (14+ minutes, closer to 15min limit)

        with pytest.raises(TimeoutApproachingError):
            check_lambda_timeout(None, start_time, 60)

        # Should not raise with recent start time
        recent_start = time.time()
        check_lambda_timeout(None, recent_start, 60)


class TestMemoryUsageChecking:
    """Test memory usage checking."""

    @patch('builtins.__import__', side_effect=lambda name, *args: Mock() if name == 'psutil' else __import__(name, *args))
    def test_check_memory_usage_normal(self, mock_import):
        """Test memory usage checking under normal conditions."""
        # Mock psutil and os within the function
        with patch('psutil.Process') as mock_process_class, \
             patch('os.getpid', return_value=12345), \
             patch('os.getenv', return_value='1024'):

            # Mock memory info
            mock_process = Mock()
            mock_process.memory_info.return_value.rss = 512 * 1024 * 1024  # 512MB
            mock_process_class.return_value = mock_process

            # Should not raise at 50% usage
            check_memory_usage(85.0, "job_123")

    @patch('builtins.__import__', side_effect=lambda name, *args: Mock() if name == 'psutil' else __import__(name, *args))
    @patch('src.utils.error_handlers.logger')
    def test_check_memory_usage_high(self, mock_logger, mock_import):
        """Test memory usage checking with high usage."""
        with patch('psutil.Process') as mock_process_class, \
             patch('os.getpid', return_value=12345), \
             patch('os.getenv', return_value='1024'):

            # Mock memory usage at 90%
            mock_process = Mock()
            mock_process.memory_info.return_value.rss = 900 * 1024 * 1024  # 900MB
            mock_process_class.return_value = mock_process

            # Should log warning but not raise at 90% with 85% threshold
            check_memory_usage(85.0, "job_123")
            mock_logger.warning.assert_called()

    @patch('builtins.__import__', side_effect=lambda name, *args: Mock() if name == 'psutil' else __import__(name, *args))
    def test_check_memory_usage_critical(self, mock_import):
        """Test memory usage checking at critical level."""
        with patch('psutil.Process') as mock_process_class, \
             patch('os.getpid', return_value=12345), \
             patch('os.getenv', return_value='1024'):

            # Mock memory usage at 98%
            mock_process = Mock()
            mock_process.memory_info.return_value.rss = 1000 * 1024 * 1024  # 1000MB
            mock_process_class.return_value = mock_process

            # Should raise at 98% usage
            with pytest.raises(MemoryExhaustedError):
                check_memory_usage(85.0, "job_123")

    @patch('builtins.__import__', side_effect=ImportError("No module named 'psutil'"))
    @patch('src.utils.error_handlers.logger')
    def test_check_memory_usage_no_psutil(self, mock_logger, mock_import):
        """Test memory usage checking when psutil is not available."""
        # Should not raise and log debug message
        check_memory_usage(85.0, "job_123")
        mock_logger.debug.assert_called_with("psutil not available, skipping memory check")


class TestProcessingStageHandling:
    """Test processing stage handling with comprehensive error handling."""

    @pytest.mark.asyncio
    async def test_handle_processing_stage_success(self):
        """Test successful processing stage handling."""
        mock_storage = Mock()
        mock_storage.get_job_status = AsyncMock(return_value={"status": "processing"})
        mock_storage.save_job_status = AsyncMock()

        mock_stage_func = AsyncMock(return_value="stage_result")
        mock_context = Mock()
        mock_context.get_remaining_time_in_millis.return_value = 300000  # 5 minutes

        with patch('src.utils.error_handlers.check_memory_usage'):
            result = await handle_processing_stage(
                "test_stage",
                mock_stage_func,
                "job_123",
                mock_storage,
                mock_context,
                time.time(),
                "arg1",
                kwarg1="value1"
            )

        assert result == "stage_result"
        mock_stage_func.assert_called_once_with("arg1", kwarg1="value1")

        # Should update job status twice: in_progress and completed
        assert mock_storage.save_job_status.call_count == 2

    @pytest.mark.asyncio
    async def test_handle_processing_stage_failure(self):
        """Test processing stage handling with failure."""
        mock_storage = Mock()
        mock_storage.get_job_status = AsyncMock(return_value={"status": "processing"})
        mock_storage.save_job_status = AsyncMock()

        original_error = ValueError("Stage failed")
        mock_stage_func = AsyncMock(side_effect=original_error)
        mock_context = Mock()
        mock_context.get_remaining_time_in_millis.return_value = 300000

        with patch('src.utils.error_handlers.check_memory_usage'):
            with pytest.raises(ProcessingStageError) as exc_info:
                await handle_processing_stage(
                    "test_stage",
                    mock_stage_func,
                    "job_123",
                    mock_storage,
                    mock_context,
                    time.time()
                )

        assert exc_info.value.details["stage"] == "test_stage"
        assert exc_info.value.details["job_id"] == "job_123"

        # Should update status to failed
        mock_storage.save_job_status.assert_called()

    @pytest.mark.asyncio
    async def test_handle_processing_stage_timeout(self):
        """Test processing stage handling with timeout."""
        mock_storage = Mock()
        mock_storage.get_job_status = AsyncMock(return_value={"status": "processing"})
        mock_storage.save_job_status = AsyncMock()

        mock_stage_func = AsyncMock(return_value="result")
        mock_context = Mock()
        mock_context.get_remaining_time_in_millis.return_value = 30000  # 30 seconds

        with patch('src.utils.error_handlers.check_memory_usage'), \
             patch('src.utils.error_handlers.check_lambda_timeout', side_effect=TimeoutApproachingError(25.0)):
            with pytest.raises(ProcessingStageError):
                await handle_processing_stage(
                    "test_stage",
                    mock_stage_func,
                    "job_123",
                    mock_storage,
                    mock_context,
                    time.time()
                )


class TestAPIErrorResponse:
    """Test API error response creation."""

    def test_create_api_error_response_basic(self):
        """Test basic API error response creation."""
        response = create_api_error_response(400, "Bad request")

        assert response['statusCode'] == 400
        assert 'application/json' in response['headers']['Content-Type']

        body = json.loads(response['body'])
        assert body['error'] == "Bad request"
        assert 'timestamp' in body
        assert 'correlation_id' in body

    def test_create_api_error_response_with_details(self):
        """Test API error response with additional details."""
        details = {"field": "value", "code": 123}
        response = create_api_error_response(
            422,
            "Validation error",
            "VALIDATION_FAILED",
            details,
            "corr_123"
        )

        body = json.loads(response['body'])
        assert body['error'] == "Validation error"
        assert body['error_code'] == "VALIDATION_FAILED"
        assert body['details'] == details
        assert body['correlation_id'] == "corr_123"
        assert response['headers']['X-Correlation-ID'] == "corr_123"


class TestLambdaMetrics:
    """Test Lambda metrics logging."""

    @patch('src.utils.error_handlers.logger')
    def test_log_lambda_metrics_success(self, mock_logger):
        """Test Lambda metrics logging for successful execution."""
        log_lambda_metrics(
            "test-function",
            45.5,
            memory_used=512,
            success=True,
            error_count=0,
            job_id="job_123"
        )

        mock_logger.info.assert_called_once()
        logged_data = json.loads(mock_logger.info.call_args[0][0])

        assert logged_data["event_type"] == "lambda_metrics"
        assert logged_data["function_name"] == "test-function"
        assert logged_data["execution_time_seconds"] == 45.5
        assert logged_data["memory_used_mb"] == 512
        assert logged_data["success"] is True
        assert logged_data["error_count"] == 0
        assert logged_data["job_id"] == "job_123"

    @patch('src.utils.error_handlers.logger')
    def test_log_lambda_metrics_failure(self, mock_logger):
        """Test Lambda metrics logging for failed execution."""
        log_lambda_metrics(
            "test-function",
            120.0,
            success=False,
            error_count=3
        )

        mock_logger.info.assert_called_once()
        logged_data = json.loads(mock_logger.info.call_args[0][0])

        assert logged_data["success"] is False
        assert logged_data["error_count"] == 3
        assert "job_id" not in logged_data  # Optional field
        assert "memory_used_mb" not in logged_data  # Optional field


class TestIntegrationScenarios:
    """Test integration scenarios with realistic error patterns."""

    @pytest.mark.asyncio
    async def test_complete_error_handling_flow(self):
        """Test complete error handling flow."""
        # Mock storage that tracks all calls
        mock_storage = Mock()
        job_data = {
            "status": "processing",
            "stages_completed": ["pdf_processing"],
            "current_stage": None
        }
        mock_storage.get_job_status = AsyncMock(return_value=job_data)
        mock_storage.save_job_status = AsyncMock()

        # Mock stage function that fails
        mock_stage_func = AsyncMock(side_effect=ValueError("Processing failed"))

        # Mock context with adequate time
        mock_context = Mock()
        mock_context.get_remaining_time_in_millis.return_value = 300000

        with patch('src.utils.error_handlers.check_memory_usage'):
            with patch('src.utils.error_handlers.log_structured_error') as mock_log:
                with pytest.raises(ProcessingStageError):
                    await handle_processing_stage(
                        "drawing_analysis",
                        mock_stage_func,
                        "job_456",
                        mock_storage,
                        mock_context,
                        time.time()
                    )

        # Verify all expected interactions
        mock_log.assert_called_once()
        mock_storage.save_job_status.assert_called()

        # Verify final status update includes failure info
        final_call_args = mock_storage.save_job_status.call_args_list[-1]
        updated_job_data = final_call_args[0][1]  # Second argument is job data

        assert "error_details" in updated_job_data
        assert updated_job_data["error_details"]["stage"] == "drawing_analysis"
