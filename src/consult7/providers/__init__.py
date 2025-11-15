"""Provider implementations for Consult7."""

from .openrouter import OpenRouterProvider

# Only OpenRouter is supported
PROVIDERS = {
    "openrouter": OpenRouterProvider(),
}

__all__ = ["PROVIDERS", "OpenRouterProvider"]
