"""The server responsible for handling the incoming and outgoing connections."""

from __future__ import annotations

import asyncio
import ssl
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING

from structlog import get_logger
from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import WebSocketException
from websockets.http11 import Request

from companion.message_handler import MessageHandler

if TYPE_CHECKING:
    from logging import Logger

_logger: Logger = get_logger(__name__)


class SecureWebSocketServer:
    """A websocket server to control games."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8081) -> None:  # noqa: S104
        """Initialize the server.

        Args:
            host: The host to use. Defaults to "0.0.0.0".
            port: The port to use. Defaults to 8081.

        """
        self.host = host
        self.port = port
        self.ssl_context = self._create_ssl_context()
        self.message_handler = MessageHandler()

    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context for wss:// connections.

        Returns:
            The ssl context.

        """
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

        # Load your certificate and private key
        # TO DO: generate this using
        # openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -sha256 -days 365 -nodes
        cert_path = Path("/app/cert.pem")
        key_path = Path("/app/key.pem")

        # cert_path = Path("/home/alex/projects/companion/nogit/cert.pem")
        # key_path = Path("/home/alex/projects/companion/nogit/key.pem")

        # ssl_context.set_ciphers("DEFAULT@SECLEVEL=1")

        ssl_context.load_cert_chain(cert_path, key_path)
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context

    async def process_request(self, _: ServerConnection, request: Request) -> None:
        """Validate WebSocket upgrade request before accepting.

        Args:
            path: The path indicated in the request.
            headers: The headers for the request.

        Raises:
            WebSocketException: Raised if the request was invalid.

        """
        if request.path != "/game":
            raise WebSocketException(HTTPStatus.NOT_FOUND)

        headers = request.headers

        # Ensure required WebSocket headers
        if headers.get("Upgrade", "") != "websocket":
            raise WebSocketException(HTTPStatus.BAD_REQUEST)
        if headers.get("Connection", "") != "Upgrade":
            raise WebSocketException(HTTPStatus.BAD_REQUEST)
        if headers.get("Sec-WebSocket-Key") is None:
            raise WebSocketException(HTTPStatus.BAD_REQUEST)
        if headers.get("Sec-WebSocket-Version") != "13":
            raise WebSocketException(HTTPStatus.BAD_REQUEST)

        _logger.info("WebSocket upgrade accepted", extra={"path": request.path})

    async def run(self) -> None:
        """Run the server."""
        async with serve(
            handler=self.message_handler.handler,
            host=self.host,
            port=self.port,
            ssl=self.ssl_context,
            process_request=self.process_request,
        ):
            _logger.info("WebSocket server running on wss://%s:%d/game", self.host, self.port)
            await asyncio.Future()
