# Validation Suite Report Template

## Report Header
- **Report ID:** {report_id}
- **Validation Run ID:** {validation_run_id}
- **Generated At:** {generated_at}
- **Test Set Version:** {test_set_version}

## Executive Summary

### Overall Performance: {performance_category}
- **Success Criteria Met:** {success_criteria_met}
- **Total Drawings Tested:** {total_drawings_tested}
- **Success Rate:** {success_rate_percentage}%
- **Average Processing Time:** {average_processing_time_minutes} minutes

### Key Findings
{key_findings_list}

### Priority Recommendations
{priority_recommendations_list}

## Detailed Analysis

### Assessment Breakdown
- **Good Assessments:** {good_count} ({good_percentage}%)
- **Fair Assessments:** {fair_count} ({fair_percentage}%)
- **Poor Assessments:** {poor_count} ({poor_percentage}%)
- **Failed Processing:** {failed_count}

### Performance by Complexity
{complexity_analysis_table}

### Performance by Challenge Type
{challenge_type_analysis_table}

## Pattern Analysis

### Common Strengths
{common_strengths_list}

### Common Weaknesses
{common_weaknesses_list}

### Context Effectiveness
{context_effectiveness_analysis}

## Success Criteria Evaluation

### Criteria Definition
- Minimum 60% of drawings must receive "Good" assessment
- Maximum 20% of drawings may receive "Poor" assessment
- Average judge confidence score above 0.7 (if available)

### Results
- **Good Rate:** {actual_good_rate} (Target: ≥60%) {good_criteria_status}
- **Poor Rate:** {actual_poor_rate} (Target: ≤20%) {poor_criteria_status}

### Gap Analysis
{gap_analysis_details}

## Recommendations

{recommendations_section}

## Performance Metrics

### Processing Time Statistics
- **Mean Processing Time:** {mean_processing_time} seconds
- **Min Processing Time:** {min_processing_time} seconds
- **Max Processing Time:** {max_processing_time} seconds
- **Total Processing Time:** {total_processing_time} seconds

### Component Extraction Statistics
- **Mean Components per Drawing:** {mean_components}
- **Min Components:** {min_components}
- **Max Components:** {max_components}
- **Total Components Extracted:** {total_components}

### Cost Analysis
- **Total Estimated Cost:** ${total_cost}
- **Cost per Drawing:** ${cost_per_drawing}
- **Cost per Good Assessment:** ${cost_per_good_assessment}
- **Efficiency Rating:** {efficiency_rating}

## Appendices

### A. Drawing-by-Drawing Breakdown
{drawing_breakdown_table}

### B. Common Issues Catalog
{common_issues_catalog}

### C. Technical Details
- **Pipeline Configuration:** Full analysis (context → schedule → excel → judge)
- **Models Used:** Gemini 2.5 Flash (context, excel), Gemini 2.5 Pro (schedule, judge)
- **Storage Mode:** {storage_mode}
- **Test Environment:** {test_environment}

### D. Recommendations Summary
{recommendations_summary_table}

---

## Report Generation Notes

This report template supports the following data substitutions:

### Executive Summary Variables
- `{report_id}` - Unique report identifier
- `{validation_run_id}` - Source validation run ID
- `{generated_at}` - Report generation timestamp
- `{test_set_version}` - Version of test description metadata
- `{performance_category}` - Overall performance rating (Excellent/Good/Fair/Poor)
- `{success_criteria_met}` - Boolean success criteria status
- `{total_drawings_tested}` - Count of drawings in test set
- `{success_rate_percentage}` - Percentage of good assessments
- `{average_processing_time_minutes}` - Mean processing time per drawing

### Analysis Variables
- `{good_count}`, `{fair_count}`, `{poor_count}`, `{failed_count}` - Assessment counts
- `{good_percentage}`, `{fair_percentage}`, `{poor_percentage}` - Assessment percentages
- `{complexity_analysis_table}` - Performance breakdown by drawing complexity
- `{challenge_type_analysis_table}` - Performance breakdown by challenge type

### Pattern Analysis Variables
- `{common_strengths_list}` - Bulleted list of system strengths
- `{common_weaknesses_list}` - Bulleted list of system weaknesses
- `{context_effectiveness_analysis}` - Analysis of context usage impact

### Success Criteria Variables
- `{actual_good_rate}`, `{actual_poor_rate}` - Measured rates
- `{good_criteria_status}`, `{poor_criteria_status}` - ✅ or ❌ status
- `{gap_analysis_details}` - Analysis of criteria gaps if not met

### Recommendations Variables
- `{recommendations_section}` - Full prioritized recommendations list
- `{recommendations_summary_table}` - Summary table of all recommendations

### Performance Variables
- `{mean_processing_time}`, `{min_processing_time}`, `{max_processing_time}` - Timing stats
- `{total_processing_time}` - Sum of all processing time
- `{mean_components}`, `{min_components}`, `{max_components}` - Component stats
- `{total_components}` - Sum of all extracted components
- `{total_cost}`, `{cost_per_drawing}`, `{cost_per_good_assessment}` - Cost analysis
- `{efficiency_rating}` - Overall efficiency rating

### Appendix Variables
- `{drawing_breakdown_table}` - Detailed per-drawing results
- `{common_issues_catalog}` - Catalog of frequent issues
- `{storage_mode}` - Local or AWS storage mode
- `{test_environment}` - Environment details

## Usage Instructions

1. Generate validation results using `scripts/validation_suite.py`
2. Process results with `ValidationReportGenerator.generate_comprehensive_report()`
3. Use `ValidationReportGenerator.generate_markdown_report()` to create formatted output
4. Substitute template variables with actual values from report data
5. Save final report to `tests/evaluation/validation_suite/reports/`

## Report Versioning

Reports should be versioned and stored with naming convention:
- `{validation_run_id}_comprehensive_report.json` - Full structured data
- `{validation_run_id}_executive_summary.md` - Executive summary only
- `{validation_run_id}_full_report.md` - Complete markdown report