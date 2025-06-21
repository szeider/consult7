# Timeout Parameter Feature

## Overview
This document describes the implementation of an optional `timeout` parameter for the consultation tool in Consult7. This feature allows users to override the default 22-second timeout on a per-call basis.

## Motivation
- Users reported that hardcoded timeouts don't respect MCP client timeout settings
- Different queries require different timeout tolerances:
  - Quick queries on small files may only need 10-15 seconds
  - Complex analysis with thinking models may need 60+ seconds
  - Large codebases with deep analysis could require even longer

## Important Constraint
The timeout parameter must be less than your MCP client's internal timeout setting. By default, MCP clients timeout after 25 seconds, so any timeout value ≥25s will be ineffective unless you've configured your MCP client with a longer timeout.

## Implementation Plan

### 1. Add Timeout Parameter to Tool Definition
In `server.py`, update the consultation tool's input schema:

```python
"timeout": {
    "type": "number", 
    "description": ToolDescriptions.get_timeout_description(),
}
```

The parameter is optional to maintain backward compatibility.

### 2. Create Timeout Description Method
In `tool_definitions.py`, add:

```python
@classmethod
def get_timeout_description(cls) -> str:
    """Get the timeout parameter description."""
    return "Optional timeout in seconds (overrides default 22s). Must be less than your MCP client's timeout (default 25s). Useful for long-running queries or slow models."
```

### 3. Update Consultation Implementation
In `consultation.py`:

1. Add missing imports:
   ```python
   import asyncio
   from .constants import LLM_CALL_TIMEOUT
   ```

2. Add timeout parameter to function signature:
   ```python
   async def consultation_impl(
       path: str,
       pattern: str,
       query: str,
       model: str,
       exclude_pattern: Optional[str] = None,
       provider: str = "openrouter",
       api_key: str = None,
       timeout: Optional[float] = None,  # New parameter
   ) -> str:
   ```

3. Use the timeout parameter:
   ```python
   # Use provided timeout or fall back to default
   effective_timeout = timeout or LLM_CALL_TIMEOUT
   
   try:
       async with asyncio.timeout(effective_timeout):
           response, error, thinking_budget = await provider_instance.call_llm(
               content + size_info, query, model, api_key, thinking_mode, custom_thinking
           )
   except asyncio.TimeoutError:
       return f"Error: Request timed out after {effective_timeout} seconds. Try using fewer files or a smaller query.\n\nCollected {len(files)} files ({total_size:,} bytes){token_info}"
   ```

### 4. Pass Timeout from Server
In `server.py`'s `call_tool` method:

```python
result = await consultation_impl(
    arguments["path"],
    arguments["pattern"],
    arguments["query"],
    arguments["model"],
    arguments.get("exclude_pattern"),
    server.provider,
    server.api_key,
    arguments.get("timeout"),  # Pass timeout parameter
)
```

## Usage Examples

### Default timeout (22 seconds):
```json
{
  "name": "consultation",
  "arguments": {
    "path": "/project",
    "pattern": ".*\\.py$",
    "query": "List all functions",
    "model": "gemini-2.5-flash"
  }
}
```

### Custom timeout for complex analysis:
```json
{
  "name": "consultation",
  "arguments": {
    "path": "/large-project",
    "pattern": ".*\\.(js|ts)$",
    "query": "Analyze all security vulnerabilities and suggest fixes",
    "model": "gemini-2.5-pro|thinking",
    "timeout": 120
  }
}
```

### Short timeout for quick queries:
```json
{
  "name": "consultation",
  "arguments": {
    "path": "/src",
    "pattern": "main.py",
    "query": "What does this file do?",
    "model": "gemini-2.5-flash",
    "timeout": 10
  }
}
```

## Benefits

1. **Flexibility**: Users can adjust timeout based on query complexity
2. **Backward Compatibility**: Optional parameter doesn't break existing integrations
3. **Better UX**: Clear error messages show actual timeout used
4. **Respects Client Settings**: When not specified, allows MCP client timeout to take precedence
5. **Thinking Model Support**: Longer timeouts for models that need more processing time

## Validation Considerations

When implementing, consider:
1. Warning users if timeout >= 25s (unless they've configured a longer MCP client timeout)
2. Maximum timeout validation (e.g., 600 seconds to prevent abuse)
3. Minimum timeout validation (e.g., 1 second)
4. Type validation (positive number)

## Testing Considerations

1. Test with various timeout values (5s, 20s, 24s)
2. Test timeout expiration with large files
3. Test with thinking models that typically take longer
4. Verify backward compatibility when timeout not provided
5. Test error messages show correct timeout value
6. Test behavior when timeout approaches MCP client limit (e.g., 24s with 25s client timeout)

## Future Considerations

- Could add timeout auto-adjustment based on file size and model type
- Could add warning when timeout seems too low for the query complexity
- Could integrate with MCP client timeout detection (if API available)