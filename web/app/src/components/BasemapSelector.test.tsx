import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { BasemapSelector } from './BasemapSelector'

describe('BasemapSelector', () => {
  it('renders a labelled dropdown with the active vector option', () => {
    const html = renderToStaticMarkup(
      <BasemapSelector language="en" mode="vector" onChange={vi.fn()} />,
    )

    expect(html).toContain('<select aria-label="Basemap">')
    expect(html).toContain('<option value="neutral">Neutral</option>')
    expect(html).toContain('<option value="vector" selected="">Street map</option>')
  })

  it('renders the Hebrew selector right-to-left', () => {
    const html = renderToStaticMarkup(
      <BasemapSelector language="he" mode="neutral" onChange={vi.fn()} />,
    )

    expect(html).toContain('class="basemap-selector" dir="rtl"')
    expect(html).toContain('aria-label="מפת בסיס"')
    expect(html).toContain('<option value="neutral" selected="">ללא רקע</option>')
  })
})
