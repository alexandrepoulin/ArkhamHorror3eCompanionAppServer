"""The game state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from companion.decks import ArchiveDeck, Deck, EmptyDeckError, EventDeck, NeighbourhoodDeck, create_all_scenario_decks
from companion.mappings import DEFAULT_TERROR_NEIGHBOURHOOD
from companion.util_classes import (
    Card,
    CodexCard,
    CodexNeighbourhoodCard,
    HeadlineCard,
    Neighbourhood,
    NeighbourhoodCard,
)

if TYPE_CHECKING:
    from pathlib import Path

    from companion.base_models import GameSettings


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
        self.headline_deck: Deck[HeadlineCard] = all_decks["Headline"]
        self.later_decks: dict[str, dict[Neighbourhood, Any]] = all_decks["later"]
        self.archive_deck: ArchiveDeck = all_decks["Archive_deck"]
        self.codex: ArchiveDeck = ArchiveDeck(archive={})

        self.has_anomalies = all_decks["Anomalies_deck"] is not None
        self.anomalies_deck: Deck[Card] = all_decks["Anomalies_deck"]
        self.has_terror = all_decks["Terror_deck"] is not None
        self.terror_deck: Deck[Card] = all_decks["Terror_deck"]

        self.active_rumor = HeadlineCard | None

    @property
    def number_of_encounter_decks(self) -> int:
        """Return the number of encounter decks.

        Returns:
            The number of decks.

        """
        return len(self.neighbourhood_decks) + (1 if self.has_anomalies else 0) + (1 if self.has_terror else 0)

    def get_neighbourhood_back(self, neighbourhood: Neighbourhood) -> Path:
        """Get the back of a neighbourhood card.

        Args:
            neighbourhood: The Neighbourhood to get the back for.

        Returns:
            The path to the image file.

        """
        return self.neighbourhood_decks[neighbourhood].card_back.face

    def get_anomalies_back(self) -> Path:
        """Get the back of the anomalies deck.

        Raises:
            ValueError: Raised if there are no anomalies for this scenario.

        Returns:
            The path to the image file.

        """
        if not self.has_anomalies:
            raise ValueError("This scenario has no Anomalies deck.")
        return self.anomalies_deck.card_back.face

    def get_terror_back(self) -> Path:
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
            raise EmptyDeckError
        return self.terror_deck.card_back.face

    def get_headline_back(self) -> Path:
        """Get the back of the headline deck.

        Raises:
            EmptyDeckError: Raised if the deck is empty.

        Returns:
            The path to the image file.

        """
        if len(self.headline_deck) == 0:
            raise EmptyDeckError
        return self.headline_deck.card_back.face

    def get_event_back(self) -> Path:
        """Get the back of the event deck.

        Raises:
            EmptyDeckError: Raised if the deck is empty.

        Returns:
            The path to the image file.

        """
        if len(self.event_deck) == 0:
            raise EmptyDeckError
        return self.event_deck.peek_top_card().back

    def get_discard_face(self) -> Path:
        """Get the face of the event discard pile.

        Raises:
            EmptyDeckError: Raised if the pile is empty.

        Returns:
            The path to the image file.

        """
        if len(self.event_deck_discard) == 0:
            raise EmptyDeckError
        return self.event_deck_discard.peek_bottom_card().face

    def draw_from_neighbourhood(self, neighbourhood: Neighbourhood) -> NeighbourhoodCard:
        """Handle a regular encounter from a neighbourhood.

        Args:
            neighbourhood: The target neighbourhood.

        Returns:
            The neighbourhood card

        """
        card = self.neighbourhood_decks[neighbourhood].draw()
        if not any((isinstance(card, CodexCard), card.is_event)):
            self.neighbourhood_decks[neighbourhood].bottom(card)
        return card

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

    def attach_codex_card(self, number: int) -> None:
        """Attach a codex card from the codex to a neighbourhood.

        Args:
            number: The codex card number.

        Raises:
            ValueError: Raised if card doesn't exist or the card can't be attached.

        """
        if number not in self.codex:
            raise ValueError("Card must be in codex first.")
        card = self.codex.get_card(number)
        if not isinstance(card, CodexNeighbourhoodCard):
            raise TypeError("Codex card can't be attached.")
        if not card.can_attach:
            raise ValueError("Codex card can't be attached.")
        self.neighbourhood_decks[card.neighbourhood].attach_codex_card(card)

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

    def spread_terror(self) -> Card:
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
        location = DEFAULT_TERROR_NEIGHBOURHOOD[self.settings.scenario]
        if len(self.event_deck_discard) > 0:
            location = self.event_deck_discard.peek_bottom_card().neighbourhood
        self.neighbourhood_decks[location].add_terror(self.terror_deck.draw())
        return self.neighbourhood_decks[location].card_back

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

    def remove_clue(self, neighbourhood: Neighbourhood) -> None:
        """Remove a clue from a neighbourhood.

        Raises:
            ValueError: Raised if already at 0 clues.

        Args:
            neighbourhood: The neighbourhood in question

        """
        if self.neighbourhood_decks[neighbourhood].clues == 0:
            raise ValueError("Already at 0 clues.")
        self.neighbourhood_decks[neighbourhood].clues -= 1

    def gate_burst(self) -> NeighbourhoodCard:
        """Handle a gate burst.

        Raises:
            EmptyDeckError: Raised if the deck is empty.

        Returns:
            The card that was drawn

        """
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

    def get_archive(self) -> ArchiveDeck:
        """Return the whole archive.

        Returns:
            The archive.

        """
        return self.archive_deck

    def get_codex(self) -> ArchiveDeck:
        """Return the whole codex.

        Returns:
            The codex.

        """
        return self.codex

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
            self.neighbourhood_decks[card.neighbourhood].shuffle_into_top_three(card)
            return
        self.codex.add_card(self.archive_deck.get_card(number))

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

    def add_neighbourhoods(self, neighbourhoods: list[Neighbourhood]) -> None:
        """Add a list of neighbourhoods to the game.

        Args:
            neighbourhoods: The list of neighbourhoods to add.

        """
        for neighbourhood in neighbourhoods:
            self.event_deck += self.later_decks["Event_Decks"][neighbourhood]
            self.neighbourhood_decks[neighbourhood] = self.later_decks["Neighbourhoods"][neighbourhood]
