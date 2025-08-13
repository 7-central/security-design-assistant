# Real Deployment Integration Checklist

## Pre-Deployment Setup

### ✅ Repository Configuration

**Repository**: `7-central/security-design-assistant`

- [ ] **Verify Repository Exists**: https://github.com/7-central/security-design-assistant
- [ ] **Confirm Collaborators**: 
  - `7-central` (owner)
  - `junksamiad` (developer with push access)
- [ ] **Check Default Branch**: `main` is default branch

### ✅ GitHub Actions Secrets

Navigate to: `https://github.com/7-central/security-design-assistant/settings/secrets/actions`

**Required Secrets**:
- [ ] `AWS_ACCESS_KEY_ID` (from lee-hayton IAM user)
- [ ] `AWS_SECRET_ACCESS_KEY` (from lee-hayton IAM user)  
- [ ] `AWS_REGION` = `eu-west-2`
- [ ] `GEMINI_API_KEY` (production Google Gemini API key)

**Optional (if using IAM roles)**:
- [ ] `AWS_STAGING_ROLE_ARN` 
- [ ] `AWS_PRODUCTION_ROLE_ARN`

### ✅ Branch Protection Rules

**Main Branch** (`https://github.com/7-central/security-design-assistant/settings/branch_protection_rules`):
- [ ] Require pull request reviews (1 approval)
- [ ] Dismiss stale PR approvals  
- [ ] Require status checks: `Validate Changes`, `Deploy to Staging Environment`, `Pre-production Validation`
- [ ] Require branches to be up to date
- [ ] Include administrators
- [ ] Restrict pushes that create files
- [ ] Disable force pushes and deletions

**Develop Branch**:
- [ ] Require pull request reviews (1 approval)
- [ ] Require status checks: `Validate Changes`
- [ ] Include administrators
- [ ] Disable force pushes and deletions

### ✅ Environment Protection

**Environments** (`https://github.com/7-central/security-design-assistant/settings/environments`):

- [ ] **staging**: 
  - Deployment branches: `develop` only
  - No required reviewers (automatic)
- [ ] **production**:
  - Deployment branches: `main` only  
  - Required reviewers: `7-central`
- [ ] **production-approval**:
  - Deployment branches: `main` only
  - Required reviewers: `7-central`

## AWS Infrastructure Verification

### ✅ S3 Bucket
- [ ] **Bucket Exists**: `security-assistant-sam-deployments` in `eu-west-2`
- [ ] **Access Verified**: Both `design-lee` and `design` profiles can access
- [ ] **Versioning Enabled**: Confirm versioning is enabled
- [ ] **Lifecycle Policy**: 30-day retention for old versions

### ✅ IAM Permissions
- [ ] **design-lee profile**: Can deploy SAM stacks in `eu-west-2`
- [ ] **design profile**: Can deploy SAM stacks in `eu-west-2` 
- [ ] **Test Deployment**: Run `sam validate` with both profiles

### ✅ Regional Configuration
- [ ] **Region Consistency**: All infrastructure uses `eu-west-2`
- [ ] **SAM Config Updated**: `infrastructure/samconfig.toml` uses `eu-west-2`
- [ ] **Workflows Updated**: GitHub Actions use `eu-west-2`

## First Staging Deployment

### ✅ Pre-Deployment Tests
- [ ] **Local Build**: `sam build` succeeds locally
- [ ] **Template Validation**: `sam validate` passes
- [ ] **CFN Lint**: `cfn-lint infrastructure/template.yaml` passes
- [ ] **Unit Tests**: `pytest tests/unit/` passes
- [ ] **Security Scan**: `bandit -r src/` shows no critical issues

### ✅ Trigger Staging Deployment
- [ ] **Create Feature Branch**: From `develop`
- [ ] **Make Test Change**: Update version or add comment
- [ ] **Push Branch**: Verify validation workflow runs
- [ ] **Create PR to develop**: Verify all checks pass
- [ ] **Merge PR**: Should trigger automatic staging deployment

### ✅ Staging Deployment Verification
- [ ] **GitHub Actions Success**: `deploy-staging.yml` completes successfully
- [ ] **CloudFormation Stack**: `security-assistant-staging` exists in `eu-west-2`
- [ ] **API Gateway**: Health endpoint returns 200
- [ ] **DynamoDB Table**: `security-assistant-jobs-staging` created
- [ ] **S3 Bucket**: `security-assistant-files-staging` created
- [ ] **SQS Queues**: Processing and DLQ queues created
- [ ] **Lambda Functions**: All functions deployed and healthy
- [ ] **CloudWatch Logs**: Log groups created with proper retention
- [ ] **Monitoring**: CloudWatch dashboards accessible

### ✅ Post-Deployment Health Checks
- [ ] **API Health**: `curl https://{api-endpoint}/health` returns 200
- [ ] **Lambda Invocation**: Functions can be invoked successfully
- [ ] **DynamoDB Access**: Can read/write to tables
- [ ] **S3 Operations**: Can upload/download files
- [ ] **SQS Processing**: Messages can be sent/received
- [ ] **Error Rates**: < 1% error rate in first hour
- [ ] **Response Times**: Average < 2 seconds

### ✅ Monitoring Validation
- [ ] **CloudWatch Metrics**: Custom metrics appearing
- [ ] **X-Ray Traces**: Distributed tracing working
- [ ] **Log Aggregation**: Structured logs in CloudWatch
- [ ] **Alarm Configuration**: Alarms active and properly configured
- [ ] **Dashboard Access**: Can view application metrics

## Production Deployment Validation

### ✅ Pre-Production Checks
- [ ] **Staging Stable**: No errors in staging for 24+ hours
- [ ] **Load Testing**: Staging environment handles expected load
- [ ] **Security Review**: No high/medium security issues
- [ ] **Documentation Updated**: All deployment docs current

### ✅ Production Deployment Process
- [ ] **Create PR**: From `develop` to `main`
- [ ] **Validation Passes**: All pre-production checks pass
- [ ] **Manual Approval**: Repository owner approves deployment
- [ ] **Gradual Rollout**: Traffic shifting with monitoring
- [ ] **Health Monitoring**: 10-minute health check period passes

### ✅ Production Verification
- [ ] **CloudFormation Stack**: `security-assistant-prod` deployed
- [ ] **All Resources Created**: Lambda, API Gateway, DynamoDB, S3, SQS
- [ ] **Termination Protection**: Enabled for production stack
- [ ] **API Functionality**: Production endpoint fully functional
- [ ] **Performance**: Meets SLA requirements
- [ ] **Security**: No security alerts in first hour

### ✅ Rollback Testing
- [ ] **Simulate Failure**: Test automatic rollback triggers
- [ ] **Manual Rollback**: Verify rollback procedures work
- [ ] **Recovery Time**: < 5 minutes for automatic rollback

## Documentation Updates

### ✅ Lessons Learned
- [ ] **Document Issues**: Any problems encountered during deployment
- [ ] **Update Procedures**: Improve deployment documentation
- [ ] **Performance Notes**: Document actual vs expected performance
- [ ] **Security Findings**: Note any security configurations needed

### ✅ Final Documentation
- [ ] **README Update**: Include deployment status and endpoints
- [ ] **Architecture Docs**: Reflect actual deployed configuration
- [ ] **Runbook Update**: Include real environment details
- [ ] **Contact Information**: Update with support/escalation details

## Sign-off Checklist

### ✅ Technical Sign-off
- [ ] **Developer**: `junksamiad` - All code and infrastructure deployed
- [ ] **Infrastructure**: Confirmed working in both staging and production
- [ ] **Monitoring**: All alerting and monitoring operational
- [ ] **Documentation**: Complete and accurate

### ✅ Business Sign-off  
- [ ] **Product Owner**: `7-central` - System meets requirements
- [ ] **Operations**: Ready for production use
- [ ] **Security**: Security review completed
- [ ] **Go-Live Approval**: Approved for production traffic

## Post-Deployment

### ✅ Immediate (First 24 Hours)
- [ ] **Monitor Closely**: Watch for any issues or alerts
- [ ] **Performance Baseline**: Establish normal operating metrics  
- [ ] **User Feedback**: Collect initial user feedback
- [ ] **Support Readiness**: Support team trained and ready

### ✅ Short Term (First Week)
- [ ] **Optimization**: Address any performance issues
- [ ] **Cost Analysis**: Review actual vs projected costs
- [ ] **Process Improvement**: Update deployment process based on learnings
- [ ] **Team Retrospective**: Conduct deployment retrospective

---

## Emergency Contacts

**Technical Issues**: junksamiad@gmail.com
**Business Issues**: info@7central.co.uk  
**AWS Account**: 445567098699
**Region**: eu-west-2

## Success Criteria

✅ **Deployment Complete When**:
- Both staging and production environments operational
- All automated tests passing
- Monitoring and alerting functional  
- Documentation complete and accurate
- Team trained on operations and support

**🎉 Ready for Production Traffic!**