"""
Configuration Settings

환경변수 기반 애플리케이션 설정
"""

import os
from typing import List, Optional
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings
from functools import lru_cache


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _resolve_env_file_name(env_value: Optional[str] = None) -> str:
    env = (env_value or os.getenv("ENV", "development")).strip()
    return f".env.{env}" if env != "development" else ".env.dev"


def resolve_env_file_path(env_value: Optional[str] = None) -> Path:
    """실행 위치와 무관하게 환경 파일 경로를 결정한다."""
    env_file_name = _resolve_env_file_name(env_value)
    candidates = [
        Path.cwd() / env_file_name,
        BACKEND_ROOT / env_file_name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    # 파일이 아직 없을 때도 backend 루트 기준 경로를 기본값으로 반환
    return BACKEND_ROOT / env_file_name


class Settings(BaseSettings):
    """애플리케이션 설정"""
    
    # Environment
    env: str = "development"
    debug: bool = True
    
    # Database
    database_url: str = "sqlite:///./interviews.db"
    redis_url: str = "redis://localhost:6379"
    
    # External APIs
    github_token: Optional[str] = None
    openai_api_key: Optional[str] = None  # Deprecated - Use Gemini instead
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None  # Required for Gemini
    upstage_api_key: Optional[str] = None  # Preferred for Solar Pro3
    
    # LangSmith
    langsmith_api_key: Optional[str] = None
    langsmith_project: str = "techgiterview"
    
    # Vector Database
    chroma_host: str = "localhost"
    chroma_port: int = 8000  # 8001과 충돌 방지를 위해 8000으로 변경
    
    # Security
    secret_key: str = "default_secret_key_for_development"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    token_signing_keys_json: Optional[str] = None
    token_active_kid: str = "default"
    token_issuer: str = "techgiterview"
    token_audience: str = "techgiterview-backend"
    analysis_token_ttl_seconds: int = 3600
    interview_token_ttl_seconds: int = 14400
    ws_query_token_ttl_seconds: int = 90
    
    # CORS
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001,https://tgv.oursophy.com"
    
    def get_allowed_origins(self) -> List[str]:
        """CORS allowed origins 리스트 반환"""
        if isinstance(self.allowed_origins, str):
            return [origin.strip() for origin in self.allowed_origins.split(",")]
        return self.allowed_origins
    
    # GitHub API
    github_api_base_url: str = "https://api.github.com"
    github_rate_limit_per_hour: int = 5000
    
    # Performance
    max_concurrent_requests: int = 10
    request_timeout_seconds: int = 30
    cache_ttl_seconds: int = 3600
    file_selector_display_variant: str = "selector_v2"
    file_selector_shadow_enabled: bool = True
    file_selector_canary_percent: int = 0
    
    class Config:
        env_file = str(resolve_env_file_path())
        case_sensitive = False
        extra = "ignore"


def check_env_file_exists() -> bool:
    """환경 파일이 존재하는지 확인"""
    return resolve_env_file_path().exists()


def update_api_keys(
    github_token: Optional[str] = None,
    google_api_key: Optional[str] = None,
    upstage_api_key: Optional[str] = None,
) -> None:
    """런타임에 API 키 업데이트 및 AI 서비스 재초기화"""
    import logging
    
    logger = logging.getLogger(__name__)
    global settings
    if github_token is not None:
        settings.github_token = github_token
    if google_api_key is not None:
        settings.google_api_key = google_api_key
    if upstage_api_key is not None:
        settings.upstage_api_key = upstage_api_key
    
    # AI 서비스 재초기화
    try:
        from app.core.ai_service import ai_service
        logger.info("Reinitializing AI service with new API keys...")
        ai_service.reinitialize()
        
        # 사용 가능한 모든 프로바이더 로그
        for provider, config in ai_service.available_providers.items():
            logger.info(f"- {provider.value}: {config['model']} ({config['status']})")
            
    except Exception as e:
        logger.error(f"Failed to reinitialize AI service: {e}")
        raise


@lru_cache()
def get_settings() -> Settings:
    """설정 싱글톤 인스턴스 반환"""
    env = os.getenv("ENV", "development")
    env_file_path = resolve_env_file_path(env)
    
    class _Settings(Settings):
        class Config:
            env_file = str(env_file_path) if env_file_path.exists() else None
            case_sensitive = False
            extra = "ignore"
    
    return _Settings()


# 전역 설정 인스턴스
settings = get_settings()
