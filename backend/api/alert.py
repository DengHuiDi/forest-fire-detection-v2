"""
告警相关 API 路由
=================

POST /api/alert/describe
    输入: YOLO 检测结果 (detections) [+ 可选图像]
    输出: 结构化告警文案 (severity/title/description/recommendations)

设计原则:
    - LLM 不可用 -> 走 fallback 模板 (status 仍为 success,但 llm_used=False)
    - 失败/超时 -> 兜底文案
    - 永远不让告警系统因为 LLM 故障停摆
"""
from __future__ import annotations

import time
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from backend.llm.deepseek_client import DeepSeekVLClient, DeepSeekVLConfig, LLMUnavailable
from backend.llm.prompt_templates import (
    build_alert_message,
    add_image_to_message,
    fallback_alert,
    parse_llm_json,
)
from backend.llm.schema import (
    AlertDescribeRequest,
    AlertDescribeResponse,
    AlertDescription,
    Severity,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/alert", tags=["alert"])

# 全局客户端 (由 main.py 启动时注入)
_client: Optional[DeepSeekVLClient] = None
_config: Optional[DeepSeekVLConfig] = None


def init_alert_router(client: DeepSeekVLClient, config: DeepSeekVLConfig) -> None:
    """由 main.py 在 startup 时调用,注入 LLM 客户端"""
    global _client, _config
    _client = client
    _config = config
    logger.info(f"[alert] 路由初始化完成: llm_enabled={config.enabled}")


# ============================================================================
# POST /api/alert/describe
# ============================================================================
@router.post("/describe", response_model=AlertDescribeResponse)
async def describe_alert(req: AlertDescribeRequest):
    """
    根据 YOLO 检测结果生成告警文案。

    典型用法 (前端):
        POST /api/alert/describe
        {
            "detections": [
                {"class_name": "fire", "confidence": 0.87, "bbox": [120,80,300,260]}
            ],
            "image_type": "drone",
            "location_hint": "云南楚雄禄丰县",
            "weather_hint": "西南风 3 级, 气温 28℃, 湿度 35%"
        }
    """
    t0 = time.time()

    # ---- 构造 context ----
    context = req.to_context()
    summary = context.summary()

    # 如果没有任何检测目标,直接走 fallback (不必消耗 LLM)
    if summary["fire_count"] == 0 and summary["smoke_count"] == 0:
        fb = fallback_alert(context)
        return AlertDescribeResponse(
            status="success",
            severity=Severity(fb["severity"]),
            title=fb["title"],
            description=fb["description"],
            recommendations=fb["recommendations"],
            llm_used=False,
            model=None,
            latency_ms=int((time.time() - t0) * 1000),
            fallback_reason="no_detections",
        )

    # ---- 尝试 LLM ----
    if _client is None or _config is None or not _config.enabled:
        fb = fallback_alert(context)
        return AlertDescribeResponse(
            status="success",
            severity=Severity(fb["severity"]),
            title=fb["title"],
            description=fb["description"],
            recommendations=fb["recommendations"],
            llm_used=False,
            model=None,
            latency_ms=int((time.time() - t0) * 1000),
            fallback_reason="llm_disabled",
        )

    try:
        messages = build_alert_message(context)
        if req.image_base64:
            add_image_to_message(messages, req.image_base64)

        content = _client.chat_multimodal(messages)
        parsed = parse_llm_json(content)
        desc = AlertDescription.model_validate(parsed)

        return AlertDescribeResponse(
            status="success",
            severity=desc.severity,
            title=desc.title,
            description=desc.description,
            recommendations=desc.recommendations,
            llm_used=True,
            model=_config.model,
            latency_ms=int((time.time() - t0) * 1000),
        )

    except LLMUnavailable as e:
        logger.warning(f"[alert] LLM 不可用,走 fallback: {e}")
        fb = fallback_alert(context)
        return AlertDescribeResponse(
            status="success",
            severity=Severity(fb["severity"]),
            title=fb["title"],
            description=fb["description"],
            recommendations=fb["recommendations"],
            llm_used=False,
            model=None,
            latency_ms=int((time.time() - t0) * 1000),
            fallback_reason=f"llm_unavailable: {e}"[:200],
        )
    except (ValidationError, ValueError) as e:
        logger.warning(f"[alert] LLM 输出无法解析,走 fallback: {e}")
        fb = fallback_alert(context)
        return AlertDescribeResponse(
            status="success",
            severity=Severity(fb["severity"]),
            title=fb["title"],
            description=fb["description"],
            recommendations=fb["recommendations"],
            llm_used=False,
            model=None,
            latency_ms=int((time.time() - t0) * 1000),
            fallback_reason="llm_output_parse_error",
        )
    except Exception as e:
        logger.exception(f"[alert] 未知错误: {e}")
        # 最后的兜底: 500 但带文案,前端能展示
        fb = fallback_alert(context)
        return AlertDescribeResponse(
            status="success",
            severity=Severity(fb["severity"]),
            title=fb["title"],
            description=fb["description"],
            recommendations=fb["recommendations"],
            llm_used=False,
            model=None,
            latency_ms=int((time.time() - t0) * 1000),
            fallback_reason=f"unknown_error: {type(e).__name__}"[:200],
        )


# ============================================================================
# GET /api/alert/status
# ============================================================================
@router.get("/status")
async def alert_status():
    """查询告警 LLM 状态 (前端可用来决定是否展示 AI 文案徽标)"""
    enabled = _config is not None and _config.enabled
    return {
        "llm_enabled": enabled,
        "model": _config.model if enabled else None,
        "base_url": _config.base_url if enabled else None,
    }
