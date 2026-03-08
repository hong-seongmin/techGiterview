export type AIProviderType = 'upstage' | 'gemini'

export const API_STORAGE_KEYS = {
  GITHUB_TOKEN: 'techgiterview_github_token',
  GOOGLE_API_KEY: 'techgiterview_google_api_key',
  UPSTAGE_API_KEY: 'techgiterview_upstage_api_key',
  SELECTED_AI_ID: 'techgiterview_selected_ai_id',
  SELECTED_AI_PROVIDER: 'techgiterview_selected_ai_provider',
  ANALYSIS_TOKEN_PREFIX: 'techgiterview_analysis_token_',
  INTERVIEW_TOKEN_PREFIX: 'techgiterview_interview_token_',
  WS_JOIN_TOKEN_PREFIX: 'techgiterview_ws_join_token_',
} as const

export interface StoredApiKeys {
  githubToken: string
  googleApiKey: string
  upstageApiKey: string
  selectedAIId: string
  selectedProvider: AIProviderType
}

const normalizeProvider = (provider?: string | null): AIProviderType =>
  provider === 'gemini' || provider === 'google' ? 'gemini' : 'upstage'

export const getProviderFromSelectedAI = (
  selectedAI?: string | null,
  fallbackProvider?: string | null
): AIProviderType => {
  const normalized = (selectedAI || '').toLowerCase()

  if (normalized.includes('gemini') || normalized.includes('google')) {
    return 'gemini'
  }

  if (normalized.includes('upstage') || normalized.includes('solar')) {
    return 'upstage'
  }

  return normalizeProvider(fallbackProvider)
}

export const getApiKeysFromStorage = (): StoredApiKeys => {
  try {
    return {
      githubToken: localStorage.getItem(API_STORAGE_KEYS.GITHUB_TOKEN) || '',
      googleApiKey: localStorage.getItem(API_STORAGE_KEYS.GOOGLE_API_KEY) || '',
      upstageApiKey: localStorage.getItem(API_STORAGE_KEYS.UPSTAGE_API_KEY) || '',
      selectedAIId: localStorage.getItem(API_STORAGE_KEYS.SELECTED_AI_ID) || '',
      selectedProvider: normalizeProvider(
        localStorage.getItem(API_STORAGE_KEYS.SELECTED_AI_PROVIDER)
      ),
    }
  } catch (error) {
    return {
      githubToken: '',
      googleApiKey: '',
      upstageApiKey: '',
      selectedAIId: '',
      selectedProvider: 'upstage',
    }
  }
}

export const persistSelectedAI = (selectedAIId: string): void => {
  if (!selectedAIId) return

  try {
    localStorage.setItem(API_STORAGE_KEYS.SELECTED_AI_ID, selectedAIId)
    localStorage.setItem(
      API_STORAGE_KEYS.SELECTED_AI_PROVIDER,
      getProviderFromSelectedAI(selectedAIId)
    )
  } catch {
    // ignore localStorage errors
  }
}

interface CreateApiHeadersOptions {
  includeApiKeys?: boolean
  selectedAI?: string
  provider?: AIProviderType
  apiKeys?: Partial<StoredApiKeys>
  analysisToken?: string
  interviewToken?: string
}

export const createApiHeaders = (
  includeApiKeysOrOptions: boolean | CreateApiHeadersOptions = false
): Record<string, string> => {
  const options: CreateApiHeadersOptions =
    typeof includeApiKeysOrOptions === 'boolean'
      ? { includeApiKeys: includeApiKeysOrOptions }
      : includeApiKeysOrOptions

  const headers: Record<string, string> = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
  }

  if (options.includeApiKeys) {
    const stored = getApiKeysFromStorage()
    const mergedKeys: StoredApiKeys = {
      ...stored,
      ...options.apiKeys,
      selectedProvider: normalizeProvider(
        options.apiKeys?.selectedProvider || stored.selectedProvider
      ),
    }

    if (mergedKeys.githubToken) {
      headers['X-GitHub-Token'] = mergedKeys.githubToken
    }

    const resolvedProvider =
      options.provider ??
      getProviderFromSelectedAI(options.selectedAI, mergedKeys.selectedProvider)

    if (resolvedProvider === 'gemini') {
      if (mergedKeys.googleApiKey) {
        headers['X-Google-API-Key'] = mergedKeys.googleApiKey
      }
    } else if (mergedKeys.upstageApiKey) {
      headers['X-Upstage-API-Key'] = mergedKeys.upstageApiKey
    }
  }

  if (options.analysisToken) {
    headers['X-Analysis-Token'] = options.analysisToken
  }
  if (options.interviewToken) {
    headers['X-Interview-Token'] = options.interviewToken
  }

  return headers
}

export const hasRequiredApiKeys = (
  selectedAI?: string,
  provider?: AIProviderType
): boolean => {
  const keys = getApiKeysFromStorage()

  const resolvedProvider =
    provider ?? getProviderFromSelectedAI(selectedAI, keys.selectedProvider)

  return resolvedProvider === 'gemini'
    ? !!keys.googleApiKey
    : !!keys.upstageApiKey
}

const normalizeIdKey = (id: string): string => id.trim().toLowerCase()

export const setAnalysisToken = (analysisId: string, token: string): void => {
  if (!analysisId || !token) return
  try {
    localStorage.setItem(
      `${API_STORAGE_KEYS.ANALYSIS_TOKEN_PREFIX}${normalizeIdKey(analysisId)}`,
      token
    )
  } catch {
    // ignore localStorage errors
  }
}

export const getAnalysisToken = (analysisId?: string | null): string => {
  if (!analysisId) return ''
  try {
    return (
      localStorage.getItem(
        `${API_STORAGE_KEYS.ANALYSIS_TOKEN_PREFIX}${normalizeIdKey(analysisId)}`
      ) || ''
    )
  } catch {
    return ''
  }
}

export const setInterviewToken = (interviewId: string, token: string): void => {
  if (!interviewId || !token) return
  try {
    localStorage.setItem(
      `${API_STORAGE_KEYS.INTERVIEW_TOKEN_PREFIX}${normalizeIdKey(interviewId)}`,
      token
    )
  } catch {
    // ignore localStorage errors
  }
}

export const getInterviewToken = (interviewId?: string | null): string => {
  if (!interviewId) return ''
  try {
    return (
      localStorage.getItem(
        `${API_STORAGE_KEYS.INTERVIEW_TOKEN_PREFIX}${normalizeIdKey(interviewId)}`
      ) || ''
    )
  } catch {
    return ''
  }
}

export const setWsJoinToken = (interviewId: string, token: string): void => {
  if (!interviewId || !token) return
  try {
    localStorage.setItem(
      `${API_STORAGE_KEYS.WS_JOIN_TOKEN_PREFIX}${normalizeIdKey(interviewId)}`,
      token
    )
  } catch {
    // ignore localStorage errors
  }
}

export const getWsJoinToken = (interviewId?: string | null): string => {
  if (!interviewId) return ''
  try {
    return (
      localStorage.getItem(
        `${API_STORAGE_KEYS.WS_JOIN_TOKEN_PREFIX}${normalizeIdKey(interviewId)}`
      ) || ''
    )
  } catch {
    return ''
  }
}
