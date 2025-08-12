# Branch Protection Rules Configuration

This document outlines the required branch protection rules for the Security Design Assistant repository to ensure safe deployments and code quality.

## Required Branch Protection Rules

### Main Branch (`main`)

**Purpose**: Production deployments and releases

**Protection Rules**:
- ✅ Require a pull request before merging
- ✅ Require approvals: **2 reviewers minimum**
- ✅ Dismiss stale PR approvals when new commits are pushed
- ✅ Require review from code owners
- ✅ Require status checks to pass before merging
  - `validate / Validate Changes`
  - `pre-production-validation / Pre-production Validation`
- ✅ Require branches to be up to date before merging
- ✅ Require signed commits
- ✅ Include administrators in these restrictions
- ✅ Restrict pushes that create files that match a pattern
- ✅ Lock branch (disable force pushes and deletions)

**Status Checks Required**:
- Validation workflow must pass
- Pre-production validation must pass
- Staging environment must be healthy

### Develop Branch (`develop`)

**Purpose**: Staging deployments and integration

**Protection Rules**:
- ✅ Require a pull request before merging
- ✅ Require approvals: **1 reviewer minimum**
- ✅ Dismiss stale PR approvals when new commits are pushed
- ✅ Require status checks to pass before merging
  - `validate / Validate Changes`
- ✅ Require branches to be up to date before merging
- ✅ Include administrators in these restrictions
- ✅ Restrict pushes that create files that match a pattern

**Status Checks Required**:
- Validation workflow must pass
- All tests must pass
- Security scan must pass

## Setup Instructions

### Using GitHub Web Interface

1. Navigate to repository Settings → Branches
2. Click "Add rule" for each branch
3. Configure the rules as specified above

### Using GitHub CLI

```bash
# Install GitHub CLI if not already installed
# brew install gh  # macOS
# or follow instructions at https://cli.github.com/

# Authenticate
gh auth login

# Configure main branch protection
gh api repos/:owner/:repo/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"checks":[{"context":"validate / Validate Changes"},{"context":"pre-production-validation / Pre-production Validation"}]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"dismiss_stale_reviews":true,"require_code_owner_reviews":true,"required_approving_review_count":2}' \
  --field restrictions='{"users":[],"teams":[],"apps":[]}' \
  --field required_signatures=true

# Configure develop branch protection
gh api repos/:owner/:repo/branches/develop/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"checks":[{"context":"validate / Validate Changes"}]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1}' \
  --field restrictions='{"users":[],"teams":[],"apps":[]}'
```

### Using GitHub API

```bash
# Replace {owner} and {repo} with actual values
OWNER="your-organization"
REPO="security_and_design"

# Main branch protection
curl -X PUT \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/$OWNER/$REPO/branches/main/protection \
  -d '{
    "required_status_checks": {
      "strict": true,
      "checks": [
        {"context": "validate / Validate Changes"},
        {"context": "pre-production-validation / Pre-production Validation"}
      ]
    },
    "enforce_admins": true,
    "required_pull_request_reviews": {
      "dismiss_stale_reviews": true,
      "require_code_owner_reviews": true,
      "required_approving_review_count": 2
    },
    "restrictions": {
      "users": [],
      "teams": [],
      "apps": []
    },
    "required_signatures": true
  }'

# Develop branch protection
curl -X PUT \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/$OWNER/$REPO/branches/develop/protection \
  -d '{
    "required_status_checks": {
      "strict": true,
      "checks": [
        {"context": "validate / Validate Changes"}
      ]
    },
    "enforce_admins": true,
    "required_pull_request_reviews": {
      "dismiss_stale_reviews": true,
      "require_code_owner_reviews": false,
      "required_approving_review_count": 1
    },
    "restrictions": {
      "users": [],
      "teams": [],
      "apps": []
    }
  }'
```

## Code Owners File

Create a `.github/CODEOWNERS` file to define code review requirements:

```
# Global owners
* @team-leads @senior-developers

# Infrastructure changes require infrastructure team review
infrastructure/ @infrastructure-team @devops-team

# Source code changes require development team review
src/ @development-team @senior-developers

# CI/CD changes require devops team review
.github/workflows/ @devops-team @infrastructure-team

# Security-related changes require security team review
src/lambda_functions/ @security-team @senior-developers
```

## Environment Configuration

### GitHub Environments

1. **production**: Requires manual approval from designated reviewers
2. **staging**: Automatic deployment from develop branch
3. **production-approval**: Manual gate for production deployments

### Required Secrets

- `AWS_STAGING_ROLE_ARN`: IAM role for staging deployments
- `AWS_PRODUCTION_ROLE_ARN`: IAM role for production deployments
- `GEMINI_API_KEY`: API key for Gemini services

### Environment Protection Rules

**Production Environment**:
- Required reviewers: 2 minimum
- Deployment branches: `main` only
- Environment secrets: Production API keys and credentials

**Staging Environment**:
- Required reviewers: 1 minimum
- Deployment branches: `develop` only
- Environment secrets: Staging API keys and credentials

## Deployment Flow

1. **Feature Development**: 
   - Create feature branch from `develop`
   - Submit PR to `develop`
   - Automatic validation runs
   - 1 reviewer approval required
   - Merge triggers staging deployment

2. **Production Release**:
   - Create PR from `develop` to `main`
   - Pre-production validation runs
   - 2 reviewer approvals required
   - Manual approval gate
   - Merge triggers production deployment with gradual rollout

## Monitoring and Alerting

- All deployments are monitored with health checks
- Automatic rollback on failure detection
- CloudWatch alarms for error rates and system health
- SNS notifications for deployment events

---

**Note**: These branch protection rules ensure safe, validated deployments while maintaining development velocity. Adjust reviewer requirements based on team size and organizational policies.