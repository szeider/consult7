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

# ==============================================================================
# MODEL EXAMPLES - Update these when new models become available
# ==============================================================================
MODEL_EXAMPLES = {
    "openrouter": [
        '"google/gemini-2.5-pro-preview" (intelligent, 1M context)',
        '"google/gemini-2.5-flash-preview-05-20" (fast, 1M context)',
        '"google/gemini-2.5-flash-preview-05-20:thinking" (reasoning, 1M context)',
        '"anthropic/claude-opus-4" (very intelligent, 200k context)',
    ],
    "google": [
        '"gemini-2.5-flash-preview-05-20" (fast, 1M context)',
        '"gemini-2.5-pro-preview-06-05" (intelligent, 1M context)',
        '"gemini-2.0-flash-thinking-exp-01-21" (reasoning, 32k context)',
    ],
    "openai": [
        '"o4-mini-2025-04-16|200k" (intelligent, reasoning)',
        '"o3-2025-04-16|200k" (very intelligent, reasoning)',
        '"gpt-4.1-2025-04-14|1047576" (fast, huge context)',
        '"gpt-4.1-nano-2025-04-14|1047576" (very fast, huge context)',
    ],
}
# ==============================================================================

# Model context limits (updated dynamically)
model_context_length = None
# Token estimation safety buffer (reserve 10% for overhead since estimation already has buffer)
TOKEN_SAFETY_FACTOR = 0.9

# Initialize MCP server
mcp = FastMCP("Consult7")

# Global variables for CLI args (will be set in main)
api_key = None
provider = "openrouter"  # default provider


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


async def get_google_model_info(model_name: str) -> Optional[dict]:
    """Get model information for Google models."""
    if not GOOGLE_AVAILABLE:
        return None

    try:
        from google import genai

        client = genai.Client(api_key=api_key)

        # Ensure model name has correct format
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"

        model_info = client.models.get(model=model_name)

        # Return context info in consistent format
        return {
            "context_length": model_info.input_token_limit,
            "max_output_tokens": model_info.output_token_limit,
            "provider": "google",
        }
    except Exception as e:
        print(f"Warning: Could not fetch Google model info: {e}")
        return None


def get_openai_model_info(model_name: str) -> Optional[dict]:
    """Get model information for OpenAI models."""
    # OpenAI API doesn't provide context length via API
    # Context must be specified by the user
    return None  # No default context - must be specified


async def get_openrouter_model_info(model_name: str) -> Optional[dict]:
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
                if model_info.get("id") == model_name:
                    # Return in consistent format
                    return {
                        "context_length": model_info.get("context_length", 128000),
                        "max_output_tokens": model_info.get(
                            "max_completion_tokens", 4096
                        ),
                        "provider": "openrouter",
                        "pricing": model_info.get("pricing"),
                        "raw_info": model_info,  # Keep full info for debugging
                    }

            # Model not found in list
            print(f"Warning: Model '{model_name}' not found in OpenRouter models list")
            return None

    except Exception as e:
        print(f"Warning: Error fetching model info: {e}")
        return None


async def get_model_context_info(model_name: str) -> Optional[dict]:
    """Get model context information based on provider and model."""
    global model_context_length

    try:
        # Parse model name for OpenAI models with context specification
        actual_model_name = model_name
        specified_context = None

        if provider == "openai" and "|" in model_name:
            actual_model_name, context_str = model_name.split("|", 1)
            # Parse context like "200k" -> 200000, "1047576" -> 1047576
            if context_str.endswith("k"):
                specified_context = int(float(context_str[:-1]) * 1000)
            else:
                specified_context = int(context_str)

        # Get model info based on provider
        if provider == "google":
            info = await get_google_model_info(actual_model_name)
        elif provider == "openai":
            # OpenAI requires context to be specified
            if not specified_context:
                raise ValueError(
                    f"OpenAI models require context length specification. Use format: '{actual_model_name}|128k' or '{actual_model_name}|200000'"
                )
            info = {
                "context_length": specified_context,
                "max_output_tokens": 16384,  # OpenAI models typically support this
                "provider": "openai",
            }
        else:  # openrouter
            info = await get_openrouter_model_info(actual_model_name)

        if info and "context_length" in info:
            model_context_length = info["context_length"]
            return info

        # Fallback to default if no info available
        print(
            f"Warning: Could not determine context length for {model_name}, using default of 128k tokens"
        )
        model_context_length = 128000
        return {"context_length": 128000, "provider": provider}

    except ValueError:
        # Re-raise ValueError to be caught by caller
        raise
    except Exception as e:
        print(f"Error getting model info: {e}")
        model_context_length = 128000
        return {"context_length": 128000, "provider": provider}


async def call_google(
    content: str, query: str, model_name: str
) -> tuple[str, Optional[str]]:
    """
    Call Google AI API with the content and query.
    Returns (response, error)
    """
    if not GOOGLE_AVAILABLE:
        return "", "Google AI SDK not available. Install with: pip install google-genai"

    if not api_key:
        return "", "No API key provided. Use --api-key flag"

    # Get model context info
    try:
        model_info = await get_model_context_info(model_name)
        context_length = model_info.get("context_length", 128000)
    except ValueError as e:
        return "", str(e)

    # Estimate tokens for the input
    system_msg = "You are a helpful assistant analyzing code and files. Be concise and specific in your responses."
    user_msg = f"Here are the files to analyze:\n\n{content}\n\nQuery: {query}"
    total_input = system_msg + user_msg
    estimated_tokens = estimate_tokens(total_input)

    # Check against model context limit
    max_output_tokens = model_info.get("max_output_tokens", 65536)
    available_for_input = int(
        (context_length - max_output_tokens) * TOKEN_SAFETY_FACTOR
    )

    if estimated_tokens > available_for_input:
        return "", (
            f"Content too large: ~{estimated_tokens:,} tokens estimated, "
            f"but model {model_name} has only ~{available_for_input:,} tokens available for input "
            f"(total limit: {context_length:,}, reserved for output: {max_output_tokens:,}). "
            f"Try reducing file count/size."
        )

    try:
        client = genai.Client(api_key=api_key)

        response = await client.aio.models.generate_content(
            model=model_name,
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


async def call_openai(
    content: str, query: str, model_name: str
) -> tuple[str, Optional[str]]:
    """
    Call OpenAI API with the content and query.
    Returns (response, error)
    """
    if not OPENAI_AVAILABLE:
        return "", "OpenAI SDK not available. Install with: pip install openai"

    if not api_key:
        return "", "No API key provided. Use --api-key flag"

    # Get model context info (including parsed context from model|context format)
    try:
        model_info = await get_model_context_info(model_name)
        context_length = model_info.get("context_length", 128000)
    except ValueError as e:
        return "", str(e)

    # Extract actual model name (without context specification)
    actual_model_name = model_name.split("|")[0] if "|" in model_name else model_name

    # Estimate tokens for the input
    system_msg = "You are a helpful assistant analyzing code and files. Be concise and specific in your responses."
    user_msg = f"Here are the files to analyze:\n\n{content}\n\nQuery: {query}"
    total_input = system_msg + user_msg
    estimated_tokens = estimate_tokens(total_input)

    # Check against model context limit
    max_output_tokens = model_info.get("max_output_tokens", 16000)
    available_for_input = int(
        (context_length - max_output_tokens) * TOKEN_SAFETY_FACTOR
    )

    if estimated_tokens > available_for_input:
        return "", (
            f"Content too large: ~{estimated_tokens:,} tokens estimated, "
            f"but model {model_name} has only ~{available_for_input:,} tokens available for input "
            f"(total limit: {context_length:,}, reserved for output: {max_output_tokens:,}). "
            f"Try reducing file count/size."
        )

    try:
        client = AsyncOpenAI(api_key=api_key)

        response = await client.chat.completions.create(
            model=actual_model_name,
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


async def call_openrouter(
    content: str, query: str, model_name: str
) -> tuple[str, Optional[str]]:
    """
    Call OpenRouter API with the content and query.
    Returns (response, error)
    """
    if not api_key:
        return "", "No API key provided. Use --api-key flag"

    # Get model context info
    try:
        model_info = await get_model_context_info(model_name)
        context_length = model_info.get("context_length", 128000)
    except ValueError as e:
        return "", str(e)

    # Estimate tokens for the input
    system_msg = "You are a helpful assistant analyzing code and files. Be concise and specific in your responses."
    user_msg = f"Here are the files to analyze:\n\n{content}\n\nQuery: {query}"
    total_input = system_msg + user_msg
    estimated_tokens = estimate_tokens(total_input)

    # Check against model context limit if known
    # Reserve tokens for output
    max_output_tokens = 16000 if context_length > 100000 else 4000
    available_for_input = int(
        (context_length - max_output_tokens) * TOKEN_SAFETY_FACTOR
    )

    if estimated_tokens > available_for_input:
        return "", (
            f"Content too large: ~{estimated_tokens:,} tokens estimated, "
            f"but model {model_name} has only ~{available_for_input:,} tokens available for input "
            f"(total limit: {context_length:,}, reserved for output: {max_output_tokens:,}). "
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

    data = {
        "model": model_name,
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


def create_consultation_tool():
    """Create the consultation tool with provider-specific documentation."""
    # Get model examples for the configured provider
    examples = MODEL_EXAMPLES.get(provider, [])

    # Build model parameter description
    if provider == "openai":
        model_desc = f"model: The model to use with {provider.title()} (include context length with | separator). Examples:\n"
    else:
        model_desc = f"model: The model to use with {provider.title()}. Examples:\n"

    for example in examples:
        model_desc += f"               - {example}\n"
    model_desc = model_desc.rstrip()  # Remove trailing newline

    # Build provider-specific notes
    if provider == "openai":
        provider_notes = f'- {provider.title()} requires context length specification with | separator: "model-name|128k" or "model-name|200000"'
    else:
        provider_notes = (
            f"- {provider.title()} model context windows are auto-detected from the API"
        )

    # Get example models for the Examples section
    # Extract just the model name without attributes
    if examples:
        # Split on the closing quote to get just the model name
        example1 = examples[0].split('"')[1] if '"' in examples[0] else "model-name"
        example2 = examples[1].split('"')[1] if len(examples) > 1 and '"' in examples[1] else example1
    else:
        example1 = "model-name"
        example2 = example1

    # Build the docstring
    docstring = f"""
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
        {model_desc}
        exclude_pattern: Optional regex to exclude files (e.g., ".*test.*" to skip tests)

    Returns:
        The LLM's analysis of your code based on the query

    Example:
        # Analyze Python authentication code, excluding tests
        consultation(
            path="/Users/john/backend",
            pattern=".*\\.py$",
            query="How is user authentication implemented? What security measures are in place?",
            model="{example1}",
            exclude_pattern=".*test.*\\.py$"
        )

        # Find all API endpoints in a Node.js project
        consultation(
            path="/home/dev/api-server",
            pattern=".*\\.(js|ts)$",
            query="List all REST API endpoints with their HTTP methods and authentication requirements",
            model="{example2}",
            exclude_pattern="node_modules/.*"
        )

    Notes:
        - Automatically ignores: __pycache__, .env, secrets.py, .DS_Store, .git, node_modules
        - File size limit: 10MB per file, 100MB total (optimized for large context models)
        - Large files are skipped with an error message
        - Includes detailed errors for debugging (permissions, missing paths, etc.)
        {provider_notes}
    """

    # Define the function WITHOUT the decorator first
    async def consultation(
        path: str,
        pattern: str,
        query: str,
        model: str,
        exclude_pattern: Optional[str] = None,
    ) -> str:
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
        size_info = f"\n\n[File collection summary: {len(files)} files, {total_size:,} bytes used of {MAX_TOTAL_SIZE:,} bytes available ({(total_size / MAX_TOTAL_SIZE) * 100:.1f}% utilized)]"

        # Get model context info to display
        try:
            model_info = await get_model_context_info(model)
            model_context_length = model_info.get("context_length", 128000)
        except ValueError as e:
            return f"Error: {str(e)}"

        # Estimate tokens
        full_content = content + size_info
        estimated_tokens = estimate_tokens(full_content)
        token_info = f"\nEstimated tokens: ~{estimated_tokens:,}"
        if model_context_length:
            token_info += f" (Model limit: {model_context_length:,} tokens)"

        # Call appropriate LLM based on provider
        if provider == "google":
            response, error = await call_google(content + size_info, query, model)
        elif provider == "openai":
            response, error = await call_openai(content + size_info, query, model)
        else:  # openrouter (default)
            response, error = await call_openrouter(content + size_info, query, model)

        if error:
            return f"Error calling {provider} LLM: {error}\n\nCollected {len(files)} files ({total_size:,} bytes){token_info}"

        # Add size info to response for agent awareness
        return f"{response}\n\n---\nProcessed {len(files)} files ({total_size:,} bytes) with {model} ({provider}){token_info}"

    # Set the docstring BEFORE applying the decorator
    consultation.__doc__ = docstring

    # Apply the decorator manually and return the decorated function
    return mcp.tool()(consultation)


async def test_api_connection():
    """Test the API connection with a simple query."""
    print(f"\nTesting {provider} API connection...")
    print(f"API Key: {'Set' if api_key else 'Not set'}")

    if not api_key:
        print("\nError: No API key provided!")
        print("Use --api-key flag")
        return False

    # Use a default test model for each provider
    test_models = {
        "openrouter": "google/gemini-2.5-flash-preview-05-20",
        "google": "gemini-2.0-flash-exp",
        "openai": "gpt-4o-mini|128k",
    }
    test_model = test_models.get(provider, "google/gemini-2.5-flash-preview-05-20")

    # Simple test query
    test_content = "This is a test file with sample content."
    test_query = "Reply with 'API test successful' if you can read this."

    # Call appropriate provider
    if provider == "google":
        response, error = await call_google(test_content, test_query, test_model)
    elif provider == "openai":
        response, error = await call_openai(test_content, test_query, test_model)
    else:  # openrouter
        response, error = await call_openrouter(test_content, test_query, test_model)

    if error:
        print(f"\nError: {error}")
        return False

    print(f"\nSuccess! Response from {test_model} ({provider}):")
    print(response)
    return True


def main():
    """Parse command line arguments and run the server."""
    global api_key, provider

    # Simple argument parsing
    args = sys.argv[1:]
    test_mode = False

    # Check for --test flag at the end
    if args and args[-1] == "--test":
        test_mode = True
        args = args[:-1]  # Remove --test from args

    # Validate arguments
    if len(args) < 2:
        print("Error: Missing required arguments")
        print("Usage: consult7 <provider> <api-key> [--test]")
        print()
        print("Providers: openrouter, google, openai")
        print()
        print("Examples:")
        print("  consult7 openrouter sk-or-v1-...")
        print("  consult7 google AIza...")
        print("  consult7 openai sk-proj-...")
        print("  consult7 openrouter sk-or-v1-... --test")
        sys.exit(1)

    if len(args) > 2:
        print(f"Error: Too many arguments. Expected 2, got {len(args)}")
        print("Usage: consult7 <provider> <api-key> [--test]")
        sys.exit(1)

    # Parse provider and api key
    provider = args[0]
    api_key = args[1]

    # Validate provider
    if provider not in ["openrouter", "google", "openai"]:
        print(f"Error: Invalid provider '{provider}'")
        print("Valid providers: openrouter, google, openai")
        sys.exit(1)

    # Create the consultation tool with provider-specific documentation
    create_consultation_tool()

    # Show model examples for the provider
    print("Starting Consult7 MCP Server")
    print(f"Provider: {provider}")
    print("API Key: Set")

    examples = MODEL_EXAMPLES.get(provider, [])
    if examples:
        print(f"\nExample models for {provider}:")
        for example in examples:
            print(f"  - {example}")
        if provider == "openai":
            print("  Note: Include context length with | separator")

    # Run test mode if requested
    if test_mode:
        import asyncio

        success = asyncio.run(test_api_connection())
        sys.exit(0 if success else 1)

    # Normal server mode
    mcp.run()


if __name__ == "__main__":
    main()
