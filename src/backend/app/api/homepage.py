"""
Homepage 초기화 API 엔드포인트 (통합)

기존 config와 ai_settings API를 통합하여 
단일 요청으로 홈페이지 초기화 데이터 제공
"""
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

from app.core.config import settings, check_env_file_exists
from app.api.config import check_keys_required
from app.api.ai_settings import get_available_providers

router = APIRouter(prefix="/api/v1/homepage", tags=["homepage"])


class HomePageInitResponse(BaseModel):
    """홈페이지 초기화 응답 모델"""
    config: Dict[str, Any]
    providers: List[Dict[str, Any]]
    cache_info: Dict[str, Any]


@router.get("/init", response_model=HomePageInitResponse)
async def get_homepage_init_data(
    github_token: Optional[str] = Header(None, alias="x-github-token"),
    google_api_key: Optional[str] = Header(None, alias="x-google-api-key"),
    upstage_api_key: Optional[str] = Header(None, alias="x-upstage-api-key"),
):
    """
    홈페이지 초기화에 필요한 모든 데이터를 단일 요청으로 제공
    
    - 설정 상태 (keys_required 등)
    - AI 제공업체 목록
    - 캐싱 정보
    """
    try:
        # 1. 설정 상태 확인 (기존 로직 재사용)
        config_response = await check_keys_required()
        config_data = {
            "keys_required": config_response.keys_required,
            "use_local_storage": config_response.use_local_storage,
            "missing_keys": config_response.missing_keys
        }
        
        # 2. AI 제공업체 목록 (기존 로직 재사용)
        providers_data = await get_available_providers(
            github_token=github_token,
            google_api_key=google_api_key,
            upstage_api_key=upstage_api_key,
        )
        providers_list = [provider.dict() for provider in providers_data]
        
        # 3. 캐싱 정보
        cache_info = {
            "ttl": 300,  # 5분
            "last_updated": "server",
            "source": "api"
        }
        
        # 4. 응답 생성 (캐싱 헤더 포함)
        response_data = HomePageInitResponse(
            config=config_data,
            providers=providers_list,
            cache_info=cache_info
        )
        
        # 캐싱 헤더 설정
        headers = {
            "Cache-Control": "public, max-age=300",  # 5분 캐시
            "ETag": f'"homepage-{hash(str(response_data.dict()))}"',
            "Vary": "X-GitHub-Token, X-Upstage-API-Key, X-Google-API-Key"
        }
        
        return JSONResponse(
            content=response_data.dict(),
            headers=headers
        )
        
    except Exception as e:
        # 에러 발생 시 최소한의 데이터라도 제공
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Homepage initialization failed: {e}", exc_info=True)
        
        fallback_data = {
            "config": {
                "keys_required": True,
                "use_local_storage": True,
                "missing_keys": {
                    "github_token": True,
                    "upstage_api_key": True,
                    "google_api_key": True,
                }
            },
            "providers": [{
                "id": "upstage-solar-pro3",
                "name": "Upstage Solar Pro3 (기본)",
                "model": settings.upstage_solar_model,
                "status": "available",
                "recommended": True
            }],
            "cache_info": {
                "ttl": 60,
                "last_updated": "fallback",
                "source": "error_fallback",
                "error": str(e)
            }
        }
        
        return JSONResponse(
            content=fallback_data,
            status_code=200,  # 200으로 반환하여 클라이언트에서 처리 가능하도록
            headers={"Cache-Control": "no-cache"}
        )


@router.get("/health")
async def homepage_health_check():
    """홈페이지 관련 서비스 상태 확인"""
    return {
        "status": "healthy",
        "services": {
            "config_api": "ok",
            "ai_providers": "ok",
            "cache": "ok"
        },
        "timestamp": "2025-01-14T06:40:00Z"
    }
