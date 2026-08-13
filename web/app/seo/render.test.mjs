import { describe, expect, it } from 'vitest'
import { LANGUAGES } from './config.mjs'
import { handleSeoRequest } from './render.mjs'

const party = {
  id: 'מחל',
  ballotLetter: 'מחל',
  names: { he: 'הליכוד', en: 'Likud' },
  color: '#2455a4',
  votes: 100,
  voteShare: 0.5,
  mandates: 32,
}

const record = {
  id: 'loc:3000',
  code: '3000',
  names: { he: 'ירושלים', en: 'JERUSALEM' },
  totals: {
    eligibleVoters: 200,
    actualVoters: 150,
    validVotes: 145,
    turnout: 0.75,
  },
  winner: { partyId: 'מחל' },
  partyVotes: { מחל: 100 },
}

const catalog = {
  elections: [
    {
      id: 'K25',
      resultUrls: {
        national: 'results/k25/national.json',
        locality: 'results/k25/localities.json',
        'statistical-area': 'results/k25/statistical-areas.json',
      },
    },
  ],
}

const national = {
  totals: { validVotes: 200, contestingParties: 2, mandates: 120 },
  threshold: { share: 0.0325 },
  parties: [party],
  sources: { officialResultsUrl: 'https://example.com/results' },
}

const localityResults = { parties: [party], records: [record] }
const statisticalResults = {
  parties: [party],
  records: [
    {
      ...record,
      id: 'stat2011:30000115',
      code: '30000115',
      names: { he: 'ירושלים · 115', en: 'JERUSALEM · 115' },
    },
  ],
}

const fixtures = new Map([
  ['data/v2/catalog.json', catalog],
  ['data/v2/results/k25/national.json', national],
  ['data/v2/results/k25/localities.json', localityResults],
  ['data/v2/results/k25/statistical-areas.json', statisticalResults],
])

const readJson = async (path) => {
  if (!fixtures.has(path)) {
    throw new Error(`Missing fixture: ${path}`)
  }
  return fixtures.get(path)
}

async function request(path, method = 'GET') {
  return handleSeoRequest(new Request(`https://yoavfried.com${path}`, { method }), { readJson })
}

describe('multilingual SEO routes', () => {
  it.each(LANGUAGES)('renders a complete $code overview with reciprocal hreflang', async ({ code, hreflang }) => {
    const response = await request(`/isr-electionmap/${code}/`)
    const html = await response.text()
    expect(response.status).toBe(200)
    expect(html).toContain(`<html lang="${hreflang}"`)
    expect(html).toContain(`rel="canonical" href="https://yoavfried.com/isr-electionmap/${code}/"`)
    expect(html.match(/rel="alternate" hreflang=/g)).toHaveLength(LANGUAGES.length + 1)
    expect(html).not.toMatch(/\{[a-zA-Z]+\}/)
  })

  it('renders localized 2026 information without claiming results exist', async () => {
    const response = await request('/isr-electionmap/he/elections/2026/')
    const html = await response.text()
    expect(response.status).toBe(200)
    expect(html).toContain('בחירות ישראל 2026')
    expect(html).toContain('עדיין אין במאגר תוצאות רשמיות')
    expect(html).toContain('https://www.gov.il/he/pages/26elections-info')
  })

  it('renders national and exact local result pages from validated data', async () => {
    const electionResponse = await request('/isr-electionmap/en/elections/2022/')
    const electionHtml = await electionResponse.text()
    expect(electionHtml).toContain('Israel election results · 2022')
    expect(electionHtml).toContain('Likud')

    const localResponse = await request('/isr-electionmap/fr/elections/2022/localities/loc%3A3000/')
    const localHtml = await localResponse.text()
    expect(localResponse.status).toBe(200)
    expect(localHtml).toContain('Comment Jerusalem a-t-elle voté en 2022')
    expect(localHtml).toContain('area=loc%3A3000')
  })

  it('returns a real noindex 404 for an unknown result', async () => {
    const response = await request('/isr-electionmap/de/elections/2022/localities/missing/')
    const html = await response.text()
    expect(response.status).toBe(404)
    expect(html).toContain('content="noindex, follow"')
  })

  it('publishes a sitemap index and result-bearing language sitemap', async () => {
    const indexResponse = await request('/isr-electionmap/sitemap.xml')
    const index = await indexResponse.text()
    expect(index).toContain('/sitemaps/he-k25-localities.xml')
    expect(index).toContain('/sitemaps/pl-k17-statistical-areas.xml')

    const dataResponse = await request('/isr-electionmap/en/sitemaps/nope.xml/')
    expect(dataResponse.status).toBe(404)

    const resultSitemapResponse = await request('/isr-electionmap/sitemaps/en-k25-localities.xml')
    const resultSitemap = await resultSitemapResponse.text()
    expect(resultSitemapResponse.status).toBe(200)
    expect(resultSitemap).toContain('/en/elections/2022/localities/loc%3A3000/')
  })

  it('supports HEAD without sending the HTML body', async () => {
    const response = await request('/isr-electionmap/ru/', 'HEAD')
    expect(response.status).toBe(200)
    expect(await response.text()).toBe('')
  })
})
