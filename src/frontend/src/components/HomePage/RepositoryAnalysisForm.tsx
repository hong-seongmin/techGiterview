import React from 'react';

interface RepositoryAnalysisFormProps {
  repoUrl: string;
  displayRepoUrl?: string;
  isAnalyzing: boolean;
  selectedAI: string;
  onRepoUrlChange: (url: string) => void;
  onSubmit: (e: React.FormEvent) => void;
}

export const RepositoryAnalysisForm: React.FC<RepositoryAnalysisFormProps> = ({
  repoUrl,
  displayRepoUrl,
  isAnalyzing,
  selectedAI,
  onRepoUrlChange,
  onSubmit,
}) => {
  const isPreviewing = Boolean(displayRepoUrl && displayRepoUrl !== repoUrl);

  return (
    <form
      onSubmit={onSubmit}
      className="home-v2-input-form"
      role="form"
      aria-label="저장소 분석 요청"
    >
      <div className="url-input-group">
        {/* Terminal prompt icon */}
        <span className="terminal-prompt" aria-hidden="true">›_</span>
        <label htmlFor="repo-url-input" className="v2-sr-only">
          GitHub 저장소 URL
        </label>
        <input
          id="repo-url-input"
          type="url"
          value={displayRepoUrl ?? repoUrl}
          onChange={(e) => onRepoUrlChange(e.target.value)}
          placeholder="github.com/owner/repo"
          className={`terminal-input ${isPreviewing ? 'terminal-input--preview' : ''}`}
          required
          disabled={isAnalyzing}
          aria-describedby="url-help"
        />
        <div id="url-help" className="v2-sr-only">
          분석하고 싶은 GitHub 저장소의 전체 URL을 입력해주세요.
        </div>
        <button
          type="submit"
          className="btn-analyze"
          disabled={isAnalyzing || !repoUrl.trim() || !selectedAI}
          aria-label={isAnalyzing ? '저장소 분석 중...' : '저장소 분석 시작'}
        >
          {isAnalyzing ? (
            <>
              <span className="spinner"></span>
              분석 중...
            </>
          ) : (
            <>
              분석 시작
              <span aria-hidden="true">→</span>
            </>
          )}
        </button>
      </div>
    </form>
  );
};
