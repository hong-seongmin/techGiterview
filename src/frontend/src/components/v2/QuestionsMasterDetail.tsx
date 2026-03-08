import React from 'react'
import { Search, Clock, MessageSquare, Play, RefreshCw, File, Terminal, Monitor, MessageCircle, Zap, Database, TrendingUp, CheckCircle, Star, AlertTriangle, Code } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Question } from '../../types/dashboard'
import { formatQuestionForDisplay } from '../../utils/questionFormatter'
import './QuestionsMasterDetail.css'

// ── helpers ──────────────────────────────────────────────────────────────────

function getDifficultyBadgeClass(d: string): string {
  const l = d.toLowerCase()
  if (['easy','beginner','low'].includes(l)) return 'v2-badge v2-badge-easy'
  if (['medium','intermediate','normal'].includes(l)) return 'v2-badge v2-badge-medium'
  if (['hard','advanced','high'].includes(l)) return 'v2-badge v2-badge-hard'
  return 'v2-badge v2-badge-default'
}

function getCategoryBadgeClass(type: string): string {
  const l = (type || '').toLowerCase()
  if (l.includes('arch')) return 'v2-badge v2-badge-arch'
  if (l.includes('logic') || l.includes('code')) return 'v2-badge v2-badge-logic'
  if (l.includes('sys') || l.includes('design')) return 'v2-badge v2-badge-sys'
  if (l.includes('tech')) return 'v2-badge v2-badge-tech'
  return 'v2-badge v2-badge-default'
}

function getCategoryIcon(type: string): React.ReactNode {
  const l = (type || '').toLowerCase()
  if (l === 'technical') return <Terminal className="v2-icon-xs" />
  if (l === 'architectural') return <Monitor className="v2-icon-xs" />
  if (l === 'scenario') return <MessageCircle className="v2-icon-xs" />
  if (l === 'algorithm') return <Zap className="v2-icon-xs" />
  if (l === 'data-structure') return <Database className="v2-icon-xs" />
  if (l === 'system-design') return <TrendingUp className="v2-icon-xs" />
  if (l === 'code-review') return <CheckCircle className="v2-icon-xs" />
  if (l === 'best-practices') return <Star className="v2-icon-xs" />
  if (l === 'debugging') return <AlertTriangle className="v2-icon-xs" />
  return <Code className="v2-icon-xs" />
}

// ── List Card ─────────────────────────────────────────────────────────────────

function QuestionListCard({ question, index, isSelected, onClick }: {
  question: Question
  index: number
  isSelected: boolean
  onClick: () => void
}) {
  const fmt = formatQuestionForDisplay(question)
  const preview = fmt.headline || question.question || ''

  return (
    <div
      className={`v2-qlc ${isSelected ? 'v2-qlc--selected' : ''}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick() } }}
      aria-pressed={isSelected}
    >
      <div className="v2-qlc-header">
        <span className="v2-qlc-num">Q{index + 1}</span>
        {getCategoryIcon(question.type)}
        <span className={getCategoryBadgeClass(question.type)}>
          {question.type || 'General'}
        </span>
        <span className={getDifficultyBadgeClass(question.difficulty)}>
          {question.difficulty}
        </span>
        {question.time_estimate && (
          <span className="v2-qlc-time">
            <Clock className="v2-icon-xs" />
            {question.time_estimate}
          </span>
        )}
      </div>
      <div className="v2-qlc-preview v2-clamp-2">{preview}</div>
      {question.source_file && (
        <div className="v2-qlc-file">
          <File className="v2-icon-xs" />
          <span className="v2-truncate">{question.source_file}</span>
        </div>
      )}
    </div>
  )
}

// ── Detail Panel ─────────────────────────────────────────────────────────────

function QuestionDetail({ question, index, onStartInterview, onRegenerate, isLoadingQuestions, expandedCode, onToggleCode }: {
  question: Question
  index: number
  onStartInterview: () => void
  onRegenerate: () => void
  isLoadingQuestions: boolean
  expandedCode: boolean
  onToggleCode: () => void
}) {
  const fmt = formatQuestionForDisplay(question)

  return (
    <div className="v2-detail-content">
      {/* Header */}
      <div className="v2-detail-header">
        <div className="v2-detail-header-left">
          <span className="v2-qlc-num">Q{index + 1}</span>
          {getCategoryIcon(question.type)}
          <span className={getCategoryBadgeClass(question.type)}>{question.type || 'General'}</span>
          <span className={getDifficultyBadgeClass(question.difficulty)}>{question.difficulty}</span>
          {question.time_estimate && (
            <span className="v2-detail-time">
              <Clock className="v2-icon-xs" />
              예상 {question.time_estimate}
            </span>
          )}
        </div>
        <div className="v2-detail-header-right">
          <button className="v2-btn v2-btn-outline v2-btn-sm" onClick={onRegenerate} disabled={isLoadingQuestions}>
            <RefreshCw className="v2-btn-icon" />
            질문 재생성
          </button>
          <button className="v2-btn v2-btn-primary v2-btn-sm" onClick={onStartInterview} disabled={isLoadingQuestions}>
            <Play className="v2-btn-icon" />
            이 질문으로 모의면접 시작
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="v2-detail-body">
        {/* Section 1: 질문 전문 */}
        <div className="v2-detail-title">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {fmt.headline || question.question}
          </ReactMarkdown>
        </div>

        {/* Section 2: 요약 (detailsMarkdown이 있으면 bullet으로, 없으면 skip) */}
        {fmt.hasDetails && fmt.detailsMarkdown && (
          <div className="v2-detail-section-card">
            <span className="v2-detail-section-label">요약</span>
            <div className="v2-detail-markdown">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{fmt.detailsMarkdown}</ReactMarkdown>
            </div>
          </div>
        )}

        {/* Section 3: 근거 파일 */}
        {question.source_file && (
          <div className="v2-detail-source">
            <span className="v2-detail-source-label">📄 근거 파일</span>
            <File className="v2-icon-sm" style={{ color: 'var(--v2-text-muted)', flexShrink: 0 }} />
            <span className="v2-detail-source-path">{question.source_file}</span>
            {question.importance && (
              <span className={`v2-badge ${question.importance === 'high' ? 'v2-badge-arch' : 'v2-badge-default'}`}>
                {question.importance === 'high' ? 'CORE' : 'SUB'}
              </span>
            )}
          </div>
        )}

        {/* Section 4: 코드 스니펫 */}
        {question.code_snippet && (
          <div className="v2-code-block">
            <div className="v2-code-header">
              <File className="v2-icon-xs" />
              <span className="v2-truncate">{question.code_snippet.file_path}</span>
              {question.code_snippet.has_real_content === true && (
                <span className="v2-badge v2-badge-logic" style={{ marginLeft: 'auto' }}>실제 코드</span>
              )}
              {question.code_snippet.has_real_content === false && (
                <span className="v2-badge v2-badge-default" style={{ marginLeft: 'auto' }}>미리보기</span>
              )}
            </div>
            <pre className={`v2-code-pre ${expandedCode ? '' : 'collapsed'}`}>
              {question.code_snippet.content}
            </pre>
            {question.code_snippet.content && (
              <button className="v2-code-expand-btn" onClick={onToggleCode}>
                {expandedCode ? '코드 접기 ▲' : '코드 더 보기 ▼'}
              </button>
            )}
          </div>
        )}

        {/* Section 5: 핵심 답변 포인트 */}
        {question.expected_answer_points && question.expected_answer_points.length > 0 && (
          <div className="v2-detail-section-card">
            <span className="v2-detail-section-label">핵심 답변 포인트</span>
            <ol className="v2-answer-points">
              {question.expected_answer_points.map((pt, i) => (
                <li key={i}>{pt}</li>
              ))}
            </ol>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────

interface QuestionsMasterDetailProps {
  questions: Question[]
  selectedId: string | null
  onSelect: (id: string | null) => void
  onStartInterview: () => void
  onRegenerate: () => void
  isLoadingQuestions: boolean
  filterSearch: string
  filterCategory: string
  filterDifficulty: string
  onFilterSearch: (v: string) => void
  onFilterCategory: (v: string) => void
  onFilterDifficulty: (v: string) => void
  totalCount: number
}

export function QuestionsMasterDetail({
  questions, selectedId, onSelect,
  onStartInterview, onRegenerate, isLoadingQuestions,
  filterSearch, filterCategory, filterDifficulty,
  onFilterSearch, onFilterCategory, onFilterDifficulty,
  totalCount,
}: QuestionsMasterDetailProps) {
  const [expandedCode, setExpandedCode] = React.useState(false)

  const selectedQuestionById = selectedId ? questions.find(q => q.id === selectedId) ?? null : null
  const selectedQuestion = selectedQuestionById ?? (questions.length > 0 ? questions[0] : null)
  const effectiveSelectedId = selectedQuestion?.id ?? null
  const selectedIndex = selectedQuestion ? questions.findIndex(q => q.id === selectedQuestion.id) : -1

  // Reset code expand when question changes
  React.useEffect(() => { setExpandedCode(false) }, [effectiveSelectedId])

  // Always keep a selected question when list is available.
  React.useEffect(() => {
    if (questions.length === 0) {
      if (selectedId !== null) {
        onSelect(null)
      }
      return
    }

    const hasSelected = selectedId ? questions.some((question) => question.id === selectedId) : false
    if (!hasSelected) {
      onSelect(questions[0].id)
    }
  }, [questions, selectedId, onSelect])

  return (
    <div className="v2-qmd">
      {/* Split */}
      <div className="v2-qmd-split">
        {/* Left: List */}
        <div className="v2-qmd-list">
          <div className="v2-qmd-filter-bar">
            <div className="v2-qmd-search-wrap">
              <Search className="v2-icon-sm v2-qmd-search-icon" />
              <input
                type="text"
                className="v2-input v2-qmd-search-input"
                placeholder="질문 검색..."
                value={filterSearch}
                onChange={e => onFilterSearch(e.target.value)}
                aria-label="질문 검색"
              />
            </div>
            <select className="v2-select" value={filterCategory} onChange={e => onFilterCategory(e.target.value)} aria-label="유형 필터">
              <option value="all">전체 유형</option>
              <option value="technical">Technical</option>
              <option value="architectural">Architectural</option>
              <option value="scenario">Scenario</option>
              <option value="algorithm">Algorithm</option>
              <option value="system-design">System Design</option>
              <option value="code-review">Code Review</option>
              <option value="best-practices">Best Practices</option>
              <option value="debugging">Debugging</option>
            </select>
            <select className="v2-select" value={filterDifficulty} onChange={e => onFilterDifficulty(e.target.value)} aria-label="난이도 필터">
              <option value="all">전체 난이도</option>
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
            </select>
            <span className="v2-badge v2-badge-arch" style={{ borderRadius: 'var(--v2-radius-full)', flexShrink: 0 }}>
              {questions.length}/{totalCount}
            </span>
          </div>
          <div className="v2-qmd-list-scroll">
            {questions.length === 0 ? (
              <div className="v2-qmd-empty">
                <MessageSquare className="v2-icon-2xl v2-qmd-empty-icon" />
                <p className="v2-qmd-empty-title">
                  {isLoadingQuestions ? '질문 생성 중...' : totalCount === 0 ? '질문을 불러오는 중입니다' : '검색 결과가 없습니다'}
                </p>
                <p className="v2-qmd-empty-sub">
                  {isLoadingQuestions
                    ? 'AI가 저장소를 분석하고 있습니다'
                    : totalCount === 0
                      ? 'AI가 맞춤형 면접 질문을 준비하고 있습니다'
                      : '다른 검색어나 필터를 사용해보세요'}
                </p>
              </div>
            ) : (
              questions.map((q, i) => (
                <QuestionListCard
                  key={q.id}
                  question={q}
                  index={i}
                  isSelected={effectiveSelectedId === q.id}
                  onClick={() => onSelect(q.id)}
                />
              ))
            )}
          </div>
          <div className="v2-qmd-list-cta">
            <button
              className="v2-btn v2-btn-primary v2-btn-sm v2-qmd-start-btn"
              onClick={onStartInterview}
              disabled={isLoadingQuestions || questions.length === 0}
            >
              <Play className="v2-btn-icon" />
              {isLoadingQuestions ? '질문 준비 중...' : '면접 시작하기'}
            </button>
          </div>
        </div>

        {/* Right: Detail */}
        <div className="v2-qmd-detail">
          {selectedQuestion && selectedIndex >= 0 ? (
            <QuestionDetail
              question={selectedQuestion}
              index={selectedIndex}
              onStartInterview={onStartInterview}
              onRegenerate={onRegenerate}
              isLoadingQuestions={isLoadingQuestions}
              expandedCode={expandedCode}
              onToggleCode={() => setExpandedCode(p => !p)}
            />
          ) : (
            <div className="v2-qmd-detail-empty">
              <MessageSquare className="v2-icon-2xl v2-qmd-empty-icon" />
              <p className="v2-qmd-empty-title">질문을 선택하세요</p>
              <p className="v2-qmd-empty-sub">왼쪽 목록에서 질문을 클릭하면 상세 내용이 표시됩니다</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
