# Branch Protection Rules Setup

## Repository Configuration

**Repository**: `https://github.com/7-central/security-design-assistant`
**Owner**: `7-central` (info@7central.co.uk)

## Required Branch Protection Rules

### Main Branch Protection

Navigate to: `https://github.com/7-central/security-design-assistant/settings/branch_protection_rules`

#### Create Rule for `main` Branch:

**Branch name pattern**: `main`

**Settings to Enable**:
- ✅ **Require pull request reviews before merging**
  - Required approving reviews: `1`
  - ✅ Dismiss stale PR approvals when new commits are pushed
  - ✅ Require review from code owners
  - ✅ Restrict who can dismiss pull request reviews
- ✅ **Require status checks to pass before merging**  
  - ✅ Require branches to be up to date before merging
  - Required status checks:
    - `Validate Changes` (from validate.yml workflow)
    - `Deploy to Staging Environment` (from deploy-staging.yml)
    - `Pre-production Validation` (from deploy-production.yml)
- ✅ **Require conversation resolution before merging**
- ✅ **Include administrators** (applies rules to repository admins)
- ✅ **Restrict pushes that create files, folders and symbolic links**
- ✅ **Allow force pushes** = ❌ (disabled for safety)
- ✅ **Allow deletions** = ❌ (disabled for safety)

### Develop Branch Protection  

**Branch name pattern**: `develop`

**Settings to Enable**:
- ✅ **Require pull request reviews before merging**
  - Required approving reviews: `1`
  - ✅ Dismiss stale PR approvals when new commits are pushed
- ✅ **Require status checks to pass before merging**
  - ✅ Require branches to be up to date before merging
  - Required status checks:
    - `Validate Changes` (from validate.yml workflow)
- ✅ **Require conversation resolution before merging**
- ✅ **Include administrators**
- ✅ **Allow force pushes** = ❌ (disabled)
- ✅ **Allow deletions** = ❌ (disabled)

## Environment Protection Rules

### Staging Environment

Navigate to: `https://github.com/7-central/security-design-assistant/settings/environments`

#### Create Environment: `staging`
- **Deployment branches**: Only `develop` branch
- **Environment secrets**: None required (uses repository secrets)
- **Required reviewers**: None (automatic deployment)
- **Wait timer**: 0 minutes

### Production Environment

#### Create Environment: `production`
- **Deployment branches**: Only `main` branch
- **Required reviewers**: 
  - `7-central` (repository owner)
  - `junksamiad` (Lee Hayton)
- **Wait timer**: 0 minutes
- **Environment secrets**: 
  - Use production-specific secrets if different from repository secrets

#### Create Environment: `production-approval`
- **Deployment branches**: Only `main` branch  
- **Required reviewers**:
  - `7-central` (repository owner)
- **Wait timer**: 0 minutes
- **Purpose**: Manual approval gate before production deployment

## Deployment Workflow

### Feature Development
1. Create feature branch from `develop`
2. Make changes and commit
3. Push feature branch 
4. Create PR to `develop`
5. **Required**: 1 approval + status checks pass
6. Merge to `develop` → **Automatic staging deployment**

### Production Release
1. Create PR from `develop` to `main`
2. **Required**: 1 approval + status checks pass + staging deployment success
3. Merge to `main` → **Manual approval required** → Production deployment

## Status Check Configuration

The following GitHub Actions workflows provide required status checks:

### validate.yml
- **Triggered**: On PR to `develop` or `main`
- **Status Check**: "Validate Changes"
- **Purpose**: Code quality, linting, tests, SAM validation

### deploy-staging.yml  
- **Triggered**: On push to `develop`
- **Status Check**: "Deploy to Staging Environment"
- **Purpose**: Automated staging deployment and health checks

### deploy-production.yml
- **Triggered**: On push to `main`
- **Status Check**: "Pre-production Validation"
- **Purpose**: Pre-deployment validation before manual approval

## Code Owners

Create `.github/CODEOWNERS` file:

```
# Global owners for all files
* @7-central @junksamiad

# Infrastructure requires additional review
/infrastructure/ @7-central
/.github/workflows/ @7-central
/docs/deployment/ @7-central

# Source code
/src/ @junksamiad
/tests/ @junksamiad
```

## Setup Commands

### Using GitHub CLI:

```bash
# Create branch protection for main
gh api repos/7-central/security-design-assistant/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["Validate Changes","Deploy to Staging Environment","Pre-production Validation"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true,"require_code_owner_reviews":true}' \
  --field restrictions=null

# Create branch protection for develop  
gh api repos/7-central/security-design-assistant/branches/develop/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["Validate Changes"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
  --field restrictions=null
```

### Using Web Interface:

1. Go to `https://github.com/7-central/security-design-assistant/settings/branches`
2. Click "Add rule" 
3. Configure settings as described above
4. Save protection rule

## Verification

### Test Branch Protection:
1. Create test branch from `develop`
2. Make small change and push
3. Create PR - verify approval required
4. Verify status checks are required
5. Test that direct push to `main` is blocked

### Test Deployment Flow:
1. Merge PR to `develop` 
2. Verify staging deployment triggers automatically
3. Create PR from `develop` to `main`
4. Verify production approval required
5. Test production deployment with approval

## Security Considerations

1. **Admin Override**: Even admins must follow branch protection rules
2. **Force Push Protection**: Disabled to prevent history manipulation  
3. **Required Reviews**: Prevents accidental direct merges
4. **Status Checks**: Ensures code quality and successful staging deployment
5. **Environment Protection**: Production deployments require manual approval

## Troubleshooting

### Common Issues:

1. **Status Checks Not Found**: 
   - Ensure workflow names match exactly
   - Run workflows at least once to register status checks

2. **Admin Can't Bypass**:
   - This is intentional for security
   - Use emergency procedures if needed

3. **PR Can't Merge**:
   - Check all required status checks have passed
   - Ensure required approvals are met
   - Verify branch is up to date

## Emergency Procedures

In case of critical production issues:

1. **Temporary Rule Disable**: Repository admins can temporarily disable branch protection
2. **Hotfix Process**: Create `hotfix/` branch from `main`, merge back to both `main` and `develop`
3. **Emergency Deployment**: Use manual workflow dispatch with skip approval option

## Documentation

After setup, document the actual configuration in:
- README.md (development workflow section)
- CONTRIBUTING.md (for external contributors)
- This file (as reference for future changes)