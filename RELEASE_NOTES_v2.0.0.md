# Release Notes v2.0.0

## Breaking Changes
- **New file list interface**: Replaced `path`/`pattern`/`exclude_pattern` with `files` list
  - Now accepts list of absolute file paths with wildcards in filenames only
  - No more regex patterns or recursive searching
  - Simpler, more intuitive, and predictable

## Key Improvements
- **Clearer file specification**: Wildcards only in filenames, not paths
- **Better validation**: Clear error messages for invalid paths or patterns

## Usage
```json
{
  "files": [
    "/path/to/src/*.py",
    "/path/to/lib/*.js",
    "/path/to/README.md"
  ],
  "query": "Analyze this code",
  "model": "gemini-2.5-flash"
}
```