# Security Design Assistant

An AI-powered system that analyzes security drawings and floor plans to automatically generate comprehensive security equipment schedules in Excel format.

## Project Overview

The Security Design Assistant streamlines the process of creating security equipment schedules from architectural drawings. By leveraging Google's Gemini AI, it:

- Extracts text and visual information from PDF drawings
- Identifies security components (doors, cameras, sensors, etc.)
- Generates detailed Excel schedules with component specifications
- Validates accuracy through multi-stage processing

## Repository Information

**Repository**: https://github.com/7-central/security-design-assistant  
**Owner**: 7-central (info@7central.co.uk)  
**Developer**: Lee Hayton

## Architecture

### Simplified Single-User Design

This application uses a streamlined architecture optimized for single-user operation:

- **Local Development**: FastAPI server runs locally, uses dev AWS storage for testing
- **Production Deployment**: Serverless AWS Lambda + API Gateway
- **No CI/CD Pipeline**: Quality checks run locally via pre-push hooks
- **Direct Deployment**: Push to main branch auto-deploys to production

### Storage Architecture

- **Development**: AWS S3 + DynamoDB (dev environment only)
- **Production**: AWS S3 + DynamoDB (production environment)
- **Local Testing**: Can use either local files or dev AWS storage

## Quick Start

### 1. Prerequisites

- Python 3.11 (strict requirement)
- AWS CLI configured with `design-lee` profile
- Gemini API key
- poppler-utils (for PDF processing)

### 2. Installation

```bash
# Clone repository
git clone https://github.com/7-central/security-design-assistant.git
cd security-design-assistant

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install poppler (macOS)
brew install poppler
```

### 3. Configuration

Create `.env` file:
```bash
GEMINI_API_KEY=your-key-here
ENV=dev
STORAGE_MODE=aws
AWS_PROFILE=design-lee
```

### 4. Run Tests & Start Server

```bash
# Complete test suite + server start
./test_local.sh

# Or start server directly
uvicorn src.api.main:app --reload
```

### 5. Use the Application

Open browser to: **http://localhost:8000/docs**

Upload a PDF drawing and get back an Excel schedule!

## Development Workflow

### Local Development
1. Make code changes
2. Run `./test_local.sh` (validation + tests + server)
3. Test manually with Swagger UI
4. Commit and push to feature branch

### Deployment to Production
```bash
git checkout main
git merge feature-branch
git push origin main  # Auto-deploys to AWS
```

### Testing Strategy

- **Unit Tests**: Mock external dependencies, test business logic
- **Manual Testing**: Use Swagger UI with dev AWS storage
- **Validation**: Automatic pre-push hooks ensure code quality

No automated E2E tests - replaced with manual testing using real dev storage.

## Project Structure

```
security-design-assistant/
├── src/
│   ├── api/              # FastAPI application
│   ├── agents/           # AI processing agents
│   ├── models/           # Data models
│   ├── storage/          # Storage abstraction
│   └── utils/            # Utilities
├── tests/
│   └── unit/            # Unit tests only
├── infrastructure/       # AWS SAM templates
├── scripts/             # Development scripts
├── test_local.sh        # Local test runner
├── USAGE.md            # Detailed usage guide
└── CLAUDE.md           # Development guidelines
```

## Key Files

- **USAGE.md** - Complete guide on using the application
- **CLAUDE.md** - Development workflow and guidelines
- **test_local.sh** - Run validation, tests, and start server
- **.github/workflows/deploy-production.yml** - Auto-deploy on push to main

## AWS Resources

### Development (Storage Only)
- S3 Bucket: `security-assistant-dev-445567098699`
- DynamoDB: `security-assistant-dev-jobs`
- Cost: <$1/month

### Production (Full Stack)
- API Gateway + Lambda
- S3 + DynamoDB
- Deployed via SAM

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `ENV` | Environment (dev/prod) | `dev` |
| `STORAGE_MODE` | Storage type (local/aws) | `aws` |
| `AWS_PROFILE` | AWS credentials profile | `design-lee` |
| `GEMINI_API_KEY` | Google Gemini API key | `your-key` |

## Commands Reference

```bash
# Run complete test suite
./test_local.sh

# Validation only
./scripts/validate_types.sh

# Unit tests only
pytest tests/unit -m unit -v

# Start server with dev storage
ENV=dev STORAGE_MODE=aws uvicorn src.api.main:app --reload

# Deploy to production
git push origin main
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /docs` | Swagger UI |
| `POST /process-drawing` | Upload PDF for processing |
| `GET /status/{job_id}` | Check processing status |
| `GET /download/{job_id}/excel` | Download Excel schedule |

## Monitoring

- **Local Logs**: Terminal output when running server
- **AWS CloudWatch**: Production logs in AWS console
- **S3 Browser**: View files in dev/prod buckets

## Support

For issues or questions:
- Create an issue on GitHub
- Contact: info@7central.co.uk

## License

Proprietary - 7Central Group