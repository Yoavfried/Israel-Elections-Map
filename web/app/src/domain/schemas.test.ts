import { describe, expect, it } from 'vitest'
import {
  AppCatalogSchema,
  ElectionResultsSchema,
  GeographySearchIndexSchema,
  NationalResultsSchema,
} from './schemas'

const coverage = {
  totalRows: 100,
  totalActualVoters: 10_000,
  mappedRows: 80,
  mappedActualVoters: 8_000,
  mappedActualVoterShare: 0.8,
  pendingRows: 20,
  pendingActualVoters: 2_000,
  unmappedRows: 20,
  unmappedActualVoters: 2_000,
}

describe('web data contracts', () => {
  it('accepts a versioned catalog', () => {
    const catalog = AppCatalogSchema.parse({
      schemaVersion: 5,
      buildId: '12345678abcdef00',
      generatedAt: '2026-07-14T10:00:00.000Z',
      source: {
        statisticalAreaVintages: [1995, 2008, 2011, 2022],
        localityGeometryVintage: 2022,
        electionRange: { first: 'K17', last: 'K25' },
        assignmentStatus: 'partial',
        resultColumnExclusions: [],
      },
      bounds: [
        [34.2, 29.4],
        [35.9, 33.4],
      ],
      partyColorPolicy: { status: 'provisional', description: 'Pending review' },
      geographyModes: [
        {
          id: 'statistical-area',
          vintage: 2022,
          label: { en: 'Statistical areas', he: 'אזורים סטטיסטיים' },
          geometryUrl: 'geographies/statistical-areas.geojson',
          markerGeometryUrl: 'geographies/statistical-area-markers.geojson',
          featureCount: 3_857,
          markerFeatureCount: 100,
        },
        {
          id: 'locality',
          vintage: 2022,
          label: { en: 'Localities', he: 'יישובים' },
          geometryUrl: 'geographies/localities.geojson',
          markerGeometryUrl: 'geographies/locality-markers.geojson',
          featureCount: 1_329,
          markerFeatureCount: 100,
        },
      ],
      elections: [
        {
          id: 'K25',
          number: 25,
          statisticalAreaVintage: 2011,
          dateLabel: '2022',
          label: { en: 'Knesset 25', he: 'הכנסת ה־25' },
          coverageByMode: {
            'statistical-area': coverage,
            locality: { ...coverage, mappedActualVoterShare: 1 },
          },
          resultUrls: {
            'statistical-area': 'results/k25/statistical-areas.json',
            locality: 'results/k25/localities.json',
            national: 'results/k25/national.json',
            search: 'results/k25/search.json',
          },
          geographiesByMode: {
            'statistical-area': {
              vintage: 2011,
              geometryUrl: 'geographies/statistical-areas-2011.geojson',
              markerGeometryUrl: 'geographies/statistical-area-markers-2011.geojson',
              featureCount: 2_848,
              markerFeatureCount: 118,
            },
            locality: {
              vintage: 2022,
              geometryUrl: 'geographies/localities.geojson',
              markerGeometryUrl: 'geographies/locality-markers.geojson',
              featureCount: 1_329,
              markerFeatureCount: 100,
            },
          },
        },
      ],
      assets: [{ path: 'result.json', bytes: 12, sha256: 'a'.repeat(64) }],
    })

    expect(catalog.elections[0].id).toBe('K25')
  })

  it('rejects coverage values above 100 percent', () => {
    const result = ElectionResultsSchema.safeParse({
      schemaVersion: 2,
      electionId: 'K25',
      geographyMode: 'locality',
      coverage: { ...coverage, mappedActualVoterShare: 1.01 },
      parties: [],
      records: [],
      envelope: null,
      hiddenGeographyIds: [],
    })

    expect(result.success).toBe(false)
  })

  it('accepts a bounded bilingual geography search index', () => {
    const searchIndex = GeographySearchIndexSchema.parse({
      schemaVersion: 1,
      electionId: 'K25',
      items: [
        {
          id: 'stat2011:30001024',
          geographyMode: 'statistical-area',
          names: { en: 'Jerusalem · 1024', he: 'ירושלים · 1024' },
          aliases: { en: ['Jerusalem'], he: ['ירושלים'] },
          code: '1024',
          hasResults: true,
          bounds: [
            [35.2, 31.7],
            [35.3, 31.8],
          ],
        },
      ],
    })

    expect(searchIndex.items[0].bounds[1][0]).toBe(35.3)
  })

  it('accepts a documented display-only municipality result', () => {
    const parsed = ElectionResultsSchema.parse({
      schemaVersion: 2,
      electionId: 'K20',
      geographyMode: 'statistical-area',
      coverage,
      parties: [],
      records: [
        {
          id: 'municipality-fallback:2011:loc:10',
          geographyType: 'municipality-fallback',
          names: { en: 'Locality', he: 'יישוב' },
          notice: {
            en: 'No ballots have a supported statistical-area assignment.',
            he: 'אין שיוך נתמך של קלפיות לאזורים סטטיסטיים.',
          },
          code: '10',
          localityId: 'loc:10',
          totals: {
            contributingRows: 2,
            contributingKalpis: 2,
            eligibleVoters: 100,
            actualVoters: 80,
            validVotes: 79,
            invalidVotes: 1,
            turnout: 0.8,
          },
          winner: {
            partyId: '',
            votes: 0,
            runnerUpVotes: 0,
            marginVotes: 0,
            voteShare: 0,
          },
          partyVotes: {},
        },
      ],
      envelope: null,
      hiddenGeographyIds: [],
    })

    expect(parsed.records[0].geographyType).toBe('municipality-fallback')
  })

  it('accepts a complete national result payload', () => {
    const parsed = NationalResultsSchema.parse({
      schemaVersion: 1,
      electionId: 'K25',
      threshold: { share: 0.0325, votes: 154_855 },
      totals: {
        validVotes: 4_764_742,
        representedVotes: 4_347_342,
        representedVoteShare: 0.9124,
        mandates: 120,
        contestingParties: 40,
        representedParties: 10,
      },
      sources: {
        officialResultsUrl: 'https://example.com/results',
        thresholdSourceUrl: 'https://example.com/threshold',
      },
      parties: [
        {
          id: 'party',
          ballotLetter: 'א',
          names: { en: 'Party', he: 'מפלגה' },
          listNameHe: 'מפלגה',
          wikipedia: { he: null, en: null },
          color: '#123456',
          colorStatus: 'reviewed',
          votes: 1_000_000,
          voteShare: 0.21,
          mandates: 30,
          passedThreshold: true,
        },
      ],
    })

    expect(parsed.threshold.share).toBe(0.0325)
    expect(parsed.parties[0].mandates).toBe(30)
  })
})
