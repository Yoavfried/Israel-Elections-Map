import { describe, expect, it } from 'vitest'
import {
  buildBackgroundPolygonVisibilityFilter,
  buildMarkerVisibilityFilter,
  buildPolygonVisibilityFilter,
  buildResultPolygonVisibilityFilter,
  mayHaveDisplayMarker,
} from './mapPresentation'
import type { ResultRecord } from './schemas'

describe('map presentation rules', () => {
  it('recognizes records eligible for custom and West Bank marker proxies', () => {
    expect(mayHaveDisplayMarker(record('custom:gaza', 'custom', null, 'GAZA'))).toBe(true)
    expect(mayHaveDisplayMarker(record('loc:3616', 'locality', 'loc:3616', '3616'))).toBe(true)
    expect(
      mayHaveDisplayMarker(record('stat2022:36160001', 'statistical-area', 'loc:3616', '36160001')),
    ).toBe(true)
    expect(mayHaveDisplayMarker(record('loc:1791', 'locality', 'loc:1791', '1791'))).toBe(true)
    expect(mayHaveDisplayMarker(record('loc:3488', 'locality', 'loc:3488', '3488'))).toBe(true)
    expect(
      mayHaveDisplayMarker(
        record('stat1995:9400008', 'statistical-area', 'loc:9400', '9400008'),
      ),
    ).toBe(true)
    expect(mayHaveDisplayMarker(record('loc:3000', 'locality', 'loc:3000', '3000'))).toBe(false)
    expect(
      mayHaveDisplayMarker(
        record(
          'municipality-fallback:2011:loc:3616',
          'municipality-fallback',
          'loc:3616',
          '3616',
        ),
      ),
    ).toBe(false)
  })

  it('includes only markers with data and excludes election-hidden markers', () => {
    const filter = buildMarkerVisibilityFilter(
      [
        record('custom:hebron', 'custom', null, 'HEBRON'),
        record('loc:3616', 'locality', 'loc:3616', '3616'),
        record('loc:3000', 'locality', 'loc:3000', '3000'),
      ],
      ['loc:3778', 'loc:3720'],
    )

    expect(filter).toEqual([
      'all',
      ['!', ['in', ['get', 'id'], ['literal', ['loc:3720', 'loc:3778']]]],
      ['in', ['get', 'id'], ['literal', ['custom:hebron', 'loc:3616']]],
    ])
  })

  it('keeps Kinneret, hidden areas, and inactive custom polygons out of the fill layer', () => {
    expect(
      buildPolygonVisibilityFilter(
        ['loc:628', 'loc:9920'],
        [
          record('custom:hebron', 'custom', null, 'HEBRON'),
          record(
            'municipality-fallback:2011:loc:3400',
            'municipality-fallback',
            'loc:3400',
            '3400',
          ),
          record('stat2011:34000001', 'statistical-area', 'loc:3400', '1'),
        ],
      ),
    ).toEqual([
      'all',
      ['!=', ['get', 'displayMode'], 'marker'],
      ['!=', ['get', 'localityCode'], '9920'],
      ['!', ['in', ['get', 'id'], ['literal', ['loc:628', 'loc:9920']]]],
      [
        'any',
        [
          'all',
          ['!=', ['get', 'geographyType'], 'custom'],
          ['!=', ['get', 'geographyType'], 'municipality-fallback'],
        ],
        [
          'in',
          ['get', 'id'],
          [
            'literal',
            ['custom:hebron', 'municipality-fallback:2011:loc:3400'],
          ],
        ],
      ],
    ])
  })

  it('separates result polygons from non-interactive background polygons', () => {
    const records = [
      record('stat2011:38230001', 'statistical-area', 'loc:3823', '38230001'),
      record(
        'municipality-fallback:2011:loc:3400',
        'municipality-fallback',
        'loc:3400',
        '3400',
      ),
    ]
    const baseFilter = buildPolygonVisibilityFilter([], records)
    const baseConditions = Array.isArray(baseFilter) ? baseFilter.slice(1) : []
    const resultIds = [
      'municipality-fallback:2011:loc:3400',
      'stat2011:38230001',
    ]

    expect(buildResultPolygonVisibilityFilter([], records)).toEqual([
      'all',
      ...baseConditions,
      ['in', ['get', 'id'], ['literal', resultIds]],
    ])
    expect(buildBackgroundPolygonVisibilityFilter([], records)).toEqual([
      'all',
      ...baseConditions,
      ['!', ['in', ['get', 'id'], ['literal', resultIds]]],
    ])
  })
})

function record(
  id: string,
  geographyType: ResultRecord['geographyType'],
  localityId: string | null,
  code: string,
): ResultRecord {
  return {
    id,
    geographyType,
    names: { en: id, he: id },
    code,
    localityId,
    totals: {
      contributingRows: 1,
      contributingKalpis: 1,
      eligibleVoters: 1,
      actualVoters: 1,
      validVotes: 1,
      invalidVotes: 0,
      turnout: 1,
    },
    winner: {
      partyId: 'party',
      votes: 1,
      runnerUpVotes: 0,
      marginVotes: 1,
      voteShare: 1,
    },
    partyVotes: { party: 1 },
  }
}
