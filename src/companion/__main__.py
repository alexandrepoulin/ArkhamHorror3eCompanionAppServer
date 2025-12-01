"""Main class."""

from __future__ import annotations

import sys

import uvicorn


def main() -> None:
    """Execute the main function."""
    uvicorn.run(
        "companion.service:app",
        host="0.0.0.0",  # noqa: S104
        port=8080,
        reload=True,  # Dev mode auto-reload
        log_level="info",
    )


if __name__ == "__main__":
    sys.exit(main())
