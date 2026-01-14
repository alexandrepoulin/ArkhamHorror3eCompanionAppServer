"""The game state."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from copy import deepcopy
from typing import TYPE_CHECKING, Any, cast

from companion.deck_factory import create_all_scenario_decks, get_neighbourhood_back_path
from companion.decks import ArchiveDeck, Deck, EmptyDeckError, EventDeck, NeighbourhoodDeck
from companion.mappings import DEFAULT_TERROR_NEIGHBOURHOOD
from companion.util_classes import (
    Card,
    CodexNeighbourhoodCard,
    HeadlineCard,
    Neighbourhood,
    NeighbourhoodCard,
)

if TYPE_CHECKING:
    from companion.util_classes import GameSettings


class GameState:
    """The game state keeping track of all the decks."""

    def __init__(self, settings: GameSettings) -> None:
        """Create all the required decks and setup the game state.

        Args:
            settings: The game settings.

        """
        self.settings = settings
        all_decks = create_all_scenario_decks(settings)
        self.neighbourhood_decks: dict[Neighbourhood, NeighbourhoodDeck] = all_decks["Neighbourhood_Decks"]
        self.event_deck: EventDeck = all_decks["Event_deck"]
        self.event_deck_discard: EventDeck = EventDeck(deck=[])
        self.headline_deck: Deck[HeadlineCard] = all_decks["Headline_deck"]
        self.later_decks: dict[str, dict[Neighbourhood, Any]] = all_decks["later"]
        self.archive_deck: ArchiveDeck = all_decks["Archive_deck"]
        self.codex: ArchiveDeck = ArchiveDeck(archive={}, card_back="codex_61_back")

        self.has_terror = all_decks["Terror_deck"] is not None
        self.terror_deck: Deck[Card] = all_decks["Terror_deck"]
        self.terror_deck_name: str = all_decks["Terror_deck_name"]

        self.active_rumor: HeadlineCard | None = None

        self.temporary_zone: dict[str, NeighbourhoodCard] = {}

    def is_stable(self) -> bool:
        """Whether this is a game state we can revert to.

        Returns:
            True if yes, false otherwise.

        """
        return len(self.temporary_zone) == 0

    def get_neighbourhood_back(self, neighbourhood: Neighbourhood) -> str:
        """Get the back of a neighbourhood card.

        Args:
            neighbourhood: The Neighbourhood to get the back for.

        Returns:
            The path to the image file.

        """
        return self.neighbourhood_decks[neighbourhood].card_back

    def get_terror_back(self) -> str:
        """Get the back of the terror deck.

        Raises:
            ValueError: Raised if terror is not used in this scenario.
            EmptyDeckError: Raised if the deck is empty.

        Returns:
            The path to the image file.

        """
        if not self.has_terror:
            raise ValueError("This scenario has no Terror deck.")
        if len(self.terror_deck) == 0:
            return "empty_back"
        return self.terror_deck.card_back

    def get_headline_back(self) -> str:
        """Get the back of the headline deck.

        Raises:
            EmptyDeckError: Raised if the deck is empty.

        Returns:
            The path to the image file.

        """
        if len(self.headline_deck) == 0:
            return "empty_back"
        return self.headline_deck.card_back

    def get_event_back(self) -> str:
        """Get the back of the event deck.

        Returns:
            The path to the image file.

        """
        if len(self.event_deck) == 0:
            return "empty_back"
        return get_neighbourhood_back_path(self.event_deck.peek_top_card().neighbourhood)

    def get_discard_face(self) -> str:
        """Get the face of the event discard pile.

        Raises:
            EmptyDeckError: Raised if the pile is empty.

        Returns:
            The path to the image file.

        """
        if len(self.event_deck_discard) == 0:
            return "empty_face"
        return self.event_deck_discard.peek_bottom_card().face

    def draw_from_neighbourhood(self, neighbourhood: Neighbourhood) -> tuple[NeighbourhoodCard, str]:
        """Handle a regular encounter from a neighbourhood.

        Args:
            neighbourhood: The target neighbourhood.

        Returns:
            The neighbourhood card

        """
        card = self.neighbourhood_decks[neighbourhood].draw()
        temp_uuid = str(uuid.uuid4())
        if isinstance(card, CodexNeighbourhoodCard):
            card.is_flipped = False
            self.archive_deck.add_card(card)
        elif card.is_event:
            self.temporary_zone[temp_uuid] = card
        else:
            self.neighbourhood_decks[neighbourhood].bottom(card)
        return card, temp_uuid

    def resolve_temporary_zone(self, identifier: str, passed: bool) -> None:
        """Handle the result of whether an event card was succeeded or not.

        Args:
            identifier: The identifier for the card in the temporary zone.
            passed: True if the card should go back to the event deck, false if it should be reshuffled in.

        Returns:
            The neighbourhood card

        """
        if identifier not in self.temporary_zone:
            raise ValueError
        card = self.temporary_zone.pop(identifier)
        if passed:
            self.event_deck_discard.bottom(card)
            return
        self.neighbourhood_decks[card.neighbourhood].shuffle_into_top_three(card)

    def draw_terror_from_neighbourhood(self, neighbourhood: Neighbourhood) -> Card:
        """Draw a terror card that has been attached to a neighbourhood.

        Args:
            neighbourhood: The target neighbourhood.

        Returns:
            The terror card

        """
        card = self.neighbourhood_decks[neighbourhood].attached_terror.draw()
        self.terror_deck.bottom(card)
        return card

    def detach_codex_card(self, neighbourhood: Neighbourhood) -> CodexNeighbourhoodCard | None:
        """Attach a codex card from the codex to a neighbourhood.

        Args:
            neighbourhood: The neighbourhood to get the card from.

        Returns:
            The card or None

        """
        if self.neighbourhood_decks[neighbourhood].attached_codex is None:
            return None
        card = self.neighbourhood_decks[neighbourhood].pop_codex_card()
        self.archive_deck.add_card(card)
        return card

    def view_codex_card(self, neighbourhood: Neighbourhood) -> CodexNeighbourhoodCard | None:
        """View a codex card from the codex to a neighbourhood.

        Args:
            neighbourhood: The neighbourhood to get the card from.

        Returns:
            The card or None

        """
        if self.neighbourhood_decks[neighbourhood].attached_codex is None:
            return None
        return self.neighbourhood_decks[neighbourhood].attached_codex

    def draw_from_event_deck(self, *, from_top: bool = True) -> NeighbourhoodCard:
        """Handle a drawing from the top or bottom of the event deck.

        Raises:
            EmptyDeckError: Raised if the deck is empty.

        Returns:
            The event card

        """
        try:
            return self.event_deck.draw(from_top=from_top)
        except EmptyDeckError:
            self.event_deck.shuffle_discard(self.event_deck_discard)
            raise

    def spread_doom(self) -> NeighbourhoodCard:
        """Handle spreading doom.

        Raises:
            EmptyDeckError: Raised if the deck is empty.

        Returns:
            The event card card that was drawn.

        """
        card = self.draw_from_event_deck(from_top=False)
        self.event_deck_discard.bottom(card)
        return card

    def spread_terror(self) -> NeighbourhoodCard | Neighbourhood:
        """Handle spreading doom.

        Raises:
            ValueError: Raised if terror is not used in this scenario
            EmptyDeckError: Raised if the deck is empty.

        Returns:
            The event card card that was drawn.

        """
        if not self.has_terror:
            raise ValueError("This scenario has no Terror deck.")
        if len(self.terror_deck) == 0:
            raise EmptyDeckError
        if len(self.event_deck_discard) > 0:
            location_card = self.event_deck_discard.peek_bottom_card()
            location = location_card.neighbourhood
            self.neighbourhood_decks[location].add_terror(self.terror_deck.draw())
            return location_card
        location = DEFAULT_TERROR_NEIGHBOURHOOD[self.settings.scenario]
        self.neighbourhood_decks[location].add_terror(self.terror_deck.draw())
        return location

    def spread_clue(self) -> NeighbourhoodCard:
        """Handle spreading a clue.

        Raises:
            EmptyDeckError: Raised if the deck is empty.

        Returns:
            The neighbourhood card that was shuffled.

        """
        card = self.draw_from_event_deck()
        self.neighbourhood_decks[card.neighbourhood].shuffle_into_top_three(card)
        return card

    def gate_burst(self) -> NeighbourhoodCard | None:
        """Handle a gate burst.

        Raises:
            EmptyDeckError: Raised if the deck is empty.

        Returns:
            The card that was drawn

        """
        card = None
        if len(self.event_deck) > 0:
            card = self.event_deck.draw()
            self.event_deck_discard.bottom(card)
        self.event_deck.shuffle_discard(self.event_deck_discard)
        self.event_deck_discard = EventDeck(deck=[])
        return card

    def draw_headline(self) -> HeadlineCard:
        """Handle a headline.

        Raises:
            EmptyDeckError: Raised if the deck is empty.

        Returns:
            The card that was drawn

        """
        card = self.headline_deck.draw()
        if card.is_rumor:
            self.active_rumor = card
        return card

    def get_archive(self) -> list[dict[str, Any]]:
        """Return the whole archive.

        Returns:
            The archive.

        """
        
        return sorted([card.to_dict() for card in self.archive_deck.values()], key=lambda x: x["number"])

    def get_codex(self) -> list[dict[str, Any]]:
        """Return the whole codex.

        Returns:
            The codex.

        """
        return sorted([card.to_dict(in_codex=True) for card in self.codex.values()], key=lambda x: x["number"])

    def add_from_archive(self, number: int) -> None:
        """Move a card from the archive to the codex.

        Args:
            number: The codex card number.

        Raises:
            ValueError: Raised if that number isn't available to be moved.

        """
        if number not in self.archive_deck:
            raise ValueError("Invalid archive card number to add to codex.")
        card = self.archive_deck.get_card(number)
        if isinstance(card, CodexNeighbourhoodCard):
            if card.can_attach:
                self.neighbourhood_decks[card.neighbourhood].attach_codex_card(card)
            elif card.is_encounter:
                if 13 <= card.number <= 17:
                    self.neighbourhood_decks[card.neighbourhood].shuffle_into_top_three(card)
                elif 161 <= card.number <= 165:
                    self.neighbourhood_decks[card.neighbourhood].top(card)
            return
        self.codex.add_card(card)

    def return_to_archive(self, number: int) -> None:
        """Move a card from the codex to the archive.

        Args:
            number: The codex card number.

        Raises:
            ValueError: Raised if that number isn't available to be moved.

        """
        if number not in self.codex:
            raise ValueError("Invalid codex card number to return to archive.")
        card = self.codex.get_card(number)
        card.is_flipped = False
        self.archive_deck.add_card(card)

    def add_neighbourhood(self, neighbourhood: Neighbourhood) -> None:
        """Add a list of neighbourhoods to the game.

        Args:
            neighbourhoods: The list of neighbourhoods to add.

        """
        if neighbourhood in self.later_decks["Event_Decks"]:
            if neighbourhood == Neighbourhood.THE_UNDERWORLD:
                self.event_deck = self.event_deck[:-4]
                self.event_deck += self.later_decks["Event_Decks"][neighbourhood][:2]
                self.event_deck.shuffle()
                self.event_deck_discard.bottom(self.later_decks["Event_Decks"][neighbourhood][-1])
                self.event_deck_discard.bottom(self.later_decks["Event_Decks"][neighbourhood][-2])

                self.neighbourhood_decks[neighbourhood] = deepcopy(self.later_decks["Neighbourhoods"][neighbourhood])
                del self.later_decks["Neighbourhoods"][neighbourhood]
                del self.later_decks["Event_Decks"][neighbourhood]
                return
            self.event_deck += self.later_decks["Event_Decks"][neighbourhood]
            self.event_deck.shuffle_discard(self.event_deck_discard)
            self.event_deck_discard = EventDeck(deck=[])
            del self.later_decks["Event_Decks"][neighbourhood]
        self.neighbourhood_decks[neighbourhood] = deepcopy(self.later_decks["Neighbourhoods"][neighbourhood])
        del self.later_decks["Neighbourhoods"][neighbourhood]

    def update_info(self) -> dict[str, Any]:
        """Return the information needed to render the decks screen.

        Returns:
            The information to draw the game screen.

        """
        decks: list[Mapping[str, Any]] = [
            {
                "name": neighbourhood.value,
                "visible_image": deck.card_back,
                "num_cards": len(deck),
                "has_attached_codex": deck.attached_codex is not None,
                "num_attached_terror": len(deck.attached_terror),
            }
            for neighbourhood, deck in self.neighbourhood_decks.items()
        ]

        decks.extend(
            [
                {
                    "name": "Headlines",
                    "visible_image": self.get_headline_back(),
                    "num_cards": len(self.headline_deck),
                    "has_attached_codex": False,
                    "num_attached_terror": 0,
                },
                {
                    "name": "Event Deck",
                    "visible_image": self.get_event_back(),
                    "num_cards": len(self.event_deck),
                    "has_attached_codex": False,
                    "num_attached_terror": 0,
                },
                {
                    "name": "Event Discard",
                    "visible_image": self.get_discard_face(),
                    "num_cards": len(self.event_deck_discard),
                    "has_attached_codex": False,
                    "num_attached_terror": 0,
                },
                {
                    "name": "Codex",
                    "visible_image": self.codex.card_back,
                    "num_cards": len(self.codex),
                    "has_attached_codex": False,
                    "num_attached_terror": 0,
                },
            ]
        )
        
        if self.has_terror:
            decks.append(
                {
                    "name": self.terror_deck_name,
                    "visible_image": self.get_terror_back(),
                    "num_cards": len(self.terror_deck),
                    "has_attached_codex": False,
                    "num_attached_terror": 0,
                }
            )
        
        if self.active_rumor is not None:
            decks.append(
                {
                    "name": "Rumor",
                    "visible_image": self.active_rumor.face,
                    "num_cards": 1,
                    "has_attached_codex": False,
                    "num_attached_terror": 0,
                }
            )
        if len(self.later_decks["Neighbourhoods"]) > 0:
            decks.append(
                {
                    "name": "Add Deck",
                    "visible_image": "add_neighbourhood",
                    "num_cards": 1,
                    "has_attached_codex": False,
                    "num_attached_terror": 0,
                }
            )

        future_decks: list[Mapping[str, Any]] = [
            {
                "name": neighbourhood.value,
                "visible_image": cast("NeighbourhoodDeck", deck).card_back,
                "num_cards": len(cast("NeighbourhoodDeck", deck)),
                "has_attached_codex": False,
                "num_attached_terror": 0,
            }
            for neighbourhood, deck in self.later_decks["Neighbourhoods"].items()
        ]
        terror_card_back = None if not self.has_terror else self.terror_deck.card_back
        return {
            "Decks": decks,
            "Additional_Decks": future_decks,
            "Uses_Terror": self.has_terror,
            "Terror_Deck_Back": terror_card_back,
        }
