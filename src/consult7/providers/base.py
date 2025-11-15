"""Base provider interface and shared utilities for Consult7."""

from abc import ABC, abstractmethod
from typing import Optional, Tuple

from ..constants import MAX_RESPONSE_SIZE


def process_llm_response(response_content: Optional[str]) -> str:
    """Normalize and truncate LLM response if needed.

    Args:
        response_content: The response content from the LLM

    Returns:
        Processed response content
    """
    response = response_content or ""
    if len(response) > MAX_RESPONSE_SIZE:
        return response[:MAX_RESPONSE_SIZE] + "\n[TRUNCATED - Response exceeded size limit]"
    return response


class BaseProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def get_model_info(self, model_name: str, api_key: Optional[str]) -> Optional[dict]:
        """Get model context information.

        Args:
            model_name: The name of the model
            api_key: API key for the provider

        Returns:
            Dictionary with model information or None if not available
            Expected keys: context_length, max_output_tokens, provider
        """
        pass

    @abstractmethod
    async def call_llm(
        self,
        content: str,
        query: str,
        model_name: str,
        api_key: str,
        thinking_mode: bool = False,
        thinking_budget: Optional[int] = None,
    ) -> Tuple[str, Optional[str], Optional[int]]:
        """Call the LLM and return the response.

        Args:
            content: The formatted file content
            query: The user's query
            model_name: The model to use
            api_key: API key for the provider
            thinking_mode: Whether thinking/reasoning mode is enabled
            thinking_budget: Number of thinking tokens to use (if applicable)

        Returns:
            Tuple of (response, error_message, actual_thinking_budget_used)
        """
        pass
