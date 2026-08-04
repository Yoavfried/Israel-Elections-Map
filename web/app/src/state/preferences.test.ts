import { describe, expect, it } from 'vitest'
import { defaultPreferences, loadPreferences, savePreferences } from './preferences'

class MemoryStorage {
  value: string | null = null

  getItem() {
    return this.value
  }

  setItem(_key: string, value: string) {
    this.value = value
  }
}

describe('preferences', () => {
  it('uses Hebrew for a Hebrew browser locale', () => {
    expect(defaultPreferences('he-IL').language).toBe('he')
  })

  it('round-trips only the versioned UI preferences', () => {
    const storage = new MemoryStorage()
    savePreferences(storage, {
      language: 'he',
      electionId: 'K22',
      geographyMode: 'locality',
      basemapMode: 'neutral',
    })

    expect(loadPreferences(storage, 'en')).toEqual({
      language: 'he',
      electionId: 'K22',
      geographyMode: 'locality',
      basemapMode: 'neutral',
    })
  })

  it('falls back from the removed satellite preference to the vector map', () => {
    const storage = new MemoryStorage()
    storage.value = JSON.stringify({
      language: 'en',
      electionId: 'K25',
      geographyMode: 'statistical-area',
      basemapMode: 'satellite',
    })

    expect(loadPreferences(storage, 'en').basemapMode).toBe('vector')
  })

  it('falls back safely when storage contains invalid JSON', () => {
    const storage = new MemoryStorage()
    storage.value = '{not-json'
    expect(loadPreferences(storage, 'en')).toEqual(defaultPreferences('en'))
  })
})
