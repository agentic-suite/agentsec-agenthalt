"""agenthalt — the universal agent kill-switch.

One command composes a stop across the process tree, credentials, MCP gateway and sandbox,
preserves a hash-chained evidence snapshot, and returns a proof that the stop happened.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0.dev0"
