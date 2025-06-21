# OpenRouter Authentication Bug Report

## Issue Summary
OpenRouter authentication fails with 401 "No auth credentials found" error when using the `--test` flag, but works correctly in all other scenarios.

## Environment
- Version: 1.2.2 (also present in 1.2.1)
- Introduced: After refactoring from monolithic to modular architecture (commit ea87b59)
- Provider: OpenRouter only (Google and OpenAI work correctly)

## Reproduction Steps
```bash
# This fails with 401 error
uv run python -m consult7 openrouter sk-or-v1-xxx --test

# But these work correctly:
# 1. E2E tests
uv run python tests/e2e/test_single_model.py openrouter 'google/gemini-2.5-flash' test_data/file_5k.py

# 2. Normal MCP operation
claude mcp add -s project consult7-openrouter -- uv --directory /path/to/consult7 run python -m consult7 openrouter sk-or-v1-xxx
```

## Technical Details

### What We Know
1. **Same API key works** in e2e tests that call `consultation_impl` directly
2. **Same code path** - both --test and e2e eventually call `provider_instance.call_llm()`
3. **API key is correct** - verified with debug output showing correct key format
4. **Headers are identical** - tried with/without optional headers (HTTP-Referer, X-Title)
5. **GET requests work** - `get_model_info` succeeds, only POST to chat/completions fails
6. **Other providers work** - Google and OpenAI use identical command syntax without issues

### What We've Tried
1. ✗ Removed optional headers (HTTP-Referer, X-Title)
2. ✗ Added explicit Content-Type header
3. ✗ Changed model from google/gemini-2.5-flash to google/gemini-2.5-flash-preview-05-20
4. ✗ Verified Authorization header format matches OpenRouter docs: `Bearer <key>`
5. ✗ Checked for API key corruption - key is passed correctly

### Code Comparison
Before refactoring (working):
- Used global variables for `api_key` and `provider`
- Exact same headers and HTTP request structure

After refactoring (broken in --test only):
- API key passed as parameter through the call chain
- Providers implemented as singleton instances
- No state stored in provider classes

### Error Details
```
Error: API error: 401 - {"error":{"message":"No auth credentials found","code":401}}
```

Response headers from OpenRouter indicate:
```
x-clerk-auth-message: 'Invalid JWT form. A JWT consists of three parts separated by dots.'
```

This is misleading as OpenRouter API keys are not JWTs.

## Impact
- `--test` flag doesn't work for OpenRouter
- Normal operations unaffected
- E2E tests pass correctly

## Hypothesis
The issue appears to be specific to how the test_api_connection function interacts with the OpenRouter provider, possibly related to:
1. Some subtle difference in how httpx handles the request in this context
2. A timing or state issue with the singleton provider pattern
3. An undocumented requirement from OpenRouter's API

## Workaround
Users can verify their OpenRouter setup by:
1. Running the e2e test suite
2. Using the MCP server directly without --test flag
3. Testing with a simple Python script that calls the API directly