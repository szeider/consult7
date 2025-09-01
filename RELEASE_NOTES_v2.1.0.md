# Release Notes v2.1.0

## New Features

### Optional File Output
- Added `output_file` parameter to save LLM responses directly to files
- Prevents flooding agent context with large responses
- Automatic conflict resolution with `_updated` suffix
- Returns brief confirmation: "Result has been saved to /path/to/file"

## Use Cases
- Generate reports and documentation without overwhelming agent memory
- Save code reviews, architecture analyses, and other lengthy outputs
- Preserve analysis results for future reference

## Usage Example
```python
# Save response to file instead of returning it
consultation(
    files=["/path/src/*.py"], 
    query="Generate a comprehensive code review",
    model="gemini-2.5-pro",
    output_file="/path/reports/review.md"
)
# Returns: "Result has been saved to /path/reports/review.md"
```

## Compatibility
- Fully backward compatible - `output_file` is optional
- No changes to existing functionality
- Works with all supported providers (OpenRouter, Google, OpenAI)