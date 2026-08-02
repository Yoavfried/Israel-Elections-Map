import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import type { Party } from '../domain/schemas'
import { PartyComparisonPanel } from './PartyComparisonPanel'

const parties: Party[] = [
  party('a', 'Alpha', '#2244aa'),
  party('b', 'Beta', '#cc3322'),
  party('c', 'Gamma', '#228855'),
]

describe('PartyComparisonPanel', () => {
  it('renders two exclusive party selectors and explicit neutral states', () => {
    const html = renderToStaticMarkup(
      <PartyComparisonPanel
        language="en"
        parties={parties}
        firstPartyId="a"
        secondPartyId="b"
        onFirstPartyChange={vi.fn()}
        onSecondPartyChange={vi.fn()}
      />,
    )

    expect(html).toContain('aria-label="Party comparison controls"')
    expect(html.match(/<select/g)).toHaveLength(2)
    expect(html).toContain('<option value="b" disabled="">Beta (b)</option>')
    expect(html).toContain('Share between selected parties')
    expect(html).toContain('Equal')
    expect(html).toContain('Neither party received votes')
    expect(html).toContain('No result')
  })
})

function party(id: string, name: string, color: string): Party {
  return {
    id,
    ballotLetter: id,
    names: { en: name, he: name },
    listNameHe: name,
    wikipedia: { en: null, he: null },
    color,
    colorStatus: 'reviewed',
  }
}
