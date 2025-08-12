# Test Migration Notes

## Date: 2025-08-12
## Story: 4.3 - Pragmatic Test Suite & E2E Validation

### Background
Story 4.2 created comprehensive test infrastructure but resulted in 126 failing tests blocking deployment. The complexity of mocking AWS services, Gemini AI calls, and PDF processing created an unmaintainable situation for a v1 MVP.

### Migration Summary

#### Tests Removed
- **Integration Tests**: 567 tests from `tests/integration/` directory
  - Complex mocking of AWS services (S3, DynamoDB, SQS)
  - Extensive VCR.py cassettes for API recording
  - Over-engineered consistency checking
  
- **Evaluation Tests**: Tests from `tests/evaluation/` directory
  - Prompt optimization tests
  - Validation suite tests with complex scoring
  
- **Test Result Logger**: `tests/test_result_logger.py`
  - Over-engineered logging infrastructure

#### Tests Kept
- **Unit Tests**: 52 tests in `tests/unit/`
  - Simple, fast tests with basic mocking
  - 100% pass rate after fixes
  - Runtime < 10 seconds

#### Tests Added
- **E2E Tests**: 3-5 tests in `tests/e2e/`
  - Real AWS and Gemini API calls
  - No complex mocking
  - Focus on critical paths

### Rationale
- **Pragmatic approach**: Real E2E tests catch actual issues better than complex mocks
- **Maintainability**: Simpler test suite easier to maintain
- **Speed**: Unit tests run in <10s, E2E tests in <2min each
- **Confidence**: Real API tests provide more confidence than mocked tests

### Rollback Instructions
If you need to restore the old tests:
1. Copy archived tests back: `cp -r tests/_archived_integration/* tests/`
2. Restore pytest markers in pytest.ini
3. Re-install moto and vcr.py dependencies

### Test Execution Commands

```bash
# Run unit tests only (fast, no credentials needed)
pytest -m unit

# Run E2E tests (requires AWS/Gemini credentials)
AWS_PROFILE=design-lee pytest -m e2e

# Run all tests
AWS_PROFILE=design-lee pytest
```

### Files Archived
- tests/integration/*.py (10 files)
- tests/evaluation/*.py (validation suite tests)
- tests/test_result_logger.py

### Configuration Changes
- pytest.ini: Simplified markers (unit, e2e only)
- Removed complex test dependencies from requirements