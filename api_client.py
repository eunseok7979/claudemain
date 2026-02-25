"""
api_client.py: Claude API 호출 래퍼
"""

from __future__ import annotations

import anthropic

import config


class ClaudeClient:
    """Claude API 단일 진입점."""

    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    def complete(self, prompt: str, system: str = "") -> str:
        """단순 텍스트 완성 요청을 보내고 응답 텍스트를 반환한다."""
        messages = [{"role": "user", "content": prompt}]
        kwargs: dict = {
            "model": config.MODEL_ID,
            "max_tokens": config.MAX_TOKENS,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        response = self._client.messages.create(**kwargs)
        return response.content[0].text
