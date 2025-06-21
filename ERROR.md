# Error Handling and Crash Recovery Analysis for Consult7

## Current State Analysis

### 1. Limited Error Handling
The current implementation has minimal error handling in critical areas:

#### Server.py Issues:
- **No try/except in main loop**: The `server.run()` call in lines 188-199 has no exception handling
- **No graceful shutdown**: No signal handlers for SIGTERM/SIGINT
- **No recovery mechanism**: When server crashes, it simply exits
- **Basic error messages**: Clients only see generic "disconnected" message

#### Consultation.py Issues:
- **Some try/except blocks**: Has basic error handling for model info (lines 15-70)
- **Provider errors passed through**: Errors from providers are returned but not logged
- **No retry logic**: Failed API calls are not retried

#### Provider Issues:
- **Basic exception handling**: Providers catch exceptions but don't retry
- **No timeout handling**: Network timeouts can crash the server
- **Rate limiting not handled**: API rate limits cause immediate failures

### 2. Critical Failure Points

1. **Server Startup**: No protection around server initialization
2. **Tool Calls**: Unhandled exceptions in `call_tool()` crash the server
3. **Provider API Calls**: 
   - Network errors (connection timeout, DNS failure)
   - Internet connection down
   - API timeouts (request takes too long)
   - Rate limits exceeded
   - Invalid or expired API keys
   - Model not available or deprecated
   - Service outages (provider down)
4. **File Processing**: 
   - Large files causing memory issues
   - Permission errors
   - Invalid file paths
   - Corrupted files
5. **Memory Issues**: No protection against OOM when processing large codebases
6. **Model-Specific Issues**:
   - Model not found (e.g., typo in model name)
   - Model deprecated or renamed
   - Model temporarily unavailable
   - Model quota exceeded

### 3. MCP Protocol Limitations
- MCP uses stdio transport by default - when server dies, pipe breaks
- No built-in reconnection mechanism in MCP protocol
- Clients (like Claude) show generic "disconnected" message

## Proposed Solutions

### 1. Comprehensive Error Handling

#### A. Wrap Main Server Loop
```python
async def main():
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Existing server setup code...
            
            # Wrap server.run() in try/except
            async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
                await server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(...)
                )
            break  # Exit loop on clean shutdown
            
        except KeyboardInterrupt:
            print("\nShutting down gracefully...")
            break
        except Exception as e:
            retry_count += 1
            print(f"\nServer crashed: {e}")
            print(f"Retry attempt {retry_count}/{max_retries}")
            
            if retry_count < max_retries:
                await asyncio.sleep(2 ** retry_count)  # Exponential backoff
            else:
                print("Max retries exceeded. Exiting.")
                sys.exit(EXIT_FAILURE)
```

#### B. Protected Tool Calls
```python
@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls with error protection."""
    try:
        if name == "consultation":
            result = await consultation_impl(...)
            return [types.TextContent(type="text", text=result)]
        else:
            error_msg = f"Unknown tool: {name}"
            print(f"Error: {error_msg}")
            return [types.TextContent(type="text", text=f"Error: {error_msg}")]
            
    except asyncio.TimeoutError:
        error_msg = "Request timed out. Please try again with fewer files."
        print(f"Timeout error in tool call: {arguments}")
        return [types.TextContent(type="text", text=f"Error: {error_msg}")]
        
    except Exception as e:
        error_msg = f"Tool execution failed: {str(e)}"
        print(f"Error in tool call: {e}")
        print(f"Arguments: {arguments}")
        return [types.TextContent(type="text", text=f"Error: {error_msg}")]
```

### 2. Add Retry Logic for Providers

```python
async def call_llm_with_retry(self, content, query, model, api_key, max_retries=3):
    """Call LLM with exponential backoff retry."""
    last_error = None
    
    for attempt in range(max_retries):
        try:
            # Set timeout for API calls
            async with asyncio.timeout(300):  # 5 minute timeout
                return await self.call_llm(content, query, model, api_key)
                
        except asyncio.TimeoutError:
            last_error = "API request timed out after 5 minutes"
            wait_time = 5  # Short wait for timeout
            
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            
            # Determine retry strategy based on error type
            if any(x in error_str for x in ["rate limit", "quota", "429"]):
                wait_time = 60 * (attempt + 1)  # Wait longer for rate limits
                
            elif any(x in error_str for x in ["connection", "network", "timeout", "dns"]):
                wait_time = 5 * (attempt + 1)  # Network errors - retry sooner
                
            elif any(x in error_str for x in ["not found", "invalid model", "404"]):
                # Don't retry for invalid model names
                return "", f"Model '{model}' not found. Please check the model name.", None
                
            elif any(x in error_str for x in ["unauthorized", "invalid api", "401", "403"]):
                # Don't retry for auth errors
                return "", "Invalid or expired API key. Please check your credentials.", None
                
            else:
                wait_time = 2 ** attempt  # Exponential backoff for other errors
                
            if attempt < max_retries - 1:
                print(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
            
    return "", f"Failed after {max_retries} attempts: {last_error}", None
```

#### Network Connectivity Check
```python
async def check_internet_connection():
    """Check if internet is accessible."""
    import httpx
    
    test_urls = [
        "https://www.google.com",
        "https://8.8.8.8",  # Google DNS
        "https://1.1.1.1",  # Cloudflare DNS
    ]
    
    async with httpx.AsyncClient(timeout=5) as client:
        for url in test_urls:
            try:
                response = await client.get(url)
                if response.status_code < 500:
                    return True
            except:
                continue
                
    return False

# Use in provider before making API calls
if not await check_internet_connection():
    return "", "No internet connection detected. Please check your network.", None
```

### 3. Signal Handlers for Graceful Shutdown

```python
import signal

class Consult7Server(Server):
    def __init__(self, name: str, api_key: str, provider: str):
        super().__init__(name)
        self.api_key = api_key
        self.provider = provider
        self.shutdown_event = asyncio.Event()
        
    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"\nReceived signal {signum}. Shutting down...")
        self.shutdown_event.set()

# In main():
signal.signal(signal.SIGTERM, server.handle_shutdown)
signal.signal(signal.SIGINT, server.handle_shutdown)
```

### 4. Supervisor Script (Optional)

Create `consult7-supervisor.py`:
```python
#!/usr/bin/env python3
"""Supervisor script to auto-restart consult7 on crashes."""

import subprocess
import sys
import time
import datetime

def run_server(args):
    """Run the consult7 server and monitor it."""
    max_restarts = 5
    restart_count = 0
    restart_window = 300  # 5 minutes
    restart_times = []
    
    while True:
        start_time = time.time()
        print(f"\n[{datetime.datetime.now()}] Starting consult7 server...")
        
        process = subprocess.Popen(
            ["consult7"] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Monitor the process
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            print("Server shut down cleanly.")
            break
            
        # Handle crash
        print(f"\n[{datetime.datetime.now()}] Server crashed with code {process.returncode}")
        if stderr:
            print(f"Error output:\n{stderr}")
            
        # Check restart rate
        current_time = time.time()
        restart_times = [t for t in restart_times if current_time - t < restart_window]
        restart_times.append(current_time)
        
        if len(restart_times) >= max_restarts:
            print(f"Too many restarts ({max_restarts}) in {restart_window}s. Giving up.")
            sys.exit(1)
            
        # Exponential backoff
        wait_time = min(60, 2 ** len(restart_times))
        print(f"Restarting in {wait_time} seconds...")
        time.sleep(wait_time)

if __name__ == "__main__":
    run_server(sys.argv[1:])
```

### 5. Health Monitoring

Add health check capability:
```python
@server.get_resource("health://status")
async def get_health_status() -> str:
    """Provide server health status."""
    uptime = time.time() - server.start_time
    return {
        "status": "healthy",
        "uptime_seconds": uptime,
        "provider": server.provider,
        "version": SERVER_VERSION,
        "last_error": getattr(server, 'last_error', None),
        "request_count": getattr(server, 'request_count', 0)
    }
```

### 6. Better Error Messages

Update error returns to be more helpful:
```python
ERROR_MESSAGES = {
    # Network and connectivity errors
    "timeout": "Request timed out. Try:\n- Using fewer files\n- Narrowing your regex pattern\n- Checking your internet connection",
    "network": "Network error. Please:\n- Check your internet connection\n- Verify firewall settings\n- Try again in a few moments",
    "dns": "DNS resolution failed. Please check your network settings.",
    "connection": "Connection failed. The service might be down or blocked.",
    
    # API and authentication errors
    "rate_limit": "API rate limit reached. Please:\n- Wait 60 seconds before retrying\n- Consider upgrading your API plan\n- Reduce request frequency",
    "api_key": "Invalid API key. Please:\n- Check your credentials\n- Ensure the key hasn't expired\n- Verify you're using the correct provider",
    "unauthorized": "Authentication failed. Your API key may be invalid or expired.",
    "forbidden": "Access forbidden. Check your API key permissions.",
    
    # Model-related errors
    "model_not_found": "Model not found. Please:\n- Check the model name spelling\n- Verify the model is available for your provider\n- See available models in the startup message",
    "model_deprecated": "This model has been deprecated. Please use an updated model.",
    "model_unavailable": "Model temporarily unavailable. Try:\n- A different model\n- Waiting a few minutes\n- Checking provider status page",
    
    # Content and limit errors
    "context_exceeded": "Content exceeds model context. Try:\n- Using fewer files\n- Using a model with larger context window\n- Filtering with exclude_pattern",
    "quota_exceeded": "API quota exceeded. Please:\n- Check your usage limits\n- Upgrade your plan\n- Wait for quota reset",
    
    # Server errors
    "server_error": "Provider server error. Please:\n- Try again in a few moments\n- Check provider status page\n- Use a different model",
    "service_unavailable": "Service temporarily unavailable. The provider may be experiencing issues.",
}

def get_error_message(error: Exception) -> str:
    """Get user-friendly error message based on exception."""
    error_str = str(error).lower()
    
    # Check for specific error patterns
    if "timeout" in error_str:
        return ERROR_MESSAGES["timeout"]
    elif any(x in error_str for x in ["rate limit", "429"]):
        return ERROR_MESSAGES["rate_limit"]
    elif any(x in error_str for x in ["not found", "404"]) and "model" in error_str:
        return ERROR_MESSAGES["model_not_found"]
    elif any(x in error_str for x in ["unauthorized", "401"]):
        return ERROR_MESSAGES["unauthorized"]
    elif any(x in error_str for x in ["forbidden", "403"]):
        return ERROR_MESSAGES["forbidden"]
    elif any(x in error_str for x in ["network", "connection"]):
        return ERROR_MESSAGES["network"]
    elif "dns" in error_str:
        return ERROR_MESSAGES["dns"]
    elif "context" in error_str and "exceed" in error_str:
        return ERROR_MESSAGES["context_exceeded"]
    elif "quota" in error_str:
        return ERROR_MESSAGES["quota_exceeded"]
    elif any(x in error_str for x in ["500", "502", "503", "504"]):
        return ERROR_MESSAGES["server_error"]
    else:
        # Return original error with generic advice
        return f"{error}\n\nPlease check the error details and try again."
```

## Implementation Priority

1. **High Priority** (Prevents crashes):
   - Wrap main server loop with try/except
   - Add error handling to tool calls
   - Handle timeouts in provider calls

2. **Medium Priority** (Improves reliability):
   - Add retry logic with exponential backoff
   - Implement graceful shutdown
   - Better error messages

3. **Low Priority** (Nice to have):
   - Supervisor script for auto-restart
   - Health monitoring endpoint
   - Detailed logging system

## Testing Strategy

1. **Simulate Crashes**:
   - Invalid API keys
   - Network timeouts (unplug ethernet/disable wifi)
   - Internet connection down
   - DNS failures (invalid DNS server)
   - Large file processing
   - Rate limit errors
   - Invalid model names
   - Model not available errors
   - Provider service outages

2. **Monitor Recovery**:
   - Check auto-restart works
   - Verify error messages are helpful
   - Test graceful shutdown
   - Verify retry logic with different error types
   - Check timeout handling

3. **Load Testing**:
   - Multiple concurrent requests
   - Large codebases
   - Long-running queries
   - Memory pressure scenarios

4. **Specific Error Scenarios to Test**:
   ```python
   # Test invalid model
   await test_with_model("gpt-4-turbo-invalid-name")
   
   # Test network timeout
   with mock.patch('httpx.AsyncClient.post', side_effect=asyncio.TimeoutError):
       await test_consultation()
   
   # Test rate limit
   with mock.patch('httpx.AsyncClient.post', side_effect=httpx.HTTPStatusError(429)):
       await test_consultation()
   
   # Test no internet
   with mock.patch('socket.create_connection', side_effect=OSError("Network unreachable")):
       await test_consultation()
   ```

## Notes

- The stdio transport makes recovery challenging - when the process dies, the pipe breaks
- Consider SSE or HTTP transport for better recovery options
- Claude Desktop may need updates to handle reconnection
- Logging to file would help diagnose production issues