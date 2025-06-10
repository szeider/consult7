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

### Using Specific Models

```bash
# OpenRouter with Claude
uvx consult7 --api-key "sk-or-v1-..." --model "anthropic/claude-3.5-sonnet"

# Google AI with 2M token model
uvx consult7 --api-key "AIza..." --provider google --model "gemini-2.5-pro-preview-06-05" --context 2M

# OpenAI with GPT-4o mini and custom context
uvx consult7 --api-key "sk-proj-..." --provider openai --model "gpt-4o-mini" --context 128K
```

### Context Window Examples

```bash
# Use 2 million token context
uvx consult7 --api-key "..." --provider google --context 2M

# Use 128K token context
uvx consult7 --api-key "..." --provider openai --context 128K

# Use exact token count
uvx consult7 --api-key "..." --context 500000
```

## MCP Configuration

### For Claude Desktop

Add to your Claude Desktop configuration file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

#### OpenRouter (Default)

```json
{
  "mcpServers": {
    "consult7": {
      "command": "uvx",
      "args": [
        "consult7",
        "--api-key", "your-openrouter-api-key"
      ]
    }
  }
}
```

#### Google AI
```json
{
  "mcpServers": {
    "consult7": {
      "command": "uvx",
      "args": [
        "consult7",
        "--api-key", "your-google-api-key",
        "--provider", "google"
      ]
    }
  }
}
```

#### OpenAI
```json
{
  "mcpServers": {
    "consult7": {
      "command": "uvx",
      "args": [
        "consult7",
        "--api-key", "your-openai-api-key",
        "--provider", "openai"
      ]
    }
  }
}
```

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

## Configuration

**Ignored by default:**
- `__pycache__`
- `.env`
- `secrets.py`
- `.DS_Store`
- `.git`
- `node_modules`

**Size limits:**
- 10MB per file
- 100MB total
- 100KB response

## API Key Setup

### OpenRouter
1. Sign up at https://openrouter.ai
2. Get your API key from the dashboard
3. Format: `sk-or-v1-...`

### Google AI
1. Visit https://makersuite.google.com/app/apikey
2. Create a new API key
3. Format: `AIza...`

### OpenAI
1. Visit https://platform.openai.com/api-keys
2. Create a new API key
3. Format: `sk-proj-...`

## Choosing a Provider

- **OpenRouter**: Best for flexibility and access to multiple models
- **Google AI**: Best for largest context windows (use --context 2M for newer Gemini models)
- **OpenAI**: Best for GPT-4o's advanced reasoning capabilities

## Context Window Notes

- Default: 1M tokens (suitable for most models)
- Google Gemini models support up to 2M tokens (use `--context 2M`)
- OpenAI models typically support 128K tokens (use `--context 128K`)
- OpenRouter auto-detects the model's context size when `--context` is not specified

## Supported Providers

### OpenRouter (Default)

- Access to multiple models through a unified API
- Default model: `google/gemini-2.5-pro-preview`
- Supports Anthropic, Google, Meta, and other providers
- Auto-detects context size from API when --context not specified

### Google AI (Direct)

- Direct access to Gemini models
- Default model: `gemini-2.0-flash-exp`
- Popular models: `gemini-2.5-pro-preview-06-05`, `gemini-2.5-flash-preview-05-20`

### OpenAI

- Access to GPT models
- Default model: `gpt-4o`
- Also supports: `gpt-4o-mini`, `gpt-4.1-nano-2025-04-14`