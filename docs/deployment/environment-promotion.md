# Environment Promotion Workflow

This document describes the process for promoting code and configurations through the different environments in the Security Design Assistant deployment pipeline.

## Environment Overview

The Security Design Assistant uses a three-tier environment strategy:

```
Development (Local/Dev) → Staging → Production
```

Each environment serves specific purposes and has different requirements for promotion.

## Promotion Flow

### 1. Development to Staging

**Trigger**: Merge to `develop` branch
**Automation**: Fully automated via GitHub Actions

#### Prerequisites
- All validation checks pass (linting, tests, security scan)
- Pull request approved by at least 1 reviewer
- Branch is up to date with develop

#### Process
1. Developer creates feature branch from `develop`
2. Makes changes and commits
3. Creates Pull Request to `develop`
4. Automated validation workflow runs:
   - Code quality checks (ruff, mypy)
   - Unit and integration tests
   - Security scan (bandit)
   - SAM template validation
   - CFN lint checks
5. After approval and merge, automatic deployment to staging
6. Post-deployment health checks and smoke tests

#### Validation Criteria
- All tests pass with >80% coverage
- No HIGH severity security issues
- SAM template validates successfully
- No linting or type errors

### 2. Staging to Production

**Trigger**: Merge to `main` branch
**Automation**: Semi-automated (requires manual approval)

#### Prerequisites
- Staging environment is stable and healthy
- Pre-production validation passes
- Manual approval from 2+ reviewers
- Business approval for production changes

#### Process
1. Create Pull Request from `develop` to `main`
2. Pre-production validation runs:
   - All standard validation checks
   - Staging environment health verification
   - Extended test suite execution
3. Code review and approval process
4. Manual approval gate (production approval environment)
5. Automated production deployment with gradual rollout
6. Continuous monitoring during deployment
7. Post-deployment validation and smoke tests

#### Validation Criteria
- Staging environment error rate <5% for past 24 hours
- All critical tests pass
- No unresolved HIGH or MEDIUM security issues
- Performance benchmarks meet requirements
- Business stakeholder approval

## Branch Protection Rules

### Develop Branch
- Requires 1 approval
- Status checks must pass
- Branch must be up to date
- Dismiss stale reviews when new commits pushed

### Main Branch  
- Requires 2 approvals
- Status checks must pass
- Branch must be up to date
- Requires review from code owners
- Requires signed commits
- Dismiss stale reviews when new commits pushed

## Environment-Specific Configurations

### Development
```yaml
Resources:
  Memory: 512MB
  Timeout: 5 minutes
  Traffic Shifting: 50% every 2 minutes
  Monitoring: Basic
  Approval: None required
```

### Staging
```yaml
Resources:
  Memory: 1GB
  Timeout: 10 minutes
  Traffic Shifting: 10% every 5 minutes
  Monitoring: Enhanced
  Approval: 1 reviewer
```

### Production
```yaml
Resources:
  Memory: 2GB
  Timeout: 15 minutes
  Traffic Shifting: 5% every 10 minutes
  Monitoring: Comprehensive
  Approval: 2 reviewers + manual gate
```

## Promotion Checklist

### Before Staging Promotion

- [ ] Feature complete and tested locally
- [ ] Unit tests updated and passing
- [ ] Integration tests passing
- [ ] Documentation updated
- [ ] Security scan clean
- [ ] Performance impact assessed
- [ ] Breaking changes documented

### Before Production Promotion

- [ ] Staging deployment successful
- [ ] Staging environment stable for 24+ hours
- [ ] Performance testing completed
- [ ] Security review completed
- [ ] Business stakeholder approval
- [ ] Rollback plan documented
- [ ] Monitoring and alerting verified
- [ ] Team available for deployment support

## Special Promotion Scenarios

### Emergency/Hotfix Promotion

**When to Use**:
- Critical production bugs
- Security vulnerabilities
- Service outages

**Process**:
1. Create hotfix branch from `main`
2. Apply minimal fix
3. Fast-track review process
4. Skip normal staging validation (with approval)
5. Direct deployment to production
6. Post-deployment monitoring
7. Backport fix to `develop`

**Approval Required**:
- Technical Lead approval
- Business stakeholder approval
- Operations team notification

### Configuration-Only Changes

**Examples**:
- Environment variable updates
- Feature flags
- Timeout adjustments
- Scaling parameters

**Process**:
1. Update configuration files
2. Follow normal promotion process
3. Deploy with faster traffic shifting
4. Monitor for configuration-related issues

### Infrastructure Changes

**Examples**:
- SAM template updates
- New resources
- IAM policy changes
- Monitoring updates

**Process**:
1. Infrastructure changes require extra review
2. Test in staging with production-like load
3. Plan for potential rollback
4. Coordinate with operations team
5. Monitor resource utilization post-deployment

## Monitoring During Promotion

### Key Metrics to Watch

1. **Error Rates**
   - Lambda function errors
   - API Gateway 4xx/5xx responses
   - DLQ message count

2. **Performance**
   - Response times
   - Lambda duration
   - Queue processing time

3. **Resource Utilization**
   - Lambda concurrency
   - DynamoDB capacity
   - Memory usage

4. **Business Metrics**
   - Processing success rate
   - User experience metrics
   - Cost impact

### Automated Monitoring

- CloudWatch alarms for error thresholds
- Pre/post-traffic hook validations
- Automated rollback on failure detection
- SNS notifications for deployment events

### Manual Monitoring

- Real-time dashboard monitoring
- Log analysis for errors
- Performance baseline comparison
- Customer impact assessment

## Rollback Procedures

Each environment has specific rollback procedures:

### Staging Rollback
- Automated rollback via GitHub Actions
- Fast rollback (minimal business impact)
- Can be used for testing rollback procedures

### Production Rollback
- Automated rollback via CloudFormation
- Manual emergency rollback procedures
- Requires immediate team notification
- Customer communication may be required

## Approval Matrix

| Change Type | Staging | Production |
|-------------|---------|------------|
| Feature Updates | 1 Developer | 2 Developers + Business |
| Bug Fixes | 1 Developer | 2 Developers |
| Hotfixes | 1 Senior Dev | 1 Senior Dev + Business |
| Infrastructure | 1 DevOps | 2 DevOps + 1 Developer |
| Configuration | 1 Developer | 1 Senior Dev + DevOps |

## Best Practices

### Code Promotion
- Keep changes small and focused
- Test thoroughly in lower environments
- Use feature flags for gradual rollouts
- Document all changes clearly

### Timing
- Deploy during low-traffic periods
- Avoid deployments on Fridays/holidays
- Schedule maintenance windows for major changes
- Coordinate with business stakeholders

### Communication
- Notify stakeholders before production deployments
- Update status pages for major changes
- Have team available during deployments
- Post-deployment summary communications

### Risk Mitigation
- Use gradual traffic shifting
- Monitor key metrics during deployment
- Have rollback plan ready
- Test rollback procedures regularly

## Troubleshooting Common Issues

### Promotion Blocked
- Check branch protection rules
- Verify all status checks pass
- Ensure approvals are in place
- Check for merge conflicts

### Deployment Failures
- Review CloudFormation events
- Check IAM permissions
- Verify resource limits
- Examine application logs

### Performance Issues
- Monitor CloudWatch metrics
- Check Lambda memory allocation
- Verify database capacity
- Analyze queue depths

---

For specific technical procedures, see:
- [Deployment Guide](./README.md)
- [Rollback Procedures](./rollback-procedures.md)
- [Monitoring Guide](../monitoring/README.md)