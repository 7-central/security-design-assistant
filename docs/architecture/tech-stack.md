# Tech Stack

> ✅ **UPDATE COMPLETE**: The AI Provider has been successfully migrated from `google-cloud-aiplatform` (Vertex AI) to `google-genai` SDK in Story 0.1. See [gemini-sdk-migration-plan.md](./gemini-sdk-migration-plan.md) for migration details.

## Cloud Infrastructure

- **Provider:** AWS (Amazon Web Services)
- **Key Services:** Lambda, API Gateway, SQS, DynamoDB, S3, CloudWatch
- **Deployment Regions:** us-east-1 (primary)

## Technology Stack Table

| Category | Technology | Version | Purpose | Rationale |
|----------|------------|---------|---------|-----------|
| **Language** | Python | 3.11 | Primary development language | Excellent AI/ML libraries, AWS Lambda support, team familiarity |
| **Runtime** | AWS Lambda | Python 3.11 | Serverless compute | Auto-scaling, pay-per-use, no infrastructure management |
| **API Framework** | FastAPI | 0.109.0 | REST API framework | Modern, fast, automatic OpenAPI docs, async support |
| **PDF Processing** | pypdf | 4.2.0 | Genuine PDF text extraction | Modern fork of PyPDF2, actively maintained, no deprecation warnings |
| **PDF to Image** | ~~pdf2image~~ | ~~1.17.0~~ | ~~Scanned PDF conversion~~ | **REMOVED** - Native PDF support in GenAI SDK |
| **Image Processing** | Pillow | 10.2.0 | Image manipulation | Industry standard, efficient memory usage |
| **AI Provider** | Google GenAI | 0.2.0 | AI/ML services | Gemini models, native PDF support, simplified auth |
| **AI Models** | Gemini 2.5 Flash | latest | Context processing & Excel generation | Cost-effective, supports code execution ($0.075/1M tokens) |
| **AI Models** | Gemini 2.5 Pro | latest | Drawing analysis & evaluation | Superior accuracy for complex analysis ($2.50/1M tokens) |
| **Excel Generation** | openpyxl | 3.1.2 | Excel file creation | Runs in Gemini code execution environment, full formatting support |
| **Queue Service** | AWS SQS | - | Async job processing | Managed service, automatic retries, DLQ support |
| **Database** | DynamoDB | - | Job status tracking | Serverless, auto-scaling, pay-per-request |
| **Storage** | AWS S3 | - | File storage | Durable, scalable, presigned URLs for security |
| **Monitoring** | CloudWatch | - | Logs and metrics | Native AWS integration, custom metrics support |
| **Testing** | pytest | 8.0.0 | Test framework | Industry standard, excellent plugins, simple syntax |
| **API Mocking** | ~~VCR.py~~ | ~~6.0.1~~ | ~~Record/replay HTTP~~ | **REMOVED** - Not needed with GenAI SDK |
| **HTTP Client** | httpx | 0.26.0 | Async HTTP requests | Modern, async support, connection pooling |
| **Environment** | python-dotenv | 1.0.1 | Environment management | Simple config management for local/prod |
| **IaC** | AWS SAM | 1.100+ | Infrastructure deployment only | Defines and deploys AWS resources (Lambda, SQS, etc.) to cloud |
| **Deployment** | GitHub Actions | - | CI/CD pipeline | Free for public repos, excellent AWS integration |
| **Code Quality** | ruff | 0.1.14 | Linting and formatting | Fast, comprehensive, replaces multiple tools |
| **Type Checking** | mypy | 1.8.0 | Static type checking | Catches errors early, improves code quality |

## Development Mode Clarification

**Local Development**: Uses file system mode with environment variables to simulate AWS services locally without any AWS dependencies. FastAPI runs with `uvicorn` and stores files locally.

**Production Deployment**: SAM templates define AWS infrastructure and deploy to cloud. The same code switches behavior based on `STORAGE_MODE` environment variable.
