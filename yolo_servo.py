import time
import atexit


# ========== KONFIGURASI GPIO ==========
GPIO_AVAILABLE = False
try:
import RPi.GPIO as GPIO
GPIO_AVAILABLE = True
# print("STATUS: RPi.GPIO berhasil dimuat.")
except Exception:
# If import fails we run in simulation mode
GPIO_AVAILABLE = False


# ========== PIN CONFIGURATION ==========
SERVO_BIN_PIN = 11 # Servo 1 (Pembagi Kategori) - BOARD PIN 11
SERVO_LID_PIN = 13 # Servo 2 (Pembuka/Penutup) - BOARD PIN 13


# ========== DUTY CYCLE HASIL KALIBRASI ==========
DUTY_ORG = 5.0 # Organic (kanan)
DUTY_NON = 9.53 # Non-organic (kiri)
DUTY_B3 = 7.0 # Posisi default (B3)
BACK_ORG = 9.5 # Balik ke B3 dari Organic
BACK_NON = 4.1 # Balik ke B3 dari Non-organic


# ========== SERVO 2 (TUTUP) DUTY CYCLE ==========
DUTY_TUTUP_TERTUTUP = 2.5 # Tutup ditutup
DUTY_TUTUP_TENGAH = 7.5 # Posisi tengah
DUTY_TUTUP_TERBUKA = 11.5 # Tutup dibuka


# ========== WAKTU GERAKAN ==========
WAKTU_ROTASI = 1.0 # Waktu rotasi bin (detik)
WAKTU_BUKA_TUTUP = 3.5 # Waktu tunggu tutup terbuka (detik)


# ========== STATUS ==========
servo_sedang_jalan = False
_gpio_cleaned = False


# servo pwm object placeholders
servo_bin = None
servo_tutup = None


# Initialize hardware if available
if GPIO_AVAILABLE:
try:
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
init_servo()