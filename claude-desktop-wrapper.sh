#!/bin/bash
# Wrapper script for Claude Desktop to properly set environment variables

# Set the GitHub Copilot API key from the command line argument
export GITHUB_COPILOT_API_KEY="$3"

# Call the actual consult7 command
exec uvx --from /Users/francojc/.local/mcp/dev/consult7 consult7 "$1" "$2"