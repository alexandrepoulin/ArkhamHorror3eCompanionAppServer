"""Models for socket messages."""

import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass


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
        super().__init__(action="reconnect_reply")
        self.name = name
        self.colour = colour


@dataclass
class Ack(BaseMessage):
    """Class for simple acknowledgements."""

    message: str

    def __init__(self, message: str) -> None:
        super().__init__(action="ack")
        self.message = message


@dataclass
class ErrorReply(BaseMessage):
    """Class for an error reply."""

    message: str

    def __init__(self, message: str) -> None:
        super().__init__(action="error")
        self.message = message


@dataclass
class HelloMessage(BaseMessage):
    """Hello messages will have this structure."""

    game_available: bool
    taken_names: Iterable[str] | None
    taken_colours: Iterable[str] | None

    def __init__(
        self,
        game_available: bool,
        taken_names: Iterable[str] | None = None,
        taken_colours: Iterable[str] | None = None,
    ) -> None:
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

    def __init__(self, game_data: Mapping[str, str], can_undo: bool, can_redo: bool) -> None:
        super().__init__(action="update")
        self.game_data = game_data
        self.can_undo = can_undo
        self.can_redo = can_redo


@dataclass
class ViewerReply(BaseMessage):
    """Class for replies that will show the viewer."""

    cards: Iterable[Mapping[str, str]]

    def __init__(self, cards: Iterable[Mapping[str, str]]) -> None:
        super().__init__(action="viewer_reply")
        self.cards = cards
