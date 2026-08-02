import type { StyleSpecification } from 'maplibre-gl'
import type { BasemapMode } from '../domain/schemas'

export const VECTOR_BASEMAP_STYLE_URL =
  import.meta.env.VITE_VECTOR_BASEMAP_STYLE_URL?.trim() ||
  'https://tiles.openfreemap.org/styles/positron'

const neutralStyle: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [
    {
      id: 'paper-background',
      type: 'background',
      paint: { 'background-color': '#f3f0e8' },
    },
  ],
}

export function basemapStyle(mode: BasemapMode): StyleSpecification | string {
  return mode === 'vector' ? VECTOR_BASEMAP_STYLE_URL : neutralStyle
}
