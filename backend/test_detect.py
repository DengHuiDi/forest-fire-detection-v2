"""Test detection API endpoint."""
import urllib.request
import urllib.error
import json
import os
import cv2
import numpy as np

img = np.zeros((640, 640, 3), dtype=np.uint8)
cv2.rectangle(img, (200, 200), (450, 450), (0, 50, 200), -1)
cv2.rectangle(img, (100, 100), (250, 250), (0, 80, 255), -1)
test_path = os.path.join(os.path.dirname(__file__), "test_detect.png")
cv2.imwrite(test_path, img)
print(f"Test image created: {test_path}")

boundary = b"----PythonFormBoundary7MA4YWxkTrZu0gW"
with open(test_path, "rb") as f:
    img_data = f.read()

body = b""
body += b"--" + boundary + b"\r\n"
body += b'Content-Disposition: form-data; name="file"; filename="test_detect.png"\r\n'
body += b"Content-Type: image/png\r\n\r\n"
body += img_data
body += b"\r\n--" + boundary + b"--\r\n"

req = urllib.request.Request(
    "http://127.0.0.1:8000/api/detect",
    data=body,
    method="POST",
)
req.add_header("Content-Type", f"multipart/form-data; boundary={boundary.decode()}")

print("Sending detection request...")
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
        print("Status:", result.get("status"))
        print("Has fire:", result.get("has_fire"))
        print("Detections:", len(result.get("detections", [])))
        for d in result.get("detections", []):
            cls = d["class"]
            conf = d["confidence"]
            bbox = [round(x, 1) for x in d["bbox"]]
            print(f"  - {cls} conf={conf} bbox={bbox}")
        img_len = len(result.get("image_base64", ""))
        print(f"Image base64 length: {img_len}")
        if img_len > 0:
            print("SUCCESS - Backend detection works correctly!")
        else:
            print("WARNING - No annotated image returned")
except urllib.error.HTTPError as e:
    body_resp = e.read()
    print(f"HTTP Error {e.code}: {e.reason}")
    print(f"Response body: {body_resp[:500]}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
