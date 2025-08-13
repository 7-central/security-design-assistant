# Claude Developer Guidelines

## Fast Validation Workflow

When making code changes, use this fast validation loop to ensure code quality without running expensive E2E tests:

### Quick Validation (Run After Every Change)
```bash
# Run type checking and linting with strict rules
./scripts/validate_types.sh
```

### Mypy Daemon (For Instant Feedback)
```bash
# Start the daemon once per session
./scripts/start_mypy_daemon.sh

# Then use for instant checks
dmypy check src
```

### Testing Hierarchy
1. **During Development** - Run validation script frequently
2. **After Each Phase** - Run unit tests: `pytest tests/unit -m unit -v`
3. **Before Push** - Smoke test: `ENV=dev STORAGE_MODE=local pytest tests/e2e/test_error_handling_e2e.py::TestErrorHandlingE2E::test_invalid_file_upload -v`
4. **Final Validation** - Full E2E: `ENV=dev STORAGE_MODE=local pytest tests/e2e -m e2e -v`

### Pre-Push Hook
A git pre-push hook is installed that automatically runs validation before allowing pushes. This prevents broken code from reaching the repository.

## Validation Commands

### Lint and Type Checking
```bash
# Run both mypy and ruff with strict settings
./scripts/validate_types.sh

# Run mypy alone with strict settings
mypy src --strict --show-error-codes --pretty --ignore-missing-imports

# Run ruff alone with strict settings
ruff check src tests
```

### Fix Commands
```bash
# Auto-fix safe lint issues
ruff check --fix src tests

# Format code
ruff format src tests
```

## Important Notes
- Always run `./scripts/validate_types.sh` before committing
- The pre-push hook will block pushes if validation fails
- Use `# type: ignore[specific-code]` sparingly and document why