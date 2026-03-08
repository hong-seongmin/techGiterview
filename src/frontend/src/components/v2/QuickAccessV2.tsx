import { useNavigate } from 'react-router-dom'
import {
  AlertCircle,
  FileText,
} from 'lucide-react'
import { useQuickAccessDataWithCache } from '../../hooks/useQuickAccessData'
import { setAnalysisToken } from '../../utils/apiHeaders'
import type { RecentAnalysis, RecentReport } from '../../types/dashboard'
import { RecentAnalysesPanel, RecentReportsPanel } from './QuickAccessPanels'
import './QuickAccessV2.css'

interface QuickAccessV2Props {
  limit?: number
}

export function QuickAccessV2({ limit = 3 }: QuickAccessV2Props) {
  const navigate = useNavigate()
  const { data, isLoading, error, refetch } = useQuickAccessDataWithCache(limit)

  const handleAnalysisClick = (analysis: RecentAnalysis) => {
    if (analysis.analysis_token) {
      setAnalysisToken(analysis.analysis_id, analysis.analysis_token)
    }
    navigate(`/dashboard/${analysis.analysis_id}`)
  }

  const handleReportClick = (report: RecentReport) => {
    navigate(`/reports?interview=${report.interview_id}`)
  }

  if (isLoading) {
    return (
      <section className="v2-qa" aria-label="최근 활동">
        <div className="v2-qa-header">
          <h2>최근 활동</h2>
          <p>최근 분석 및 면접 결과를 빠르게 확인하세요</p>
        </div>
        <div className="v2-qa-state">
          <div className="v2-spinner" />
          <p>활동 데이터를 불러오는 중입니다...</p>
        </div>
      </section>
    )
  }

  if (error) {
    return (
      <section className="v2-qa" aria-label="최근 활동">
        <div className="v2-qa-header">
          <h2>최근 활동</h2>
          <p>최근 분석 및 면접 결과를 빠르게 확인하세요</p>
        </div>
        <div className="v2-qa-state v2-qa-state--error">
          <AlertCircle className="v2-icon-sm" />
          <p>{error}</p>
          <button className="v2-btn v2-btn-outline v2-btn-sm" onClick={refetch}>
            다시 시도
          </button>
        </div>
      </section>
    )
  }

  const hasData = data.recent_analyses.length > 0 || data.recent_reports.length > 0
  if (!hasData) {
    return (
      <section className="v2-qa" aria-label="최근 활동">
        <div className="v2-qa-header">
          <h2>최근 활동</h2>
          <p>최근 분석 및 면접 결과를 빠르게 확인하세요</p>
        </div>
        <div className="v2-qa-state">
          <FileText className="v2-icon-sm" />
          <p>아직 활동 데이터가 없습니다. 저장소 분석을 시작해보세요.</p>
          <button className="v2-btn v2-btn-primary v2-btn-sm" onClick={() => navigate('/')}>
            저장소 분석 시작
          </button>
        </div>
      </section>
    )
  }

  return (
    <section className="v2-qa" aria-label="최근 활동">
      <div className="v2-qa-header">
        <h2>최근 활동</h2>
        <p>최근 분석 및 면접 결과를 빠르게 확인하세요</p>
      </div>

      <div className="v2-qa-grid">
        <RecentAnalysesPanel
          analyses={data.recent_analyses}
          onOpenAnalysis={handleAnalysisClick}
          onOpenAll={() => navigate('/dashboard')}
        />

        <RecentReportsPanel
          reports={data.recent_reports}
          onOpenReport={handleReportClick}
          onOpenAll={() => navigate('/reports')}
        />
      </div>
    </section>
  )
}
