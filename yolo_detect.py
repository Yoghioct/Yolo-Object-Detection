import os
import sys
import argparse
import glob
import time
import atexit
import threading

import cv2
import numpy as np
from ultralytics import YOLO

# Import servo functions only
from yolo_servo import jalankan_servo, cleanup_servo

# Define and parse user input arguments
parser = argparse.ArgumentParser()
parser.add_argument('--model', help='Path to YOLO model file (example: "runs/detect/train/weights/best.pt")',
                    required=True)
parser.add_argument('--source', help='Image source, can be image file ("test.jpg"), \
                    image folder ("test_dir"), video file ("testvid.mp4"), or index of USB camera ("usb0")', 
                    required=True)
parser.add_argument('--thresh', help='Minimum confidence threshold for displaying detected objects (example: "0.4")',
                    default=0.5, type=float)
parser.add_argument('--resolution', help='Resolution in WxH to display inference results at (example: "640x480"), \
                    otherwise, match source resolution',
                    default=None)
parser.add_argument('--record', help='Record results from video or webcam and save it as "demo1.avi". Must specify --resolution argument to record.',
                    action='store_true')

args = parser.parse_args()

# Parse user inputs
model_path = args.model
img_source = args.source
min_thresh = args.thresh
user_res = args.resolution
record = args.record

# async servo
def servo_async(label):
    Thread(target=jalankan_servo, args=(label,), daemon=True).start()

# Check if model file exists and is valid
if (not os.path.exists(model_path)):
    print('ERROR: Model path is invalid or model was not found. Make sure the model filename was entered correctly.')
    sys.exit(1)

# Load the model into memory and get labemap
model = YOLO(model_path, task='detect')
labels = model.names

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
        sys.exit(1)
elif img_source.startswith('usb'):
    source_type = 'usb'
    try:
        usb_idx = int(img_source[3:])
    except Exception:
        print('USB camera index invalid. Use e.g. usb0 or usb1')
        sys.exit(1)
elif img_source.startswith('picamera'):
    source_type = 'picamera'
    try:
        picam_idx = int(img_source[8:])
    except Exception:
        picam_idx = 0
else:
    print(f'Input {img_source} is invalid. Please try again.')
    sys.exit(1)

# Parse user-specified display resolution
resize = False
resW = resH = None
if user_res:
    try:
        resize = True
        resW, resH = int(user_res.split('x')[0]), int(user_res.split('x')[1])
    except Exception:
        print('Resolution must be in the form WIDTHxHEIGHT, e.g. 640x480')
        sys.exit(1)

# Check if recording is valid and set up recording
recorder = None
if record:
    if source_type not in ['video','usb']:
        print('Recording only works for video and camera sources. Please try again.')
        sys.exit(1)
    if not user_res:
        print('Please specify resolution to record video at.')
        sys.exit(1)

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

    if source_type == 'video':
        cap_arg = img_source
        cap = cv2.VideoCapture(cap_arg)
    elif source_type == 'usb':
        cap_arg = usb_idx
        # Use V4L2 backend for USB camera to avoid GStreamer issues
        cap = cv2.VideoCapture(cap_arg, cv2.CAP_V4L2)

    # Set camera or video resolution if specified by user
    if user_res:
        ret = cap.set(3, resW)
        ret = cap.set(4, resH)

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

# Register cleanup to run on exit
atexit.register(cleanup_servo)

# Begin inference loop
try:
    while True:

        t_start = time.perf_counter()

        # Load frame from image source
        if source_type == 'image' or source_type == 'folder': # If source is image or image folder, load the image using its filename
            if img_count >= len(imgs_list):
                print('All images have been processed. Exiting program.')
                break
            img_filename = imgs_list[img_count]
            frame = cv2.imread(img_filename)
            img_count = img_count + 1
        
        elif source_type == 'video': # If source is a video, load next frame from video file
            ret, frame = cap.read()
            if not ret:
                print('Reached end of the video file. Exiting program.')
                break
        
        elif source_type == 'usb': # If source is a USB camera, grab frame from camera
            ret, frame = cap.read()
            if (frame is None) or (not ret):
                print('Unable to read frames from the camera. This indicates the camera is disconnected or not working. Exiting program.')
                break

        elif source_type == 'picamera': # If source is a Picamera, grab frames using picamera interface
            frame_bgra = cap.capture_array()
            frame = cv2.cvtColor(np.copy(frame_bgra), cv2.COLOR_BGRA2BGR)
            if (frame is None):
                print('Unable to read frames from the Picamera. This indicates the camera is disconnected or not working. Exiting program.')
                break

        small_frame = cv2.resize(frame, (416, 416))

        # Resize frame to desired display resolution
        if resize == True and frame is not None:
            frame = cv2.resize(frame,(resW,resH))

        # Run inference on frame
        # results = model(frame, imgsz=320, verbose=False)
        results = model(small_frame, imgsz=320, verbose=False)

        # Extract results
        detections = results[0].boxes

        # Initialize variable for basic object counting example
        object_count = 0

        # Go through each detection and get bbox coords, confidence, and class
        for i in range(len(detections)):

            # Get bounding box coordinates
            xyxy_tensor = detections[i].xyxy.cpu()
            xyxy = xyxy_tensor.numpy().squeeze()
            xmin, ymin, xmax, ymax = xyxy.astype(int)

            # Get bounding box class ID and name
            classidx = int(detections[i].cls.item())
            classname = labels[classidx]

            # Get bounding box confidence
            conf = detections[i].conf.item()

            # Draw box if confidence threshold is high enough
            if conf > min_thresh:

                color = bbox_colors[classidx % 10]
                cv2.rectangle(frame, (xmin,ymin), (xmax,ymax), color, 2)

                label = f'{classname}: {int(conf*100)}%'
                labelSize, baseLine = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                label_ymin = max(ymin, labelSize[1] + 10)
                cv2.rectangle(frame, (xmin, label_ymin-labelSize[1]-10), (xmin+labelSize[0], label_ymin+baseLine-10), color, cv2.FILLED)
                cv2.putText(frame, label, (xmin, label_ymin-7), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

                # Basic example: count the number of objects in the image
                object_count = object_count + 1

                # Jalankan servo untuk kategori yang valid (no cleanup here)
                if classname in ['non-organic', 'organic', 'b3']:
                    try:
                        servo_async(classname)
                    except Exception as e:
                        print("Servo runtime error (caught):", e)

        # Calculate and draw framerate (if using video, USB, or Picamera source)
        if source_type in ['video', 'usb', 'picamera']:
            cv2.putText(frame, f'FPS: {avg_frame_rate:0.2f}', (10,20), cv2.FONT_HERSHEY_SIMPLEX, .7, (0,255,255), 2)

        # Display detection results
        cv2.putText(frame, f'Number of objects: {object_count}', (10,40), cv2.FONT_HERSHEY_SIMPLEX, .7, (0,255,255), 2)
        cv2.imshow('YOLO detection results',frame)
        if recorder is not None:
            recorder.write(frame)

        # Key handling
        if source_type in ['image','folder']:
            key = cv2.waitKey()
        else:
            key = cv2.waitKey(5)

        if key == ord('q') or key == ord('Q'):
            break
        elif key == ord('s') or key == ord('S'):
            cv2.waitKey()
        elif key == ord('p') or key == ord('P'):
            cv2.imwrite('capture.png',frame)

        # Calculate FPS for this frame
        t_stop = time.perf_counter()
        frame_rate_calc = float(1/(t_stop - t_start)) if (t_stop - t_start) > 0 else 0.0

        # Append FPS result to frame_rate_buffer (for finding average FPS over multiple frames)
        if len(frame_rate_buffer) >= fps_avg_len:
            frame_rate_buffer.pop(0)
        frame_rate_buffer.append(frame_rate_calc)

        # Calculate average FPS for past frames
        avg_frame_rate = np.mean(frame_rate_buffer) if frame_rate_buffer else 0.0

finally:
    # Clean up resources ONCE
    print(f'Average pipeline FPS: {avg_frame_rate:.2f}')
    try:
        if source_type in ['video','usb']:
            cap.release()
        elif source_type == 'picamera':
            cap.stop()
    except Exception:
        pass

    if recorder is not None:
        try:
            recorder.release()
        except Exception:
            pass

    try:
        cleanup_servo()
    except Exception as e:
        print('Cleanup servo error:', e)

    cv2.destroyAllWindows()