# Production Deployment Validation Guide

## Overview

This guide provides step-by-step instructions for executing the first production deployment with manual approval gates and comprehensive validation.

## Prerequisites

Before beginning production deployment:

- [ ] **Staging Environment**: Successfully deployed and stable for 24+ hours
- [ ] **Branch Protection**: `main` branch protection rules active
- [ ] **Environment Protection**: Production approval environment configured
- [ ] **Performance Testing**: Staging load testing completed
- [ ] **Security Review**: No high/medium security issues
- [ ] **Documentation**: All deployment guides current

## Pre-Production Validation

### 1. Staging Health Verification

```bash
# Get staging API endpoint
STAGING_API=$(aws cloudformation describe-stacks \
  --stack-name security-assistant-staging \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
  --output text \
  --profile design-lee)

# Verify staging health
curl -f "$STAGING_API/health"
# Expected: HTTP 200 response

# Check staging error rates (last 24 hours)
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=security-assistant-worker-staging \
  --start-time $(date -u -d '24 hours ago' '+%Y-%m-%dT%H:%M:%S') \
  --end-time $(date -u '+%Y-%m-%dT%H:%M:%S') \
  --period 86400 \
  --statistics Sum \
  --profile design-lee

# Expected: < 5 errors in 24 hours
```

### 2. Code Quality Validation

```bash
# Navigate to project root
cd /path/to/security-design-assistant

# Ensure on latest develop
git checkout develop
git pull origin develop

# Final security scan
bandit -r src/ -f json -o production-bandit-report.json

# Check for high severity issues
HIGH_ISSUES=$(cat production-bandit-report.json | \
  python -c "import sys,json; data=json.load(sys.stdin); \
  print(len([r for r in data.get('results',[]) if r.get('issue_severity') == 'HIGH']))")

echo "High security issues: $HIGH_ISSUES"
# Expected: 0 high issues

# Final test run
python -m pytest tests/ -v --tb=short
# Expected: All tests pass
```

### 3. Infrastructure Validation

```bash
# Validate SAM template
sam validate --template-file infrastructure/template.yaml

# CFN Lint with strict checks
cfn-lint infrastructure/template.yaml --ignore-checks W

# Test build
sam build --template-file infrastructure/template.yaml
```

## Production Deployment Process

### 1. Create Production Release PR

```bash
# Ensure develop is up to date
git checkout develop
git pull origin develop

# Create release PR to main
gh pr create \
  --title "Production Release: $(date '+%Y-%m-%d')" \
  --body "$(cat <<'EOF'
# Production Release

## Changes
- Real deployment integration completed
- AWS account integration: 445567098699
- Region: eu-west-2
- All placeholders replaced with actual values

## Staging Validation
- [x] Staging deployed successfully  
- [x] All health checks passing
- [x] Error rate < 1% for 24+ hours
- [x] Performance meets SLA requirements

## Pre-Production Checklist
- [x] Security scan: No high/medium issues
- [x] All tests passing
- [x] Infrastructure validated
- [x] Documentation complete

## Deployment Plan
1. Pre-production validation (automated)
2. Manual approval required  
3. Gradual production deployment with monitoring
4. 10-minute health monitoring period
5. Automatic rollback on failure

**Ready for production deployment with approval**
EOF
)" \
  --head develop \
  --base main
```

### 2. Manual Approval Process

#### GitHub Environment Protection
Navigate to: `https://github.com/7-central/security-design-assistant/actions`

**Approval Requirements**:
1. **PR Approval**: At least 1 approval on the PR to `main`
2. **Status Checks**: All required checks must pass:
   - `Validate Changes`
   - `Deploy to Staging Environment` (from staging deployment)
   - `Pre-production Validation` (runs before approval)

#### Production Approval Workflow
1. **Merge PR to main**: Triggers production deployment workflow
2. **Pre-production Validation**: Automated checks run first
3. **Manual Approval Required**: Deployment pauses for human approval
4. **Approval Decision**: Repository owner (`7-central`) must approve
5. **Production Deployment**: Continues after approval

### 3. Monitor Pre-Production Validation

Watch GitHub Actions for the `Pre-production Validation` job:

```
✅ Staging environment health verified
✅ Error rates acceptable  
✅ Code quality checks passed
✅ Security scan passed
✅ Infrastructure validation passed
✅ Test suite passed
🔒 Manual approval required for production deployment
```

### 4. Manual Approval Execution

When prompted in GitHub Actions:

1. **Review Validation Results**: Ensure all checks passed
2. **Verify Staging Health**: Confirm staging is stable  
3. **Business Approval**: Confirm ready for production traffic
4. **Approve Deployment**: Click "Review pending deployments" → "Approve and deploy"

## Production Deployment Monitoring

### 1. Deployment Progress Tracking

Monitor the GitHub Actions deployment job for:

```
🚀 Starting production deployment with gradual rollout...
✅ CloudFormation stack deployment initiated
✅ Termination protection enabled
✅ Lambda layer optimized for production
✅ Gradual deployment with 5% traffic shifting
✅ Stack deployment completed: security-assistant-prod
🔍 Monitoring deployment health for 10 minutes...
```

### 2. Real-time Health Monitoring

The deployment includes automated health monitoring:

- **API Health Checks**: Every 30 seconds for 10 minutes (20 checks)
- **Lambda Error Rate**: < 2 errors per 5-minute window
- **DLQ Depth**: Must remain at 0 messages
- **Response Time**: Average < 2 seconds

### 3. Manual Monitoring (Parallel)

```bash
# Get production API endpoint (once deployment completes)
PROD_API=$(aws cloudformation describe-stacks \
  --stack-name security-assistant-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
  --output text \
  --profile design-lee)

echo "Production API: $PROD_API"

# Monitor health in parallel
while true; do
  HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$PROD_API/health" 2>/dev/null || echo "000")
  TIMESTAMP=$(date '+%H:%M:%S')
  if [ "$HTTP_STATUS" = "200" ]; then
    echo "[$TIMESTAMP] ✅ Health check OK ($HTTP_STATUS)"
  else
    echo "[$TIMESTAMP] ❌ Health check FAIL ($HTTP_STATUS)"
  fi
  sleep 10
done
```

## Production Environment Verification

### 1. AWS Console Verification

#### CloudFormation Stack
Navigate to: `https://eu-west-2.console.aws.amazon.com/cloudformation/`

- [ ] **Stack Name**: `security-assistant-prod`
- [ ] **Status**: `CREATE_COMPLETE` or `UPDATE_COMPLETE`
- [ ] **Termination Protection**: `Enabled`
- [ ] **All Resources**: Created successfully without errors

#### Production Resources Checklist

**Lambda Functions** (`https://eu-west-2.console.aws.amazon.com/lambda/`):
- [ ] `security-assistant-api-prod`: Runtime Python 3.11, Memory 2048MB
- [ ] `security-assistant-worker-prod`: Configured with production settings
- [ ] `security-assistant-pre-traffic-prod`: Pre-deployment validation
- [ ] `security-assistant-post-traffic-prod`: Post-deployment validation

**API Gateway** (`https://eu-west-2.console.aws.amazon.com/apigateway/`):
- [ ] `security-assistant-api-prod`: Production API created
- [ ] **Stages**: Prod stage with gradual deployment enabled
- [ ] **Throttling**: Production limits configured

**DynamoDB** (`https://eu-west-2.console.aws.amazon.com/dynamodb/`):
- [ ] `security-assistant-jobs-prod`: Production table
- [ ] **Capacity**: On-demand scaling configured
- [ ] **Encryption**: Enabled with AWS managed keys

**S3 Buckets** (`https://s3.console.aws.amazon.com/s3/`):
- [ ] `security-assistant-files-prod`: Production file storage
- [ ] **Versioning**: Enabled with lifecycle policies
- [ ] **Security**: Public access blocked

**SQS Queues** (`https://eu-west-2.console.aws.amazon.com/sqs/`):
- [ ] `security-assistant-processing-prod`: Main processing queue
- [ ] `security-assistant-dlq-prod`: Dead letter queue with alarms

### 2. Security Validation

```bash
# Verify IAM role permissions
aws iam get-role \
  --role-name security-assistant-lambda-role-prod \
  --profile design-lee

# Check S3 bucket policies
aws s3api get-bucket-policy \
  --bucket security-assistant-files-prod \
  --profile design-lee

# Verify encryption settings
aws dynamodb describe-table \
  --table-name security-assistant-jobs-prod \
  --query 'Table.SSEDescription' \
  --profile design-lee
```

### 3. Performance Testing

```bash
# Production performance baseline
echo "Testing production performance..."
TOTAL=0
COUNT=10

for i in $(seq 1 $COUNT); do
  RESPONSE_TIME=$(curl -w "%{time_total}" \
                      -o /dev/null \
                      -s "$PROD_API/health")
  TOTAL=$(echo "$TOTAL + $RESPONSE_TIME" | bc)
  echo "Request $i: ${RESPONSE_TIME}s"
done

AVERAGE=$(echo "scale=3; $TOTAL / $COUNT" | bc)
echo "Average response time: ${AVERAGE}s"
# Expected: < 2 seconds average

# Load test with concurrency
echo "Testing with concurrent requests..."
for i in {1..5}; do
  curl -w "Request $i: %{time_total}s\n" \
       -o /dev/null \
       -s "$PROD_API/health" &
done
wait
```

### 4. Functional Testing

```bash
# Set production environment for tests
export API_BASE_URL="$PROD_API"
export ENVIRONMENT="prod"
export STORAGE_MODE="aws"

# Run critical production smoke tests
python -m pytest tests/integration/test_e2e.py::test_health_check -v
python -m pytest tests/integration/test_e2e.py::test_api_cors -v

# Test specific production endpoints
curl -X OPTIONS \
     -H "Origin: https://7central.co.uk" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: Content-Type" \
     "$PROD_API/jobs"
```

### 5. Monitoring Dashboard Verification

Navigate to CloudWatch dashboards:
`https://eu-west-2.console.aws.amazon.com/cloudwatch/home?region=eu-west-2#dashboards:`

**Production Dashboard Checks**:
- [ ] **API Metrics**: Request count, latency, error rates
- [ ] **Lambda Metrics**: Invocations, duration, errors, throttles
- [ ] **DynamoDB Metrics**: Read/write capacity, throttling
- [ ] **SQS Metrics**: Message flow, DLQ depth
- [ ] **Custom Metrics**: Business logic metrics visible

**X-Ray Tracing** (`https://eu-west-2.console.aws.amazon.com/xray/`):
- [ ] **Service Map**: Production service dependencies visible
- [ ] **Traces**: End-to-end request tracing working
- [ ] **Performance Insights**: Bottleneck analysis available

## Post-Deployment Validation

### 1. Smoke Test Suite

```bash
# Run comprehensive production smoke tests
python -m pytest tests/integration/ \
  -v \
  --tb=short \
  -m "smoke" \
  --timeout=60 \
  --maxfail=1

# Expected: All smoke tests pass
```

### 2. Business Continuity Test

```bash
# Test critical business workflows
echo "Testing critical business workflows..."

# Health check
curl -f "$PROD_API/health" || echo "❌ Health check failed"

# CORS preflight
curl -f -X OPTIONS \
     -H "Origin: https://app.7central.co.uk" \
     "$PROD_API/jobs" || echo "❌ CORS failed"

echo "✅ Business continuity tests completed"
```

### 3. Performance SLA Verification

```bash
# Check CloudWatch metrics for SLA compliance
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Latency \
  --dimensions Name=ApiName,Value=security-assistant-api-prod \
  --start-time $(date -u -d '30 minutes ago' '+%Y-%m-%dT%H:%M:%S') \
  --end-time $(date -u '+%Y-%m-%dT%H:%M:%S') \
  --period 1800 \
  --statistics Average,Maximum \
  --profile design-lee

# Expected: Average < 2000ms, Maximum < 5000ms
```

## Rollback Procedures

### 1. Automatic Rollback Triggers

The deployment will automatically rollback if:
- Health check failures (HTTP non-200 responses)
- Lambda error rate > 2 errors per 5 minutes
- DLQ messages detected
- CloudWatch alarms triggered

### 2. Manual Rollback

If manual intervention is needed:

```bash
# Emergency rollback via CloudFormation
aws cloudformation cancel-update-stack \
  --stack-name security-assistant-prod \
  --profile design-lee

# Wait for rollback completion
aws cloudformation wait stack-rollback-complete \
  --stack-name security-assistant-prod \
  --profile design-lee

# Verify rollback success
aws cloudformation describe-stacks \
  --stack-name security-assistant-prod \
  --query 'Stacks[0].StackStatus' \
  --profile design-lee
```

### 3. Post-Rollback Actions

```bash
# Verify old version is working
curl -f "$PROD_API/health"

# Check error rates post-rollback
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=security-assistant-api-prod \
  --start-time $(date -u -d '15 minutes ago' '+%Y-%m-%dT%H:%M:%S') \
  --end-time $(date -u '+%Y-%m-%dT%H:%M:%S') \
  --period 900 \
  --statistics Sum \
  --profile design-lee

# Document rollback reason
echo "Rollback completed at $(date)" >> docs/deployment/rollback-log.md
```

## Success Criteria

**✅ Production Deployment Successful When:**

### Technical Criteria
- [ ] **GitHub Actions**: Production deployment workflow completed successfully
- [ ] **CloudFormation**: Stack status `CREATE_COMPLETE` or `UPDATE_COMPLETE`
- [ ] **Health Monitoring**: All 20 health checks passed during 10-minute monitoring
- [ ] **API Functionality**: All endpoints responding correctly
- [ ] **Performance**: Average response time < 2 seconds
- [ ] **Error Rates**: < 1% error rate in first hour
- [ ] **Monitoring**: All dashboards showing healthy metrics

### Business Criteria
- [ ] **Manual Approval**: Repository owner approved deployment
- [ ] **Security**: No security alerts in first hour
- [ ] **Functionality**: Core business workflows functional
- [ ] **SLA Compliance**: Performance meets business requirements
- [ ] **Documentation**: Deployment process documented

### Operational Criteria
- [ ] **Monitoring**: All alerts and dashboards operational
- [ ] **Rollback Tested**: Rollback procedures verified
- [ ] **Support**: Support team notified and ready
- [ ] **Documentation**: Runbooks updated with production details

## Sign-off Process

### Technical Sign-off
- [ ] **Infrastructure Team**: All AWS resources provisioned correctly
- [ ] **Development Team**: Application functionality verified
- [ ] **Security Team**: Security posture acceptable
- [ ] **Operations Team**: Monitoring and alerting operational

### Business Sign-off
- [ ] **Product Owner**: System meets business requirements
- [ ] **Stakeholders**: Ready to accept production traffic
- [ ] **Support Team**: Trained and ready for production support
- [ ] **Management**: Go-live approved

## Go-Live Activities

### 1. DNS/Traffic Routing
```bash
# Update DNS records to point to production API
# (This would be done through DNS provider)
# Example: api.7central.co.uk -> $PROD_API
```

### 2. Monitoring Setup
```bash
# Enable all production alerts
aws cloudwatch put-metric-alarm \
  --alarm-name "SecurityAssistant-Prod-HighErrorRate" \
  --alarm-description "High error rate in production" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --alarm-actions arn:aws:sns:eu-west-2:445567098699:security-assistant-alerts \
  --profile design-lee
```

### 3. Team Notifications
```bash
# Send go-live notification
echo "🎉 PRODUCTION GO-LIVE SUCCESSFUL 🎉

Deployment Details:
- Environment: Production
- API Endpoint: $PROD_API
- Region: eu-west-2
- Deployment Time: $(date)
- All health checks: PASSED
- Performance: Within SLA
- Security: No alerts

System is ready for production traffic!

Support: junksamiad@gmail.com
Business: info@7central.co.uk
" > go-live-notification.txt

echo "Production deployment completed successfully!"
echo "API Endpoint: $PROD_API"
echo "Ready for production traffic!"
```

## Post-Go-Live Checklist

### First 24 Hours
- [ ] **Monitor Closely**: Watch for any issues or degraded performance
- [ ] **Performance Baseline**: Establish normal operating metrics
- [ ] **Error Rate Tracking**: Ensure error rates remain < 1%
- [ ] **User Feedback**: Collect any initial user feedback
- [ ] **Support Readiness**: Ensure support team is monitoring

### First Week
- [ ] **Performance Review**: Analyze actual vs expected performance
- [ ] **Cost Analysis**: Review AWS costs vs projections
- [ ] **Optimization**: Address any performance bottlenecks
- [ ] **Process Improvement**: Update deployment procedures
- [ ] **Team Retrospective**: Conduct deployment retrospective

### Documentation Updates
- [ ] **Real Endpoints**: Update docs with production API endpoints
- [ ] **Lessons Learned**: Document deployment lessons
- [ ] **Runbook Updates**: Include production-specific procedures
- [ ] **Architecture Diagrams**: Reflect actual deployed architecture

---

**🚀 Production Deployment Complete!**

The Security Design Assistant is now live in production and ready to serve users.