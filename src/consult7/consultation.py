"""Main consultation orchestration logic for Consult7."""

import asyncio
import logging
from typing import Optional

from .constants import DEFAULT_CONTEXT_LENGTH, LLM_CALL_TIMEOUT
from .file_processor import expand_file_patterns, format_content, save_output_to_file
from .token_utils import estimate_tokens, get_thinking_budget, calculate_max_file_size
from .providers import PROVIDERS

logger = logging.getLogger("consult7")


async def get_model_context_info(model_name: str, provider: str, api_key: Optional[str]) -> dict:
    """Get model context information from OpenRouter API."""
    try:
        # Get provider instance (always openrouter)
        if not (provider_instance := PROVIDERS.get(provider)):
            logger.warning(f"Unknown provider '{provider}'")
            return {"context_length": DEFAULT_CONTEXT_LENGTH, "provider": provider}

        # Get model info from provider API
        info = await provider_instance.get_model_info(model_name, api_key)

        if info and "context_length" in info:
            return info

        # Fallback to default if no info available
        logger.warning(
            f"Could not determine context length for {model_name}, using default of 128k tokens"
        )
        return {"context_length": DEFAULT_CONTEXT_LENGTH, "provider": provider}

    except Exception as e:
        logger.error(f"Error getting model info: {e}")
        return {"context_length": DEFAULT_CONTEXT_LENGTH, "provider": provider}


async def consultation_impl(
    files: list[str],
    query: str,
    model: str,
    mode: str,
    provider: str = "openrouter",
    api_key: Optional[str] = None,
    output_file: Optional[str] = None,
) -> str:
    """Implementation of the consultation tool logic."""
    # Expand file patterns
    file_paths, errors = expand_file_patterns(files)

    if not file_paths and errors:
        return "Error: No files found. Errors:\n" + "\n".join(errors)

    # Provide immediate feedback about what was found
    if not file_paths:
        return "No files matching the patterns were found."

    # Get model info to calculate dynamic limits
    model_info = await get_model_context_info(model, provider, api_key)
    model_context_length = model_info.get("context_length", DEFAULT_CONTEXT_LENGTH)

    # Calculate dynamic file size limits based on model's context window
    max_total_size, max_file_size = calculate_max_file_size(model_context_length, mode, model)

    # Format content with model-specific limits
    content, total_size = format_content(file_paths, errors, max_total_size, max_file_size)

    # Determine thinking mode based on mode parameter
    thinking_budget_value = get_thinking_budget(model, mode)
    thinking_mode = thinking_budget_value is not None

    # Add size info that will be part of the query
    size_info = f"\n\n---\nTotal content size: {total_size:,} bytes from {len(file_paths)} files"

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

    # Call the provider with generous timeout protection (10 minutes)
    try:
        async with asyncio.timeout(LLM_CALL_TIMEOUT):
            response, error, thinking_budget = await provider_instance.call_llm(
                content + size_info,
                query,
                model,
                api_key,
                thinking_mode,
                thinking_budget_value,
            )
    except asyncio.TimeoutError:
        return (
            f"Error: Request timed out after {LLM_CALL_TIMEOUT} seconds "
            f"(10 minutes). This is an extremely long time - "
            f"the model or API may be having issues.\n\n"
            f"Collected {len(file_paths)} files ({total_size:,} bytes){token_info}"
        )

    # Add reasoning budget info if applicable (even for errors)
    if thinking_budget is not None:
        if thinking_budget == -1:
            # Special marker for OpenAI effort-based reasoning
            token_info += ", reasoning mode: effort=high (~80% of output budget)"
        elif thinking_budget == -2:
            # Special marker for Gemini 3 Pro with reasoning enabled
            token_info += ", reasoning mode: enabled=true (dynamic reasoning)"
        elif thinking_budget == -3:
            # Special marker for Gemini 3 Pro without reasoning
            token_info += ", reasoning mode: enabled=true (no reasoning used)"
        elif thinking_budget > 0:
            # Calculate percentage of maximum possible reasoning tokens
            # Import these only when needed to avoid circular imports
            from .token_utils import (
                FLASH_MAX_THINKING_TOKENS,
                MAX_REASONING_TOKENS,
            )

            # Determine max reasoning based on model
            if "gemini" in model.lower() and "flash" in model.lower():
                max_reasoning = FLASH_MAX_THINKING_TOKENS  # 24,576
            else:
                max_reasoning = MAX_REASONING_TOKENS  # 32,000 (Anthropic, others)

            percentage = (thinking_budget / max_reasoning) * 100
            token_info += (
                f", reasoning budget: {thinking_budget:,} tokens ({percentage:.1f}% of max)"
            )
        else:
            token_info += ", reasoning disabled (insufficient context)"

    if error:
        return (
            f"Error calling {provider} LLM: {error}\n\n"
            f"Collected {len(file_paths)} files ({total_size:,} bytes){token_info}"
        )

    # Handle output file if specified
    if output_file:
        # Save just the LLM response (without the metadata)
        save_path, save_error = save_output_to_file(response, output_file)

        if save_error:
            return f"Error saving output: {save_error}"

        # Return brief confirmation message
        return f"Result has been saved to {save_path}"

    # Normal mode: return full response with metadata
    mode_str = f" [{mode}]" if mode != "fast" else ""
    return (
        f"{response}\n\n---\n"
        f"Processed {len(file_paths)} files ({total_size:,} bytes) "
        f"with {model}{mode_str} ({provider}){token_info}"
    )
