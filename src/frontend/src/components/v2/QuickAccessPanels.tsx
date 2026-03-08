import {
  ArrowRight,
  CheckCircle2,
  Clock3,
  GitBranch,
  Star,
  TrendingUp,
} from 'lucide-react'
import type { RecentAnalysis, RecentReport } from '../../types/dashboard'

export const formatRelativeDate = (dateString: string): string => {
  const date = new Date(dateString)
  const now = new Date()
  const diffTime = Math.abs(now.getTime() - date.getTime())
  const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return '오늘'
  if (diffDays === 1) return '어제'
  if (diffDays < 7) return `${diffDays}일 전`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}주 전`
  return date.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })
}

export const formatDuration = (minutes: number): string => {
  if (minutes < 60) return `${minutes}분`
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  return mins > 0 ? `${hours}시간 ${mins}분` : `${hours}시간`
}

interface RecentAnalysesPanelProps {
  analyses: RecentAnalysis[]
  onOpenAnalysis: (analysis: RecentAnalysis) => void
  onOpenAll?: () => void
  compact?: boolean
}

interface RecentReportsPanelProps {
  reports: RecentReport[]
  onOpenReport: (report: RecentReport) => void
  onOpenAll?: () => void
  compact?: boolean
}

export function RecentAnalysesPanel({
  analyses,
  onOpenAnalysis,
  onOpenAll,
  compact = false,
}: RecentAnalysesPanelProps) {
  const items = compact ? analyses.slice(0, 3) : analyses

  return (
    <article className="v2-qa-card">
      <div className="v2-qa-card-head">
        <div className="v2-qa-card-title">
          <GitBranch className="v2-icon-sm" />
          <h3>최근 분석</h3>
        </div>
        {onOpenAll ? (
          <button className="v2-btn v2-btn-ghost v2-btn-sm" onClick={onOpenAll}>
            전체보기
          </button>
        ) : null}
      </div>
      <div className="v2-qa-list">
        {items.length > 0 ? (
          items.map((analysis) => (
            <button
              key={analysis.analysis_id}
              className="v2-qa-item"
              onClick={() => onOpenAnalysis(analysis)}
              aria-label={`${analysis.repository_owner}/${analysis.repository_name} 분석 결과 보기`}
            >
              <div className="v2-qa-item-main">
                <div className="v2-qa-item-title">
                  {analysis.repository_owner}/{analysis.repository_name}
                </div>
                <div className="v2-qa-item-meta">
                  <span className="v2-qa-meta-chip">
                    <Clock3 className="v2-icon-xs" />
                    {formatRelativeDate(analysis.created_at)}
                  </span>
                  <span className="v2-qa-meta-chip">{analysis.primary_language}</span>
                  <span className="v2-qa-meta-chip">{analysis.file_count}개 파일</span>
                </div>
              </div>
              <ArrowRight className="v2-icon-xs" />
            </button>
          ))
        ) : (
          <div className="v2-qa-empty">
            <p>최근 분석이 없습니다. 첫 저장소 분석을 시작해보세요.</p>
          </div>
        )}
      </div>
    </article>
  )
}

export function RecentReportsPanel({
  reports,
  onOpenReport,
  onOpenAll,
  compact = false,
}: RecentReportsPanelProps) {
  const items = compact ? reports.slice(0, 3) : reports

  return (
    <article className="v2-qa-card">
      <div className="v2-qa-card-head">
        <div className="v2-qa-card-title">
          <TrendingUp className="v2-icon-sm" />
          <h3>최근 면접</h3>
        </div>
        {onOpenAll ? (
          <button className="v2-btn v2-btn-ghost v2-btn-sm" onClick={onOpenAll}>
            전체보기
          </button>
        ) : null}
      </div>
      <div className="v2-qa-list">
        {items.length > 0 ? (
          items.map((report) => (
            <button
              key={report.interview_id}
              className="v2-qa-item"
              onClick={() => onOpenReport(report)}
              aria-label={`${report.repository_owner}/${report.repository_name} 면접 리포트 보기`}
            >
              <div className="v2-qa-item-main">
                <div className="v2-qa-item-title">
                  {report.repository_owner}/{report.repository_name}
                </div>
                <div className="v2-qa-item-meta">
                  <span className="v2-qa-meta-chip">
                    <Clock3 className="v2-icon-xs" />
                    {formatRelativeDate(report.completed_at)}
                  </span>
                  <span className="v2-qa-meta-chip">
                    <Star className="v2-icon-xs" />
                    {formatDuration(report.duration_minutes)}
                  </span>
                  <span className="v2-qa-meta-chip">
                    <CheckCircle2 className="v2-icon-xs" />
                    {report.answers_count}/{report.questions_count}
                  </span>
                </div>
              </div>
              <ArrowRight className="v2-icon-xs" />
            </button>
          ))
        ) : (
          <div className="v2-qa-empty">
            <p>아직 완료된 면접이 없습니다. 질문을 생성하고 첫 모의면접을 시작해보세요.</p>
          </div>
        )}
      </div>
    </article>
  )
}
