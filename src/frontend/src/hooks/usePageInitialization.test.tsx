import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useQuery } from '@tanstack/react-query'
import { usePageInitialization } from './usePageInitialization'
import { API_STORAGE_KEYS } from '../utils/apiHeaders'

vi.mock('@tanstack/react-query', () => ({
  useQuery: vi.fn(),
}))

describe('usePageInitialization', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.mocked(useQuery).mockReturnValue({
      data: {
        config: {
          keys_required: false,
          use_local_storage: true,
          missing_keys: {},
        },
        providers: [
          {
            id: 'upstage-solar-pro3',
            name: 'Upstage Solar Pro3 (추천)',
            model: 'solar-pro3-260126',
            status: 'ready',
            recommended: true,
          },
          {
            id: 'gemini-flash',
            name: 'Google Gemini 2.0 Flash',
            model: 'gemini-2.0-flash',
            status: 'ready',
            recommended: false,
          },
        ],
      },
      isLoading: false,
      error: null,
      isSuccess: true,
    } as never)
  })

  it('restores the exact stored ai selection first', async () => {
    localStorage.setItem(API_STORAGE_KEYS.SELECTED_AI_ID, 'gemini-flash')
    localStorage.setItem(API_STORAGE_KEYS.SELECTED_AI_PROVIDER, 'gemini')

    const { result } = renderHook(() => usePageInitialization())

    await waitFor(() => {
      expect(result.current.selectedAI).toBe('gemini-flash')
    })
  })

  it('falls back to the stored provider when exact ai id is missing', async () => {
    localStorage.setItem(API_STORAGE_KEYS.SELECTED_AI_PROVIDER, 'gemini')

    const { result } = renderHook(() => usePageInitialization())

    await waitFor(() => {
      expect(result.current.selectedAI).toBe('gemini-flash')
    })
  })
})
