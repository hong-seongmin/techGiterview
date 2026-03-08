import { useQuery } from '@tanstack/react-query'
import { useState, useEffect, useMemo } from 'react'
import {
  createApiHeaders,
  getApiKeysFromStorage,
  getProviderFromSelectedAI,
} from '../utils/apiHeaders'

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
    const headers = createApiHeaders({ includeApiKeys: true })
    
    // 새로운 통합 API 호출
    const response = await fetch('/api/v1/homepage/init', { 
      headers
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
  const { githubToken, upstageApiKey, googleApiKey } = getApiKeysFromStorage()
  const hasRequiredKeys = !!(upstageApiKey || googleApiKey)
  const providers: AIProvider[] = []

  if (upstageApiKey) {
    providers.push({
      id: 'upstage-solar-pro3',
      name: 'Upstage Solar Pro3 (기본)',
      model: 'solar-pro3',
      status: 'ready',
      recommended: true
    })
  }

  if (googleApiKey) {
    providers.push({
      id: 'gemini-flash',
      name: 'Google Gemini 2.0 Flash',
      model: 'gemini-2.0-flash',
      status: 'ready',
      recommended: !upstageApiKey
    })
  }

  if (!providers.length) {
    providers.push({
      id: 'upstage-solar-pro3',
      name: 'Upstage Solar Pro3 (기본)',
      model: 'solar-pro3',
      status: 'configured',
      recommended: true
    })
  }
  
  return {
    config: {
      keys_required: !hasRequiredKeys,
      use_local_storage: true,
      missing_keys: {
        github_token: !githubToken,
        upstage_api_key: !upstageApiKey,
        google_api_key: !googleApiKey
      }
    },
    providers
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
  const sortedProviders = useMemo(
    () =>
      [...effectiveData.providers].sort((a, b) => {
        if (a.recommended === b.recommended) return a.name.localeCompare(b.name)
        return a.recommended ? -1 : 1
      }),
    [effectiveData.providers]
  )
  
  // AI 제공업체 선택 상태
  const [selectedAI, setSelectedAI] = useState('')
  
  // 추천 AI 자동 선택
  useEffect(() => {
    if (!sortedProviders.length || selectedAI) return

    const stored = getApiKeysFromStorage()
    const exactMatch = sortedProviders.find((provider) => provider.id === stored.selectedAIId)
    const providerMatch = sortedProviders.find(
      (provider) => getProviderFromSelectedAI(provider.id) === stored.selectedProvider
    )
    const recommended = sortedProviders.find((provider) => provider.recommended)

    setSelectedAI((exactMatch ?? providerMatch ?? recommended ?? sortedProviders[0]).id)
  }, [sortedProviders, selectedAI])
  
  return {
    // 데이터
    config: effectiveData.config,
    providers: sortedProviders,
    selectedAI,
    setSelectedAI,
    
    // 상태
    isLoading,
    error,
    isSuccess,
    isUsingLocalData: !serverData,
    
    // 유틸리티
    hasStoredKeys: () => {
      const { upstageApiKey, googleApiKey } = getApiKeysFromStorage()
      return !!(upstageApiKey || googleApiKey)
    },
    
    createApiHeaders
  }
}
