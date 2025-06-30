"""Configurable OpenAI-compatible provider implementation."""

import logging
import os
from typing import Dict, Optional, Tuple

from openai import AsyncOpenAI

from ..config.models import CustomProviderConfig, ModelConfig
from ..constants import DEFAULT_TEMPERATURE, LLM_CALL_TIMEOUT
from ..exceptions import FeatureNotSupportedError, ProviderInitializationError
from .base import BaseProvider, process_llm_response

logger = logging.getLogger(__name__)


class ConfigurableOpenAIProvider(BaseProvider):
    """Generic OpenAI-compatible provider using configuration."""
    
    def __init__(self, config: CustomProviderConfig):
        """Initialize the configurable provider.
        
        Args:
            config: CustomProviderConfig with provider details
            
        Raises:
            ProviderInitializationError: If initialization fails
        """
        self.config = config
        self.name = config.name
        
        # Secure API key loading from environment
        api_key = os.getenv(config.authentication.api_key_env)
        if not api_key:
            raise ProviderInitializationError(
                f"API key environment variable '{config.authentication.api_key_env}' not set",
                provider_name=config.name
            )
        
        # Initialize OpenAI client with custom base URL
        try:
            self.client = AsyncOpenAI(
                base_url=config.api_base_url,
                api_key=api_key,
                timeout=LLM_CALL_TIMEOUT
            )
            logger.debug(f"Initialized {config.name} provider with base URL: {config.api_base_url}")
        except Exception as e:
            raise ProviderInitializationError(
                f"Failed to initialize OpenAI client: {e}",
                provider_name=config.name
            )
    
    def _get_model_config(self, model_name: str) -> Optional[ModelConfig]:
        """Get configuration for a specific model.
        
        Args:
            model_name: Name of the model
            
        Returns:
            ModelConfig if found, None otherwise
        """
        for model in self.config.models:
            if model.name == model_name:
                return model
        return None
    
    def _build_request_params(self, model_name: str, messages: list, thinking_mode: bool = False, thinking_budget: Optional[int] = None) -> Dict:
        """Build request parameters with overrides applied.
        
        Args:
            model_name: Name of the model
            messages: List of messages for the conversation
            thinking_mode: Whether thinking mode is requested
            thinking_budget: Thinking token budget (if applicable)
            
        Returns:
            Dictionary of request parameters
        """
        # Base parameters
        params = {
            "model": model_name,
            "messages": messages,
            "temperature": DEFAULT_TEMPERATURE,
        }
        
        # Apply global parameter overrides
        if self.config.parameter_overrides:
            params.update(self.config.parameter_overrides)
        
        # Apply model-specific parameter overrides
        model_config = self._get_model_config(model_name)
        if model_config and model_config.parameter_overrides:
            params.update(model_config.parameter_overrides)
        
        # Handle thinking mode if supported
        if thinking_mode:
            if not self.config.feature_support.thinking_mode:
                raise FeatureNotSupportedError(
                    f"Provider '{self.name}' does not support thinking_mode",
                    provider_name=self.name,
                    feature="thinking_mode"
                )
            
            # Add thinking mode parameters (implementation may vary by provider)
            if thinking_budget:
                params["reasoning_effort"] = thinking_budget
        
        return params
    
    async def get_model_info(self, model_name: str, api_key: str) -> Optional[dict]:
        """Get model context information from configuration.
        
        Args:
            model_name: The name of the model
            api_key: API key for the provider (not used, from config instead)
            
        Returns:
            Dictionary with model information or None if not available
        """
        model_config = self._get_model_config(model_name)
        if not model_config:
            logger.warning(f"Model '{model_name}' not found in {self.name} provider configuration")
            return None
        
        return {
            "context_length": model_config.context_length,
            "max_output_tokens": model_config.max_output_tokens,
            "provider": self.config.display_name,
            "model_name": model_name,
        }
    
    async def call_llm(
        self,
        content: str,
        query: str,
        model_name: str,
        api_key: str,  # Not used, from config instead
        thinking_mode: bool = False,
        thinking_budget: Optional[int] = None,
    ) -> Tuple[str, Optional[str], Optional[int]]:
        """Call the LLM and return the response.
        
        Args:
            content: The formatted file content
            query: The user's query
            model_name: The model to use
            api_key: API key (not used, from config instead)
            thinking_mode: Whether thinking/reasoning mode is enabled
            thinking_budget: Number of thinking tokens to use (if applicable)
            
        Returns:
            Tuple of (response, error_message, actual_thinking_budget_used)
        """
        try:
            # Validate model exists in configuration
            if not self._get_model_config(model_name):
                return "", f"Model '{model_name}' not available in provider '{self.name}'", None
            
            # Prepare messages
            messages = [
                {"role": "user", "content": f"{content}\n\nQuery: {query}"}
            ]
            
            # Build request parameters with configuration overrides
            params = self._build_request_params(model_name, messages, thinking_mode, thinking_budget)
            
            logger.debug(f"Calling {self.name} API with model {model_name}")
            
            # Make API call
            response = await self.client.chat.completions.create(**params)
            
            # Extract response content
            if response.choices and response.choices[0].message:
                response_content = response.choices[0].message.content
                processed_response = process_llm_response(response_content)
                
                # Extract thinking budget used (if available)
                thinking_used = None
                if thinking_mode and hasattr(response, "usage") and hasattr(response.usage, "reasoning_tokens"):
                    thinking_used = response.usage.reasoning_tokens
                
                logger.debug(f"Received response from {self.name} (length: {len(processed_response)})")
                return processed_response, None, thinking_used
            else:
                logger.warning(f"Empty response from {self.name} API")
                return "", "Empty response received", None
                
        except FeatureNotSupportedError:
            # Re-raise feature support errors
            raise
        except Exception as e:
            error_msg = f"API call failed for {self.name}: {str(e)}"
            logger.error(error_msg)
            return "", error_msg, None