import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiKeySetup } from '../components/ApiKeySetup';
import { usePageInitialization } from '../hooks/usePageInitialization';
import {
  ApiKeySetupCard,
  HomePageFooter,
  HomePageNavbar,
  RepositoryAnalysisForm,
  SampleRepositoriesSection,
} from '../components/HomePage';
import { handleRepositoryAnalysis } from '../utils/repositoryAnalysisService';
import {
  createApiHeaders as createSharedApiHeaders,
  persistSelectedAI,
} from '../utils/apiHeaders'
import type { HomePageState } from '../types/homePage';
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

  const [state, setState] = useState<HomePageState>({
    repoUrl: '',
    isAnalyzing: false,
    showApiKeySetup: false,
  });
  const [hoverPreviewRepo, setHoverPreviewRepo] = useState<string | null>(null);

  const shouldShowApiKeySetup = state.showApiKeySetup;
  const needsApiKeySetup = config.keys_required && !hasStoredKeys();

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

  return (
    <div className="home-page-v2 v2-root v2-tone-709">
      <HomePageNavbar
        onShowApiKeySetup={() => updateState({ showApiKeySetup: true })}
        needsApiKeySetup={needsApiKeySetup}
        isConnected={!error && !isLoading}
        providers={providers}
        selectedAI={selectedAI}
        onSelectedAIChange={handleSelectedAIChange}
      />

      <main className="home-v2-main">
        <section className="home-v2-hero">
          <div className="home-v2-shell">
            <h1 className="home-v2-title">분석할 GitHub 저장소를 입력하세요</h1>
            <p className="home-v2-subtitle">
              저장소를 분석하고 맞춤 면접 질문을 생성해 실전처럼 연습하세요.
            </p>

            <ApiKeySetupCard
              onShowApiKeySetup={() => updateState({ showApiKeySetup: true })}
              isUsingLocalData={isUsingLocalData}
              error={error as Error | string | null}
              isLoading={isLoading}
              needsSetup={needsApiKeySetup}
            />

            <div className="home-v2-search-card">
              <RepositoryAnalysisForm
                repoUrl={state.repoUrl}
                displayRepoUrl={hoverPreviewRepo ?? state.repoUrl}
                isAnalyzing={state.isAnalyzing}
                selectedAI={selectedAI}
                onRepoUrlChange={(url) => {
                  setHoverPreviewRepo(null);
                  updateState({ repoUrl: url });
                }}
                onSubmit={handleSubmit}
              />
              <SampleRepositoriesSection
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
                isAnalyzing={state.isAnalyzing}
              />
            </div>
          </div>
        </section>

        <section className="home-v2-activity">
          <div className="home-v2-shell">
            <QuickAccessV2 limit={3} />
          </div>
        </section>
      </main>

      {shouldShowApiKeySetup && <ApiKeySetup onApiKeysSet={handleApiKeysSet} />}

      <HomePageFooter />
    </div>
  );
};
