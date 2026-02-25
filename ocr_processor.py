"""
ocr_processor.py: HWP/PDF → 텍스트 전산화 모듈 (2단계)

지원 형식:
  - .hwp  : pyhwp 라이브러리 (hwp5txt CLI + 삽입 이미지 OCR)
  - .pdf  : pdfplumber (텍스트 레이어) + pytesseract (스캔 페이지 OCR)
  - .txt / .md : 직접 읽기

출력:
  - {파일명}_text.txt      : 추출된 전체 텍스트
  - {파일명}_pages/        : 페이지별 PNG 이미지 (PDF 한정)

의존 패키지:
  pip install pdfplumber pdf2image pytesseract opencv-python-headless pillow pyhwp
  apt-get install tesseract-ocr tesseract-ocr-kor poppler-utils
"""

from __future__ import annotations

import io
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from PIL import Image

# ── 상수 ──────────────────────────────────────────────────

TESSERACT_LANG = "kor+eng"
TESSERACT_CONFIG = "--oem 1 --psm 3"
SUPPORTED_EXTENSIONS: set[str] = {".hwp", ".pdf", ".txt", ".md"}

# 페이지당 추출 텍스트가 이 값(자) 미만이면 스캔 문서로 판단 → OCR 적용
_SCAN_THRESHOLD = 100

_HWP_FORMAT_MSG = (
    "\n한글(HWP) 파일을 읽을 수 없습니다.\n"
    "한글 프로그램에서 [파일] → [다른 이름으로 저장] 후\n"
    "PDF 또는 TXT 형식으로 저장하여 다시 시도해 주세요."
)


# ── 이미지 전처리 ──────────────────────────────────────────

def _deskew(gray: np.ndarray) -> np.ndarray:
    """어두운 픽셀(텍스트)의 분포로 기울기 각도를 추정하고 보정한다.

    cv2.minAreaRect 는 [-90, 0) 범위의 각도를 반환한다.
    - angle < -45 : 세로로 긴 영역 → 실제 기울기 = angle + 90
    - 그 외        : 실제 기울기 = angle (음수이면 시계 반대 방향 기울기)
    """
    inverted = cv2.bitwise_not(gray)
    coords = np.column_stack(np.where(inverted > 128))
    if len(coords) < 200:
        return gray

    angle = cv2.minAreaRect(coords.astype(np.float32))[-1]
    if angle < -45:
        angle = 90 + angle

    if abs(angle) < 0.5:  # 보정 불필요
        return gray

    h, w = gray.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(
        gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def _preprocess_for_ocr(pil_img: Image.Image) -> Image.Image:
    """OCR 정확도 향상을 위한 전처리: 기울기 보정 → Otsu 이진화 → 잡음 제거."""
    img_np = np.array(pil_img.convert("RGB"))
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)

    gray = _deskew(gray)

    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 3×3 중앙값 필터로 점 잡음 제거
    denoised = cv2.medianBlur(binary, 3)

    return Image.fromarray(denoised)


def _ocr_image(pil_img: Image.Image) -> str:
    """단일 이미지에 한국어 Tesseract OCR 을 적용하여 텍스트를 반환한다."""
    processed = _preprocess_for_ocr(pil_img)
    return pytesseract.image_to_string(
        processed, lang=TESSERACT_LANG, config=TESSERACT_CONFIG
    )


# ── PDF 처리 ───────────────────────────────────────────────

def _extract_pdf(path: Path) -> tuple[str, list[Image.Image]]:
    """PDF 에서 텍스트와 페이지 이미지를 추출한다.

    처리 순서:
    1. pdf2image 로 전체 페이지를 300 dpi PNG 로 변환 (원본 보존용).
    2. pdfplumber 로 텍스트 레이어 추출.
    3. 페이지당 텍스트가 _SCAN_THRESHOLD 자 미만이면 Tesseract OCR 로 대체.
    """
    page_images: list[Image.Image] = convert_from_path(str(path), dpi=300)

    texts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for idx, page in enumerate(pdf.pages):
            layer_text = page.extract_text() or ""
            if len(layer_text.strip()) < _SCAN_THRESHOLD:
                ocr_text = _ocr_image(page_images[idx])
                texts.append(ocr_text)
            else:
                texts.append(layer_text)

    return "\n\n".join(texts), page_images


# ── HWP 처리 ──────────────────────────────────────────────

def _hwp_text_via_cli(path: Path) -> str | None:
    """hwp5txt CLI 를 사용하여 HWP 텍스트를 추출한다. 실패 시 None 반환."""
    try:
        result = subprocess.run(
            ["hwp5txt", str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _hwp_text_via_api(path: Path) -> str | None:
    """pyhwp Python API 를 사용하여 HWP 텍스트를 추출한다. 실패 시 None 반환."""
    try:
        from hwp5.xmlmodel import Hwp5File  # type: ignore[import]

        hwp = Hwp5File(str(path))
        parts: list[str] = []
        for section in hwp.bodytext.sections:
            for para in section.paragraphs:
                try:
                    parts.append(para.text)
                except Exception:  # noqa: BLE001
                    pass
        text = "\n".join(parts).strip()
        return text if text else None
    except Exception:  # noqa: BLE001
        return None


def _hwp_embedded_image_texts(path: Path) -> list[str]:
    """HWP 파일 내 삽입 이미지를 꺼내 OCR 로 텍스트를 추출한다.

    pyhwp 의 OLE 스토리지 API 로 BinData 섹션에 접근하여
    BMP / PNG / JPEG 매직 바이트를 가진 스트림을 이미지로 열어 OCR 처리한다.
    """
    ocr_texts: list[str] = []
    try:
        from hwp5.storage import open_storage  # type: ignore[import]

        with open_storage(str(path)) as storage:
            if "BinData" not in storage:
                return []
            bin_storage = storage["BinData"]
            for name in bin_storage:
                try:
                    data = bin_storage[name].read()
                    is_bmp = data[:2] == b"BM"
                    is_png = data[:4] == b"\x89PNG"
                    is_jpeg = data[:3] == b"\xff\xd8\xff"
                    if is_bmp or is_png or is_jpeg:
                        img = Image.open(io.BytesIO(data))
                        text = _ocr_image(img)
                        if text.strip():
                            ocr_texts.append(text)
                except Exception:  # noqa: BLE001
                    continue
    except Exception:  # noqa: BLE001
        pass
    return ocr_texts


def _extract_hwp(path: Path) -> tuple[str, list[Image.Image]]:
    """HWP 파일에서 텍스트를 추출한다.

    처리 순서:
    1. hwp5txt CLI 로 텍스트 추출 시도.
    2. 실패 시 pyhwp Python API 로 재시도.
    3. 모두 실패 시 사용자에게 포맷 변환을 안내하는 ValueError 발생.
    4. 성공 후 삽입 이미지가 있으면 OCR 로 추가 텍스트를 추출하여 덧붙임.

    HWP 는 페이지 이미지 생성이 불가하므로 이미지 목록은 빈 리스트를 반환한다.
    """
    body_text = _hwp_text_via_cli(path) or _hwp_text_via_api(path)
    if body_text is None:
        raise ValueError(f"{path.name}{_HWP_FORMAT_MSG}")

    image_texts = _hwp_embedded_image_texts(path)
    if image_texts:
        body_text += "\n\n[삽입 이미지 추출 텍스트]\n" + "\n\n---\n\n".join(image_texts)

    return body_text, []


# ── 일반 텍스트 처리 ────────────────────────────────────────

def _extract_plain(path: Path) -> tuple[str, list[Image.Image]]:
    """일반 텍스트 파일을 그대로 읽는다."""
    return path.read_text(encoding="utf-8", errors="replace"), []


# ── 결과 저장 ──────────────────────────────────────────────

def _save_results(path: Path, text: str, images: list[Image.Image]) -> None:
    """추출된 텍스트와 페이지 이미지를 파일로 저장한다.

    - {파일 위치}/{파일명}_text.txt
    - {파일 위치}/{파일명}_pages/page_001.png ...
    """
    out_dir = path.parent
    stem = path.stem

    text_path = out_dir / f"{stem}_text.txt"
    text_path.write_text(text, encoding="utf-8")

    if images:
        pages_dir = out_dir / f"{stem}_pages"
        pages_dir.mkdir(exist_ok=True)
        for i, img in enumerate(images, start=1):
            img.save(pages_dir / f"page_{i:03d}.png", "PNG")


# ── 공개 인터페이스 ────────────────────────────────────────

def extract_text(path: Path) -> tuple[str, list[Image.Image]]:
    """파일을 읽어 (텍스트, 페이지 이미지 목록) 튜플을 반환한다.

    결과는 {파일명}_text.txt 와 {파일명}_pages/ 에도 동시에 저장된다.
    지원 형식: .hwp, .pdf, .txt, .md
    """
    ext = path.suffix.lower()
    if ext == ".hwp":
        result = _extract_hwp(path)
    elif ext == ".pdf":
        result = _extract_pdf(path)
    elif ext in {".txt", ".md"}:
        result = _extract_plain(path)
    else:
        raise ValueError(f"지원하지 않는 파일 형식: {ext}")

    text, images = result
    _save_results(path, text, images)
    return result


def process_files(file_paths: list[Path]) -> dict[Path, str]:
    """파일 목록에서 텍스트를 일괄 추출한다.

    반환값: {파일 경로: 추출된 텍스트}
    (analyzer 등 하위 단계와의 인터페이스를 유지하기 위해 str 만 반환)
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
            text, images = extract_text(fp)
            results[fp] = text
            img_note = f", {len(images)}페이지 이미지 저장" if images else ""
            print(f"  [+] 추출 완료: {fp.name} ({len(text):,} 자{img_note})")
        except ValueError as exc:
            print(f"  [!] {exc}")
        except Exception as exc:  # noqa: BLE001
            print(f"  [!] 오류 ({fp.name}): {exc}")

    print(f"\n총 {len(results)}개 파일 텍스트 추출 완료.\n")
    return results
