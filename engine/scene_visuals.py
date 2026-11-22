"""
engine/scene_visuals.py
Real-time Visual Generation Pipeline for Aegis AI Dungeon Master.
Generates cinematic dark-fantasy scene illustrations, visual prompts, and procedural vector art
for biomes, locations, and narrative transitions.
"""

from __future__ import annotations

import html
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class SceneIllustration:
    location_name: str
    biome: str
    art_prompt: str
    image_url: str
    mood: str
    lighting: str
    composition_style: str
    svg_data: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Biome-specific visual themes (colors, ambient lighting, mood, SVG layers)
BIOME_VISUAL_THEMES: dict[str, dict[str, Any]] = {
    "Obsidian Crags": {
        "mood": "Volcanic, ominous, primordial",
        "lighting": "Violaceous aurora and pulsating magma fissures",
        "sky_top": "#080312",
        "sky_bottom": "#240a33",
        "accent_glow": "#9333ea",
        "fissure_color": "#dc2626",
        "fog_color": "#4c1d95",
        "silhouette_dark": "#050209",
        "silhouette_mid": "#130822",
        "silhouette_light": "#25123e",
        "accent_particles": "#c084fc",
        "symbol": "crags",
    },
    "Sunken Crypts": {
        "mood": "Subterranean, spectral, claustrophobic",
        "lighting": "Pale jade bioluminescence reflecting off stagnant black water",
        "sky_top": "#030c0c",
        "sky_bottom": "#0a2625",
        "accent_glow": "#10b981",
        "fissure_color": "#059669",
        "fog_color": "#064e3b",
        "silhouette_dark": "#020707",
        "silhouette_mid": "#081c1c",
        "silhouette_light": "#0f3635",
        "accent_particles": "#34d399",
        "symbol": "crypt",
    },
    "Gargoyle Roost": {
        "mood": "Vertiginous, tempestuous, stone-cold",
        "lighting": "Lightning flashes piercing slate-grey gale clouds",
        "sky_top": "#060913",
        "sky_bottom": "#132338",
        "accent_glow": "#38bdf8",
        "fissure_color": "#0284c7",
        "fog_color": "#1e3a8a",
        "silhouette_dark": "#04070d",
        "silhouette_mid": "#0b1526",
        "silhouette_light": "#172b4d",
        "accent_particles": "#7dd3fc",
        "symbol": "gargoyle",
    },
    "Whispering Fen": {
        "mood": "Melancholic, spectral, damp",
        "lighting": "Will-o'-the-wisps weaving through swirling emerald mist",
        "sky_top": "#050e09",
        "sky_bottom": "#0f2617",
        "accent_glow": "#22c55e",
        "fissure_color": "#15803d",
        "fog_color": "#14532d",
        "silhouette_dark": "#020805",
        "silhouette_mid": "#091e13",
        "silhouette_light": "#143724",
        "accent_particles": "#86efac",
        "symbol": "fen",
    },
    "Astral Observatory": {
        "mood": "Transcendent, arcane, eternal",
        "lighting": "Cosmic stellar nebula and spinning golden celestial rings",
        "sky_top": "#070417",
        "sky_bottom": "#1c1145",
        "accent_glow": "#eab308",
        "fissure_color": "#a855f7",
        "fog_color": "#3b0764",
        "silhouette_dark": "#04020f",
        "silhouette_mid": "#10092c",
        "silhouette_light": "#241854",
        "accent_particles": "#fde047",
        "symbol": "astral",
    },
    "Ashen Citadel": {
        "mood": "Imposing, scorched, militaristic",
        "lighting": "Smoldering fortress braziers and sulfurous forge-glow",
        "sky_top": "#120505",
        "sky_bottom": "#381010",
        "accent_glow": "#f97316",
        "fissure_color": "#ea580c",
        "fog_color": "#7c2d12",
        "silhouette_dark": "#090303",
        "silhouette_mid": "#220a0a",
        "silhouette_light": "#431414",
        "accent_particles": "#fdba74",
        "symbol": "citadel",
    },
    "Tavern of the Broken Blade": {
        "mood": "Warm, hearth-lit, conspiratorial",
        "lighting": "Flickering amber hearth flames and golden lantern glints",
        "sky_top": "#110904",
        "sky_bottom": "#2d1607",
        "accent_glow": "#f59e0b",
        "fissure_color": "#d97706",
        "fog_color": "#78350f",
        "silhouette_dark": "#090401",
        "silhouette_mid": "#1f0f04",
        "silhouette_light": "#3b1e09",
        "accent_particles": "#fcd34d",
        "symbol": "hearth",
    },
}

DEFAULT_THEME = BIOME_VISUAL_THEMES["Obsidian Crags"]


def _generate_procedural_svg(
    location_name: str,
    biome: str,
    theme: dict[str, Any],
    tension: int,
) -> str:
    """Generate a responsive 16:9 cinematic dark-fantasy vector illustration."""
    # Tension modulates rune glow opacity and storm density
    glow_intensity = min(1.0, max(0.3, tension / 100.0 + 0.3))
    
    esc_loc = html.escape(location_name)
    esc_biome = html.escape(biome)
    
    # Procedural silhouette elements based on biome symbol
    symbol = theme.get("symbol", "crags")
    
    if symbol == "crypt":
        focal_elements = f"""
        <!-- Submerged Catacomb Arches & Sarcophagi -->
        <path d="M 150 675 L 150 340 Q 250 240 350 340 L 350 675 Z" fill="{theme['silhouette_mid']}" opacity="0.95" />
        <path d="M 850 675 L 850 340 Q 950 240 1050 340 L 1050 675 Z" fill="{theme['silhouette_mid']}" opacity="0.95" />
        <path d="M 450 675 L 450 280 Q 600 160 750 280 L 750 675 Z" fill="{theme['silhouette_dark']}" />
        <!-- Glowing Vault Runes -->
        <circle cx="600" cy="220" r="32" fill="none" stroke="{theme['accent_glow']}" stroke-width="3" opacity="{glow_intensity}" />
        <polygon points="600,195 620,235 580,235" fill="none" stroke="{theme['accent_glow']}" stroke-width="2" opacity="{glow_intensity}" />
        <!-- Water Reflection Fissure -->
        <ellipse cx="600" cy="580" rx="380" ry="24" fill="{theme['fissure_color']}" opacity="0.3" filter="url(#glow-filter)" />
        """
    elif symbol == "gargoyle":
        focal_elements = f"""
        <!-- High Spires & Perched Sentinels -->
        <polygon points="120,675 220,180 320,675" fill="{theme['silhouette_light']}" />
        <polygon points="880,675 980,180 1080,675" fill="{theme['silhouette_light']}" />
        <polygon points="460,675 600,140 740,675" fill="{theme['silhouette_dark']}" />
        <!-- Stone Gargoyle Silhouette -->
        <path d="M 590 140 Q 600 110 610 140 Q 640 135 625 155 Q 600 165 590 140 Z" fill="{theme['accent_glow']}" opacity="{glow_intensity * 0.8}" />
        <!-- Lightning Arcs -->
        <polyline points="590,40 610,90 595,120 620,160" fill="none" stroke="{theme['accent_glow']}" stroke-width="2" opacity="{glow_intensity * 0.7}" filter="url(#glow-filter)" />
        """
    elif symbol == "astral":
        focal_elements = f"""
        <!-- Astral Rings & Floating Shards -->
        <ellipse cx="600" cy="260" rx="340" ry="85" fill="none" stroke="{theme['accent_glow']}" stroke-width="3" stroke-dasharray="14 8" opacity="{glow_intensity}" transform="rotate(-15 600 260)" />
        <ellipse cx="600" cy="260" rx="220" ry="55" fill="none" stroke="{theme['fissure_color']}" stroke-width="2" opacity="{glow_intensity * 0.8}" transform="rotate(20 600 260)" />
        <polygon points="560,320 600,180 640,320 600,420" fill="{theme['silhouette_dark']}" stroke="{theme['accent_glow']}" stroke-width="2" />
        <circle cx="600" cy="280" r="18" fill="{theme['accent_glow']}" filter="url(#glow-filter)" opacity="{glow_intensity}" />
        """
    elif symbol == "citadel":
        focal_elements = f"""
        <!-- Fortress Bastions & Iron Blast-Walls -->
        <rect x="250" y="320" width="160" height="355" fill="{theme['silhouette_mid']}" />
        <rect x="790" y="320" width="160" height="355" fill="{theme['silhouette_mid']}" />
        <polygon points="230,320 330,220 430,320" fill="{theme['silhouette_dark']}" />
        <polygon points="770,320 870,220 970,320" fill="{theme['silhouette_dark']}" />
        <rect x="410" y="280" width="380" height="395" fill="{theme['silhouette_dark']}" />
        <polygon points="380,280 600,160 820,280" fill="{theme['silhouette_dark']}" />
        <!-- Smoldering Forge Gate -->
        <rect x="540" y="490" width="120" height="185" rx="60" fill="{theme['fissure_color']}" opacity="{glow_intensity}" filter="url(#glow-filter)" />
        """
    elif symbol == "fen":
        focal_elements = f"""
        <!-- Spectral Marsh Reeds & Gnarled Trees -->
        <path d="M 180 675 Q 220 450 160 300 Q 240 380 280 675 Z" fill="{theme['silhouette_dark']}" />
        <path d="M 980 675 Q 940 450 1020 300 Q 960 380 900 675 Z" fill="{theme['silhouette_dark']}" />
        <!-- Floating Wisps -->
        <circle cx="360" cy="420" r="8" fill="{theme['accent_particles']}" filter="url(#glow-filter)" opacity="{glow_intensity}" />
        <circle cx="580" cy="460" r="12" fill="{theme['accent_particles']}" filter="url(#glow-filter)" opacity="{glow_intensity * 0.9}" />
        <circle cx="820" cy="400" r="6" fill="{theme['accent_particles']}" filter="url(#glow-filter)" opacity="{glow_intensity}" />
        """
    elif symbol == "hearth":
        focal_elements = f"""
        <!-- Colosseum Archways & Warm Hearth Fire -->
        <path d="M 200 675 L 200 320 Q 600 180 1000 320 L 1000 675 Z" fill="{theme['silhouette_dark']}" />
        <path d="M 380 675 L 380 440 Q 600 320 820 440 L 820 675 Z" fill="{theme['silhouette_mid']}" />
        <!-- Radiant Hearth Fire -->
        <polygon points="560,675 600,480 640,675" fill="{theme['fissure_color']}" filter="url(#glow-filter)" opacity="{glow_intensity}" />
        <circle cx="600" cy="560" r="45" fill="{theme['accent_glow']}" filter="url(#glow-filter)" opacity="{glow_intensity * 0.7}" />
        """
    else:  # Obsidian Crags default
        focal_elements = f"""
        <!-- Volcanic Spire Peaks -->
        <polygon points="50,675 280,240 450,675" fill="{theme['silhouette_light']}" />
        <polygon points="750,675 920,220 1150,675" fill="{theme['silhouette_light']}" />
        <polygon points="320,675 580,160 840,675" fill="{theme['silhouette_mid']}" />
        <polygon points="460,675 620,120 780,675" fill="{theme['silhouette_dark']}" />
        <!-- Magma Fissure Lines -->
        <path d="M 580 160 Q 620 380 540 675" stroke="{theme['fissure_color']}" stroke-width="4" fill="none" opacity="{glow_intensity}" filter="url(#glow-filter)" />
        <path d="M 600 280 Q 660 440 680 675" stroke="{theme['accent_glow']}" stroke-width="3" fill="none" opacity="{glow_intensity * 0.8}" filter="url(#glow-filter)" />
        """

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 675" width="100%" height="100%" preserveAspectRatio="xMidYMid slice" style="display:block;">
  <defs>
    <linearGradient id="skyGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="{theme['sky_top']}" />
      <stop offset="100%" stop-color="{theme['sky_bottom']}" />
    </linearGradient>
    <linearGradient id="fogGrad" x1="0%" y1="100%" x2="0%" y2="0%">
      <stop offset="0%" stop-color="{theme['fog_color']}" stop-opacity="0.8" />
      <stop offset="60%" stop-color="{theme['fog_color']}" stop-opacity="0.2" />
      <stop offset="100%" stop-color="{theme['fog_color']}" stop-opacity="0.0" />
    </linearGradient>
    <filter id="glow-filter" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="16" result="blur" />
      <feComposite in="SourceGraphic" in2="blur" operator="over" />
    </filter>
  </defs>

  <!-- Sky & Celestial Atmosphere -->
  <rect width="1200" height="675" fill="url(#skyGrad)" />
  
  <!-- Atmospheric Aurora / Horizon Corona -->
  <ellipse cx="600" cy="180" rx="550" ry="140" fill="{theme['accent_glow']}" opacity="0.18" filter="url(#glow-filter)" />

  <!-- Background Mountainous/Structural Ridge -->
  <polygon points="0,675 0,420 220,320 480,440 760,290 1020,400 1200,310 1200,675" fill="{theme['silhouette_light']}" opacity="0.8" />

  <!-- Midground Focal Architecture / Spires -->
  {focal_elements}

  <!-- Foreground Atmospheric Fog Depth Layer -->
  <rect y="380" width="1200" height="295" fill="url(#fogGrad)" />

  <!-- Cinematic Frame Vignette -->
  <rect width="1200" height="675" fill="none" stroke="#0f172a" stroke-width="2" opacity="0.4" />

  <!-- Stylized Inscription Tag (Bottom-Right) -->
  <g transform="translate(1160, 645)" text-anchor="end">
    <text font-family="'Cinzel', 'Georgia', serif" font-size="14" font-weight="bold" fill="{theme['accent_particles']}" letter-spacing="3" opacity="0.75">{esc_loc.upper()}</text>
    <text y="16" font-family="'Inter', sans-serif" font-size="10" fill="#94a3b8" letter-spacing="1.5" opacity="0.6">{esc_biome.upper()}</text>
  </g>
</svg>"""
    return svg


def render_scene_illustration(
    location_name: str,
    biome: str,
    description: str,
    tension_level: int = 25,
) -> SceneIllustration:
    """
    Generate an evocative visual prompt and high-resolution procedural vector illustration
    for the specified location and biome.
    """
    theme = BIOME_VISUAL_THEMES.get(biome, DEFAULT_THEME)

    art_prompt = (
        f"Cinematic dark fantasy landscape concept art of {location_name}, set within {biome}. "
        f"{description} "
        f"Atmosphere: {theme['mood']}. "
        f"Lighting: {theme['lighting']}. "
        f"Art style: Mythic oil painting, atmospheric volumetric fog, high fantasy matte illustration, "
        f"Elden Ring and Frank Frazetta aesthetic, dramatic composition, highly detailed."
    )

    svg_data = _generate_procedural_svg(
        location_name=location_name,
        biome=biome,
        theme=theme,
        tension=tension_level,
    )

    return SceneIllustration(
        location_name=location_name,
        biome=biome,
        art_prompt=art_prompt,
        image_url=f"/api/scene/image/{location_name.replace(' ', '%20')}",
        mood=theme["mood"],
        lighting=theme["lighting"],
        composition_style="Cinematic Mythic Matte Painting",
        svg_data=svg_data,
    )
