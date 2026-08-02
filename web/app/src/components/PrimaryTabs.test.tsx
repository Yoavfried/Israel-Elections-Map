import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { PrimaryTabs } from './PrimaryTabs'

describe('PrimaryTabs', () => {
  it('marks the active top-level view', () => {
    const html = renderToStaticMarkup(
      <PrimaryTabs activeView="national" language="en" onChange={vi.fn()} />,
    )

    expect(html).toContain('aria-label="Primary views"')
    expect(html).toContain('aria-current="page"')
    expect(html).toContain('National results')
    expect(html).toContain('Single Party Map')
    expect(html).toContain('Party Comparison')
    expect(html).toContain('Full Map')
  })
})
