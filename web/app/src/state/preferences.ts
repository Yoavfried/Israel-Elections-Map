import { BasemapModeSchema, GeographyModeSchema, LanguageSchema } from '../domain/schemas'
import type { BasemapMode, GeographyMode, Language } from '../domain/schemas'

const STORAGE_KEY = 'israel-election-map:preferences:v1'

export interface AppPreferences {
  language: Language
  electionId: string
  geographyMode: GeographyMode
  basemapMode: BasemapMode
}

interface StorageLike {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
}

export function defaultPreferences(browserLanguage = 'en'): AppPreferences {
  return {
    language: browserLanguage.toLowerCase().startsWith('he') ? 'he' : 'en',
    electionId: 'K26',
    geographyMode: 'statistical-area',
    basemapMode: 'vector',
  }
}

export function loadPreferences(
  storage: StorageLike | undefined,
  browserLanguage = 'en',
): AppPreferences {
  const defaults = defaultPreferences(browserLanguage)
  if (!storage) {
    return defaults
  }

  try {
    const raw = storage.getItem(STORAGE_KEY)
    if (!raw) {
      return defaults
    }
    const parsed = JSON.parse(raw) as Record<string, unknown>
    return {
      language: LanguageSchema.catch(defaults.language).parse(parsed.language),
      electionId:
        typeof parsed.electionId === 'string' && /^K\d+$/.test(parsed.electionId)
          ? parsed.electionId
          : defaults.electionId,
      geographyMode: GeographyModeSchema.catch(defaults.geographyMode).parse(parsed.geographyMode),
      basemapMode: BasemapModeSchema.catch(defaults.basemapMode).parse(parsed.basemapMode),
    }
  } catch {
    return defaults
  }
}

export function savePreferences(storage: StorageLike | undefined, preferences: AppPreferences): void {
  if (!storage) {
    return
  }
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify(preferences))
  } catch {
    // Storage can be unavailable or full; preferences remain valid for this session.
  }
}
