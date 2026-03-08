"""
Interview API Router

모의면접 세션 관리 및 실시간 면접 진행을 위한 API 엔드포인트
"""

import uuid
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from datetime import datetime, timedelta

from app.core.config import settings
from app.models.interview_session import (
    InterviewSessionData,
    InterviewStatus,
    FeedbackType,
    MessageType,
    QuestionFeedback,
    session_manager
)

# Legacy 임시 메모리 저장소 (호환성 유지)
interview_cache = {}

router = APIRouter()


class InterviewStartRequest(BaseModel):
    """면접 시작 요청"""
    repo_url: HttpUrl
    analysis_id: str
    question_ids: List[str]
    interview_type: str = "technical"
    difficulty_level: str = "medium"


class QuestionData(BaseModel):
    """질문 데이터"""
    id: str
    question: str
    type: str
    difficulty: str
    context: Optional[str] = None
    technology: Optional[str] = None
    time_estimate: Optional[str] = None


class InterviewSession(BaseModel):
    """면접 세션 정보"""
    interview_id: str
    analysis_id: str
    repo_url: str
    question_ids: List[str]
    current_question_index: int
    interview_type: str
    difficulty_level: str
    status: str  # "active", "paused", "completed"
    started_at: datetime
    expected_duration: int  # 예상 소요 시간 (분)
    participant_name: Optional[str] = None


class QuestionResponse(BaseModel):
    """질문 응답"""
    question_id: str
    question_text: str
    user_answer: str
    response_time: int  # 초
    confidence_score: Optional[float] = None


class InterviewAnswer(BaseModel):
    """면접 답변 제출"""
    interview_id: str
    question_id: str
    answer: str
    time_taken: int  # 초


class ConversationRequest(BaseModel):
    """대화 모드 질문"""
    interview_id: str
    question_id: str
    original_answer: str
    conversation_question: str


class InterviewResult(BaseModel):
    """면접 결과"""
    interview_id: str
    total_questions: int
    answered_questions: int
    total_time: int  # 초
    average_confidence: float
    status: str
    completed_at: Optional[datetime] = None


@router.post("/start")
async def start_interview(request: InterviewStartRequest):
    """새 면접 세션 시작"""
    try:
        # 질문 ID 유효성 검증
        if not request.question_ids:
            raise HTTPException(status_code=400, detail="질문 ID가 제공되지 않았습니다.")
        
        # 질문 캐시에서 질문이 존재하는지 확인
        from app.api.questions import question_cache
        if request.analysis_id not in question_cache:
            raise HTTPException(status_code=400, detail="해당 분석 ID에 대한 질문이 없습니다. 먼저 질문을 생성해주세요.")
        
        cache_data = question_cache[request.analysis_id]
        cached_questions = cache_data.parsed_questions
        available_question_ids = {q.id for q in cached_questions}
        
        # 요청된 질문 ID가 모두 캐시에 있는지 확인
        missing_question_ids = set(request.question_ids) - available_question_ids
        if missing_question_ids:
            raise HTTPException(status_code=400, detail=f"다음 질문 ID를 찾을 수 없습니다: {list(missing_question_ids)}")
        
        # 면접 ID 생성
        interview_id = str(uuid.uuid4())
        
        # 새로운 세션 관리 시스템을 사용하여 세션 생성
        session = session_manager.create_session(
            interview_id=interview_id,
            analysis_id=request.analysis_id,
            repo_url=str(request.repo_url),
            question_ids=request.question_ids,
            interview_type=request.interview_type,
            difficulty_level=request.difficulty_level
        )
        
        # 시작 메시지 추가
        session.add_conversation_message(
            MessageType.SYSTEM,
            "면접이 시작되었습니다. 첫 번째 질문부터 시작해주세요!",
            metadata={"event": "interview_started"}
        )
        
        # Legacy 호환성을 위해 기존 캐시에도 저장
        legacy_session = InterviewSession(
            interview_id=interview_id,
            analysis_id=request.analysis_id,
            repo_url=str(request.repo_url),
            question_ids=request.question_ids,
            current_question_index=0,
            interview_type=request.interview_type,
            difficulty_level=request.difficulty_level,
            status="active",
            started_at=datetime.utcnow(),
            expected_duration=session.expected_duration
        )
        interview_cache[interview_id] = legacy_session
        
        return {
            "success": True,
            "message": "면접이 성공적으로 시작되었습니다.",
            "data": {
                "interview_id": interview_id,
                "expected_duration": session.expected_duration,
                "total_questions": len(request.question_ids),
                "status": session.status.value
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"면접 시작에 실패했습니다: {str(e)}")


@router.get("/session/{interview_id}")
async def get_interview_session(interview_id: str):
    """면접 세션 정보 조회"""
    try:
        # UUID 검증
        uuid.UUID(interview_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="올바르지 않은 면접 ID 형식입니다.")
    
    if interview_id not in interview_cache:
        raise HTTPException(status_code=404, detail="면접 세션을 찾을 수 없습니다.")
    
    session = interview_cache[interview_id]
    
    # 현재 진행 상황 계산
    progress = {
        "current_question": session.current_question_index + 1,
        "total_questions": len(session.question_ids),
        "progress_percentage": round((session.current_question_index / len(session.question_ids)) * 100, 1),
        "elapsed_time": int((datetime.utcnow() - session.started_at).total_seconds()),
        "remaining_time": max(0, session.expected_duration * 60 - int((datetime.utcnow() - session.started_at).total_seconds()))
    }
    
    return {
        "success": True,
        "data": {
            "interview_id": interview_id,
            "analysis_id": session.analysis_id,
            "repo_url": session.repo_url,
            "status": session.status,
            "interview_type": session.interview_type,
            "difficulty_level": session.difficulty_level,
            "started_at": session.started_at.isoformat(),
            "progress": progress
        }
    }


@router.post("/answer")
async def submit_answer(answer_request: InterviewAnswer):
    """면접 답변 제출 및 분석"""
    interview_id = answer_request.interview_id
    
    try:
        # UUID 검증
        uuid.UUID(interview_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="올바르지 않은 면접 ID 형식입니다.")
    
    # 새로운 세션 관리자에서 세션 가져오기
    session_data = session_manager.get_session(interview_id)
    if not session_data:
        print(f"[ERROR] 새로운 세션 매니저에서 세션을 찾을 수 없음: {interview_id}")
        print(f"[DEBUG] 현재 활성 세션 수: {session_manager.get_session_count()}")
        
        # Legacy 시스템에서 세션 확인
        if interview_id in interview_cache:
            print(f"[INFO] Legacy 캐시에서 세션 발견: {interview_id}")
            legacy_session = interview_cache[interview_id]
            
            # Legacy 세션을 새로운 시스템으로 마이그레이션
            session_data = session_manager.create_session(
                interview_id=interview_id,
                analysis_id=legacy_session.analysis_id,
                repo_url=legacy_session.repo_url,
                question_ids=legacy_session.question_ids,
                interview_type=legacy_session.interview_type,
                difficulty_level=legacy_session.difficulty_level
            )
            session_data.current_question_index = legacy_session.current_question_index
            session_data.started_at = legacy_session.started_at
            session_manager.update_session(interview_id, session_data)
            print(f"[INFO] Legacy 세션을 새로운 시스템으로 마이그레이션 완료")
        else:
            print(f"[ERROR] Legacy 캐시에서도 세션을 찾을 수 없음")
            raise HTTPException(
                status_code=404, 
                detail="면접 세션을 찾을 수 없습니다. 서버가 재시작되었거나 세션이 만료되었을 수 있습니다. 면접을 다시 시작해주세요."
            )
    
    print(f"[DEBUG] 세션 상태: {session_data.status}, 타입: {type(session_data.status)}")
    print(f"[DEBUG] InterviewStatus.ACTIVE: {InterviewStatus.ACTIVE}, 타입: {type(InterviewStatus.ACTIVE)}")
    
    if session_data.status != InterviewStatus.ACTIVE:
        print(f"[ERROR] 세션이 활성 상태가 아님: {session_data.status}")
        raise HTTPException(status_code=400, detail=f"활성화된 면접 세션이 아닙니다. 현재 상태: {session_data.status}")
    
    # 질문 정보 가져오기 (답변 분석에 필요)
    from app.api.questions import question_cache
    current_question = None
    
    if session_data.analysis_id in question_cache:
        cache_data = question_cache[session_data.analysis_id]
        cached_questions = cache_data.parsed_questions
        question_id_to_data = {q.id: q for q in cached_questions}
        
        if answer_request.question_id in question_id_to_data:
            current_question = question_id_to_data[answer_request.question_id]
    
    # 첫 번째 답변인지 확인 (답변 추가 전에 체크)
    existing_answer = session_data.get_answer_by_question_id(answer_request.question_id)
    is_first_answer = existing_answer is None
    print(f"[DEBUG] 질문 {answer_request.question_id}: 첫 번째 답변? {is_first_answer}, 기존 답변: {existing_answer is not None}")
    print(f"[DEBUG] 현재 세션 답변 개수: {len(session_data.answers)}")
    if session_data.answers:
        print(f"[DEBUG] 기존 답변들의 질문 ID: {[a.question_id for a in session_data.answers]}")
    else:
        print(f"[DEBUG] 세션에 기존 답변이 없음")
    
    # 세션에 답변 추가
    session_data.add_answer(
        question_id=answer_request.question_id,
        question_text=current_question.question if current_question else "",
        user_answer=answer_request.answer,
        response_time=answer_request.time_taken
    )
    
    # 답변 분석 수행
    feedback = None
    feedback_data = None
    if current_question:
        try:
            from app.services.answer_analyzer import answer_analyzer
            
            question_dict = {
                "id": current_question.id,
                "question": current_question.question,
                "category": current_question.type,
                "difficulty": current_question.difficulty,
                "context": current_question.context
            }
            
            # 첫 번째 답변만 정식 분석, 추가 답변은 대화형 응답만 제공
            if is_first_answer:
                print(f"[DEBUG] 첫 번째 답변으로 인식 - 정식 AI 분석 시작")
                analysis_result = await answer_analyzer.analyze_answer(question_dict, answer_request.answer)
                
                # 피드백 타입 매핑 (answer_analyzer의 FeedbackType -> interview_session의 FeedbackType)
                analyzer_feedback_type = analysis_result.feedback_type.value.lower()
                if analyzer_feedback_type in ["strength", "good"]:
                    session_feedback_type = FeedbackType.GOOD
                elif analyzer_feedback_type in ["improvement", "needs_improvement"]:
                    session_feedback_type = FeedbackType.NEEDS_IMPROVEMENT
                elif analyzer_feedback_type in ["suggestion", "average"]:
                    session_feedback_type = FeedbackType.AVERAGE
                elif analyzer_feedback_type in ["keyword_missing", "poor"]:
                    session_feedback_type = FeedbackType.POOR
                else:
                    # 점수 기반 fallback
                    if analysis_result.score >= 8:
                        session_feedback_type = FeedbackType.GOOD
                    elif analysis_result.score >= 6:
                        session_feedback_type = FeedbackType.AVERAGE
                    elif analysis_result.score >= 4:
                        session_feedback_type = FeedbackType.NEEDS_IMPROVEMENT
                    else:
                        session_feedback_type = FeedbackType.POOR
                
                # 피드백 데이터 생성
                feedback_data = QuestionFeedback(
                    question_id=answer_request.question_id,
                    score=analysis_result.score,
                    message=analysis_result.message,
                    feedback_type=session_feedback_type,
                    details=analysis_result.details,
                    suggestions=analysis_result.suggestions
                )
                
                # 세션에 피드백 추가
                session_data.add_feedback(answer_request.question_id, feedback_data)
                
                feedback = {
                    "score": analysis_result.score,
                    "message": analysis_result.message,
                    "feedback_type": analysis_result.feedback_type.value,
                    "details": analysis_result.details,
                    "suggestions": analysis_result.suggestions
                }
                print(f"[INFO] AI 분석 완료: 점수 {analysis_result.score}")
            else:
                print(f"[DEBUG] 추가 답변으로 인식 - 대화형 응답 생성")
                # 추가 답변에 대한 대화형 응답 생성 (점수/평가 없이)
                conversation_prompt = f"""당신은 경험이 풍부한 기술면접관입니다. 면접자가 추가로 질문하거나 답변을 보완하고 있습니다.

**원래 질문**: {current_question.question}
**면접자의 추가 답변/질문**: {answer_request.answer}

다음과 같이 자연스럽고 도움이 되는 응답을 해주세요:
- 점수나 평가 없이 내용 위주로 응답
- 면접관 톤으로 친근하지만 전문적으로 답변
- 구체적이고 실용적인 조언 제공
- 하나의 통합된 답변으로 제공 (개선 제안으로 나누지 말고)

200-300자 내외로 답변해주세요."""

                from app.core.ai_service import ai_service, AIProvider
                
                ai_response = await ai_service.generate_analysis(
                    prompt=conversation_prompt,
                    provider=AIProvider.GEMINI_FLASH
                )
                
                conversation_response = ai_response["content"]
                
                # 대화형 피드백 (점수 없음)
                feedback = {
                    "message": conversation_response,
                    "is_conversation": True,  # 프론트엔드에서 구분용
                    "feedback_type": "conversation"
                }
                print(f"[INFO] 추가 답변에 대한 대화형 응답 생성 완료")
            
        except Exception as e:
            print(f"[WARNING] AI 분석 실패, fallback 사용: {str(e)}")
            
            if is_first_answer:
                # 첫 번째 답변에만 fallback 피드백 제공
                answer_text = answer_request.answer.strip()
                answer_length = len(answer_text)
                word_count = len(answer_text.split())
                
                # 답변 길이와 내용에 따른 점수 계산
                if answer_length < 10 or answer_text.lower() in ['모르겠습니다', '모르겠어', '모르겠음', '모름', '잘 모르겠습니다']:
                    fallback_score = 2.0
                    message = "답변이 너무 간단합니다. 알고 있는 내용이라도 최대한 구체적으로 설명해보세요."
                    feedback_type = FeedbackType.NEEDS_IMPROVEMENT
                    details = f"답변 길이: {answer_length}자. 기술면접에서는 '모르겠다'고 답하기보다는 관련 지식이나 추론 과정을 보여주는 것이 중요합니다. 부분적으로라도 아는 내용을 설명하거나, 문제 해결 접근 방식을 제시해보세요."
                    suggestions = [
                        "관련된 기본 개념부터 설명 시작하기",
                        "알고 있는 유사한 기술이나 경험 언급하기", 
                        "문제 해결을 위한 접근 방법 제시하기",
                        "학습 계획이나 추가로 공부할 방향 제시하기"
                    ]
                elif answer_length < 50:
                    fallback_score = 3.5
                    message = "답변의 기본 방향은 좋으나 더 구체적인 설명이 필요합니다."
                    feedback_type = FeedbackType.NEEDS_IMPROVEMENT
                    details = f"답변 길이: {answer_length}자, 단어 수: {word_count}개. 기본 아이디어는 있지만 설명이 부족합니다. 구체적인 예시, 단계별 설명, 실무 적용 사례 등을 추가하면 더 완성도 높은 답변이 될 것입니다."
                    suggestions = [
                        "구체적인 코드 예시나 실제 사례 추가",
                        "단계별로 더 자세한 설명 제공",
                        "장단점이나 주의사항 언급",
                        "실무에서의 적용 경험이나 고려사항 추가"
                    ]
                elif answer_length < 150:
                    fallback_score = 5.5
                    message = "기본적인 내용은 잘 설명했습니다. 심화 내용을 추가하면 더 좋겠습니다."
                    feedback_type = FeedbackType.AVERAGE
                    details = f"답변 길이: {answer_length}자, 단어 수: {word_count}개. 기본 개념에 대한 이해는 보여주고 있습니다. 더 깊이 있는 분석이나 실무 경험, 다양한 관점에서의 접근을 추가하면 우수한 답변이 될 것입니다."
                    suggestions = [
                        "기술의 내부 동작 원리나 메커니즘 설명",
                        "다른 대안 기술과의 비교 분석",
                        "실무 프로젝트에서 겪은 경험이나 트러블슈팅 사례",
                        "성능, 보안, 확장성 등 비기능적 요구사항 고려"
                    ]
                else:
                    fallback_score = 7.0
                    message = "상세한 답변을 해주셨습니다. 실무 경험이나 구체적 사례가 더 있다면 완벽할 것 같습니다."
                    feedback_type = FeedbackType.GOOD
                    details = f"답변 길이: {answer_length}자, 단어 수: {word_count}개. 충분히 자세한 설명을 제공했습니다. 기술적 깊이와 실무 경험을 더 보강하면 매우 우수한 답변이 될 것입니다."
                    suggestions = [
                        "실제 프로젝트에서의 구현 경험이나 도전과제 공유",
                        "최신 트렌드나 업계 모범사례 언급",
                        "성능 최적화나 문제 해결 경험 추가",
                        "팀 협업이나 코드 리뷰 관점에서의 고려사항"
                    ]
                
                # 질문 카테고리별 맞춤 제안사항 추가
                if current_question and current_question.type:
                    category_suggestions = _get_category_specific_suggestions(current_question.type)
                    suggestions.extend(category_suggestions[:2])  # 최대 2개 추가
                
                feedback_data = QuestionFeedback(
                    question_id=answer_request.question_id,
                    score=fallback_score,
                    message=message,
                    feedback_type=feedback_type,
                    details=details,
                    suggestions=suggestions[:5]  # 최대 5개로 제한
                )
                
                # 세션에 피드백 추가
                session_data.add_feedback(answer_request.question_id, feedback_data)
                
                feedback = {
                    "score": fallback_score,
                    "message": feedback_data.message,
                    "feedback_type": feedback_data.feedback_type.value,
                    "details": feedback_data.details,
                    "suggestions": feedback_data.suggestions
                }
                print(f"[INFO] Fallback 분석 완료: 점수 {fallback_score}")
            else:
                # 추가 답변에 대한 간단한 fallback 응답 (점수 없음)
                feedback = {
                    "message": f"'{answer_request.answer}'에 대해 답변드리겠습니다. 추가적인 설명이나 질문이 있으시면 언제든 말씀해주세요.",
                    "is_conversation": True,
                    "feedback_type": "conversation"
                }
                print(f"[INFO] 추가 답변에 대한 fallback 응답 생성 완료")
    
    # 첫 번째 답변인 경우에만 다음 질문으로 이동
    if is_first_answer:
        session_data.current_question_index += 1
        
        # 모든 질문 완료 확인
        if session_data.current_question_index >= len(session_data.question_ids):
            session_data.complete_interview()
    
    # 세션 업데이트
    session_manager.update_session(interview_id, session_data)
    
    # Legacy 호환성 유지
    if interview_id in interview_cache:
        legacy_session = interview_cache[interview_id]
        legacy_session.current_question_index = session_data.current_question_index
        legacy_session.status = session_data.status.value
        interview_cache[interview_id] = legacy_session
        
        # Legacy 답변 저장
        response_key = f"{interview_id}_responses"
        if response_key not in interview_cache:
            interview_cache[response_key] = []
        
        response = QuestionResponse(
            question_id=answer_request.question_id,
            question_text=current_question.question if current_question else "",
            user_answer=answer_request.answer,
            response_time=answer_request.time_taken
        )
        interview_cache[response_key].append(response)
        
        # Legacy 피드백 저장
        if feedback:
            feedback_key = f"{interview_id}_feedback"
            if feedback_key not in interview_cache:
                interview_cache[feedback_key] = []
            interview_cache[feedback_key].append(feedback)
    
    return {
        "success": True,
        "message": "답변이 성공적으로 제출되었습니다.",
        "data": {
            "next_question_index": session_data.current_question_index,
            "is_completed": session_data.is_completed(),
            "total_questions": len(session_data.question_ids),
            "feedback": feedback,  # 답변 분석 결과 추가
            "progress": session_data.calculate_progress()
        }
    }


@router.post("/pause/{interview_id}")
async def pause_interview(interview_id: str):
    """면접 일시정지"""
    try:
        # UUID 검증
        uuid.UUID(interview_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="올바르지 않은 면접 ID 형식입니다.")
    
    if interview_id not in interview_cache:
        raise HTTPException(status_code=404, detail="면접 세션을 찾을 수 없습니다.")
    
    session = interview_cache[interview_id]
    
    if session.status != "active":
        raise HTTPException(status_code=400, detail="활성화된 면접만 일시정지할 수 있습니다.")
    
    session.status = "paused"
    interview_cache[interview_id] = session
    
    return {
        "success": True,
        "message": "면접이 일시정지되었습니다.",
        "data": {
            "status": "paused"
        }
    }


@router.post("/resume/{interview_id}")
async def resume_interview(interview_id: str):
    """면접 재개"""
    try:
        # UUID 검증
        uuid.UUID(interview_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="올바르지 않은 면접 ID 형식입니다.")
    
    if interview_id not in interview_cache:
        raise HTTPException(status_code=404, detail="면접 세션을 찾을 수 없습니다.")
    
    session = interview_cache[interview_id]
    
    if session.status != "paused":
        raise HTTPException(status_code=400, detail="일시정지된 면접만 재개할 수 있습니다.")
    
    session.status = "active"
    interview_cache[interview_id] = session
    
    return {
        "success": True,
        "message": "면접이 재개되었습니다.",
        "data": {
            "status": "active"
        }
    }


@router.post("/{interview_id}/finish")
async def finish_interview(interview_id: str):
    """면접 완료"""
    try:
        # UUID 검증
        uuid.UUID(interview_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="올바르지 않은 면접 ID 형식입니다.")
    
    # 세션 관리자에서 먼저 확인
    if session_manager.has_session(interview_id):
        session = session_manager.get_session(interview_id)
        session.set_status(InterviewStatus.COMPLETED)
        
        return {
            "success": True,
            "message": "면접이 완료되었습니다.",
            "interview_id": interview_id,
            "status": "completed"
        }
    
    # Legacy 캐시에서 확인
    if interview_id in interview_cache:
        return await complete_interview(interview_id)
    
    # 세션이 존재하지 않는 경우 - 404 대신 일반적인 완료 응답 반환
    return {
        "success": True,
        "message": "면접이 이미 완료되었거나 세션을 찾을 수 없습니다.",
        "interview_id": interview_id,
        "status": "completed",
        "note": "Session not found but treating as completed"
    }


@router.post("/complete/{interview_id}")
async def complete_interview(interview_id: str):
    """면접 완료"""
    try:
        # UUID 검증
        uuid.UUID(interview_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="올바르지 않은 면접 ID 형식입니다.")
    
    if interview_id not in interview_cache:
        raise HTTPException(status_code=404, detail="면접 세션을 찾을 수 없습니다.")
    
    session = interview_cache[interview_id]
    session.status = "completed"
    interview_cache[interview_id] = session
    
    # 결과 계산
    response_key = f"{interview_id}_responses"
    responses = interview_cache.get(response_key, [])
    
    total_time = int((datetime.utcnow() - session.started_at).total_seconds())
    average_response_time = sum(r.response_time for r in responses) / len(responses) if responses else 0
    
    result = InterviewResult(
        interview_id=interview_id,
        total_questions=len(session.question_ids),
        answered_questions=len(responses),
        total_time=total_time,
        average_confidence=85.0,  # 임시값
        status="completed",
        completed_at=datetime.utcnow()
    )
    
    return {
        "success": True,
        "message": "면접이 완료되었습니다.",
        "data": {
            "result": result.dict(),
            "summary": {
                "completion_rate": round((len(responses) / len(session.question_ids)) * 100, 1),
                "average_response_time": round(average_response_time, 1),
                "total_duration": f"{total_time // 60}분 {total_time % 60}초"
            }
        }
    }


@router.get("/result/{interview_id}")
async def get_interview_result(interview_id: str):
    """면접 결과 조회"""
    try:
        # UUID 검증
        uuid.UUID(interview_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="올바르지 않은 면접 ID 형식입니다.")
    
    if interview_id not in interview_cache:
        raise HTTPException(status_code=404, detail="면접 세션을 찾을 수 없습니다.")
    
    session = interview_cache[interview_id]
    response_key = f"{interview_id}_responses"
    responses = interview_cache.get(response_key, [])
    
    if session.status != "completed":
        raise HTTPException(status_code=400, detail="완료된 면접만 결과를 조회할 수 있습니다.")
    
    total_time = int((datetime.utcnow() - session.started_at).total_seconds())
    
    return {
        "success": True,
        "data": {
            "interview_id": interview_id,
            "analysis_id": session.analysis_id,
            "repo_url": session.repo_url,
            "status": session.status,
            "started_at": session.started_at.isoformat(),
            "total_questions": len(session.question_ids),
            "answered_questions": len(responses),
            "completion_rate": round((len(responses) / len(session.question_ids)) * 100, 1),
            "total_time": total_time,
            "responses": [r.dict() for r in responses]
        }
    }


@router.get("/history")
async def get_interview_history(skip: int = 0, limit: int = 10):
    """면접 히스토리 조회"""
    interviews = []
    
    for interview_id, session in interview_cache.items():
        if isinstance(session, InterviewSession):
            response_key = f"{interview_id}_responses"
            responses = interview_cache.get(response_key, [])
            
            interviews.append({
                "interview_id": interview_id,
                "analysis_id": session.analysis_id,
                "repo_url": session.repo_url,
                "status": session.status,
                "interview_type": session.interview_type,
                "difficulty_level": session.difficulty_level,
                "started_at": session.started_at.isoformat(),
                "total_questions": len(session.question_ids),
                "answered_questions": len(responses),
                "completion_rate": round((len(responses) / len(session.question_ids)) * 100, 1) if session.question_ids else 0
            })
    
    # 날짜순 정렬
    interviews.sort(key=lambda x: x["started_at"], reverse=True)
    
    return {
        "success": True,
        "data": interviews[skip:skip + limit],
        "total": len(interviews)
    }


def _get_category_specific_suggestions(category: str) -> List[str]:
    """질문 카테고리별 맞춤 제안사항 반환"""
    category_suggestions = {
        "technical": [
            "해당 기술의 내부 동작 원리 설명하기",
            "관련 기술과의 차이점이나 비교 분석하기"
        ],
        "tech_stack": [
            "실제 프로젝트에서 사용한 경험이나 설정 방법 공유하기",
            "다른 스택과의 장단점 비교하기"
        ],
        "architecture": [
            "시스템 설계 시 고려한 요소들 설명하기",
            "확장성이나 성능 측면에서의 고려사항 언급하기"
        ],
        "algorithm": [
            "시간 복잡도와 공간 복잡도 분석하기",
            "다른 알고리즘과의 성능 비교하기"
        ],
        "database": [
            "데이터베이스 설계 시 고려사항 설명하기",
            "성능 최적화나 인덱싱 전략 언급하기"
        ],
        "frontend": [
            "사용자 경험(UX) 관점에서의 고려사항 설명하기",
            "브라우저 호환성이나 성능 최적화 방법 언급하기"
        ],
        "backend": [
            "서버 아키텍처나 API 설계 원칙 설명하기",
            "보안이나 성능 최적화 측면에서의 고려사항 언급하기"
        ],
        "devops": [
            "CI/CD 파이프라인 구성이나 배포 전략 설명하기",
            "모니터링이나 운영 관점에서의 고려사항 언급하기"
        ],
        "testing": [
            "테스트 전략이나 커버리지 향상 방법 설명하기",
            "다양한 테스트 종류의 적용 사례 언급하기"
        ],
        "security": [
            "보안 위협과 대응 방안 구체적으로 설명하기",
            "실제 보안 적용 경험이나 사례 공유하기"
        ]
    }
    
    return category_suggestions.get(category.lower(), [
        "관련 기술의 최신 동향이나 업계 표준 언급하기",
        "실무에서 마주한 도전과제와 해결 방법 공유하기"
    ])


@router.delete("/session/{interview_id}")
async def delete_interview_session(interview_id: str):
    """면접 세션 삭제"""
    try:
        # UUID 검증
        uuid.UUID(interview_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="올바르지 않은 면접 ID 형식입니다.")
    
    if interview_id not in interview_cache:
        raise HTTPException(status_code=404, detail="면접 세션을 찾을 수 없습니다.")
    
    # 세션과 응답 데이터 모두 삭제
    del interview_cache[interview_id]
    response_key = f"{interview_id}_responses"
    if response_key in interview_cache:
        del interview_cache[response_key]
    
    return {
        "success": True,
        "message": "면접 세션이 삭제되었습니다."
    }


@router.get("/session/{interview_id}/questions")
async def get_interview_questions(interview_id: str):
    """면접 질문 목록 조회"""
    try:
        # UUID 검증
        uuid.UUID(interview_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="올바르지 않은 면접 ID 형식입니다.")
    
    if interview_id not in interview_cache:
        raise HTTPException(status_code=404, detail="면접 세션을 찾을 수 없습니다.")
    
    session = interview_cache[interview_id]
    if not isinstance(session, InterviewSession):
        raise HTTPException(status_code=404, detail="잘못된 면접 세션입니다.")
    
    # 질문 캐시에서 실제 질문 데이터 가져오기
    from app.api.questions import question_cache
    
    questions = []
    
    # 분석 ID로 질문 캐시에서 질문 조회
    if session.analysis_id in question_cache:
        cache_data = question_cache[session.analysis_id]
        cached_questions = cache_data.parsed_questions
        
        # 질문 ID 순서에 맞게 정렬
        question_id_to_data = {q.id: q for q in cached_questions}
        
        for question_id in session.question_ids:
            if question_id in question_id_to_data:
                question_data = question_id_to_data[question_id]
                questions.append({
                    "id": question_data.id,
                    "question": question_data.question,
                    "category": question_data.type,  # 프론트엔드에서 category로 사용
                    "difficulty": question_data.difficulty,
                    "context": question_data.context,
                    "technology": question_data.technology,
                    "time_estimate": question_data.time_estimate
                })
            else:
                # 캐시에 없는 질문 ID의 경우 기본 질문 생성
                questions.append({
                    "id": question_id,
                    "question": f"질문 {len(questions)+1}: 이 프로젝트에서 사용된 주요 기술 스택에 대해 설명해주세요.",
                    "category": "technical",
                    "difficulty": session.difficulty_level,
                    "context": f"{session.repo_url} 저장소를 기반으로 한 질문입니다.",
                    "technology": "General",
                    "time_estimate": "5분"
                })
    else:
        # 질문 캐시에 없는 경우 기본 질문들 생성
        for i, question_id in enumerate(session.question_ids):
            questions.append({
                "id": question_id,
                "question": f"질문 {i+1}: 이 프로젝트에서 사용된 주요 기술 스택에 대해 설명해주세요.",
                "category": "technical",
                "difficulty": session.difficulty_level,
                "context": f"{session.repo_url} 저장소를 기반으로 한 질문입니다.",
                "technology": "General",
                "time_estimate": "5분"
            })
    
    return {
        "success": True,
        "data": {
            "interview_id": interview_id,
            "questions": questions,
            "current_question_index": session.current_question_index,
            "status": session.status
        }
    }


@router.post("/conversation")
async def handle_conversation(request: ConversationRequest):
    """대화 모드 - 질문에 대한 AI 응답"""
    interview_id = request.interview_id
    
    try:
        # UUID 검증
        uuid.UUID(interview_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="올바르지 않은 면접 ID 형식입니다.")
    
    # 새로운 세션 관리자에서 세션 가져오기
    session_data = session_manager.get_session(interview_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="면접 세션을 찾을 수 없습니다.")
    
    # 질문 정보 가져오기
    from app.api.questions import question_cache
    current_question = None
    
    if session_data.analysis_id in question_cache:
        cache_data = question_cache[session.analysis_id]
        cached_questions = cache_data.parsed_questions
        question_id_to_data = {q.id: q for q in cached_questions}
        
        if request.question_id in question_id_to_data:
            current_question = question_id_to_data[request.question_id]
    
    if not current_question:
        raise HTTPException(status_code=404, detail="질문을 찾을 수 없습니다.")
    
    # AI를 사용한 대화 응답 생성
    try:
        from app.services.answer_analyzer import answer_analyzer
        
        # 대화용 프롬프트 생성
        conversation_prompt = f"""당신은 경험이 풍부하면서도 친근한 기술면접관입니다. 면접자와 자연스러운 대화를 나누고 있습니다.

**상황**: 기술면접 중 추가 질문 시간
**면접 질문**: {current_question.question}
**면접자의 원래 답변**: {request.original_answer}
**면접자의 추가 질문**: {request.conversation_question}

면접자의 추가 질문에 대해 다음과 같이 응답해주세요:

**응답 방식**:
- 면접관 톤으로 친근하지만 전문적으로 답변
- "좋은 질문이네요!", "그 부분이 궁금하셨군요" 등 자연스러운 반응
- 구체적인 예시와 코드를 포함하여 설명
- 실무 경험을 바탕으로 한 팁 제공
- 면접자의 수준에 맞춘 설명

**구성**:
1. 질문에 대한 공감/인정 (1문장)
2. 핵심 설명 (2-3문단)
3. 실무 팁이나 추가 학습 방향 (1문단)

**톤**: 격려하면서도 교육적인, 실제 면접관 같은 말투

답변 길이: 3-4문단, 자연스러운 대화체"""

        # AI 서비스를 통해 응답 생성
        from app.core.ai_service import ai_service, AIProvider
        
        ai_response = await ai_service.generate_analysis(
            prompt=conversation_prompt,
            provider=AIProvider.GEMINI_FLASH
        )
        
        conversation_response = ai_response["content"]
        
        # 대화 기록 저장
        conversation_key = f"{interview_id}_conversations"
        if conversation_key not in interview_cache:
            interview_cache[conversation_key] = []
        
        interview_cache[conversation_key].append({
            "question_id": request.question_id,
            "original_answer": request.original_answer,
            "user_question": request.conversation_question,
            "ai_response": conversation_response,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        return {
            "success": True,
            "message": "대화 응답이 생성되었습니다.",
            "data": {
                "response": conversation_response,
                "question_context": current_question.question,
                "original_answer": request.original_answer
            }
        }
        
    except Exception as e:
        # AI 실패 시 기본 응답
        fallback_response = f"""안녕하세요! "{request.conversation_question}"에 대해 답변드리겠습니다.

원래 답변 "{request.original_answer}"에 대한 추가 설명이 필요하시군요.

이 질문은 "{current_question.question}"에 관한 것으로, 더 구체적인 설명이나 예시를 원하신다면 다음과 같은 방향으로 학습해보시기 바랍니다:

1. 공식 문서나 튜토리얼을 참고하여 기본 개념을 더 확실히 익히세요
2. 실제 코드 예시를 작성해보며 실습하세요  
3. 관련 기술의 장단점과 사용 사례를 조사해보세요

더 궁금한 점이 있으시면 언제든지 질문해주세요!"""

        return {
            "success": True,
            "message": "기본 응답이 생성되었습니다.",
            "data": {
                "response": fallback_response,
                "question_context": current_question.question,
                "original_answer": request.original_answer
            }
        }


@router.get("/session/{interview_id}/data")
async def get_session_data(interview_id: str):
    """세션 데이터 상세 조회 (답변 및 피드백 포함)"""
    try:
        # UUID 검증
        uuid.UUID(interview_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="올바르지 않은 면접 ID 형식입니다.")
    
    session_data = session_manager.get_session(interview_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    
    return {
        "success": True,
        "data": {
            "session_info": session_data.to_summary(),
            "answers": [
                {
                    "question_id": answer.question_id,
                    "question_text": answer.question_text,
                    "user_answer": answer.user_answer,
                    "response_time": answer.response_time,
                    "submitted_at": answer.submitted_at.isoformat(),
                    "feedback": {
                        "score": answer.feedback.score,
                        "message": answer.feedback.message,
                        "feedback_type": answer.feedback.feedback_type.value,
                        "details": answer.feedback.details,
                        "suggestions": answer.feedback.suggestions,
                        "created_at": answer.feedback.created_at.isoformat()
                    } if answer.feedback else None
                }
                for answer in session_data.answers
            ],
            "conversations": [
                {
                    "id": msg.id,
                    "type": msg.type.value,
                    "content": msg.content,
                    "question_id": msg.question_id,
                    "timestamp": msg.timestamp.isoformat(),
                    "metadata": msg.metadata
                }
                for msg in session_data.conversations
            ],
            "progress": session_data.calculate_progress(),
            "statistics": {
                "total_answers": len(session_data.answers),
                "total_conversations": len(session_data.conversations),
                "average_score": session_data.calculate_average_score(),
                "average_response_time": sum(a.response_time for a in session_data.answers) / len(session_data.answers) if session_data.answers else 0
            }
        }
    }


@router.get("/sessions")
async def list_sessions(limit: int = 10, offset: int = 0):
    """세션 목록 조회"""
    sessions = session_manager.list_sessions(limit=limit, offset=offset)
    total_count = session_manager.get_session_count()
    
    return {
        "success": True,
        "data": {
            "sessions": sessions,
            "pagination": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total_count
            }
        }
    }


@router.post("/sessions/cleanup")
async def cleanup_expired_sessions(max_age_hours: int = 24):
    """만료된 세션 정리"""
    cleaned_count = session_manager.cleanup_expired_sessions(max_age_hours)
    
    return {
        "success": True,
        "message": f"{cleaned_count}개의 만료된 세션이 정리되었습니다.",
        "data": {
            "cleaned_sessions": cleaned_count,
            "remaining_sessions": session_manager.get_session_count()
        }
    }


@router.get("/debug/cache")
async def debug_interview_cache():
    """면접 캐시 상태 확인 (디버깅용)"""
    from app.api.questions import question_cache
    
    return {
        "legacy_cache_size": len(interview_cache),
        "new_session_manager_size": session_manager.get_session_count(),
        "question_cache_size": len(question_cache),
        "sessions": [
            {
                "id": key,
                "type": type(value).__name__,
                "analysis_id": value.analysis_id if hasattr(value, 'analysis_id') else None,
                "question_ids": value.question_ids if hasattr(value, 'question_ids') else None,
                "status": value.status if hasattr(value, 'status') else None,
                "data": value.dict() if hasattr(value, 'dict') else str(value)[:100]
            }
            for key, value in interview_cache.items()
        ],
        "new_sessions": session_manager.list_sessions(limit=50),
        "question_cache_keys": list(question_cache.keys())
    }