export interface RepositoryInfo {
  name: string
  owner: string
  url?: string
  description: string | null
  language: string | null
  stars: number
  forks: number
  size: number
  topics: string[]
  default_branch: string
}

export interface FileInfo {
  path: string
  type: string
  size: number
  content?: string
  importance?: 'high' | 'medium' | 'low'
}

// SmartFileAnalysis 인터페이스 정의 (CriticalFilesPreview와 동일)
export interface SmartFileAnalysis {
  file_path: string
  importance_score: number
  reasons: string[]
  metrics: {
    structural_importance: number
    dependency_centrality: number
    churn_risk: number
    complexity_score: number
  }
  category: 'critical' | 'important' | 'moderate' | 'low'
  rank: number
}

export interface AnalysisResult {
  success: boolean
  analysis_id: string
  selected_provider_id?: string
  repo_info: RepositoryInfo
  tech_stack: Record<string, number>
  key_files: FileInfo[]
  summary: string
  recommendations: string[]
  created_at: string
  smart_file_analysis?: {
    critical_files: SmartFileAnalysis[]
    importance_distribution?: {
      mean: number
      median: number
      std_dev: number
      min: number
      max: number
    }
    categorized_files?: {
      critical: string[]
      important: string[]
      moderate: string[]
      low: string[]
    }
    summary?: {
      total_files_analyzed: number
      critical_files_count: number
      important_files_count: number
      average_importance: number
      highest_importance: number
    }
  }
}

export interface Question {
  id: string
  type: string
  question: string
  question_headline?: string
  question_details_markdown?: string
  question_has_details?: boolean
  difficulty: string
  context?: string
  time_estimate?: string
  code_snippet?: {
    content: string
    language: string
    file_path: string
    complexity: number
    has_real_content?: boolean
    content_unavailable_reason?: string
  }
  expected_answer_points?: string[]
  technology?: string
  pattern?: string
  // 서브 질문 관련 필드
  parent_question_id?: string
  sub_question_index?: number
  total_sub_questions?: number
  is_compound_question?: boolean
  // 파일 연관성 필드
  source_file?: string
  importance?: 'high' | 'medium' | 'low'
  generated_by?: string
}

export interface FileTreeNode {
  name: string
  path: string
  type: string // "file" or "dir"
  size?: number
  children?: FileTreeNode[]
}

// 분석 목록을 위한 인터페이스 (QuickAccessSection과 동일)
export interface RecentAnalysis {
  analysis_id: string
  analysis_token?: string
  repository_name: string
  repository_owner: string
  created_at: string
  tech_stack: string[]
  file_count: number
  primary_language: string
}

export type DifficultyLevel = 'easy' | 'medium' | 'hard' | 'beginner' | 'intermediate' | 'advanced' | 'normal' | 'low' | 'high'
export type TabType = 'questions' | 'graph'
export type CategoryFilter = 'all' | 'technical' | 'architectural' | 'scenario' | 'algorithm' | 'system-design' | 'code-review' | 'best-practices' | 'debugging'
export type DifficultyFilter = 'all' | 'easy' | 'medium' | 'hard'

export type LoadingStepStatus = 'pending' | 'active' | 'done' | 'failed'

export type LoadingStageKey =
  | 'analysis_fetch'
  | 'files_fetch'
  | 'questions_check'
  | 'questions_generate'
  | 'finalize'
  | 'analysis_list_fetch'

export interface DashboardLoadingStep {
  key: LoadingStageKey
  label: string
  status: LoadingStepStatus
  detail?: string
}

export interface DashboardLoadingProgress {
  mode: 'analysis' | 'analysis_list'
  title: string
  percent: number
  steps: DashboardLoadingStep[]
  currentStepKey: LoadingStageKey
  currentStepLabel: string
  currentDetail?: string
  startedAt: string
  attempt?: {
    current: number
    total: number
  }
  error?: string
}
