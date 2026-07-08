"""Tool descriptions and model examples for Consult7 MCP server."""


class ToolDescriptions:
    """Centralized management of tool descriptions and model examples."""

    MODEL_EXAMPLES = {
        "openrouter": [
            '"openai/gpt-5.5" (GPT-5.5, 1M context)',
            '"google/gemini-3.1-pro-preview" (Gemini 3.1 Pro, 1M context, flagship reasoning)',
            '"google/gemini-3-flash-preview" (Gemini 3 Flash, 1M context, fast)',
            '"google/gemini-3.1-flash-lite-preview" (Gemini 3.1 Flash Lite, 1M context, ultra fast)',
            '"anthropic/claude-fable-5" (Claude Fable 5, 1M context, most capable — premium price, for hard problems)',
            '"anthropic/claude-opus-4.8" (Claude Opus 4.8, 1M context, adaptive thinking)',
            '"anthropic/claude-sonnet-4.6" (Claude Sonnet 4.6, 1M context)',
            '"anthropic/claude-haiku-4.5" (Claude Haiku 4.5, 200k context, budget)',
            '"x-ai/grok-4.20" (Grok 4.20, 2M context)',
            '"x-ai/grok-4.1-fast" (Grok 4.1 Fast, 2M context)',
            '"openrouter/fusion" (Fusion: multi-model panel + judge, 128K context; mode = research depth)',
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
- WARNING: a query that is BOTH long AND densely packed with special/math characters (< > | & =, parens, LaTeX) can make the call fail with a misleading "'model' is a required property" error (trailing fields dropped). Put bulk/symbolic detail in a file and keep query short and prose-only.

Quick mnemonics:
- gptt = openai/gpt-5.5 + think (latest GPT, deep reasoning)
- gemt = google/gemini-3.1-pro-preview + think (Gemini 3.1 Pro, flagship reasoning)
- grot = x-ai/grok-4.20 + think (Grok 4.20, deep reasoning)
- oput = anthropic/claude-opus-4.8 + think (Claude Opus, adaptive thinking)
- opuf = anthropic/claude-opus-4.8 + fast (Claude Opus, no reasoning)
- fabt = anthropic/claude-fable-5 + think (Claude Fable, deepest reasoning [effort xhigh]; premium, hard problems only)
- fabm = anthropic/claude-fable-5 + mid (Claude Fable, high-effort reasoning; premium)
- gemf = google/gemini-3-flash-preview + fast (Gemini 3 Flash, ultra fast)
- ULTRA = call GEMT, GPTT, GROT, and OPUT IN PARALLEL (4 frontier models for maximum insight)
- FUSE = openrouter/fusion (one call: a frontier panel deliberates, a judge synthesizes; mode sets web-research depth). 128K context cap — for hard questions, not giant bundles

{provider_notes}

Files: Absolute paths, wildcards only in filenames (e.g., /path/*.py not /*/path/*.py)
Ignores: __pycache__, .env, secrets.py, .DS_Store, .git, node_modules
Limits: Dynamic per model - each model optimized for its full context capacity"""

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
        return 'Absolute file paths or patterns. Example: ["/path/src/*.py", "/path/README.md"]'

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
            "Optional: Save response to file (adds _updated suffix if exists). "
            "Tip: For code files, prompt the LLM to return raw code without markdown formatting"
        )

    @classmethod
    def get_zdr_description(cls) -> str:
        """Get the zdr parameter description."""
        return (
            "Optional: Enable Zero Data Retention. When true, routes only to endpoints "
            "with ZDR policy (prompts not retained by provider). Default: false. "
            "ZDR available: Gemini 3.1 Pro/Flash, Claude Opus 4.8, GPT-5, GPT-5.5. "
            "Not available: Grok 4.20, Claude Fable 5 (requires 30-day retention)"
        )

    @classmethod
    def _get_provider_notes(cls, provider: str) -> str:
        """Get provider-specific notes."""
        return (
            "Performance Modes (use 'mode' parameter):\n"
            "- fast: No reasoning, fastest\n"
            "- mid: Moderate reasoning\n"
            "- think: Maximum reasoning for deepest analysis\n\n"
            "TIMEOUT TIP: If 'think' times out, retry with 'mid' (especially GPT-5.5). "
            "For FUSION this won't help (the cost is the panel of models, not reasoning "
            "depth) — instead retry with a single model (e.g. openai/gpt-5.5, "
            "google/gemini-3.1-pro-preview) or split the question. On timeout consult7 "
            "returns the partial output with a [TRUNCATED] marker rather than discarding it."
        )
