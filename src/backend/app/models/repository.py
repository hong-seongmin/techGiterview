"""
Repository Analysis Models

저장소 분석 관련 모델
"""

from sqlalchemy import Column, String, DateTime, Integer, Numeric, Text, ForeignKey, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


class RepositoryAnalysis(Base):
    """저장소 분석 결과 모델"""
    
    __tablename__ = "repository_analyses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    repository_url = Column(String(500), nullable=False, index=True)
    repository_name = Column(String(255), nullable=True)
    primary_language = Column(String(100), nullable=True)
    tech_stack = Column(JSON, nullable=True)  # {"python": 0.8, "javascript": 0.2}
    file_count = Column(Integer, nullable=True)
    complexity_score = Column(Numeric(3, 2), nullable=True)  # 0.00 ~ 10.00
    analysis_metadata = Column(JSON, nullable=True)
    status = Column(String(50), default="pending", nullable=False)  # pending, analyzing, completed, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", backref="repository_analyses")
    
    def __repr__(self):
        return f"<RepositoryAnalysis(id={self.id}, repository_name='{self.repository_name}', status='{self.status}')>"


class AnalyzedFile(Base):
    """분석된 파일 정보 모델"""
    
    __tablename__ = "analyzed_files"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("repository_analyses.id"), nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_type = Column(String(50), nullable=True)  # source, config, test, documentation
    language = Column(String(50), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    lines_of_code = Column(Integer, nullable=True)
    complexity_score = Column(Numeric(3, 2), nullable=True)
    importance_score = Column(Numeric(3, 2), nullable=True)  # AI가 계산한 중요도
    content_summary = Column(Text, nullable=True)  # LLM이 생성한 파일 요약
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    analysis = relationship("RepositoryAnalysis", backref="analyzed_files")
    
    def __repr__(self):
        return f"<AnalyzedFile(id={self.id}, file_path='{self.file_path}', importance_score={self.importance_score})>"


class FileSelectionRun(Base):
    """중요 파일 선정 실행 기록"""

    __tablename__ = "file_selection_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("repository_analyses.id"), nullable=False, index=True)
    experiment_id = Column(String(100), nullable=False)
    variant = Column(String(50), nullable=False)
    is_shadow = Column(Integer, nullable=False, default=0)
    selected_file_count = Column(Integer, nullable=False, default=0)
    latency_ms = Column(Integer, nullable=True)
    selected_files = Column(JSON, nullable=False, default=list)
    run_metadata = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    analysis = relationship("RepositoryAnalysis", backref="file_selection_runs")

    def __repr__(self):
        return (
            f"<FileSelectionRun(id={self.id}, analysis_id={self.analysis_id}, "
            f"variant='{self.variant}', shadow={self.is_shadow})>"
        )


class QuestionGenerationRun(Base):
    """질문 생성 실행 기록"""

    __tablename__ = "question_generation_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("repository_analyses.id"), nullable=False, index=True)
    experiment_id = Column(String(100), nullable=False)
    selector_experiment_id = Column(String(100), nullable=True)
    selector_variant = Column(String(50), nullable=False)
    generator_variant = Column(String(50), nullable=False)
    provider = Column(String(50), nullable=True)
    generated_question_count = Column(Integer, nullable=False, default=0)
    parsed_question_count = Column(Integer, nullable=False, default=0)
    latency_ms = Column(Integer, nullable=True)
    questions_payload = Column(JSON, nullable=False, default=dict)
    run_metadata = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    analysis = relationship("RepositoryAnalysis", backref="question_generation_runs")

    def __repr__(self):
        return (
            f"<QuestionGenerationRun(id={self.id}, analysis_id={self.analysis_id}, "
            f"selector_variant='{self.selector_variant}', generator_variant='{self.generator_variant}')>"
        )


class SelectorManualReview(Base):
    """중요 파일 선정 수동 평가 기록"""

    __tablename__ = "selector_manual_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_selection_run_id = Column(UUID(as_uuid=True), ForeignKey("file_selection_runs.id"), nullable=False, index=True)
    iteration_id = Column(String(100), nullable=False, index=True)
    reviewer = Column(String(100), nullable=False)
    passed = Column(Boolean, nullable=False, default=False)
    overall_score = Column(Numeric(4, 2), nullable=False)
    scores_json = Column(JSON, nullable=False, default=dict)
    failure_tags = Column(JSON, nullable=False, default=list)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    file_selection_run = relationship("FileSelectionRun", backref="manual_reviews")

    def __repr__(self):
        return (
            f"<SelectorManualReview(id={self.id}, iteration_id='{self.iteration_id}', "
            f"passed={self.passed}, overall_score={self.overall_score})>"
        )


class QuestionManualReview(Base):
    """질문 세트 수동 평가 기록"""

    __tablename__ = "question_manual_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_generation_run_id = Column(UUID(as_uuid=True), ForeignKey("question_generation_runs.id"), nullable=False, index=True)
    iteration_id = Column(String(100), nullable=False, index=True)
    reviewer = Column(String(100), nullable=False)
    passed = Column(Boolean, nullable=False, default=False)
    overall_score = Column(Numeric(4, 2), nullable=False)
    set_scores_json = Column(JSON, nullable=False, default=dict)
    question_reviews_json = Column(JSON, nullable=False, default=list)
    failure_tags = Column(JSON, nullable=False, default=list)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    question_generation_run = relationship("QuestionGenerationRun", backref="manual_reviews")

    def __repr__(self):
        return (
            f"<QuestionManualReview(id={self.id}, iteration_id='{self.iteration_id}', "
            f"passed={self.passed}, overall_score={self.overall_score})>"
        )
