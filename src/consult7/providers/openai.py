"""OpenAI provider implementation for Consult7."""

from typing import Optional, Tuple

# Provider-specific imports will be done conditionally
try:
    from openai import AsyncOpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from .base import BaseProvider, process_llm_response
from ..constants import DEFAULT_OUTPUT_TOKENS, DEFAULT_TEMPERATURE
from ..token_utils import TOKEN_SAFETY_FACTOR, estimate_tokens


class OpenAIProvider(BaseProvider):
    """OpenAI provider implementation."""

    async def get_model_info(self, model_name: str, api_key: str) -> Optional[dict]:
        """Get model information for OpenAI models.

        OpenAI API doesn't provide context length via API.
        Context must be specified by the user in the model name.
        """
        # OpenAI requires context to be specified in model name
        # Format: model|context or model|context|thinking
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
        """Call OpenAI API with the content and query.

        Returns:
            Tuple of (response, error, thinking_budget_used)
        """
        if not OPENAI_AVAILABLE:
            return (
                "",
                "OpenAI SDK not available. Install with: pip install openai",
                None,
            )

        if not api_key:
            return "", "No API key provided. Use --api-key flag", None

        # Parse model name for thinking mode and context
        parts = model_name.split("|") if "|" in model_name else [model_name]
        actual_model_name = parts[0]
        has_thinking = "thinking" in parts

        # Check if this is an o-series model that supports reasoning
        is_reasoning_model = any(
            x in actual_model_name.lower() for x in ["o1", "o3", "o4"]
        )

        # Parse context from model specification
        specified_context = None
        for part in parts[1:]:  # Skip the model name
            if part and part != "thinking":
                # Parse context like "200k" -> 200000, "1047576" -> 1047576
                if part.endswith("k"):
                    specified_context = int(float(part[:-1]) * 1000)
                else:
                    specified_context = int(part)
                break

        if not specified_context:
            return (
                "",
                (
                    f"OpenAI models require context length specification. "
                    f"Use format: '{actual_model_name}|128k' or '{actual_model_name}|200000'"
                ),
                None,
            )

        context_length = specified_context

        # Estimate tokens for the input
        system_msg = "You are a helpful assistant analyzing code and files. Be concise and specific in your responses."
        user_msg = f"Here are the files to analyze:\n\n{content}\n\nQuery: {query}"
        total_input = system_msg + user_msg
        estimated_tokens = estimate_tokens(total_input)

        # Check against model context limit
        max_output_tokens = DEFAULT_OUTPUT_TOKENS
        available_for_input = int(
            (context_length - max_output_tokens) * TOKEN_SAFETY_FACTOR
        )

        if estimated_tokens > available_for_input:
            return (
                "",
                (
                    f"Content too large: ~{estimated_tokens:,} tokens estimated, "
                    f"but model {model_name} has only ~{available_for_input:,} tokens available for input "
                    f"(total limit: {context_length:,}, reserved for output: {max_output_tokens:,}). "
                    f"Try reducing file count/size."
                ),
                None,
            )

        try:
            client = AsyncOpenAI(api_key=api_key)

            # Build parameters
            # o-series models don't support system messages
            if any(x in actual_model_name.lower() for x in ["o1", "o3", "o4"]):
                messages = [
                    {"role": "user", "content": f"{system_msg}\n\n{user_msg}"},
                ]
            else:
                messages = [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ]

            # Build base parameters
            params = {
                "model": actual_model_name,
                "messages": messages,
            }

            # o-series models have different parameter requirements
            if any(x in actual_model_name.lower() for x in ["o1", "o3", "o4"]):
                params["max_completion_tokens"] = DEFAULT_OUTPUT_TOKENS
                # o-series models only support temperature=1
            else:
                params["max_tokens"] = DEFAULT_OUTPUT_TOKENS
                params["temperature"] = DEFAULT_TEMPERATURE

            # Note: o-series models automatically use reasoning tokens internally
            # The API doesn't support reasoning_effort parameter in SDK 1.88.0
            # But usage stats will show reasoning_tokens in the response

            response = await client.chat.completions.create(**params)

            llm_response = process_llm_response(response.choices[0].message.content)

            # Add note about thinking mode if used
            if has_thinking:
                if is_reasoning_model:
                    llm_response += "\n\n[Note: o-series models use reasoning tokens automatically. The |thinking suffix is informational - use OpenRouter for effort control.]"
                else:
                    llm_response += f"\n\n[Note: |thinking not supported for {actual_model_name}. Only o-series models support reasoning.]"

            return llm_response, None, None

        except Exception as e:
            return "", f"Error calling OpenAI: {str(e)}", None
