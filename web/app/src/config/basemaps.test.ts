import type { StyleSpecification } from 'maplibre-gl'
import { describe, expect, it } from 'vitest'
import {
  basemapStyle,
  VECTOR_BASEMAP_STYLE_URL,
} from './basemaps'

describe('basemap configuration', () => {
  it('keeps the vector style URL replaceable', () => {
    expect(basemapStyle('vector')).toBe(VECTOR_BASEMAP_STYLE_URL)
  })

  it('keeps neutral mode network-independent', () => {
    const style = basemapStyle('neutral') as StyleSpecification

    expect(style.sources).toEqual({})
    expect(style.layers).toHaveLength(1)
  })
})
