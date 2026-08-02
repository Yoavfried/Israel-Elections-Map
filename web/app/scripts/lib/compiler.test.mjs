import { describe, expect, it } from 'vitest'
import {
  applyStatisticalDisplayGroups,
  aliasJoinedCompositeResults,
  buildCompositeMetadataIndex,
  buildDisplayMarkers,
  buildGeographySearchIndex,
  buildHiddenLocalityIds,
  buildMunicipalityFallbackDisplay,
  buildNationalResultsPayload,
  buildPartyRegistryIndex,
  buildResultPayload,
  isPointLikeGeometry,
  isPointProxyLocalityCode,
  isWestBankSettlementCode,
  parseCsv,
  pruneGeography,
  stablePartyColor,
} from './compiler.mjs'

const coverage = {
  totalRows: 1,
  totalActualVoters: 80,
  mappedRows: 1,
  mappedActualVoters: 80,
  mappedActualVoterShare: 1,
  pendingRows: 0,
  pendingActualVoters: 0,
  unmappedRows: 0,
  unmappedActualVoters: 0,
}

function registryFor(electionId, parties) {
  return buildPartyRegistryIndex(
    parties.map(({ sourceColumn, ballotLetter = sourceColumn, totalVotes, nameHe, nameEn = '' }) => ({
      election: electionId,
      source_column: sourceColumn,
      ballot_letter: ballotLetter,
      total_votes: String(totalVotes),
      list_name_he: nameHe,
      display_name_he: nameHe,
      display_name_en: nameEn,
      wikipedia_he_url: '',
      wikipedia_en_url: '',
    })),
  ).get(electionId)
}

describe('web data compiler', () => {
  it('parses UTF-8 BOM CSV headers', () => {
    expect(parseCsv('\ufeffid,name\n1,שלום\n')).toEqual([{ id: '1', name: 'שלום' }])
  })

  it('builds and validates a complete national result', () => {
    const partyRegistry = registryFor('K25', [
      { sourceColumn: 'a', ballotLetter: 'א', totalVotes: 60, nameHe: 'רשימה א' },
      { sourceColumn: 'b', ballotLetter: 'ב', totalVotes: 30, nameHe: 'רשימה ב' },
      { sourceColumn: 'c', ballotLetter: 'ג', totalVotes: 9, nameHe: 'רשימה ג' },
    ])
    const payload = buildNationalResultsPayload({
      electionId: 'K25',
      electionRule: {
        electoral_threshold_share: '0.1',
        total_mandates: '5',
        official_results_url: 'https://example.com/results',
        threshold_source_url: 'https://example.com/threshold',
      },
      mandateRows: [
        { source_column: 'a', mandates: '3' },
        { source_column: 'b', mandates: '2' },
      ],
      partyRegistry,
      partyColorsByBallotLetter: { א: '#123456' },
    })

    expect(payload).toMatchObject({
      schemaVersion: 1,
      electionId: 'K25',
      threshold: { share: 0.1, votes: 10 },
      totals: {
        validVotes: 99,
        representedVotes: 90,
        mandates: 5,
        contestingParties: 3,
        representedParties: 2,
      },
    })
    expect(payload.parties.map((party) => [party.id, party.mandates])).toEqual([
      ['a', 3],
      ['b', 2],
      ['c', 0],
    ])
    expect(payload.parties[0]).toMatchObject({
      color: '#123456',
      colorStatus: 'reviewed',
      passedThreshold: true,
    })
    expect(payload.parties[2].passedThreshold).toBe(false)
  })

  it('publishes only documented positive-vote parties in national results', () => {
    const partyRegistry = registryFor('K25', [
      { sourceColumn: 'a', totalVotes: 60, nameHe: 'רשימה א' },
      { sourceColumn: 'b', totalVotes: 40, nameHe: 'רשימה ב' },
      { sourceColumn: 'withdrawn', totalVotes: 0, nameHe: 'רשימה שפרשה' },
    ])
    const args = {
      electionId: 'K25',
      electionRule: {
        electoral_threshold_share: '0.1',
        total_mandates: '5',
        official_results_url: 'https://example.com/results',
        threshold_source_url: 'https://example.com/threshold',
      },
      mandateRows: [
        { source_column: 'a', mandates: '3' },
        { source_column: 'b', mandates: '2' },
      ],
      partyRegistry,
    }

    expect(() => buildNationalResultsPayload(args)).toThrow(
      /zero-vote parties must be declared as result-column exclusions: withdrawn/,
    )

    const payload = buildNationalResultsPayload({
      ...args,
      excludedPartyColumns: ['withdrawn'],
    })
    expect(payload.totals).toMatchObject({
      validVotes: 100,
      contestingParties: 2,
    })
    expect(payload.parties.map((party) => party.id)).toEqual(['a', 'b'])
  })

  it('rejects national mandate allocations that do not fill the Knesset', () => {
    const partyRegistry = registryFor('K25', [
      { sourceColumn: 'a', totalVotes: 60, nameHe: 'רשימה א' },
      { sourceColumn: 'b', totalVotes: 40, nameHe: 'רשימה ב' },
    ])

    expect(() =>
      buildNationalResultsPayload({
        electionId: 'K25',
        electionRule: {
          electoral_threshold_share: '0.1',
          total_mandates: '5',
          official_results_url: 'https://example.com/results',
          threshold_source_url: 'https://example.com/threshold',
        },
        mandateRows: [{ source_column: 'a', mandates: '4' }],
        partyRegistry,
      }),
    ).toThrow(/sums to 4, expected 5/)
  })

  it('collapses non-exclusive statistical components only when every total matches', () => {
    const resultRow = (id, eligible, actual, valid, invalid, partyA, partyB) => ({
      election: 'K21',
      stat_area_id: id,
      contributing_rows: '1',
      contributing_kalpis: '1',
      eligible_voters: String(eligible),
      actual_voters: String(actual),
      valid_votes: String(valid),
      invalid_votes: String(invalid),
      winning_ballot_letter: 'a',
      winning_votes: String(partyA),
      runner_up_votes: String(partyB),
      margin_votes: String(partyA - partyB),
      winning_vote_share: String(partyA / valid),
      a: String(partyA),
      b: String(partyB),
    })
    const primaryRows = [
      resultRow('stat2011:1', 100, 40, 39, 1, 30, 9),
      resultRow('stat2011:2', 120, 50, 49, 1, 29, 20),
      resultRow('stat2011:ordinary', 80, 30, 30, 0, 20, 10),
    ]
    const customRow = {
      election: 'K21',
      geography_mode: 'locality',
      custom_geography_id: 'custom:tribal',
      geography_id: 'custom:tribal',
      contributing_rows: '2',
      contributing_kalpis: '2',
      eligible_voters: '220',
      actual_voters: '90',
      valid_votes: '88',
      invalid_votes: '2',
      winning_ballot_letter: 'a',
      winning_votes: '59',
      runner_up_votes: '29',
      margin_votes: '30',
      winning_vote_share: String(59 / 88),
      a: '59',
      b: '29',
    }
    const groups = [
      {
        displayGeographyId: 'custom:tribal',
        componentIds: ['stat2011:1', 'stat2011:2', 'stat2011:zero-result'],
      },
    ]

    const grouped = applyStatisticalDisplayGroups({
      electionId: 'K21',
      primaryRows,
      customRows: [customRow],
      groups,
    })

    expect(grouped.primaryRows.map((row) => row.stat_area_id)).toEqual([
      'stat2011:ordinary',
    ])
    expect(grouped.displayRows).toEqual([
      expect.objectContaining({
        custom_geography_id: 'custom:tribal',
        geography_mode: 'statistical-area',
      }),
    ])
    expect(grouped.hiddenGeographyIds).toEqual([
      'stat2011:1',
      'stat2011:2',
      'stat2011:zero-result',
    ])

    expect(() =>
      applyStatisticalDisplayGroups({
        electionId: 'K21',
        primaryRows,
        customRows: [{ ...customRow, actual_voters: '91' }],
        groups,
      }),
    ).toThrow(/does not equal its components: actual_voters=90\/91/)
  })

  it('builds a reviewed presentation aggregate by summing component result rows', () => {
    const resultRow = (id, eligible, actual, valid, invalid, partyA, partyB) => ({
      election: 'K24',
      stat_area_id: id,
      contributing_rows: '1',
      contributing_kalpis: '1',
      eligible_voters: String(eligible),
      actual_voters: String(actual),
      valid_votes: String(valid),
      invalid_votes: String(invalid),
      winning_ballot_letter: 'a',
      winning_votes: String(partyA),
      runner_up_votes: String(partyB),
      margin_votes: String(partyA - partyB),
      winning_vote_share: String(partyA / valid),
      a: String(partyA),
      b: String(partyB),
    })
    const primaryRows = [
      resultRow('stat2011:1', 100, 40, 39, 1, 30, 9),
      resultRow('stat2011:2', 120, 50, 49, 1, 29, 20),
      resultRow('stat2011:ordinary', 80, 30, 30, 0, 20, 10),
    ]

    const grouped = applyStatisticalDisplayGroups({
      electionId: 'K24',
      primaryRows,
      customRows: [],
      groups: [
        {
          displayGeographyId: 'display:aggregate',
          componentIds: ['stat2011:1', 'stat2011:2', 'stat2011:zero-result'],
          aggregationMethod: 'sum-components',
        },
      ],
    })

    expect(grouped.primaryRows.map((row) => row.stat_area_id)).toEqual([
      'stat2011:ordinary',
    ])
    expect(grouped.displayRows).toEqual([
      expect.objectContaining({
        custom_geography_id: 'display:aggregate',
        geography_mode: 'statistical-area',
        contributing_rows: 2,
        contributing_kalpis: 2,
        eligible_voters: 220,
        actual_voters: 90,
        valid_votes: 88,
        invalid_votes: 2,
        a: 59,
        b: 29,
      }),
    ])
    expect(grouped.hiddenGeographyIds).toEqual([
      'stat2011:1',
      'stat2011:2',
      'stat2011:zero-result',
    ])
  })

  it('adds stable feature IDs and custom geometries', () => {
    const source = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: {
            stat_area_id: 'stat2022:100001',
            locality_id: 'loc:10',
            locality_code: 3616,
            locality_name_he: 'תירוש',
            locality_name_en: 'TIROSH',
            stat_2022: 1,
          },
          geometry: {
            type: 'Polygon',
            coordinates: [[[35.3, 31.7], [35.4, 31.7], [35.4, 31.8], [35.3, 31.7]]],
          },
        },
      ],
    }
    const custom = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: { custom_id: 'custom:test', name_he: 'בדיקה', name_en: 'Test' },
          geometry: {
            type: 'Polygon',
            coordinates: [[[34.3, 31.3], [34.4, 31.3], [34.4, 31.4], [34.3, 31.3]]],
          },
        },
        {
          type: 'Feature',
          properties: {
            custom_id: 'custom:polygon',
            name_he: 'פוליגון',
            name_en: 'Polygon',
            display_mode: 'polygon',
          },
          geometry: {
            type: 'Polygon',
            coordinates: [[[34.5, 31.3], [34.6, 31.3], [34.6, 31.4], [34.5, 31.3]]],
          },
        },
      ],
    }

    const output = pruneGeography(source, 'statistical-area', custom)
    expect(output.features.map((feature) => feature.id)).toEqual([
      'stat2022:100001',
      'custom:test',
      'custom:polygon',
    ])
    expect(output.features.map((feature) => feature.properties.displayMode)).toEqual([
      'marker',
      'marker',
      'polygon',
    ])

    const markers = buildDisplayMarkers(output)
    expect(markers.features.map((feature) => feature.id)).toEqual([
      'stat2022:100001',
      'custom:test',
    ])
    expect(markers.features.map((feature) => feature.geometry)).toEqual([
      { type: 'Point', coordinates: [35.35, 31.75] },
      { type: 'Point', coordinates: [34.35, 31.35] },
    ])
  })

  it('builds display-only municipality results and hides their empty component areas', () => {
    const localityGeography = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          id: 'loc:10',
          properties: {
            id: 'loc:10',
            geographyType: 'locality',
            localityId: 'loc:10',
            localityCode: '10',
            nameHe: 'יישוב',
            nameEn: 'Locality',
            displayMode: 'polygon',
            isComposite: false,
          },
          geometry: {
            type: 'Polygon',
            coordinates: [[[35, 32], [35.1, 32], [35.1, 32.1], [35, 32]]],
          },
        },
        {
          type: 'Feature',
          id: 'composite:test',
          properties: {
            id: 'composite:test',
            geographyType: 'locality',
            localityId: 'composite:test',
            localityCode: '20',
            nameHe: 'יישוב היסטורי',
            nameEn: 'Historical locality',
            displayMode: 'polygon',
            isComposite: true,
            componentLocalityIds: ['loc:20', 'loc:21'],
            includedNames: { he: ['מרכיב'], en: ['Component'] },
          },
          geometry: {
            type: 'Polygon',
            coordinates: [[[35.2, 32], [35.3, 32], [35.3, 32.1], [35.2, 32]]],
          },
        },
      ],
    }
    const statisticalGeography = {
      type: 'FeatureCollection',
      features: ['loc:10', 'loc:20', 'loc:21'].map((localityId, index) => ({
        type: 'Feature',
        id: `stat2011:${index + 1}`,
        properties: {
          id: `stat2011:${index + 1}`,
          geographyType: 'statistical-area',
          localityId,
        },
        geometry: { type: 'Point', coordinates: [35 + index / 10, 32] },
      })),
    }
    const fallbackRow = (id, localityId, localityCode, localityName) => ({
      election: 'K20',
      fallback_geography_id: id,
      stat_area_vintage: '2011',
      fallback_reason: 'no_ballot_has_a_supported_statistical_area_assignment',
      boundary_source: 'display_only',
      locality_id: localityId,
      locality_code: localityCode,
      locality_name: localityName,
    })

    const display = buildMunicipalityFallbackDisplay({
      electionId: 'K20',
      vintage: 2011,
      fallbackRows: [
        fallbackRow('municipality-fallback:2011:loc:10', 'loc:10', '10', 'יישוב'),
        fallbackRow(
          'municipality-fallback:2011:composite:test',
          'composite:test',
          '20',
          'יישוב היסטורי',
        ),
      ],
      localityGeography,
      statisticalGeography,
    })

    expect(display.hiddenGeographyIds).toEqual(['stat2011:1', 'stat2011:2', 'stat2011:3'])
    expect(display.features.map((feature) => feature.properties.geographyType)).toEqual([
      'municipality-fallback',
      'municipality-fallback',
    ])
    expect(display.features.every((feature) => feature.properties.displayMode === 'polygon')).toBe(
      true,
    )
    expect(display.displayRows[0]).toMatchObject({
      custom_geography_id: 'municipality-fallback:2011:loc:10',
      geography_mode: 'statistical-area',
    })
    expect(display.metadataById.get('municipality-fallback:2011:loc:10')).toMatchObject({
      geographyType: 'municipality-fallback',
      localityId: 'loc:10',
      notice: {
        en: expect.stringContaining('No ballot-to-statistical-area'),
        he: expect.stringContaining('אין נתוני שיוך'),
      },
    })
    expect(display.metadataById.get('municipality-fallback:2011:composite:test')).toMatchObject({
      includedNames: { he: ['מרכיב'], en: ['Component'] },
    })
  })

  it('limits fixed-size official markers to West Bank locality codes', () => {
    expect(isWestBankSettlementCode('3555')).toBe(true)
    expect(isWestBankSettlementCode(3825)).toBe(true)
    expect(isWestBankSettlementCode('3000')).toBe(false)
    expect(isWestBankSettlementCode('4000')).toBe(false)
    expect(isPointProxyLocalityCode('1791')).toBe(true)
    expect(isPointProxyLocalityCode('1794')).toBe(true)
    expect(isPointProxyLocalityCode('3488')).toBe(true)
    expect(isPointProxyLocalityCode('3000')).toBe(false)

    const pointProxyRing = Array.from({ length: 9 }, (_, index) => [index, index])
    const detailedRing = Array.from({ length: 14 }, (_, index) => [index, index])

    expect(
      isPointLikeGeometry({ type: 'Polygon', coordinates: [pointProxyRing] }),
    ).toBe(true)
    expect(
      isPointLikeGeometry({ type: 'Polygon', coordinates: [detailedRing] }),
    ).toBe(false)
  })

  it('keeps audited detailed West Bank display geometry polygonal', () => {
    const source = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: {
            locality_id: 'loc:3605',
            locality_code: 3605,
            locality_name_he: '3605',
            locality_name_en: 'MASU\'A',
            display_geometry_source: 'arcgis_systematics_elections2019',
          },
          geometry: {
            type: 'Polygon',
            coordinates: [[[35, 32], [35.1, 32], [35.1, 32.1], [35, 32]]],
          },
        },
      ],
    }
    const empty = { type: 'FeatureCollection', features: [] }

    const output = pruneGeography(source, 'locality', empty)

    expect(output.features[0].properties.displayMode).toBe('polygon')
    expect(buildDisplayMarkers(output).features).toHaveLength(0)
  })

  it('honors an explicit marker override for a suppressed overlapping source feature', () => {
    const source = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: {
            stat_area_id: 'stat1995:1062001',
            locality_id: 'loc:1062',
            locality_code: 1062,
            locality_name_he: 'נווה אפרים',
            locality_name_en: 'NEWE EFRAYIM',
            stat_area_number: 1,
            stat_area_vintage: 1995,
            display_mode: 'marker',
          },
          geometry: {
            type: 'Polygon',
            coordinates: [[[34.87, 32.02], [34.89, 32.02], [34.89, 32.04], [34.87, 32.02]]],
          },
        },
      ],
    }
    const empty = { type: 'FeatureCollection', features: [] }

    const output = pruneGeography(source, 'statistical-area', empty)

    expect(output.features[0].properties.displayMode).toBe('marker')
    expect(buildDisplayMarkers(output).features[0].geometry.type).toBe('Point')
  })

  it('adds reviewed composite localities and hides their components only in active elections', () => {
    const localities = {
      type: 'FeatureCollection',
      features: ['3720', '3778'].map((code) => ({
        type: 'Feature',
        properties: {
          locality_id: `loc:${code}`,
          locality_code: code,
          locality_name_he: code,
          locality_name_en: code,
        },
        geometry: {
          type: 'Polygon',
          coordinates: [[[35, 32], [35.1, 32], [35.1, 32.1], [35, 32]]],
        },
      })),
    }
    const composites = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: {
            composite_locality_id: 'composite:test',
            elections: 'K17|K18',
            component_locality_codes: '3720|3778',
            component_locality_ids: 'loc:3720|loc:3778',
            name_he: 'בדיקה',
            name_en: 'Test composite',
            host_locality_code: '3720',
            included_locality_names_he: 'מצורף',
            included_locality_names_en: 'Included locality',
          },
          geometry: {
            type: 'MultiPolygon',
            coordinates: [
              [[[35, 32], [35.02, 32], [35.02, 32.02], [35, 32]]],
              [[[35.2, 32.2], [35.22, 32.2], [35.22, 32.22], [35.2, 32.2]]],
            ],
          },
        },
      ],
    }
    const empty = { type: 'FeatureCollection', features: [] }
    const output = pruneGeography(localities, 'locality', empty, composites)

    expect(output.features.map((feature) => feature.id)).toEqual([
      'loc:3720',
      'loc:3778',
      'composite:test',
    ])
    expect(buildHiddenLocalityIds(output, 'K17')).toEqual(['loc:3720', 'loc:3778'])
    expect(buildHiddenLocalityIds(output, 'K25')).toEqual(['composite:test'])
    expect(output.features.find((feature) => feature.id === 'composite:test')?.properties.displayMode).toBe(
      'marker',
    )
    expect(buildCompositeMetadataIndex(composites).get('composite:test')?.nameEn).toBe(
      'Test composite',
    )
    expect(buildCompositeMetadataIndex(composites).get('composite:test')).toMatchObject({
      localityCode: '3720',
      includedNames: { he: ['מצורף'], en: ['Included locality'] },
    })
    expect(buildDisplayMarkers(output).features.at(-1)?.geometry).toEqual({
      type: 'MultiPoint',
      coordinates: [
        [35.01, 32.01],
        [35.21, 32.21],
      ],
    })
  })

  it('aliases a host result to an active joined-register composite', () => {
    const geography = {
      type: 'FeatureCollection',
      features: [
        {
          id: 'composite:joined-k19-567',
          properties: {
            id: 'composite:joined-k19-567',
            isComposite: true,
            compositeKind: 'joined_polling_register',
            activeElections: ['K19'],
            hostLocalityId: 'loc:567',
            componentLocalityIds: ['loc:567', 'loc:493', 'loc:566'],
          },
          geometry: null,
        },
      ],
    }
    const rows = [
      { locality_id: 'loc:10' },
      { locality_id: 'loc:567' },
    ]

    expect(aliasJoinedCompositeResults(rows, geography, 'K19')).toEqual([
      { locality_id: 'loc:10' },
      { locality_id: 'composite:joined-k19-567' },
    ])
    expect(aliasJoinedCompositeResults(rows, geography, 'K20')).toEqual(rows)
    expect(() =>
      aliasJoinedCompositeResults([...rows, { locality_id: 'loc:493' }], geography, 'K19'),
    ).toThrow(/would hide standalone result loc:493/)
  })

  it('compiles dynamic ballot-letter columns into typed records', () => {
    const row = {
      election: 'K25',
      locality_id: 'loc:10',
      contributing_rows: '1',
      contributing_kalpis: '1',
      eligible_voters: '100',
      actual_voters: '80',
      valid_votes: '79',
      invalid_votes: '1',
      winning_ballot_letter: 'אמת',
      winning_votes: '50',
      runner_up_votes: '29',
      margin_votes: '21',
      winning_vote_share: '0.632911',
      אמת: '50',
      מחל: '29',
    }
    const metadata = new Map([
      [
        'loc:10',
        {
          id: 'loc:10',
          localityId: 'loc:10',
          localityCode: '10',
          nameHe: 'תירוש',
          nameEn: 'TIROSH',
          statAreaNumber: '',
          yishuvStat2022: '',
        },
      ],
    ])
    const payload = buildResultPayload({
      electionId: 'K25',
      mode: 'locality',
      primaryRows: [row],
      customRows: [],
      metadataById: metadata,
      customMetadataById: new Map(),
      coverage,
      partyColorsByBallotLetter: { אמת: '#C62828', מחל: '#2455A4' },
      partyOverrides: { מחל: { color: '#123456' } },
      partyRegistry: registryFor('K25', [
        { sourceColumn: 'אמת', totalVotes: 100, nameHe: 'העבודה', nameEn: 'Labor' },
        { sourceColumn: 'מחל', totalVotes: 58, nameHe: 'הליכוד', nameEn: 'Likud' },
      ]),
      envelopeRows: [
        {
          election: row.election,
          envelope_id: 'envelope:official',
          envelope_name_he: 'מעטפות חיצוניות',
          envelope_name_en: 'Envelope votes',
          contributing_rows: row.contributing_rows,
          contributing_kalpis: row.contributing_kalpis,
          eligible_voters: row.eligible_voters,
          actual_voters: row.actual_voters,
          valid_votes: row.valid_votes,
          invalid_votes: row.invalid_votes,
          winning_ballot_letter: row.winning_ballot_letter,
          winning_votes: row.winning_votes,
          runner_up_votes: row.runner_up_votes,
          margin_votes: row.margin_votes,
          winning_vote_share: row.winning_vote_share,
          אמת: row.אמת,
          מחל: row.מחל,
        },
      ],
    })

    expect(payload.records[0].partyVotes).toEqual({ אמת: 50, מחל: 29 })
    expect(payload.records[0].totals.turnout).toBe(0.8)
    expect(payload.parties).toHaveLength(2)
    expect(payload.parties[0].names).toEqual({ he: 'העבודה', en: 'Labor' })
    expect(payload.parties.find((party) => party.id === 'אמת')).toMatchObject({
      color: '#C62828',
      colorStatus: 'reviewed',
    })
    expect(payload.parties.find((party) => party.id === 'מחל')).toMatchObject({
      color: '#123456',
      colorStatus: 'reviewed',
    })
    expect(payload.envelope?.geographyType).toBe('envelope')
    expect(payload.envelope?.names).toEqual({
      en: 'Double envelopes',
      he: 'מעטפות כפולות',
    })
    expect(payload.envelope?.totals.turnout).toBeNull()
  })

  it('keeps fallback party colors deterministic by ballot letter', () => {
    expect(stablePartyColor('אמת')).toBe(stablePartyColor('אמת'))
    expect(stablePartyColor('אמת')).not.toBe(stablePartyColor('מחל'))
  })

  it('builds an election-aware search index with aliases and empty visible areas', () => {
    const square = (offset) => ({
      type: 'Polygon',
      coordinates: [
        [
          [offset, 0],
          [offset + 1, 0],
          [offset + 1, 1],
          [offset, 1],
          [offset, 0],
        ],
      ],
    })
    const geography = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          id: 'loc:1',
          properties: {
            id: 'loc:1',
            geographyType: 'locality',
            localityCode: '1',
            nameHe: 'First',
            nameEn: 'First',
          },
          geometry: square(0),
        },
        {
          type: 'Feature',
          id: 'loc:2',
          properties: {
            id: 'loc:2',
            geographyType: 'locality',
            localityCode: '2',
            nameHe: 'Second',
            nameEn: 'Second',
          },
          geometry: square(1),
        },
        {
          type: 'Feature',
          id: 'loc:3',
          properties: {
            id: 'loc:3',
            geographyType: 'locality',
            localityCode: '3',
            nameHe: 'Empty place',
            nameEn: 'Empty place',
          },
          geometry: square(2),
        },
        {
          type: 'Feature',
          id: 'composite:old',
          properties: {
            id: 'composite:old',
            geographyType: 'locality',
            isComposite: true,
            activeElections: ['K17'],
            componentLocalityIds: ['loc:1', 'loc:2'],
            nameHe: 'Old municipality',
            nameEn: 'Old municipality',
          },
          geometry: square(3),
        },
        {
          type: 'Feature',
          id: 'custom:bucket',
          properties: {
            id: 'custom:bucket',
            geographyType: 'custom',
            nameHe: 'Bucket',
            nameEn: 'Bucket',
          },
          geometry: square(4),
        },
        {
          type: 'Feature',
          id: 'custom:unused',
          properties: {
            id: 'custom:unused',
            geographyType: 'custom',
            nameHe: 'Unused',
            nameEn: 'Unused',
          },
          geometry: square(5),
        },
      ],
    }
    const results = {
      electionId: 'K17',
      geographyMode: 'locality',
      hiddenGeographyIds: ['loc:1', 'loc:2'],
      records: [
        {
          id: 'composite:old',
          names: { he: 'Old municipality', en: 'Old municipality' },
          code: 'old',
        },
        {
          id: 'custom:bucket',
          names: { he: 'Bucket', en: 'Bucket' },
          code: 'custom:bucket',
        },
      ],
    }

    const index = buildGeographySearchIndex({
      electionId: 'K17',
      modes: [{ geographyMode: 'locality', geography, results }],
    })

    expect(index.items.map((item) => item.id).toSorted()).toEqual([
      'composite:old',
      'custom:bucket',
      'loc:3',
    ])
    expect(index.items.find((item) => item.id === 'composite:old')).toMatchObject({
      aliases: { he: ['First', 'Second'], en: ['First', 'Second'] },
      hasResults: true,
      bounds: [
        [3, 0],
        [4, 1],
      ],
    })
    expect(index.items.find((item) => item.id === 'loc:3')).toMatchObject({
      code: '3',
      hasResults: false,
    })
  })

  it('excludes declared source metadata and recomputes the winner', () => {
    const row = {
      election: 'K18',
      locality_id: 'loc:921',
      contributing_rows: '1',
      contributing_kalpis: '1',
      eligible_voters: '137',
      actual_voters: '5',
      valid_votes: '4',
      invalid_votes: '1',
      winning_ballot_letter: 'ת. עדכון',
      winning_votes: '12',
      runner_up_votes: '1',
      margin_votes: '11',
      winning_vote_share: '3',
      אמת: '1',
      מחל: '3',
      פח: '0',
      'ת. עדכון': '12',
    }
    const metadata = new Map([
      [
        'loc:921',
        {
          id: 'loc:921',
          localityId: 'loc:921',
          localityCode: '921',
          nameHe: 'שער מנשה',
          nameEn: "SHA'AR MENASHE",
          statAreaNumber: '',
          yishuvStat2022: '',
        },
      ],
    ])
    const payload = buildResultPayload({
      electionId: 'K18',
      mode: 'locality',
      primaryRows: [row],
      customRows: [],
      metadataById: metadata,
      customMetadataById: new Map(),
      coverage,
      partyRegistry: registryFor('K18', [
        { sourceColumn: 'אמת', totalVotes: 1, nameHe: 'העבודה' },
        { sourceColumn: 'מחל', totalVotes: 3, nameHe: 'הליכוד' },
        { sourceColumn: 'פח', totalVotes: 0, nameHe: 'מהפך בחינוך' },
      ]),
      excludedPartyColumns: ['פח', 'ת. עדכון'],
      validatePartyTotals: true,
    })

    expect(payload.records[0].winner).toEqual({
      partyId: 'מחל',
      votes: 3,
      runnerUpVotes: 1,
      marginVotes: 2,
      voteShare: 0.75,
    })
    expect(payload.parties.map((party) => party.id)).not.toContain('ת. עדכון')
    expect(payload.parties.map((party) => party.id)).not.toContain('פח')
  })

  it('keeps source columns distinct from corrected official ballot letters', () => {
    const registry = registryFor('K19', [
      {
        sourceColumn: 'מרץ',
        ballotLetter: 'מרצ',
        totalVotes: 172403,
        nameHe: 'מרצ',
        nameEn: 'Meretz',
      },
    ])

    expect(registry.get('מרץ')).toMatchObject({
      sourceColumn: 'מרץ',
      ballotLetter: 'מרצ',
      displayNameHe: 'מרצ',
    })
  })
})
