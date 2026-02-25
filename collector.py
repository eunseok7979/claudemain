"""
collector.py: 자료 수집 모듈 (1단계)

사용자에게 파일 경로를 입력받아 workspace/ 하위 폴더에 복사·정리한다.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import config


# 수집 대상 파일 카테고리 (필요에 따라 확장)
CATEGORIES: list[str] = [
    "징계_통지서",
    "소명서",
    "증거자료",
    "회의록",
    "기타",
]


def setup_workspace(case_id: str) -> Path:
    """사건 ID별 작업 폴더를 생성하고 경로를 반환한다."""
    case_dir = Path(config.WORK_DIR) / case_id
    for cat in CATEGORIES:
        (case_dir / cat).mkdir(parents=True, exist_ok=True)
    print(f"[+] 작업 폴더 생성: {case_dir}")
    return case_dir


def collect_files(case_id: str) -> list[Path]:
    """
    사용자에게 파일 경로를 반복 입력받아 카테고리별 폴더에 복사한다.
    빈 입력 시 종료한다.
    반환값: 복사된 파일 경로 목록
    """
    case_dir = setup_workspace(case_id)
    collected: list[Path] = []

    print("\n=== [1단계] 자료 수집 ===")
    print("파일 경로를 입력하세요. 완료하려면 빈 줄을 입력하세요.\n")

    while True:
        file_path_str = input("파일 경로: ").strip()
        if not file_path_str:
            break

        src = Path(file_path_str)
        if not src.exists():
            print(f"  [!] 파일을 찾을 수 없습니다: {src}")
            continue

        # 카테고리 선택
        print("  카테고리를 선택하세요:")
        for idx, cat in enumerate(CATEGORIES, 1):
            print(f"    {idx}. {cat}")
        cat_input = input("  번호 입력: ").strip()

        try:
            cat_idx = int(cat_input) - 1
            category = CATEGORIES[cat_idx]
        except (ValueError, IndexError):
            print("  [!] 잘못된 번호입니다. '기타'로 분류합니다.")
            category = "기타"

        dest_dir = case_dir / category
        dest = dest_dir / src.name
        shutil.copy2(src, dest)
        collected.append(dest)
        print(f"  [+] 복사 완료: {dest}")

    print(f"\n총 {len(collected)}개 파일 수집 완료.\n")
    return collected


def list_collected_files(case_id: str) -> list[Path]:
    """workspace에서 해당 사건 ID의 모든 파일을 재귀적으로 열거한다."""
    case_dir = Path(config.WORK_DIR) / case_id
    if not case_dir.exists():
        return []
    return sorted(case_dir.rglob("*"))
