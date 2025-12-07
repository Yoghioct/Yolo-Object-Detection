# ==============================
# FILE: yolo_audio.py
# ==============================

PYGAME_AVAILABLE = False

snd_b3 = None
snd_organic = None
snd_non = None
snd_fail = None

try:
    import pygame
    pygame.mixer.init()
    PYGAME_AVAILABLE = True
    print("STATUS: Pygame Mixer berhasil diinisialisasi.")
except Exception as e:
    print(f"WARNING: Audio disabled: {e}")

# File audio
SOUND_B3 = 'b3.mp3'
SOUND_ORGANIC = 'organic.mp3'
SOUND_NON_ORGANIC = 'non-organic.mp3'
SOUND_FAIL = 'waste-cant-detect.mp3'

# Preload sounds
if PYGAME_AVAILABLE:
    try:
        snd_b3 = pygame.mixer.Sound(SOUND_B3)
        snd_organic = pygame.mixer.Sound(SOUND_ORGANIC)
        snd_non = pygame.mixer.Sound(SOUND_NON_ORGANIC)
        snd_fail = pygame.mixer.Sound(SOUND_FAIL)
        print("STATUS: Semua file audio berhasil di-preload.")
    except Exception as e:
        print(f"WARNING: Gagal memuat file audio: {e}")
        PYGAME_AVAILABLE = False

def play_sound(sound_obj):
    """Play sound (non-blocking, safe)."""
    if PYGAME_AVAILABLE and sound_obj is not None:
        try:
            pygame.mixer.Channel(0).play(sound_obj)
        except Exception as e:
            print(f"ERROR play_sound(): {e}")
    else:
        print("[SIMULASI AUDIO] Bunyi diputar")
