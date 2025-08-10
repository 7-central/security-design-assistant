# External APIs

## ✅ UPDATE: Google GenAI SDK Migration Complete

**Status**: Migration from Vertex AI SDK to Google GenAI SDK was **COMPLETED** in Story 0.1.  
**Migration Details**: See [gemini-sdk-migration-plan.md](./gemini-sdk-migration-plan.md)

## Google Gemini API (Current Architecture - Implemented)

- **Purpose:** AI-powered document analysis, component extraction, code generation, and quality evaluation
- **Documentation:** https://ai.google.dev/gemini-api/docs
- **SDK:** `google-genai` (NOT `google-cloud-aiplatform`)
- **Authentication:** API Key via GEMINI_API_KEY environment variable
- **Rate Limits:** 
  - Gemini Flash: 1000 requests/minute
  - Gemini Pro: 60 requests/minute
  - Token limits: 1,048,576 input / 65,536 output

**Key Features:**
- Native PDF support (up to 1,000 pages, 2GB)
- File API for persistent uploads
- Context caching for cost reduction (75% savings)
- Batch processing (50% cost reduction)
- Code execution capability for dynamic content generation
- Simplified error handling

**Code Execution Feature (Validated in Story 1.4):**
- **Purpose:** Generate executable Python code for Excel file creation
- **Model:** gemini-2.5-flash (stable, supports code execution)
- **Libraries Available:** openpyxl, pandas, numpy, matplotlib, and 30+ others
- **Limitations:** 30-second execution timeout, 2MB file input limit
- **Output:** Base64-encoded files returned in execution results
- **Configuration:** `types.Tool(code_execution=types.ToolCodeExecution())`

**Integration Notes:** 
- Use Gemini 2.5 Flash for context processing ($0.075/1M input tokens)
- Use Gemini 2.5 Flash for Excel generation with code execution (same pricing)
- Use Gemini 2.5 Pro for drawing analysis ($1.25/1M input tokens with caching)
- Direct PDF upload without manual conversion
- 48-hour automatic file retention
- Each PDF page = 258 tokens
- No additional cost for code execution feature

## Google Vertex AI / Gemini API (Legacy - Removed)

✅ **REMOVED**: This implementation was successfully migrated to Google GenAI SDK in Story 0.1.

- **Purpose:** AI-powered document analysis (current implementation)
- **Documentation:** https://cloud.google.com/vertex-ai/docs
- **Base URL(s):** https://{region}-aiplatform.googleapis.com
- **Authentication:** Service account JSON key via GOOGLE_APPLICATION_CREDENTIALS
- **Issues:**
  - Complex authentication setup
  - Manual PDF-to-image conversion required
  - Missing cost optimization features
  - Not aligned with Google's current documentation

## AWS Services (Internal APIs)

While not external APIs, these AWS services are accessed via boto3 SDK:

- **S3:** Object storage for files
- **DynamoDB:** NoSQL database for job metadata
- **SQS:** Message queue for async processing
- **CloudWatch:** Logging and metrics

**Note:** No other external APIs are required for Phase 1. Future phases may integrate with:
- AutoCAD web services (for native DWG support)
- Microsoft Graph API (for direct Excel integration)
- Authentication providers (for multi-tenant support)
