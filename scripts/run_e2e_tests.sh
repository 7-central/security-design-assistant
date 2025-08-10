#!/bin/bash

# End-to-End Test Runner Script
# Executes integration tests for Security Design Assistant

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="local"
API_BASE_URL="http://localhost:8000"
GENERATE_REPORT=false
VERBOSE=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --url)
            API_BASE_URL="$2"
            shift 2
            ;;
        --report)
            GENERATE_REPORT=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --env ENV        Environment to test against (local|staging|prod) [default: local]"
            echo "  --url URL        API base URL [default: http://localhost:8000]"
            echo "  --report         Generate HTML test report"
            echo "  --verbose, -v    Verbose output"
            echo "  --help, -h       Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                           # Run tests against local environment"
            echo "  $0 --env staging             # Run tests against staging"
            echo "  $0 --url http://api.test    # Run tests against custom URL"
            echo "  $0 --report                  # Generate HTML report"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Set environment-specific URLs
case $ENVIRONMENT in
    local)
        API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
        ;;
    staging)
        API_BASE_URL="${API_BASE_URL:-https://staging-api.7central.com}"
        ;;
    prod)
        echo -e "${RED}ERROR: E2E tests should not run against production!${NC}"
        exit 1
        ;;
    *)
        echo -e "${YELLOW}Warning: Unknown environment '$ENVIRONMENT', using provided URL${NC}"
        ;;
esac

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   E2E Test Runner - Security Design${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Environment: $ENVIRONMENT"
echo "API URL: $API_BASE_URL"
echo "Generate Report: $GENERATE_REPORT"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}ERROR: Python 3 is not installed${NC}"
    exit 1
fi

# Check Python version (should be 3.11)
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
if [[ "$PYTHON_VERSION" != "3.11" ]]; then
    echo -e "${YELLOW}Warning: Python $PYTHON_VERSION detected, 3.11 recommended${NC}"
fi

# Check if pytest is installed
if ! python3 -m pytest --version &> /dev/null; then
    echo -e "${RED}ERROR: pytest is not installed${NC}"
    echo "Install with: pip install pytest pytest-html httpx openpyxl"
    exit 1
fi

# Export environment variables for tests
export API_BASE_URL="$API_BASE_URL"
export STORAGE_MODE="local"
export LOCAL_OUTPUT_DIR="./output"

# Create output directory if it doesn't exist
mkdir -p ./output
mkdir -p ./test-reports

# Check if API is running (for local environment)
if [[ "$ENVIRONMENT" == "local" ]]; then
    echo "Checking if API is running..."
    if ! curl -s -f -o /dev/null "$API_BASE_URL/health"; then
        echo -e "${YELLOW}Warning: API at $API_BASE_URL is not responding${NC}"
        echo "Please ensure the API is running before running tests"
        echo "Start with: python -m uvicorn src.api.main:app --reload"
        exit 1
    fi
    echo -e "${GREEN}✓ API is running${NC}"
fi

# Build pytest command
PYTEST_CMD="python3 -m pytest tests/integration/test_e2e.py"

# Add verbose flag if requested
if [[ "$VERBOSE" == true ]]; then
    PYTEST_CMD="$PYTEST_CMD -v"
else
    PYTEST_CMD="$PYTEST_CMD -q"
fi

# Add test report generation if requested
if [[ "$GENERATE_REPORT" == true ]]; then
    REPORT_FILE="./test-reports/e2e_report_$(date +%Y%m%d_%H%M%S).html"
    PYTEST_CMD="$PYTEST_CMD --html=$REPORT_FILE --self-contained-html"
fi

# Add additional pytest options
PYTEST_CMD="$PYTEST_CMD --tb=short --color=yes"

# Run the tests
echo ""
echo "Running E2E tests..."
echo "Command: $PYTEST_CMD"
echo ""

if $PYTEST_CMD; then
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}   ✓ All E2E tests passed!${NC}"
    echo -e "${GREEN}========================================${NC}"
    
    if [[ "$GENERATE_REPORT" == true ]]; then
        echo ""
        echo "Test report generated: $REPORT_FILE"
        
        # Open report in browser if on macOS
        if [[ "$OSTYPE" == "darwin"* ]]; then
            open "$REPORT_FILE"
        fi
    fi
    
    exit 0
else
    EXIT_CODE=$?
    echo ""
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}   ✗ E2E tests failed${NC}"
    echo -e "${RED}========================================${NC}"
    
    if [[ "$GENERATE_REPORT" == true ]]; then
        echo ""
        echo "Test report generated: $REPORT_FILE"
        echo "Review the report for detailed failure information"
    fi
    
    echo ""
    echo "Troubleshooting tips:"
    echo "1. Check if the API is running: curl $API_BASE_URL/health"
    echo "2. Verify test fixtures exist: ls -la tests/fixtures/pdfs/"
    echo "3. Check API logs for errors"
    echo "4. Run with --verbose flag for more details"
    
    exit $EXIT_CODE
fi