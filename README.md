# Consult7 MCP Server

A Model Context Protocol (MCP) server that enables AI agents to consult large context window models for analyzing extensive file collections - entire codebases, document repositories, or mixed content that exceed the current agent's context limits.

## Why Consult7?

When working with AI agents that have limited context windows (like Claude with 200K tokens), Consult7 allows them to leverage models with massive context windows to analyze large codebases or document collections that would otherwise be impossible to process in a single query.

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

### Documentation analysis
* **Query:** "Review all markdown files and create a comprehensive documentation index"
* **Pattern:** `".*\.md$"` (Markdown files)
* **Path:** `/Users/john/docs`

### Security audit
* **Query:** "Identify potential security vulnerabilities in the codebase, focusing on SQL queries, authentication, and input validation"
* **Pattern:** `".*\.(py|js|php)$"` (Python, JavaScript, PHP files)
* **Path:** `/Users/john/webapp`
* **Exclude:** `".*test.*"` (skip test files)

### API endpoint mapping
* **Query:** "Create a complete list of all REST API endpoints with their methods, parameters, and authentication requirements"
* **Pattern:** `".*\.(py|js|ts)$"` (backend files)
* **Path:** `/Users/john/api-server`

## Installation

### Option 1: Run without installation (Recommended)

Run directly from GitHub:

```bash
uvx --from git+https://github.com/szeider/consult7 consult7 --api-key "..." --provider google --test
```

### Option 2: Install with uv

```bash
# Install from PyPI (once published)
uv add consult7

# Or install from GitHub
uv add git+https://github.com/szeider/consult7

# Or install from local directory for development
git clone https://github.com/szeider/consult7
cd consult7
uv pip install -e .
```

## Usage

### Command Line Options

```bash
uvx consult7 --api-key KEY [--provider PROVIDER] [--model MODEL] [--context TOKENS] [--test]
```

- `--api-key`: Required. Your API key for the chosen provider
- `--provider`: Optional. Choose from `openrouter` (default), `google`, or `openai`
- `--model`: Optional. Specific model to use (defaults to provider's default)
- `--context`: Optional. Model context window size (default: 1M). Accepts formats like '2M', '128K', or '1000000'
- `--test`: Optional. Test the API connection

### Testing Connections

```bash
# Test OpenRouter (default)
uvx consult7 --api-key "sk-or-v1-..." --test

# Test Google AI
uvx consult7 --api-key "AIza..." --provider google --test

# Test OpenAI
uvx consult7 --api-key "sk-proj-..." --provider openai --test
```


## MCP Configuration

### For Claude Desktop

Add to your Claude Desktop configuration file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "consult7": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/szeider/consult7",
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

**Configuration parameters:**
- `--api-key`: Required. Your API key for the chosen provider
- `--provider`: Optional. Choose from `openrouter` (default), `google`, or `openai`
- `--model`: Optional. Specific model to use (defaults: openrouter → `google/gemini-2.5-pro-preview`, google → `gemini-2.0-flash-exp`, openai → `gpt-4o`)
- `--context`: Optional. Model context window (default: 1M). Use `2M` for Google Gemini models, `128K` for OpenAI

### For Claude Code

Add to your settings (⌘+, on Mac) following the same pattern as above, but under `"claude-code.mcpServers"` instead.

## Tool: consultation

The server provides a single tool called `consultation` that:
1. Collects files matching a regex pattern from a directory
2. Formats them into a structured document
3. Sends to an LLM with your query
4. Returns the LLM's analysis

**Parameters:**
- `path`: Absolute path to search from
- `pattern`: Regex to match filenames (e.g., `".*\.py$"`)
- `query`: Your question about the code
- `exclude_pattern`: Optional regex to exclude files

