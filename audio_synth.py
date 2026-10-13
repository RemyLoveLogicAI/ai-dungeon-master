import math
import os
import random
import struct
import wave

SAMPLE_RATE = 44100

def _write_wav(filename: str, samples: list):
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1) # Mono
        wav_file.setsampwidth(2) # 16-bit
        wav_file.setframerate(SAMPLE_RATE)
        
        # Convert float [-1.0, 1.0] to 16-bit PCM integers
        packed_frames = bytearray()
        for s in samples:
            clamped = max(-1.0, min(1.0, s))
            val = int(clamped * 32767.0)
            packed_frames.extend(struct.pack('<h', val))
            
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
                noise = (random.random() * 2.0 - 1.0) * env * 0.6
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
        noise = (random.random() * 2.0 - 1.0) * math.exp(-t * 40.0)
        
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
        hiss = (random.random() * 2.0 - 1.0) * math.exp(-t * 4.0)
        
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

def generate_all_sfx(output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    paths = {
        "dice_roll": os.path.join(output_dir, "dice_roll.wav"),
        "sword_clash": os.path.join(output_dir, "sword_clash.wav"),
        "fireball_impact": os.path.join(output_dir, "fireball_impact.wav"),
        "crit_fanfare": os.path.join(output_dir, "crit_fanfare.wav")
    }
    
    synthesize_dice_roll(paths["dice_roll"])
    synthesize_sword_clash(paths["sword_clash"])
    synthesize_fireball_impact(paths["fireball_impact"])
    synthesize_crit_fanfare(paths["crit_fanfare"])
    
    return paths

if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "audio_output")
    res = generate_all_sfx(out)
    print("Synthesized audio SFX:")
    for name, p in res.items():
        print(f"  - {name}: {p} ({os.path.getsize(p)} bytes)")
