# Process Notes

Searchable session log. Not loaded routinely—search with grep when needed.

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
