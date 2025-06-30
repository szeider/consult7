# Implementation Plan: Custom OpenAI-Compatible Endpoints

**Status:** Ready for Implementation  
**Created:** 2025-06-30  
**Updated:** 2025-06-30  
**Priority:** Medium  
**Complexity:** Medium-High  
**Estimated Timeline:** 8 days

## Overview

Based on comprehensive analysis of the Consult7 codebase and research into real-world OpenAI-compatible API variations, here's a production-ready plan to add support for custom OpenAI-compatible API endpoints while maintaining backward compatibility and addressing security concerns.

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

## Current Architecture Analysis

### Strengths
- **Clean Provider Pattern**: Well-designed `BaseProvider` abstract class
- **Robust Error Handling**: Comprehensive timeout and error management
- **Flexible Thinking Mode**: Sophisticated reasoning token management
- **Good Separation of Concerns**: Each provider handles its own configuration

### Extension Points Identified
1. **Provider Registration** (`providers/__init__.py:9-16`): Currently hardcoded to 3 providers
2. **Command Line Validation** (`server.py:105-108`): Hardcoded provider list
3. **Tool Descriptions** (`tool_definitions.py`): Provider-specific model examples hardcoded
4. **Constants** (`constants.py:44-48`): Test models hardcoded per provider

### Real-World API Variations Discovered
Research into OpenAI-compatible APIs reveals significant deviations that must be addressed:

1. **Inconsistent Response Behavior**: APIs cannot guarantee identical results for the same prompt
2. **Schema Differences**: Each provider creates different API schemas, making universal compatibility challenging
3. **Feature Support Variations**: Tool calling, streaming, and parameter support varies significantly
4. **Authentication Variations**: Different header requirements, prefixes, and authentication methods
5. **Model-Specific Requirements**: Chat templates, context specifications, and parameter completeness issues
6. **Error Format Differences**: Non-standard error responses and status codes

## Implementation Phases

**Note**: The discovery spike (Phase 2) is critical for de-risking the project by learning real API quirks before building generic solutions.

## Phase 1: Configuration Foundation (Days 1-2)

### Files to Create/Modify:
- `src/consult7/config/models.py` (NEW) - Pydantic models for configuration schema
- `src/consult7/config/loader.py` (NEW) - Configuration loading and validation
- `providers.yaml` (NEW) - Example configuration file  
- `src/consult7/constants.py` - Add config file discovery paths

### Enhanced Configuration Schema (YAML):
```yaml
# ~/.config/consult7/providers.yaml
# Security-first: API keys via environment variables only

custom_providers:
  - name: "my-groq"
    display_name: "Groq"
    api_base_url: "https://api.groq.com/openai/v1"
    
    authentication:
      type: "bearer_token"
      api_key_env: "GROQ_API_KEY"  # Environment variable name
    
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
        # Model-specific parameter overrides
        parameter_overrides:
          top_p: 0.9
      - name: "gemma-7b-it"
        context_length: 8192
        max_output_tokens: 4096

  - name: "my-anyscale"
    display_name: "Anyscale Endpoints"
    api_base_url: "https://api.endpoints.anyscale.com/v1"
    authentication:
      type: "bearer_token"
      api_key_env: "ANYSCALE_API_KEY"
    feature_support:
      tool_calling: false  # Example: provider doesn't support tools
      json_mode: true
      streaming: true
      thinking_mode: false
    models:
      - name: "meta-llama/Llama-3-8B-Instruct"
        context_length: 8192
        max_output_tokens: 4096
```

### Implementation Tasks:
1. Create Pydantic models for robust schema validation
2. Implement ConfigLoader with environment variable substitution (${VAR} pattern)
3. Configuration file discovery hierarchy:
   - `CONSULT7_CONFIG_PATH` environment variable
   - `./providers.yaml` (project-specific)
   - `~/.config/consult7/providers.yaml` (user-global)
   - `/etc/consult7/providers.yaml` (system-wide)
4. Graceful error handling with informative messages

## Phase 2: Discovery Spike (Day 3)

**Critical De-risking Phase**: Test with a real provider before building generic solution.

### Files to Create/Modify:
- `src/consult7/providers/spike_provider.py` (TEMPORARY) - Real API testing
- `docs/api_quirks_discovered.md` (NEW) - Document findings

### Implementation Strategy:
1. Choose one complex provider (Groq recommended - good documentation, free tier)
2. Create specific (non-generic) provider class using Phase 1 config system
3. Make real API calls and document every quirk, deviation, or required adjustment
4. Test parameter variations, error responses, and edge cases
5. Document findings as input for Phase 3 generic design

### Critical Learning Areas:
- Authentication header variations and requirements
- Required vs. optional parameters differences
- Error response format variations  
- Rate limiting and timeout behavior
- Model name mapping requirements
- Context length validation approaches

## Phase 3: Generic Provider Implementation (Days 4-5)

### Files to Create/Modify:
- `src/consult7/providers/configurable_openai_provider.py` (NEW)
- `src/consult7/exceptions.py` (NEW) - Custom exceptions

### Key Implementation Details:
```python
class FeatureNotSupportedError(Exception):
    """Raised when a provider doesn't support a requested feature."""
    pass

class ConfigurableOpenAIProvider(BaseProvider):
    def __init__(self, config: CustomProviderConfig):
        self.config = config
        self.name = config.name
        
        # Secure API key loading from environment
        api_key = os.getenv(config.authentication.api_key_env)
        if not api_key:
            raise ValueError(f"API key env var '{config.authentication.api_key_env}' not set")
        
        self.client = AsyncOpenAI(
            base_url=config.api_base_url,
            api_key=api_key
        )
        
    async def call_llm(self, content, query, model_name, api_key, thinking_mode=False, thinking_budget=None):
        # Check feature support before attempting
        if thinking_mode and not self.config.feature_support.thinking_mode:
            raise FeatureNotSupportedError(f"Provider '{self.name}' does not support thinking_mode")
        
        # Apply parameter overrides from config
        params = {"model": model_name, "messages": messages}
        if self.config.parameter_overrides:
            params.update(self.config.parameter_overrides)
        
        # Model-specific overrides
        model_config = self._get_model_config(model_name)
        if model_config and model_config.parameter_overrides:
            params.update(model_config.parameter_overrides)
```

### Features:
- Implements BaseProvider interface with configuration-driven behavior
- Environment variable-based API key security
- Feature support checking with custom exceptions
- Global and model-specific parameter override system
- Robust error handling informed by spike discoveries
- Graceful degradation for unsupported features

## Phase 4: Dynamic Provider Registration (Day 6)

### Files to Modify:
- `src/consult7/providers/__init__.py` - Enhanced dynamic registration
- `src/consult7/server.py` - Remove hardcoded provider validation

### Implementation Strategy:
```python
# Enhanced registration with error isolation
def _register_custom_providers():
    """Load and register providers from configuration with error isolation."""
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
_register_custom_providers()  # Additive, isolated from built-ins
```

### Key Changes:
- Isolated error handling prevents custom provider failures from affecting built-ins
- Built-in providers take precedence over custom providers with same names
- Comprehensive logging for troubleshooting custom provider issues
- Graceful degradation when configuration is missing or malformed

## Phase 5: CLI Enhancement & Integration (Day 7)

### Files to Modify:
- `src/consult7/server.py` - Dynamic provider validation and error handling
- `src/consult7/tool_definitions.py` - Dynamic model examples
- Core application logic - Add FeatureNotSupportedError handling

### Critical Changes:
```python
# Replace hardcoded validation:
if provider not in ["openrouter", "google", "openai"]:

# With dynamic validation:
if provider not in PROVIDERS.keys():
    available = ", ".join(PROVIDERS.keys())
    raise ValueError(f"Unknown provider '{provider}'. Available: {available}")
```

### Core Application Integration:
```python
# Add feature support checking where needed
try:
    response = await provider.call_llm(content, query, model, api_key, thinking_mode=True)
except FeatureNotSupportedError as e:
    return f"Error: {e}. Try without thinking mode or use a different provider."
```

### Enhancements:
- Replace hardcoded provider lists with dynamic lookups throughout codebase
- Support custom provider names in CLI arguments  
- Generate helpful error messages listing available providers
- Add feature capability checking in core consultation logic
- Maintain existing CLI argument structure for backward compatibility

## Phase 6: Testing & Documentation (Day 8)

### Files to Create/Modify:
- `tests/test_config_loader.py` (NEW) - Configuration system tests
- `tests/test_configurable_provider.py` (NEW) - Provider implementation tests
- `tests/test_integration.py` (NEW) - End-to-end integration tests
- `docs/CUSTOM_PROVIDERS.md` (NEW) - Comprehensive user guide
- `examples/providers.yaml` (NEW) - Working examples
- `README.md` - Add custom provider documentation section

### Testing Strategy:
- **Unit Tests**: Configuration loading, validation, Pydantic model validation
- **Integration Tests**: httpx-mock tests simulating discovered API quirks
- **End-to-End Tests**: Real provider tests using test configuration
- **Backward Compatibility**: Verify existing providers continue working unchanged
- **Error Handling**: Malformed configs, missing environment variables, API failures
- **Security Tests**: Verify API keys never logged or exposed

### Documentation Requirements:
- Complete YAML schema reference with examples
- Security best practices for API key management
- Troubleshooting guide for common configuration issues
- Provider-specific examples (Groq, Anyscale, Local LLMs)
- Migration guide from hardcoded to configuration-based approach

## Implementation Priority & Timeline

```
Day 1-2: Phase 1 (Foundation) --> Day 3: Phase 2 (Spike) --> Day 4-5: Phase 3 (Provider)
                                                                        |
Day 8: Phase 6 (Testing/Docs) <-- Day 7: Phase 5 (Integration) <-- Day 6: Phase 4 (Registration)
```

**Critical Path**: Configuration → Spike → Generic Provider → Registration → Integration

## Dependencies and Constraints

### New Dependencies Required:
- **PyYAML**: Configuration file parsing
- **Pydantic**: Schema validation and type safety
- **platformdirs**: Cross-platform config directory detection
- **httpx-mock**: Testing framework for API mocking

### Technical Dependencies:
- Phase 1 configuration system must be complete before Phase 2 spike
- Phase 2 spike discoveries directly inform Phase 3 generic provider design
- Phase 3 provider must be complete before Phase 4 registration
- Phase 4 registration must be complete before Phase 5 integration
- Phase 6 testing requires all components integrated

### Security Constraints:
- **No API keys in configuration files**: Environment variables only
- **Fail-safe defaults**: Missing custom config doesn't break built-in providers
- **Input validation**: All configuration must pass Pydantic validation
- **Error isolation**: Custom provider failures must not affect application stability

### Backward Compatibility Constraints:
- **CLI interface**: Existing `uvx consult7 provider api-key` syntax unchanged
- **MCP protocol**: No changes to MCP server interface or tool definitions
- **Provider interface**: All providers must implement unchanged BaseProvider abstract class
- **Error behavior**: Built-in provider error handling must remain identical

## Usage After Implementation

Users would be able to:

1. **Create configuration file:**
```bash
# Create ~/.consult7/providers.yaml with custom endpoints
```

2. **Use custom providers:**
```bash
# Add custom provider to Claude Desktop config
claude mcp add -s user consult7 uvx -- consult7 my-local-llm my-api-key

# Test custom provider
uvx consult7 my-local-llm my-api-key --test
```

3. **Maintain existing functionality:**
```bash
# Existing providers continue to work unchanged
uvx consult7 openrouter sk-or-v1-... --test
```

## Risk Assessment & Mitigation

### Low Risk (Properly Mitigated):
- **Configuration file parsing**: Pydantic validation catches all malformed configs
- **Provider registration**: Error isolation prevents cascading failures
- **Backward compatibility**: Additive-only changes, built-ins take precedence

### Medium Risk (Addressed by Design):
- **API compatibility variations**: Discovery spike identifies real quirks before generalization
- **Authentication variations**: Flexible config schema handles different auth patterns
- **Parameter differences**: Override system provides escape hatch for provider-specific needs
- **Performance impact**: Configuration loaded once at startup, cached thereafter

### High Risk (Critical Attention Required):
- **Security vulnerabilities**: Environment variable-only approach prevents key exposure
- **Complex error scenarios**: Comprehensive exception handling with informative messages
- **Configuration discovery**: Multi-tier fallback hierarchy ensures reliability
- **Provider namespace conflicts**: Built-in providers always take precedence

### Risk Mitigation Strategies:
1. **Spike Phase**: De-risks generic implementation by testing real provider first
2. **Error Isolation**: Custom provider failures cannot affect built-in providers
3. **Graceful Degradation**: Missing features return clear errors rather than crashes
4. **Comprehensive Testing**: Unit, integration, and end-to-end tests cover edge cases
5. **Security First**: No secrets in config files, comprehensive input validation

## Success Criteria

### Core Functionality:
- [ ] Users can define custom OpenAI-compatible endpoints via YAML configuration
- [ ] No source code changes needed for adding new endpoints
- [ ] All existing functionality continues to work unchanged
- [ ] Custom endpoints support parameter overrides and feature flags
- [ ] Test mode (`--test` flag) works with custom endpoints

### Security & Reliability:
- [ ] API keys stored in environment variables only (never in config files)
- [ ] Custom provider failures don't affect built-in providers
- [ ] Comprehensive error messages for configuration issues
- [ ] Input validation prevents malformed configurations

### User Experience:
- [ ] Clear documentation with working examples for common providers
- [ ] Helpful error messages listing available providers
- [ ] Graceful degradation when features are unsupported
- [ ] Troubleshooting guide for configuration issues

### Technical Requirements:
- [ ] Backward compatibility verified with existing test suite
- [ ] New dependencies properly declared in pyproject.toml
- [ ] Configuration file discovery works across platforms
- [ ] Performance impact negligible (< 100ms startup overhead)

## Future Enhancements

### Post-v1 Considerations:
- **Dynamic Provider Plugin System**: Modular plugin architecture for providers beyond configuration
- **Advanced Configuration Management**: Secrets management integration (HashiCorp Vault, etc.)
- **Unified Tokenization Strategy**: Provider-agnostic tokenization library for better estimates
- **Model Discovery API Integration**: Dynamic model discovery for compatible endpoints
- **Provider Marketplace**: Community-contributed provider configurations
- **Configuration UI**: Web interface for managing provider configurations
- **Health Monitoring**: Provider availability and performance monitoring
- **Rate Limiting**: Configurable rate limits per provider

### Immediate Next Steps After Implementation:
1. **Community Feedback**: Gather user feedback on configuration schema
2. **Provider Examples**: Create configuration examples for popular providers
3. **Performance Optimization**: Profile and optimize configuration loading if needed
4. **Documentation Improvements**: Based on real user questions and issues

---

This comprehensive plan provides a production-ready roadmap for extending Consult7 to support custom OpenAI-compatible endpoints. The plan prioritizes security, reliability, and backward compatibility while addressing real-world API variations discovered through research. The discovery spike approach de-risks the implementation by learning actual provider quirks before building generic solutions.