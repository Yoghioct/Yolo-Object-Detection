#!/bin/bash

echo "Mengecek apakah yolo_detect.py sudah berjalan..."

# Hentikan jika sudah berjalan
PID=$(pgrep -f "yolo_detect.py")

if [ ! -z "$PID" ]; then
    echo "yolo_detect.py sudah berjalan (PID: $PID). Dihentikan..."
    kill -9 $PID
    sleep 1
fi

echo "Menjalankan YOLO..."

cd ~/yolo || exit

source venv/bin/activate

python yolo_detect.py \
    --model my_model_ncnn_model \
    --source usb0 \
    --resolution 416x416