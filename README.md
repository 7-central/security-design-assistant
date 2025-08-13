# Security Design Assistant

An AI-powered system that analyzes security drawings and floor plans to automatically generate comprehensive security equipment schedules in Excel format.

## Project Overview

The Security Design Assistant streamlines the process of creating security equipment schedules from architectural drawings. By leveraging advanced AI models, it:

- Extracts text and visual information from PDF drawings
- Identifies security components (cameras, door contacts, motion sensors, etc.)
- Generates detailed Excel schedules with component counts and locations
- Ensures accuracy through multi-stage validation

## Repository Information

**Repository**: https://github.com/7-central/security-design-assistant  
**Owner**: 7-central (info@7central.co.uk)  
**Developer**: junksamiad (junksamiad@gmail.com)

## Quick Start

For detailed setup instructions, see:
- [AWS Setup Guide](docs/setup/aws-setup.md) - AWS account and profile configuration
- [Local Development Guide](docs/setup/local-development.md) - Development environment setup
- [GitHub Setup Guide](docs/setup/github-setup.md) - Repository and CI/CD configuration

## Development Setup

### Requirements

- Python 3.11 (strict version requirement)
- AWS CLI v2
- SAM CLI v1.100+
- Virtual environment (recommended)
- poppler-utils (system dependency for PDF processing)

### Installation

1. Install system dependencies:

   **Ubuntu/Debian:**
   ```bash
   sudo apt-get install poppler-utils
   ```

   **macOS:**
   ```bash
   brew install poppler
   ```

   **Windows:**
   Download and install poppler from: https://github.com/oschwartz10612/poppler-windows/releases/

2. Install AWS and SAM CLI:
```bash
# macOS
brew install awscli
brew tap aws/tap
brew install aws-sam-cli

# Other platforms: See docs/setup/local-development.md
```

3. Clone the repository:
```bash
git clone https://github.com/RICG777/security-design-assistant.git
cd security-design-assistant
```

4. Create and activate a virtual environment:
```bash
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

5. Install dependencies:
```bash
pip install -r requirements.txt
```

### Environment Configuration

The project supports three environments with automatic resource switching:

#### Local Development (File System)
```bash
cp .env.local.example .env
# Uses local file system for storage, no AWS resources needed
```

#### Development Environment (AWS Dev Resources)
```bash
cp .env.dev.example .env
# Uses dev AWS resources: security-assistant-dev-* (<$1/month)
# Requires: AWS_PROFILE=design-lee
```

#### Production Environment
```bash
# Production uses environment variables set in Lambda
# Resources: security-assistant-files (S3), security-assistant-jobs (DynamoDB)
```

Key environment variables:
- `STORAGE_MODE`: "local" or "aws"
- `ENV`: "local", "dev", or "prod" (determines which AWS resources to use)
- `GEMINI_API_KEY`: Your Google GenAI API key (get from https://aistudio.google.com/app/apikey)
- `AWS_PROFILE`: Set to "design-lee" for local AWS development

⚠️ **Note**: This project now uses Google's GenAI SDK instead of Vertex AI for better performance and simplified authentication.

### Running the Application

Start the FastAPI development server:

```bash
uvicorn src.api.main:app --reload
```

The API will be available at `http://localhost:8000`

API documentation: `http://localhost:8000/docs`

## Basic Troubleshooting

### Common Issues

1. **Python version mismatch**: Ensure you're using Python 3.11 exactly
   ```bash
   python --version  # Should output Python 3.11.x
   ```

2. **Module import errors**: Make sure you've activated the virtual environment and installed all dependencies

3. **Permission errors**: Verify the output directory has write permissions
   ```bash
   chmod 755 ./local_output  # Unix/Linux/Mac
   ```

4. **Environment variables not loading**: Ensure `.env` file is in the project root and contains all required variables

5. **Port already in use**: Change the port when starting uvicorn
   ```bash
   uvicorn src.api.main:app --reload --port 8001
   ```

## Testing

The project uses a pragmatic testing approach with fast unit tests and real E2E validation.

### Test Strategy

- **Unit Tests (90%)**: Fast, isolated tests for business logic
- **E2E Tests (10%)**: Real API validation for critical paths
- **Philosophy**: Real-world validation over complex mocking

### Test Setup

1. **Install dependencies** (already included in requirements.txt):
   ```bash
   pip install pytest pytest-asyncio pytest-mock
   ```

2. **Configure environment**:
   ```bash
   # Load environment variables
   source .env
   
   # Set AWS profile for E2E tests (optional)
   export AWS_PROFILE=design-lee
   export AWS_DEFAULT_REGION=eu-west-2
   ```

### Running Tests

#### Unit Tests Only (Fast, No Credentials Required)
```bash
pytest -m unit
```
- Runs in <10 seconds
- No external service dependencies
- 52 tests covering core business logic

#### E2E Tests (Requires Dev AWS Resources)

⚠️ **Prerequisites**: E2E tests require dev AWS resources to be deployed first:
```bash
# Deploy dev resources (one-time setup)
cd infrastructure
sam deploy --template-file dev-template.yaml --stack-name security-assistant-dev \
  --capabilities CAPABILITY_IAM --region eu-west-2 --profile design-lee \
  --s3-bucket security-assistant-sam-deployments --no-confirm-changeset
```

Run E2E tests:
```bash
# Use dev environment configuration
cp .env.dev.example .env
source .env

# Run E2E tests with dev resources
ENV=dev pytest -m e2e
```
- Uses dev AWS resources (S3, DynamoDB)
- Real Gemini API calls
- Tests full pipeline with FastAPI server
- 3 scenarios: full pipeline, error handling, consistency

#### All Tests
```bash
AWS_PROFILE=design-lee pytest
```

#### With Coverage Report
```bash
pytest -m unit --cov=src --cov-report=term-missing
```

#### Verbose E2E Tests (for debugging)
```bash
AWS_PROFILE=design-lee pytest -m e2e -v -s
```

### Test Coverage

#### Unit Tests Cover
- PDF processing logic
- Component extraction algorithms
- Excel generation formatting
- Error handling paths
- Data validation

#### E2E Tests Validate
- **Full Pipeline**: PDF → Components → Excel with real APIs
- **Error Handling**: Invalid files, corrupted PDFs
- **Consistency**: <5% variance across multiple runs

### Test Data

- **Unit test fixtures**: Defined inline in test files
- **E2E test PDFs**: Located in `tests/fixtures/pdfs/`
  - `example_b2_drawing.pdf`: Baseline security drawing
  - `103P3-E34-QCI-40098_Ver1.pdf`: Complex multi-page drawing
  - `corrupted.pdf`: Error handling test

### Troubleshooting

1. **Unit test failures**: Clear environment cache with `get_env_cache().clear_cache()`
2. **E2E connection issues**: Verify AWS credentials and Gemini API key
3. **Missing fixtures**: Check `tests/fixtures/pdfs/` directory
4. **Timeout errors**: E2E tests may take up to 2 minutes each

### Migration Notes

See `tests/MIGRATION_NOTES.md` for details on the simplified test infrastructure from Story 4.3.

## CI/CD Pipeline

The project uses GitHub Actions for continuous integration and deployment.

### Workflows

#### CI - Test and Validate (`ci.yml`)
- **Triggers**: Pull requests to main/dev, pushes to dev
- **Jobs**:
  - Lint and type check with ruff and mypy
  - Run unit tests with coverage
  - Run E2E tests against dev AWS resources
  - Validate SAM templates
- **Requirements**: GitHub secrets configured (see below)

#### Deploy to Dev (`deploy-dev.yml`)
- **Triggers**: Push to dev branch or manual dispatch
- **Actions**:
  - Deploy dev infrastructure (S3 + DynamoDB)
  - Run smoke tests
  - Cost: <$1/month for dev resources

#### Deploy to Production (`deploy-prod.yml`)
- **Triggers**: Push to main branch or manual dispatch
- **Actions**:
  - Run full test suite
  - Build and deploy Lambda functions
  - Deploy production infrastructure
  - Create deployment tags

### GitHub Secrets Configuration

Required secrets (configure at https://github.com/7-central/security-design-assistant/settings/secrets):
- `AWS_ACCESS_KEY_ID`: From 7c-IAM-Admin-User
- `AWS_SECRET_ACCESS_KEY`: From 7c-IAM-Admin-User
- `GEMINI_API_KEY`: Your Google GenAI API key

### Branch Protection

Recommended settings for main branch:
- Require pull request reviews before merging
- Require status checks to pass (CI workflow)
- Require branches to be up to date before merging
- Include administrators in restrictions

## Environment Strategy

### Three-Environment Approach

1. **Local Development**
   - File system storage (no AWS needed)
   - Fast iteration and debugging
   - Unit tests only

2. **Development Environment (AWS)**
   - Dedicated dev resources with `-dev-` naming
   - 7-day S3 lifecycle for automatic cleanup
   - E2E testing with real services
   - Cost: <$1/month

3. **Production Environment**
   - Full AWS infrastructure
   - Lambda functions with API Gateway
   - Auto-scaling and monitoring
   - Production data isolation