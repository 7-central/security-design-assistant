# E2E Test Troubleshooting Guide

## Prerequisites Checklist

Before running E2E tests, ensure you have:

1. **Dev AWS Resources Deployed**
   ```bash
   # Check if dev resources exist
   aws s3 ls s3://security-assistant-dev-445567098699 --profile design-lee
   aws dynamodb describe-table --table-name security-assistant-dev-jobs --profile design-lee --region eu-west-2
   ```

2. **Environment Configuration**
   ```bash
   # Verify .env file has correct settings
   cat .env | grep -E "ENV|STORAGE_MODE|GEMINI_API_KEY"
   # Should show: ENV=dev, STORAGE_MODE=aws, and your API key
   ```

3. **AWS Profile Configured**
   ```bash
   aws configure list --profile design-lee
   # Should show your AWS credentials
   ```

## Common Issues and Solutions

### 1. E2E Tests Fail with "bucket does not exist"

**Error**: `botocore.exceptions.NoSuchBucket: The specified bucket does not exist`

**Solution**:
```bash
# Deploy dev resources first
cd infrastructure
sam deploy --template-file dev-template.yaml --stack-name security-assistant-dev \
  --capabilities CAPABILITY_IAM --region eu-west-2 --profile design-lee \
  --s3-bucket security-assistant-sam-deployments --no-confirm-changeset
```

### 2. FastAPI Server Fails to Start

**Error**: `RuntimeError: FastAPI server failed to start`

**Causes & Solutions**:

a) **Port already in use**
   ```bash
   # Check what's using port 8000
   lsof -i :8000  # macOS/Linux
   netstat -ano | findstr :8000  # Windows
   
   # Kill the process or use a different port
   ```

b) **Import errors**
   ```bash
   # Ensure all dependencies are installed
   pip install -r requirements.txt
   pip install httpx uvicorn
   ```

### 3. Gemini API Key Issues

**Error**: `GEMINI_API_KEY not set in environment`

**Solution**:
```bash
# Add to .env file
echo "GEMINI_API_KEY=your_actual_key_here" >> .env

# Or export directly
export GEMINI_API_KEY="your_actual_key_here"
```

### 4. AWS Credentials Not Found

**Error**: `Unable to locate credentials`

**Solution**:
```bash
# Configure AWS profile
aws configure --profile design-lee

# Or set environment variable
export AWS_PROFILE=design-lee
export AWS_DEFAULT_REGION=eu-west-2
```

### 5. DynamoDB Table Not Found

**Error**: `ResourceNotFoundException: Requested resource not found`

**Solution**:
```bash
# Verify table exists
aws dynamodb list-tables --profile design-lee --region eu-west-2

# If missing, redeploy dev resources
cd infrastructure
sam deploy --template-file dev-template.yaml ...
```

### 6. Test Timeout Issues

**Error**: `Job did not complete within timeout`

**Causes & Solutions**:

a) **Slow Gemini API response**
   - Increase timeout in test (default is 120 seconds)
   - Check Gemini API status at https://status.cloud.google.com/

b) **Processing actually failed**
   - Check job status in DynamoDB
   - Review CloudWatch logs if available

### 7. Module Import Errors

**Error**: `ModuleNotFoundError: No module named 'src'`

**Solution**:
```bash
# Run tests from project root
cd /path/to/security-design-assistant
pytest tests/e2e -m e2e

# Not from tests directory
# ❌ cd tests && pytest e2e
```

### 8. Environment Variable Not Loading

**Error**: Tests using wrong resources (prod instead of dev)

**Solution**:
```bash
# Explicitly set environment
ENV=dev STORAGE_MODE=aws pytest tests/e2e -m e2e

# Or source .env file
set -a && source .env && set +a
pytest tests/e2e -m e2e
```

## Debugging Tips

### 1. Verbose Output
```bash
# Show detailed test output
pytest tests/e2e -m e2e -v -s

# Show all print statements
pytest tests/e2e -m e2e --capture=no
```

### 2. Run Single Test
```bash
# Test specific scenario
pytest tests/e2e/test_full_pipeline_e2e.py::TestFullPipelineE2E::test_full_pipeline_with_b2_drawing -v
```

### 3. Check Server Logs
```python
# In conftest.py, change log_level
config = uvicorn.Config(
    app=app,
    host="127.0.0.1",
    port=8000,
    log_level="debug"  # Changed from "warning"
)
```

### 4. Verify API Manually
```bash
# Start server manually
uvicorn src.api.main:app --reload

# In another terminal, test endpoints
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/v1/process \
  -H "Content-Type: application/json" \
  -d '{"job_id": "test123", "client_name": "test", "project_name": "test", "file_path": "s3://..."}'
```

### 5. Check AWS Resources
```bash
# List S3 objects
aws s3 ls s3://security-assistant-dev-445567098699/ --recursive --profile design-lee

# Query DynamoDB
aws dynamodb scan --table-name security-assistant-dev-jobs \
  --profile design-lee --region eu-west-2
```

## Clean Up After Testing

```bash
# Remove test files from S3
aws s3 rm s3://security-assistant-dev-445567098699/ --recursive --profile design-lee

# Clear local test output
rm -rf local_output/*

# Stop any running servers
pkill -f uvicorn
```

## Still Having Issues?

1. Check the [main troubleshooting guide](../README.md#troubleshooting)
2. Review test logs in `tests/results/` directory
3. Open an issue at https://github.com/7-central/security-design-assistant/issues