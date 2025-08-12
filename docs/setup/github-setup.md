# GitHub Setup Documentation

## Account Structure & Roles

### GitHub Account Hierarchy
```
7-central (Organization Account)
├── Account Type: Organization account for 7Central business
├── Email: info@7central.co.uk
├── Managed By: Lee Hayton (junksamiad) with full admin access
└── security-design-assistant (Repository)
    ├── main (Production branch)
    └── develop (Staging branch)
```

### Key Personnel & Roles

| Person | Role | GitHub Username | Access Level | Responsibilities |
|--------|------|----------------|--------------|------------------|
| Ric | Product Owner | @RICG777 (personal) | Owner (via 7-central) | Business decisions, approvals |
| Lee Hayton | Developer/DevOps | @junksamiad | Admin on 7-central account + Collaborator | Development, CI/CD setup, repo management |

### Important Context
- **7-central account**: Created by Lee on behalf of Ric (Product Owner) to properly organize business repositories
- **@junksamiad (Lee)**: Has full admin access to 7-central account for setup and management, plus collaborator access for development
- **@RICG777**: Ric's personal GitHub account (not used for this project, but may be referenced in future)
- **Repository URL**: https://github.com/7-central/security-design-assistant

### Access Clarification
- **Lee (junksamiad)** can:
  - ✅ Create and manage repositories under 7-central
  - ✅ Configure GitHub secrets and settings
  - ✅ Set up branch protection rules
  - ✅ Manage CI/CD workflows
  - ✅ Push code as collaborator
  - ✅ Admin all aspects of 7-central account
  
- **Future State**: Additional developers will be added as collaborators with appropriate access levels

## Repository Configuration

### Repository Settings

1. **General Settings**
   - Repository name: `security-design-assistant`
   - Description: "AI-powered security and design review system for 7Central"
   - Topics: `ai`, `security`, `design-review`, `aws`, `serverless`, `gemini`
   - Default branch: `main`

2. **Branch Protection Rules**

   **Main Branch:**
   - Require pull request reviews (1 approval minimum)
   - Dismiss stale PR approvals on new commits
   - Require status checks to pass
   - Require branches to be up to date
   - Include administrators in restrictions

   **Develop Branch:**
   - Require pull request reviews (1 approval minimum)
   - Require status checks to pass

3. **GitHub Actions Secrets**

   Required secrets for CI/CD:
   ```
   AWS_ACCESS_KEY_ID        # From 7c-IAM-Admin-User
   AWS_SECRET_ACCESS_KEY    # From 7c-IAM-Admin-User
   AWS_REGION              # eu-west-2
   GEMINI_API_KEY          # Google Gemini API key
   ```

## Access Management

### Current Setup

1. **7-central** - Organization Account
   - Managed by: Lee Hayton (@junksamiad) with admin access
   - Account email: info@7central.co.uk
   - Purpose: Host all 7Central business repositories
   - Lee can configure all settings, secrets, and CI/CD

2. **junksamiad** (Lee Hayton) - Developer/Admin
   - Email: junksamiad@gmail.com
   - Dual role:
     - Admin access to 7-central account (can configure everything)
     - Collaborator on repos for development work
   - Responsibilities:
     - Repository setup and management
     - GitHub secrets configuration
     - CI/CD pipeline setup
     - Development and code commits

### Development Workflow

Since Lee has admin access to 7-central account, the workflow is streamlined:

```mermaid
graph LR
    A[Local: Lee/junksamiad] -->|push| B[Remote: feature branch]
    B -->|PR| C[Remote: develop]
    C -->|PR| D[Remote: main]
    A -->|Can also configure| E[GitHub Secrets]
    A -->|Can also configure| F[Branch Protection]
    C -->|Auto Deploy| G[AWS: Staging]
    D -->|Auto Deploy| H[AWS: Production]
```

**Key Points:**
- Lee works locally as @junksamiad
- Pushes code to 7-central/security-design-assistant
- Can directly configure all repository settings via 7-central admin access
- No need to coordinate with another admin for secrets or settings

## Git Configuration

### Initial Setup

```bash
# Configure git identity (for commits)
git config user.name "Lee Hayton"
git config user.email "junksamiad@gmail.com"

# Add remote repository
git remote add origin https://github.com/7-central/security-design-assistant.git

# Verify remote configuration
git remote -v
```

### Authentication

For Lee (junksamiad) pushing to 7-central's repository:

```bash
# Lee has dual access:
# 1. Admin access to 7-central account (for configuration)
# 2. Collaborator access to repos (for development)

# Option 1: Use GitHub CLI (Recommended)
gh auth login
# Authenticate with junksamiad account
# Then work normally with git commands

# Option 2: Use Personal Access Token
git remote set-url origin https://junksamiad:TOKEN@github.com/7-central/security-design-assistant.git

# Option 3: Use SSH key (if configured)
git remote set-url origin git@github.com:7-central/security-design-assistant.git
```

### Current Configuration Status

```bash
# Repository Structure
Organization: 7-central (managed by Lee/junksamiad)
Repository: 7-central/security-design-assistant
Repository URL: https://github.com/7-central/security-design-assistant.git

# Access Configuration
Admin of 7-central: junksamiad (Lee Hayton)
Collaborator on repo: junksamiad (Lee Hayton)
Local git user: Lee Hayton <junksamiad@gmail.com>

# Practical Impact
- Lee can push code as junksamiad
- Lee can configure secrets via 7-central admin access
- Lee can set up CI/CD without external coordination
```

## Branch Strategy

### Branch Types

1. **main** - Production-ready code
2. **develop** - Integration branch for features
3. **feature/** - New features (e.g., `feature/story-3-4-aws-setup`)
4. **bugfix/** - Bug fixes (e.g., `bugfix/pdf-processing-error`)
5. **hotfix/** - Urgent production fixes

### Branch Naming Convention

```
type/story-number-description

Examples:
- feature/story-1-2-schedule-agent
- bugfix/story-2-3-excel-formatting
- hotfix/critical-api-error
```

## GitHub Actions Workflows

### CI/CD Pipeline

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to AWS

on:
  push:
    branches:
      - main
      - develop

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      - name: Run tests
        run: pytest

  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ secrets.AWS_REGION }}
      - name: Deploy with SAM
        run: |
          sam build
          if [ "${{ github.ref }}" == "refs/heads/main" ]; then
            sam deploy --config-env prod --no-confirm-changeset
          else
            sam deploy --config-env staging --no-confirm-changeset
          fi
```

### Code Quality Checks

Create `.github/workflows/quality.yml`:

```yaml
name: Code Quality

on:
  pull_request:
    branches:
      - main
      - develop

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install ruff mypy
      - name: Run linting
        run: ruff check src/ tests/
      - name: Run type checking
        run: mypy src/
```

## Pull Request Template

Create `.github/pull_request_template.md`:

```markdown
## Description
Brief description of changes

## Story Reference
- Story: #X.Y

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No sensitive data exposed
```

## Issue Templates

### Bug Report
Create `.github/ISSUE_TEMPLATE/bug_report.md`:

```markdown
---
name: Bug Report
about: Report a bug in the application
title: '[BUG] '
labels: bug
---

**Description**
Clear description of the bug

**Steps to Reproduce**
1. Step 1
2. Step 2

**Expected Behavior**
What should happen

**Actual Behavior**
What actually happens

**Environment**
- Environment: [staging/production]
- Browser/Client: 
- Date/Time:
```

### Feature Request
Create `.github/ISSUE_TEMPLATE/feature_request.md`:

```markdown
---
name: Feature Request
about: Suggest a new feature
title: '[FEATURE] '
labels: enhancement
---

**Problem Statement**
What problem does this solve?

**Proposed Solution**
How should it work?

**Alternatives Considered**
Other options explored

**Additional Context**
Any other relevant information
```

## Repository Files

### README.md
Update the main README with:
- Project overview
- Quick start guide
- Links to documentation
- Build status badges
- Contributing guidelines

### .gitignore
Ensure includes:
```
# Python
__pycache__/
*.py[cod]
venv/
.env

# AWS
.aws-sam/
samconfig.toml.local

# Local storage
local_output/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

### CODEOWNERS
Create `.github/CODEOWNERS` file:
```
# Code ownership structure for PR reviews
# Note: @RICG777 is Ric's personal account (Product Owner)
# @junksamiad is Lee's account (Developer/Admin)

# Default owners for everything
* @junksamiad

# Future: When Ric joins GitHub development
# * @RICG777 @junksamiad

# Infrastructure and deployment
/infrastructure/ @junksamiad
/.github/ @junksamiad
/scripts/ @junksamiad

# Application code
/src/ @junksamiad
/tests/ @junksamiad

# Documentation (for future PO review)
/docs/prd/ @junksamiad
/docs/stories/ @junksamiad
```

## Deployment Strategy

### Environments

1. **Local Development**
   - Branch: feature/*
   - Deploy: Manual local testing
   - Storage: Local file system

2. **Staging**
   - Branch: develop
   - Deploy: Automatic on push
   - AWS Stack: security-assistant-staging

3. **Production**
   - Branch: main
   - Deploy: Automatic on push (with approval)
   - AWS Stack: security-assistant-prod

### Release Process

1. Create feature branch from develop
2. Implement and test locally
3. Push and create PR to develop
4. Review and merge to develop (auto-deploy to staging)
5. Test in staging environment
6. Create PR from develop to main
7. Review, approve, and merge (auto-deploy to production)

## Security Considerations

1. **Never commit sensitive data**
   - Use GitHub Secrets for credentials
   - Add .env to .gitignore
   - Use git-secrets pre-commit hooks

2. **Access Control**
   - Limit write access to trusted developers
   - Require PR reviews for main branch
   - Use CODEOWNERS for critical files

3. **Dependency Management**
   - Use Dependabot for security updates
   - Review and test dependency updates
   - Pin versions in requirements.txt

## Monitoring

### GitHub Insights
- Track commit frequency
- Monitor PR turnaround time
- Review code coverage trends

### Actions Monitoring
- Set up notifications for failed deployments
- Monitor build times
- Track deployment frequency

## Troubleshooting

### Common Issues

1. **Permission Denied on Push**
   ```bash
   # Check remote URL
   git remote -v
   # Should show: https://github.com/7-central/security-design-assistant.git
   
   # If needed, update with correct credentials
   git remote set-url origin https://junksamiad:TOKEN@github.com/7-central/security-design-assistant.git
   ```

2. **Merge Conflicts**
   ```bash
   # Update local branch
   git pull origin develop
   # Resolve conflicts
   git add .
   git commit -m "resolve conflicts"
   git push
   ```

3. **Actions Failing**
   - Check GitHub Actions logs
   - Verify secrets are configured
   - Test locally with same commands

## Next Steps

1. ~~Create repository on 7-central account~~ ✅ DONE
2. Configure branch protection rules (Lee can do via 7-central admin)
3. Add GitHub Actions secrets (Lee can do via 7-central admin)
4. Set up initial CI/CD workflows (Story 4.3.1)
5. Configure Dependabot for security updates
6. Create first feature branch and test workflow

**Note**: Since Lee has admin access to 7-central, all configuration can be done directly without coordination.