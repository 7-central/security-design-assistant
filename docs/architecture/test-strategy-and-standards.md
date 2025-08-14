# Test Strategy and Standards (Simplified)

## Testing Philosophy

**Local validation with real services over complex automation**

Our testing approach has been simplified to match the single-user nature of this application. We prioritize fast local validation and manual testing over complex automated pipelines.

### Core Principles
- Unit tests validate business logic with mocks
- Manual testing validates real system behavior
- No CI/CD pipeline - all tests run locally
- Focus on developer productivity over coverage metrics

## Test Types

### Unit Tests

- **Framework:** pytest 8.0.0
- **Location:** `tests/unit/`
- **Mocking:** pytest-mock for external dependencies
- **Execution:** `pytest tests/unit -m unit -v`
- **Purpose:** Fast validation of business logic

**What We Test:**
- Core business logic
- Data transformations
- Error handling
- Agent behavior (with mocked APIs)

**What We Mock:**
- Gemini API calls
- AWS S3/DynamoDB operations
- External HTTP requests
- File system operations

### Manual Testing (Replaced E2E Tests)

- **Tool:** Swagger UI at http://localhost:8000/docs
- **Storage:** Dev AWS resources (S3 + DynamoDB)
- **Execution:** Upload test PDFs and verify results
- **Purpose:** Validate full pipeline with real services

**Test Process:**
1. Start server with `./test_local.sh`
2. Upload test PDF via Swagger UI
3. Verify job completes successfully
4. Download and check Excel output
5. Verify S3/DynamoDB entries if needed

## Test Execution

### Complete Test Suite
```bash
./test_local.sh
```
This script:
1. Runs type checking (mypy)
2. Runs linting (ruff)
3. Runs unit tests
4. Starts server for manual testing

### Quick Validation
```bash
# Type checking and linting only
./scripts/validate_types.sh

# Unit tests only
pytest tests/unit -m unit -v
```

### Manual Testing Checklist
- [ ] Upload simple door schedule PDF
- [ ] Upload complex multi-page drawing
- [ ] Test with context file
- [ ] Verify Excel output correctness
- [ ] Check error handling (invalid PDF)

## Quality Gates

### Pre-Push Hook
Automatically runs before git push:
- Type checking with mypy (strict mode)
- Linting with ruff
- Blocks push if validation fails

### Local Development
- Run `./scripts/validate_types.sh` frequently
- Run unit tests after significant changes
- Manual test before pushing to main

## Test Data

### Test PDFs
Located in `tests/fixtures/drawings/`:
- `simple_door_schedule.pdf` - Basic test case
- `complex_e1_drawing.pdf` - Complex components
- `b2_level_plan.pdf` - Multi-page test
- `variations/` - Edge cases

### Dev AWS Resources
- **S3 Bucket:** `security-assistant-dev-445567098699`
- **DynamoDB:** `security-assistant-dev-jobs`
- **Lifecycle:** 7-day auto-deletion
- **Cost:** <$1/month

## What We DON'T Do Anymore

### Removed Complexity
- ❌ **E2E test automation** - Manual testing is sufficient
- ❌ **CI/CD test execution** - Tests run locally only
- ❌ **Coverage requirements** - Quality over metrics
- ❌ **Integration tests** - Either unit or manual
- ❌ **Staging validation** - Test with dev storage

### Why We Simplified
- Single-user application
- Quick fix and redeploy capability
- Manual testing takes <5 minutes
- Automation maintenance exceeded value

## When to Add Complexity

### Add E2E Automation When:
- API grows beyond 10 endpoints
- Multiple users require stability
- Manual testing takes >15 minutes
- Regression bugs become frequent

### Add CI/CD Testing When:
- Multiple developers contribute
- External users depend on service
- Deployment frequency increases
- Quality issues emerge

## Best Practices

### Writing Unit Tests
```python
def test_component_extraction():
    """Test that components are correctly extracted from page data."""
    # Arrange
    mock_response = {"components": [...]}
    
    # Act
    result = extract_components(mock_response)
    
    # Assert
    assert len(result) == 5
    assert result[0].type == "door"
```

### Manual Testing Discipline
1. Always test after significant changes
2. Use consistent test data
3. Document unexpected behaviors
4. Verify both success and error paths

## Summary

Our simplified test strategy acknowledges that:
- **Quality doesn't require complexity**
- **Manual testing is valid for small apps**
- **Local validation catches most issues**
- **Single-user apps have different needs**

The focus is on maintaining code quality through local validation while avoiding the overhead of complex test automation that provides minimal value for a single-user application.