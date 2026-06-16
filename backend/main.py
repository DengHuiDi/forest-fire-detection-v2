"""
Forest Fire Detection Backend - FastAPI
Uses the fire_detect_model custom ultralytics with proper Addmodules redirection.
Must be run with: E:\Anaconda3\envs\yolov11_mask\python.exe -m uvicorn main:app ...
"""
import os
import sys
import cv2
import numpy as np
import base64
import torch
import types
from pathlib import Path
from importlib import import_module
import importlib.util

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path
import logging

# LLM 多模态模块
from backend.llm.deepseek_client import DeepSeekVLClient, DeepSeekVLConfig
from backend.api.alert import router as alert_router, init_alert_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("forest_fire_backend")


# ---- Addmodules setup (must be done before any torch.load) ----
FIRE_MODEL_BASE = Path(r"E:\Vibe_coding\Product\forest_fire_deteciton_v2\fire_detect_model")
FIRE_ADDMMODULES = FIRE_MODEL_BASE / "nn" / "Addmodules"


def _create_addmodules_module():
    addmod = types.ModuleType("ultralytics.nn.Addmodules")
    addmod.__file__ = str(FIRE_ADDMMODULES / "__init__.py")
    addmod.__path__ = [str(FIRE_ADDMMODULES)]
    addmod.__package__ = "ultralytics.nn.Addmodules"

    ADDMODULE_FILES = [
        "CDFA",
        "DynamicHead",
        "AFPN4Head",
        "FASFFHead",
        "AdaptiveDilatedDWConvHead",
        "DWRSeg",
        "FocalModulation",
        "MLLA",
        "TransNext",
        "SlimNeck",
        "RepGFPN",
        "MoileNetV3",
    ]

    for fname in ADDMODULE_FILES:
        filepath = FIRE_ADDMMODULES / f"{fname}.py"
        if not filepath.exists():
            continue
        try:
            spec = importlib.util.spec_from_file_location(
                f"ultralytics.nn.Addmodules.{fname}", filepath
            )
            if not spec or not spec.loader:
                continue
            module = importlib.util.module_from_spec(spec)
            for lib_name, short in [
                ("torch", "torch"),
                ("torch.nn", "nn"),
                ("torch.nn.functional", "F"),
                ("numpy", "numpy"),
                ("scipy", "scipy"),
            ]:
                try:
                    setattr(module, short, import_module(lib_name))
                except ImportError:
                    pass
            spec.loader.exec_module(module)
            for k in dir(module):
                if not k.startswith("_"):
                    try:
                        setattr(addmod, k, getattr(module, k))
                    except Exception:
                        pass
        except Exception as e:
            print(f"[WARNING] Could not load Addmodules/{fname}: {e}")

    return addmod


def _ensure_addmodules():
    if "ultralytics.nn.Addmodules" not in sys.modules:
        addmod = _create_addmodules_module()
        sys.modules["ultralytics.nn.Addmodules"] = addmod


_ensure_addmodules()


# ---- FastAPI app ----
app = FastAPI(title="Forest Fire Detection API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 LLM 告警路由
app.include_router(alert_router)

from ultralytics.utils.nms import non_max_suppression

model = None
model_loaded = False
model_names = {0: "fire", 1: "smoke"}
model_nc = 2


def load_model():
    """Load the fire detection model."""
    global model, model_loaded, model_names, model_nc

    weight_path = os.path.join(os.path.dirname(__file__), "weights", "best.pt")
    if not os.path.exists(weight_path):
        print(f"[ERROR] Model weight not found: {weight_path}")
        return False

    print(f"[INFO] Loading fire detection model from: {weight_path}")
    try:
        ckpt = torch.load(weight_path, map_location="cpu", weights_only=False)
        model = (ckpt.get("ema") or ckpt["model"]).float()
        model.eval()

        model_names = getattr(model, "names", {0: "fire", 1: "smoke"})
        model_nc = getattr(model, "nc", 2)

        print(f"[INFO] Model loaded successfully!")
        print(f"[INFO] Classes: {model_names}")
        print(f"[INFO] Number of classes: {model_nc}")
        model_loaded = True
        return True
    except Exception as e:
        print(f"[ERROR] Failed to load model: {e}")
        import traceback
        traceback.print_exc()
        return False


def draw_boxes(img, detections, names):
    """Draw bounding boxes on the image."""
    for det in detections:
        bbox = det["bbox"]
        cls_name = det["class"]
        conf = det["confidence"]

        x1, y1, x2, y2 = map(int, bbox)
        color = (0, 100, 255) if cls_name == "fire" else (255, 165, 0)

        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        label = f"{cls_name} {conf:.2f}"
        (label_w, label_h), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
        )
        cv2.rectangle(
            img, (x1, y1 - label_h - 10), (x1 + label_w, y1), color, -1
        )
        cv2.putText(
            img, label, (x1, y1 - 5),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
        )
    return img


@app.on_event("startup")
async def startup_event():
    """Load model on startup."""
    global model_loaded
    success = load_model()
    if not success:
        print("[ERROR] Model failed to load on startup!")

    # 初始化 LLM 客户端 (告警文案生成)
    llm_config = DeepSeekVLConfig()
    llm_client = DeepSeekVLClient(llm_config)
    init_alert_router(llm_client, llm_config)
    if llm_config.enabled:
        logger.info(f"[LLM] DeepSeek 已启用: model={llm_config.model}")
    else:
        logger.warning("[LLM] DEEPSEEK_API_KEY 未设置,告警将走 fallback 模板")


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok" if model_loaded else "model_not_loaded",
        "model_loaded": model_loaded,
        "classes": model_names,
    }


@app.post("/api/detect")
async def detect_image(file: UploadFile = File(...)):
    """Detect fire/smoke in uploaded image."""
    global model, model_loaded

    if not model_loaded or model is None:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "message": "模型未加载，请检查后端启动日志",
            }
        )

    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "图片解码失败"},
            )

        input_size = 640
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_resized = cv2.resize(img_rgb, (input_size, input_size))

        img_t = (
            torch.from_numpy(img_resized)
            .permute(2, 0, 1)
            .float()
            / 255.0
        )
        img_t = img_t.unsqueeze(0)

        with torch.no_grad():
            out = model(img_t)

        pred = out[0] if isinstance(out, (list, tuple)) else out
        pred = non_max_suppression(pred, conf_thres=0.25, iou_thres=0.45, max_det=100)

        detections = []
        has_fire = False

        for det in pred[0]:
            if len(det) == 0:
                continue
            item = det.cpu().numpy()
            box = item[:4]
            conf = float(item[4])
            cls_int = int(item[5])
            cls_name = model_names.get(cls_int, f"class_{cls_int}")

            detections.append({
                "class": cls_name,
                "confidence": round(conf, 3),
                "bbox": [round(float(x), 1) for x in box],
            })

            if "fire" in cls_name.lower() or "smoke" in cls_name.lower():
                has_fire = True

        annotated = draw_boxes(cv2.resize(img.copy(), (input_size, input_size)), detections, model_names)

        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
        _, buffer = cv2.imencode(".jpg", annotated, encode_param)
        img_base64 = base64.b64encode(buffer).decode("utf-8")

        return {
            "status": "success",
            "has_fire": has_fire,
            "detections": detections,
            "image_base64": img_base64,
        }

    except Exception as e:
        import traceback
        print(f"[ERROR] Detection failed: {e}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"推理失败: {str(e)}"},
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
