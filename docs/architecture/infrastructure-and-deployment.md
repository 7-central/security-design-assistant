# Infrastructure and Deployment

## Infrastructure as Code

- **Tool:** AWS SAM 1.100+
- **Location:** `infrastructure/template.yaml`
- **Approach:** Serverless-first, pay-per-use resources only

## Deployment Strategy

- **Strategy:** Blue/Green deployment with automatic rollback
- **CI/CD Platform:** GitHub Actions
- **Pipeline Configuration:** `.github/workflows/deploy.yml`

## Environments

- **Local Development:** Local file system mode with minimal dev AWS resources
  - Purpose: Rapid development and E2E testing
  - Local Storage: File system for unit tests
  - Dev AWS Resources (Story 4.3.1):
    - S3: `security-assistant-dev-445567098699` (7-day lifecycle)
    - DynamoDB: `security-assistant-dev-jobs` (on-demand billing)
  - Cost: <$1/month for dev AWS resources
  - Environment: Set `ENV=dev` and `STORAGE_MODE=aws` for E2E tests
  
- **Staging:** Full AWS deployment with test data (Account: 445567098699, Region: eu-west-2)
  - Purpose: Integration testing, client demos
  - Resources: Separate S3 bucket, DynamoDB table, Lambda, SQS
  - SAM Artifacts: security-assistant-sam-deployments bucket
  - Naming: `security-assistant-staging-*`
  - Cost: ~$5/month (full infrastructure)
  
- **Production:** Full AWS deployment (Account: 445567098699, Region: eu-west-2)
  - Purpose: Live system
  - Resources: Production S3, DynamoDB, CloudWatch, Lambda, SQS
  - SAM Artifacts: security-assistant-sam-deployments bucket
  - Naming: `security-assistant-prod-*` or `security-assistant-*`

## Environment Promotion Flow

```
Local Development + Dev AWS Resources
    ↓ (pytest -m e2e with dev resources)
    ↓ (git push to feature branch)
PR to develop branch
    ↓ (GitHub Actions runs tests)
    ↓ (merge on approval)
Staging Deployment (AWS 445567098699, eu-west-2)
    ↓ (integration testing)
    ↓ (manual approval)
PR to main branch
    ↓ (merge with approval)
Production Deployment (AWS 445567098699, eu-west-2)
```

## Rollback Strategy

- **Primary Method:** SAM automatic rollback on CloudWatch alarms
- **Trigger Conditions:** 
  - Lambda error rate > 10%
  - API Gateway 5xx errors > 5%
  - DLQ messages present
- **Recovery Time Objective:** < 5 minutes (automatic rollback)

## SAM Template Structure

```yaml