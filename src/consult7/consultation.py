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
            if not info: # If provider returns None, initialize a basic dict
                info = {"provider": provider}

        # Add 'supports_images' flag
        if provider == "google":
            # Assuming all Google models fetched via its get_model_info support images.
            # A more granular check (e.g. based on model name patterns like 'gemini') could be added.
            info["supports_images"] = True
        else:
            info["supports_images"] = False # Default for other providers

        if "context_length" not in info:
             # Fallback to default if no context_length info available after provider call
            logger.warning(
                f"Could not determine context length for {model_name} (provider: {provider}), using default of {DEFAULT_CONTEXT_LENGTH:,} tokens"
            )
            info["context_length"] = DEFAULT_CONTEXT_LENGTH

        return info

    except ValueError:
        # Re-raise ValueError to be caught by caller (e.g. OpenAI context spec error)
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
    include_images: bool = False, # New parameter
) -> str:
    """Implementation of the consultation tool logic."""
    # Discover files
    # discover_files now returns (text_files, image_files, errors)
    text_files, image_files, errors = discover_files(path, pattern, exclude_pattern)

    all_files_count = len(text_files) + len(image_files)

    if not all_files_count and errors:
        return "Error: No files found. Errors:\n" + "\n".join(errors)

    if not all_files_count:
        return "No files matching the pattern were found."

    # Format content - now takes text_files, image_files, and include_images flag
    # format_content now returns List[Dict[str, Any]] for content_parts
    content_parts, total_size = format_content(
        path, text_files, image_files, errors, include_images
    )

    # For providers that only support text, we might need to reconstruct a string
    # or handle this in the provider itself.
    # For now, let's assume the provider (like GoogleProvider) can handle content_parts.
    # Other providers will need adjustment or will only use text parts.

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

    # Add size info that will be part of the query (or handled by provider)
    # For multimodal, the "content" is now content_parts.
    # Token estimation needs to handle this list.
    # For now, we'll pass content_parts to providers that can handle it (Google).
    # For others, we might need to serialize text parts or raise an error if images are included.

    # For text-only providers, reconstruct a text version for token estimation and call
    # This is a temporary measure; ideally, each provider handles its content type.
    text_only_content_for_estimation = ""
    if provider != "google": # Assuming only Google handles List[Dict] for now
        for part in content_parts:
            if "text" in part:
                text_only_content_for_estimation += part["text"] + "\n"
    # If Google, token estimation is handled within the provider based on multimodal parts.

    # This estimation is now primarily for non-Google providers or as a pre-check.
    # Google provider will do its own more accurate multimodal token estimation.
    query_tokens = estimate_tokens(f"\n\nQuery: {query}")

    # The main token estimation for the content itself will now largely be provider-specific
    # especially for multimodal. The `total_estimated_tokens` in `GoogleProvider` is more accurate.
    # Here, we can make a rough estimate for display or for text-only providers.

    # For display purposes:
    display_token_info = f"\nTotal content size: {total_size:,} bytes from {all_files_count} files."
    # More detailed token estimation will be logged by the provider or if an error occurs.

    token_info = f"\nEstimated query tokens: ~{query_tokens:,}"
    if model_context_length:
        token_info += f" (Model context limit: {model_context_length:,} tokens)"
    # Note: Actual content token estimation for Google provider is done inside its `call_llm`.
    # For other providers, they still expect a single string.

    # Call appropriate LLM based on provider
    thinking_budget = None # Renamed from thinking_budget_used for clarity before call
    provider_instance = PROVIDERS.get(provider)
    if not provider_instance:
        return f"Error: Unknown provider '{provider}'"

    # Parse thinking mode from model string (e.g., "gemini-pro|thinking" or "gemini-pro|thinking=10000")
    # actual_model_name_for_call will be "gemini-pro"
    # custom_thinking_tokens will be None or 10000
    # effective_thinking_mode will be True if |thinking or |thinking=X is present
    actual_model_name_for_call, custom_thinking_tokens = parse_model_thinking(model)
    effective_thinking_mode = custom_thinking_tokens is not None or model.endswith("|thinking")


    # Call the provider with timeout protection
    try:
        async with asyncio.timeout(LLM_CALL_TIMEOUT):
            model_supports_images = model_info.get("supports_images", False)

            content_to_send: Any # Type hint for clarity, can be List[Dict] or str

            if model_supports_images and include_images:
                content_to_send = content_parts # Send the list of dicts for multimodal
                # This warning is useful if we ever set supports_images=True for a non-Google provider
                # without ensuring its provider implementation can handle List[Dict].
                if provider not in ["google"]: # Check against a list of known multimodal-ready providers
                    logger.warning(
                        f"Model '{model_for_info}' on provider '{provider}' is marked `supports_images=True`, "
                        f"but provider '{provider}' may not be fully multimodal-ready in this tool. Sending structured content."
                    )
            else:
                # Concatenate text parts for text-only models, or if --include-images is false
                text_content_str = ""
                for part in content_parts:
                    if "text" in part:
                        text_content_str += part["text"] + "\n"
                content_to_send = text_content_str

                # Log warning if images were found and meant to be included but model doesn't support them
                if image_files and include_images and not model_supports_images:
                    logger.warning(
                        f"Images were found and --include-images was used, but model '{model_for_info}' on provider '{provider}' does not support image input. Images will be ignored."
                    )

            response, error, thinking_budget_used = await provider_instance.call_llm(
                content_to_send, # This will be List[Dict] or str
                query,
                model, # Pass the original model string (e.g. "gemini-pro|thinking")
                       # The provider's call_llm will parse it again if needed
                api_key,
                effective_thinking_mode, # Pass the boolean flag
                custom_thinking_tokens,  # Pass the parsed token budget or None
            )
    except asyncio.TimeoutError:
        return f"Error: Request timed out after {LLM_CALL_TIMEOUT} seconds. Try using fewer files or a smaller query.\n\nCollected {all_files_count} files ({total_size:,} bytes). {display_token_info} {token_info}"

    # Add thinking/reasoning budget info if applicable (even for errors)
    # Append to `token_info` which is part of the final display string.
    if thinking_budget_used is not None: # Check the returned budget
        budget_type = "thinking" if provider == "google" else "reasoning"
        if thinking_budget_used == -1: # OpenAI effort marker
            # Special marker for OpenAI effort-based reasoning
            token_info += f", {budget_type} mode: effort=high (~80% of output budget)"
        elif thinking_budget_used > 0:
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
            percentage = (thinking_budget_used / max_thinking) * 100 # Use thinking_budget_used
            token_info += f", {budget_type} budget: {thinking_budget_used:,} tokens ({percentage:.1f}% of max)"
        else: # thinking_budget_used is 0 or some other non-positive, non -1 value
            token_info += f", {budget_type} disabled or not applicable"

    if error:
        return f"Error calling {provider} LLM: {error}\n\nCollected {all_files_count} files ({total_size:,} bytes). {display_token_info} {token_info}"

    # Add size info to response for agent awareness
    return f"{response}\n\n---\nProcessed {all_files_count} files ({total_size:,} bytes) with {model} ({provider}). {display_token_info} {token_info}"
