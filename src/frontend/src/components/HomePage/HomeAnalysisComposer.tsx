import React from 'react'
import { AIModelSelector } from './AIModelSelector'
import { ApiKeySetupCard } from './ApiKeySetupCard'
import { RepositoryAnalysisForm } from './RepositoryAnalysisForm'
import { SampleRepositoriesSection } from './SampleRepositoriesSection'

interface AIProvider {
  id: string
  name: string
  model: string
  status: string
  recommended?: boolean
}

interface HomeAnalysisComposerProps {
  compact?: boolean
  providers: AIProvider[]
  selectedAI: string
  isLoadingProviders: boolean
  repoUrl: string
  displayRepoUrl?: string
  isAnalyzing: boolean
  needsApiKeySetup: boolean
  isUsingLocalData: boolean
  error: Error | string | null
  onRepoUrlChange: (url: string) => void
  onSubmit: (event: React.FormEvent) => void
  onShowApiKeySetup: () => void
  onSelectedAIChange: (aiId: string) => void
  onRepoSelect: (url: string) => void
  onRepoHoverStart?: (url: string) => void
  onRepoHoverEnd?: () => void
}

export function HomeAnalysisComposer({
  compact = false,
  providers,
  selectedAI,
  isLoadingProviders,
  repoUrl,
  displayRepoUrl,
  isAnalyzing,
  needsApiKeySetup,
  isUsingLocalData,
  error,
  onRepoUrlChange,
  onSubmit,
  onShowApiKeySetup,
  onSelectedAIChange,
  onRepoSelect,
  onRepoHoverStart,
  onRepoHoverEnd,
}: HomeAnalysisComposerProps) {
  const [showAdvanced, setShowAdvanced] = React.useState(false)

  return (
    <section className={`home-composer ${compact ? 'home-composer--compact' : ''}`}>
      <ApiKeySetupCard
        variant="inline"
        showDescription={needsApiKeySetup}
        onShowApiKeySetup={onShowApiKeySetup}
        isUsingLocalData={isUsingLocalData}
        error={error}
        isLoading={isLoadingProviders}
        needsSetup={needsApiKeySetup}
        selectedAI={selectedAI}
        onToggleAdvanced={() => setShowAdvanced((prev) => !prev)}
        isAdvancedOpen={showAdvanced}
      />

      {showAdvanced ? (
        <div className="home-composer-advanced">
          <AIModelSelector
            providers={providers}
            selectedAI={selectedAI}
            onSelectedAIChange={onSelectedAIChange}
            isLoading={isLoadingProviders}
          />
        </div>
      ) : null}

      <div className="home-composer-body">
        <RepositoryAnalysisForm
          repoUrl={repoUrl}
          displayRepoUrl={displayRepoUrl}
          isAnalyzing={isAnalyzing}
          selectedAI={selectedAI}
          onRepoUrlChange={onRepoUrlChange}
          onSubmit={onSubmit}
        />
        <SampleRepositoriesSection
          onRepoSelect={onRepoSelect}
          onRepoHoverStart={onRepoHoverStart}
          onRepoHoverEnd={onRepoHoverEnd}
          isAnalyzing={isAnalyzing}
        />
      </div>
    </section>
  )
}
