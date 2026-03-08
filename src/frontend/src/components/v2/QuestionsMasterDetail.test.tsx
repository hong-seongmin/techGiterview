import { render, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import { QuestionsMasterDetail } from './QuestionsMasterDetail'
import type { Question } from '../../types/dashboard'

const baseQuestion: Question = {
  id: 'q-1',
  type: 'technical',
  question: '**질문:** React 상태 업데이트 흐름을 설명해 주세요.',
  difficulty: 'medium',
  time_estimate: '5분',
  source_file: 'src/app.tsx',
  expected_answer_points: ['state batching', 'render scheduling'],
}

function renderComponent(overrides: Partial<React.ComponentProps<typeof QuestionsMasterDetail>> = {}) {
  const onSelect = vi.fn()
  const onRegenerate = vi.fn()

  render(
    <QuestionsMasterDetail
      questions={[baseQuestion]}
      selectedId={null}
      onSelect={onSelect}
      onRegenerate={onRegenerate}
      isLoadingQuestions={false}
      filterSearch=""
      filterCategory="all"
      filterDifficulty="all"
      onFilterSearch={vi.fn()}
      onFilterCategory={vi.fn()}
      onFilterDifficulty={vi.fn()}
      totalCount={1}
      {...overrides}
    />
  )

  return { onSelect, onRegenerate }
}

describe('QuestionsMasterDetail', () => {
  it('auto-selects the first question and keeps the detail CTA focused on regenerate only', async () => {
    const { onSelect } = renderComponent()

    await waitFor(() => {
      expect(onSelect).toHaveBeenCalledWith('q-1')
    })

    expect(screen.getByRole('button', { name: '질문 재생성' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /면접 시작하기/i })).not.toBeInTheDocument()
  })

  it('shows the loading empty state when no questions exist yet', () => {
    renderComponent({
      questions: [],
      totalCount: 0,
      isLoadingQuestions: true,
    })

    expect(screen.getByText('질문 생성 중...')).toBeInTheDocument()
    expect(screen.getByText('AI가 저장소를 분석하고 있습니다')).toBeInTheDocument()
  })
})
