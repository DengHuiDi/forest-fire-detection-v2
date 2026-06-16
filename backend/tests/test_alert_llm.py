"""
告警 LLM 模块测试
==================

覆盖:
    1. Fallback 模板 (无 LLM)
    2. LLM 不可用 / key 缺失 -> 降级
    3. LLM 输出 JSON 解析
    4. 完整端到端: 模拟 LLM 返回 -> 校验 schema

运行 (在 backend 目录):
    cd backend
    python -m pytest tests/test_alert_llm.py -v
或:
    python -m tests.test_alert_llm
"""
import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

# 允许独立运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.llm.schema import (
    AlertContext,
    AlertDescription,
    DetectionItem,
    Severity,
    ImageType,
    AlertDescribeRequest,
)
from backend.llm.prompt_templates import (
    build_alert_message,
    fallback_alert,
    parse_llm_json,
    add_image_to_message,
)
from backend.llm.deepseek_client import (
    DeepSeekVLClient,
    DeepSeekVLConfig,
    LLMUnavailable,
)


class TestFallback(unittest.TestCase):
    """无 LLM 时的规则兜底"""

    def test_no_detections(self):
        ctx = AlertContext(detections=[])
        out = fallback_alert(ctx)
        self.assertEqual(out["severity"], Severity.LOW.value)
        self.assertIn("巡检正常", out["title"])

    def test_only_smoke(self):
        ctx = AlertContext(
            detections=[DetectionItem(class_name="smoke", confidence=0.6)]
        )
        out = fallback_alert(ctx)
        self.assertEqual(out["severity"], Severity.LOW.value)
        self.assertIn("烟雾", out["title"])

    def test_single_fire_medium(self):
        ctx = AlertContext(
            detections=[DetectionItem(class_name="fire", confidence=0.55)]
        )
        out = fallback_alert(ctx)
        self.assertEqual(out["severity"], Severity.MEDIUM.value)

    def test_multi_fire_high(self):
        ctx = AlertContext(
            detections=[
                DetectionItem(class_name="fire", confidence=0.9),
                DetectionItem(class_name="fire", confidence=0.8),
                DetectionItem(class_name="fire", confidence=0.7),
            ]
        )
        out = fallback_alert(ctx)
        self.assertEqual(out["severity"], Severity.HIGH.value)

    def test_mixed(self):
        ctx = AlertContext(
            detections=[
                DetectionItem(class_name="fire", confidence=0.7),
                DetectionItem(class_name="smoke", confidence=0.5),
            ]
        )
        out = fallback_alert(ctx)
        self.assertEqual(out["severity"], Severity.MEDIUM.value)
        # 验证文案里有数字
        self.assertIn("1", out["description"])


class TestPromptBuild(unittest.TestCase):
    """Prompt 构造器"""

    def test_build_message_structure(self):
        ctx = AlertContext(
            detections=[DetectionItem(class_name="fire", confidence=0.85)],
            image_type=ImageType.DRONE,
            location_hint="云南",
            weather_hint="西南风 3 级",
        )
        messages = build_alert_message(ctx)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        # 文本上下文里要有 0.85
        content = messages[1]["content"]
        self.assertIsInstance(content, list)
        text_part = content[0]["text"]
        self.assertIn("0.85", text_part)
        self.assertIn("云南", text_part)
        self.assertIn("西南风", text_part)

    def test_add_image(self):
        ctx = AlertContext(
            detections=[DetectionItem(class_name="fire", confidence=0.9)]
        )
        messages = build_alert_message(ctx)
        messages = add_image_to_message(messages, "iVBORw0KGgo=")
        # 应该有 2 个 content 项: text + image
        self.assertEqual(len(messages[-1]["content"]), 2)
        self.assertEqual(messages[-1]["content"][1]["type"], "image_url")
        self.assertIn("data:image/jpeg;base64,", messages[-1]["content"][1]["image_url"]["url"])


class TestLLMClient(unittest.TestCase):
    """DeepSeekVLClient 单元测试 (mock httpx)"""

    def test_disabled_when_no_key(self):
        # 清掉 .env 加载的 key, 隔离测试
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DEEPSEEK_API_KEY", None)
            cfg = DeepSeekVLConfig(api_key="")
            self.assertFalse(cfg.enabled)
            client = DeepSeekVLClient(cfg)
            with self.assertRaises(LLMUnavailable):
                client._headers()

    def test_chat_success(self):
        cfg = DeepSeekVLConfig(api_key="sk-test")
        client = DeepSeekVLClient(cfg)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "hello"}}]
        }
        with patch("httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.post.return_value = mock_resp
            result = client.chat([{"role": "user", "content": "hi"}])
            self.assertIn("choices", result)
            self.assertEqual(client._extract_content(result), "hello")

    def test_chat_401(self):
        cfg = DeepSeekVLConfig(api_key="sk-bad")
        client = DeepSeekVLClient(cfg)
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        with patch("httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.post.return_value = mock_resp
            with self.assertRaises(LLMUnavailable) as ctx:
                client.chat([{"role": "user", "content": "hi"}])
            self.assertIn("401", str(ctx.exception))

    def test_chat_5xx_retries(self):
        cfg = DeepSeekVLConfig(api_key="sk-test", max_retries=1, timeout=0.1)
        client = DeepSeekVLClient(cfg)
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.text = "Service Unavailable"
        with patch("httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.post.return_value = mock_resp
            with self.assertRaises(LLMUnavailable):
                client.chat([{"role": "user", "content": "hi"}])

    def test_chat_timeout(self):
        import httpx
        cfg = DeepSeekVLConfig(api_key="sk-test", max_retries=0, timeout=0.01)
        client = DeepSeekVLClient(cfg)
        with patch("httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.post.side_effect = (
                httpx.TimeoutException("slow")
            )
            with self.assertRaises(LLMUnavailable):
                client.chat([{"role": "user", "content": "hi"}])


class TestParseLLMJson(unittest.TestCase):
    """LLM 输出解析"""

    def test_pure_json(self):
        s = '{"severity": "high", "title": "x", "description": "y", "recommendations": ["a"]}'
        out = parse_llm_json(s)
        self.assertEqual(out["severity"], "high")

    def test_markdown_wrapped(self):
        s = "```json\n{\"severity\": \"low\"}\n```"
        out = parse_llm_json(s)
        self.assertEqual(out["severity"], "low")

    def test_with_prose(self):
        s = (
            "好的,根据分析...\n"
            "{\"severity\": \"medium\", \"title\": \"t\", \"description\": \"d\", \"recommendations\": []}\n"
            "请注意..."
        )
        out = parse_llm_json(s)
        self.assertEqual(out["severity"], "medium")

    def test_invalid(self):
        with self.assertRaises(Exception):
            parse_llm_json("not json at all")


class TestSchema(unittest.TestCase):
    """Pydantic 模型校验"""

    def test_detection_item(self):
        d = DetectionItem(class_name="Fire", confidence=0.9)  # 大小写归一
        self.assertEqual(d.class_name, "fire")
        self.assertEqual(d.confidence, 0.9)

    def test_confidence_out_of_range(self):
        with self.assertRaises(Exception):
            DetectionItem(class_name="fire", confidence=1.5)

    def test_alert_description(self):
        d = AlertDescription(
            severity=Severity.HIGH,
            title="t",
            description="d",
            recommendations=["r1", "r2"],
        )
        self.assertEqual(d.severity, Severity.HIGH)
        out = d.to_alert_dict()
        self.assertEqual(out["severity"], "high")

    def test_alert_context_summary(self):
        ctx = AlertContext(
            detections=[
                DetectionItem(class_name="fire", confidence=0.9),
                DetectionItem(class_name="smoke", confidence=0.6),
            ]
        )
        s = ctx.summary()
        self.assertEqual(s["fire_count"], 1)
        self.assertEqual(s["smoke_count"], 1)
        self.assertEqual(s["max_confidence"], 0.9)

    def test_request_to_context(self):
        req = AlertDescribeRequest(
            detections=[DetectionItem(class_name="fire", confidence=0.8)],
            image_type=ImageType.SATELLITE,
        )
        ctx = req.to_context()
        self.assertEqual(ctx.image_type, ImageType.SATELLITE)
        self.assertTrue(ctx.has_fire())


class TestEndToEnd(unittest.TestCase):
    """端到端: 模拟 describe 接口的完整逻辑

    关键设计: 我们不 import backend.main.app (它有 startup 事件,
    会用 .env 里的真 key 重新 init_alert_router 覆盖我们的 mock).
    我们构造一个最小 FastAPI app, 只挂上 alert router.
    """

    def _make_app_with_alert(self):
        from fastapi import FastAPI
        from backend.api.alert import router
        app = FastAPI()
        app.include_router(router)
        return app

    def test_describe_with_fallback(self):
        """当 _client 未启用时,描述走 fallback"""
        from backend.api.alert import init_alert_router

        # 隔离 .env 加载, 强制走 llm_disabled 路径
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DEEPSEEK_API_KEY", None)
            cfg = DeepSeekVLConfig(api_key="")
            client = DeepSeekVLClient(cfg)
            init_alert_router(client, cfg)

            from fastapi.testclient import TestClient
            app = self._make_app_with_alert()
            with TestClient(app) as tc:
                r = tc.post(
                    "/api/alert/describe",
                    json={
                        "detections": [
                            {"class_name": "fire", "confidence": 0.9},
                            {"class_name": "fire", "confidence": 0.85},
                        ],
                        "image_type": "drone",
                    },
                )
                self.assertEqual(r.status_code, 200)
                data = r.json()
                self.assertEqual(data["status"], "success")
                self.assertFalse(data["llm_used"])
                self.assertEqual(data["fallback_reason"], "llm_disabled")
                self.assertEqual(data["severity"], "high")

    def test_describe_with_mocked_llm(self):
        """当 LLM 返回有效 JSON 时, 校验完整链路"""
        from backend.api.alert import init_alert_router
        from fastapi.testclient import TestClient

        llm_response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "severity": "high",
                                "title": "🔥 大面积明火",
                                "description": "检测到 2 处明火,呈蔓延趋势,建议立即处置。",
                                "recommendations": [
                                    "启动应急响应",
                                    "通知消防部门",
                                ],
                                "confidence_reasoning": "高置信度 + 多目标",
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

        cfg = DeepSeekVLConfig(api_key="sk-test", model="deepseek-vl2")
        client = DeepSeekVLClient(cfg)

        with patch.object(client, "chat_multimodal", return_value=llm_response["choices"][0]["message"]["content"]):
            init_alert_router(client, cfg)

            app = self._make_app_with_alert()
            with TestClient(app) as tc:
                r = tc.post(
                    "/api/alert/describe",
                    json={
                        "detections": [
                            {"class_name": "fire", "confidence": 0.9},
                            {"class_name": "fire", "confidence": 0.85},
                        ],
                    },
                )
                self.assertEqual(r.status_code, 200)
                data = r.json()
                self.assertEqual(data["status"], "success")
                self.assertTrue(data["llm_used"])
                self.assertEqual(data["severity"], "high")
                self.assertEqual(data["title"], "🔥 大面积明火")
                self.assertEqual(len(data["recommendations"]), 2)

    def test_describe_with_invalid_llm_output(self):
        """当 LLM 返回无效 JSON 时, 走 fallback"""
        from backend.api.alert import init_alert_router
        from fastapi.testclient import TestClient

        cfg = DeepSeekVLConfig(api_key="sk-test")
        client = DeepSeekVLClient(cfg)

        with patch.object(client, "chat_multimodal", return_value="我无法判断,这不是 JSON"):
            init_alert_router(client, cfg)

            app = self._make_app_with_alert()
            with TestClient(app) as tc:
                r = tc.post(
                    "/api/alert/describe",
                    json={
                        "detections": [
                            {"class_name": "fire", "confidence": 0.8},
                        ],
                    },
                )
                self.assertEqual(r.status_code, 200)
                data = r.json()
                self.assertFalse(data["llm_used"])
                self.assertEqual(data["fallback_reason"], "llm_output_parse_error")


if __name__ == "__main__":
    unittest.main(verbosity=2)
