# REST API Spec

```yaml
openapi: 3.0.0
info:
  title: Security Design Assistant API
  version: 1.0.0
  description: API for processing security drawings and generating equipment schedules
servers:
  - url: https://api.security-assistant.7central.com
    description: Production server
  - url: http://localhost:8000
    description: Local development

paths:
  /health:
    get:
      summary: Health check endpoint
      responses:
        '200':
          description: Service is healthy
          content:
            application/json:
              schema:
                type: object
                properties:
                  status:
                    type: string
                    example: healthy
                  version:
                    type: string
                    example: 1.0.0

  /process-drawing:
    post:
      summary: Submit drawing for processing
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              required:
                - drawing_file
                - client_name
                - project_name
              properties:
                drawing_file:
                  type: string
                  format: binary
                  description: PDF drawing file (max 100MB)
                context_file:
                  type: string
                  format: binary
                  description: Optional context document (DOCX/PDF/TXT)
                client_name:
                  type: string
                  example: "St. Mary's Hospital"
                project_name:
                  type: string
                  example: "Emergency Wing Expansion"
                pipeline:
                  type: string
                  enum: [full_analysis, no_context, extract_only]
                  default: full_analysis
                  description: Processing pipeline to use (future feature)
      responses:
        '202':
          description: Job accepted for processing
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobCreatedResponse'
        '400':
          $ref: '#/components/responses/BadRequest'
        '413':
          description: File too large
        '422':
          description: Invalid file format

  /status/{job_id}:
    get:
      summary: Check job processing status
      parameters:
        - name: job_id
          in: path
          required: true
          schema:
            type: string
            example: job_1734567890
      responses:
        '200':
          description: Job status
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobStatusResponse'
        '404':
          description: Job not found

  /download/{job_id}/{file_type}:
    get:
      summary: Download processed files
      parameters:
        - name: job_id
          in: path
          required: true
          schema:
            type: string
        - name: file_type
          in: path
          required: true
          schema:
            type: string
            enum: [excel, components, evaluation]
      responses:
        '302':
          description: Redirect to S3 presigned URL
          headers:
            Location:
              schema:
                type: string
                format: uri
        '404':
          description: File not found
        '423':
          description: Job still processing

components:
  schemas:
    JobCreatedResponse:
      type: object
      properties:
        job_id:
          type: string
          example: job_1734567890
        status:
          type: string
          enum: [queued]
        estimated_time_seconds:
          type: integer
          example: 300

    JobStatusResponse:
      type: object
      properties:
        job_id:
          type: string
        status:
          type: string
          enum: [queued, processing, completed, failed]
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time
        client_name:
          type: string
        project_name:
          type: string
        progress:
          type: object
          properties:
            stages_completed:
              type: array
              items:
                type: string
            current_stage:
              type: string
        files:
          type: object
          properties:
            excel:
              type: string
              description: URL path for Excel download
            components:
              type: string
              description: URL path for components JSON
            evaluation:
              type: string
              description: URL path for evaluation report
        summary:
          type: object
          properties:
            doors_found:
              type: integer
            processing_time_seconds:
              type: integer
            confidence:
              type: number
        error:
          type: object
          properties:
            message:
              type: string
            stage:
              type: string
            details:
              type: object

  responses:
    BadRequest:
      description: Invalid request
      content:
        application/json:
          schema:
            type: object
            properties:
              error:
                type: string
              details:
                type: object
```
