# CLAUDE.md Archive

Archived content from CLAUDE.md to keep the main file manageable.

---

## Archived Version History

### v3.7.2 (June 20, 2026)
- **Fusion timeout no longer discards partial output.** The total budget now lives *inside* the provider: `asyncio.timeout` wraps the SSE read loop in `openrouter.py`, and on timeout (or a stalled httpx read) it returns the streamed content with a `[TRUNCATED — …]` marker (`error=None`), keeping any captured cost. Outer `asyncio.timeout` in `consultation.py` is now a loose backstop (`OPENROUTER_TIMEOUT + 120s`).
- **Budget raised 1000 → 1800s** (`OPENROUTER_TIMEOUT`); `LLM_CALL_TIMEOUT` derives from it (`+120s`). Killed the stale "10 minutes" string (minutes now derive from the constant).
- TIMEOUT TIP fixed for FUSION (`mid` doesn't shrink wall-clock — advises single model / splitting). Refactored reasoning-budget return into a single `budget_return` var. Detail: [[MEM_002]].

### v3.7.1 (June 14, 2026)
- **Mid-stream error surfacing**: the SSE parser checks each data chunk for a top-level `error` key (OpenRouter can emit an error chunk after the initial 200) and returns `API error (mid-stream): <msg>` instead of "No content received". Preserves captured cost. (From a Fusion self-review of `openrouter.py`.)

### v3.7.0 (June 14, 2026)
- Added **Fusion** (`openrouter/fusion`) — multi-model panel + judge. Injects `plugins:[{id:"fusion", max_tool_calls:N}]` with default Quality panel. `mode` → max_tool_calls 2/8/16. 128K context. `FUSE` mnemonic. Detail: [[MEM_002]].
- Upgraded Claude Opus 4.7 → **4.8** (1M context, adaptive `toggle`). 4.7 legacy.
- **Cost reporting**: footer ends with `cost: $X`; `call_llm` returns 4-tuple `(response, error, reasoning_budget, cost)`; `usage:{include:true}`; `format_cost()` in consultation.py.
- ZDR: GPT-5.5 supports ZDR (200); Grok 4.20 does not (404).

### v3.6.1 (April 25, 2026)
- Footer for toggle-reasoning models (Opus 4.7, Grok 4.20) now distinguishes `mid` vs `think` and notes that effort/budget are ignored upstream — `mid` says `adaptive (model ignores effort; mid ≡ think)`, `think` says `adaptive (model ignores effort/budget)`
- ZDR 404 (no-endpoint) errors now wrapped with a friendly message naming the model and suggesting alternatives; raw OpenRouter response preserved after `Raw upstream response:`
- `output_file` return now includes the standard metadata footer (model, mode, tokens, reasoning) so callers can verify what ran without opening the file

### v3.6.0 (April 24, 2026)
- Upgraded models: GPT-5.5, Claude Opus 4.7, Grok 4.20
- Claude Opus 4.7 (1M context, up from 200K) uses **adaptive thinking only** — new `toggle` reasoning type sends `{"reasoning": {"enabled": true}}` since `reasoning.effort` / `reasoning.max_tokens` are ignored upstream
- Grok 4.20 (2M context) also uses the `toggle` reasoning type (automatic reasoning, no effort/budget knob)
- Updated mnemonics: `gptt` → GPT-5.5, `oput`/`opuf` → Claude Opus 4.7, `grot` → Grok 4.20
- Bumped deps: mcp 1.27.0, ruff 0.15.12, anthropic 0.97.0
- Legacy model IDs (gpt-5.4/5.2, claude-opus-4.6, grok-4) still supported

### v3.5.0 (March 5, 2026)
- Upgraded GPT-5.2 → GPT-5.4 (~1M context, up from 400K)
- Updated `gptt` mnemonic to GPT-5.4
- Legacy gpt-5.2 model ID still supported

### v3.4.0 (March 5, 2026)
- Upgraded models: Gemini 3.1 Pro, Claude Opus 4.6, Claude Sonnet 4.6, Grok 4.1 Fast
- Added new models: Claude Haiku 4.5, Gemini 3.1 Flash Lite
- Updated mnemonics: `gemt` → Gemini 3.1 Pro, `oput`/`opuf` → Claude Opus 4.6
- Bumped deps: mcp 1.26.0, ruff 0.15.4, anthropic 0.84.0
- Fixed: `calculate_reasoning_max_tokens` now caps integer-budget path at model_max
- Legacy model IDs still supported
- Migrated PROCESS_NOTES.md → MEM/MEM_000.md

### v3.3.3 (January 2, 2026)
- Proper `mid` mode support with distinct effort levels
- Fix variable shadowing in streaming parser

### v3.3.0–v3.3.2 (January 1, 2026)
- Switched to SSE streaming for all API calls (prevents truncation)
- Formula-based reasoning token calculation with effort ratios
- Fixed GPT-5.2 empty response issue (reasoning tokens consume max_tokens)
- Added `zdr` parameter for Zero Data Retention routing
- Updated GEMF mnemonic to Gemini 3 Flash

### v3.2.0 (December 12, 2025)
- Updated GPT model from `openai/gpt-5.1` to `openai/gpt-5.2`
- GPT-5.2 adds new `xhigh` reasoning effort level (we use `high` for consistency)
- Tested and confirmed working via OpenRouter (400K context, effort-based reasoning)

### v3.1.2 (November 25, 2025)
- Updated Claude Opus to `anthropic/claude-opus-4.5`
- Added mnemonics: `oput` (Opus + think), `opuf` (Opus + fast)
- ULTRA now includes 4 frontier models (added OPUT)

### v3.1.1 (November 19, 2025)
- Documentation improvements: Enhanced README for better PyPI presentation
- No code changes - documentation only

### v3.1.0 (November 19, 2025)
- Added `google/gemini-3-pro-preview` (1M context, flagship reasoning model)
- New mnemonics: `gemt` (Gemini 3 Pro), `grot` (Grok 4), `oput`/`opuf` (Claude Opus), `ULTRA` (parallel execution)
- Implements `{"reasoning": {"enabled": true}}` API format for Gemini 3 Pro

## Archived Version History (2026-01-02)

### v3.0.0 (November 2025)
- **BREAKING CHANGE**: Removed Google and OpenAI direct providers (OpenRouter only)
- Added GPT-5 support, simplified CLI to `consult7 <api-key>`

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
