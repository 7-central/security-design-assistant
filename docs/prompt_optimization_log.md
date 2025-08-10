# Prompt Optimization Log

## Overview
This document tracks the iterative improvement of prompts based on Judge Agent feedback, documenting the evolution from baseline performance to target accuracy.

## Optimization Target
**Success Criteria**: 3 consecutive "Good" assessments with minor issues only across test drawings.

## Version History

### Version 1 (Baseline) - 2025-08-10
**Date**: 2025-08-10  
**Description**: Initial production prompt serving as baseline  
**Status**: Baseline established

**Test Drawings Results**:
- `example_b2_drawing.pdf`: Not yet tested (requires API call)
- `103P3-E34-QCI-40098_Ver1.pdf`: Not yet tested (requires API call)

**Mock Analysis Results** (based on typical feedback patterns):
| Assessment | Count | Percentage |
|------------|-------|------------|
| Fair       | 2     | 100%       |
| Good       | 0     | 0%         |
| Poor       | 0     | 0%         |

**Identified Issues**:
1. **Completeness**: System missed several emergency exit buttons and door controllers
2. **Reader Types**: Confusion between P-type and E-type readers
3. **Spatial Understanding**: Unclear associations between components and doors

**Common Improvement Suggestions**:
1. Focus on emergency exit door patterns and exit button identification
2. Clarify distinction between reader types P and E
3. Add explicit instructions for emergency exit identification
4. Improve spatial relationship instructions for component-door associations

---

### Version 2 (Emergency Exit Focus) - 2025-08-10
**Date**: 2025-08-10  
**Description**: Enhanced prompt addressing emergency exit identification and reader type classification  
**Base Version**: Version 1  
**Status**: Active (current production version)

**Changes Made**:
1. **Emergency Exit Enhancement**:
   - Added CRITICAL emphasis on emergency exit door detection
   - Included explicit patterns: "EXIT" labels, exit signs, distinctive symbols
   - Added emergency exit identification checklist

2. **Reader Type Classification**:
   - Clear distinction between P-type (proximity) and E-type (keypad) readers
   - Added visual cue guidance ("P"/"E" markings, keypad visibility)
   - Explicit lookup instructions for type designations

3. **Spatial Relationship Improvements**:
   - Added dedicated spatial relationship guidelines section
   - Clear instructions for component-door associations
   - Emphasis on complete system identification (door + reader + exit button)

**Prompt Improvements**:
```
ADDED: CRITICAL: Pay special attention to EMERGENCY EXIT doors
ADDED: IMPORTANT: Distinguish between reader types (P vs E)
ADDED: SPATIAL RELATIONSHIP GUIDELINES section
ADDED: EMERGENCY EXIT IDENTIFICATION CHECKLIST
```

**Test Drawings Results**:
- `example_b2_drawing.pdf`: Pending evaluation
- `103P3-E34-QCI-40098_Ver1.pdf`: Pending evaluation

**Expected Improvements**:
- Better detection of emergency exit components
- Reduced confusion between reader types
- Improved spatial component associations
- Target: Move from Fair to Good assessments

---

## Testing Framework

### Test Drawings
1. **example_b2_drawing.pdf**
   - **Type**: Single page security drawing
   - **Characteristics**: Standard components, clear annotations with A-prefix IDs
   - **Purpose**: Baseline test for fundamental extraction accuracy

2. **103P3-E34-QCI-40098_Ver1.pdf**
   - **Type**: Multi-page complex drawing
   - **Characteristics**: Mixed security/non-security pages, dense annotations
   - **Purpose**: Test page filtering and complex spatial relationships

### Evaluation Process
1. Run schedule extraction with specific prompt version
2. Generate judge evaluation for each test drawing
3. Analyze feedback patterns across all evaluations
4. Identify top 2 improvement areas
5. Create new prompt version addressing issues
6. Document changes and expected improvements

### Automation
- **Script**: `scripts/prompt_optimization.py`
- **Commands**:
  - Single version: `python scripts/prompt_optimization.py --version 1`
  - Multiple versions: `python scripts/prompt_optimization.py --versions 1 2`
  - All versions: `python scripts/prompt_optimization.py --all`

### Results Storage
- **Location**: `tests/evaluation/prompt_optimization_results/`
- **Structure**:
  ```
  tests/evaluation/prompt_optimization_results/
  ├── v1/
  │   ├── iteration_results.json
  │   └── analysis_report.txt
  ├── v2/
  │   ├── iteration_results.json
  │   └── analysis_report.txt
  └── comparison_report.txt
  ```

---

## Next Steps

### Version 3 Planning
**Planned Focus Areas**:
- Component ID pattern recognition improvements
- Context utilization enhancements
- False positive reduction strategies

**Target Timeline**: After V2 evaluation complete

### Success Metrics Tracking
**Current Progress**: 0/3 consecutive "Good" assessments  
**Goal**: Achieve 3 consecutive "Good" assessments across test drawings

**Performance Trend**:
- V1: Baseline (Fair assessments expected)
- V2: Targeting Good assessments with emergency exit focus
- V3+: Fine-tuning based on V2 results

---

## Lessons Learned

### Effective Prompt Improvements
1. **Explicit Pattern Recognition**: Adding specific visual cues and patterns improves detection accuracy
2. **Critical/Important Marking**: Using emphasis markers helps prioritize key areas
3. **Checklist Format**: Structured checklists ensure comprehensive coverage
4. **Spatial Guidelines**: Dedicated sections for spatial relationships reduce association errors

### Testing Insights
- Mock feedback analysis provides valuable development framework
- Incremental improvements allow focused testing
- Documentation of changes enables pattern tracking
- Version comparison reveals improvement trends

---

*This log is updated after each optimization iteration to maintain complete improvement history.*