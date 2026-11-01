import { describe, expect, it } from 'vitest'
import { LANGUAGES } from './config.mjs'
import { handleSeoRequest } from './render.mjs'
import { K26_PUBLICATION_STATUS } from './publication-status.mjs'

const party = {
  id: 'מחל',
  ballotLetter: 'מחל',
  names: { he: 'הליכוד', en: 'Likud' },
  color: '#2455a4',
  votes: 100,
  voteShare: 0.5,
  mandates: 32,
}

const secondParty = {
  id: 'שס',
  ballotLetter: 'שס',
  names: { he: 'ש"ס', en: 'Shas' },
  color: '#171916',
  votes: 80,
  voteShare: 0.4,
  mandates: 11,
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
      id: 'K26',
      resultUrls: {
        national: 'results/k26/national.json',
        locality: 'results/k26/localities.json',
        'statistical-area': 'results/k26/statistical-areas.json',
      },
    },
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
  parties: [party, secondParty],
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
  ['data/v2/results/k26/national.json', national],
  ['data/v2/results/k26/localities.json', localityResults],
  ['data/v2/results/k26/statistical-areas.json', statisticalResults],
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
    const response = await request(`/isr-electionmap/${code}`)
    const html = await response.text()
    expect(response.status).toBe(200)
    expect(html).toContain(`<html lang="${hreflang}"`)
    expect(html).toContain('<link rel="icon" href="/isr-electionmap/favicon.svg" type="image/svg+xml" />')
    expect(html).toContain(`rel="canonical" href="https://yoavfried.com/isr-electionmap/${code}"`)
    expect(html).toContain('<a href="https://yoavfried.com/">')
    expect(html.match(/rel="alternate" hreflang=/g)).toHaveLength(LANGUAGES.length + 1)
    expect(html).not.toMatch(/\{[a-zA-Z]+\}/)
  })

  it('labels the portfolio return link in Hebrew and English', async () => {
    const hebrew = await (await request('/isr-electionmap/he')).text()
    const english = await (await request('/isr-electionmap/en')).text()
    expect(hebrew).toContain('<a href="https://yoavfried.com/">האתר של יואב פריד</a>')
    expect(english).toContain('<a href="https://yoavfried.com/">Yoav Fried&#39;s portfolio</a>')
  })

  it('renders the published 2026 results instead of the obsolete future-election page', async () => {
    const response = await request('/isr-electionmap/he/elections/2026')
    const html = await response.text()
    expect(response.status).toBe(200)
    expect(html).toContain('2026')
    expect(html).toContain('הליכוד')
    expect(html).toContain('election=K26')
    expect(html).not.toContain('עדיין אין במאגר תוצאות רשמיות')
  })

  it('returns a real 404 for the not-yet-formed K26 coalition', async () => {
    const response = await request('/isr-electionmap/en/elections/2026/coalition')
    expect(response.status).toBe(404)
    expect(await response.text()).toContain('Page not found')
  })

  it.each(LANGUAGES)('discloses K26 publication and geography limits in $code', async ({ code }) => {
    const response = await request(`/isr-electionmap/${code}/elections/2026`)
    expect(response.status).toBe(200)
    const html = await response.text()
    expect(html).toContain(K26_PUBLICATION_STATUS[code])
    expect(html).not.toContain('not yet certified')
    expect(html).not.toContain('טרם אושרו סופית')
    expect(html).not.toContain('/elections/2026/coalition')
  })

  it.each(LANGUAGES)('publishes advanced feature copy in $code', async ({ code }) => {
    const response = await request(`/isr-electionmap/${code}/features`)
    const html = await response.text()
    expect(response.status).toBe(200)
    expect(html).toContain('WebApplication')
    expect(html).toContain(`/isr-electionmap/${code}/features/party-comparison`)
    expect(html).toContain(`/isr-electionmap/${code}/elections/2022/coalition`)
    expect(html).not.toMatch(/\{[a-zA-Z]+\}/)
  })

  it('renders coalition, single-party, and comparison entry pages with stable app links', async () => {
    const coalitionResponse = await request('/isr-electionmap/en/elections/2022/coalition')
    const coalitionHtml = await coalitionResponse.text()
    expect(coalitionResponse.status).toBe(200)
    expect(coalitionHtml).toContain('Coalition results · 2022')
    expect(coalitionHtml).toContain('view=coalition')
    expect(coalitionHtml).toContain('Likud')
    expect(coalitionHtml).toContain('Shas')

    const partyResponse = await request('/isr-electionmap/en/elections/2022/parties/%D7%9E%D7%97%D7%9C')
    const partyHtml = await partyResponse.text()
    expect(partyResponse.status).toBe(200)
    expect(partyHtml).toContain('Likud · 2022 election')
    expect(partyHtml).toContain('view=party-map')
    expect(partyHtml).toContain('party=%D7%9E%D7%97%D7%9C')

    const comparisonResponse = await request('/isr-electionmap/en/features/party-comparison')
    const comparisonHtml = await comparisonResponse.text()
    expect(comparisonResponse.status).toBe(200)
    expect(comparisonHtml).toContain('view=party-comparison')
    expect(comparisonHtml).toContain('party1=%D7%9E%D7%97%D7%9C')
    expect(comparisonHtml).toContain('party2=%D7%A9%D7%A1')
  })

  it('publishes complete social metadata for share previews', async () => {
    const response = await request('/isr-electionmap/en')
    const html = await response.text()
    expect(html).toContain('property="og:image:width" content="1440"')
    expect(html).toContain('property="og:locale" content="en_US"')
    expect(html).toContain('name="twitter:title"')
    expect(html).toContain('name="twitter:description"')
    expect(html).toContain('name="twitter:image:alt"')
  })

  it('renders national and exact local result pages from validated data', async () => {
    const electionResponse = await request('/isr-electionmap/en/elections/2022')
    const electionHtml = await electionResponse.text()
    expect(electionHtml).toContain('Israel election results · 2022')
    expect(electionHtml).toContain('Likud')

    const localResponse = await request('/isr-electionmap/fr/elections/2022/localities/loc%3A3000')
    const localHtml = await localResponse.text()
    expect(localResponse.status).toBe(200)
    expect(localHtml).toContain('Comment Jerusalem a-t-elle voté en 2022')
    expect(localHtml).toContain('area=loc%3A3000')
  })

  it('returns a real noindex 404 for an unknown result', async () => {
    const response = await request('/isr-electionmap/de/elections/2022/localities/missing')
    const html = await response.text()
    expect(response.status).toBe(404)
    expect(html).toContain('content="noindex, follow"')
  })

  it('publishes a sitemap index and result-bearing language sitemap', async () => {
    const indexResponse = await request('/isr-electionmap/sitemap.xml')
    const index = await indexResponse.text()
    expect(index).toContain('/sitemaps/he-k25-localities.xml')
    expect(index).toContain('/sitemaps/he-k25-analysis.xml')
    expect(index).toContain('/sitemaps/pl-k17-statistical-areas.xml')

    const dataResponse = await request('/isr-electionmap/en/sitemaps/nope.xml')
    expect(dataResponse.status).toBe(404)

    const resultSitemapResponse = await request('/isr-electionmap/sitemaps/en-k25-localities.xml')
    const resultSitemap = await resultSitemapResponse.text()
    expect(resultSitemapResponse.status).toBe(200)
    expect(resultSitemap).toContain('/en/elections/2022/localities/loc%3A3000')

    const analysisSitemapResponse = await request('/isr-electionmap/sitemaps/en-k25-analysis.xml')
    const analysisSitemap = await analysisSitemapResponse.text()
    expect(analysisSitemapResponse.status).toBe(200)
    expect(analysisSitemap).toContain('/en/elections/2022/coalition')
    expect(analysisSitemap).toContain('/en/elections/2022/parties/%D7%9E%D7%97%D7%9C')
  })

  it('supports HEAD without sending the HTML body', async () => {
    const response = await request('/isr-electionmap/ru', 'HEAD')
    expect(response.status).toBe(200)
    expect(await response.text()).toBe('')
  })

  it('normalizes trailing slashes to the canonical host convention', async () => {
    const response = await request('/isr-electionmap/en/')
    expect(response.status).toBe(308)
    expect(response.headers.get('location')).toBe('https://yoavfried.com/isr-electionmap/en')
  })
})
