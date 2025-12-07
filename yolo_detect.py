import os
import sys
import argparse
import glob
import time

import cv2
import numpy as np
from ultralytics import YOLO

# Import modul servo
from yolo_servo import jalankan_servo, cleanup_servo

# ========== ARGUMENT PARSER ==========
parser = argparse.ArgumentParser(description='YOLO Waste Detection System')
parser.add_argument('--model',
                    help='Path to YOLO model file',
                    required=True)
parser.add_argument('--source',
                    help='Source: image file, folder, video, or "usb0" for camera',
                    default='usb0')
parser.add_argument('--thresh',
                    help='Confidence threshold (0.0-1.0)',
                    type=float,
                    default=0.5)
parser.add_argument('--resolution',
                    help='Resolution (WxH), e.g., "640x480"',
                    default='416x416')
parser.add_argument('--record',
                    help='Record video output as demo1.avi',
                    action='store_true')

args = parser.parse_args()

# ========== KONFIGURASI ==========
model_path = args.model
img_source = args.source
min_thresh = args.thresh
user_res = args.resolution
record = args.record

# ========== DETEKSI PARAMETER ==========
detection_interval = 0.5  # Deteksi setiap 0.5 detik
skip_frames = 2           # Proses setiap N frame

# ========== CEK MODEL ==========
if not os.path.exists(model_path):
    print(f'ERROR: Model tidak ditemukan di {model_path}')
    sys.exit(1)

# ========== LOAD MODEL ==========
print(f"STATUS: Memuat model YOLO dari {model_path}...")
try:
    model = YOLO(model_path, task='detect', verbose=False)
    labels = model.names
    print(f"STATUS: Model berhasil dimuat. Classes: {list(labels.values())}")
except Exception as e:
    print(f"FATAL ERROR: Gagal memuat model: {e}")
    sys.exit(1)

# ========== DETEKSI TIPE SOURCE ==========
img_ext_list = ['.jpg', '.JPG', '.jpeg', '.JPEG', '.png', '.PNG', '.bmp', '.BMP']
vid_ext_list = ['.avi', '.mov', '.mp4', '.mkv', '.wmv']

if os.path.isdir(img_source):
    source_type = 'folder'
elif os.path.isfile(img_source):
    _, ext = os.path.splitext(img_source)
    if ext in img_ext_list:
        source_type = 'image'
    elif ext in vid_ext_list:
        source_type = 'video'
    else:
        print(f'ERROR: Format file {ext} tidak didukung.')
        sys.exit(1)
elif 'usb' in img_source:
    source_type = 'usb'
    usb_idx = int(img_source[3:])
elif 'picamera' in img_source:
    source_type = 'picamera'
    picam_idx = int(img_source[8:])
else:
    print(f'ERROR: Input {img_source} tidak valid.')
    sys.exit(1)

print(f"STATUS: Sumber input: {source_type}")

# ========== PARSE RESOLUSI ==========
resize = False
if user_res:
    resize = True
    resW, resH = int(user_res.split('x')[0]), int(user_res.split('x')[1])

# ========== SETUP RECORDING ==========
if record:
    if source_type not in ['video', 'usb']:
        print('ERROR: Recording hanya untuk video dan kamera.')
        sys.exit(1)
    if not user_res:
        print('ERROR: Harus specify resolusi untuk recording.')
        sys.exit(1)

    record_name = 'demo1.avi'
    record_fps = 30
    recorder = cv2.VideoWriter(record_name, cv2.VideoWriter_fourcc(*'MJPG'),
                               record_fps, (resW, resH))

# ========== INISIALISASI SOURCE ==========
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
    cap_arg = img_source if source_type == 'video' else usb_idx

    print(f"STATUS: Membuka kamera/video: {cap_arg}")

    try:
        if source_type == 'usb':
            cap = cv2.VideoCapture(cap_arg, cv2.CAP_V4L2)
            print("STATUS: Menggunakan V4L2 backend")
        else:
            cap = cv2.VideoCapture(cap_arg)
    except Exception as e:
        print(f"FATAL ERROR: Gagal membuka kamera: {e}")
        sys.exit(1)

    if not cap.isOpened():
        print(f"FATAL ERROR: Kamera/video tidak bisa dibuka")
        sys.exit(1)

    # Set resolusi jika diminta
    if user_res:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, resW)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resH)

        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        if actual_w != resW or actual_h != resH:
            print(f"WARNING: Resolusi sebenarnya: {actual_w}x{actual_h}")
            resW, resH = actual_w, actual_h

elif source_type == 'picamera':
    from picamera2 import Picamera2
    cap = Picamera2()
    cap.configure(cap.create_video_configuration(
        main={"format": 'XRGB8888', "size": (resW, resH)}))
    cap.start()

# ========== WARNA BOUNDING BOX ==========
bbox_colors = [(164,120,87), (68,148,228), (93,97,209), (178,182,133), (88,159,106),
               (96,202,231), (159,124,168), (169,162,241), (98,118,150), (172,176,184)]

# ========== VARIABEL TRACKING ==========
avg_frame_rate = 0
frame_rate_buffer = []
fps_avg_len = 200
img_count = 0
last_detection_time = 0
last_detections = []
frame_count = 0
consecutive_errors = 0
max_consecutive_errors = 10

print("=" * 60)
print("STATUS: Memulai deteksi YOLO...")
print("KONTROL:")
print("  Q - Quit (keluar)")
print("  S - Pause (jeda)")
print("  P - Capture screenshot")
print("=" * 60)

# ========== MAIN LOOP ==========
try:
    while True:
        t_start = time.perf_counter()
        current_time = time.perf_counter()

        # ===== BACA FRAME =====
        try:
            if source_type == 'image' or source_type == 'folder':
                if img_count >= len(imgs_list):
                    print('Semua gambar telah diproses.')
                    break
                img_filename = imgs_list[img_count]
                frame = cv2.imread(img_filename)
                img_count += 1

            elif source_type == 'video':
                ret, frame = cap.read()
                if not ret:
                    print('Video selesai.')
                    break

            elif source_type == 'usb':
                ret, frame = cap.read()
                time.sleep(0.005)  # Stabilitas I/O

                if frame is None or not ret:
                    consecutive_errors += 1
                    print(f'WARNING: Gagal baca frame ({consecutive_errors}/{max_consecutive_errors})')

                    if consecutive_errors >= max_consecutive_errors:
                        print('CRITICAL: Kamera terputus.')
                        break

                    time.sleep(0.1)
                    continue
                else:
                    if consecutive_errors > 0:
                        print(f"STATUS: Kamera pulih dari {consecutive_errors} error")
                        consecutive_errors = 0

            elif source_type == 'picamera':
                frame_bgra = cap.capture_array()
                frame = cv2.cvtColor(np.copy(frame_bgra), cv2.COLOR_BGRA2BGR)
                if frame is None:
                    print('ERROR: Picamera terputus.')
                    break

        except Exception as e:
            print(f"ERROR saat baca frame: {e}")
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                print('CRITICAL: Terlalu banyak error.')
                break
            time.sleep(0.1)
            continue

        # ===== RESIZE FRAME =====
        if resize:
            frame = cv2.resize(frame, (resW, resH))

        frame_count += 1

        # ===== JALANKAN DETEKSI =====
        if (frame_count % skip_frames == 0) and \
           (current_time - last_detection_time >= detection_interval):

            last_detection_time = current_time

            try:
                results = model(frame, verbose=False, imgsz=416,
                               conf=min_thresh, iou=0.45, max_det=1)
            except Exception as e:
                print(f"CRITICAL: Error inference: {e}")
                break

            detections = results[0].boxes
            last_detections = []

            # Ekstrak hasil deteksi
            for i in range(len(detections)):
                xyxy_tensor = detections[i].xyxy.cpu()
                xyxy = xyxy_tensor.numpy().squeeze()
                xmin, ymin, xmax, ymax = xyxy.astype(int)

                classidx = int(detections[i].cls.item())
                classname = labels[classidx]
                conf = detections[i].conf.item()

                if conf > min_thresh:
                    last_detections.append({
                        'bbox': (xmin, ymin, xmax, ymax),
                        'class': classname,
                        'classidx': classidx,
                        'conf': conf
                    })

            # ===== JALANKAN SERVO =====
            if last_detections:
                # Ambil deteksi dengan confidence tertinggi
                sorted_detections = sorted(last_detections,
                                          key=lambda x: x['conf'],
                                          reverse=True)
                best_detection = sorted_detections[0]
                classname = best_detection['class']

                # Jalankan servo untuk kategori yang valid
                if classname in ['non-organic', 'organic', 'b3']:
                    print(f">>> DETEKSI: {classname.upper()} " +
                          f"(conf: {best_detection['conf']:.2f}) <<<")
                    jalankan_servo(classname)

        # ===== GAMBAR BOUNDING BOX =====
        object_count = 0
        for det in last_detections:
            xmin, ymin, xmax, ymax = det['bbox']
            class_name = det['class']
            class_idx = det['classidx']
            conf = det['conf']

            # Gambar box
            color = bbox_colors[class_idx % 10]
            cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), color, 2)

            # Gambar label
            label = f'{class_name}: {int(conf*100)}%'
            labelSize, baseLine = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            label_ymin = max(ymin, labelSize[1] + 10)
            cv2.rectangle(frame, (xmin, label_ymin-labelSize[1]-10),
                         (xmin+labelSize[0], label_ymin+baseLine-10), color, cv2.FILLED)
            cv2.putText(frame, label, (xmin, label_ymin-7),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

            object_count += 1

        # ===== TAMPILKAN FPS DAN INFO =====
        if source_type in ['video', 'usb', 'picamera']:
            cv2.putText(frame, f'FPS: {avg_frame_rate:0.2f}', (10, 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        cv2.putText(frame, f'Objects: {object_count}', (10, 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        cv2.imshow('YOLO Waste Detection', frame)

        if record:
            recorder.write(frame)

        # ===== KEYBOARD INPUT =====
        if source_type in ['image', 'folder']:
            key = cv2.waitKey()
        else:
            key = cv2.waitKey(5)

        if key == ord('q') or key == ord('Q'):
            break
        elif key == ord('s') or key == ord('S'):
            cv2.waitKey()
        elif key == ord('p') or key == ord('P'):
            cv2.imwrite('capture.png', frame)
            print("Screenshot disimpan: capture.png")

        # ===== HITUNG FPS =====
        t_stop = time.perf_counter()
        frame_rate_calc = float(1 / (t_stop - t_start))

        if len(frame_rate_buffer) >= fps_avg_len:
            frame_rate_buffer.pop(0)
        frame_rate_buffer.append(frame_rate_calc)

        avg_frame_rate = np.mean(frame_rate_buffer)

except KeyboardInterrupt:
    print("\nProgram dihentikan oleh user.")

# ========== CLEANUP ==========
print(f'Average FPS: {avg_frame_rate:.2f}')

if source_type in ['video', 'usb']:
    cap.release()
elif source_type == 'picamera':
    cap.stop()

if record:
    recorder.release()

cv2.destroyAllWindows()
cleanup_servo()

print("Program selesai.")
