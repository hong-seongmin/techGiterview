import { beforeEach, describe, expect, it } from 'vitest'
import {
  API_STORAGE_KEYS,
  createApiHeaders,
  persistSelectedAI,
} from './apiHeaders'

describe('apiHeaders', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('persists selected ai id and provider', () => {
    persistSelectedAI('gemini-flash')

    expect(localStorage.getItem(API_STORAGE_KEYS.SELECTED_AI_ID)).toBe('gemini-flash')
    expect(localStorage.getItem(API_STORAGE_KEYS.SELECTED_AI_PROVIDER)).toBe('gemini')
  })

  it('creates upstage-only headers when solar is selected', () => {
    localStorage.setItem(API_STORAGE_KEYS.UPSTAGE_API_KEY, 'upstage-key')
    localStorage.setItem(API_STORAGE_KEYS.GOOGLE_API_KEY, 'google-key')

    const headers = createApiHeaders({
      includeApiKeys: true,
      selectedAI: 'upstage-solar-pro3',
    })

    expect(headers['X-Upstage-API-Key']).toBe('upstage-key')
    expect(headers['X-Google-API-Key']).toBeUndefined()
  })

  it('creates gemini-only headers when gemini is selected', () => {
    localStorage.setItem(API_STORAGE_KEYS.UPSTAGE_API_KEY, 'upstage-key')
    localStorage.setItem(API_STORAGE_KEYS.GOOGLE_API_KEY, 'google-key')

    const headers = createApiHeaders({
      includeApiKeys: true,
      selectedAI: 'gemini-flash',
    })

    expect(headers['X-Google-API-Key']).toBe('google-key')
    expect(headers['X-Upstage-API-Key']).toBeUndefined()
  })
})
