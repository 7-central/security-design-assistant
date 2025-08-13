# GitHub Actions Secrets Setup

## Required Secrets Configuration

The following secrets must be configured in the GitHub repository settings at:
`https://github.com/7-central/security-design-assistant/settings/secrets/actions`

### AWS Credentials

#### For Development/Staging (design-lee profile):
- **AWS_ACCESS_KEY_ID**: Access key ID from `lee-hayton` IAM user
- **AWS_SECRET_ACCESS_KEY**: Secret access key from `lee-hayton` IAM user

#### For Production (design profile):
- **AWS_PRODUCTION_ACCESS_KEY_ID**: Access key ID from `7c-IAM-Admin-User` IAM user
- **AWS_PRODUCTION_SECRET_ACCESS_KEY**: Secret access key from `7c-IAM-Admin-User` IAM user

#### AWS Configuration:
- **AWS_REGION**: `eu-west-2`

### API Keys:
- **GEMINI_API_KEY**: Production Google Gemini API key

### Alternative: AWS IAM Roles (Recommended for Production)

Instead of using access keys, consider setting up OIDC with AWS IAM roles:

#### Staging Role:
- **AWS_STAGING_ROLE_ARN**: `arn:aws:iam::445567098699:role/GitHubActions-Staging-Role`

#### Production Role:
- **AWS_PRODUCTION_ROLE_ARN**: `arn:aws:iam::445567098699:role/GitHubActions-Production-Role`

## IAM Role Setup (If Using OIDC)

### 1. Create IAM Roles

Create two IAM roles in AWS Account `445567098699`:

```bash
# Staging role
aws iam create-role \
  --role-name GitHubActions-Staging-Role \
  --assume-role-policy-document file://staging-trust-policy.json

# Production role  
aws iam create-role \
  --role-name GitHubActions-Production-Role \
  --assume-role-policy-document file://production-trust-policy.json
```

### 2. Trust Policy for Staging

Create `staging-trust-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::445567098699:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:7-central/security-design-assistant:ref:refs/heads/develop"
        }
      }
    }
  ]
}
```

### 3. Trust Policy for Production

Create `production-trust-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::445567098699:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:7-central/security-design-assistant:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

### 4. Attach Policies to Roles

```bash
# Staging role permissions
aws iam attach-role-policy \
  --role-name GitHubActions-Staging-Role \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess

# Production role permissions (more restrictive recommended)
aws iam attach-role-policy \
  --role-name GitHubActions-Production-Role \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
```

## Setup Instructions

### Using Access Keys (Simpler):

1. Navigate to: `https://github.com/7-central/security-design-assistant/settings/secrets/actions`
2. Add the following secrets:
   - `AWS_ACCESS_KEY_ID` (from lee-hayton IAM user)
   - `AWS_SECRET_ACCESS_KEY` (from lee-hayton IAM user) 
   - `AWS_REGION` = `eu-west-2`
   - `GEMINI_API_KEY` (production API key)

3. Update workflows to use access keys instead of role assumption:
   ```yaml
   - name: Configure AWS credentials
     uses: aws-actions/configure-aws-credentials@v4
     with:
       aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
       aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
       aws-region: ${{ secrets.AWS_REGION }}
   ```

### Using IAM Roles (More Secure):

1. Set up OIDC provider in AWS account
2. Create IAM roles with trust policies
3. Add role ARNs as secrets in GitHub
4. Workflows already configured to use role assumption

## Security Best Practices

1. **Rotate secrets regularly**: Set calendar reminders to rotate AWS access keys every 90 days
2. **Use least privilege**: Consider creating custom policies instead of AdministratorAccess for production
3. **Monitor usage**: Enable CloudTrail logging to monitor API usage from GitHub Actions
4. **Environment separation**: Use different IAM roles/users for staging vs production

## Verification

After setting up secrets, verify they work by:

1. Pushing a change to `develop` branch to trigger staging deployment
2. Check GitHub Actions logs for successful authentication
3. Verify AWS resources are created in `eu-west-2` region
4. Test staging deployment health checks

## Troubleshooting

### Common Issues:

1. **Permission Denied**: Check IAM user/role has required permissions
2. **Region Mismatch**: Ensure all resources use `eu-west-2` region
3. **Invalid Credentials**: Verify access keys are correctly copied
4. **Role Assumption Failed**: Check trust policy and OIDC provider setup

### Debug Commands:

```bash
# Test credentials locally
aws sts get-caller-identity --profile design-lee

# Check S3 bucket access
aws s3 ls s3://security-assistant-sam-deployments --profile design-lee

# Validate SAM template
sam validate --template-file infrastructure/template.yaml
```

## Next Steps

After configuring secrets:
1. Test staging deployment pipeline
2. Verify monitoring and alerting
3. Execute production deployment with approval
4. Document any lessons learned