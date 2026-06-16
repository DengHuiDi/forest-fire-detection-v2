"""
LLM 多模态模块
================

将 YOLO 检测结果与 DeepSeek-VL 多模态模型结合，生成结构化告警文案。

公共接口：
    from backend.llm import DeepSeekVLClient, build_alert_message, AlertContext
"""

from backend.llm.deepseek_client import DeepSeekVLClient, DeepSeekVLConfig
from backend.llm.prompt_templates import build_alert_message, ALERT_SYSTEM_PROMPT
from backend.llm.schema import AlertContext, AlertDescription, Severity, ImageType

__all__ = [
    "DeepSeekVLClient",
    "DeepSeekVLConfig",
    "build_alert_message",
    "ALERT_SYSTEM_PROMPT",
    "AlertContext",
    "AlertDescription",
    "Severity",
    "ImageType",
]
