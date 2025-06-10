# Consult7 MCP Server

**Consult7** is a Model Context Protocol (MCP) server that enables AI agents to consult large context window models for analyzing extensive file collections - entire codebases, document repositories, or mixed content that exceed the current agent's context limits. Supports providers Openrouter, OpenAI, and Google.

## Why Consult7?

When working with AI agents that have limited context windows (like Claude with 200K tokens), **Consult7** allows them to leverage models with massive context windows to analyze large codebases or document collections that would otherwise be impossible to process in a single query.



> "For Claude Code users, Consult7 is a game changer."



## Example Use Cases

### Summarize an entire codebase
* **Query:** "Summarize the architecture and main components of this Python project"
* **Pattern:** `".*\.py$"` (all Python files)
* **Path:** `/Users/john/my-python-project`

### Find specific method definitions

* **Query:** "Find the implementation of the authenticate_user method and explain how it handles password verification"
* **Pattern:** `".*\.(py|js|ts)$"` (Python, JavaScript, TypeScript files)
* **Path:** `/Users/john/backend`

### Analyze test coverage
* **Query:** "List all the test files and identify which components lack test coverage"
* **Pattern:** `".*test.*\.py$|.*_test\.py$"` (test files)
* **Path:** `/Users/john/project`

## Installation

Add to your Claude Desktop configuration file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

For Claude Code, add to your settings (⌘+, on Mac) under `"claude-code.mcpServers"` instead.

No installation required - `uvx` automatically downloads and runs consult7 in an isolated environment.

```json
{
  "mcpServers": {
    "consult7": {
      "command": "uvx",
      "args": [
        "consult7",
        "--api-key", "your-api-key",
        "--provider", "openrouter",
        "--model", "qwen/qwen-turbo",
        "--context", "1M"
      ]
    }
  }
}
```



## Command Line Options

```bash
uvx consult7 --api-key KEY [--provider PROVIDER] [--model MODEL] [--context TOKENS] [--test]
```

- `--api-key`: Required. Your API key for the chosen provider
- `--provider`: Optional. Choose from `openrouter` (default), `google`, or `openai`
- `--model`: Optional. Specific model to use (defaults to provider's default)
- `--context`: Optional. Model context window size (default: 1M). Accepts formats like '2M', '128K', or '1000000'
- `--test`: Optional. Test the API connection

## Testing

```bash
# Test OpenRouter (default)
uvx consult7 --api-key "sk-or-v1-..." --test

# Test Google AI
uvx consult7 --api-key "AIza..." --provider google --test

# Test OpenAI
uvx consult7 --api-key "sk-proj-..." --provider openai --test
```

