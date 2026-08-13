import type { AppView } from '../components/PrimaryTabs'
import type { GeographyMode, Language } from '../domain/schemas'
import type { AppPreferences } from './preferences'

const APP_VIEWS = new Set<AppView>([
  'map',
  'national',
  'party-map',
  'party-comparison',
  'coalition',
])
const ELECTION_IDS = new Set(Array.from({ length: 9 }, (_, index) => `K${index + 17}`))

export interface InitialMapLink {
  electionId?: string
  geographyMode?: GeographyMode
  language?: Language
  view: AppView
  areaId?: string
}

export function parseMapLinkSearch(search: string): InitialMapLink {
  const parameters = new URLSearchParams(search)
  const election = parameters.get('election')
  const mode = parameters.get('mode')
  const language = parameters.get('lang')
  const view = parameters.get('view')
  const area = parameters.get('area')?.trim()

  return {
    electionId: election && ELECTION_IDS.has(election) ? election : undefined,
    geographyMode:
      mode === 'locality' || mode === 'statistical-area' ? mode : undefined,
    language: language === 'he' || language === 'en' ? language : undefined,
    view: view && APP_VIEWS.has(view as AppView) ? (view as AppView) : 'map',
    areaId: area || undefined,
  }
}

export function applyMapLinkPreferences(
  preferences: AppPreferences,
  mapLink: InitialMapLink,
): AppPreferences {
  return {
    ...preferences,
    ...(mapLink.electionId ? { electionId: mapLink.electionId } : {}),
    ...(mapLink.geographyMode ? { geographyMode: mapLink.geographyMode } : {}),
    ...(mapLink.language ? { language: mapLink.language } : {}),
  }
}
