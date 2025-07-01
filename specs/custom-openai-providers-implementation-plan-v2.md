# Implementation Plan: Custom OpenAI-Compatible Endpoints (v2 - Direct API Key)

**Status:** Ready for Implementation  
**Created:** 2025-06-30  
**Updated:** 2025-06-30  
**Priority:** Medium  
**Complexity:** Medium  
**Estimated Timeline:** 6 days

## Overview

Based on comprehensive analysis of the Consult7 codebase, here's a simplified plan to add support for custom OpenAI-compatible API endpoints using the existing direct command-line API key approach, maintaining full consistency with current providers like OpenRouter.

## Key Changes from v1

- **No environment variables**: API keys passed directly via command line like existing providers
- **Simpler configuration**: Only endpoint URLs and model definitions needed
- **Consistent CLI usage**: `uvx consult7 <provider-name> <api-key>`
- **Reduced complexity**: No separate authentication configuration

## Architecture Flow

```
[Configuration File] --> [Config Loader] --> [Dynamic Provider Registration]
        |                                            |
        v                                            v
[Custom Providers] --> [Generic OpenAI Provider] --> [CLI Handler]
        |                                            |
        v                                            v
    [Runtime] -----> [Existing Provider Pattern] --> [MCP Server]
```

## Implementation Phases

## Phase 1: Configuration Foundation (Days 1-2)

### Files to Create/Modify:
- `src/consult7/config/models.py` (NEW) - Pydantic models for configuration schema
- `src/consult7/config/loader.py` (NEW) - Configuration loading and validation
- `providers.yaml` (NEW) - Example configuration file  
- `src/consult7/constants.py` - Add config file discovery paths

### Simplified Configuration Schema (YAML):
```yaml
# ~/.config/consult7/providers.yaml
# Direct API key approach - no environment variables

custom_providers:
  - name: "github-copilot"
    display_name: "GitHub Copilot"
    api_base_url: "https://api.githubcopilot.com"
    
    feature_support:
      tool_calling: true
      json_mode: true
      streaming: true  
      thinking_mode: false
    
    models:
      - name: "gemini-2.5-pro"
        context_length: 1000000
        max_output_tokens: 8192
      - name: "gpt-4.1"
        context_length: 1000000
        max_output_tokens: 4096
      - name: "o3-mini"
        context_length: 200000
        max_output_tokens: 65536

  - name: "groq"
    display_name: "Groq"
    api_base_url: "https://api.groq.com/openai/v1"
    
    feature_support:
      tool_calling: true
      json_mode: true
      streaming: true
      thinking_mode: false
    
    # Global parameter overrides for all models
    parameter_overrides:
      temperature: 0.2
    
    models:
      - name: "llama3-8b-8192"
        context_length: 8192
        max_output_tokens: 4096
      - name: "gemma-7b-it"
        context_length: 8192
        max_output_tokens: 4096
```

### Implementation Tasks:
1. Create Pydantic models for robust schema validation
2. Implement ConfigLoader that reads YAML configuration
3. Configuration file discovery hierarchy:
   - `CONSULT7_CONFIG_PATH` environment variable (for path only)
   - `./providers.yaml` (project-specific)
   - `~/.config/consult7/providers.yaml` (user-global)
   - `/etc/consult7/providers.yaml` (system-wide)
4. Graceful error handling with informative messages

## Phase 2: Generic Provider Implementation (Days 3-4)

### Files to Create/Modify:
- `src/consult7/providers/configurable_openai_provider.py` (NEW)
- `src/consult7/exceptions.py` - Add custom exceptions if needed

### Key Implementation Details:
```python
class ConfigurableOpenAIProvider(BaseProvider):
    def __init__(self, config: CustomProviderConfig):
        self.config = config
        self.name = config.name
        self.display_name = config.display_name
        
    async def call_llm(self, content, query, model_name, api_key, thinking_mode=False, thinking_budget=None):
        """Call custom OpenAI-compatible API with direct API key."""
        if not api_key:
            return "", "No API key provided. Use --api-key flag", None
            
        # Check feature support before attempting
        if thinking_mode and not self.config.feature_support.thinking_mode:
            return "", f"Provider '{self.name}' does not support thinking mode", None
        
        # Create client with provided API key
        client = AsyncOpenAI(
            base_url=self.config.api_base_url,
            api_key=api_key  # Direct from command line
        )
        
        # Apply parameter overrides from config
        params = {"model": model_name, "messages": messages}
        if self.config.parameter_overrides:
            params.update(self.config.parameter_overrides)
        
        # Rest of implementation similar to OpenRouterProvider
```

### Features:
- Implements BaseProvider interface with configuration-driven behavior
- Direct API key usage from command line arguments
- Feature support checking with clear error messages
- Global and model-specific parameter override system
- Consistent with existing provider patterns

## Phase 3: Dynamic Provider Registration (Day 5)

### Files to Modify:
- `src/consult7/providers/__init__.py` - Enhanced dynamic registration
- `src/consult7/server.py` - Remove hardcoded provider validation
- `src/consult7/tool_definitions.py` - Dynamic model examples
- `src/consult7/constants.py` - Dynamic test models

### Implementation Strategy:
```python
# Enhanced registration in providers/__init__.py
def _register_custom_providers():
    """Load and register providers from configuration."""
    try:
        from ..config.loader import ConfigLoader
        from .configurable_openai_provider import ConfigurableOpenAIProvider
        
        custom_configs = ConfigLoader.load()
        if not custom_configs:
            return
            
        for config in custom_configs:
            # Namespace collision protection - built-ins win
            if config.name in PROVIDERS:
                logging.warning(f"Custom provider '{config.name}' conflicts with built-in. Skipping.")
                continue
                
            try:
                provider_instance = ConfigurableOpenAIProvider(config)
                PROVIDERS[config.name] = provider_instance
                
                # Add to MODEL_EXAMPLES for tool descriptions
                if config.models:
                    ToolDescriptions.MODEL_EXAMPLES[config.name] = [
                        model.name for model in config.models[:3]  # Show first 3 models
                    ]
                
                # Add default test model
                if config.models:
                    TEST_MODELS[config.name] = config.models[0].name
                
                logging.info(f"Registered custom provider: {config.name}")
            except Exception as e:
                logging.error(f"Failed to register custom provider '{config.name}': {e}")
                
    except Exception as e:
        logging.error(f"Failed to load custom providers: {e}")
        # Application continues with built-in providers only

# Registration order: built-ins first, then custom
_register_provider("openrouter", OpenRouterProvider)
_register_provider("google", GoogleProvider) 
_register_provider("openai", OpenAIProvider)
_register_custom_providers()
```

### Key Changes:
- Dynamic provider registration at startup
- Built-in providers take precedence over custom providers
- Update MODEL_EXAMPLES and TEST_MODELS dynamically
- Comprehensive error isolation

## Phase 4: Testing & Documentation (Day 6)

### Files to Create/Modify:
- `tests/test_config_loader.py` (NEW) - Configuration system tests
- `tests/test_configurable_provider.py` (NEW) - Provider implementation tests
- `docs/CUSTOM_PROVIDERS.md` (NEW) - User guide
- `README.md` - Add custom provider section

### Testing Strategy:
- Unit tests for configuration loading and validation
- Integration tests with mock HTTP responses
- Backward compatibility verification
- Error handling for missing/malformed configs

### Documentation Requirements:
- Complete YAML schema reference
- Example configurations for popular providers
- Troubleshooting guide
- Migration guide for users

## Usage After Implementation

Users would configure custom providers once, then use them exactly like built-in providers:

1. **Create configuration file:**
```bash
# ~/.config/consult7/providers.yaml
custom_providers:
  - name: "github-copilot"
    api_base_url: "https://api.githubcopilot.com"
    # ... rest of config
```

2. **Use in Claude Desktop config:**
```json
{
  "consult7-github-copilot": {
    "type": "stdio",
    "command": "uvx",
    "args": [
      "consult7",
      "github-copilot",
      "ghu_GfgOAL0fBfN..."
    ]
  }
}
```

3. **Test custom provider:**
```bash
uvx consult7 github-copilot ghu_GfgOAL0fBfN... --test
```

## Key Differences from v1

### Removed:
- Environment variable configuration for API keys
- Complex authentication configuration
- Discovery spike phase (simplified approach)
- Security-focused API key management (uses existing pattern)

### Simplified:
- Configuration only needs endpoint URL and models
- Direct API key passing like existing providers
- No changes to existing security model
- Consistent CLI usage pattern

### Benefits:
- Fully consistent with existing providers
- Simpler configuration file
- No environment variable complexity
- Easier to understand and use
- Shorter implementation timeline

## Success Criteria

- [ ] Custom providers work exactly like built-in providers
- [ ] API keys passed directly via command line
- [ ] Configuration file defines endpoints and models only
- [ ] All existing functionality continues unchanged
- [ ] Test mode works with custom providers
- [ ] Clear error messages for configuration issues
- [ ] Documentation with working examples

## Risk Mitigation

- **Configuration errors**: Comprehensive validation with clear messages
- **Provider conflicts**: Built-in providers always take precedence
- **API compatibility**: Test with common providers (Groq, Anyscale)
- **Performance**: Configuration loaded once at startup

---

This simplified plan maintains full consistency with existing providers while adding extensibility through configuration files. The direct API key approach matches current usage patterns perfectly.