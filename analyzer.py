"""
analyzer.py: 쟁점 추출 모듈 (3단계)

추출된 텍스트를 Claude API에 전달하여 징계 쟁점을 구조화한다.
"""

from __future__ import annotations

from pathlib import Path

import config
from api_client import ClaudeClient


def _build_combined_text(texts: dict[Path, str]) -> str:
    """여러 파일의 텍스트를 하나의 문자열로 합친다."""
    parts: list[str] = []
    for fp, text in texts.items():
        parts.append(f"### 파일: {fp.name}\n{text.strip()}")
    return "\n\n---\n\n".join(parts)


def extract_issues(texts: dict[Path, str], client: ClaudeClient | None = None) -> str:
    """
    텍스트 맵을 받아 Claude API로 쟁점을 추출하고 결과 문자열을 반환한다.

    Parameters
    ----------
    texts:  {파일경로: 텍스트} – ocr_processor.process_files() 반환값
    client: ClaudeClient 인스턴스 (None이면 내부에서 생성)
    """
    print("\n=== [3단계] 쟁점 추출 ===")

    if not texts:
        print("  [!] 분석할 텍스트가 없습니다.")
        return ""

    if client is None:
        client = ClaudeClient()

    combined = _build_combined_text(texts)
    prompt = config.PROMPTS["extract_issues"].format(text=combined)

    print("  Claude API 호출 중...")
    result = client.complete(prompt)
    print("  [+] 쟁점 추출 완료.\n")
    return result


def save_issues(issues: str, output_path: Path) -> None:
    """추출된 쟁점 텍스트를 파일로 저장한다."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(issues, encoding="utf-8")
    print(f"  [+] 쟁점 저장: {output_path}")
