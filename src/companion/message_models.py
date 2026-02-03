"""Models for socket messages."""

import json
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


@dataclass
class BaseMessage:
    """Every socket message should follow this base."""

    action: str

    def as_message(self) -> str:
        """Transform the instance into a message for the socket.

        Returns:
            The socket message.

        """
        return json.dumps(asdict(self))


@dataclass
class ReconnectMessage(BaseMessage):
    """Class for reconnection requests."""

    name: str
    colour: str

    def __init__(self, name: str, colour: str) -> None:
        """Initialize the class.

        Args:
            name: The player name.
            colour: The player colour.

        """
        super().__init__(action="reconnect_reply")
        self.name = name
        self.colour = colour


@dataclass
class Ack(BaseMessage):
    """Class for simple acknowledgements."""

    message: str

    def __init__(self, message: str) -> None:
        """Initialize the class.

        Args:
            message: The message added to the ack.

        """
        super().__init__(action="ack")
        self.message = message


@dataclass
class ErrorReply(BaseMessage):
    """Class for an error reply."""

    message: str

    def __init__(self, message: str) -> None:
        """Initialize the class.

        Args:
            message: The message added to the error.

        """
        super().__init__(action="error")
        self.message = message


@dataclass
class Boot(BaseMessage):
    """Class for a message booting a player."""

    def __init__(self) -> None:
        """Initialize the class."""
        super().__init__(action="boot")


@dataclass
class AllLogMessage(BaseMessage):
    """Log messages will have this structure."""

    logs: list[dict[str, Any]]

    def __init__(self, logs: list[LogMessage]) -> None:
        """Initialize the class.

        Args:
            logs: All the log messages from a game.

        """
        super().__init__(action="all_logs")
        self.logs = [asdict(message) for message in logs]


@dataclass
class HelloMessage(BaseMessage):
    """Hello messages will have this structure."""

    game_available: bool
    taken_names: Iterable[str] | None
    taken_colours: Iterable[str] | None

    def __init__(
        self,
        *,
        game_available: bool,
        taken_names: Iterable[str] | None = None,
        taken_colours: Iterable[str] | None = None,
    ) -> None:
        """Initialize the class.

        Args:
            game_available: Whether a game exists.
            taken_names: Names that will be unavailable to be used. Defaults to None.
            taken_colours: Colours that will be unavailable to be used. Defaults to None.

        """
        super().__init__(action="hello")
        self.game_available = game_available
        self.taken_names = taken_names
        self.taken_colours = taken_colours


@dataclass
class LogMessage(BaseMessage):
    """Log messages will have this structure."""

    message: str
    card: Mapping[str, str] | None
    colour: str

    def __init__(self, message: str, card: Mapping[str, str] | None, colour: str) -> None:
        """Initialize the class.

        Args:
            message: The log message.
            card: Any related cards.
            colour: The colour to display the log with.

        """
        super().__init__(action="log")
        self.message = message
        self.card = card
        self.colour = colour


@dataclass
class UpdateMessage(BaseMessage):
    """Hello messages will have this structure."""

    game_data: Mapping[str, str] | None
    can_undo: bool
    can_redo: bool

    def __init__(self, *, game_data: Mapping[str, str], can_undo: bool, can_redo: bool) -> None:
        """Initialize the class.

        Args:
            game_data: The game data.
            can_undo: Whether or not the player can undo.
            can_redo: Whether or not the player can redo.

        """
        super().__init__(action="update")
        self.game_data = game_data
        self.can_undo = can_undo
        self.can_redo = can_redo


@dataclass
class ViewerReply(BaseMessage):
    """Class for replies that will show the viewer."""

    cards: Iterable[Mapping[str, str]]
    trigger: str | None
    deck: str | None

    def __init__(self, cards: Iterable[Mapping[str, str]], trigger: str | None = None, deck: str | None = None) -> None:
        """Initialize the class.

        Args:
            cards: The cards for viewing.
            trigger: What the triggering call was. Defaults to None.
            deck: Any decks used in the triggering call. Defaults to None.

        """
        super().__init__(action="viewer_reply")
        self.trigger = trigger
        self.cards = cards
        self.deck = deck
