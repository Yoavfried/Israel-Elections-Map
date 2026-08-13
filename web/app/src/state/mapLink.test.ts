import { describe, expect, it } from 'vitest'
import {
  applyMapLinkPreferences,
  buildMapLinkSearch,
  parseMapLinkSearch,
} from './mapLink'

describe('map deep links', () => {
  it('parses a localized statistical-area result link', () => {
    expect(
      parseMapLinkSearch(
        '?election=K25&mode=statistical-area&view=map&lang=he&area=stat2011%3A30000115',
      ),
    ).toEqual({
      electionId: 'K25',
      geographyMode: 'statistical-area',
      language: 'he',
      view: 'map',
      areaId: 'stat2011:30000115',
      partyId: undefined,
      comparisonPartyIds: undefined,
      partyMapDisplayMode: undefined,
    })
  })

  it('round-trips single-party and comparison selections', () => {
    const partySearch = buildMapLinkSearch({
      electionId: 'K25',
      geographyMode: 'locality',
      language: 'en',
      view: 'party-map',
      partyId: 'מרצ',
      partyMapDisplayMode: 'circles',
    })
    expect(parseMapLinkSearch(partySearch)).toMatchObject({
      electionId: 'K25',
      geographyMode: 'locality',
      view: 'party-map',
      partyId: 'מרצ',
      partyMapDisplayMode: 'circles',
    })

    const comparisonSearch = buildMapLinkSearch({
      electionId: 'K24',
      geographyMode: 'statistical-area',
      language: 'he',
      view: 'party-comparison',
      comparisonPartyIds: ['מחל', 'אמת'],
    })
    expect(parseMapLinkSearch(comparisonSearch)).toMatchObject({
      view: 'party-comparison',
      comparisonPartyIds: ['מחל', 'אמת'],
    })
  })

  it('ignores unsupported values without replacing valid stored preferences', () => {
    const link = parseMapLinkSearch('?election=K99&mode=ward&view=nope&lang=fr')
    expect(
      applyMapLinkPreferences(
        {
          language: 'en',
          electionId: 'K24',
          geographyMode: 'locality',
          basemapMode: 'neutral',
        },
        link,
      ),
    ).toEqual({
      language: 'en',
      electionId: 'K24',
      geographyMode: 'locality',
      basemapMode: 'neutral',
    })
    expect(link.view).toBe('map')
  })
})
