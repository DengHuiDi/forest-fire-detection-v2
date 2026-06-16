"""
DeepSeek-VL 的告警文案 prompt 模板
====================================

设计原则:
    1. 强制结构化 JSON 输出 (避免模型自由发挥)
    2. 把 YOLO 检测结果作为强先验注入 (不让 VLM 幻觉)
    3. 图像作为补充证据 (让 VLM 验证 YOLO + 补环境描述)
"""
from __future__ import annotations

import json
from typing import List

from backend.llm.schema import AlertContext, Severity


# ============================================================================
# System Prompt
# ============================================================================
ALERT_SYSTEM_PROMPT = """你是森林防火智能告警分析助手。任务:根据 YOLO 检测器给出的目标列表,以及提供的图像(如有),生成结构化告警文案。

# 输出要求 (必须严格遵守)
- 仅输出**一个 JSON 对象**,不要任何解释/前言/后语/Markdown 代码块包裹
- 字段:
  - severity: low | medium | high | critical
  - title: <= 24 字,告警一句话标题
  - description: 60-150 字,中文,描述火情/烟雾态势
  - recommendations: 1-4 条具体建议
  - confidence_reasoning: <= 50 字,简述判断依据

# 严重程度判定参考
- low: 仅烟雾,无明火,或远处小火
- medium: 1 处明火,处于初起阶段
- high: 多处明火 / 大面积 / 高置信度
- critical: 威胁居民区/重要设施/快速蔓延

# 建议措施参考
- low: 持续监控、复核图像
- medium: 派遣护林员现场核实
- high: 启动扑救队伍,通知应急部门
- critical: 立即启动应急响应,疏散周边,联系消防
"""


# ============================================================================
# User Prompt 构造器
# ============================================================================
def build_alert_message(context: AlertContext) -> List[dict]:
    """
    构造发给 DeepSeek-VL 的 messages 列表 (OpenAI Chat Completion 格式)。

    如果有图像,作为第一条 user message 的一部分传入 (data URL);
    YOLO 检测结果始终以纯文本注入,确保模型不幻觉。
    """
    summary = context.summary()
    detections_brief = [
        {
            "class": d.class_name,
            "conf": round(d.confidence, 3),
            "bbox": d.bbox,
        }
        for d in context.detections
    ]

    # 文本上下文 (强先验)
    text_context_lines = [
        "## YOLO 检测结果 (强先验,务必以此为基准)",
        f"- 火点数量: {summary['fire_count']}",
        f"- 烟雾数量: {summary['smoke_count']}",
        f"- 最高置信度: {summary['max_confidence']:.2f}",
        "- 详细目标:",
    ]
    for i, d in enumerate(detections_brief, 1):
        text_context_lines.append(
            f"  {i}. {d['class']} (conf={d['conf']}), bbox={d['bbox']}"
        )

    if context.location_hint:
        text_context_lines.append(f"\n## 地理位置\n{context.location_hint}")
    if context.timestamp:
        text_context_lines.append(f"\n## 时间\n{context.timestamp}")
    if context.weather_hint:
        text_context_lines.append(f"\n## 气象\n{context.weather_hint}")
    if context.image_type and context.image_type.value != "unknown":
        text_context_lines.append(f"\n## 图像来源\n{context.image_type.value}")

    text_context_lines.append(
        "\n## 任务\n"
        "请结合 YOLO 检测结果(强先验)和图像(辅助证据),"
        "按照系统提示中的 JSON schema 输出告警文案。"
        "若图像与 YOLO 严重不一致,以 YOLO 为准并在 confidence_reasoning 中说明。"
    )
    text_payload = "\n".join(text_context_lines)

    # 构造 message
    messages: List[dict] = [
        {"role": "system", "content": ALERT_SYSTEM_PROMPT},
    ]

    # 注:DeepSeek-VL 通过 content 数组传入多模态 (OpenAI Vision 格式)
    user_content: List[dict] = [{"type": "text", "text": text_payload}]
    messages.append({"role": "user", "content": user_content})

    return messages


def add_image_to_message(messages: List[dict], image_base64: str, mime: str = "image/jpeg") -> List[dict]:
    """
    把图像附加到最后一条 user message 的 content 数组中。
    图像需为裸 base64 (不带 data: 前缀),默认 mime 为 jpeg。
    """
    if not messages or messages[-1]["role"] != "user":
        raise ValueError("最后一条消息必须是 user")

    last = messages[-1]
    if isinstance(last["content"], str):
        last["content"] = [{"type": "text", "text": last["content"]}]

    last["content"].append({
        "type": "image_url",
        "image_url": {"url": f"data:{mime};base64,{image_base64}"},
    })
    return messages


# ============================================================================
# Fallback 模板 (LLM 不可用时使用,绝不让告警系统因 LLM 故障停摆)
# ============================================================================
def _pick_severity(context: AlertContext) -> Severity:
    summary = context.summary()
    if summary["fire_count"] == 0 and summary["smoke_count"] == 0:
        return Severity.LOW
    if summary["fire_count"] == 0:
        return Severity.LOW
    if summary["fire_count"] >= 3 or summary["max_confidence"] >= 0.85:
        return Severity.HIGH
    return Severity.MEDIUM


def fallback_alert(context: AlertContext) -> dict:
    """当 LLM 不可用时,基于规则生成告警文案"""
    severity = _pick_severity(context)
    summary = context.summary()

    if severity == Severity.HIGH:
        title = "高风险火情告警"
        description = (
            f"检测到 {summary['fire_count']} 处明火"
            f"{'及 ' + str(summary['smoke_count']) + ' 处烟雾' if summary['smoke_count'] else ''},"
            f"最高置信度 {summary['max_confidence']:.0%}。"
            f"建议立即启动应急响应。"
        )
        recs = [
            "立即派遣扑救队伍前往现场",
            "通知应急管理及森林防火部门",
            "评估周边居民区与设施风险,必要时组织疏散",
        ]
    elif severity == Severity.MEDIUM:
        title = "疑似火情告警"
        description = (
            f"检测到 {summary['fire_count']} 处明火"
            f"{'及 ' + str(summary['smoke_count']) + ' 处烟雾' if summary['smoke_count'] else ''},"
            f"处于初起阶段,最高置信度 {summary['max_confidence']:.0%}。"
            f"建议尽快现场核实。"
        )
        recs = [
            "派遣护林员前往核实",
            "持续监控图像变化",
            "准备扑救装备待命",
        ]
    else:
        if summary["smoke_count"] > 0:
            title = "烟雾检测告警"
            description = (
                f"检测到 {summary['smoke_count']} 处烟雾,未发现明确明火,"
                f"可能存在阴燃或远距火源。"
            )
            recs = ["持续监控", "复核图像,关注变化趋势"]
        else:
            title = "巡检正常"
            description = "未发现火情或烟雾目标。"
            recs = ["继续按计划巡检"]

    return {
        "severity": severity.value,
        "title": title,
        "description": description,
        "recommendations": recs,
        "confidence_reasoning": "基于规则的兜底文案 (LLM 不可用)",
    }


def parse_llm_json(text: str) -> dict:
    """
    健壮地解析 LLM 输出的 JSON。处理:
        - 纯 JSON
        - 被 ```json ``` 包裹
        - 前置/后置废话
    """
    text = text.strip()
    if text.startswith("```"):
        # 去掉 markdown 代码块
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试找到第一个 { 和最后一个 }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise
