# Deployment Documentation - SIMPLIFIED

**⚠️ This project now uses a simplified deployment process as of August 2024.**

## Current Process (Simple)

### How to Deploy
```bash
# Just push to main - it auto-deploys to production
git push origin main
```

That's it! The GitHub Action in `.github/workflows/deploy-production.yml` handles everything.

### Manual Deployment (if needed)
```bash
sam build --template infrastructure/template.yaml
sam deploy \
  --stack-name security-assistant-prod \
  --s3-bucket security-assistant-sam-deployments \
  --capabilities CAPABILITY_IAM \
  --region eu-west-2 \
  --parameter-overrides \
    Environment=prod \
    GeminiApiKey=$GEMINI_API_KEY
```

## Why We Simplified

See [ARCHITECTURE_CHANGE.md](../ARCHITECTURE_CHANGE.md) for the full rationale.

**Summary**: Single-user application doesn't need complex CI/CD pipelines.

## What Changed

### Before (Complex)
- 4 GitHub Actions workflows
- Dev → Staging → Production promotion
- Branch protection rules
- Approval gates
- Pre/post traffic hooks
- Gradual rollouts

### After (Simple)
- 1 workflow (deploy-production.yml)
- Push to main → Deploy to prod
- Local testing with dev AWS storage
- Manual testing via Swagger UI

## Key Documents

- **[USAGE.md](../../USAGE.md)** - How to use the application
- **[CLAUDE.md](../../CLAUDE.md)** - Development workflow
- **[test_local.sh](../../test_local.sh)** - Local testing script

## Archived Documentation

The following documents describe the OLD complex deployment process and are **no longer applicable**:

- `branch-protection-setup.md` - OLD: Complex branch rules
- `environment-promotion.md` - OLD: Dev/staging/prod promotion
- `staging-deployment-validation.md` - OLD: Staging environment
- `production-deployment-validation.md` - OLD: Complex validation
- `rollback-procedures.md` - OLD: Complex rollback process
- `github-actions-secrets-setup.md` - Still relevant for secrets
- `real-deployment-checklist.md` - OLD: Complex checklist

These files are kept for historical reference but should NOT be followed.