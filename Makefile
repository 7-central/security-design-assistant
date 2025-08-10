# Security Design Assistant - Validation Suite Makefile

.PHONY: help test validation-suite validation-dry-run lint type-check format clean

# Default target
help:
	@echo "Available commands:"
	@echo "  test              - Run all tests"
	@echo "  test-unit         - Run unit tests only"
	@echo "  test-integration  - Run integration tests only"
	@echo "  test-evaluation   - Run evaluation tests (requires RUN_EVAL_TESTS=true)"
	@echo "  validation-suite  - Run complete validation suite"
	@echo "  validation-dry-run - Run validation suite in dry-run mode (cost estimation)"
	@echo "  lint              - Run code linting with ruff"
	@echo "  type-check        - Run type checking with mypy"
	@echo "  format            - Format code with ruff"
	@echo "  clean             - Clean up temporary files"

# Testing commands
test:
	python -m pytest tests/ -v

test-unit:
	python -m pytest tests/unit/ -v

test-integration:
	python -m pytest tests/integration/ -v

test-evaluation:
	RUN_EVAL_TESTS=true python -m pytest tests/evaluation/ -v

test-validation-suite:
	python -m pytest tests/evaluation/test_validation_suite.py -v

# Validation Suite commands
validation-suite:
	@echo "Running complete validation suite..."
	@echo "This will process all test drawings and generate comprehensive reports."
	@echo "Estimated cost: Run 'make validation-dry-run' first to see cost estimate."
	@read -p "Continue? [y/N] " -n 1 -r; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		echo; \
		python scripts/validation_suite.py; \
	else \
		echo; \
		echo "Cancelled."; \
	fi

validation-dry-run:
	@echo "Running validation suite dry run (cost estimation only)..."
	python scripts/validation_suite.py --dry-run

validation-suite-baseline:
	@echo "Running validation suite on baseline drawings only..."
	python scripts/validation_suite.py --drawings "01_*.pdf"

validation-suite-with-context:
	@echo "Running validation suite with context document..."
	@if [ -f "tests/fixtures/context.docx" ]; then \
		python scripts/validation_suite.py --context tests/fixtures/context.docx; \
	else \
		echo "No context file found at tests/fixtures/context.docx"; \
		echo "Running without context..."; \
		python scripts/validation_suite.py; \
	fi

# Code quality commands
lint:
	python -m ruff check .

lint-fix:
	python -m ruff check . --fix

type-check:
	python -m mypy src/ tests/

format:
	python -m ruff format .

# Development commands
install-dev:
	pip install -r requirements.txt
	pip install pytest mypy ruff

setup-validation-env:
	@echo "Setting up validation suite environment..."
	mkdir -p tests/fixtures/validation_suite
	mkdir -p tests/evaluation/validation_suite/results
	mkdir -p tests/evaluation/validation_suite/reports
	mkdir -p tests/evaluation/validation_suite/alerts
	@echo "Validation suite directories created."

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true

# Comprehensive validation workflow
validation-workflow:
	@echo "Running comprehensive validation workflow..."
	@echo "1. Running dry run for cost estimation..."
	python scripts/validation_suite.py --dry-run
	@echo
	@echo "2. Running validation suite tests..."
	python -m pytest tests/evaluation/test_validation_suite.py -v
	@echo
	@echo "3. Running code quality checks..."
	python -m ruff check scripts/validation_suite.py src/utils/validation_report_generator.py src/utils/success_criteria_validator.py src/utils/recommendations_engine.py
	@echo
	@echo "✅ Validation workflow complete!"

# CI/CD integration
ci-validation:
	python -m ruff check .
	python -m mypy src/ --no-error-summary
	python -m pytest tests/unit/ tests/integration/ -v
	python -m pytest tests/evaluation/test_validation_suite.py -v
	@echo "✅ CI validation checks passed!"

# Documentation generation (if needed in future)
docs-validation:
	@echo "Generating validation suite documentation..."
	@echo "📝 Validation suite components:"
	@echo "  - ValidationSuite: scripts/validation_suite.py"
	@echo "  - ReportGenerator: src/utils/validation_report_generator.py"
	@echo "  - SuccessCriteriaValidator: src/utils/success_criteria_validator.py"
	@echo "  - RecommendationsEngine: src/utils/recommendations_engine.py"
	@echo "  - Tests: tests/evaluation/test_validation_suite.py"