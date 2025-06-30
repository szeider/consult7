"""Custom exceptions for Consult7."""


class FeatureNotSupportedError(Exception):
    """Raised when a provider doesn't support a requested feature."""
    
    def __init__(self, message: str, provider_name: str = None, feature: str = None):
        super().__init__(message)
        self.provider_name = provider_name
        self.feature = feature


class ConfigurationError(Exception):
    """Raised when there's an issue with custom provider configuration."""
    
    def __init__(self, message: str, config_path: str = None):
        super().__init__(message)
        self.config_path = config_path


class ProviderInitializationError(Exception):
    """Raised when a custom provider fails to initialize."""
    
    def __init__(self, message: str, provider_name: str = None):
        super().__init__(message)
        self.provider_name = provider_name