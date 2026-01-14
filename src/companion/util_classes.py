"""Utility classes and enums."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Scenarios(str, Enum):
    """The games scenarios."""

    # Base Game
    APPROACH_OF_AZATHOTH = "Approach of Azathoth"
    FEAST_FOR_UMORDHOTH = "Feast for Umordhoth"
    VEIL_OF_TWILIGHT = "Veil of Twilight"
    ECHOES_OF_THE_DEEP = "Echoes of the Deep"

    # Dead of Night Expansion
    SHOTS_IN_THE_DARK = "Shots in the Dark"
    SILENCE_OF_TSATHOGGUA = "Silence of Tsathoggua"

    # Under Dark Waves Expansion
    DREAMS_OF_RLYEH = "Dreams of R'lyeh"
    THE_PALE_LANTERN = "The Pale Lantern"
    TYRANTS_OF_RUIN = "Tyrants of Ruin"
    ITHAQUAS_CHILDREN = "Ithaqua's Children"

    # Secrets of the Order Expansion
    THE_DEAD_CRY_OUT = "The Dead Cry Out"
    THE_KEY_AND_THE_GATE = "The Key and the Gate"
    BOUND_TO_SERVE = "Bound to Serve"


class Expansions(int, Enum):
    """The games expansions."""

    BASE = 0
    DEAD_OF_NIGHT = 1
    UNDER_DARK_WAVES = 2
    SECRETS_OF_THE_ORDER = 4


class Terror(str, Enum):
    """The games terror."""

    FEEDING_FRENZY = "Feeding Frenzy"
    FROZEN_CITY = "Frozen City"


class Neighbourhood(str, Enum):
    """The games neighbourhoods."""

    ##### Base Game #####

    # Neighbourhood
    DOWNTOWN = "Downtown"
    EASTTOWN = "Easttown"
    MERCHANT_DISTRICT = "Merchant District"
    MISKATONIC_UNIVERSITY = "Miskatonic University"
    NORTHSIDE = "Northside"
    RIVERTOWN = "Rivertown"
    SOUTHSIDE = "Southside"
    UPTOWN = "Uptown"

    # Between Neighbourhood
    THE_STREETS = "The Streets"

    ##### Dead of Night Expansion #####
    # None

    ##### Under Dark Waves Expansion #####

    # Neighbourhood
    CENTRAL_KINGSPORT = "Central Kingsport"
    INNSMOUTH_SHORE = "Innsmouth Shore"
    INNSMOUTH_VILLAGE = "Innsmouth Village"
    KINGSPORT_HARBOR = "Kingsport Harbor"

    # Between Neighbourhood
    TRAVEL_ROUTES = "Travel Routes"

    # Mysteries
    DEVIL_REEF = "Devil Reef"
    STRANGE_HIGH_HOUSE = "Strange High House"

    ##### Secrets of the Order Expansion #####

    # Neighbourhoods
    FRENCH_HILL = "French Hill"
    THE_UNDERWORLD = "The Underworld"

    # Between Neighbourhood
    THRESHOLDS = "Thresholds"

    # Mysteries
    THE_UNNAMABLE = "The Unnamable"
    WITCH_HOUSE = "Witch House"

    ##### Anomalies are essentially neighbourhoods #####

    FRACTURED_REALITY = "Fractured Reality"
    LOST_SOULS = "Lost Souls"
    NIGHTMARE_BREACH = "Nightmare Breach"
    TEMPORAL_FISSURE = "Temporal Fissure"
    VISIONS_OF_THE_MOON = "Visions of the Moon"
    YUGGOTH_EMERGENT = "Yuggoth Emergent"


@dataclass
class Card:
    """A basic card."""

    face: str
    back: str

    def to_dict(
        self, needs_resolving: bool = False, identifier: str = "", in_codex: bool = False, from_deck: bool = False
    ) -> dict[str, Any]:
        """Convert an instance of a Card or a subclass into something that can be sent as a message.

        Args:
            needs_resolving: True if this is an event card drawn from a neighbourhood deck, False otherwise.

        Returns:
            A dict of info needed for viewing.

        """
        return {
            "face": self.face.lower(),
            "back": self.back.lower(),
            "needs_resolving": needs_resolving,  # whether to enable the x, pass and fail buttons
            "identifier": identifier,  # for the response when resolving
            "number": getattr(self, "number", 0),
            "is_codex": isinstance(self, CodexCard),  # whether to allow to swap between front and back
            "is_flipped": getattr(self, "is_flipped", False),  # which side of the codex card to show
            "in_codex": in_codex,
            "from_deck": from_deck,
        }


@dataclass
class HeadlineCard(Card):
    """A headline card."""

    is_rumor: bool


@dataclass
class NeighbourhoodCard(Card):
    """A neighbourhood card."""

    neighbourhood: Neighbourhood
    is_event: bool


@dataclass
class CodexCard(Card):
    """A codex card."""

    number: int
    is_item: bool
    is_flipped: bool
    is_monster: bool
    can_attach: bool
    is_encounter: bool


@dataclass
class CodexNeighbourhoodCard(CodexCard, NeighbourhoodCard):
    """A codex card associated with a neighbourhood."""

    def __init__(
        self, /, face: str, back: str, number: int, can_attach: bool, is_encounter: bool, neighbourhood: Neighbourhood
    ):
        super().__init__(
            face=face,
            back=back,
            number=number,
            is_item=False,
            is_flipped=False,
            is_monster=False,
            can_attach=can_attach,
            is_encounter=is_encounter,
        )
        self.neighbourhood = neighbourhood
        self.is_event = False


@dataclass
class GameSettings:
    """The game settings."""

    scenario: Scenarios
    expansions: int
