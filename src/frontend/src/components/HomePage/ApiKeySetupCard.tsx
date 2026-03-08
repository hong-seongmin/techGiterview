import React from 'react';
import { ChevronDown, Github, Key, Settings, AlertCircle, CheckCircle2 } from 'lucide-react';

interface ApiKeySetupCardProps {
  onShowApiKeySetup: () => void;
  isUsingLocalData: boolean;
  error: Error | string | null;
  isLoading: boolean;
  needsSetup?: boolean;
  variant?: 'inline' | 'warning-banner';
  showDescription?: boolean;
  selectedAI?: string;
  onToggleAdvanced?: () => void;
  isAdvancedOpen?: boolean;
}

export const ApiKeySetupCard: React.FC<ApiKeySetupCardProps> = ({
  onShowApiKeySetup,
  isUsingLocalData,
  error,
  isLoading,
  needsSetup = false,
  variant = 'inline',
  showDescription = true,
  selectedAI,
  onToggleAdvanced,
  isAdvancedOpen = false,
}) => {
  const isConnected = !error && !isLoading;
  const statusLabel = needsSetup ? '설정 필요' : isConnected ? '연결됨' : isUsingLocalData ? '로컬 모드' : '확인 필요';
  const statusClass = needsSetup
    ? 'home-api-status--warning'
    : isConnected
      ? 'home-api-status--success'
      : 'home-api-status--neutral';
  const stepClass = needsSetup
    ? 'home-api-step-badge--warning'
    : isConnected
      ? 'home-api-step-badge--success'
      : 'home-api-step-badge--neutral';
  const cardStateClass = needsSetup
    ? 'home-api-key-card--warning'
    : isConnected
      ? 'home-api-key-card--success'
      : 'home-api-key-card--neutral';
  const selectedProviderLabel = selectedAI?.includes('gemini')
    ? 'Gemini'
    : selectedAI?.includes('upstage') || selectedAI?.includes('solar')
      ? 'Upstage Solar'
      : 'AI 모델 미선택';

  return (
    <div className={`home-api-key-card home-api-key-card--${variant} ${cardStateClass}`}>
      <div className="home-api-key-card-body">
        <div className="home-api-key-main">
          <span className={`home-api-step-badge ${stepClass}`} aria-hidden="true">
            {variant === 'warning-banner' ? '1' : <Github className="v2-icon-xs" />}
          </span>
          <div className="home-api-key-text">
            <div className="home-api-key-title-row">
              <h3 className="home-api-key-title">
                <Key className="v2-icon-sm home-api-key-title-icon" />
                {variant === 'warning-banner' ? 'Step 1. API 키 설정' : '분석 준비 상태'}
              </h3>
              <span className={`home-api-status-chip ${statusClass}`}>
                {needsSetup ? (
                  <AlertCircle className="v2-icon-xs" />
                ) : (
                  <CheckCircle2 className="v2-icon-xs" />
                )}
                {statusLabel}
              </span>
              <span className="home-api-model-chip">{selectedProviderLabel}</span>
            </div>
            {showDescription ? (
              <p className="home-api-key-copy">
                Upstage 또는 Google API 키 중 하나만 설정하면 바로 분석을 시작할 수 있습니다.
              </p>
            ) : null}
          </div>
        </div>
        <div className="home-api-key-actions">
          <button
            className={`home-api-key-btn ${needsSetup ? 'home-api-key-btn--warning' : ''}`}
            onClick={onShowApiKeySetup}
            type="button"
          >
            <Settings className="v2-icon-sm" />
            {needsSetup ? 'API 관리' : '설정 변경'}
          </button>
          {onToggleAdvanced ? (
            <button
              className="home-api-key-btn home-api-key-btn--secondary"
              onClick={onToggleAdvanced}
              type="button"
            >
              모델 옵션
              <ChevronDown
                className={`v2-icon-xs home-api-key-chevron ${isAdvancedOpen ? 'home-api-key-chevron--open' : ''}`}
              />
            </button>
          ) : null}
        </div>
      </div>

      {needsSetup && (
        <div className="home-api-key-notice">
          ⚠️ GitHub 토큰은 선택 사항이며, AI API 키(Upstage/Google) 중 하나는 필수입니다.
        </div>
      )}
    </div>
  );
};
