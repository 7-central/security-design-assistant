# Epic 2: Accuracy & Context Enhancement

**Goal**: Enhance the basic pipeline to achieve the target accuracy by adding context processing capabilities, implementing an AI judge for accuracy measurement, and optimizing prompts. This epic transforms the proof-of-concept into a reliable system that meets business accuracy requirements.

## Story 2.1: Context Processing Framework

**As a** system,  
**I want** to process context from multiple sources (DOCX, PDF, text),  
**so that** I can use project-specific information to improve drawing interpretation.

**Acceptance Criteria:**
1. Update `/process-drawing` endpoint to accept optional context parameter (file or text)
2. Context classifier identifies type: `{type: "docx"|"pdf"|"text", format: "file"|"string"}`
3. DOCX processing: Extract text using python-docx, preserve section headings and tables
4. PDF context: Use Gemini Flash multimodal to extract structured content
5. Text context: Parse directly into structured format
6. All context converted to schema: `{sections: [{title: str, content: str, type: "specification"|"general"}]}`
7. Context agent uses Gemini Flash for cost-efficient processing
8. Error handling: Gracefully continue without context if processing fails
9. Log context processing: `{type: str, sections_found: N, tokens_used: N}`

## Story 2.2: Enhanced Drawing Analysis with Context

**As a** system,  
**I want** to use context information to improve component identification,  
**so that** I can achieve higher accuracy in schedule generation.

**Acceptance Criteria:**
1. Modify Gemini Pro prompt to include context sections with drawing
2. Context injection format: "Project specifications: [relevant sections]"
3. Implement smart context selection: Only include sections mentioning door types, lock types, or hardware
4. Add reasoning to prompt: "Explain why each component was identified"
5. Enhanced output schema includes: `{id: str, type: str, confidence: float, reasoning: str}`
6. Handle context conflicts: When spec disagrees with drawing, note in reasoning
7. Measure accuracy improvement: Process test drawing with and without context
8. Target: Achieve 75-80% accuracy with context (up from 67% baseline)

## Story 2.3: AI Judge Implementation (Simplified)

**As a** system,  
**I want** to semantically evaluate extraction quality using an AI judge,  
**so that** I can understand how well the pipeline performed and identify improvement areas.

**Acceptance Criteria:**
1. Create AI judge agent that receives: Original drawing, context used, schedule agent's JSON response, generated Excel file
2. Judge prompt explains pipeline scope: "This system extracts access control components from security drawings"
3. Judge evaluates using consistent question framework:
   - **Completeness**: "Looking at the drawing, are there obvious access control components that were missed?"
   - **Correctness**: "Are the extracted components correctly identified and classified?"
   - **Context Usage**: "Did the system appropriately use the provided context to enhance extraction?"
   - **Spatial Understanding**: "Are components correctly associated (e.g., readers with doors)?"
   - **False Positives**: "Are there any components in the schedule that don't appear in the drawing?"
4. Judge output format:
   ```json
   {
     "overall_assessment": "Good/Fair/Poor performance with clear reasoning",
     "completeness": "Found most doors in main areas, missed emergency exits on east side",
     "correctness": "Door IDs accurate, some confusion between readers and exit buttons",
     "context_usage": "Successfully applied lock type specifications from context",
     "spatial_understanding": "Generally good, but struggled with overlapping annotations",
     "false_positives": "None detected",
     "improvement_suggestions": [
       "Focus on emergency exit door patterns",
       "Clarify distinction between reader types P and E"
     ]
   }
   ```
5. Judge maintains consistency by always addressing all evaluation questions
6. Run judge after each test to track improvement trends
7. Log judge assessments for pattern analysis over time

## Story 2.4: Prompt Optimization Sprint

**As a** developer,  
**I want** to iteratively improve prompts based on judge feedback,  
**so that** I can reach the target accuracy.

**Acceptance Criteria:**
1. Create prompt versioning system
2. After each judge evaluation, identify top 2 improvement suggestions
3. Implement prompt changes addressing judge feedback
4. Test iterations: Run drawing → Get judge feedback → Adjust → Repeat
5. Track progression: "v1: Fair (missed exits) → v2: Good (found exits, confused readers) → v3: Good (all issues addressed)"
6. Success criteria: 3 consecutive "Good" assessments with minor issues only
7. Document what prompt changes led to improvements

## Story 2.5: Validation Suite

**As a** QA engineer,  
**I want** a comprehensive test suite for accuracy measurement,  
**so that** I can ensure consistent performance.

**Acceptance Criteria:**
1. Create test set: Original B2 drawing + 5-10 variations
2. Run each through pipeline and judge evaluation
3. Compile judge assessments into overall report:
   ```
   Test Summary:
   - 8 of 10 drawings rated "Good"
   - 2 drawings rated "Fair" (complex multi-level, unusual symbols)
   - Common strengths: Door ID extraction, lock type mapping
   - Common weaknesses: Emergency exits, overlapping annotations
   - Context significantly helps with: Lock type selection, hardware associations
   ```
4. Identify drawing types that challenge the system
5. Document patterns: "System performs well on standard layouts, struggles with dense annotations"
6. Success criteria: Majority of test drawings receive "Good" assessment
7. Create recommendations for drawing types to prioritize in future development
