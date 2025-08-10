# Data Models

## Job

**Purpose:** Tracks drawing processing requests through the system lifecycle with multi-client organization

**Key Attributes:**
- company#client#job: string - Composite primary key (e.g., "7central#st_marys#job_123")
- company_id: string - Company identifier (Phase 1: always "7central")
- client_name: string - Client/customer name (e.g., "St. Mary's Hospital")
- project_name: string - Specific project (e.g., "Emergency Wing Expansion")
- job_id: string - Unique identifier (format: job_<timestamp>)
- status: enum - Current processing state (queued, processing, completed, failed)
- created_at: datetime - Job submission timestamp
- updated_at: datetime - Last status change timestamp
- input_file_key: string - S3 key for uploaded drawing PDF
- context_file_key: string (optional) - S3 key for context document
- output_files: object - S3 keys for generated files (excel, evaluation)
- error: object (optional) - Error details if job failed
- metadata: object - Drawing info including project details
- ttl: number - DynamoDB TTL for automatic cleanup (30 days)

**Relationships:**
- Has many Checkpoints (one per processing stage)
- Has many ProcessingEvents (audit trail)
- Organized by company → client → project hierarchy

## Checkpoint

**Purpose:** Enables recovery and modification workflows by saving intermediate processing state

**Key Attributes:**
- checkpoint_id: string - Format: {job_id}_{stage}_{version}
- job_id: string - Parent job reference
- stage: enum - Processing stage (context_extracted, components_extracted, excel_generated)
- version: integer - Increments for modifications
- timestamp: datetime - When checkpoint was created
- data_key: string - S3 key for checkpoint data (JSON)
- data_hash: string - SHA256 for change detection
- confidence_scores: object - Per-component confidence mappings

**Relationships:**
- Belongs to Job
- Versioned for modification history

## Component

**Purpose:** Represents extracted security components from drawings (stored in checkpoint JSON with flexible schema)

**Key Attributes:**
- id: string - Component identifier (e.g., A-101-DR-B2)
- type: enum - Component type (door, reader, exit_button, lock)
- location: string - Descriptive location on drawing
- page_number: integer - Source page in PDF
- confidence: float - Extraction confidence (0.0-1.0)
- attributes: object - Flexible, project-specific properties
- reasoning: string - AI explanation for identification

**Dynamic Schema Example:**
```json
// Project A might have:
{
  "id": "A-101-DR-B2",
  "attributes": {
    "lock_type": "11",
    "card_reader": "A-101-RDR-P",
    "intercom": true
  }
}

// Project B might have:
{
  "id": "A-201-DR-B1",
  "attributes": {
    "lock_type": "12",
    "keypad": "A-201-KPD",
    "motion_sensor": "A-201-MOT"
  }
}
```

**Relationships:**
- Grouped by door_id for equipment association
- JSON structure enables project-specific Excel generation

## ProcessingEvent

**Purpose:** Audit trail for debugging and performance analysis

**Key Attributes:**
- event_id: string - Unique identifier
- job_id: string - Parent job reference
- timestamp: datetime - When event occurred
- event_type: enum - (job_created, agent_started, agent_completed, error_occurred)
- agent_name: string (optional) - Which agent generated event
- duration_ms: integer (optional) - Processing time
- token_usage: object (optional) - AI token consumption
- details: object - Event-specific data

**Relationships:**
- Belongs to Job
- Time-ordered sequence

## Data Storage Strategy

**DynamoDB - Job Metadata & Status:**
- Quick lookups by company/client/job
- Real-time status updates
- Small, frequently accessed data
- Query patterns: by client, by status, by date range

**S3 - Files & Component Data:**
```
/company_id/client_name/project_name/job_id/
  ├── drawing.pdf           # Original upload
  ├── context.docx          # Optional context
  ├── checkpoint_context_v1.json
  ├── checkpoint_components_v1.json  # Flexible schema per project
  ├── schedule_v1.xlsx      # Generated output
  └── evaluation.json       # AI judge results
```

**Key Design Decision:** Components stored as JSON in S3 (not DynamoDB) because:
- No fixed schema - each project has different component attributes
- Read all at once for Excel generation (no need for queries)
- Can be large (100+ components with detailed attributes)
- Enables dynamic Excel column generation by Gemini

## Future Expansion Path

**Phase 1 (Current):**
- company_id: Always "7central"
- Single business model

**Phase 2+ (White Label):**
- Add tenant layer if needed: `tenant_id/company_id/client_name/`
- Minimal code changes required
- Data already organized correctly
