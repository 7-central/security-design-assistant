# Claude Developer Guidelines

## Simplified Workflow

This project uses a streamlined development workflow:
- **Local development** with dev AWS storage for testing
- **Direct deployment** to production on main branch push
- **No CI/CD pipeline** - quality checks run locally

## Development Workflow

### 1. Complete Local Test Suite
```bash
# Run everything: validation, unit tests, then start server
./test_local.sh
```

This script:
1. Runs type checking and linting (`./scripts/validate_types.sh`)
2. Runs unit tests
3. Starts API server with dev AWS storage for manual testing

### 2. Manual Testing with Dev Storage
The local test script configures:
- `ENV=dev`
- `STORAGE_MODE=aws` 
- `AWS_PROFILE=design-lee`
- Uses dev S3 bucket and DynamoDB table

Test endpoints:
```bash
# Health check
curl http://localhost:8000/health

# Process a drawing
curl -X POST http://localhost:8000/process-drawing \
  -F 'drawing_file=@test.pdf' \
  -F 'client_name=test' \
  -F 'project_name=test'
```

### 3. Deploy to Production
```bash
# Commit and push to main (triggers auto-deploy)
git add .
git commit -m "Your changes"
git push origin main
```

## Quick Commands

### Validation Only
```bash
# Fast type checking and linting
./scripts/validate_types.sh
```

### Unit Tests Only
```bash
pytest tests/unit -m unit -v
```

### Fix Commands
```bash
# Auto-fix safe lint issues
ruff check --fix src tests

# Format code
ruff format src tests
```

## Important Notes
- **No dev/staging branches** - work on feature branches, merge to main
- **No E2E test suite** - replaced with manual testing
- **Dev AWS resources** - only S3 and DynamoDB for safe testing
- **Pre-push hook** - validates code before allowing push
- **Simple deployment** - push to main deploys to production