"""Main class."""

from __future__ import annotations

import asyncio
import sys

from companion.logger import setup_logging
from companion.server import SecureWebSocketServer


async def async_main() -> None:
    """Execute the main function."""
    setup_logging()
    server = SecureWebSocketServer()
    await server.run()


def main() -> None:
    """Run the app."""
    asyncio.run(async_main())


if __name__ == "__main__":
    sys.exit(main())
