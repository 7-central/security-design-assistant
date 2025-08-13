# Archived Tests - Future Use

This directory contains tests that are valuable but not needed in the current development phase.

## test_consistency_e2e.py

**Archived Date**: 2025-08-13  
**Reason**: High latency (5+ minutes) with low value in early development phases  
**Future Value**: Will be valuable for production stability validation

### What the test validates:
- AI model consistency across multiple runs (40% variance threshold)
- Component ID consistency (15% threshold) 
- Excel generation consistency
- Full pipeline stress testing (8 Gemini API calls)

### When to re-enable:
- Production deployment phase
- When AI model stability becomes critical
- For long-term regression detection
- When performance impact is acceptable

### How to re-enable:
1. Move `test_consistency_e2e.py` back to `tests/e2e/`
2. Add "consistency" back to CI/CD matrix in `.github/workflows/ci.yml`
3. Update expected pipeline runtime documentation

### Current pipeline impact without this test:
- **Before**: ~8-9 minutes total CI/CD runtime
- **After**: ~3-4 minutes total CI/CD runtime
- **Tests remaining**: 52 unit tests + 3 E2E test groups (api, pipeline, error)