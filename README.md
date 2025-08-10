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

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

Required environment variables:

- `STORAGE_MODE`: Set to "local" for local development
- `LOCAL_OUTPUT_DIR`: Directory for output files (default: "./local_output")
- `GEMINI_API_KEY`: Your Google GenAI API key (get from https://aistudio.google.com/app/apikey)
- `AWS_PROFILE`: Set to "design-lee" for local AWS access (optional)

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

### End-to-End Integration Tests

The project includes comprehensive end-to-end tests that verify the complete pipeline from drawing submission to Excel generation.

#### Test Setup

1. **Install test dependencies**:
   ```bash
   pip install pytest pytest-html httpx openpyxl
   ```

2. **Ensure the API is running** (for local testing):
   ```bash
   uvicorn src.api.main:app --reload
   ```

#### Running E2E Tests

**Quick test run**:
```bash
./scripts/run_e2e_tests.sh
```

**With HTML report**:
```bash
./scripts/run_e2e_tests.sh --report
```

**Against different environments**:
```bash
./scripts/run_e2e_tests.sh --env staging
./scripts/run_e2e_tests.sh --url http://custom-api.com
```

**Verbose output**:
```bash
./scripts/run_e2e_tests.sh --verbose
```

#### Test Coverage

The E2E test suite covers:
- Complete pipeline execution with valid drawings
- API response time validation (<2 seconds)
- File generation and Excel content validation
- Accuracy measurement against baseline data
- Performance monitoring (<10 minutes processing)
- Error handling scenarios (400, 404, 413, 422, 423)
- Security tests (path traversal, SQL injection, input sanitization)

#### Troubleshooting Test Failures

1. **API not responding**: Ensure the API is running on the expected port
2. **Missing fixtures**: Verify test fixtures exist in `tests/fixtures/pdfs/`
3. **Timeout errors**: Check if processing is taking longer than expected
4. **Permission errors**: Ensure write access to `./output` directory

#### Updating Test Baselines

When the expected output changes:
1. Manually verify the new output is correct
2. Update `tests/fixtures/expected/baseline_schedule.json`
3. Document the change in test documentation