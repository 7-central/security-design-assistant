# Lambda Layer Dependencies

This layer contains shared dependencies for all Lambda functions in the Security Design Assistant project.

## Purpose

Lambda layers help reduce the deployment package size and allow for faster deployments by sharing common dependencies across multiple Lambda functions.

## Contents

- Core Python dependencies required by all Lambda functions
- AI/ML libraries (Google GenAI)
- AWS SDK libraries
- HTTP client libraries
- PDF and image processing libraries

## Building the Layer

The layer is automatically built during SAM deployment. The build process:

1. Installs dependencies from `layer/requirements.txt`
2. Packages them in the correct directory structure (`python/`)
3. Creates a deployable layer artifact

## Layer Structure

```
layer/
├── requirements.txt    # Dependencies to install
├── python/            # Python packages (auto-generated)
│   ├── google/
│   ├── httpx/
│   ├── boto3/
│   └── ...
└── README.md          # This file
```

## Usage in Lambda Functions

Lambda functions automatically have access to layer dependencies through the Python path. No special imports required.

```python
# These imports work automatically with the layer
from google import genai
import httpx
import boto3
from pypdf import PdfReader
```

## Layer Versioning Strategy

- **Development**: Layer is rebuilt on every deployment
- **Staging**: Layer version is pinned after validation
- **Production**: Layer version is explicitly controlled and tested

## Size Optimization

The layer build process automatically:

- Removes `.pyc` files and `__pycache__` directories
- Excludes test files and documentation
- Strips debug symbols where possible
- Compresses the final artifact

## Dependencies Included

| Package | Version | Purpose |
|---------|---------|---------|
| google-genai | 0.2.0 | AI model integration |
| httpx | 0.26.0 | Async HTTP client |
| Pillow | 10.2.0 | Image processing |
| pypdf | 4.2.0 | PDF text extraction |
| openpyxl | 3.1.2 | Excel file generation |
| boto3 | 1.34.0+ | AWS SDK |
| python-dotenv | 1.0.1 | Environment variables |
| pydantic | 2.5.0+ | Data validation |

## Best Practices

1. **Keep it lean**: Only include dependencies used by multiple functions
2. **Version pinning**: Use specific versions for reproducible builds  
3. **Regular updates**: Keep dependencies updated for security
4. **Size monitoring**: Monitor layer size to stay within AWS limits (250MB unzipped)

## Troubleshooting

### Layer too large
- Remove unused dependencies
- Use slim/minimal package versions where available
- Consider splitting into multiple layers

### Import errors
- Verify package is listed in `layer/requirements.txt`
- Check Python version compatibility (3.11)
- Ensure layer is properly attached to Lambda function

### Performance issues
- Layer extraction adds cold start time
- Consider moving heavy dependencies to container images for very large packages