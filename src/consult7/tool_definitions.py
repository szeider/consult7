"""Tool descriptions and model examples for Consult7 MCP server."""


class ToolDescriptions:
    """Centralized management of tool descriptions and model examples."""

    MODEL_EXAMPLES = {
        "openrouter": [
            '"openai/gpt-5.1" (GPT-5.1, 400k context)',
            '"google/gemini-3-pro-preview" (Gemini 3 Pro, 1M context, flagship reasoning)',
            '"google/gemini-2.5-flash" (Gemini Flash, 1M context)',
            '"google/gemini-2.5-flash-lite" (Gemini Flash Lite, 1M context)',
            '"anthropic/claude-sonnet-4.5" (Claude Sonnet 4.5, 1M context)',
            '"anthropic/claude-opus-4.1" (Claude Opus 4.1, 200k context)',
            '"x-ai/grok-4" (Grok 4, 256k context)',
            '"x-ai/grok-4-fast" (Grok 4 Fast, 2M context)',
        ],
    }

    @classmethod
    def get_consultation_tool_description(cls, provider: str) -> str:
        """Get the main description for the consultation tool."""
        provider_notes = cls._get_provider_notes(provider)

        return f"""Analyze files with an LLM - provide absolute file paths, query, model, and mode.

STATELESS: Each call must contain complete absolute paths. No context is remembered.

TIPS:
- Hard questions: Spawn 3 parallel calls with varied query formulations
- Long instructions: Put them in a file, include in files list, keep query short

Quick mnemonics:
- gptt = openai/gpt-5.1 + think (latest GPT, deep reasoning)
- gemt = google/gemini-3-pro-preview + think (Gemini 3 Pro, flagship reasoning)
- grot = x-ai/grok-4 + think (Grok 4, deep reasoning)
- gemf = google/gemini-2.5-flash-lite + fast (ultra fast)
- ULTRA = call GEMT, GPTT, and GROT IN PARALLEL (3 frontier models for maximum insight)

{provider_notes}

Files: Absolute paths, wildcards only in filenames (e.g., /path/*.py not /*/path/*.py)
Ignores: __pycache__, .env, secrets.py, .DS_Store, .git, node_modules
Limits: Dynamic per model - each model optimized for its full context capacity"""

    @classmethod
    def get_model_parameter_description(cls, provider: str) -> str:
        """Get the model parameter description with provider-specific examples."""
        examples = cls.MODEL_EXAMPLES.get(provider, [])

        # Show all 8 flagship models
        model_desc = "Model name. Options:\n"
        for example in examples:
            model_desc += f"  {example}\n"

        return model_desc.rstrip()

    @classmethod
    def get_files_description(cls) -> str:
        """Get the files parameter description."""
        return 'Absolute file paths or patterns. Example: ["/path/src/*.py", "/path/README.md"]'

    @classmethod
    def get_query_description(cls) -> str:
        """Get the query parameter description."""
        return "Your question about the files"

    @classmethod
    def get_output_file_description(cls) -> str:
        """Get the output_file parameter description."""
        return (
            "Optional: Save response to file (adds _updated suffix if exists). "
            "Tip: For code files, prompt the LLM to return raw code without markdown formatting"
        )

    @classmethod
    def _get_provider_notes(cls, provider: str) -> str:
        """Get provider-specific notes."""
        return (
            "Performance Modes (use 'mode' parameter):\n"
            "- fast: No reasoning, fastest\n"
            "- mid: Moderate reasoning\n"
            "- think: Maximum reasoning for deepest analysis"
        )
