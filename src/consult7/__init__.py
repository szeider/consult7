"""Consult7 - MCP server for consulting large context window models.

The only supported interface is the MCP `consultation` tool. Nothing in this
package is a public Python API: `consultation_impl` and the provider classes are
internal, and their signatures and return formats change between releases
without notice. Scripts should not import them. Batch work belongs to the
calling agent: one tool call per item, several in parallel, with `output_file`
so only the footer comes back.
"""

from .constants import SERVER_VERSION as __version__
from .server import main

__all__ = ["main", "__version__"]
