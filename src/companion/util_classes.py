"""Utility classes and enums."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


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

    DEAD_OF_NIGHT = 1
    UNDER_DARK_WAVES = 2
    SECRETS_OF_THE_ORDER = 4


class Anomalies(str, Enum):
    """The games anomalies."""

    FRACTURED_REALITY = "Fractured Reality"
    LOST_SOULS = "Lost Souls"
    NIGHTMARE_BREACH = "Nightmare Breach"
    TEMPORAL_FISSURE = "Temporal Fissure"
    VISIONS_OF_THE_MOON = "Visions of the Moon"
    YUGGOTH_EMERGENT = "Yuggoth Emergent"


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

    # Neighbourhood
    SHOTS_IN_THE_DARK = "SHOTS_IN_THE_DARK"
    SILENCE_OF_TSATHOGGUA = "SILENCE_OF_TSATHOGGUA"

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


@dataclass
class Card:
    """A basic card."""

    face: Path


@dataclass
class HeadlineCard(Card):
    """A headline card."""

    is_rumor: bool


@dataclass
class NeighbourhoodCard(Card):
    """A neighbourhood card."""

    back: Path
    neighbourhood: Neighbourhood
    is_event: bool


@dataclass
class CodexCard(Card):
    """A codex card."""

    back: Path
    number: int = -1
    is_item: bool = False
    is_flipped: bool = False
    is_monster: bool = False
    can_attach: bool = False
    is_encounter: bool = False


@dataclass
class CodexNeighbourhoodCard(CodexCard, NeighbourhoodCard):
    """A codex card associated with a neighbourhood."""

    is_item: bool = False
    is_flipped: bool = False
    is_monster: bool = False
    is_codex: bool = True
    is_event: bool = False
