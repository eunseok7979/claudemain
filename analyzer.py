"""
analyzer.py: 쟁점 추출 모듈 (3단계)

collector.py 가 정의한 카테고리 폴더명을 기준으로 파일을 분류한 뒤,
구조화된 프롬프트를 Claude API 에 전달하여 양측 주장의 쟁점을 추출한다.
"""

from __future__ import annotations

from pathlib import Path

from api_client import ClaudeClient

# ── 카테고리 매핑 ──────────────────────────────────────────
# collector.py 의 CollectItem.key 값과 반드시 일치해야 한다.

_CAT_REQUESTOR = "04_징계결의요구서"   # 징계요청자 자료
_CAT_RESPONDENT = "05_소명서"          # 징계당사자 자료
_CAT_MINUTES = "02_초심회의록"         # 초심 회의록
_CAT_SUPPLEMENT = {                    # 기타 참고 자료
    "01_초심결정문",
    "03_초심통지문",
    "06_기타참고자료",
}

# ── 프롬프트 ───────────────────────────────────────────────

_SYSTEM_PROMPT = """\
당신은 노동조합 징계위원회 사건을 분석하는 전문가입니다.
제출된 자료를 검토하여 사실관계가 불분명하거나 \
양측 주장이 상충하는 쟁점을 식별해야 합니다."""

_USER_PROMPT_TEMPLATE = """\
아래는 징계위원회에 제출된 자료입니다.

## 징계결의요구서 및 관련 자료
{requestor_text}

## 소명서 및 관련 자료
{respondent_text}

## 초심 회의록
{minutes_text}
{supplement_section}
위 자료를 검토하고 다음을 수행해주세요:

1. 징계요청자와 징계당사자의 주장이 서로 다른 부분을 사안별로 정리
2. 각 쟁점에 대해 사실관계 확인을 위해 추가로 조사해야 할 사항 제안
3. 추가 조사 시 누구에게 어떤 질문을 해야 하는지 구체적으로 제시

출력 형식:
### 쟁점 1: [쟁점 제목]
- 징계요청자 주장: ...
- 징계당사자 주장: ...
- 불명확한 사실관계: ...
- 추가 조사 필요 사항: ...
- 조사 대상 및 질문: ..."""

# 청크 분할 시 사용하는 프롬프트 (complete_chunked 에 전달)
_CHUNK_PROMPT_TEMPLATE = """\
아래는 징계위원회 자료의 일부입니다 ({chunk_index}/{total_chunks} 부분).
이 부분에서 징계요청자와 징계당사자 간의 주장이 상충하는 쟁점을 추출해주세요.

[자료 일부]
{chunk}

각 쟁점을 아래 형식으로 작성하세요:
### 쟁점: [제목]
- 징계요청자 주장: ...
- 징계당사자 주장: ...
- 불명확한 사실관계: ..."""

_MERGE_PROMPT_TEMPLATE = """\
아래는 동일한 징계위원회 자료를 여러 부분으로 나눠 분석한 결과입니다.
중복 쟁점을 하나로 통합하고 누락 없이 최종 쟁점 목록을 완성해주세요.

{partial_results}

최종 출력 형식:
### 쟁점 1: [쟁점 제목]
- 징계요청자 주장: ...
- 징계당사자 주장: ...
- 불명확한 사실관계: ...
- 추가 조사 필요 사항: ...
- 조사 대상 및 질문: ..."""


# ── 내부 헬퍼 ──────────────────────────────────────────────

def _category_of(path: Path) -> str:
    """파일 경로에서 collector.py 가 정의한 카테고리 폴더명을 추출한다.

    예) cases/2024-001/04_징계결의요구서/doc.pdf → '04_징계결의요구서'

    경로 상에 카테고리 폴더가 없으면 '기타'를 반환한다.
    """
    all_keys = {_CAT_REQUESTOR, _CAT_RESPONDENT, _CAT_MINUTES} | _CAT_SUPPLEMENT
    for part in reversed(path.parts):
        if part in all_keys:
            return part
    return "기타"


def _join_texts(file_texts: list[tuple[Path, str]]) -> str:
    """파일별 텍스트를 하나의 문자열로 합친다. 목록이 비어 있으면 '없음' 반환."""
    if not file_texts:
        return "(제출된 자료 없음)"
    parts = [f"#### {fp.name}\n{text.strip()}" for fp, text in file_texts]
    return "\n\n".join(parts)


def _categorize(
    texts: dict[Path, str],
) -> dict[str, list[tuple[Path, str]]]:
    """texts 맵을 카테고리별로 분류하여 반환한다."""
    cats: dict[str, list[tuple[Path, str]]] = {
        _CAT_REQUESTOR: [],
        _CAT_RESPONDENT: [],
        _CAT_MINUTES: [],
        "supplement": [],
    }
    for fp, text in texts.items():
        cat = _category_of(fp)
        if cat in (_CAT_REQUESTOR, _CAT_RESPONDENT, _CAT_MINUTES):
            cats[cat].append((fp, text))
        else:
            cats["supplement"].append((fp, text))
    return cats


def _build_prompt(cats: dict[str, list[tuple[Path, str]]]) -> str:
    """카테고리별 텍스트를 구조화된 사용자 프롬프트로 조립한다."""
    supplement_items = cats.get("supplement", [])
    if supplement_items:
        sup_text = _join_texts(supplement_items)
        supplement_section = f"\n## 참고 자료\n{sup_text}\n"
    else:
        supplement_section = ""

    return _USER_PROMPT_TEMPLATE.format(
        requestor_text=_join_texts(cats[_CAT_REQUESTOR]),
        respondent_text=_join_texts(cats[_CAT_RESPONDENT]),
        minutes_text=_join_texts(cats[_CAT_MINUTES]),
        supplement_section=supplement_section,
    )


# ── 공개 인터페이스 ────────────────────────────────────────

def extract_issues(texts: dict[Path, str], client: ClaudeClient | None = None) -> str:
    """텍스트 맵을 카테고리별로 분류하여 Claude API 로 쟁점을 추출한다.

    Parameters
    ----------
    texts:
        {파일 경로: 텍스트} – ocr_processor.process_files() 의 반환값.
    client:
        ClaudeClient 인스턴스. None 이면 내부에서 생성한다.

    Returns
    -------
    str
        Claude 가 반환한 쟁점 분석 결과 텍스트.
    """
    print("\n=== [3단계] 쟁점 추출 ===")

    if not texts:
        print("  [!] 분석할 텍스트가 없습니다.")
        return ""

    if client is None:
        client = ClaudeClient()

    cats = _categorize(texts)
    print(
        f"  분류 결과 | 징계결의요구서 {len(cats[_CAT_REQUESTOR])}건 | "
        f"소명서 {len(cats[_CAT_RESPONDENT])}건 | "
        f"초심회의록 {len(cats[_CAT_MINUTES])}건 | "
        f"참고자료 {len(cats['supplement'])}건"
    )

    prompt = _build_prompt(cats)
    print("  Claude API 호출 중...")

    # 프롬프트가 청크 한계 이하면 단일 호출, 초과하면 청크 분할 처리
    if len(prompt) <= 150_000:
        result = client.complete(prompt, system=_SYSTEM_PROMPT)
    else:
        # 전체 원문을 이어붙여 청크 분할 분석
        all_text = "\n\n".join(texts.values())
        result = client.complete_chunked(
            text=all_text,
            chunk_prompt_template=_CHUNK_PROMPT_TEMPLATE,
            merge_prompt_template=_MERGE_PROMPT_TEMPLATE,
            system=_SYSTEM_PROMPT,
        )

    client.print_usage_summary()
    print("  [+] 쟁점 추출 완료.\n")
    return result


def save_issues(issues: str, output_path: Path) -> None:
    """추출된 쟁점 텍스트를 파일로 저장한다."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(issues, encoding="utf-8")
    print(f"  [+] 쟁점 저장: {output_path}")
