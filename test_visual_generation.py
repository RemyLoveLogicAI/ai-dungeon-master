"""Tests for the Real-time Scene Visual Generation Pipeline."""

from fastapi.testclient import TestClient

from engine.api_server import app
from engine.scene_visuals import BIOME_VISUAL_THEMES, render_scene_illustration
from engine.story_engine import StoryEngine


def test_render_scene_illustration_all_biomes():
    for biome in BIOME_VISUAL_THEMES:
        illustration = render_scene_illustration(
            location_name=f"Sanctum of {biome}",
            biome=biome,
            description="Ancient monoliths jut out from the mist.",
            tension_level=45,
        )
        assert illustration.location_name == f"Sanctum of {biome}"
        assert illustration.biome == biome
        assert len(illustration.art_prompt) > 30
        assert "<svg" in illustration.svg_data
        assert "</svg>" in illustration.svg_data
        assert "viewBox=\"0 0 1200 675\"" in illustration.svg_data
        assert illustration.image_url.startswith("/api/scene/image/")


def test_render_scene_illustration_unknown_biome_fallback():
    illustration = render_scene_illustration(
        location_name="Void Nexus",
        biome="Unknown Alien Expanse",
        description="A rift in space and time.",
        tension_level=80,
    )
    assert illustration.biome == "Unknown Alien Expanse"
    assert "<svg" in illustration.svg_data
    assert illustration.mood == BIOME_VISUAL_THEMES["Obsidian Crags"]["mood"]


def test_story_engine_attaches_scene_illustration_on_process_turn():
    engine = StoryEngine(enable_dynamic_narrative=False)
    ui_package = engine.process_turn("investigate the eerie monoliths")
    assert ui_package.scene_illustration is not None
    assert ui_package.scene_illustration.location_name == engine.get_current_location().name
    assert ui_package.scene_illustration.biome == engine.get_current_location().biome
    assert "<svg" in ui_package.scene_illustration.svg_data


def test_api_server_scene_endpoints():
    client = TestClient(app)
    
    # 1. Current scene illustration endpoint
    res = client.get("/api/scene/current")
    assert res.status_code == 200
    data = res.json()
    assert "illustration" in data
    assert "art_prompt" in data["illustration"]
    assert "svg_data" in data["illustration"]
    assert "<svg" in data["illustration"]["svg_data"]

    # 2. Scene image SVG endpoint
    res_img = client.get("/api/scene/image/Sunken%20Crypts")
    assert res_img.status_code == 200
    assert "image/svg+xml" in res_img.headers.get("content-type", "")
    assert "<svg" in res_img.text
    assert "SUNKEN CRYPTS" in res_img.text
