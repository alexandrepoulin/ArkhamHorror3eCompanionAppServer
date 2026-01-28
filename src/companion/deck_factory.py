"""Everything related to deck creation."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from companion.cards import CODEX_CARDS, EVENT_CARDS, HEADLINE_CARDS, NEIGHBOURHOOD_CARDS, TERROR_CARDS
from companion.decks import ArchiveDeck, Deck, EventDeck, NeighbourhoodDeck
from companion.mappings import (
    CODEX_ATTACHABLE,
    CODEX_ENCOUNTERS,
    CODEX_ITEMS,
    CODEX_MONSTERS,
    CODEX_NEIGHBOURHOODS,
    HEADLINE_RUMORS,
    REQUIRED_CODEX,
    REQUIRED_NEIGHBOURHOODS,
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
    from companion.util_classes import GameSettings

_number_re = re.compile(r"(\d+)")


# Terror decks
def create_terror_deck(settings: GameSettings) -> tuple[Deck[Card], str] | tuple[None, None]:
    """Create the terror deck if applicable.

    Args:
        settings: The game settings.

    Returns:
        The deck for the terror or None if not applicable.

    """
    if (terror := SCENARIO_TERROR_MAP.get(settings.scenario)) is None:
        return None, None

    back = TERROR_CARDS[terror]["back"].lower()
    deck = Deck(
        deck=[Card(face=face.lower(), back=back) for face in TERROR_CARDS[terror]["face"]],
        card_back=back,
    )

    deck.shuffle()
    return deck, terror.value


# Headline decks
def create_headline_deck(settings: GameSettings) -> Deck[HeadlineCard]:
    """Create the headline deck.

    Args:
        settings: The game settings.

    Returns:
        The headline deck.

    """
    card_back = HEADLINE_CARDS["back"].lower()

    deck: list[HeadlineCard] = []
    for expansion in Expansions:
        if not (expansion == 0 or (settings.expansions & expansion > 0)):
            continue
        for card in HEADLINE_CARDS[expansion]:
            number = int(_number_re.findall(card)[0])
            is_rumor = number in HEADLINE_RUMORS[expansion]
            deck.append(
                HeadlineCard(face=card.lower(), back=card_back, is_rumor=is_rumor, counters=0 if is_rumor else -1)
            )

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
    card_back = NEIGHBOURHOOD_CARDS[neighbourhood]["back"].lower()

    deck: list[NeighbourhoodCard] = []
    for expansion in Expansions:
        if not (expansion == 0 or (settings.expansions & expansion > 0)):
            continue
        if expansion not in NEIGHBOURHOOD_CARDS[neighbourhood]:
            continue
        deck.extend(
            [
                NeighbourhoodCard(face=card.lower(), back=card_back, neighbourhood=neighbourhood, is_event=False)
                for card in NEIGHBOURHOOD_CARDS[neighbourhood][expansion]
            ]
        )

    final_deck = NeighbourhoodDeck(deck=deck, card_back=card_back)
    final_deck.shuffle()
    return final_deck


def get_neighbourhood_back_path(neighbourhood: Neighbourhood) -> str:
    """Get the card back path or a neighbourhood.

    Args:
        neighbourhood: The neighbourhood in question.

    Returns:
        The path to the card back image.

    """
    return NEIGHBOURHOOD_CARDS[neighbourhood]["back"].lower()


def get_neighbourhood_from_back(back: str) -> Neighbourhood:
    """Get the neighbourhood from its back.

    Args:
        back: The image name for the back of a neighbourhood.

    Raises:
        ValueError: Raised if there are no matches.

    Returns:
        The associated neighbourhood.

    """
    for neighbourhood in Neighbourhood:
        if back == NEIGHBOURHOOD_CARDS[neighbourhood]["back"].lower():
            return neighbourhood
    raise ValueError("Unknown neighbourhood back")


def create_event_deck(settings: GameSettings) -> EventDeck:
    """Create the event deck.

    Args:
        settings: The game settings.

    Returns:
        The event deck.

    """
    deck = EventDeck(
        deck=[
            NeighbourhoodCard(
                face=card["face"].lower(),
                back=card["back"].lower(),
                neighbourhood=get_neighbourhood_from_back(card["back"].lower()),
                is_event=True,
            )
            for card in EVENT_CARDS[settings.scenario]
        ]
    )
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
    archive: dict[int, CodexCard] = {}
    for number in required:
        if number in CODEX_NEIGHBOURHOODS:
            archive[number] = CodexNeighbourhoodCard(
                face=CODEX_CARDS[number]["face"].lower(),
                back=CODEX_CARDS[number]["back"].lower(),
                number=number,
                is_encounter=number in CODEX_ENCOUNTERS,
                can_attach=number in CODEX_ATTACHABLE,
                neighbourhood=CODEX_NEIGHBOURHOODS[number],
            )
            continue
        archive[number] = CodexCard(
            face=CODEX_CARDS[number]["face"].lower(),
            back=CODEX_CARDS[number]["back"].lower(),
            number=number,
            is_item=number in CODEX_ITEMS,
            is_flipped=False,
            is_monster=number in CODEX_MONSTERS,
            can_attach=False,
            is_encounter=False,
            counters=0,
        )

    return ArchiveDeck(archive=archive, card_back="codex_61_back")


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
    terror_deck, terror_deck_name = create_terror_deck(settings)

    return {
        "Neighbourhood_Decks": neighbourhood_needs,
        "Event_deck": event_deck,
        "Terror_deck": terror_deck,
        "Terror_deck_name": terror_deck_name,
        "Headline_deck": create_headline_deck(settings),
        "Archive_deck": create_archive(settings),
        "later": {"Event_Decks": event_decks_later, "Neighbourhoods": neighbourhood_later},
    }
