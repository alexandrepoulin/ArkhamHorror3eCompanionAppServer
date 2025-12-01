"""The service."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import TypeAdapter

from companion.base_models import GameSettings
from companion.game_state import GameState

app = FastAPI()

GameSettings.model_rebuild()
adapter = TypeAdapter(GameSettings)


@app.post("/new_game")
async def new_game(settings: GameSettings) -> None:
    """Create a new game.
    
    \f

    Args:
        settings: The game settings to use.
    """
    app.state.game_state = GameState(settings=settings)
