import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import type { Party } from '../domain/schemas'
import { PartyMapPanel } from './PartyMapPanel'

const parties: Party[] = [
  {
    id: 'a',
    ballotLetter: 'A',
    names: { en: 'Alpha', he: 'Alpha' },
    listNameHe: 'Alpha',
    wikipedia: { en: null, he: null },
    color: '#2244aa',
    colorStatus: 'reviewed',
  },
]

describe('PartyMapPanel', () => {
  it('renders the selected party and numerical gradient domain', () => {
    const html = renderToStaticMarkup(
      <PartyMapPanel
        language="en"
        parties={parties}
        selectedPartyId="a"
        upperBoundShare={0.4}
        onPartyChange={vi.fn()}
      />,
    )

    expect(html).toContain('Single Party Map controls')
    expect(html).toContain('<option value="a" dir="auto" selected="">Alpha (A)</option>')
    expect(html).toContain('0.0%')
    expect(html).toContain('20.0%')
    expect(html).toContain('&gt;40.0%')
    expect(html).toContain('Above the positive-share 95th percentile: 40.0%')
    expect(html).toContain('No result')
  })
})
