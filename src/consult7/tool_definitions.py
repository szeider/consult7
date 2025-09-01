"""Tool descriptions and model examples for Consult7 MCP server."""


class ToolDescriptions:
    """Centralized management of tool descriptions and model examples."""

    MODEL_EXAMPLES = {
        "openrouter": [
            '"google/gemini-2.5-pro" (intelligent, 1M context)',
            '"google/gemini-2.5-flash" (fast, 1M context)',
            '"google/gemini-2.5-flash-lite" (ultra fast, 1M context)',
            '"anthropic/claude-sonnet-4" (Claude Sonnet, 200k context)',
            '"anthropic/claude-opus-4.1" (Claude Opus 4.1, 200k context)',
            '"openai/gpt-5" (GPT-5, 400k context)',
            '"openai/gpt-4.1" (GPT-4.1, 1M+ context)',
            '"anthropic/claude-sonnet-4|thinking" (Claude with 31,999 tokens)',
            '"anthropic/claude-opus-4.1|thinking" (Opus 4.1 with reasoning)',
            '"google/gemini-2.5-flash-lite|thinking" (ultra fast with reasoning)',
            '"openai/gpt-5|thinking" (GPT-5 with reasoning)',
            '"openai/gpt-4.1|thinking" (GPT-4.1 with reasoning effort=high)',
        ],
        "google": [
            '"gemini-2.5-flash" (fast, standard mode)',
            '"gemini-2.5-flash-lite" (ultra fast, lite model)',
            '"gemini-2.5-pro" (intelligent, standard mode)',
            '"gemini-2.0-flash-exp" (experimental model)',
            '"gemini-2.5-flash|thinking" (fast with deep reasoning)',
            '"gemini-2.5-flash-lite|thinking" (ultra fast with deep reasoning)',
            '"gemini-2.5-pro|thinking" (intelligent with deep reasoning)',
        ],
        "openai": [
            '"gpt-5|400k" (GPT-5, 400k context)',
            '"gpt-5-mini|400k" (GPT-5 Mini, faster)',
            '"gpt-5-nano|400k" (GPT-5 Nano, ultra fast)',
            '"gpt-4.1-2025-04-14|1047576" (1M+ context, very fast)',
            '"gpt-4.1-nano-2025-04-14|1047576" (1M+ context, ultra fast)',
            '"o3-2025-04-16|200k" (advanced reasoning model)',
            '"o4-mini-2025-04-16|200k" (fast reasoning model)',
            '"o1-mini|128k|thinking" (mini reasoning with |thinking marker)',
            '"o3-2025-04-16|200k|thinking" (advanced reasoning with |thinking marker)',
        ],
    }

    @classmethod
    def get_consultation_tool_description(cls, provider: str) -> str:
        """Get the main description for the consultation tool."""
        provider_notes = cls._get_provider_notes(provider)

        return f"""Analyze files with an LLM by providing a list of file paths.

Provide a list of absolute file paths (with optional wildcards in filenames only).
The tool collects these files, formats them, and sends them to your chosen LLM
along with your query.

{provider_notes}

File specification rules:
- All paths must be absolute (start with /)
- Wildcards (*) allowed ONLY in filenames, not in directory paths
- Must specify extension when using wildcards (e.g., *.py not just *)
- Mix specific files and patterns: ["/path/src/*.py", "/path/README.md"]

Examples:
- Single file: ["/Users/john/project/main.py"]
- Multiple files: ["/path/src/*.py", "/path/tests/*.py", "/path/README.md"]
- All Python files in a directory: ["/Users/john/project/src/*.py"]

Automatically ignores: __pycache__, .env, secrets.py, .DS_Store, .git, node_modules
Size limits: 1MB per file, 4MB total (optimized for ~1M token context)"""

    @classmethod
    def get_model_parameter_description(cls, provider: str) -> str:
        """Get the model parameter description with provider-specific examples."""
        examples = cls.MODEL_EXAMPLES.get(provider, [])

        if provider == "openai":
            model_desc = (
                "The model to use. Include context length with | "
                'separator (e.g., "model-name|200k").\nExamples:'
            )
        else:
            model_desc = "The model to use. Examples:"

        # Add examples on new lines, but check where to add |thinking note
        thinking_examples_start = -1
        for i, example in enumerate(examples):
            if "|thinking" in example and thinking_examples_start == -1:
                thinking_examples_start = i
                # Add the |thinking note before the first thinking example
                if provider in ["google", "openrouter"]:
                    suffix_type = "thinking" if provider == "google" else "reasoning"
                    model_desc += f"\n\nAdd |thinking suffix for {suffix_type} mode:"
                elif provider == "openai":
                    model_desc += "\n\n|thinking suffix (o-series models only):"
            model_desc += f"\n  {example}"

        return model_desc

    @classmethod
    def get_files_description(cls) -> str:
        """Get the files parameter description."""
        return (
            "List of absolute file paths or patterns. Examples:\n"
            '  - Specific file: "/Users/john/project/main.py"\n'
            '  - Directory with wildcard: "/Users/john/project/src/*.py"\n'
            '  - Multiple patterns: ["/path/src/*.js", "/path/lib/*.js", '
            '"/path/README.md"]\n'
            "Rules: Paths must be absolute, wildcards only in filenames, "
            "extension required with wildcards"
        )

    @classmethod
    def get_query_description(cls) -> str:
        """Get the query parameter description."""
        return "Your question about the code (e.g., 'Which functions handle authentication?')"

    @classmethod
    def get_output_file_description(cls) -> str:
        """Get the output_file parameter description."""
        return (
            "Optional: Absolute path to save the LLM response to a file instead of returning it. "
            "If the file exists, it will be saved with '_updated' suffix (e.g., report.md → report_updated.md). "
            "When specified, the tool returns only a brief confirmation message."
        )

    @classmethod
    def _get_provider_notes(cls, provider: str) -> str:
        """Get provider-specific notes."""
        if provider == "openai":
            return ""  # Move note to model parameter description
        elif provider == "google":
            return (
                "Thinking Mode: Add |thinking to any model for deep reasoning "
                "(e.g., gemini-2.5-flash|thinking).\n"
                "Advanced: For custom thinking limits, use |thinking=30000"
            )
        elif provider == "openrouter":
            return (
                "Reasoning Mode: Add |thinking suffix to enable deeper analysis.\n"
                "Advanced: For custom limits, use |thinking=30000"
            )
        else:
            return "Note: Model context windows are auto-detected from the API"
