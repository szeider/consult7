# Release Notes v1.2.0

## 🎯 Thinking Mode Support

This release introduces support for thinking/reasoning modes across LLM providers using a consistent `|thinking` suffix convention.

### New Features

#### 🧠 Thinking Mode with `|thinking` Suffix
- **OpenRouter**: Add `|thinking` suffix to enable reasoning mode (e.g., `"google/gemini-2.5-flash|thinking"`)
  - Activates reasoning with `{"effort": "high"}` parameter
- **Google**: Add `|thinking` suffix to enable thinking mode (e.g., `"gemini-2.5-flash|thinking"`)
  - Uses `ThinkingConfig` with dynamic thinking budget (`thinking_budget: -1`)
- **OpenAI**: No changes - continues to use `|` for context specification only

### Improvements

#### 📝 Enhanced Documentation
- Model examples now show both regular and thinking mode variants
- Clearer provider-agnostic language in tool descriptions
- Unified format without redundancy in model parameter descriptions

#### 🔧 Code Quality
- Updated all dependencies to latest stable versions
- Fixed linting issues identified by ruff
- Improved code formatting consistency

### Technical Details

- **Dependencies Updated**:
  - `mcp` → 1.9.4
  - `openai` → 1.88.0
  - Other dependencies remain at latest stable versions

- **API Changes**:
  - Model name parsing now handles `|thinking` suffix before API calls
  - Model context info fetched with stripped model names
  - Backward compatible - existing model names work without changes

### Examples

```python
# OpenRouter with reasoning mode
model="google/gemini-2.5-flash|thinking"

# Google with thinking mode  
model="gemini-2.5-flash|thinking"

# Regular mode (no thinking)
model="google/gemini-2.5-flash"
model="gemini-2.5-flash"
```

### Migration Guide

No breaking changes. Existing configurations continue to work. To enable thinking mode, simply add `|thinking` to supported model names.

---

**Full Changelog**: https://github.com/szeider/consult7/compare/v1.1.1...v1.2.0