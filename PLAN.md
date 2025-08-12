# Plan: Change Consultation Tool to Use File List Instead of Path+Regex

## Overview
Replace the current `path` + `pattern` (regex) approach with a simpler, more intuitive `files` parameter that accepts a list of file paths with wildcards allowed ONLY in filenames.

## Motivation
- **Current approach problems**:
  - Regex patterns are tricky to understand and error-prone
  - Files scattered across multiple paths require multiple tool calls
  - The combination of base path + filename regex is confusing
  
- **New approach benefits**:
  - Clear and explicit: list exactly which files or patterns you want
  - JSON-compatible list of strings
  - Simple wildcards in filenames only (e.g., `*.py`, `*.js`)
  - Can mix specific files and patterns in one call
  - No duplication possible since paths are explicit
  - Easier for AI agents to understand and use

## New Tool Interface

### Before (Current)
```json
{
  "path": "/Users/john/project",
  "pattern": ".*\\.py$",
  "exclude_pattern": ".*test.*",
  "query": "What does this code do?",
  "model": "gemini-2.5-flash"
}
```

### After (Proposed)
```json
{
  "files": [
    "/Users/john/project/src/*.py",
    "/Users/john/project/lib/*.js",
    "/Users/john/project/README.md",
    "/Users/john/other_project/main.py"
  ],
  "query": "What does this code do?",
  "model": "gemini-2.5-flash"
}
```

## Implementation Plan

### Phase 1: Core Changes

#### 1.1 Update `file_processor.py`
- **Remove**: `discover_files()` function that uses regex
- **Add**: `expand_file_patterns()` function
  - Takes a list of file paths/patterns
  - For each entry:
    - If it's a specific file path (no `*`) → add to results if exists
    - If it contains `*` in filename only → use `glob.glob()` to expand in that directory
    - Reject if `*` appears in the path portion (not the filename)
    - Reject if no extension specified with wildcard (e.g., `/path/*` not allowed, must be `/path/*.py`)
  - Returns list of resolved file paths
- **Keep**: `format_content()` mostly unchanged (just adapt to new input)
- **Keep**: `should_ignore_path()` to filter out `.git`, `__pycache__`, etc.
- **Add**: Validation for absolute paths (all paths must be absolute)

#### 1.2 Update `consultation.py`
- **Change** `consultation_impl()` signature:
  - Remove: `path`, `pattern`, `exclude_pattern` parameters
  - Add: `files` parameter (list of strings)
- **Update** file discovery call:
  - Replace `discover_files(path, pattern, exclude_pattern)`
  - With `expand_file_patterns(files)`

#### 1.3 Update `server.py`
- **Update** tool schema in `list_tools()`:
  - Remove: `path`, `pattern`, `exclude_pattern` properties
  - Add: `files` property (array of strings)
- **Update** `call_tool()`:
  - Pass `arguments["files"]` instead of path/pattern

#### 1.4 Update `tool_definitions.py`
- **Update** tool description to explain file list approach
- **Update** parameter descriptions
- **Add** examples showing glob patterns

### Phase 2: Enhanced Features

#### 2.1 Smart Defaults
- Automatically ignore common unwanted files (keep current DEFAULT_IGNORED)
- Even when explicitly matched by a pattern

#### 2.2 Error Handling
- Clear errors for:
  - Non-absolute paths
  - Non-existent files
  - Wildcards in path portion (only allowed in filename)
  - Missing extension with wildcards (e.g., `/path/*` not allowed)
  - Permission issues
- Continue processing other files even if some fail

#### 2.3 Directory Handling
- If a directory path is provided without wildcards:
  - Treat as error (must be explicit about what files to include)
  - Suggest adding `/*.ext` pattern with specific extension

### Phase 3: Testing & Documentation

#### 3.1 Update Tests
- Modify existing tests to use new interface
- Add tests for:
  - Glob pattern expansion
  - Mixed specific files and patterns
  - Error cases

#### 3.2 Update Documentation
- Update README.md with new examples
- Update CLAUDE.md with new interface
- Create migration guide for existing users

## Technical Details

### Glob Pattern Support
Use Python's `glob.glob()` (NO recursive flag needed):
- `*.py` - All Python files in the specific directory
- `*.js` - All JavaScript files in the specific directory
- `/absolute/path/file.py` - Specific file
- NOT ALLOWED: `**/*.py` (no recursive wildcards)
- NOT ALLOWED: `/*/path/*.py` (no wildcards in path)
- NOT ALLOWED: `/path/*` (must specify extension)

### File Path Validation
- All paths MUST be absolute (start with `/`)
- Wildcards ONLY allowed in filename portion
- Extension must be specified when using wildcards
- Rationale: Simple, predictable, no duplication possible
- Clear error messages if rules are violated

## Example Usage

### Simple Case
```json
{
  "files": ["/home/project/src/*.py"],
  "query": "Find all TODO comments",
  "model": "gemini-2.5-flash"
}
```

### Complex Case
```json
{
  "files": [
    "/home/project/src/*.py",
    "/home/project/lib/*.py",
    "/home/project/tests/*_test.py", 
    "/home/project/README.md",
    "/home/project/docs/*.md",
    "/home/shared/utils.py"
  ],
  "query": "Analyze the architecture",
  "model": "gemini-2.5-pro"
}
```

### Invalid Examples (will be rejected)
```json
{
  "files": [
    "/home/**/*.py",           // ERROR: Wildcards in path
    "/home/project/*",         // ERROR: No extension specified
    "src/*.py",                // ERROR: Not absolute path
    "/home/*/project/*.py"     // ERROR: Wildcards in path
  ]
}
```

## Timeline
1. Phase 1: Core implementation (1-2 hours)
2. Phase 2: Enhanced features (30 min)
3. Phase 3: Testing & docs (1 hour)

Total: ~3 hours of work

## Benefits of This Simplified Approach
- **No duplication possible** - each directory/pattern is explicit
- **Very predictable** - users know exactly what they're getting
- **Simple implementation** - just glob.glob() on specific directories
- **Clear errors** - easy to validate and explain what's wrong
- **No recursive complexity** - no deep directory traversal surprises