"""
Safe torch.load wrapper that redirects model checkpoints trained with custom ultralytics
sources to the fire_detect_model Addmodules.

Usage:
    from fire_model_utils import load_fire_model
    ckpt, model = load_fire_model("weights/best.pt")
    # model = ckpt["ema"]  # use EMA weights
"""
import sys
import types
from pathlib import Path
from importlib import import_module
import importlib.util


# The fire_detect_model Addmodules source directory
FIRE_MODEL_BASE = Path(r"E:\Vibe_coding\Product\forest_fire_deteciton_v2\fire_detect_model")
FIRE_ADDMMODULES = FIRE_MODEL_BASE / "nn" / "Addmodules"


def _create_addmodules_module():
    """
    Create a fake 'ultralytics.nn.Addmodules' module by loading all .py files
    from fire_detect_model/nn/Addmodules/ directly.
    """
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
            print(f"[WARNING] Could not load {fname}: {e}")

    return addmod


def ensure_addmodules_registered():
    """Register the Addmodules module in sys.modules if not already present."""
    if "ultralytics.nn.Addmodules" not in sys.modules:
        addmod = _create_addmodules_module()
        sys.modules["ultralytics.nn.Addmodules"] = addmod


def load_fire_model(weight_path, device="cpu"):
    """
    Load a YOLO model checkpoint trained with the fire_detect_model custom ultralytics.

    Args:
        weight_path (str): Path to .pt checkpoint
        device: Device to load model on

    Returns:
        tuple: (checkpoint dict, EMA model)
    """
    import torch

    ensure_addmodules_registered()

    ckpt = torch.load(weight_path, map_location=device, weights_only=False)

    model = (ckpt.get("ema") or ckpt["model"]).float()
    model.eval()
    return ckpt, model


def run_inference(model, image_np, conf_thres=0.25, iou_thres=0.45, max_det=100):
    """
    Run inference on a numpy image (HxWx3 BGR).

    Returns:
        list of dicts with keys: bbox, confidence, class, class_id
    """
    import torch
    from ultralytics.utils import ops as yops

    img_t = torch.from_numpy(image_np).permute(2, 0, 1).float() / 255.0
    img_t = img_t.unsqueeze(0)

    with torch.no_grad():
        out = model(img_t)

    pred = out[0] if isinstance(out, (list, tuple)) else out
    pred = yops.non_max_suppression(
        pred, conf_thres=conf_thres, iou_thres=iou_thres, max_det=max_det
    )

    names = getattr(model, "names", {0: "fire", 1: "smoke"})
    results = []
    for det in pred:
        if len(det):
            for item in det.cpu().numpy():
                box = item[:4]
                conf = float(item[4])
                cls = int(item[5])
                results.append({
                    "bbox": [float(x) for x in box],
                    "confidence": conf,
                    "class": names.get(cls, f"class_{cls}"),
                    "class_id": cls,
                })
        else:
            results.append({
                "bbox": [],
                "confidence": 0.0,
                "class": None,
                "class_id": -1,
            })
    return results
