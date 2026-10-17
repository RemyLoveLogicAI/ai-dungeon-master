import math
import os
import random
import struct
import wave

SAMPLE_RATE = 44100

# Audio noise must not draw from the global Mersenne Twister. Combat reads that
# same shared stream, so any sample consumed here would shift every later combat
# roll and make a seeded encounter irreproducible. This generator is private to
# audio, so synthesising SFX can no longer perturb the simulation.
_RNG = random.Random()


def _write_wav(filename: str, samples: list):
    with wave.open(filename, "w") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(SAMPLE_RATE)

        # Convert float [-1.0, 1.0] to 16-bit PCM integers
        packed_frames = bytearray()
        for s in samples:
            clamped = max(-1.0, min(1.0, s))
            val = int(clamped * 32767.0)
            packed_frames.extend(struct.pack("<h", val))

        wav_file.writeframes(packed_frames)


def synthesize_dice_roll(output_path: str, duration: float = 0.45):
    total_samples = int(SAMPLE_RATE * duration)
    samples = [0.0] * total_samples

    # Simulate 6 quick dice tumble clicks
    for click in range(6):
        start = int(click * (total_samples / 6))
        burst_len = int(0.015 * SAMPLE_RATE)
        for i in range(burst_len):
            idx = start + i
            if idx < total_samples:
                t = i / SAMPLE_RATE
                env = math.exp(-t * 220.0)
                noise = (_RNG.random() * 2.0 - 1.0) * env * 0.6
                samples[idx] += noise

    _write_wav(output_path, samples)


def synthesize_sword_clash(output_path: str, duration: float = 0.5):
    total_samples = int(SAMPLE_RATE * duration)
    samples = [0.0] * total_samples

    for i in range(total_samples):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 7.5)
        # Metallic resonance frequencies (harmonic overtones)
        ring1 = math.sin(2.0 * math.pi * 2350.0 * t)
        ring2 = math.sin(2.0 * math.pi * 3820.0 * t)
        noise = (_RNG.random() * 2.0 - 1.0) * math.exp(-t * 40.0)

        samples[i] = (noise * 0.4 + (ring1 + ring2) * 0.3) * env

    _write_wav(output_path, samples)


def synthesize_fireball_impact(output_path: str, duration: float = 0.75):
    total_samples = int(SAMPLE_RATE * duration)
    samples = [0.0] * total_samples

    for i in range(total_samples):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 3.5)
        # Low frequency explosion + hiss
        rumble = math.sin(2.0 * math.pi * (70.0 - 30.0 * t) * t)
        hiss = (_RNG.random() * 2.0 - 1.0) * math.exp(-t * 4.0)

        samples[i] = (rumble * 0.65 + hiss * 0.3) * env

    _write_wav(output_path, samples)


def synthesize_crit_fanfare(output_path: str, duration: float = 0.6):
    total_samples = int(SAMPLE_RATE * duration)
    samples = [0.0] * total_samples

    # C major triad arpeggio
    notes = [523.25, 659.25, 783.99, 1046.50]
    for i in range(total_samples):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 3.0)
        note_sum = sum(math.sin(2.0 * math.pi * f * t) for f in notes) / len(notes)
        samples[i] = note_sum * env * 0.75

    _write_wav(output_path, samples)


def synthesize_ambient_drone(
    output_path: str,
    duration: float = 2.0,
    root_freq: float = 55.0,
    tension: float = 0.0,
):
    """Synthesizes a deep atmospheric drone with harmonic fifths, chorus, and tension overtones."""
    total_samples = int(SAMPLE_RATE * duration)
    samples = [0.0] * total_samples

    # Root, fifth (82.4 Hz), and detuned oscillator
    f1 = root_freq
    f2 = root_freq * 1.4983  # Musical fifth
    f3 = root_freq * 1.01  # Chorus detune
    # Tension overtone (tritone / sharp fourth for dark tension)
    tension_freq = root_freq * (1.414 if tension > 0.5 else 2.0)

    for i in range(total_samples):
        t = i / SAMPLE_RATE
        # Envelope: gentle fade-in and fade-out to loop smoothly
        fade_len = 0.2
        if t < fade_len:
            env = t / fade_len
        elif t > (duration - fade_len):
            env = (duration - t) / fade_len
        else:
            env = 1.0

        osc1 = math.sin(2.0 * math.pi * f1 * t)
        osc2 = math.sin(2.0 * math.pi * f2 * t) * 0.4
        osc3 = math.sin(2.0 * math.pi * f3 * t) * 0.3
        tension_osc = math.sin(2.0 * math.pi * tension_freq * t) * (0.35 * tension)

        # Subtle filtered rumble noise
        noise = (_RNG.random() * 2.0 - 1.0) * 0.04

        val = (osc1 * 0.4 + osc2 + osc3 + tension_osc + noise) * env * 0.6
        samples[i] = val

    _write_wav(output_path, samples)


def synthesize_cavern_ambience(output_path: str, duration: float = 2.0):
    """Synthesizes dark cavern acoustics: low wind hum and procedural water drips."""
    total_samples = int(SAMPLE_RATE * duration)
    samples = [0.0] * total_samples

    # Wind hum base
    for i in range(total_samples):
        t = i / SAMPLE_RATE
        wind = math.sin(
            2.0 * math.pi * (45.0 + 8.0 * math.sin(2.0 * math.pi * 0.3 * t)) * t
        )
        samples[i] = wind * 0.2

    # Add 4 water drip pings at varying intervals
    drip_times = [0.35, 0.85, 1.30, 1.75]
    for drip_t in drip_times:
        drip_idx = int(drip_t * SAMPLE_RATE)
        drip_freq = 1400.0 + _RNG.random() * 400.0
        drip_len = int(0.06 * SAMPLE_RATE)
        for j in range(drip_len):
            idx = drip_idx + j
            if idx < total_samples:
                dt = j / SAMPLE_RATE
                env = math.exp(-dt * 90.0)
                ping = math.sin(2.0 * math.pi * drip_freq * dt) * env * 0.45
                samples[idx] += ping

    _write_wav(output_path, samples)


def synthesize_tension_pulse(
    output_path: str, tension: float = 0.5, duration: float = 1.5
):
    """Synthesizes a low rhythmic heartbeat / tension pulse that scales with combat stakes."""
    total_samples = int(SAMPLE_RATE * duration)
    samples = [0.0] * total_samples

    # Heartbeat rate increases with tension: 1 Hz (60 bpm) to 2.2 Hz (132 bpm)
    bpm_freq = 1.0 + tension * 1.2
    pulse_interval = int(SAMPLE_RATE / bpm_freq)

    pos = 0
    while pos < total_samples:
        # Lub-dub double beat
        for beat_offset in [0, int(0.12 * SAMPLE_RATE)]:
            b_start = pos + beat_offset
            b_len = int(0.08 * SAMPLE_RATE)
            for k in range(b_len):
                idx = b_start + k
                if idx < total_samples:
                    t = k / SAMPLE_RATE
                    env = math.exp(-t * 40.0)
                    pulse_sound = (
                        math.sin(2.0 * math.pi * (60.0 - 20.0 * t) * t)
                        * env
                        * (0.5 + 0.3 * tension)
                    )
                    samples[idx] += pulse_sound
        pos += pulse_interval

    _write_wav(output_path, samples)


def calculate_encounter_tension(
    enemy_hp_pct: float, player_hp_pct: float, round_number: int
) -> float:
    """Calculates normalized tension (0.0 to 1.0) based on health pools and round progression."""
    danger = (1.0 - player_hp_pct) * 0.55
    enemy_desperation = (1.0 - enemy_hp_pct) * 0.25
    round_escalation = min(0.20, round_number * 0.04)
    raw = danger + enemy_desperation + round_escalation
    return max(0.0, min(1.0, round(raw, 2)))


AUDIO_DIR_ENV = "AI_DM_AUDIO_DIR"


def default_audio_dir() -> str:
    """Return a writable directory for the generated SFX."""
    override = os.environ.get(AUDIO_DIR_ENV)
    if override:
        return override
    cache_root = os.environ.get("XDG_CACHE_HOME") or os.path.join(
        os.path.expanduser("~"), ".cache"
    )
    return os.path.join(cache_root, "ai-dungeon-master", "audio_output")


def generate_all_sfx(output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    paths = {
        "dice_roll": os.path.join(output_dir, "dice_roll.wav"),
        "sword_clash": os.path.join(output_dir, "sword_clash.wav"),
        "fireball_impact": os.path.join(output_dir, "fireball_impact.wav"),
        "crit_fanfare": os.path.join(output_dir, "crit_fanfare.wav"),
        "ambient_drone": os.path.join(output_dir, "ambient_drone.wav"),
        "cavern_ambience": os.path.join(output_dir, "cavern_ambience.wav"),
        "tension_pulse": os.path.join(output_dir, "tension_pulse.wav"),
    }

    synthesize_dice_roll(paths["dice_roll"])
    synthesize_sword_clash(paths["sword_clash"])
    synthesize_fireball_impact(paths["fireball_impact"])
    synthesize_crit_fanfare(paths["crit_fanfare"])
    synthesize_ambient_drone(paths["ambient_drone"])
    synthesize_cavern_ambience(paths["cavern_ambience"])
    synthesize_tension_pulse(paths["tension_pulse"])

    return paths


if __name__ == "__main__":
    out = os.path.join(os.getcwd(), "audio_output")
    res = generate_all_sfx(out)
    print("Synthesized audio assets:")
    for name, p in res.items():
        print(f"  - {name}: {p} ({os.path.getsize(p)} bytes)")
