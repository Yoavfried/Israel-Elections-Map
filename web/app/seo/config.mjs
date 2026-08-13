export const CANONICAL_ORIGIN = 'https://yoavfried.com'
export const APP_PATH = '/isr-electionmap'
export const CANONICAL_BASE = `${CANONICAL_ORIGIN}${APP_PATH}`

export const LANGUAGES = Object.freeze([
  { code: 'he', hreflang: 'he', locale: 'he-IL', dir: 'rtl', label: 'עברית' },
  { code: 'en', hreflang: 'en', locale: 'en', dir: 'ltr', label: 'English' },
  { code: 'fr', hreflang: 'fr', locale: 'fr', dir: 'ltr', label: 'Français' },
  { code: 'es', hreflang: 'es', locale: 'es', dir: 'ltr', label: 'Español' },
  { code: 'ru', hreflang: 'ru', locale: 'ru', dir: 'ltr', label: 'Русский' },
  { code: 'zh', hreflang: 'zh-Hans', locale: 'zh-CN', dir: 'ltr', label: '中文' },
  { code: 'ar', hreflang: 'ar', locale: 'ar', dir: 'rtl', label: 'العربية' },
  { code: 'de', hreflang: 'de', locale: 'de', dir: 'ltr', label: 'Deutsch' },
  { code: 'uk', hreflang: 'uk', locale: 'uk', dir: 'ltr', label: 'Українська' },
  { code: 'pl', hreflang: 'pl', locale: 'pl', dir: 'ltr', label: 'Polski' },
])

export const LANGUAGE_BY_CODE = new Map(LANGUAGES.map((language) => [language.code, language]))

export const ELECTIONS = Object.freeze([
  { id: 'K25', number: 25, slug: '2022', year: 2022 },
  { id: 'K24', number: 24, slug: '2021', year: 2021 },
  { id: 'K23', number: 23, slug: '2020', year: 2020 },
  { id: 'K22', number: 22, slug: '2019-september', year: 2019, month: 9 },
  { id: 'K21', number: 21, slug: '2019-april', year: 2019, month: 4 },
  { id: 'K20', number: 20, slug: '2015', year: 2015 },
  { id: 'K19', number: 19, slug: '2013', year: 2013 },
  { id: 'K18', number: 18, slug: '2009', year: 2009 },
  { id: 'K17', number: 17, slug: '2006', year: 2006 },
])

export const ELECTION_BY_ID = new Map(ELECTIONS.map((election) => [election.id, election]))
export const ELECTION_BY_SLUG = new Map(ELECTIONS.map((election) => [election.slug, election]))

export const FUTURE_ELECTION = Object.freeze({ number: 26, slug: '2026', year: 2026 })
export const BUILD_DATE = '2026-08-13'

export function localizedPath(languageCode, suffix = '') {
  const normalizedSuffix = suffix ? `/${String(suffix).replace(/^\/+|\/+$/g, '')}` : ''
  return `${APP_PATH}/${languageCode}${normalizedSuffix}`
}

export function canonicalUrl(languageCode, suffix = '') {
  return `${CANONICAL_ORIGIN}${localizedPath(languageCode, suffix)}`
}

export function electionSuffix(election) {
  return `elections/${election.slug}`
}

export function resultSuffix(election, mode, recordId) {
  const family = mode === 'locality' ? 'localities' : 'statistical-areas'
  return `${electionSuffix(election)}/${family}/${encodeURIComponent(recordId)}`
}

export function featuresSuffix() {
  return 'features'
}

export function comparisonSuffix() {
  return `${featuresSuffix()}/party-comparison`
}

export function coalitionSuffix(election) {
  return `${electionSuffix(election)}/coalition`
}

export function partySuffix(election, partyId) {
  return `${electionSuffix(election)}/parties/${encodeURIComponent(partyId)}`
}

export function mapUrl({
  electionId = 'K25',
  mode = 'statistical-area',
  areaId,
  view = 'map',
  languageCode = 'en',
  partyId,
  comparisonPartyIds,
  partyDisplay,
} = {}) {
  const parameters = new URLSearchParams({
    election: electionId,
    mode,
    view,
    lang: languageCode === 'he' ? 'he' : 'en',
  })
  if (areaId) {
    parameters.set('area', areaId)
  }
  if (view === 'party-map' && partyId) {
    parameters.set('party', partyId)
    if (partyDisplay === 'circles') {
      parameters.set('display', partyDisplay)
    }
  }
  if (view === 'party-comparison' && comparisonPartyIds?.[0] && comparisonPartyIds?.[1]) {
    parameters.set('party1', comparisonPartyIds[0])
    parameters.set('party2', comparisonPartyIds[1])
  }
  return `${CANONICAL_BASE}?${parameters}`
}
