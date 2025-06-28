"""Google AI provider implementation for Consult7."""

import logging
from typing import Optional, Tuple

logger = logging.getLogger("consult7")

# Provider-specific imports will be done conditionally
try:
    from google import genai
    from google.genai import types as genai_types

    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

from .base import BaseProvider, process_llm_response
from ..constants import (
    DEFAULT_CONTEXT_LENGTH,
    DEFAULT_OUTPUT_TOKENS,
    DEFAULT_TEMPERATURE,
)
from ..token_utils import (
    TOKEN_SAFETY_FACTOR,
    estimate_tokens,
    parse_model_thinking,
    get_thinking_budget,
    estimate_image_tokens, # New import
)
from typing import List, Dict, Any # For type hinting content parts


class GoogleProvider(BaseProvider):
    """Google AI provider implementation."""

    async def get_model_info(self, model_name: str, api_key: str) -> Optional[dict]:
        """Get model information for Google models."""
        if not GOOGLE_AVAILABLE:
            return None

        try:
            # Ensure model name has correct format for API
            api_model_name = model_name
            if not model_name.startswith("models/"):
                api_model_name = f"models/{model_name}"

            # Defer client creation until API key is validated or available
            # genai.configure(api_key=api_key) # Configure once if needed globally

            # Use the synchronous client for this blocking call, or make an async version
            # For simplicity, assuming a synchronous call here if genai.Client is not async by default
            # If genai.Client().models.get is async, it should be awaited.
            # The original code uses client.models.get which is synchronous.
            # Let's assume genai.get_model is the intended synchronous or awaitable async method.
            # Reverting to original structure for now, assuming genai.Client handles auth.

            client = genai.Client(api_key=api_key)
            model_info_obj = client.models.get(model=api_model_name) # Corrected to use api_model_name

            # Return context info in consistent format
            return {
                "context_length": model_info_obj.input_token_limit,
                "max_output_tokens": model_info_obj.output_token_limit,
                "provider": "google",
            }
        except Exception as e:
            logger.warning(f"Could not fetch Google model info for '{model_name}': {e}")
            return None

    async def call_llm(
        self,
        content_parts: List[Dict[str, Any]], # Changed from content: str
        query: str,
        model_name: str,
        api_key: str,
        thinking_mode: bool = False,
        thinking_budget: Optional[int] = None, # This might be redundant if using model's thinking_config
    ) -> Tuple[str, Optional[str], Optional[int]]:
        """Call Google AI API with multimodal content and query.

        Returns:
            Tuple of (response, error, thinking_budget_used)
        """
        if not GOOGLE_AVAILABLE:
            return (
                "",
                "Google AI SDK not available. Install with: pip install google-genai",
                None,
            )

        if not api_key:
            return "", "No API key provided. Use --api-key flag", None

        actual_model, custom_thinking = parse_model_thinking(model_name)
        # thinking_mode is determined by suffix or custom_thinking, not passed directly
        effective_thinking_mode = custom_thinking is not None or model_name.endswith("|thinking")


        try:
            model_info = await self.get_model_info(actual_model, api_key)
            if not model_info: # Fallback if info fetch fails
                logger.warning(f"Using default context length for {actual_model} due to failed info retrieval.")
                model_info = {"context_length": DEFAULT_CONTEXT_LENGTH, "max_output_tokens": DEFAULT_OUTPUT_TOKENS}
            context_length = model_info.get("context_length", DEFAULT_CONTEXT_LENGTH)
            max_output_tokens = model_info.get("max_output_tokens", DEFAULT_OUTPUT_TOKENS)

        except Exception as e:
            logger.error(f"Error fetching model info for {actual_model}: {e}")
            return "", f"Error fetching model info: {e}", None

        # Prepare multimodal content for Gemini
        # System message should be the first text part if used
        # User query should be the last text part

        gemini_contents = []
        system_msg = "You are a helpful assistant analyzing code and files. Be concise and specific in your responses."
        gemini_contents.append({"text": system_msg})

        # Add processed file content parts
        # These parts already have the structure {"text": ...} or {"mime_type": ..., "data": ...}
        total_estimated_tokens = estimate_tokens(system_msg) # Start with system message tokens

        for part in content_parts:
            if "text" in part:
                gemini_contents.append(part)
                total_estimated_tokens += estimate_tokens(part["text"])
            elif "inline_data" in part:
                inline_data_content = part["inline_data"]
                if isinstance(inline_data_content, dict) and \
                   "mime_type" in inline_data_content and \
                   "data" in inline_data_content:

                    if inline_data_content["mime_type"].startswith("image/"):
                        gemini_contents.append(part) # Append the whole part, e.g., {"inline_data": {"mime_type": ..., "data": ...}}
                        total_estimated_tokens += estimate_image_tokens(
                            inline_data_content["data"],
                            inline_data_content["mime_type"]
                        )
                    else:
                        logger.warning(f"Unsupported inline_data mime_type: {inline_data_content['mime_type']}")
                else:
                    logger.warning(f"Malformed inline_data part: {part}")
            # else: # Optional: Log if part is neither text nor inline_data
                # logger.warning(f"Unknown part structure encountered: {part}")

        gemini_contents.append({"text": f"\n\nQuery: {query}"})
        total_estimated_tokens += estimate_tokens(f"\n\nQuery: {query}")

        # Fixed output token limit - consider if model_info provides this
        # max_output_tokens = DEFAULT_OUTPUT_TOKENS # Already fetched from model_info or defaulted

        # Binary approach for thinking mode - reserve full amount upfront
        thinking_budget_to_use = 0
        unknown_model_msg = ""
        if effective_thinking_mode:
            thinking_budget_to_use = get_thinking_budget(actual_model, custom_thinking)

            if thinking_budget_to_use is None: # Model not known for thinking, and no override
                effective_thinking_mode = False # Disable thinking
                thinking_budget_to_use = 0
                unknown_model_msg = f"\nNote: Unknown model '{actual_model}' for thinking mode. To enable, use format: {actual_model}|thinking=X (e.g., 30000)."


        # Calculate available input space
        # Subtract max_output_tokens and thinking_budget_to_use from context_length
        available_for_input = int(
            (context_length - max_output_tokens - thinking_budget_to_use) * TOKEN_SAFETY_FACTOR
        )

        if total_estimated_tokens > available_for_input:
            error_detail = (
                f"~{total_estimated_tokens:,} tokens estimated for input (including text and images), "
                f"but model {actual_model} has ~{available_for_input:,} tokens available "
                f"(context: {context_length:,}, max_output: {max_output_tokens:,}, "
                f"thinking_reserved: {thinking_budget_to_use if effective_thinking_mode else 0:,}). "
            )
            if effective_thinking_mode:
                # Check if it would fit without thinking
                available_without_thinking = int(
                    (context_length - max_output_tokens) * TOKEN_SAFETY_FACTOR
                )
                if total_estimated_tokens <= available_without_thinking:
                    error_detail += (
                        f"The content might fit if thinking mode is disabled "
                        f"(~{available_without_thinking:,} available without thinking). "
                        f"Try removing '|thinking' or custom thinking budget."
                    )
                else:
                     error_detail += "Content is too large even without thinking mode. "
            error_detail += "Try reducing file count/size or using a model with a larger context window."
            return "", error_detail, 0


        try:
            # Use genai.Client for making the call, similar to the reference commit
            # and original consult7 structure.
            client = genai.Client(api_key=api_key)

            # Prepare generation config
            generation_config = genai_types.GenerateContentConfig(
                max_output_tokens=max_output_tokens,
                temperature=DEFAULT_TEMPERATURE,
            )

            # Add thinking config if applicable
            if effective_thinking_mode and thinking_budget_to_use is not None:
                # thinking_budget_to_use can be 0 (disable for Flash), -1 (dynamic), or positive.
                generation_config.thinking_config = genai_types.ThinkingConfig(
                    thinking_budget=thinking_budget_to_use
                )

            # Ensure model name for API call is prefixed with "models/" if not already.
            # The `actual_model` variable already has provider prefixes like "google/" stripped if they were there.
            api_call_model_name = actual_model
            if not api_call_model_name.startswith("models/"):
                api_call_model_name = f"models/{api_call_model_name}"

            # Make the asynchronous API call
            response = await client.aio.models.generate_content(
                model=api_call_model_name,
                contents=gemini_contents, # Send the multimodal content list
                config=generation_config, # Changed 'generation_config' to 'config'
                # request_options=request_options # If applicable
            )

            llm_response = process_llm_response(response.text)

            if unknown_model_msg:
                llm_response += unknown_model_msg

            # Return thinking budget used (or configured) if in thinking mode
            thinking_budget_returned = thinking_budget_to_use if effective_thinking_mode else None
            return llm_response, None, thinking_budget_returned

        except Exception as e:
            error_msg = f"Error calling Google AI ({actual_model}): {str(e)}"
            if unknown_model_msg and "not found" in str(e).lower(): # More specific error check
                 error_msg += unknown_model_msg
            # Consider logging the full exception for debugging
            logger.error(f"Google AI API call failed: {e}", exc_info=True)
            return "", error_msg, None
