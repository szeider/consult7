"""Constants and static configuration for Consult7 MCP server."""

# File size limits
MAX_FILE_SIZE = 10_000_000  # 10MB per file (increased for large context models)
MAX_TOTAL_SIZE = 100_000_000  # 100MB total (increased for large context models)
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
OPENROUTER_TIMEOUT = 30.0  # Timeout for OpenRouter API calls
API_FETCH_TIMEOUT = 10.0  # Timeout for fetching model info
DEFAULT_CONTEXT_LENGTH = 128_000  # Default context when not available from API
LLM_CALL_TIMEOUT = (
    180.0  # 180 seconds - reasonable default with 20s buffer before MCP's 200s timeout
)

# Application constants
SERVER_VERSION = "1.3.0"
EXIT_SUCCESS = 0
EXIT_FAILURE = 1
MIN_ARGS = 2

# Output token constants
DEFAULT_OUTPUT_TOKENS = 8_000  # Default max output tokens (~300 lines of code)
SMALL_OUTPUT_TOKENS = 4_000  # Output tokens for smaller models
SMALL_MODEL_THRESHOLD = 100_000  # Context size threshold for small models

# Test models for each provider
TEST_MODELS = {
    "openrouter": "google/gemini-2.5-flash-preview-05-20",
    "google": "gemini-2.0-flash-exp",
    "openai": "gpt-4o-mini|128k",
}
