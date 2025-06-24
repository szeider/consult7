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
)


class GoogleProvider(BaseProvider):
    """Google AI provider implementation."""

    async def get_model_info(self, model_name: str, api_key: str) -> Optional[dict]:
        """Get model information for Google models."""
        if not GOOGLE_AVAILABLE:
            return None

        try:
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
            logger.warning(f"Could not fetch Google model info: {e}")
            return None

    async def call_llm(
        self,
        content: str,
        query: str,
        model_name: str,
        api_key: str,
        thinking_mode: bool = False,
        thinking_budget: Optional[int] = None,
    ) -> Tuple[str, Optional[str], Optional[int]]:
        """Call Google AI API with the content and query.

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

        # Parse model and thinking override
        actual_model, custom_thinking = parse_model_thinking(model_name)
        thinking_mode = custom_thinking is not None or model_name.endswith("|thinking")

        # Get model context info
        try:
            model_info = await self.get_model_info(actual_model, api_key)
            if not model_info:
                model_info = {"context_length": DEFAULT_CONTEXT_LENGTH}
            context_length = model_info.get("context_length", DEFAULT_CONTEXT_LENGTH)
        except Exception as e:
            return "", str(e), None

        # Estimate tokens for the input
        system_msg = "You are a helpful assistant analyzing code and files. Be concise and specific in your responses."
        user_msg = f"Here are the files to analyze:\n\n{content}\n\nQuery: {query}"
        total_input = system_msg + user_msg
        estimated_tokens = estimate_tokens(total_input)

        # Fixed output token limit
        max_output_tokens = DEFAULT_OUTPUT_TOKENS

        # Binary approach for thinking mode - reserve full amount upfront
        thinking_budget_actual = 0
        unknown_model_msg = ""
        if thinking_mode:
            thinking_budget_actual = get_thinking_budget(actual_model, custom_thinking)

            # If unknown model without override, disable thinking and add note
            if thinking_budget_actual is None:
                thinking_mode = False
                thinking_budget_actual = 0
                unknown_model_msg = f"\nNote: Unknown model '{actual_model}' requires thinking=X parameter for thinking mode. Example: {actual_model}|thinking=30000"

        # Calculate available input space with thinking reserved upfront
        available_for_input = int(
            (context_length - max_output_tokens - thinking_budget_actual)
            * TOKEN_SAFETY_FACTOR
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
                            f"Context: {context_length:,}, output: {max_output_tokens:,}, thinking: {thinking_budget_actual:,}. "
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
                config_params["thinking_config"] = genai_types.ThinkingConfig(
                    thinking_budget=thinking_budget_actual  # Use calculated budget
                )

            response = await client.aio.models.generate_content(
                model=actual_model,
                contents=f"{system_msg}\n\n{user_msg}",
                config=genai_types.GenerateContentConfig(**config_params),
            )

            llm_response = process_llm_response(response.text)

            # Add unknown model message if applicable
            if unknown_model_msg:
                llm_response = llm_response + unknown_model_msg

            # Return thinking budget (None for normal mode, value for thinking mode)
            return llm_response, None, thinking_budget_actual if thinking_mode else None

        except Exception as e:
            error_msg = f"Error calling Google AI: {str(e)}"
            # Add unknown model message if applicable
            if unknown_model_msg and "not found" in str(e).lower():
                error_msg += unknown_model_msg
            return "", error_msg, None
