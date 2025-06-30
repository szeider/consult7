"""Provider implementations for Consult7."""

import logging

from .google import GoogleProvider, GOOGLE_AVAILABLE
from .openai import OpenAIProvider, OPENAI_AVAILABLE
from .openrouter import OpenRouterProvider

logger = logging.getLogger(__name__)

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
            logger.debug("No custom providers found in configuration")
            return
            
        for config in custom_configs:
            # Namespace collision protection - built-ins win
            if config.name in PROVIDERS:
                logger.warning(f"Custom provider '{config.name}' conflicts with built-in. Skipping.")
                continue
                
            try:
                provider_instance = ConfigurableOpenAIProvider(config)
                PROVIDERS[config.name] = provider_instance
                logger.info(f"Registered custom provider: {config.name}")
            except Exception as e:
                logger.error(f"Failed to register custom provider '{config.name}': {e}")
                
    except Exception as e:
        logger.error(f"Failed to load custom providers: {e}")
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
