import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import type { Party, ResultRecord } from '../domain/schemas'
import { DetailsPanel } from './DetailsPanel'

const parties: Party[] = Array.from({ length: 10 }, (_, index) => {
  const number = index + 1
  return {
    id: `P${number}`,
    ballotLetter: `P${number}`,
    names: { en: `List ${number}`, he: `רשימה ${number}` },
    listNameHe: `רשימה ${number}`,
    wikipedia: { en: null, he: null },
    color: '#336655',
    colorStatus: 'provisional',
  }
})

const record: ResultRecord = {
  id: 'loc:10',
  geographyType: 'locality',
  names: { en: 'Test locality', he: 'יישוב בדיקה' },
  code: '10',
  localityId: 'loc:10',
  totals: {
    contributingRows: 1,
    contributingKalpis: 1,
    eligibleVoters: 100,
    actualVoters: 90,
    validVotes: 45,
    invalidVotes: 0,
    turnout: 0.9,
  },
  winner: {
    partyId: 'P1',
    votes: 9,
    runnerUpVotes: 8,
    marginVotes: 1,
    voteShare: 0.2,
  },
  partyVotes: Object.fromEntries(
    parties.map((party, index) => [party.id, Math.max(9 - index, 0)]),
  ),
}

describe('DetailsPanel', () => {
  it('renders the complete party result, including rows after eight and zero votes', () => {
    const html = renderToStaticMarkup(
      <DetailsPanel language="en" record={record} parties={parties} />,
    )

    expect(html.match(/<li/g)).toHaveLength(10)
    expect(html.match(/<dt>/g)).toHaveLength(3)
    expect(html).toContain('List 10')
    expect(html).toContain('<span class="party-votes">0</span>')
    expect(html).toContain('<h3>Vote breakdown</h3>')
    expect(html).toContain('1 Polling stations')
    expect(html).toContain('<strong dir="auto">List 1</strong><span>20.0%</span>')
    expect(html).not.toContain('vote share')
    expect(html).toContain('<span class="party-share">20.0%</span>')
    expect(html).toContain('<span class="party-share">0.0%</span>')
    expect(html).not.toContain('<dt>Lead</dt>')
    expect(html).not.toContain('Geography code')
    expect(html).toContain('<div class="details-scroll-body" tabindex="0"')
    expect(html.indexOf('details-heading')).toBeLessThan(
      html.indexOf('details-scroll-body'),
    )
  })

  it('renders a labeled close action when selection clearing is available', () => {
    const html = renderToStaticMarkup(
      <DetailsPanel
        language="en"
        record={record}
        parties={parties}
        onClose={vi.fn()}
      />,
    )

    expect(html).toContain('class="details-close"')
    expect(html).toContain('aria-label="Close results"')
  })

  it('surfaces and highlights both selected comparison parties', () => {
    const html = renderToStaticMarkup(
      <DetailsPanel
        language="en"
        record={record}
        parties={parties}
        highlightedPartyIds={['P2', 'P7']}
      />,
    )

    expect(html).toContain('aria-label="Selected-party comparison"')
    expect(html.match(/class="party-breakdown__highlighted"/g)).toHaveLength(2)
    expect(html).toContain('<strong>8</strong><span>17.8%</span>')
    expect(html).toContain('<strong>3</strong><span>6.7%</span>')
  })

  it('summarizes and highlights every coalition member', () => {
    const html = renderToStaticMarkup(
      <DetailsPanel
        language="en"
        record={record}
        parties={parties}
        highlightedPartyIds={['P1', 'P2', 'P3']}
        highlightedPartiesLabel="Coalition parties"
        highlightedPartyTotalLabel="Coalition total"
        highlightedPartyNotes={{ P2: 'Only some members joined.' }}
      />,
    )

    expect(html).toContain('aria-label="Coalition parties"')
    expect(html).toContain('<span>Coalition total</span><strong>24 · 53.3%</strong>')
    expect(html.match(/class="party-breakdown__highlighted"/g)).toHaveLength(3)
    expect(html).toContain('<strong>7</strong><span>15.6%</span>')
    expect(html).toContain('aria-label="Only some members joined."')
  })

  it('shows attached locality names through a bilingual info tooltip', () => {
    const joinedRecord: ResultRecord = {
      ...record,
      names: { en: "ZOR'A", he: 'צרעה' },
      includedNames: {
        en: ['DEIR RAFAT', "GIV'AT SHEMESH"],
        he: ['דייר ראפאת', 'גבעת שמש'],
      },
    }

    const english = renderToStaticMarkup(
      <DetailsPanel language="en" record={joinedRecord} parties={parties} />,
    )
    const hebrew = renderToStaticMarkup(
      <DetailsPanel language="he" record={joinedRecord} parties={parties} />,
    )

    expect(english).toContain('aria-label="Includes: DEIR RAFAT, GIV&#x27;AT SHEMESH"')
    expect(hebrew).toContain('aria-label="כולל: דייר ראפאת, גבעת שמש"')
  })

  it('shows the complete display-only municipality explanation inline', () => {
    const fallbackRecord: ResultRecord = {
      ...record,
      id: 'municipality-fallback:2011:loc:10',
      geographyType: 'municipality-fallback',
      notice: {
        en: 'No ballots have a supported statistical-area assignment in this election.',
        he: 'אין שיוך נתמך של קלפיות לאזורים סטטיסטיים בבחירות האלה.',
      },
    }

    const html = renderToStaticMarkup(
      <DetailsPanel language="en" record={fallbackRecord} parties={parties} />,
    )

    expect(html).toContain('class="details-notice"')
    expect(html).toContain(
      'No ballots have a supported statistical-area assignment in this election.',
    )
    expect(html).not.toContain('class="included-localities-info"')
  })

  it('shows unavailable turnout instead of a false zero', () => {
    const unavailableRecord: ResultRecord = {
      ...record,
      totals: { ...record.totals, eligibleVoters: 0, turnout: null },
    }

    const html = renderToStaticMarkup(
      <DetailsPanel language="en" record={unavailableRecord} parties={parties} />,
    )

    expect(html).toContain('<dt>Turnout</dt><dd>Unavailable</dd>')
    expect(html).not.toContain('<dt>Turnout</dt><dd>0.0%</dd>')
  })

  it('explains a searchable polygon that has no mapped result', () => {
    const html = renderToStaticMarkup(
      <DetailsPanel
        language="en"
        record={null}
        emptySelection={{
          id: 'stat2011:30001001',
          geographyMode: 'statistical-area',
          names: { en: 'Jerusalem · 1001', he: 'Jerusalem · 1001' },
          aliases: { en: [], he: [] },
          code: '1001',
          hasResults: false,
          notice: {
            en: 'This area is part of an unresolved polling group.',
            he: 'אזור זה הוא חלק מקבוצת קלפיות שטרם נפתרה.',
          },
          bounds: [
            [35.2, 31.7],
            [35.21, 31.71],
          ],
        }}
        parties={parties}
      />,
    )

    expect(html).toContain('<h2 dir="auto">Jerusalem · 1001</h2>')
    expect(html).toContain(
      'No mapped result is available for this geography in the selected election.',
    )
    expect(html).toContain('This area is part of an unresolved polling group.')
    expect(html).toContain('class="details-notice"')
    expect(html).not.toContain('Select an area')
  })

  it('omits invalid votes and turnout from envelope details', () => {
    const envelopeRecord: ResultRecord = {
      ...record,
      id: 'envelope:official',
      geographyType: 'envelope',
      localityId: null,
      totals: { ...record.totals, eligibleVoters: 0, invalidVotes: 3094, turnout: null },
    }

    const html = renderToStaticMarkup(
      <DetailsPanel language="en" record={envelopeRecord} parties={parties} />,
    )

    expect(html.match(/<dt>/g)).toHaveLength(2)
    expect(html).toContain('class="metric-grid metric-grid--envelope"')
    expect(html).not.toContain('Invalid votes')
    expect(html).not.toContain('Turnout')
    expect(html).not.toContain('3,094')
    expect(html).not.toContain('National non-geographic result')
  })
})
