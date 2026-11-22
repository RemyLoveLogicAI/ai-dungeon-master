"""
engine/character_service.py
Bridges campaign_core's starter-character builder and persistence store to the
rest of the engine: creates a persisted character for a player/session and
loads it back by campaign id. This is the callable contract the API layer and
StoryEngine wire into; it holds no transport or framework concerns itself.
"""

from __future__ import annotations

from typing import Any

from campaign_core import CampaignStore, NotFoundError, build_starter_character


def create_character(store: CampaignStore, data: dict[str, Any]) -> dict[str, Any]:
    """Build a starter character sheet and persist it as a new campaign.

    Returns the created campaign state: its id/revision plus the character
    sheet under state["character"].
    """
    character = build_starter_character(data)
    return store.create({
        "title": f"{character['name']}'s Campaign",
        "phase": "onboarding",
        "character": character,
    })


def get_current_character(store: CampaignStore, campaign_id: str) -> dict[str, Any] | None:
    """Fetch the character sheet for a campaign, or None if the id is unknown."""
    try:
        state = store.get(campaign_id)
    except NotFoundError:
        return None
    return state.get("character")


def delete_character(store: CampaignStore, campaign_id: str) -> bool:
    """Delete a campaign and its character. Returns False if the id is unknown."""
    try:
        store.delete(campaign_id)
    except NotFoundError:
        return False
    return True
