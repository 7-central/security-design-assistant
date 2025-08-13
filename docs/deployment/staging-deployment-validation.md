# Staging Deployment Validation Guide

## Overview

This guide provides step-by-step instructions for executing and validating the first staging deployment to the real AWS environment.

## Prerequisites

Before beginning staging deployment:

- [ ] GitHub repository configured: `7-central/security-design-assistant`
- [ ] GitHub Actions secrets configured
- [ ] Branch protection rules enabled
- [ ] AWS S3 bucket exists: `security-assistant-sam-deployments`
- [ ] AWS profiles configured: `design-lee` and `design`
- [ ] SAM CLI installed and configured

## Pre-Deployment Validation

### 1. Local Environment Check

```bash
# Verify AWS CLI access
aws sts get-caller-identity --profile design-lee

# Expected output:
{
    "UserId": "AIDAXXXXXXXXXXXXXXXXX",
    "Account": "445567098699",
    "Arn": "arn:aws:iam::445567098699:user/lee-hayton"
}

# Verify SAM CLI
sam --version
# Expected: SAM CLI, version 1.100.0 or higher

# Verify deployment bucket access
aws s3 ls s3://security-assistant-sam-deployments --profile design-lee
```

### 2. Template and Code Validation

```bash
# Navigate to project root
cd /path/to/security-design-assistant

# Validate SAM template
sam validate --template-file infrastructure/template.yaml

# Run CFN Lint
cfn-lint infrastructure/template.yaml

# Run code quality checks
python -m ruff check src/ tests/
python -m mypy src/

# Run unit tests
python -m pytest tests/unit/ -v

# Security scan
bandit -r src/ -f json -o bandit-report.json
```

### 3. Test Local Build

```bash
# Build the application
sam build --template-file infrastructure/template.yaml

# Check build artifacts
ls -la .aws-sam/build/
```

## Staging Deployment Execution

### 1. Trigger Deployment via GitHub Actions

#### Method A: Push to develop branch

```bash
# Create feature branch
git checkout develop
git pull origin develop
git checkout -b test-staging-deployment

# Make a small test change
echo "# Test deployment $(date)" >> docs/deployment/deployment-test.md
git add .
git commit -m "test: trigger staging deployment validation"

# Push and create PR
git push origin test-staging-deployment

# Create PR to develop branch via GitHub UI or CLI
gh pr create \
  --title "Test: Validate Staging Deployment" \
  --body "Testing the staging deployment pipeline with real AWS account" \
  --head test-staging-deployment \
  --base develop
```

#### Method B: Manual workflow dispatch

```bash
# Trigger via GitHub CLI
gh workflow run deploy-staging.yml \
  --ref develop \
  --field force_deploy=false
```

### 2. Monitor GitHub Actions

Navigate to: `https://github.com/7-central/security-design-assistant/actions`

**Watch for**:
- [ ] **Pre-deployment Validation**: All checks pass
- [ ] **AWS Credentials**: Successfully configured
- [ ] **SAM Build**: Completes without errors
- [ ] **SAM Deploy**: Creates CloudFormation stack
- [ ] **Health Checks**: All post-deployment checks pass

### 3. Expected GitHub Actions Output

#### Successful Deployment Log Markers:
```
✅ All validation checks passed
✅ SAM build completed successfully
✅ CloudFormation stack deployment initiated
✅ Stack deployment completed: security-assistant-staging
✅ API Gateway health check passed
✅ CloudWatch metrics accessible  
✅ DynamoDB table accessible
✅ S3 bucket accessible
✅ SQS queue accessible
🎉 All health checks passed!
✅ Smoke tests passed
🚀 Staging deployment successful!
```

## Staging Environment Verification

### 1. AWS Console Verification

#### CloudFormation Stack
Navigate to: `https://eu-west-2.console.aws.amazon.com/cloudformation/`

- [ ] **Stack Name**: `security-assistant-staging`
- [ ] **Status**: `CREATE_COMPLETE` or `UPDATE_COMPLETE`  
- [ ] **Resources**: All resources created successfully
- [ ] **Outputs**: API endpoint URL available

#### API Gateway
Navigate to: `https://eu-west-2.console.aws.amazon.com/apigateway/`

- [ ] **API Created**: `security-assistant-api-staging`
- [ ] **Stage**: `Prod` stage deployed
- [ ] **Health Endpoint**: `/health` returns 200

#### Lambda Functions  
Navigate to: `https://eu-west-2.console.aws.amazon.com/lambda/`

- [ ] **API Function**: `security-assistant-api-staging`
- [ ] **Worker Function**: `security-assistant-worker-staging`
- [ ] **Pre-traffic Hook**: `security-assistant-pre-traffic-staging`
- [ ] **Post-traffic Hook**: `security-assistant-post-traffic-staging`

#### DynamoDB
Navigate to: `https://eu-west-2.console.aws.amazon.com/dynamodb/`

- [ ] **Table Name**: `security-assistant-jobs-staging`
- [ ] **Status**: `ACTIVE`
- [ ] **GSI**: Status and client indexes created

#### S3 Buckets
Navigate to: `https://s3.console.aws.amazon.com/s3/`

- [ ] **Files Bucket**: `security-assistant-files-staging`
- [ ] **Deployment Bucket**: `security-assistant-sam-deployments` (shared)

#### SQS Queues
Navigate to: `https://eu-west-2.console.aws.amazon.com/sqs/`

- [ ] **Processing Queue**: `security-assistant-processing-staging`
- [ ] **Dead Letter Queue**: `security-assistant-dlq-staging`

### 2. API Testing

```bash
# Get API endpoint from CloudFormation output
API_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name security-assistant-staging \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
  --output text \
  --profile design-lee)

echo "API Endpoint: $API_ENDPOINT"

# Test health endpoint
curl -v "$API_ENDPOINT/health"
# Expected: HTTP 200 with health status

# Test CORS
curl -H "Origin: https://example.com" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: Content-Type" \
     -X OPTIONS \
     "$API_ENDPOINT/jobs"
# Expected: CORS headers in response
```

### 3. Functional Testing

```bash
# Set environment variables for integration tests
export API_BASE_URL="$API_ENDPOINT"
export ENVIRONMENT="staging"
export STORAGE_MODE="aws"

# Run integration tests against staging
python -m pytest tests/integration/ -v \
  --tb=short \
  -k "not local" \
  --timeout=300
```

### 4. CloudWatch Monitoring Validation

#### Logs
Navigate to: `https://eu-west-2.console.aws.amazon.com/cloudwatch/home?region=eu-west-2#logsV2:`

- [ ] **API Logs**: `/aws/lambda/security-assistant-api-staging`
- [ ] **Worker Logs**: `/aws/lambda/security-assistant-worker-staging`
- [ ] **Log Retention**: 30 days configured
- [ ] **Structured Logging**: JSON format logs visible

#### Metrics
Navigate to: `https://eu-west-2.console.aws.amazon.com/cloudwatch/home?region=eu-west-2#metricsV2:`

- [ ] **Lambda Metrics**: Invocations, Duration, Errors
- [ ] **API Gateway Metrics**: Count, Latency, 4XXError, 5XXError
- [ ] **DynamoDB Metrics**: Read/Write capacity, throttles
- [ ] **SQS Metrics**: Messages sent, received, visible

#### Dashboards
Navigate to: `https://eu-west-2.console.aws.amazon.com/cloudwatch/home?region=eu-west-2#dashboards:`

- [ ] **Application Dashboard**: Shows key metrics
- [ ] **Health Dashboard**: Service health indicators

#### X-Ray Tracing
Navigate to: `https://eu-west-2.console.aws.amazon.com/xray/`

- [ ] **Service Map**: Shows service dependencies
- [ ] **Traces**: Request traces visible
- [ ] **Performance**: Trace analysis available

### 5. Performance Testing

```bash
# Simple load test with curl
for i in {1..10}; do
  curl -w "Response time: %{time_total}s\n" \
       -o /dev/null \
       -s "$API_ENDPOINT/health"
done

# Expected: < 2 seconds average response time

# Check CloudWatch metrics after load
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=security-assistant-api-staging \
  --start-time $(date -u -d '10 minutes ago' '+%Y-%m-%dT%H:%M:%S') \
  --end-time $(date -u '+%Y-%m-%dT%H:%M:%S') \
  --period 300 \
  --statistics Average,Maximum \
  --profile design-lee
```

## Validation Checklist

### ✅ Infrastructure Deployment
- [ ] CloudFormation stack created successfully
- [ ] All AWS resources provisioned
- [ ] Resource naming follows conventions
- [ ] Tags applied correctly

### ✅ Application Functionality
- [ ] API Gateway responds to health checks
- [ ] Lambda functions execute without errors
- [ ] DynamoDB read/write operations work
- [ ] S3 file upload/download works
- [ ] SQS message processing works

### ✅ Security Configuration
- [ ] IAM roles have least privilege
- [ ] API Gateway has CORS configured
- [ ] S3 buckets not publicly accessible
- [ ] DynamoDB table has encryption
- [ ] Lambda functions in VPC (if required)

### ✅ Monitoring and Alerting
- [ ] CloudWatch logs aggregating
- [ ] Custom metrics reporting
- [ ] X-Ray traces captured
- [ ] Dashboards displaying data
- [ ] Alarms configured and functional

### ✅ Performance and Reliability
- [ ] API response times < 2 seconds
- [ ] Lambda cold start times acceptable
- [ ] Error rates < 1%
- [ ] Auto-scaling configured
- [ ] Health checks passing

## Troubleshooting

### Common Issues

#### 1. Deployment Failure
```bash
# Check CloudFormation events
aws cloudformation describe-stack-events \
  --stack-name security-assistant-staging \
  --profile design-lee

# Check Lambda logs for errors
aws logs describe-log-groups \
  --log-group-name-prefix /aws/lambda/security-assistant \
  --profile design-lee
```

#### 2. API Gateway Issues
```bash
# Test API Gateway directly
aws apigateway test-invoke-method \
  --rest-api-id YOUR_API_ID \
  --resource-id YOUR_RESOURCE_ID \
  --http-method GET \
  --path-with-query-string /health \
  --profile design-lee
```

#### 3. Permission Issues
```bash
# Check IAM role trust policies
aws iam get-role \
  --role-name security-assistant-lambda-role-staging \
  --profile design-lee

# Check role policies
aws iam list-attached-role-policies \
  --role-name security-assistant-lambda-role-staging \
  --profile design-lee
```

### Recovery Procedures

#### Rollback Deployment
```bash
# Delete the stack to rollback
aws cloudformation delete-stack \
  --stack-name security-assistant-staging \
  --profile design-lee

# Wait for deletion to complete
aws cloudformation wait stack-delete-complete \
  --stack-name security-assistant-staging \
  --profile design-lee
```

#### Emergency Fixes
```bash
# Quick configuration updates via AWS CLI
aws lambda update-function-configuration \
  --function-name security-assistant-api-staging \
  --timeout 30 \
  --profile design-lee
```

## Success Criteria

**✅ Staging Deployment Successful When:**

1. **GitHub Actions**: All workflows complete successfully
2. **Infrastructure**: All AWS resources created and healthy  
3. **Functionality**: API endpoints respond correctly
4. **Monitoring**: All logs and metrics flowing
5. **Performance**: Meets SLA requirements
6. **Security**: No security alerts or issues
7. **Documentation**: Deployment lessons documented

## Next Steps

After successful staging validation:

1. **Document Issues**: Record any problems and solutions
2. **Update Procedures**: Improve deployment documentation
3. **Performance Baseline**: Establish normal operating metrics
4. **Production Readiness**: Prepare for production deployment

## Sign-off

- [ ] **Technical Validation**: All systems functional
- [ ] **Performance Validation**: Meets requirements  
- [ ] **Security Validation**: Security review passed
- [ ] **Documentation**: Complete and accurate
- [ ] **Ready for Production**: Approved for prod deployment