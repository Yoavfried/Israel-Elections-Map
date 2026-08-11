import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import type { ElectionCatalog, NationalResults } from '../domain/schemas'
import { NationalResultsScreen } from './NationalResultsScreen'

const election = {
  id: 'K25',
  number: 25,
  statisticalAreaVintage: 2011,
  dateLabel: '2022',
  label: { en: 'Knesset 25 · 2022', he: 'הכנסת ה־25 · 2022' },
} as ElectionCatalog

const results: NationalResults = {
  schemaVersion: 1,
  electionId: 'K25',
  threshold: { share: 0.0325, votes: 33 },
  totals: {
    validVotes: 1_000,
    representedVotes: 950,
    representedVoteShare: 0.95,
    mandates: 120,
    contestingParties: 2,
    representedParties: 1,
  },
  sources: {
    officialResultsUrl: 'https://example.com/results',
    thresholdSourceUrl: 'https://example.com/threshold',
  },
  parties: [
    {
      id: 'a',
      ballotLetter: 'א',
      names: { en: 'Party A', he: 'מפלגה א' },
      listNameHe: 'מפלגה א',
      wikipedia: {
        he: 'https://he.wikipedia.org/wiki/A',
        en: 'https://en.wikipedia.org/wiki/A',
      },
      color: '#123456',
      colorStatus: 'reviewed',
      votes: 950,
      voteShare: 0.95,
      mandates: 120,
      passedThreshold: true,
    },
    {
      id: 'b',
      ballotLetter: 'ב',
      names: { en: 'Party B', he: 'מפלגה ב' },
      listNameHe: 'מפלגה ב',
      wikipedia: { he: null, en: null },
      color: '#654321',
      colorStatus: 'provisional',
      votes: 50,
      voteShare: 0.05,
      mandates: 0,
      passedThreshold: false,
    },
  ],
}

describe('NationalResultsScreen', () => {
  it('renders every list, mandate total, threshold, colors, and wiki states', () => {
    const html = renderToStaticMarkup(
      <NationalResultsScreen
        language="en"
        elections={[election]}
        electionId="K25"
        results={results}
        loading={false}
        error={null}
        onElectionChange={vi.fn()}
      />,
    )

    expect(html).toContain('National results')
    expect(html).toContain('3.25%')
    expect(html).toContain('Party A')
    expect(html).toContain('Party B')
    expect(html).toContain('background-color:#123456')
    expect(html).toContain('>120</td>')
    expect(html).toContain('Electoral threshold')
    expect(html).toContain('https://en.wikipedia.org/wiki/A')
    expect(html).toContain('aria-label="English Wikipedia: No article recorded"')
    expect(html).toContain('Provisional color')
    expect(html).toContain('class="national-results-content"')
    expect(html).toContain('class="national-party-identity"')
    expect(html).toContain('<strong dir="ltr">1 / 2</strong>')
    expect(html).toContain('List / ballot')
    expect(html).toContain('Votes / share')
    expect(html).toContain('national-ballot-letter--mobile')
    expect(html).toContain('national-vote-share--mobile')
  })
})
