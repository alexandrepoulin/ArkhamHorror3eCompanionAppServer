"""Definitions of how decks work."""

from __future__ import annotations

import secrets
from collections import defaultdict
from copy import deepcopy
from typing import TYPE_CHECKING, Literal, Self, SupportsIndex, overload

from companion.util_classes import (
    Card,
    CodexCard,
    CodexNeighbourhoodCard,
    DeckLabel,
    HeadlineCard,
    Label,
    Neighbourhood,
    NeighbourhoodCard,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, MutableSequence

    from websockets.asyncio.server import ServerConnection


def secure_shuffle[T: Card](deck: MutableSequence[T]) -> None:
    """Shuffle a mutable sequence in place using cryptographically secure randomness (Fisher-Yates).

    Args:
        deck: The deck to shuffle.

    """
    for index in range(len(deck) - 1, 0, -1):
        swap = secrets.randbelow(index + 1)
        deck[index], deck[swap] = deck[swap], deck[index]


class EmptyDeckError(Exception):
    """Raised when a deck is empty."""


class DeckBase[T: Card](list[T]):
    """Basic deck."""

    def __init__(self, deck: list[T]) -> None:
        """Initialize class.

        Args:
            deck: The list of cards.

        """
        super().__init__(deck)

    def shuffle(self) -> None:
        """Shuffle the deck."""
        secure_shuffle(self)

    def draw(self, *, from_top: bool = True) -> T:
        """Return the a card from either the top or bottom.

        The top card is the last element of the list.

        Args:
            from_top: Whether to draw from the top or bottom.

        """
        try:
            if from_top:
                return self.pop()
            return self.pop(0)
        except IndexError as e:
            raise EmptyDeckError from e

    def bottom(self, card: T) -> None:
        """Put a card back on the bottom of the deck which is the 0th element of the list.

        Args:
            card: the card to put to the bottom.

        """
        self.insert(0, card)

    def top(self, card: T) -> None:
        """Put a card on top of the deck which is the 0th element of the list.

        Args:
            card: the card to put on top.

        """
        self.append(card)

    def shuffle_into_top_three(self, card: T) -> None:
        """Shuffle a new card into the top 3 cards of the deck.

        Args:
            card: the card to shuffle in.

        """
        top_3 = [self.pop(), self.pop(), card]
        secure_shuffle(top_3)
        self.extend(top_3)

    @overload
    def __getitem__(self, index: SupportsIndex) -> T: ...
    @overload
    def __getitem__(self, index: slice) -> Self: ...

    def __getitem__(self, index: SupportsIndex | slice) -> T | Self:
        """Override the [] operation."""
        if isinstance(index, slice):
            return type(self)(deck=super().__getitem__(index), **vars(self))
        return super().__getitem__(index)


class Deck[T: Card](DeckBase[T]):
    """A deck with the same card back for every card."""

    def __init__(self, deck: list[T], card_back: str) -> None:
        """Initialize class.

        Args:
            deck: The list of cards.
            card_back: The card back to use for the deck.

        """
        super().__init__(deck)
        self.card_back = card_back


class NeighbourhoodDeck(Deck[NeighbourhoodCard]):
    """A deck for a neighbourhood."""

    def __init__(self, deck: list[NeighbourhoodCard], card_back: str) -> None:
        """Initialize class.

        Args:
            deck: The list of cards
            card_back: The card back to use for the deck.

        """
        super().__init__(deck=deck, card_back=card_back)
        self.attached_terror: DeckBase[Card] = DeckBase(deck=[])
        self.attached_codex: CodexNeighbourhoodCard | None = None

    def has_codex(self, number: int) -> bool:
        """Check to see if this deck has a specific codex card attached.

        Args:
            number: The codex card number.

        Returns:
            Results of the check.

        """
        return self.attached_codex is not None and self.attached_codex.number == number

    def add_terror(self, card: Card) -> None:
        """Attach a terror card to the deck.

        Args:
            card: The terror card.

        """
        self.attached_terror.top(card)

    def get_codex_card(self) -> CodexNeighbourhoodCard:
        """Get the attached codex card.

        Raises:
            ValueError: There are no attached codex cards.

        Returns:
            The card.

        """
        if self.attached_codex is None:
            raise ValueError
        return self.attached_codex

    def attach_codex_card(self, card: CodexNeighbourhoodCard) -> None:
        """Attach a codex card to the deck.

        Args:
            card: The codex card.

        Raises:
            ValueError: raised if there is already a codex card attached.

        """
        if self.attached_codex is not None:
            raise ValueError("Codex card already present.")
        self.attached_codex = card

    def pop_codex_card(self) -> CodexNeighbourhoodCard:
        """Remove the codex card and return it.

        Raises:
            ValueError: raised if there are no codex cards attached.

        Returns:
            The codex card that was popped.

        """
        if self.attached_codex is None:
            raise ValueError("No Codex card is attached.")
        card, self.attached_codex = self.attached_codex, None
        return card

    def handle_clue(self, card: NeighbourhoodCard) -> None:
        """Handle a new clue event.

        Args:
            card: The event card to shuffle into the top 3.

        """
        self.shuffle_into_top_three(card)

    def modify_codex_counters(self, modification: int) -> None:
        """Modify the number of counters of the codex card.

        Args:
            modification: The number of counters to modify by.

        """
        if self.attached_codex is not None:
            self.attached_codex.counters = max(0, modification + self.attached_codex.counters)

    def flip_codex(self) -> None:
        """Modify the number of counters of the codex card.

        Args:
            modification: The number of counters to modify by.

        """
        if self.attached_codex is not None:
            self.attached_codex.is_flipped = True


class ArchiveDeck(dict[int, CodexCard]):
    """The archive/codex deck."""

    def __init__(self, archive: dict[int, CodexCard], card_back: str) -> None:
        """Initialize class.

        Args:
            archive: The archive cards.
            card_back: The back of the card.

        """
        super().__init__(archive)
        self.card_back = card_back

    def get_card(self, codex_number: int) -> CodexCard:
        """Get a codex card by number.

        Args:
            codex_number: The codex number to get.

        Returns:
            The Codex card.

        """
        return self.pop(codex_number)

    def add_card(self, card: CodexCard) -> None:
        """Add a card to the deck.

        Args:
            card: The card to add.

        """
        self[card.number] = card


class EventDeck(DeckBase[NeighbourhoodCard]):
    """The event decks."""

    def __init__(self, deck: list[NeighbourhoodCard]) -> None:
        """Initialize class.

        Args:
            deck: The cards.

        """
        super().__init__(deck=deck)

    def remove_neighbourhood(self, neighbourhoods: list[Neighbourhood]) -> dict[Neighbourhood, EventDeck]:
        """Remove every card belonging to one of the neighbourhoods in the input.

        Args:
            neighbourhoods: A list of neighbourhoods to remove.

        Returns:
            A dict with the removed cards per neighbourhood.

        """
        keep: list[NeighbourhoodCard] = []
        remove: dict[Neighbourhood, list[NeighbourhoodCard]] = defaultdict(list)
        for card in self:
            if card.neighbourhood in neighbourhoods:
                remove[card.neighbourhood].append(card)
                continue
            keep.append(card)

        removed_decks = {neighbourhood: EventDeck(deck) for neighbourhood, deck in remove.items()}
        self[:] = keep
        return removed_decks

    def shuffle_discard(self, discard_pile: EventDeck) -> None:
        """Shuffle the discard into the bottom of the deck.

        Args:
            discard_pile: The discard pile.

        """
        discard_pile.shuffle()
        self[:] = discard_pile + self

    def peek_top_card(self) -> NeighbourhoodCard:
        """Get the top card without removing it.

        Returns:
            The top card of the event deck.

        """
        return self[-1]

    def peek_bottom_card(self) -> NeighbourhoodCard:
        """Get the bottom card without removing it.

        Returns:
            The bottom card of the event deck.

        """
        return self[0]

    def __add__(self, other: EventDeck) -> Self:  # type:ignore reportIncompatibleMethodOverride
        """Override for add.

        Args:
            other: The other deck.

        """
        result = super().__add__(other)
        return type(self)(deck=result)

    def __radd__(self, other: EventDeck) -> Self:
        """Override for radd.

        Args:
            other: The other deck.

        """
        result = other.__add__(self)
        return type(self)(deck=result)


class ActionRequiredDeck(dict[str, NeighbourhoodCard]):
    """Placeholder deck for event cards waiting resolution."""

    def __init__(self) -> None:
        """Initialize class.

        Args:
            deck: The cards.

        """
        super().__init__()


DeckType = NeighbourhoodDeck | EventDeck | ActionRequiredDeck | ArchiveDeck | Deck[HeadlineCard] | Deck[Card] | None


class DeckHistory:
    """Class representing a decks history."""

    def __init__(self, start: DeckType) -> None:
        """Initialize the class.

        Args:
            start: The initial state of the deck history.

        """
        self.state: list[DeckType] = []
        self.state.append(start)
        self.cur_index = 0

    def get(self) -> DeckType:
        """Get the current deck value.

        Returns:
            The current deck.

        """
        return self.state[self.cur_index]

    def clear_futures(self) -> None:
        """Clear a histories future."""
        self.state = self.state[: self.cur_index + 1]

    def add(self) -> None:
        """Add a new deck state to the history.

        Note that this clears the future histories.

        Args:
            item: _description_

        """
        self.state.append(deepcopy(self.state[self.cur_index]))

    def add_new(self, deck: DeckType) -> None:
        """Add a whole new deck to the history.

        Args:
            deck: The deck to add.

        """
        self.state.append(deck)
        self.cur_index += 1

    def undo(self) -> None:
        """Perform an undo operation."""
        if self.cur_index == 0:
            raise ValueError
        self.cur_index -= 1

    def redo(self) -> None:
        """Perform a redo operation."""
        if self.cur_index == (len(self.state) + 1):
            raise ValueError
        self.cur_index += 1


class AllHistories:
    """All of the histories for all of the decks."""

    def __init__(self, initial: dict[Label, DeckType]) -> None:
        """Initialize the class.

        Args:
            initial: The initial dict of decks.

        """
        self.state: dict[Label, DeckHistory] = {}
        for label, deck in initial.items():
            self.state[label] = DeckHistory(deck)

    @overload
    def get(self, key: Neighbourhood) -> NeighbourhoodDeck: ...
    @overload
    def get(self, key: Literal[DeckLabel.EVENT_DECK, DeckLabel.EVENT_DISCARD]) -> EventDeck: ...
    @overload
    def get(self, key: Literal[DeckLabel.ACTION_REQUIRED]) -> ActionRequiredDeck: ...
    @overload
    def get(self, key: Literal[DeckLabel.CODEX, DeckLabel.ARCHIVE]) -> ArchiveDeck: ...
    @overload
    def get(self, key: Literal[DeckLabel.HEADLINE, DeckLabel.RUMOR]) -> Deck[HeadlineCard]: ...
    @overload
    def get(self, key: Literal[DeckLabel.TERROR]) -> Deck[Card]: ...

    def get(self, key: Label) -> DeckType:
        """Get the current deck for a label.

        Args:
            key: The key for the deck.

        Returns:
            The current state of a deck.

        """
        return self.state[key].get()

    def clear_histories(self) -> None:
        """Clear all deck histories."""
        for history in self.state.values():
            history.clear_futures()

    def add(self, keys: Label | Iterable[Label]) -> None:
        """Add a new deck to a history.

        Args:
            keys: The label for the deck history (or a list of labels.)

        """
        self.clear_histories()
        if isinstance(keys, Label):
            self.state[keys].add()
            return
        for key in keys:
            self.state[key].add()

    def add_new(self, key: Label, deck: DeckType) -> None:
        """Add a new deck history.

        None will indicate that the deck is not present.

        Args:
            key: The label for the deck history
            deck: The deck to add.

        """
        self.state[key] = DeckHistory(None)
        self.state[key].add_new(deck)

    def undo(self, keys: Iterable[Label]) -> None:
        """Run an undo on the histories defined by keys.

        Args:
            keys: The keys to the decks to run the undo operation on.

        """
        for key in keys:
            self.state[key].undo()

    def redo(self, keys: Iterable[Label]) -> None:
        """Run an undo on the histories defined by keys.

        Args:
            keys: The keys to the decks to run the undo operation on.

        """
        for key in keys:
            self.state[key].redo()


class PlayerHistories:
    """The history of changes for each player."""

    def __init__(self) -> None:
        """Initialize the class."""
        self.state: dict[ServerConnection, list[set[Label]]] = defaultdict(list)
        self.state_index: dict[ServerConnection, int] = defaultdict(lambda: -1)

    def clear_futures(self) -> None:
        """Clear the future states."""
        for player in self.state:
            self.state[player] = self.state[player][: self.state_index[player] + 1]

    def record_change(self, player: ServerConnection, changes: set[Label]) -> None:
        """Record a change that someone has done.

        Args:
            player: The player that made the change.
            changes: The decks that were changed.

        """
        self.clear_futures()
        self.state[player].append(changes)

    def can_undo(self, player: ServerConnection) -> bool:
        """Check whether a player can undo.

        Args:
            player: The player to check for

        Returns:
            True if yes, false otherwise

        """
        if self.state_index[player] == -1:
            return False
        last_change = self.state[player][-1]
        for other, other_changes in self.state.items():
            if other == player or self.state_index[other] == -1:
                continue
            if len(last_change.intersection(other_changes[-1])) > 0:
                return False
        return True

    def can_redo(self, player: ServerConnection) -> bool:
        """Check whether a player can redo.

        Args:
            player: The player to check for

        Returns:
            True if yes, false otherwise

        """
        return len(self.state[player]) > (self.state_index[player] + 1)

    def undo(self, player: ServerConnection) -> set[Label]:
        """Perform an undo operation for a Player.

        Args:
            player: The player to do the undo for.

        """
        if not self.can_redo(player):
            raise ValueError
        states_to_change = self.state[player][self.state_index[player]]
        self.state_index[player] -= 1
        return states_to_change

    def redo(self, player: ServerConnection) -> set[Label]:
        """Perform an redo operation for a Player.

        Args:
            player: The player to do the redo for.

        """
        if not self.can_redo(player):
            raise ValueError
        states_to_change = self.state[player][self.state_index[player]]
        self.state_index[player] += 1
        return states_to_change
