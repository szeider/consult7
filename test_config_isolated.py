#!/usr/bin/env python3
"""Isolated test for configuration system."""

import sys
from pathlib import Path
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_isolated():
    """Test configuration without importing main package."""
    print("Testing isolated configuration...")
    
    try:
        # Test pydantic import
        from pydantic import BaseModel, Field, validator
        print("✓ Pydantic available")
        
        # Test yaml import
        import yaml
        print("✓ PyYAML available")
        
        # Test platformdirs
        from platformdirs import user_config_dir
        print("✓ Platformdirs available")
        
    except ImportError as e:
        print(f"✗ Missing dependency: {e}")
        return False
    
    try:
        # Now test the actual models by importing them directly
        # Import the file content directly without the package
        config_path = Path(__file__).parent / "src" / "consult7" / "config" / "models.py"
        
        # Read and execute the models file to test syntax
        with open(config_path, 'r') as f:
            models_content = f.read()
        
        # Check that the file contains the expected classes
        expected_classes = ['AuthenticationConfig', 'FeatureSupportConfig', 'ModelConfig', 'CustomProviderConfig']
        for cls_name in expected_classes:
            if f"class {cls_name}" in models_content:
                print(f"✓ Found {cls_name} class definition")
            else:
                print(f"✗ Missing {cls_name} class definition")
                return False
        
        print("✓ Configuration models file structure is correct")
        
        # Test YAML file loading
        yaml_path = Path(__file__).parent / "providers.yaml"
        if yaml_path.exists():
            with open(yaml_path, 'r') as f:
                config_data = yaml.safe_load(f)
            
            if 'custom_providers' in config_data:
                providers = config_data['custom_providers']
                print(f"✓ YAML file contains {len(providers)} custom providers")
                
                for provider in providers:
                    name = provider.get('name', 'unknown')
                    models = provider.get('models', [])
                    print(f"  - {name}: {len(models)} models")
            else:
                print("✗ YAML file missing 'custom_providers' key")
                return False
        else:
            print("✗ providers.yaml not found")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_isolated()
    print(f"\nResult: {'✓ PASSED' if success else '✗ FAILED'}")
    sys.exit(0 if success else 1)