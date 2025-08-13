# Security Design Assistant - Deployment Guide

This guide covers the deployment process, requirements, and procedures for the Security Design Assistant serverless application.

## Overview

The Security Design Assistant uses a serverless architecture deployed on AWS with Infrastructure as Code (SAM) and automated CI/CD pipelines (GitHub Actions).

## Architecture

- **Infrastructure**: AWS SAM (Serverless Application Model)
- **Compute**: AWS Lambda (Python 3.11)
- **API**: AWS API Gateway
- **Storage**: AWS DynamoDB + S3
- **Messaging**: AWS SQS + SNS
- **Monitoring**: CloudWatch + X-Ray
- **CI/CD**: GitHub Actions
- **Deployment Strategy**: Blue/Green with gradual traffic shifting

## Environments

### Development (dev)
- **Purpose**: Local development and testing
- **Resources**: Minimal (512MB RAM, 5min timeout)
- **Traffic Shifting**: Fast (50% every 2 minutes)
- **Monitoring**: Basic
- **Cost**: Optimized for development

### Staging (staging) 
- **Purpose**: Pre-production testing and validation
- **Resources**: Production-like (1GB RAM, 10min timeout)
- **Traffic Shifting**: Moderate (10% every 5 minutes)
- **Monitoring**: Enhanced
- **Data**: Production-like test data

### Production (prod)
- **Purpose**: Live customer workloads
- **Resources**: High performance (2GB RAM, 15min timeout)
- **Traffic Shifting**: Conservative (5% every 10 minutes)
- **Monitoring**: Comprehensive
- **Security**: Enhanced (encryption, VPC, compliance)

## Prerequisites

### Required Tools

- **AWS CLI** (v2.0+)
- **SAM CLI** (v1.100+)
- **Python** (3.11)
- **Git**
- **GitHub CLI** (optional, for branch protection setup)

### Required Accounts & Permissions

- **AWS Account** with administrative access
- **GitHub Repository** with Actions enabled
- **Gemini API Key** for AI processing

## Environment Configuration

### Required Environment Variables

- `STORAGE_MODE`: Set to "local" for development or "aws" for production
- `LOCAL_OUTPUT_DIR`: Directory for local file storage (default: ./local_output)
- `GEMINI_API_KEY`: Your Google GenAI API key (obtain from https://aistudio.google.com/app/apikey)

### Deprecated Environment Variables (DO NOT USE)

The following variables were used with the old Vertex AI SDK and should be removed:
- ~~`GOOGLE_APPLICATION_CREDENTIALS`~~
- ~~`VERTEX_AI_PROJECT_ID`~~
- ~~`VERTEX_AI_LOCATION`~~

## Deployment Process

### Automated Deployment (Recommended)

The automated deployment process uses GitHub Actions:

#### 1. Development Workflow
```
Feature Branch → PR to develop → Auto-deploy to staging
```

1. Create feature branch from `develop`
2. Make changes and commit
3. Create Pull Request to `develop`
4. Automated validation runs (linting, tests, SAM validation)
5. After approval and merge, automatic deployment to staging

#### 2. Production Workflow
```  
develop → PR to main → Manual approval → Auto-deploy to production
```

1. Create Pull Request from `develop` to `main`
2. Pre-production validation runs
3. Requires 2 approvals
4. Manual approval gate for production
5. After merge, automatic deployment to production with gradual rollout

### Manual Deployment

For emergency deployments or local testing:

#### 1. Development Environment
```bash
# Build the application
sam build

# Deploy to dev
sam deploy --config-env dev
```

#### 2. Staging Environment
```bash
# Build the application  
sam build

# Deploy to staging
sam deploy --config-env staging --guided
```

#### 3. Production Environment
```bash
# Build the application
sam build

# Deploy to production (requires confirmation)
sam deploy --config-env prod --guided
```

## Validation & Testing

### Pre-deployment Validation

Every deployment includes:

- **Code Quality**: Linting (ruff), type checking (mypy)
- **Security Scan**: Static analysis (bandit)
- **Infrastructure**: SAM template validation, CFN lint
- **Tests**: Unit tests (80% coverage), integration tests

### Deployment Validation

#### Pre-traffic Hook Validation
- Lambda function health check
- Database connectivity test
- S3 bucket access verification
- SQS queue availability check
- Environment variable validation

#### Post-traffic Hook Validation  
- Error rate monitoring (< 5% threshold)
- Response time validation
- Queue health monitoring
- Smoke test execution

## Monitoring & Alerting

### CloudWatch Dashboards

1. **Main Dashboard**: Overall system health
2. **Health Dashboard**: Error rates, availability

### Alerts

- **Error Rate**: > 10% (staging), > 5% (production)
- **DLQ Depth**: Any messages in dead letter queue
- **Lambda Duration**: Exceeds timeout thresholds
- **API Latency**: > 5 seconds for API calls
- **Cost**: Monthly projection exceeds budget

### Notifications

- **SNS Topics**: Infrastructure alerts
- **Slack Integration**: Deployment notifications
- **Email Alerts**: Critical system events

## Troubleshooting

### Common Issues

1. **Deployment Failures**
   - Check SAM template syntax
   - Verify AWS permissions
   - Check resource limits/quotas

2. **Lambda Errors**
   - Review CloudWatch Logs
   - Check environment variables
   - Verify layer compatibility

3. **Performance Issues**
   - Monitor CloudWatch metrics
   - Check Lambda memory allocation
   - Review concurrent execution limits

For specific procedures, see:
- [Rollback Procedures](./rollback-procedures.md)
- [Environment Promotion](./environment-promotion.md)