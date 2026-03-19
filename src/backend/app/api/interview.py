"""
Interview API Router - Database-based Version

실제 데이터베이스를 사용한 영구 면접 세션 관리 API
"""

import uuid
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, HttpUrl
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.interview_repository import InterviewRepository
from app.models.interview import InterviewSession, InterviewQuestion, InterviewAnswer
from app.agents.mock_interview_agent import MockInterviewAgent


router = APIRouter()


class InterviewStartRequest(BaseModel):
    """면접 시작 요청"""
    repo_url: HttpUrl
    analysis_id: str
    question_ids: List[str]
    interview_type: str = "technical"
    difficulty_level: str = "medium"


class AnswerSubmitRequest(BaseModel):
    """답변 제출 요청"""
    interview_id: str
    question_id: str
    answer: str
    time_taken: int = 0


class ConversationRequest(BaseModel):
    """대화 요청"""
    interview_id: str
    question_id: str
    original_answer: str
    conversation_question: str


@router.post("/start")
async def start_interview(request: InterviewStartRequest, db: Session = Depends(get_db)):
    """새 면접 세션 시작"""
    try:
        # 질문 ID 유효성 검증
        if not request.question_ids:
            raise HTTPException(status_code=400, detail="질문 ID가 제공되지 않았습니다.")
        
        # 질문 캐시에서 질문 데이터 확인 (active variant-aware cache 사용)
        from app.api.questions import get_question_cache_entry
        cache_data = get_question_cache_entry(request.analysis_id)
        if not cache_data:
            raise HTTPException(
                status_code=400, 
                detail="해당 분석 ID에 대한 질문이 없습니다. 먼저 질문을 생성해주세요."
            )

        cached_questions = cache_data.parsed_questions
        available_question_ids = {q.id for q in cached_questions}
        
        # 요청된 질문 ID가 모두 캐시에 있는지 확인
        missing_question_ids = set(request.question_ids) - available_question_ids
        if missing_question_ids:
            raise HTTPException(
                status_code=400, 
                detail=f"다음 질문 ID를 찾을 수 없습니다: {list(missing_question_ids)}"
            )
        
        # 분석 ID 검증 및 생성 (데이터베이스에 없으면 생성)
        from app.models.repository import RepositoryAnalysis
        analysis = db.query(RepositoryAnalysis).filter(
            RepositoryAnalysis.id == uuid.UUID(request.analysis_id)
        ).first()
        
        if not analysis:
            # 분석 데이터가 데이터베이스에 없으면 임시로 생성
            analysis = RepositoryAnalysis(
                id=uuid.UUID(request.analysis_id),
                user_id=uuid.uuid4(),  # 임시 사용자 ID
                repository_url=str(request.repo_url),
                repository_name=str(request.repo_url).split('/')[-1],
                primary_language="Unknown",
                tech_stack={},
                file_count=0,
                complexity_score=0.0,
                analysis_metadata={"temporary": True, "source": "question_cache"},
                status="completed"
            )
            db.add(analysis)
            db.commit()
            db.refresh(analysis)
        
        # InterviewRepository를 사용하여 세션 생성
        repo = InterviewRepository(db)
        session = repo.create_session({
            'analysis_id': uuid.UUID(request.analysis_id),
            'interview_type': request.interview_type,
            'difficulty_level': request.difficulty_level
        })
        
        # 선택된 질문들을 데이터베이스에 저장 (필요시)
        question_id_mapping = {}  # 원본 ID -> UUID 매핑
        
        for question_data in cached_questions:
            if question_data.id in request.question_ids:
                # 질문 ID가 UUID 형식인지 확인
                try:
                    question_uuid = uuid.UUID(question_data.id)
                    # UUID 형식이면 기존 질문 확인
                    existing_question = db.query(InterviewQuestion).filter(
                        InterviewQuestion.id == question_uuid
                    ).first()
                except ValueError:
                    # UUID 형식이 아니면 새 UUID 생성
                    question_uuid = uuid.uuid4()
                    existing_question = None
                
                question_id_mapping[question_data.id] = question_uuid
                
                if not existing_question:
                    # 새 질문 저장
                    db_question = InterviewQuestion(
                        id=question_uuid,
                        analysis_id=uuid.UUID(request.analysis_id),
                        category=question_data.type,  # QuestionResponse uses 'type' not 'category'
                        difficulty=question_data.difficulty,
                        question_text=question_data.question,
                        context={
                            "original_data": question_data.dict(),
                            "original_id": question_data.id,
                            "experiment": {
                                "experiment_id": cache_data.experiment_id,
                                "selector_variant": cache_data.selector_variant,
                                "generator_variant": cache_data.generator_variant,
                                "provider_id": cache_data.provider_id,
                                "applied_profile": cache_data.applied_profile,
                                "analysis_profile_status": cache_data.analysis_profile_status,
                                "best_case_guaranteed": cache_data.best_case_guaranteed,
                            },
                        }
                    )
                    db.add(db_question)
        
        db.commit()
        
        return {
            "success": True,
            "message": "면접이 성공적으로 시작되었습니다.",
            "data": {
                "interview_id": str(session.id),
                "analysis_id": request.analysis_id,
                "interview_type": session.interview_type,
                "difficulty": session.difficulty,
                "status": session.status,
                "started_at": session.started_at.isoformat(),
                "question_count": len(request.question_ids)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"면접 시작에 실패했습니다: {str(e)}")


@router.get("/session/{interview_id}")
async def get_interview_session(interview_id: str, db: Session = Depends(get_db)):
    """면접 세션 정보 조회"""
    try:
        # UUID 정규화 후 검증
        normalized_interview_id = normalize_uuid_string(interview_id)
        session_uuid = uuid.UUID(normalized_interview_id)
        print(f"[DEBUG] 면접 세션 조회 - UUID 정규화: '{interview_id}' → '{normalized_interview_id}'")
    except ValueError as e:
        print(f"[ERROR] 면접 ID UUID 변환 실패: {str(e)}")
        raise HTTPException(status_code=400, detail=f"올바르지 않은 면접 ID 형식입니다: {str(e)}")
    
    repo = InterviewRepository(db)
    session_data = repo.get_session_with_details(session_uuid)
    
    if not session_data:
        raise HTTPException(status_code=404, detail="면접 세션을 찾을 수 없습니다.")
    
    session = session_data['session']
    progress = session_data['progress']
    
    return {
        "success": True,
        "data": {
            "interview_id": str(session.id),
            "analysis_id": str(session.analysis_id),
            "interview_type": session.interview_type,
            "difficulty_level": session.difficulty,
            "status": session.status,
            "started_at": session.started_at.isoformat(),
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
            "overall_score": float(session.overall_score) if session.overall_score else None,
            "progress": progress
        }
    }


@router.get("/session/{interview_id}/questions")
async def get_interview_questions(interview_id: str, db: Session = Depends(get_db)):
    """면접 질문 목록 조회"""
    try:
        normalized_interview_id = normalize_uuid_string(interview_id)
        session_uuid = uuid.UUID(normalized_interview_id)
        print(f"[DEBUG] 면접 질문 조회 - UUID 정규화: '{interview_id}' → '{normalized_interview_id}'")
    except ValueError as e:
        print(f"[ERROR] 면접 ID UUID 변환 실패: {str(e)}")
        raise HTTPException(status_code=400, detail=f"올바르지 않은 면접 ID 형식입니다: {str(e)}")
    
    repo = InterviewRepository(db)
    session = repo.get_session(session_uuid)
    
    if not session:
        raise HTTPException(status_code=404, detail="면접 세션을 찾을 수 없습니다.")
    
    # 해당 분석의 모든 질문 조회
    questions = db.query(InterviewQuestion).filter(
        InterviewQuestion.analysis_id == session.analysis_id
    ).all()
    
    # 답변된 질문 수 확인
    answered_count = db.query(InterviewAnswer).filter(
        InterviewAnswer.session_id == session_uuid
    ).count()
    
    questions_data = []
    for question in questions:
        questions_data.append({
            "id": str(question.id),
            "question": question.question_text,
            "category": question.category,
            "difficulty": question.difficulty,
            "context": question.context.get("original_data") if question.context else None
        })
    
    return {
        "success": True,
        "data": {
            "questions": questions_data,
            "current_question_index": answered_count,
            "total_questions": len(questions_data)
        }
    }


@router.get("/session/{interview_id}/data")
async def get_session_data(interview_id: str, db: Session = Depends(get_db)):
    """세션 데이터 상세 조회 (답변 및 피드백 포함)"""
    try:
        normalized_interview_id = normalize_uuid_string(interview_id)
        session_uuid = uuid.UUID(normalized_interview_id)
        print(f"[DEBUG] 면접 질문 조회 - UUID 정규화: '{interview_id}' → '{normalized_interview_id}'")
    except ValueError as e:
        print(f"[ERROR] 면접 ID UUID 변환 실패: {str(e)}")
        raise HTTPException(status_code=400, detail=f"올바르지 않은 면접 ID 형식입니다: {str(e)}")
    
    repo = InterviewRepository(db)
    session_data = repo.get_session_with_details(session_uuid)
    
    if not session_data:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    
    # 답변 데이터 포맷팅
    answers_data = []
    for answer in session_data['answers']:
        answers_data.append({
            "question_id": str(answer.question_id),
            "user_answer": answer.user_answer,
            "submitted_at": answer.submitted_at.isoformat(),
            "feedback": {
                "score": float(answer.feedback_score) if answer.feedback_score else None,
                "message": answer.feedback_message,
                "details": answer.feedback_details,
                "created_at": answer.submitted_at.isoformat()
            } if answer.feedback_score else None
        })
    
    # 대화 데이터 포맷팅
    conversations_data = []
    for conv in session_data['conversations']:
        conversations_data.append({
            "id": str(conv.id),
            "question_id": str(conv.question_id) if conv.question_id else None,
            "type": conv.speaker,
            "content": conv.message_content,
            "timestamp": conv.created_at.isoformat()
        })
    
    return {
        "success": True,
        "data": {
            "answers": answers_data,
            "conversations": conversations_data,
            "progress": session_data['progress']
        }
    }


def normalize_uuid_string(uuid_str: str) -> str:
    """UUID 문자열을 표준 형식으로 변환 (하이픈 제거/추가 자동 처리)"""
    if not uuid_str:
        raise ValueError("UUID 문자열이 비어있습니다.")
    
    # 하이픈 제거
    cleaned = uuid_str.replace('-', '')
    
    # 길이 검증
    if len(cleaned) != 32:
        raise ValueError(f"UUID 길이가 올바르지 않습니다: {len(cleaned)} (32 필요)")
    
    # 표준 UUID 형식으로 변환
    return f"{cleaned[:8]}-{cleaned[8:12]}-{cleaned[12:16]}-{cleaned[16:20]}-{cleaned[20:]}"


@router.post("/answer")
async def submit_answer(request: AnswerSubmitRequest, db: Session = Depends(get_db)):
    """답변 제출"""
    print(f"[DEBUG] 원본 요청 데이터:")
    print(f"  - interview_id: '{request.interview_id}'")
    print(f"  - question_id: '{request.question_id}'")
    print(f"  - answer: '{request.answer[:50]}...'")
    
    try:
        # UUID 정규화 후 변환
        normalized_interview_id = normalize_uuid_string(request.interview_id)
        normalized_question_id = normalize_uuid_string(request.question_id)
        
        print(f"[DEBUG] 정규화된 UUID:")
        print(f"  - interview_id: '{normalized_interview_id}'")
        print(f"  - question_id: '{normalized_question_id}'")
        
        session_uuid = uuid.UUID(normalized_interview_id)
        question_uuid = uuid.UUID(normalized_question_id)
        
        print(f"[DEBUG] UUID 변환 성공:")
        print(f"  - session_uuid: {session_uuid}")
        print(f"  - question_uuid: {question_uuid}")
        
    except ValueError as e:
        print(f"[ERROR] UUID 변환 실패: {str(e)}")
        raise HTTPException(status_code=400, detail=f"올바르지 않은 ID 형식입니다: {str(e)}")
    
    repo = InterviewRepository(db)
    session = repo.get_session(session_uuid)
    
    if not session:
        raise HTTPException(status_code=404, detail="면접 세션을 찾을 수 없습니다.")
    
    if session.status != "active":
        raise HTTPException(status_code=400, detail="활성화된 면접 세션에만 답변할 수 있습니다.")
    
    try:
        # 첫 번째 답변인지 확인 (기존 답변 존재 여부로 판단)
        existing_answer = db.query(InterviewAnswer).filter(
            InterviewAnswer.session_id == session_uuid,
            InterviewAnswer.question_id == question_uuid
        ).first()
        is_first_answer = existing_answer is None
        
        print(f"[DEBUG] 질문 {question_uuid}: 첫 번째 답변? {is_first_answer}")
        print(f"[DEBUG] 기존 답변 존재: {existing_answer is not None}")
        
        # Mock Interview Agent를 사용하여 피드백 생성
        interview_agent = MockInterviewAgent()
        
        # 질문 정보 조회
        question = db.query(InterviewQuestion).filter(
            InterviewQuestion.id == question_uuid
        ).first()
        
        if not question:
            raise HTTPException(status_code=404, detail="질문을 찾을 수 없습니다.")
        
        # 피드백 생성 (답변 횟수 정보 포함)
        feedback_result = await interview_agent.evaluate_answer(
            question=question.question_text,
            answer=request.answer,
            is_first_answer=is_first_answer,  # 답변 횟수 정보 전달
            context={
                "category": question.category,
                "difficulty": question.difficulty,
                "expected_points": question.expected_points or []
            }
        )
        
        print(f"[FEEDBACK_RESULT] 피드백 생성 결과:", feedback_result)
        if feedback_result and feedback_result.get("success"):
            feedback_data = feedback_result.get("data", {})
            print(f"[FEEDBACK_DATA] 피드백 데이터:")
            print(f"  - overall_score: {feedback_data.get('overall_score', 'N/A')}")
            print(f"  - feedback: {feedback_data.get('feedback', 'N/A')[:50]}...")
            print(f"  - suggestions count: {len(feedback_data.get('suggestions', []))}")
        
        # 답변 및 피드백 저장
        answer_data = {
            "answer": request.answer,
            "time_taken": request.time_taken,
            "feedback": feedback_result if feedback_result.get("success") else None
        }
        
        saved_answer = repo.save_answer(session_uuid, question_uuid, answer_data)
        
        # 다음 질문 확인
        total_questions = db.query(InterviewQuestion).filter(
            InterviewQuestion.analysis_id == session.analysis_id
        ).count()
        
        answered_questions = db.query(InterviewAnswer).filter(
            InterviewAnswer.session_id == session_uuid
        ).count()
        
        is_completed = answered_questions >= total_questions
        
        if is_completed:
            repo.update_session_status(session_uuid, "completed")
        
        return {
            "success": True,
            "message": "답변이 성공적으로 제출되었습니다.",
            "data": {
                "answer_id": str(saved_answer.id),
                "feedback": feedback_result.get("data") if feedback_result and feedback_result.get("success") else None,
                "is_completed": is_completed,
                "next_question_index": answered_questions if not is_completed else None
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"답변 처리에 실패했습니다: {str(e)}")


@router.post("/conversation")
async def handle_conversation(request: ConversationRequest, db: Session = Depends(get_db)):
    """대화 처리"""
    try:
        normalized_interview_id = normalize_uuid_string(request.interview_id)
        normalized_question_id = normalize_uuid_string(request.question_id)
        session_uuid = uuid.UUID(normalized_interview_id)
        question_uuid = uuid.UUID(normalized_question_id)
        print(f"[DEBUG] 대화 처리 - UUID 정규화: '{request.interview_id}' → '{normalized_interview_id}', '{request.question_id}' → '{normalized_question_id}'")
    except ValueError as e:
        print(f"[ERROR] 대화 처리 UUID 변환 실패: {str(e)}")
        raise HTTPException(status_code=400, detail="올바르지 않은 ID 형식입니다.")
    
    repo = InterviewRepository(db)
    session = repo.get_session(session_uuid)
    
    if not session:
        raise HTTPException(status_code=404, detail="면접 세션을 찾을 수 없습니다.")
    
    try:
        # 사용자 질문 저장
        user_conversation = repo.save_conversation(session_uuid, {
            "question_id": question_uuid,
            "speaker": "user",
            "content": request.conversation_question,
            "metadata": {"original_answer": request.original_answer}
        })
        
        # AI 응답 생성
        interview_agent = MockInterviewAgent()
        ai_response = await interview_agent.handle_follow_up_question(
            original_question="",  # 필요시 DB에서 조회
            original_answer=request.original_answer,
            follow_up_question=request.conversation_question
        )
        
        # AI 응답 저장
        ai_conversation = repo.save_conversation(session_uuid, {
            "question_id": question_uuid,
            "speaker": "ai",
            "content": ai_response.get("response", "죄송합니다. 응답을 생성할 수 없습니다."),
            "metadata": {"response_data": ai_response}
        })
        
        return {
            "success": True,
            "message": "대화가 성공적으로 처리되었습니다.",
            "data": {
                "response": ai_response.get("response", "응답을 생성할 수 없습니다."),
                "conversation_id": str(ai_conversation.id)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"대화 처리에 실패했습니다: {str(e)}")


@router.get("/sessions")
async def list_sessions(limit: int = 10, offset: int = 0, db: Session = Depends(get_db)):
    """세션 목록 조회"""
    sessions = db.query(InterviewSession).order_by(
        InterviewSession.started_at.desc()
    ).offset(offset).limit(limit).all()
    
    total_count = db.query(InterviewSession).count()
    
    sessions_data = []
    for session in sessions:
        sessions_data.append({
            "interview_id": str(session.id),
            "analysis_id": str(session.analysis_id),
            "interview_type": session.interview_type,
            "difficulty": session.difficulty,
            "status": session.status,
            "overall_score": float(session.overall_score) if session.overall_score else None,
            "started_at": session.started_at.isoformat(),
            "ended_at": session.ended_at.isoformat() if session.ended_at else None
        })
    
    return {
        "success": True,
        "data": {
            "sessions": sessions_data,
            "pagination": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + limit) < total_count
            }
        }
    }


@router.get("/sessions/latest")
async def get_latest_session(db: Session = Depends(get_db)):
    """가장 최근 세션 조회"""
    repo = InterviewRepository(db)
    session = repo.get_latest_session()
    
    if not session:
        raise HTTPException(status_code=404, detail="세션이 없습니다.")
    
    return {
        "success": True,
        "data": {
            "interview_id": str(session.id),
            "analysis_id": str(session.analysis_id),
            "status": session.status,
            "started_at": session.started_at.isoformat()
        }
    }


@router.post("/session/{interview_id}/complete")
async def complete_interview(interview_id: str, db: Session = Depends(get_db)):
    """면접 완료 처리"""
    try:
        normalized_interview_id = normalize_uuid_string(interview_id)
        session_uuid = uuid.UUID(normalized_interview_id)
        print(f"[DEBUG] 면접 질문 조회 - UUID 정규화: '{interview_id}' → '{normalized_interview_id}'")
    except ValueError as e:
        print(f"[ERROR] 면접 ID UUID 변환 실패: {str(e)}")
        raise HTTPException(status_code=400, detail=f"올바르지 않은 면접 ID 형식입니다: {str(e)}")
    
    repo = InterviewRepository(db)
    success = repo.update_session_status(session_uuid, "completed")
    
    if not success:
        raise HTTPException(status_code=404, detail="면접 세션을 찾을 수 없습니다.")
    
    return {
        "success": True,
        "message": "면접이 완료되었습니다.",
        "data": {"status": "completed"}
    }


@router.post("/{interview_id}/finish")
async def finish_interview(interview_id: str, db: Session = Depends(get_db)):
    """면접 종료 처리 (프론트엔드 호환성을 위한 별칭)"""
    # complete_interview 함수와 동일한 로직
    try:
        normalized_interview_id = normalize_uuid_string(interview_id)
        session_uuid = uuid.UUID(normalized_interview_id)
        print(f"[DEBUG] 면접 질문 조회 - UUID 정규화: '{interview_id}' → '{normalized_interview_id}'")
    except ValueError as e:
        print(f"[ERROR] 면접 ID UUID 변환 실패: {str(e)}")
        raise HTTPException(status_code=400, detail=f"올바르지 않은 면접 ID 형식입니다: {str(e)}")
    
    repo = InterviewRepository(db)
    success = repo.update_session_status(session_uuid, "completed")
    
    if not success:
        raise HTTPException(status_code=404, detail="면접 세션을 찾을 수 없습니다.")
    
    return {
        "success": True,
        "message": "면접이 종료되었습니다.",
        "data": {"status": "completed"}
    }
