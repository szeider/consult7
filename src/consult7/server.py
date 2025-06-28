"""Consult7 MCP server - Analyze large file collections with AI models."""

import sys
import logging
from mcp.server import Server
import mcp.server.stdio
import mcp.types as types
from mcp.server.models import InitializationOptions
from mcp.server.lowlevel import NotificationOptions

# Import constants
from .constants import SERVER_VERSION, EXIT_SUCCESS, EXIT_FAILURE, MIN_ARGS, TEST_MODELS
from .tool_definitions import ToolDescriptions
from .providers import PROVIDERS
from .consultation import consultation_impl

# Set up consult7 logger
logger = logging.getLogger("consult7")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
logger.addHandler(handler)


class Consult7Server(Server):
    """Extended MCP Server that stores API configuration."""

    def __init__(self, name: str, api_key: str, provider: str):
        super().__init__(name)
        self.api_key = api_key
        self.provider = provider


async def test_api_connection(server: Consult7Server):
    """Test the API connection with a simple query."""
    print(f"\nTesting {server.provider} API connection...")
    print(f"API Key: {'Set' if server.api_key else 'Not set'}")

    if not server.api_key:
        print("\nError: No API key provided!")
        print("Use --api-key flag")
        return False

    # Use a default test model for each provider
    test_model = TEST_MODELS.get(server.provider, TEST_MODELS["openrouter"])

    # Simple test query
    test_content = "This is a test file with sample content."
    test_query = "Reply with 'API test successful' if you can read this."

    # Call appropriate provider
    provider_instance = PROVIDERS.get(server.provider)
    if not provider_instance:
        print(f"\nError: Unknown provider '{server.provider}'")
        return False

    response, error, _ = await provider_instance.call_llm(
        test_content, test_query, test_model, server.api_key
    )

    if error:
        print(f"\nError: {error}")
        return False

    print(f"\nSuccess! Response from {test_model} ({server.provider}):")
    print(response)
    return True


async def main():
    """Parse command line arguments and run the server."""
    # Simple argument parsing
    args = sys.argv[1:]
    test_mode = False
    include_images = False # New flag

    # Process flags like --test and --include-images
    processed_args = []
    for arg in args:
        if arg == "--test":
            test_mode = True
        elif arg == "--include-images":
            include_images = True
        else:
            processed_args.append(arg)

    args = processed_args

    # Validate arguments (provider and api_key are mandatory)
    if len(args) < MIN_ARGS: # MIN_ARGS is likely 2 (provider, api_key)
        print("Error: Missing required arguments.")
        print("Usage: consult7 <provider> <api-key> [--include-images] [--test]")
        print()
        print("Providers: openrouter, google, openai")
        print("Flags:")
        print("  --include-images: Enable image processing (currently Google provider only).")
        print("  --test: Run a connection test with the provider.")
        print()
        print("Examples:")
        print("  consult7 google AIza... --include-images")
        print("  consult7 openrouter sk-or-v1-... --test")
        sys.exit(EXIT_FAILURE)

    if len(args) > MIN_ARGS:
        print(f"Error: Too many positional arguments. Expected {MIN_ARGS}, got {len(args)}.")
        print("Usage: consult7 <provider> <api-key> [--include-images] [--test]")
        sys.exit(EXIT_FAILURE)

    provider = args[0]
    api_key = args[1]

    if provider not in PROVIDERS.keys():
        print(f"Error: Invalid provider '{provider}'.")
        print(f"Valid providers: {', '.join(PROVIDERS.keys())}")
        sys.exit(EXIT_FAILURE)

    # Create server with stored configuration, now including include_images
    server = Consult7Server("consult7", api_key, provider)
    # Store include_images flag on the server instance or pass it to relevant functions
    server.include_images = include_images

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        """List available tools with provider-specific model examples. (Temporarily simplified for debugging)"""
        return [
            types.Tool(
                name="consultation",
                description="Performs a consultation on a set of files.", # Static description
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Base path for file discovery.", # Static
                        },
                        "pattern": {
                            "type": "string",
                            "description": "Regex pattern to match files.", # Static
                        },
                        "query": {
                            "type": "string",
                            "description": "The query or question for the LLM.", # Static
                        },
                        "model": {
                            "type": "string",
                            "description": "The model to use for consultation.", # Static
                        },
                        # Temporarily commenting out optional exclude_pattern for maximum simplicity
                        # "exclude_pattern": {
                        #    "type": "string",
                        #    "description": "Optional regex pattern to exclude files.", # Static
                        # },
                    },
                    "required": ["path", "pattern", "query", "model"],
                },
            )
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        """Handle tool calls."""
        try:
            if name == "consultation":
                # Prepare keyword arguments from the 'arguments' dict
                tool_kwargs = {
                    "path": arguments["path"],
                    "pattern": arguments["pattern"],
                    "query": arguments["query"],
                    "model": arguments["model"],
                }
                # Only add exclude_pattern if it's actually provided by the client
                if "exclude_pattern" in arguments and arguments["exclude_pattern"] is not None:
                    tool_kwargs["exclude_pattern"] = arguments["exclude_pattern"]

                # Add server-provided arguments, also as keywords
                tool_kwargs["provider"] = server.provider
                tool_kwargs["api_key"] = server.api_key
                tool_kwargs["include_images"] = server.include_images

                # Call consultation_impl using keyword argument unpacking
                result = await consultation_impl(**tool_kwargs)
                return [types.TextContent(type="text", text=result)]
            else:
                return [
                    types.TextContent(type="text", text=f"Error: Unknown tool '{name}'")
                ]
        except Exception as e:
            # Log the full error for debugging
            logger.error(f"Error in {name}: {type(e).__name__}: {str(e)}")

            # Simple error message mapping
            error_str = str(e).lower()
            if any(
                x in error_str
                for x in ["connection", "network", "timeout", "unreachable"]
            ):
                error_msg = "Network error. Please check your internet connection."
            elif any(
                x in error_str for x in ["unauthorized", "401", "403", "invalid api"]
            ):
                error_msg = "Invalid API key. Please check your credentials."
            elif any(x in error_str for x in ["rate limit", "429", "quota"]):
                error_msg = "Rate limit exceeded. Please wait and try again."
            elif "not found" in error_str and "model" in error_str:
                error_msg = "Model not found. Please check the model name."
            elif any(x in error_str for x in ["too large", "exceeds", "context"]):
                error_msg = "Content too large. Try using fewer files or a larger context model."
            else:
                # Return the original error if no mapping
                error_msg = str(e)

            return [types.TextContent(type="text", text=f"Error: {error_msg}")]

    # Show model examples for the provider
    logger.info("Starting Consult7 MCP Server")
    logger.info(f"Provider: {server.provider}")
    logger.info("API Key: Set")

    examples = ToolDescriptions.MODEL_EXAMPLES.get(server.provider, [])
    if examples:
        logger.info(f"Example models for {server.provider}:")
        for example in examples:
            logger.info(f"  - {example}")
        if server.provider == "openai":
            logger.info("  Note: Include context length with | separator")

    # Run test mode if requested
    if test_mode:
        success = await test_api_connection(server)
        sys.exit(EXIT_SUCCESS if success else EXIT_FAILURE)

    # Normal server mode
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="consult7",
                server_version=SERVER_VERSION,
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def run():
    """Entry point for the consult7 command."""
    import asyncio

    asyncio.run(main())


if __name__ == "__main__":
    run()
