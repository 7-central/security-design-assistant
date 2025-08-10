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

- **Development:** Local file system mode, no AWS resources
  - Purpose: Rapid development and testing
  - Cost: $0 (uses local storage)
  
- **Staging:** Full AWS deployment with test data
  - Purpose: Integration testing, client demos
  - Resources: Separate S3 bucket, DynamoDB table
  - Naming: `security-assistant-staging-*`
  
- **Production:** Full AWS deployment
  - Purpose: Live system
  - Resources: Production S3, DynamoDB, CloudWatch
  - Naming: `security-assistant-prod-*`

## Environment Promotion Flow

```
Development (Local)
    ↓ (git push)
PR to develop branch
    ↓ (merge)
Staging Deployment
    ↓ (manual approval)
PR to main branch
    ↓ (merge)
Production Deployment
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