# v1.1.0

## Major Feature

- Model can now be selected dynamically per tool call
- Previously, the model was fixed at startup via command line

## Breaking Changes

- Command line arguments changed from flags (`--api-key`, `--provider`) to positional arguments
- Removed `--model` parameter (model is now specified during tool invocation)

## Other Changes

- Simplified command line interface: `uvx consult7 <provider> <api-key>`
- Provider-specific model examples shown at startup
- Improved error messages

## Installation

```bash
# PyPI
pip install consult7==1.1.0

# Claude Code
claude mcp add -s user consult7 uvx -- consult7 <provider> <api-key>
```