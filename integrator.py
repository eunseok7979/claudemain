"""
integrator.py: 통합 문서 생성 모듈 (4단계)

쟁점 분석 결과를 바탕으로 심의 자료 문서를 생성한다.
출력 형식: HWP (pyhwp) 또는 텍스트 폴백
"""

from __future__ import annotations

from pathlib import Path

import config
from api_client import ClaudeClient


# ── HWP 출력 헬퍼 ─────────────────────────────────────────

def _write_hwp(content: str, output_path: Path) -> None:
    """
    pyhwp를 이용해 HWP 파일을 생성한다.
    TODO: pyhwp API에 맞게 구현 필요.
    """
    raise NotImplementedError("HWP 생성 미구현 – pyhwp 통합 필요")


def _write_txt(content: str, output_path: Path) -> None:
    """텍스트 파일로 폴백 저장한다."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


# ── 공개 인터페이스 ───────────────────────────────────────

def generate_document(issues: str, client: ClaudeClient | None = None) -> str:
    """
    쟁점 텍스트를 받아 Claude API로 공식 심의 자료를 생성한다.

    Parameters
    ----------
    issues: analyzer.extract_issues() 반환값
    client: ClaudeClient 인스턴스 (None이면 내부에서 생성)
    """
    print("\n=== [4단계] 통합 문서 생성 ===")

    if not issues:
        print("  [!] 쟁점 데이터가 없습니다.")
        return ""

    if client is None:
        client = ClaudeClient()

    prompt = config.PROMPTS["integrate_document"].format(issues=issues)

    print("  Claude API 호출 중...")
    document = client.complete(prompt)
    print("  [+] 심의 자료 생성 완료.\n")
    return document


def save_document(document: str, output_path: Path, *, use_hwp: bool = False) -> None:
    """
    생성된 문서를 파일로 저장한다.

    Parameters
    ----------
    use_hwp: True면 HWP 형식 시도, 실패 시 .txt로 폴백
    """
    if use_hwp:
        hwp_path = output_path.with_suffix(".hwp")
        try:
            _write_hwp(document, hwp_path)
            print(f"  [+] HWP 저장: {hwp_path}")
            return
        except NotImplementedError as exc:
            print(f"  [!] {exc} → 텍스트로 저장합니다.")

    txt_path = output_path.with_suffix(".txt")
    _write_txt(document, txt_path)
    print(f"  [+] 텍스트 저장: {txt_path}")
