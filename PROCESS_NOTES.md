# Process Notes

Searchable session log. Not loaded routinely—search with grep when needed.

---

## 2026-01-02

**Goal**: Fix GPT-5.2 empty response issue and implement proper mid mode for all models

**Done**:
- Diagnosed GPT-5.2 empty response root cause: reasoning tokens consume max_tokens budget
- Implemented formula-based reasoning calculation using OpenRouter documented effort ratios
- Added mid mode for all models (effort=medium for OpenAI, effort=low for Gemini 3)
- Fixed code review issues: REASONING_ADDITIONAL bug, variable shadowing, naming inconsistencies
- Added model metadata tables: MODEL_REASONING_BEHAVIOR, MODEL_MAX_OUTPUT, EFFORT_RATIOS
- WS7 research on GPT-5.2 timeout causes (proxy idle timeouts, Cloudflare 524 errors)

**Tried**:
- Streaming mode (v3.3.0) — didn't solve empty response, but helps with connection timeouts
- Hardcoded 64K max_tokens (v3.3.1) — worked but was a duck-tape fix
- Formula-based calculation (v3.3.2) — proper fix using max_tokens = desired_output / (1 - effort_ratio)

**Notes**:
- GPT-5.x models still failing in consult7-testing despite fixes (timeouts, empty responses)
- May be OpenRouter-specific issue rather than code issue
- Changes not yet committed (pending Stefan's approval per Release Protocol)
- Other models working: Grok-4, Gemini-3-Pro, Gemini-3-Flash, Claude Opus 4.5

---

## 2026-01-01

**Goal**: Fix GPT-5.2 truncation issue, add ZDR support, update models

**Done**:
- Fixed response truncation by switching to SSE streaming for all API calls
- Added `zdr` parameter for Zero Data Retention routing
- Added Gemini 3 Flash model, updated `gemf` mnemonic
- Updated MCP dependency from 1.9.4 to 1.25.0
- Released v3.3.0 to GitHub and PyPI

**Tried**:
- Non-streaming requests with 17-min timeout — still truncated mid-sentence during reasoning
- SSE streaming — solved the issue by keeping connection alive

**Notes**: ZDR tested across ULTRA models: Gemini 3 Pro/Flash and Claude Opus have ZDR endpoints; GPT-5.2 and Grok 4 do not.

---
