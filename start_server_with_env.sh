#!/bin/bash

# Load environment variables from .env file
export $(cat .env | grep -v '^#' | xargs)

# Print the loaded environment variables (hiding sensitive parts)
echo "================================"
echo "Starting server with environment:"
echo "================================"
echo "GEMINI_API_KEY: ${GEMINI_API_KEY:0:20}..."
echo "STORAGE_MODE: $STORAGE_MODE"
echo "LOCAL_OUTPUT_DIR: $LOCAL_OUTPUT_DIR"
echo "================================"

# Start the server
echo "Starting FastAPI server..."
python -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000