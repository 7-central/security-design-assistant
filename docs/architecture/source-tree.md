# Source Tree

```
security-design-assistant/
├── .env.example                    # Environment variables template
├── .gitignore                      # Git ignore rules
├── README.md                       # Project documentation
├── requirements.txt                # Python dependencies
├── pytest.ini                      # Test configuration
├── pyproject.toml                  # Python project metadata
├── Makefile                        # Common commands
│
├── src/                            # Source code
│   ├── __init__.py
│   ├── api/                        # API layer
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI app entry point
│   │   ├── routes.py              # API route definitions
│   │   ├── models.py              # Pydantic request/response models
│   │   └── dependencies.py        # Dependency injection
│   │
│   ├── agents/                     # AI agents
│   │   ├── __init__.py
│   │   ├── base_agent_v2.py       # Abstract base agent class (V2)
│   │   ├── context_agent.py       # Context document processor
│   │   ├── schedule_agent_v2.py   # Drawing analyzer (V2)
│   │   ├── excel_generation_agent.py  # Excel generator using Gemini code execution
│   │   └── judge_agent.py         # Quality evaluator
│   │
│   ├── storage/                    # Storage abstraction
│   │   ├── __init__.py
│   │   ├── interface.py           # Abstract storage interface
│   │   ├── aws_storage.py         # S3 & DynamoDB implementation
│   │   └── local_storage.py       # File system implementation
│   │
│   ├── models/                     # Data models
│   │   ├── __init__.py
│   │   ├── job.py                 # Job data model
│   │   ├── checkpoint.py          # Checkpoint schemas
│   │   └── component.py           # Component schemas
│   │
│   ├── utils/                      # Utilities
│   │   ├── __init__.py
│   │   ├── pdf_processor.py       # PDF handling utilities
│   │   ├── validators.py          # Input validation
│   │   ├── id_generator.py        # Job ID generation
│   │   ├── name_normalizer.py     # Client/project name normalization
│   │   └── storage_manager.py     # Storage abstraction implementation
│   │
│   ├── config/                     # Configuration
│   │   ├── __init__.py
│   │   ├── settings.py            # Environment-based settings
│   │   ├── pipeline_config.py     # Pipeline definitions
│   │   └── prompts/               # AI prompts
│   │       ├── context_prompt.txt
│   │       ├── schedule_prompt.txt
│   │       └── judge_prompt.txt
│   │
│   └── lambda_handler.py          # AWS Lambda entry point
│
├── tests/                          # Test suite
│   ├── __init__.py
│   ├── conftest.py                # Pytest fixtures
│   ├── unit/                      # Unit tests (VCR enabled)
│   │   ├── test_agents/
│   │   ├── test_storage/
│   │   └── test_utils/
│   ├── integration/               # Integration tests (VCR enabled)
│   │   ├── test_pipeline.py
│   │   └── test_api.py
│   ├── evaluation/                # AI evaluation tests (no VCR)
│   │   ├── test_accuracy.py
│   │   └── test_consistency.py
│   └── fixtures/                  # Test data
│       ├── sample_drawing.pdf
│       ├── context.docx
│       └── cassettes/             # VCR recordings
│
├── infrastructure/                 # AWS infrastructure
│   ├── template.yaml              # SAM template
│   ├── samconfig.toml             # SAM configuration
│   └── buildspec.yml              # CodeBuild spec
│
├── scripts/                        # Utility scripts
│   ├── local_dev.sh              # Start local development
│   ├── run_tests.sh              # Run test suites
│   └── deploy.sh                 # Deploy to AWS
│
├── docs/                          # Documentation
│   ├── architecture.md           # This document
│   ├── prd.md                   # Product requirements
│   ├── api.md                   # API documentation
│   └── deployment.md            # Deployment guide
│
└── local_output/                  # Local development output (gitignored)
    ├── jobs.json
    └── 7central/
        └── [client folders]
```
