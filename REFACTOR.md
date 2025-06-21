# Refactoring Plan for consult7 server.py

## Overview
This document outlines the plan to refactor the monolithic `server.py` (1332 lines) into smaller, more maintainable modules, each under 300 lines.

## Goals
1. **Improve maintainability**: Split code into logical, single-responsibility modules
2. **Enhance testability**: Enable unit testing of individual components
3. **Maintain functionality**: Ensure zero regression in existing features
4. **Enable extensibility**: Make it easier to add new providers or features

## Target Module Structure

```
src/consult7/
├── __init__.py          # Package initialization
├── __main__.py          # Module entry point (unchanged)
├── server.py            # Main entry point, CLI parsing, MCP server (~250 lines)
├── constants.py         # All constants and static configuration (~90 lines)
├── token_utils.py       # Token estimation and thinking budget utilities (~120 lines)
├── file_processor.py    # File discovery, formatting, and utilities (~180 lines)
├── tool_definitions.py  # ToolDescriptions class (~120 lines)
├── consultation.py      # Main consultation orchestration logic (~200 lines)
└── providers/           # Provider-specific implementations
    ├── __init__.py      # Export provider registry (~30 lines)
    ├── base.py          # Base provider interface and shared utilities (~80 lines)
    ├── google.py        # Google AI implementation (~150 lines)
    ├── openai.py        # OpenAI implementation (~100 lines)
    └── openrouter.py    # OpenRouter implementation (~190 lines)
```

## Detailed Module Breakdown

### 1. constants.py
**Purpose**: Centralize all static configuration and constants
**Contents**:
- File size limits: `MAX_FILE_SIZE`, `MAX_TOTAL_SIZE`, `MAX_RESPONSE_SIZE`, `FILE_SEPARATOR`
- Output token constants: `DEFAULT_OUTPUT_TOKENS`, `SMALL_OUTPUT_TOKENS`, `SMALL_MODEL_THRESHOLD`
- API constants: `OPENROUTER_URL`, `MODELS_URL`, URLs, timeouts, temperature
- Application constants: `SERVER_VERSION`, `EXIT_SUCCESS`, `EXIT_FAILURE`, `MIN_ARGS`
- Default ignored paths: `DEFAULT_IGNORED`
- Test models dictionary: `TEST_MODELS`
**Note**: Token-related constants moved to `token_utils.py`

### 2. token_utils.py (NEW - Prevents circular dependencies)
**Purpose**: Token estimation and thinking budget calculations
**Contents**:
- Constants:
  - `TOKEN_SAFETY_FACTOR`, `CHARS_PER_TOKEN_REGULAR`, `CHARS_PER_TOKEN_HTML`
  - `MIN_THINKING_TOKENS`, `MIN_REASONING_TOKENS`, `MAX_REASONING_TOKENS`
  - `FLASH_MAX_THINKING_TOKENS`, `PRO_MAX_THINKING_TOKENS`
  - `THINKING_LIMITS` dictionary
- Functions:
  - `estimate_tokens()` - Estimate token count for text
  - `parse_thinking_suffix()` - Parse |thinking suffix
  - `parse_model_thinking()` - Parse model|thinking=X format
  - `get_thinking_budget()` - Calculate thinking token budget
**Dependencies**: None (leaf module)

### 3. file_processor.py
**Purpose**: File system operations, content formatting, and path utilities
**Contents**:
- `should_ignore_path()` - Check if path should be ignored
- `discover_files()` - Find files matching patterns
- `format_content()` - Format files into structured text
**Dependencies**: `constants`

### 4. tool_definitions.py
**Purpose**: MCP tool descriptions and examples
**Contents**:
- `ToolDefinitions` class with:
  - `MODEL_EXAMPLES` dict
  - `get_consultation_tool_description()`
  - `get_model_parameter_description()`
  - Other parameter descriptions
**Dependencies**: `constants`

### 5. providers/base.py
**Purpose**: Base provider interface and shared utilities
**Contents**:
- `BaseProvider` abstract class with:
  - `get_model_info()` abstract method
  - `call_llm()` abstract method
- `process_llm_response()` - Shared response processing
**Example**:
```python
from abc import ABC, abstractmethod
from typing import Optional, Tuple
from ..constants import MAX_RESPONSE_SIZE

def process_llm_response(response_content: Optional[str]) -> str:
    """Process LLM response: handle None and truncate if needed."""
    if response_content is None:
        response_content = ""
    
    if len(response_content) > MAX_RESPONSE_SIZE:
        response_content = (
            response_content[:MAX_RESPONSE_SIZE]
            + "\n[TRUNCATED - Response exceeded size limit]"
        )
    
    return response_content

class BaseProvider(ABC):
    @abstractmethod
    async def get_model_info(self, model_name: str, api_key: str) -> Optional[dict]:
        """Get model context information."""
        pass
    
    @abstractmethod
    async def call_llm(self, content: str, query: str, model_name: str, 
                       api_key: str) -> Tuple[str, Optional[str], Optional[int]]:
        """Call the LLM and return (response, error, thinking_budget)."""
        pass
```
**Dependencies**: `constants`

### 6. providers/google.py
**Purpose**: Google AI provider implementation
**Contents**:
- `GOOGLE_AVAILABLE` flag (try-except import)
- `GoogleProvider` class implementing `BaseProvider`
- `get_model_info()` - Fetch Google model information
- `call_llm()` - Call Google AI with thinking mode support
**Dependencies**: `google.genai`, `constants`, `token_utils`, `.base`

### 7. providers/openai.py
**Purpose**: OpenAI provider implementation
**Contents**:
- `OPENAI_AVAILABLE` flag (try-except import)
- `OpenAIProvider` class implementing `BaseProvider`
- `get_model_info()` - Parse context from model specification
- `call_llm()` - Call OpenAI API with o-series support
**Dependencies**: `openai`, `constants`, `token_utils`, `.base`

### 8. providers/openrouter.py
**Purpose**: OpenRouter provider implementation
**Contents**:
- `OpenRouterProvider` class implementing `BaseProvider`
- `get_model_info()` - Fetch model info from OpenRouter API
- `call_llm()` - Call OpenRouter with reasoning mode support
**Dependencies**: `httpx`, `constants`, `token_utils`, `.base`

### 9. providers/__init__.py
**Purpose**: Export provider registry
**Contents**:
```python
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
```

### 10. consultation.py
**Purpose**: Main consultation orchestration logic
**Contents**:
- `process_llm_response()` - Process and truncate LLM responses
- `get_model_context_info()` - Unified model info fetching (dispatches to providers)
- `consultation_impl()` - Main consultation orchestration:
  - Calls file discovery
  - Formats content
  - Estimates tokens and validates against limits
  - Dispatches to appropriate provider
  - Formats final response
**Dependencies**: `providers`, `file_processor`, `constants`, `token_utils`

### 11. server.py (refactored)
**Purpose**: CLI and MCP server setup
**Contents**:
- `test_api_connection()` - Test provider connectivity (passes api_key explicitly)
- `main()` - Parse CLI args, setup MCP server
- MCP handler functions using decorators (@server.list_tools, @server.call_tool)
- `run()` - Entry point
**Note**: No more global `api_key` and `provider` variables - passed explicitly
**Dependencies**: All other modules

## Incremental Implementation Plan

### Phase 1: Foundation (No breaking changes)
1. **Step 1.1**: Create `constants.py`
   - Move all constants from server.py
   - Update server.py imports
   - **Test**: Run existing e2e tests to ensure nothing breaks

2. **Step 1.2**: Create `utils.py`
   - Move utility functions
   - Update server.py imports
   - **Test**: Run existing unit tests for token estimation

3. **Step 1.3**: Create `tool_definitions.py`
   - Move ToolDescriptions class
   - Update server.py imports
   - **Test**: Verify tool descriptions are correctly generated

### Phase 2: Core Functionality
4. **Step 2.1**: Create `file_processor.py`
   - Move file discovery and formatting functions
   - **Test**: Create unit tests for file discovery with various patterns

5. **Step 2.2**: Create `providers/base.py`
   - Define base provider interface
   - **Test**: Ensure interface is properly defined

### Phase 3: Provider Migration
6. **Step 3.1**: Create `providers/google.py`
   - Move Google-specific code
   - **Test**: Run e2e test with Google provider

7. **Step 3.2**: Create `providers/openai.py`
   - Move OpenAI-specific code
   - **Test**: Run e2e test with OpenAI provider

8. **Step 3.3**: Create `providers/openrouter.py`
   - Move OpenRouter-specific code
   - **Test**: Run e2e test with OpenRouter provider

9. **Step 3.4**: Create `providers/__init__.py`
   - Create provider registry
   - **Test**: Verify provider lookup works

### Phase 4: Orchestration
10. **Step 4.1**: Create `llm_orchestrator.py`
    - Move consultation_impl and model info logic
    - **Test**: Run full e2e test suite

### Phase 5: Final Cleanup
11. **Step 5.1**: Refactor `server.py`
    - Remove moved code
    - Update imports
    - Clean up structure
    - **Test**: Full regression test suite

## Testing Strategy

### Unit Tests (New)
Create unit tests for each module:
- `test_utils.py` - Test token estimation, parsing functions
- `test_file_processor.py` - Test file discovery, content formatting
- `test_providers_*.py` - Test each provider independently

### E2E Tests (Existing + Enhanced)
1. **Existing tests must pass** at each phase:
   - `tests/test_providers.py`
   - `tests/e2e/test_consult7.py`
   - `tests/thinking_budget/test_thinking_simple.py`

2. **New incremental tests**:
   ```bash
   # After each phase, run:
   uv run python tests/e2e/test_consult7.py --provider google --api-key $GOOGLE_API_KEY
   uv run python tests/e2e/test_consult7.py --provider openrouter --api-key $OPENROUTER_API_KEY
   uv run python tests/e2e/test_consult7.py --provider openai --api-key $OPENAI_API_KEY
   ```

3. **Regression test checklist** after each step:
   - [ ] Basic file discovery works
   - [ ] Pattern matching (include/exclude) works
   - [ ] Token estimation is accurate
   - [ ] All three providers connect successfully
   - [ ] Thinking/reasoning modes work correctly
   - [ ] Error handling remains consistent
   - [ ] CLI argument parsing works
   - [ ] --test mode functions properly

## Risk Mitigation

1. **Git Strategy**: Create a new branch `refactor-server-modules`
2. **Incremental Commits**: One commit per step with descriptive message
3. **Rollback Plan**: Each phase should be independently revertable
4. **Review Points**: After each phase, review changes before proceeding
5. **Documentation**: Update docstrings and comments as code moves

## Success Criteria

1. All existing tests pass without modification
2. Each new module is under 300 lines
3. No circular imports
4. Improved code organization and readability
5. No performance degradation
6. All features work exactly as before

## Timeline Estimate

- Phase 1: 1 hour (low risk, mechanical changes)
- Phase 2: 1 hour (moderate complexity)
- Phase 3: 2 hours (provider migration is critical)
- Phase 4: 1 hour (orchestration logic)
- Phase 5: 30 minutes (cleanup)
- Testing & Validation: 1.5 hours

**Total: ~7 hours of focused work**

## Questions to Resolve

1. Should we use dependency injection for providers instead of a registry?
2. Should model info fetching be async for all providers?
3. Should we add type hints comprehensively during refactoring?
4. Should we create a `models.py` for model info fetching instead of keeping it in providers?
5. How should we handle the global `api_key` and `provider` variables?

## Next Steps

1. Review this plan with the team
2. Get approval for the approach
3. Set up the feature branch
4. Begin Phase 1 implementation
5. Document any deviations from the plan