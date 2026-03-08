import React from 'react'
import { ArrowRight, Clock3, FileText, PlayCircle } from 'lucide-react'
import type { RecentAnalysis, RecentReport } from '../../types/dashboard'
import { formatDuration, formatRelativeDate } from '../v2/QuickAccessPanels'

interface HomeContinueCardProps {
  latestAnalysis: RecentAnalysis | null
  latestReport: RecentReport | null
  onContinueAnalysis: (analysis: RecentAnalysis) => void
  onOpenReport: (report: RecentReport) => void
}

export const HomeContinueCard: React.FC<HomeContinueCardProps> = ({
  latestAnalysis,
  latestReport,
  onContinueAnalysis,
  onOpenReport,
}) => {
  return (
    <aside className="home-continue-card">
      <div className="home-continue-card-head">
        <span className="home-continue-kicker">Continue</span>
        <h2>최근 작업 이어서 보기</h2>
        <p>가장 최근 분석으로 바로 돌아가 질문을 검토하고 면접 흐름을 이어갑니다.</p>
      </div>

      {latestAnalysis ? (
        <button
          className="home-continue-primary"
          onClick={() => onContinueAnalysis(latestAnalysis)}
          aria-label={`${latestAnalysis.repository_owner}/${latestAnalysis.repository_name} 분석 이어서 보기`}
        >
          <div className="home-continue-primary-icon">
            <PlayCircle className="v2-icon-md" />
          </div>
          <div className="home-continue-primary-body">
            <div className="home-continue-primary-title">
              {latestAnalysis.repository_owner}/{latestAnalysis.repository_name}
            </div>
            <div className="home-continue-primary-meta">
              <span>{latestAnalysis.primary_language}</span>
              <span>
                <Clock3 className="v2-icon-xs" />
                {formatRelativeDate(latestAnalysis.created_at)}
              </span>
            </div>
          </div>
          <ArrowRight className="v2-icon-sm" />
        </button>
      ) : (
        <div className="home-continue-empty">
          <FileText className="v2-icon-sm" />
          <p>아직 이어서 볼 분석 결과가 없습니다.</p>
        </div>
      )}

      {latestReport ? (
        <button
          className="home-continue-secondary"
          onClick={() => onOpenReport(latestReport)}
          aria-label={`${latestReport.repository_owner}/${latestReport.repository_name} 최근 면접 리포트 보기`}
        >
          <div className="home-continue-secondary-copy">
            <span className="home-continue-secondary-label">최근 리포트</span>
            <strong>
              {latestReport.repository_owner}/{latestReport.repository_name}
            </strong>
            <span>
              {formatDuration(latestReport.duration_minutes)} ·{' '}
              {formatRelativeDate(latestReport.completed_at)}
            </span>
          </div>
          <ArrowRight className="v2-icon-sm" />
        </button>
      ) : null}
    </aside>
  )
}
