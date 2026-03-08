import {
  validateGitHubUrl,
  processAnalysisResponse,
  processError,
} from './homePageUtils';
import { apiFetch } from './apiUtils';
import { getApiKeysFromStorage, setAnalysisToken } from './apiHeaders';

/**
 * 저장소 분석 요청 처리 로직
 */
export const handleRepositoryAnalysis = async (
  repoUrl: string,
  createApiHeaders: (includeApiKeys: boolean, selectedAI?: string) => Record<string, string>,
  selectedAI: string,
  onNavigate: (path: string) => void
): Promise<{
  success: boolean;
  error?: string;
  shouldShowApiKeySetup?: boolean;
}> => {
  // GitHub URL 유효성 검사
  if (!validateGitHubUrl(repoUrl)) {
    return {
      success: false,
      error: '올바른 GitHub 저장소 URL을 입력해주세요.',
    };
  }

  try {
    // 저장소 분석 요청 (임시로 간단한 분석 사용)
    const apiHeaders = createApiHeaders(true, selectedAI);
    const { githubToken, googleApiKey, upstageApiKey, selectedProvider } =
      getApiKeysFromStorage();
    console.log(
      '[HOMEPAGE] 분석 요청 헤더:',
      JSON.stringify(apiHeaders, null, 2)
    );
    console.log('[HOMEPAGE] localStorage 키 확인:', {
      githubToken: githubToken ? '설정됨' : '없음',
      googleApiKey: googleApiKey ? '설정됨' : '없음',
      upstageApiKey: upstageApiKey ? '설정됨' : '없음',
      selectedProvider,
      selectedAI,
    });

    const response = await apiFetch('/api/v1/repository/analyze-simple', {
      method: 'POST',
      headers: apiHeaders,
      body: JSON.stringify({
        repo_url: repoUrl,
        selected_ai: selectedAI,
        selected_provider_id: selectedAI,
      }),
    });

    console.log('[HOMEPAGE] 응답 상태:', response.status, response.statusText);

    if (!response.ok) {
      // 403 에러 처리 (API 키 필요)
      if (response.status === 403) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.detail ||
            'GitHub API 접근이 제한되었습니다. API 키 설정이 필요합니다.'
        );
      }
      throw new Error('저장소 분석에 실패했습니다.');
    }

    const result = await response.json();
    const issuedAnalysisToken =
      response.headers.get('X-Analysis-Token') || result?.security?.analysis_token;
    const { analysisId, error } = processAnalysisResponse(result);

    if (analysisId) {
      if (issuedAnalysisToken) {
        setAnalysisToken(analysisId, issuedAnalysisToken);
      }
      onNavigate(`/dashboard/${analysisId}`);
      return { success: true };
    } else {
      return { success: false, error };
    }
  } catch (error) {
    console.error('Analysis error:', error);
    const { message, shouldShowApiKeySetup } = processError(error);
    return {
      success: false,
      error: message,
      shouldShowApiKeySetup,
    };
  }
};
