"""Consult7 MCP server - Analyze large file collections with AI models."""

import os
import re
import sys
from pathlib import Path
from typing import Optional
import httpx
from mcp.server import Server
import mcp.server.stdio
import mcp.types as types
from mcp.server.models import InitializationOptions
from mcp.server.lowlevel import NotificationOptions

# Provider-specific imports will be done conditionally
try:
    from google import genai
    from google.genai import types as genai_types

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

# Token and model constants
TOKEN_SAFETY_FACTOR = 0.9  # Safety buffer for token calculations
DEFAULT_OUTPUT_TOKENS = 8_000  # Default max output tokens (~300 lines of code)
SMALL_OUTPUT_TOKENS = 4_000  # Output tokens for smaller models
SMALL_MODEL_THRESHOLD = 100_000  # Context size threshold for small models

# Thinking/reasoning constants
MIN_THINKING_TOKENS = 500  # Minimum tokens needed for meaningful thinking
MIN_REASONING_TOKENS = 1_024  # OpenRouter minimum reasoning requirement
MAX_REASONING_TOKENS = (
    31_999  # OpenRouter maximum reasoning cap (actual limit for Anthropic)
)
FLASH_MAX_THINKING_TOKENS = 24_576  # Google Flash model thinking limit
PRO_MAX_THINKING_TOKENS = 32_768  # Google Pro model thinking limit

# Token estimation constants
CHARS_PER_TOKEN_REGULAR = 3.2  # Characters per token for regular text/code
CHARS_PER_TOKEN_HTML = 2.5  # Characters per token for HTML/XML
TOKEN_ESTIMATION_BUFFER = 1.1  # 10% buffer for token estimation

# API constants
DEFAULT_TEMPERATURE = 0.7  # Default temperature for all providers
OPENROUTER_TIMEOUT = 30.0  # Timeout for OpenRouter API calls
API_FETCH_TIMEOUT = 10.0  # Timeout for fetching model info
DEFAULT_CONTEXT_LENGTH = 128_000  # Default context when not available from API

# Application constants
SERVER_VERSION = "1.2.1"
EXIT_SUCCESS = 0
EXIT_FAILURE = 1
MIN_ARGS = 2

# Test models for each provider
TEST_MODELS = {
    "openrouter": "google/gemini-2.5-flash-preview-05-20",
    "google": "gemini-2.0-flash-exp",
    "openai": "gpt-4o-mini|128k",
}

# Thinking/Reasoning Token Limits by Model
# Easy to update: just add new models here
THINKING_LIMITS = {
    # Google models
    "gemini-2.0-flash-exp": 32_768,
    "gemini-2.0-flash-thinking-exp": 32_768,
    "gemini-2.0-flash-thinking-exp-01-21": 32_768,
    "gemini-2.5-flash": 24_576,
    "gemini-2.5-flash-latest": 24_576,
    "gemini-2.5-pro": 32_768,
    "gemini-2.5-pro-latest": 32_768,
    # OpenRouter models
    "google/gemini-2.5-flash": 24_576,
    "google/gemini-2.5-pro": 32_768,
    "anthropic/claude-opus-4": 31_999,  # Actual limit is 31,999, not 32,000
    "anthropic/claude-sonnet-4": 31_999,  # Using same limit for consistency
    # OpenAI models - special marker for effort-based handling
    "openai/gpt-4.1": "effort",
    "openai/gpt-4.1-mini": "effort",
    "openai/gpt-4.1-nano": "effort",
    "openai/o1": "effort",
}


# ==============================================================================
# TOOL DESCRIPTIONS - Centralized class for managing tool descriptions
# ==============================================================================
class ToolDescriptions:
    """Centralized management of tool descriptions and model examples."""

    MODEL_EXAMPLES = {
        "openrouter": [
            '"google/gemini-2.5-pro" (intelligent, 1M context)',
            '"google/gemini-2.5-flash" (fast, 1M context)',
            '"anthropic/claude-sonnet-4" (Claude Sonnet, 200k context)',
            '"openai/gpt-4.1" (GPT-4.1, 1M+ context)',
            '"anthropic/claude-sonnet-4|thinking" (Claude with 31,999 tokens)',
            '"openai/gpt-4.1|thinking" (GPT-4.1 with reasoning effort=high)',
        ],
        "google": [
            '"gemini-2.5-flash" (fast, standard mode)',
            '"gemini-2.5-pro" (intelligent, standard mode)',
            '"gemini-2.0-flash-exp" (experimental model)',
            '"gemini-2.5-flash|thinking" (fast with deep reasoning)',
            '"gemini-2.5-pro|thinking" (intelligent with deep reasoning)',
        ],
        "openai": [
            '"gpt-4.1-2025-04-14|1047576" (1M+ context, very fast)',
            '"gpt-4.1-nano-2025-04-14|1047576" (1M+ context, ultra fast)',
            '"o3-2025-04-16|200k" (advanced reasoning model)',
            '"o4-mini-2025-04-16|200k" (fast reasoning model)',
            '"o1-mini|128k|thinking" (mini reasoning with |thinking marker)',
            '"o3-2025-04-16|200k|thinking" (advanced reasoning with |thinking marker)',
        ],
    }

    @classmethod
    def get_consultation_tool_description(cls, provider: str) -> str:
        """Get the main description for the consultation tool."""
        provider_notes = cls._get_provider_notes(provider)

        return f"""Consult an LLM about code files matching a pattern in a directory.

This tool collects all files matching a regex pattern from a directory tree,
formats them into a structured document, and sends them to an LLM along with
your query. The LLM analyzes the code and returns insights.

{provider_notes}

Notes:
- Automatically ignores: __pycache__, .env, secrets.py, .DS_Store, .git, node_modules
- File size limit: 10MB per file, 100MB total (optimized for large context models)
- Large files are skipped with an error message
- Includes detailed errors for debugging (permissions, missing paths, etc.)"""

    @classmethod
    def get_model_parameter_description(cls, provider: str) -> str:
        """Get the model parameter description with provider-specific examples."""
        examples = cls.MODEL_EXAMPLES.get(provider, [])

        if provider == "openai":
            model_desc = ('The model to use. Include context length with | '
                         'separator (e.g., "model-name|200k").\nExamples:')
        else:
            model_desc = "The model to use. Examples:"

        # Add examples on new lines, but check where to add |thinking note
        thinking_examples_start = -1
        for i, example in enumerate(examples):
            if "|thinking" in example and thinking_examples_start == -1:
                thinking_examples_start = i
                # Add the |thinking note before the first thinking example
                if provider in ["google", "openrouter"]:
                    suffix_type = "thinking" if provider == "google" else "reasoning"
                    model_desc += f"\n\nAdd |thinking suffix for {suffix_type} mode:"
                elif provider == "openai":
                    model_desc += "\n\n|thinking suffix (o-series models only):"
            model_desc += f"\n  {example}"

        return model_desc

    @classmethod
    def get_path_description(cls) -> str:
        """Get the path parameter description."""
        return "Absolute filesystem path to search from (e.g., /Users/john/myproject)"

    @classmethod
    def get_pattern_description(cls) -> str:
        """Get the pattern parameter description."""
        return ('Regex to match filenames. Common patterns: ".*\\.py$" for '
                'Python files, ".*\\.(js|ts)$" for JavaScript/TypeScript')

    @classmethod
    def get_query_description(cls) -> str:
        """Get the query parameter description."""
        return "Your question about the code (e.g., 'Which functions handle authentication?')"

    @classmethod
    def get_exclude_pattern_description(cls) -> str:
        """Get the exclude_pattern parameter description."""
        return 'Optional regex to exclude files (e.g., ".*test.*" to skip tests)'

    @classmethod
    def _get_provider_notes(cls, provider: str) -> str:
        """Get provider-specific notes."""
        if provider == "openai":
            return ""  # Move note to model parameter description
        elif provider == "google":
            return (
                "Thinking Mode: Add |thinking to any model for deep reasoning (e.g., gemini-2.5-flash|thinking).\n"
                "Advanced: For custom thinking limits, use |thinking=30000"
            )
        elif provider == "openrouter":
            return (
                "Reasoning Mode: Add |thinking suffix to enable deeper analysis.\n"
                "Advanced: For custom limits, use |thinking=30000"
            )
        else:
            return "Note: Model context windows are auto-detected from the API"


# ==============================================================================

# Model context limits (updated dynamically)
model_context_length = None

# Global variables for CLI args (will be set in main)
api_key = None
provider = "openrouter"  # default provider


def _process_llm_response(response_content: Optional[str]) -> str:
    """Process LLM response: handle None and truncate if needed."""
    if response_content is None:
        response_content = ""

    if len(response_content) > MAX_RESPONSE_SIZE:
        response_content = (
            response_content[:MAX_RESPONSE_SIZE]
            + "\n[TRUNCATED - Response exceeded size limit]"
        )

    return response_content


def _parse_thinking_suffix(model_name: str) -> tuple[str, bool]:
    """Parse model name and check for |thinking suffix."""
    if "|thinking" in model_name:
        return model_name.split("|")[0], True
    return model_name, False


def parse_model_thinking(model_spec: str) -> tuple[str, Optional[int]]:
    """
    Parse model|thinking or model|thinking=12345.
    Returns (model_name, custom_thinking_tokens or None)
    """
    if "|thinking" not in model_spec:
        return model_spec, None

    parts = model_spec.split("|thinking")
    model_name = parts[0]

    # Check for =value after |thinking
    if len(parts) > 1 and parts[1].startswith("="):
        try:
            custom_tokens = int(parts[1][1:])
            # Validate the custom value
            if custom_tokens < 0:
                return model_name, None  # Negative values disable thinking
            return model_name, custom_tokens
        except ValueError:
            # Invalid number, ignore the override
            pass

    # Just |thinking without =value
    return model_name, None


def get_thinking_budget(
    model_name: str, custom_tokens: Optional[int] = None
) -> Optional[int]:
    """
    Get thinking tokens for a model. Returns None if unknown model without override.
    """
    if custom_tokens is not None:
        return custom_tokens

    # Exact match in dictionary
    if model_name in THINKING_LIMITS:
        return THINKING_LIMITS[model_name]

    # Try without provider prefix (for OpenRouter models)
    if "/" in model_name:
        base_model = model_name.split("/", 1)[1]
        if base_model in THINKING_LIMITS:
            return THINKING_LIMITS[base_model]

    # Unknown model without override - return None to disable thinking
    return None


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
        base_estimate = len(text) / CHARS_PER_TOKEN_HTML
    else:
        # Regular text/code
        base_estimate = len(text) / CHARS_PER_TOKEN_REGULAR

    # Add safety buffer
    return int(base_estimate * TOKEN_ESTIMATION_BUFFER)


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
            response = await client.get(
                MODELS_URL, headers=headers, timeout=API_FETCH_TIMEOUT
            )

            if response.status_code != 200:
                print(f"Warning: Could not fetch model info: {response.status_code}")
                return None

            models = response.json().get("data", [])
            for model_info in models:
                if model_info.get("id") == model_name:
                    # Return in consistent format
                    return {
                        "context_length": model_info.get(
                            "context_length", DEFAULT_CONTEXT_LENGTH
                        ),
                        "max_output_tokens": model_info.get(
                            "max_completion_tokens", SMALL_OUTPUT_TOKENS
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
            parts = model_name.split("|")
            actual_model_name = parts[0]

            # Check if we have context specification
            # It should be in parts[1] and not be "thinking"
            if len(parts) >= 2 and parts[1] and parts[1] != "thinking":
                context_str = parts[1]
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
                "max_output_tokens": DEFAULT_OUTPUT_TOKENS,  # Use our standard output allocation
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
        model_context_length = DEFAULT_CONTEXT_LENGTH
        return {"context_length": DEFAULT_CONTEXT_LENGTH, "provider": provider}

    except ValueError:
        # Re-raise ValueError to be caught by caller
        raise
    except Exception as e:
        print(f"Error getting model info: {e}")
        model_context_length = DEFAULT_CONTEXT_LENGTH
        return {"context_length": DEFAULT_CONTEXT_LENGTH, "provider": provider}


async def call_google(
    content: str, query: str, model_name: str
) -> tuple[str, Optional[str], Optional[int]]:
    """
    Call Google AI API with the content and query.
    Returns (response, error, thinking_budget)
    """
    if not GOOGLE_AVAILABLE:
        return (
            "",
            "Google AI SDK not available. Install with: pip install google-genai",
            None,
        )

    if not api_key:
        return "", "No API key provided. Use --api-key flag", None

    # Parse model and thinking override
    actual_model, custom_thinking = parse_model_thinking(model_name)
    thinking_mode = custom_thinking is not None or model_name.endswith("|thinking")

    # Get model context info
    try:
        model_info = await get_model_context_info(actual_model)
        context_length = model_info.get("context_length", DEFAULT_CONTEXT_LENGTH)
    except ValueError as e:
        return "", str(e), None

    # Estimate tokens for the input
    system_msg = "You are a helpful assistant analyzing code and files. Be concise and specific in your responses."
    user_msg = f"Here are the files to analyze:\n\n{content}\n\nQuery: {query}"
    total_input = system_msg + user_msg
    estimated_tokens = estimate_tokens(total_input)

    # Fixed output token limit
    max_output_tokens = DEFAULT_OUTPUT_TOKENS

    # Binary approach for thinking mode - reserve full amount upfront
    thinking_budget = 0
    unknown_model_msg = ""
    if thinking_mode:
        thinking_budget = get_thinking_budget(actual_model, custom_thinking)

        # If unknown model without override, disable thinking and add note
        if thinking_budget is None:
            thinking_mode = False
            thinking_budget = 0
            unknown_model_msg = f"\nNote: Unknown model '{actual_model}' requires thinking=X parameter for thinking mode. Example: {actual_model}|thinking=30000"

    # Calculate available input space with thinking reserved upfront
    available_for_input = int(
        (context_length - max_output_tokens - thinking_budget) * TOKEN_SAFETY_FACTOR
    )

    # Check against adjusted limit
    if estimated_tokens > available_for_input:
        if thinking_mode:
            # Check if it would fit without thinking
            available_without_thinking = int(
                (context_length - max_output_tokens) * TOKEN_SAFETY_FACTOR
            )
            if estimated_tokens > available_without_thinking:
                # Too large even without thinking
                return (
                    "",
                    (
                        f"Content too large for model: ~{estimated_tokens:,} tokens estimated, "
                        f"but model {actual_model} has only ~{available_without_thinking:,} tokens available "
                        f"even without thinking mode "
                        f"(context: {context_length:,}, output: {max_output_tokens:,}). "
                        f"Try reducing file count/size or using a model with larger context."
                    ),
                    0,
                )
            else:
                # Only too large because of thinking
                return (
                    "",
                    (
                        f"Content too large for thinking mode: ~{estimated_tokens:,} tokens estimated, "
                        f"but only ~{available_for_input:,} tokens available with thinking "
                        f"(~{available_without_thinking:,} available without thinking). "
                        f"Context: {context_length:,}, output: {max_output_tokens:,}, thinking: {thinking_budget:,}. "
                        f"Try without |thinking suffix."
                    ),
                    0,
                )
        else:
            return (
                "",
                (
                    f"Content too large: ~{estimated_tokens:,} tokens estimated, "
                    f"but model {model_name} has only ~{available_for_input:,} tokens available for input "
                    f"(total limit: {context_length:,}, reserved for output: {max_output_tokens:,}). "
                    f"Try reducing file count/size."
                ),
                0,
            )

    try:
        client = genai.Client(api_key=api_key)

        # Build config
        config_params = {
            "max_output_tokens": max_output_tokens,
            "temperature": DEFAULT_TEMPERATURE,
        }

        # Add thinking config if |thinking suffix was used
        if thinking_mode:
            # Google API uses specific values:
            # -1 = dynamic thinking (model decides)
            # 0 = disable thinking (for Flash/Flash Lite)
            # positive = specific budget
            # For now, we use the full budget when |thinking is specified
            config_params["thinking_config"] = genai_types.ThinkingConfig(
                thinking_budget=thinking_budget  # Use calculated budget
            )

        response = await client.aio.models.generate_content(
            model=actual_model,
            contents=f"{system_msg}\n\n{user_msg}",
            config=genai_types.GenerateContentConfig(**config_params),
        )

        llm_response = _process_llm_response(response.text)

        # Add unknown model message if applicable
        if unknown_model_msg:
            llm_response = llm_response + unknown_model_msg

        # Return thinking budget (None for normal mode, value for thinking mode)
        return llm_response, None, thinking_budget if thinking_mode else None

    except Exception as e:
        error_msg = f"Error calling Google AI: {str(e)}"
        # Add unknown model message if applicable
        if unknown_model_msg and "not found" in str(e).lower():
            error_msg += unknown_model_msg
        return "", error_msg, None


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

    # Parse model name for thinking mode
    parts = model_name.split("|") if "|" in model_name else [model_name]
    actual_model_name = parts[0]
    has_thinking = "thinking" in parts

    # Check if this is an o-series model that supports reasoning
    is_reasoning_model = any(x in actual_model_name.lower() for x in ["o1", "o3", "o4"])

    # Get model context info (including parsed context from model|context format)
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
    max_output_tokens = model_info.get("max_output_tokens", DEFAULT_OUTPUT_TOKENS)
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

        # Build parameters
        # o-series models don't support system messages
        if any(x in actual_model_name.lower() for x in ["o1", "o3", "o4"]):
            messages = [
                {"role": "user", "content": f"{system_msg}\n\n{user_msg}"},
            ]
        else:
            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ]

        # Build base parameters
        params = {
            "model": actual_model_name,
            "messages": messages,
        }

        # o-series models have different parameter requirements
        if any(x in actual_model_name.lower() for x in ["o1", "o3", "o4"]):
            params["max_completion_tokens"] = DEFAULT_OUTPUT_TOKENS
            # o-series models only support temperature=1
        else:
            params["max_tokens"] = DEFAULT_OUTPUT_TOKENS
            params["temperature"] = DEFAULT_TEMPERATURE

        # Note: o-series models automatically use reasoning tokens internally
        # The API doesn't support reasoning_effort parameter in SDK 1.88.0
        # But usage stats will show reasoning_tokens in the response

        response = await client.chat.completions.create(**params)

        llm_response = _process_llm_response(response.choices[0].message.content)

        # Add note about thinking mode if used
        if has_thinking:
            if is_reasoning_model:
                llm_response += "\n\n[Note: o-series models use reasoning tokens automatically. The |thinking suffix is informational - use OpenRouter for effort control.]"
            else:
                llm_response += f"\n\n[Note: |thinking not supported for {actual_model_name}. Only o-series models support reasoning.]"

        return llm_response, None

    except Exception as e:
        return "", f"Error calling OpenAI: {str(e)}"


async def call_openrouter(
    content: str, query: str, model_name: str
) -> tuple[str, Optional[str], Optional[int]]:
    """
    Call OpenRouter API with the content and query.
    Returns (response, error, reasoning_budget)
    """
    if not api_key:
        return "", "No API key provided. Use --api-key flag", None

    # Parse model and thinking override
    actual_model, custom_thinking = parse_model_thinking(model_name)
    reasoning_mode = custom_thinking is not None or model_name.endswith("|thinking")

    # Get model context info
    try:
        model_info = await get_model_context_info(actual_model)
        context_length = model_info.get("context_length", 128000)
    except ValueError as e:
        return "", str(e), None

    # Estimate tokens for the input
    system_msg = "You are a helpful assistant analyzing code and files. Be concise and specific in your responses."
    user_msg = f"Here are the files to analyze:\n\n{content}\n\nQuery: {query}"
    total_input = system_msg + user_msg
    estimated_tokens = estimate_tokens(total_input)

    # Fixed output token limit for initial calculation
    base_max_output_tokens = (
        DEFAULT_OUTPUT_TOKENS
        if context_length > SMALL_MODEL_THRESHOLD
        else SMALL_OUTPUT_TOKENS
    )
    max_output_tokens = base_max_output_tokens

    # Binary approach for reasoning mode - reserve full amount upfront
    reasoning_budget = 0
    unknown_model_msg = ""
    is_openai_model = any(x in actual_model.lower() for x in ["gpt-4", "o1", "openai"])

    if reasoning_mode:
        # Check if it's an OpenAI model that uses effort levels
        limit_value = get_thinking_budget(actual_model, custom_thinking)

        if limit_value == "effort":
            # OpenAI models use effort levels, not token counts
            is_openai_model = True
            # For OpenAI models, reasoning uses part of the output budget
            # We don't increase max_output_tokens
            reasoning_budget = 0  # Signal that we're using effort mode
        else:
            # Non-OpenAI models: get reasoning budget
            reasoning_budget = limit_value

            # If unknown model without override, disable reasoning and add note
            if reasoning_budget is None:
                reasoning_mode = False
                reasoning_budget = 0
                unknown_model_msg = f"\nNote: Unknown model '{actual_model}' requires thinking=X parameter for reasoning mode. Example: {actual_model}|thinking=30000"
            else:
                # For Anthropic models, reasoning tokens come FROM max_tokens, not in addition
                # For other models (Gemini), they're additional
                if "anthropic" in actual_model.lower():
                    # Anthropic: ensure max_tokens > reasoning_budget
                    # We need at least reasoning_budget + some tokens for the actual response
                    max_output_tokens = (
                        reasoning_budget + 2000
                    )  # 2k for actual response
                else:
                    # Gemini and others: reasoning is additional to output
                    max_output_tokens = DEFAULT_OUTPUT_TOKENS + reasoning_budget

    # Calculate available input space with reasoning reserved upfront
    available_for_input = int(
        (context_length - max_output_tokens) * TOKEN_SAFETY_FACTOR
    )

    # Check against adjusted limit
    if estimated_tokens > available_for_input:
        if reasoning_mode:
            # Check if it would fit without reasoning
            available_without_reasoning = int(
                (context_length - DEFAULT_OUTPUT_TOKENS) * TOKEN_SAFETY_FACTOR
            )
            if estimated_tokens > available_without_reasoning:
                # Too large even without reasoning
                return (
                    "",
                    (
                        f"Content too large for model: ~{estimated_tokens:,} tokens estimated, "
                        f"but model {actual_model} has only ~{available_without_reasoning:,} tokens available "
                        f"even without reasoning mode "
                        f"(context: {context_length:,}, output: {DEFAULT_OUTPUT_TOKENS:,}). "
                        f"Try reducing file count/size or using a model with larger context."
                    ),
                    0,
                )
            else:
                # Only too large because of reasoning
                return (
                    "",
                    (
                        f"Content too large for reasoning mode: ~{estimated_tokens:,} tokens estimated, "
                        f"but only ~{available_for_input:,} tokens available with reasoning "
                        f"(~{available_without_reasoning:,} available without reasoning). "
                        f"Context: {context_length:,}, output: {DEFAULT_OUTPUT_TOKENS:,}, reasoning: {reasoning_budget:,}. "
                        f"Try without |thinking suffix."
                    ),
                    0,
                )
        else:
            return (
                "",
                (
                    f"Content too large: ~{estimated_tokens:,} tokens estimated, "
                    f"but model {model_name} has only ~{available_for_input:,} tokens available for input "
                    f"(total limit: {context_length:,}, reserved for output: {max_output_tokens:,}). "
                    f"Try using a model with larger context or reducing file count/size."
                ),
                0,
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
        "model": actual_model,
        "messages": messages,
        "temperature": DEFAULT_TEMPERATURE,
        "max_tokens": max_output_tokens,
    }

    # Add reasoning mode if |thinking suffix was used
    if reasoning_mode:
        if is_openai_model:
            # OpenAI models: use effort level
            data["reasoning"] = {"effort": "high"}
            # Note: This uses ~80% of the 8k output budget for reasoning
            # Total context reduction is still just 8k (not additional)
        else:
            # Anthropic, Gemini, and others: use max_tokens
            data["reasoning"] = {"max_tokens": reasoning_budget}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                OPENROUTER_URL, headers=headers, json=data, timeout=OPENROUTER_TIMEOUT
            )

            if response.status_code != 200:
                return "", f"API error: {response.status_code} - {response.text}", None

            result = response.json()

            if "choices" not in result or not result["choices"]:
                return "", f"Unexpected API response format: {result}", None

            llm_response = _process_llm_response(
                result["choices"][0]["message"]["content"]
            )

            # Add unknown model message if applicable
            if unknown_model_msg:
                llm_response = llm_response + unknown_model_msg

            # Return reasoning budget (for OpenAI effort models, return a special value)
            if reasoning_mode and is_openai_model:
                return (
                    llm_response,
                    None,
                    -1,
                )  # Special marker for effort-based reasoning
            else:
                return llm_response, None, reasoning_budget if reasoning_mode else None

    except httpx.TimeoutException:
        return "", f"Request timed out after {OPENROUTER_TIMEOUT} seconds", None
    except Exception as e:
        return "", f"Error calling API: {e}", None


async def consultation_impl(
    path: str,
    pattern: str,
    query: str,
    model: str,
    exclude_pattern: Optional[str] = None,
) -> str:
    """Implementation of the consultation tool logic."""
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
    # For OpenAI, we need to preserve the context specification
    if provider == "openai" and "|" in model:
        # Keep model|context but remove |thinking if present
        parts = model.split("|")
        if len(parts) >= 2 and parts[-1] == "thinking":
            # Remove only the thinking part
            model_for_info = "|".join(parts[:-1])
        else:
            model_for_info = model
    else:
        # For other providers, just strip everything after first |
        model_for_info = model.split("|")[0] if "|" in model else model

    try:
        model_info = await get_model_context_info(model_for_info)
        model_context_length = model_info.get("context_length", DEFAULT_CONTEXT_LENGTH)
    except ValueError as e:
        return f"Error: {str(e)}"

    # Estimate tokens
    full_content = content + size_info
    estimated_tokens = estimate_tokens(full_content)
    token_info = f"\nEstimated tokens: ~{estimated_tokens:,}"
    if model_context_length:
        token_info += f" (Model limit: {model_context_length:,} tokens)"

    # Call appropriate LLM based on provider
    thinking_budget = None
    if provider == "google":
        response, error, thinking_budget = await call_google(
            content + size_info, query, model
        )
    elif provider == "openai":
        response, error = await call_openai(content + size_info, query, model)
    else:  # openrouter (default)
        response, error, thinking_budget = await call_openrouter(
            content + size_info, query, model
        )

    # Add thinking/reasoning budget info if applicable (even for errors)
    if thinking_budget is not None:
        budget_type = "thinking" if provider == "google" else "reasoning"
        if thinking_budget == -1:
            # Special marker for OpenAI effort-based reasoning
            token_info += f", {budget_type} mode: effort=high (~80% of output budget)"
        elif thinking_budget > 0:
            # Calculate percentage of maximum possible thinking
            max_thinking = (
                FLASH_MAX_THINKING_TOKENS
                if "flash" in model.lower()
                else PRO_MAX_THINKING_TOKENS
            )
            if provider == "openrouter":
                # OpenRouter has model-specific limits
                if "gemini" in model.lower() and "flash" in model.lower():
                    max_thinking = FLASH_MAX_THINKING_TOKENS  # 24,576
                else:
                    max_thinking = MAX_REASONING_TOKENS  # 32,000
            percentage = (thinking_budget / max_thinking) * 100
            token_info += f", {budget_type} budget: {thinking_budget:,} tokens ({percentage:.1f}% of max)"
        else:
            token_info += f", {budget_type} disabled (insufficient context)"

    if error:
        return f"Error calling {provider} LLM: {error}\n\nCollected {len(files)} files ({total_size:,} bytes){token_info}"

    # Add size info to response for agent awareness
    return f"{response}\n\n---\nProcessed {len(files)} files ({total_size:,} bytes) with {model} ({provider}){token_info}"


async def test_api_connection():
    """Test the API connection with a simple query."""
    print(f"\nTesting {provider} API connection...")
    print(f"API Key: {'Set' if api_key else 'Not set'}")

    if not api_key:
        print("\nError: No API key provided!")
        print("Use --api-key flag")
        return False

    # Use a default test model for each provider
    test_model = TEST_MODELS.get(provider, TEST_MODELS["openrouter"])

    # Simple test query
    test_content = "This is a test file with sample content."
    test_query = "Reply with 'API test successful' if you can read this."

    # Call appropriate provider
    if provider == "google":
        response, error, _ = await call_google(test_content, test_query, test_model)
    elif provider == "openai":
        response, error = await call_openai(test_content, test_query, test_model)
    else:  # openrouter
        response, error, _ = await call_openrouter(test_content, test_query, test_model)

    if error:
        print(f"\nError: {error}")
        return False

    print(f"\nSuccess! Response from {test_model} ({provider}):")
    print(response)
    return True


async def main():
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
    if len(args) < MIN_ARGS:
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
        sys.exit(EXIT_FAILURE)

    if len(args) > MIN_ARGS:
        print(f"Error: Too many arguments. Expected {MIN_ARGS}, got {len(args)}")
        print("Usage: consult7 <provider> <api-key> [--test]")
        sys.exit(EXIT_FAILURE)

    # Parse provider and api key
    provider = args[0]
    api_key = args[1]

    # Validate provider
    if provider not in ["openrouter", "google", "openai"]:
        print(f"Error: Invalid provider '{provider}'")
        print("Valid providers: openrouter, google, openai")
        sys.exit(1)

    # Create server
    server = Server("consult7")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        """List available tools with provider-specific model examples."""
        return [
            types.Tool(
                name="consultation",
                description=ToolDescriptions.get_consultation_tool_description(
                    provider
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": ToolDescriptions.get_path_description(),
                        },
                        "pattern": {
                            "type": "string",
                            "description": ToolDescriptions.get_pattern_description(),
                        },
                        "query": {
                            "type": "string",
                            "description": ToolDescriptions.get_query_description(),
                        },
                        "model": {
                            "type": "string",
                            "description": ToolDescriptions.get_model_parameter_description(
                                provider
                            ),
                        },
                        "exclude_pattern": {
                            "type": "string",
                            "description": ToolDescriptions.get_exclude_pattern_description(),
                        },
                    },
                    "required": ["path", "pattern", "query", "model"],
                },
            )
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        """Handle tool calls."""
        if name == "consultation":
            result = await consultation_impl(
                arguments["path"],
                arguments["pattern"],
                arguments["query"],
                arguments["model"],
                arguments.get("exclude_pattern"),
            )
            return [types.TextContent(type="text", text=result)]
        else:
            raise ValueError(f"Unknown tool: {name}")

    # Show model examples for the provider
    print("Starting Consult7 MCP Server")
    print(f"Provider: {provider}")
    print("API Key: Set")

    examples = ToolDescriptions.MODEL_EXAMPLES.get(provider, [])
    if examples:
        print(f"\nExample models for {provider}:")
        for example in examples:
            print(f"  - {example}")
        if provider == "openai":
            print("  Note: Include context length with | separator")

    # Run test mode if requested
    if test_mode:
        success = await test_api_connection()
        sys.exit(EXIT_SUCCESS if success else EXIT_FAILURE)

    # Normal server mode
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="consult7",
                server_version=SERVER_VERSION,
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def run():
    """Entry point for the consult7 command."""
    import asyncio

    asyncio.run(main())


if __name__ == "__main__":
    run()
