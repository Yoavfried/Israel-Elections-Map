import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { Party, ResultRecord } from '../domain/schemas'
import { EnvelopeSummary } from './EnvelopeSummary'

const party: Party = {
  id: 'A',
  ballotLetter: 'A',
  names: { en: 'List A', he: 'רשימה א' },
  listNameHe: 'רשימה א',
  wikipedia: { en: null, he: null },
  color: '#336655',
  colorStatus: 'reviewed',
}

const envelope: ResultRecord = {
  id: 'envelope:official',
  geographyType: 'envelope',
  names: { en: 'Envelope votes', he: 'מעטפות חיצוניות' },
  code: 'envelope',
  localityId: null,
  totals: {
    contributingRows: 2,
    contributingKalpis: 2,
    eligibleVoters: 0,
    actualVoters: 100,
    validVotes: 98,
    invalidVotes: 2,
    turnout: null,
  },
  winner: {
    partyId: 'A',
    votes: 60,
    runnerUpVotes: 38,
    marginVotes: 22,
    voteShare: 60 / 98,
  },
  partyVotes: { A: 60, B: 38 },
}

describe('EnvelopeSummary', () => {
  it('renders a selectable national result without map placement', () => {
    const html = renderToStaticMarkup(
      <EnvelopeSummary
        language="en"
        record={envelope}
        parties={[party]}
        selected
        onSelect={() => undefined}
      />,
    )

    expect(html).toContain('Double envelopes')
    expect(html).toContain('envelope-summary__chevron')
    expect(html).not.toContain('National result')
    expect(html).toContain('100')
    expect(html).toContain('aria-pressed="true"')
  })
})
