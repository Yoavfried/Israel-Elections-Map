import type { StyleSpecification } from 'maplibre-gl'
import type { BasemapMode } from '../domain/schemas'

export const VECTOR_BASEMAP_STYLE_URL =
  import.meta.env.VITE_VECTOR_BASEMAP_STYLE_URL?.trim() ||
  'https://tiles.openfreemap.org/styles/positron'

export const MAP_CONTEXT_ATTRIBUTION =
  '<a href="https://www.openstreetmap.org/copyright">' +
  '&copy; OpenStreetMap contributors</a>'

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
  if (mode === 'vector') {
    return VECTOR_BASEMAP_STYLE_URL
  }
  return neutralStyle
}
