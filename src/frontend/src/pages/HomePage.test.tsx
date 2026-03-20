import { render, screen } from '@testing-library/react'
import { vi } from 'vitest'
import { HomePage } from './HomePage'

const mockNavigate = vi.fn()
const mockUsePageInitialization = vi.fn()
const mockUseQuickAccessDataWithCache = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

vi.mock('../hooks/usePageInitialization', () => ({
  usePageInitialization: (...args: unknown[]) => mockUsePageInitialization(...args),
}))

vi.mock('../hooks/useQuickAccessData', () => ({
  useQuickAccessDataWithCache: (...args: unknown[]) => mockUseQuickAccessDataWithCache(...args),
}))

vi.mock('../components/ApiKeySetup', () => ({
  ApiKeySetup: () => <div data-testid="api-key-setup-modal">api-key-setup</div>,
}))

vi.mock('../components/HomePage', () => ({
  HomePageFooter: () => <div data-testid="home-footer">footer</div>,
  HomeAnalysisComposer: ({ compact = false }: { compact?: boolean }) => (
    <div data-testid={compact ? 'home-composer-compact' : 'home-composer-default'}>composer</div>
  ),
  HomeContinueCard: () => <div data-testid="home-continue-card">continue-card</div>,
  HomePageNavbar: () => <div data-testid="home-navbar">navbar</div>,
}))

vi.mock('../components/v2/QuickAccessPanels', () => ({
  RecentAnalysesPanel: () => <div data-testid="recent-analyses-panel">recent-analyses</div>,
  RecentReportsPanel: () => <div data-testid="recent-reports-panel">recent-reports</div>,
}))

vi.mock('../components/v2/QuickAccessV2', () => ({
  QuickAccessV2: () => <div data-testid="quick-access-v2">quick-access</div>,
}))

const createInitializationState = () => ({
  config: { keys_required: true },
  providers: [
    {
      id: 'upstage-solar-pro3',
      name: 'Upstage Solar Pro3',
      model: 'solar-pro3-260126',
      status: 'ready',
      recommended: true,
    },
  ],
  selectedAI: 'upstage-solar-pro3',
  setSelectedAI: vi.fn(),
  isLoading: false,
  error: null,
  isUsingLocalData: false,
  hasStoredKeys: () => true,
})

describe('HomePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUsePageInitialization.mockReturnValue(createInitializationState())
  })

  it('renders the first-visit hero when there is no recent history', () => {
    mockUseQuickAccessDataWithCache.mockReturnValue({
      data: { recent_analyses: [], recent_reports: [] },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<HomePage />)

    expect(screen.getByText('분석할 GitHub 저장소를 입력하세요')).toBeInTheDocument()
    expect(screen.getByTestId('home-composer-default')).toBeInTheDocument()
    expect(screen.getByTestId('quick-access-v2')).toBeInTheDocument()
    expect(screen.queryByTestId('home-continue-card')).not.toBeInTheDocument()
  })

  it('renders the returning-user layout when recent activity exists', () => {
    mockUseQuickAccessDataWithCache.mockReturnValue({
      data: {
        recent_analyses: [
          {
            analysis_id: 'analysis-1',
            repository_name: 'repo',
            repository_owner: 'owner',
            created_at: new Date().toISOString(),
            tech_stack: ['React'],
            file_count: 12,
            primary_language: 'TypeScript',
          },
        ],
        recent_reports: [],
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<HomePage />)

    expect(screen.getByTestId('home-composer-compact')).toBeInTheDocument()
    expect(screen.getByTestId('home-continue-card')).toBeInTheDocument()
    expect(screen.getByTestId('recent-analyses-panel')).toBeInTheDocument()
    expect(screen.getByTestId('recent-reports-panel')).toBeInTheDocument()
    expect(screen.queryByText('분석할 GitHub 저장소를 입력하세요')).not.toBeInTheDocument()
  })
})
