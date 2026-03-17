"""
AI 서비스 모듈 - Upstage Solar Pro3 우선순위 기반 AI 클라이언트 관리
"""
import os
import logging
import asyncio
import time
from typing import Dict, Any, Optional, List
from enum import Enum
import aiohttp

try:
    import google.generativeai as genai
    GOOGLE_AI_AVAILABLE = True
except ImportError:
    GOOGLE_AI_AVAILABLE = False

from app.core.config import settings
    
logger = logging.getLogger(__name__)


class AIProvider(str, Enum):
    UPSTAGE_SOLAR = "upstage-solar-pro3"
    GEMINI_FLASH = "gemini-flash"
    OPENAI_GPT = "openai-gpt"
    ANTHROPIC_CLAUDE = "anthropic-claude"


class AIService:
    """AI 서비스 클래스 - 여러 AI 제공업체 통합 관리"""
    
    def __init__(self):
        self.provider_priority = [
            AIProvider.UPSTAGE_SOLAR,
            AIProvider.GEMINI_FLASH,
            AIProvider.OPENAI_GPT,
            AIProvider.ANTHROPIC_CLAUDE
        ]
        self.available_providers = {}
        self.selected_provider = None  # 사용자가 선택한 프로바이더
        
        # Rate limiting 관련 변수
        self.last_request_time = {}  # 각 provider별 마지막 요청 시간
        self.request_count = {}      # 각 provider별 요청 횟수 (분당)
        self.rate_limits = {
            AIProvider.UPSTAGE_SOLAR: {"requests_per_minute": 20, "min_interval": 3.0},
            AIProvider.GEMINI_FLASH: {"requests_per_minute": 15, "min_interval": 4.0}  # 4초 간격
        }
        
        self._initialize_providers()
    
    def _initialize_providers(self):
        """사용 가능한 AI 제공업체 초기화"""
        
        try:
            # 기존 providers 초기화 (재초기화 시 중요)
            self.available_providers.clear()
            
            logger.info("Initializing AI providers...")
            
            # Upstage Solar Pro3 초기화 (최우선)
            try:
                upstage_api_key = getattr(settings, 'upstage_api_key', None)
                logger.info(f"Upstage API Key found: {upstage_api_key is not None}")

                if upstage_api_key:
                    self.available_providers[AIProvider.UPSTAGE_SOLAR] = {
                        "client": None,
                        "model": "solar-pro3",
                        "status": "ready"
                    }
                    logger.info("Upstage Solar Pro3 initialized successfully")
                else:
                    logger.warning("Upstage API key not found")
            except Exception as e:
                logger.error(f"Error accessing Upstage API settings: {e}")

            # Google Gemini Flash 초기화
            try:
                google_api_key = getattr(settings, 'google_api_key', None)
                logger.info(f"Google API Key found: {google_api_key is not None}")
                logger.info(f"Google AI available: {GOOGLE_AI_AVAILABLE}")
                
                if google_api_key and GOOGLE_AI_AVAILABLE:
                    try:
                        genai.configure(api_key=google_api_key)
                        self.available_providers[AIProvider.GEMINI_FLASH] = {
                            "client": genai,
                            "model": "gemini-2.0-flash",
                            "status": "ready"
                        }
                        logger.info("Google Gemini Flash initialized successfully")
                    except Exception as e:
                        logger.error(f"Failed to initialize Google Gemini: {e}")
                        # Gemini 초기화 실패해도 계속 진행
                elif not google_api_key:
                    logger.warning("Google API key not found")
                elif not GOOGLE_AI_AVAILABLE:
                    logger.warning("Google AI library not available")
            except Exception as e:
                logger.error(f"Error accessing Google API settings: {e}")
                # settings 접근 오류 시에도 계속 진행
            
            # OpenAI 초기화
            try:
                openai_api_key = getattr(settings, 'openai_api_key', None)
                logger.info(f"OpenAI API Key: {openai_api_key}")
                if openai_api_key and openai_api_key != "your_openai_api_key_here":
                    self.available_providers[AIProvider.OPENAI_GPT] = {
                        "client": None,  # OpenAI 클라이언트는 필요시 구현
                        "model": "gpt-3.5-turbo",
                        "status": "configured"
                    }
                    logger.info("OpenAI GPT configured")
            except Exception as e:
                logger.error(f"Error accessing OpenAI API settings: {e}")
                # OpenAI 설정 오류 시에도 계속 진행
            
            # Anthropic Claude 초기화
            try:
                anthropic_api_key = getattr(settings, 'anthropic_api_key', None)
                logger.info(f"Anthropic API Key: {anthropic_api_key}")
                if anthropic_api_key and anthropic_api_key != "your_anthropic_api_key_here":
                    self.available_providers[AIProvider.ANTHROPIC_CLAUDE] = {
                        "client": None,  # Anthropic 클라이언트는 필요시 구현
                        "model": "claude-3-sonnet",
                        "status": "configured"
                    }
                    logger.info("Anthropic Claude configured")
            except Exception as e:
                logger.error(f"Error accessing Anthropic API settings: {e}")
                # Anthropic 설정 오류 시에도 계속 진행
            
            logger.info(f"Total providers initialized: {len(self.available_providers)}")
            
            # 프로바이더가 하나도 없는 경우 기본 프로바이더 추가
            if not self.available_providers:
                logger.warning("No AI providers available, adding fallback provider")
                self.available_providers[AIProvider.UPSTAGE_SOLAR] = {
                    "client": None,
                    "model": "solar-pro3",
                    "status": "fallback"
                }
                
        except Exception as e:
            logger.error(f"Critical error during AI providers initialization: {e}")
            # 최소한의 fallback 프로바이더라도 제공
            self.available_providers = {
                AIProvider.UPSTAGE_SOLAR: {
                    "client": None,
                    "model": "solar-pro3",
                    "status": "error_fallback"
                }
            }
    
    def reinitialize(self):
        """AI 서비스를 완전히 재초기화 (API 키 업데이트 시 사용)"""
        logger.info("Reinitializing AI service...")
        self._initialize_providers()
        logger.info(f"AI service reinitialized. Available providers: {len(self.available_providers)}")
    
    def get_preferred_provider(self, api_keys: Optional[Dict[str, str]] = None) -> Optional[AIProvider]:
        """우선순위에 따라 사용 가능한 최적의 AI 제공업체 반환"""
        # 사용자가 선택한 프로바이더가 있고 사용 가능하면 우선 사용
        if self.selected_provider and self.selected_provider in self.available_providers:
            return self.selected_provider
            
        # 배포 환경(.env.dev 없음)에서 API 키 기반 동적 선택
        from app.core.config import check_env_file_exists
        env_exists = check_env_file_exists()
        
        if not env_exists and api_keys:
            # 배포 환경에서는 제공된 API 키 기반으로 우선순위 결정
            for provider in self.provider_priority:
                if provider == AIProvider.UPSTAGE_SOLAR and "upstage_api_key" in api_keys:
                    logger.info(f"배포 환경: API 키 기반으로 {provider} 선택")
                    return provider
                if provider == AIProvider.GEMINI_FLASH and "google_api_key" in api_keys:
                    logger.info(f"배포 환경: API 키 기반으로 {provider} 선택")
                    return provider
            return None
            
        # 로컬 환경(.env.dev 있음)에서는 기존 방식 유지
        for provider in self.provider_priority:
            if provider in self.available_providers:
                return provider
        return None
    
    def set_selected_provider(self, provider: AIProvider) -> bool:
        """사용자가 선택한 AI 프로바이더 설정"""
        if provider in self.available_providers:
            self.selected_provider = provider
            logger.info(f"AI 프로바이더가 {provider.value}로 변경되었습니다")
            return True
        else:
            logger.warning(f"사용할 수 없는 AI 프로바이더입니다: {provider.value}")
            return False
    
    def get_selected_provider(self) -> Optional[AIProvider]:
        """현재 선택된 AI 프로바이더 반환"""
        return self.selected_provider
    
    def get_available_providers(self) -> List[Dict[str, Any]]:
        """사용 가능한 모든 AI 제공업체 목록 반환"""
        providers = []
        for provider_enum in self.provider_priority:
            if provider_enum in self.available_providers:
                provider_info = self.available_providers[provider_enum]
                providers.append({
                    "id": provider_enum.value,
                    "name": self._get_provider_display_name(provider_enum),
                    "model": provider_info["model"],
                    "status": provider_info["status"],
                    "recommended": provider_enum == self.provider_priority[0]
                })
        return providers
    
    def _get_provider_display_name(self, provider: AIProvider) -> str:
        """AI 제공업체의 사용자 친화적 이름 반환"""
        names = {
            AIProvider.UPSTAGE_SOLAR: "Upstage Solar Pro3 (추천)",
            AIProvider.GEMINI_FLASH: "Google Gemini 2.0 Flash",
            AIProvider.OPENAI_GPT: "OpenAI GPT",
            AIProvider.ANTHROPIC_CLAUDE: "Anthropic Claude"
        }
        return names.get(provider, provider.value)
    
    async def _wait_for_rate_limit(self, provider: AIProvider):
        """Rate limit에 따른 대기"""
        if provider not in self.rate_limits:
            return
        
        current_time = time.time()
        rate_limit = self.rate_limits[provider]
        min_interval = rate_limit["min_interval"]
        
        # 마지막 요청 시간 확인
        if provider in self.last_request_time:
            time_since_last = current_time - self.last_request_time[provider]
            if time_since_last < min_interval:
                wait_time = min_interval - time_since_last
                logger.info(f"Rate limiting: {provider} - {wait_time:.1f}초 대기")
                await asyncio.sleep(wait_time)
        
        self.last_request_time[provider] = time.time()

    async def generate_analysis(self, 
                              prompt: str,
                              provider: Optional[AIProvider] = None,
                              max_retries: int = 3,
                              api_keys: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """AI를 사용하여 분석 생성 (Rate limiting 및 재시도 포함)"""
        
        # 제공업체가 지정되지 않은 경우 우선순위에 따라 선택
        if provider is None:
            provider = self.get_preferred_provider(api_keys)
        
        # 배포 환경(.env.dev 없음)에서 헤더 API 키 기반 동적 프로바이더 지원
        from app.core.config import check_env_file_exists
        env_exists = check_env_file_exists()
        
        # 배포 환경에서 API 키가 있으면 해당 프로바이더를 임시로 사용 가능하게 처리
        if not env_exists and api_keys and provider:
            has_provider_key = (
                (provider == AIProvider.UPSTAGE_SOLAR and "upstage_api_key" in api_keys)
                or (provider == AIProvider.GEMINI_FLASH and "google_api_key" in api_keys)
            )

            if has_provider_key:
                logger.info(f"배포 환경: {provider} 프로바이더를 헤더 API 키로 임시 활성화")
            elif provider in (AIProvider.UPSTAGE_SOLAR, AIProvider.GEMINI_FLASH):
                raise ValueError(f"배포 환경에서 {provider} 프로바이더에 필요한 API 키가 없습니다")
            else:
                raise ValueError(f"배포 환경에서 지원되지 않는 프로바이더입니다: {provider}")
        elif provider is None:
            raise ValueError("사용 가능한 AI 제공업체가 없습니다")
        elif env_exists and provider not in self.available_providers:
            # 로컬 환경(.env.dev 있음)에서는 기존 방식 유지
            raise ValueError(f"요청된 AI 제공업체를 사용할 수 없습니다: {provider}")
        
        # Rate limiting 적용
        await self._wait_for_rate_limit(provider)
        
        # 재시도 로직
        last_exception = None
        for attempt in range(max_retries):
            try:
                if provider == AIProvider.UPSTAGE_SOLAR:
                    return await self._generate_with_upstage(prompt, api_keys)
                elif provider == AIProvider.GEMINI_FLASH:
                    return await self._generate_with_gemini(prompt, api_keys)
                elif provider == AIProvider.OPENAI_GPT:
                    return await self._generate_with_openai(prompt, api_keys)
                elif provider == AIProvider.ANTHROPIC_CLAUDE:
                    return await self._generate_with_anthropic(prompt, api_keys)
                else:
                    raise ValueError(f"지원되지 않는 AI 제공업체: {provider}")
                    
            except Exception as e:
                last_exception = e
                error_str = str(e)
                
                # 429 에러 (Rate limit exceeded) 처리
                if "429" in error_str or "quota" in error_str.lower():
                    if attempt < max_retries - 1:  # 마지막 시도가 아니면
                        wait_time = (attempt + 1) * 10  # 10초, 20초, 30초 대기
                        logger.warning(f"Rate limit exceeded, waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                        await asyncio.sleep(wait_time)
                        continue
                
                # 다른 에러의 경우 즉시 실패
                logger.error(f"AI 분석 생성 실패 ({provider}), attempt {attempt + 1}/{max_retries}: {e}")
                if attempt == max_retries - 1:  # 마지막 시도
                    break
                    
                # 일반적인 재시도 대기
                await asyncio.sleep(2 ** attempt)  # 지수 백오프: 1초, 2초, 4초
        
        # 모든 재시도 실패
        logger.error(f"AI 분석 생성 최종 실패 ({provider}): {last_exception}")
        raise last_exception

    async def _generate_with_upstage(self, prompt: str, api_keys: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Upstage Solar Pro3로 분석 생성"""
        upstage_api_key = None
        if api_keys and api_keys.get("upstage_api_key"):
            upstage_api_key = api_keys["upstage_api_key"]
            logger.info("Using API key from request headers for Upstage")
        elif getattr(settings, "upstage_api_key", None):
            upstage_api_key = settings.upstage_api_key

        if not upstage_api_key:
            raise ValueError("Upstage API key not available")

        endpoint = os.getenv("UPSTAGE_API_URL", "https://api.upstage.ai/v1/chat/completions")
        payload = {
            "model": "solar-pro3",
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {upstage_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, json=payload, headers=headers, timeout=60) as response:
                if response.status >= 400:
                    body = await response.text()
                    raise ValueError(f"Upstage request failed: {response.status} {body}")

                data = await response.json()
                choices = data.get("choices") or []
                if not choices:
                    raise ValueError("Upstage response does not include choices")

                content = choices[0].get("message", {}).get("content", "")
                if not content:
                    raise ValueError("Upstage response content is empty")

                usage = data.get("usage", {})
                return {
                    "provider": AIProvider.UPSTAGE_SOLAR.value,
                    "model": payload["model"],
                    "content": content,
                    "usage": {
                        "prompt_tokens": usage.get("prompt_tokens", len(prompt.split())),
                        "completion_tokens": usage.get("completion_tokens", len(content.split())),
                    },
                }
    
    async def _generate_with_gemini(self, prompt: str, api_keys: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Google Gemini 2.0 Flash로 분석 생성"""
        try:
            # 헤더에서 받은 API 키가 있으면 임시로 사용
            if api_keys and "google_api_key" in api_keys:
                google_api_key = api_keys["google_api_key"]
                logger.info("Using API key from request headers for Gemini")
                # 임시 클라이언트 생성
                genai.configure(api_key=google_api_key)
            elif settings.google_api_key:
                # 기존 설정 사용
                genai.configure(api_key=settings.google_api_key)
            else:
                raise ValueError("Google API key not available")
            
            model = genai.GenerativeModel('gemini-2.0-flash')
            response = await asyncio.to_thread(model.generate_content, prompt)
            
            return {
                "provider": AIProvider.GEMINI_FLASH.value,
                "model": "gemini-2.0-flash",
                "content": response.text,
                "usage": {
                    "prompt_tokens": len(prompt.split()),
                    "completion_tokens": len(response.text.split())
                }
            }
        except Exception as e:
            logger.error(f"Gemini 분석 생성 실패: {e}")
            raise
    
    async def _generate_with_openai(self, prompt: str, api_keys: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """OpenAI GPT로 분석 생성 (향후 구현)"""
        # TODO: OpenAI 클라이언트 구현
        raise NotImplementedError("OpenAI 통합은 향후 구현 예정입니다")
    
    async def _generate_with_anthropic(self, prompt: str, api_keys: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Anthropic Claude로 분석 생성 (향후 구현)"""
        # TODO: Anthropic 클라이언트 구현
        raise NotImplementedError("Anthropic 통합은 향후 구현 예정입니다")


# 전역 AI 서비스 인스턴스
ai_service = AIService()
