# Introduction

This document outlines the overall project architecture for Security Design Assistant, including backend systems, shared services, and non-UI specific concerns. Its primary goal is to serve as the guiding architectural blueprint for AI-driven development, ensuring consistency and adherence to chosen patterns and technologies.

**Relationship to Frontend Architecture:**
If the project includes a significant user interface, a separate Frontend Architecture Document will detail the frontend-specific design and MUST be used in conjunction with this document. Core technology stack choices documented herein (see "Tech Stack") are definitive for the entire project, including any frontend components.

## Starter Template or Existing Project

N/A

## Scope and Constraints

**Phase 1 Scope Boundaries:**
- **In Scope**: Access control components (A-prefix), PDF processing, Excel generation, async processing, AI accuracy evaluation
- **Out of Scope**: CCTV (C-prefix), intruder detection (I-prefix), native CAD formats, real-time processing, web UI, multi-tenant features
- **Hybrid Drawings**: Extract only A-prefix components, ignore others for Phase 1
- **Processing**: Single building per job, with metadata structure supporting future multi-building capability

**Key Architectural Constraints:**
- **Lambda Execution Limits**: 15-minute maximum requires chunking large drawings and checkpoint mechanisms
- **AI Provider Dependencies**: Gemini-specific features (multimodal, code execution) require abstraction layer
- **Data Privacy**: 55-day retention by Google requires obfuscation for sensitive building layouts
- **Async Processing**: No real-time requirements, optimize for accuracy over speed
- **Token Budgets**: Must implement limits to prevent cost overruns on complex drawings

**Future Extensibility Considerations:**
- Component extraction designed to be type-agnostic (easy addition of C, I prefixes)
- Modular AI provider interface to prevent vendor lock-in
- Service-oriented design ready for authentication layer
- Drawing revision tracking hooks in data model
- Multi-tenant isolation patterns in queue design

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|---------|
| 2025-08-04 | 1.0 | Initial architecture document creation | Winston (Architect) |
