# Release v3.0.0

## Breaking Changes
- Removed Google and OpenAI direct providers - now OpenRouter only
- `mode` parameter now required (no default)
- Removed `|thinking` suffix - use `mode` parameter instead

## New Features
- Dynamic file size limits based on model context window
- Clean mode API: `fast`, `mid`, `think`
- Support for all 500+ OpenRouter models

## Improvements
- Simplified CLI: `consult7 <api-key>` (removed provider parameter)
- Better error messages with actionable hints
- Improved tool descriptions

## Migration Guide
- Change `consult7 openrouter <key>` to `consult7 <key>`
- Change model name from `google/gemini-2.5-pro|thinking` to `google/gemini-2.5-pro` with `mode="think"`
- Always specify `mode` parameter (fast/mid/think)
