"""Token estimation and thinking budget utilities for Consult7."""

from typing import Optional
from .constants import DEFAULT_OUTPUT_TOKENS

# Token and model constants
TOKEN_SAFETY_FACTOR = 0.9  # Safety buffer for token calculations

# Thinking/reasoning constants
MAX_REASONING_TOKENS = 31_999  # OpenRouter maximum reasoning cap (actual limit for Anthropic)

# Reasoning headroom: share of the model max output given to adaptive/effort reasoning
DYNAMIC_REASONING_RATIO = 0.50  # Use 50% of model max for dynamic reasoning

# Token estimation constants
CHARS_PER_TOKEN_REGULAR = 3.2  # Characters per token for regular text/code
CHARS_PER_TOKEN_HTML = 2.5  # Characters per token for HTML/XML
TOKEN_ESTIMATION_BUFFER = 1.1  # 10% buffer for token estimation

# Reasoning budget behavior: reasoning tokens consume the max_tokens budget
REASONING_FROM_OUTPUT = "from_output"

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
    # GPT-6 Astra: reasoning is MANDATORY (default effort medium; bare ≈ medium in probes),
    # so the GPT "effort" profile would make mid ≡ fast. Effort honored and monotone
    # (verified low/medium/high/xhigh/max all 200; 33/45/72/105/160 reasoning tokens on a
    # moderate prompt) — reuse the effort_fable profile: fast=default, mid=high, think=xhigh.
    "openai/gpt-6-astra": "effort_fable",
    # GPT-5.6 Sol: OpenRouter honors the effort scale (verified low/med/high/xhigh all 200,
    # reasoning tokens scale 457/516/942 on a hard prompt) — same shape as gpt-5.5.
    "openai/gpt-5.6-sol": "effort",  # legacy
    "openai/gpt-5.5": "effort",  # legacy
    "openai/gpt-5.4": "effort",  # legacy
    "openai/gpt-5.2": "effort",  # legacy
    # Gemini 4 Argon / 3.8 Flash / 3.1 Pro: reasoning mandatory and the bare call already
    # reasons (Argon and 3.8 Flash ≈ medium, 3.1 Pro ≈ high), so leaving fast bare and
    # sending low in mid made mid weaker than fast. effort_gemini sends an effort in every
    # mode: fast=low, mid=medium, think=high. Probed reasoning tokens low/medium/high:
    # Argon 0/450/1.2K (low skips thinking), 3.8 Flash 420/1.1K/2.7K, 3.1 Pro
    # 1.2K/1.7K/4.5K. xhigh is accepted but not above high.
    "google/gemini-4-argon": "effort_gemini",
    "google/gemini-3.8-flash": "effort_gemini",
    "google/gemini-3.1-pro-preview": "effort_gemini",  # legacy
    # Anthropic Claude models
    # Fable 5.1: all five native efforts accepted; honored and monotone from high up
    # (high/xhigh/max = 170/264/431 reasoning tokens); at low/medium/bare it usually skips
    # thinking. Same effort_fable profile as Fable 5 (mid=high, think=xhigh, max unexposed).
    "anthropic/claude-fable-5.1": "effort_fable",
    # Fable 5: OpenRouter DOES honor the native effort scale (verified: low/medium/high/
    # xhigh/max all accepted, unlike Opus 4.8 which is toggle-only). Two productive tiers —
    # max reserved (Anthropic + our token data: overthinking + ~2x reasoning tokens).
    "anthropic/claude-fable-5": "effort_fable",  # legacy
    # Opus 4.8: adaptive thinking only, reasoning.max_tokens/effort ignored — use "toggle"
    "anthropic/claude-opus-4.8": "toggle",
    "anthropic/claude-opus-4.7": "toggle",  # legacy
    "anthropic/claude-opus-4.6": 31_999,  # legacy
    "anthropic/claude-sonnet-4.6": 31_999,
    "anthropic/claude-haiku-4.5": 31_999,
    # Anthropic Claude models (legacy, still valid)
    "anthropic/claude-sonnet-4.5": 31_999,
    "anthropic/claude-opus-4.5": 31_999,
    # X-AI Grok models
    # Grok 4.7: same shape as 4.6 — effort honored low→high (3.3K/4.8K/8.0K reasoning tokens
    # on a moderate prompt), plateau at high/xhigh/max, mandatory reasoning (bare ≈ high).
    "x-ai/grok-4.7": "effort_fable",
    # Grok 4.6: effort honored coarsely (verified low/med/high/xhigh all 200; reasoning
    # tokens 350/412/612/611 on a light prompt, flat on hard ones — adaptive baseline
    # like Fable) — reuse the effort_fable profile (mid=high, think=xhigh, from_output).
    "x-ai/grok-4.6": "effort_fable",  # legacy
    # Grok 4.20: base model accepts reasoning.enabled only, no effort/max_tokens — use "toggle"
    "x-ai/grok-4.20": "toggle",  # legacy (kept: 2M context vs 4.6's 500K)
    "x-ai/grok-4": 32_000,  # legacy
    "x-ai/grok-4.1-fast": 32_000,
    "x-ai/grok-4-fast": 32_000,  # legacy
}

# How each model handles reasoning token allocation
MODEL_REASONING_BEHAVIOR = {
    # OpenAI: reasoning consumes max_tokens, effort-based (can use 50k+ tokens)
    "openai/gpt-6-astra": REASONING_FROM_OUTPUT,
    "openai/gpt-5.6-sol": REASONING_FROM_OUTPUT,  # legacy
    "openai/gpt-5.5": REASONING_FROM_OUTPUT,  # legacy
    "openai/gpt-5.4": REASONING_FROM_OUTPUT,  # legacy
    "openai/gpt-5.2": REASONING_FROM_OUTPUT,  # legacy
    # Anthropic: reasoning consumes max_tokens
    "anthropic/claude-fable-5.1": REASONING_FROM_OUTPUT,
    "anthropic/claude-fable-5": REASONING_FROM_OUTPUT,  # legacy
    "anthropic/claude-opus-4.8": REASONING_FROM_OUTPUT,
    "anthropic/claude-opus-4.7": REASONING_FROM_OUTPUT,  # legacy
    "anthropic/claude-opus-4.6": REASONING_FROM_OUTPUT,  # legacy
    "anthropic/claude-sonnet-4.6": REASONING_FROM_OUTPUT,
    "anthropic/claude-haiku-4.5": REASONING_FROM_OUTPUT,
    "anthropic/claude-sonnet-4.5": REASONING_FROM_OUTPUT,  # legacy
    "anthropic/claude-opus-4.5": REASONING_FROM_OUTPUT,  # legacy
    # Gemini effort_gemini models: completion_tokens include reasoning
    "google/gemini-4-argon": REASONING_FROM_OUTPUT,
    "google/gemini-3.8-flash": REASONING_FROM_OUTPUT,
    "google/gemini-3.1-pro-preview": REASONING_FROM_OUTPUT,  # legacy
    # Grok: reasoning from output
    "x-ai/grok-4.7": REASONING_FROM_OUTPUT,
    "x-ai/grok-4.6": REASONING_FROM_OUTPUT,  # legacy
    "x-ai/grok-4.20": REASONING_FROM_OUTPUT,  # legacy
    "x-ai/grok-4": REASONING_FROM_OUTPUT,  # legacy
    "x-ai/grok-4.1-fast": REASONING_FROM_OUTPUT,
    "x-ai/grok-4-fast": REASONING_FROM_OUTPUT,  # legacy
}

# Max output tokens by model (from OpenRouter API)
MODEL_MAX_OUTPUT = {
    "anthropic/claude-fable-5.1": 128_000,
    "anthropic/claude-fable-5": 128_000,  # legacy
    "openai/gpt-6-astra": 128_000,
    "openai/gpt-5.6-sol": 128_000,  # legacy
    "openai/gpt-5.5": 128_000,  # legacy
    "openai/gpt-5.4": 128_000,  # legacy
    "openai/gpt-5.2": 128_000,  # legacy
    "anthropic/claude-opus-4.8": 128_000,
    "anthropic/claude-opus-4.7": 128_000,  # legacy
    "anthropic/claude-opus-4.6": 32_000,  # legacy
    "anthropic/claude-sonnet-4.6": 64_000,
    "anthropic/claude-haiku-4.5": 16_000,
    "anthropic/claude-sonnet-4.5": 64_000,  # legacy
    "anthropic/claude-opus-4.5": 32_000,  # legacy
    "google/gemini-4-argon": 65_536,
    "google/gemini-3.8-flash": 65_536,
    "google/gemini-3.1-pro-preview": 65_536,  # legacy
    # Grok 4.7 / 4.6: OpenRouter lists 450k max output, but max_tokens also reserves context
    # (openrouter.py: input room = context − max_tokens). 128k keeps the 50% reasoning
    # headroom at 64k, leaving most of the 500k context for input.
    "x-ai/grok-4.7": 128_000,
    "x-ai/grok-4.6": 128_000,  # legacy
    "x-ai/grok-4.20": 128_000,  # OpenRouter API reports null; 128k is a safe practical ceiling
    "x-ai/grok-4": 131_072,  # legacy
    "x-ai/grok-4.1-fast": 131_072,
    "x-ai/grok-4-fast": 131_072,  # legacy
}

# effort_gemini markers (Gemini 4 Argon / 3.8 Flash / 3.1 Pro), sent in fast/mid/think
EFFORT_GEMINI = ("effort_gemini_low", "effort_gemini_medium", "effort_gemini_high")

# Default max output when model not in table
DEFAULT_MAX_OUTPUT = 32_000


def calculate_max_file_size(context_length: int, mode: str, model_name: str) -> int:
    """Calculate the maximum total file size in bytes based on model's context window.

    Uses generous limits - lets the API be the final arbiter if context overflows.
    There is no separate per-file limit: one file may use the whole budget.

    Args:
        context_length: Model's context window in tokens
        mode: Performance mode (fast/mid/think)
        model_name: The model name

    Returns:
        Maximum total bytes for all files together
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
    elif thinking_budget_value == "toggle_on":
        # Opus 4.8 / Grok 4.20: adaptive reasoning, use dynamic ratio
        thinking_budget = int(output_reserve * DYNAMIC_REASONING_RATIO)
    elif thinking_budget_value in ("effort_fable_high", "effort_fable_xhigh") + EFFORT_GEMINI:
        # effort_fable (Fable 5.x / Grok 4.6+ / GPT-6 Astra) and effort_gemini (Gemini 4
        # Argon / 3.8 Flash / 3.1 Pro): effort honored; reasoning consumes output budget — dynamic ratio
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
    return available_tokens * 4


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
        Thinking token budget, a reasoning marker string ("effort_*", "toggle_on"), or None
    """
    # Get model's max thinking limit
    limit = THINKING_LIMITS.get(model_name)

    # Gemini 4 Argon / 3.8 Flash / 3.1 Pro: an explicit effort in every mode, fast included
    if limit == "effort_gemini":
        return {"fast": "effort_gemini_low", "mid": "effort_gemini_medium"}.get(
            mode, "effort_gemini_high"
        )

    # Fast mode: no thinking
    if mode == "fast":
        return None

    if limit is None:
        # Unknown model - return None to disable thinking
        return None

    # OpenAI models use effort-based reasoning
    if limit == "effort":
        # Return different markers for mid vs think
        return "effort_medium" if mode == "mid" else "effort_high"

    # Fable 5.x / Grok 4.6+ / GPT-6 Astra: OpenRouter honors the native effort scale. Two tiers in
    # the productive band (mid=high, think=xhigh); higher levels reserved to avoid
    # overthinking and extra reasoning-token cost.
    if limit == "effort_fable":
        return "effort_fable_high" if mode == "mid" else "effort_fable_xhigh"

    # Claude Opus 4.8 / Grok 4.20: enable reasoning only (adaptive/automatic)
    # reasoning.effort and reasoning.max_tokens are ignored/unsupported
    if limit == "toggle":
        return "toggle_on"

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

    Reasoning tokens consume the max_tokens budget for every tuned model.

    Args:
        model_name: The model name
        mode: Performance mode ("fast", "mid", "think")
        thinking_budget: The thinking budget value (marker string, int, or None)
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

    elif thinking_budget == "toggle_on":
        # Opus 4.8 / Grok 4.20: adaptive/automatic reasoning — no budget knob
        # Reasoning counts toward max_tokens, so give generous headroom
        return int(model_max * DYNAMIC_REASONING_RATIO)

    elif thinking_budget in ("effort_fable_high", "effort_fable_xhigh") + EFFORT_GEMINI:
        # Fable 5.x / Grok 4.6+ / GPT-6 Astra / effort_gemini models: effort honored;
        # reasoning counts toward max_tokens. Generous headroom — 50% of the model ceiling.
        return int(model_max * DYNAMIC_REASONING_RATIO)

    elif isinstance(thinking_budget, int):
        # Explicit token budget
        if behavior == REASONING_FROM_OUTPUT:
            # Reasoning comes from max_tokens: need reasoning + response space
            # Cap at model max to avoid API errors
            return min(thinking_budget + base_output_tokens, model_max)
        else:
            # Dynamic or unknown: conservative allocation
            return thinking_budget + base_output_tokens

    # Fallback
    return base_output_tokens
