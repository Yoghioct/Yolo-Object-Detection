import time
import atexit

# ... existing constants ...

# initialize servo variables even if GPIO not available
servo_bin = None
servo_tutup = None

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


def pwm_safe_change(pwm_obj, duty, sleep_after):
    """Call ChangeDutyCycle safely if pwm_obj exists."""
    try:
        if GPIO_AVAILABLE and pwm_obj is not None:
            pwm_obj.ChangeDutyCycle(duty)
            time.sleep(sleep_after)
            pwm_obj.ChangeDutyCycle(0)
            time.sleep(0.05)
        else:
            # simulation mode
            print(f"[SIMULASI] PWM change to {duty} (sleep {sleep_after}s)")
            time.sleep(sleep_after)
    except Exception as e:
        print(f"[ERROR] PWM operation failed: {e}")


def servo1_goto(duty):
    """Menggerakkan Servo1 (Bin) ke duty cycle tertentu."""
    pwm_safe_change(servo_bin, duty, WAKTU_ROTASI)


def servo2_buka_tutup():
    print("Servo 2 mulai buka/tutup...")
    if GPIO_AVAILABLE and servo_tutup is None:
        print("[WARNING] servo_tutup is None despite GPIO_AVAILABLE=True")
    # 1. Tutup
    pwm_safe_change(servo_tutup, DUTY_TUTUP_TERTUTUP, 0.7)
    # 2. Tengah (we don't zero immediately to allow movement)
    try:
        if GPIO_AVAILABLE and servo_tutup is not None:
            servo_tutup.ChangeDutyCycle(DUTY_TUTUP_TENGAH)
            time.sleep(0.5)
            servo_tutup.ChangeDutyCycle(0)
    except Exception as e:
        print(f"[ERROR] servo_tutup middle move failed: {e}")

    # 3. wait
    print(f"Menunggu selama {WAKTU_BUKA_TUTUP} detik...")
    time.sleep(WAKTU_BUKA_TUTUP)

    # 4. Buka
    pwm_safe_change(servo_tutup, DUTY_TUTUP_TERBUKA, 0.8)
    print("Servo 2 selesai.")


def cleanup_servo():
    """Membersihkan GPIO saat program selesai. Safe to call multiple times."""
    global servo_bin, servo_tutup
    if GPIO_AVAILABLE:
        try:
            print("Membersihkan GPIO...")
            # Stop PWM only if objects exist
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

            GPIO.cleanup()
            print("GPIO dibersihkan!")
        except Exception as e:
            print("cleanup_servo error:", e)
    else:
        print("GPIO cleanup (mode simulasi)")

# Register cleanup on normal program exit
atexit.register(cleanup_servo)
