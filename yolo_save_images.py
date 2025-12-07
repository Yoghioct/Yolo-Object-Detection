"""
YOLO11 Detection - Save Results as Images
Captures frames at interval, runs detection, saves as images in folder
Perfect for reviewing detection results later
"""

import os
import sys
import time
import cv2
import numpy as np
from ultralytics import YOLO
import argparse
from datetime import datetime

# Parse arguments
parser = argparse.ArgumentParser(description='YOLO Detection - Save as Images')
parser.add_argument('--model', required=True, help='Path to YOLO model (e.g., yolo11n.pt)')
parser.add_argument('--camera', type=int, default=1, help='Camera index (default: 1)')
parser.add_argument('--interval', type=float, default=1.0, help='Capture interval in seconds (default: 1.0)')
parser.add_argument('--resolution', default='320x320', help='Resolution WxH (default: 320x320)')
parser.add_argument('--output-folder', default=None, help='Output folder (default: auto-generated with timestamp)')
parser.add_argument('--thresh', type=float, default=0.5, help='Confidence threshold (default: 0.5)')
parser.add_argument('--max-frames', type=int, default=0, help='Maximum frames to capture (0 = unlimited)')
parser.add_argument('--save-original', action='store_true', help='Also save original frame without detection boxes')

args = parser.parse_args()

# Configuration
MODEL_PATH = args.model
CAMERA_INDEX = args.camera
CAPTURE_INTERVAL = args.interval
CONFIDENCE_THRESHOLD = args.thresh
MAX_FRAMES = args.max_frames
SAVE_ORIGINAL = args.save_original

# Parse resolution
resW, resH = map(int, args.resolution.split('x'))

# Create output folder
if args.output_folder:
    OUTPUT_FOLDER = args.output_folder
else:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUTPUT_FOLDER = f'yolo_detections_{timestamp}'

# Create folders
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
if SAVE_ORIGINAL:
    ORIGINAL_FOLDER = os.path.join(OUTPUT_FOLDER, 'original')
    os.makedirs(ORIGINAL_FOLDER, exist_ok=True)

print(f"\n{'='*70}")
print(f"YOLO Detection - Save as Images")
print(f"{'='*70}")
print(f"Model: {MODEL_PATH}")
print(f"Camera Index: {CAMERA_INDEX}")
print(f"Resolution: {resW}x{resH}")
print(f"Interval: {CAPTURE_INTERVAL}s")
print(f"Confidence Threshold: {CONFIDENCE_THRESHOLD}")
print(f"Output Folder: {OUTPUT_FOLDER}")
print(f"Max Frames: {MAX_FRAMES if MAX_FRAMES > 0 else 'Unlimited'}")
print(f"Save Original: {'Yes' if SAVE_ORIGINAL else 'No'}")
print(f"{'='*70}\n")

# Load YOLO model
print("Loading YOLO model...")
model = YOLO(MODEL_PATH)
labels = model.names
print(f"Model loaded! Classes: {len(labels)}")
print(f"Classes: {list(labels.values())}\n")

# Initialize camera
print(f"Opening camera {CAMERA_INDEX}...")
cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)  # Use DirectShow for Windows

if not cap.isOpened():
    print(f"ERROR: Cannot open camera {CAMERA_INDEX}")
    print("Try different camera indices (0, 1, 2, etc.)")
    sys.exit(1)

# Set camera resolution
cap.set(cv2.CAP_PROP_FRAME_WIDTH, resW)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resH)

# Get actual resolution
actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"Camera opened! Actual resolution: {actual_width}x{actual_height}\n")

# Bounding box colors (Tableau 10 color scheme)
bbox_colors = [(164,120,87), (68,148,228), (93,97,209), (178,182,133), (88,159,106),
               (96,202,231), (159,124,168), (169,162,241), (98,118,150), (172,176,184)]

# Initialize variables
last_capture_time = 0
frame_count = 0
total_objects_detected = 0
detection_summary = []

print(f"Starting detection and saving to: {OUTPUT_FOLDER}")
print(f"Press Ctrl+C to stop\n")

try:
    while True:
        current_time = time.time()

        # Check if reached max frames
        if MAX_FRAMES > 0 and frame_count >= MAX_FRAMES:
            print(f"\nReached maximum frames ({MAX_FRAMES}). Stopping...")
            break

        # Check if it's time to capture and process
        if current_time - last_capture_time >= CAPTURE_INTERVAL:
            t_start = time.perf_counter()
            frame_count += 1

            print(f"\n[Frame {frame_count}] Capturing and processing...")

            # Capture frame
            ret, frame = cap.read()
            if not ret or frame is None:
                print("ERROR: Failed to capture frame")
                break

            # Resize if needed
            if frame.shape[1] != resW or frame.shape[0] != resH:
                frame = cv2.resize(frame, (resW, resH))

            # Save original frame if requested
            original_frame = frame.copy()
            if SAVE_ORIGINAL:
                original_filename = os.path.join(ORIGINAL_FOLDER, f'frame_{frame_count:04d}.jpg')
                cv2.imwrite(original_filename, original_frame)

            # Run YOLO inference
            print("  Running YOLO inference...")
            results = model(frame, verbose=False)
            detections = results[0].boxes

            # Process detections
            object_count = 0
            detected_classes = []

            for i in range(len(detections)):
                # Get bounding box coordinates
                xyxy_tensor = detections[i].xyxy.cpu()
                xyxy = xyxy_tensor.numpy().squeeze()
                xmin, ymin, xmax, ymax = xyxy.astype(int)

                # Get class and confidence
                classidx = int(detections[i].cls.item())
                classname = labels[classidx]
                conf = detections[i].conf.item()

                # Draw if confidence is high enough
                if conf > CONFIDENCE_THRESHOLD:
                    color = bbox_colors[classidx % 10]
                    cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), color, 2)

                    # Draw label
                    label = f'{classname}: {int(conf*100)}%'
                    labelSize, baseLine = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                    label_ymin = max(ymin, labelSize[1] + 10)
                    cv2.rectangle(frame, (xmin, label_ymin-labelSize[1]-10),
                                (xmin+labelSize[0], label_ymin+baseLine-10), color, cv2.FILLED)
                    cv2.putText(frame, label, (xmin, label_ymin-7),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

                    object_count += 1
                    detected_classes.append(f"{classname} ({int(conf*100)}%)")

            total_objects_detected += object_count

            # Calculate processing time
            t_stop = time.perf_counter()
            processing_time = t_stop - t_start

            # Draw info overlay on frame
            cv2.putText(frame, f'Frame: {frame_count}', (10, 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.putText(frame, f'Objects: {object_count}', (10, 45),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.putText(frame, f'Time: {processing_time:.2f}s', (10, 70),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            # Add timestamp
            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(frame, timestamp_str, (10, resH - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

            # Save detected frame
            output_filename = os.path.join(OUTPUT_FOLDER, f'detection_{frame_count:04d}.jpg')
            cv2.imwrite(output_filename, frame)

            # Store summary
            detection_summary.append({
                'frame': frame_count,
                'objects': object_count,
                'classes': detected_classes,
                'time': processing_time,
                'timestamp': timestamp_str
            })

            # Print summary
            print(f"  Detected {object_count} objects in {processing_time:.2f}s")
            if object_count > 0:
                print(f"  Classes: {', '.join(detected_classes)}")
            print(f"  Saved to: {output_filename}")

            last_capture_time = current_time

        # Small sleep to prevent busy waiting
        time.sleep(0.05)

except KeyboardInterrupt:
    print("\n\nStopped by user (Ctrl+C)")

finally:
    # Save summary report
    report_file = os.path.join(OUTPUT_FOLDER, 'detection_report.txt')
    with open(report_file, 'w') as f:
        f.write("="*70 + "\n")
        f.write("YOLO Detection Report\n")
        f.write("="*70 + "\n\n")
        f.write(f"Model: {MODEL_PATH}\n")
        f.write(f"Camera Index: {CAMERA_INDEX}\n")
        f.write(f"Resolution: {resW}x{resH}\n")
        f.write(f"Interval: {CAPTURE_INTERVAL}s\n")
        f.write(f"Confidence Threshold: {CONFIDENCE_THRESHOLD}\n")
        f.write(f"Total Frames: {frame_count}\n")
        f.write(f"Total Objects Detected: {total_objects_detected}\n")
        if frame_count > 0:
            f.write(f"Average Objects per Frame: {total_objects_detected/frame_count:.2f}\n")
        f.write("\n" + "="*70 + "\n")
        f.write("Frame-by-Frame Summary\n")
        f.write("="*70 + "\n\n")

        for summary in detection_summary:
            f.write(f"Frame {summary['frame']:04d} - {summary['timestamp']}\n")
            f.write(f"  Objects: {summary['objects']}\n")
            if summary['classes']:
                f.write(f"  Detected: {', '.join(summary['classes'])}\n")
            f.write(f"  Processing Time: {summary['time']:.2f}s\n")
            f.write("\n")

    # Cleanup
    print(f"\n{'='*70}")
    print(f"Summary:")
    print(f"{'='*70}")
    print(f"Total frames processed: {frame_count}")
    print(f"Total objects detected: {total_objects_detected}")
    if frame_count > 0:
        print(f"Average objects per frame: {total_objects_detected/frame_count:.2f}")
    print(f"\nResults saved to: {OUTPUT_FOLDER}")
    print(f"  - Detection images: {frame_count} files")
    if SAVE_ORIGINAL:
        print(f"  - Original images: {frame_count} files in 'original' subfolder")
    print(f"  - Report: {report_file}")
    print(f"{'='*70}\n")

    cap.release()
    cv2.destroyAllWindows()

    print("Done!")
