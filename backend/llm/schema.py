"""
告警 LLM 模块的数据模型
========================

Pydantic 模型用于：
    1. 内部数据流转（检测结果 -> LLM context）
    2. FastAPI 请求/响应序列化
    3. LLM 输出的结构化解析（可选）
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class Severity(str, Enum):
    """火情严重程度"""
    LOW = "low"           # 烟雾/远距小火
    MEDIUM = "medium"     # 明火发展中
    HIGH = "high"         # 大面积/快速蔓延
    CRITICAL = "critical" # 威胁人员/重要设施


class ImageType(str, Enum):
    """图像来源类型"""
    SATELLITE = "satellite"   # 卫星遥感
    DRONE = "drone"           # 无人机航拍
    GROUND = "ground"         # 地面监控
    UNKNOWN = "unknown"


class DetectionItem(BaseModel):
    """单个 YOLO 检测目标"""
    class_name: str = Field(..., description="类别名 fire/smoke")
    confidence: float = Field(..., ge=0.0, le=1.0)
    bbox: Optional[List[float]] = Field(default=None, description="[x1,y1,x2,y2]")

    @field_validator("class_name")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower().strip()


class AlertContext(BaseModel):
    """传给 LLM 的告警上下文"""
    detections: List[DetectionItem] = Field(..., description="YOLO 检测目标列表")
    image_type: ImageType = Field(default=ImageType.UNKNOWN, description="图像来源")
    location_hint: Optional[str] = Field(default=None, description="可选地理位置描述")
    timestamp: Optional[str] = Field(default=None, description="ISO 时间戳")
    weather_hint: Optional[str] = Field(default=None, description="可选天气/风速/温湿度描述")

    def has_fire(self) -> bool:
        return any(d.class_name == "fire" for d in self.detections)

    def has_smoke(self) -> bool:
        return any(d.class_name == "smoke" for d in self.detections)

    def summary(self) -> Dict[str, Any]:
        return {
            "fire_count": sum(1 for d in self.detections if d.class_name == "fire"),
            "smoke_count": sum(1 for d in self.detections if d.class_name == "smoke"),
            "max_confidence": max((d.confidence for d in self.detections), default=0.0),
        }


class AlertDescription(BaseModel):
    """LLM 输出的结构化告警文案"""
    severity: Severity = Field(..., description="严重程度")
    title: str = Field(..., max_length=80, description="一句话标题")
    description: str = Field(..., description="详细描述 (2-4 句)")
    recommendations: List[str] = Field(..., min_length=1, description="建议措施列表")
    confidence_reasoning: Optional[str] = Field(
        default=None, description="模型对判断的简要说明 (可选)"
    )

    def to_alert_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")


class AlertDescribeRequest(BaseModel):
    """POST /api/alert/describe 的请求体"""
    detections: List[DetectionItem] = Field(..., description="YOLO 检测结果")
    image_type: ImageType = ImageType.UNKNOWN
    location_hint: Optional[str] = None
    timestamp: Optional[str] = None
    weather_hint: Optional[str] = None
    image_base64: Optional[str] = Field(
        default=None, description="可选 - 图像 base64 (裸 base64, 不带 data: 前缀)"
    )

    def to_context(self) -> AlertContext:
        return AlertContext(
            detections=self.detections,
            image_type=self.image_type,
            location_hint=self.location_hint,
            timestamp=self.timestamp,
            weather_hint=self.weather_hint,
        )


class AlertDescribeResponse(BaseModel):
    """POST /api/alert/describe 的响应"""
    status: str = "success"
    severity: Severity
    title: str
    description: str
    recommendations: List[str]
    llm_used: bool = Field(..., description="是否真用了 LLM (False 表示走了 fallback 模板)")
    model: Optional[str] = None
    latency_ms: Optional[int] = None
    fallback_reason: Optional[str] = None
