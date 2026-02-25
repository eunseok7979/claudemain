"""
summarizer.py: 요약문 작성 모듈 (5단계)

통합 심의 자료를 받아 위원들용 간결한 요약문을 생성한다.
"""

from __future__ import annotations

from pathlib import Path

import config
from api_client import ClaudeClient


def summarize(document: str, client: ClaudeClient | None = None) -> str:
    """
    심의 자료 텍스트를 받아 Claude API로 요약문을 생성한다.

    Parameters
    ----------
    document: integrator.generate_document() 반환값
    client:   ClaudeClient 인스턴스 (None이면 내부에서 생성)
    """
    print("\n=== [5단계] 요약문 작성 ===")

    if not document:
        print("  [!] 심의 자료가 없습니다.")
        return ""

    if client is None:
        client = ClaudeClient()

    prompt = config.PROMPTS["summarize"].format(document=document)

    print("  Claude API 호출 중...")
    summary = client.complete(prompt)
    print("  [+] 요약문 작성 완료.\n")
    return summary


def save_summary(summary: str, output_path: Path) -> None:
    """요약문을 텍스트 파일로 저장한다."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(summary, encoding="utf-8")
    print(f"  [+] 요약문 저장: {output_path}")
