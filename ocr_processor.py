"""
ocr_processor.py: HWP/PDF → 텍스트 전산화 모듈 (2단계)

지원 형식:
  - .hwp  : pyhwp 라이브러리
  - .pdf  : pdfplumber (텍스트 레이어) + pytesseract (이미지 페이지 OCR)
  - .txt / .md : 직접 읽기
"""

from __future__ import annotations

from pathlib import Path


# ── 내부 헬퍼 ─────────────────────────────────────────────

def _extract_hwp(path: Path) -> str:
    """HWP 파일에서 텍스트를 추출한다."""
    # TODO: pyhwp 또는 libreoffice 변환 구현
    raise NotImplementedError(f"HWP 추출 미구현: {path}")


def _extract_pdf(path: Path) -> str:
    """PDF 파일에서 텍스트를 추출한다 (텍스트 레이어 → OCR 순서)."""
    # TODO: pdfplumber로 텍스트 레이어 시도, 빈 페이지는 pytesseract OCR 처리
    raise NotImplementedError(f"PDF 추출 미구현: {path}")


def _extract_plain(path: Path) -> str:
    """일반 텍스트 파일을 그대로 읽는다."""
    return path.read_text(encoding="utf-8", errors="replace")


# ── 공개 인터페이스 ───────────────────────────────────────

SUPPORTED_EXTENSIONS: set[str] = {".hwp", ".pdf", ".txt", ".md"}


def extract_text(path: Path) -> str:
    """
    파일 확장자에 따라 적절한 추출 함수를 호출하고 텍스트를 반환한다.
    지원하지 않는 형식은 ValueError를 발생시킨다.
    """
    ext = path.suffix.lower()
    if ext == ".hwp":
        return _extract_hwp(path)
    if ext == ".pdf":
        return _extract_pdf(path)
    if ext in {".txt", ".md"}:
        return _extract_plain(path)
    raise ValueError(f"지원하지 않는 파일 형식: {ext}")


def process_files(file_paths: list[Path]) -> dict[Path, str]:
    """
    파일 목록을 순회하며 텍스트를 추출한다.
    반환값: {파일 경로: 추출된 텍스트}
    """
    results: dict[Path, str] = {}
    print("\n=== [2단계] OCR / 텍스트 추출 ===")

    for fp in file_paths:
        if not fp.is_file():
            continue
        if fp.suffix.lower() not in SUPPORTED_EXTENSIONS:
            print(f"  [skip] 지원 형식 아님: {fp.name}")
            continue
        try:
            text = extract_text(fp)
            results[fp] = text
            print(f"  [+] 추출 완료: {fp.name} ({len(text)} 자)")
        except NotImplementedError as exc:
            print(f"  [!] {exc}")
        except Exception as exc:  # noqa: BLE001
            print(f"  [!] 오류 ({fp.name}): {exc}")

    print(f"\n총 {len(results)}개 파일 텍스트 추출 완료.\n")
    return results
