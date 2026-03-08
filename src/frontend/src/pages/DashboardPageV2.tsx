import React from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Github, Star, GitFork, Play, RefreshCw, MessageSquare, GitBranch,
  LayoutDashboard, ArrowLeft
} from 'lucide-react'
import { useDashboard } from '../hooks/useDashboard'
import { AppShellV2 } from '../components/v2/AppShellV2'
import { FileTreeV2 } from '../components/v2/FileTreeV2'
import { StatsBar } from '../components/v2/StatsBar'
import { QuestionsMasterDetail } from '../components/v2/QuestionsMasterDetail'
import { LoadingState } from '../components/v2/LoadingState'
import CodeGraphViewer from '../components/CodeGraphViewer'
import { FileContentModal } from '../components/FileContentModal'
import { setAnalysisToken } from '../utils/apiHeaders'
import './DashboardPageV2.css'

export function DashboardPageV2() {
  const { analysisId } = useParams<{ analysisId?: string }>()
  const navigate = useNavigate()
  const [isFileExplorerOpen, setIsFileExplorerOpen] = React.useState(false)

  React.useEffect(() => {
    setIsFileExplorerOpen(false)
  }, [analysisId])

  const {
    // 분석 결과
    analysisResult,
    isLoadingAnalysis,
    isLoadingAllAnalyses,
    loadingProgress,
    error,
    allAnalyses,
    // 질문
    questions,
    isLoadingQuestions,
    questionsGenerated,
    filteredQuestions,
    selectedQuestionId,
    questionSearch,
    questionCategory,
    questionDifficulty,
    // 탭
    activeMainTab,
    // 그래프
    graphData,
    graphStatus,
    isLoadingGraph,
    // 파일
    allFiles,
    isLoadingAllFiles,
    expandedFolders,
    searchTerm,
    isFileModalOpen,
    selectedFilePath,
    // 사이드바
    sidebarWidth,
    isResizingSidebar,
    // handlers
    startInterview,
    regenerateQuestions,
    loadOrGenerateQuestions,
    fetchGraphData,
    loadAllFiles,
    handleSearch,
    toggleFolder,
    handleFileClick,
    closeFileModal,
    startSidebarResize,
    resetSidebarWidth,
    setActiveMainTab,
    setSelectedQuestionId,
    setQuestionSearch,
    setQuestionCategory,
    setQuestionDifficulty,
  } = useDashboard(analysisId)

  // TS strict mode placeholder for requested hook fields in this page structure.
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
    if (!analysisResult || !isFileExplorerOpen || allFiles.length > 0 || isLoadingAllFiles) {
      return
    }

    void loadAllFiles()
  }, [analysisResult, isFileExplorerOpen, allFiles.length, isLoadingAllFiles, loadAllFiles])

  // ── 로딩 상태 ────────────────────────────────────────────────────────────
  if (isLoadingAnalysis || isLoadingAllAnalyses) {
    return (
      <LoadingState
        title={analysisId ? '분석 결과 로딩 중' : '분석 목록 로딩 중'}
        progressModel={loadingProgress}
        onCancel={() => navigate('/')}
      />
    )
  }

  // ── 에러 상태 ────────────────────────────────────────────────────────────
  if (!analysisId && !error) {
    // 분석 목록 표시
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
            {allAnalyses.map(analysis => (
              <div
                key={analysis.analysis_id}
                className="v2-analysis-card"
                onClick={() => goToDashboard(analysis.analysis_id, analysis.analysis_token)}
                role="button"
                tabIndex={0}
                onKeyDown={e => e.key === 'Enter' && goToDashboard(analysis.analysis_id, analysis.analysis_token)}
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
                  {analysis.tech_stack.slice(0, 4).map((tech, i) => (
                    <span key={i} className="v2-badge v2-badge-arch">{tech}</span>
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
  const highlightedKeyFiles = (key_files || []).slice(0, 16)
  const hasGraphData = Boolean(
    graphData && Array.isArray(graphData.nodes) && graphData.nodes.length > 0
  )

  // ── Header ───────────────────────────────────────────────────────────────
  const header = (
    <>
      <div className="v2-header-left">
        <button className="v2-btn v2-btn-ghost v2-btn-sm" onClick={() => navigate('/dashboard')} aria-label="목록으로">
          <ArrowLeft className="v2-btn-icon" />
        </button>
        <Github className="v2-icon-sm v2-header-repo-icon" />
        <span className="v2-header-title">
          {repo_info.owner} / {repo_info.name}
        </span>
        {repo_info.language && (
          <span className="v2-badge v2-badge-arch">{repo_info.language}</span>
        )}
        <span className="v2-header-stat">
          <Star className="v2-icon-xs" />
          {repo_info.stars.toLocaleString()}
        </span>
        <span className="v2-header-stat">
          <GitFork className="v2-icon-xs" />
          {repo_info.forks.toLocaleString()}
        </span>
      </div>
      <div className="v2-header-right">
        <button
          className="v2-btn v2-btn-outline v2-btn-sm"
          onClick={regenerateQuestions}
          disabled={isLoadingQuestions}
        >
          <RefreshCw className="v2-btn-icon" />
          질문 재생성
        </button>
        <button
          className="v2-btn v2-btn-primary v2-btn-sm"
          onClick={startInterview}
          disabled={isLoadingQuestions || questions.length === 0}
        >
          <Play className="v2-btn-icon" />
          {isLoadingQuestions ? '준비 중...' : '면접 시작하기'}
        </button>
      </div>
    </>
  )

  // ── Sidebar ───────────────────────────────────────────────────────────────
  const sidebar = (
    <div className="v2-sidebar-inner">
      {/* Repo Info */}
      <div className="v2-sidebar-section">
        <div className="v2-sidebar-section-header">
          <Github className="v2-icon-sm" />
          <span className="v2-label">저장소 정보</span>
        </div>
        <div className="v2-sidebar-section-body">
          <h4 className="v2-repo-title">{repo_info.owner}/{repo_info.name}</h4>
          {repo_info.description && (
            <p className="v2-repo-desc">{repo_info.description}</p>
          )}
          <div className="v2-repo-stats">
            <span className="v2-repo-stat"><Star className="v2-icon-xs" />{repo_info.stars.toLocaleString()}</span>
            <span className="v2-repo-stat"><GitFork className="v2-icon-xs" />{repo_info.forks.toLocaleString()}</span>
            {repo_info.language && <span className="v2-repo-stat">{repo_info.language}</span>}
          </div>
        </div>
      </div>

      {/* File Tree */}
      <div className="v2-sidebar-section v2-sidebar-section--grow">
        <div className="v2-sidebar-section-header">
          <span className="v2-label">주요 파일</span>
          {allFiles.length > 0 && (
            <span className="v2-badge v2-badge-arch v2-sidebar-files-count">
              {allFiles.length}
            </span>
          )}
        </div>
        <div className="v2-sidebar-section-body v2-sidebar-files-body">
          {highlightedKeyFiles.length > 0 ? (
            <ul className="v2-sidebar-key-files">
              {highlightedKeyFiles.map((file) => (
                <li key={file.path} className="v2-sidebar-key-file-item v2-truncate">
                  {file.path}
                </li>
              ))}
            </ul>
          ) : (
            <p className="v2-sidebar-files-empty">아직 주요 파일 정보가 없습니다.</p>
          )}

          <button
            className="v2-btn v2-btn-outline v2-btn-sm v2-sidebar-toggle-files"
            onClick={() => setIsFileExplorerOpen((prev) => !prev)}
            type="button"
          >
            {isFileExplorerOpen ? '전체 파일 숨기기' : '전체 파일 보기'}
          </button>
        </div>

        {isFileExplorerOpen && (
          <FileTreeV2
            nodes={allFiles}
            expandedFolders={expandedFolders}
            onToggleFolder={toggleFolder}
            onFileClick={handleFileClick}
            searchTerm={searchTerm}
            onSearch={handleSearch}
            isLoading={isLoadingAllFiles}
          />
        )}
      </div>
    </div>
  )

  // ── Main ──────────────────────────────────────────────────────────────────
  const main = (
    <div className="v2-dashboard-main">
      {/* Stats Bar */}
      <StatsBar
        techStack={tech_stack || {}}
        questionCount={questions.length}
        keyFileCount={key_files?.length || 0}
        recommendationCount={recommendations?.length || 0}
        language={repo_info.language}
        repoSize={repo_info.size}
      />

      {/* Tabs */}
      <div className="v2-main-tabs">
        <button
          className={`v2-main-tab ${activeMainTab === 'questions' ? 'v2-main-tab--active' : ''}`}
          onClick={() => setActiveMainTab('questions')}
        >
          <MessageSquare className="v2-icon-sm" />
          면접 질문
          {questions.length > 0 && (
            <span className="v2-badge v2-badge-arch v2-main-tab-count">
              {questions.length}
            </span>
          )}
        </button>
        <button
          className={`v2-main-tab ${activeMainTab === 'graph' ? 'v2-main-tab--active' : ''}`}
          onClick={() => setActiveMainTab('graph')}
        >
          <GitBranch className="v2-icon-sm" />
          코드 그래프
        </button>
      </div>

      {/* Tab Panels */}
      {activeMainTab === 'questions' && (
        <div className="v2-tab-panel v2-tab-panel--questions">
          <QuestionsMasterDetail
            questions={filteredQuestions}
            selectedId={selectedQuestionId}
            onSelect={setSelectedQuestionId}
            onStartInterview={startInterview}
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
        </div>
      )}

      {activeMainTab === 'graph' && (
        <div className="v2-tab-panel v2-tab-panel--graph">
          {hasGraphData ? (
            <CodeGraphViewer graphData={graphData} />
          ) : isLoadingGraph || graphStatus === 'loading' ? (
            <div className="v2-graph-empty">
              <span className="v2-badge v2-badge-default">로딩 중</span>
              <h3>코드 그래프를 불러오는 중입니다.</h3>
              <p>분석 가능한 의존성 그래프가 있으면 바로 표시합니다.</p>
            </div>
          ) : graphStatus === 'unsupported' ? (
            <div className="v2-graph-empty">
              <span className="v2-badge v2-badge-default">미지원</span>
              <h3>현재 서버에는 코드 그래프 API가 없습니다.</h3>
              <p>그래프 탭은 유지되지만, 서버가 그래프 데이터를 제공할 때만 시각화됩니다.</p>
            </div>
          ) : graphStatus === 'error' ? (
            <div className="v2-graph-empty">
              <span className="v2-badge v2-badge-default">오류</span>
              <h3>코드 그래프 로딩에 실패했습니다.</h3>
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
    </div>
  )

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <>
      <AppShellV2
        header={header}
        sidebar={sidebar}
        sidebarWidth={sidebarWidth}
        isResizing={isResizingSidebar}
        onResizeStart={(e) => startSidebarResize(e as React.MouseEvent<HTMLDivElement>)}
        onResizeReset={resetSidebarWidth}
        className="v2-tone-709 dashboard-v2-shell"
      >
        {main}
      </AppShellV2>

      {isFileModalOpen && selectedFilePath && (
        <FileContentModal
          isOpen={isFileModalOpen}
          filePath={selectedFilePath}
          analysisId={analysisResult.analysis_id}
          onClose={closeFileModal}
        />
      )}
    </>
  )
}
