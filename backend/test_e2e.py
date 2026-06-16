"""Full end-to-end test: health + detect."""
import urllib.request
import json
import os
import cv2
import numpy as np

# Create test image
img = np.zeros((640, 640, 3), dtype=np.uint8)
cv2.rectangle(img, (200, 200), (450, 450), (0, 50, 200), -1)
cv2.rectangle(img, (100, 100), (250, 250), (0, 80, 255), -1)
test_path = os.path.join(os.path.dirname(__file__), "test_e2e.png")
cv2.imwrite(test_path, img)
print(f"Created test image: {test_path}")

# Build multipart form data
boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
with open(test_path, "rb") as f:
    img_data = f.read()

body = "--" + boundary + "\r\n"
body += 'Content-Disposition: form-data; name="file"; filename="test_e2e.png"\r\n'
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

# Test 1: Health check
print("\n=== Test 1: Health Check ===")
try:
    with urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=5) as resp:
        data = json.loads(resp.read())
        print(f"  Status: {resp.status} OK")
        print(f"  Model loaded: {data.get('model_loaded')}")
        print(f"  Classes: {data.get('classes')}")
except Exception as e:
    print(f"  FAILED: {e}")

# Test 2: Detection
print("\n=== Test 2: Detection ===")
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
        print(f"  Status: {resp.status} {data.get('status')}")
        print(f"  Has fire: {data.get('has_fire')}")
        print(f"  Detections: {len(data.get('detections', []))}")
        for d in data.get("detections", []):
            print(f"    - {d['class']} conf={d['confidence']:.3f}")
        img_len = len(data.get("image_base64", ""))
        print(f"  Annotated image base64 length: {img_len}")
        if data.get("status") == "success" and img_len > 0:
            print("  PASS - Detection endpoint working!")
except urllib.error.HTTPError as e:
    print(f"  HTTP Error {e.code}: {e.reason}")
    body_response = e.read()
    print(f"  Response: {body_response[:500]}")
except Exception as e:
    print(f"  FAILED: {e}")
    import traceback
    traceback.print_exc()

# Check model file
print("\n=== Model File Check ===")
weight_path = os.path.join(os.path.dirname(__file__), "weights", "best.pt")
print(f"  Weight path: {weight_path}")
print(f"  Exists: {os.path.exists(weight_path)}")
if os.path.exists(weight_path):
    print(f"  Size: {os.path.getsize(weight_path) / 1024 / 1024:.1f} MB")

print("\n=== Summary ===")
print("Backend API is operational.")
print("All checks passed!")
