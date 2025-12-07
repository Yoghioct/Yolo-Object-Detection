import time
import atexit

# ========== KONFIGURASI GPIO ==========
GPIO_AVAILABLE = False
PYGAME_AVAILABLE = False

snd_b3 = None
snd_organic = None
snd_non = None
snd_fail = None

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
    print("STATUS: RPi.GPIO berhasil dimuat.")

    try:
        import pygame
        pygame.mixer.init()
        PYGAME_AVAILABLE = True
        print("STATUS: Pygame Mixer berhasil diinisialisasi.")
    except Exception as e:
        print(f"WARNING: Audio disabled: {e}")
except Exception:
    # If import fails we run in simulation mode
    GPIO_AVAILABLE = False

# ========== PIN CONFIGURATION ==========
SERVO_BIN_PIN = 11      # Servo 1 (Pembagi Kategori) - BOARD PIN 11
SERVO_LID_PIN = 13      # Servo 2 (Pembuka/Penutup) - BOARD PIN 13

# ========== DUTY CYCLE HASIL KALIBRASI ==========
DUTY_ORG = 5.0          # Organic (kanan)
DUTY_NON = 9.53         # Non-organic (kiri)
DUTY_B3  = 7.0          # Posisi default (B3)
BACK_ORG = 9.5          # Balik ke B3 dari Organic
BACK_NON = 4.1          # Balik ke B3 dari Non-organic

# ========== SERVO 2 (TUTUP) DUTY CYCLE ==========
DUTY_TUTUP_TERTUTUP = 2.5   # Tutup ditutup
DUTY_TUTUP_TENGAH = 7.5     # Posisi tengah
DUTY_TUTUP_TERBUKA = 11.5   # Tutup dibuka

# ========== WAKTU GERAKAN ==========
WAKTU_ROTASI = 1.0          # Waktu rotasi bin (detik)
WAKTU_BUKA_TUTUP = 3.5      # Waktu tunggu tutup terbuka (detik)

# ========== STATUS ==========
servo_sedang_jalan = False
_gpio_cleaned = False

# servo pwm object placeholders
servo_bin = None
servo_tutup = None

SOUND_B3 = 'b3.mp3'
SOUND_ORGANIC = 'organic.mp3'
SOUND_NON_ORGANIC = 'non-organic.mp3'
SOUND_FAIL = 'waste-cant-detect.mp3'

# Initialize hardware if available
if GPIO_AVAILABLE:
    try:
        pygame.mixer.init()

        try:
            snd_b3 = pygame.mixer.Sound(SOUND_B3)
            snd_organic = pygame.mixer.Sound(SOUND_ORGANIC)
            snd_non = pygame.mixer.Sound(SOUND_NON_ORGANIC)
        except Exception as e:
            print(f"Audio gagal dimuat: {e}")
            snd_b3 = snd_organic = snd_non = None

        GPIO.setwarnings(False)
        # ensure clean start
        GPIO.cleanup()
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(SERVO_BIN_PIN, GPIO.OUT)
        GPIO.setup(SERVO_LID_PIN, GPIO.OUT)

        servo_bin = GPIO.PWM(SERVO_BIN_PIN, 50)
        servo_tutup = GPIO.PWM(SERVO_LID_PIN, 50)

        servo_bin.start(0)
        servo_tutup.start(0)
    except Exception as e:
        # fallback to simulation mode if init fails
        print(f"[WARNING] GPIO init failed, switching to simulation mode: {e}")
        GPIO_AVAILABLE = False

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

# --------- Utility: safe pwm change ---------

def _pwm_safe_change(pwm_obj, duty, sleep_after):
    """Change duty cycle safely. In simulation mode it simply sleeps and prints."""
    try:
        if GPIO_AVAILABLE and pwm_obj is not None:
            pwm_obj.ChangeDutyCycle(duty)
            time.sleep(sleep_after)
            # do not always zero-out immediately for intermediate moves; some callers do explicit zeroing
            pwm_obj.ChangeDutyCycle(0)
            time.sleep(0.05)
        else:
            # simulation
            print(f"[SIMULASI] PWM change to {duty} (sleep {sleep_after}s)")
            time.sleep(sleep_after)
    except Exception as e:
        # don't let low-level errors bubble up and crash the program
        print(f"[ERROR] PWM operation failed: {e}")


# ========== FUNGSI SERVO 1: PUTAR BIN ==========
def servo1_goto(duty):
    """Menggerakkan Servo1 (Bin) ke duty cycle tertentu."""
    _pwm_safe_change(servo_bin, duty, WAKTU_ROTASI)


# ========== FUNGSI SERVO 2: BUKA TUTUP ==========
def servo2_buka_tutup():
    """
    Menggerakkan Servo2 (Tutup) dengan urutan:
    Tutup -> Tengah -> Tunggu -> Buka
    """
    print("Servo 2: buka/tutup sequence")

    # 1. Tutup
    _pwm_safe_change(servo_tutup, DUTY_TUTUP_TERTUTUP, 0.7)

    # 2. Gerak ke Tengah (some servos prefer a short non-zero stay)
    try:
        if GPIO_AVAILABLE and servo_tutup is not None:
            servo_tutup.ChangeDutyCycle(DUTY_TUTUP_TENGAH)
            time.sleep(0.5)
            servo_tutup.ChangeDutyCycle(0)
    except Exception as e:
        print(f"[ERROR] servo_tutup middle move failed: {e}")

    # 3. Waktu tunggu
    print(f"Menunggu selama {WAKTU_BUKA_TUTUP} detik...")
    time.sleep(WAKTU_BUKA_TUTUP)

    # 4. Buka
    _pwm_safe_change(servo_tutup, DUTY_TUTUP_TERBUKA, 0.8)

    print("Servo 2 sequence complete")


# ========== FUNGSI UTAMA: JALANKAN SERVO ==========
def jalankan_servo(jenis_sampah):
    """
    Menjalankan urutan gerakan servo sesuai jenis sampah.

    Args:
        jenis_sampah (str): 'b3', 'organic', atau 'non-organic'
    """
    global servo_sedang_jalan

    if servo_sedang_jalan:
        print(f"Servo sedang sibuk, lewati {jenis_sampah}")
        return

    try:
        servo_sedang_jalan = True

        # === B3 ===
        if jenis_sampah == 'b3':
            play_sound(snd_b3)
            print("=== SAMPAH B3 TERDETEKSI ===")
            print("Servo1 sudah di posisi default (B3), tidak bergerak.")
            servo2_buka_tutup()
            print("=== SELESAI ===\n")

        # === ORGANIC ===
        elif jenis_sampah == 'organic':
            play_sound(snd_organic)
            print("=== SAMPAH ORGANIK TERDETEKSI ===")
            print("1. Memutar bin ke KANAN (organic)...")
            servo1_goto(DUTY_ORG)

            print("2. Buka/tutup bin...")
            servo2_buka_tutup()

            print("3. Kembali ke B3...")
            servo1_goto(BACK_ORG)
            print("=== SELESAI ===\n")

        # === NON-ORGANIC ===
        elif jenis_sampah == 'non-organic':
            play_sound(snd_non)
            print("=== SAMPAH NON-ORGANIC TERDETEKSI ===")
            print("1. Memutar bin ke KIRI (non-organic)...")
            servo1_goto(DUTY_NON)

            print("2. Buka/tutup bin...")
            servo2_buka_tutup()

            print("3. Kembali ke B3...")
            servo1_goto(BACK_NON)
            print("=== SELESAI ===\n")

        else:
            print(f"Jenis sampah tidak dikenali: {jenis_sampah}")

    finally:
        servo_sedang_jalan = False


# ========== INISIALISASI POSISI AWAL ==========

def init_servo():
    """Inisialisasi servo ke posisi awal (B3)."""
    print("Menginisialisasi servo ke posisi awal...")
    try:
        if GPIO_AVAILABLE and servo_bin is not None:
            servo_bin.ChangeDutyCycle(DUTY_B3)
            time.sleep(WAKTU_ROTASI)
            servo_bin.ChangeDutyCycle(0)
        else:
            print("[SIMULASI] Servo diinisialisasi ke posisi B3")
    except Exception as e:
        print(f"[ERROR] init_servo failed: {e}")
    print("Servo siap digunakan!\n")


# ========== CLEANUP GPIO (idempotent) ==========

def cleanup_servo():
    """Membersihkan GPIO saat program selesai. Safe to call multiple times."""
    global _gpio_cleaned, servo_bin, servo_tutup

    if _gpio_cleaned:
        # already cleaned
        return

    if GPIO_AVAILABLE:
        try:
            print("Membersihkan GPIO...")
            if servo_bin is not None:
                try:
                    servo_bin.stop()
                except Exception as e:
                    print(f"Error stopping servo_bin: {e}")
                servo_bin = None
            if servo_tutup is not None:
                try:
                    servo_tutup.stop()
                except Exception as e:
                    print(f"Error stopping servo_tutup: {e}")
                servo_tutup = None

            try:
                GPIO.cleanup()
            except Exception as e:
                print(f"Error during GPIO.cleanup(): {e}")

            _gpio_cleaned = True
            print("GPIO dibersihkan!")
        except Exception as e:
            print("cleanup_servo error:", e)
    else:
        print("GPIO cleanup (mode simulasi)")
        _gpio_cleaned = True


# Register cleanup on normal program exit
atexit.register(cleanup_servo)

# Auto init when imported
init_servo()