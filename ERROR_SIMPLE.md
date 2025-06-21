# Simple Error Handling Plan for Consult7

## Philosophy
- **Fast Fail**: Return errors immediately, don't retry
- **Stateless**: Each request is independent, no recovery state
- **Simple**: Minimal code changes, maximum stability
- **Clear Feedback**: Users get actionable error messages

## Current Problem
When the server encounters an unhandled exception, it crashes and clients see "disconnected". This provides no useful information to users.

## Simple Solution: Catch and Return Errors

### 1. Protect the Main Server Loop
Add minimal exception handling to prevent crashes:

```python
# In server.py - wrap the tool handler
@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls."""
    try:
        if name == "consultation":
            result = await consultation_impl(
                arguments["path"],
                arguments["pattern"],
                arguments["query"],
                arguments["model"],
                arguments.get("exclude_pattern"),
                server.provider,
                server.api_key,
            )
            return [types.TextContent(type="text", text=result)]
        else:
            return [types.TextContent(type="text", text=f"Error: Unknown tool '{name}'")]
    except Exception as e:
        # Log the full error for debugging
        print(f"Error in {name}: {type(e).__name__}: {str(e)}")
        
        # Return user-friendly error
        error_msg = get_simple_error_message(e)
        return [types.TextContent(type="text", text=f"Error: {error_msg}")]
```

### 2. Simple Error Message Mapping
Just enough to be helpful, not complex:

```python
def get_simple_error_message(e: Exception) -> str:
    """Convert exceptions to user-friendly messages."""
    error_str = str(e).lower()
    
    # Network/connection issues
    if any(x in error_str for x in ["connection", "network", "timeout", "unreachable"]):
        return "Network error. Please check your internet connection and try again."
    
    # API key issues
    if any(x in error_str for x in ["unauthorized", "401", "403", "invalid api"]):
        return "Invalid API key. Please check your credentials."
    
    # Rate limiting
    if any(x in error_str for x in ["rate limit", "429", "quota"]):
        return "Rate limit exceeded. Please wait a moment and try again."
    
    # Model not found
    if any(x in error_str for x in ["not found", "404"]) and "model" in error_str:
        return f"Model not found. Please check the model name."
    
    # File/content too large
    if any(x in error_str for x in ["too large", "exceeds", "context"]):
        return "Content too large. Try using fewer files or a larger context model."
    
    # Default - return the actual error
    return str(e)
```

### 3. Add Timeout Protection
Simple timeout to prevent hanging:

```python
# In consultation.py - wrap provider calls
try:
    # Simple 5-minute timeout
    async with asyncio.timeout(300):
        response, error, thinking_budget = await provider_instance.call_llm(
            content + size_info, query, model, api_key, thinking_mode, custom_thinking
        )
except asyncio.TimeoutError:
    return "Error: Request timed out after 5 minutes. Try using fewer files."
```

### 4. Log Errors for Debugging
Simple logging without complexity:

```python
# In server.py at the top
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('consult7.log'),
        logging.StreamHandler()
    ]
)
```

## What We DON'T Do

1. **No Retry Logic**: If it fails, it fails. User can retry.
2. **No Recovery Mechanisms**: Each request is independent.
3. **No Complex State Management**: Keep it stateless.
4. **No Auto-Restart**: If server crashes despite our catch, let it crash.
5. **No Network Checks**: Just try and fail fast if no connection.

## Benefits

1. **Server Stays Up**: Exceptions are caught and returned as errors
2. **Fast Feedback**: Users know immediately what went wrong
3. **Simple Code**: Minimal changes, easy to maintain
4. **Actionable Errors**: Users can fix issues (check connection, reduce files, fix API key)

## Implementation Priority

1. **Must Have** (prevents crashes):
   - Wrap call_tool() with try/except
   - Add timeout to LLM calls
   - Return errors instead of crashing

2. **Nice to Have** (better UX):
   - Simple error message mapping
   - Basic logging to file

## Testing

Simple manual tests:
```bash
# Test with invalid API key
consult7 google invalid-key

# Test with invalid model  
# Use consultation tool with model="invalid-model-name"

# Test with network disconnected
# Disconnect internet and try a query

# Test with huge file
# Try processing a very large codebase
```

## Summary

This approach adds just enough error handling to:
- Prevent server crashes
- Give users clear feedback
- Maintain simplicity
- Stay stateless

The philosophy is: "Fail fast, fail clearly, let the user decide what to do next."