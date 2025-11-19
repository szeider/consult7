"""Token estimation and thinking budget utilities for Consult7."""

from typing import Optional
from .constants import DEFAULT_OUTPUT_TOKENS

# Token and model constants
TOKEN_SAFETY_FACTOR = 0.9  # Safety buffer for token calculations

# Thinking/reasoning constants
MAX_REASONING_TOKENS = 31_999  # OpenRouter maximum reasoning cap (actual limit for Anthropic)
FLASH_MAX_THINKING_TOKENS = 24_576  # Google Flash model thinking limit
PRO_MAX_THINKING_TOKENS = 32_768  # Google Pro model thinking limit

# Token estimation constants
CHARS_PER_TOKEN_REGULAR = 3.2  # Characters per token for regular text/code
CHARS_PER_TOKEN_HTML = 2.5  # Characters per token for HTML/XML
TOKEN_ESTIMATION_BUFFER = 1.1  # 10% buffer for token estimation

# Thinking/Reasoning Token Limits by Model - Officially Supported Models Only
THINKING_LIMITS = {
    # OpenAI models - use effort-based reasoning (not token counts)
    "openai/gpt-5.1": "effort",
    # Google Gemini models
    "google/gemini-3-pro-preview": "enabled",  # Uses reasoning.enabled=true
    "google/gemini-2.5-pro": 32_768,
    "google/gemini-2.5-flash": 24_576,
    "google/gemini-2.5-flash-lite": 24_576,
    # Anthropic Claude models
    "anthropic/claude-sonnet-4.5": 31_999,
    "anthropic/claude-opus-4.1": 31_999,
    # X-AI Grok models - TBD (need to test)
    "x-ai/grok-4": 32_000,  # To be confirmed
    "x-ai/grok-4-fast": 32_000,  # To be confirmed
}


def calculate_max_file_size(context_length: int, mode: str, model_name: str) -> tuple[int, int]:
    """Calculate maximum file size in bytes based on model's context window.

    Uses generous limits - lets the API be the final arbiter if context overflows.

    Args:
        context_length: Model's context window in tokens
        mode: Performance mode (fast/mid/think)
        model_name: The model name

    Returns:
        Tuple of (max_total_bytes, max_per_file_bytes)
    """
    # Reserve tokens for output
    output_reserve = DEFAULT_OUTPUT_TOKENS

    # Reserve tokens for reasoning/thinking if applicable
    thinking_budget_value = get_thinking_budget(model_name, mode)

    # Handle different thinking budget types
    if thinking_budget_value == "effort":
        # OpenAI effort-based: reserve ~40% of output budget for reasoning
        thinking_budget = int(output_reserve * 0.4)
    elif thinking_budget_value == "enabled":
        # Gemini 3 Pro: reasoning is dynamic, reserve conservative amount
        thinking_budget = int(output_reserve * 0.3)
    elif thinking_budget_value is not None:
        thinking_budget = thinking_budget_value
    else:
        thinking_budget = 0

    # Calculate available tokens for input files
    # Be generous - let the API reject if truly too much
    available_tokens = context_length - output_reserve - thinking_budget

    # Ensure we have at least some capacity
    available_tokens = max(available_tokens, 10_000)  # Minimum 10k tokens

    # Convert tokens to bytes (approximately 4 bytes per token for code)
    max_total_bytes = available_tokens * 4

    # Per-file limit: generous - 50% of total or 10MB, whichever is smaller
    max_per_file = min(max_total_bytes // 2, 10_000_000)

    return max_total_bytes, max_per_file


def estimate_tokens(text: str) -> int:
    """Estimate tokens in text using character-based approximation.

    Args:
        text: The text to estimate tokens for

    Returns:
        Estimated number of tokens (rounded up)
    """
    # Check if text contains HTML/XML markers
    is_html = "<" in text and ">" in text

    # Use appropriate character-to-token ratio
    chars_per_token = CHARS_PER_TOKEN_HTML if is_html else CHARS_PER_TOKEN_REGULAR

    # Estimate tokens and apply buffer
    base_estimate = len(text) / chars_per_token
    buffered_estimate = base_estimate * TOKEN_ESTIMATION_BUFFER

    return int(buffered_estimate + 0.5)  # Round to nearest integer


def get_thinking_budget(model_name: str, mode: str) -> Optional[int]:
    """Get thinking tokens for a model based on mode.

    Args:
        model_name: The model name
        mode: Performance mode - "fast", "mid", or "think"

    Returns:
        Thinking token budget, "effort" for OpenAI models, "enabled" for Gemini 3 Pro, or None for fast mode
    """
    # Fast mode: no thinking
    if mode == "fast":
        return None

    # Get model's max thinking limit
    limit = THINKING_LIMITS.get(model_name)

    if limit is None:
        # Unknown model - return None to disable thinking
        return None

    # OpenAI models use effort-based reasoning
    if limit == "effort":
        return "effort"

    # Gemini 3 Pro uses enabled=true reasoning
    if limit == "enabled":
        return "enabled"

    # Mid mode: moderate reasoning (50% of max)
    if mode == "mid":
        return limit // 2

    # Think mode: maximum reasoning budget
    if mode == "think":
        return limit

    # Unknown mode - default to fast
    return None
