import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { HomePageNavbar } from './HomePageNavbar'

describe('HomePageNavbar', () => {
  it('opens settings when the action button is clicked', async () => {
    const user = userEvent.setup()
    const onShowApiKeySetup = vi.fn()

    render(
      <HomePageNavbar
        onShowApiKeySetup={onShowApiKeySetup}
        needsApiKeySetup={false}
        isConnected={true}
      />
    )

    await user.click(screen.getByRole('button', { name: '설정' }))
    expect(onShowApiKeySetup).toHaveBeenCalledTimes(1)
  })

  it('shows warning label when API setup is required', () => {
    render(
      <HomePageNavbar
        onShowApiKeySetup={vi.fn()}
        needsApiKeySetup={true}
        isConnected={false}
      />
    )

    expect(screen.getByText('API 설정 필요')).toBeInTheDocument()
  })

  it('renders top navigation links with active analysis tab', () => {
    render(
      <HomePageNavbar
        onShowApiKeySetup={vi.fn()}
        needsApiKeySetup={false}
        isConnected={true}
      />
    )

    const analysisLink = screen.getByRole('link', { name: '분석' })
    const reportsLink = screen.getByRole('link', { name: '내 기록' })
    const guideButton = screen.getByRole('button', { name: '가이드' })

    expect(analysisLink).toHaveClass('navbar-nav-link--active')
    expect(reportsLink).toHaveAttribute('href', '/reports')
    expect(guideButton).toBeDisabled()
    expect(screen.queryByText(/Upstage Solar|Gemini/i)).not.toBeInTheDocument()
  })
})
