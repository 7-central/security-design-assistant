# GitHub Setup Documentation

## Repository Structure

### Current Repository Structure
```
7-central (Account Owner)
├── Username: 7-central  
├── Email: info@7central.co.uk
└── security-design-assistant (Repository)
    ├── main (Production branch)
    └── develop (Staging branch)
    └── Collaborators:
        └── junksamiad (Lee Hayton) - Push access
```

**Repository URL**: https://github.com/7-central/security-design-assistant

*Note: Future expansion planned for 7Central GitHub Organization with separate repos for Security, Argan-HR, and Tier8 business units.*

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

### Collaborators

1. **7-central** - Owner
   - Account: info@7central.co.uk
   - Full repository access
   - Settings management
   - Deployment approvals
   - Personal Access Token configured for CI/CD

2. **junksamiad** (Lee Hayton) - Developer  
   - Email: junksamiad@gmail.com
   - Push access granted
   - Create branches and pull requests
   - Local development and commits

### Development Workflow

```mermaid
graph LR
    A[Local: junksamiad] -->|push| B[Remote: feature branch]
    B -->|PR| C[Remote: develop]
    C -->|PR + Approval| D[Remote: main]
    C -->|Auto Deploy| E[AWS: Staging]
    D -->|Auto Deploy| F[AWS: Production]
```

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

For pushing to 7-central's repository from junksamiad account:

```bash
# Current setup: junksamiad has been added as collaborator with push access
# Standard HTTPS authentication will work with GitHub credentials

# Option 1: Use GitHub CLI (Recommended)
gh auth login
# Then work normally with git commands

# Option 2: Use Personal Access Token (if needed)
git remote set-url origin https://junksamiad:TOKEN@github.com/7-central/security-design-assistant.git

# Option 3: Use SSH key (if configured)
git remote set-url origin git@github.com:7-central/security-design-assistant.git
```

### Current Configuration Status

```bash
# Repository details
Repository: 7-central/security-design-assistant
Owner: 7-central (info@7central.co.uk)
Collaborator: junksamiad (junksamiad@gmail.com) with push access
Local git user: Lee Hayton <junksamiad@gmail.com>
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
Create `CODEOWNERS` file:
```
# Default owners for everything
* @RICG777 @junksamiad

# Infrastructure
/infrastructure/ @RICG777
/scripts/ @RICG777

# Application code
/src/ @junksamiad
/tests/ @junksamiad
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
   # Update with correct credentials
   git remote set-url origin https://TOKEN@github.com/RICG777/repo.git
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

1. Create repository on RICG777 account
2. Configure branch protection rules
3. Add GitHub Actions secrets
4. Set up initial CI/CD workflows
5. Configure Dependabot
6. Create first feature branch and test workflow