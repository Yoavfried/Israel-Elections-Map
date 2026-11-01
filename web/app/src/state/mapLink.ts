import type { AppView } from '../components/PrimaryTabs'
import type { PartyMapDisplayMode } from '../domain/partyMap'
import type { GeographyMode, Language } from '../domain/schemas'
import type { AppPreferences } from './preferences'
import electionDefinitions from '../../config/elections.json'

const APP_VIEWS = new Set<AppView>([
  'map',
  'national',
  'party-map',
  'party-comparison',
  'coalition',
])
const ELECTION_IDS = new Set(electionDefinitions.map((election) => election.id))

export interface InitialMapLink {
  electionId?: string
  geographyMode?: GeographyMode
  language?: Language
  view: AppView
  areaId?: string
  partyId?: string
  comparisonPartyIds?: [string, string]
  partyMapDisplayMode?: PartyMapDisplayMode
}

export function parseMapLinkSearch(search: string): InitialMapLink {
  const parameters = new URLSearchParams(search)
  const election = parameters.get('election')
  const mode = parameters.get('mode')
  const language = parameters.get('lang')
  const view = parameters.get('view')
  const area = parameters.get('area')?.trim()
  const party = parameters.get('party')?.trim()
  const firstParty = parameters.get('party1')?.trim()
  const secondParty = parameters.get('party2')?.trim()
  const display = parameters.get('display')

  return {
    electionId: election && ELECTION_IDS.has(election) ? election : undefined,
    geographyMode:
      mode === 'locality' || mode === 'statistical-area' ? mode : undefined,
    language: language === 'he' || language === 'en' ? language : undefined,
    view: view && APP_VIEWS.has(view as AppView) ? (view as AppView) : 'map',
    areaId: area || undefined,
    partyId: party || undefined,
    comparisonPartyIds:
      firstParty && secondParty && firstParty !== secondParty
        ? [firstParty, secondParty]
        : undefined,
    partyMapDisplayMode:
      display === 'areas' || display === 'circles' ? display : undefined,
  }
}

interface MapLinkState {
  electionId: string
  geographyMode: GeographyMode
  language: Language
  view: AppView
  areaId?: string | null
  partyId?: string | null
  comparisonPartyIds?: readonly [string | null, string | null]
  partyMapDisplayMode?: PartyMapDisplayMode
}

export function buildMapLinkSearch(state: MapLinkState): string {
  const parameters = new URLSearchParams({
    election: state.electionId,
    mode: state.geographyMode,
    view: state.view,
    lang: state.language,
  })
  if (state.areaId) {
    parameters.set('area', state.areaId)
  }
  if (state.view === 'party-map' && state.partyId) {
    parameters.set('party', state.partyId)
    if (state.partyMapDisplayMode === 'circles') {
      parameters.set('display', 'circles')
    }
  }
  if (
    state.view === 'party-comparison' &&
    state.comparisonPartyIds?.[0] &&
    state.comparisonPartyIds[1] &&
    state.comparisonPartyIds[0] !== state.comparisonPartyIds[1]
  ) {
    parameters.set('party1', state.comparisonPartyIds[0])
    parameters.set('party2', state.comparisonPartyIds[1])
  }
  return `?${parameters.toString()}`
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
