import { describe, expect, it } from 'vitest'
import {
  parseAddressCandidates,
  resolveAddressCandidates,
  shouldSearchAddresses,
} from './addressSearch'
import type { GeographyBounds, GeographySearchItem } from './schemas'

const bounds: GeographyBounds = [
  [34.2, 29.4],
  [35.9, 33.4],
]

const area: GeographySearchItem = {
  id: 'display:polling-group:K25:5000:143',
  geographyMode: 'statistical-area',
  names: {
    he: 'תל אביב -יפו · 343, 514',
    en: 'TEL AVIV - YAFO · 343, 514',
  },
  aliases: { he: [], en: [] },
  code: '',
  hasResults: true,
  bounds: [
    [34.77, 32.07],
    [34.78, 32.08],
  ],
}

describe('address search', () => {
  it('starts remote lookup only for address-like text containing a number', () => {
    expect(shouldSearchAddresses('דיזנגוף 100 תל אביב')).toBe(true)
    expect(shouldSearchAddresses('תל אביב')).toBe(false)
    expect(shouldSearchAddresses('1024')).toBe(false)
  })

  it('accepts an exact Photon house result and formats an Israeli address', () => {
    const candidates = parseAddressCandidates(
      {
        type: 'FeatureCollection',
        features: [
          {
            type: 'Feature',
            properties: {
              osm_type: 'N',
              osm_id: 2078972536,
              housenumber: '100',
              street: 'דיזנגוף',
              city: 'תל אביב–יפו',
            },
            geometry: { type: 'Point', coordinates: [34.774114, 32.079249] },
          },
        ],
      },
      'דיזנגוף 100 תל אביב',
      bounds,
    )

    expect(candidates).toEqual([
      {
        id: 'N:2078972536',
        label: 'דיזנגוף 100, תל אביב–יפו',
        coordinates: [34.774114, 32.079249],
      },
    ])
  })

  it('rejects a street centroid that does not confirm the requested house number', () => {
    const candidates = parseAddressCandidates(
      {
        type: 'FeatureCollection',
        features: [
          {
            properties: { street: 'דיזנגוף', city: 'תל אביב–יפו' },
            geometry: { type: 'Point', coordinates: [34.774, 32.079] },
          },
        ],
      },
      'דיזנגוף 100 תל אביב',
      bounds,
    )
    expect(candidates).toEqual([])
  })

  it('joins the geocoded point to the visible election-specific polygon', () => {
    const matches = resolveAddressCandidates(
      [
        {
          id: 'N:2078972536',
          label: 'דיזנגוף 100, תל אביב–יפו',
          coordinates: [34.774114, 32.079249],
        },
      ],
      [area],
      {
        type: 'FeatureCollection',
        features: [
          {
            id: area.id,
            properties: { id: area.id },
            geometry: {
              type: 'Polygon',
              coordinates: [
                [
                  [34.77, 32.07],
                  [34.78, 32.07],
                  [34.78, 32.08],
                  [34.77, 32.08],
                  [34.77, 32.07],
                ],
              ],
            },
          },
        ],
      },
    )

    expect(matches).toHaveLength(1)
    expect(matches[0].area.id).toBe(area.id)
    expect(matches[0].coordinates).toEqual([34.774114, 32.079249])
  })
})
