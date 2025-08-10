# Coding Standards

These standards are MANDATORY for AI agents working on the Security Design Assistant codebase. They focus on project-specific conventions essential for maintaining consistency.

## Core Standards

- **Languages & Runtimes:** Python 3.11 (strict version requirement)
- **Style & Linting:** ruff with configuration in `pyproject.toml` - combines black formatting and flake8 rules
- **Test Organization:** Tests mirror source structure in `tests/` directory with `test_` prefix

## Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Variables | snake_case | `job_id`, `client_name` |
| Functions | snake_case | `process_drawing()`, `save_checkpoint()` |
| Classes | PascalCase | `ScheduleAgent`, `JobStatus` |
| Constants | UPPER_SNAKE_CASE | `MAX_FILE_SIZE`, `PIPELINE_CONFIGS` |
| Files | snake_case.py | `schedule_agent.py`, `aws_storage.py` |

## Critical Rules

- **Always use storage abstraction:** Never directly call S3/DynamoDB - use `storage.interface` classes
- **Structured logging only:** Use `logger.info()` with structured data, never `print()` statements
- **Async-first for AI calls:** All Gemini API calls must use async/await pattern for efficiency
- **Environment-based configuration:** All settings via environment variables, never hardcoded
- **Checkpoint after each agent:** Save intermediate state after every pipeline stage completes
- **Company#client#job keys:** Always use composite keys for multi-tenant data organization
- **Type hints required:** All function signatures must include type hints for parameters and returns
- **Token limit awareness:** Check token counts before Gemini API calls - fail fast if over 80% of limit
- **Interface stability:** Never modify existing function signatures - use optional parameters for extensions

## Google GenAI SDK Patterns

### Client Initialization
```python
from google import genai
from src.config.settings import settings

# Always initialize in BaseAgentV2 or similar base class
client = genai.Client(api_key=settings.GEMINI_API_KEY)
```

### Native PDF Upload
```python
# Upload PDF directly without conversion
pdf_file = client.files.upload(path="drawing.pdf")
# File is automatically available for 48 hours
```

### Model Selection
```python
# Use Flash for cost-sensitive operations
GEMINI_FLASH = "models/gemini-2.0-flash-exp"
# Use Pro for complex analysis
GEMINI_PRO = "models/gemini-2.0-flash-exp"  # Currently using Flash for all
```

### Code Execution for Excel
```python
from google.genai import types

# Enable code execution for Excel generation
response = client.models.generate_content(
    model=GEMINI_FLASH,
    contents=[prompt],
    config=types.GenerateContentConfig(
        tools=[types.Tool(code_execution=types.ToolCodeExecution())]
    )
)
```

### Error Handling
```python
from google.api_core import exceptions

try:
    response = client.models.generate_content(...)
except exceptions.InvalidArgument as e:
    logger.error(f"Invalid request: {e}")
except exceptions.ResourceExhausted as e:
    logger.error(f"Rate limit exceeded: {e}")
    # Implement exponential backoff
```

### Testing with Mocks
```python
from unittest.mock import Mock, patch

@patch('src.agents.base_agent_v2.genai.Client')
def test_agent_behavior(mock_client):
    mock_response = Mock()
    mock_response.text = "expected_response"
    mock_client.return_value.models.generate_content.return_value = mock_response
    # Test agent logic
```
