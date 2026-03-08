import { render, screen } from '@testing-library/react'
import { LoadingState } from './LoadingState'
import type { DashboardLoadingProgress } from '../../types/dashboard'

const progressModel: DashboardLoadingProgress = {
  mode: 'analysis',
  title: '분석 결과 로딩 중',
  percent: 62,
  steps: [
    { key: 'analysis_fetch', label: '저장소 정보 조회', status: 'done', detail: '조회 완료' },
    { key: 'files_fetch', label: '핵심 파일 요약', status: 'active', detail: '핵심 파일 요약 중' },
    { key: 'questions_check', label: '기존 질문 확인', status: 'pending' },
    { key: 'questions_generate', label: 'AI 질문 생성', status: 'pending' },
    { key: 'finalize', label: '결과 정리', status: 'pending' },
  ],
  currentStepKey: 'files_fetch',
  currentStepLabel: '핵심 파일 요약',
  currentDetail: '핵심 파일 요약 중',
  startedAt: new Date(Date.now() - 12_000).toISOString(),
  attempt: {
    current: 2,
    total: 12,
  },
}

describe('LoadingState', () => {
  it('renders detailed progress with actual step statuses', () => {
    render(<LoadingState progressModel={progressModel} />)

    expect(screen.getByText('📊 분석 결과 로딩 중')).toBeInTheDocument()
    expect(screen.getByTestId('loading-percent')).toHaveTextContent('62%')
    expect(
      screen.getByText('핵심 파일 요약 중', { selector: '.v2-loading-hint' })
    ).toBeInTheDocument()
    expect(screen.getByText(/재시도 2\/12/)).toBeInTheDocument()

    const doneStep = screen.getByText('저장소 정보 조회').closest('.v2-loading-step')
    const activeStep = screen.getByText('핵심 파일 요약').closest('.v2-loading-step')

    expect(doneStep).toHaveClass('v2-loading-step--done')
    expect(activeStep).toHaveClass('v2-loading-step--active')
  })
})
