"""Mappings describing what needs what."""

from companion.util_classes import Expansions, Neighbourhood, Scenarios, Terror

SCENARIO_BY_EXPANSION = {
    Scenarios.SHOTS_IN_THE_DARK: Expansions.DEAD_OF_NIGHT,  # Dead of Night
    Scenarios.SILENCE_OF_TSATHOGGUA: Expansions.DEAD_OF_NIGHT,
    Scenarios.DREAMS_OF_RLYEH: Expansions.UNDER_DARK_WAVES,  # Under Dark Waves
    Scenarios.THE_PALE_LANTERN: Expansions.UNDER_DARK_WAVES,
    Scenarios.TYRANTS_OF_RUIN: Expansions.UNDER_DARK_WAVES,
    Scenarios.ITHAQUAS_CHILDREN: Expansions.UNDER_DARK_WAVES,
    Scenarios.THE_DEAD_CRY_OUT: Expansions.SECRETS_OF_THE_ORDER,  # Secrets of the Order
    Scenarios.THE_KEY_AND_THE_GATE: Expansions.SECRETS_OF_THE_ORDER,
    Scenarios.BOUND_TO_SERVE: Expansions.SECRETS_OF_THE_ORDER,
}

HEADLINE_RUMORS: dict[Expansions, list[int]] = {
    Expansions.BASE: [29, 30, 31, 32],
    Expansions.DEAD_OF_NIGHT: [38, 39],
    Expansions.UNDER_DARK_WAVES: [43],
    Expansions.SECRETS_OF_THE_ORDER: [],
}

REQUIRED_CODEX = {
    Scenarios.APPROACH_OF_AZATHOTH: [2, *list(range(3, 10))],
    Scenarios.FEAST_FOR_UMORDHOTH: [1, *list(range(10, 20))],
    Scenarios.VEIL_OF_TWILIGHT: [2, *list(range(20, 29))],
    Scenarios.ECHOES_OF_THE_DEEP: [2, *list(range(29, 41))],
    Scenarios.SHOTS_IN_THE_DARK: [1, *list(range(41, 53))],
    Scenarios.SILENCE_OF_TSATHOGGUA: [2, *list(range(53, 60))],
    Scenarios.TYRANTS_OF_RUIN: list(range(61, 76)),
    Scenarios.THE_PALE_LANTERN: [2, *list(range(76, 91))],
    Scenarios.ITHAQUAS_CHILDREN: [61, *list(range(91, 106))],
    Scenarios.DREAMS_OF_RLYEH: [2, *list(range(106, 121))],
    Scenarios.BOUND_TO_SERVE: [2, *list(range(121, 135))],
    Scenarios.THE_DEAD_CRY_OUT: [1, *list(range(135, 150))],
    Scenarios.THE_KEY_AND_THE_GATE: [2, *list(range(150, 165))],
}

DEFAULT_TERROR_NEIGHBOURHOOD = {
    Scenarios.TYRANTS_OF_RUIN: Neighbourhood.INNSMOUTH_SHORE,
    Scenarios.ITHAQUAS_CHILDREN: Neighbourhood.EASTTOWN,
}

SCENARIO_TERROR_MAP = {
    Scenarios.TYRANTS_OF_RUIN: Terror.FEEDING_FRENZY,
    Scenarios.ITHAQUAS_CHILDREN: Terror.FROZEN_CITY,
}

CODEX_ITEMS = [68, 69, 70, 90]
CODEX_MONSTERS = [19, 28, 39, 40, 60, 74, 75, 89, 104, 105, 145, 146]
CODEX_ATTACHABLE = [32, 33, 34, 35, 55, 56]
CODEX_ENCOUNTERS = [13, 14, 15, 16, 17, 147, 148, 149, 161, 162, 163, 164, 168]
CODEX_SHUFFLE_ENCOUNTERS = [13, 14, 15, 16, 17]
CODEX_TOP_ENCOUNTERS = [161, 162, 163, 164, 168]
CODEX_NEIGHBOURHOODS = {
    13: Neighbourhood.DOWNTOWN,
    14: Neighbourhood.EASTTOWN,
    15: Neighbourhood.RIVERTOWN,
    16: Neighbourhood.UPTOWN,
    17: Neighbourhood.SOUTHSIDE,
    32: Neighbourhood.RIVERTOWN,
    33: Neighbourhood.DOWNTOWN,
    34: Neighbourhood.NORTHSIDE,
    35: Neighbourhood.MISKATONIC_UNIVERSITY,
    55: Neighbourhood.NORTHSIDE,
    56: Neighbourhood.UPTOWN,
    147: Neighbourhood.THE_UNDERWORLD,
    148: Neighbourhood.THE_UNDERWORLD,
    149: Neighbourhood.THE_UNDERWORLD,
    161: Neighbourhood.EASTTOWN,
    162: Neighbourhood.FRENCH_HILL,
    163: Neighbourhood.MERCHANT_DISTRICT,
    164: Neighbourhood.RIVERTOWN,
    168: Neighbourhood.UPTOWN,
}


REQUIRED_NEIGHBOURHOODS = {
    Scenarios.APPROACH_OF_AZATHOTH: {
        "start": [
            Neighbourhood.NORTHSIDE,
            Neighbourhood.DOWNTOWN,
            Neighbourhood.EASTTOWN,
            Neighbourhood.MERCHANT_DISTRICT,
            Neighbourhood.RIVERTOWN,
            Neighbourhood.THE_STREETS,
            Neighbourhood.TEMPORAL_FISSURE,
        ],
    },
    Scenarios.FEAST_FOR_UMORDHOTH: {
        "start": [
            Neighbourhood.DOWNTOWN,
            Neighbourhood.EASTTOWN,
            Neighbourhood.RIVERTOWN,
            Neighbourhood.UPTOWN,
            Neighbourhood.SOUTHSIDE,
            Neighbourhood.THE_STREETS,
        ],
    },
    Scenarios.VEIL_OF_TWILIGHT: {
        "start": [
            Neighbourhood.NORTHSIDE,
            Neighbourhood.RIVERTOWN,
            Neighbourhood.SOUTHSIDE,
            Neighbourhood.MISKATONIC_UNIVERSITY,
            Neighbourhood.UPTOWN,
            Neighbourhood.THE_STREETS,
            Neighbourhood.FRACTURED_REALITY,
        ],
    },
    Scenarios.ECHOES_OF_THE_DEEP: {
        "start": [
            Neighbourhood.MISKATONIC_UNIVERSITY,
            Neighbourhood.MERCHANT_DISTRICT,
            Neighbourhood.NORTHSIDE,
            Neighbourhood.RIVERTOWN,
            Neighbourhood.DOWNTOWN,
            Neighbourhood.THE_STREETS,
            Neighbourhood.NIGHTMARE_BREACH,
        ],
    },
    Scenarios.SHOTS_IN_THE_DARK: {
        "start": [
            Neighbourhood.DOWNTOWN,
            Neighbourhood.EASTTOWN,
            Neighbourhood.RIVERTOWN,
            Neighbourhood.NORTHSIDE,
            Neighbourhood.MERCHANT_DISTRICT,
            Neighbourhood.THE_STREETS,
        ],
    },
    Scenarios.SILENCE_OF_TSATHOGGUA: {
        "start": [
            Neighbourhood.NORTHSIDE,
            Neighbourhood.MERCHANT_DISTRICT,
            Neighbourhood.RIVERTOWN,
            Neighbourhood.MISKATONIC_UNIVERSITY,
            Neighbourhood.UPTOWN,
            Neighbourhood.THE_STREETS,
            Neighbourhood.YUGGOTH_EMERGENT,
        ],
    },
    Scenarios.DREAMS_OF_RLYEH: {
        "start": [
            Neighbourhood.MISKATONIC_UNIVERSITY,
            Neighbourhood.RIVERTOWN,
            Neighbourhood.UPTOWN,
            Neighbourhood.SOUTHSIDE,
            Neighbourhood.THE_STREETS,
            Neighbourhood.TRAVEL_ROUTES,
        ],
        "later": [
            Neighbourhood.CENTRAL_KINGSPORT,
            Neighbourhood.KINGSPORT_HARBOR,
            Neighbourhood.INNSMOUTH_SHORE,
            Neighbourhood.INNSMOUTH_VILLAGE,
        ],
    },
    Scenarios.THE_PALE_LANTERN: {
        "start": [
            Neighbourhood.DOWNTOWN,
            Neighbourhood.MISKATONIC_UNIVERSITY,
            Neighbourhood.UPTOWN,
            Neighbourhood.CENTRAL_KINGSPORT,
            Neighbourhood.KINGSPORT_HARBOR,
            Neighbourhood.THE_STREETS,
            Neighbourhood.TRAVEL_ROUTES,
            Neighbourhood.STRANGE_HIGH_HOUSE,
            Neighbourhood.VISIONS_OF_THE_MOON,
        ],
    },
    Scenarios.TYRANTS_OF_RUIN: {
        "start": [
            Neighbourhood.NORTHSIDE,
            Neighbourhood.EASTTOWN,
            Neighbourhood.MISKATONIC_UNIVERSITY,
            Neighbourhood.SOUTHSIDE,
            Neighbourhood.INNSMOUTH_SHORE,
            Neighbourhood.INNSMOUTH_VILLAGE,
            Neighbourhood.THE_STREETS,
            Neighbourhood.TRAVEL_ROUTES,
            Neighbourhood.DEVIL_REEF,
        ],
    },
    Scenarios.ITHAQUAS_CHILDREN: {
        "start": [
            Neighbourhood.DOWNTOWN,
            Neighbourhood.NORTHSIDE,
            Neighbourhood.RIVERTOWN,
            Neighbourhood.EASTTOWN,
            Neighbourhood.SOUTHSIDE,
            Neighbourhood.INNSMOUTH_SHORE,
            Neighbourhood.CENTRAL_KINGSPORT,
            Neighbourhood.THE_STREETS,
            Neighbourhood.TRAVEL_ROUTES,
        ],
    },
    Scenarios.THE_DEAD_CRY_OUT: {
        "start": [
            Neighbourhood.NORTHSIDE,
            Neighbourhood.EASTTOWN,
            Neighbourhood.MISKATONIC_UNIVERSITY,
            Neighbourhood.THE_UNDERWORLD,
            Neighbourhood.FRENCH_HILL,
            Neighbourhood.UPTOWN,
            Neighbourhood.SOUTHSIDE,
            Neighbourhood.THE_STREETS,
            Neighbourhood.THRESHOLDS,
        ],
    },
    Scenarios.THE_KEY_AND_THE_GATE: {
        "start": [
            Neighbourhood.EASTTOWN,
            Neighbourhood.FRENCH_HILL,
            Neighbourhood.UPTOWN,
            Neighbourhood.RIVERTOWN,
            Neighbourhood.MERCHANT_DISTRICT,
            Neighbourhood.THE_STREETS,
            Neighbourhood.THE_UNNAMABLE,
            Neighbourhood.FRACTURED_REALITY,
        ],
        "later": [
            Neighbourhood.THRESHOLDS,
            Neighbourhood.THE_UNDERWORLD,
        ],
    },
    Scenarios.BOUND_TO_SERVE: {
        "start": [
            Neighbourhood.DOWNTOWN,
            Neighbourhood.MERCHANT_DISTRICT,
            Neighbourhood.RIVERTOWN,
            Neighbourhood.FRENCH_HILL,
            Neighbourhood.UPTOWN,
            Neighbourhood.SOUTHSIDE,
            Neighbourhood.THE_STREETS,
            Neighbourhood.WITCH_HOUSE,
            Neighbourhood.LOST_SOULS,
        ],
    },
}
