# Error Handling Strategy

## General Approach

- **Error Model:** Structured error classes with context preservation
- **Exception Hierarchy:** Custom exceptions for business logic, standard for system errors
- **Error Propagation:** Bubble up with context, handle at appropriate level

## Logging Standards

- **Library:** Python logging with JSON formatter
- **Format:** Structured JSON with correlation IDs
- **Levels:** ERROR (failures), WARNING (degraded), INFO (normal), DEBUG (development)
- **Required Context:**
  - Correlation ID: `job_<timestamp>` format
  - Service Context: Agent name, Lambda request ID
  - User Context: Company, client, project (no PII)

## Error Handling Patterns

### External API Errors

- **Retry Policy:** Exponential backoff with jitter (2, 4, 8 seconds)
- **Circuit Breaker:** Not needed for Phase 1 (low volume)
- **Timeout Configuration:** 
  - Gemini API: 60 seconds
  - S3 operations: 30 seconds
- **Error Translation:** Map provider errors to user-friendly messages

```python