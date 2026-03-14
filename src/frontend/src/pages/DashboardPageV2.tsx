import React from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Github, Star, GitFork, Play, RefreshCw, MessageSquare, GitBranch,
  LayoutDashboard, ArrowLeft, PanelRightOpen
} from 'lucide-react'
import { useDashboard } from '../hooks/useDashboard'
import { QuestionsMasterDetail } from '../components/v2/QuestionsMasterDetail'
import { LoadingState } from '../components/v2/LoadingState'
import CodeGraphViewer from '../components/CodeGraphViewer'
import { FileContentModal } from '../components/FileContentModal'
import { setAnalysisToken } from '../utils/apiHeaders'
import { DashboardSummaryStrip } from '../components/v2/DashboardSummaryStrip'
import { RepositoryInfoDrawer } from '../components/v2/RepositoryInfoDrawer'
import './DashboardPageV2.css'

export function DashboardPageV2() {
  const { analysisId } = useParams<{ analysisId?: string }>()
  const navigate = useNavigate()
  const [isRepoDrawerOpen, setIsRepoDrawerOpen] = React.useState(false)

  React.useEffect(() => {
    setIsRepoDrawerOpen(false)
  }, [analysisId])

  const {
    analysisResult,
    isLoadingAnalysis,
    isLoadingAllAnalyses,
    loadingProgress,
    error,
    allAnalyses,
    questions,
    isLoadingQuestions,
    questionsGenerated,
    filteredQuestions,
    selectedQuestionId,
    questionSearch,
    questionCategory,
    questionDifficulty,
    activeMainTab,
    graphData,
    graphStatus,
    isLoadingGraph,
    allFiles,
    isLoadingAllFiles,
    expandedFolders,
    searchTerm,
    isFileModalOpen,
    selectedFilePath,
    startInterview,
    regenerateQuestions,
    loadOrGenerateQuestions,
    fetchGraphData,
    loadAllFiles,
    handleSearch,
    toggleFolder,
    handleFileClick,
    closeFileModal,
    setActiveMainTab,
    setSelectedQuestionId,
    setQuestionSearch,
    setQuestionCategory,
    setQuestionDifficulty,
  } = useDashboard(analysisId)

  void questionsGenerated
  void loadOrGenerateQuestions

  const goToDashboard = (targetAnalysisId: string, analysisToken?: string) => {
    if (analysisToken) {
      setAnalysisToken(targetAnalysisId, analysisToken)
    }
    navigate(`/dashboard/${targetAnalysisId}`)
  }

  React.useEffect(() => {
    if (!analysisResult || activeMainTab !== 'graph' || graphStatus !== 'idle') {
      return
    }

    void fetchGraphData(analysisResult.analysis_id)
  }, [analysisResult, activeMainTab, graphStatus, fetchGraphData])

  React.useEffect(() => {
    if (!analysisResult || !isRepoDrawerOpen || allFiles.length > 0 || isLoadingAllFiles) {
      return
    }

    void loadAllFiles()
  }, [analysisResult, isRepoDrawerOpen, allFiles.length, isLoadingAllFiles, loadAllFiles])

  if (isLoadingAnalysis || isLoadingAllAnalyses) {
    return (
      <LoadingState
        title={analysisId ? '분석 결과 로딩 중' : '분석 목록 로딩 중'}
        progressModel={loadingProgress}
        onCancel={() => navigate('/')}
      />
    )
  }

  if (!analysisId && !error) {
    return (
      <div className="v2-root v2-tone-709 v2-analyses-list-page">
        <div className="v2-analyses-shell">
          <div className="v2-analyses-header">
            <h1 className="v2-analyses-title">
              <LayoutDashboard className="v2-icon-md" />
              전체 분석 결과
            </h1>
            <p className="v2-analyses-sub">총 {allAnalyses.length}개의 분석 결과</p>
          </div>
          <div className="v2-analyses-grid">
            {allAnalyses.map((analysis) => (
              <div
                key={analysis.analysis_id}
                className="v2-analysis-card"
                onClick={() => goToDashboard(analysis.analysis_id, analysis.analysis_token)}
                role="button"
                tabIndex={0}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    goToDashboard(analysis.analysis_id, analysis.analysis_token)
                  }
                }}
              >
                <div className="v2-analysis-card-header">
                  <Github className="v2-icon-sm" />
                  <h3>{analysis.repository_owner}/{analysis.repository_name}</h3>
                </div>
                <div className="v2-analysis-card-meta">
                  <span>{analysis.primary_language}</span>
                  <span>{analysis.file_count}개 파일</span>
                </div>
                <div className="v2-analysis-card-stack">
                  {analysis.tech_stack.slice(0, 4).map((tech, index) => (
                    <span key={index} className="v2-badge v2-badge-arch">{tech}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (error || !analysisResult) {
    return (
      <div className="v2-root v2-tone-709 v2-error-page">
        <div className="v2-error-shell">
          <h2>분석 결과를 찾을 수 없습니다</h2>
          <p>{error || '분석이 완료되지 않았거나 잘못된 ID입니다.'}</p>
          <button className="v2-btn v2-btn-outline" onClick={() => navigate('/')}>
            홈으로
          </button>
        </div>
      </div>
    )
  }

  const { repo_info, tech_stack, key_files, recommendations } = analysisResult
  const hasGraphData = Boolean(graphData && Array.isArray(graphData.nodes) && graphData.nodes.length > 0)

  return (
    <>
      <div className="v2-root v2-tone-709 dashboard-v2-page">
        <header className="dashboard-v2-header">
          <div className="dashboard-v2-header-main">
            <button className="v2-btn v2-btn-ghost v2-btn-sm" onClick={() => navigate('/dashboard')} aria-label="목록으로">
              <ArrowLeft className="v2-btn-icon" />
            </button>
            <div className="dashboard-v2-repo-meta">
              <div className="dashboard-v2-repo-title-row">
                <Github className="v2-icon-sm dashboard-v2-repo-icon" />
                <h1>{repo_info.owner} / {repo_info.name}</h1>
              </div>
              <div className="dashboard-v2-repo-inline-stats">
                {repo_info.language ? <span className="v2-badge v2-badge-arch">{repo_info.language}</span> : null}
                <span className="v2-header-stat"><Star className="v2-icon-xs" />{repo_info.stars.toLocaleString()}</span>
                <span className="v2-header-stat"><GitFork className="v2-icon-xs" />{repo_info.forks.toLocaleString()}</span>
              </div>
            </div>
          </div>

          <div className="dashboard-v2-header-actions">
            <div className="dashboard-v2-view-switch" role="tablist" aria-label="대시보드 보기 전환">
              <button
                className={`dashboard-v2-view-btn ${activeMainTab === 'questions' ? 'dashboard-v2-view-btn--active' : ''}`}
                onClick={() => setActiveMainTab('questions')}
                role="tab"
                aria-selected={activeMainTab === 'questions'}
              >
                <MessageSquare className="v2-icon-sm" />
                질문
              </button>
              <button
                className={`dashboard-v2-view-btn ${activeMainTab === 'graph' ? 'dashboard-v2-view-btn--active' : ''}`}
                onClick={() => setActiveMainTab('graph')}
                role="tab"
                aria-selected={activeMainTab === 'graph'}
              >
                <GitBranch className="v2-icon-sm" />
                코드 그래프
              </button>
            </div>

            <button className="v2-btn v2-btn-ghost v2-btn-sm" onClick={() => setIsRepoDrawerOpen(true)}>
              <PanelRightOpen className="v2-btn-icon" />
              저장소 정보
            </button>

            <button className="v2-btn v2-btn-outline v2-btn-sm" onClick={regenerateQuestions} disabled={isLoadingQuestions}>
              <RefreshCw className="v2-btn-icon" />
              질문 재생성
            </button>

            <button className="v2-btn v2-btn-primary v2-btn-sm" onClick={startInterview} disabled={isLoadingQuestions || questions.length === 0}>
              <Play className="v2-btn-icon" />
              {isLoadingQuestions ? '준비 중...' : '전체 모의면접 시작'}
            </button>
          </div>
        </header>

        <main className="dashboard-v2-main">
          <DashboardSummaryStrip
            techStack={tech_stack || {}}
            questionCount={questions.length}
            keyFileCount={key_files?.length || 0}
            recommendationCount={recommendations?.length || 0}
          />

          {activeMainTab === 'questions' ? (
            <QuestionsMasterDetail
              questions={filteredQuestions}
              selectedId={selectedQuestionId}
              onSelect={setSelectedQuestionId}
              onRegenerate={regenerateQuestions}
              isLoadingQuestions={isLoadingQuestions}
              filterSearch={questionSearch}
              filterCategory={questionCategory}
              filterDifficulty={questionDifficulty}
              onFilterSearch={setQuestionSearch}
              onFilterCategory={setQuestionCategory}
              onFilterDifficulty={setQuestionDifficulty}
              totalCount={questions.length}
            />
          ) : (
            <div className="dashboard-v2-graph-shell">
              {hasGraphData ? (
                <CodeGraphViewer graphData={graphData} />
              ) : isLoadingGraph || graphStatus === 'loading' ? (
                <div className="v2-graph-empty">
                  <span className="v2-badge v2-badge-default">로딩 중</span>
                  <h3>코드 그래프를 불러오는 중입니다.</h3>
                  <p>핵심 파일 간 의존 관계를 시각화합니다.</p>
                </div>
              ) : graphStatus === 'empty' ? (
                <div className="v2-graph-empty">
                  <span className="v2-badge v2-badge-default">그래프 없음</span>
                  <h3>그래프화할 의존성 관계를 찾지 못했습니다.</h3>
                  <p>{graphData?.message || '선택된 핵심 파일 사이에 분석 가능한 import 또는 flow 연결이 충분하지 않습니다.'}</p>
                </div>
              ) : graphStatus === 'needs_reanalysis' ? (
                <div className="v2-graph-empty">
                  <span className="v2-badge v2-badge-default">재분석 필요</span>
                  <h3>이 분석은 그래프를 재구성할 원본 파일 내용이 없습니다.</h3>
                  <p>{graphData?.message || '현재 서버 세션에서 저장소를 다시 분석하면 코드 그래프를 볼 수 있습니다.'}</p>
                </div>
              ) : graphStatus === 'error' ? (
                <div className="v2-graph-empty">
                  <span className="v2-badge v2-badge-default">오류</span>
                  <h3>코드 그래프를 불러오지 못했습니다.</h3>
                  <p>다시 탭을 열거나 새로고침해 재시도할 수 있습니다.</p>
                </div>
              ) : (
                <div className="v2-graph-empty">
                  <span className="v2-badge v2-badge-default">준비 중</span>
                  <h3>그래프 탭을 열면 코드 그래프를 요청합니다.</h3>
                  <p>초기 로딩 속도를 줄이기 위해 그래프는 필요할 때만 가져옵니다.</p>
                </div>
              )}
            </div>
          )}
        </main>
      </div>

      <RepositoryInfoDrawer
        open={isRepoDrawerOpen}
        onClose={() => setIsRepoDrawerOpen(false)}
        repoInfo={repo_info}
        techStack={tech_stack || {}}
        keyFiles={key_files || []}
        allFiles={allFiles}
        isLoadingAllFiles={isLoadingAllFiles}
        expandedFolders={expandedFolders}
        searchTerm={searchTerm}
        onSearch={handleSearch}
        onToggleFolder={toggleFolder}
        onFileClick={handleFileClick}
        onLoadAllFiles={() => void loadAllFiles()}
      />

      {isFileModalOpen && selectedFilePath ? (
        <FileContentModal
          isOpen={isFileModalOpen}
          filePath={selectedFilePath}
          analysisId={analysisResult.analysis_id}
          onClose={closeFileModal}
        />
      ) : null}
    </>
  )
}
