# 🔥 Forest Fire Detection v2

> **YOLOv11-seg + DeepSeek-VL multimodal alerting** · End-to-end runnable · 24/24 tests passing

Real-time forest fire detection from drone/satellite imagery, with **AI-generated alert narratives** powered by a multimodal LLM. Falls back to a rule-based engine when the LLM is unavailable — the alert pipeline **never blocks**.

![demo](docs/demo.gif)

<p align="left">
  <a href="README.md"><img alt="中文" src="https://img.shields.io/badge/lang-中文-red?style=flat-square"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="Next.js 16" src="https://img.shields.io/badge/Next.js-16-black?style=flat-square&logo=next.js">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white">
  <img alt="PyTorch" src="https://img.shields.io/badge/PyTorch-EE4C2C?style=flat-square&logo=pytorch&logoColor=white">
  <img alt="Tests" src="https://img.shields.io/badge/tests-24%2F24-44cc11?style=flat-square">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-yellow?style=flat-square">
</p>

---

## ✨ Why this is different

| Pain point | How this project solves it |
|---|---|
| YOLO only outputs boxes & classes | Plug in **DeepSeek-VL** to turn detections into **natural-language** alert narratives + severity |
| LLM API flaky / refuses / timeouts | **5xx/timeout retry + 401 instant fallback** + rule-based template engine |
| Frontend CORS / 404 hell | Next.js 16 **`rewrites`** to FastAPI — **single origin** |
| Weak test coverage | **24 tests** covering schema, parsing, retry, fallback, end-to-end |

---

## 🏗 Architecture

```
┌────────────┐    HTTP    ┌──────────────┐    inference    ┌──────────────┐
│  Browser   │ ─────────▶ │   FastAPI    │ ──────────────▶ │  YOLOv11-seg │
│  Next.js   │            │   (8000)     │                 │  (best.pt)   │
└────────────┘            └──────┬───────┘                 └──────────────┘
       ▲                         │ detections
       │                         ▼
       │                  ┌──────────────┐    HTTPS    ┌──────────────┐
       │ alert + AI text  │ DeepSeekVL   │ ──────────▶ │  DeepSeek    │
       └──────────────── │   Client     │             │     -VL      │
                          └──────┬───────┘             └──────────────┘
                                 │ failure / unavailable
                                 ▼
                          ┌──────────────┐
                          │ Rule engine  │  ←─ fallback (never blocks)
                          └──────────────┘
```

![architecture](docs/architecture.png)

---

## 🚀 Quick Start

### 1. Prerequisites

```bash
# Clone
git clone https://github.com/<your-user>/forest-fire-detection-v2.git
cd forest-fire-detection-v2

# Python (conda)
conda create -n yolov11_mask_llm python=3.10 -y
conda activate yolov11_mask_llm
pip install -r backend/requirements.txt  # if present

# Frontend
cd frontend
npm install
cd ..
```

### 2. Configure DeepSeek API Key (optional)

The system runs without it — it will just use the rule-based engine.

```bash
# backend/.env
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-vl2
```

### 3. Run

```bash
# Terminal 1 — backend
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — frontend
cd frontend
npm run dev
```

Open `http://localhost:3000` and upload an image.

---

## 🧪 Tests

```bash
conda activate yolov11_mask_llm
python -m pytest backend/tests/test_alert_llm.py -v
```

**Result**: ✅ **24/24 passed in 4.59s**

| Suite | Covers |
|---|---|
| `TestSchema` | Pydantic models / range validation / normalization |
| `TestParseLLMJson` | Pure JSON / Markdown-wrapped / prose-mixed / invalid |
| `TestLLMClient` | 401 / 5xx retry / timeout / success / disabled-when-no-key |
| `TestFallback` | Rule engine: single fire / multi fire / smoke-only / no detection / severity levels |
| `TestPromptBuild` | System message / user message / multimodal `image_url` |
| `TestEndToEnd` | Fallback / mocked LLM / invalid-output graceful degradation |

---

## 🛠 Tech Stack

| Layer | Choice |
|---|---|
| Detection | YOLOv11-seg (ultralytics) · custom Addmodules (CDFA / AFPN4Head / DynamicHead / …) |
| LLM | DeepSeek-VL (multimodal) · deepseek-chat (text-only fallback) |
| Backend | FastAPI · Pydantic v2 · uvicorn |
| Frontend | Next.js 16 · React 19 · TypeScript · Tailwind 4 · ECharts |
| Testing | pytest · unittest · FastAPI TestClient |
| Proxying | Next.js `rewrites` → FastAPI (single origin on :3000) |

---

## 🔌 API

### `POST /api/alert/describe`

Request:

```json
{
  "detections": [
    { "class_name": "fire",  "confidence": 0.92, "bbox": [120, 80, 300, 260] },
    { "class_name": "smoke", "confidence": 0.71, "bbox": [80, 60, 200, 180] }
  ],
  "image_type": "drone",
  "image_base64": "<optional — enables multimodal input>"
}
```

Response:

```json
{
  "status": "success",
  "llm_used": true,
  "fallback_reason": null,
  "title": "1 active fire detected, medium intensity",
  "description": "...",
  "severity": "medium",
  "confidence": 0.92
}
```

When `llm_used=false`, `description` comes from the rule engine and `fallback_reason` is one of:
`llm_disabled` · `llm_invalid_output` · `llm_401` · `llm_5xx` · `llm_timeout`.

### `GET /api/alert/status`

```json
{ "enabled": true, "model": "deepseek-vl2", "base_url": "https://api.deepseek.com" }
```

The frontend uses this to decide whether to show the **"AI-generated"** badge.

---

## 🧠 Design Decisions

- **Multimodal LLM is a "nice-to-have", not the main path.** Fire detection is the core product. Even when the LLM degrades, alerts keep flowing.
- **Synchronous over streaming.** Alert narratives are 50–200 words; sync latency is acceptable and code stays simple.
- **Next.js `rewrites` over CORS.** Same-origin eliminates 90% of the CORS / cookie / preflight pain.
- **Tiny `.env` loader over `python-dotenv`.** One fewer dependency, faster cold start.

---

## 📁 Project Layout

```
forest_fire_deteciton_v2/
├── backend/
│   ├── api/
│   │   └── alert.py             # /api/alert/* routes
│   ├── llm/
│   │   └── deepseek_client.py   # DeepSeek VL client + fallback engine
│   ├── tests/
│   │   └── test_alert_llm.py    # 24 tests
│   ├── main.py
│   └── .env
├── frontend/
│   ├── app/
│   │   └── page.tsx             # Main page
│   ├── components/
│   │   └── YunnanMap.tsx
│   ├── next.config.js           # Rewrites proxy
│   └── package.json
├── fire_detect_model/           # Custom ultralytics Addmodules
├── .gitignore
└── README.md
```

---

## 🛣 Roadmap

- [ ] Persist alerts (SQLite / Postgres)
- [ ] WebSocket real-time detection stream
- [ ] Alert history + replay page
- [ ] Feed the actual image (base64) to the LLM
- [ ] Docker Compose one-command start
- [ ] Observability (Prometheus / OpenTelemetry)

---

## 📜 License

MIT

---

## 🙏 Acknowledgements

- [Ultralytics YOLOv11](https://github.com/ultralytics/ultralytics)
- [DeepSeek](https://platform.deepseek.com/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Next.js](https://nextjs.org/)
