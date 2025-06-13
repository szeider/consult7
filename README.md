# Consult7 MCP Server

**Consult7** is a Model Context Protocol (MCP) server that enables AI agents to consult large context window models for analyzing extensive file collections - entire codebases, document repositories, or mixed content that exceed the current agent's context limits. Supports providers *Openrouter*, *OpenAI*, and *Google*.

## Why Consult7?

When working with AI agents that have limited context windows (like Claude with 200K tokens), **Consult7** allows them to leverage models with massive context windows to analyze large codebases or document collections that would otherwise be impossible to process in a single query.

> "For Claude Code users, Consult7 is a game changer."

## How it works

**Consult7** recursively collects all files from a given path that match your regex pattern (including all subdirectories), assembles them into a single context, and sends them to a large context window model along with your query. The result of this query is directly fed back to the agent you are working with.

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

