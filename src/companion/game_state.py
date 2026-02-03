"""The game state."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, cast

from companion.deck_factory import create_all_scenario_decks, get_neighbourhood_back_path
from companion.decks import (
    ActionRequiredDeck,
    AllHistories,
    ArchiveDeck,
    Deck,
    EmptyDeckError,
    EventDeck,
    NeighbourhoodDeck,
    PlayerHistories,
)
from companion.mappings import CODEX_SHUFFLE_ENCOUNTERS, CODEX_TOP_ENCOUNTERS, DEFAULT_TERROR_NEIGHBOURHOOD
from companion.util_classes import (
    Card,
    CardViewState,
    CodexNeighbourhoodCard,
    DeckLabel,
    HeadlineCard,
    Label,
    Neighbourhood,
    NeighbourhoodCard,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from websockets.asyncio.server import ServerConnection

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

        self.decks: AllHistories = all_decks["all_histories"]
        self.terror_deck_name: str = all_decks["Terror_deck_name"]
        self.has_terror = len(self.decks.get(DeckLabel.TERROR)) == 0
        self.neighbourhoods: list[Neighbourhood] = all_decks["neighbourhoods"]
        self.later_decks = all_decks["later"]

        self.player_histories = PlayerHistories()

    ## ------------
    ## shorthands
    ## ------------
    @property
    def event_deck(self) -> EventDeck:
        """Return the event deck.

        Returns:
            Return the event deck.

        """
        return self.decks.get(DeckLabel.EVENT_DECK)

    @property
    def discard(self) -> EventDeck:
        """Return the discard deck.

        Returns:
            Return the discard deck.

        """
        return self.decks.get(DeckLabel.EVENT_DISCARD)

    @property
    def action_required(self) -> ActionRequiredDeck:
        """Return the action required deck.

        Returns:
            Return the action required deck.

        """
        return self.decks.get(DeckLabel.ACTION_REQUIRED)

    @property
    def codex(self) -> ArchiveDeck:
        """Return the codex deck.

        Returns:
            Return the codex deck.

        """
        return self.decks.get(DeckLabel.CODEX)

    @property
    def archive(self) -> ArchiveDeck:
        """Return the archive deck.

        Returns:
            Return the archive deck.

        """
        return self.decks.get(DeckLabel.ARCHIVE)

    @property
    def headline(self) -> Deck[HeadlineCard]:
        """Return the headline deck.

        Returns:
            Return the headline deck.

        """
        return self.decks.get(DeckLabel.HEADLINE)

    @property
    def rumor(self) -> Deck[HeadlineCard]:
        """Return the rumor deck.

        Returns:
            Return the rumor deck.

        """
        return self.decks.get(DeckLabel.RUMOR)

    @property
    def terror(self) -> Deck[Card]:
        """Return the terror deck.

        Returns:
            Return the terror deck.

        """
        return self.decks.get(DeckLabel.TERROR)

    def nb_deck(self, neighbourhood: Neighbourhood) -> NeighbourhoodDeck:
        """Return the deck from a neighbourhood.

        Args:
            neighbourhood: The neighbourhood to get.

        Returns:
            Return the deck from a neighbourhood.

        """
        return self.decks.get(neighbourhood)

    ## ------------
    ## real logic
    ## ------------

    def get_neighbourhood_back(self, neighbourhood: Neighbourhood) -> str:
        """Get the back of a neighbourhood card.

        Args:
            neighbourhood: The Neighbourhood to get the back for.

        Returns:
            The name of the image.

        """
        return self.nb_deck(neighbourhood).card_back

    def get_terror_back(self) -> str:
        """Get the back of the terror deck.

        Raises:
            ValueError: Raised if terror is not used in this scenario.

        Returns:
            The name of the image.

        """
        if not self.has_terror:
            raise ValueError("This scenario has no Terror deck.")
        if len(self.terror) == 0:
            return "empty_back"
        return self.terror.card_back

    def get_headline_back(self) -> str:
        """Get the back of the headline deck.

        Returns:
            The name of the image.

        """
        if len(self.headline) == 0:
            return "empty_back"
        return self.headline.card_back

    def get_event_back(self) -> str:
        """Get the back of the event deck.

        Returns:
            The name of the image.

        """
        if len(self.event_deck) == 0:
            return "empty_back"
        return get_neighbourhood_back_path(self.event_deck.peek_top_card().neighbourhood)

    def get_discard_face(self) -> str:
        """Get the face of the event discard pile.

        Returns:
            The name of the image.

        """
        if len(self.discard) == 0:
            return "empty_face"
        return self.discard.peek_bottom_card().face

    def draw_from_neighbourhood(
        self, neighbourhood: Neighbourhood, sender: ServerConnection
    ) -> tuple[NeighbourhoodCard, str]:
        """Handle a regular encounter from a neighbourhood.

        Args:
            neighbourhood: The target neighbourhood.
            sender: The player taking the action.

        Returns:
            The neighbourhood card

        """
        self.decks.add(neighbourhood)
        changes: set[Label] = {neighbourhood}
        card = self.nb_deck(neighbourhood).draw()
        temp_uuid = str(uuid.uuid4())
        if isinstance(card, CodexNeighbourhoodCard):
            changes.add(DeckLabel.ARCHIVE)
            self.decks.add(DeckLabel.ARCHIVE)
            card.is_flipped = False
            self.archive.add_card(card)
        elif card.is_event:
            changes.add(DeckLabel.ACTION_REQUIRED)
            self.decks.add(DeckLabel.ACTION_REQUIRED)
            self.action_required[temp_uuid] = card
        else:
            self.nb_deck(neighbourhood).bottom(card)
        self.player_histories.record_change(sender, changes)
        return card, temp_uuid

    def resolve_temporary_zone(self, *, identifier: str, passed: bool, sender: ServerConnection) -> None:
        """Handle the result of whether an event card was succeeded or not.

        Args:
            identifier: The identifier for the card in the temporary zone.
            passed: True if the card should go back to the event deck, false if it should be reshuffled in.
            sender: The player taking the action.

        """
        if identifier not in self.action_required:
            raise ValueError
        self.decks.add(DeckLabel.ACTION_REQUIRED)
        changes: set[Label] = {DeckLabel.ACTION_REQUIRED}
        card = self.action_required.pop(identifier)
        if passed:
            self.decks.add(DeckLabel.EVENT_DISCARD)
            changes.add(DeckLabel.EVENT_DISCARD)
            self.player_histories.record_change(sender, changes)
            self.discard.bottom(card)
            return
        self.decks.add(card.neighbourhood)
        changes.add(card.neighbourhood)
        self.player_histories.record_change(sender, changes)
        self.nb_deck(card.neighbourhood).shuffle_into_top_three(card)

    def draw_terror_from_neighbourhood(self, neighbourhood: Neighbourhood, sender: ServerConnection) -> Card:
        """Draw a terror card that has been attached to a neighbourhood.

        Args:
            neighbourhood: The target neighbourhood.
            sender: The player taking the action.

        Raises:
            EmptyDeckError: raised if the deck is empty.

        Returns:
            The terror card

        """
        if len(self.nb_deck(neighbourhood).attached_terror) == 0:
            raise EmptyDeckError
        changes: set[Label] = {neighbourhood, DeckLabel.TERROR}
        self.decks.add(changes)
        self.player_histories.record_change(sender, changes)
        card = self.nb_deck(neighbourhood).attached_terror.draw()
        self.terror.bottom(card)
        return card

    def _detach_codex_card(self, neighbourhood: Neighbourhood) -> None:
        """Detach a codex card from the codex to a neighbourhood.

        Args:
            neighbourhood: The neighbourhood to get the card from.

        """
        card = self.nb_deck(neighbourhood).pop_codex_card()
        card.is_flipped = False
        card.counters = 0
        self.archive.add_card(card)

    def view_codex_card(self, neighbourhood: Neighbourhood) -> CodexNeighbourhoodCard | None:
        """View a codex card from the codex to a neighbourhood.

        Args:
            neighbourhood: The neighbourhood to get the card from.

        Returns:
            The card or None

        """
        if self.nb_deck(neighbourhood).attached_codex is None:
            return None
        return self.nb_deck(neighbourhood).attached_codex

    def _draw_from_event_deck(self, *, from_top: bool = True) -> NeighbourhoodCard:
        """Handle a drawing from the top or bottom of the event deck.

        Raises:
            EmptyDeckError: Raised if the deck is empty.

        Returns:
            The event card

        """
        try:
            return self.event_deck.draw(from_top=from_top)
        except EmptyDeckError:
            self.decks.add(DeckLabel.EVENT_DISCARD)
            self.event_deck.shuffle_discard(self.discard)
            self.discard.clear()
            raise

    def spread_doom(self, sender: ServerConnection) -> NeighbourhoodCard:
        """Handle spreading doom.

        Args:
            sender: The player taking the action.

        Raises:
            EmptyDeckError: Raised if the deck is empty.

        Returns:
            The event card card that was drawn.

        """
        changes: set[Label] = {DeckLabel.EVENT_DECK, DeckLabel.EVENT_DISCARD}
        self.decks.add(DeckLabel.EVENT_DECK)
        self.player_histories.record_change(sender, changes)

        card = self._draw_from_event_deck(from_top=False)
        self.decks.add(DeckLabel.EVENT_DISCARD)
        self.discard.bottom(card)
        return card

    def spread_terror(self, sender: ServerConnection) -> NeighbourhoodCard | Neighbourhood:
        """Handle spreading terror.

        Args:
            sender: The player taking the action.

        Raises:
            ValueError: Raised if terror is not used in this scenario
            EmptyDeckError: Raised if the deck is empty.

        Returns:
            The event card card that was drawn.

        """
        if not self.has_terror:
            raise ValueError("This scenario has no Terror deck.")
        if len(self.terror) == 0:
            raise EmptyDeckError

        if len(self.discard) > 0:
            location_card = self.discard.peek_bottom_card()
            location = location_card.neighbourhood

            changes: set[Label] = {DeckLabel.TERROR, location}
            self.decks.add(changes)
            self.player_histories.record_change(sender, changes)

            self.nb_deck(location).add_terror(self.terror.draw())
            return location_card

        changes: set[Label] = {DeckLabel.TERROR}
        self.decks.add(changes)
        self.player_histories.record_change(sender, changes)

        location = DEFAULT_TERROR_NEIGHBOURHOOD[self.settings.scenario]
        self.nb_deck(location).add_terror(self.terror.draw())
        return location

    def place_terror(self, neighbourhood: Neighbourhood, sender: ServerConnection) -> None:
        """Handle spreading terror to a specific neighbourhood.

        Args:
            neighbourhood: The neighbourhood to get the card from.
            sender: The player taking the action.

        Raises:
            ValueError: Raised if terror is not used in this scenario
            EmptyDeckError: Raised if the deck is empty.

        """
        if not self.has_terror:
            raise ValueError("This scenario has no Terror deck.")
        if len(self.terror) == 0:
            raise EmptyDeckError

        changes: set[Label] = {DeckLabel.TERROR, neighbourhood}
        self.decks.add(changes)
        self.player_histories.record_change(sender, changes)
        self.nb_deck(neighbourhood).add_terror(self.terror.draw())

    def spread_clue(self, sender: ServerConnection) -> NeighbourhoodCard:
        """Handle spreading a clue.

        Args:
            sender: The player taking the action.

        Raises:
            EmptyDeckError: Raised if the deck is empty.

        Returns:
            The neighbourhood card that was shuffled.

        """
        changes: set[Label] = {DeckLabel.EVENT_DECK}
        self.decks.add(DeckLabel.EVENT_DECK)

        try:
            card = self._draw_from_event_deck()
        except EmptyDeckError:
            changes.add(DeckLabel.EVENT_DISCARD)
            self.player_histories.record_change(sender, changes)
            raise
        changes.add(card.neighbourhood)
        self.decks.add(card.neighbourhood)
        self.player_histories.record_change(sender, changes)
        self.nb_deck(card.neighbourhood).shuffle_into_top_three(card)
        return card

    def gate_burst(self, sender: ServerConnection) -> NeighbourhoodCard | None:
        """Handle a gate burst.

        Args:
            sender: The player taking the action.

        Raises:
            EmptyDeckError: Raised if the deck is empty.

        Returns:
            The card that was drawn

        """
        changes: set[Label] = {DeckLabel.EVENT_DECK, DeckLabel.EVENT_DISCARD}
        self.decks.add(changes)
        self.player_histories.record_change(sender, changes)
        card = self._draw_from_event_deck()
        self.event_deck.shuffle_discard(self.discard)
        self.discard.clear()
        return card

    def draw_headline(self, sender: ServerConnection) -> HeadlineCard:
        """Handle a headline.

        Args:
            sender: The player taking the action.

        Raises:
            EmptyDeckError: Raised if the deck is empty.

        Returns:
            The card that was drawn

        """
        changes: set[Label] = {DeckLabel.HEADLINE}
        self.decks.add(DeckLabel.HEADLINE)

        card = self.headline.draw()
        if card.is_rumor:
            changes.add(DeckLabel.RUMOR)
            self.decks.add(DeckLabel.RUMOR)
            self.rumor.clear()
            self.rumor.append(card)

        self.player_histories.record_change(sender, changes)
        return card

    def clear_rumor(self, sender: ServerConnection) -> None:
        """Clear the current rumor.

        Args:
            sender: The player who is doing the action.

        """
        changes: set[Label] = {DeckLabel.RUMOR}
        self.decks.add(DeckLabel.RUMOR)
        self.player_histories.record_change(sender, changes)
        self.rumor.clear()

    def modify_counter_on_rumor(self, modification: int, sender: ServerConnection) -> None:
        """Add or remove counters from the rumor.

        Args:
            modification: The number of counters to change.
            sender: The player taking the action.

        """
        changes: set[Label] = {DeckLabel.RUMOR}
        self.decks.add(changes)
        self.player_histories.record_change(sender, changes)
        self.rumor[0].counters = max(0, self.rumor[0].counters + modification)

    def get_archive(self) -> list[dict[str, Any]]:
        """Return the whole archive.

        Returns:
            The archive.

        """
        return sorted(
            [card.to_dict(state=CardViewState.ARCHIVE) for card in self.archive.values()],
            key=lambda x: x["number"],
        )

    def get_codex(self) -> list[dict[str, Any]]:
        """Return the whole codex.

        Returns:
            The codex.

        """
        result: list[dict[str, Any]] = []
        for card in self.codex.values():
            state = CardViewState.UN_FLIPPED_CODEX if not card.is_flipped else CardViewState.FLIPPED_CODEX
            result.append(card.to_dict(state=state))

        return sorted(result, key=lambda x: x["number"])

    def add_from_archive(self, number: int, sender: ServerConnection) -> None:
        """Move a card out of the archive.

        Args:
            number: The codex card number.
            sender: The player taking the action.

        Raises:
            ValueError: Raised if that number isn't available to be moved.

        """
        if number not in self.archive:
            raise ValueError("Invalid archive card number to add to codex.")

        changes: set[Label] = {DeckLabel.ARCHIVE}
        self.decks.add(DeckLabel.ARCHIVE)

        card = self.archive.get_card(number)
        if not isinstance(card, CodexNeighbourhoodCard):
            changes.add(DeckLabel.CODEX)
            self.decks.add(DeckLabel.CODEX)
            self.player_histories.record_change(sender, changes)
            self.codex.add_card(card)
            return

        changes.add(card.neighbourhood)
        self.decks.add(card.neighbourhood)
        self.player_histories.record_change(sender, changes)

        if card.can_attach:
            self.nb_deck(card.neighbourhood).attach_codex_card(card)
        elif card.is_encounter:
            if card.number in CODEX_SHUFFLE_ENCOUNTERS:
                self.nb_deck(card.neighbourhood).shuffle_into_top_three(card)
            elif card.number in CODEX_TOP_ENCOUNTERS:
                self.nb_deck(card.neighbourhood).top(card)
            # TODO: handle card 147-149, see card 142 for instructions

    def return_to_archive(self, number: int, sender: ServerConnection) -> None:
        """Move a card back to the archive.

        Args:
            number: The codex card number.
            sender: The player taking the action.

        Raises:
            ValueError: Raised if that number isn't available to be moved.

        """
        if number in self.decks.get(DeckLabel.CODEX):
            changes: set[Label] = {DeckLabel.CODEX, DeckLabel.ARCHIVE}
            self.decks.add(changes)
            self.player_histories.record_change(sender, changes)
            card = self.decks.get(DeckLabel.CODEX).get_card(number)
            card.counters = 0
            card.is_flipped = False
            self.decks.get(DeckLabel.ARCHIVE).add_card(card)
            return
        for neighbourhood in self.neighbourhoods:
            if self.decks.get(neighbourhood).has_codex(number):
                changes: set[Label] = {neighbourhood, DeckLabel.ARCHIVE}
                self.decks.add(changes)
                self.player_histories.record_change(sender, changes)
                self._detach_codex_card(neighbourhood)
                return
        raise ValueError("Invalid codex card number to return to archive.")

    def modify_counter_on_codex(self, number: int, modification: int, sender: ServerConnection) -> None:
        """Modify counters on a codex card.

        Args:
            number: The codex card number.
            modification: The change to the number of counters.
            sender: The player taking the action.

        Raises:
            ValueError: Raised if that number isn't available to be moved.

        """
        if number in self.codex:
            changes: set[Label] = {DeckLabel.CODEX}
            self.decks.add(changes)
            self.player_histories.record_change(sender, changes)
            self.codex[number].counters = max(0, self.codex[number].counters + modification)
            return
        for neighbourhood in self.neighbourhoods:
            if self.nb_deck(neighbourhood).has_codex(number):
                changes: set[Label] = {neighbourhood}
                self.decks.add(changes)
                self.player_histories.record_change(sender, changes)
                self.nb_deck(neighbourhood).modify_codex_counters(modification)
                return
        raise ValueError("Invalid codex card to add or remove counters.")

    def flip_codex(self, number: int, sender: ServerConnection) -> Card:
        """Flip a codex card.

        Args:
            number: The codex card number.
            sender: The player taking the action.

        Raises:
            ValueError: Raised if that number isn't available to be moved.

        """
        if number in self.codex:
            changes: set[Label] = {DeckLabel.CODEX}
            self.decks.add(changes)
            self.player_histories.record_change(sender, changes)
            self.codex[number].is_flipped = True
            return self.codex[number]
        for neighbourhood in self.neighbourhoods:
            if self.nb_deck(neighbourhood).has_codex(number):
                changes: set[Label] = {neighbourhood}
                self.decks.add(changes)
                self.player_histories.record_change(sender, changes)
                self.nb_deck(neighbourhood).flip_codex()
                return self.nb_deck(neighbourhood).get_codex_card()  # pyright: ignore[reportReturnType]
        raise ValueError("Invalid codex card number to return to archive.")

    def add_neighbourhood(self, neighbourhood: Neighbourhood, sender: ServerConnection) -> int:
        """Add a neighbourhood to the game.

        Args:
            neighbourhood: The neighbourhood to add.
            sender: The player taking the action.

        """
        ##Handle this special case
        if neighbourhood == Neighbourhood.THE_UNDERWORLD:
            self.neighbourhoods.append(Neighbourhood.THE_UNDERWORLD)
            changes: set[Label] = {neighbourhood, DeckLabel.EVENT_DECK, DeckLabel.EVENT_DISCARD}
            self.decks.add(changes)
            self.player_histories.record_change(sender, changes)
            doom_to_add = 0
            for _ in range(4):
                try:
                    self._draw_from_event_deck()
                except EmptyDeckError:
                    doom_to_add += 1
            self.event_deck.__add__(self.later_decks["Event_Decks"][neighbourhood][:2])
            self.event_deck.shuffle()
            self.discard.bottom(self.later_decks["Event_Decks"][neighbourhood][-1])
            self.discard.bottom(self.later_decks["Event_Decks"][neighbourhood][-2])
            self.decks.add_new(neighbourhood, self.later_decks["Neighbourhoods"][neighbourhood])
            del self.later_decks["Neighbourhoods"][neighbourhood]
            del self.later_decks["Event_Decks"][neighbourhood]
            return doom_to_add

        changes: set[Label] = {neighbourhood}
        self.decks.add_new(neighbourhood, self.later_decks["Neighbourhoods"][neighbourhood])
        del self.later_decks["Neighbourhoods"][neighbourhood]
        self.neighbourhoods.append(neighbourhood)

        if neighbourhood in self.later_decks["Event_Decks"]:
            changes.update({DeckLabel.EVENT_DECK, DeckLabel.EVENT_DISCARD})
            self.decks.add({DeckLabel.EVENT_DECK, DeckLabel.EVENT_DISCARD})

            self.event_deck.__add__(self.later_decks["Event_Decks"][neighbourhood])
            self.event_deck.shuffle_discard(self.discard)
            self.discard.clear()
            del self.later_decks["Event_Decks"][neighbourhood]
        self.player_histories.record_change(sender, changes)
        return 0

    def can_undo(self, player: ServerConnection) -> bool:
        """Check to see if a player can undo.

        Args:
            player: The player taking the action.

        Returns:
            True is yes, False otherwise.

        """
        return self.player_histories.can_undo(player)

    def can_redo(self, player: ServerConnection) -> bool:
        """Check to see if a player can undo.

        Args:
            player: The player taking the action.

        Returns:
            True is yes, False otherwise.

        """
        return self.player_histories.can_redo(player)

    def undo(self, player: ServerConnection) -> None:
        """Perform an undo operation.

        Args:
            player: The player taking the action.

        """
        self.decks.undo(self.player_histories.undo(player))

    def redo(self, player: ServerConnection) -> None:
        """Perform an redo operation.

        Args:
            player: The player taking the action.

        """
        self.decks.redo(self.player_histories.redo(player))

    def update_info(self) -> dict[str, Any]:
        """Return the information needed to render the decks screen.

        Returns:
            The information to draw the game screen.

        """
        decks: list[Mapping[str, Any]] = [
            {
                "name": neighbourhood.value,
                "visible_image": self.nb_deck(neighbourhood).card_back,
                "num_cards": len(self.nb_deck(neighbourhood)),
                "has_attached_codex": self.nb_deck(neighbourhood).attached_codex is not None,
                "num_attached_terror": len(self.nb_deck(neighbourhood).attached_terror),
            }
            for neighbourhood in self.neighbourhoods
            if self.nb_deck(neighbourhood) is not None  # pyright: ignore[reportUnnecessaryComparison]
        ]

        decks.extend(
            [
                {
                    "name": "Headlines",
                    "visible_image": self.get_headline_back(),
                    "num_cards": len(self.headline),
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
                    "num_cards": len(self.discard),
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
                    "num_cards": len(self.terror),
                    "has_attached_codex": False,
                    "num_attached_terror": 0,
                }
            )

        if len(self.rumor) > 0:
            decks.append(
                {
                    "name": "Rumor",
                    "visible_image": self.rumor[0].face,
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
        terror_card_back = None if not self.has_terror else self.terror.card_back
        return {
            "Decks": decks,
            "Additional_Decks": future_decks,
            "Uses_Terror": self.has_terror,
            "Terror_Deck_Back": terror_card_back,
        }
