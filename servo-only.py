import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BOARD)

# ====================================================
# PIN SETUP
# ====================================================
GPIO.setup(11, GPIO.OUT)  # Servo1 (Pembagi Kategori)
GPIO.setup(13, GPIO.OUT)  # Servo2 (Pembuka/Penutup)

servo1 = GPIO.PWM(11, 50)
servo2 = GPIO.PWM(13, 50)

# ====================================================
# DUTY HASIL KALIBRASI
# ====================================================
DUTY_ORG = 4.9      # Organic (kanan)
DUTY_NON = 9.9     # Non-organic (kiri)
DUTY_B3  = 7.0     # Posisi default (B3)
BACK_ORG = 9.3      # Balik ke B3 dari Organic 
BACK_NON = 4.7      # Balik ke B3 dari Non-organic
# ====================================================

def servo1_goto(duty):
    """
    Menggerakkan Servo1.
    """
    servo1.ChangeDutyCycle(duty)
    time.sleep(1.0)
    servo1.ChangeDutyCycle(0) 
    time.sleep(0.2)

def servo2_buka_tutup():
    """
    Menggerakkan Servo2 dengan total waktu sekitar 5.0 detik, 
    dan mematikan sinyal PWM (DC=0) selama waktu tunggu 3.0 detik.
    """
    print("Servo 2 mulai buka/tutup...")

    # 1. Tutup
    servo2.ChangeDutyCycle(2.5)
    time.sleep(0.7)
    
    # 2. Gerak ke Tengah (posisi netral)
    servo2.ChangeDutyCycle(7.5)
    time.sleep(0.5) 
    
    # 3. Waktu Tunggu DIAM (Total 5.0s = 0.7 + 0.5 + 3.0 + 0.8)
    print(f"Menunggu selama 3.0 detik tanpa sinyal PWM...")
    servo2.ChangeDutyCycle(0) # <--- MEMATIKAN SINYAL AGAR SERVO DIAM!
    time.sleep(3.5)  
    
    # 4. Buka
    servo2.ChangeDutyCycle(11.5)
    time.sleep(0.8)

    servo2.ChangeDutyCycle(0) # Matikan sinyal setelah selesai
    print("Servo 2 selesai.\n" + ("-" * 25))

# ====================================================
# INISIALISASI & LOGIKA UTAMA
# ====================================================
servo1.start(0)
servo2.start(0)

print("Mengatur Servo1 ke posisi default awal (B3 / 7.0)...")
servo1_goto(DUTY_B3) 

print("\nPilih kategori:")
print("1. B3 (Default)")
print("2. NON-ORGANIC (KIRI)")
print("3. ORGANIC (KANAN)")

try:
    choice = int(input("Masukkan angka (1–3): "))
except ValueError:
    print("Input tidak valid!")
    choice = 0

# ====================================================
if choice == 1:
    print("=== B3 ===")
    print("Servo1 sudah di posisi default (B3), tidak bergerak lagi.")
    servo2_buka_tutup()

elif choice == 2:
    print("=== NON-ORGANIC (KIRI) ===")
    servo1_goto(DUTY_NON)
    servo2_buka_tutup()
    print("Kembali ke B3...")
    servo1_goto(BACK_NON)

elif choice == 3:
    print("=== ORGANIC (KANAN) ===")
    servo1_goto(DUTY_ORG)
    servo2_buka_tutup()
    print("Kembali ke B3...")
    servo1_goto(BACK_ORG)

else:
    print("Pilihan tidak valid.")

# ====================================================
servo1.stop()
servo2.stop()
GPIO.cleanup()
print("Program selesai.")

