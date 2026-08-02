import {
  AppCatalogSchema,
  ElectionResultsSchema,
  GeographySearchIndexSchema,
  NationalResultsSchema,
} from '../domain/schemas'
import type {
  AppCatalog,
  ElectionResults,
  GeographySearchIndex,
  GeographyMode,
  NationalResults,
} from '../domain/schemas'

const DATA_ROOT = `${import.meta.env.BASE_URL}data/v2/`
const catalogUrl = `${DATA_ROOT}catalog.json`

let catalogRequest: Promise<AppCatalog> | undefined
const resultsRequests = new Map<string, Promise<ElectionResults>>()
const nationalResultsRequests = new Map<string, Promise<NationalResults>>()
const geographySearchRequests = new Map<string, Promise<GeographySearchIndex>>()

export function loadCatalog(): Promise<AppCatalog> {
  catalogRequest ??= fetchJson(catalogUrl).then((value) => AppCatalogSchema.parse(value))
  return catalogRequest
}

export function loadElectionResults(
  electionId: string,
  mode: GeographyMode,
  relativeUrl: string,
): Promise<ElectionResults> {
  const cacheKey = `${electionId}:${mode}:${relativeUrl}`
  const existing = resultsRequests.get(cacheKey)
  if (existing) {
    return existing
  }

  const request = fetchJson(resolveDataUrl(relativeUrl))
    .then((value) => ElectionResultsSchema.parse(value))
    .then((results) => {
      if (results.electionId !== electionId || results.geographyMode !== mode) {
        throw new Error(`Result asset identity does not match ${electionId}/${mode}`)
      }
      return results
    })
  resultsRequests.set(cacheKey, request)
  return request
}

export function loadNationalResults(
  electionId: string,
  relativeUrl: string,
): Promise<NationalResults> {
  const existing = nationalResultsRequests.get(relativeUrl)
  if (existing) {
    return existing
  }

  const request = fetchJson(resolveDataUrl(relativeUrl))
    .then((value) => NationalResultsSchema.parse(value))
    .then((results) => {
      if (results.electionId !== electionId) {
        throw new Error(`National result asset identity does not match ${electionId}`)
      }
      return results
    })
  nationalResultsRequests.set(relativeUrl, request)
  return request
}

export function loadGeographySearchIndex(
  electionId: string,
  relativeUrl: string,
): Promise<GeographySearchIndex> {
  const existing = geographySearchRequests.get(relativeUrl)
  if (existing) {
    return existing
  }

  const request = fetchJson(resolveDataUrl(relativeUrl))
    .then((value) => GeographySearchIndexSchema.parse(value))
    .then((searchIndex) => {
      if (searchIndex.electionId !== electionId) {
        throw new Error(`Search-index identity does not match ${electionId}`)
      }
      return searchIndex
    })
  geographySearchRequests.set(relativeUrl, request)
  return request
}

export function resolveDataUrl(relativeUrl: string): string {
  return `${DATA_ROOT}${relativeUrl.replace(/^\/+/, '')}`
}

async function fetchJson(url: string): Promise<unknown> {
  const response = await fetch(url, { headers: { Accept: 'application/json' } })
  if (!response.ok) {
    throw new Error(`Could not load ${url} (HTTP ${response.status})`)
  }
  return response.json()
}
