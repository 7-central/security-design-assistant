# Epic 1: Minimal Working Pipeline

> ⚠️ **Timeline Update**: Extended from 2 weeks to 3 weeks due to critical SDK migration requirement (Story 0.1)

**Goal**: Establish a basic end-to-end pipeline that can process a security drawing PDF and generate an Excel schedule, proving the core concept works even with limited accuracy. This epic focuses on delivering immediate value by creating a simple but functional system that processes drawings and outputs schedules.

## Timeline Impact

**Original Timeline**: 2 weeks (42 story points)  
**Revised Timeline**: 3 weeks (82 story points including Story 0.1)  
**Added**: Story 0.1 - Google GenAI SDK Migration (40 points) - MUST complete first

## Story 0.1: URGENT - Google GenAI SDK Migration (BLOCKING)

**Priority**: HIGHEST - Must complete before any other development

**As a** system architect,  
**I want** to migrate from the deprecated Vertex AI SDK to Google's new GenAI SDK,  
**So that** we align with Google's current best practices and unlock enhanced capabilities.

**Acceptance Criteria:**
1. Remove all `google-cloud-aiplatform` dependencies
2. Add `google-genai` SDK with proper version pinning
3. Update environment configuration (remove old vars, add GEMINI_API_KEY)
4. Migrate all AI agents to new SDK patterns
5. Update error handling for new SDK
6. Implement native PDF processing
7. All tests passing with new implementation
8. Re-record VCR.py cassettes
9. Update all documentation
10. Verify cost reduction (min 25%)

**Story Points**: 40 (1 week, full team effort)

## Story 1.1: Project Setup and Basic API

**As a** developer,  
**I want** to set up the project structure with a basic REST API,  
**so that** we have a foundation for receiving drawing processing requests.

**Acceptance Criteria:**
1. Python project initialized with FastAPI framework and folder structure (api/, agents/, utils/, tests/)
2. Create initial README.md with:
   - Project overview and purpose
   - Development setup instructions
   - Environment variable requirements
   - Basic troubleshooting section
3. Create documentation skeleton structure:
   - docs/setup/README.md (placeholder)
   - docs/api/README.md (placeholder)
   - docs/deployment/README.md (placeholder)
   - docs/troubleshooting/README.md (placeholder)
4. Single POST endpoint `/process-drawing` that accepts multipart/form-data with PDF file
5. Request validation: Return 400 for non-PDF files, 413 for files >100MB, 422 for missing file
6. Health check endpoint `/health` returns JSON: `{"status": "healthy", "version": "1.0.0"}`
7. Create output directory structure (`./output/`) with write permissions verified
8. Environment configuration supports `STORAGE_MODE=local` and `LOCAL_OUTPUT_DIR`
9. Error handling returns: 400 (bad request), 413 (file too large), 500 (server error)
10. Endpoint returns: `{"job_id": "job_<timestamp>", "status": "processing"}`

## Story 1.2: PDF Processing Foundation

**As a** system,  
**I want** to handle both genuine and scanned PDF files,  
**so that** I can extract content regardless of PDF type.

**Acceptance Criteria:**
1. Prerequisites documented: Install poppler-utils for pdf2image functionality
2. Detect PDF type using PyPDF2, return 'genuine' or 'scanned' classification
3. For genuine PDFs: Extract text in format `{page: 1, text: "...", dimensions: {width: X, height: Y}}`
4. For scanned PDFs: Convert to PNG images at 300 DPI using pdf2image
5. Support page sizes: A0 (841×1189mm), A1 (594×841mm), and detect custom dimensions
6. Log PDF properties: `{type: "genuine|scanned", pages: N, dimensions: [...]}` 
7. Error handling: Return specific errors for corrupted PDFs, password-protected files
8. Store extracted data in memory structure: `{pages: [{page_num: 1, content: ...}]}`

## Story 1.3: Gemini Integration for Drawing Analysis

**As a** system,  
**I want** to analyze security drawings using Gemini AI,  
**so that** I can identify access control components.

**Acceptance Criteria:**
1. Prerequisites verified: GOOGLE_APPLICATION_CREDENTIALS configured, Gemini 2.5 Pro accessible
2. Vertex AI client initialized with retry configuration (3 attempts, exponential backoff)
3. Multimodal prompt includes: component list (readers, exit buttons), A-XXX-BB-B2 pattern, page context
4. Process pages individually if total tokens exceed 50% of model limit
5. Extract components matching schema: `{pages: [{page_num: int, components: [{id: str, type: str, location: str, confidence: float}]}]}`
6. Handle specific errors: AuthError (fail fast), RateLimitError (retry), TokenLimitError (split request)
7. Return structured JSON with all found components and metadata
8. Log per request: `{tokens_used: N, estimated_cost: $X.XX, processing_time_ms: N}`

## Story 1.4: Excel Schedule Generation

**As a** system,  
**I want** to generate an Excel schedule from extracted components,  
**so that** users receive output in their required format.

**Acceptance Criteria:**
1. Use Gemini's code execution with openpyxl to generate Excel file
2. Create Excel with columns: Door ID | Location | Reader E/KP | EBG | Outputs | Lock Type (11-22)
3. Map each component to appropriate row with door ID as primary key
4. Include quantity summary row: Total Doors | Total Readers | Total Exit Buttons
5. Apply basic formatting: Headers bold, borders on data cells, autofit columns
6. Save file as: `./output/job_<id>/schedule_<timestamp>.xlsx`
7. Handle generation errors: Return partial schedule if some components fail
8. API response includes: `{job_id: str, status: "completed", file_path: str, summary: {doors_found: N, processing_time_seconds: N}}`

## Story 1.5: End-to-End Testing

**As a** developer,  
**I want** to test the complete pipeline with the example drawing,  
**so that** we can verify the system works end-to-end.

**Acceptance Criteria:**
1. Test fixtures include: Example B2 drawing PDF and baseline schedule in test/fixtures/
2. Automated test script: `test_e2e.py` processes example drawing via API
3. Verify API returns 200 with job_id within 2 seconds
4. Confirm Excel file generated at expected path within 10 minutes
5. Automated validation: Excel contains >0 rows with door IDs matching A-XXX-BB-B2 pattern
6. Accuracy measurement: Count doors found vs baseline (e.g., "Found 30 of 45 doors = 67%")
7. Performance check: Total processing time <10 minutes logged
8. Error scenarios tested: Corrupted PDF returns 400, missing file returns 422
