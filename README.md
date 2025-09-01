# Consult7 MCP Server

**Consult7** is a Model Context Protocol (MCP) server that enables AI agents to consult large context window models for analyzing extensive file collections - entire codebases, document repositories, or mixed content that exceed the current agent's context limits. Supports providers *Openrouter*, *OpenAI*, and *Google*.

## Why Consult7?

When working with AI agents that have limited context windows (like Claude with 200K tokens), **Consult7** allows them to leverage models with massive context windows to analyze large codebases or document collections that would otherwise be impossible to process in a single query.

> "For Claude Code users, Consult7 is a game changer."

## How it works

**Consult7** collects files from the specific paths you provide (with optional wildcards in filenames), assembles them into a single context, and sends them to a large context window model along with your query. The result is directly fed back to the agent you are working with.

## Example Use Cases

### Summarize an entire codebase

* **Files:** `["/Users/john/project/src/*.py", "/Users/john/project/lib/*.py"]`
* **Query:** "Summarize the architecture and main components of this Python project"
* **Model:** `"gemini-2.5-flash"`

### Find specific method definitions
* **Files:** `["/Users/john/backend/src/*.py", "/Users/john/backend/auth/*.js"]`
* **Query:** "Find the implementation of the authenticate_user method and explain how it handles password verification"
* **Model:** `"gemini-2.5-pro"`

### Analyze test coverage
* **Files:** `["/Users/john/project/tests/*_test.py", "/Users/john/project/src/*.py"]`
* **Query:** "List all the test files and identify which components lack test coverage"
* **Model:** `"gemini-2.5-flash"`

### Complex analysis with thinking mode
* **Files:** `["/Users/john/webapp/src/*.py", "/Users/john/webapp/auth/*.py", "/Users/john/webapp/api/*.js"]`
* **Query:** "Analyze the authentication flow across this codebase. Think step by step about security vulnerabilities and suggest improvements"
* **Model:** `"gemini-2.5-flash|thinking"`

### Generate a report saved to file
* **Files:** `["/Users/john/project/src/*.py", "/Users/john/project/tests/*.py"]`
* **Query:** "Generate a comprehensive code review report with architecture analysis, code quality assessment, and improvement recommendations"
* **Model:** `"gemini-2.5-pro"`
* **Output File:** `"/Users/john/reports/code_review.md"`
* **Result:** Returns `"Result has been saved to /Users/john/reports/code_review.md"` instead of flooding the agent's context

## Installation

### Claude Code

Simply run:

```bash
# OpenRouter
claude mcp add -s user consult7 uvx -- consult7 openrouter your-api-key

# Google AI
claude mcp add -s user consult7 uvx -- consult7 google your-api-key

# OpenAI
claude mcp add -s user consult7 uvx -- consult7 openai your-api-key
```

### Claude Desktop

Add to your Claude Desktop configuration file:

```json
{
  "mcpServers": {
    "consult7": {
      "type": "stdio",
      "command": "uvx",
      "args": ["consult7", "openrouter", "your-api-key"]
    }
  }
}
```

Replace `openrouter` with your provider choice (`google` or `openai`) and `your-api-key` with your actual API key.

No installation required - `uvx` automatically downloads and runs consult7 in an isolated environment.


## Command Line Options

```bash
uvx consult7 <provider> <api-key> [--test]
```

- `<provider>`: Required. Choose from `openrouter`, `google`, or `openai`
- `<api-key>`: Required. Your API key for the chosen provider
- `--test`: Optional. Test the API connection

The model is specified when calling the tool, not at startup. The server shows example models for your provider on startup.

### Model Examples

#### Google
Standard models:
- `"gemini-2.5-flash"` - Fast model
- `"gemini-2.5-flash-lite"` - Ultra fast lite model
- `"gemini-2.5-pro"` - Intelligent model
- `"gemini-2.0-flash-exp"` - Experimental model

With thinking mode (add `|thinking` suffix):
- `"gemini-2.5-flash|thinking"` - Fast with deep reasoning
- `"gemini-2.5-flash-lite|thinking"` - Ultra fast with deep reasoning
- `"gemini-2.5-pro|thinking"` - Intelligent with deep reasoning

#### OpenRouter
Standard models:
- `"google/gemini-2.5-pro"` - Intelligent, 1M context
- `"google/gemini-2.5-flash"` - Fast, 1M context
- `"google/gemini-2.5-flash-lite"` - Ultra fast, 1M context
- `"anthropic/claude-sonnet-4"` - Claude Sonnet, 200k context
- `"anthropic/claude-opus-4.1"` - Claude Opus 4.1, 200k context
- `"openai/gpt-5"` - GPT-5, 400k context
- `"openai/gpt-4.1"` - GPT-4.1, 1M+ context

With reasoning mode (add `|thinking` suffix):
- `"anthropic/claude-sonnet-4|thinking"` - Claude with 31,999 reasoning tokens
- `"anthropic/claude-opus-4.1|thinking"` - Opus 4.1 with reasoning
- `"google/gemini-2.5-flash-lite|thinking"` - Ultra fast with reasoning
- `"openai/gpt-5|thinking"` - GPT-5 with reasoning
- `"openai/gpt-4.1|thinking"` - GPT-4.1 with reasoning effort=high

#### OpenAI
Standard models (include context length):
- `"gpt-5|400k"` - GPT-5, 400k context
- `"gpt-5-mini|400k"` - GPT-5 Mini, faster
- `"gpt-5-nano|400k"` - GPT-5 Nano, ultra fast
- `"gpt-4.1-2025-04-14|1047576"` - 1M+ context, very fast
- `"gpt-4.1-nano-2025-04-14|1047576"` - 1M+ context, ultra fast
- `"o3-2025-04-16|200k"` - Advanced reasoning model
- `"o4-mini-2025-04-16|200k"` - Fast reasoning model

O-series models with |thinking marker:
- `"o1-mini|128k|thinking"` - Mini reasoning with |thinking marker
- `"o3-2025-04-16|200k|thinking"` - Advanced reasoning with |thinking marker

**Note:** For OpenAI, |thinking is only supported on o-series models and serves as an informational marker. The models use reasoning tokens automatically.

**Advanced:** You can specify custom thinking tokens with `|thinking=30000` but this is rarely needed. 

## File Specification Rules

When using the consultation tool, you provide a list of file paths with these rules:

1. **All paths must be absolute** (start with `/`)
   - ✅ Good: `/Users/john/project/src/*.py`
   - ❌ Bad: `src/*.py` or `./src/*.py`

2. **Wildcards (`*`) only allowed in filenames**, not in directory paths
   - ✅ Good: `/Users/john/project/*.py`
   - ❌ Bad: `/Users/*/project/*.py` or `/Users/john/**/*.py`

3. **Must specify extension when using wildcards**
   - ✅ Good: `/Users/john/project/*.py`
   - ❌ Bad: `/Users/john/project/*`

4. **Mix specific files and patterns freely**
   - ✅ Good: `["/path/src/*.py", "/path/README.md", "/path/tests/*_test.py"]`

5. **Common patterns:**
   - All Python files in a directory: `/path/to/dir/*.py`
   - Test files: `/path/to/tests/*_test.py` or `/path/to/tests/test_*.py`
   - Multiple extensions: Use multiple patterns like `["/path/*.js", "/path/*.ts"]`

The tool automatically ignores: `__pycache__`, `.env`, `secrets.py`, `.DS_Store`, `.git`, `node_modules`

**Size limits:** 1MB per file, 4MB total (optimized for ~1M token context windows)

## Tool Parameters

The consultation tool accepts the following parameters:

- **files** (required): List of absolute file paths or patterns with wildcards in filenames only
- **query** (required): Your question or instruction for the LLM to process the files
- **model** (required): The LLM model to use (see Model Examples above for each provider)
- **output_file** (optional): Absolute path to save the response to a file instead of returning it
  - If the file exists, it will be saved with `_updated` suffix (e.g., `report.md` → `report_updated.md`)
  - When specified, returns only: `"Result has been saved to /path/to/file"`
  - Useful for generating reports, documentation, or analyses without flooding the agent's context

## Testing

```bash
# Test OpenRouter
uvx consult7 openrouter sk-or-v1-... --test

# Test Google AI
uvx consult7 google AIza... --test

# Test OpenAI
uvx consult7 openai sk-proj-... --test
```

## Uninstalling

To remove consult7 from Claude Code (or before reinstalling):

```bash
claude mcp remove consult7 -s user
```

