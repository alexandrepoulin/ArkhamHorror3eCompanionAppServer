"""Base models for the app."""

from __future__ import annotations

from typing import Annotated, Self

from pydantic import BaseModel, Field, model_validator

from companion.mappings import SCENARIO_BY_EXPANSION
from companion.util_classes import Scenarios

ScenarioType = Annotated[Scenarios, Field(..., description="Valid scenario")]
ExpansionType = Annotated[int, Field(..., ge=0, le=7, description="Expansion bit flag")]


class GameSettings(BaseModel):
    """The model to be passed in at the start of the game."""

    scenario: Scenarios = Field(..., description="Valid scenario")
    expansions: int = Field(..., ge=0, le=7, description="Expansion bit flag")

    @model_validator(mode="after")
    def validate_item_type_for_level(self) -> Self:
        """Validate the settings.

        Raises:
            ValueError: raised if trying to select a scenario without having that expansion selected.

        Returns:
            Just returns itself.

        """
        if not (self.expansions & SCENARIO_BY_EXPANSION[self.scenario]):
            raise ValueError("Invalid Scenario and expansion selection.")
        return self

    model_config = {"from_attributes": True}
