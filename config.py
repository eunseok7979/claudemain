"""
config.py: API 키, 모델 설정, 프롬프트 템플릿 관리
"""

import os

# ── API 설정 ──────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL_ID: str = "claude-opus-4-6"
MAX_TOKENS: int = 8192

# ── 파일 경로 설정 ─────────────────────────────────────────
BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
WORK_DIR: str = os.path.join(BASE_DIR, "workspace")  # 작업 파일 저장 루트

# ── 프롬프트 템플릿 ────────────────────────────────────────
PROMPTS: dict = {
    # 3단계: 쟁점 추출
    "extract_issues": """\
당신은 노동조합 징계위원회 전문 법무 보조입니다.
아래 자료를 읽고 핵심 쟁점을 구조화하여 추출하세요.

[자료]
{text}

출력 형식:
1. 사건 개요 (당사자, 일시, 경위)
2. 징계 사유 목록 (번호 매김)
3. 당사자 주요 주장
4. 법적·규약적 쟁점
5. 추가 확인 필요 사항
""",

    # 4단계: 통합 문서 생성
    "integrate_document": """\
당신은 노동조합 징계위원회 간사입니다.
아래 쟁점 분석 결과를 바탕으로 공식 심의 자료를 작성하세요.

[쟁점 분석]
{issues}

출력 형식: 징계위원회 심의 자료 (표준 양식)
""",

    # 5단계: 요약문 작성
    "summarize": """\
당신은 노동조합 징계위원회 간사입니다.
아래 심의 자료를 위원들이 이해하기 쉽도록 간결하게 요약하세요.

[심의 자료]
{document}

요약 분량: A4 1장 이내
""",
}
