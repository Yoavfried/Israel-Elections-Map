import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { PartyMapDisplaySelector } from './PartyMapDisplaySelector'

describe('PartyMapDisplaySelector', () => {
  it('renders a two-way areas and vote-circles control', () => {
    const html = renderToStaticMarkup(
      <PartyMapDisplaySelector language="en" mode="circles" onChange={() => undefined} />,
    )

    expect(html).toContain('aria-label="Single-party display"')
    expect(html).toContain('Areas')
    expect(html).toContain('Vote circles')
    expect(html).toContain('aria-pressed="true"')
  })
})
