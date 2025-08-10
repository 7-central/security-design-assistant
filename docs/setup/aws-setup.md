# AWS Setup Documentation

## AWS Account Configuration

### Account Details
- **Account ID**: 445567098699
- **Primary Region**: eu-west-2 (Europe - London)
- **Business Structure**: 7Central Group → Security Design Business

### AWS CLI Profiles

Two profiles have been configured for the Security Design Assistant project:

#### 1. `design-lee` (Development Profile)
- **IAM User**: lee-hayton
- **Purpose**: Local development and testing
- **Permissions**: AdministratorAccess
- **Usage**: For developers working on the project locally

```bash
# Test profile access
aws sts get-caller-identity --profile design-lee

# Deploy with this profile
sam deploy --profile design-lee
```

#### 2. `design` (CI/CD Profile)
- **IAM User**: 7c-IAM-Admin-User
- **Purpose**: Automated deployments via GitHub Actions
- **Permissions**: AdministratorAccess
- **Usage**: For CI/CD pipelines and automated deployments

```bash
# Test profile access
aws sts get-caller-identity --profile design

# Deploy with this profile
sam deploy --profile design
```

### Profile Configuration

To set up these profiles on a new machine:

```bash
# Configure design-lee profile
aws configure --profile design-lee
# Enter:
# - AWS Access Key ID: [Your lee-hayton access key]
# - AWS Secret Access Key: [Your lee-hayton secret key]
# - Default region: eu-west-2
# - Default output format: json

# Configure design profile
aws configure --profile design
# Enter:
# - AWS Access Key ID: [7c-IAM-Admin-User access key]
# - AWS Secret Access Key: [7c-IAM-Admin-User secret key]
# - Default region: eu-west-2
# - Default output format: json
```

## S3 Deployment Bucket

### Bucket Configuration
- **Name**: `security-assistant-sam-deployments`
- **Region**: eu-west-2
- **Purpose**: Store SAM deployment artifacts
- **Versioning**: Enabled
- **Lifecycle Policy**: Delete old versions after 30 days

### Bucket Tags
- `Project`: SecurityDesignAssistant
- `ManagedBy`: SAM
- `Business`: Security
- `Environment`: Shared

### Access
Both `design-lee` and `design` profiles have full access to this bucket.

## IAM Users and Permissions

### lee-hayton (Personal Development)
- **Type**: Personal IAM user
- **Access Level**: AdministratorAccess
- **Used By**: design-lee profile
- **Purpose**: Individual developer access

### 7c-IAM-Admin-User (Service Account)
- **Type**: Service IAM user (shared across 7Central projects)
- **Access Level**: AdministratorAccess
- **Used By**: design profile
- **Purpose**: CI/CD and automated deployments

## Resource Naming Convention

All resources for the Security Design Assistant should follow these conventions:

- **Prefix**: `security-assistant-`
- **Environment Suffixes**:
  - Development: Local only (no AWS resources)
  - Staging: `security-assistant-staging-*`
  - Production: `security-assistant-prod-*`

## Required AWS Services

The following AWS services are used by the application:

- **Lambda**: Serverless compute for processing
- **API Gateway**: REST API endpoints
- **DynamoDB**: Job status and metadata storage
- **S3**: File storage for PDFs and outputs
- **SQS**: Asynchronous job processing queue
- **CloudWatch**: Logging and monitoring
- **CloudFormation**: Infrastructure as code (via SAM)

## Verification Commands

```bash
# Verify AWS CLI installation
aws --version

# Verify SAM CLI installation
sam --version

# Test design-lee profile
aws s3 ls --profile design-lee

# Test design profile
aws s3 ls --profile design

# Check deployment bucket
aws s3api get-bucket-versioning \
  --bucket security-assistant-sam-deployments \
  --profile design-lee

# List Lambda functions
aws lambda list-functions \
  --profile design-lee \
  --query 'Functions[?starts_with(FunctionName, `security-assistant`)].FunctionName'
```

## Troubleshooting

### Common Issues

1. **Access Denied Errors**
   - Verify profile is correctly configured: `aws configure list --profile design-lee`
   - Check IAM user status in AWS Console

2. **Region Mismatch**
   - Ensure all resources are in eu-west-2
   - Check profile region: `aws configure get region --profile design-lee`

3. **SAM Deployment Fails**
   - Verify S3 bucket exists and is accessible
   - Check CloudFormation stack status in AWS Console
   - Review CloudWatch logs for Lambda errors

## Security Best Practices

1. **Never commit AWS credentials** to version control
2. **Rotate access keys** regularly (every 90 days)
3. **Use MFA** for console access when possible
4. **Monitor CloudTrail** for unusual API activity
5. **Tag all resources** for cost tracking and organization

## Cost Management

- All resources should be tagged with `Project=SecurityDesignAssistant`
- Use AWS Cost Explorer to track project costs
- Set up billing alerts for unexpected charges
- Review and delete unused resources regularly

## Next Steps

After AWS setup is complete:
1. Configure GitHub repository and Actions
2. Set up local development environment
3. Deploy initial application stack
4. Configure monitoring and alerts