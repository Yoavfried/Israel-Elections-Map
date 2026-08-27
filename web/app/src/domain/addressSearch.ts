import {
  ADDRESS_GEOCODER_URL,
  ADDRESS_SEARCH_RESULT_LIMIT,
} from '../config/geocoding'
import type {
  GeographyBounds,
  GeographySearchItem,
  Language,
} from './schemas'

export type MapPosition = [number, number]

export interface AddressSearchMatch {
  id: string
  label: string
  coordinates: MapPosition
  area: GeographySearchItem
}

export interface AddressCandidate {
  id: string
  label: string
  coordinates: MapPosition
}

interface SearchGeometryFeatureCollection {
  type: 'FeatureCollection'
  features: SearchGeometryFeature[]
}

interface SearchGeometryFeature {
  id?: string | number
  properties?: { id?: string | number }
  geometry: unknown
}

const candidateCache = new Map<string, AddressCandidate[]>()
const geometryRequests = new Map<string, Promise<SearchGeometryFeatureCollection>>()

export function shouldSearchAddresses(query: string): boolean {
  const trimmed = query.trim()
  return trimmed.length >= 4 && /\p{L}/u.test(trimmed) && /\d/u.test(trimmed)
}

export async function searchAddresses({
  query,
  language,
  bounds,
  statisticalItems,
  geometryUrl,
  signal,
}: {
  query: string
  language: Language
  bounds: GeographyBounds
  statisticalItems: GeographySearchItem[]
  geometryUrl: string
  signal: AbortSignal
}): Promise<AddressSearchMatch[]> {
  const candidates = await fetchAddressCandidates(query, language, bounds, signal)
  if (candidates.length === 0) {
    return []
  }
  const geometry = await loadSearchGeometry(geometryUrl)
  if (signal.aborted) {
    throw new DOMException('Address search aborted', 'AbortError')
  }
  return resolveAddressCandidates(candidates, statisticalItems, geometry)
}

export function parseAddressCandidates(
  payload: unknown,
  query: string,
  bounds: GeographyBounds,
): AddressCandidate[] {
  if (!isRecord(payload) || !Array.isArray(payload.features)) {
    return []
  }

  const queryNumbers = digitGroups(query)
  const seen = new Set<string>()
  const candidates: AddressCandidate[] = []
  for (const feature of payload.features) {
    if (!isRecord(feature) || !isRecord(feature.geometry)) {
      continue
    }
    const geometry = feature.geometry
    if (geometry.type !== 'Point' || !isPosition(geometry.coordinates)) {
      continue
    }
    const coordinates: MapPosition = [geometry.coordinates[0], geometry.coordinates[1]]
    if (!boundsContainPoint(bounds, coordinates)) {
      continue
    }
    const properties = isRecord(feature.properties) ? feature.properties : {}
    const houseNumber = stringProperty(properties, 'housenumber')
    if (!houseNumber || !sharesDigitGroup(queryNumbers, digitGroups(houseNumber))) {
      continue
    }
    const label = formatAddressLabel(properties)
    if (!label) {
      continue
    }
    const osmType = stringProperty(properties, 'osm_type') || 'osm'
    const osmId = stringProperty(properties, 'osm_id') || coordinates.join(',')
    const id = `${osmType}:${osmId}`
    const dedupeKey = `${id}:${coordinates.join(',')}`
    if (seen.has(dedupeKey)) {
      continue
    }
    seen.add(dedupeKey)
    candidates.push({ id, label, coordinates })
  }
  return candidates.slice(0, ADDRESS_SEARCH_RESULT_LIMIT)
}

export function resolveAddressCandidates(
  candidates: AddressCandidate[],
  statisticalItems: GeographySearchItem[],
  geometry: SearchGeometryFeatureCollection,
): AddressSearchMatch[] {
  const items = statisticalItems.filter(
    (item) => item.geographyMode === 'statistical-area',
  )
  const itemsById = new Map(items.map((item) => [item.id, item]))
  const featuresById = new Map(
    geometry.features.map((feature) => [featureId(feature), feature]),
  )
  const matches: AddressSearchMatch[] = []
  const seen = new Set<string>()

  for (const candidate of candidates) {
    const containingAreas = items
      .filter((item) => boundsContainPoint(item.bounds, candidate.coordinates))
      .filter((item) => {
        const feature = featuresById.get(item.id)
        return geometryContainsPoint(feature?.geometry, candidate.coordinates)
      })
      .toSorted(
        (left, right) =>
          boundsArea(left.bounds) - boundsArea(right.bounds) ||
          Number(right.hasResults) - Number(left.hasResults) ||
          left.id.localeCompare(right.id),
      )
    const area = containingAreas[0]
    if (!area || !itemsById.has(area.id)) {
      continue
    }
    const key = `${candidate.id}:${area.id}`
    if (seen.has(key)) {
      continue
    }
    seen.add(key)
    matches.push({
      id: `address:${candidate.id}:${area.id}`,
      label: candidate.label,
      coordinates: candidate.coordinates,
      area,
    })
  }
  return matches
}

function formatAddressLabel(properties: Record<string, unknown>): string {
  const street =
    stringProperty(properties, 'street') ||
    stringProperty(properties, 'name')
  const houseNumber = stringProperty(properties, 'housenumber')
  const locality =
    stringProperty(properties, 'city') ||
    stringProperty(properties, 'town') ||
    stringProperty(properties, 'village') ||
    stringProperty(properties, 'locality') ||
    stringProperty(properties, 'district')
  const addressLine = [street, houseNumber].filter(Boolean).join(' ')
  return uniqueText([addressLine, locality]).join(', ')
}

async function fetchAddressCandidates(
  query: string,
  language: Language,
  bounds: GeographyBounds,
  signal: AbortSignal,
): Promise<AddressCandidate[]> {
  const url = buildPhotonUrl(query, language, bounds)
  const cacheKey = url.toString()
  const cached = candidateCache.get(cacheKey)
  if (cached) {
    return cached
  }
  const response = await fetch(url, {
    signal,
    cache: 'no-store',
    referrerPolicy: 'no-referrer',
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    throw new Error(`Address search failed with HTTP ${response.status}`)
  }
  const candidates = parseAddressCandidates(await response.json(), query, bounds)
  candidateCache.set(cacheKey, candidates)
  return candidates
}

function buildPhotonUrl(
  query: string,
  language: Language,
  bounds: GeographyBounds,
): URL {
  const base = globalThis.location?.href ?? 'http://localhost/'
  const url = new URL(ADDRESS_GEOCODER_URL, base)
  url.searchParams.set('q', query.trim())
  url.searchParams.set('limit', String(ADDRESS_SEARCH_RESULT_LIMIT))
  url.searchParams.set(
    'bbox',
    `${bounds[0][0]},${bounds[0][1]},${bounds[1][0]},${bounds[1][1]}`,
  )
  if (language === 'en') {
    url.searchParams.set('lang', 'en')
  }
  return url
}

function loadSearchGeometry(url: string): Promise<SearchGeometryFeatureCollection> {
  const existing = geometryRequests.get(url)
  if (existing) {
    return existing
  }
  const request = fetch(url, { headers: { Accept: 'application/geo+json, application/json' } })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`Could not load address lookup geometry (HTTP ${response.status})`)
      }
      return parseSearchGeometry(await response.json())
    })
    .catch((error: unknown) => {
      geometryRequests.delete(url)
      throw error
    })
  geometryRequests.set(url, request)
  return request
}

function parseSearchGeometry(payload: unknown): SearchGeometryFeatureCollection {
  if (!isRecord(payload) || payload.type !== 'FeatureCollection' || !Array.isArray(payload.features)) {
    throw new Error('Address lookup geometry is not a GeoJSON FeatureCollection')
  }
  return payload as unknown as SearchGeometryFeatureCollection
}

function geometryContainsPoint(
  geometry: unknown,
  point: MapPosition,
): boolean {
  if (!isRecord(geometry) || !Array.isArray(geometry.coordinates)) {
    return false
  }
  if (geometry.type === 'Polygon') {
    return polygonContainsPoint(geometry.coordinates as number[][][], point)
  }
  if (geometry.type === 'MultiPolygon') {
    return (geometry.coordinates as number[][][][]).some((polygon) =>
      polygonContainsPoint(polygon, point),
    )
  }
  return false
}

function polygonContainsPoint(polygon: number[][][], point: MapPosition): boolean {
  const outer = polygon[0]
  return Boolean(
    outer &&
      ringContainsPoint(outer, point) &&
      !polygon.slice(1).some((ring) => ringContainsPoint(ring, point)),
  )
}

function ringContainsPoint(ring: number[][], point: MapPosition): boolean {
  let inside = false
  for (let index = 0, previous = ring.length - 1; index < ring.length; previous = index++) {
    const current = ring[index]
    const prior = ring[previous]
    if (!isPosition(current) || !isPosition(prior)) {
      continue
    }
    if (pointOnSegment(point, prior, current)) {
      return true
    }
    const crossesLatitude = current[1] > point[1] !== prior[1] > point[1]
    const crossingLongitude =
      ((prior[0] - current[0]) * (point[1] - current[1])) /
        (prior[1] - current[1]) +
      current[0]
    if (crossesLatitude && point[0] < crossingLongitude) {
      inside = !inside
    }
  }
  return inside
}

function pointOnSegment(point: MapPosition, start: MapPosition, end: MapPosition): boolean {
  const deltaX = end[0] - start[0]
  const deltaY = end[1] - start[1]
  const lengthSquared = deltaX * deltaX + deltaY * deltaY
  if (lengthSquared === 0) {
    return point[0] === start[0] && point[1] === start[1]
  }
  const cross =
    (point[0] - start[0]) * deltaY -
    (point[1] - start[1]) * deltaX
  if (Math.abs(cross) > 1e-10) {
    return false
  }
  const dot =
    (point[0] - start[0]) * deltaX +
    (point[1] - start[1]) * deltaY
  return dot >= 0 && dot <= lengthSquared
}

function featureId(feature: SearchGeometryFeature): string {
  return String(feature.id ?? feature.properties?.id ?? '')
}

function boundsContainPoint(bounds: GeographyBounds, point: MapPosition): boolean {
  return (
    point[0] >= bounds[0][0] &&
    point[0] <= bounds[1][0] &&
    point[1] >= bounds[0][1] &&
    point[1] <= bounds[1][1]
  )
}

function boundsArea(bounds: GeographyBounds): number {
  return (bounds[1][0] - bounds[0][0]) * (bounds[1][1] - bounds[0][1])
}

function sharesDigitGroup(left: string[], right: string[]): boolean {
  return left.length > 0 && right.length > 0 && left.some((value) => right.includes(value))
}

function digitGroups(value: string): string[] {
  return value.match(/\d+/gu) ?? []
}

function uniqueText(values: string[]): string[] {
  const seen = new Set<string>()
  return values.filter((value) => {
    const normalized = value.trim().toLocaleLowerCase()
    if (!normalized || seen.has(normalized)) {
      return false
    }
    seen.add(normalized)
    return true
  })
}

function stringProperty(value: Record<string, unknown>, key: string): string {
  const property = value[key]
  return typeof property === 'string' || typeof property === 'number'
    ? String(property).trim()
    : ''
}

function isPosition(value: unknown): value is MapPosition {
  return (
    Array.isArray(value) &&
    value.length >= 2 &&
    typeof value[0] === 'number' &&
    Number.isFinite(value[0]) &&
    typeof value[1] === 'number' &&
    Number.isFinite(value[1])
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}
