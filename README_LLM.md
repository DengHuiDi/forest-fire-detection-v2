# LLM 多模态告警模块

> 在 V2.0 (YOLO 纯视觉) 之上,引入 DeepSeek-VL 多模态模型,把检测结果升级为结构化、可执行的告警文案。

## 🎯 解决什么问题

| 旧版 (V2.0) | 新版 (V2.5) |
|-------------|-------------|
| 只输出 "fire 0.87" 这种原始数字 | 输出一段人话:"云南楚雄林区检测到 2 处明火,呈蔓延趋势,建议..." |
| 没有严重程度判定 | 自动判定 low/medium/high/critical |
| 没有处置建议 | 给出 1-4 条具体行动建议 |
| LLM 挂了告警也挂 | LLM 挂了自动走规则兜底,告警永远可用 |

## 🏗️ 架构

```
┌─────────────┐    POST /api/detect     ┌─────────────┐
│  Frontend   │ ──────────────────────► │  YOLO 检测  │
│  (Next.js)  │                         │  (现有)     │
└──────┬──────┘                         └─────────────┘
       │                                       │
       │  has_fire=true                        ▼
       │                              detections: [{class, conf, bbox}]
       │                                       │
       │           POST /api/alert/describe    │
       └──────────────────────────────────┐    │
                                          ▼    ▼
                                  ┌──────────────────┐
                                  │   alert.py 路由  │
                                  └────────┬─────────┘
                                           │
                              ┌────────────┴────────────┐
                              ▼                         ▼
                    ┌──────────────────┐      ┌─────────────────┐
                    │ DeepSeek-VL 调用 │      │   规则 Fallback │
                    │  (有 API Key)    │      │  (无 Key/失败)  │
                    └────────┬─────────┘      └────────┬────────┘
                             │                         │
                             └────────────┬────────────┘
                                          ▼
                              ┌───────────────────────┐
                              │  AlertDescribeResponse│
                              │  severity/title/desc/ │
                              │  recommendations      │
                              └───────────────────────┘
```

## 🚀 快速开始

### 1. 安装新依赖

```powershell
conda activate yolov11_mask_llm
cd E:\Vibe_coding\Product\forest_fire_deteciton_v2\backend
pip install -r requirements_llm.txt
```

### 2. 配置 DeepSeek API Key

申请: <https://platform.deepseek.com/>

```powershell
# 方式 A: 环境变量 (推荐)
$env:DEEPSEEK_API_KEY = "sk-your-real-key"

# 方式 B: .env 文件 (需额外 pip install python-dotenv, 并在 main.py 顶部加 load_dotenv)
copy .env.example .env
# 编辑 .env 填入真实 key
```

### 3. 启动后端

```powershell
conda activate yolov11_mask_llm
cd E:\Vibe_coding\Product\forest_fire_deteciton_v2\backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

启动日志会显示:
- ✅ `[LLM] DeepSeek 已启用: model=deepseek-vl2` — 正常
- ⚠️ `[LLM] DEEPSEEK_API_KEY 未设置,告警将走 fallback 模板` — 也能跑

### 4. 启动前端

```powershell
cd E:\Vibe_coding\Product\forest_fire_deteciton_v2\frontend
npm run dev
```

### 5. 测试

```powershell
# 单元测试
cd E:\Vibe_coding\Product\forest_fire_deteciton_v2\backend
python -m pytest tests/test_alert_llm.py -v

# 端到端 (后端运行后)
curl -X POST http://127.0.0.1:8000/api/alert/describe ^
  -H "Content-Type: application/json" ^
  -d "{\"detections\":[{\"class_name\":\"fire\",\"confidence\":0.9}],\"image_type\":\"drone\"}"
```

## 📡 API 接口

### `POST /api/alert/describe`

**请求体**:
```json
{
  "detections": [
    {"class_name": "fire", "confidence": 0.9, "bbox": [120, 80, 300, 260]},
    {"class_name": "smoke", "confidence": 0.6}
  ],
  "image_type": "drone",          // satellite | drone | ground | unknown
  "location_hint": "云南楚雄",     // 可选
  "timestamp": "2026-06-16T10:00:00",  // 可选
  "weather_hint": "西南风 3 级",   // 可选
  "image_base64": "..."           // 可选, 裸 base64
}
```

**响应** (LLM 成功):
```json
{
  "status": "success",
  "severity": "high",
  "title": "🔥 多点明火告警",
  "description": "检测到 2 处明火, 最高置信度 90%, 烟雾伴随, 火势有蔓延风险。",
  "recommendations": [
    "立即派遣扑救队伍",
    "通知应急管理部门",
    "评估周边居民区风险"
  ],
  "llm_used": true,
  "model": "deepseek-vl2",
  "latency_ms": 1850,
  "fallback_reason": null
}
```

**响应** (LLM 不可用,走 fallback):
```json
{
  "status": "success",
  "severity": "high",
  "title": "高风险火情告警",
  "description": "检测到 2 处明火, 最高置信度 90%。建议立即启动应急响应。",
  "recommendations": ["立即派遣扑救队伍前往现场", "..."],
  "llm_used": false,
  "model": null,
  "latency_ms": 5,
  "fallback_reason": "llm_disabled"
}
```

### `GET /api/alert/status`

```json
{"llm_enabled": true, "model": "deepseek-vl2", "base_url": "https://api.deepseek.com"}
```

## 🛡️ 降级策略 (重要)

| 场景 | 行为 | 告警可用? |
|------|------|-----------|
| 正常 | 调用 LLM 生成文案 | ✅ |
| 无 API Key | 走规则模板 | ✅ |
| LLM 超时 | 走规则模板 | ✅ |
| LLM 返回 5xx | 重试 2 次后走规则 | ✅ |
| LLM 返回 401/402 | 立即走规则 | ✅ |
| LLM 返回非 JSON | 走规则 + 标记 parse_error | ✅ |
| 后端任意异常 | 走规则 + 标记 unknown_error | ✅ |

**核心原则**: 告警系统永远不会被 LLM 故障拖垮。

## 🔧 调优建议

### 1. 减少 LLM 调用次数

当前实现:**只在 `has_fire=true` 时调用 LLM** (避免纯烟雾/空检测浪费 token)。

如需更激进:
```python
# backend/api/alert.py
if summary["fire_count"] == 0:
    fb = fallback_alert(context)
    return ...
```
把这条规则的阈值调高 (例如: 单个小火也不调)。

### 2. 改用更便宜的模型

```python
cfg = DeepSeekVLConfig(
    model="deepseek-vl2-small",  # 更便宜版本
    text_model="deepseek-chat",
)
```

### 3. 添加缓存

```python
# TODO: 同图+同类结果, 1 分钟内复用 (避免重复扣费)
```

## 📁 文件清单

```
backend/
├── llm/
│   ├── __init__.py              # 公共导出
│   ├── deepseek_client.py       # DeepSeek-VL HTTP 客户端
│   ├── prompt_templates.py      # Prompt + Fallback
│   └── schema.py                # Pydantic 模型
├── api/
│   ├── __init__.py
│   └── alert.py                 # /api/alert/describe 路由
├── tests/
│   ├── __init__.py
│   └── test_alert_llm.py        # 单元 + 端到端测试
├── main.py                      # 改: 注册路由 + 初始化 LLM
├── requirements_llm.txt         # 新增依赖
└── .env.example                 # API Key 配置

frontend/
└── app/
    └── page.tsx                 # 改: 加 LLM 文案面板 + 严重程度徽标
```

## 🐛 故障排查

| 现象 | 排查 |
|------|------|
| 前端一直显示 "AI 正在分析" | 浏览器 Network 看 `/api/alert/describe` 响应, 是否有错 |
| `llm_used=false` 但 key 配了 | 后端启动时是否设了 env var, 注意 power shell 进程重启会丢 |
| LLM 返回空 | 检查 base_url 是否可达, 国内可能需要代理 |
| 解析失败 | 升级 prompt 让模型更严格按 JSON 输出,或在 `parse_llm_json` 加更多容忍 |

## 📊 成本估算

DeepSeek-VL2 当前价格(参考):
- 输入: ~0.001 元/千 token
- 输出: ~0.002 元/千 token

一次告警大约 1500-2500 token, **单次告警成本约 0.005 元**。
即使一天触发 1000 次火情告警, 成本不到 5 元。

## 🗓️ 后续迭代

- [ ] 加 Redis 缓存, 同图+同类结果 1 分钟内复用
- [ ] 支持历史告警 LLM 复盘 (批量分析)
- [ ] 接入多模态视频帧分析 (取代单帧)
- [ ] 接入更多 LLM 供应商 (Qwen-VL / GPT-4V), 通过环境变量切换
- [ ] 告警分级 → 飞书/钉钉 webhook 推送
