"""Constants and static configuration for Consult7 MCP server."""

# File size limits
MAX_FILE_SIZE = 1_000_000  # 1MB per file (reasonable for source code files)
MAX_TOTAL_SIZE = 4_000_000  # 4MB total (~1M tokens with 3.5 chars/token)
MAX_RESPONSE_SIZE = 100_000  # 100KB response
FILE_SEPARATOR = "-" * 80

# Default ignored paths
DEFAULT_IGNORED = [
    "__pycache__",
    ".env",
    "secrets.py",
    ".DS_Store",
    ".git",
    "node_modules",
]

# API URLs
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODELS_URL = "https://openrouter.ai/api/v1/models"

# OpenRouter Fusion (multi-model deliberation with a judge)
# A panel of frontier models answers in parallel, a judge compares them, and the
# judge writes the final answer. consult7 uses the default "Quality" panel
# (opus + gpt + gemini-pro, auto-tracking '~latest' aliases) by leaving
# analysis_models/model unset. mode maps to the web-search/fetch depth budget.
FUSION_MODEL = "openrouter/fusion"
FUSION_MAX_TOOL_CALLS = {"fast": 2, "mid": 8, "think": 16}  # max_tool_calls per panel/judge step

# API constants
DEFAULT_TEMPERATURE = 0.7  # Default temperature for all providers
# Total wall-clock budget for one streaming call (also the httpx per-operation
# timeout). Fusion (panel + judge + web research) is the slowest call type; on
# expiry the provider returns whatever it streamed so far rather than discarding
# it. This is a safety brake we expect most calls to finish well within.
OPENROUTER_TIMEOUT = 1800.0  # 30 minutes
API_FETCH_TIMEOUT = 30.0  # 30 seconds for fetching model info
DEFAULT_CONTEXT_LENGTH = 128_000  # Default context when not available from API
# Outer backstop in consultation.py. Set strictly above OPENROUTER_TIMEOUT so the
# provider's graceful partial-return path always fires first; this only trips if
# call_llm hangs *outside* the stream loop (get_model_info has its own timeout).
LLM_CALL_TIMEOUT = OPENROUTER_TIMEOUT + 120.0  # backstop only (~32 minutes)

# Application constants
SERVER_VERSION = "3.9.1"
EXIT_SUCCESS = 0
EXIT_FAILURE = 1
MIN_ARGS = 1

# Output token constants
DEFAULT_OUTPUT_TOKENS = 8_000  # Default max output tokens (~300 lines of code)
SMALL_OUTPUT_TOKENS = 4_000  # Output tokens for smaller models
SMALL_MODEL_THRESHOLD = 100_000  # Context size threshold for small models

# Test model for OpenRouter
TEST_MODELS = {
    "openrouter": "openai/gpt-5.6-sol",
}
