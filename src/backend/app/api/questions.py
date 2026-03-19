"""
Question Generation API Router

질문 생성 관련 API 엔드포인트
"""

from typing import Dict, List, Any, Optional, Tuple
import re
import uuid
import json
import time
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from sqlalchemy import text

from app.agents.question_generator import QuestionGenerator
from app.core.ai_service import AIProvider
from app.core.database import engine, SessionLocal

router = APIRouter()

QUESTION_GENERATION_EXPERIMENT_ID = "question_generation_v1"
LEGACY_GENERATOR_VARIANT = "generator_v1"
DEFAULT_GENERATOR_VARIANT = "generator_grounded_prod_v1"
BEST_CASE_GENERATOR_PROFILE = "best_case_generator_v1"
CANONICAL_SELECTOR_VARIANT = "selector_v2"
ANALYSIS_STATUS_FRESH_BEST_CASE = "fresh_best_case"
ANALYSIS_STATUS_LEGACY_UNVERIFIED = "legacy_unverified"

# 질문 캐시 (variant-aware cache key -> payload)
question_cache: Dict[str, "QuestionCacheData"] = {}
question_cache_active_keys: Dict[str, str] = {}


def extract_api_keys_from_headers(
    github_token: Optional[str] = Header(None, alias="x-github-token"),
    google_api_key: Optional[str] = Header(None, alias="x-google-api-key"),
    upstage_api_key: Optional[str] = Header(None, alias="x-upstage-api-key"),
) -> Dict[str, str]:
    """요청 헤더에서 API 키 추출"""
    api_keys = {}
    if github_token:
        api_keys["github_token"] = github_token
    if google_api_key:
        api_keys["google_api_key"] = google_api_key
    if upstage_api_key:
        api_keys["upstage_api_key"] = upstage_api_key
    return api_keys





class QuestionGenerationRequest(BaseModel):
    """질문 생성 요청"""
    repo_url: str
    analysis_result: Optional[Dict[str, Any]] = None
    question_type: str = "technical"
    difficulty: str = "medium"
    question_count: int = 9
    force_regenerate: bool = False  # 강제 재생성 옵션
    provider_id: Optional[str] = None


def resolve_provider_id(provider_id: Optional[str]) -> Optional[AIProvider]:
    if not provider_id:
        return None

    normalized = provider_id.strip().lower()

    if "upstage" in normalized or "solar" in normalized:
        return AIProvider.UPSTAGE_SOLAR

    if "gemini" in normalized or "google" in normalized:
        return AIProvider.GEMINI_FLASH

    raise HTTPException(status_code=400, detail=f"지원되지 않는 provider_id: {provider_id}")


class QuestionResponse(BaseModel):
    """질문 응답"""
    id: str
    type: str
    question: str
    difficulty: str
    context: Optional[str] = None
    time_estimate: Optional[str] = None
    code_snippet: Optional[Dict[str, Any]] = None
    expected_answer_points: Optional[List[str]] = None
    technology: Optional[str] = None
    pattern: Optional[str] = None
    # 서브 질문 관련 필드
    parent_question_id: Optional[str] = None
    sub_question_index: Optional[int] = None
    total_sub_questions: Optional[int] = None
    is_compound_question: bool = False


class QuestionCacheData(BaseModel):
    """질문 캐시 데이터 구조"""
    analysis_id: str
    cache_key: str
    experiment_id: str
    selector_variant: str
    generator_variant: str
    provider_id: Optional[str] = None
    applied_profile: Optional[str] = None
    analysis_profile_status: str = ANALYSIS_STATUS_LEGACY_UNVERIFIED
    best_case_guaranteed: bool = False
    original_questions: List[QuestionResponse]  # AI 원본 질문
    parsed_questions: List[QuestionResponse]   # 파싱된 개별 질문
    question_groups: Dict[str, List[str]]      # 그룹별 질문 관계 (parent_id -> [sub_question_ids])
    created_at: str


def _extract_selector_context(analysis_result: Optional[Dict[str, Any]]) -> Tuple[str, Optional[str]]:
    selector_experiment = (
        (analysis_result or {})
        .get("smart_file_analysis", {})
        .get("selector_experiment", {})
    )

    selector_variant = selector_experiment.get("display_variant") or "selector_v1"
    selector_experiment_id = selector_experiment.get("experiment_id")
    return selector_variant, selector_experiment_id


def _resolve_analysis_profile_context(analysis_result: Optional[Dict[str, Any]]) -> Tuple[str, bool]:
    selector_experiment = (
        (analysis_result or {})
        .get("smart_file_analysis", {})
        .get("selector_experiment", {})
    )
    selector_variant = selector_experiment.get("display_variant")
    best_case_guaranteed = bool(selector_experiment.get("best_case_guaranteed"))
    analysis_profile_status = selector_experiment.get("analysis_profile_status")

    if (
        selector_variant == CANONICAL_SELECTOR_VARIANT
        and best_case_guaranteed
        and analysis_profile_status == ANALYSIS_STATUS_FRESH_BEST_CASE
    ):
        return ANALYSIS_STATUS_FRESH_BEST_CASE, True

    return ANALYSIS_STATUS_LEGACY_UNVERIFIED, False


def build_question_cache_key(
    analysis_id: str,
    selector_variant: str,
    generator_variant: str = DEFAULT_GENERATOR_VARIANT,
) -> str:
    return f"{analysis_id}:{selector_variant}:{generator_variant}"


def get_question_cache_entry(
    analysis_id: str,
    *,
    selector_variant: Optional[str] = None,
    generator_variant: str = DEFAULT_GENERATOR_VARIANT,
) -> Optional[QuestionCacheData]:
    if selector_variant:
        return question_cache.get(
            build_question_cache_key(analysis_id, selector_variant, generator_variant)
        )

    active_key = question_cache_active_keys.get(analysis_id)
    if active_key:
        return question_cache.get(active_key)

    legacy_entry = question_cache.get(analysis_id)
    if legacy_entry:
        return legacy_entry
    return None


def _store_question_cache_entry(cache_data: QuestionCacheData, *, make_active: bool = True) -> None:
    question_cache[cache_data.cache_key] = cache_data
    if make_active:
        question_cache_active_keys[cache_data.analysis_id] = cache_data.cache_key


def _serialize_question(question: QuestionResponse) -> Dict[str, Any]:
    return question.model_dump()


def _serialize_question_list(questions: List[QuestionResponse]) -> List[Dict[str, Any]]:
    return [_serialize_question(question) for question in questions]


def _save_question_generation_run(
    *,
    analysis_id: str,
    experiment_id: str,
    selector_experiment_id: Optional[str],
    selector_variant: str,
    generator_variant: str,
    provider_id: Optional[str],
    applied_profile: Optional[str],
    analysis_profile_status: str,
    best_case_guaranteed: bool,
    original_questions: List[QuestionResponse],
    parsed_questions: List[QuestionResponse],
    question_groups: Dict[str, List[str]],
    latency_ms: int,
) -> Optional[str]:
    from app.models.repository import QuestionGenerationRun, RepositoryAnalysis

    db = SessionLocal()
    try:
        run = QuestionGenerationRun(
            analysis_id=uuid.UUID(analysis_id),
            experiment_id=experiment_id,
            selector_experiment_id=selector_experiment_id,
            selector_variant=selector_variant,
            generator_variant=generator_variant,
            provider=provider_id,
            generated_question_count=len(original_questions),
            parsed_question_count=len(parsed_questions),
            latency_ms=latency_ms,
            questions_payload={
                "original_questions": _serialize_question_list(original_questions),
                "parsed_questions": _serialize_question_list(parsed_questions),
                "question_groups": question_groups,
            },
            run_metadata={
                "analysis_id": analysis_id,
                "provider_id": provider_id,
                "applied_profile": applied_profile,
                "analysis_profile_status": analysis_profile_status,
                "best_case_guaranteed": best_case_guaranteed,
            },
        )
        db.add(run)

        analysis_row = db.query(RepositoryAnalysis).filter(
            RepositoryAnalysis.id == uuid.UUID(analysis_id)
        ).first()
        if analysis_row:
            analysis_metadata = analysis_row.analysis_metadata or {}
            if not isinstance(analysis_metadata, dict):
                analysis_metadata = {}
            analysis_metadata["latest_question_generation"] = {
                "experiment_id": experiment_id,
                "selector_experiment_id": selector_experiment_id,
                "selector_variant": selector_variant,
                "generator_variant": generator_variant,
                "provider_id": provider_id,
                "applied_profile": applied_profile,
                "analysis_profile_status": analysis_profile_status,
                "best_case_guaranteed": best_case_guaranteed,
                "generated_question_count": len(original_questions),
                "parsed_question_count": len(parsed_questions),
                "latency_ms": latency_ms,
                "created_at": datetime.now().isoformat(),
            }
            analysis_row.analysis_metadata = analysis_metadata

        db.commit()
        db.refresh(run)
        return str(run.id)
    except Exception as exc:
        db.rollback()
        print(f"[QUESTION_RUN] Error saving generation run: {exc}")
        return None
    finally:
        db.close()


def create_question_groups(questions: List[QuestionResponse]) -> Dict[str, List[str]]:
    """질문 그룹 관계 생성"""
    groups = {}
    
    for question in questions:
        if question.parent_question_id:
            parent_id = question.parent_question_id
            if parent_id not in groups:
                groups[parent_id] = []
            groups[parent_id].append(question.id)
    
    return groups


def is_header_or_title(text: str) -> bool:
    """
    텍스트가 제목이나 헤더인지 확인
    """
    text = text.strip()
    
    # 1. 마크다운 헤더 패턴 (#, ##, ###)
    if re.match(r'^#{1,6}\s+', text):
        return True
    
    # 2. numbered list로 시작하는 경우는 제목이 아님 (실제 질문일 가능성 높음)
    if re.match(r'^\d+\.\s+\*\*.*\*\*', text):
        return False
        
    # 3. 질문 키워드가 포함된 경우는 제목이 아님
    question_keywords = ['설명해주세요', '어떻게', '무엇', '왜', '방법', '차이점', '장점', '단점', 
                        '예시', '구체적으로', '비교', '선택', '고려', '적용', '사용', '?']
    if any(keyword in text for keyword in question_keywords):
        return False
    
    # 4. 제목 형태 패턴 (실제 섹션 제목들만)
    title_patterns = [
        r'^[가-힣\s]*기술\s*면접\s*질문[가-힣\s]*$',  # "기술 면접 질문"으로만 구성
        r'^[가-힣\s]*아키텍처[가-힣\s]*$',           # "아키텍처"만 포함하는 단순 제목
        r'^[가-힣\s]*관련\s*질문[가-힣\s]*$',        # "관련 질문"으로만 구성
        r'^[가-힣\s]*면접\s*문제[가-힣\s]*$',        # "면접 문제"로만 구성
    ]
    
    for pattern in title_patterns:
        if re.match(pattern, text, re.IGNORECASE):
            return True
    
    # 5. 질문이 아닌 짧은 문장 (물음표가 없고 너무 짧은 경우)
    if (len(text) < 15 and '?' not in text and 
        not any(keyword in text for keyword in ['설명', '어떻게', '무엇', '왜'])):
        return True
    
    # 6. 마크다운 구분자
    if text in ['---', '***', '===']:
        return True
    
    return False


def is_valid_question(text: str) -> bool:
    """
    텍스트가 유효한 질문인지 확인
    """
    text = text.strip()
    
    # 1. 최소 길이 확인
    if len(text) < 10:
        return False
    
    # 2. 질문 키워드 확인
    question_indicators = [
        '?', '어떻게', '무엇', '왜', '설명', '차이점', '장점', '단점', 
        '방법', '전략', '구현', '사용', '적용', '고려', '처리', '해결'
    ]
    
    has_question_indicator = any(indicator in text for indicator in question_indicators)
    
    # 3. 제목/헤더가 아닌지 확인
    is_not_header = not is_header_or_title(text)
    
    return has_question_indicator and is_not_header


def parse_compound_question(question: QuestionResponse) -> List[QuestionResponse]:
    """
    마크다운 내용을 정리하여 질문으로 변환
    
    Args:
        question: 원본 질문 객체
        
    Returns:
        List[QuestionResponse]: 정리된 질문 리스트
    """
    question_text = question.question

    # 1. 코드 블록과 설명 섹션 제거
    question_text = re.sub(r"```.*?```", " ", question_text, flags=re.DOTALL)
    question_text = re.split(r"\*\*(?:근거|의도|추가 설명|참조 코드|파일 경로)\*\*[:：]", question_text, maxsplit=1)[0]
    question_text = re.split(r"(?:근거|의도|추가 설명|참조 코드|파일 경로)[:：]", question_text, maxsplit=1)[0]

    # 2. 마크다운 제목과 불필요한 내용 제거
    question_text = re.sub(r'^#{1,6}\s+.*$', '', question_text, flags=re.MULTILINE)
    question_text = re.sub(r'^---+\s*$', '', question_text, flags=re.MULTILINE)
    question_text = re.sub(r'\n\s*\n', '\n\n', question_text)

    # 3. 줄 단위로 분리하여 처리
    lines = question_text.split('\n')
    processed_lines = []
    in_code_block = False
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        if line_stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
            
        # 마크다운 제목 스킵
        if re.match(r'^#{1,6}\s+', line_stripped):
            continue

        if re.match(r"^\*\*(?:근거|의도|추가 설명|참조 코드|파일 경로)\*\*[:：]", line_stripped):
            break
        if re.match(r"^(?:근거|의도|추가 설명|참조 코드|파일 경로)[:：]", line_stripped):
            break
            
        # numbered list 항목의 번호 제거 및 정리
        clean_line = line_stripped
        
        # 다양한 numbered list 패턴 처리
        patterns_to_remove = [
            r'^\d+\.\s+',      # "1. "
            r'^\d+\)\s+',      # "1) "
            r'^\s*\d+\.\s+',  # "  1. "
        ]
        
        for pattern in patterns_to_remove:
            if re.match(pattern, clean_line):
                clean_line = re.sub(pattern, '', clean_line).strip()
                break

        clean_line = re.sub(r'^\*\*질문\*\*[:：]?\s*', '', clean_line, flags=re.IGNORECASE)
        clean_line = clean_line.replace("**", "").strip()
        clean_line = re.sub(r'^질문[:：]?\s*', '', clean_line, flags=re.IGNORECASE)
        
        # 빈 줄이 아닌 경우만 추가
        if clean_line:
            processed_lines.append(clean_line)
    
    # 4. 처리된 내용을 하나의 질문으로 결합
    cleaned_question = ' '.join(processed_lines).strip().strip('"').strip("'")
    cleaned_question = re.sub(r'\s+', ' ', cleaned_question)
    cleaned_question = re.sub(
        r'^다음은 실제 .*?(?:기술면접 )?질문(?:입니다)?[:：]\s*',
        '',
        cleaned_question,
        flags=re.IGNORECASE,
    ).strip().strip('"').strip("'")
    cleaned_question = re.sub(
        r'^(?:실제 )?(?:package\.json|pyproject\.toml|README) 파일(?:의 내용)?(?:을 직접 참조하여)? 생성한 질문(?:입니다)?[:：]\s*',
        '',
        cleaned_question,
        flags=re.IGNORECASE,
    ).strip().strip('"').strip("'")
    has_choice_markers = any(
        re.search(pattern, cleaned_question)
        for pattern in (
            r'(?:^|\s)1[.)]\s+',
            r'(?:^|\s)2[.)]\s+',
            r'(?:^|\s)[A-D][.)]\s+',
            r'[①②③④]',
            r'(?:^|\s)[가나다라][.)]\s+',
            r'(?:^|\s)-\s+',
            r'(?:^|\s)•\s+',
        )
    )
    if cleaned_question.startswith("다음 중") and not has_choice_markers:
        cleaned_question = re.sub(r'^다음 중(?:에서)?\s*', '', cleaned_question).strip()
    
    # 5. 정리된 질문이 유효한지 확인
    if (len(cleaned_question) > 20 and 
        any(keyword in cleaned_question for keyword in ['설명해주세요', '어떻게', '무엇', '왜', '방법', '차이점', '?', '예시', '구체적'])):
        
        # 정리된 질문으로 업데이트
        question.question = cleaned_question
        return [question]
    
    # 6. 유효하지 않은 경우 원본 그대로 반환
    return [question]


def parse_questions_list(questions: List[QuestionResponse]) -> List[QuestionResponse]:
    """
    질문 리스트를 처리하여 compound question들을 분리
    
    Args:
        questions: 원본 질문 리스트
        
    Returns:
        List[QuestionResponse]: 파싱된 질문 리스트
    """
    parsed_questions = []
    
    for question in questions:
        # 각 질문을 파싱하여 결과 추가
        parsed_list = parse_compound_question(question)
        parsed_questions.extend(parsed_list)
    
    return parsed_questions


def ensure_unique_question_ids(questions: List[QuestionResponse]) -> List[QuestionResponse]:
    """
    모든 질문 ID를 전역 고유 UUID로 재할당하고 parent_question_id 참조도 함께 보정한다.

    interview_questions.id는 전역 unique primary key이므로,
    분석별로 짧은 난수 ID를 재사용하면 다른 analysis의 질문과 충돌할 수 있다.
    """
    id_remap: Dict[str, str] = {}
    normalized_questions: List[QuestionResponse] = []

    for question in questions:
        normalized_question = question.model_copy(deep=True)
        original_id = normalized_question.id or str(uuid.uuid4())
        new_id = str(uuid.uuid4())

        if original_id not in id_remap:
            id_remap[original_id] = new_id

        normalized_question.id = new_id
        normalized_questions.append(normalized_question)

    for question in normalized_questions:
        if question.parent_question_id:
            question.parent_question_id = id_remap.get(
                question.parent_question_id,
                question.parent_question_id,
            )

    return normalized_questions


class QuestionGenerationResult(BaseModel):
    """질문 생성 결과"""
    success: bool
    questions: List[QuestionResponse]
    analysis_id: Optional[str] = None
    error: Optional[str] = None
    experiment_id: Optional[str] = None
    selector_variant: Optional[str] = None
    generator_variant: Optional[str] = None
    applied_profile: Optional[str] = None
    analysis_profile_status: Optional[str] = None
    best_case_guaranteed: Optional[bool] = None


@router.post("/generate", response_model=QuestionGenerationResult)
async def generate_questions(
    request: QuestionGenerationRequest,
    github_token: Optional[str] = Header(None, alias="x-github-token"),
    google_api_key: Optional[str] = Header(None, alias="x-google-api-key"),
    upstage_api_key: Optional[str] = Header(None, alias="x-upstage-api-key"),
):
    """GitHub 저장소 분석 결과를 바탕으로 기술면접 질문 생성"""
    
    try:
        # 분석 결과에서 analysis_id 추출
        analysis_id = None
        if request.analysis_result and "analysis_id" in request.analysis_result:
            analysis_id = request.analysis_result["analysis_id"]

        selector_variant, selector_experiment_id = _extract_selector_context(request.analysis_result)
        analysis_profile_status, best_case_guaranteed = _resolve_analysis_profile_context(
            request.analysis_result
        )
        applied_profile = BEST_CASE_GENERATOR_PROFILE
        generator_variant = DEFAULT_GENERATOR_VARIANT

        # 이미 생성된 질문이 있는지 확인 (강제 재생성이 아닌 경우)
        if analysis_id and not request.force_regenerate:
            cache_data = get_question_cache_entry(
                analysis_id,
                selector_variant=selector_variant,
                generator_variant=generator_variant,
            )
            if cache_data:
                question_cache_active_keys[analysis_id] = cache_data.cache_key
                return QuestionGenerationResult(
                    success=True,
                    questions=cache_data.parsed_questions,
                    analysis_id=analysis_id,
                    experiment_id=cache_data.experiment_id,
                    selector_variant=cache_data.selector_variant,
                    generator_variant=cache_data.generator_variant,
                    applied_profile=cache_data.applied_profile,
                    analysis_profile_status=cache_data.analysis_profile_status,
                    best_case_guaranteed=cache_data.best_case_guaranteed,
                )

        started_at = time.perf_counter()

        # 헤더에서 API 키 추출
        api_keys = extract_api_keys_from_headers(github_token, google_api_key, upstage_api_key)

        # 질문 생성기 초기화
        generator = QuestionGenerator(
            preferred_provider=resolve_provider_id(request.provider_id)
        )

        # 질문 생성 실행 - QuestionGenerator 내부 기본값 사용 (3가지 타입 균등 분배)
        result = await generator.generate_questions(
            repo_url=request.repo_url,
            difficulty_level=request.difficulty,
            question_count=request.question_count,
            question_types=None,  # 기본값 ["tech_stack", "architecture", "code_analysis"] 사용
            analysis_data=request.analysis_result,
            api_keys=api_keys  # API 키 전달
        )

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "질문 생성 실패"))

        # 응답 형식에 맞게 변환
        questions = []
        for q in result["questions"]:
            questions.append(QuestionResponse(
                id=q.get("id", ""),
                type=q.get("type", "technical"),
                question=q.get("question", ""),
                difficulty=q.get("difficulty", request.difficulty),
                context=q.get("context"),
                time_estimate=q.get("time_estimate", "5분"),
                code_snippet=q.get("code_snippet"),
                expected_answer_points=q.get("expected_answer_points"),
                technology=q.get("technology"),
                pattern=q.get("pattern")
            ))

        # 질문 파싱 처리 (compound question 분리)
        parsed_questions = ensure_unique_question_ids(parse_questions_list(questions))

        # 질문 그룹 관계 생성
        question_groups = create_question_groups(parsed_questions)

        # 캐시에 저장 (구조화된 데이터)
        if analysis_id:
            cache_data = QuestionCacheData(
                analysis_id=analysis_id,
                cache_key=build_question_cache_key(
                    analysis_id,
                    selector_variant,
                    generator_variant,
                ),
                experiment_id=QUESTION_GENERATION_EXPERIMENT_ID,
                selector_variant=selector_variant,
                generator_variant=generator_variant,
                provider_id=request.provider_id,
                applied_profile=applied_profile,
                analysis_profile_status=analysis_profile_status,
                best_case_guaranteed=best_case_guaranteed,
                original_questions=questions,
                parsed_questions=parsed_questions,
                question_groups=question_groups,
                created_at=datetime.now().isoformat()
            )
            _store_question_cache_entry(cache_data)

            # DB에도 저장하여 영구 보존
            await _save_questions_to_db(
                analysis_id,
                parsed_questions,
                selector_variant=selector_variant,
                generator_variant=generator_variant,
                experiment_id=QUESTION_GENERATION_EXPERIMENT_ID,
                provider_id=request.provider_id,
                applied_profile=applied_profile,
                analysis_profile_status=analysis_profile_status,
                best_case_guaranteed=best_case_guaranteed,
            )

            _save_question_generation_run(
                analysis_id=analysis_id,
                experiment_id=QUESTION_GENERATION_EXPERIMENT_ID,
                selector_experiment_id=selector_experiment_id,
                selector_variant=selector_variant,
                generator_variant=generator_variant,
                provider_id=request.provider_id,
                applied_profile=applied_profile,
                analysis_profile_status=analysis_profile_status,
                best_case_guaranteed=best_case_guaranteed,
                original_questions=questions,
                parsed_questions=parsed_questions,
                question_groups=question_groups,
                latency_ms=int((time.perf_counter() - started_at) * 1000),
            )

            return QuestionGenerationResult(
                success=True,
                questions=parsed_questions,
                analysis_id=analysis_id,
                experiment_id=QUESTION_GENERATION_EXPERIMENT_ID,
                selector_variant=selector_variant,
                generator_variant=generator_variant,
                applied_profile=applied_profile,
                analysis_profile_status=analysis_profile_status,
                best_case_guaranteed=best_case_guaranteed,
            )

        return QuestionGenerationResult(
            success=True,
            questions=parsed_questions,
            analysis_id=analysis_id,
            experiment_id=QUESTION_GENERATION_EXPERIMENT_ID,
            selector_variant=selector_variant,
            generator_variant=generator_variant,
            applied_profile=applied_profile,
            analysis_profile_status=analysis_profile_status,
            best_case_guaranteed=best_case_guaranteed,
        )
        
    except Exception as e:
        return QuestionGenerationResult(
            success=False,
            questions=[],
            error=str(e)
        )


@router.get("/{analysis_id}")
async def get_questions(analysis_id: str):
    """분석 ID로 질문 조회"""
    try:
        cache_data = get_question_cache_entry(analysis_id)
        if not cache_data:
            raise HTTPException(status_code=404, detail="질문을 찾을 수 없습니다")

        return {
            "success": True,
            "questions": cache_data.parsed_questions,
            "question_groups": cache_data.question_groups,
            "created_at": cache_data.created_at,
            "selector_variant": cache_data.selector_variant,
            "generator_variant": cache_data.generator_variant,
            "applied_profile": cache_data.applied_profile,
            "analysis_profile_status": cache_data.analysis_profile_status,
            "best_case_guaranteed": cache_data.best_case_guaranteed,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{analysis_id}/groups")
async def get_question_groups(analysis_id: str):
    """질문 그룹 정보 조회"""
    try:
        cache_data = get_question_cache_entry(analysis_id)
        if not cache_data:
            raise HTTPException(status_code=404, detail="질문을 찾을 수 없습니다")

        return {
            "success": True,
            "question_groups": cache_data.question_groups,
            "total_questions": len(cache_data.parsed_questions),
            "total_groups": len(cache_data.question_groups),
            "selector_variant": cache_data.selector_variant,
            "generator_variant": cache_data.generator_variant,
            "applied_profile": cache_data.applied_profile,
            "analysis_profile_status": cache_data.analysis_profile_status,
            "best_case_guaranteed": cache_data.best_case_guaranteed,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/clear")
async def clear_question_cache():
    """질문 캐시 초기화"""
    try:
        global question_cache
        cache_count = len(question_cache)
        question_cache.clear()
        question_cache_active_keys.clear()
        
        return {
            "success": True,
            "message": f"질문 캐시가 초기화되었습니다. ({cache_count}개 항목 제거)",
            "cleared_count": cache_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/status")
async def get_cache_status():
    """질문 캐시 상태 조회"""
    try:
        cache_info = {}
        for cache_key, cache_data in question_cache.items():
            cache_info[cache_key] = {
                "analysis_id": cache_data.analysis_id,
                "cache_key": cache_key,
                "original_questions_count": len(cache_data.original_questions),
                "parsed_questions_count": len(cache_data.parsed_questions),
                "groups_count": len(cache_data.question_groups),
                "created_at": cache_data.created_at,
                "selector_variant": cache_data.selector_variant,
                "generator_variant": cache_data.generator_variant,
                "applied_profile": cache_data.applied_profile,
                "analysis_profile_status": cache_data.analysis_profile_status,
                "best_case_guaranteed": cache_data.best_case_guaranteed,
            }
        
        return {
            "success": True,
            "total_cached_analyses": len(question_cache),
            "active_cache_keys": question_cache_active_keys,
            "cache_details": cache_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/{analysis_id}")
async def get_questions_by_analysis(analysis_id: str):
    """분석 ID로 생성된 질문 조회 - 메모리 캐시 우선, 없으면 DB 조회"""
    try:
        # 1. 먼저 메모리 캐시에서 조회
        cache_data = get_question_cache_entry(analysis_id)
        if cache_data:
            print(f"[QUESTIONS] Found questions in memory cache for {analysis_id}")
            return QuestionGenerationResult(
                success=True,
                questions=cache_data.parsed_questions,
                analysis_id=analysis_id,
                experiment_id=cache_data.experiment_id,
                selector_variant=cache_data.selector_variant,
                generator_variant=cache_data.generator_variant,
                applied_profile=cache_data.applied_profile,
                analysis_profile_status=cache_data.analysis_profile_status,
                best_case_guaranteed=cache_data.best_case_guaranteed,
            )
        
        # 2. 메모리 캐시에 없으면 DB에서 조회
        print(f"[QUESTIONS] Memory cache miss, checking database for {analysis_id}")
        db_questions, cache_metadata = await _load_questions_from_db(analysis_id)
        
        if db_questions:
            print(f"[QUESTIONS] Found {len(db_questions)} questions in database, restoring to cache")
            
            # DB에서 가져온 질문들을 메모리 캐시에 복원
            await _restore_questions_to_cache(
                analysis_id,
                db_questions,
                experiment_id=cache_metadata.get("experiment_id", QUESTION_GENERATION_EXPERIMENT_ID),
                selector_variant=cache_metadata.get("selector_variant", "selector_v1"),
                generator_variant=cache_metadata.get("generator_variant", DEFAULT_GENERATOR_VARIANT),
                provider_id=cache_metadata.get("provider_id"),
                applied_profile=cache_metadata.get("applied_profile"),
                analysis_profile_status=cache_metadata.get("analysis_profile_status", ANALYSIS_STATUS_LEGACY_UNVERIFIED),
                best_case_guaranteed=cache_metadata.get("best_case_guaranteed", False),
            )
            
            return QuestionGenerationResult(
                success=True,
                questions=db_questions,
                analysis_id=analysis_id,
                experiment_id=cache_metadata.get("experiment_id", QUESTION_GENERATION_EXPERIMENT_ID),
                selector_variant=cache_metadata.get("selector_variant", "selector_v1"),
                generator_variant=cache_metadata.get("generator_variant", DEFAULT_GENERATOR_VARIANT),
                applied_profile=cache_metadata.get("applied_profile"),
                analysis_profile_status=cache_metadata.get("analysis_profile_status", ANALYSIS_STATUS_LEGACY_UNVERIFIED),
                best_case_guaranteed=cache_metadata.get("best_case_guaranteed", False),
            )
        
        # 3. 메모리 캐시와 DB 모두에 없음
        print(f"[QUESTIONS] No questions found for {analysis_id} in cache or database")
        return QuestionGenerationResult(
            success=False,
            questions=[],
            analysis_id=analysis_id,
            error="해당 분석 ID에 대한 질문이 없습니다."
        )
        
    except Exception as e:
        print(f"Error in get_questions_by_analysis: {e}")
        return QuestionGenerationResult(
            success=False,
            questions=[],
            analysis_id=analysis_id,
            error=f"질문 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/types")
async def get_question_types():
    """사용 가능한 질문 타입 목록 조회"""
    return {
        "question_types": [
            "code_analysis",
            "tech_stack", 
            "architecture",
            "design_patterns",
            "problem_solving",
            "best_practices"
        ],
        "difficulties": ["easy", "medium", "hard"]
    }


@router.get("/debug/cache")
async def debug_question_cache():
    """질문 캐시 상태 확인 (디버깅용)"""
    return {
        "cache_size": len(question_cache),
        "cached_analysis_ids": list(question_cache.keys()),
        "cache_details": [
            {
                "analysis_id": cache_data.analysis_id,
                "cache_key": cache_key,
                "original_question_count": len(cache_data.original_questions),
                "parsed_question_count": len(cache_data.parsed_questions),
                "selector_variant": cache_data.selector_variant,
                "generator_variant": cache_data.generator_variant,
                "applied_profile": cache_data.applied_profile,
                "analysis_profile_status": cache_data.analysis_profile_status,
                "best_case_guaranteed": cache_data.best_case_guaranteed,
                "question_types": list(set(q.type for q in cache_data.parsed_questions))
            }
            for cache_key, cache_data in question_cache.items()
        ]
    }


@router.get("/debug/original/{analysis_id}")
async def debug_original_questions(analysis_id: str):
    """원본 질문 확인 (디버깅용)"""
    try:
        cache_data = get_question_cache_entry(analysis_id)
        if not cache_data:
            raise HTTPException(status_code=404, detail="질문을 찾을 수 없습니다")

        return {
            "success": True,
            "original_questions": [
                {
                    "id": q.id,
                    "type": q.type, 
                    "question": q.question,
                    "is_compound": q.is_compound_question,
                    "total_sub_questions": q.total_sub_questions
                }
                for q in cache_data.original_questions
            ],
            "parsed_questions_count": len(cache_data.parsed_questions),
            "groups_count": len(cache_data.question_groups),
            "selector_variant": cache_data.selector_variant,
            "generator_variant": cache_data.generator_variant,
            "applied_profile": cache_data.applied_profile,
            "analysis_profile_status": cache_data.analysis_profile_status,
            "best_case_guaranteed": cache_data.best_case_guaranteed,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/debug/add-test-questions/{analysis_id}")
async def add_test_questions(analysis_id: str):
    """테스트용 질문 추가 (디버깅용)"""
    try:
        # 테스트용 질문 생성
        test_questions = [
            QuestionResponse(
                id=str(uuid.uuid4()),
                type="technical",
                question="Linux 커널의 주요 서브시스템에 대해 설명해주세요.",
                difficulty="medium",
                context="Linux 커널 아키텍처",
                time_estimate="5분",
                technology="C"
            ),
            QuestionResponse(
                id=str(uuid.uuid4()),
                type="architecture",
                question="1. 메모리 관리 서브시스템의 역할은?\n2. 프로세스 스케줄러의 동작 원리는?\n3. 파일 시스템의 VFS 레이어 목적은?",
                difficulty="medium",
                context="Linux 커널 아키텍처",
                time_estimate="10분",
                technology="C"
            ),
            QuestionResponse(
                id=str(uuid.uuid4()),
                type="code_analysis",
                question="디바이스 드라이버를 작성할 때 고려해야 할 주요 요소들은 무엇인가요?",
                difficulty="medium",
                context="Linux 커널 개발",
                time_estimate="7분",
                technology="C"
            )
        ]
        
        # 질문 파싱 처리
        parsed_questions = parse_questions_list(test_questions)
        
        # 질문 그룹 관계 생성
        question_groups = create_question_groups(parsed_questions)
        
        # 캐시에 저장
        cache_data = QuestionCacheData(
            analysis_id=analysis_id,
            cache_key=build_question_cache_key(analysis_id, "selector_v1", DEFAULT_GENERATOR_VARIANT),
            experiment_id=QUESTION_GENERATION_EXPERIMENT_ID,
            selector_variant="selector_v1",
            generator_variant=DEFAULT_GENERATOR_VARIANT,
            original_questions=test_questions,
            parsed_questions=parsed_questions,
            question_groups=question_groups,
            created_at=datetime.now().isoformat()
        )
        _store_question_cache_entry(cache_data)
        
        return {
            "success": True,
            "message": f"테스트 질문이 추가되었습니다. (원본: {len(test_questions)}, 파싱: {len(parsed_questions)})",
            "analysis_id": analysis_id,
            "questions": parsed_questions
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/debug/cache")
async def debug_question_cache():
    """질문 캐시 상태 확인 (디버깅용)"""
    return {
        "cache_size": len(question_cache),
        "cached_analysis_ids": list(question_cache.keys()),
        "cache_details": [
            {
                "analysis_id": cache_data.analysis_id,
                "cache_key": cache_key,
                "question_count": len(cache_data.parsed_questions),
                "created_at": cache_data.created_at,
                "selector_variant": cache_data.selector_variant,
                "generator_variant": cache_data.generator_variant,
                "applied_profile": cache_data.applied_profile,
                "analysis_profile_status": cache_data.analysis_profile_status,
                "best_case_guaranteed": cache_data.best_case_guaranteed,
            }
            for cache_key, cache_data in question_cache.items()
        ]
    }


@router.delete("/debug/cache")
async def clear_question_cache():
    """질문 캐시 초기화 (디버깅용)"""
    cache_size_before = len(question_cache)
    question_cache.clear()
    question_cache_active_keys.clear()
    
    return {
        "message": "질문 캐시가 성공적으로 초기화되었습니다",
        "cleared_items": cache_size_before,
        "current_cache_size": len(question_cache)
    }


async def _load_questions_from_db(analysis_id: str) -> Tuple[List[QuestionResponse], Dict[str, Any]]:
    """데이터베이스에서 질문 조회"""
    try:
        with engine.connect() as conn:
            # InterviewQuestion 테이블에서 질문 조회
            result = conn.execute(text(
                """
                SELECT id, category, difficulty, question_text, expected_points, 
                       related_files, context, created_at
                FROM interview_questions 
                WHERE analysis_id = :analysis_id
                ORDER BY created_at ASC
                """
            ), {"analysis_id": analysis_id})
            
            questions = []
            cache_metadata: Dict[str, Any] = {
                "experiment_id": QUESTION_GENERATION_EXPERIMENT_ID,
                "selector_variant": "selector_v1",
                "generator_variant": LEGACY_GENERATOR_VARIANT,
                "provider_id": None,
                "applied_profile": None,
                "analysis_profile_status": ANALYSIS_STATUS_LEGACY_UNVERIFIED,
                "best_case_guaranteed": False,
            }
            for row in result:
                context_value = row[6]
                if isinstance(context_value, str):
                    try:
                        context_value = json.loads(context_value)
                    except json.JSONDecodeError:
                        context_value = {}
                elif not isinstance(context_value, dict):
                    context_value = {}

                experiment_meta = context_value.get("experiment", {})
                if experiment_meta:
                    cache_metadata = {
                        "experiment_id": experiment_meta.get("experiment_id", QUESTION_GENERATION_EXPERIMENT_ID),
                        "selector_variant": experiment_meta.get("selector_variant", "selector_v1"),
                        "generator_variant": experiment_meta.get("generator_variant", LEGACY_GENERATOR_VARIANT),
                        "provider_id": experiment_meta.get("provider_id"),
                        "applied_profile": experiment_meta.get("applied_profile"),
                        "analysis_profile_status": experiment_meta.get(
                            "analysis_profile_status",
                            ANALYSIS_STATUS_LEGACY_UNVERIFIED,
                        ),
                        "best_case_guaranteed": experiment_meta.get("best_case_guaranteed", False),
                    }

                # expected_points JSON 파싱
                expected_points = None
                if row[4]:  # expected_points 필드
                    try:
                        expected_points = json.loads(row[4]) if isinstance(row[4], str) else row[4]
                    except json.JSONDecodeError:
                        expected_points = None
                
                # 데이터베이스 row를 QuestionResponse 객체로 변환
                question = QuestionResponse(
                    id=str(row[0]),
                    type=row[1],  # category -> type
                    question=row[3],  # question_text -> question
                    difficulty=row[2],
                    context=None,  # context는 JSON이므로 간단히 None으로 처리
                    time_estimate="5분",  # 기본값
                    code_snippet=None,
                    expected_answer_points=expected_points,
                    technology=None,
                    pattern=None
                )
                questions.append(question)
            
            print(f"[DB] Loaded {len(questions)} questions from database for analysis {analysis_id}")
            return questions, cache_metadata
            
    except Exception as e:
        print(f"[DB] Error loading questions from database: {e}")
        return [], {
            "experiment_id": QUESTION_GENERATION_EXPERIMENT_ID,
            "selector_variant": "selector_v1",
            "generator_variant": LEGACY_GENERATOR_VARIANT,
            "provider_id": None,
            "applied_profile": None,
            "analysis_profile_status": ANALYSIS_STATUS_LEGACY_UNVERIFIED,
            "best_case_guaranteed": False,
        }


async def _restore_questions_to_cache(
    analysis_id: str,
    questions: List[QuestionResponse],
    *,
    experiment_id: str = QUESTION_GENERATION_EXPERIMENT_ID,
    selector_variant: str = "selector_v1",
    generator_variant: str = DEFAULT_GENERATOR_VARIANT,
    provider_id: Optional[str] = None,
    applied_profile: Optional[str] = None,
    analysis_profile_status: str = ANALYSIS_STATUS_LEGACY_UNVERIFIED,
    best_case_guaranteed: bool = False,
):
    """DB에서 가져온 질문들을 메모리 캐시에 복원"""
    try:
        # 질문 그룹 관계 생성
        question_groups = create_question_groups(questions)
        
        # 캐시에 저장할 데이터 구조 생성
        cache_data = QuestionCacheData(
            analysis_id=analysis_id,
            cache_key=build_question_cache_key(analysis_id, selector_variant, generator_variant),
            experiment_id=experiment_id,
            selector_variant=selector_variant,
            generator_variant=generator_variant,
            provider_id=provider_id,
            applied_profile=applied_profile,
            analysis_profile_status=analysis_profile_status,
            best_case_guaranteed=best_case_guaranteed,
            original_questions=questions,  # DB에서 가져온 질문들을 원본으로 처리
            parsed_questions=questions,    # 이미 파싱된 상태로 간주
            question_groups=question_groups,
            created_at=datetime.now().isoformat()
        )
        
        # 메모리 캐시에 저장
        _store_question_cache_entry(cache_data)
        
        print(f"[CACHE] Restored {len(questions)} questions to memory cache for analysis {analysis_id}")
        
    except Exception as e:
        print(f"[CACHE] Error restoring questions to cache: {e}")


async def _save_questions_to_db(
    analysis_id: str,
    questions: List[QuestionResponse],
    *,
    selector_variant: str,
    generator_variant: str,
    experiment_id: str,
    provider_id: Optional[str] = None,
    applied_profile: Optional[str] = None,
    analysis_profile_status: str = ANALYSIS_STATUS_LEGACY_UNVERIFIED,
    best_case_guaranteed: bool = False,
):
    """생성된 질문들을 데이터베이스에 저장"""
    try:
        with engine.connect() as conn:
            # 기존 질문이 있으면 삭제 (중복 방지)
            conn.execute(text(
                "DELETE FROM interview_questions WHERE analysis_id = :analysis_id"
            ), {"analysis_id": analysis_id})
            
            # 새로운 질문들 저장
            from datetime import datetime
            current_time = datetime.now()
            
            for question in questions:
                conn.execute(text(
                    """
                    INSERT INTO interview_questions 
                    (id, analysis_id, category, difficulty, question_text, expected_points, context, created_at)
                    VALUES (:id, :analysis_id, :category, :difficulty, :question_text, :expected_points, :context, :created_at)
                    """
                ), {
                    "id": question.id,
                    "analysis_id": analysis_id,
                    "category": question.type,
                    "difficulty": question.difficulty,
                    "question_text": question.question,
                    "expected_points": json.dumps(question.expected_answer_points) if question.expected_answer_points else None,
                    "context": json.dumps({
                        "experiment": {
                            "experiment_id": experiment_id,
                            "selector_variant": selector_variant,
                            "generator_variant": generator_variant,
                            "provider_id": provider_id,
                            "applied_profile": applied_profile,
                            "analysis_profile_status": analysis_profile_status,
                            "best_case_guaranteed": best_case_guaranteed,
                        }
                    }),
                    "created_at": current_time
                })
            
            # 변경사항 커밋
            conn.commit()
            
            print(f"[DB] Saved {len(questions)} questions to database for analysis {analysis_id}")
            
    except Exception as e:
        print(f"[DB] Error saving questions to database: {e}")
        # DB 저장 실패는 질문 생성 자체를 실패시키지 않음
