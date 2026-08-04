import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { BasemapSelector } from './BasemapSelector'

describe('BasemapSelector', () => {
  it('renders a labelled two-way control with the active vector option', () => {
    const html = renderToStaticMarkup(
      <BasemapSelector language="en" mode="vector" onChange={vi.fn()} />,
    )

    expect(html).toContain('role="group" aria-label="Basemap"')
    expect(html).toContain('aria-pressed="false" title="Neutral"')
    expect(html).toContain('class="is-active" aria-pressed="true" title="Street map"')
    expect(html).not.toContain('Satellite')
  })

  it('renders the Hebrew selector right-to-left', () => {
    const html = renderToStaticMarkup(
      <BasemapSelector language="he" mode="neutral" onChange={vi.fn()} />,
    )

    expect(html).toContain('class="basemap-selector" dir="rtl" role="group"')
    expect(html).toContain('aria-label="מפת בסיס"')
    expect(html).toContain('class="is-active" aria-pressed="true" title="ללא רקע"')
  })
})
