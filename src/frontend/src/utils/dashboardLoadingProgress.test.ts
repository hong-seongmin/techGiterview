import {
  activateLoadingStep,
  completeLoadingStep,
  createAnalysisLoadingProgress,
  failLoadingStep,
  setLoadingAttempt,
} from './dashboardLoadingProgress'

describe('dashboardLoadingProgress', () => {
  it('increments progress as steps become active and done', () => {
    const initial = createAnalysisLoadingProgress()
    expect(initial.percent).toBe(0)

    const active = activateLoadingStep(initial, 'analysis_fetch', '저장소 조회 중')
    expect(active.steps.find((step) => step.key === 'analysis_fetch')?.status).toBe('active')
    expect(active.percent).toBeGreaterThan(0)

    const done = completeLoadingStep(active, 'analysis_fetch', '완료')
    expect(done.steps.find((step) => step.key === 'analysis_fetch')?.status).toBe('done')
    expect(done.percent).toBeGreaterThanOrEqual(20)
  })

  it('reaches 100 when all analysis steps are complete', () => {
    const stepKeys = [
      'analysis_fetch',
      'files_fetch',
      'questions_check',
      'questions_generate',
      'finalize',
    ] as const

    const completed = stepKeys.reduce(
      (acc, key) => completeLoadingStep(activateLoadingStep(acc, key), key),
      createAnalysisLoadingProgress()
    )

    expect(completed.percent).toBe(100)
    expect(completed.steps.every((step) => step.status === 'done')).toBe(true)
  })

  it('records failure and retry attempt metadata', () => {
    const base = createAnalysisLoadingProgress()
    const withAttempt = setLoadingAttempt(base, 3, 12)
    const failed = failLoadingStep(withAttempt, 'questions_generate', '질문 생성 실패')

    expect(failed.attempt).toBeUndefined()
    expect(failed.error).toBe('질문 생성 실패')
    expect(failed.steps.find((step) => step.key === 'questions_generate')?.status).toBe('failed')
  })
})
