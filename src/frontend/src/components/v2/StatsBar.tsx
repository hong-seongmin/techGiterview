import './StatsBar.css'

interface StatsBarProps {
  techStack: Record<string, number>
  questionCount: number
  keyFileCount: number
  recommendationCount: number
  language?: string | null
  repoSize?: number
}

const TECH_COLORS = ['#3B82F6', '#22C55E', '#F59E0B', '#A78BFA', '#F87171', '#94A3B8']

export function StatsBar({ techStack, questionCount, keyFileCount, recommendationCount, language, repoSize }: StatsBarProps) {
  const techEntries = Object.entries(techStack || {}).sort(([,a],[,b]) => b - a).slice(0, 4)
  const topTech = techEntries.slice(0, 3)

  return (
    <div className="v2-stats-bar">
      {/* Tech Stack */}
      <div className="v2-stat-card v2-stat-card--tech">
        <div className="v2-label v2-stat-card-title">Tech Stack</div>
        {topTech.length > 0 ? (
          <div className="v2-tech-mini">
            {topTech.map(([tech, score], i) => (
              <div key={tech} className="v2-tech-mini-row">
                <span className="v2-tech-mini-name v2-truncate">{tech}</span>
                <div className="v2-mini-bar-track" style={{ flex: 1 }}>
                  <div
                    className="v2-mini-bar-fill"
                    style={{ width: `${Math.max(4, score * 100)}%`, background: TECH_COLORS[i] }}
                  />
                </div>
                <span className="v2-tech-mini-pct">{(score * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="v2-stat-empty">분석 중...</p>
        )}
      </div>

      {/* Questions */}
      <div className="v2-stat-card v2-stat-card--questions">
        <div className="v2-label v2-stat-card-title">Questions</div>
        <div className="v2-stat-value v2-stat-value--accent">{questionCount}</div>
        <div className="v2-stat-sub">생성된 면접 질문</div>
      </div>

      {/* Key Files */}
      <div className="v2-stat-card v2-stat-card--key-files">
        <div className="v2-label v2-stat-card-title">Key Files</div>
        <div className="v2-stat-value">{keyFileCount}</div>
        <div className="v2-stat-sub">
          {language && <span>{language}</span>}
          {repoSize ? <span> · {(repoSize / 1024).toFixed(1)} MB</span> : null}
        </div>
      </div>

      {/* Insights */}
      <div className="v2-stat-card v2-stat-card--insights">
        <div className="v2-label v2-stat-card-title">Insights</div>
        <div className="v2-stat-value v2-stat-value--success">{recommendationCount}</div>
        <div className="v2-stat-sub">개선 제안 항목</div>
      </div>
    </div>
  )
}
