"""Pydantic models for configuration schema validation."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator


class AuthenticationConfig(BaseModel):
    """Authentication configuration for a custom provider."""
    
    type: str = Field(default="bearer_token", description="Authentication type")
    api_key_env: str = Field(..., description="Environment variable name for API key")
    
    @validator("type")
    def validate_auth_type(cls, v):
        valid_types = ["bearer_token"]
        if v not in valid_types:
            raise ValueError(f"Authentication type must be one of: {valid_types}")
        return v


class FeatureSupportConfig(BaseModel):
    """Feature support configuration for a custom provider."""
    
    tool_calling: bool = Field(default=True, description="Whether provider supports tool calling")
    json_mode: bool = Field(default=True, description="Whether provider supports JSON mode")
    streaming: bool = Field(default=True, description="Whether provider supports streaming")
    thinking_mode: bool = Field(default=False, description="Whether provider supports thinking mode")


class ModelConfig(BaseModel):
    """Configuration for a specific model within a provider."""
    
    name: str = Field(..., description="Model name as used by the provider")
    context_length: int = Field(..., description="Maximum context length in tokens")
    max_output_tokens: int = Field(..., description="Maximum output tokens")
    parameter_overrides: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="Model-specific parameter overrides"
    )
    
    @validator("context_length", "max_output_tokens")
    def validate_positive_integers(cls, v):
        if v <= 0:
            raise ValueError("Token limits must be positive integers")
        return v


class CustomProviderConfig(BaseModel):
    """Configuration for a custom OpenAI-compatible provider."""
    
    name: str = Field(..., description="Unique provider name for CLI usage")
    display_name: str = Field(..., description="Human-readable provider name")
    api_base_url: str = Field(..., description="Base URL for the OpenAI-compatible API")
    authentication: AuthenticationConfig = Field(..., description="Authentication configuration")
    feature_support: FeatureSupportConfig = Field(
        default_factory=FeatureSupportConfig,
        description="Feature support configuration"
    )
    parameter_overrides: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Global parameter overrides for all models"
    )
    models: List[ModelConfig] = Field(..., description="List of available models")
    
    @validator("name")
    def validate_name(cls, v):
        # Ensure name is valid for CLI usage
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Provider name must contain only alphanumeric characters, hyphens, and underscores")
        if v in ["openrouter", "google", "openai"]:
            raise ValueError(f"Provider name '{v}' conflicts with built-in provider")
        return v
    
    @validator("api_base_url")
    def validate_url(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("API base URL must start with http:// or https://")
        return v.rstrip("/")  # Remove trailing slash for consistency
    
    @validator("models")
    def validate_models_not_empty(cls, v):
        if not v:
            raise ValueError("At least one model must be specified")
        return v


class ConfigurationFile(BaseModel):
    """Root configuration file schema."""
    
    custom_providers: List[CustomProviderConfig] = Field(
        default_factory=list,
        description="List of custom provider configurations"
    )
    
    @validator("custom_providers")
    def validate_unique_provider_names(cls, v):
        names = [provider.name for provider in v]
        if len(names) != len(set(names)):
            raise ValueError("Provider names must be unique")
        return v