"""
AI 설정 관련 API 엔드포인트
"""
from fastapi import APIRouter, HTTPException, Header
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from app.core.ai_service import ai_service, AIProvider
from app.core.config import check_env_file_exists, settings

router = APIRouter(prefix="/api/v1/ai", tags=["ai-settings"])


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


def get_effective_providers(api_keys: Dict[str, str]) -> List[Dict[str, Any]]:
    """유효한 AI 제공업체 목록 반환 (헤더 키 고려)"""
    env_exists = check_env_file_exists()
    
    if env_exists:
        # 로컬 환경(.env.dev 있음): 기존 방식 사용
        return ai_service.get_available_providers()
    else:
        # 배포 환경(.env.dev 없음): 헤더의 키를 기반으로 동적 생성
        providers = []
        
        has_upstage_key = bool(api_keys.get("upstage_api_key"))
        has_google_key = bool(api_keys.get("google_api_key"))

        # Upstage 키가 있으면 Solar Pro3 우선 추가
        if has_upstage_key:
            providers.append({
                "id": AIProvider.UPSTAGE_SOLAR.value,
                "name": "Upstage Solar Pro3 (추천)",
                "model": settings.upstage_solar_model,
                "status": "ready",
                "recommended": True
            })

        # Google API 키가 있으면 Gemini 추가
        if has_google_key:
            providers.append({
                "id": AIProvider.GEMINI_FLASH.value,
                "name": "Google Gemini 2.0 Flash",
                "model": "gemini-2.0-flash",
                "status": "ready",
                "recommended": not has_upstage_key
            })
        
        # 배포 환경에서 API 키가 없으면 빈 목록 반환
        return providers


class AIProviderInfo(BaseModel):
    id: str
    name: str
    model: str
    status: str
    recommended: bool


class AIProviderSelectionRequest(BaseModel):
    provider_id: str


@router.get("/providers", response_model=List[AIProviderInfo])
async def get_available_providers(
    github_token: Optional[str] = Header(None, alias="x-github-token"),
    google_api_key: Optional[str] = Header(None, alias="x-google-api-key"),
    upstage_api_key: Optional[str] = Header(None, alias="x-upstage-api-key"),
):
    """사용 가능한 AI 제공업체 목록 조회"""
    try:
        api_keys = extract_api_keys_from_headers(github_token, google_api_key, upstage_api_key)
        providers = get_effective_providers(api_keys)
        return [AIProviderInfo(**provider) for provider in providers]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 제공업체 목록 조회 실패: {str(e)}")


@router.get("/providers/preferred")
async def get_preferred_provider():
    """현재 우선 순위에 따른 추천 AI 제공업체 조회"""
    try:
        preferred = ai_service.get_preferred_provider()
        if preferred is None:
            raise HTTPException(status_code=404, detail="사용 가능한 AI 제공업체가 없습니다")
        
        provider_info = ai_service.available_providers[preferred]
        return {
            "id": preferred.value,
            "name": ai_service._get_provider_display_name(preferred),
            "model": provider_info["model"],
            "status": provider_info["status"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"추천 AI 제공업체 조회 실패: {str(e)}")


@router.post("/test")
async def test_ai_provider(
    request: AIProviderSelectionRequest,
    github_token: Optional[str] = Header(None, alias="x-github-token"),
    google_api_key: Optional[str] = Header(None, alias="x-google-api-key"),
    upstage_api_key: Optional[str] = Header(None, alias="x-upstage-api-key"),
):
    """선택된 AI 제공업체 테스트"""
    try:
        # AIProvider enum으로 변환
        provider = None
        for p in AIProvider:
            if p.value == request.provider_id:
                provider = p
                break
        
        if provider is None:
            raise HTTPException(status_code=400, detail="잘못된 AI 제공업체 ID입니다")
        
        # API 키 추출
        api_keys = extract_api_keys_from_headers(github_token, google_api_key, upstage_api_key)
        
        # 로컬 환경과 배포 환경 구분 처리
        env_exists = check_env_file_exists()
        if not env_exists:
            # 배포 환경(.env.dev 없음): 헤더의 키를 사용
            if provider == AIProvider.GEMINI_FLASH and not api_keys.get("google_api_key"):
                raise HTTPException(status_code=400, detail="Google API 키가 필요합니다")
            if provider == AIProvider.UPSTAGE_SOLAR and not api_keys.get("upstage_api_key"):
                raise HTTPException(status_code=400, detail="Upstage API 키가 필요합니다")
        elif env_exists and provider not in ai_service.available_providers:
            # 로컬 환경(.env.dev 있음): 기존 방식 유지
            raise HTTPException(status_code=400, detail="요청된 AI 제공업체를 사용할 수 없습니다")
        
        # 간단한 테스트 프롬프트로 AI 응답 테스트
        test_prompt = "Hello, please respond with a simple greeting in Korean."
        result = await ai_service.generate_analysis(test_prompt, provider, api_keys=api_keys)
        
        return {
            "status": "success",
            "provider": request.provider_id,
            "test_response": result["content"][:100] + "..." if len(result["content"]) > 100 else result["content"],
            "model": result["model"]
        }
        
    except Exception as e:
        return {
            "status": "error",
            "provider": request.provider_id,
            "error": str(e)
        }


@router.post("/providers/select")
async def select_ai_provider(request: AIProviderSelectionRequest):
    """AI 제공업체 선택"""
    try:
        # AIProvider enum으로 변환
        provider = None
        for p in AIProvider:
            if p.value == request.provider_id:
                provider = p
                break
        
        if provider is None:
            raise HTTPException(status_code=400, detail="잘못된 AI 제공업체 ID입니다")
        
        # 프로바이더 설정
        success = ai_service.set_selected_provider(provider)
        
        if not success:
            raise HTTPException(status_code=400, detail="요청된 AI 제공업체를 사용할 수 없습니다")
        
        # 현재 선택된 프로바이더 정보 반환
        selected = ai_service.get_selected_provider()
        provider_info = ai_service.available_providers[selected]
        
        return {
            "status": "success",
            "message": f"{ai_service._get_provider_display_name(selected)} AI가 선택되었습니다",
            "selected_provider": {
                "id": selected.value,
                "name": ai_service._get_provider_display_name(selected),
                "model": provider_info["model"],
                "status": provider_info["status"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 제공업체 선택 실패: {str(e)}")


@router.get("/providers/current")
async def get_current_provider():
    """현재 선택된 AI 제공업체 조회"""
    try:
        current = ai_service.get_preferred_provider()
        if current is None:
            raise HTTPException(status_code=404, detail="사용 가능한 AI 제공업체가 없습니다")
        
        provider_info = ai_service.available_providers[current]
        is_user_selected = current == ai_service.get_selected_provider()
        
        return {
            "id": current.value,
            "name": ai_service._get_provider_display_name(current),
            "model": provider_info["model"],
            "status": provider_info["status"],
            "is_user_selected": is_user_selected,
            "selection_type": "user_selected" if is_user_selected else "auto_priority"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"현재 AI 제공업체 조회 실패: {str(e)}")
