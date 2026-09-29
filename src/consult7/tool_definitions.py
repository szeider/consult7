"""Tool descriptions and model examples for Consult7 MCP server."""


class ToolDescriptions:
    """Centralized management of tool descriptions and model examples."""

    MODEL_EXAMPLES = {
        "openrouter": [
            '"openai/gpt-6-astra" (GPT-6 Astra, 1M context, top-tier GPT — premium price)',
            '"google/gemini-3.1-pro-preview" (Gemini 3.1 Pro, 1M context, flagship reasoning)',
            '"google/gemini-3-flash-preview" (Gemini 3 Flash, 1M context, fast)',
            '"google/gemini-3.1-flash-lite-preview" (Gemini 3.1 Flash Lite, 1M context, ultra fast)',
            '"anthropic/claude-fable-5.1" (Claude Fable 5.1, 1M context, most capable — premium price, for hard problems)',
            '"anthropic/claude-opus-4.8" (Claude Opus 4.8, 1M context, adaptive thinking)',
            '"anthropic/claude-sonnet-4.6" (Claude Sonnet 4.6, 1M context)',
            '"anthropic/claude-haiku-4.5" (Claude Haiku 4.5, 200k context, budget)',
            '"x-ai/grok-4.7" (Grok 4.7, 500K context, frontier Grok)',
            '"x-ai/grok-4.20" (Grok 4.20, 2M context, for giant bundles)',
            '"x-ai/grok-4.1-fast" (Grok 4.1 Fast, 2M context)',
            '"openrouter/fusion" (Fusion: multi-model panel + judge, 128K context; mode = research depth)',
        ],
    }

    @classmethod
    def get_consultation_tool_description(cls, provider: str) -> str:
        """Get the main description for the consultation tool."""
        provider_notes = cls._get_provider_notes(provider)

        # Keep this under ~2,000 characters: Claude Code truncates longer tool
        # descriptions, so the rules a caller needs most come first.
        return f"""Analyze files with an LLM - provide absolute file paths, query, model, and mode. Stateless: every call must list complete absolute paths.

Files: absolute paths; wildcards only in filenames and with an extension (/path/*.py, not /path/*/x.py or /path/*). Never sent: __pycache__, .env, secrets.py, .DS_Store, .git, node_modules (wildcards skip them; naming one is an error). A bad path, a wildcard with no match, or files over the model's size limit fail the call before anything is sent (no cost). files=[] means query only.

{provider_notes}

Tips: for hard questions, spawn 3 parallel calls with varied formulations. Put long or symbol-heavy instructions in a file and keep the query short prose (see query).

Mnemonics:
- gptt = openai/gpt-6-astra + think (premium)
- gemt = google/gemini-3.1-pro-preview + think
- grot = x-ai/grok-4.7 + think (500K context, slow; bigger bundles: x-ai/grok-4.20, 2M)
- oput / opuf = anthropic/claude-opus-4.8 + think / fast
- fabt / fabm = anthropic/claude-fable-5.1 + think / mid (premium, hard problems)
- gemf = google/gemini-3-flash-preview + fast
- ULTRA = GPTT, GROT and FABT in parallel (3 calls in one message)
- FUSE = openrouter/fusion (panel + judge in one call; mode sets web-research depth; 128K context)"""

    @classmethod
    def get_model_parameter_description(cls, provider: str) -> str:
        """Get the model parameter description with provider-specific examples."""
        examples = cls.MODEL_EXAMPLES.get(provider, [])

        # Show all flagship models
        model_desc = "Model name. Options:\n"
        for example in examples:
            model_desc += f"  {example}\n"

        return model_desc.rstrip()

    @classmethod
    def get_files_description(cls) -> str:
        """Get the files parameter description."""
        return (
            'Absolute file paths or patterns. Example: ["/path/src/*.py", "/path/README.md"]. '
            "Use [] for a query without files."
        )

    @classmethod
    def get_query_description(cls) -> str:
        """Get the query parameter description."""
        return (
            "Your question about the files. KEEP SHORT and mostly prose. A query that is both "
            "long AND densely packed with special/math characters (< > | & =, parentheses, "
            "LaTeX) can make the call fail with a misleading \"'model' is a required property\" "
            "error (the trailing model/mode fields get dropped). Put long or symbol-heavy detail "
            "in a file (via `files`) and keep `query` short."
        )

    @classmethod
    def get_output_file_description(cls) -> str:
        """Get the output_file parameter description."""
        return (
            "Optional: absolute path to save the response to, checked before the call "
            "(if the file exists, saves as name_updated.ext). "
            "Tip: For code files, prompt the LLM to return raw code without markdown formatting"
        )

    @classmethod
    def get_zdr_description(cls) -> str:
        """Get the zdr parameter description."""
        return (
            "Optional: Enable Zero Data Retention. When true, routes only to endpoints "
            "with ZDR policy (prompts not retained by provider). Default: false. "
            "ZDR available: GPT-6 Astra, Grok 4.7, Gemini 3.1 Pro/Flash, Claude Opus 4.8, "
            "GPT-5, GPT-5.5, Grok 4.6. "
            "Not available: Claude Fable 5.1 and 5 (require 30-day retention), GPT-5.6 Sol, "
            "Grok 4.20"
        )

    @classmethod
    def _get_provider_notes(cls, provider: str) -> str:
        """Get provider-specific notes."""
        return (
            "Modes: fast = no reasoning requested (GPT-6 Astra, Grok 4.7 and Fable still "
            "reason at their default level); mid = moderate reasoning; think = maximum "
            "reasoning. If think times out, retry with mid; for FUSE use a single model or "
            "split the question instead. On timeout the partial output is returned with a "
            "[TRUNCATED] marker."
        )
