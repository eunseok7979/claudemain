"""
summarizer.py: 요약문 작성 모듈 (5단계)

전산화된 모든 자료와 추가조사 녹취록을 종합하여
징계위원회 위원들이 심의에 사용할 사건 요약문 초안을 생성한다.
"""

from __future__ import annotations

from pathlib import Path

from api_client import ClaudeClient

# ── 카테고리 레이블 ────────────────────────────────────────
# collector.py 의 CollectItem.key → 사람이 읽을 수 있는 문서명
# 프롬프트 내 출처 표기에 사용된다.

_CAT_LABELS: dict[str, str] = {
    "01_초심결정문":   "초심 결정문",
    "02_초심회의록":   "초심 회의록",
    "03_초심통지문":   "초심 통지문",
    "04_징계결의요구서": "징계결의요구서",
    "05_소명서":       "소명서",
    "06_기타참고자료":  "기타 참고자료",
}

# ── 프롬프트 ───────────────────────────────────────────────

_SYSTEM_PROMPT = """\
당신은 노동조합 징계위원회 간사입니다.
징계위원회 위원들이 사건을 심의할 수 있도록 객관적이고 균형잡힌 요약문을 작성해야 합니다.
문체는 공문서체로, 사실에 기반하여 서술하세요."""

_USER_PROMPT_TEMPLATE = """\
아래 자료를 바탕으로 징계위원회 요약문을 작성해주세요.

{full_text}

요약문 구성:

1. 당사자 및 관계자
   - 제출 문서에 언급된 인물들의 성명, 노조 가입 이력, 직위 등을 정리

2. 배경 및 경과
   - 관련 직종/지역의 관행이나 특성 등 배경지식 서술
   - 징계 사건 관련 경과를 날짜순으로 서술

3. 징계요청자의 주장
   - 징계결의요구서의 사안별로 요청자의 주장을 정리

4. 징계당사자의 소명
   - 사안별로 당사자의 입장을 정리

5. 쟁점 정리
   - 양측이 사실관계를 다르게 주장하는 부분
   - 노동조합 상벌규정에 비추어 징계 가능 여부
   - 양정상 고려사항 (정상참작 요소, 가중 요소 등)

각 섹션은 출처(어떤 문서의 내용인지)를 괄호 안에 명시해주세요.
예: (징계결의요구서 p.3)"""

# 청크 분할 시 각 청크 분석용
_CHUNK_PROMPT_TEMPLATE = """\
아래는 징계위원회 자료의 일부입니다 ({chunk_index}/{total_chunks} 부분).
이 부분에서 중요한 사실관계, 날짜, 인물, 주장을 빠짐없이 추출하고
출처 문서명을 함께 기록해주세요.

[자료 일부]
{chunk}"""

# 청크별 결과 통합용
_MERGE_PROMPT_TEMPLATE = """\
아래는 동일한 징계위원회 자료를 여러 부분으로 나눠 추출한 내용입니다.
이를 종합하여 아래 형식의 완성된 요약문을 작성해주세요.

{partial_results}

요약문 구성:

1. 당사자 및 관계자
   - 제출 문서에 언급된 인물들의 성명, 노조 가입 이력, 직위 등을 정리

2. 배경 및 경과
   - 관련 직종/지역의 관행이나 특성 등 배경지식 서술
   - 징계 사건 관련 경과를 날짜순으로 서술

3. 징계요청자의 주장
   - 징계결의요구서의 사안별로 요청자의 주장을 정리

4. 징계당사자의 소명
   - 사안별로 당사자의 입장을 정리

5. 쟁점 정리
   - 양측이 사실관계를 다르게 주장하는 부분
   - 노동조합 상벌규정에 비추어 징계 가능 여부
   - 양정상 고려사항 (정상참작 요소, 가중 요소 등)

각 섹션은 출처를 괄호 안에 명시해주세요. 예: (징계결의요구서 p.3)"""


# ── 내부 헬퍼 ──────────────────────────────────────────────

def _label_of(path: Path) -> str:
    """파일 경로에서 사람이 읽을 수 있는 문서 레이블을 반환한다.

    예) cases/2024-001/04_징계결의요구서/doc.pdf → '징계결의요구서'
    """
    for part in reversed(path.parts):
        if part in _CAT_LABELS:
            return _CAT_LABELS[part]
    return "참고자료"


def _build_full_text(texts: dict[Path, str], transcripts: list[str]) -> str:
    """모든 자료를 카테고리 순서와 문서명 헤더를 붙여 하나의 텍스트로 조립한다.

    모델이 출처를 정확히 참조할 수 있도록
    각 문서 앞에 '## [카테고리명] 파일명' 형식의 헤더를 붙인다.
    """
    # _CAT_LABELS 정의 순서대로 카테고리 버킷을 만든다
    ordered: dict[str, list[tuple[Path, str]]] = {k: [] for k in _CAT_LABELS}
    others: list[tuple[Path, str]] = []

    for fp, text in texts.items():
        placed = False
        for part in reversed(fp.parts):
            if part in _CAT_LABELS:
                ordered[part].append((fp, text))
                placed = True
                break
        if not placed:
            others.append((fp, text))

    sections: list[str] = []

    for cat_key, label in _CAT_LABELS.items():
        for fp, text in ordered[cat_key]:
            sections.append(f"## [{label}] {fp.name}\n\n{text.strip()}")

    for fp, text in others:
        sections.append(f"## [기타] {fp.name}\n\n{text.strip()}")

    for i, transcript in enumerate(transcripts, start=1):
        sections.append(f"## [추가조사 녹취록 {i}]\n\n{transcript.strip()}")

    return "\n\n---\n\n".join(sections)


# ── 공개 인터페이스 ────────────────────────────────────────

def summarize(
    texts: dict[Path, str],
    transcripts: list[str] | None = None,
    client: ClaudeClient | None = None,
) -> str:
    """전산화된 자료와 추가조사 녹취록을 종합하여 요약문 초안을 생성한다.

    Parameters
    ----------
    texts:
        {파일 경로: 텍스트} – ocr_processor.process_files() 의 반환값.
    transcripts:
        추가조사 녹취록 텍스트 목록. None 이면 빈 리스트로 처리한다.
    client:
        ClaudeClient 인스턴스. None 이면 내부에서 생성한다.
    """
    print("\n=== [5단계] 요약문 작성 ===")

    if not texts and not transcripts:
        print("  [!] 작성할 자료가 없습니다.")
        return ""

    if client is None:
        client = ClaudeClient()

    transcripts = transcripts or []
    full_text = _build_full_text(texts, transcripts)

    transcript_note = f", 녹취록 {len(transcripts)}건" if transcripts else ""
    print(f"  투입 자료: {len(texts)}개 파일{transcript_note}")

    prompt = _USER_PROMPT_TEMPLATE.format(full_text=full_text)
    print("  Claude API 호출 중...")

    if len(prompt) <= 150_000:
        summary = client.complete(prompt, system=_SYSTEM_PROMPT)
    else:
        summary = client.complete_chunked(
            text=full_text,
            chunk_prompt_template=_CHUNK_PROMPT_TEMPLATE,
            merge_prompt_template=_MERGE_PROMPT_TEMPLATE,
            system=_SYSTEM_PROMPT,
        )

    client.print_usage_summary()
    print("  [+] 요약문 작성 완료.\n")
    return summary


def save_summary(summary: str, output_path: Path) -> None:
    """요약문을 텍스트 파일로 저장한다."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(summary, encoding="utf-8")
    print(f"  [+] 요약문 저장: {output_path}")
