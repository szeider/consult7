"""Token estimation and thinking budget utilities for Consult7."""

from typing import Optional
from .constants import DEFAULT_OUTPUT_TOKENS

# Token and model constants
TOKEN_SAFETY_FACTOR = 0.9  # Safety buffer for token calculations

# Thinking/reasoning constants
MAX_REASONING_TOKENS = 31_999  # OpenRouter maximum reasoning cap (actual limit for Anthropic)

# Dynamic reasoning allocation ratio (for Gemini 3 "enabled" mode)
DYNAMIC_REASONING_RATIO = 0.50  # Use 50% of model max for dynamic reasoning

# File size limits
MAX_PER_FILE_BYTES = 10_000_000  # 10MB per file limit

# Token estimation constants
CHARS_PER_TOKEN_REGULAR = 3.2  # Characters per token for regular text/code
CHARS_PER_TOKEN_HTML = 2.5  # Characters per token for HTML/XML
TOKEN_ESTIMATION_BUFFER = 1.1  # 10% buffer for token estimation

# Reasoning budget behavior types
# - "from_output": Reasoning tokens consume max_tokens budget (OpenAI, Claude, Grok)
# - "additional": Reasoning tokens are separate from output (Gemini 2.5)
# - "dynamic": Model decides reasoning allocation (Gemini 3)
REASONING_FROM_OUTPUT = "from_output"
REASONING_ADDITIONAL = "additional"
REASONING_DYNAMIC = "dynamic"

# OpenRouter effort level ratios (documented at openrouter.ai/docs/use-cases/reasoning-tokens)
# These represent approximate fraction of max_tokens used for reasoning
EFFORT_RATIOS = {
    "high": 0.80,  # ~80% of max_tokens for reasoning
    "medium": 0.50,  # ~50% of max_tokens for reasoning
    "low": 0.20,  # ~20% of max_tokens for reasoning
}

# Minimum recommended tokens for reasoning models (OpenAI guidance)
MIN_REASONING_BUDGET = 25_000

# Thinking/Reasoning Token Limits by Model - Officially Supported Models Only
THINKING_LIMITS = {
    # OpenAI models - use effort-based reasoning (not token counts)
    "openai/gpt-5.2": "effort",
    # Google Gemini 3 models - use reasoning.enabled=true
    "google/gemini-3-pro-preview": "enabled",
    "google/gemini-3-flash-preview": "enabled",
    # Google Gemini 2.5 models
    "google/gemini-2.5-pro": 32_768,
    "google/gemini-2.5-flash": 24_576,
    # Anthropic Claude models
    "anthropic/claude-sonnet-4.5": 31_999,
    "anthropic/claude-opus-4.5": 31_999,
    # X-AI Grok models - TBD (need to test)
    "x-ai/grok-4": 32_000,  # To be confirmed
    "x-ai/grok-4-fast": 32_000,  # To be confirmed
}

# How each model handles reasoning token allocation
MODEL_REASONING_BEHAVIOR = {
    # OpenAI: reasoning consumes max_tokens, effort-based (can use 50k+ tokens)
    "openai/gpt-5.2": REASONING_FROM_OUTPUT,
    # Anthropic: reasoning consumes max_tokens
    "anthropic/claude-sonnet-4.5": REASONING_FROM_OUTPUT,
    "anthropic/claude-opus-4.5": REASONING_FROM_OUTPUT,
    # Gemini 2.5: reasoning is additional to output
    "google/gemini-2.5-pro": REASONING_ADDITIONAL,
    "google/gemini-2.5-flash": REASONING_ADDITIONAL,
    # Gemini 3: dynamic reasoning allocation
    "google/gemini-3-pro-preview": REASONING_DYNAMIC,
    "google/gemini-3-flash-preview": REASONING_DYNAMIC,
    # Grok: assume similar to OpenAI (reasoning from output)
    "x-ai/grok-4": REASONING_FROM_OUTPUT,
    "x-ai/grok-4-fast": REASONING_FROM_OUTPUT,
}

# Max output tokens by model (from OpenRouter API)
MODEL_MAX_OUTPUT = {
    "openai/gpt-5.2": 128_000,
    "anthropic/claude-sonnet-4.5": 64_000,
    "anthropic/claude-opus-4.5": 32_000,
    "google/gemini-2.5-pro": 65_536,
    "google/gemini-2.5-flash": 65_536,
    "google/gemini-3-pro-preview": 65_536,
    "google/gemini-3-flash-preview": 65_536,
    "x-ai/grok-4": 131_072,
    "x-ai/grok-4-fast": 131_072,
}

# Default max output when model not in table
DEFAULT_MAX_OUTPUT = 32_000


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
    if thinking_budget_value in ("effort_high", "effort_medium"):
        # OpenAI effort-based: use appropriate effort ratio
        effort_key = "high" if thinking_budget_value == "effort_high" else "medium"
        thinking_budget = int(output_reserve * EFFORT_RATIOS[effort_key])
    elif thinking_budget_value in ("enabled_high", "enabled_low"):
        # Gemini 3 Pro: reasoning is dynamic, use dynamic ratio
        thinking_budget = int(output_reserve * DYNAMIC_REASONING_RATIO)
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

    # Per-file limit: generous - 50% of total or max per file, whichever is smaller
    max_per_file = min(max_total_bytes // 2, MAX_PER_FILE_BYTES)

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
        # Return different markers for mid vs think
        return "effort_medium" if mode == "mid" else "effort_high"

    # Gemini 3 Pro uses thinkingLevel (low/high) via reasoning.effort
    if limit == "enabled":
        # Return different markers for mid vs think
        return "enabled_low" if mode == "mid" else "enabled_high"

    # Mid mode: moderate reasoning (50% of max)
    if mode == "mid":
        return limit // 2

    # Think mode: maximum reasoning budget
    if mode == "think":
        return limit

    # Unknown mode - default to fast
    return None


def calculate_reasoning_max_tokens(
    model_name: str,
    mode: str,
    thinking_budget: Optional[int],
    base_output_tokens: int,
) -> int:
    """Calculate appropriate max_tokens for a model in reasoning mode.

    Different models handle reasoning tokens differently:
    - from_output: Reasoning consumes max_tokens (OpenAI effort, Claude, Grok)
    - additional: Reasoning is separate from output (Gemini 2.5)
    - dynamic: Model decides allocation (Gemini 3)

    Args:
        model_name: The model name
        mode: Performance mode ("fast", "mid", "think")
        thinking_budget: The thinking budget value ("effort", "enabled", int, or None)
        base_output_tokens: Base output tokens for non-reasoning responses

    Returns:
        Appropriate max_tokens value for the API call
    """
    # Fast mode or no thinking: use base output tokens
    if mode == "fast" or thinking_budget is None:
        return base_output_tokens

    # Get model's reasoning behavior (default to from_output for unknown models)
    behavior = MODEL_REASONING_BEHAVIOR.get(model_name, REASONING_FROM_OUTPUT)
    model_max = MODEL_MAX_OUTPUT.get(model_name, DEFAULT_MAX_OUTPUT)

    if thinking_budget in ("effort_high", "effort_medium"):
        # OpenAI effort-based: reasoning tokens consume max_tokens budget
        # Formula from OpenRouter docs: max_tokens >= desired_output / (1 - effort_ratio)
        # high (80% reasoning): max_tokens >= 5 × desired_output
        # medium (50% reasoning): max_tokens >= 2 × desired_output
        effort_key = "high" if thinking_budget == "effort_high" else "medium"
        effort_ratio = EFFORT_RATIOS.get(effort_key, 0.50)

        # Calculate: desired_output / (1 - effort_ratio)
        # This ensures enough room for both reasoning AND the actual response
        calculated = int(base_output_tokens / (1 - effort_ratio))

        # Apply minimum recommended budget (OpenAI guidance: 25k+)
        # Cap at model max to avoid API errors
        return min(max(calculated, MIN_REASONING_BUDGET), model_max)

    elif thinking_budget in ("enabled_high", "enabled_low"):
        # Gemini 3 dynamic: model allocates reasoning internally
        # Use dynamic ratio - model handles the split
        return int(model_max * DYNAMIC_REASONING_RATIO)

    elif isinstance(thinking_budget, int):
        # Explicit token budget
        if behavior == REASONING_FROM_OUTPUT:
            # Reasoning comes from max_tokens: need reasoning + response space
            return thinking_budget + base_output_tokens
        elif behavior == REASONING_ADDITIONAL:
            # Reasoning is separate: just need response space
            # (reasoning budget passed separately in API)
            return base_output_tokens
        else:
            # Dynamic or unknown: conservative allocation
            return thinking_budget + base_output_tokens

    # Fallback
    return base_output_tokens
