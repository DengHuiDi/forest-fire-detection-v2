"""
DeepSeek-VL 多模态客户端
=========================

特点:
    1. 纯 httpx,无 SDK 依赖 (轻量)
    2. OpenAI 兼容 ChatCompletion 接口
    3. 默认带超时与重试,失败抛 LLMUnavailable
    4. 自动从 backend/.env 加载,环境变量优先级更高
"""
from __future__ import annotations

import os
import time
import logging
from pathlib import Path
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)


def _load_env_file(env_path: Path) -> None:
    """
    简易 .env 加载器 (不依赖 python-dotenv)

    规则:
        - KEY=VALUE 形式, 跳过空行和 # 注释
        - 已存在的环境变量不被覆盖 (环境变量优先)
        - 解析失败也不抛错, 静默忽略
    """
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # 去掉包裹的引号
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception as e:
        logger.warning(f"[DeepSeek] .env 解析失败, 忽略: {e}")


# 模块导入时自动加载 backend/.env
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_load_env_file(_BACKEND_DIR / ".env")


class LLMUnavailable(Exception):
    """LLM 服务不可用 (key 缺失/网络/超时/5xx)"""
    pass


class DeepSeekVLConfig:
    """DeepSeek API 配置"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        text_model: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 2,
    ):
        # 优先级: 显式参数 > 环境变量 > 代码默认
        self.api_key = (
            (api_key or os.environ.get("DEEPSEEK_API_KEY") or "").strip()
        )
        self.base_url = (
            base_url
            or os.environ.get("DEEPSEEK_BASE_URL")
            or "https://api.deepseek.com"
        ).rstrip("/")
        self.model = model or os.environ.get("DEEPSEEK_MODEL") or "deepseek-v4-flash"
        self.text_model = (
            text_model or os.environ.get("DEEPSEEK_TEXT_MODEL") or "deepseek-chat"
        )
        self.timeout = timeout
        self.max_retries = max_retries

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def __repr__(self) -> str:
        return (
            f"DeepSeekVLConfig(model={self.model!r}, enabled={self.enabled}, "
            f"base_url={self.base_url!r})"
        )


class DeepSeekVLClient:
    """
    DeepSeek-VL 客户端封装。

    用法:
        cfg = DeepSeekVLConfig()
        client = DeepSeekVLClient(cfg)
        try:
            result = client.chat(messages)
        except LLMUnavailable as e:
            ...
    """

    def __init__(self, config: Optional[DeepSeekVLConfig] = None):
        self.config = config or DeepSeekVLConfig()

    def _headers(self) -> dict:
        if not self.config.enabled:
            raise LLMUnavailable("DEEPSEEK_API_KEY 未设置")
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    def chat(
        self,
        messages: List[dict],
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 800,
    ) -> dict:
        """
        调用 Chat Completion 接口。

        Args:
            messages: OpenAI 格式 messages 列表 (可含 image_url)
            model: 覆盖默认模型
            temperature: 越低越确定
            max_tokens: 输出 token 上限

        Returns:
            原始响应 dict

        Raises:
            LLMUnavailable: 网络/超时/4xx-5xx
        """
        url = f"{self.config.base_url}/v1/chat/completions"
        use_model = model or self.config.model

        payload = {
            "model": use_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        last_err: Optional[Exception] = None
        for attempt in range(self.config.max_retries + 1):
            try:
                logger.info(
                    f"[DeepSeek] POST {url} model={use_model} attempt={attempt+1}"
                )
                with httpx.Client(timeout=self.config.timeout) as client:
                    resp = client.post(url, json=payload, headers=self._headers())
                if resp.status_code >= 500:
                    raise LLMUnavailable(f"上游 5xx: {resp.status_code} {resp.text[:200]}")
                if resp.status_code == 401:
                    raise LLMUnavailable("API Key 无效 (401)")
                if resp.status_code == 402:
                    raise LLMUnavailable("账户余额不足 (402)")
                if resp.status_code == 429:
                    raise LLMUnavailable("请求频率超限 (429)")
                if resp.status_code >= 400:
                    raise LLMUnavailable(
                        f"客户端错误 {resp.status_code}: {resp.text[:200]}"
                    )
                return resp.json()
            except httpx.TimeoutException as e:
                last_err = e
                logger.warning(f"[DeepSeek] timeout: {e}")
            except httpx.HTTPError as e:
                last_err = e
                logger.warning(f"[DeepSeek] network error: {e}")
            except LLMUnavailable:
                # 4xx 不重试,直接抛
                raise
            except Exception as e:  # 兜底
                last_err = e
                logger.exception(f"[DeepSeek] unexpected: {e}")

            if attempt < self.config.max_retries:
                time.sleep(0.6 * (attempt + 1))

        raise LLMUnavailable(f"重试 {self.config.max_retries} 次仍失败: {last_err}")

    def chat_text(
        self, system: str, user: str, **kwargs
    ) -> str:
        """便捷:纯文本对话,返回 content 字符串"""
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        resp = self.chat(messages, model=self.config.text_model, **kwargs)
        return self._extract_content(resp)

    def chat_multimodal(
        self,
        messages: List[dict],
        **kwargs,
    ) -> str:
        """便捷:多模态,返回 content 字符串"""
        resp = self.chat(messages, **kwargs)
        return self._extract_content(resp)

    @staticmethod
    def _extract_content(resp: dict) -> str:
        try:
            return resp["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise LLMUnavailable(f"响应格式异常: {e}; body={resp}")
