# Consult7 MCP Server

**Consult7** is a Model Context Protocol (MCP) server that enables AI agents to consult large context window models via [OpenRouter](https://openrouter.ai) for analyzing extensive file collections - entire codebases, document repositories, or mixed content that exceed the current agent's context limits.

## Why Consult7?

**Consult7** enables any MCP-compatible agent to offload file analysis to large context models (up to 2M tokens). Useful when:
- Agent's current context is full
- Task requires specialized model capabilities
- Need to analyze large codebases in a single query
- Want to compare results from different models

> "For Claude Code users, Consult7 is a game changer."

## How it works

**Consult7** collects files from the specific paths you provide (with optional wildcards in filenames), assembles them into a single context, and sends them to a large context window model along with your query. The result is directly fed back to the agent you are working with.

## Example Use Cases

### Quick codebase summary

* **Files:** `["/Users/john/project/src/*.py", "/Users/john/project/lib/*.py"]`
* **Query:** "Summarize the architecture and main components of this Python project"
* **Model:** `"google/gemini-3-flash-preview"`
* **Mode:** `"fast"`

### Deep analysis with reasoning
* **Files:** `["/Users/john/webapp/src/*.py", "/Users/john/webapp/auth/*.py", "/Users/john/webapp/api/*.js"]`
* **Query:** "Analyze the authentication flow across this codebase. Think step by step about security vulnerabilities and suggest improvements"
* **Model:** `"anthropic/claude-opus-4.8"`
* **Mode:** `"think"`

### Generate a report saved to file
* **Files:** `["/Users/john/project/src/*.py", "/Users/john/project/tests/*.py"]`
* **Query:** "Generate a comprehensive code review report with architecture analysis, code quality assessment, and improvement recommendations"
* **Model:** `"google/gemini-2.5-pro"`
* **Mode:** `"think"`
* **Output File:** `"/Users/john/reports/code_review.md"`
* **Result:** Returns `"Result has been saved to /Users/john/reports/code_review.md"` instead of flooding the agent's context

## Featured: Gemini 3.1 Models

Consult7 supports **Google's Gemini 3.1** family:
- **Gemini 3.1 Pro** (`google/gemini-3.1-pro-preview`) - Flagship reasoning model, 1M context
- **Gemini 3 Flash** (`google/gemini-3-flash-preview`) - Ultra-fast model, 1M context
- **Gemini 3.1 Flash Lite** (`google/gemini-3.1-flash-lite-preview`) - Ultra-fast lite model, 1M context

**Quick mnemonics for power users:**
- **`gemt`** = Gemini 3.1 Pro + think (flagship reasoning)
- **`gemf`** = Gemini 3 Flash + fast (ultra fast)
- **`gptt`** = GPT-5.6 Sol + think (latest GPT)
- **`grot`** = Grok 4.20 + think (automatic reasoning)
- **`oput`** = Claude Opus 4.8 + think (adaptive thinking)
- **`fabt`** = Claude Fable 5 + think (deepest reasoning; premium — reserved for hard problems)
- **`ULTRA`** = Run GEMT, GPTT, GROT, and OPUT in parallel (4 frontier models)
- **`FUSE`** = Fusion: a frontier panel deliberates and a judge synthesizes, in one call

These mnemonics make it easy to reference model+mode combinations in your queries.

> **Note on Fable 5.** `anthropic/claude-fable-5` is Anthropic's most capable model but priced at a premium (~2× Opus 4.8). It **does not replace Opus 4.8** as the default Claude workhorse and is **not part of the `ULTRA` panel** — reach for it deliberately, only on specifically hard problems where the extra depth is worth the cost. Unlike Opus 4.8 (adaptive thinking only), OpenRouter honors Fable's effort scale, so `mid`/`think` map to `effort=high`/`effort=xhigh`.

## Featured: Fusion (multi-model analysis)

Consult7 supports OpenRouter's **Fusion** (`openrouter/fusion`) — a single call where a panel of frontier models (Opus, GPT, Gemini Pro) answers your query in parallel and a judge model synthesizes their responses into one answer. Reach for it on hard questions where multiple perspectives help and the cost of being wrong outweighs a few extra completions.

- **Context:** 128K — smaller than the 1M–2M single models, so it's best for hard questions on moderate input, not giant file bundles.
- **Mode → research depth:** `fast` / `mid` / `think` map the panel's web-search/fetch budget to `max_tool_calls` of 2 / 8 / 16.
- **Mnemonic:** `FUSE` = `openrouter/fusion`.

Trivial prompts answer directly (no panel); the panel fires only when the question warrants deliberation. Fusion is billed per panel run, so it costs more than a single-model call.

## Installation

### Claude Code

Simply run:

```bash
claude mcp add -s user consult7 uvx -- consult7 your-openrouter-api-key
```

### Claude Desktop

Add to your Claude Desktop configuration file:

```json
{
  "mcpServers": {
    "consult7": {
      "type": "stdio",
      "command": "uvx",
      "args": ["consult7", "your-openrouter-api-key"]
    }
  }
}
```

Replace `your-openrouter-api-key` with your actual OpenRouter API key.

No installation required - `uvx` automatically downloads and runs consult7 in an isolated environment.

## Command Line Options

```bash
uvx consult7 <api-key> [--test]
```

- `<api-key>`: Required. Your OpenRouter API key
- `--test`: Optional. Test the API connection

The model and mode are specified when calling the tool, not at startup.

## Supported Models

Consult7 supports **all 500+ models** available on OpenRouter. Below are the flagship models with optimized dynamic file size limits:

| Model | Context | Use Case |
|-------|---------|----------|
| `openai/gpt-5.6-sol` | 1M | Latest top-tier GPT, effort-based reasoning |
| `google/gemini-3.1-pro-preview` | 1M | **Flagship reasoning model** |
| `google/gemini-3-flash-preview` | 1M | **Gemini 3 Flash, ultra fast** |
| `google/gemini-3.1-flash-lite-preview` | 1M | Ultra-fast lite model |
| `anthropic/claude-fable-5` | 1M | Most capable; **premium price — reserved for hard problems** |
| `anthropic/claude-opus-4.8` | 1M | Best quality, adaptive thinking |
| `anthropic/claude-sonnet-4.6` | 1M | Excellent reasoning, fast |
| `anthropic/claude-haiku-4.5` | 200k | Budget, very fast |
| `x-ai/grok-4.20` | 2M | Automatic reasoning, huge context |
| `x-ai/grok-4.1-fast` | 2M | Largest context window |
| `openrouter/fusion` | 128k | Multi-model panel + judge (see Featured: Fusion) |

**Quick mnemonics:**
- `gptt` = `openai/gpt-5.6-sol` + `think` (latest GPT, deep reasoning)
- `gemt` = `google/gemini-3.1-pro-preview` + `think` (Gemini 3.1 Pro, flagship reasoning)
- `grot` = `x-ai/grok-4.20` + `think` (Grok 4.20, automatic reasoning)
- `oput` = `anthropic/claude-opus-4.8` + `think` (Claude Opus, adaptive thinking)
- `opuf` = `anthropic/claude-opus-4.8` + `fast` (Claude Opus, no reasoning)
- `fabt` = `anthropic/claude-fable-5` + `think` (Claude Fable, deepest reasoning [effort xhigh]; premium, hard problems only)
- `fabm` = `anthropic/claude-fable-5` + `mid` (Claude Fable, high-effort reasoning; premium)
- `gemf` = `google/gemini-3-flash-preview` + `fast` (Gemini 3 Flash, ultra fast)
- `ULTRA` = call GEMT, GPTT, GROT, and OPUT IN PARALLEL (4 frontier models for maximum insight; Fable is deliberately **not** in the panel)
- `FUSE` = `openrouter/fusion` (one call: a frontier panel deliberates, a judge synthesizes; mode sets web-research depth)

You can use any OpenRouter model ID (e.g., `deepseek/deepseek-r1-0528`). See the [full model list](https://openrouter.ai/models). File size limits are automatically calculated based on each model's context window.

## Performance Modes

- **`fast`**: No reasoning - quick answers, simple tasks
- **`mid`**: Moderate reasoning - code reviews, bug analysis
- **`think`**: Maximum reasoning - security audits, complex refactoring

## File Specification Rules

- **Absolute paths only**: `/Users/john/project/src/*.py`
- **Wildcards in filenames only**: `/Users/john/project/*.py` (not in directory paths)
- **Extension required with wildcards**: `*.py` not `*`
- **Mix files and patterns**: `["/path/src/*.py", "/path/README.md", "/path/tests/*_test.py"]`

**Common patterns:**
- All Python files: `/path/to/dir/*.py`
- Test files: `/path/to/tests/*_test.py` or `/path/to/tests/test_*.py`
- Multiple extensions: `["/path/*.js", "/path/*.ts"]`

**Automatically ignored:** `__pycache__`, `.env`, `secrets.py`, `.DS_Store`, `.git`, `node_modules`

**Size limits:** Dynamic based on model context window (e.g., Grok 4.20: ~8MB, GPT-5.6 Sol: ~4MB)

## Tool Parameters

The consultation tool accepts the following parameters:

- **files** (required): List of absolute file paths or patterns with wildcards in filenames only
- **query** (required): Your question or instruction for the LLM to process the files
- **model** (required): The LLM model to use (see Supported Models above)
- **mode** (required): Performance mode - `fast`, `mid`, or `think`
- **output_file** (optional): Absolute path to save the response to a file instead of returning it
  - If the file exists, it will be saved with `_updated` suffix (e.g., `report.md` → `report_updated.md`)
  - When specified, returns only: `"Result has been saved to /path/to/file"`
  - Useful for generating reports, documentation, or analyses without flooding the agent's context
- **zdr** (optional): Enable Zero Data Retention routing (default: `false`)
  - When `true`, routes only to endpoints with ZDR policy (prompts not retained by provider)
  - ZDR available: Gemini 3.1 Pro/Flash, Claude Opus 4.8, GPT-5, GPT-5.5
  - Not available: GPT-5.6 Sol, Grok 4.20, Claude Fable 5 (returns error)

## Usage Examples

### Via MCP in Claude Code

Claude Code will automatically use the tool with proper parameters:

```json
{
  "files": ["/Users/john/project/src/*.py"],
  "query": "Explain the main architecture",
  "model": "google/gemini-3-flash-preview",
  "mode": "fast"
}
```

### Via Python API

```python
from consult7.consultation import consultation_impl

result = await consultation_impl(
    files=["/path/to/file.py"],
    query="Explain this code",
    model="google/gemini-3-flash-preview",
    mode="fast",  # fast, mid, or think
    provider="openrouter",
    api_key="sk-or-v1-..."
)
```

## Testing

```bash
# Test OpenRouter connection
uvx consult7 sk-or-v1-your-api-key --test
```

## Uninstalling

To remove consult7 from Claude Code:

```bash
claude mcp remove consult7 -s user
```

## Version History

### v3.9.0
- **New default GPT: GPT-5.6 Sol** (`openai/gpt-5.6-sol`) — the latest top-tier GPT, ~1M context / 128K output, effort-based reasoning (`mid` → `effort=medium`, `think` → `effort=high`). Replaces GPT-5.5 as the `gptt` default; GPT-5.5 stays available as a legacy model. ZDR is **not** supported on GPT-5.6 Sol (GPT-5.5 still is).
- **Grok 4.5 not added:** `x-ai/grok-4.5` is region-restricted on OpenRouter (returns a 403 "not available in your region") and could not be verified against the real API, so it was not integrated. Grok 4.20 remains the `grot` default.

### v3.8.0
- **Added Claude Fable 5** (`anthropic/claude-fable-5`) — Anthropic's most capable model, 1M context. Premium price (~2× Opus 4.8), so it's **reserved for specifically hard problems** and is **not** part of the `ULTRA` panel; it does not replace Opus 4.8 as the default Claude model. New mnemonics `fabt` (think) / `fabm` (mid). Unlike Opus 4.8 (adaptive thinking only), OpenRouter honors Fable's effort scale, so `mid`/`think` map to `effort=high`/`effort=xhigh` (`max` intentionally not exposed — it tends to overthink at ~2× token cost). ZDR not supported (Fable requires 30-day retention).
- **Response-length prompt tuned:** the system prompt now asks the model to match answer length to the task (thorough when the question needs depth, concise otherwise) instead of a blunt "be concise".

### v3.7.1
- Surface mid-stream API errors: when OpenRouter sends an error as a streaming data chunk (after the initial 200), the call now returns that error message instead of a misleading "No content received".

### v3.7.0
- Added **Fusion** (`openrouter/fusion`) — a multi-model panel plus a judge in one call; `mode` maps to web-research depth (`fast`/`mid`/`think` → `max_tool_calls` 2/8/16). New `FUSE` mnemonic.
- Upgraded Claude Opus 4.7 → **4.8** (1M context, adaptive thinking); `oput`/`opuf` now point to 4.8, and 4.7 is kept as a legacy ID.
- The response footer now reports the **call cost in USD** (from OpenRouter usage accounting), e.g. `cost: $0.0923`.

### v3.6.1
- Toggle-reasoning footer now distinguishes `mid` vs `think` for adaptive models (Opus, Grok)
- Friendlier error message when a model has no Zero Data Retention endpoint
- `output_file` return now includes the metadata footer so callers can verify what ran

### v3.6.0
- Upgraded models: GPT-5.5, Claude Opus 4.7, Grok 4.20
- Claude Opus 4.7 (1M context) uses adaptive thinking — `reasoning.enabled=true`
- Grok 4.20 (2M context) uses automatic reasoning — `reasoning.enabled=true`
- Updated mnemonics: `gptt` → GPT-5.5, `oput`/`opuf` → Claude Opus 4.7, `grot` → Grok 4.20
- Legacy model IDs still supported

### v3.5.0
- Upgraded GPT-5.2 → GPT-5.4 (~1M context)

### v3.4.0
- Upgraded models: Gemini 3.1 Pro, Claude Opus 4.6, Claude Sonnet 4.6, Grok 4.1 Fast
- Added new models: Claude Haiku 4.5, Gemini 3.1 Flash Lite
- Updated mnemonics: `gemt` → Gemini 3.1 Pro, `oput`/`opuf` → Claude Opus 4.6
- Legacy model IDs still supported

### v3.3.0
- Fixed GPT-5.2 thinking mode truncation issue (switched to streaming)
- Added `google/gemini-3-flash-preview` (Gemini 3 Flash, ultra fast)
- Updated `gemf` mnemonic to use Gemini 3 Flash
- Added `zdr` parameter for Zero Data Retention routing

### v3.2.0
- Updated to GPT-5.2 with effort-based reasoning

### v3.1.0
- Added `google/gemini-3-pro-preview` (1M context, flagship reasoning model)
- New mnemonics: `gemt` (Gemini 3 Pro), `grot` (Grok 4), `ULTRA` (parallel execution)

### v3.0.0
- Removed Google and OpenAI direct providers - now OpenRouter only
- Removed `|thinking` suffix - use `mode` parameter instead (now required)
- Clean `mode` parameter API: `fast`, `mid`, `think`
- Simplified CLI from `consult7 <provider> <key>` to `consult7 <key>`
- Better MCP integration with enum validation for modes
- Dynamic file size limits based on model context window

### v2.1.0
- Added `output_file` parameter to save responses to files

### v2.0.0
- New file list interface with simplified validation
- Reduced file size limits to realistic values

## License

MIT
