#!/bin/bash

# Simple local testing script - uses dev AWS storage
# Run: ./test_local.sh

echo "========================================="
echo "Local Testing Suite"
echo "========================================="

# Set environment to use dev AWS storage
export ENV=dev
export STORAGE_MODE=aws
export AWS_PROFILE=design-lee

echo ""
echo "🔍 Running validation checks..."
echo "---------------------------------"
./scripts/validate_types.sh

if [ $? -ne 0 ]; then
    echo "❌ Validation failed. Fix issues before testing."
    exit 1
fi

echo ""
echo "🧪 Running unit tests..."
echo "---------------------------------"
pytest tests/unit -m unit -v --tb=short

if [ $? -ne 0 ]; then
    echo "❌ Unit tests failed."
    exit 1
fi

echo ""
echo "🚀 Starting API server for manual testing..."
echo "---------------------------------"
echo "Using dev AWS storage (S3 + DynamoDB)"
echo ""
echo "Test endpoints:"
echo "  curl http://localhost:8000/health"
echo "  curl -X POST http://localhost:8000/process-drawing \\"
echo "    -F 'drawing_file=@test.pdf' \\"
echo "    -F 'client_name=test' \\"
echo "    -F 'project_name=test'"
echo ""
echo "Press Ctrl+C to stop the server"
echo "---------------------------------"

# Start the FastAPI server
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000