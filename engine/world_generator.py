"""
engine/world_generator.py
Procedural mythic world, faction, biome, and dungeon generator for AI Dungeon Master.
"""

import random
import uuid
from dataclasses import dataclass


@dataclass
class Faction:
    id: str
    name: str
    motto: str
    ideology: str
    leader: str
    influence: int  # 1-100
    hostility_to_player: int  # -100 (beloved) to +100 (sworn enemy)
    sigil: str


@dataclass
class LocationNode:
    id: str
    name: str
    region: str
    biome: str  # e.g. "Abyssal Mire", "Obsidian Crags", "Ancient Sanctum"
    threat_tier: int  # 1-10
    description: str
    coordinates: dict[str, float]  # x: 0-100, y: 0-100 for SVG atlas
    connections: list[str]  # IDs of neighboring nodes
    discovered: bool = False
    cleared: bool = False
    secrets_count: int = 2
    ambient_theme: str = "ambient_drone"


@dataclass
class WorldState:
    id: str
    name: str
    epoch: str
    cosmology: str
    cataclysm_lore: str
    factions: list[Faction]
    locations: list[LocationNode]
    current_location_id: str
    tension_level: int = 15  # 0 to 100
    active_quest: str = ""
    world_seed: int = 42


WORLD_PREFIXES = ["Aegis", "Valdor", "Kharak", "Onyx", "Nethys", "Astral", "Vael", "Solara", "Dusk"]
WORLD_SUFFIXES = ["Prime", "Reach", "Expanse", "Domain", "Hollow", "Vortex", "Bastion", "Spire"]

BIOMES = [
    {
        "type": "Obsidian Crags",
        "desc": "Jagged volcanic spires emitting ash-choked vapors and faint violet sparks.",
        "ambient": "ominous_pulse",
        "threat": 4,
    },
    {
        "type": "Sunken Crypts",
        "desc": "Submerged limestone catacombs where water echoes against bone-inscribed sarcophagi.",
        "ambient": "ambient_drone",
        "threat": 6,
    },
    {
        "type": "Gargoyle Roost",
        "desc": "High windblown pinnacles guarded by animated stone sentinels and shadow gargoyles.",
        "ambient": "battle_tension",
        "threat": 7,
    },
    {
        "type": "Whispering Fen",
        "desc": "A spectral marshland where spirits of forgotten warriors murmur warnings in the reeds.",
        "ambient": "ambient_drone",
        "threat": 3,
    },
    {
        "type": "Astral Observatory",
        "desc": "Floating crystalline domes capturing cosmic radiation from dead gods.",
        "ambient": "ethereal_mystery",
        "threat": 5,
    },
    {
        "type": "Ashen Citadel",
        "desc": "The iron stronghold of the Obsidian Covenant, fortified by runic blast-walls.",
        "ambient": "battle_tension",
        "threat": 8,
    },
    {
        "type": "Tavern of the Broken Blade",
        "desc": "A fortified safe haven built into a ruined colosseum where mercenaries gather.",
        "ambient": "tavern_hearth",
        "threat": 1,
    },
]

FACTION_TEMPLATES = [
    {
        "name": "The Obsidian Covenant",
        "motto": "Strength forged in cold iron and shadow.",
        "ideology": "Militaristic order seeking total dominion over unstable arcane rifts.",
        "leader": "Lord Commander Vane",
        "hostility": 40,
        "sigil": "Black Blade on Crest",
    },
    {
        "name": "Weavers of the Astral Veil",
        "motto": "Truth lies beyond the threshold of mortal sight.",
        "ideology": "Mystics seeking to mend the fractured fabric of reality.",
        "leader": "Archivist Sylas",
        "hostility": -20,
        "sigil": "Golden Infinite Spiral",
    },
    {
        "name": "Scavengers of the Deep Mire",
        "motto": "Nothing wasted, nothing buried forever.",
        "ideology": "Outcasts and rogue artificers recovering lost technologies.",
        "leader": "Queen Mother Khora",
        "hostility": 10,
        "sigil": "Rune-Carved Skull",
    },
]


def generate_procedural_world(seed: int | None = None) -> WorldState:
    rng = random.Random(seed if seed is not None else random.randint(1000, 999999))
    actual_seed = rng.randint(10000, 99999)

    world_name = f"{rng.choice(WORLD_PREFIXES)} {rng.choice(WORLD_SUFFIXES)}"
    epochs = [
        "Age of Iron and Ash",
        "Era of the Shattered Sky",
        "Epoch of the Eclipse Sentinel",
        "The Twilight Reckoning",
    ]
    epoch = rng.choice(epochs)

    cosmology = (
        "Three dying moons revolve around a cracked crystalline sphere. Magic bleeds "
        "through tectonic rift-lines known as Ley-Faults, fueling volatile creatures and ancient ruins."
    )
    cataclysm_lore = (
        "Seven centuries ago, the Aegis Engine fractured. The sky fractured into auroras, and stone gargoyles "
        "woke to defend long-abandoned vaults. Only brave wanderers dare venture beyond the sanctuary rim."
    )

    # Generate Factions
    factions: list[Faction] = []
    for f in FACTION_TEMPLATES:
        factions.append(
            Faction(
                id=str(uuid.uuid4())[:8],
                name=f["name"],
                motto=f["motto"],
                ideology=f["ideology"],
                leader=f["leader"],
                influence=rng.randint(45, 90),
                hostility_to_player=f["hostility"],
                sigil=f["sigil"],
            )
        )

    # Generate Locations on a 2D Atlas
    locations: list[LocationNode] = []
    loc_coords = [
        {"x": 18, "y": 72},  # Tavern / safe starting point
        {"x": 38, "y": 55},  # Whispering Fen
        {"x": 62, "y": 68},  # Obsidian Crags
        {"x": 45, "y": 32},  # Astral Observatory
        {"x": 22, "y": 28},  # Sunken Crypts
        {"x": 78, "y": 38},  # Gargoyle Roost
        {"x": 82, "y": 18},  # Ashen Citadel (Endgame)
    ]

    for i, b in enumerate(BIOMES):
        coords = loc_coords[i % len(loc_coords)]
        # Add slight jitter
        coords_jittered = {
            "x": max(10, min(90, coords["x"] + rng.uniform(-4, 4))),
            "y": max(10, min(90, coords["y"] + rng.uniform(-4, 4))),
        }
        loc_id = f"loc_{i+1}"
        locations.append(
            LocationNode(
                id=loc_id,
                name=f"{b['type']}",
                region=f"Sector {chr(65+i)}",
                biome=b["type"],
                threat_tier=b["threat"],
                description=b["desc"],
                coordinates=coords_jittered,
                connections=[],
                discovered=(i == 0 or i == 1),  # First two visible
                cleared=False,
                secrets_count=rng.randint(1, 4),
                ambient_theme=b["ambient"],
            )
        )

    # Establish topology edges
    connections_map = {
        "loc_1": ["loc_2", "loc_3"],
        "loc_2": ["loc_1", "loc_4", "loc_5"],
        "loc_3": ["loc_1", "loc_4", "loc_6"],
        "loc_4": ["loc_2", "loc_3", "loc_7"],
        "loc_5": ["loc_2"],
        "loc_6": ["loc_3", "loc_7"],
        "loc_7": ["loc_4", "loc_6"],
    }
    for loc in locations:
        loc.connections = connections_map.get(loc.id, [])

    active_quest = (
        "Infiltrate the Gargoyle Roost, recover the fractured Amulet of Dawn, "
        "and decipher why the stone sentinels are awakening across the realm."
    )

    return WorldState(
        id=str(uuid.uuid4())[:8],
        name=world_name,
        epoch=epoch,
        cosmology=cosmology,
        cataclysm_lore=cataclysm_lore,
        factions=factions,
        locations=locations,
        current_location_id="loc_1",
        tension_level=20,
        active_quest=active_quest,
        world_seed=actual_seed,
    )
