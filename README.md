# 🔥 Forest Fire Detection v2

> **YOLOv11-seg + DeepSeek-VL 多模态告警系统** · 端到端可运行 · 24/24 单元测试通过

无人机/卫星视角下的林火实时检测 + 智能告警。YOLO 完成像素级检测，DeepSeek 多模态大模型生成**可读**的告警文案；模型不可用时自动降级到规则引擎，**告警链路绝不中断**。

![demo](docs/demo.gif) <!-- 替换为真实截图 -->

<p align="left">
  <a href="README_EN.md"><img alt="English" src="https://img.shields.io/badge/lang-English-blue?style=flat-square"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="Next.js 16" src="https://img.shields.io/badge/Next.js-16-black?style=flat-square&logo=next.js">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white">
  <img alt="PyTorch" src="https://img.shields.io/badge/PyTorch-EE4C2C?style=flat-square&logo=pytorch&logoColor=white">
  <img alt="Tests" src="https://img.shields.io/badge/tests-24%2F24-44cc11?style=flat-square">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-yellow?style=flat-square">
</p>

---

## ✨ 为什么不一样

| 痛点 | 这个项目怎么做 |
|---|---|
| YOLO 只能给框和类别 | 接入 **DeepSeek-VL** 多模态，生成**自然语言**告警 + 风险等级 |
| LLM API 不稳定 / 拒答 / 超时 | **5xx/timeout 重试 + 401 立刻降级** + 规则模板兜底 |
| 前端 CORS / 404 杂症 | Next.js 16 **rewrites 反代**到 FastAPI，**单一域名** |
| 测试覆盖薄弱 | **24 个测试**覆盖 schema/解析/重试/fallback/端到端 |

---

## 🏗 架构

```
┌────────────┐    HTTP    ┌──────────────┐    推理    ┌──────────────┐
│  浏览器/前端 │ ─────────▶ │   FastAPI    │ ─────────▶ │  YOLOv11-seg │
│  Next.js 16 │            │   (8000)     │            │  (best.pt)   │
└────────────┘            └──────┬───────┘            └──────────────┘
       ▲                         │ 检测结果
       │                         ▼
       │                  ┌──────────────┐    HTTPS   ┌──────────────┐
       │ 告警 + AI 文案  │ DeepSeekVL    │ ─────────▶ │  DeepSeek    │
       └──────────────── │   Client      │            │     -VL      │
                          └──────┬───────┘            └──────────────┘
                                 │ 失败 / 不可用
                                 ▼
                          ┌──────────────┐
                          │  规则引擎     │  ←─ fallback (永不阻塞)
                          └──────────────┘
```

![arch](docs/architecture.png) <!-- 替换为真实架构图 -->

---

## 🚀 快速开始

### 1. 准备环境

```powershell
# 克隆
git clone https://github.com/<your-user>/forest-fire-detection-v2.git
cd forest-fire-detection-v2

# Python 环境 (conda)
conda create -n yolov11_mask_llm python=3.10 -y
conda activate yolov11_mask_llm
pip install -r backend/requirements.txt  # 如有

# 前端
cd frontend
npm install
cd ..
```

### 2. 配置 DeepSeek API Key (可选)

跳过此步也能跑——会自动降级到规则引擎。

```bash
# backend/.env
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-vl2
```

### 3. 启动

```powershell
# 终端 1: 后端
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 终端 2: 前端
cd frontend
npm run dev
```

打开 `http://localhost:3000` —— 上传图片即可检测。

---

## 🧪 测试

```powershell
conda activate yolov11_mask_llm
python -m pytest backend/tests/test_alert_llm.py -v
```

**结果**：✅ **24/24 passed in 4.59s**

| 模块 | 覆盖点 |
|---|---|
| `TestSchema` | Pydantic 模型 / 范围校验 / 归一化 |
| `TestParseLLMJson` | 纯 JSON / Markdown 包裹 / 散文混合 / 无效 |
| `TestLLMClient` | 401 / 5xx 重试 / timeout / 成功 / 无 key 禁用 |
| `TestFallback` | 规则引擎：单火 / 多火 / 仅烟 / 无目标 / 中高等级 |
| `TestPromptBuild` | 系统消息 / 用户消息 / 多模态 image_url |
| `TestEndToEnd` | fallback / mock LLM / 无效输出降级 |

---

## 🛠 技术栈

| 类别 | 选型 |
|---|---|
| 检测模型 | YOLOv11-seg (ultralytics) · 自定义 Addmodules (CDFA / AFPN4Head / DynamicHead 等) |
| LLM | DeepSeek-VL (多模态) · deepseek-chat (纯文本备用) |
| 后端 | FastAPI · Pydantic v2 · uvicorn |
| 前端 | Next.js 16 · React 19 · TypeScript · Tailwind 4 · ECharts |
| 测试 | pytest · unittest · FastAPI TestClient |
| 反代 | Next.js `rewrites` → FastAPI (单一域名 3000) |

---

## 🔌 API

### `POST /api/alert/describe`

```json
{
  "detections": [
    { "class_name": "fire",  "confidence": 0.92, "bbox": [120, 80, 300, 260] },
    { "class_name": "smoke", "confidence": 0.71, "bbox": [80, 60, 200, 180] }
  ],
  "image_type": "drone",
  "image_base64": "<可选, 启用多模态>"
}
```

**响应**：

```json
{
  "status": "success",
  "llm_used": true,
  "fallback_reason": null,
  "title": "检测到 1 处明火, 火势中等",
  "description": "...",
  "severity": "medium",
  "confidence": 0.92
}
```

`llm_used=false` 时, `description` 来自规则引擎, `fallback_reason` 标注原因 (`llm_disabled` / `llm_invalid_output` / `llm_401` / `llm_5xx` / `llm_timeout`)。

### `GET /api/alert/status`

```json
{ "enabled": true, "model": "deepseek-vl2", "base_url": "https://api.deepseek.com" }
```

前端用此决定是否显示「AI 智能生成」徽标。

---

## 🧠 设计取舍

- **多模态 LLM 是"加分项"而非"主路径"**：fire detection 才是核心业务，告警文案即使降级到模板也不影响告警本身。**永远不阻塞**。
- **同步调用 vs 流式**：告警文案是 50-200 字短文本，**同步调用延迟可接受**，流式收益不大。
- **Next.js rewrites 而非 CORS**：同源避免 90% 的 CORS / cookie / 预检麻烦。
- **简易 .env loader 而非 python-dotenv**：减少一个依赖，启动也快。

---

## 📁 目录结构

```
forest_fire_deteciton_v2/
├── backend/
│   ├── api/
│   │   └── alert.py          # /api/alert/* 路由
│   ├── llm/
│   │   └── deepseek_client.py  # DeepSeek VL 客户端 + fallback
│   ├── tests/
│   │   └── test_alert_llm.py   # 24 个测试
│   ├── main.py
│   └── .env
├── frontend/
│   ├── app/
│   │   └── page.tsx            # 主页面
│   ├── components/
│   │   └── YunnanMap.tsx
│   ├── next.config.js          # rewrites 反代
│   └── package.json
├── fire_detect_model/         # 自定义 ultralytics 插件
├── .gitignore
└── README.md
```

---

## 🛣 Roadmap

- [ ] 告警持久化 (SQLite / Postgres)
- [ ] WebSocket 实时推送检测结果
- [ ] 告警历史 + 复盘页面
- [ ] 多模态图像一并喂给 LLM（目前仅 detections 文本）
- [ ] Docker Compose 一键启动
- [ ] 性能监控 (Prometheus / OpenTelemetry)

---

## 📜 License

MIT

---

## 🙏 致谢

- [Ultralytics YOLOv11](https://github.com/ultralytics/ultralytics)
- [DeepSeek](https://platform.deepseek.com/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Next.js](https://nextjs.org/)
