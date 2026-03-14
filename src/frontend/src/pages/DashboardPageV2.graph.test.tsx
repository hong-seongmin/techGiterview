import { render, screen } from '@testing-library/react'
import { vi } from 'vitest'
import { DashboardPageV2 } from './DashboardPageV2'

const mockNavigate = vi.fn()
const mockUseDashboard = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useParams: () => ({ analysisId: 'analysis-123' }),
    useNavigate: () => mockNavigate,
  }
})

vi.mock('../hooks/useDashboard', () => ({
  useDashboard: (...args: unknown[]) => mockUseDashboard(...args),
}))

vi.mock('../components/CodeGraphViewer', () => ({
  default: () => <div data-testid="code-graph-viewer">code-graph-viewer</div>,
}))

vi.mock('../components/v2/QuestionsMasterDetail', () => ({
  QuestionsMasterDetail: () => <div data-testid="questions-master-detail">questions-master-detail</div>,
}))

vi.mock('../components/v2/RepositoryInfoDrawer', () => ({
  RepositoryInfoDrawer: () => null,
}))

vi.mock('../components/FileContentModal', () => ({
  FileContentModal: () => null,
}))

function createDashboardState(overrides: Record<string, unknown> = {}) {
  return {
    analysisResult: {
      analysis_id: 'analysis-123',
      repo_info: {
        owner: 'owner',
        name: 'repo',
        description: 'desc',
        language: 'TypeScript',
        stars: 1,
        forks: 1,
        size: 1,
        topics: [],
        default_branch: 'main',
      },
      tech_stack: { TypeScript: 1 },
      key_files: [{ path: 'src/app.ts', type: 'file', size: 10 }],
      recommendations: ['rec'],
      summary: 'summary',
      created_at: new Date().toISOString(),
      success: true,
    },
    isLoadingAnalysis: false,
    isLoadingAllAnalyses: false,
    loadingProgress: null,
    error: null,
    allAnalyses: [],
    questions: [],
    isLoadingQuestions: false,
    questionsGenerated: true,
    filteredQuestions: [],
    selectedQuestionId: null,
    questionSearch: '',
    questionCategory: 'all',
    questionDifficulty: 'all',
    activeMainTab: 'graph',
    graphData: null,
    graphStatus: 'idle',
    isLoadingGraph: false,
    allFiles: [],
    isLoadingAllFiles: false,
    expandedFolders: new Set<string>(),
    searchTerm: '',
    isFileModalOpen: false,
    selectedFilePath: '',
    startInterview: vi.fn(),
    regenerateQuestions: vi.fn(),
    loadOrGenerateQuestions: vi.fn(),
    fetchGraphData: vi.fn(),
    loadAllFiles: vi.fn(),
    handleSearch: vi.fn(),
    toggleFolder: vi.fn(),
    handleFileClick: vi.fn(),
    closeFileModal: vi.fn(),
    setActiveMainTab: vi.fn(),
    setSelectedQuestionId: vi.fn(),
    setQuestionSearch: vi.fn(),
    setQuestionCategory: vi.fn(),
    setQuestionDifficulty: vi.fn(),
    ...overrides,
  }
}

describe('DashboardPageV2 graph states', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the graph viewer when graph data is ready', () => {
    mockUseDashboard.mockReturnValue(
      createDashboardState({
        graphStatus: 'loaded',
        graphData: {
          state: 'ready',
          message: null,
          nodes: [{ id: 'src/app.ts', name: 'app.ts', val: 0.8, type: 'logic', density: 0.4 }],
          links: [],
        },
      })
    )

    render(<DashboardPageV2 />)

    expect(screen.getByTestId('code-graph-viewer')).toBeInTheDocument()
  })

  it('renders an empty-graph explanation when no dependency graph can be built', () => {
    mockUseDashboard.mockReturnValue(
      createDashboardState({
        graphStatus: 'empty',
        graphData: {
          state: 'empty',
          message: '핵심 파일 간 분석 가능한 의존성 관계를 찾지 못했습니다.',
          nodes: [],
          links: [],
        },
      })
    )

    render(<DashboardPageV2 />)

    expect(screen.getByText('그래프화할 의존성 관계를 찾지 못했습니다.')).toBeInTheDocument()
    expect(screen.queryByText('현재 서버에는 코드 그래프 API가 없습니다.')).not.toBeInTheDocument()
  })

  it('renders a reanalysis notice for persisted analyses without source file contents', () => {
    mockUseDashboard.mockReturnValue(
      createDashboardState({
        graphStatus: 'needs_reanalysis',
        graphData: {
          state: 'requires_reanalysis',
          message: '이 분석은 현재 서버 세션에 원본 파일 내용이 없어 코드 그래프를 다시 만들 수 없습니다.',
          nodes: [],
          links: [],
        },
      })
    )

    render(<DashboardPageV2 />)

    expect(screen.getByText('이 분석은 그래프를 재구성할 원본 파일 내용이 없습니다.')).toBeInTheDocument()
  })

  it('renders an error state when the graph request fails', () => {
    mockUseDashboard.mockReturnValue(
      createDashboardState({
        graphStatus: 'error',
      })
    )

    render(<DashboardPageV2 />)

    expect(screen.getByText('코드 그래프를 불러오지 못했습니다.')).toBeInTheDocument()
  })
})
