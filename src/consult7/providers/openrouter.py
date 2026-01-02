"""OpenRouter provider implementation for Consult7."""

import json
import logging
from typing import Optional, Tuple
import httpx

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
    calculate_reasoning_max_tokens,
)

logger = logging.getLogger("consult7")


class OpenRouterProvider(BaseProvider):
    """OpenRouter provider implementation."""

    async def get_model_info(self, model_name: str, api_key: Optional[str]) -> Optional[dict]:
        """Get model information from OpenRouter API."""
        if not api_key:
            return None

        headers = {
            "Authorization": f"Bearer {api_key}",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(MODELS_URL, headers=headers, timeout=API_FETCH_TIMEOUT)

                if response.status_code != 200:
                    logger.warning(f"Could not fetch model info: {response.status_code}")
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
                logger.warning(f"Model '{model_name}' not found in OpenRouter models list")
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
        zdr: bool = False,
    ) -> Tuple[str, Optional[str], Optional[int]]:
        """Call OpenRouter API with the content and query.

        Returns:
            Tuple of (response, error, reasoning_budget_used)
        """
        if not api_key:
            return (
                "",
                "No API key provided for OpenRouter. Start consult7 with your key: "
                "`consult7 sk-or-v1-...` (or configure --api-key in your MCP client).",
                None,
            )

        # Get model context info
        try:
            model_info = await self.get_model_info(model_name, api_key)
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

        # Base output token limit
        base_max_output_tokens = (
            DEFAULT_OUTPUT_TOKENS if context_length > SMALL_MODEL_THRESHOLD else SMALL_OUTPUT_TOKENS
        )

        # Track reasoning type for API call formatting
        uses_effort_reasoning = thinking_budget in ("effort_high", "effort_medium")
        uses_enabled_reasoning = thinking_budget in ("enabled_high", "enabled_low")

        # Calculate max_tokens using model-aware reasoning budget calculation
        # This handles different models' reasoning token behavior:
        # - OpenAI/Claude/Grok: reasoning consumes max_tokens budget
        # - Gemini 2.5: reasoning is separate from output
        # - Gemini 3: dynamic reasoning allocation
        mode_for_calc = "think" if thinking_mode else "fast"
        max_output_tokens = calculate_reasoning_max_tokens(
            model_name, mode_for_calc, thinking_budget, base_max_output_tokens
        )

        # Track actual reasoning budget for reporting (0 for effort/enabled modes)
        if thinking_budget in ("effort_high", "effort_medium", "enabled_high", "enabled_low"):
            reasoning_budget_actual = 0
        elif isinstance(thinking_budget, int):
            reasoning_budget_actual = thinking_budget
        else:
            reasoning_budget_actual = 0

        # Calculate available input space with reasoning reserved upfront
        available_for_input = int((context_length - max_output_tokens) * TOKEN_SAFETY_FACTOR)

        # Check against adjusted limit
        if estimated_tokens > available_for_input:
            if thinking_mode:
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
                            f"but model {model_name} has only ~{available_without_reasoning:,} tokens available "
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
            "model": model_name,
            "messages": messages,
            "temperature": DEFAULT_TEMPERATURE,
            "max_tokens": max_output_tokens,
            "stream": True,  # Use streaming to prevent timeout truncation
        }

        # Add Zero Data Retention routing if requested
        if zdr:
            data["provider"] = {"zdr": True}

        # Add reasoning mode if thinking_mode is enabled
        if thinking_mode:
            if uses_effort_reasoning:
                # OpenAI models: use effort level based on mode
                effort_level = "high" if thinking_budget == "effort_high" else "medium"
                data["reasoning"] = {"effort": effort_level}
            elif uses_enabled_reasoning:
                # Gemini 3 Pro: use effort level (maps to thinkingLevel via OpenAI compat)
                effort_level = "high" if thinking_budget == "enabled_high" else "low"
                data["reasoning"] = {"effort": effort_level}
            else:
                # Anthropic, Gemini 2.5, and others: use max_tokens
                data["reasoning"] = {"max_tokens": reasoning_budget_actual}

        try:
            # Use streaming to keep connection alive during long reasoning
            # This prevents intermediate proxy/server timeouts
            collected_content = []
            finish_reason = None

            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    OPENROUTER_URL,
                    headers=headers,
                    json=data,
                    timeout=OPENROUTER_TIMEOUT,
                ) as response:
                    if response.status_code != 200:
                        # Read error response body
                        error_body = await response.aread()
                        return (
                            "",
                            f"API error: {response.status_code} - {error_body.decode()}",
                            None,
                        )

                    # Process SSE stream
                    async for line in response.aiter_lines():
                        if not line:
                            continue

                        # SSE format: "data: {...}" or "data: [DONE]"
                        if line.startswith("data: "):
                            data_str = line[6:]  # Remove "data: " prefix

                            if data_str == "[DONE]":
                                break

                            try:
                                chunk = json.loads(data_str)

                                # Extract content from delta
                                if "choices" in chunk and chunk["choices"]:
                                    choice = chunk["choices"][0]
                                    delta = choice.get("delta", {})
                                    chunk_content = delta.get("content", "")
                                    if chunk_content:
                                        collected_content.append(chunk_content)

                                    # Track finish_reason
                                    if choice.get("finish_reason"):
                                        finish_reason = choice["finish_reason"]

                            except json.JSONDecodeError:
                                # Skip malformed chunks
                                continue

            # Combine all chunks
            full_response = "".join(collected_content)

            if not full_response:
                return "", "No content received from API (empty response)", None

            llm_response = process_llm_response(full_response)

            # Log finish_reason for debugging truncation issues
            if finish_reason and finish_reason != "stop":
                logger.warning(f"Response finish_reason: {finish_reason} (may indicate truncation)")

            # Return reasoning budget (for special reasoning modes, return markers)
            # -1: OpenAI effort=high, -2: OpenAI effort=medium
            # -3: Gemini 3 effort=high, -4: Gemini 3 effort=low
            if thinking_mode and uses_effort_reasoning:
                marker = -1 if thinking_budget == "effort_high" else -2
                return (llm_response, None, marker)
            elif thinking_mode and uses_enabled_reasoning:
                marker = -3 if thinking_budget == "enabled_high" else -4
                return (llm_response, None, marker)
            else:
                return (
                    llm_response,
                    None,
                    reasoning_budget_actual if thinking_mode else None,
                )

        except httpx.TimeoutException:
            timeout_mins = OPENROUTER_TIMEOUT / 60
            return (
                "",
                f"Request timed out after {OPENROUTER_TIMEOUT:.0f} seconds ({timeout_mins:.0f} minutes). "
                f"Model may be overloaded or experiencing issues.",
                None,
            )
        except Exception as e:
            return "", f"Error calling API: {e}", None
