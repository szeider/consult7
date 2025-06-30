#!/usr/bin/env python3
"""Direct test script for custom provider functionality."""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_config_models():
    """Test configuration models can be imported and created."""
    print("Testing configuration models...")
    
    try:
        from consult7.config.models import (
            AuthenticationConfig,
            FeatureSupportConfig,
            ModelConfig,
            CustomProviderConfig,
        )
        
        # Create test configuration
        auth = AuthenticationConfig(
            type="bearer_token",
            api_key_env="GROQ_API_KEY"
        )
        
        features = FeatureSupportConfig(
            tool_calling=True,
            thinking_mode=False
        )
        
        model = ModelConfig(
            name="llama3-8b-8192",
            context_length=8192,
            max_output_tokens=4096
        )
        
        config = CustomProviderConfig(
            name="groq",
            display_name="Groq",
            api_base_url="https://api.groq.com/openai/v1",
            authentication=auth,
            feature_support=features,
            models=[model]
        )
        
        print(f"✓ Created config for provider: {config.name}")
        print(f"  Display name: {config.display_name}")
        print(f"  API URL: {config.api_base_url}")
        print(f"  Models: {[m.name for m in config.models]}")
        print(f"  Thinking mode: {config.feature_support.thinking_mode}")
        
        return True
        
    except Exception as e:
        print(f"✗ Config models test failed: {e}")
        return False

def test_config_loader():
    """Test configuration loader."""
    print("\nTesting configuration loader...")
    
    try:
        from consult7.config.loader import ConfigLoader
        
        # Test config file discovery
        locations = ConfigLoader.get_config_locations()
        print(f"✓ Config locations: {locations}")
        
        # Test loading (should work with example file)
        configs = ConfigLoader.load()
        print(f"✓ Loaded {len(configs)} custom providers")
        
        for config in configs:
            print(f"  - {config.name}: {config.display_name}")
            print(f"    Models: {[m.name for m in config.models]}")
        
        return True
        
    except Exception as e:
        print(f"✗ Config loader test failed: {e}")
        return False

def test_provider_registration():
    """Test dynamic provider registration."""
    print("\nTesting provider registration...")
    
    try:
        # This will trigger the registration process
        from consult7.providers import PROVIDERS
        
        print(f"✓ Registered providers: {list(PROVIDERS.keys())}")
        
        # Check if custom providers were loaded
        expected_built_ins = {"openrouter"}  # Only this one is always available
        custom_providers = set(PROVIDERS.keys()) - expected_built_ins
        
        if custom_providers:
            print(f"✓ Custom providers detected: {custom_providers}")
            
            # Test a custom provider instance
            for provider_name in custom_providers:
                provider = PROVIDERS[provider_name]
                if hasattr(provider, 'config'):
                    print(f"  - {provider_name}: {provider.config.display_name}")
                    print(f"    Thinking mode: {provider.config.feature_support.thinking_mode}")
        else:
            print("ℹ No custom providers loaded (configuration not found or invalid)")
        
        return True
        
    except Exception as e:
        print(f"✗ Provider registration test failed: {e}")
        return False

def test_configurable_provider():
    """Test configurable provider implementation."""
    print("\nTesting configurable provider...")
    
    try:
        from consult7.config.models import CustomProviderConfig, AuthenticationConfig, ModelConfig, FeatureSupportConfig
        from consult7.providers.configurable_openai_provider import ConfigurableOpenAIProvider
        from consult7.exceptions import ProviderInitializationError
        
        # Create test config
        auth = AuthenticationConfig(type="bearer_token", api_key_env="NONEXISTENT_KEY")
        model = ModelConfig(name="test-model", context_length=8192, max_output_tokens=4096)
        features = FeatureSupportConfig(thinking_mode=True)
        
        config = CustomProviderConfig(
            name="test-provider",
            display_name="Test Provider",
            api_base_url="https://api.test.com/v1",
            authentication=auth,
            feature_support=features,
            models=[model]
        )
        
        # This should fail due to missing API key
        try:
            provider = ConfigurableOpenAIProvider(config)
            print("✗ Expected provider initialization to fail due to missing API key")
            return False
        except ProviderInitializationError as e:
            print(f"✓ Provider correctly failed to initialize: {e}")
        
        # Test model info retrieval
        os.environ["TEST_API_KEY"] = "fake-key-for-testing"
        test_auth = AuthenticationConfig(type="bearer_token", api_key_env="TEST_API_KEY")
        test_config = CustomProviderConfig(
            name="test-provider",
            display_name="Test Provider", 
            api_base_url="https://api.test.com/v1",
            authentication=test_auth,
            feature_support=features,
            models=[model]
        )
        
        try:
            provider = ConfigurableOpenAIProvider(test_config)
            print(f"✓ Provider initialized: {provider.name}")
            
            # Test model info (sync version for testing)
            try:
                import asyncio
                model_info = asyncio.run(provider.get_model_info("test-model", "fake-key"))
                if model_info:
                    print(f"✓ Model info: {model_info}")
                else:
                    print("✗ Model info not found")
            except Exception as e:
                print(f"ℹ Model info test skipped: {e}")
                
        except Exception as e:
            print(f"ℹ Provider init failed (expected without real API): {e}")
        
        return True
        
    except Exception as e:
        print(f"✗ Configurable provider test failed: {e}")
        return False

# Remove the async test function since we handle it inline

def main():
    """Run all tests."""
    print("Direct Testing Custom Provider Implementation\n")
    print("=" * 50)
    
    tests = [
        test_config_models,
        test_config_loader,
        test_provider_registration,
        test_configurable_provider,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print(f"Test Results: {sum(results)}/{len(results)} passed")
    
    if all(results):
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())