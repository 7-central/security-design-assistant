# Security Design Assistant - Usage Guide

## Quick Start

### Starting the Server

#### Option 1: Complete Test Suite (Recommended)
```bash
./test_local.sh
```
This runs validation, unit tests, then starts the server with dev AWS storage.

#### Option 2: Direct Server Start
```bash
ENV=dev STORAGE_MODE=aws AWS_PROFILE=design-lee uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

The server will be available at: `http://localhost:8000`

## Using the Application

### 1. Browser Interface (Swagger UI)

Navigate to: **http://localhost:8000/docs**

This provides an interactive interface where you can:
- Upload PDF files directly
- Test all API endpoints
- See request/response schemas
- Download results

### 2. Command Line Usage

#### Health Check
```bash
curl http://localhost:8000/health
```
Response:
```json
{"status": "healthy", "version": "1.0.0"}
```

#### Process a Drawing
```bash
curl -X POST http://localhost:8000/process-drawing \
  -F "drawing_file=@path/to/your/drawing.pdf" \
  -F "client_name=your-client" \
  -F "project_name=your-project" \
  -F "context_text=Optional context information"
```

Example with test file:
```bash
curl -X POST http://localhost:8000/process-drawing \
  -F "drawing_file=@tests/fixtures/drawings/simple_door_schedule.pdf" \
  -F "client_name=test-client" \
  -F "project_name=test-project"
```

Response:
```json
{
  "job_id": "job_20240315_abc123",
  "status": "processing",
  "estimated_time_seconds": 300,
  "metadata": {
    "file_name": "simple_door_schedule.pdf",
    "file_size_mb": 1.5,
    "total_pages": 2
  }
}
```

#### Check Job Status
```bash
curl http://localhost:8000/status/{job_id}
```

Replace `{job_id}` with the ID from the previous response.

Response when complete:
```json
{
  "job_id": "job_20240315_abc123",
  "status": "completed",
  "file_path": "test-client/test-project/job_20240315_abc123/schedule.xlsx",
  "summary": {
    "doors_found": 15,
    "processing_time_seconds": 45.2
  },
  "evaluation": {
    "overall_assessment": "High Quality",
    "completeness": 0.95,
    "correctness": 0.98
  }
}
```

#### Download Results
```bash
# Download Excel schedule
curl http://localhost:8000/download/{job_id}/excel -o schedule.xlsx

# Download components JSON
curl http://localhost:8000/download/{job_id}/components -o components.json
```

### 3. Python Script Usage

```python
import requests

# Upload a drawing
with open('drawing.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/process-drawing',
        files={'drawing_file': f},
        data={
            'client_name': 'test-client',
            'project_name': 'test-project'
        }
    )
    job_data = response.json()
    job_id = job_data['job_id']

# Check status
status = requests.get(f'http://localhost:8000/status/{job_id}').json()
print(f"Status: {status['status']}")

# Download Excel when complete
if status['status'] == 'completed':
    excel_data = requests.get(f'http://localhost:8000/download/{job_id}/excel')
    with open('schedule.xlsx', 'wb') as f:
        f.write(excel_data.content)
```

## Storage Locations

When running locally with dev AWS storage:
- **S3 Bucket**: `security-assistant-dev-445567098699`
- **DynamoDB Table**: `security-assistant-dev-jobs`
- **File Structure**: `{client_name}/{project_name}/{job_id}/`

## Development Workflow

### 1. Make Code Changes
Edit your code in your preferred editor.

### 2. Validate Code
```bash
# Quick validation only
./scripts/validate_types.sh

# Or run full test suite
./test_local.sh
```

### 3. Test Manually
Upload test PDFs and verify the output matches expectations.

### 4. Deploy to Production
```bash
git add .
git commit -m "Description of changes"
git push origin main
```

This automatically triggers deployment to AWS production.

## Monitoring & Debugging

### View Server Logs
The server logs show:
- Incoming requests
- Processing steps
- Gemini API calls
- Storage operations
- Any errors

### Check AWS Resources
```bash
# View S3 files
aws s3 ls s3://security-assistant-dev-445567098699/ --recursive --profile design-lee

# Query DynamoDB
aws dynamodb scan \
  --table-name security-assistant-dev-jobs \
  --profile design-lee \
  --region eu-west-2
```

### Common Issues

#### Server Won't Start
- Check AWS credentials: `aws sts get-caller-identity --profile design-lee`
- Verify environment variables are set
- Ensure port 8000 is not in use

#### PDF Processing Fails
- Check file size (max 100MB)
- Verify PDF is not password protected
- Check Gemini API key is set: `echo $GEMINI_API_KEY`

#### Can't Download Results
- Verify job completed successfully
- Check S3 bucket permissions
- Ensure file wasn't deleted (7-day lifecycle policy)

## Test Files

Example PDFs for testing are located in:
```
tests/fixtures/drawings/
├── simple_door_schedule.pdf       # Basic door schedule
├── complex_e1_drawing.pdf         # Complex electrical drawing
├── b2_level_plan.pdf             # Building floor plan
└── variations/                    # Various test cases
```

## API Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/process-drawing` | POST | Upload and process PDF |
| `/status/{job_id}` | GET | Check job status |
| `/download/{job_id}/excel` | GET | Download Excel schedule |
| `/download/{job_id}/components` | GET | Download components JSON |
| `/docs` | GET | Swagger UI documentation |

## Environment Variables

Required for local development:
```bash
ENV=dev                           # Environment
STORAGE_MODE=aws                  # Use AWS storage
AWS_PROFILE=design-lee           # AWS credentials profile
GEMINI_API_KEY=your-key-here    # Gemini API key
```

## Tips

1. **Use Swagger UI** for exploring the API - it's the easiest way to test
2. **Keep test PDFs small** (<5MB) for faster testing
3. **Monitor the terminal** where server is running for real-time logs
4. **Use dev storage** for all testing - never test against prod
5. **Manual testing is fine** - you're the only user, trust your judgment