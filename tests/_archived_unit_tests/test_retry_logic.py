"""
Unit tests for retry logic with rate limit detection.
"""

import time
from unittest.mock import AsyncMock, Mock, patch

import pytest
from google.api_core import exceptions as google_exceptions

from src.utils.retry_logic import (
    RateLimitExceededException,
    _calculate_exponential_backoff,
    _extract_rate_limit_reset,
    check_gemini_rate_limits,
    retry_with_exponential_backoff,
)


class TestRetryWithExponentialBackoff:
    """Test retry logic with exponential backoff."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        """Test successful function call on first attempt."""
        mock_func = AsyncMock(return_value="success")

        result = await retry_with_exponential_backoff(mock_func, "arg1", kwarg1="value1")

        assert result == "success"
        mock_func.assert_called_once_with("arg1", kwarg1="value1")

    @pytest.mark.asyncio
    async def test_success_on_retry(self):
        """Test successful function call after retries."""
        mock_func = AsyncMock(side_effect=[
            google_exceptions.ResourceExhausted("Rate limit exceeded"),
            google_exceptions.ResourceExhausted("Rate limit exceeded"),
            "success"
        ])

        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await retry_with_exponential_backoff(mock_func, max_retries=3)

        assert result == "success"
        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_rate_limit_exhausted(self):
        """Test rate limit exceeded with max retries."""
        mock_func = AsyncMock(side_effect=google_exceptions.ResourceExhausted("Rate limit exceeded"))

        with patch('asyncio.sleep', new_callable=AsyncMock), pytest.raises(RateLimitExceededException):
            await retry_with_exponential_backoff(mock_func, max_retries=2)

        assert mock_func.call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_non_retryable_error(self):
        """Test that non-retryable errors are not retried."""
        mock_func = AsyncMock(side_effect=google_exceptions.InvalidArgument("Invalid request"))

        with pytest.raises(google_exceptions.InvalidArgument):
            await retry_with_exponential_backoff(mock_func)

        mock_func.assert_called_once()

    @pytest.mark.asyncio
    async def test_timeout_constraint(self):
        """Test retry behavior with timeout constraints."""
        mock_func = AsyncMock(side_effect=google_exceptions.ResourceExhausted("Rate limit exceeded"))

        # Very little time remaining should prevent retries
        with patch('asyncio.sleep', new_callable=AsyncMock):
            with pytest.raises(RateLimitExceededException):  # Should be RateLimitExceededException when rate limited with timeout constraints
                await retry_with_exponential_backoff(
                    mock_func,
                    max_retries=3,
                    context_timeout_remaining=10  # Only 10 seconds remaining
                )

        # Should not call function if timeout is too short even for first attempt
        assert mock_func.call_count == 0

    @pytest.mark.asyncio
    async def test_deadline_exceeded_retry(self):
        """Test retry on deadline exceeded errors."""
        mock_func = AsyncMock(side_effect=[
            google_exceptions.DeadlineExceeded("Request timeout"),
            "success"
        ])

        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await retry_with_exponential_backoff(mock_func, max_retries=2)

        assert result == "success"
        assert mock_func.call_count == 2

    @pytest.mark.asyncio
    async def test_service_unavailable_retry(self):
        """Test retry on service unavailable errors."""
        mock_func = AsyncMock(side_effect=[
            google_exceptions.ServiceUnavailable("Service unavailable"),
            "success"
        ])

        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await retry_with_exponential_backoff(mock_func, max_retries=2)

        assert result == "success"
        assert mock_func.call_count == 2


class TestExponentialBackoffCalculation:
    """Test exponential backoff calculation."""

    def test_exponential_backoff_calculation(self):
        """Test basic exponential backoff calculation."""
        delay0 = _calculate_exponential_backoff(0, 2.0, 60.0, False)
        delay1 = _calculate_exponential_backoff(1, 2.0, 60.0, False)
        delay2 = _calculate_exponential_backoff(2, 2.0, 60.0, False)

        assert delay0 == 2.0
        assert delay1 == 4.0
        assert delay2 == 8.0

    def test_max_delay_limit(self):
        """Test that delay is capped at max_delay."""
        delay = _calculate_exponential_backoff(10, 2.0, 60.0, False)
        assert delay == 60.0

    def test_jitter_applied(self):
        """Test that jitter is applied when enabled."""
        delay_no_jitter = _calculate_exponential_backoff(1, 2.0, 60.0, False)
        _calculate_exponential_backoff(1, 2.0, 60.0, True)

        # With jitter, delay should be different (unless very unlucky)
        # Test multiple times to reduce flakiness
        jittered_delays = [
            _calculate_exponential_backoff(1, 2.0, 60.0, True)
            for _ in range(10)
        ]

        # At least some should be different from base delay
        assert any(delay != delay_no_jitter for delay in jittered_delays)

        # All should be positive
        assert all(delay >= 0 for delay in jittered_delays)


class TestRateLimitExtraction:
    """Test rate limit reset time extraction."""

    @patch('src.utils.retry_logic.logger')
    def test_extract_retry_after_header(self, mock_logger):
        """Test extraction of retry-after header."""
        # Create a mock exception with response attribute
        exception = Mock(spec=google_exceptions.ResourceExhausted)
        exception.response = Mock()
        exception.response.headers = {'retry-after': '30'}

        reset_time = _extract_rate_limit_reset(exception)
        assert reset_time == 30.0

    @patch('src.utils.retry_logic.logger')
    def test_extract_ratelimit_reset_header(self, mock_logger):
        """Test extraction of x-ratelimit-reset header."""
        future_timestamp = int(time.time()) + 45

        exception = Mock(spec=google_exceptions.ResourceExhausted)
        exception.response = Mock()
        exception.response.headers = {'x-ratelimit-reset': str(future_timestamp)}

        reset_time = _extract_rate_limit_reset(exception)
        assert 40 <= reset_time <= 50  # Should be around 45 seconds

    @patch('src.utils.retry_logic.logger')
    def test_no_headers_returns_none(self, mock_logger):
        """Test that missing headers return None."""
        exception = Mock(spec=google_exceptions.ResourceExhausted)
        exception.response = Mock()
        exception.response.headers = {}

        reset_time = _extract_rate_limit_reset(exception)
        assert reset_time is None

    def test_no_response_returns_none(self):
        """Test that exception without response returns None."""
        exception = google_exceptions.ResourceExhausted("Rate limit")

        reset_time = _extract_rate_limit_reset(exception)
        assert reset_time is None


class TestCheckGeminiRateLimits:
    """Test Gemini API rate limit checking."""

    @pytest.mark.asyncio
    async def test_rate_limit_check_success(self):
        """Test successful rate limit check."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.headers = {
            'x-ratelimit-requests-remaining': '100',
            'x-ratelimit-tokens-remaining': '50000'
        }

        mock_client.models.generate_content = AsyncMock(return_value=mock_response)

        result = await check_gemini_rate_limits(mock_client, "gemini-pro")

        assert result['status'] == 'ok'
        assert result['requests_remaining'] == 100
        assert result['tokens_remaining'] == 50000

    @pytest.mark.asyncio
    async def test_rate_limit_check_exhausted(self):
        """Test rate limit check when rate limited."""
        mock_client = Mock()
        mock_client.models.generate_content = AsyncMock(
            side_effect=google_exceptions.ResourceExhausted("Rate limit exceeded")
        )

        result = await check_gemini_rate_limits(mock_client, "gemini-pro")

        assert result['status'] == 'rate_limited'
        assert result['requests_remaining'] == 0
        assert result['tokens_remaining'] == 0

    @pytest.mark.asyncio
    async def test_rate_limit_check_error(self):
        """Test rate limit check with other errors."""
        mock_client = Mock()
        mock_client.models.generate_content = AsyncMock(
            side_effect=Exception("Network error")
        )

        result = await check_gemini_rate_limits(mock_client, "gemini-pro")

        assert result['status'] == 'error'
        assert result['requests_remaining'] is None
        assert result['tokens_remaining'] is None


class TestIntegrationScenarios:
    """Test integration scenarios with realistic patterns."""

    @pytest.mark.asyncio
    async def test_realistic_rate_limit_scenario(self):
        """Test realistic rate limiting scenario."""
        call_count = 0

        async def mock_gemini_call():
            nonlocal call_count
            call_count += 1

            if call_count <= 2:
                # Simulate rate limiting for first two calls
                raise google_exceptions.ResourceExhausted("Rate limit exceeded")
            return "success"

        # Mock sleep to speed up test
        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await retry_with_exponential_backoff(
                mock_gemini_call,
                max_retries=3,
                base_delay=1.0
            )

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_lambda_timeout_scenario(self):
        """Test behavior when Lambda timeout approaches."""
        mock_func = AsyncMock(side_effect=google_exceptions.ResourceExhausted("Rate limit"))

        with patch('asyncio.sleep', new_callable=AsyncMock):
            with pytest.raises(RateLimitExceededException) as exc_info:  # Should be RateLimitExceededException when rate limited with timeout constraints
                await retry_with_exponential_backoff(
                    mock_func,
                    max_retries=3,
                    context_timeout_remaining=5  # Very short timeout
                )

        assert "timeout approaching" in str(exc_info.value).lower()
        assert mock_func.call_count == 0  # Should not call function if timeout is too short
