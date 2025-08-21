import { useQuery } from '@tanstack/react-query'
import { useState, useEffect } from 'react'
import { apiFetch } from '../utils/apiUtils'

// 로컬스토리지 유틸리티
const getApiKeysFromStorage = () => {
  try {
    return {
      githubToken: localStorage.getItem('techgiterview_github_token') || '',
      googleApiKey: localStorage.getItem('techgiterview_google_api_key') || ''
    }
  } catch (error) {
    return { githubToken: '', googleApiKey: '' }
  }
}

// API 요청 헤더 생성
const createApiHeaders = (includeApiKeys: boolean = false) => {
  const headers: Record<string, string> = {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
  }
  
  if (includeApiKeys) {
    const { githubToken, googleApiKey } = getApiKeysFromStorage()
    if (githubToken) headers['X-GitHub-Token'] = githubToken
    if (googleApiKey) headers['X-Google-API-Key'] = googleApiKey
  }
  
  return headers
}

// API 인터페이스
interface AIProvider {
  id: string
  name: string
  model: string
  status: string
  recommended: boolean
}

interface PageInitData {
  config: {
    keys_required: boolean
    use_local_storage: boolean
    missing_keys: Record<string, boolean>
  }
  providers: AIProvider[]
}

// 통합 API 호출 함수 (새로운 단일 엔드포인트 사용)
const fetchPageInitData = async (): Promise<PageInitData> => {
  try {
    const headers = createApiHeaders(true)
    
    // 새로운 통합 API 호출
    const response = await apiFetch('/api/v1/homepage/init', { 
      headers,
      timeout: 5000 // 5초 타임아웃
    })
    
    if (!response.ok) {
      // 백엔드 연결 실패 시 로컬 데이터로 폴백
      console.warn(`Homepage Init API 연결 실패 (${response.status}), 로컬 모드로 전환`)
      throw new Error(`Backend connection failed: ${response.status}`)
    }
    
    const data = await response.json()
    
    return {
      config: data.config,
      providers: data.providers
    }
  } catch (error) {
    // 네트워크 에러나 연결 실패 시 로컬 데이터 사용
    console.warn('백엔드 서버 연결 실패, 로컬 모드로 전환:', error)
    throw error // React Query가 에러를 처리하도록 함
  }
}

// 로컬스토리지에서 즉시 사용 가능한 데이터 생성
const getLocalData = (): PageInitData => {
  const { githubToken, googleApiKey } = getApiKeysFromStorage()
  const hasKeys = !!(githubToken && googleApiKey)
  
  return {
    config: {
      keys_required: !hasKeys,
      use_local_storage: true,
      missing_keys: {
        github_token: !githubToken,
        google_api_key: !googleApiKey
      }
    },
    providers: [{
      id: 'gemini_flash',
      name: 'Google Gemini 2.0 Flash (기본)',
      model: 'gemini-2.0-flash-exp',
      status: 'available',
      recommended: true
    }]
  }
}

// 메인 Hook
export const usePageInitialization = () => {
  const [localData] = useState(() => getLocalData())
  
  // React Query로 서버 데이터 가져오기 (백그라운드)
  const {
    data: serverData,
    isLoading,
    error,
    isSuccess
  } = useQuery({
    queryKey: ['page-initialization'],
    queryFn: fetchPageInitData,
    staleTime: 5 * 60 * 1000, // 5분 캐시
    retry: 1, // 재시도 1번으로 줄여서 빠른 폴백
    retryDelay: 1000,
    // 에러 발생 시에도 로컬 데이터 사용하므로 silent 실패
    throwOnError: false,
    // 백그라운드에서 재시도하지 않음 (로컬 모드로 동작)
    refetchOnWindowFocus: false,
    refetchOnReconnect: true, // 네트워크 재연결 시에만 재시도
  })
  
  // 서버 데이터가 있으면 사용, 없으면 로컬 데이터 사용
  const effectiveData = serverData || localData
  
  // AI 제공업체 선택 상태
  const [selectedAI, setSelectedAI] = useState('')
  
  // 추천 AI 자동 선택
  useEffect(() => {
    if (effectiveData.providers.length > 0 && !selectedAI) {
      const recommended = effectiveData.providers.find(p => p.recommended)
      if (recommended) {
        setSelectedAI(recommended.id)
      } else {
        setSelectedAI(effectiveData.providers[0].id)
      }
    }
  }, [effectiveData.providers, selectedAI])
  
  return {
    // 데이터
    config: effectiveData.config,
    providers: effectiveData.providers,
    selectedAI,
    setSelectedAI,
    
    // 상태
    isLoading,
    error,
    isSuccess,
    isUsingLocalData: !serverData,
    
    // 유틸리티
    hasStoredKeys: () => {
      const { githubToken, googleApiKey } = getApiKeysFromStorage()
      return !!(githubToken && googleApiKey)
    },
    
    createApiHeaders
  }
}