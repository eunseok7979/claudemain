"""
collector.py: 자료 수집 모듈 (1단계)

징계위원회 차수별 폴더를 생성하고 자료 종류별로 파일을 순서대로 수집한다.
저장 위치: ./cases/{징계위차수}/{자료종류}/
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import config

CASES_DIR = Path(config.CASES_DIR)


# ── 수집 항목 정의 ────────────────────────────────────────

@dataclass(frozen=True)
class CollectItem:
    key: str       # 하위 폴더명
    label: str     # 사용자 안내 레이블
    required: bool # 필수 여부
    multi: bool    # 복수 파일 허용 여부


COLLECT_ITEMS: list[CollectItem] = [
    CollectItem("01_초심결정문",    "초심 결정문",               required=True,  multi=False),
    CollectItem("02_초심회의록",    "초심 회의록",               required=True,  multi=False),
    CollectItem("03_초심통지문",    "초심 통지문",               required=True,  multi=False),
    CollectItem("04_징계결의요구서", "징계결의요구서 및 첨부자료", required=True,  multi=True),
    CollectItem("05_소명서",       "소명서 및 첨부자료",         required=False, multi=True),
    CollectItem("06_기타참고자료",  "기타 참고자료",             required=False, multi=True),
]


# ── 내부 헬퍼 ─────────────────────────────────────────────

def _setup_case_dir(case_id: str) -> Path:
    """차수별 폴더와 항목별 하위 폴더를 모두 생성하고 경로를 반환한다."""
    case_dir = CASES_DIR / case_id
    for item in COLLECT_ITEMS:
        (case_dir / item.key).mkdir(parents=True, exist_ok=True)
    return case_dir


def _parse_paths(raw: str) -> list[Path]:
    """쉼표로 구분된 입력 문자열을 Path 목록으로 변환한다."""
    return [Path(p.strip()) for p in raw.split(",") if p.strip()]


def _validate_paths(paths: list[Path]) -> tuple[list[Path], list[Path]]:
    """(존재하는 파일 목록, 존재하지 않는 파일 목록)으로 분리한다."""
    valid, missing = [], []
    for p in paths:
        (valid if p.is_file() else missing).append(p)
    return valid, missing


def _copy_files(src_paths: list[Path], dest_dir: Path) -> list[Path]:
    """파일들을 dest_dir에 복사한다. 이름 충돌 시 _1, _2 ... 접미사를 붙인다."""
    copied: list[Path] = []
    for src in src_paths:
        dest = dest_dir / src.name
        stem, suffix = src.stem, src.suffix
        counter = 1
        while dest.exists():
            dest = dest_dir / f"{stem}_{counter}{suffix}"
            counter += 1
        shutil.copy2(src, dest)
        copied.append(dest)
    return copied


def _prompt_item(item: CollectItem, case_dir: Path) -> list[Path]:
    """
    항목 하나에 대해 파일 경로를 입력받아 복사하고 결과 목록을 반환한다.

    - 필수 항목: 유효 파일이 1개 이상 입력될 때까지 재입력 요청
    - 선택 항목: 빈 입력이면 건너뜀
    - 단일 항목: 경로가 2개 이상이면 재입력 요청
    """
    dest_dir = case_dir / item.key
    tag = "[필수]" if item.required else "[선택]"
    hint = "여러 파일은 쉼표로 구분" if item.multi else "파일 1개"

    while True:
        print(f"\n  {tag} {item.label}  ({hint})")
        if not item.required:
            print("        빈 줄 입력 시 건너뜁니다.")

        raw = input("  경로 입력: ").strip()

        # ── 빈 입력 ──────────────────────────────────────
        if not raw:
            if item.required:
                print("  [!] 필수 항목입니다. 파일 경로를 입력해주세요.")
                continue
            print("  [-] 건너뜁니다.")
            return []

        # ── 경로 파싱 ─────────────────────────────────────
        paths = _parse_paths(raw)

        if not item.multi and len(paths) > 1:
            print("  [!] 이 항목은 파일을 1개만 입력할 수 있습니다. 다시 입력해주세요.")
            continue

        # ── 존재 여부 검증 ────────────────────────────────
        valid, missing = _validate_paths(paths)
        for m in missing:
            print(f"  [!] 파일을 찾을 수 없습니다: {m}")

        if not valid:
            if item.required:
                print("  [!] 유효한 파일이 없습니다. 다시 입력해주세요.")
                continue
            print("  [-] 유효한 파일이 없어 건너뜁니다.")
            return []

        # ── 복사 ─────────────────────────────────────────
        copied = _copy_files(valid, dest_dir)
        for cp in copied:
            print(f"  [+] 저장: {cp.relative_to(CASES_DIR)}")
        return copied


# ── 공개 인터페이스 ───────────────────────────────────────

def collect_files(case_id: str) -> dict[str, list[Path]]:
    """
    사건 ID(징계위 차수)를 받아 6종 자료를 순서대로 수집한다.

    반환값: {항목 key: [복사된 파일 경로, ...]}
    """
    case_dir = _setup_case_dir(case_id)

    print(f"\n{'='*54}")
    print(f"  [1단계] 자료 수집  ·  징계위 차수: {case_id}")
    print(f"  저장 위치: {case_dir}")
    print(f"{'='*54}")
    print("  항목별로 파일 경로를 입력하세요.\n")

    results: dict[str, list[Path]] = {}
    total = 0

    for item in COLLECT_ITEMS:
        copied = _prompt_item(item, case_dir)
        results[item.key] = copied
        total += len(copied)

    # ── 수집 결과 요약 ────────────────────────────────────
    print(f"\n{'─'*54}")
    print(f"  수집 완료 – 총 {total}개 파일")
    for item in COLLECT_ITEMS:
        files = results.get(item.key, [])
        status = f"{len(files)}개 수집" if files else "건너뜀"
        print(f"    · {item.label}: {status}")
    print(f"{'─'*54}\n")

    return results


def list_collected_files(case_id: str) -> list[Path]:
    """해당 사건 ID 폴더의 모든 파일을 재귀적으로 열거한다."""
    case_dir = CASES_DIR / case_id
    if not case_dir.exists():
        return []
    return sorted(p for p in case_dir.rglob("*") if p.is_file())
