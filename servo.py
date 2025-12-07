import os
import sys
import argparse
import glob
import time
# Hapus import threading karena kita tidak menggunakannya lagi untuk sound
# import threading 

import cv2
import numpy as np
# Pastikan Anda sudah menginstal ultralytics
try:
    from ultralytics import YOLO 
    print("STATUS: Ultralytics YOLO berhasil dimuat.")
except ImportError:
    print("FATAL ERROR: Ultralytics YOLO tidak terinstal atau gagal dimuat.")
    sys.exit(1)


# ========== KONFIGURASI AUDIO (PYGAME) ==========
PYGAME_AVAILABLE = False
# Objek Sound yang akan di-preload
snd_b3 = None
snd_organic = None
snd_non = None
snd_fail = None

try:
    import pygame
    # PENTING: Inisialisasi mixer di sini agar potensi crash terjadi di awal
    pygame.mixer.init() 
    PYGAME_AVAILABLE = True
    print("STATUS: Pygame Mixer berhasil diinisialisasi.")
except ImportError:
    print("WARNING: Pygame tidak tersedia. Suara dinonaktifkan.")
except Exception as e:
    print(f"FATAL WARNING: Gagal inisialisasi Pygame Mixer: {e}. Suara dinonaktifkan.")

# Definisikan file suara sesuai permintaan
SOUND_B3 = 'b3.mp3'
SOUND_ORGANIC = 'organic.mp3'
SOUND_NON_ORGANIC = 'non-organic.mp3'
SOUND_FAIL = 'waste-cant-detect.mp3' # Suara gagal (opsional)

# >>> SOLUSI #2: PRELOAD SEMUA SOUND
if PYGAME_AVAILABLE:
    try:
        snd_b3 = pygame.mixer.Sound(SOUND_B3)
        snd_organic = pygame.mixer.Sound(SOUND_ORGANIC)
        snd_non = pygame.mixer.Sound(SOUND_NON_ORGANIC)
        snd_fail = pygame.mixer.Sound(SOUND_FAIL)
        print("STATUS: Semua file audio berhasil di-preload.")
    except Exception as e:
        print(f"WARNING: Gagal me-load file audio: {e}. Pygame dinonaktifkan.")
        PYGAME_AVAILABLE = False

# >>> SOLUSI #1: FUNGSI play_sound() BARU (Non-Threading)
def play_sound(sound_obj):
    """Memutar objek Sound yang sudah di-preload."""
    if PYGAME_AVAILABLE and sound_obj is not None:
        try:
            # Mainkan di Channel 0 (play() bersifat non-blocking)
            pygame.mixer.Channel(0).play(sound_obj) 
        except Exception as e:
            print(f"ERROR playing sound: {e}")
    elif not PYGAME_AVAILABLE:
        print(f"[SIMULASI AUDIO] Memainkan suara.")
    elif sound_obj is None:
        print(f"[SIMULASI AUDIO] Sound object is None/File tidak ditemukan.")

# Try to import RPi.GPIO for servo control (only available on Raspberry Pi)
GPIO_AVAILABLE = False
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
    print("STATUS: RPi.GPIO berhasil dimuat.")
except ImportError:
    print("WARNING: RPi.GPIO tidak tersedia. Kontrol Servo dinonaktifkan.")

# Define and parse user input arguments

parser = argparse.ArgumentParser()
parser.add_argument('--model', help='Path to YOLO model file (example: "runs/detect/train/weights/best.pt")',
                     required=True)
parser.add_argument('--source', help='Image source, can be image file ("test.jpg"), \
                     image folder ("test_dir"), video file ("testvid.mp4"), or index of USB camera ("usb0")',
                     default='usb0')
parser.add_argument('--thresh', help='Minimum confidence threshold for displaying detected objects (example: "0.4")',
                     default=0.5)
parser.add_argument('--resolution', help='Resolution in WxH to display inference results at (example: "640x480"), \
                     otherwise, match source resolution',
                     default='416x416')
parser.add_argument('--record', help='Record results from video or webcam and save it as "demo1.avi". Must specify --resolution argument to record.',
                     action='store_true')

args = parser.parse_args()


# Parse user inputs
model_path = args.model
img_source = args.source
min_thresh = args.thresh
user_res = args.resolution
record = args.record

# Check if model file exists and is valid
if (not os.path.exists(model_path)):
    print('ERROR: Model path is invalid or model was not found. Make sure the model filename was entered correctly.')
    sys.exit(0)

# Load the model into memory and get labemap
print(f"STATUS: Memuat model YOLO dari {model_path}...")
try:
    # Baris ini SANGAT KRITIS dan bisa menyebabkan Segmentation Fault/Memory Crash
    model = YOLO(model_path, task='detect') 
    labels = model.names
    print("STATUS: Model YOLO berhasil dimuat.")
except Exception as e:
    print(f"FATAL ERROR: Gagal memuat model YOLO. Ini bisa jadi sumber SegFault: {e}")
    sys.exit(1)

# Optimize model for inference speed
#model.fuse()  # Fuse Conv2d + BatchNorm layers for faster inference

# ========== KONFIGURASI SERVO ==========
SERVO_BIN_PIN = 11      # servo 1 (Pembagi Kategori) - BOARD PIN 11
SERVO_LID_PIN = 13      # servo 2 (Pembuka/Penutup) - BOARD PIN 13

# DUTY CYCLE HASIL KALIBRASI (dari script servo yang sudah dikalibrasi)
DUTY_ORG = 5.0      # Organic (kanan)
DUTY_NON = 9.53     # Non-organic (kiri)
DUTY_B3  = 7.0      # Posisi default (B3)
BACK_ORG = 9.5      # Balik ke B3 dari Organic
BACK_NON = 4.1      # Balik ke B3 dari Non-organic

# Servo 2 (Tutup) duty cycle
DUTY_TUTUP_TERTUTUP = 2.5   # Tutup ditutup
DUTY_TUTUP_TENGAH = 7.5     # Posisi tengah
DUTY_TUTUP_TERBUKA = 11.5   # Tutup dibuka

WAKTU_ROTASI = 1.0          # Waktu tunggu rotasi bin (detik)
WAKTU_BUKA_TUTUP = 3.5      # Waktu tunggu saat tutup terbuka (detik)

servo_sedang_jalan = False  # Cek apakah servo sedang bergerak

# Inisialisasi GPIO untuk kontrol servo
if GPIO_AVAILABLE == True:
    # Bersihkan GPIO terlebih dahulu untuk menghindari warning
    GPIO.setwarnings(False)
    GPIO.cleanup()

    GPIO.setmode(GPIO.BOARD)  # Gunakan BOARD mode sesuai script kalibrasi
    GPIO.setup(SERVO_BIN_PIN, GPIO.OUT)
    GPIO.setup(SERVO_LID_PIN, GPIO.OUT)

    # Buat PWM untuk servo (50Hz untuk servo standar)
    servo_bin = GPIO.PWM(SERVO_BIN_PIN, 50)    # Servo untuk putar bin
    servo_tutup = GPIO.PWM(SERVO_LID_PIN, 50)  # Servo untuk buka tutup

    servo_bin.start(0)
    servo_tutup.start(0)

    # KOREKSI AUDIO: Menghapus pemanggilan SOUND_B3 di sini
    def servo1_goto(duty):
        """Menggerakkan Servo1 (Bin) ke duty cycle tertentu."""
        # Suara sekarang hanya dipanggil di fungsi jalankan_servo
        servo_bin.ChangeDutyCycle(duty)
        time.sleep(WAKTU_ROTASI) 
        servo_bin.ChangeDutyCycle(0)
        time.sleep(0.2)

    def servo2_buka_tutup():
        """
        Menggerakkan Servo2 (Tutup) dengan urutan:
        Tutup -> Tengah -> Tunggu -> Buka
        """
        print("Servo 2 mulai buka/tutup...")

        # 1. Tutup
        servo_tutup.ChangeDutyCycle(DUTY_TUTUP_TERTUTUP)
        time.sleep(0.7)

        # 2. Gerak ke Tengah (posisi netral)
        servo_tutup.ChangeDutyCycle(DUTY_TUTUP_TENGAH)
        time.sleep(0.5)

        # 3. Waktu Tunggu DIAM (mematikan sinyal agar servo diam)
        print(f"Menunggu selama {WAKTU_BUKA_TUTUP} detik...")
        servo_tutup.ChangeDutyCycle(0)
        time.sleep(WAKTU_BUKA_TUTUP)

        # 4. Buka
        servo_tutup.ChangeDutyCycle(DUTY_TUTUP_TERBUKA)
        time.sleep(0.8)

        servo_tutup.ChangeDutyCycle(0)
        print("Servo 2 selesai.")  

    def jalankan_servo(jenis_sampah):
        """
        Fungsi untuk menjalankan urutan gerakan servo sesuai jenis sampah.
        Dijalankan secara BLOCKING untuk kestabilan.
        """
        global servo_sedang_jalan
        
        # Di mode BLOCKING, kita tidak perlu Lock/Release, hanya set status global
        if servo_sedang_jalan:
            print(f"Servo sedang sibuk, lewati {jenis_sampah}")
            return
            
        try:
            servo_sedang_jalan = True

            # Tentukan objek sound yang sesuai
            sound_obj_to_play = snd_fail
            if jenis_sampah == 'b3':
                sound_obj_to_play = snd_b3
            elif jenis_sampah == 'organic':
                sound_obj_to_play = snd_organic
            elif jenis_sampah == 'non-organic':
                sound_obj_to_play = snd_non
                
            # >>> SOLUSI #1: Panggil play_sound() LANGSUNG (non-blocking)
            play_sound(sound_obj_to_play)
            time.sleep(0.2) # Jeda sedikit agar suara sempat berbunyi sebelum print selanjutnya

            # Mulai gerakan servo
            if jenis_sampah == 'b3':
                # B3: Hanya buka dan tutup (tidak perlu putar bin)
                print("=== SAMPAH B3 TERDETEKSI ===")
                print("Servo1 sudah di posisi default (B3), tidak bergerak.")
                servo2_buka_tutup()
                print("=== SELESAI ===\n")

            elif jenis_sampah == 'organic':
                # Organik: Putar kanan, buka tutup, kembali ke tengah
                print("=== SAMPAH ORGANIK TERDETEKSI ===")
                print("1. Memutar bin ke KANAN (organic)...")
                servo1_goto(DUTY_ORG) # Servo1 geser

                print("2. Buka/tutup bin...")
                servo2_buka_tutup()

                print("3. Kembali ke B3...")
                servo1_goto(BACK_ORG) # Servo1 geser kembali
                print("=== SELESAI ===\n")

            elif jenis_sampah == 'non-organic':
                # Non-organic: Putar kiri, buka tutup, kembali ke tengah
                print("=== SAMPAH NON-ORGANIC TERDETEKSI ===")
                print("1. Memutar bin ke KIRI (non-organic)...")
                servo1_goto(DUTY_NON) # Servo1 geser

                print("2. Buka/tutup bin...")
                servo2_buka_tutup()

                print("3. Kembali ke B3...")
                servo1_goto(BACK_NON) # Servo1 geser kembali
                print("=== SELESAI ===\n")

            else:
                print(f"Jenis sampah tidak dikenali: {jenis_sampah}")

        finally:
            servo_sedang_jalan = False # Set kembali ke False setelah selesai

    # Inisialisasi servo ke posisi awal
    print("Menginisialisasi servo ke posisi awal...")
    # Servo 1 ke posisi B3, DENGAN PANGGILAN SUARA untuk inisialisasi
    play_sound(snd_b3)
    
    servo_bin.ChangeDutyCycle(DUTY_B3)
    time.sleep(WAKTU_ROTASI)
    servo_bin.ChangeDutyCycle(0)
    print("Servo siap digunakan!\n")
else:
    # Fungsi dummy ketika GPIO tidak tersedia
    def servo1_goto(duty):
        print(f"[SIMULASI] Servo1 bergerak ke duty: {duty}")
        time.sleep(1.2)
        
    def jalankan_servo(jenis_sampah):
        global servo_sedang_jalan
        
        if servo_sedang_jalan:
            print(f"Servo sedang sibuk, lewati {jenis_sampah}")
            return
            
        try:
            servo_sedang_jalan = True
            print(f"[SIMULASI] Servo akan dijalankan untuk: {jenis_sampah}")
            
            # Tentukan objek sound yang sesuai (simulasi)
            sound_obj_to_play = snd_b3 if jenis_sampah == 'b3' else (snd_organic if jenis_sampah == 'organic' else (snd_non if jenis_sampah == 'non-organic' else snd_fail))
            
            # Panggil play_sound() langsung
            play_sound(sound_obj_to_play)
            
            # Simulasi gerakan servo
            if jenis_sampah != 'b3':
                servo1_goto(DUTY_ORG)
                servo1_goto(BACK_ORG)
            else:
                time.sleep(4.0)
                
        finally:
            servo_sedang_jalan = False
            
            
# Parse input to determine if image source is a file, folder, video, or USB camera
img_ext_list = ['.jpg','.JPG','.jpeg','.JPEG','.png','.PNG','.bmp','.BMP']
vid_ext_list = ['.avi','.mov','.mp4','.mkv','.wmv']

if os.path.isdir(img_source):
    source_type = 'folder'
elif os.path.isfile(img_source):
    _, ext = os.path.splitext(img_source)
    if ext in img_ext_list:
        source_type = 'image'
    elif ext in vid_ext_list:
        source_type = 'video'
    else:
        print(f'File extension {ext} is not supported.')
        sys.exit(0)
elif 'usb' in img_source:
    source_type = 'usb'
    usb_idx = int(img_source[3:])
elif 'picamera' in img_source:
    source_type = 'picamera'
    picam_idx = int(img_source[8:])
else:
    print(f'Input {img_source} is invalid. Please try again.')
    sys.exit(0)

print(f"STATUS: Sumber input terdeteksi: {source_type}")

# Parse user-specified display resolution
resize = False
if user_res:
    resize = True
    resW, resH = int(user_res.split('x')[0]), int(user_res.split('x')[1])

# Check if recording is valid and set up recording
if record:
    if source_type not in ['video','usb']:
        print('Recording only works for video and camera sources. Please try again.')
        sys.exit(0)
    if not user_res:
        print('Please specify resolution to record video at.')
        sys.exit(0)
    
    # Set up recording
    record_name = 'demo1.avi'
    record_fps = 30
    recorder = cv2.VideoWriter(record_name, cv2.VideoWriter_fourcc(*'MJPG'), record_fps, (resW,resH))

# Load or initialize image source
if source_type == 'image':
    imgs_list = [img_source]
elif source_type == 'folder':
    imgs_list = []
    filelist = glob.glob(img_source + '/*')
    for file in filelist:
        _, file_ext = os.path.splitext(file)
        if file_ext in img_ext_list:
            imgs_list.append(file)
elif source_type == 'video' or source_type == 'usb':

    if source_type == 'video': cap_arg = img_source
    elif source_type == 'usb': cap_arg = usb_idx
    
    # Baris ini SANGAT KRITIS dan bisa menyebabkan SegFault/Crash
    print(f"STATUS: Mencoba membuka kamera/video: {cap_arg}")
    
    # --- REVISI: Pengecekan dan setting resolusi yang lebih baik ---
    cap = cv2.VideoCapture(cap_arg)
    
    if not cap.isOpened():
        print(f"FATAL ERROR: Gagal membuka kamera/video pada argumen: {cap_arg}. Pastikan perangkat tersedia dan indeks kamera USB sudah benar.")
        sys.exit(1)
        
    # Set camera or video resolution if specified by user
    if user_res:
        print(f"STATUS: Mencoba mengatur resolusi ke {resW}x{resH}...")
        
        # Set resolusi
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, resW)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resH)
        
        # VERIFIKASI RESOLUSI: Cek apakah setting resolusi berhasil
        actual_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        
        if actual_w != resW or actual_h != resH:
            print(f"WARNING: Gagal mengatur resolusi ke {resW}x{resH}. Resolusi aktual: {actual_w:.0f}x{actual_h:.0f}")
            # Nonaktifkan resize jika resolusi aktual tidak sama
            resize = False 
        else:
            print(f"STATUS: Resolusi berhasil diatur ke {resW}x{resH}.")
    # --- AKHIR REVISI ---

elif source_type == 'picamera':
    from picamera2 import Picamera2
    cap = Picamera2()
    cap.configure(cap.create_video_configuration(main={"format": 'XRGB8888', "size": (resW, resH)}))
    cap.start()

# Set bounding box colors (using the Tableu 10 color scheme)
bbox_colors = [(164,120,87), (68,148,228), (93,97,209), (178,182,133), (88,159,106), 
              (96,202,231), (159,124,168), (169,162,241), (98,118,150), (172,176,184)]

# Initialize control and status variables
avg_frame_rate = 0
frame_rate_buffer = []
fps_avg_len = 200
img_count = 0
last_detection_time = 0
detection_interval =  0.5 # Process detection every 0.5 seconds for better performance
last_detections = []  # Store last detection results to display continuously
frame_count = 0
skip_frames = 2  # Process every N frames (1 = every frame, 2 = every other frame)

print("STATUS: Memulai loop inference...")
# Begin inference loop
while True:

    t_start = time.perf_counter()
    current_time = time.perf_counter()

    # Load frame from image source
    if source_type == 'image' or source_type == 'folder':
        if img_count >= len(imgs_list):
            print('All images have been processed. Exiting program.')
            sys.exit(0)
        img_filename = imgs_list[img_count]
        frame = cv2.imread(img_filename)
        img_count = img_count + 1
        
    elif source_type == 'video':
        ret, frame = cap.read()
        if ret == False:
            print('Reached end of the video file. Exiting program.')
            break

    elif source_type == 'usb': # If source is a USB camera, grab frame from camera
        ret, frame = cap.read()
        # JEDA I/O JANGKA PENDEK UNTUK STABILITAS
        time.sleep(0.005) 
        
        if (frame is None) or (ret == False):
            print('CRITICAL: Gagal membaca frame dari kamera. Mungkin terputus atau gagal diinisialisasi.')
            break

    elif source_type == 'picamera': # If source is a Picamera, grab frames using picamera interface
        frame_bgra = cap.capture_array()
        frame = cv2.cvtColor(np.copy(frame_bgra), cv2.COLOR_BGRA2BGR)
        if (frame is None):
            print('Unable to read frames from the Picamera. This indicates the camera is disconnected or not working. Exiting program.')
            break

    # Resize frame to desired display resolution
    if resize == True:
        frame = cv2.resize(frame,(resW,resH))

    # Increment frame counter
    frame_count += 1

    # Only run inference at specified intervals and on selected frames
    if (frame_count % skip_frames == 0) and (current_time - last_detection_time >= detection_interval):
        last_detection_time = current_time

        # Run inference on frame with optimizations
        try:
            results = model(frame, verbose=False, imgsz=416, half=False,conf=0.5, iou=0.45, max_det=1)
        except Exception as e:
            print(f"CRITICAL: Error saat menjalankan inference model: {e}")
            break # Hentikan loop jika inference crash

        # Extract results
        detections = results[0].boxes

        # Clear previous detections and store new ones
        last_detections = []

        # Go through each detection and get bbox coords, confidence, and class
        for i in range(len(detections)):

            # Get bounding box coordinates
            # Ultralytics returns results in Tensor format, which have to be converted to a regular Python array
            xyxy_tensor = detections[i].xyxy.cpu() # Detections in Tensor format in CPU memory
            xyxy = xyxy_tensor.numpy().squeeze() # Convert tensors to Numpy array
            xmin, ymin, xmax, ymax = xyxy.astype(int) # Extract individual coordinates and convert to int

            # Get bounding box class ID and name
            classidx = int(detections[i].cls.item())
            classname = labels[classidx]

            # Get bounding box confidence
            conf = detections[i].conf.item()

            # Store detection if confidence threshold is met
            if conf > min_thresh:
                last_detections.append({
                    'bbox': (xmin, ymin, xmax, ymax),
                    'class': classname,
                    'classidx': classidx,
                    'conf': conf
                })

        # Proses servo HANYA untuk deteksi terbaik (confidence tertinggi) pada interval ini
        if last_detections and not servo_sedang_jalan:
            # Urutkan deteksi berdasarkan confidence (tertinggi dulu)
            sorted_detections = sorted(last_detections, key=lambda x: x['conf'], reverse=True)
            best_detection = sorted_detections[0]
            classname = best_detection['class']

            # Jalankan servo hanya untuk sampah dengan confidence tinggi
            if classname in ['non-organic', 'organic', 'b3']:
                print(f">>> SAMPAH {classname.upper()} TERDETEKSI! (conf: {best_detection['conf']:.2f}) <<<")
                
                # PANGGIL LANGSUNG (BLOCKING MODE)
                jalankan_servo(classname) 
                

    # Draw last detections on every frame for continuous display
    object_count = 0
    for det in last_detections:
        xmin, ymin, xmax, ymax = det['bbox']
        class_name = det['class']
        class_idx = det['classidx']
        conf = det['conf']

        # Draw box
        color = bbox_colors[class_idx % 10]
        cv2.rectangle(frame, (xmin,ymin), (xmax,ymax), color, 2)

        label = f'{class_name}: {int(conf*100)}%'
        labelSize, baseLine = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1) # Get font size
        label_ymin = max(ymin, labelSize[1] + 10) # Make sure not to draw label too close to top of window
        cv2.rectangle(frame, (xmin, label_ymin-labelSize[1]-10), (xmin+labelSize[0], label_ymin+baseLine-10), color, cv2.FILLED) # Draw white box to put label text in
        cv2.putText(frame, label, (xmin, label_ymin-7), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1) # Draw label text

        object_count = object_count + 1

    # Calculate and draw framerate (if using video, USB, or Picamera source)
    if source_type == 'video' or source_type == 'usb' or source_type == 'picamera':
        cv2.putText(frame, f'FPS: {avg_frame_rate:0.2f}', (10,20), cv2.FONT_HERSHEY_SIMPLEX, .7, (0,255,255), 2) # Draw framerate
    
    # Display detection results
    cv2.putText(frame, f'Number of objects: {object_count}', (10,40), cv2.FONT_HERSHEY_SIMPLEX, .7, (0,255,255), 2) # Draw total number of detected objects
    cv2.imshow('YOLO detection results',frame) # Display image
    if record == True: recorder.write(frame)

    # If inferencing on individual images, wait for user keypress before moving to next image. Otherwise, wait 5ms before moving to next frame.
    if source_type == 'image' or source_type == 'folder':
        key = cv2.waitKey()
    elif source_type == 'video' or source_type == 'usb' or source_type == 'picamera':
        key = cv2.waitKey(5)
    
    if key == ord('q') or key == ord('Q'): # Press 'q' to quit
        break
    elif key == ord('s') or key == ord('S'): # Press 's' to pause inference
        cv2.waitKey()
    elif key == ord('p') or key == ord('P'): # Press 'p' to save a picture of results on this frame
        cv2.imwrite('capture.png',frame)
    
    # Calculate FPS for this frame
    t_stop = time.perf_counter()
    frame_rate_calc = float(1/(t_stop - t_start))

    # Append FPS result to frame_rate_buffer (for finding average FPS over multiple frames)
    if len(frame_rate_buffer) >= fps_avg_len:
        temp = frame_rate_buffer.pop(0)
        frame_rate_buffer.append(frame_rate_calc)
    else:
        frame_rate_buffer.append(frame_rate_calc) # <-- SINTAKS TELAH DIPERBAIKI

    # Calculate average FPS for past frames
    avg_frame_rate = np.mean(frame_rate_buffer)


# Clean up
print(f'Average pipeline FPS: {avg_frame_rate:.2f}')
if source_type == 'video' or source_type == 'usb':
    cap.release()
elif source_type == 'picamera':
    cap.stop()
if record == True: recorder.release()
cv2.destroyAllWindows()

# Bersihkan GPIO
if GPIO_AVAILABLE == True:
    print("Membersihkan GPIO...")
    servo_bin.stop()
    servo_tutup.stop()
    GPIO.cleanup()
    print("GPIO dibersihkan!")
    
# >>> SOLUSI AMAN: MENGGANTI .quit() DENGAN .stop() UNTUK MENCEGAH DOUBLE FREE
if PYGAME_AVAILABLE:
    print("Membersihkan Pygame Mixer (safe mode)...")
    try:
        # Hentikan semua playback, tidak mem-free memori internal yang berisiko
        pygame.mixer.stop()  
    except Exception as e:
        print(f"Pygame cleanup error: {e}")
    print("Pygame Mixer selesai dibersihkan.")
# >>> AKHIR SOLUSI AMAN
