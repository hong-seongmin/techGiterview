import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiKeySetup } from '../components/ApiKeySetup';
import { usePageInitialization } from '../hooks/usePageInitialization';
import { useQuickAccessDataWithCache } from '../hooks/useQuickAccessData';
import {
  HomePageFooter,
  HomeAnalysisComposer,
  HomeContinueCard,
  HomePageNavbar,
} from '../components/HomePage';
import { handleRepositoryAnalysis } from '../utils/repositoryAnalysisService';
import {
  createApiHeaders as createSharedApiHeaders,
  persistSelectedAI,
  setAnalysisToken,
} from '../utils/apiHeaders'
import type { HomePageState } from '../types/homePage';
import { RecentAnalysesPanel, RecentReportsPanel } from '../components/v2/QuickAccessPanels';
import { QuickAccessV2 } from '../components/v2/QuickAccessV2';
import './HomePage.css';

export const HomePage: React.FC = () => {
  const navigate = useNavigate();

  const {
    config,
    providers,
    selectedAI,
    setSelectedAI,
    isLoading,
    error,
    isUsingLocalData,
    hasStoredKeys,
  } = usePageInitialization();
  const quickAccess = useQuickAccessDataWithCache(4)

  const [state, setState] = useState<HomePageState>({
    repoUrl: '',
    isAnalyzing: false,
    showApiKeySetup: false,
  });
  const [hoverPreviewRepo, setHoverPreviewRepo] = useState<string | null>(null);

  const shouldShowApiKeySetup = state.showApiKeySetup;
  const needsApiKeySetup = config.keys_required && !hasStoredKeys();
  const hasHistory =
    quickAccess.data.recent_analyses.length > 0 ||
    quickAccess.data.recent_reports.length > 0
  const homeMode = hasHistory ? 'returning' : 'first-visit'

  const updateState = (updates: Partial<HomePageState>) => {
    setState((prev) => ({ ...prev, ...updates }));
  };

  const handleSelectedAIChange = (aiId: string) => {
    persistSelectedAI(aiId)
    setSelectedAI(aiId)
  }

  const createApiHeadersForAnalysis = (includeApiKeys: boolean, selectedAI?: string) =>
    createSharedApiHeaders({ includeApiKeys, selectedAI });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!state.repoUrl.trim() || !selectedAI) return;

    updateState({ isAnalyzing: true });

    try {
      const result = await handleRepositoryAnalysis(
        state.repoUrl,
        createApiHeadersForAnalysis,
        selectedAI,
        navigate
      );

      if (!result.success) {
        if (result.shouldShowApiKeySetup) {
          updateState({ showApiKeySetup: true });
        }
        if (result.error) {
          alert(result.error);
        }
      }
    } catch (submitError) {
      console.error('Analysis error:', submitError);
      alert('예상치 못한 오류가 발생했습니다.');
    } finally {
      updateState({ isAnalyzing: false });
    }
  };

  const handleApiKeysSet = () => {
    updateState({ showApiKeySetup: false });
  };

  const handleAnalysisOpen = (analysis: { analysis_id: string; analysis_token?: string }) => {
    if (analysis.analysis_token) {
      setAnalysisToken(analysis.analysis_id, analysis.analysis_token)
    }
    navigate(`/dashboard/${analysis.analysis_id}`)
  }

  const handleReportOpen = (report: { interview_id: string }) => {
    navigate(`/reports?interview=${report.interview_id}`)
  }

  return (
    <div className="home-page-v2 v2-root v2-tone-709">
      <HomePageNavbar
        onShowApiKeySetup={() => updateState({ showApiKeySetup: true })}
        needsApiKeySetup={needsApiKeySetup}
        isConnected={!error && !isLoading}
      />

      <main className={`home-v2-main home-v2-main--${homeMode}`}>
        {homeMode === 'first-visit' ? (
          <>
            <section className="home-v2-hero home-v2-hero--first">
              <div className="home-v2-shell">
                <div className="home-v2-hero-copy">
                  <h1 className="home-v2-title">분석할 GitHub 저장소를 입력하세요</h1>
                  <p className="home-v2-subtitle">
                    저장소를 분석하고 맞춤 면접 질문을 생성해 실전처럼 연습하세요.
                  </p>
                </div>

                <HomeAnalysisComposer
                  providers={providers}
                  selectedAI={selectedAI}
                  isLoadingProviders={isLoading}
                  repoUrl={state.repoUrl}
                  displayRepoUrl={hoverPreviewRepo ?? state.repoUrl}
                  isAnalyzing={state.isAnalyzing}
                  needsApiKeySetup={needsApiKeySetup}
                  isUsingLocalData={isUsingLocalData}
                  error={error as Error | string | null}
                  onRepoUrlChange={(url) => {
                    setHoverPreviewRepo(null);
                    updateState({ repoUrl: url });
                  }}
                  onSubmit={handleSubmit}
                  onShowApiKeySetup={() => updateState({ showApiKeySetup: true })}
                  onSelectedAIChange={handleSelectedAIChange}
                  onRepoSelect={(url) => {
                    setHoverPreviewRepo(null);
                    updateState({ repoUrl: url });
                  }}
                  onRepoHoverStart={(url) => {
                    if (!state.isAnalyzing) {
                      setHoverPreviewRepo(url);
                    }
                  }}
                  onRepoHoverEnd={() => setHoverPreviewRepo(null)}
                />
              </div>
            </section>

            <section className="home-v2-activity">
              <div className="home-v2-shell">
                <QuickAccessV2 limit={3} />
              </div>
            </section>
          </>
        ) : (
          <section className="home-v2-returning">
            <div className="home-v2-shell home-v2-shell--returning">
              <div className="home-v2-returning-top">
                <HomeAnalysisComposer
                  compact
                  providers={providers}
                  selectedAI={selectedAI}
                  isLoadingProviders={isLoading}
                  repoUrl={state.repoUrl}
                  displayRepoUrl={hoverPreviewRepo ?? state.repoUrl}
                  isAnalyzing={state.isAnalyzing}
                  needsApiKeySetup={needsApiKeySetup}
                  isUsingLocalData={isUsingLocalData}
                  error={error as Error | string | null}
                  onRepoUrlChange={(url) => {
                    setHoverPreviewRepo(null);
                    updateState({ repoUrl: url });
                  }}
                  onSubmit={handleSubmit}
                  onShowApiKeySetup={() => updateState({ showApiKeySetup: true })}
                  onSelectedAIChange={handleSelectedAIChange}
                  onRepoSelect={(url) => {
                    setHoverPreviewRepo(null);
                    updateState({ repoUrl: url });
                  }}
                  onRepoHoverStart={(url) => {
                    if (!state.isAnalyzing) {
                      setHoverPreviewRepo(url);
                    }
                  }}
                  onRepoHoverEnd={() => setHoverPreviewRepo(null)}
                />

                <HomeContinueCard
                  latestAnalysis={quickAccess.data.recent_analyses[0] ?? null}
                  latestReport={quickAccess.data.recent_reports[0] ?? null}
                  onContinueAnalysis={handleAnalysisOpen}
                  onOpenReport={handleReportOpen}
                />
              </div>

              <div className="home-v2-returning-bottom">
                <RecentAnalysesPanel
                  analyses={quickAccess.data.recent_analyses}
                  onOpenAnalysis={handleAnalysisOpen}
                  onOpenAll={() => navigate('/dashboard')}
                />
                <RecentReportsPanel
                  reports={quickAccess.data.recent_reports}
                  onOpenReport={handleReportOpen}
                  onOpenAll={() => navigate('/reports')}
                />
              </div>
            </div>
          </section>
        )}
      </main>

      {shouldShowApiKeySetup && <ApiKeySetup onApiKeysSet={handleApiKeysSet} />}

      <HomePageFooter />
    </div>
  );
};
