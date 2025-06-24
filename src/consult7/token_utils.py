"""Token estimation and thinking budget utilities for Consult7."""

from typing import Optional

# Token and model constants
TOKEN_SAFETY_FACTOR = 0.9  # Safety buffer for token calculations

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

# Thinking/Reasoning Token Limits by Model
# Easy to update: just add new models here
THINKING_LIMITS = {
    # Google models
    "gemini-2.0-flash-exp": 32_768,
    "gemini-2.0-flash-thinking-exp": 32_768,
    "gemini-2.0-flash-thinking-exp-01-21": 32_768,
    "gemini-2.5-flash": 24_576,
    "gemini-2.5-flash-latest": 24_576,
    "gemini-2.5-flash-lite-preview-06-17": 24_576,  # Flash Lite uses same limit as Flash
    "gemini-2.5-pro": 32_768,
    "gemini-2.5-pro-latest": 32_768,
    # OpenRouter models
    "google/gemini-2.5-flash": 24_576,
    "google/gemini-2.5-flash-lite-preview-06-17": 24_576,  # Flash Lite on OpenRouter
    "google/gemini-2.5-pro": 32_768,
    "anthropic/claude-opus-4": 31_999,  # Actual limit is 31,999, not 32,000
    "anthropic/claude-sonnet-4": 31_999,  # Using same limit for consistency
    # OpenAI models - special marker for effort-based handling
    "openai/gpt-4.1": "effort",
    "openai/gpt-4.1-mini": "effort",
    "openai/gpt-4.1-nano": "effort",
    "openai/o1": "effort",
}


def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in the given text using character-based approximation.

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


def _parse_thinking_suffix(model_name: str) -> tuple[str, bool]:
    """Extract thinking suffix from model name."""
    if "|thinking" in model_name:
        return model_name.replace("|thinking", ""), True
    return model_name, False


def parse_model_thinking(model_spec: str) -> tuple[str, Optional[int]]:
    """Parse model specification to extract model name and optional thinking tokens.

    Examples:
        "gemini-2.5-flash|thinking" -> ("gemini-2.5-flash", None)
        "gemini-2.5-flash|thinking=10000" -> ("gemini-2.5-flash", 10000)
        "gemini-2.5-flash" -> ("gemini-2.5-flash", None)

    Args:
        model_spec: Model specification string

    Returns:
        Tuple of (model_name, thinking_tokens or None)
    """
    # Check for |thinking or |thinking=N suffix
    if "|thinking" in model_spec:
        parts = model_spec.split("|thinking", 1)
        model_name = parts[0]

        # Check if there's a value after |thinking
        if len(parts) > 1 and parts[1].startswith("="):
            try:
                thinking_value = int(parts[1][1:])  # Skip the '='
                return model_name, thinking_value
            except ValueError:
                # Invalid number, treat as no override
                return model_name, None

        # Just |thinking without value
        return model_name, None

    # No thinking suffix
    return model_spec, None


def get_thinking_budget(
    model_name: str, custom_tokens: Optional[int] = None
) -> Optional[int]:
    """Get thinking tokens for a model. Returns None if unknown model without override.

    Args:
        model_name: The model name (without |thinking suffix)
        custom_tokens: Optional user-specified thinking budget

    Returns:
        Thinking token budget or None if model is unknown
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
