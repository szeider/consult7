"""Main consultation orchestration logic for Consult7."""

import asyncio
import logging
from typing import Optional

from .constants import DEFAULT_CONTEXT_LENGTH, LLM_CALL_TIMEOUT
from .file_processor import discover_files, format_content
from .token_utils import estimate_tokens, parse_model_thinking
from .providers import PROVIDERS

logger = logging.getLogger("consult7")


async def get_model_context_info(
    model_name: str, provider: str, api_key: str
) -> Optional[dict]:
    """Get model context information based on provider and model."""
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

        # Get provider instance
        provider_instance = PROVIDERS.get(provider)
        if not provider_instance:
            logger.warning(f"Unknown provider '{provider}'")
            return {"context_length": DEFAULT_CONTEXT_LENGTH, "provider": provider}

        # Handle OpenAI special case
        if provider == "openai":
            # OpenAI requires context to be specified
            if not specified_context:
                raise ValueError(
                    f"OpenAI models require context length specification. Use format: '{actual_model_name}|128k' or '{actual_model_name}|200000'"
                )
            info = {
                "context_length": specified_context,
                "max_output_tokens": 8000,  # Use standard output allocation
                "provider": "openai",
            }
        else:
            # Get model info from provider
            info = await provider_instance.get_model_info(actual_model_name, api_key)

        if info and "context_length" in info:
            return info

        # Fallback to default if no info available
        logger.warning(
            f"Could not determine context length for {model_name}, using default of 128k tokens"
        )
        return {"context_length": DEFAULT_CONTEXT_LENGTH, "provider": provider}

    except ValueError:
        # Re-raise ValueError to be caught by caller
        raise
    except Exception as e:
        logger.error(f"Error getting model info: {e}")
        return {"context_length": DEFAULT_CONTEXT_LENGTH, "provider": provider}


async def consultation_impl(
    path: str,
    pattern: str,
    query: str,
    model: str,
    exclude_pattern: Optional[str] = None,
    provider: str = "openrouter",
    api_key: str = None,
) -> str:
    """Implementation of the consultation tool logic."""
    # Discover files
    files, errors = discover_files(path, pattern, exclude_pattern)

    if not files and errors:
        return "Error: No files found. Errors:\n" + "\n".join(errors)

    # Provide immediate feedback about what was found
    if not files:
        return "No files matching the pattern were found."

    # Format content
    content, total_size = format_content(path, files, errors)

    # Get model info (strip |thinking suffix if present, but keep context for OpenAI)
    if provider == "openai" and "|" in model:
        # For OpenAI, we need to preserve the context specification
        parts = model.split("|")
        if len(parts) >= 3 and parts[2] == "thinking":
            # Format: model|context|thinking
            model_for_info = "|".join(parts[:2])
        elif len(parts) == 2 and parts[1] != "thinking":
            # Format: model|context
            model_for_info = model
        else:
            # Format: model|thinking (invalid for OpenAI)
            model_for_info = parts[0]
    else:
        # For other providers, strip |thinking suffix
        model_for_info = model.split("|")[0] if "|" in model else model
    try:
        model_info = await get_model_context_info(model_for_info, provider, api_key)
        model_context_length = model_info.get("context_length", DEFAULT_CONTEXT_LENGTH)
    except ValueError as e:
        # OpenAI context specification error
        return f"Error: {e}"

    # Add size info that will be part of the query
    size_info = (
        f"\n\n---\nTotal content size: {total_size:,} bytes from {len(files)} files"
    )

    # Estimate tokens for the full input
    full_content = content + size_info + f"\n\nQuery: {query}"
    estimated_tokens = estimate_tokens(full_content)
    token_info = f"\nEstimated tokens: ~{estimated_tokens:,}"
    if model_context_length:
        token_info += f" (Model limit: {model_context_length:,} tokens)"

    # Call appropriate LLM based on provider
    thinking_budget = None
    provider_instance = PROVIDERS.get(provider)
    if not provider_instance:
        return f"Error: Unknown provider '{provider}'"

    # Parse thinking mode
    actual_model, custom_thinking = parse_model_thinking(model)
    thinking_mode = custom_thinking is not None or model.endswith("|thinking")

    # Call the provider with timeout protection
    try:
        async with asyncio.timeout(LLM_CALL_TIMEOUT):
            response, error, thinking_budget = await provider_instance.call_llm(
                content + size_info,
                query,
                model,
                api_key,
                thinking_mode,
                custom_thinking,
            )
    except asyncio.TimeoutError:
        return f"Error: Request timed out after {LLM_CALL_TIMEOUT} seconds. Try using fewer files or a smaller query.\n\nCollected {len(files)} files ({total_size:,} bytes){token_info}"

    # Add thinking/reasoning budget info if applicable (even for errors)
    if thinking_budget is not None:
        budget_type = "thinking" if provider == "google" else "reasoning"
        if thinking_budget == -1:
            # Special marker for OpenAI effort-based reasoning
            token_info += f", {budget_type} mode: effort=high (~80% of output budget)"
        elif thinking_budget > 0:
            # Calculate percentage of maximum possible thinking
            # Import these only when needed to avoid circular imports
            from .token_utils import (
                FLASH_MAX_THINKING_TOKENS,
                PRO_MAX_THINKING_TOKENS,
                MAX_REASONING_TOKENS,
            )

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
