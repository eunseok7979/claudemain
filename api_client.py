"""
api_client.py: Claude API 호출 래퍼

기능:
  - 단순 완성 (complete): 단일 API 호출
  - 청크 분할 완성 (complete_chunked): 긴 문서를 여러 청크로 나눠 처리
  - 비용 추적 (usage_history / total_usage / print_usage_summary)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import anthropic

import config

logger = logging.getLogger(__name__)

# 청크 분할 기준
# claude-opus-4-6 컨텍스트는 200k 토큰 ≈ 한국어 약 30만 자.
# 시스템 프롬프트·출력 여유분을 남기고 청크당 150,000자로 제한한다.
_CHUNK_CHARS = 150_000
_OVERLAP_CHARS = 2_000   # 청크 경계에서 문맥을 이어주는 중복 문자 수


# ── 사용량 추적 ────────────────────────────────────────────

@dataclass
class UsageStat:
    """API 호출 1회의 토큰 사용량."""
    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


# ── 클라이언트 ─────────────────────────────────────────────

class ClaudeClient:
    """Claude API 단일 진입점.

    사용 예시::

        client = ClaudeClient()
        answer = client.complete("안녕하세요?", system="친절하게 답하세요.")
        client.print_usage_summary()
    """

    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.usage_history: list[UsageStat] = []

    # ── 내부 헬퍼 ─────────────────────────────────────────

    def _call(self, messages: list[dict], system: str = "") -> tuple[str, UsageStat]:
        """실제 API 요청을 수행하고 (응답 텍스트, 사용량)을 반환한다."""
        kwargs: dict = {
            "model": config.MODEL_ID,
            "max_tokens": config.MAX_TOKENS,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        response = self._client.messages.create(**kwargs)

        usage = UsageStat(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        self.usage_history.append(usage)

        logger.info(
            "API 호출 완료 | 입력 %d tok | 출력 %d tok | 누적 합계 %d tok",
            usage.input_tokens,
            usage.output_tokens,
            self.total_usage.total_tokens,
        )
        return response.content[0].text, usage

    @staticmethod
    def _split_chunks(
        text: str,
        chunk_size: int = _CHUNK_CHARS,
        overlap: int = _OVERLAP_CHARS,
    ) -> list[str]:
        """텍스트를 chunk_size 문자 단위로 분할한다.

        인접한 청크는 overlap 문자만큼 겹쳐 문맥 단절을 최소화한다.
        """
        if len(text) <= chunk_size:
            return [text]

        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start = end - overlap
        return chunks

    # ── 공개 인터페이스 ────────────────────────────────────

    @property
    def total_usage(self) -> UsageStat:
        """지금까지 누적된 토큰 사용량을 반환한다."""
        return UsageStat(
            input_tokens=sum(u.input_tokens for u in self.usage_history),
            output_tokens=sum(u.output_tokens for u in self.usage_history),
        )

    def complete(self, prompt: str, system: str = "") -> str:
        """단순 텍스트 완성 요청을 보내고 응답 텍스트를 반환한다."""
        messages = [{"role": "user", "content": prompt}]
        text, _ = self._call(messages, system)
        return text

    def complete_chunked(
        self,
        text: str,
        chunk_prompt_template: str,
        merge_prompt_template: str,
        system: str = "",
        chunk_size: int = _CHUNK_CHARS,
    ) -> str:
        """긴 텍스트를 청크로 나눠 분석하고 결과를 하나로 통합하여 반환한다.

        Parameters
        ----------
        text:
            분석할 원문 텍스트.
        chunk_prompt_template:
            각 청크를 분석할 프롬프트 템플릿.
            ``{chunk_index}``, ``{total_chunks}``, ``{chunk}`` 자리표시자 사용.
        merge_prompt_template:
            청크별 분석 결과를 통합할 프롬프트 템플릿.
            ``{partial_results}`` 자리표시자 사용.
        system:
            시스템 프롬프트 (청크 분석과 통합 단계에 모두 적용).
        chunk_size:
            청크당 최대 문자 수.
        """
        chunks = self._split_chunks(text, chunk_size)

        if len(chunks) == 1:
            # 분할 불필요: 템플릿에 전체 텍스트를 그대로 주입
            prompt = chunk_prompt_template.format(
                chunk_index=1, total_chunks=1, chunk=text
            )
            return self.complete(prompt, system)

        # 청크별 분석
        print(f"  문서가 길어 {len(chunks)}개 청크로 나눠 분석합니다.")
        partial: list[str] = []
        for i, chunk in enumerate(chunks, start=1):
            print(f"  청크 {i}/{len(chunks)} 분석 중...")
            prompt = chunk_prompt_template.format(
                chunk_index=i, total_chunks=len(chunks), chunk=chunk
            )
            result = self.complete(prompt, system)
            partial.append(f"[청크 {i}/{len(chunks)} 분석 결과]\n{result}")

        # 통합
        print("  청크 결과 통합 중...")
        merge_prompt = merge_prompt_template.format(
            partial_results="\n\n".join(partial)
        )
        return self.complete(merge_prompt, system)

    def print_usage_summary(self) -> None:
        """콘솔에 누적 토큰 사용량 요약을 출력한다."""
        total = self.total_usage
        print(
            f"\n  [비용 추적] 총 API 호출 {len(self.usage_history)}회 | "
            f"입력 {total.input_tokens:,} tok | "
            f"출력 {total.output_tokens:,} tok | "
            f"합계 {total.total_tokens:,} tok"
        )
