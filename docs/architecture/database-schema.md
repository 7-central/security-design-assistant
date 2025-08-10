# Database Schema

## DynamoDB Tables

### Jobs Table
```
Table Name: security-assistant-jobs
Partition Key: company#client#job (String)
No Sort Key

Attributes:
{
  "company#client#job": "7central#st_marys#job_1734567890",
  "company_id": "7central",
  "client_name": "St. Mary's Hospital", 
  "project_name": "Emergency Wing Expansion",
  "job_id": "job_1734567890",
  "status": "completed",  // queued|processing|completed|failed
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T10:15:32Z",
  "input_files": {
    "drawing": "7central/st_marys/emergency_wing/job_1734567890/drawing.pdf",
    "context": "7central/st_marys/emergency_wing/job_1734567890/context.docx"
  },
  "checkpoints": {
    "context_extracted": {
      "timestamp": "2024-01-15T10:02:15Z",
      "data_key": "7central/st_marys/emergency_wing/job_1734567890/checkpoint_context_v1.json",
      "version": 1
    },
    "components_extracted": {
      "timestamp": "2024-01-15T10:08:45Z",
      "data_key": "7central/st_marys/emergency_wing/job_1734567890/checkpoint_components_v1.json",
      "version": 1,
      "summary": {
        "total_components": 45,
        "by_type": {
          "door": 45,
          "reader": 42,
          "exit_button": 38
        }
      }
    }
  },
  "output_files": {
    "excel": "7central/st_marys/emergency_wing/job_1734567890/schedule_v1.xlsx",
    "evaluation": "7central/st_marys/emergency_wing/job_1734567890/evaluation.json"
  },
  "metadata": {
    "file_name": "Building_A_Level_2_Security.pdf",
    "file_size_mb": 24.5,
    "total_pages": 15,
    "pdf_type": "scanned",
    "processing_time_seconds": 932,
    "token_usage": {
      "total": 53500,
      "by_agent": {
        "context": 2500,
        "schedule": 45000,
        "codegen": 3000,
        "judge": 3000
      }
    }
  },
  "error": null,  // Or error details if failed
  "ttl": 1739751890  // Unix timestamp for 30-day auto-deletion
}

Global Secondary Indexes:

GSI1: StatusDateIndex
- Partition Key: status (String)
- Sort Key: created_at (String)
- Purpose: Query all jobs by status, sorted by date
- Example: Get all "completed" jobs from newest to oldest

GSI2: ClientProjectIndex  
- Partition Key: client_name (String)
- Sort Key: created_at (String)
- Purpose: Query all jobs for a specific client
- Example: Show all jobs for "St. Mary's Hospital"

GSI3: DateRangeIndex
- Partition Key: date_bucket (String, format: "2024-01")
- Sort Key: created_at (String)
- Purpose: Query jobs within date ranges for reporting
- Example: Get all jobs from January 2024
```

### ProcessingEvents Table (Optional for Phase 1)
```
Table Name: security-assistant-events
Partition Key: job_id (String)
Sort Key: timestamp#event_id (String)

Attributes:
{
  "job_id": "job_1734567890",
  "timestamp#event_id": "2024-01-15T10:00:00.123Z#evt_abc123",
  "event_type": "job_created",  // job_created|agent_started|agent_completed|error_occurred
  "agent_name": "schedule_agent",  // If applicable
  "duration_ms": 8432,
  "details": {
    "message": "Successfully extracted 45 components",
    "token_usage": 45000,
    "pages_processed": 15
  }
}

Purpose: Detailed audit trail for debugging and performance analysis
TTL: 7 days (shorter retention than jobs)
```

## S3 Bucket Structure
```
security-assistant-files/
├── 7central/                          # company_id
│   ├── st_marys_hospital/            # client_name (normalized)
│   │   ├── emergency_wing/           # project_name (normalized)
│   │   │   ├── job_1734567890/
│   │   │   │   ├── drawing.pdf
│   │   │   │   ├── context.docx
│   │   │   │   ├── checkpoint_context_v1.json
│   │   │   │   ├── checkpoint_components_v1.json
│   │   │   │   ├── schedule_v1.xlsx
│   │   │   │   └── evaluation.json
│   │   │   └── job_1734567891/
│   │   └── main_building/
│   └── tech_campus/
└── _temp/                            # For upload staging

Bucket Policies:
- Lifecycle: Move to Intelligent Tiering immediately
- Expiration: Delete objects after 90 days
- Versioning: Disabled (we handle versions in file names)
- Encryption: SSE-S3 (server-side encryption)
```

## Local Development Storage
```
local_output/
├── jobs.json                         # Replaces DynamoDB
├── 7central/
│   └── [same structure as S3]

Example jobs.json:
{
  "7central#st_marys#job_123": {
    // Same schema as DynamoDB
  },
  "7central#tech_campus#job_456": {
    // Another job
  }
}
```
