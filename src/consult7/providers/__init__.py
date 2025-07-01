"""Provider implementations for Consult7."""

import logging
import sys

from .google import GoogleProvider, GOOGLE_AVAILABLE
from .openai import OpenAIProvider, OPENAI_AVAILABLE
from .openrouter import OpenRouterProvider

logger = logging.getLogger("consult7")

# Initialize with built-in providers first
PROVIDERS = {}


def _register_provider(name: str, provider_instance):
    """Register a provider instance.
    
    Args:
        name: Provider name
        provider_instance: Instance of a provider class
    """
    PROVIDERS[name] = provider_instance
    logger.debug(f"Registered built-in provider: {name}")


def _register_custom_providers():
    """Load and register providers from configuration with error isolation."""
    try:
        from ..config.loader import ConfigLoader
        from .configurable_openai_provider import ConfigurableOpenAIProvider

        custom_configs = ConfigLoader.load()
        if not custom_configs:
            logger.info("No custom providers found in configuration")
            return

        logger.info(f"Loading {len(custom_configs)} custom providers")

        for config in custom_configs:
            # Namespace collision protection - built-ins win
            if config.name in PROVIDERS:
                logger.warning(f"Custom provider '{config.name}' conflicts with built-in. Skipping.")
                continue

            try:
                provider_instance = ConfigurableOpenAIProvider(config)
                PROVIDERS[config.name] = provider_instance

                # Add model examples for tool descriptions
                from ..tool_definitions import ToolDescriptions
                if config.models:
                    examples = []
                    for i, model in enumerate(config.models[:3]):  # Show first 3 models
                        context_str = f"{model.context_length // 1000}k" if model.context_length >= 1000 else str(model.context_length)
                        examples.append(f'"{model.name}" ({context_str} context)')
                    ToolDescriptions.MODEL_EXAMPLES[config.name] = examples

                # Add default test model
                from ..constants import TEST_MODELS
                if config.models:
                    TEST_MODELS[config.name] = config.models[0].name

                logger.info(f"Registered custom provider: {config.name}")
            except Exception as e:
                logger.error(f"Failed to register custom provider '{config.name}': {e}")

    except Exception as e:
        import traceback
        logger.error(f"Failed to load custom providers: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Application continues with built-in providers only


# Registration order: built-ins first, then custom
_register_provider("openrouter", OpenRouterProvider())

if GOOGLE_AVAILABLE:
    _register_provider("google", GoogleProvider())

if OPENAI_AVAILABLE:
    _register_provider("openai", OpenAIProvider())

# Register custom providers (additive, isolated from built-ins)
_register_custom_providers()

__all__ = ["PROVIDERS", "GoogleProvider", "OpenAIProvider", "OpenRouterProvider"]
