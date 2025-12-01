"""Everything related to deck creation."""

from __future__ import annotations

import re
import secrets
from collections import defaultdict
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self, SupportsIndex, cast, overload

from companion.mappings import (
    CODEX_ATTACHABLE,
    CODEX_ENCOUNTERS,
    CODEX_ITEMS,
    CODEX_MONSTERS,
    CODEX_NEIGHBOURHOODS,
    REQUIRED_CODEX,
    REQUIRED_NEIGHBOURHOODS,
    SCENARIO_ANOMALY_MAP,
    SCENARIO_TERROR_MAP,
)
from companion.util_classes import (
    Card,
    CodexCard,
    CodexNeighbourhoodCard,
    Expansions,
    HeadlineCard,
    Neighbourhood,
    NeighbourhoodCard,
)

if TYPE_CHECKING:
    from collections.abc import MutableSequence

    from companion.base_models import GameSettings

IMAGES = Path("resources/triaged_images")
NEIGHBOURHOOD_RE = re.compile("(.*) Neighbou{0,1}rhood.*")


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

    def __init__(self, deck: list[T], card_back: Card) -> None:
        """Initialize class.

        Args:
            deck: The list of cards.
            card_back: The card back to use for the deck.

        """
        super().__init__(deck)
        self.card_back = card_back


class NeighbourhoodDeck(Deck[NeighbourhoodCard]):
    """A deck for a neighbourhood."""

    def __init__(self, deck: list[NeighbourhoodCard], card_back: Card) -> None:
        """Initialize class.

        Args:
            deck: The list of cards
            card_back: The card back to use for the deck.

        """
        super().__init__(deck=deck, card_back=card_back)
        self.card_back = card_back
        self.attached_terror: DeckBase[Card] = DeckBase(deck=[])
        self.attached_codex: CodexCard | None = None
        self.clues = 0

    def add_terror(self, card: Card) -> None:
        """Attach a terror card to the deck.

        Args:
            card: The terror card.

        """
        self.attached_terror.top(card)

    def attach_codex_card(self, card: CodexCard) -> None:
        """Attach a codex card to the deck.

        Args:
            card: The codex card.

        Raises:
            ValueError: raised if there is already a codex card attached.

        """
        if self.attach_codex_card is not None:
            raise ValueError("Codex card already present.")
        self.attached_codex = card

    def pop_codex_card(self) -> CodexCard:
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
        self.clues += 1


class ArchiveDeck(dict[int, CodexCard]):
    """The archive/codex deck."""

    def __init__(self, archive: dict[int, CodexCard]) -> None:
        """Initialize class.

        Args:
            archive: The archive cards.

        """
        super().__init__(archive)

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


# Anomalies decks
def create_anomalies_deck(settings: GameSettings) -> Deck[Card] | None:
    """Create the anomalies deck if applicable.

    Args:
        settings: The game settings.

    Returns:
        The deck for the anomalies or None if not applicable.

    """
    if (anomaly := SCENARIO_ANOMALY_MAP.get(settings.scenario)) is None:
        return None

    directory = IMAGES / "Anomalies" / f"{anomaly} Anomalies"
    deck = Deck(
        card_back=Card(face=next(directory.glob(f"{anomaly} Anomalies*back*"))),
        deck=[Card(face=path) for path in directory.glob(f"{anomaly} Anomalies*face*")],
    )
    deck.shuffle()
    return deck


# Terror decks
def create_terror_deck(settings: GameSettings) -> Deck[Card] | None:
    """Create the terror deck if applicable.

    Args:
        settings: The game settings.

    Returns:
        The deck for the terror or None if not applicable.

    """
    if (terror := SCENARIO_TERROR_MAP.get(settings.scenario)) is None:
        return None

    directory = IMAGES / "Terror" / f"{terror} Terror"
    deck = Deck(
        card_back=Card(face=next(directory.glob(f"{terror} Terror*back*"))),
        deck=[Card(face=path) for path in directory.glob(f"{terror} Terror*face*")],
    )
    deck.shuffle()
    return deck


# Headline decks
def create_headline_deck(settings: GameSettings) -> Deck[HeadlineCard]:
    """Create the headline deck.

    Args:
        settings: The game settings.

    Returns:
        The headline deck.

    """
    directory = IMAGES / "Headlines" / "Headlines"
    card_back = Card(face=next(directory.glob("Headlines*back*")))
    base_rumors = ("6", "7", "10", "11")
    deck = [
        HeadlineCard(face=path, is_rumor=any(num in path.stem for num in base_rumors))
        for path in directory.glob("Headlines*face*")
    ]

    if settings.expansions & Expansions.DEAD_OF_NIGHT:
        directory = IMAGES / "Headlines" / "Headlines (DoN)"
        don_rumors = ("4", "6")
        deck.extend(
            [
                HeadlineCard(face=path, is_rumor=any(num in path.stem for num in don_rumors))
                for path in directory.glob("*")
            ]
        )
    if settings.expansions & Expansions.UNDER_DARK_WAVES:
        # No rumors in Under Dark Waves
        directory = IMAGES / "Headlines" / "Headlines (UDW)"
        deck.extend([HeadlineCard(face=path, is_rumor=False) for path in directory.glob("*")])
    if settings.expansions & Expansions.SECRETS_OF_THE_ORDER:
        directory = IMAGES / "Headlines" / "Headlines (SotO)"
        # Only one rumor in Secrets of the Order
        deck.extend([HeadlineCard(face=path, is_rumor="0" in path.stem) for path in directory.glob("*")])
    all_cards = Deck(deck=deck, card_back=card_back)
    all_cards.shuffle()
    return all_cards[:13]


def create_scenario_neighbourhoods_deck(
    settings: GameSettings,
) -> tuple[dict[Neighbourhood, Deck[NeighbourhoodCard]], dict[Neighbourhood, Deck[NeighbourhoodCard]]]:
    """Create the required neighbourhood decks.

    Args:
        settings: The game settings.

    Returns:
        A mapping of neighbourhoods required right away, and one for decks that can be added later.

    """
    required = REQUIRED_NEIGHBOURHOODS[settings.scenario]
    need_now = required["start"]
    set_aside = required.get("later", [])

    decks_at_start: dict[Neighbourhood, Deck[NeighbourhoodCard]] = {}
    for neighbourhood in need_now:
        decks_at_start[neighbourhood] = create_neighbourhoods_deck(settings, neighbourhood)

    decks_set_aside: dict[Neighbourhood, Deck[NeighbourhoodCard]] = {}
    for neighbourhood in set_aside:
        decks_set_aside[neighbourhood] = create_neighbourhoods_deck(settings, neighbourhood)

    return (decks_at_start, decks_set_aside)


def create_neighbourhoods_deck(settings: GameSettings, neighbourhood: Neighbourhood) -> Deck[NeighbourhoodCard]:
    """Create a specific neighbourhood deck.

    Args:
        settings: The game settings.
        neighbourhood: The neighbourhood.

    Returns:
        The deck for the neighbourhood.

    """
    directory = IMAGES / "Neighborhoods" / f"{neighbourhood} Neighbourhood"
    card_back_path = get_neighbourhood_back_path(neighbourhood)
    card_back = Card(face=card_back_path)
    deck = [
        NeighbourhoodCard(neighbourhood=neighbourhood, face=path, back=card_back_path, is_event=False)
        for path in directory.glob(f"{neighbourhood}*face*")
    ]
    if settings.expansions & Expansions.DEAD_OF_NIGHT:
        directory = IMAGES / "Neighborhoods" / f"{neighbourhood} Neighbourhood (DoN)"
        deck.extend(
            [
                NeighbourhoodCard(neighbourhood=neighbourhood, face=path, back=card_back_path, is_event=False)
                for path in directory.glob(f"{neighbourhood}*face*")
            ]
        )
    if settings.expansions & Expansions.UNDER_DARK_WAVES:
        directory = IMAGES / "Neighborhoods" / f"{neighbourhood} Neighbourhood (UDW)"
        deck.extend(
            [
                NeighbourhoodCard(neighbourhood=neighbourhood, face=path, back=card_back_path, is_event=False)
                for path in directory.glob(f"{neighbourhood}*face*")
            ]
        )
    if settings.expansions & Expansions.SECRETS_OF_THE_ORDER:
        directory = IMAGES / "Neighborhoods" / f"{neighbourhood} Neighbourhood (SotO)"
        deck.extend(
            [
                NeighbourhoodCard(neighbourhood=neighbourhood, face=path, back=card_back_path, is_event=False)
                for path in directory.glob(f"{neighbourhood}*face*")
            ]
        )
    deck = NeighbourhoodDeck(deck=deck, card_back=card_back)
    deck.shuffle()
    return deck


@cache
def get_neighbourhood_back_path(neighbourhood: Neighbourhood) -> Path:
    """Get the card back path or a neighbourhood.

    Args:
        neighbourhood: The neighbourhood in question.

    Returns:
        The path to the card back image.

    """
    directory = IMAGES / "Neighborhoods" / f"{neighbourhood} Neighbourhood"
    return next(directory.glob(f"{neighbourhood}*back*"))


def create_event_deck(settings: GameSettings) -> EventDeck:
    """Create the event deck.

    Args:
        settings: The game settings.

    Returns:
        The event deck.

    """
    directory = IMAGES / "Events" / f"{settings.scenario} Event Deck/"
    deck: list[NeighbourhoodCard] = []
    for path in directory.glob("*face*"):
        neighbourhood = Neighbourhood(cast("re.Match[str]", NEIGHBOURHOOD_RE.match(path.stem)).group(1))
        card_back_path = get_neighbourhood_back_path(neighbourhood)
        deck.append(NeighbourhoodCard(neighbourhood=neighbourhood, face=Path(path), back=card_back_path, is_event=True))

    deck = EventDeck(deck=deck)
    deck.shuffle()
    return deck


def create_archive(settings: GameSettings) -> ArchiveDeck:
    """Create the archive deck.

    Args:
        settings: The game settings.

    Returns:
        The archive deck.

    """
    required = REQUIRED_CODEX[settings.scenario]
    directory = IMAGES / "Codex"
    archive: dict[int, CodexCard] = {}
    for number in required:
        paths = list(directory.glob(f"*{number}*"))
        face, back = paths if "face" in paths[0].stem else (paths[1], paths[0])
        if number in CODEX_NEIGHBOURHOODS:
            archive[number] = CodexNeighbourhoodCard(
                face=Path(face),
                back=Path(back),
                number=number,
                is_encounter=number in CODEX_ENCOUNTERS,
                can_attach=number in CODEX_ATTACHABLE,
                neighbourhood=CODEX_NEIGHBOURHOODS[number],
            )
        else:
            archive[number] = CodexCard(
                face=Path(face),
                back=Path(back),
                number=number,
                is_item=number in CODEX_ITEMS,
                is_flipped=False,
                is_monster=number in CODEX_MONSTERS,
                can_attach=False,
                is_encounter=False,
            )

    return ArchiveDeck(archive=archive)


def create_all_scenario_decks(settings: GameSettings) -> dict[str, Any]:
    """Create all the required decks based on game settings.

    Args:
        settings: The Game settings.

    Returns:
        A dict mapping the kind of deck to the deck.

    """
    neighbourhood_needs, neighbourhood_later = create_scenario_neighbourhoods_deck(settings)
    event_deck = create_event_deck(settings)
    event_decks_later = event_deck.remove_neighbourhood(list(neighbourhood_later.keys()))

    return {
        "Neighbourhood_Decks": neighbourhood_needs,
        "Event_deck": event_deck,
        "Terror_deck": create_terror_deck(settings),
        "Anomalies_deck": create_anomalies_deck(settings),
        "Headline_deck": create_headline_deck(settings),
        "Archive_deck": create_archive(settings),
        "later": {"Event_Decks": event_decks_later, "Neighbourhoods": neighbourhood_later},
    }
