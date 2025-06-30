# Custom OpenAI-Compatible Providers

This guide explains how to add custom OpenAI-compatible API endpoints to Consult7 without modifying source code.

## Overview

Consult7 now supports custom providers through YAML configuration files. This allows you to:

- Add any OpenAI-compatible API endpoint (Groq, Anyscale, local LLMs, etc.)
- Configure models, context lengths, and parameter overrides
- Specify feature support (tool calling, thinking mode, etc.)
- Use secure environment variable-based API key management

## Quick Start

1. **Create Configuration File**
   ```bash
   mkdir -p ~/.config/consult7
   cp providers.yaml ~/.config/consult7/providers.yaml
   ```

2. **Set API Keys**
   ```bash
   export GROQ_API_KEY="your-groq-api-key"
   export ANYSCALE_API_KEY="your-anyscale-api-key"
   ```

3. **Use Custom Provider**
   ```bash
   # Test custom provider
   uvx consult7 groq your-api-key --test
   
   # Use in MCP
   claude mcp add -s user consult7 uvx -- consult7 groq your-api-key
   ```

## Configuration File Format

### Location Priority

Configuration files are loaded in this order (first found is used):

1. `$CONSULT7_CONFIG_PATH` environment variable
2. `./providers.yaml` (project-specific)
3. `~/.config/consult7/providers.yaml` (user-global)
4. `/etc/consult7/providers.yaml` (system-wide, Unix only)

### YAML Schema

```yaml
custom_providers:
  - name: "groq"                              # CLI provider name
    display_name: "Groq"                      # Human-readable name
    api_base_url: "https://api.groq.com/openai/v1"
    
    authentication:
      type: "bearer_token"                    # Currently only bearer_token supported
      api_key_env: "GROQ_API_KEY"            # Environment variable name
    
    feature_support:
      tool_calling: true                      # Supports function/tool calling
      json_mode: true                         # Supports JSON response mode
      streaming: true                         # Supports streaming responses
      thinking_mode: false                    # Supports reasoning/thinking mode
    
    parameter_overrides:                      # Global overrides for all models
      temperature: 0.2
      top_p: 0.9
    
    models:
      - name: "llama3-8b-8192"               # Model name as used by provider
        context_length: 8192                  # Maximum context tokens
        max_output_tokens: 4096               # Maximum output tokens
        parameter_overrides:                  # Model-specific overrides
          temperature: 0.1
      
      - name: "gemma-7b-it"
        context_length: 8192
        max_output_tokens: 4096
```

## Security Best Practices

### API Key Management

- **Never put API keys in configuration files**
- Always use environment variables for secrets
- Use specific environment variable names (e.g., `GROQ_API_KEY`, not `API_KEY`)

### Example Environment Setup

```bash
# ~/.bashrc or ~/.zshrc
export GROQ_API_KEY="gsk_..."
export ANYSCALE_API_KEY="esecret_..."
export TOGETHER_API_KEY="..."
```

### Configuration Validation

The system validates all configuration:
- Provider names must be unique and alphanumeric (+ hyphens/underscores)
- URLs must be valid HTTP/HTTPS endpoints  
- Token limits must be positive integers
- Built-in provider names (`openai`, `google`, `openrouter`) are reserved

## Provider Examples

### Groq

```yaml
custom_providers:
  - name: "groq"
    display_name: "Groq"
    api_base_url: "https://api.groq.com/openai/v1"
    authentication:
      type: "bearer_token"
      api_key_env: "GROQ_API_KEY"
    feature_support:
      tool_calling: true
      thinking_mode: false
    models:
      - name: "llama3-8b-8192"
        context_length: 8192
        max_output_tokens: 4096
      - name: "mixtral-8x7b-32768"
        context_length: 32768
        max_output_tokens: 4096
```

### Anyscale Endpoints

```yaml
custom_providers:
  - name: "anyscale"
    display_name: "Anyscale Endpoints"
    api_base_url: "https://api.endpoints.anyscale.com/v1"
    authentication:
      type: "bearer_token"
      api_key_env: "ANYSCALE_API_KEY"
    feature_support:
      tool_calling: false
      thinking_mode: false
    models:
      - name: "meta-llama/Llama-3-8B-Instruct"
        context_length: 8192
        max_output_tokens: 4096
```

### Local LLM (Ollama + OpenAI Compatibility)

```yaml
custom_providers:
  - name: "local-ollama"
    display_name: "Local Ollama"
    api_base_url: "http://localhost:11434/v1"
    authentication:
      type: "bearer_token"
      api_key_env: "OLLAMA_API_KEY"  # Set to any value
    feature_support:
      tool_calling: false
      thinking_mode: false
    models:
      - name: "llama3"
        context_length: 8192
        max_output_tokens: 4096
```

## Usage

### Command Line

```bash
# List available providers
uvx consult7 --help

# Test custom provider
uvx consult7 groq fake-key --test

# Use custom provider
uvx consult7 groq $GROQ_API_KEY "/path/to/code" "*.py" "What does this code do?"
```

### MCP Integration

```json
{
  "mcpServers": {
    "consult7-groq": {
      "command": "uvx",
      "args": ["consult7", "groq", "env:GROQ_API_KEY"]
    },
    "consult7-anyscale": {
      "command": "uvx", 
      "args": ["consult7", "anyscale", "env:ANYSCALE_API_KEY"]
    }
  }
}
```

## Troubleshooting

### Common Issues

1. **Provider not found**
   ```
   Error: Invalid provider 'groq'
   Valid providers: openrouter, google, openai
   ```
   - Check configuration file location and syntax
   - Verify YAML is valid
   - Check logs for configuration errors

2. **API key not found**
   ```
   API key environment variable 'GROQ_API_KEY' not set
   ```
   - Set the environment variable: `export GROQ_API_KEY="your-key"`
   - Check variable name matches configuration
   - Restart terminal/application after setting

3. **Model not found**
   ```
   Model 'llama3-8b-8192' not available in provider 'groq'
   ```
   - Check model name spelling in configuration
   - Verify model is supported by the provider's API
   - Check provider documentation for exact model names

4. **Feature not supported**
   ```
   Provider 'anyscale' does not support thinking_mode
   ```
   - Check `feature_support` configuration
   - Use providers that support the required features
   - Remove feature flags (e.g., `|thinking`) when not supported

### Debug Configuration

```bash
# Check configuration locations
python3 -c "
from consult7.config.loader import ConfigLoader
for loc in ConfigLoader.get_config_locations():
    print(loc)
"

# Validate YAML syntax
python3 -c "
import yaml
with open('providers.yaml') as f:
    config = yaml.safe_load(f)
    print('✓ Valid YAML')
    print(f'Providers: {len(config.get(\"custom_providers\", []))}')
"
```

### Logging

Enable debug logging to see provider registration:

```bash
export CONSULT7_LOG_LEVEL=DEBUG
uvx consult7 groq $GROQ_API_KEY --test
```

## Advanced Configuration

### Parameter Overrides

Control API behavior with global and model-specific overrides:

```yaml
custom_providers:
  - name: "provider"
    # ... other config ...
    parameter_overrides:        # Applied to all models
      temperature: 0.2
      top_p: 0.9
      max_tokens: 2048
    
    models:
      - name: "model-1"
        # ... model config ...
        parameter_overrides:    # Model-specific (overrides global)
          temperature: 0.1      # More deterministic for this model
```

### Environment Variable Substitution

Use environment variables in configuration:

```yaml
custom_providers:
  - name: "dynamic"
    api_base_url: "${CUSTOM_API_URL:-https://default.api.com/v1}"
    authentication:
      api_key_env: "${API_KEY_VAR:-DEFAULT_API_KEY}"
```

### Multiple Configurations

Use different configurations for different contexts:

```bash
# Development
export CONSULT7_CONFIG_PATH="./dev-providers.yaml"

# Production  
export CONSULT7_CONFIG_PATH="./prod-providers.yaml"

# User-specific
# Uses ~/.config/consult7/providers.yaml automatically
```

## Compatibility Notes

- **Backward Compatibility**: Built-in providers (`openai`, `google`, `openrouter`) continue to work unchanged
- **Provider Priority**: Built-in providers take precedence over custom providers with the same name
- **API Compatibility**: Custom providers must implement OpenAI's chat completions API
- **Feature Support**: Not all providers support all features (tool calling, thinking mode, etc.)

## Migration from Hardcoded Providers

No migration is required. Existing usage continues to work:

```bash
# These continue to work as before
uvx consult7 openrouter $OR_API_KEY --test
uvx consult7 google $GOOGLE_API_KEY --test
uvx consult7 openai $OPENAI_API_KEY --test
```

Custom providers are additive and don't affect existing functionality.