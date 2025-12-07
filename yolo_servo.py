import time

# ========== KONFIGURASI GPIO ==========
GPIO_AVAILABLE = False
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
    print("STATUS: RPi.GPIO berhasil dimuat.")
except ImportError:
    print("WARNING: RPi.GPIO tidak tersedia. Servo berjalan dalam mode simulasi.")

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

# ========== INISIALISASI GPIO ==========
if GPIO_AVAILABLE:
    GPIO.setwarnings(False)
    GPIO.cleanup()

    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(SERVO_BIN_PIN, GPIO.OUT)
    GPIO.setup(SERVO_LID_PIN, GPIO.OUT)

    servo_bin = GPIO.PWM(SERVO_BIN_PIN, 50)
    servo_tutup = GPIO.PWM(SERVO_LID_PIN, 50)

    servo_bin.start(0)
    servo_tutup.start(0)


# ========== FUNGSI SERVO 1: PUTAR BIN ==========
def servo1_goto(duty):
    """Menggerakkan Servo1 (Bin) ke duty cycle tertentu."""
    if GPIO_AVAILABLE:
        servo_bin.ChangeDutyCycle(duty)
        time.sleep(WAKTU_ROTASI)
        servo_bin.ChangeDutyCycle(0)
        time.sleep(0.2)
    else:
        print(f"[SIMULASI] Servo1 bergerak ke duty: {duty}")
        time.sleep(WAKTU_ROTASI)


# ========== FUNGSI SERVO 2: BUKA TUTUP ==========
def servo2_buka_tutup():
    """
    Menggerakkan Servo2 (Tutup) dengan urutan:
    Tutup -> Tengah -> Tunggu -> Buka
    """
    print("Servo 2 mulai buka/tutup...")

    if GPIO_AVAILABLE:
        # 1. Tutup
        servo_tutup.ChangeDutyCycle(DUTY_TUTUP_TERTUTUP)
        time.sleep(0.7)

        # 2. Gerak ke Tengah
        servo_tutup.ChangeDutyCycle(DUTY_TUTUP_TENGAH)
        time.sleep(0.5)

        # 3. Waktu Tunggu DIAM
        print(f"Menunggu selama {WAKTU_BUKA_TUTUP} detik...")
        servo_tutup.ChangeDutyCycle(0)
        time.sleep(WAKTU_BUKA_TUTUP)

        # 4. Buka
        servo_tutup.ChangeDutyCycle(DUTY_TUTUP_TERBUKA)
        time.sleep(0.8)

        servo_tutup.ChangeDutyCycle(0)
    else:
        print(f"[SIMULASI] Servo2 buka/tutup (total {WAKTU_BUKA_TUTUP + 2.0} detik)")
        time.sleep(WAKTU_BUKA_TUTUP + 2.0)

    print("Servo 2 selesai.")


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
            print("=== SAMPAH B3 TERDETEKSI ===")
            print("Servo1 sudah di posisi default (B3), tidak bergerak.")
            servo2_buka_tutup()
            print("=== SELESAI ===\n")

        # === ORGANIC ===
        elif jenis_sampah == 'organic':
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
    if GPIO_AVAILABLE:
        servo_bin.ChangeDutyCycle(DUTY_B3)
        time.sleep(WAKTU_ROTASI)
        servo_bin.ChangeDutyCycle(0)
    else:
        print("[SIMULASI] Servo diinisialisasi ke posisi B3")
    print("Servo siap digunakan!\n")


# ========== CLEANUP GPIO ==========
def cleanup_servo():
    """Membersihkan GPIO saat program selesai."""
    if GPIO_AVAILABLE:
        print("Membersihkan GPIO...")
        servo_bin.stop()
        servo_tutup.stop()
        GPIO.cleanup()
        print("GPIO dibersihkan!")
    else:
        print("GPIO cleanup (mode simulasi)")


# ========== AUTO INIT ==========
if __name__ != '__main__':
    # Inisialisasi otomatis saat module di-import
    init_servo()
