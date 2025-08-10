# Local Development Setup

## Prerequisites

### Required Software
- Python 3.11 (exact version required)
- AWS CLI v2
- SAM CLI v1.100+
- Git
- GitHub CLI (optional but recommended)

### Installation Commands

```bash
# Install Python 3.11 (macOS with Homebrew)
brew install python@3.11

# Install AWS CLI
brew install awscli

# Install SAM CLI
brew tap aws/tap
brew install aws-sam-cli

# Install GitHub CLI
brew install gh
```

## AWS Profile Configuration

### Setting Up Profiles

Two AWS profiles are required for this project:

```bash
# Configure development profile
aws configure --profile design-lee
# Region: eu-west-2
# Output: json

# Configure deployment profile (for testing CI/CD locally)
aws configure --profile design
# Region: eu-west-2
# Output: json
```

### Verify Configuration

```bash
# Test profiles
aws sts get-caller-identity --profile design-lee
aws sts get-caller-identity --profile design
```

## Project Setup

### Clone Repository

```bash
# Once GitHub repository is created
git clone [repository-url]
cd security-design-assistant

# Or add remote to existing local directory
git remote add origin [repository-url]
```

### Python Environment

```bash
# Create virtual environment
python3.11 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Development dependencies
```

### Environment Variables

Create a `.env` file in the project root:

```bash
# Copy example environment file
cp .env.example .env

# Edit with your configuration
vim .env
```

Required environment variables:

```bash
# Storage mode for local development
STORAGE_MODE=local

# Local storage path
LOCAL_STORAGE_PATH=./local_output

# AWS Profile (for local AWS service access)
AWS_PROFILE=design-lee

# Google Gemini API Key
GEMINI_API_KEY=your_api_key_here

# Optional: Enable debug logging
DEBUG=true
```

## Development Workflow

### Running Locally

```bash
# Start FastAPI development server
uvicorn src.api.main:app --reload --port 8000

# Or use the convenience script
./scripts/local_dev.sh
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_agents/test_schedule_agent.py

# Run with verbose output
pytest -v

# Use convenience script
./scripts/run_tests.sh
```

### Code Quality

```bash
# Format code with ruff
ruff format src/ tests/

# Check linting
ruff check src/ tests/

# Type checking
mypy src/

# All checks at once
make lint
```

## SAM Local Development

### Build Application

```bash
# Build SAM application
sam build

# Build with specific profile
sam build --profile design-lee
```

### Local Testing

```bash
# Start local API Gateway
sam local start-api --profile design-lee

# Invoke specific function
sam local invoke ScheduleAgent --event events/test_event.json

# Start local Lambda environment
sam local start-lambda --profile design-lee
```

### Deploy to AWS

```bash
# Deploy to staging
sam deploy --config-env staging --profile design-lee

# Deploy to production (requires approval)
sam deploy --config-env prod --profile design-lee

# Deploy with guided mode (first time)
sam deploy --guided --profile design-lee
```

## Git Workflow

### Branch Strategy

```bash
# Main branch (production)
main

# Develop branch (staging)
develop

# Feature branches
feature/story-x-y-description

# Bugfix branches
bugfix/issue-description
```

### Typical Workflow

```bash
# Start new feature
git checkout develop
git pull origin develop
git checkout -b feature/story-3-4-aws-setup

# Make changes
git add .
git commit -m "feat: implement AWS profile configuration"

# Push to remote
git push origin feature/story-3-4-aws-setup

# Create pull request (via GitHub web or CLI)
gh pr create --base develop
```

### Commit Convention

Follow conventional commits:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Test additions or changes
- `refactor:` Code refactoring
- `chore:` Maintenance tasks

## Directory Structure

```
security-design-assistant/
├── .env                    # Local environment variables (git ignored)
├── .env.example            # Example environment template
├── venv/                   # Python virtual environment (git ignored)
├── local_output/           # Local file storage (git ignored)
│   └── 7central/
│       └── [client]/
│           └── [job_id]/
├── .aws-sam/               # SAM build artifacts (git ignored)
└── src/                    # Source code
```

## Debugging

### VS Code Configuration

Create `.vscode/launch.json`:

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: FastAPI",
            "type": "python",
            "request": "launch",
            "module": "uvicorn",
            "args": [
                "src.api.main:app",
                "--reload",
                "--port",
                "8000"
            ],
            "jinja": true,
            "env": {
                "STORAGE_MODE": "local",
                "DEBUG": "true"
            }
        }
    ]
}
```

### Common Issues

1. **Port already in use**
   ```bash
   # Find process using port 8000
   lsof -i :8000
   # Kill process
   kill -9 [PID]
   ```

2. **Module import errors**
   ```bash
   # Ensure virtual environment is activated
   which python  # Should show venv path
   # Reinstall dependencies
   pip install -r requirements.txt
   ```

3. **AWS credentials not found**
   ```bash
   # Check profile configuration
   aws configure list --profile design-lee
   # Export profile for session
   export AWS_PROFILE=design-lee
   ```

## Performance Tips

1. **Use local storage mode** during development to avoid AWS costs
2. **Enable DEBUG logging** to see detailed execution flow
3. **Use pytest fixtures** for faster test execution
4. **Cache Gemini API responses** during development with VCR.py
5. **Run specific tests** instead of full suite during development

## Security Reminders

1. **Never commit** `.env` files or AWS credentials
2. **Use separate** API keys for development and production
3. **Rotate** development credentials regularly
4. **Clear** local storage after testing sensitive data
5. **Use** git-secrets to prevent credential commits

## Useful Commands

```bash
# Check Python version
python --version

# List installed packages
pip list

# Show project structure
tree -I 'venv|__pycache__|.git'

# Watch test files for changes
pytest-watch

# Format code on save (add to VS Code settings)
"editor.formatOnSave": true
"python.formatting.provider": "black"

# Profile SAM deployment
sam deploy --debug --profile design-lee

# Tail CloudWatch logs
sam logs -n ScheduleAgent --profile design-lee --tail
```

## Next Steps

1. Complete GitHub repository setup
2. Configure GitHub Actions for CI/CD
3. Set up monitoring and alerts
4. Create initial test data
5. Deploy first version to staging