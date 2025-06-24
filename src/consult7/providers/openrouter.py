"""OpenRouter provider implementation for Consult7."""

import logging
from typing import Optional, Tuple
import httpx

logger = logging.getLogger("consult7")

from .base import BaseProvider, process_llm_response
from ..constants import (
    OPENROUTER_URL,
    MODELS_URL,
    DEFAULT_CONTEXT_LENGTH,
    DEFAULT_OUTPUT_TOKENS,
    SMALL_OUTPUT_TOKENS,
    SMALL_MODEL_THRESHOLD,
    DEFAULT_TEMPERATURE,
    OPENROUTER_TIMEOUT,
    API_FETCH_TIMEOUT,
)
from ..token_utils import (
    TOKEN_SAFETY_FACTOR,
    estimate_tokens,
    parse_model_thinking,
    get_thinking_budget,
)


class OpenRouterProvider(BaseProvider):
    """OpenRouter provider implementation."""

    async def get_model_info(self, model_name: str, api_key: str) -> Optional[dict]:
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
                    logger.warning(
                        f"Could not fetch model info: {response.status_code}"
                    )
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
                logger.warning(
                    f"Model '{model_name}' not found in OpenRouter models list"
                )
                return None

        except Exception as e:
            logger.warning(f"Error fetching model info: {e}")
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
        """Call OpenRouter API with the content and query.

        Returns:
            Tuple of (response, error, reasoning_budget_used)
        """
        if not api_key:
            return "", "No API key provided. Use --api-key flag", None

        # Parse model and thinking override
        actual_model, custom_thinking = parse_model_thinking(model_name)
        reasoning_mode = custom_thinking is not None or model_name.endswith("|thinking")

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

        # Fixed output token limit for initial calculation
        base_max_output_tokens = (
            DEFAULT_OUTPUT_TOKENS
            if context_length > SMALL_MODEL_THRESHOLD
            else SMALL_OUTPUT_TOKENS
        )
        max_output_tokens = base_max_output_tokens

        # Binary approach for reasoning mode - reserve full amount upfront
        reasoning_budget_actual = 0
        unknown_model_msg = ""
        is_openai_model = any(
            x in actual_model.lower() for x in ["gpt-4", "o1", "openai"]
        )

        if reasoning_mode:
            # Check if it's an OpenAI model that uses effort levels
            limit_value = get_thinking_budget(actual_model, custom_thinking)

            if limit_value == "effort":
                # OpenAI models use effort levels, not token counts
                is_openai_model = True
                # For OpenAI models, reasoning uses part of the output budget
                # We don't increase max_output_tokens
                reasoning_budget_actual = 0  # Signal that we're using effort mode
            else:
                # Non-OpenAI models: get reasoning budget
                reasoning_budget_actual = limit_value

                # If unknown model without override, disable reasoning and add note
                if reasoning_budget_actual is None:
                    reasoning_mode = False
                    reasoning_budget_actual = 0
                    unknown_model_msg = f"\nNote: Unknown model '{actual_model}' requires thinking=X parameter for reasoning mode. Example: {actual_model}|thinking=30000"
                else:
                    # For Anthropic models, reasoning tokens come FROM max_tokens, not in addition
                    # For other models (Gemini), they're additional
                    if "anthropic" in actual_model.lower():
                        # Anthropic: ensure max_tokens > reasoning_budget
                        # We need at least reasoning_budget + some tokens for the actual response
                        max_output_tokens = (
                            reasoning_budget_actual + 2000
                        )  # 2k for actual response
                    else:
                        # Gemini and others: reasoning is additional to output
                        max_output_tokens = (
                            DEFAULT_OUTPUT_TOKENS + reasoning_budget_actual
                        )

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
                            f"Context: {context_length:,}, output: {DEFAULT_OUTPUT_TOKENS:,}, reasoning: {reasoning_budget_actual:,}. "
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
                data["reasoning"] = {"max_tokens": reasoning_budget_actual}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    OPENROUTER_URL,
                    headers=headers,
                    json=data,
                    timeout=OPENROUTER_TIMEOUT,
                )

                if response.status_code != 200:
                    return (
                        "",
                        f"API error: {response.status_code} - {response.text}",
                        None,
                    )

                result = response.json()

                if "choices" not in result or not result["choices"]:
                    return "", f"Unexpected API response format: {result}", None

                llm_response = process_llm_response(
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
                    return (
                        llm_response,
                        None,
                        reasoning_budget_actual if reasoning_mode else None,
                    )

        except httpx.TimeoutException:
            return "", f"Request timed out after {OPENROUTER_TIMEOUT} seconds", None
        except Exception as e:
            return "", f"Error calling API: {e}", None
