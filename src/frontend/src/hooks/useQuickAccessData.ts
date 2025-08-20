import { useState, useEffect, useCallback } from 'react'

interface RecentAnalysis {
  analysis_id: string
  repository_name: string
  repository_owner: string
  created_at: string
  tech_stack: string[]
  file_count: number
  primary_language: string
}

interface RecentReport {
  interview_id: string
  repository_name: string
  repository_owner: string
  overall_score: number
  completed_at: string
  duration_minutes: number
  questions_count: number
  answers_count: number
  category_scores: Record<string, number>
  difficulty_level: string
}

interface QuickAccessData {
  recent_analyses: RecentAnalysis[]
  recent_reports: RecentReport[]
}

interface UseQuickAccessDataResult {
  data: QuickAccessData
  isLoading: boolean
  error: string | null
  refetch: () => Promise<void>
}

export const useQuickAccessData = (limit: number = 3): UseQuickAccessDataResult => {
  const [data, setData] = useState<QuickAccessData>({ 
    recent_analyses: [], 
    recent_reports: [] 
  })
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)

      // 병렬로 두 API 호출 (Vite 프록시 사용)
      const [analysesResponse, reportsResponse] = await Promise.all([
        fetch(`/api/v1/repository/analysis/recent?limit=${limit}`),
        fetch(`/api/v1/reports/recent?limit=${limit}`)
      ])

      // 응답 처리
      const analysesResult = await analysesResponse.json()
      const reportsResult = await reportsResponse.json()

      // 데이터 설정
      setData({
        recent_analyses: analysesResult.success ? analysesResult.data : [],
        recent_reports: reportsResult.success ? reportsResult.data.reports : []
      })

      console.log('[QUICK_ACCESS_HOOK] 데이터 로드 완료:', {
        analyses: analysesResult.success ? analysesResult.data.length : 0,
        reports: reportsResult.success ? reportsResult.data.reports?.length : 0
      })

    } catch (error) {
      console.error('[QUICK_ACCESS_HOOK] 데이터 로딩 오류:', error)
      setError('데이터를 불러오는데 실패했습니다.')
    } finally {
      setIsLoading(false)
    }
  }, [limit])

  // 컴포넌트 마운트 시 데이터 로드
  useEffect(() => {
    fetchData()
  }, [fetchData])

  return {
    data,
    isLoading,
    error,
    refetch: fetchData
  }
}

// Local Storage를 활용한 캐싱 버전
export const useQuickAccessDataWithCache = (limit: number = 3): UseQuickAccessDataResult => {
  const [data, setData] = useState<QuickAccessData>(() => {
    // 초기 데이터를 localStorage에서 로드
    try {
      const cached = localStorage.getItem('quick-access-data')
      if (cached) {
        const parsed = JSON.parse(cached)
        const cacheTime = localStorage.getItem('quick-access-data-time')
        const now = Date.now()
        
        // 5분 이내의 캐시만 사용
        if (cacheTime && (now - parseInt(cacheTime)) < 5 * 60 * 1000) {
          return parsed
        }
      }
    } catch (error) {
      console.warn('[QUICK_ACCESS_CACHE] 캐시 로드 실패:', error)
    }
    
    return { recent_analyses: [], recent_reports: [] }
  })
  
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)

      const [analysesResponse, reportsResponse] = await Promise.all([
        fetch(`/api/v1/repository/analysis/recent?limit=${limit}`),
        fetch(`/api/v1/reports/recent?limit=${limit}`)
      ])

      const analysesResult = await analysesResponse.json()
      const reportsResult = await reportsResponse.json()

      const newData = {
        recent_analyses: analysesResult.success ? analysesResult.data : [],
        recent_reports: reportsResult.success ? reportsResult.data.reports : []
      }

      setData(newData)

      // localStorage에 캐시 저장
      try {
        localStorage.setItem('quick-access-data', JSON.stringify(newData))
        localStorage.setItem('quick-access-data-time', Date.now().toString())
      } catch (cacheError) {
        console.warn('[QUICK_ACCESS_CACHE] 캐시 저장 실패:', cacheError)
      }

    } catch (error) {
      console.error('[QUICK_ACCESS_HOOK] 데이터 로딩 오류:', error)
      setError('데이터를 불러오는데 실패했습니다.')
    } finally {
      setIsLoading(false)
    }
  }, [limit])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  return {
    data,
    isLoading,
    error,
    refetch: fetchData
  }
}