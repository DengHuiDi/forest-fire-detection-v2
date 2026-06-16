"""Test script for the fire detection API."""
import cv2
import numpy as np
import urllib.request
import json

# Create a synthetic fire test image
img = np.zeros((640, 640, 3), dtype=np.uint8)
# Draw fire boxes
cv2.rectangle(img, (250, 250), (400, 400), (0, 50, 200), -1)
cv2.rectangle(img, (100, 100), (200, 200), (0, 80, 255), -1)
cv2.imwrite('test_fire.png', img)
print('Test image written: test_fire.png')

# Test via HTTP multipart form
from http.client import HTTPConnection
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from io import BytesIO

# Build multipart request
body = BytesIO()
body.write(b'--boundary\r\n')
body.write(b'Content-Disposition: form-data; name="file"; filename="test_fire.png"\r\n')
body.write(b'Content-Type: image/png\r\n\r\n')

with open('test_fire.png', 'rb') as f:
    img_data = f.read()
body.write(img_data)
body.write(b'\r\n--boundary--\r\n')

req = urllib.request.Request(
    'http://127.0.0.1:8000/api/detect',
    data=body.getvalue(),
    method='POST'
)
req.add_header('Content-Type', 'multipart/form-data; boundary=boundary')

print('Sending request to API...')
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
        print('Status:', result.get('status'))
        print('Has fire:', result.get('has_fire'))
        print('Detections:', len(result.get('detections', [])))
        for d in result.get('detections', []):
            print(f'  - {d["class"]} conf={d["confidence"]} bbox={[round(x,1) for x in d["bbox"]]}')
        img_len = len(result.get('image_base64', ''))
        print(f'Image base64 length: {img_len}')
        if img_len > 0:
            print('SUCCESS - Backend API works correctly!')
        else:
            print('WARNING - No annotated image returned')
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
