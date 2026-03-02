"""
main.py: 노동조합 징계위원회 간사 업무 자동화 CLI
=========================================================
단계별 흐름:
  1단계 – 자료 수집       (collector)
  2단계 – OCR / 텍스트 추출  (ocr_processor)
  3단계 – 쟁점 추출        (analyzer)
  4단계 – 통합 문서 생성    (integrator)
  5단계 – 요약문 작성       (summarizer)
"""

from __future__ import annotations

import sys
from pathlib import Path

import config
import collector
import ocr_processor
import analyzer
import integrator
import summarizer
from api_client import ClaudeClient


# ── 유틸리티 ──────────────────────────────────────────────

def _print_banner() -> None:
    print("=" * 55)
    print("  노동조합 징계위원회 간사 업무 자동화 시스템")
    print("=" * 55)


def _prompt_case_id() -> str:
    """사건 ID(폴더명)를 입력받는다."""
    while True:
        case_id = input("\n사건 ID를 입력하세요 (예: 2024-001): ").strip()
        if case_id:
            return case_id
        print("  [!] 사건 ID를 입력해야 합니다.")


def _print_menu() -> None:
    print("\n──────────────────────────────────────────────────")
    print("  메뉴")
    print("  1. 전체 단계 자동 실행 (1→5)")
    print("  2. 1단계: 자료 수집")
    print("  3. 2단계: OCR / 텍스트 추출")
    print("  4. 3단계: 쟁점 추출")
    print("  5. 4단계: 통합 문서 생성")
    print("  6. 5단계: 요약문 작성")
    print("  0. 종료")
    print("──────────────────────────────────────────────────")


# ── 단계별 실행 함수 ──────────────────────────────────────

def run_step1(case_id: str) -> list[Path]:
    """1단계: 자료 수집."""
    return collector.collect_files(case_id)


def run_step2(case_id: str) -> dict[Path, str]:
    """2단계: OCR / 텍스트 추출."""
    files = collector.list_collected_files(case_id)
    file_list = [f for f in files if f.is_file()]
    return ocr_processor.process_files(file_list)


def run_step3(case_id: str, client: ClaudeClient) -> str:
    """3단계: 쟁점 추출."""
    texts = run_step2(case_id)
    issues = analyzer.extract_issues(texts, client)
    out = Path(config.WORK_DIR) / case_id / "output" / "issues.txt"
    if issues:
        analyzer.save_issues(issues, out)
    return issues


def run_step4(case_id: str, client: ClaudeClient, issues: str = "") -> str:
    """4단계: 통합 문서 생성."""
    if not issues:
        issues_path = Path(config.WORK_DIR) / case_id / "output" / "issues.txt"
        if issues_path.exists():
            issues = issues_path.read_text(encoding="utf-8")
        else:
            print("  [!] 쟁점 파일이 없습니다. 3단계를 먼저 실행하세요.")
            return ""

    document = integrator.generate_document(issues, client)
    out = Path(config.WORK_DIR) / case_id / "output" / "document"
    if document:
        integrator.save_document(document, out)
    return document


def run_step5(case_id: str, client: ClaudeClient) -> str:
    """5단계: 요약문 작성."""
    texts = run_step2(case_id)
    summary = summarizer.summarize(texts, client=client)
    out = Path(config.WORK_DIR) / case_id / "output" / "summary.txt"
    if summary:
        summarizer.save_summary(summary, out)
    return summary


def run_all(case_id: str) -> None:
    """전체 단계를 순서대로 실행한다."""
    client = ClaudeClient()

    run_step1(case_id)
    texts = run_step2(case_id)

    issues = analyzer.extract_issues(texts, client)
    out_issues = Path(config.WORK_DIR) / case_id / "output" / "issues.txt"
    if issues:
        analyzer.save_issues(issues, out_issues)

    document = integrator.generate_document(issues, client)
    out_doc = Path(config.WORK_DIR) / case_id / "output" / "document"
    if document:
        integrator.save_document(document, out_doc)

    summary = summarizer.summarize(texts, client=client)
    out_summary = Path(config.WORK_DIR) / case_id / "output" / "summary.txt"
    if summary:
        summarizer.save_summary(summary, out_summary)

    print("\n모든 단계가 완료되었습니다.")
    print(f"결과물 위치: {Path(config.WORK_DIR) / case_id / 'output'}")


# ── 메인 루프 ─────────────────────────────────────────────

def main() -> None:
    _print_banner()

    if not config.ANTHROPIC_API_KEY:
        print("[경고] ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")
        print("       API 호출 단계에서 오류가 발생합니다.\n")

    case_id = _prompt_case_id()
    client = ClaudeClient()

    while True:
        _print_menu()
        choice = input("선택: ").strip()

        if choice == "0":
            print("\n프로그램을 종료합니다.")
            sys.exit(0)
        elif choice == "1":
            run_all(case_id)
        elif choice == "2":
            run_step1(case_id)
        elif choice == "3":
            run_step2(case_id)
        elif choice == "4":
            run_step3(case_id, client)
        elif choice == "5":
            run_step4(case_id, client)
        elif choice == "6":
            run_step5(case_id, client)
        else:
            print("  [!] 올바른 번호를 입력하세요.")


if __name__ == "__main__":
    main()
