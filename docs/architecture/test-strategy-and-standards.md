# Test Strategy and Standards

## Testing Philosophy

- **Approach:** Test-After Development with comprehensive coverage
- **Coverage Goals:** 80% unit test coverage, 100% critical path coverage
- **Test Pyramid:** 70% unit tests, 25% integration tests, 5% evaluation tests

## Test Types and Organization

### Unit Tests

- **Framework:** pytest 8.0.0
- **File Convention:** `test_<module_name>.py` in parallel directory structure
- **Location:** `tests/unit/<module_path>/`
- **Mocking Library:** pytest-mock with unittest.mock for AI responses
- **Coverage Requirement:** 80% minimum per module

**AI Agent Requirements:**
- Generate tests for all public methods
- Cover edge cases and error conditions
- Follow AAA pattern (Arrange, Act, Assert)
- Mock all external dependencies
- Mock Gemini API responses using unittest.mock

### Integration Tests

- **Scope:** End-to-end pipeline testing, multi-agent workflows
- **Location:** `tests/integration/`
- **Test Infrastructure:**
  - **Gemini API:** Mock responses using unittest.mock
  - **AWS Services:** Moto library for S3/DynamoDB mocking
  - **PDF Processing:** Test fixtures with known outputs

### End-to-End Tests

- **Framework:** pytest with real AWS services (staging environment)
- **Scope:** Full drawing processing with actual AI calls
- **Environment:** Staging AWS deployment
- **Test Data:** Curated set of 10 drawing variations in `tests/fixtures/drawings/`

## Test Data Management

- **Strategy:** Fixture-based with version control
- **Fixtures:** `tests/fixtures/` organized by type
- **Factories:** Not needed for Phase 1 (static test data)
- **Cleanup:** Automatic via pytest fixtures and AWS TTL

## Continuous Testing

- **CI Integration:** 
  - Unit/Integration tests on every commit
  - Evaluation tests weekly or after prompt changes
- **Performance Tests:** Manual benchmark suite (future phase)
- **Security Tests:** Dependency scanning via GitHub Dependabot

## AI Test Generation Guidelines

**AI agents must follow these rules when writing tests:**

1. **Test public interfaces only** - Never test private methods or internal state
2. **Mock AI responses** - Use unittest.mock for Gemini API calls
3. **Test business outcomes** - "Found 10 doors" not "Called API 3 times"
4. **Follow naming pattern** - `test_<agent>_<action>_<expected_outcome>`
5. **Include domain context** - Test security-specific edge cases (empty legend, overlapping symbols)
6. **Mock hygiene** - Clear, descriptive mock setups with realistic responses
7. **No random data** - Use deterministic fixtures from `tests/fixtures/`

**Good test example:**
```python
@patch('src.agents.schedule_agent_v2.genai.Client')
def test_schedule_agent_extracts_door_components(mock_client):
    """Test that schedule agent correctly identifies access control components."""
    # Setup mock response
    mock_response = Mock()
    mock_response.text = json.dumps({
        'components': [
            {'id': 'A-101', 'type': 'door', 'location': 'Main entrance'},
            {'id': 'A-101-R', 'type': 'reader', 'location': 'Main entrance'}
        ]
    })
    mock_client.return_value.models.generate_content.return_value = mock_response
    
    agent = ScheduleAgentV2(storage=Mock(), job=Mock())
    test_drawing = "tests/fixtures/drawings/simple_access_control.pdf"
    components = agent.extract_components(test_drawing)
    
    assert len(components) == 2
    assert all(c['type'] in ['door', 'reader', 'exit_button'] for c in components)
    assert all(c['id'].startswith('A-') for c in components)
```

## Critical Test Scenarios by Agent

**Note:** These are automated test specifications for developers. Before implementing these tests, test fixture documents must be created or collected. Most can be simple examples or generated samples. The test suite uses unittest.mock to simulate AI responses for consistent, fast testing.

### Context Agent Test Cases
1. **Parse simple DOCX with lock specifications** - Extract lock types 11-22 from tables
2. **Handle multi-section specifications** - Correctly identify relevant vs irrelevant sections
3. **Process scanned PDF context** - Use Gemini Flash for OCR and extraction
4. **Empty context document** - Gracefully handle files with no relevant content
5. **Malformed document** - Error handling for corrupted files
6. **Large context file** - Performance with 100+ page specifications

### Schedule Agent Test Cases
1. **Standard single-page drawing** - Extract all A-prefix components correctly
2. **Multi-page mixed systems** - Filter security pages from electrical/plumbing
3. **Dense overlapping annotations** - Handle text overlap near door symbols
4. **Non-standard component IDs** - Recognize variations like A.101.DR.B2
5. **Missing door labels** - Infer door locations from reader/button placement
6. **Rotated/skewed pages** - Process drawings at various orientations
7. **Poor scan quality** - Low resolution or grainy images
8. **Empty drawing legend** - Work without symbol definitions
9. **Duplicate component IDs** - Handle naming conflicts
10. **CCTV/Intruder mixed drawing** - Correctly ignore C- and I- prefix items

### Code Generation Agent Test Cases
1. **Standard door schedule** - Generate Excel with all required columns
2. **Dynamic lock type columns** - Add columns based on found lock types
3. **Missing components** - Handle doors without readers or exit buttons
4. **Special formatting requests** - Apply conditional formatting for lock types
5. **Large component sets** - Performance with 200+ doors
6. **Unicode in locations** - Handle international characters in door names
7. **Summary calculations** - Correct totals and subtotals
8. **Empty component list** - Graceful handling of no components found

### Judge Agent Test Cases
1. **High-accuracy extraction** - Recognize and praise good results
2. **Missed components** - Identify specific missing items
3. **False positives** - Detect incorrectly identified components
4. **Partial success** - Balanced evaluation of mixed results
5. **Context alignment** - Verify specifications were applied correctly
6. **Spatial relationship errors** - Detect wrong door-reader associations
7. **Improvement suggestions** - Provide actionable feedback

### Integration Test Scenarios
1. **Happy path full pipeline** - Drawing → Context → Extract → Excel → Judge
2. **No context pipeline** - Skip context agent when not provided
3. **Pipeline recovery** - Resume from checkpoint after simulated failure
4. **Concurrent job processing** - Multiple jobs don't interfere
5. **Large drawing timeout** - Checkpoint and resume after Lambda timeout
6. **Invalid input rejection** - Non-PDF files fail fast with clear errors
