# Test Results Documentation

This directory contains structured test results from integration and variation testing.

## File Format

### Variation Test Results
File: `{test_run_id}_variations.json`

Structure:
```json
{
  "test_run_id": "variation_test_20250811_143022_a1b2c3d4",
  "timestamp": "2025-08-11T14:30:22",
  "variations": [
    {
      "variation_name": "01_different_text_sizes.pdf",
      "file_path": "tests/fixtures/drawings/variations/01_different_text_sizes.pdf",
      "execution_time_ms": 1250,
      "components_found": 3,
      "judge_score": 85.0,
      "judge_feedback": "Good extraction with minor location variance",
      "errors": [],
      "success": true,
      "timestamp": 1691760622.123
    }
  ],
  "summary": {
    "total_variations": 10,
    "passed": 9,
    "failed": 1,
    "pass_rate": 90.0,
    "average_execution_time_ms": 1180.5,
    "average_judge_score": 82.3,
    "min_judge_score": 65.0,
    "max_judge_score": 95.0
  }
}
```

### Consistency Test Results
File: `{test_run_id}_consistency.json`

Structure:
```json
{
  "test_run_id": "consistency_20250811_143500_e5f6g7h8",
  "timestamp": "2025-08-11T14:35:00",
  "drawing_name": "01_different_text_sizes.pdf",
  "num_runs": 5,
  "consistency_score": 96.5,
  "component_count_variance": 2.1,
  "location_variance_data": [
    {
      "component_id": "A-200",
      "x_variance": 0.8,
      "y_variance": 1.2,
      "max_deviation": 2
    }
  ],
  "inconsistencies": [],
  "summary": {
    "total_inconsistencies": 0,
    "passes_threshold": true,
    "variance_acceptable": true
  }
}
```

## Field Descriptions

### Variation Test Fields

- `test_run_id`: Unique identifier for the test run
- `timestamp`: ISO timestamp when test run started
- `variation_name`: Name of the variation file
- `file_path`: Full path to the variation file
- `execution_time_ms`: Time taken to process variation (milliseconds)
- `components_found`: Number of components extracted
- `judge_score`: AI Judge evaluation score (0-100)
- `judge_feedback`: Textual feedback from AI Judge
- `errors`: List of error messages if any
- `success`: Boolean indicating if processing succeeded

### Summary Fields

- `total_variations`: Total number of variations tested
- `passed`/`failed`: Count of successful/failed variations
- `pass_rate`: Percentage of variations that passed
- `average_execution_time_ms`: Average processing time
- `average_judge_score`: Average AI Judge score
- `min_judge_score`/`max_judge_score`: Score range

### Consistency Test Fields

- `drawing_name`: Name of drawing used for consistency testing
- `num_runs`: Number of times the same drawing was processed
- `consistency_score`: Overall consistency score (0-100)
- `component_count_variance`: Variance percentage in component counts
- `location_variance_data`: Detailed location variance for each component
- `inconsistencies`: List of detected inconsistencies

## Usage

### Loading Results
```python
from tests.test_result_logger import TestResultLogger

logger = TestResultLogger()

# Get all test runs
runs = logger.get_test_runs()

# Load specific test run
results = logger.load_test_run("variation_test_20250811_143022_a1b2c3d4")
```

### Analyzing Trends
```python
# Analyze variation test trends
trends = logger.analyze_trends("variation_test", limit=5)
print(f"Pass rate trend: {trends['pass_rate_trend']}")

# Generate summary report
report = logger.generate_summary_report()
print(report)
```

### Custom Analysis
```python
import json
from pathlib import Path

# Load and analyze specific metrics
results_dir = Path("tests/results")
for result_file in results_dir.glob("*_variations.json"):
    with open(result_file) as f:
        data = json.load(f)
    
    # Extract metrics for analysis
    scores = [v["judge_score"] for v in data["variations"]]
    avg_score = sum(scores) / len(scores)
    print(f"Run {data['test_run_id']}: Avg Score = {avg_score:.1f}")
```

## Quality Thresholds

### Variation Testing
- **Pass Rate**: Should be > 90%
- **Judge Score**: Individual scores should be > 70, average > 80
- **Execution Time**: Should be < 5000ms per variation

### Consistency Testing
- **Consistency Score**: Should be > 95%
- **Component Count Variance**: Should be < 5%
- **Location Variance**: Should be < 2 pixels max deviation

## Troubleshooting

### Low Judge Scores
If judge scores are consistently low:
1. Check if components are being extracted correctly
2. Verify component locations are accurate
3. Review component attribute detection (readers, buttons)

### High Variance
If consistency tests show high variance:
1. Check for randomness in AI model responses
2. Verify input preprocessing is deterministic
3. Review component matching algorithms

### Execution Time Issues
If processing is slow:
1. Check for memory leaks in processing pipeline
2. Verify drawing sizes are reasonable
3. Review timeout configurations

## Maintenance

### Cleanup Old Results
```bash
# Keep only last 30 days of results
find tests/results -name "*.json" -mtime +30 -delete
```

### Backup Important Results
```bash
# Archive important test runs
tar -czf test_results_$(date +%Y%m%d).tar.gz tests/results/
```