# Deployment Documentation

This section will contain deployment guides for the Security Design Assistant.

## Topics to be covered:

- AWS deployment with SAM
- Environment configuration
- CI/CD pipeline setup
- Monitoring and logging
- Scaling considerations

## Environment Configuration

### Required Environment Variables

- `STORAGE_MODE`: Set to "local" for development or "aws" for production
- `LOCAL_OUTPUT_DIR`: Directory for local file storage (default: ./local_output)
- `GEMINI_API_KEY`: Your Google GenAI API key (obtain from https://aistudio.google.com/app/apikey)

### Deprecated Environment Variables (DO NOT USE)

The following variables were used with the old Vertex AI SDK and should be removed:
- ~~`GOOGLE_APPLICATION_CREDENTIALS`~~
- ~~`VERTEX_AI_PROJECT_ID`~~
- ~~`VERTEX_AI_LOCATION`~~