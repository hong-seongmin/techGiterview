import { render, screen } from '@testing-library/react'
import { SiteFooter } from './SiteFooter'

describe('SiteFooter', () => {
  it('renders brand, core sections, and legal links', () => {
    render(<SiteFooter />)

    expect(screen.getByText('TechGiterview')).toBeInTheDocument()
    expect(screen.getByText('기능')).toBeInTheDocument()
    expect(screen.getByText('지원 기술')).toBeInTheDocument()
    expect(screen.getByText('연락처')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'README' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'LICENSE' })).toBeInTheDocument()
  })

  it('opens external contact links in new tab with noopener noreferrer', () => {
    render(<SiteFooter />)

    const repoLink = screen.getByRole('link', { name: /GitHub Repository/i })
    expect(repoLink).toHaveAttribute('target', '_blank')
    expect(repoLink).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('renders compact variant with slim quick links', () => {
    render(<SiteFooter variant="compact" />)

    expect(screen.getByRole('link', { name: 'README' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'LICENSE' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'GitHub' })).toBeInTheDocument()
    expect(screen.queryByText('지원 기술')).not.toBeInTheDocument()
  })
})
