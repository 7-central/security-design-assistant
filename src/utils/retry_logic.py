"""
Retry logic with rate limit detection for Gemini API calls.
Provides exponential backoff and rate limit handling for Lambda constraints.
"""

import asyncio
import logging
import random
import time
from collections.abc import Callable
from typing import Any

from google.api_core import exceptions as google_exceptions

logger = logging.getLogger(__name__)


class RetryExhaustedException(Exception):
    """Raised when maximum retry attempts are exceeded."""
    pass


class RateLimitExceededException(Exception):
    """Raised when rate limit is exceeded and cannot be retried."""
    pass


async def retry_with_exponential_backoff(
    func: Callable,
    *args,
    max_retries: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    context_timeout_remaining: float | None = None,
    **kwargs
) -> Any:
    """
    Retry function with exponential backoff and Gemini-specific error handling.

    Args:
        func: Async function to retry
        *args: Arguments for the function
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds for exponential backoff
        max_delay: Maximum delay between retries
        jitter: Add random jitter to delay
        context_timeout_remaining: Lambda timeout remaining in seconds
        **kwargs: Keyword arguments for the function

    Returns:
        Function result

    Raises:
        RetryExhaustedException: If max retries exceeded
        RateLimitExceededException: If rate limit cannot be handled
    """

    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            # Check if we have enough time for this attempt
            if context_timeout_remaining:
                estimated_time = base_delay * (2 ** attempt)
                if context_timeout_remaining < estimated_time + 30:  # 30s buffer
                    logger.warning(
                        f"Insufficient time remaining ({context_timeout_remaining}s) "
                        f"for retry attempt {attempt}, estimated time: {estimated_time}s"
                    )
                    raise RetryExhaustedException(
                        f"Timeout approaching, cannot complete retry attempt {attempt}"
                    )

            # Execute function
            result = await func(*args, **kwargs)

            if attempt > 0:
                logger.info(f"Function succeeded on retry attempt {attempt}")

            return result

        except google_exceptions.ResourceExhausted as e:
            # Rate limit exceeded
            last_exception = e

            # Extract rate limit information from headers if available
            rate_limit_reset = _extract_rate_limit_reset(e)

            if attempt >= max_retries:
                logger.error(f"Rate limit exceeded, max retries ({max_retries}) reached")
                raise RateLimitExceededException(
                    f"Gemini API rate limit exceeded after {max_retries} attempts"
                ) from e

            # Calculate delay based on rate limit reset time or exponential backoff
            if rate_limit_reset:
                delay = min(rate_limit_reset, max_delay)
                logger.warning(
                    f"Rate limit exceeded (attempt {attempt + 1}/{max_retries + 1}), "
                    f"waiting {delay}s based on reset time"
                )
            else:
                delay = _calculate_exponential_backoff(attempt, base_delay, max_delay, jitter)
                logger.warning(
                    f"Rate limit exceeded (attempt {attempt + 1}/{max_retries + 1}), "
                    f"using exponential backoff: {delay}s"
                )

            # Check if we have time to wait and retry
            if context_timeout_remaining and context_timeout_remaining < delay + 30:
                logger.warning(
                    f"Insufficient time remaining ({context_timeout_remaining}s) "
                    f"for delay ({delay}s), cannot retry"
                )
                raise RateLimitExceededException(
                    "Timeout approaching, cannot wait for rate limit reset"
                ) from e

            await asyncio.sleep(delay)

        except google_exceptions.InvalidArgument as e:
            # Invalid request - don't retry
            logger.error(f"Invalid request to Gemini API: {e}")
            raise

        except google_exceptions.DeadlineExceeded as e:
            # Timeout - retry with exponential backoff
            last_exception = e

            if attempt >= max_retries:
                logger.error(f"Request timeout, max retries ({max_retries}) reached")
                raise RetryExhaustedException(
                    f"Gemini API timeout after {max_retries} attempts"
                ) from e

            delay = _calculate_exponential_backoff(attempt, base_delay, max_delay, jitter)
            logger.warning(
                f"Request timeout (attempt {attempt + 1}/{max_retries + 1}), "
                f"retrying in {delay}s"
            )

            await asyncio.sleep(delay)

        except google_exceptions.ServiceUnavailable as e:
            # Service unavailable - retry with exponential backoff
            last_exception = e

            if attempt >= max_retries:
                logger.error(f"Service unavailable, max retries ({max_retries}) reached")
                raise RetryExhaustedException(
                    f"Gemini API service unavailable after {max_retries} attempts"
                ) from e

            delay = _calculate_exponential_backoff(attempt, base_delay, max_delay, jitter)
            logger.warning(
                f"Service unavailable (attempt {attempt + 1}/{max_retries + 1}), "
                f"retrying in {delay}s"
            )

            await asyncio.sleep(delay)

        except Exception as e:
            # Other exceptions - don't retry
            logger.error(f"Non-retryable error in Gemini API call: {type(e).__name__}: {e}")
            raise

    # Should never reach here, but just in case
    raise RetryExhaustedException(
        f"Max retries ({max_retries}) exceeded"
    ) from last_exception


def _calculate_exponential_backoff(
    attempt: int,
    base_delay: float,
    max_delay: float,
    jitter: bool
) -> float:
    """Calculate exponential backoff delay with optional jitter."""
    delay = min(base_delay * (2 ** attempt), max_delay)

    if jitter:
        # Add ±25% jitter
        jitter_range = delay * 0.25
        delay += random.uniform(-jitter_range, jitter_range)
        delay = max(0, delay)  # Ensure non-negative

    return delay


def _extract_rate_limit_reset(exception: google_exceptions.ResourceExhausted) -> float | None:
    """
    Extract rate limit reset time from exception headers.

    Args:
        exception: ResourceExhausted exception from Google API

    Returns:
        Reset time in seconds, or None if not available
    """
    try:
        # Try to extract from exception metadata
        if hasattr(exception, 'response') and exception.response:
            headers = getattr(exception.response, 'headers', {})

            # Look for common rate limit headers
            reset_time = None
            if 'retry-after' in headers:
                reset_time = float(headers['retry-after'])
            elif 'x-ratelimit-reset' in headers:
                reset_timestamp = int(headers['x-ratelimit-reset'])
                reset_time = max(0, reset_timestamp - int(time.time()))
            elif 'x-ratelimit-reset-after' in headers:
                reset_time = float(headers['x-ratelimit-reset-after'])

            if reset_time:
                logger.info(f"Found rate limit reset time: {reset_time}s")
                return reset_time

    except Exception as e:
        logger.debug(f"Could not extract rate limit reset time: {e}")

    return None


async def check_gemini_rate_limits(client, model: str) -> dict[str, Any]:
    """
    Check current rate limit status for Gemini API.

    Args:
        client: Gemini client instance
        model: Model name to check

    Returns:
        Rate limit information dictionary
    """
    try:
        # Make a minimal request to check rate limits
        # This is a placeholder - actual implementation depends on available API
        response = await client.models.generate_content(
            model=model,
            contents=["test"],
            config={'max_output_tokens': 1}
        )

        # Extract rate limit info from response headers if available
        rate_limit_info = {
            'requests_remaining': None,
            'tokens_remaining': None,
            'reset_time': None,
            'status': 'ok'
        }

        # This would need to be adapted based on actual Gemini API headers
        if hasattr(response, 'headers'):
            headers = response.headers
            if 'x-ratelimit-requests-remaining' in headers:
                rate_limit_info['requests_remaining'] = int(headers['x-ratelimit-requests-remaining'])
            if 'x-ratelimit-tokens-remaining' in headers:
                rate_limit_info['tokens_remaining'] = int(headers['x-ratelimit-tokens-remaining'])
            if 'x-ratelimit-reset' in headers:
                rate_limit_info['reset_time'] = int(headers['x-ratelimit-reset'])

        return rate_limit_info

    except google_exceptions.ResourceExhausted as e:
        return {
            'requests_remaining': 0,
            'tokens_remaining': 0,
            'reset_time': _extract_rate_limit_reset(e),
            'status': 'rate_limited'
        }

    except Exception as e:
        logger.error(f"Error checking rate limits: {e}")
        return {
            'requests_remaining': None,
            'tokens_remaining': None,
            'reset_time': None,
            'status': 'error'
        }
