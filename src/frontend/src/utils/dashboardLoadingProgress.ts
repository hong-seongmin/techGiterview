import type {
  DashboardLoadingProgress,
  DashboardLoadingStep,
  LoadingStageKey,
} from '../types/dashboard'

interface LoadingStepTemplate {
  key: LoadingStageKey
  label: string
  weight: number
}

const ACTIVE_WEIGHT_FACTOR = 0.35

const ANALYSIS_STEP_TEMPLATES: LoadingStepTemplate[] = [
  { key: 'analysis_fetch', label: '저장소 정보 조회', weight: 35 },
  { key: 'files_fetch', label: '핵심 파일 요약', weight: 15 },
  { key: 'questions_check', label: '기존 질문 확인', weight: 20 },
  { key: 'questions_generate', label: 'AI 질문 생성', weight: 25 },
  { key: 'finalize', label: '결과 정리', weight: 5 },
]

const LIST_STEP_TEMPLATES: LoadingStepTemplate[] = [
  { key: 'analysis_list_fetch', label: '분석 목록 조회', weight: 100 },
]

const buildProgress = (
  mode: DashboardLoadingProgress['mode'],
  title: string,
  templates: LoadingStepTemplate[]
): DashboardLoadingProgress => {
  const steps: DashboardLoadingStep[] = templates.map((template) => ({
    key: template.key,
    label: template.label,
    status: 'pending',
  }))
  return {
    mode,
    title,
    percent: 0,
    steps,
    currentStepKey: steps[0].key,
    currentStepLabel: steps[0].label,
    startedAt: new Date().toISOString(),
  }
}

const recalculatePercent = (
  progress: DashboardLoadingProgress,
  templates: LoadingStepTemplate[]
): DashboardLoadingProgress => {
  const weightMap = new Map(templates.map((template) => [template.key, template.weight]))
  const doneWeight = progress.steps
    .filter((step) => step.status === 'done')
    .reduce((acc, step) => acc + (weightMap.get(step.key) || 0), 0)
  const activeStep = progress.steps.find((step) => step.status === 'active')
  const activeWeight = activeStep ? (weightMap.get(activeStep.key) || 0) * ACTIVE_WEIGHT_FACTOR : 0
  const hasFailedStep = progress.steps.some((step) => step.status === 'failed')
  const allDone = progress.steps.every((step) => step.status === 'done')
  const percent = allDone
    ? 100
    : Math.max(0, Math.min(99, Math.round(doneWeight + activeWeight)))

  return {
    ...progress,
    percent,
    ...(hasFailedStep ? {} : { error: undefined }),
  }
}

const getTemplatesFor = (progress: DashboardLoadingProgress): LoadingStepTemplate[] =>
  progress.mode === 'analysis' ? ANALYSIS_STEP_TEMPLATES : LIST_STEP_TEMPLATES

const updateStep = (
  progress: DashboardLoadingProgress,
  key: LoadingStageKey,
  updater: (step: DashboardLoadingStep) => DashboardLoadingStep
): DashboardLoadingProgress => {
  const updatedSteps = progress.steps.map((step) => (step.key === key ? updater(step) : step))
  const updatedStep = updatedSteps.find((step) => step.key === key)

  if (!updatedStep) {
    return progress
  }

  return recalculatePercent(
    {
      ...progress,
      steps: updatedSteps,
      currentStepKey: key,
      currentStepLabel: updatedStep.label,
      currentDetail: updatedStep.detail || progress.currentDetail,
    },
    getTemplatesFor(progress)
  )
}

export const createAnalysisLoadingProgress = (): DashboardLoadingProgress =>
  buildProgress('analysis', '분석 결과 로딩 중', ANALYSIS_STEP_TEMPLATES)

export const createAnalysisListLoadingProgress = (): DashboardLoadingProgress =>
  buildProgress('analysis_list', '분석 목록 로딩 중', LIST_STEP_TEMPLATES)

export const activateLoadingStep = (
  progress: DashboardLoadingProgress,
  key: LoadingStageKey,
  detail?: string
): DashboardLoadingProgress => {
  const resetPreviousActive = progress.steps.map((step) => {
    if (step.status === 'active' && step.key !== key) {
      return { ...step, status: 'pending' as const }
    }
    return step
  })

  const next = {
    ...progress,
    steps: resetPreviousActive,
    attempt: undefined,
  }

  return updateStep(next, key, (step) => ({
    ...step,
    status: step.status === 'done' ? 'done' : 'active',
    detail: detail || step.detail,
  }))
}

export const completeLoadingStep = (
  progress: DashboardLoadingProgress,
  key: LoadingStageKey,
  detail?: string
): DashboardLoadingProgress =>
  updateStep(progress, key, (step) => ({
    ...step,
    status: 'done',
    detail: detail || step.detail,
  }))

export const failLoadingStep = (
  progress: DashboardLoadingProgress,
  key: LoadingStageKey,
  errorMessage: string
): DashboardLoadingProgress => {
  const next = updateStep(progress, key, (step) => ({
    ...step,
    status: 'failed',
    detail: errorMessage,
  }))

  return {
    ...next,
    error: errorMessage,
    currentDetail: errorMessage,
    attempt: undefined,
  }
}

export const setLoadingStepDetail = (
  progress: DashboardLoadingProgress,
  key: LoadingStageKey,
  detail: string
): DashboardLoadingProgress =>
  updateStep(progress, key, (step) => ({
    ...step,
    detail,
  }))

export const setLoadingAttempt = (
  progress: DashboardLoadingProgress,
  current: number,
  total: number
): DashboardLoadingProgress => ({
  ...progress,
  attempt: {
    current,
    total,
  },
})
