"""Test frontend API request format - simulates exactly what browser sends."""
import urllib.request
import json
import os
import cv2
import numpy as np

# Create a more realistic test image
img = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
# Draw some fire-like regions
cv2.rectangle(img, (200, 200), (450, 450), (0, 50, 200), -1)
cv2.rectangle(img, (100, 100), (250, 250), (0, 80, 255), -1)
test_path = os.path.join(os.path.dirname(__file__), "test_frontend.png")
cv2.imwrite(test_path, img)

# Build multipart form data exactly like browser/axios does
boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
with open(test_path, "rb") as f:
    img_data = f.read()

body = "--" + boundary + "\r\n"
body += 'Content-Disposition: form-data; name="file"; filename="test_frontend.png"\r\n'
body += "Content-Type: image/png\r\n\r\n"

if isinstance(img_data, str):
    img_data = img_data.encode("latin1")
body_bytes = body.encode("utf-8") + img_data + ("\r\n--" + boundary + "--\r\n").encode("utf-8")

req = urllib.request.Request(
    "http://127.0.0.1:8000/api/detect",
    data=body_bytes,
    method="POST",
)
req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

print("Testing detection endpoint...")
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
        print(f"Status: {result.get('status')}")
        print(f"Has fire: {result.get('has_fire')}")
        print(f"Detections: {len(result.get('detections', []))}")
        for d in result.get("detections", []):
            print(f"  - {d['class']} conf={d['confidence']:.3f} bbox={[round(x,1) for x in d['bbox']]}")
        img_len = len(result.get("image_base64", ""))
        print(f"Image base64 length: {img_len}")
        if result.get("status") == "success" and img_len > 0:
            print("SUCCESS!")
        else:
            print("PARTIAL - response received but check details above")
except urllib.error.HTTPError as e:
    body_response = e.read()
    print(f"HTTP Error {e.code}: {e.reason}")
    print(f"Response: {body_response[:1000]}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("\n--- Testing health endpoint ---")
try:
    with urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=5) as resp:
        print(f"Health: {resp.status}")
        print(json.loads(resp.read()))
except Exception as e:
    print(f"Health check failed: {e}")
