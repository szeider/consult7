# CLAUDE.md Archive

Archived content from CLAUDE.md to keep the main file manageable.

---

## Archived Version History (2026-01-01)

### v2.1.0 (September 2025)
- **NEW FEATURE**: Optional `output_file` parameter to save responses to files
  - Saves LLM response to specified file instead of returning to context
  - Returns brief message: "Result has been saved to /path/file"
  - Automatic conflict resolution with "_updated" suffix
  - Useful for generating reports without flooding agent context

### v2.0.0 (January 2025)
- **BREAKING CHANGE**: New file list interface replaces path/pattern/exclude
  - Now accepts `files` list with absolute paths and wildcards in filenames only
  - Simpler, more intuitive, no duplication possible
  - Clear validation rules and error messages
- **Reduced file size limits** to realistic values:
  - 1MB per file (was 10MB)
  - 4MB total (was 100MB) - optimized for ~1M token context windows
- Previous v1.3.1 features also included:
- Added GPT-5 support (all variants: base, mini, nano)
  - Uses `max_completion_tokens` instead of `max_tokens`
  - Does NOT support custom temperature (must use default temperature=1)
  - Supports system messages (unlike o-series models)
- Added Claude Opus 4.5 support via OpenRouter
- Updated tool definitions and README with new models
- **Increased timeouts to 600 seconds (10 minutes)**
  - LLM calls: 600s (was 180s)
  - OpenRouter HTTP requests: 600s (was 30s)
  - API info fetching: 30s (was 10s)
  - Very generous timeouts to allow long-running thinking/reasoning models
- **CRITICAL LESSON LEARNED**: Never mock API calls in tests - always test against real APIs

### v1.3.0 (January 24, 2025)
- Added proper logging to stderr (fixes MCP protocol violations)
- Added support for gemini-2.5-flash-lite with thinking mode

### v1.2.2
- Increased default timeout from 22s to 180s for better stability with thinking models
- Fixed missing asyncio import in consultation.py
- Improved timeout handling for complex queries and large codebases
- Code formatting improvements with ruff

### v1.2.1
- Enhanced dynamic thinking/reasoning support across providers

### v1.2.0
- Removed 80% thinking allocation buffer for better utilization
- Reduced output reservation from 16k to 8k tokens
- All hardcoded values are now named constants
- Fixed model-specific reasoning limits for OpenRouter
- Added helper functions to reduce code duplication
- Comprehensive test coverage

### v1.1.1
- Dynamic tool registration with low-level Server pattern
- Improved error handling

### v1.1.0
- Dynamic model selection and streamlined CLI
- Added thinking/reasoning mode support

---
