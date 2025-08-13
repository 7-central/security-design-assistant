# Epic 3: Production Infrastructure (Serverless Architecture)

**Goal**: Transform the working prototype into a production-ready serverless system using AWS Lambda, SQS, and DynamoDB. This epic ensures the system can handle real-world usage reliably with automatic scaling and pay-per-use pricing.

## Story 3.1: Serverless Queue Implementation

**As a** system,  
**I want** to process drawing requests asynchronously through SQS and Lambda,  
**so that** the system automatically scales with demand and costs scale with usage.

**Acceptance Criteria:**
1. Create SQS queue with visibility timeout of 30 minutes (max Lambda duration)
2. Modify `/process-drawing` endpoint (Lambda function) to:
   - Generate job ID and save initial status to DynamoDB
   - Send message to SQS with job details
   - Return: `{"job_id": "job_<timestamp>", "status": "queued"}`
3. Create processor Lambda function triggered by SQS:
   - Batch size: 1 (one drawing per invocation)
   - Timeout: 15 minutes (Lambda max)
   - Memory: 3GB (for PDF processing)
4. DynamoDB table for job tracking:
   - Partition key: job_id
   - Attributes: status, created_at, updated_at, result, error
   - TTL: 30 days for automatic cleanup
5. Implement `/status/{job_id}` endpoint (separate Lambda) reading from DynamoDB
6. Dead Letter Queue (DLQ) for failed messages after 3 attempts
7. CloudWatch alarms for DLQ depth > 5 messages

## Story 3.2: Lambda-Optimized Error Handling

**As a** system,  
**I want** to handle failures gracefully within Lambda constraints,  
**so that** temporary issues don't cause job failures.

**Acceptance Criteria:**
1. Implement error handling adapted for Lambda:
   - SQS automatic retries: 3 attempts with exponential backoff
   - Gemini rate limits: Check response headers, delay next attempt
   - Lambda timeout approaching: Save progress to DynamoDB, fail gracefully
2. Partial progress tracking in DynamoDB:
   ```json
   {
     "job_id": "job_123",
     "status": "processing",
     "stages_completed": ["validation", "pdf_processing"],
     "current_stage": "drawing_analysis",
     "last_checkpoint": "2024-01-01T00:00:00Z"
   }
   ```
3. Lambda error response handling:
   - Timeout: Message returns to queue for retry
   - Memory exceeded: Increase memory allocation via environment variable
   - Unhandled exception: Log to CloudWatch, message to DLQ
4. Step Functions consideration for complex workflows:
   - If processing exceeds 15 minutes consistently
   - Break into multiple Lambda steps
   - Checkpoint between steps
5. API Gateway error responses properly formatted
6. DLQ processor Lambda: Sends alerts and logs failed job details

## Story 3.3: Serverless Monitoring

**As a** DevOps engineer,  
**I want** comprehensive monitoring using AWS native tools,  
**so that** I can identify issues without managing monitoring infrastructure.

**Acceptance Criteria:**
1. CloudWatch Logs with structured JSON logging:
   - Log group per Lambda function
   - Consistent format with correlation IDs
   - Log Insights queries for common searches
2. CloudWatch Metrics (custom):
   - Job processing duration by stage
   - Token usage and estimated costs
   - Success/failure rates
   - Queue depth over time
3. CloudWatch Dashboard displaying:
   - Lambda invocations and errors
   - SQS queue depth and message age
   - DynamoDB read/write capacity
   - API Gateway request counts and latency
   - Cost tracking by service
4. CloudWatch Health Monitoring Dashboard:
   - API request counts by endpoint
   - Error rates by error type (4xx, 5xx)
   - Processing time metrics (p50, p90, p99)
   - Queue depth visualization over time
   - Active jobs vs completed jobs
   - Gemini API token usage trends
5. CloudWatch Alarms for:
   - Lambda error rate > 10%
   - SQS message age > 20 minutes
   - DLQ messages present
   - Monthly cost projection > budget
6. X-Ray tracing enabled:
   - Full request flow visualization
   - Performance bottleneck identification
   - Service map showing dependencies
7. Cost anomaly detection configured
8. SNS notifications for critical alarms

## Story 3.4: AWS and GitHub Account Setup

**As a** DevOps engineer,  
**I want** properly configured AWS and GitHub accounts for the project,  
**so that** we can deploy and manage the Security Design Assistant infrastructure.

**Acceptance Criteria:**
1. AWS account configuration completed:
   - AWS CLI profile `design-lee` created using existing `lee-hayton` IAM user (Account: 445567098699, Region: eu-west-2)
   - AWS CLI profile `design` created using existing `7c-IAM-Admin-User` for CI/CD deployments
   - S3 deployment bucket `security-assistant-sam-deployments` created in eu-west-2
   - Cost tracking tags configured with Project=SecurityDesignAssistant
2. GitHub repository structure established:
   - 7-central GitHub account created (info@7central.co.uk)
   - Repository created: https://github.com/7-central/security-design-assistant
   - Repository configured with main/develop branches and proper settings
   - Lee uses junksamiad account locally with collaborator push access
3. Local development workflow configured:
   - Local git configured to push to 7-central/security-design-assistant repository
   - AWS CLI profiles `design-lee` and `design` working locally
   - SAM deployment tested successfully with security-assistant-sam-deployments bucket
4. Documentation created:
   - AWS account setup documented
   - GitHub repository structure documented
   - Local development workflow documented
   - Credentials and access management documented

## Story 3.5: Serverless Deployment

**As a** developer,  
**I want** infrastructure as code and automated deployments,  
**so that** we can reliably deploy the serverless architecture.

**Acceptance Criteria:**
1. AWS SAM template defining all resources:
   - Lambda functions with environment configs
   - SQS queues with DLQ
   - DynamoDB table with indexes
   - API Gateway with stages
   - IAM roles with least privilege
2. GitHub Actions workflow:
   - On PR: sam validate and cfn-lint
   - On merge to develop: Deploy to staging
   - On merge to main: Deploy to production
3. Environment configurations:
   - Dev: Lower Lambda memory, shorter timeouts
   - Staging: Production-like with test data
   - Prod: Full resources, monitoring enabled
4. SAM deployment features:
   - Gradual deployment with CloudWatch alarms
   - Automatic rollback on errors
   - Parameter store for sensitive configs
5. Lambda layers for dependencies:
   - Common libraries in shared layer
   - Reduces deployment package size
   - Version controlled
6. Pre-traffic and post-traffic hooks for validation
7. Deployment notifications via SNS/Slack

## Story 3.6: Serverless Optimization

**As a** system administrator,  
**I want** optimized Lambda performance and costs,  
**so that** we minimize cold starts and reduce expenses.

**Acceptance Criteria:**
1. Lambda optimization techniques:
   - Provisioned concurrency for API endpoints (2 instances)
   - ARM-based Graviton2 processors (20% cheaper)
   - Memory optimization based on CloudWatch insights
   - Connection pooling for DynamoDB
2. Cold start mitigation:
   - Keep dependencies minimal
   - Lazy loading for heavy libraries
   - Lambda warmer for critical functions
3. S3 optimization:
   - Intelligent tiering for stored files
   - Lifecycle rules: Delete after 30 days
   - Transfer acceleration for uploads
   - Presigned URLs expire after 1 hour
4. Cost optimization:
   - Lambda Power Tuning tool results applied
   - SQS long polling enabled
   - DynamoDB on-demand pricing
   - S3 request consolidation
5. Performance targets achieved:
   - API cold start < 1 second
   - Warm response < 200ms
   - Processing Lambda start < 5 seconds
6. Caching strategy:
   - API Gateway caching for status checks
   - Lambda environment variable for static configs
   - S3 metadata for processed file info
7. Reserved capacity planning based on usage patterns
