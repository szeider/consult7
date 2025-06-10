import os
import re
import sys
from pathlib import Path
from typing import Optional
import httpx
from mcp.server.fastmcp import FastMCP

# Provider-specific imports will be done conditionally
try:
    from google import genai
    from google.genai import types

    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

try:
    from openai import AsyncOpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Constants
MAX_FILE_SIZE = 10_000_000  # 10MB per file (increased for large context models)
MAX_TOTAL_SIZE = 100_000_000  # 100MB total (increased for large context models)
MAX_RESPONSE_SIZE = 100_000  # 100KB response
FILE_SEPARATOR = "-" * 80
DEFAULT_IGNORED = [
    "__pycache__",
    ".env",
    "secrets.py",
    ".DS_Store",
    ".git",
    "node_modules",
]
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODELS_URL = "https://openrouter.ai/api/v1/models"

# Provider-specific defaults
DEFAULT_MODELS = {
    "openrouter": "google/gemini-2.5-pro-preview",
    "google": "gemini-2.0-flash-exp",
    "openai": "gpt-4o",
}

# Model context limits (updated dynamically)
model_context_length = None
# Token estimation safety buffer (reserve 10% for overhead since estimation already has buffer)
TOKEN_SAFETY_FACTOR = 0.9

# Initialize MCP server
mcp = FastMCP("Consult7")

# Global variables for CLI args (will be set in main)
api_key = None
provider = "openrouter"  # default provider
model = None  # Will be set based on provider


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text.
    More conservative estimates based on actual observations:
    - Code/text: ~3.2 chars/token
    - HTML/XML: ~2.5 chars/token (due to tags)
    - Add 10% buffer for safety
    """
    # Check if content looks like HTML/XML
    if "<" in text and ">" in text:
        # HTML/XML uses more tokens due to tags
        base_estimate = len(text) / 2.5
    else:
        # Regular text/code
        base_estimate = len(text) / 3.2

    # Add 10% safety buffer
    return int(base_estimate * 1.1)


def should_ignore_path(path: Path) -> bool:
    """Check if a path should be ignored based on default ignore list."""
    parts = path.parts
    for ignored in DEFAULT_IGNORED:
        if ignored in parts or path.name == ignored:
            return True
    return False


def discover_files(
    base_path: str, pattern: str, exclude_pattern: Optional[str] = None
) -> tuple[list[Path], list[str]]:
    """
    Discover files matching the pattern.
    Returns (matching_files, errors)
    """
    errors = []
    matching_files = []

    try:
        base = Path(base_path).resolve()
        if not base.exists():
            errors.append(f"Path does not exist: {base_path}")
            return [], errors

        if not base.is_dir():
            errors.append(f"Path is not a directory: {base_path}")
            return [], errors

        # Compile regex patterns
        try:
            include_re = re.compile(pattern)
        except re.error as e:
            errors.append(f"Invalid include pattern '{pattern}': {e}")
            return [], errors

        exclude_re = None
        if exclude_pattern:
            try:
                exclude_re = re.compile(exclude_pattern)
            except re.error as e:
                errors.append(f"Invalid exclude pattern '{exclude_pattern}': {e}")
                return [], errors

        # Walk directory tree
        for root, dirs, files in os.walk(base):
            root_path = Path(root)

            # Skip ignored directories
            dirs[:] = [d for d in dirs if not should_ignore_path(root_path / d)]

            for file in files:
                file_path = root_path / file

                # Skip ignored files
                if should_ignore_path(file_path):
                    continue

                # Check include pattern
                if not include_re.match(file):
                    continue

                # Check exclude pattern
                if exclude_re and exclude_re.match(file):
                    continue

                matching_files.append(file_path)

    except PermissionError as e:
        errors.append(f"Permission denied: {e}")
    except Exception as e:
        errors.append(f"Error during file discovery: {e}")

    return matching_files, errors


def format_content(
    base_path: str, files: list[Path], errors: list[str]
) -> tuple[str, int]:
    """
    Format files into text content.
    Returns (content, total_size)
    """
    content_parts = []
    total_size = 0

    # Add capacity information
    content_parts.append(f"File Size Budget: {MAX_TOTAL_SIZE:,} bytes (100MB)")
    content_parts.append(f"Files Found: {len(files)}")
    content_parts.append("")

    # Add directory tree
    content_parts.append("Directory Structure:")
    content_parts.append(FILE_SEPARATOR)

    # Build simple tree structure
    base = Path(base_path).resolve()
    tree_lines = []

    # Group files by directory
    dirs = {}
    for file in sorted(files):
        rel_path = file.relative_to(base)
        dir_path = rel_path.parent
        if dir_path not in dirs:
            dirs[dir_path] = []
        dirs[dir_path].append(rel_path.name)

    # Format tree
    for dir_path in sorted(dirs.keys()):
        if str(dir_path) == ".":
            tree_lines.append(f"{base_path}/")
        else:
            tree_lines.append(f"  {dir_path}/")
        for filename in sorted(dirs[dir_path]):
            tree_lines.append(f"    - {filename}")

    content_parts.extend(tree_lines)
    content_parts.append("")

    # Add file contents
    content_parts.append("File Contents:")
    content_parts.append(FILE_SEPARATOR)

    for file in sorted(files):
        content_parts.append(f"\nFile: {file}")
        content_parts.append(FILE_SEPARATOR)

        try:
            # Check file size
            file_size = file.stat().st_size
            if file_size > MAX_FILE_SIZE:
                content_parts.append(
                    f"[ERROR: File too large ({file_size} bytes > {MAX_FILE_SIZE} bytes)]"
                )
                errors.append(f"File too large: {file} ({file_size} bytes)")
            elif total_size + file_size > MAX_TOTAL_SIZE:
                content_parts.append("[ERROR: Total size limit exceeded]")
                errors.append(f"Total size limit exceeded at file: {file}")
                break
            else:
                # Read file content
                content = file.read_text(encoding="utf-8", errors="replace")
                content_parts.append(content)
                total_size += file_size

        except PermissionError:
            content_parts.append("[ERROR: Permission denied]")
            errors.append(f"Permission denied reading file: {file}")
        except Exception as e:
            content_parts.append(f"[ERROR: {e}]")
            errors.append(f"Error reading file {file}: {e}")

        content_parts.append("")

    # Add errors summary if any
    if errors:
        content_parts.append(FILE_SEPARATOR)
        content_parts.append("Errors encountered:")
        for error in errors:
            content_parts.append(f"- {error}")

    return "\n".join(content_parts), total_size


def get_google_model_info() -> dict:
    """Get model information for Google models."""
    return {"context_length": model_context_length, "provider": "google"}


def get_openai_model_info() -> dict:
    """Get model information for OpenAI models."""
    return {"context_length": model_context_length, "provider": "openai"}


async def get_model_info() -> Optional[dict]:
    """Get model information from OpenRouter API."""
    if not api_key:
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(MODELS_URL, headers=headers, timeout=10.0)

            if response.status_code != 200:
                print(f"Warning: Could not fetch model info: {response.status_code}")
                return None

            models = response.json().get("data", [])
            for model_info in models:
                if model_info.get("id") == model:
                    return model_info

            return None

    except Exception as e:
        print(f"Warning: Error fetching model info: {e}")
        return None


async def call_google(content: str, query: str) -> tuple[str, Optional[str]]:
    """
    Call Google AI API with the content and query.
    Returns (response, error)
    """
    if not GOOGLE_AVAILABLE:
        return "", "Google AI SDK not available. Install with: pip install google-genai"

    if not api_key:
        return "", "No API key provided. Use --api-key flag"

    # Estimate tokens for the input
    system_msg = "You are a helpful assistant analyzing code and files. Be concise and specific in your responses."
    user_msg = f"Here are the files to analyze:\n\n{content}\n\nQuery: {query}"
    total_input = system_msg + user_msg
    estimated_tokens = estimate_tokens(total_input)

    # Check against model context limit
    if model_context_length:
        max_output_tokens = 65536  # Google's max output
        available_for_input = int(
            (model_context_length - max_output_tokens) * TOKEN_SAFETY_FACTOR
        )

        if estimated_tokens > available_for_input:
            return "", (
                f"Content too large: ~{estimated_tokens:,} tokens estimated, "
                f"but model {model} has only ~{available_for_input:,} tokens available for input "
                f"(total limit: {model_context_length:,}, reserved for output: {max_output_tokens:,}). "
                f"Try reducing file count/size."
            )

    try:
        client = genai.Client(api_key=api_key)

        response = await client.aio.models.generate_content(
            model=model,
            contents=f"{system_msg}\n\n{user_msg}",
            config=types.GenerateContentConfig(
                max_output_tokens=16000, temperature=0.7
            ),
        )

        llm_response = response.text

        # Truncate if needed
        if len(llm_response) > MAX_RESPONSE_SIZE:
            llm_response = (
                llm_response[:MAX_RESPONSE_SIZE]
                + "\n[TRUNCATED - Response exceeded size limit]"
            )

        return llm_response, None

    except Exception as e:
        return "", f"Error calling Google AI: {str(e)}"


async def call_openai(content: str, query: str) -> tuple[str, Optional[str]]:
    """
    Call OpenAI API with the content and query.
    Returns (response, error)
    """
    if not OPENAI_AVAILABLE:
        return "", "OpenAI SDK not available. Install with: pip install openai"

    if not api_key:
        return "", "No API key provided. Use --api-key flag"

    # Estimate tokens for the input
    system_msg = "You are a helpful assistant analyzing code and files. Be concise and specific in your responses."
    user_msg = f"Here are the files to analyze:\n\n{content}\n\nQuery: {query}"
    total_input = system_msg + user_msg
    estimated_tokens = estimate_tokens(total_input)

    # Check against model context limit
    if model_context_length:
        max_output_tokens = 16000
        available_for_input = int(
            (model_context_length - max_output_tokens) * TOKEN_SAFETY_FACTOR
        )

        if estimated_tokens > available_for_input:
            return "", (
                f"Content too large: ~{estimated_tokens:,} tokens estimated, "
                f"but model {model} has only ~{available_for_input:,} tokens available for input "
                f"(total limit: {model_context_length:,}, reserved for output: {max_output_tokens:,}). "
                f"Try reducing file count/size."
            )

    try:
        client = AsyncOpenAI(api_key=api_key)

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.7,
            max_tokens=16000,
        )

        llm_response = response.choices[0].message.content

        # Truncate if needed
        if len(llm_response) > MAX_RESPONSE_SIZE:
            llm_response = (
                llm_response[:MAX_RESPONSE_SIZE]
                + "\n[TRUNCATED - Response exceeded size limit]"
            )

        return llm_response, None

    except Exception as e:
        return "", f"Error calling OpenAI: {str(e)}"


async def call_openrouter(content: str, query: str) -> tuple[str, Optional[str]]:
    """
    Call OpenRouter API with the content and query.
    Returns (response, error)
    """
    if not api_key:
        return "", "No API key provided. Use --api-key flag"

    # Estimate tokens for the input
    system_msg = "You are a helpful assistant analyzing code and files. Be concise and specific in your responses."
    user_msg = f"Here are the files to analyze:\n\n{content}\n\nQuery: {query}"
    total_input = system_msg + user_msg
    estimated_tokens = estimate_tokens(total_input)

    # Check against model context limit if known
    if model_context_length:
        # Reserve tokens for output
        max_output_tokens = 16000 if model_context_length > 100000 else 4000
        available_for_input = int(
            (model_context_length - max_output_tokens) * TOKEN_SAFETY_FACTOR
        )

        if estimated_tokens > available_for_input:
            return "", (
                f"Content too large: ~{estimated_tokens:,} tokens estimated, "
                f"but model {model} has only ~{available_for_input:,} tokens available for input "
                f"(total limit: {model_context_length:,}, reserved for output: {max_output_tokens:,}). "
                f"Try using a model with larger context or reducing file count/size."
            )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/consult7",
        "X-Title": "Consult7 MCP Server",
    }

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]

    # Use more tokens for models with large context windows
    max_output_tokens = (
        16000 if model_context_length and model_context_length > 100000 else 4000
    )

    data = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": max_output_tokens,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                OPENROUTER_URL, headers=headers, json=data, timeout=30.0
            )

            if response.status_code != 200:
                return "", f"API error: {response.status_code} - {response.text}"

            result = response.json()

            if "choices" not in result or not result["choices"]:
                return "", f"Unexpected API response format: {result}"

            llm_response = result["choices"][0]["message"]["content"]

            # Truncate if needed
            if len(llm_response) > MAX_RESPONSE_SIZE:
                llm_response = (
                    llm_response[:MAX_RESPONSE_SIZE]
                    + "\n[TRUNCATED - Response exceeded size limit]"
                )

            return llm_response, None

    except httpx.TimeoutException:
        return "", "Request timed out after 30 seconds"
    except Exception as e:
        return "", f"Error calling API: {e}"


@mcp.tool()
async def consultation(
    path: str, pattern: str, query: str, exclude_pattern: Optional[str] = None
) -> str:
    """
    Consult an LLM about code files matching a pattern in a directory.

    This tool collects all files matching a regex pattern from a directory tree,
    formats them into a structured document, and sends them to an LLM along with
    your query. The LLM analyzes the code and returns insights.

    Args:
        path: Absolute filesystem path to search from (e.g., "/Users/john/myproject")
        pattern: Regex to match filenames. Common patterns:
                 - ".*\\.py$" for all Python files
                 - ".*\\.(js|ts)$" for JavaScript/TypeScript files
                 - ".*test.*\\.py$" for Python test files
                 - "README.*" for README files
        query: Your question about the code. Examples:
               - "Which functions handle authentication?"
               - "Find all database queries"
               - "Explain the error handling strategy"
               - "List all API endpoints"
        exclude_pattern: Optional regex to exclude files (e.g., ".*test.*" to skip tests)

    Returns:
        The LLM's analysis of your code based on the query

    Example:
        # Analyze Python authentication code, excluding tests
        consultation(
            path="/Users/john/backend",
            pattern=".*\\.py$",
            query="How is user authentication implemented? What security measures are in place?",
            exclude_pattern=".*test.*\\.py$"
        )

        # Find all API endpoints in a Node.js project
        consultation(
            path="/home/dev/api-server",
            pattern=".*\\.(js|ts)$",
            query="List all REST API endpoints with their HTTP methods and authentication requirements",
            exclude_pattern="node_modules/.*"
        )

    Notes:
        - Automatically ignores: __pycache__, .env, secrets.py, .DS_Store, .git, node_modules
        - File size limit: 10MB per file, 100MB total (optimized for large context models)
        - Large files are skipped with an error message
        - Includes detailed errors for debugging (permissions, missing paths, etc.)
        - Default model has 1M+ token context window for analyzing large codebases
    """
    # Discover files
    files, errors = discover_files(path, pattern, exclude_pattern)

    if not files and errors:
        return "Error: No files found. Errors:\n" + "\n".join(errors)

    # Provide immediate feedback about what was found
    if not files:
        return f"No files matched pattern '{pattern}' in path '{path}'"

    # Format content
    content, total_size = format_content(path, files, errors)

    # Add size information to help the agent
    size_info = f"\n\n[File collection summary: {len(files)} files, {total_size:,} bytes used of {MAX_TOTAL_SIZE:,} bytes available ({(total_size/MAX_TOTAL_SIZE)*100:.1f}% utilized)]"

    # Estimate tokens
    full_content = content + size_info
    estimated_tokens = estimate_tokens(full_content)
    token_info = f"\nEstimated tokens: ~{estimated_tokens:,}"
    if model_context_length:
        token_info += f" (Model limit: {model_context_length:,} tokens)"

    # Call appropriate LLM based on provider
    if provider == "google":
        response, error = await call_google(content + size_info, query)
    elif provider == "openai":
        response, error = await call_openai(content + size_info, query)
    else:  # openrouter (default)
        response, error = await call_openrouter(content + size_info, query)

    if error:
        return f"Error calling {provider} LLM: {error}\n\nCollected {len(files)} files ({total_size:,} bytes){token_info}"

    # Add size info to response for agent awareness
    return f"{response}\n\n---\nProcessed {len(files)} files ({total_size:,} bytes) with {model} ({provider}){token_info}"


async def test_api_connection():
    """Test the API connection with a simple query."""
    print(f"Testing {provider} API connection...")
    print(f"Model: {model}")
    print(f"Model context window: {model_context_length:,} tokens")
    print(f"API Key: {'Set' if api_key else 'Not set'}")

    if not api_key:
        print("\nError: No API key provided!")
        print("Use --api-key flag")
        return False

    # Simple test query
    test_content = "This is a test file with sample content."
    test_query = "Reply with 'API test successful' if you can read this."

    # Call appropriate provider
    if provider == "google":
        response, error = await call_google(test_content, test_query)
    elif provider == "openai":
        response, error = await call_openai(test_content, test_query)
    else:  # openrouter
        response, error = await call_openrouter(test_content, test_query)

    if error:
        print(f"\nError: {error}")
        return False

    print(f"\nSuccess! Response from {model} ({provider}):")
    print(response)
    return True


def main():
    """Parse command line arguments and run the server."""
    global api_key, model, provider, model_context_length

    # Simple argument parsing
    args = sys.argv[1:]
    i = 0
    test_mode = False
    context_param = None

    while i < len(args):
        if args[i] == "--api-key" and i + 1 < len(args):
            api_key = args[i + 1]
            i += 2
        elif args[i] == "--provider" and i + 1 < len(args):
            provider = args[i + 1]
            if provider not in ["openrouter", "google", "openai"]:
                print(
                    f"Error: Invalid provider '{provider}'. Must be 'openrouter', 'google', or 'openai'"
                )
                sys.exit(1)
            i += 2
        elif args[i] == "--model" and i + 1 < len(args):
            model = args[i + 1]
            i += 2
        elif args[i] == "--context" and i + 1 < len(args):
            context_param = args[i + 1]
            i += 2
        elif args[i] == "--test":
            test_mode = True
            i += 1
        else:
            print(f"Unknown argument: {args[i]}")
            print(
                "Usage: consult7.py --api-key KEY [--provider PROVIDER] [--model MODEL] [--context TOKENS] [--test]"
            )
            sys.exit(1)

    # Check if API key provided
    if not api_key:
        print("Error: No API key provided. Use --api-key parameter.")
        sys.exit(1)

    # Set default model if not specified
    if not model:
        model = DEFAULT_MODELS[provider]

    # Parse context parameter
    if context_param:
        # Allow formats like "1M", "2M", "128K", or plain numbers
        try:
            if context_param.upper().endswith("M"):
                model_context_length = int(float(context_param[:-1]) * 1_000_000)
            elif context_param.upper().endswith("K"):
                model_context_length = int(float(context_param[:-1]) * 1_000)
            else:
                model_context_length = int(context_param)
        except ValueError:
            print(
                f"Error: Invalid context size '{context_param}'. Use formats like '1M', '128K', or '1000000'"
            )
            sys.exit(1)
    else:
        # Default to 1M tokens
        model_context_length = 1_000_000

    # For OpenRouter, still try to fetch actual model info
    import asyncio

    if provider == "openrouter" and not context_param:
        model_info = asyncio.run(get_model_info())
        if model_info and model_info.get("context_length"):
            model_context_length = model_info.get("context_length")

    if not test_mode:
        print(f"Model context window: {model_context_length:,} tokens")

    # Run test mode if requested
    if test_mode:
        success = asyncio.run(test_api_connection())
        sys.exit(0 if success else 1)

    # Normal server mode
    print("Starting Consult7 MCP Server")
    print(f"Provider: {provider}")
    print(f"Model: {model}")
    print("API Key: Set")

    mcp.run()


if __name__ == "__main__":
    main()
