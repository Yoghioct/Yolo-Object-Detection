import os
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
jalankan_servo(classname)
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