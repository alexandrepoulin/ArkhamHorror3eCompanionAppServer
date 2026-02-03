"""The message handler responsible for processing a new message."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, cast

from bidict import bidict
from structlog import get_logger
from websockets.exceptions import ConnectionClosedError

from companion.decks import EmptyDeckError
from companion.game_state import GameState
from companion.message_models import (
    Ack,
    AllLogMessage,
    Boot,
    ErrorReply,
    HelloMessage,
    LogMessage,
    ReconnectMessage,
    UpdateMessage,
    ViewerReply,
)
from companion.util_classes import (
    Card,
    CardViewState,
    CodexNeighbourhoodCard,
    Commands,
    GameSettings,
    Neighbourhood,
    Scenarios,
    get_expansion_text,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Mapping
    from logging import Logger

    from websockets.asyncio.server import ServerConnection

_logger: Logger = get_logger(__name__)


class MessageHandler:
    """A handler for messages from the server to control games."""

    def __init__(self) -> None:
        """Initialize the message handler."""
        self.connected_clients: set[ServerConnection] = set()
        self.players: bidict[ServerConnection, str] = bidict()
        self.player_colours: dict[ServerConnection, str] = {}
        self.game_states: GameState | None = None
        self.game_logs: list[LogMessage] = []

    @property
    def game(self) -> GameState:
        """Get the current game state.

        Raises:
            ValueError: raised if there is no game present.

        Returns:
            The current game state.

        """
        if self.game_states is not None:
            return self.game_states
        raise ValueError("There are no games")

    ## --------------------------------
    ## Connection handling
    ## --------------------------------
    async def handler(self, websocket: ServerConnection) -> None:
        """Per-connection handler."""
        await self.register(websocket)

        try:
            async for message in websocket:
                try:
                    if TYPE_CHECKING:
                        assert isinstance(message, str)
                    if (reply := await self.handle_message(message, websocket)) is not None:
                        await websocket.send(reply)
                except Exception:
                    _logger.exception("Unknown exception handling message.")
        except ConnectionClosedError:
            _logger.exception("Connection Closed Error")
        finally:
            await self.unregister(websocket)

    async def register(self, websocket: ServerConnection) -> None:
        """Register a client.

        Args:
            websocket: The client to register

        """
        self.connected_clients.add(websocket)
        _logger.info(
            "Client connected", extra={"client": websocket.remote_address, "total": len(self.connected_clients)}
        )
        await self.send_hellos()

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
            self.game_states = None
            self.future_states = []
            self.game_logs = []

        await self.send_hellos()

    ## --------------------------------
    ## Sending out messages
    ## --------------------------------

    async def broadcast(self, message: str) -> None:
        """Broadcast message to all non-players.

        Args:
            message: The message to broadcast.

        """
        await asyncio.gather(
            *(ws.send(message) for ws in self.connected_clients),
            return_exceptions=True,
        )

    async def broadcast_players(self, message: str) -> None:
        """Broadcast message to all players.

        Args:
            message: The message to broadcast.

        """
        await asyncio.gather(
            *(ws.send(message) for ws in self.players),
            return_exceptions=True,
        )

    ## --------------------------------
    ## Common simple messages
    ## --------------------------------

    async def ack(self, message: str, sender: ServerConnection) -> None:
        """Send Ack messages.

        Args:
            message: the message to send.
            sender: the socket to send it to.

        """
        message = Ack(message=message).as_message()
        await sender.send(message)
        _logger.info("Sent Ack", extra={"socket_message": message})

    async def error(self, message: str, sender: ServerConnection) -> None:
        """Send Error messages.

        Args:
            message: the message to send.
            sender: the socket to send it to.

        """
        message = ErrorReply(message=message).as_message()
        await sender.send(message)
        _logger.info("Sent Error Message", extra={"socket_message": message})

    async def update(self) -> None:
        """Send updates for the ui."""
        tasks: list[Awaitable[None]] = []
        for player in self.players:
            message = UpdateMessage(
                game_data=self.game.update_info(),
                can_redo=self.game.can_redo(player),
                can_undo=self.game.can_undo(player),
            ).as_message()
            tasks.append(player.send(message))
        await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )
        _logger.info("Sent update message.", extra={"socket_message": self.game.update_info()})

    async def send_log(self, log_message: str, originator: ServerConnection, card: Card | None = None) -> None:
        """Send a log message to everyone.

        Args:
            log_message: The log message. Should contain %s to be replace with the player name.
            originator: The socket that resulted in the log being created.
            card: The relevant card if there is one.

        """
        card_details = None if card is None else card.to_dict()
        colour = self.player_colours[originator]
        player_name = self.players[originator]
        log_message_instance = LogMessage(message=log_message % player_name, card=card_details, colour=colour)
        message = log_message_instance.as_message()
        self.game_logs.insert(0, log_message_instance)
        await self.broadcast_players(message)
        _logger.info("Sent Log message.", extra={"socket_message": message})

    async def send_hellos(self) -> None:
        """Send a hello messages to a player who is connected but not a player.

        Args:
            websocket: A websocket.

        """
        if self.game_states is not None:
            message = HelloMessage(game_available=False).as_message()
        else:
            message = HelloMessage(
                game_available=True,
                taken_names=list(self.players.values()),
                taken_colours=list(self.player_colours.values()),
            ).as_message()
        await self.broadcast(message)
        _logger.info("Sent hello message.", extra={"socket_message": message})

    ## --------------------------------
    ## Main splitter for the action
    ## --------------------------------

    async def handle_message(self, message: str, sender: ServerConnection) -> None:
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
            await self.error("Invalid Json received", sender)
            return
        try:
            action = Commands(json_message["action"])
            await getattr(self, action.value)(json_message, sender)
        except ValueError:
            await self.error("Invalid Command received", sender)
        except AttributeError:
            await self.error("Command not implemented!", sender)

    ## --------------------------------
    ## Functions for each action
    ## --------------------------------

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
            self.game_states = GameState(settings)
            await self.broadcast_players(Boot().as_message())
            self.players.clear()
            self.player_colours.clear()
            self.game_logs.clear()
            message = UpdateMessage(game_data=self.game.update_info(), can_redo=False, can_undo=False).as_message()

            await sender.send(message)
            self.players[sender] = json_message["player_name"]
            self.player_colours[sender] = json_message["player_colour"]
            _logger.info("Sent start game reply.", extra={"socket_message": message})
            await self.send_hellos()
            await self.send_log(
                f"%s Started the Game! Scenario: {json_message['scenario']}; "
                f"Expansion(s): {get_expansion_text(int(json_message['expansions']))}",
                sender,
            )
        except ValueError:
            await self.error("Bad scenario or expansion values.", sender)

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
            if self.game_states is not None:
                await self.error("The game has not been started yet.", sender)
                return
            if json_message["player_name"] in self.players.inv:
                await self.error("That name has already been chosen.", sender)
                return
            if json_message["player_colour"] in self.player_colours.values():
                await self.error("That color has already been chosen.", sender)
                return

            message = UpdateMessage(game_data=self.game.update_info(), can_redo=False, can_undo=False).as_message()
            await sender.send(message)
            self.players[sender] = json_message["player_name"]
            self.player_colours[sender] = json_message["player_colour"]
            _logger.info("Sent connect reply.", extra={"socket_message": message})
            await sender.send(AllLogMessage(self.game_logs).as_message())

            await self.send_hellos()
            await self.send_log("%s has joined!", sender)
        except ValueError:
            await self.error("Bad connection message", sender)

    async def reconnect(self, _: Mapping[str, str], sender: ServerConnection) -> None:
        """Reconnect a player to the game.

        Args:
            json_message: The message from the socket
            sender: The client that sent the request.

        """
        if sender in self.players:
            message = ReconnectMessage(name=self.players[sender], colour=self.player_colours[sender]).as_message()
            await sender.send(message)
            _logger.info("Sent reconnect reply.", extra={"socket_message": message})
            await self.send_log("%s has reconnected!", sender)
            return
        await self.error("Can't Reconnect. Please use the join button.", sender)

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
            card, identifier = self.game.draw_from_neighbourhood(Neighbourhood(neighbourhood), sender)
            state = CardViewState.EVENT if card.is_event else CardViewState.FACE_BACK
            message = ViewerReply(cards=[card.to_dict(state=state, identifier=identifier)]).as_message()
            await sender.send(message)
            _logger.info("Sent draw reply.", extra={"socket_message": message})
            await self.send_log(f"%s has drawn from the {neighbourhood} deck: View Card", sender, card)
            await self.update()
        except ValueError:
            await self.error("Bad draw message.", sender)

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
            self.game.resolve_temporary_zone(identifier=identifier, passed=passed, sender=sender)
            await self.send_log(f"%s has {'passed' if passed else 'failed'} his event!", sender)
            await self.update()
        except ValueError:
            await self.error("Bad resolve event message.", sender)

    async def view_discard(self, _: Mapping[str, str], sender: ServerConnection) -> None:
        """Handle a request to view the event discard pile.

        Args:
            sender: The client that sent the request.

        """
        message = ViewerReply(trigger="view_discard", cards=[card.to_dict() for card in self.game.discard]).as_message()
        await sender.send(message)
        _logger.info("Sent view_discard reply.", extra={"socket_message": message})

    async def view_codex(self, _: Mapping[str, str], sender: ServerConnection) -> None:
        """Handle a request to view the codex.

        Args:
            sender: The client that sent the request.

        """
        cards = self.game.get_codex()
        message = ViewerReply(trigger="view_codex", cards=cards).as_message()
        await sender.send(message)
        _logger.info("Sent view_codex reply.", extra={"socket_message": message})

    async def view_archive(self, _: Mapping[str, str], sender: ServerConnection) -> None:
        """Handle a request to view the archive.

        Args:
            sender: The client that sent the request.

        """
        cards = self.game.get_archive()
        message = ViewerReply(trigger="view_archive", cards=cards).as_message()
        await sender.send(message)
        _logger.info("Sent view_archive reply.", extra={"socket_message": message})

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
        try:
            index = json_message["codex"]
            card = self.game.archive[index]
            self.game.add_from_archive(index, sender)
        except KeyError:
            await self.error("Card already in Codex", sender)
            return

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
        else:
            await self.send_log(f"%s has added card {index} to the codex.", sender)
        await self.update()

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
        try:
            card = self.game.flip_codex(index, sender)
            await self.ack("Codex card flipped!", sender)
            await self.send_log(f"%s has flipped Codex card {index}. View Card", sender, card)
            _logger.info("Sent flip_codex reply.")
            await self.update()
        except ValueError:
            await self.error("Can't find card to flip!", sender)

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
            self.game.return_to_archive(index, sender)
            await self.ack("Codex card moved to archive!", sender)
            await self.send_log(f"%s has returned Codex card {index} to the archive.", sender)
            _logger.info("Sent remove_codex reply.")
            await self.update()
        except ValueError:
            await self.error("Bad remove codex message.", sender)

    async def view_attached_codex(self, json_message: Mapping[str, str], sender: ServerConnection) -> None:
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
            message = ViewerReply(trigger="view_attached_codex", deck=json_message["deck"], cards=[]).as_message()
        else:
            state = CardViewState.UN_FLIPPED_CODEX if not card.is_flipped else CardViewState.FLIPPED_CODEX
            message = ViewerReply(
                trigger="view_attached_codex", deck=json_message["deck"], cards=[card.to_dict(state=state)]
            ).as_message()
        await sender.send(message)
        _logger.info("Sent view_codex reply.")

    async def add_counter_codex(self, json_message: Mapping[str, int], sender: ServerConnection) -> None:
        """Add a counter to a codex card.

        {
            "codex": <int>
        }

        Args:
            json_message: The message from the socket
            sender: The client that sent the request.

        """
        try:
            self.game.modify_counter_on_codex(json_message["codex"], 1, sender)
            await self.ack("Counter Added", sender)
            await self.update()
        except ValueError:
            await self.error("Invalid codex card number!", sender)

    async def remove_counter_codex(self, json_message: Mapping[str, int], sender: ServerConnection) -> None:
        """Remove a counter to a codex card.

        {
            "codex": <int>
        }

        Args:
            json_message: The message from the socket
            sender: The client that sent the request.

        """
        try:
            self.game.modify_counter_on_codex(json_message["codex"], -1, sender)
            await self.ack("Counter Removed", sender)
            await self.update()
        except ValueError:
            await self.error("Invalid codex card number!", sender)

    async def draw_terror(self, json_message: Mapping[str, str], sender: ServerConnection) -> None:
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
            card = self.game.draw_terror_from_neighbourhood(Neighbourhood(neighbourhood), sender)
            message = ViewerReply(cards=[card.to_dict()]).as_message()
            await sender.send(message)
            await self.send_log(f"%s has drawn a terror card the {neighbourhood.value} deck: View Card", sender, card)
            _logger.info("Sent draw_terror reply.")
            await self.update()
        except EmptyDeckError:
            await self.error("No Terror cards were attached.", sender)

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
        doom_to_add = self.game.add_neighbourhood(Neighbourhood(json_message["deck"]), sender)
        if doom_to_add == 0:
            await self.ack("Deck added!", sender)
            await self.send_log(f"%s has added the {neighbourhood} deck to the game!", sender)
        else:
            await self.ack("Deck added! Add {doom_to_add} doom tokens to the scenario sheet.", sender)
            await self.send_log(
                f"%s has added the {neighbourhood} deck to the game and "
                f"added {doom_to_add} doom tokens to the scenario sheet!",
                sender,
            )
        _logger.info("Sent add_deck reply.")
        await self.update()

    async def spread_clue(self, _: Mapping[str, str], sender: ServerConnection) -> None:
        """Spread a clue.

        Args:
            sender: The client that sent the request.

        """
        try:
            card = self.game.spread_clue(sender)
            message = ViewerReply(cards=[card.to_dict(state=CardViewState.BACK_FACE)]).as_message()
            await sender.send(message)
            _logger.info("Sent spread clue reply.", extra={"socket_message": message})
            await self.send_log(f"%s has spread a clue to the {card.neighbourhood.value} deck: View Card", sender, card)
        except EmptyDeckError:
            message = ViewerReply(cards=[]).as_message()
            await sender.send(message)
            _logger.info("Sent spread clue reply.", extra={"socket_message": message})
            await self.send_log(
                "%s tried to spread a clue, but the Event deck was empty! Add a doom to the sheet instead.", sender
            )
        await self.update()

    async def spread_doom(self, _: Mapping[str, str], sender: ServerConnection) -> None:
        """Spread doom.

        Args:
            sender: The client that sent the request.

        """
        try:
            card = self.game.spread_doom(sender)
            message = ViewerReply(cards=[card.to_dict()]).as_message()
            await sender.send(message)
            _logger.info("Sent spread doom reply.", extra={"socket_message": message})
            await self.send_log(f"%s has spread doom to the {card.neighbourhood.value} deck: View Card", sender, card)
        except EmptyDeckError:
            message = ViewerReply(cards=[]).as_message()
            await sender.send(message)
            _logger.info("Sent spread clue reply.", extra={"socket_message": message})
            await self.send_log(
                "%s tried to spread doom, but the Event deck was empty! Add a doom to the sheet instead.", sender
            )
        await self.update()

    async def spread_terror(self, _: Mapping[str, str], sender: ServerConnection) -> None:
        """Spread terror.

        Args:
            sender: The client that sent the request.

        """
        try:
            result = self.game.spread_terror(sender)
            await self.ack("Terror Spread!", sender)
            if isinstance(result, Neighbourhood):
                await self.send_log(
                    f"%s has spread terror to the {result.value} deck using the default location.", sender
                )
            else:
                await self.send_log(
                    f"%s has spread terror to the {result.neighbourhood.value}: View Card", sender, result
                )
            _logger.info("Successfully spread terror.", extra={"result": result})
            await self.update()
        except EmptyDeckError:
            await self.ack("No Terror Cards Remaining!", sender)
            await self.send_log(
                "%s tried to spread terror, but the Terror deck was empty! Add a doom to the sheet instead.", sender
            )

    async def place_terror(self, json_message: Mapping[str, str], sender: ServerConnection) -> None:
        """Place a terror card in a specific neighbourhood.

        Expected input:
        {
            "deck": <str>
        }

        Args:
            json_message: The message from the socket
            sender: The client that sent the request.

        Args:
            json_message: _description_
            sender: _description_

        """
        try:
            neighbourhood = json_message["deck"]
            result = self.game.place_terror(Neighbourhood(neighbourhood), sender)
            await self.ack("Terror Spread!", sender)
            await self.send_log(f"%s has spread terror to the {neighbourhood} neighbourhood!", sender)
            _logger.info("Successfully spread terror.", extra={"result": result})
            await self.update()
        except EmptyDeckError:
            await self.ack("No Terror Cards Remaining!", sender)
            await self.send_log(
                "%s tried to spread terror, but the Terror deck was empty! Add a doom to the sheet instead.", sender
            )

    async def gate_burst(self, _: Mapping[str, str], sender: ServerConnection) -> None:
        """Resolve a gate burst.

        Args:
            sender: The client that sent the request.

        """
        card = self.game.gate_burst(sender)
        if card is None:
            message = ViewerReply(cards=[]).as_message()
            await sender.send(message)
            await self.send_log(
                "%s tried to gate burst, but the Event deck was empty. Add a doom to the sheet instead.", sender
            )
        else:
            message = ViewerReply(cards=[card.to_dict(state=CardViewState.BACK_FACE)]).as_message()
            await sender.send(message)
            await self.send_log(f"%s caused a gate burst in {card.neighbourhood.value}: View Card", sender, card)
        _logger.info("Sent gate burst reply.", extra={"socket_message": message})
        await self.update()

    async def headline(self, _: Mapping[str, str], sender: ServerConnection) -> None:
        """Draw a headline.

        Args:
            sender: The client that sent the request.

        """
        try:
            card = self.game.draw_headline(sender)
            message = ViewerReply(cards=[card.to_dict()]).as_message()
            await sender.send(message)
            cards_remaining = len(self.game.headline)
            await self.send_log(
                f"%s has read a headline. Only {cards_remaining} headlines left: View Card", sender, card
            )
            await self.update()
        except EmptyDeckError:
            message = ViewerReply(cards=[]).as_message()
            await sender.send(message)
            await self.send_log(
                "%s tried to read a headline, but the deck was empty. Add a doom to the sheet instead.", sender
            )

        _logger.info("Sent headline reply.", extra={"socket_message": message})

    async def view_rumor(self, _: Mapping[str, str], sender: ServerConnection) -> None:
        """Draw a headline.

        Args:
            sender: The client that sent the request.

        """
        if len(self.game.rumor) > 0:
            card = self.game.rumor[0]
            message = ViewerReply(trigger="view_rumor", cards=[card.to_dict(state=CardViewState.RUMOR)]).as_message()
            await sender.send(message)
            _logger.info("Successfully view_rumor.")
            return

        await self.error("There were no active rumors!", sender)

    async def remove_rumor(self, _: Mapping[str, str], sender: ServerConnection) -> None:
        """Draw a headline.

        Args:
            sender: The client that sent the request.

        """
        if len(self.game.rumor) == 0:
            await self.error("There were no active rumors!", sender)
            return
        self.game.clear_rumor(sender)
        await self.ack(message="Removed Rumor!", sender=sender)
        await self.send_log("%s has dismissed the rumor.", sender)
        _logger.info("Successfully remove_rumor.")
        await self.update()

    async def add_counter_rumor(self, _: Mapping[str, str], sender: ServerConnection) -> None:
        """Add a counter to a codex card.

        Args:
            sender: The client that sent the request.

        """
        if len(self.game.rumor) == 0:
            await self.error("No active rumor!", sender)
            return
        self.game.modify_counter_on_rumor(1, sender)
        await self.ack("Counter Added", sender)
        await self.send_log("%s added a counter to the rumor.", sender)
        await self.update()

    async def remove_counter_rumor(self, _: Mapping[str, str], sender: ServerConnection) -> None:
        """Remove a counter to a codex card.

        Args:
            sender: The client that sent the request.

        """
        if len(self.game.rumor) == 0:
            await self.error("No active rumor!", sender)
            return
        if self.game.rumor[0].counters == 0:
            await self.error("No counters to remove!", sender)
            return
        self.game.modify_counter_on_rumor(-1, sender)
        await self.ack("Counter Removed", sender)
        await self.send_log("%s removed a counter to the rumor.", sender)
        await self.update()

    async def undo(self, _: Mapping[str, str], sender: ServerConnection) -> None:
        """Handle an undo request.

        Args:
            sender: The client that sent the request.

        """
        try:
            self.game.undo(sender)
            await self.ack("Undo successful!", sender)
            await self.send_log("%s has pressed the undo Button!", sender)
            await self.update()
        except ValueError:
            await self.error("Unable to undo!", sender)

    async def redo(self, _: Mapping[str, str], sender: ServerConnection) -> None:
        """Handle an redo request.

        Args:
            sender: The client that sent the request.

        """
        try:
            self.game.redo(sender)
            await self.ack("Undo successful!", sender)
            await self.send_log("%s has pressed the redo Button!", sender)
            await self.update()
        except ValueError:
            await self.error("Unable to redo!", sender)
