import './DashboardSummaryStrip.css'

interface DashboardSummaryStripProps {
  techStack: Record<string, number>
  questionCount: number
  keyFileCount: number
  recommendationCount: number
}

export function DashboardSummaryStrip({
  techStack,
  questionCount,
  keyFileCount,
  recommendationCount,
}: DashboardSummaryStripProps) {
  const topTech = Object.entries(techStack || {})
    .sort(([, a], [, b]) => b - a)
    .slice(0, 3)
    .map(([name]) => name)

  return (
    <section className="dashboard-summary-strip" aria-label="분석 요약">
      <div className="dashboard-summary-item dashboard-summary-item--accent">
        <span className="dashboard-summary-label">질문</span>
        <strong>{questionCount}</strong>
      </div>
      <div className="dashboard-summary-item">
        <span className="dashboard-summary-label">핵심 파일</span>
        <strong>{keyFileCount}</strong>
      </div>
      <div className="dashboard-summary-item">
        <span className="dashboard-summary-label">인사이트</span>
        <strong>{recommendationCount}</strong>
      </div>
      <div className="dashboard-summary-item dashboard-summary-item--tech">
        <span className="dashboard-summary-label">기술 스택</span>
        <strong>{topTech.length > 0 ? topTech.join(' · ') : '분석 중'}</strong>
      </div>
    </section>
  )
}
