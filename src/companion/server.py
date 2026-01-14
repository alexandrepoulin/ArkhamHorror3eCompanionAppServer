"""The service."""

from __future__ import annotations

import asyncio
import json
import ssl
from collections import deque
from copy import deepcopy
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, cast

from bidict import bidict
from structlog import get_logger
from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosedError, WebSocketException
from websockets.http11 import Request

from companion.decks import EmptyDeckError
from companion.game_state import GameState
from companion.message_models import (
    Ack,
    ErrorReply,
    HelloMessage,
    LogMessage,
    ReconnectMessage,
    UpdateMessage,
    ViewerReply,
)
from companion.util_classes import Card, CodexNeighbourhoodCard, GameSettings, Neighbourhood, Scenarios

if TYPE_CHECKING:
    from collections.abc import Mapping
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
        self.connected_clients: set[ServerConnection] = set()
        self.ssl_context = self._create_ssl_context()
        self.players: bidict[ServerConnection, str] = bidict()
        self.player_colours: dict[ServerConnection, str] = {}
        self.game_states: deque[GameState] = deque(maxlen=20)
        self.future_states: list[GameState] = []

    @property
    def game(self) -> GameState:
        """Get the current game state.

        Raises:
            ValueError: raised if there is no game present.

        Returns:
            The current game state.

        """
        if len(self.game_states) >= 1:
            return self.game_states[-1]
        raise ValueError("There are no games")

    @property
    def can_redo(self) -> bool:
        return len(self.future_states) > 0

    @property
    def can_undo(self) -> bool:
        return len(self.game_states) > 1

    def backup_game(self) -> None:
        """Create a backup of the game state to allow for undo and redos."""
        self.game_states.append(deepcopy(self.game_states[-1]))
        self.future_states = []

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

        Returns:
            _description_

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

    async def register(self, websocket: ServerConnection) -> None:
        """Register a client.

        Args:
            websocket: The client to register

        """
        self.connected_clients.add(websocket)
        _logger.info(
            "Client connected", extra={"client": websocket.remote_address, "total": len(self.connected_clients)}
        )

    async def unregister(self, websocket: ServerConnection) -> None:
        """Unregister a client and cleanup the relevant game states.

        Args:
            websocket: The client to unregister.

        """
        self.connected_clients.discard(websocket)
        _logger.info(
            "Client disconnected", extra={"client": websocket.remote_address, "total": len(self.connected_clients)}
        )

        if websocket in self.players:
            await self.send_log("%s has disconnected!", websocket)
            del self.player_colours[websocket]
            del self.players[websocket]

        if len(self.connected_clients) == 0:
            _logger.info("No players left in game, deleted it.")
            self.game_states.clear()
            self.future_states = []
            
        await self.send_hellos()

    async def handle_message(self, message: str, sender: ServerConnection) -> str | None:
        """Decide how to handle a new message from a socket.

        Args:
            message: The message
            sender: The sender

        Returns:
            A message that will be broadcasts or None if that shouldn't happen.

        """
        _logger.info("Message Received", extra={"socket_message": message, "sender": sender})
        try:
            json_message = json.loads(message)
        except ValueError:
            error = json.dumps({"action": "reply", "succeeded": False, "error": "Invalid Json received"})
            await sender.send(json.dumps(error))
            _logger.warning("Returning error message", extra={"socket_message": error, "sender": sender})
            return None
        match json_message["action"]:
            case "start_game":
                await self.start_game(json_message, sender)
            case "connect":
                await self.connect(json_message, sender)
            case "reconnect":
                await self.reconnect(sender)
            case "draw":
                self.backup_game()
                await self.draw(json_message, sender)
                await self.update()
            case "resolve_event":
                self.backup_game()
                await self.resolve_event(json_message, sender)
                await self.update()
            case "view_discard":
                await self.view_discard(sender)
            case "view_codex":
                await self.view_codex(sender)
            case "view_archive":
                await self.view_archive(sender)
            case "add_codex":
                self.backup_game()
                await self.add_codex(json_message, sender)
                await self.update()
            case "flip_codex":
                self.backup_game()
                await self.flip_codex(json_message, sender)
            case "remove_codex":
                self.backup_game()
                await self.remove_codex(json_message, sender)
                await self.update()
            case "view_attached_codex":
                await self.view_attached_codex(json_message, sender)
            case "detach_codex":
                self.backup_game()
                await self.detach_codex(json_message, sender)
                await self.update()
            case "draw_terror":
                self.backup_game()
                await self.draw_terror(json_message, sender)
                await self.update()
            case "add_deck":
                self.backup_game()
                await self.add_deck(json_message, sender)
                await self.update()
            case "spread_clue":
                self.backup_game()
                await self.spread_clue(sender)
                await self.update()
            case "spread_doom":
                self.backup_game()
                await self.spread_doom(sender)
                await self.update()
            case "spread_terror":
                self.backup_game()
                await self.spread_terror(sender)
                await self.update()
            case "gate_burst":
                self.backup_game()
                await self.gate_burst(sender)
                await self.update()
            case "headline":
                self.backup_game()
                await self.headline(sender)
                await self.update()
            case "view_rumor":
                await self.view_rumor(sender)
            case "remove_rumor":
                self.backup_game()
                await self.remove_rumor(sender)
                await self.update()
            case "undo":
                await self.undo(sender)
                await self.update()
            case "redo":
                await self.redo(sender)
                await self.update()
            case _:
                return "error"
        return None

    async def broadcast(self, message: str) -> None:
        """Broadcast message to all non-players

        Args:
            message: The message to broadcast.

        """
        await asyncio.gather(
            *(ws.send(message) for ws in self.connected_clients),
            return_exceptions=True,
        )

    async def broadcast_players(self, message: str) -> None:
        """Broadcast message to all players

        Args:
            message: The message to broadcast.

        """
        await asyncio.gather(
            *(ws.send(message) for ws in self.players.keys()),
            return_exceptions=True,
        )

    async def handler(self, websocket: ServerConnection) -> None:
        """Per-connection handler."""
        await self.register(websocket)
        await self.send_hellos()

        try:
            async for message in websocket:
                try:
                    if TYPE_CHECKING:
                        assert isinstance(message, str)
                    if (reply := await self.handle_message(message, websocket)) is not None:
                        await websocket.send(reply)
                except Exception:
                    raise
                    _logger.exception("Unknown exception handling message.")
        except ConnectionClosedError:
            _logger.exception("Connection Closed Error")
        finally:
            await self.unregister(websocket)

    async def run(self) -> None:
        """Run the server."""
        async with serve(
            handler=self.handler,
            host=self.host,
            port=self.port,
            ssl=self.ssl_context,
            process_request=self.process_request,
        ):
            _logger.info("WebSocket server running on wss://%s:%d/game", self.host, self.port)
            await asyncio.Future()

    async def ack(self, message: str, sender: ServerConnection) -> None:
        """Send Ack messages.

        Args:
            message: the message to send.
            sender: the socket to send it to.

        """
        message = Ack(message=message).as_message()
        await sender.send(message)
        _logger.info("Sent Ack", extra={"message": message})

    async def update(self):
        """Send updates for the ui."""
        message = UpdateMessage(self.game.update_info(), can_redo=self.can_redo, can_undo=self.can_undo).as_message()
        await self.broadcast_players(message)
        _logger.info("Sent update message.", extra={"message": message})

    async def send_log(self, log_message: str, originator: ServerConnection, card: Card | None = None) -> None:
        """Send a log message to everyone.

        Args:
            log_message: The log message. Should contain %s to be replace with the player name.
            originator: The socket that resulted in the log being created.
            card: The relevant card if there is one.

        """
        card_details = None if card is None else card.to_dict(identifier="logging")
        colour = self.player_colours[originator]
        player_name = self.players[originator]

        message = LogMessage(message=log_message % player_name, card=card_details, colour=colour).as_message()

        await self.broadcast_players(message)
        _logger.info("Sent Log message.", extra={"message": message})

    async def send_hellos(self) -> None:
        """Send a hello messages to a player who is connected but not a player.

        Args:
            websocket: A websocket.

        """
        if len(self.game_states) == 0:
            message = HelloMessage(game_available=False).as_message()
        else:
            message = HelloMessage(
                game_available=True,
                taken_names=list(self.players.values()),
                taken_colours=list(self.player_colours.values()),
            ).as_message()
        await self.broadcast(message)
        _logger.info("Sent hello message.", extra={"message": message})

    async def start_game(self, json_message: Mapping[str, str], sender: ServerConnection) -> None:
        """Start a new game.

        Expected input:
        {
            "type": "start_game",
            "scenario": <valid scenario>,
            "expansions": <valid expansion bitflag>
            "player_name": <str>
            "player_colour": <str>
        }

        Args:
            json_message: The message from the socket
            sender: The client that sent the request.

        """
        try:
            settings = GameSettings(
                scenario=Scenarios(json_message["scenario"]), expansions=int(json_message["expansions"])
            )
            self.game_states.append(GameState(settings))
            message = UpdateMessage(self.game.update_info(), can_redo=False, can_undo=False).as_message()
            await sender.send(message)
            self.players[sender] = json_message["player_name"]
            self.player_colours[sender] = json_message["player_colour"]
            _logger.info("Sent start game reply.", extra={"message": message})
            await self.send_hellos()
        except ValueError:
            error_message = ErrorReply("Bad scenario or expansion values.").as_message()
            await sender.send(error_message)
            _logger.info("Sent error reply.", extra={"message": error_message})
            raise

    async def connect(self, json_message: Mapping[str, str], sender: ServerConnection) -> None:
        """Join a game.

        Expected input:
        {
            "player_name": <str>
            "player_colour": <str>
        }

        Args:
            json_message: The message from the socket
            sender: The client that sent the request.

        """
        try:
            if len(self.game_states) == 0:
                error_message = ErrorReply("The game has not been started yet.").as_message()
                await sender.send(error_message)
                _logger.info("Sent error reply.", extra={"message": error_message})
                return
            if json_message["player_name"] in self.players.inv:
                error_message = ErrorReply("That name has already been chosen.").as_message()
                await sender.send(error_message)
                _logger.info("Sent error reply.", extra={"message": error_message})
                return
            if json_message["player_colour"] in self.player_colours.values():
                error_message = ErrorReply("That color has already been chosen.").as_message()
                await sender.send(error_message)
                _logger.info("Sent error reply.", extra={"message": error_message})
                return

            message = UpdateMessage(
                self.game.update_info(), can_redo=self.can_redo, can_undo=self.can_undo
            ).as_message()
            await sender.send(message)
            self.players[sender] = json_message["player_name"]
            self.player_colours[sender] = json_message["player_colour"]
            _logger.info("Sent connect reply.", extra={"message": message})

            await self.send_hellos()
            await self.send_log("%s has joined!", sender)
        except ValueError:
            error_message = ErrorReply("Bad connection message").as_message()
            await sender.send(error_message)
            _logger.info("Sent error reply.", extra={"message": error_message})

    async def reconnect(self, sender: ServerConnection) -> None:
        """Reconnect a player to the game.

        Args:
            json_message: The message from the socket
            sender: The client that sent the request.

        """
        if sender in self.players:
            message = ReconnectMessage(name=self.players[sender], colour=self.player_colours[sender]).as_message()
            await sender.send(message)
            _logger.info("Sent reconnect reply.", extra={"message": message})
            await self.send_log("%s has reconnected!", sender)
            return
        error_message = ErrorReply("Can't Reconnect. Please use the join button.").as_message()
        await sender.send(error_message)
        _logger.info("Sent error reply.", extra={"message": error_message})

    async def draw(self, json_message: Mapping[str, str], sender: ServerConnection) -> None:
        """Draw a card from a neighbourhood deck.

        Expected input:
        {
            "action": "draw",
            "deck": <str>
        }

        Args:
            json_message: The message from the socket
            sender: The client that sent the request.

        """
        try:
            neighbourhood = json_message["deck"]
            card, identifier = self.game.draw_from_neighbourhood(Neighbourhood(neighbourhood))
            message = ViewerReply(
                cards=[card.to_dict(needs_resolving=card.is_event, identifier=identifier, from_deck=True)]
            ).as_message()
            await sender.send(message)
            _logger.info("Sent draw reply.", extra={"message": message})
            await self.send_log(f"%s has drawn from the {neighbourhood} deck: [[Card]]", sender, card)
        except ValueError:
            error_message = ErrorReply("Bad draw message.").as_message()
            await sender.send(error_message)
            _logger.info("Sent error reply.", extra={"message": error_message})

    async def resolve_event(self, json_message: Mapping[str, str | bool], sender: ServerConnection) -> None:
        """Resolve an event from a neighbourhood.

        Expected input:
        {
            "identifier": <str>,
            "passed": bool
        }

        Args:
            json_message: The message from the socket
            sender: The client that sent the request.

        """
        try:
            identifier, passed = cast("str", json_message["identifier"]), cast("bool", json_message["passed"])
            self.game.resolve_temporary_zone(identifier=identifier, passed=passed)
            await self.send_log(f"%s has {'passed' if passed else 'failed'} his event!", sender)
        except ValueError:
            error_message = ErrorReply("Bad resolve event message.").as_message()
            await sender.send(error_message)
            _logger.info("Sent error reply.", extra={"message": error_message})

    async def view_discard(self, sender: ServerConnection) -> None:
        """Handle a request to view the event discard pile.

        Args:
            sender: The client that sent the request.

        """
        message = ViewerReply(cards=[card.to_dict() for card in self.game.event_deck_discard]).as_message()
        await sender.send(message)
        _logger.info("Sent view_discard reply.", extra={"message": message})

    async def view_codex(self, sender: ServerConnection) -> None:
        """Handle a request to view the codex.

        Args:
            sender: The client that sent the request.

        """
        cards = self.game.get_codex()
        message = ViewerReply(cards=cards).as_message()
        await sender.send(message)
        _logger.info("Sent view_codex reply.", extra={"message": message})

    async def view_archive(self, sender: ServerConnection) -> None:
        """Handle a request to view the archive.

        Args:
            sender: The client that sent the request.

        """
        cards = self.game.get_archive()
        message = ViewerReply(cards=cards).as_message()
        await sender.send(message)
        _logger.info("Sent view_archive reply.", extra={"message": message})

    async def add_codex(self, json_message: Mapping[str, int], sender: ServerConnection) -> None:
        """Add a card to the codex.

        Expected input:
        {
            "codex": <int>
        }

        Args:
            json_message: The message from the socket
            sender: The client that sent the request.

        """
        index = json_message["codex"]
        card = self.game.archive_deck[index]
        self.game.add_from_archive(index)

        _logger.info("Added codex card.", extra={"index": index})
        await self.ack("Codex card added!", sender)

        if isinstance(card, CodexNeighbourhoodCard):
            if card.can_attach:
                await self.send_log(
                    f"%s has attached Codex card {index} to the {card.neighbourhood.value} deck.", sender
                )
                await self.update()
            elif card.is_encounter:
                await self.send_log(f"%s has added Codex card {index} to the {card.neighbourhood.value} deck.", sender)
            return
        await self.send_log(f"%s has added card {index} to the codex.", sender)

    async def flip_codex(self, json_message: Mapping[str, int], sender: ServerConnection) -> None:
        """Flip a card in the codex.

        Expected input:
        {
            "codex": <int>
        }

        Args:
            json_message: The message from the socket
            sender: The client that sent the request.

        """
        index = json_message["codex"]
        self.game.codex[index].is_flipped = not self.game.codex[index].is_flipped
        await self.ack("Codex card flipped!", sender)
        await self.send_log(f"%s has flipped Codex card {index}.", sender)
        _logger.info("Sent flip_codex reply.")

    async def remove_codex(self, json_message: Mapping[str, int], sender: ServerConnection) -> None:
        """Remove a card in the codex.

        Expected input:
        {
            "codex": <int>
        }

        Args:
            json_message: The message from the socket
            sender: The client that sent the request.

        """
        try:
            index = json_message["codex"]
            self.game.return_to_archive(index)
            await self.ack("Codex card moved to archive!", sender)
            await self.send_log(f"%s has returned Codex card {index} to the archive.", sender)
            _logger.info("Sent remove_codex reply.")
        except ValueError:
            error_message = ErrorReply("Bad remove codex message.").as_message()
            await sender.send(error_message)
            _logger.info("Sent error reply.", extra={"message": error_message})

    async def detach_codex(self, json_message: Mapping[str, int], sender: ServerConnection) -> None:
        """Detach a codex card from a neighbourhood.

        Expected input:
        {
            "deck": <str>
        }

        Args:
            json_message: The message from the socket
            sender: The client that sent the request.

        """
        neighbourhood = Neighbourhood(json_message["deck"])
        card = self.game.detach_codex_card(neighbourhood)
        if card is None:
            error_message = ErrorReply("No codex card was attached.").as_message()
            await sender.send(error_message)
            _logger.info("Sent error reply.", extra={"message": error_message})
            return
        message = ViewerReply(cards=[card.to_dict(identifier="flippable", from_deck=True)]).as_message()
        await sender.send(message)
        await self.send_log(
            f"%s has detached a Codex card from the {card.neighbourhood.value} deck: [[Card]]", sender, card
        )
        _logger.info("Sent detach_codex reply.")

    async def view_attached_codex(self, json_message: Mapping[str, int], sender: ServerConnection) -> None:
        """View attached codex card from a neighbourhood.

        Expected input:
        {
            "deck": <str>
        }

        Args:
            json_message: The message from the socket
            sender: The client that sent the request.

        """
        neighbourhood = Neighbourhood(json_message["deck"])
        card = self.game.view_codex_card(neighbourhood)
        if card is None:
            error_message = ErrorReply("No codex card was attached.").as_message()
            await sender.send(error_message)
            _logger.info("Sent error reply.", extra={"message": error_message})
            return
        message = ViewerReply(cards=[card.to_dict(from_deck=True)]).as_message()
        await sender.send(message)
        _logger.info("Sent view_codex reply.")

    async def draw_terror(self, json_message: Mapping[str, int], sender: ServerConnection) -> None:
        """Draw a terror card attached to a neighbourhood deck.

        Expected input:
        {
            "deck": <str>
        }

        Args:
            json_message: The message from the socket
            sender: The client that sent the request.

        """
        try:
            neighbourhood = Neighbourhood(json_message["deck"])
            card = self.game.draw_terror_from_neighbourhood(Neighbourhood(neighbourhood))
            message = ViewerReply(cards=[card.to_dict()]).as_message()
            await sender.send(message)
            await self.send_log(f"%s has drawn a terror card the {neighbourhood.value} deck: [[Card]]", sender, card)
            _logger.info("Sent draw_terror reply.")
        except EmptyDeckError:
            error_message = ErrorReply("No Terror cards were attached.").as_message()
            await sender.send(error_message)
            _logger.info("Sent error reply.", extra={"message": error_message})
            return

    async def add_deck(self, json_message: Mapping[str, str], sender: ServerConnection) -> None:
        """Add a neighbourhood deck.

        Expected input:
        {
            "deck": <str>
        }

        Args:
            json_message: The message from the socket
            sender: The client that sent the request.

        """
        neighbourhood = json_message["deck"]
        self.game.add_neighbourhood(Neighbourhood(json_message["deck"]))
        await self.ack("Deck added!", sender)
        await self.send_log(f"%s has added the {neighbourhood} deck to the game!", sender)
        _logger.info("Sent add_deck reply.")

    async def spread_clue(self, sender: ServerConnection) -> None:
        """Spread a clue.

        Args:
            sender: The client that sent the request.

        """
        try:
            card = self.game.spread_clue()
            message = ViewerReply(cards=[card.to_dict()]).as_message()
            await sender.send(message)
            _logger.info("Sent spread clue reply.", extra={"message": message})
            await self.send_log(f"%s has spread a clue to the {card.neighbourhood.value} deck: [[Card]]", sender, card)
        except EmptyDeckError:
            message = ViewerReply(cards=[]).as_message()
            await sender.send(message)
            _logger.info("Sent spread clue reply.", extra={"message": message})
            await self.send_log(
                "%s tried to spread a clue, but the Event deck was empty! Add a doom to the sheet instead.", sender
            )

    async def spread_doom(self, sender: ServerConnection) -> None:
        """Spread doom.

        Args:
            sender: The client that sent the request.

        """
        try:
            card = self.game.spread_doom()
            message = ViewerReply(cards=[card.to_dict()]).as_message()
            await sender.send(message)
            _logger.info("Sent spread doom reply.", extra={"message": message})
            await self.send_log(f"%s has spread doom to the {card.neighbourhood.value} deck: [[Card]]", sender, card)
        except EmptyDeckError:
            message = ViewerReply(cards=[]).as_message()
            await sender.send(message)
            _logger.info("Sent spread clue reply.", extra={"message": message})
            await self.send_log(
                "%s tried to spread doom, but the Event deck was empty! Add a doom to the sheet instead.", sender
            )

    async def spread_terror(self, sender: ServerConnection) -> None:
        """Spread terror.

        Args:
            sender: The client that sent the request.

        """
        try:
            result = self.game.spread_terror()
            await self.ack("Terror Spread!", sender)
            if isinstance(result, Neighbourhood):
                await self.send_log(f"%s has spread terror to the {result.value} deck using the default location.", sender)
            else:
                await self.send_log(f"%s has spread terror to the {result.neighbourhood.value}: [[Card]]", sender, result)
            _logger.info("Successfully spread terror.", extra={"result": result})
        except EmptyDeckError:
            await self.ack("No Terror Cards Remaining!", sender)
            await self.send_log(
                "%s tried to spread terror, but the Terror deck was empty! Add a doom to the sheet instead.", sender
            )

    async def gate_burst(self, sender: ServerConnection) -> None:
        """Resolve a gate burst.

        Args:
            sender: The client that sent the request.

        """
        card = self.game.gate_burst()
        if card is None:
            message = ViewerReply(cards=[]).as_message()
            await sender.send(message)
            await self.send_log(
                "%s tried to gate burst, but the Event deck was empty. Add a doom to the sheet instead.", sender
            )
        else:
            message = ViewerReply(cards=[card.to_dict()]).as_message()
            await sender.send(message)
            await self.send_log(f"%s caused a gate burst in {card.neighbourhood.value}: [[Card]]", sender, card)
        _logger.info("Sent gate burst reply.", extra={"message": message})

    async def headline(self, sender: ServerConnection) -> None:
        """Draw a headline.

        Args:
            sender: The client that sent the request.

        """
        try:
            card = self.game.draw_headline()
            message = ViewerReply(cards=[card.to_dict()]).as_message()
            await sender.send(message)
            cards_remaining = len(self.game.headline_deck)
            await self.send_log(
                f"%s has read a headline. Only {cards_remaining} headlines left: [[Card]]", sender, card
            )
        except EmptyDeckError:
            message = ViewerReply(cards=[]).as_message()
            await sender.send(message)
            await self.send_log(
                "%s tried to read a headline, but the deck was empty. Add a doom to the sheet instead.", sender
            )

        _logger.info("Sent headline reply.", extra={"message": message})

    async def view_rumor(self, sender: ServerConnection) -> None:
        """Draw a headline.

        Args:
            sender: The client that sent the request.

        """
        if self.game.active_rumor != None:
            card = self.game.active_rumor
            message = ViewerReply(cards=[card.to_dict()]).as_message()
            await sender.send(message)
            _logger.info("Successfully view_rumor.")
            return

        error_message = ErrorReply("There were no active rumors!").as_message()
        await sender.send(error_message)
        _logger.info("Sent error reply.", extra={"message": error_message})

    async def remove_rumor(self, sender: ServerConnection) -> None:
        """Draw a headline.

        Args:
            sender: The client that sent the request.

        """
        if self.game.active_rumor != None:
            self.game.active_rumor = None
            await self.ack(message="Removed Rumor!", sender=sender)
            await self.send_log("%s has dismissed the rumor.", sender)
            _logger.info("Successfully remove_rumor.")
            return

        error_message = ErrorReply("There were no active rumors!").as_message()
        await sender.send(error_message)
        _logger.info("Sent error reply.", extra={"message": error_message})

    async def undo(self, sender: ServerConnection) -> None:
        """Handle an undo request.

        Args:
            sender: The client that sent the request.

        """
        if len(self.game_states) <= 1:
            error_message = ErrorReply("Undo is unavailable").as_message()
            await sender.send(error_message)
            _logger.info("Sent error reply.", extra={"message": error_message})

        cur_states = deepcopy(self.game_states)
        cur_futures = deepcopy(self.future_states)

        state = self.game_states.pop()
        if state.is_stable():
            self.future_states.append(state)
        try:
            while not self.game_states[-1].is_stable():
                self.game_states.pop()
            await self.ack("Undo successful!", sender)
            await self.send_log("%s has pressed the undo Button!", sender)
        except IndexError:
            error_message = ErrorReply("There were no good states to backup to!").as_message()
            await sender.send(error_message)
            _logger.info("Sent error reply.", extra={"message": error_message})
            self.game_states=cur_states
            self.future_states = cur_futures

        

    async def redo(self, sender: ServerConnection) -> None:
        """Handle an redo request.

        Args:
            sender: The client that sent the request.

        """
        if len(self.future_states) == 0:
            error_message = ErrorReply("Redo is unavailable").as_message()
            await sender.send(error_message)
            _logger.info("Sent error reply.", extra={"message": error_message})
        self.game_states.append(self.future_states.pop(0))
        await self.ack("Redo successful!", sender)
        await self.send_log("%s has pressed the redo Button!", sender)
