import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { Party } from '../domain/schemas'
import { CoalitionPanel } from './CoalitionPanel'

const anchorParty = party('a', 'Alpha', '#2244aa')

describe('CoalitionPanel', () => {
  it('shows only the coalition gradient without duplicating the member list', () => {
    const html = renderToStaticMarkup(
      <CoalitionPanel
        language="en"
        anchorParty={anchorParty}
        upperBoundShare={0.8}
      />,
    )

    expect(html).toContain('aria-label="Coalition results"')
    expect(html).not.toContain('First coalition')
    expect(html).not.toContain('Alpha')
    expect(html).toContain('0.0%')
    expect(html).toContain('40.0%')
    expect(html).toContain('&gt;80.0%')
    expect(html).not.toContain('No result')
  })
})

function party(id: string, name: string, color: string): Party {
  return {
    id,
    ballotLetter: id.toUpperCase(),
    names: { en: name, he: name },
    listNameHe: name,
    wikipedia: { en: null, he: null },
    color,
    colorStatus: 'reviewed',
  }
}
