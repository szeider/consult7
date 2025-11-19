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

# API constants
DEFAULT_TEMPERATURE = 0.7  # Default temperature for all providers
OPENROUTER_TIMEOUT = 600.0  # 10 minutes - very generous timeout for API calls
API_FETCH_TIMEOUT = 30.0  # 30 seconds for fetching model info
DEFAULT_CONTEXT_LENGTH = 128_000  # Default context when not available from API
LLM_CALL_TIMEOUT = 600.0  # 10 minutes - very generous timeout for LLM calls

# Application constants
SERVER_VERSION = "3.1.0"
EXIT_SUCCESS = 0
EXIT_FAILURE = 1
MIN_ARGS = 1

# Output token constants
DEFAULT_OUTPUT_TOKENS = 8_000  # Default max output tokens (~300 lines of code)
SMALL_OUTPUT_TOKENS = 4_000  # Output tokens for smaller models
SMALL_MODEL_THRESHOLD = 100_000  # Context size threshold for small models

# Test model for OpenRouter
TEST_MODELS = {
    "openrouter": "openai/gpt-5.1",
}
