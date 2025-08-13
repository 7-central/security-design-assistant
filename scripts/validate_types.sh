#!/bin/bash

# Fast validation script for type checking and linting
# This script runs locally with strict rules while CI remains relaxed

set -e  # Exit on first error

echo "========================================="
echo "Fast Local Validation Loop"
echo "========================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track overall status
VALIDATION_PASSED=true

# Run mypy with strict settings (show first 50 errors for readability)
echo "🔍 Running type checks..."
echo "------------------------"
if mypy src --show-error-codes --pretty --strict --ignore-missing-imports 2>&1 | tee /tmp/mypy_output.txt; then
    echo -e "${GREEN}✓ Type checking passed${NC}"
else
    MYPY_EXIT_CODE=$?
    ERROR_COUNT=$(grep -c "error:" /tmp/mypy_output.txt || true)
    echo -e "${RED}✗ Type checking failed with $ERROR_COUNT errors${NC}"
    echo ""
    echo "Top error types:"
    grep "error:" /tmp/mypy_output.txt | cut -d'[' -f2 | cut -d']' -f1 | sort | uniq -c | sort -rn | head -10
    VALIDATION_PASSED=false
fi

echo ""

# Run ruff with strict settings (removing relaxed rules)
echo "🔍 Running lint checks..."
echo "------------------------"
if ruff check src tests
then
    echo -e "${GREEN}✓ Lint checking passed${NC}"
else
    echo -e "${RED}✗ Lint checking failed${NC}"
    VALIDATION_PASSED=false
fi

echo ""

# Summary
echo "========================================="
if [ "$VALIDATION_PASSED" = true ]; then
    echo -e "${GREEN}✅ All validation checks passed!${NC}"
    echo "Ready for unit testing."
    exit 0
else
    echo -e "${YELLOW}⚠️  Validation checks failed${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Fix the errors shown above"
    echo "2. Run this script again: ./scripts/validate_types.sh"
    echo "3. Once clean, run unit tests: pytest tests/unit -m unit -v"
    exit 1
fi