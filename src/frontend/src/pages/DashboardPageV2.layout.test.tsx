import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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

vi.mock('../components/v2/QuestionsMasterDetail', () => ({
  QuestionsMasterDetail: () => <div data-testid="questions-master-detail">questions-master-detail</div>,
}))

vi.mock('../components/v2/RepositoryInfoDrawer', () => ({
  RepositoryInfoDrawer: ({ open }: { open: boolean }) =>
    open ? <div data-testid="repository-info-drawer">repository-info-drawer</div> : null,
}))

vi.mock('../components/FileContentModal', () => ({
  FileContentModal: () => <div data-testid="file-content-modal">file-modal</div>,
}))

describe('DashboardPageV2 layout', () => {
  let dashboardState: Record<string, any>

  beforeEach(() => {
    vi.clearAllMocks()

    dashboardState = {
      analysisResult: {
        analysis_id: 'analysis-123',
        repo_info: {
          owner: 'owner',
          name: 'repo',
          description: 'desc',
          language: 'TypeScript',
          stars: 1200,
          forks: 300,
          size: 2048,
          topics: ['react'],
          default_branch: 'main',
        },
        tech_stack: { React: 0.9, TypeScript: 0.8, Vite: 0.4 },
        key_files: [{ path: 'src/app.tsx', type: 'file', size: 10 }],
        recommendations: ['Focus on state flow'],
        summary: 'summary',
        created_at: new Date().toISOString(),
        success: true,
      },
      isLoadingAnalysis: false,
      isLoadingAllAnalyses: false,
      loadingProgress: null,
      error: null,
      allAnalyses: [],
      questions: [
        {
          id: 'q-1',
          type: 'technical',
          question: '질문 1',
          difficulty: 'medium',
        },
      ],
      isLoadingQuestions: false,
      questionsGenerated: true,
      filteredQuestions: [
        {
          id: 'q-1',
          type: 'technical',
          question: '질문 1',
          difficulty: 'medium',
        },
      ],
      selectedQuestionId: 'q-1',
      questionSearch: '',
      questionCategory: 'all',
      questionDifficulty: 'all',
      activeMainTab: 'questions',
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
    }

    mockUseDashboard.mockReturnValue(dashboardState)
  })

  it('centers the layout on one primary interview CTA and opens the repository drawer on demand', async () => {
    const user = userEvent.setup()

    render(<DashboardPageV2 />)

    expect(screen.getByRole('button', { name: /전체 모의면접 시작/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '질문' })).toBeInTheDocument()
    expect(screen.getByText('핵심 파일')).toBeInTheDocument()
    expect(screen.getByTestId('questions-master-detail')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /저장소 정보/i }))

    expect(screen.getByTestId('repository-info-drawer')).toBeInTheDocument()
    await waitFor(() => {
      expect(dashboardState.loadAllFiles).toHaveBeenCalledTimes(1)
    })
  })
})
