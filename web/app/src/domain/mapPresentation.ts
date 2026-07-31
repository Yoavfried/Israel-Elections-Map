import type { ExpressionSpecification, FilterSpecification } from 'maplibre-gl'
import type { ResultRecord } from './schemas'

const WEST_BANK_LOCALITY_CODE_MIN = 3500
const WEST_BANK_LOCALITY_CODE_MAX_EXCLUSIVE = 4000
const SPECIAL_POINT_PROXY_LOCALITY_CODES = new Set([1791, 1792, 1793, 1794, 3488, 9400])

export function mayHaveDisplayMarker(record: ResultRecord): boolean {
  if (record.geographyType === 'custom') {
    return true
  }
  if (record.geographyType === 'municipality-fallback') {
    return false
  }

  const localityCode = Number(record.localityId?.replace(/^loc:/, '') ?? record.code)
  return (
    Number.isInteger(localityCode) &&
    (SPECIAL_POINT_PROXY_LOCALITY_CODES.has(localityCode) ||
      (localityCode >= WEST_BANK_LOCALITY_CODE_MIN &&
        localityCode < WEST_BANK_LOCALITY_CODE_MAX_EXCLUSIVE))
  )
}

export function buildMarkerVisibilityFilter(
  records: ResultRecord[],
  hiddenGeographyIds: string[] = [],
): FilterSpecification {
  const idsWithData = records
    .filter(mayHaveDisplayMarker)
    .map((record) => record.id)
    .toSorted()
  const excludedIds = [...new Set(hiddenGeographyIds)].toSorted()

  return [
    'all',
    ['!', ['in', ['get', 'id'], ['literal', excludedIds]]],
    ['in', ['get', 'id'], ['literal', idsWithData]],
  ]
}

export function buildPolygonVisibilityFilter(
  hiddenGeographyIds: string[],
  records: ResultRecord[] = [],
): FilterSpecification {
  return ['all', ...buildPolygonVisibilityConditions(hiddenGeographyIds, records)]
}

function buildPolygonVisibilityConditions(
  hiddenGeographyIds: string[],
  records: ResultRecord[],
): ExpressionSpecification[] {
  const excludedIds = [...new Set(hiddenGeographyIds)].toSorted()
  const conditionalPolygonIdsWithData = records
    .filter(
      (record) =>
        record.geographyType === 'custom' || record.geographyType === 'municipality-fallback',
    )
    .map((record) => record.id)
    .toSorted()

  return [
    ['!=', ['get', 'displayMode'], 'marker'],
    ['!=', ['get', 'localityCode'], '9920'],
    ['!', ['in', ['get', 'id'], ['literal', excludedIds]]],
    [
      'any',
      [
        'all',
        ['!=', ['get', 'geographyType'], 'custom'],
        ['!=', ['get', 'geographyType'], 'municipality-fallback'],
      ],
      ['in', ['get', 'id'], ['literal', conditionalPolygonIdsWithData]],
    ],
  ] as ExpressionSpecification[]
}

export function buildResultPolygonVisibilityFilter(
  hiddenGeographyIds: string[],
  records: ResultRecord[],
): FilterSpecification {
  return [
    'all',
    ...buildPolygonVisibilityConditions(hiddenGeographyIds, records),
    [
      'in',
      ['get', 'id'],
      ['literal', records.map((record) => record.id).toSorted()],
    ],
  ]
}

export function buildBackgroundPolygonVisibilityFilter(
  hiddenGeographyIds: string[],
  records: ResultRecord[],
): FilterSpecification {
  return [
    'all',
    ...buildPolygonVisibilityConditions(hiddenGeographyIds, records),
    [
      '!',
      [
        'in',
        ['get', 'id'],
        ['literal', records.map((record) => record.id).toSorted()],
      ],
    ],
  ]
}
