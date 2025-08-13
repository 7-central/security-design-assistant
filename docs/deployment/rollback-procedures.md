# Rollback Procedures

This document outlines the procedures for rolling back deployments in case of issues or failures.

## Overview

The Security Design Assistant uses multiple rollback mechanisms to ensure system stability:

1. **Automatic Rollback**: Triggered by CloudWatch alarms during deployment
2. **Manual Rollback**: Operator-initiated rollback procedures
3. **Emergency Rollback**: Fast rollback for critical issues

## Rollback Mechanisms

### 1. Automatic Rollback

**Trigger Conditions**:
- Lambda error rate > threshold (5% prod, 10% staging)
- API Gateway 5xx errors > 5 per 5-minute period
- DLQ messages present
- Pre/post-traffic hook failures

**Process**:
1. CloudWatch alarm triggers
2. CodeDeploy automatically stops traffic shifting
3. Traffic routes back to previous version
4. Rollback completes within 2-5 minutes
5. Notifications sent via SNS/Slack

### 2. Manual Rollback via GitHub Actions

**When to Use**:
- Issues discovered after deployment completes
- Performance degradation detected
- Business decision to revert changes

**Procedure**:

#### Production Rollback
```bash
# Option 1: Trigger via GitHub Actions
gh workflow run deploy-production.yml \
  --ref main \
  --field skip_approval=true \
  --field environment=prod

# Option 2: Direct AWS CLI
aws cloudformation cancel-update-stack \
  --stack-name security-assistant-prod
```

#### Staging Rollback
```bash
# Redeploy previous version
git checkout develop~1  # Go to previous commit
gh workflow run deploy-staging.yml --ref develop
```

### 3. Emergency Rollback via AWS CLI

**When to Use**:
- Critical production issues
- GitHub Actions unavailable
- Immediate rollback required

**Prerequisites**:
- AWS CLI configured with appropriate permissions
- Access to production AWS account

**Procedure**:

#### Step 1: Stop Current Deployment
```bash
# Cancel any in-progress deployment
aws cloudformation cancel-update-stack \
  --stack-name security-assistant-prod \
  --region us-east-1
```

#### Step 2: Rollback Stack
```bash
# Wait for cancellation to complete
aws cloudformation wait stack-update-complete \
  --stack-name security-assistant-prod \
  --region us-east-1 || \
aws cloudformation wait stack-rollback-complete \
  --stack-name security-assistant-prod \
  --region us-east-1
```

#### Step 3: Verify Rollback
```bash
# Check stack status
aws cloudformation describe-stacks \
  --stack-name security-assistant-prod \
  --query 'Stacks[0].StackStatus' \
  --output text

# Verify API endpoint
API_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name security-assistant-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
  --output text)

curl -f "${API_ENDPOINT}/health"
```

## Rollback Scenarios

### Scenario 1: High Error Rate

**Symptoms**:
- CloudWatch alarms firing
- Increased 5xx responses
- Customer complaints

**Actions**:
1. Check if automatic rollback triggered
2. If not, initiate manual rollback
3. Investigate root cause
4. Fix and redeploy

**Verification**:
```bash
# Check current error rate
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=security-assistant-worker-prod \
  --start-time $(date -u -d '10 minutes ago' '+%Y-%m-%dT%H:%M:%S') \
  --end-time $(date -u '+%Y-%m-%dT%H:%M:%S') \
  --period 300 \
  --statistics Sum
```

### Scenario 2: Performance Degradation

**Symptoms**:
- Increased response times
- Lambda timeouts
- Queue backlog

**Actions**:
1. Check Lambda metrics
2. Verify memory/timeout settings
3. If severe, initiate rollback
4. Optimize and redeploy

**Verification**:
```bash
# Check Lambda duration
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=security-assistant-api-prod \
  --start-time $(date -u -d '10 minutes ago' '+%Y-%m-%dT%H:%M:%S') \
  --end-time $(date -u '+%Y-%m-%dT%H:%M:%S') \
  --period 300 \
  --statistics Average,Maximum
```

### Scenario 3: Data Corruption

**Symptoms**:
- Incorrect processing results
- Database inconsistencies
- Missing or corrupted files

**Actions**:
1. **IMMEDIATE**: Stop all processing
2. Disable API endpoints if necessary
3. Initiate emergency rollback
4. Restore data from backups
5. Full system validation before re-enabling

**Emergency Stop**:
```bash
# Disable API Gateway (if needed)
aws apigateway update-stage \
  --rest-api-id $(aws apigateway get-rest-apis --query 'items[?name==`security-assistant-prod`].id' --output text) \
  --stage-name prod \
  --patch-ops op=replace,path=/throttle/rateLimit,value=0
```

## Validation After Rollback

### System Health Checks

1. **API Health**:
```bash
curl -f "${API_ENDPOINT}/health"
```

2. **Lambda Functions**:
```bash
# Test each function
aws lambda invoke \
  --function-name security-assistant-api-prod \
  --payload '{"test": true}' \
  response.json
```

3. **Database Connectivity**:
```bash
# Check DynamoDB table
aws dynamodb describe-table \
  --table-name security-assistant-jobs-prod
```

4. **Queue Status**:
```bash
# Check SQS queues
aws sqs get-queue-attributes \
  --queue-url $(aws sqs get-queue-url --queue-name security-assistant-processing-prod --query 'QueueUrl' --output text) \
  --attribute-names All
```

### Smoke Tests

Run limited smoke tests to verify basic functionality:

```bash
# Set environment for testing
export API_BASE_URL="${API_ENDPOINT}"
export ENVIRONMENT="prod"

# Run smoke tests
python -m pytest tests/integration/test_e2e.py::test_health_check -v
```

## Communication

### During Rollback

1. **Internal Team**:
   - Slack #incidents channel
   - Update status page
   - Notify stakeholders

2. **External Communication**:
   - Customer notifications (if required)
   - Status page updates
   - Support team briefing

### Post-Rollback

1. **Incident Report**:
   - Root cause analysis
   - Timeline of events
   - Action items

2. **Lessons Learned**:
   - Process improvements
   - Monitoring enhancements
   - Prevention strategies

## Prevention

### Pre-deployment Checks

- Comprehensive testing in staging
- Gradual rollout configuration
- Monitoring and alerting setup
- Rollback plan review

### Deployment Best Practices

- Deploy during low-traffic periods
- Monitor deployments closely
- Have team available during deployments
- Test rollback procedures regularly

## Testing Rollback Procedures

### Staging Environment Testing

Monthly rollback testing in staging:

```bash
# Deploy a test version
sam deploy --config-env staging --parameter-overrides "TestFlag=true"

# Simulate failure and rollback
aws cloudformation cancel-update-stack --stack-name security-assistant-staging

# Verify rollback success
curl -f "${STAGING_API_ENDPOINT}/health"
```

### Documentation Updates

- Keep rollback procedures current
- Update contact information
- Test emergency procedures quarterly
- Train team members on procedures

---

**Emergency Contacts**:
- On-call Engineer: [Contact Info]
- AWS Support: [Support Case Link]
- Management Escalation: [Contact Info]

**Quick Reference**:
- Production Stack: `security-assistant-prod`
- Staging Stack: `security-assistant-staging`
- Region: `us-east-1`
- Monitoring: [CloudWatch Dashboard Link]