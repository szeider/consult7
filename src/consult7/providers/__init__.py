"""Provider implementations for Consult7."""

from .google import GoogleProvider, GOOGLE_AVAILABLE
from .openai import OpenAIProvider, OPENAI_AVAILABLE
from .openrouter import OpenRouterProvider

# Only include available providers
PROVIDERS = {
    "openrouter": OpenRouterProvider(),
}

if GOOGLE_AVAILABLE:
    PROVIDERS["google"] = GoogleProvider()

if OPENAI_AVAILABLE:
    PROVIDERS["openai"] = OpenAIProvider()

__all__ = ["PROVIDERS", "GoogleProvider", "OpenAIProvider", "OpenRouterProvider"]
