import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import type { Party } from '../domain/schemas'
import { MobileMenu } from './MobileMenu'

const parties: Party[] = [
  {
    id: 'P1',
    ballotLetter: 'A',
    names: { en: 'First list', he: 'רשימה ראשונה' },
    listNameHe: 'רשימה ראשונה',
    wikipedia: { en: null, he: null },
    color: '#2255aa',
    colorStatus: 'reviewed',
  },
  {
    id: 'P2',
    ballotLetter: 'B',
    names: { en: 'Second list', he: 'רשימה שנייה' },
    listNameHe: 'רשימה שנייה',
    wikipedia: { en: null, he: null },
    color: '#aa3322',
    colorStatus: 'reviewed',
  },
]

describe('MobileMenu', () => {
  it('contains every view and the contextual map controls', () => {
    const html = renderToStaticMarkup(
      <MobileMenu
        language="en"
        activeView="party-comparison"
        elections={[]}
        geographyModes={[]}
        electionId="K25"
        geographyMode="statistical-area"
        basemapMode="neutral"
        partyMapDisplayMode="areas"
        parties={parties}
        selectedPartyId="P1"
        firstPartyId="P1"
        secondPartyId="P2"
        onViewChange={vi.fn()}
        onElectionChange={vi.fn()}
        onGeographyModeChange={vi.fn()}
        onBasemapModeChange={vi.fn()}
        onPartyMapDisplayModeChange={vi.fn()}
        onPartyChange={vi.fn()}
        onFirstPartyChange={vi.fn()}
        onSecondPartyChange={vi.fn()}
      />,
    )

    expect(html).toContain('aria-label="Open menu"')
    expect(html).toContain('Full Map')
    expect(html).toContain('Single Party Map')
    expect(html).toContain('Party Comparison')
    expect(html).toContain('Coalition Results')
    expect(html).toContain('National results')
    expect(html).toContain('First party/list')
    expect(html).toContain('Second party/list')
    expect(html).toContain('Street map')
    expect(html).toContain('href="https://yoavfried.com/"')
    expect(html).toContain("Yoav Fried&#x27;s portfolio")
    expect(html).toContain('Project repository and data downloads')
    expect(html).toContain('lucide-code-xml')
    expect(html).toContain('width="22" height="22"')
  })
})
