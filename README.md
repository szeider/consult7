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
* **Model:** `"google/gemini-2.5-flash"`
* **Mode:** `"fast"`

### Deep analysis with reasoning
* **Files:** `["/Users/john/webapp/src/*.py", "/Users/john/webapp/auth/*.py", "/Users/john/webapp/api/*.js"]`
* **Query:** "Analyze the authentication flow across this codebase. Think step by step about security vulnerabilities and suggest improvements"
* **Model:** `"anthropic/claude-sonnet-4.5"`
* **Mode:** `"think"`

### Generate a report saved to file
* **Files:** `["/Users/john/project/src/*.py", "/Users/john/project/tests/*.py"]`
* **Query:** "Generate a comprehensive code review report with architecture analysis, code quality assessment, and improvement recommendations"
* **Model:** `"google/gemini-2.5-pro"`
* **Mode:** `"think"`
* **Output File:** `"/Users/john/reports/code_review.md"`
* **Result:** Returns `"Result has been saved to /Users/john/reports/code_review.md"` instead of flooding the agent's context

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
| `openai/gpt-5.1` | 400k | Latest GPT, balanced performance |
| `google/gemini-2.5-pro` | 1M | Best for complex analysis |
| `google/gemini-2.5-flash` | 1M | Fast, good for most tasks |
| `google/gemini-2.5-flash-lite` | 1M | Ultra fast, simple queries |
| `anthropic/claude-sonnet-4.5` | 1M | Excellent reasoning |
| `anthropic/claude-opus-4.1` | 200k | Best quality, slower |
| `x-ai/grok-4` | 256k | Alternative reasoning model |
| `x-ai/grok-4-fast` | 2M | Largest context window |

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

**Size limits:** Dynamic based on model context window (e.g., Grok 4 Fast: ~8MB, GPT-5.1: ~1.5MB)

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

## Usage Examples

### Via MCP in Claude Code

Claude Code will automatically use the tool with proper parameters:

```json
{
  "files": ["/Users/john/project/src/*.py"],
  "query": "Explain the main architecture",
  "model": "google/gemini-2.5-flash",
  "mode": "mid"
}
```

### Via Python API

```python
from consult7.consultation import consultation_impl

result = await consultation_impl(
    files=["/path/to/file.py"],
    query="Explain this code",
    model="google/gemini-2.5-flash",
    mode="mid",  # fast, mid, or think
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
