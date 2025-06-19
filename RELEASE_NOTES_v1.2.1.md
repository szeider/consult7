# Release Notes - v1.2.1

## Improvements

### Enhanced Dynamic Thinking/Reasoning Support
- Improved dynamic handling of thinking/reasoning modes across all providers
- Better support for provider-specific thinking implementations:
  - **Google**: Native thinking mode with model-specific budgets
  - **OpenRouter**: Dynamic reasoning allocation based on model type
  - **OpenAI**: Proper o-series model handling with `max_completion_tokens`

This release refines the v1.2.0 thinking mode implementation with better cross-provider compatibility.