# Release Notes v2.0.0

## Breaking Changes
- **New file list interface**: Replaced `path`/`pattern`/`exclude_pattern` with `files` list
  - Now accepts list of absolute file paths with wildcards in filenames only
  - No more regex patterns or recursive searching
  - Simpler, more intuitive, and predictable

## New Features
- **GPT-5 support**: Added support for all GPT-5 variants (base, mini, nano)
- **Updated Gemini Flash Lite**: Now using stable version instead of preview

## Key Improvements
- **Clearer file specification**: Wildcards only in filenames, not paths
- **Better validation**: Clear error messages for invalid paths or patterns
- **Realistic file size limits**: 1MB per file, 4MB total (optimized for ~1M tokens)

## Usage
```json
{
  "files": [
    "/path/to/src/*.py",
    "/path/to/lib/*.js",
    "/path/to/README.md"
  ],
  "query": "Analyze this code",
  "model": "gpt-5|400k"
}
```