# Technical Assumptions

## Repository Structure: Monorepo
Monorepo structure to keep all components (API, queue workers, agents, utilities, testing framework) in a single repository with clear module boundaries.

## Service Architecture
**Queue-Based Asynchronous Pipeline with Multi-Agent Processing**:
- REST API endpoint accepts requests and queues them immediately
- Returns job ID for status checking (webhook support for completion)
- Queue workers process jobs through agent pipeline:
  1. **Context Agent** - Processes context based on type into AI-friendly JSON
  2. **Schedule Agent** - Analyzes drawing + context, outputs structured data
  3. **Code Generation Agent** - Creates Excel file using Gemini code execution
- Manual data obfuscation script as separate pre-processing utility
- All outputs saved to S3/storage with pre-signed URLs returned

## Testing Requirements
**Pragmatic Testing with Real Validation** - Unit tests for core utilities, real E2E tests with actual API calls for pipeline validation. Focus on consistency testing (same drawing 3x) and critical path validation with real-world feedback.

## Additional Technical Assumptions and Requests

**Architecture Patterns:**
- **Queue System**: AWS SQS for job management
- **Status Tracking**: Job status API endpoint (pending/processing/completed/failed)
- **File Storage**: S3 for input files and generated outputs
- **Response Format**: Structured JSON with file URLs and reasoning
  ```json
  {
    "job_id": "job_123",
    "status": "completed",
    "files": {
      "excel": "https://s3.../schedule_123.xlsx"  // or local path
    },
    "report": {
      "doors_found": 45,
      "confidence": 0.92,
      "reasoning": "Identified 45 access control points across 3 pages. Page 1 contained main entrance systems, Page 2 showed internal access points, Page 3 detailed emergency exits. Pages 4-6 were electrical drawings and were skipped.",
      "processing_details": {
        "total_pages": 6,
        "relevant_pages": [1, 2, 3],
        "skipped_pages": [4, 5, 6],
        "components_by_type": {
          "readers": 45,
          "exit_buttons": 38,
          "door_positions": 45,
          "lock_type_11": 23,
          "lock_type_12": 22
        }
      },
      "warnings": [
        "Page 5 appears to be electrical only, skipped",
        "Low confidence on 2 door identifiers due to overlapping text"
      ],
      "errors": []
    },
    "processing_time_seconds": 185
  }
  ```

**Language & Framework:**
- Python-based implementation
- FastAPI for REST API
- AWS Lambda for all processing (serverless-first)
- Boto3 for AWS integration
- PyPDF2 + pdf2image for scanned PDF handling

**PDF Processing Capabilities:**
- **Genuine PDFs**: Direct text/vector extraction
- **Scanned PDFs**: OCR pipeline using pdf2image → Gemini multimodal
- **Large Files**: Streaming processing, page-by-page analysis
- **Non-standard Sizes**: Support A0, A1, custom dimensions
- **Page Selection**: AI identifies relevant security pages, skips others

**AI/ML Stack:**
- Google Vertex AI/Gemini as primary provider
- **Context Tasks**: Gemini 2.5 Flash (cost optimization)
- **Drawing Analysis**: Gemini 2.5 Pro (accuracy critical)
- **Code Generation**: Gemini with built-in code execution
- **Prompt Engineering**: Explicit instruction for relevant page selection
- Model selection utility for easy switching

**Serverless Infrastructure (AWS):**
- API Gateway + Lambda for all endpoints
- SQS for asynchronous job queue
- DynamoDB for job status tracking
- S3 for file storage with lifecycle policies
- CloudWatch for monitoring and logging
- SAM (Serverless Application Model) for IaC

**Data Privacy & Google Policies:**
- **Retention**: 55 days for abuse monitoring (not used for training)
- **Caching**: Disable 24-hour cache for zero retention beyond monitoring
- **Configuration**: Project-level settings for data handling
- **Obfuscation**: Still required as data is retained for 55 days
- **Compliance**: Document this in privacy policy for clients

**Development & Deployment:**
- **Local Development**: 
  - SAM local for Lambda testing
  - LocalStack for AWS services
  - Environment variable for local vs S3 storage
- **CI/CD Pipeline**:
  - GitHub Actions for testing and deployment
  - SAM deploy for infrastructure
  - Environment promotion (dev→staging→prod)

## Future Architecture Considerations

**Flexible Pipeline System (Post-Phase 1):**
Based on architectural design insights, the system should support user-selectable processing pipelines to enable different use cases and pricing models.

**Single Agent Operations:**
- Extract Only - Just get components as JSON without Excel generation
- Excel from JSON - Generate Excel from previously extracted data
- Evaluate Schedule - Run judge on existing schedules
- Parse Context - Process specification documents independently

**Specialized Workflows:**
- Quick Validation - Skip Excel generation for rapid checks
- Door Count Only - Simple quantity reports
- Revision Compare - Diff analysis between drawing versions
- Custom Pipelines - User-defined agent sequences

**User Interface Options:**
- Dashboard with processing mode selection
- Cost/time estimates per pipeline option
- Chatbot interface for conversational pipeline selection
- API endpoints for each pipeline type

This modular pipeline approach enables:
- Different pricing tiers (basic extract vs full analysis)
- Debugging tools (run single agents)
- Custom workflows per client needs
- Gradual feature rollout without architectural changes
