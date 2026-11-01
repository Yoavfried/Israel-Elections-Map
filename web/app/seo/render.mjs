import {
  APP_PATH,
  BUILD_DATE,
  CANONICAL_BASE,
  CANONICAL_ORIGIN,
  ELECTIONS,
  ELECTION_BY_ID,
  ELECTION_BY_SLUG,
  LANGUAGES,
  LANGUAGE_BY_CODE,
  canonicalUrl,
  coalitionSuffix,
  comparisonSuffix,
  electionSuffix,
  featuresSuffix,
  localizedPath,
  mapUrl,
  partySuffix,
  resultSuffix,
} from './config.mjs'
import { electionDate, formatNumber, formatPercent, translateSeo as t } from './translations.mjs'
import coalitionDefinitions from '../config/coalitions.json' with { type: 'json' }
import { K26_PUBLICATION_STATUS } from './publication-status.mjs'
const COALITION_ELECTIONS = ELECTIONS.filter((election) => coalitionDefinitions[election.id])

const DATA_ROOT = 'data/v2/'
const PORTFOLIO_URL = `${CANONICAL_ORIGIN}/`
const REPOSITORY_URL = 'https://github.com/Yoavfried/israel-election-map'
const VOTER_INFO_URL = 'https://www.gov.il/he/pages/26elections-info'
const OPEN_GRAPH_LOCALES = {
  he: 'he_IL', en: 'en_US', fr: 'fr_FR', es: 'es_ES', ru: 'ru_RU',
  zh: 'zh_CN', ar: 'ar_IL', de: 'de_DE', uk: 'uk_UA', pl: 'pl_PL',
}

export async function handleSeoRequest(request, { readJson }) {
  const url = new URL(request.url)
  if (!url.pathname.startsWith(`${APP_PATH}/`)) {
    return null
  }
  if (!['GET', 'HEAD'].includes(request.method)) {
    return new Response('Method Not Allowed', { status: 405, headers: { Allow: 'GET, HEAD' } })
  }

  const relativePath = url.pathname.slice(APP_PATH.length + 1)
  if (relativePath === 'robots.txt') {
    return textResponse(renderRobots(), 'text/plain; charset=utf-8', request.method)
  }
  if (relativePath === 'sitemap.xml') {
    return xmlResponse(renderSitemapIndex(), request.method)
  }
  if (relativePath.startsWith('sitemaps/')) {
    return renderSitemap(relativePath.slice('sitemaps/'.length), readJson, request.method)
  }

  const segments = relativePath.split('/').filter(Boolean)
  const languageCode = segments[0]
  if (!LANGUAGE_BY_CODE.has(languageCode)) {
    return null
  }
  const canonicalPath = `${APP_PATH}/${segments.join('/')}`
  if (url.pathname !== canonicalPath) {
    return Response.redirect(`${CANONICAL_ORIGIN}${canonicalPath}`, 308)
  }

  if (segments.length === 1) {
    return htmlResponse(renderHomePage(languageCode), 200, request.method)
  }
  if (segments[1] === 'features') {
    if (segments.length === 2) {
      return htmlResponse(renderFeaturesPage(languageCode), 200, request.method)
    }
    if (segments.length === 3 && segments[2] === 'party-comparison') {
      const catalog = await readJson(`${DATA_ROOT}catalog.json`)
      const defaultElection = catalog.elections.find((item) => item.id === ELECTIONS[0].id)
      if (!defaultElection) {
        return htmlResponse(renderNotFoundPage(languageCode), 404, request.method)
      }
      const nationalResults = await readJson(`${DATA_ROOT}${defaultElection.resultUrls.national}`)
      return htmlResponse(
        renderComparisonPage(languageCode, ELECTIONS[0], nationalResults),
        200,
        request.method,
      )
    }
    return htmlResponse(renderNotFoundPage(languageCode), 404, request.method)
  }
  if (segments[1] !== 'elections') {
    return htmlResponse(renderNotFoundPage(languageCode), 404, request.method)
  }

  const election = ELECTION_BY_SLUG.get(segments[2])
  if (!election) {
    return htmlResponse(renderNotFoundPage(languageCode), 404, request.method)
  }
  const catalog = await readJson(`${DATA_ROOT}catalog.json`)
  const catalogElection = catalog.elections.find((item) => item.id === election.id)
  if (!catalogElection) {
    return htmlResponse(renderNotFoundPage(languageCode), 404, request.method)
  }

  if (segments.length === 3) {
    const [nationalResults, localityResults] = await Promise.all([
      readJson(`${DATA_ROOT}${catalogElection.resultUrls.national}`),
      readJson(`${DATA_ROOT}${catalogElection.resultUrls.locality}`),
    ])
    return htmlResponse(
      renderElectionPage(languageCode, election, nationalResults, localityResults),
      200,
      request.method,
    )
  }

  if (segments.length === 4 && segments[3] === 'coalition') {
    const nationalResults = await readJson(`${DATA_ROOT}${catalogElection.resultUrls.national}`)
    return htmlResponse(
      renderCoalitionPage(languageCode, election, nationalResults),
      200,
      request.method,
    )
  }

  if (segments.length === 5 && segments[3] === 'parties') {
    const partyId = safeDecodeURIComponent(segments[4])
    if (!partyId) {
      return htmlResponse(renderNotFoundPage(languageCode), 404, request.method)
    }
    const nationalResults = await readJson(`${DATA_ROOT}${catalogElection.resultUrls.national}`)
    const party = nationalResults.parties.find((item) => item.id === partyId && item.votes > 0)
    if (!party) {
      return htmlResponse(renderNotFoundPage(languageCode), 404, request.method)
    }
    return htmlResponse(
      renderPartyPage(languageCode, election, party),
      200,
      request.method,
    )
  }

  const routeFamily = segments[3]
  const mode = routeFamily === 'localities'
    ? 'locality'
    : routeFamily === 'statistical-areas'
      ? 'statistical-area'
      : null
  if (!mode || segments.length !== 5) {
    return htmlResponse(renderNotFoundPage(languageCode), 404, request.method)
  }

  const recordId = safeDecodeURIComponent(segments[4])
  if (!recordId) {
    return htmlResponse(renderNotFoundPage(languageCode), 404, request.method)
  }
  const results = await readJson(`${DATA_ROOT}${catalogElection.resultUrls[mode]}`)
  const record = results.records.find((item) => item.id === recordId)
  if (!record) {
    return htmlResponse(renderNotFoundPage(languageCode), 404, request.method)
  }
  return htmlResponse(
    renderResultPage(languageCode, election, mode, results, record),
    200,
    request.method,
  )
}

function renderHomePage(languageCode) {
  const electionLinks = [
    ...ELECTIONS.map((election) => `<li><a href="${escapeAttribute(canonicalUrl(languageCode, electionSuffix(election)))}"><strong>${escapeHtml(electionLabel(languageCode, election))}</strong></a></li>`),
  ].join('')
  const suffix = ''
  const body = `
    <main>
      <section class="hero-band">
        <img class="hero-background" src="${APP_PATH}/seo/map-preview.png" width="1440" height="900" alt="${escapeAttribute(t(languageCode, 'siteName'))}" />
        <div class="hero-shade" aria-hidden="true"></div>
        <div class="hero-copy">
          <p class="eyebrow">2006–2026</p>
          <h1>${escapeHtml(t(languageCode, 'homeH1'))}</h1>
          <p class="lead">${escapeHtml(t(languageCode, 'homeLead'))}</p>
          <a class="primary-action" href="${escapeAttribute(mapUrl({ languageCode }))}">${escapeHtml(t(languageCode, 'openMap'))}</a>
        </div>
      </section>
      <section class="content-band" id="elections">
        <div class="section-heading"><h2>${escapeHtml(t(languageCode, 'historyHeading'))}</h2><p>${escapeHtml(t(languageCode, 'historyBody'))}</p></div>
        <ol class="election-list">${electionLinks}</ol>
      </section>
      <section class="content-band split-band">
        <div><h2>${escapeHtml(t(languageCode, 'localHeading'))}</h2><p>${escapeHtml(t(languageCode, 'localBody'))}</p><p><a href="${escapeAttribute(mapUrl({ languageCode }))}">${escapeHtml(t(languageCode, 'openMap'))}</a></p></div>
        <div><h2>${escapeHtml(t(languageCode, 'nationalHeading'))}</h2><p>${escapeHtml(t(languageCode, 'nationalBody'))}</p></div>
      </section>
      <section class="content-band">
        <div class="section-heading"><h2>${escapeHtml(t(languageCode, 'advancedHeading'))}</h2><p>${escapeHtml(t(languageCode, 'advancedBody'))}</p></div>
        <div class="feature-grid">
          ${featureLink(t(languageCode, 'featureCoalitionHeading'), t(languageCode, 'featureCoalitionBody'), canonicalUrl(languageCode, coalitionSuffix(COALITION_ELECTIONS[0])))}
          ${featureLink(t(languageCode, 'featurePartyHeading'), t(languageCode, 'featurePartyBody'), mapUrl({ view: 'party-map', languageCode }))}
          ${featureLink(t(languageCode, 'featureComparisonHeading'), t(languageCode, 'featureComparisonBody'), canonicalUrl(languageCode, comparisonSuffix()))}
        </div>
        <p><a href="${escapeAttribute(canonicalUrl(languageCode, featuresSuffix()))}">${escapeHtml(t(languageCode, 'openFeatures'))}</a></p>
      </section>
      <section class="content-band faq-band">
        <h2>${escapeHtml(t(languageCode, 'whereVoteQ'))}</h2>
        <p>${escapeHtml(t(languageCode, 'whereVoteA'))}</p>
        <p><a href="${VOTER_INFO_URL}" rel="external">${escapeHtml(t(languageCode, 'officialVoterInfo'))}</a></p>
        <h2>${escapeHtml(t(languageCode, 'neighborhoodQ'))}</h2>
        <p>${escapeHtml(t(languageCode, 'neighborhoodA'))}</p>
      </section>
      <section class="content-band source-band">
        <h2>${escapeHtml(t(languageCode, 'sourceHeading'))}</h2>
        <p>${escapeHtml(t(languageCode, 'sourceBody'))}</p>
        <a href="${REPOSITORY_URL}" rel="external">${escapeHtml(t(languageCode, 'repository'))}</a>
      </section>
    </main>`
  const structuredData = [
    {
      '@context': 'https://schema.org', '@type': 'WebSite',
      name: t(languageCode, 'siteName'), url: canonicalUrl(languageCode),
      inLanguage: LANGUAGE_BY_CODE.get(languageCode).hreflang,
    },
    {
      '@context': 'https://schema.org', '@type': 'Dataset',
      name: t(languageCode, 'homeH1'), description: t(languageCode, 'homeDescription'),
      url: canonicalUrl(languageCode), inLanguage: LANGUAGE_BY_CODE.get(languageCode).hreflang,
      license: 'https://github.com/Yoavfried/israel-election-map/blob/main/LICENSE-DATA',
      temporalCoverage: '2006/2026', spatialCoverage: 'Israel',
      creator: { '@type': 'Person', name: 'Yoav Fried' },
    },
    webApplicationStructuredData(languageCode),
  ]
  return renderDocument({
    languageCode, suffix, title: t(languageCode, 'homeTitle'),
    description: t(languageCode, 'homeDescription'), body, structuredData,
  })
}

function renderFeaturesPage(languageCode) {
  const suffix = featuresSuffix()
  const coalitionLinks = COALITION_ELECTIONS.map((election) => `
    <li><a href="${escapeAttribute(canonicalUrl(languageCode, coalitionSuffix(election)))}">${escapeHtml(electionLabel(languageCode, election))}</a></li>`).join('')
  const body = `
    <main>
      ${renderBreadcrumbs(languageCode, [
        [t(languageCode, 'breadcrumbHome'), canonicalUrl(languageCode)],
        [t(languageCode, 'breadcrumbFeatures'), canonicalUrl(languageCode, suffix)],
      ])}
      <section class="page-intro">
        <h1>${escapeHtml(t(languageCode, 'featuresH1'))}</h1>
        <p class="lead">${escapeHtml(t(languageCode, 'featuresLead'))}</p>
        <a class="primary-action" href="${escapeAttribute(mapUrl({ languageCode }))}">${escapeHtml(t(languageCode, 'openMap'))}</a>
      </section>
      <section class="content-band">
        <div class="section-heading"><h2>${escapeHtml(t(languageCode, 'advancedHeading'))}</h2><p>${escapeHtml(t(languageCode, 'advancedBody'))}</p></div>
        <div class="feature-grid">
          ${featureLink(t(languageCode, 'featureFullMapHeading'), t(languageCode, 'featureFullMapBody'), mapUrl({ languageCode }))}
          ${featureLink(t(languageCode, 'featureNationalHeading'), t(languageCode, 'featureNationalBody'), mapUrl({ view: 'national', languageCode }))}
          ${featureLink(t(languageCode, 'featureCoalitionHeading'), t(languageCode, 'featureCoalitionBody'), canonicalUrl(languageCode, coalitionSuffix(COALITION_ELECTIONS[0])))}
          ${featureLink(t(languageCode, 'featurePartyHeading'), t(languageCode, 'featurePartyBody'), mapUrl({ view: 'party-map', languageCode }))}
          ${featureLink(t(languageCode, 'featureComparisonHeading'), t(languageCode, 'featureComparisonBody'), canonicalUrl(languageCode, comparisonSuffix()))}
        </div>
      </section>
      <section class="content-band">
        <h2>${escapeHtml(t(languageCode, 'featureCoalitionHeading'))}</h2>
        <ul class="archive-links">${coalitionLinks}</ul>
      </section>
    </main>`
  return renderDocument({
    languageCode,
    suffix,
    title: t(languageCode, 'featuresTitle'),
    description: t(languageCode, 'featuresDescription'),
    body,
    structuredData: [
      webPageStructuredData(languageCode, suffix, t(languageCode, 'featuresH1'), t(languageCode, 'featuresDescription')),
      webApplicationStructuredData(languageCode, suffix),
      breadcrumbStructuredData(languageCode, suffix, t(languageCode, 'breadcrumbFeatures')),
    ],
  })
}

function renderComparisonPage(languageCode, election, nationalResults) {
  const suffix = comparisonSuffix()
  const parties = nationalResults.parties
    .filter((party) => party.votes > 0)
    .toSorted((left, right) => right.votes - left.votes)
    .slice(0, 2)
  const comparisonPartyIds = parties.length === 2 ? parties.map((party) => party.id) : undefined
  const partyNames = parties.map((party) => partyName(languageCode, party)).join(' · ')
  const body = `
    <main>
      ${renderBreadcrumbs(languageCode, [
        [t(languageCode, 'breadcrumbHome'), canonicalUrl(languageCode)],
        [t(languageCode, 'breadcrumbFeatures'), canonicalUrl(languageCode, featuresSuffix())],
        [t(languageCode, 'breadcrumbComparison'), canonicalUrl(languageCode, suffix)],
      ])}
      <section class="page-intro">
        <h1>${escapeHtml(t(languageCode, 'comparisonH1'))}</h1>
        <p class="lead">${escapeHtml(t(languageCode, 'comparisonLead'))}</p>
        ${partyNames ? `<p class="comparison-example" dir="auto">${escapeHtml(partyNames)} · ${escapeHtml(electionDate(languageCode, election))}</p>` : ''}
        <a class="primary-action" href="${escapeAttribute(mapUrl({ electionId: election.id, view: 'party-comparison', languageCode, comparisonPartyIds }))}">${escapeHtml(t(languageCode, 'openComparison'))}</a>
      </section>
      <section class="content-band split-band">
        <div><h2>${escapeHtml(t(languageCode, 'featureComparisonHeading'))}</h2><p>${escapeHtml(t(languageCode, 'featureComparisonBody'))}</p></div>
        <div><h2>${escapeHtml(t(languageCode, 'featureFullMapHeading'))}</h2><p>${escapeHtml(t(languageCode, 'featureFullMapBody'))}</p></div>
      </section>
    </main>`
  return renderDocument({
    languageCode,
    suffix,
    title: t(languageCode, 'comparisonTitle'),
    description: t(languageCode, 'comparisonDescription'),
    body,
    structuredData: [
      webPageStructuredData(languageCode, suffix, t(languageCode, 'comparisonH1'), t(languageCode, 'comparisonDescription')),
      webApplicationStructuredData(languageCode, suffix),
      breadcrumbStructuredData(languageCode, suffix, t(languageCode, 'breadcrumbComparison')),
    ],
  })
}

function renderCoalitionPage(languageCode, election, nationalResults) {
  const suffix = coalitionSuffix(election)
  const definition = coalitionDefinitions[election.id]
  const memberIds = new Set(definition?.memberPartyIds ?? [])
  const parties = nationalResults.parties
    .filter((party) => memberIds.has(party.id) && party.votes > 0)
    .toSorted((left, right) => right.votes - left.votes)
  const votes = parties.reduce((sum, party) => sum + party.votes, 0)
  const share = nationalResults.totals.validVotes ? votes / nationalResults.totals.validVotes : 0
  const date = electionDate(languageCode, election)
  const values = {
    date,
    votes: formatNumber(languageCode, votes),
    share: formatPercent(languageCode, share, 2),
    lists: formatNumber(languageCode, parties.length),
  }
  const partyRows = parties.map((party) => `
    <tr>
      <th scope="row"><span class="party-swatch" style="--party-color:${escapeAttribute(party.color)}"></span><a href="${escapeAttribute(canonicalUrl(languageCode, partySuffix(election, party.id)))}">${escapeHtml(partyName(languageCode, party))}</a></th>
      <td dir="auto">${escapeHtml(party.ballotLetter)}</td>
      <td>${formatNumber(languageCode, party.votes)}</td>
      <td>${formatPercent(languageCode, party.voteShare, 2)}</td>
      <td>${formatNumber(languageCode, party.mandates)}</td>
    </tr>`).join('')
  const notes = Object.values(definition?.partialMembership ?? {})
    .map((note) => note[languageCode] ?? note.en)
    .filter(Boolean)
    .map((note) => `<p dir="auto">${escapeHtml(note)}</p>`)
    .join('')
  const body = `
    <main>
      ${renderBreadcrumbs(languageCode, [
        [t(languageCode, 'breadcrumbHome'), canonicalUrl(languageCode)],
        [electionLabel(languageCode, election), canonicalUrl(languageCode, electionSuffix(election))],
        [t(languageCode, 'breadcrumbCoalition'), canonicalUrl(languageCode, suffix)],
      ])}
      <section class="page-intro">
        <p class="eyebrow">K${election.number}</p>
        <h1>${escapeHtml(t(languageCode, 'coalitionH1', values))}</h1>
        <p class="lead">${escapeHtml(t(languageCode, 'coalitionLead'))}</p>
        <a class="primary-action" href="${escapeAttribute(mapUrl({ electionId: election.id, view: 'coalition', languageCode }))}">${escapeHtml(t(languageCode, 'openCoalition'))}</a>
      </section>
      <dl class="metric-band">
        ${metric(t(languageCode, 'coalitionVotes'), values.votes)}
        ${metric(t(languageCode, 'coalitionShare'), values.share)}
        ${metric(t(languageCode, 'coalitionLists'), values.lists)}
      </dl>
      ${notes ? `<aside class="notice-band">${notes}</aside>` : ''}
      <section class="content-band table-section"><h2>${escapeHtml(t(languageCode, 'featureCoalitionHeading'))}</h2>${renderResultsTable(languageCode, partyRows)}</section>
    </main>`
  return renderDocument({
    languageCode,
    suffix,
    title: t(languageCode, 'coalitionTitle', values),
    description: t(languageCode, 'coalitionDescription', values),
    body,
    structuredData: [
      datasetStructuredData(languageCode, suffix, t(languageCode, 'coalitionH1', values), t(languageCode, 'coalitionDescription', values), String(election.year)),
      breadcrumbStructuredData(languageCode, suffix, t(languageCode, 'breadcrumbCoalition')),
    ],
  })
}

function renderPartyPage(languageCode, election, party) {
  const suffix = partySuffix(election, party.id)
  const date = electionDate(languageCode, election)
  const name = partyName(languageCode, party)
  const values = {
    party: name,
    date,
    votes: formatNumber(languageCode, party.votes),
    share: formatPercent(languageCode, party.voteShare, 2),
    mandates: formatNumber(languageCode, party.mandates),
  }
  const wikiLanguage = languageCode === 'he' ? 'he' : 'en'
  const wikiUrl = party.wikipedia?.[wikiLanguage]
  const body = `
    <main>
      ${renderBreadcrumbs(languageCode, [
        [t(languageCode, 'breadcrumbHome'), canonicalUrl(languageCode)],
        [electionLabel(languageCode, election), canonicalUrl(languageCode, electionSuffix(election))],
        [t(languageCode, 'breadcrumbPartyMap'), canonicalUrl(languageCode, suffix)],
      ])}
      <section class="page-intro party-intro" style="--party-color:${escapeAttribute(party.color)}">
        <p class="eyebrow">K${election.number} · <span dir="auto">${escapeHtml(party.ballotLetter)}</span></p>
        <h1 dir="auto"><span class="party-swatch party-swatch-large" style="width:18px;height:18px"></span>${escapeHtml(t(languageCode, 'partyH1', values))}</h1>
        <p class="lead">${escapeHtml(t(languageCode, 'partyLead'))}</p>
        <div class="analysis-actions">
          <a class="primary-action" href="${escapeAttribute(mapUrl({ electionId: election.id, view: 'party-map', languageCode, partyId: party.id }))}">${escapeHtml(t(languageCode, 'openPartyMap'))}</a>
          <a href="${escapeAttribute(canonicalUrl(languageCode, comparisonSuffix()))}">${escapeHtml(t(languageCode, 'openComparison'))}</a>
          ${wikiUrl ? `<a href="${escapeAttribute(wikiUrl)}" rel="external">Wikipedia</a>` : ''}
        </div>
      </section>
      <dl class="metric-band">
        ${metric(t(languageCode, 'votes'), values.votes)}
        ${metric(t(languageCode, 'share'), values.share)}
        ${metric(t(languageCode, 'mandates'), values.mandates)}
        ${metric(t(languageCode, 'ballot'), party.ballotLetter)}
      </dl>
      <section class="content-band split-band">
        <div><h2>${escapeHtml(t(languageCode, 'featurePartyHeading'))}</h2><p>${escapeHtml(t(languageCode, 'featurePartyBody'))}</p></div>
        <div><h2>${escapeHtml(t(languageCode, 'featureNationalHeading'))}</h2><p>${escapeHtml(t(languageCode, 'partyDescription', values))}</p></div>
      </section>
    </main>`
  return renderDocument({
    languageCode,
    suffix,
    title: t(languageCode, 'partyTitle', values),
    description: t(languageCode, 'partyDescription', values),
    body,
    structuredData: [
      datasetStructuredData(languageCode, suffix, t(languageCode, 'partyH1', values), t(languageCode, 'partyDescription', values), String(election.year)),
      breadcrumbStructuredData(languageCode, suffix, name),
    ],
  })
}

function renderElectionPage(languageCode, election, nationalResults, localityResults) {
  const suffix = electionSuffix(election)
  const date = electionDate(languageCode, election)
  const winner = nationalResults.parties.toSorted((left, right) => right.votes - left.votes)[0]
  const winnerName = partyName(languageCode, winner)
  const values = {
    date,
    validVotes: formatNumber(languageCode, nationalResults.totals.validVotes),
    winner: winnerName,
    winnerVotes: formatNumber(languageCode, winner.votes),
    mandates: formatNumber(languageCode, winner.mandates),
  }
  const partyRows = nationalResults.parties.map((party) => `
    <tr>
      <th scope="row"><span class="party-swatch" style="--party-color:${escapeAttribute(party.color)}"></span><a href="${escapeAttribute(canonicalUrl(languageCode, partySuffix(election, party.id)))}">${escapeHtml(partyName(languageCode, party))}</a></th>
      <td dir="auto">${escapeHtml(party.ballotLetter)}</td>
      <td>${formatNumber(languageCode, party.votes)}</td>
      <td>${formatPercent(languageCode, party.voteShare, 2)}</td>
      <td>${formatNumber(languageCode, party.mandates)}</td>
    </tr>`).join('')
  const positiveVoteParties = nationalResults.parties.filter((party) => party.votes > 0)
  const comparisonPartyIds = positiveVoteParties.length >= 2
    ? [positiveVoteParties[0].id, positiveVoteParties[1].id]
    : undefined
  const partyAnalysisLinks = positiveVoteParties
    .map((party) => `<li><a href="${escapeAttribute(canonicalUrl(languageCode, partySuffix(election, party.id)))}"><span class="party-swatch" style="--party-color:${escapeAttribute(party.color)}"></span>${escapeHtml(partyName(languageCode, party))}</a></li>`)
    .join('')
  const topLocalities = localityResults.records
    .toSorted((left, right) => right.totals.actualVoters - left.totals.actualVoters)
    .slice(0, 30)
    .map((record) => `<li><a href="${escapeAttribute(canonicalUrl(languageCode, resultSuffix(election, 'locality', record.id)))}"><span dir="auto">${escapeHtml(geographyName(languageCode, record))}</span><strong>${formatNumber(languageCode, record.totals.actualVoters)}</strong></a></li>`)
    .join('')
  const body = `
    <main>
      ${renderBreadcrumbs(languageCode, [
        [t(languageCode, 'breadcrumbHome'), canonicalUrl(languageCode)],
        [t(languageCode, 'breadcrumbElections'), canonicalUrl(languageCode, suffix)],
      ])}
      <section class="page-intro"><p class="eyebrow">K${election.number}</p><h1>${escapeHtml(t(languageCode, 'electionH1', values))}</h1><p class="lead">${escapeHtml(t(languageCode, 'nationalSummary', values))}</p><a class="primary-action" href="${escapeAttribute(mapUrl({ electionId: election.id, view: 'national', languageCode }))}">${escapeHtml(t(languageCode, 'openMap'))}</a></section>
      <dl class="metric-band">
        ${metric(t(languageCode, 'validVotes'), values.validVotes)}
        ${metric(t(languageCode, 'threshold'), formatPercent(languageCode, nationalResults.threshold.share, 2))}
        ${metric(t(languageCode, 'candidateLists'), formatNumber(languageCode, nationalResults.totals.contestingParties))}
        ${metric(t(languageCode, 'seats'), formatNumber(languageCode, nationalResults.totals.mandates))}
      </dl>
      <section class="content-band table-section"><h2>${escapeHtml(t(languageCode, 'nationalHeading'))}</h2>${renderResultsTable(languageCode, partyRows)}</section>
      <section class="content-band">
        <div class="section-heading"><h2>${escapeHtml(t(languageCode, 'analysisHeading'))}</h2><p>${escapeHtml(t(languageCode, 'analysisBody'))}</p></div>
        <div class="analysis-actions">
          ${coalitionDefinitions[election.id] ? `<a class="primary-action" href="${escapeAttribute(canonicalUrl(languageCode, coalitionSuffix(election)))}">${escapeHtml(t(languageCode, 'openCoalition'))}</a>` : ''}
          <a href="${escapeAttribute(mapUrl({ electionId: election.id, view: 'party-comparison', languageCode, comparisonPartyIds }))}">${escapeHtml(t(languageCode, 'openComparison'))}</a>
        </div>
        <ul class="party-link-list">${partyAnalysisLinks}</ul>
      </section>
      <section class="content-band"><div class="section-heading"><h2>${escapeHtml(t(languageCode, 'topLocalities'))}</h2><p>${escapeHtml(t(languageCode, 'localResultsBody'))}</p></div><ol class="locality-links">${topLocalities}</ol></section>
      <section class="content-band source-band"><a href="${escapeAttribute(nationalResults.sources.officialResultsUrl)}" rel="external">${escapeHtml(t(languageCode, 'sourceHeading'))}</a></section>
    </main>`
  return renderDocument({
    languageCode, suffix,
    title: t(languageCode, 'electionTitle', values),
    description: t(languageCode, 'electionDescription', values), body,
    structuredData: [datasetStructuredData(languageCode, suffix, t(languageCode, 'electionH1', values), t(languageCode, 'electionDescription', values), String(election.year)), breadcrumbStructuredData(languageCode, suffix, date)],
  })
}

function renderResultPage(languageCode, election, mode, results, record) {
  const suffix = resultSuffix(election, mode, record.id)
  const date = electionDate(languageCode, election)
  const name = geographyName(languageCode, record)
  const winner = results.parties.find((party) => party.id === record.winner.partyId)
  const winnerName = winner ? partyName(languageCode, winner) : record.winner.partyId
  const values = {
    name, date, winner: winnerName,
    actualVoters: formatNumber(languageCode, record.totals.actualVoters),
    validVotes: formatNumber(languageCode, record.totals.validVotes),
    turnout: record.totals.turnout === null ? '—' : formatPercent(languageCode, record.totals.turnout),
  }
  const titleKey = mode === 'locality' ? 'localityTitle' : 'areaTitle'
  const descriptionKey = mode === 'locality' ? 'localityDescription' : 'areaDescription'
  const headingKey = mode === 'locality' ? 'localityH1' : 'areaH1'
  const partyRows = Object.entries(record.partyVotes)
    .filter(([, votes]) => votes > 0)
    .map(([partyId, votes]) => {
      const party = results.parties.find((item) => item.id === partyId)
      return { party, partyId, votes, share: record.totals.validVotes ? votes / record.totals.validVotes : 0 }
    })
    .toSorted((left, right) => right.votes - left.votes)
    .map(({ party, partyId, votes, share }) => `
      <tr>
        <th scope="row">${party ? `<span class="party-swatch" style="--party-color:${escapeAttribute(party.color)}"></span>` : ''}${escapeHtml(party ? partyName(languageCode, party) : partyId)}</th>
        <td dir="auto">${escapeHtml(party?.ballotLetter ?? partyId)}</td>
        <td>${formatNumber(languageCode, votes)}</td>
        <td>${formatPercent(languageCode, share, 2)}</td>
      </tr>`).join('')
  const mapLanguage = languageCode === 'he' ? 'he' : 'en'
  const mapLink = mapUrl({ electionId: election.id, mode, areaId: record.id, languageCode: mapLanguage })
  const notice = record.notice?.[languageCode === 'he' ? 'he' : 'en']
  const familyLabel = t(languageCode, mode === 'locality' ? 'breadcrumbLocalities' : 'breadcrumbAreas')
  const body = `
    <main>
      ${renderBreadcrumbs(languageCode, [
        [t(languageCode, 'breadcrumbHome'), canonicalUrl(languageCode)],
        [electionLabel(languageCode, election), canonicalUrl(languageCode, electionSuffix(election))],
        [familyLabel, canonicalUrl(languageCode, suffix)],
      ])}
      <section class="page-intro"><p class="eyebrow">${escapeHtml(record.code)}</p><h1 dir="auto">${escapeHtml(t(languageCode, headingKey, values))}</h1><p class="lead">${escapeHtml(t(languageCode, 'resultSummary', values))}</p><a class="primary-action" href="${escapeAttribute(mapLink)}">${escapeHtml(t(languageCode, 'openResultMap'))}</a></section>
      <dl class="metric-band">
        ${metric(t(languageCode, 'eligibleVoters'), formatNumber(languageCode, record.totals.eligibleVoters))}
        ${metric(t(languageCode, 'actualVoters'), values.actualVoters)}
        ${metric(t(languageCode, 'turnout'), values.turnout)}
        ${metric(t(languageCode, 'leadingList'), winnerName)}
      </dl>
      ${notice ? `<aside class="notice-band"><h2>${escapeHtml(t(languageCode, 'noticeHeading'))}</h2><p dir="auto">${escapeHtml(notice)}</p></aside>` : ''}
      <section class="content-band table-section"><h2>${escapeHtml(t(languageCode, 'fullResults'))}</h2>${renderResultsTable(languageCode, partyRows, { includeMandates: false })}</section>
    </main>`
  return renderDocument({
    languageCode, suffix,
    title: t(languageCode, titleKey, values),
    description: t(languageCode, descriptionKey, values), body,
    structuredData: [datasetStructuredData(languageCode, suffix, t(languageCode, headingKey, values), t(languageCode, descriptionKey, values), String(election.year)), breadcrumbStructuredData(languageCode, suffix, name)],
  })
}

function renderNotFoundPage(languageCode) {
  const body = `<main><section class="page-intro error-page"><h1>${escapeHtml(t(languageCode, 'notFoundH1'))}</h1><p class="lead">${escapeHtml(t(languageCode, 'notFoundBody'))}</p><a class="primary-action" href="${escapeAttribute(canonicalUrl(languageCode))}">${escapeHtml(t(languageCode, 'backHome'))}</a></section></main>`
  return renderDocument({ languageCode, suffix: '', title: t(languageCode, 'notFoundTitle'), description: t(languageCode, 'notFoundBody'), body, robots: 'noindex, follow', alternateLinks: false })
}

function renderDocument({ languageCode, suffix, title, description, body, structuredData = [], robots = 'index, follow', alternateLinks = true }) {
  const language = LANGUAGE_BY_CODE.get(languageCode)
  const canonical = canonicalUrl(languageCode, suffix)
  const imageUrl = `${CANONICAL_BASE}/seo/map-preview.png`
  const imageAlt = t(languageCode, 'featuresH1')
  const alternates = alternateLinks
    ? `${LANGUAGES.map((item) => `<link rel="alternate" hreflang="${item.hreflang}" href="${escapeAttribute(canonicalUrl(item.code, suffix))}" />`).join('')}<link rel="alternate" hreflang="x-default" href="${escapeAttribute(canonicalUrl('en', suffix))}" />`
    : ''
  const languageNavigation = LANGUAGES.map((item) => `<a href="${escapeAttribute(canonicalUrl(item.code, suffix))}" lang="${item.hreflang}"${item.code === languageCode ? ' aria-current="page"' : ''}>${escapeHtml(item.label)}</a>`).join('')
  const jsonLd = structuredData.map((item) => `<script type="application/ld+json">${safeJson(item)}</script>`).join('')
  const content = suffix.startsWith('elections/2026')
    ? body.replace('<main>', `<main><section class="notice-band"><p>${escapeHtml(K26_PUBLICATION_STATUS[languageCode])}</p></section>`)
    : body
  return `<!doctype html>
<html lang="${language.hreflang}" dir="${language.dir}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover" />
  <meta name="robots" content="${robots}" />
  <meta name="description" content="${escapeAttribute(description)}" />
  <meta name="theme-color" content="#f4f1e8" />
  <title>${escapeHtml(title)}</title>
  <link rel="canonical" href="${escapeAttribute(canonical)}" />
  ${alternates}
  <meta property="og:type" content="website" />
  <meta property="og:title" content="${escapeAttribute(title)}" />
  <meta property="og:description" content="${escapeAttribute(description)}" />
  <meta property="og:url" content="${escapeAttribute(canonical)}" />
  <meta property="og:locale" content="${OPEN_GRAPH_LOCALES[languageCode]}" />
  ${LANGUAGES.filter((item) => item.code !== languageCode).map((item) => `<meta property="og:locale:alternate" content="${OPEN_GRAPH_LOCALES[item.code]}" />`).join('')}
  <meta property="og:image" content="${imageUrl}" />
  <meta property="og:image:secure_url" content="${imageUrl}" />
  <meta property="og:image:type" content="image/png" />
  <meta property="og:image:width" content="1440" />
  <meta property="og:image:height" content="900" />
  <meta property="og:image:alt" content="${escapeAttribute(imageAlt)}" />
  <meta property="og:site_name" content="${escapeAttribute(t(languageCode, 'siteName'))}" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="${escapeAttribute(title)}" />
  <meta name="twitter:description" content="${escapeAttribute(description)}" />
  <meta name="twitter:image" content="${imageUrl}" />
  <meta name="twitter:image:alt" content="${escapeAttribute(imageAlt)}" />
  ${jsonLd}
  <style>${PAGE_STYLES}</style>
</head>
<body>
  <header class="site-header">
    <a class="brand" href="${escapeAttribute(canonicalUrl(languageCode))}">${escapeHtml(t(languageCode, 'siteName'))}</a>
    <nav class="language-nav" aria-label="${escapeAttribute(t(languageCode, 'languageNav'))}">${languageNavigation}</nav>
    <a class="map-link" href="${escapeAttribute(mapUrl({ languageCode }))}">${escapeHtml(t(languageCode, 'openMap'))}</a>
  </header>
  ${content}
  <footer><p>${escapeHtml(t(languageCode, 'footer'))}</p><p><a href="${escapeAttribute(PORTFOLIO_URL)}">${escapeHtml(t(languageCode, 'portfolioLink'))}</a></p><p>${escapeHtml(t(languageCode, 'updated', { date: BUILD_DATE }))}</p></footer>
</body>
</html>`
}

async function renderSitemap(fileName, readJson, method) {
  if (fileName === 'core.xml') {
    return xmlResponse(renderCoreSitemap(), method)
  }
  const analysisMatch = /^(he|en|fr|es|ru|zh|ar|de|uk|pl)-(k\d+)-analysis\.xml$/.exec(fileName)
  if (analysisMatch) {
    const [, languageCode, electionIdLower] = analysisMatch
    const election = ELECTION_BY_ID.get(electionIdLower.toUpperCase())
    if (!election) {
      return new Response('Not Found', { status: 404 })
    }
    const catalog = await readJson(`${DATA_ROOT}catalog.json`)
    const catalogElection = catalog.elections.find((item) => item.id === election.id)
    if (!catalogElection) {
      return new Response(method === 'HEAD' ? null : 'Not Found', {
        status: 404,
        headers: { 'Content-Type': 'text/plain; charset=utf-8' },
      })
    }
    const nationalResults = await readJson(`${DATA_ROOT}${catalogElection.resultUrls.national}`)
    const urls = [
      ...(coalitionDefinitions[election.id] ? [canonicalUrl(languageCode, coalitionSuffix(election))] : []),
      ...nationalResults.parties
        .filter((party) => party.votes > 0)
        .map((party) => canonicalUrl(languageCode, partySuffix(election, party.id))),
    ]
    return xmlResponse(renderUrlSet(urls), method)
  }
  const match = /^(he|en|fr|es|ru|zh|ar|de|uk|pl)-(k\d+)-(localities|statistical-areas)\.xml$/.exec(fileName)
  if (!match) {
    return new Response('Not Found', { status: 404 })
  }
  const [, languageCode, electionIdLower, family] = match
  const election = ELECTION_BY_ID.get(electionIdLower.toUpperCase())
  if (!election) {
    return new Response('Not Found', { status: 404 })
  }
  const catalog = await readJson(`${DATA_ROOT}catalog.json`)
  const catalogElection = catalog.elections.find((item) => item.id === election.id)
  if (!catalogElection) {
    return new Response(method === 'HEAD' ? null : 'Not Found', {
      status: 404,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    })
  }
  const mode = family === 'localities' ? 'locality' : 'statistical-area'
  const results = await readJson(`${DATA_ROOT}${catalogElection.resultUrls[mode]}`)
  const urls = results.records.map((record) => canonicalUrl(languageCode, resultSuffix(election, mode, record.id)))
  return xmlResponse(renderUrlSet(urls), method)
}

function renderSitemapIndex() {
  const sitemapUrls = [`${CANONICAL_BASE}/sitemaps/core.xml`]
  for (const language of LANGUAGES) {
    for (const election of ELECTIONS) {
      sitemapUrls.push(`${CANONICAL_BASE}/sitemaps/${language.code}-${election.id.toLowerCase()}-analysis.xml`)
      sitemapUrls.push(`${CANONICAL_BASE}/sitemaps/${language.code}-${election.id.toLowerCase()}-localities.xml`)
      sitemapUrls.push(`${CANONICAL_BASE}/sitemaps/${language.code}-${election.id.toLowerCase()}-statistical-areas.xml`)
    }
  }
  return `<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${sitemapUrls.map((url) => `<sitemap><loc>${escapeXml(url)}</loc><lastmod>${BUILD_DATE}</lastmod></sitemap>`).join('')}</sitemapindex>\n`
}

function renderCoreSitemap() {
  const urls = []
  for (const language of LANGUAGES) {
    urls.push(canonicalUrl(language.code))
    urls.push(canonicalUrl(language.code, featuresSuffix()))
    urls.push(canonicalUrl(language.code, comparisonSuffix()))
    for (const election of ELECTIONS) {
      urls.push(canonicalUrl(language.code, electionSuffix(election)))
    }
  }
  return renderUrlSet(urls)
}

function renderUrlSet(urls) {
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${urls.map((url) => `<url><loc>${escapeXml(url)}</loc><lastmod>${BUILD_DATE}</lastmod></url>`).join('')}</urlset>\n`
}

function renderRobots() {
  return `User-agent: *\nAllow: ${APP_PATH}/\n\nSitemap: ${CANONICAL_BASE}/sitemap.xml\n`
}

function featureLink(title, description, url) {
  return `<a class="feature-link" href="${escapeAttribute(url)}"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(description)}</span></a>`
}

function renderResultsTable(languageCode, rows, { includeMandates = true } = {}) {
  const mandateHeading = includeMandates ? `<th scope="col">${escapeHtml(t(languageCode, 'mandates'))}</th>` : ''
  return `<div class="table-scroll"><table><thead><tr><th scope="col">${escapeHtml(t(languageCode, 'party'))}</th><th scope="col">${escapeHtml(t(languageCode, 'ballot'))}</th><th scope="col">${escapeHtml(t(languageCode, 'votes'))}</th><th scope="col">${escapeHtml(t(languageCode, 'share'))}</th>${mandateHeading}</tr></thead><tbody>${rows}</tbody></table></div>`
}

function renderBreadcrumbs(languageCode, entries) {
  return `<nav class="breadcrumbs" aria-label="${escapeAttribute(t(languageCode, 'breadcrumbElections'))}"><ol>${entries.map(([label, url], index) => `<li>${index === entries.length - 1 ? `<span>${escapeHtml(label)}</span>` : `<a href="${escapeAttribute(url)}">${escapeHtml(label)}</a>`}</li>`).join('')}</ol></nav>`
}

function breadcrumbStructuredData(languageCode, suffix, currentName) {
  return {
    '@context': 'https://schema.org', '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: t(languageCode, 'breadcrumbHome'), item: canonicalUrl(languageCode) },
      { '@type': 'ListItem', position: 2, name: currentName, item: canonicalUrl(languageCode, suffix) },
    ],
  }
}

function webPageStructuredData(languageCode, suffix, name, description) {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebPage',
    name,
    description,
    url: canonicalUrl(languageCode, suffix),
    inLanguage: LANGUAGE_BY_CODE.get(languageCode).hreflang,
    dateModified: BUILD_DATE,
    isPartOf: { '@type': 'WebSite', name: t(languageCode, 'siteName'), url: canonicalUrl(languageCode) },
  }
}

function webApplicationStructuredData(languageCode, suffix = '') {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebApplication',
    name: t(languageCode, 'siteName'),
    description: t(languageCode, 'featuresDescription'),
    url: mapUrl({ languageCode }),
    mainEntityOfPage: canonicalUrl(languageCode, suffix),
    applicationCategory: 'DataVisualizationApplication',
    operatingSystem: 'Any',
    browserRequirements: 'Requires JavaScript and a modern web browser',
    isAccessibleForFree: true,
    inLanguage: LANGUAGES.map((language) => language.hreflang),
    featureList: [
      t(languageCode, 'featureFullMapHeading'),
      t(languageCode, 'featureNationalHeading'),
      t(languageCode, 'featureCoalitionHeading'),
      t(languageCode, 'featurePartyHeading'),
      t(languageCode, 'featureComparisonHeading'),
    ],
    creator: { '@type': 'Person', name: 'Yoav Fried' },
  }
}

function datasetStructuredData(languageCode, suffix, name, description, year) {
  return {
    '@context': 'https://schema.org', '@type': 'Dataset', name, description,
    url: canonicalUrl(languageCode, suffix), inLanguage: LANGUAGE_BY_CODE.get(languageCode).hreflang,
    temporalCoverage: year, spatialCoverage: 'Israel', dateModified: BUILD_DATE,
    license: 'https://github.com/Yoavfried/israel-election-map/blob/main/LICENSE-DATA', creator: { '@type': 'Person', name: 'Yoav Fried' },
  }
}

function electionLabel(languageCode, election) {
  const date = electionDate(languageCode, election)
  const labels = {
    he: `הכנסת ה־${election.number} · ${date}`,
    en: `Knesset ${election.number} · ${date}`,
    fr: `${election.number}e Knesset · ${date}`,
    es: `Knéset ${election.number} · ${date}`,
    ru: `Кнессет ${election.number}-го созыва · ${date}`,
    zh: `第${election.number}届以色列议会 · ${date}`,
    ar: `الكنيست الـ${election.number} · ${date}`,
    de: `${election.number}. Knesset · ${date}`,
    uk: `Кнесет ${election.number}-го скликання · ${date}`,
    pl: `${election.number}. Kneset · ${date}`,
  }
  return labels[languageCode] ?? labels.en
}

function partyName(languageCode, party) {
  return languageCode === 'he' ? party.names.he : party.names.en
}

function geographyName(languageCode, record) {
  return languageCode === 'he' ? record.names.he : normalizeEnglishGeographyName(record.names.en)
}

function normalizeEnglishGeographyName(value) {
  const text = String(value ?? '').trim()
  if (!text || text !== text.toUpperCase()) {
    return text
  }
  return text.toLocaleLowerCase('en').replace(/(^|[\s.'’(-])([a-z])/g, (_, prefix, letter) => `${prefix}${letter.toUpperCase()}`)
}

function metric(label, value) {
  return `<div><dt>${escapeHtml(label)}</dt><dd dir="auto">${escapeHtml(value)}</dd></div>`
}

function safeDecodeURIComponent(value) {
  try {
    return decodeURIComponent(value)
  } catch {
    return null
  }
}

function safeJson(value) {
  return JSON.stringify(value).replaceAll('<', '\\u003c')
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character])
}

const escapeAttribute = escapeHtml
const escapeXml = escapeHtml

function htmlResponse(html, status, method) {
  return new Response(method === 'HEAD' ? null : html, {
    status,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': status === 200 ? 'public, max-age=300, s-maxage=86400' : 'public, max-age=60',
      'X-Content-Type-Options': 'nosniff',
    },
  })
}

function xmlResponse(xml, method) {
  return textResponse(xml, 'application/xml; charset=utf-8', method)
}

function textResponse(text, contentType, method) {
  return new Response(method === 'HEAD' ? null : text, {
    headers: { 'Content-Type': contentType, 'Cache-Control': 'public, max-age=300, s-maxage=86400', 'X-Content-Type-Options': 'nosniff' },
  })
}

const PAGE_STYLES = `
:root{font-family:Arial,"Noto Sans",sans-serif;color:#171916;background:#f4f1e8;line-height:1.55;font-synthesis:none}*{box-sizing:border-box}body{margin:0;background:#f4f1e8;color:#171916}a{color:#185b55;text-underline-offset:3px}.site-header{min-height:68px;padding:12px clamp(18px,4vw,64px);display:flex;align-items:center;gap:22px;border-bottom:1px solid #d8d5cc;background:#faf8f2;position:sticky;top:0;z-index:5}.brand{font-weight:800;color:#171916;text-decoration:none;white-space:nowrap}.language-nav{display:flex;gap:5px;flex-wrap:wrap;margin-inline:auto}.language-nav a{font-size:13px;padding:4px 7px;color:#51544f;text-decoration:none;border-bottom:2px solid transparent}.language-nav a[aria-current=page]{color:#171916;border-color:#b14f24}.map-link,.primary-action{display:inline-flex;align-items:center;justify-content:center;min-height:42px;padding:9px 16px;background:#171916;color:#fff;text-decoration:none;font-weight:700;border-radius:5px}.map-link{white-space:nowrap}main{min-height:70vh}.hero-band,.content-band,.page-intro,.metric-band,.notice-band,.breadcrumbs{width:min(1180px,calc(100% - 36px));margin-inline:auto}.hero-band{display:grid;grid-template-columns:minmax(0,.9fr) minmax(420px,1.4fr);gap:42px;align-items:center;padding:56px 0 38px}.hero-copy h1,.page-intro h1{font-size:clamp(34px,5vw,64px);line-height:1.05;margin:8px 0 20px;letter-spacing:0}.lead{font-size:clamp(18px,2vw,23px);max-width:760px;color:#4b4f49}.eyebrow{text-transform:uppercase;font-size:13px;font-weight:800;letter-spacing:0;color:#a24720}.map-preview{margin:0;aspect-ratio:16/10;overflow:hidden;border:1px solid #cac7bf;background:#e8e6df}.map-preview img{display:block;width:100%;height:100%;object-fit:cover}.content-band{padding:42px 0;border-top:1px solid #d4d1c8}.content-band h2,.notice-band h2{font-size:clamp(23px,3vw,34px);line-height:1.2;margin:0 0 10px}.section-heading{max-width:760px;margin-bottom:24px}.feature-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));border-top:1px solid #c9c6bd;border-inline-start:1px solid #c9c6bd;margin-bottom:24px}.feature-link{display:flex;flex-direction:column;gap:7px;min-height:150px;padding:20px;color:#171916;text-decoration:none;border-inline-end:1px solid #c9c6bd;border-bottom:1px solid #c9c6bd}.feature-link:hover{background:#ebe7dd}.feature-link strong{font-size:20px}.feature-link span{color:#646760}.analysis-actions{display:flex;align-items:center;gap:18px;flex-wrap:wrap}.party-link-list{list-style:none;padding:0;margin:24px 0 0;columns:3}.party-link-list li{break-inside:avoid;padding:5px 0}.comparison-example{font-weight:750}.party-swatch-large{width:18px;height:18px}.election-list{list-style:none;padding:0;margin:0;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border-top:1px solid #c9c6bd}.election-list li{border-bottom:1px solid #c9c6bd}.election-list a{display:flex;flex-direction:column;min-height:96px;padding:18px;text-decoration:none;color:#171916}.election-list a:hover{background:#ebe7dd}.election-list span{color:#646760;font-size:14px;margin-top:4px}.election-list .future-link{grid-column:1/-1;background:#e4efe9}.split-band{display:grid;grid-template-columns:1fr 1fr;gap:clamp(32px,7vw,90px)}.faq-band h2:not(:first-child){margin-top:32px}.source-band{padding-bottom:60px}.page-intro{padding:54px 0 36px}.breadcrumbs{padding-top:24px}.breadcrumbs ol{list-style:none;display:flex;flex-wrap:wrap;gap:8px;padding:0;margin:0;color:#686b65;font-size:14px}.breadcrumbs li+li:before{content:"/";margin-inline-end:8px}.metric-band{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));border-block:1px solid #c9c6bd;padding:0}.metric-band div{padding:20px;border-inline-end:1px solid #c9c6bd}.metric-band div:last-child{border-inline-end:0}.metric-band dt{font-size:14px;color:#646760}.metric-band dd{font-size:clamp(21px,3vw,30px);font-weight:800;margin:2px 0 0}.table-section{width:min(1320px,calc(100% - 36px))}.table-scroll{overflow:auto;max-height:680px;border:1px solid #c9c6bd;background:#faf8f2}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}thead{position:sticky;top:0;background:#e9e6dd;z-index:1}th,td{text-align:start;padding:11px 14px;border-bottom:1px solid #d8d5cc}td{white-space:nowrap}tbody th{font-weight:650}.party-swatch{display:inline-block;width:11px;height:11px;background:var(--party-color);margin-inline-end:9px;border-radius:50%;border:1px solid rgba(0,0,0,.2)}.locality-links{list-style:none;padding:0;margin:0;display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid #c9c6bd}.locality-links a{display:flex;justify-content:space-between;gap:18px;padding:12px 8px;border-bottom:1px solid #d3d0c7;text-decoration:none}.archive-links{columns:2}.status-band,.notice-band{padding:24px 0;border-block:1px solid #c9c6bd}.notice-band{background:#fff2c9;padding-inline:clamp(18px,4vw,48px);margin-block:12px 36px}.notice-band h2{font-size:20px;margin-top:0}.error-page{padding-block:100px}footer{padding:28px clamp(18px,4vw,64px);border-top:1px solid #d4d1c8;color:#646760;background:#ece9e0;display:flex;justify-content:space-between;gap:20px;font-size:14px}footer p{margin:0}@media(max-width:820px){.site-header{position:static;align-items:flex-start;flex-wrap:wrap}.brand{width:calc(100% - 140px)}.map-link{margin-inline-start:auto;order:2}.language-nav{order:3;width:100%;margin:0}.hero-band{grid-template-columns:1fr;padding-top:34px}.hero-copy h1,.page-intro h1{font-size:38px}.map-preview{order:-1}.election-list{grid-template-columns:1fr 1fr}.split-band{grid-template-columns:1fr}.party-link-list{columns:2}.metric-band{grid-template-columns:1fr 1fr}.metric-band div:nth-child(2){border-inline-end:0}.metric-band div:nth-child(-n+2){border-bottom:1px solid #c9c6bd}.locality-links{grid-template-columns:1fr 1fr}footer{flex-direction:column}}@media(max-width:520px){.site-header{padding:10px 14px}.brand{width:auto;flex:1}.map-link{font-size:13px;min-height:38px;padding:7px 10px}.hero-band,.content-band,.page-intro,.metric-band,.notice-band,.breadcrumbs,.table-section{width:min(100% - 28px,1180px)}.hero-copy h1,.page-intro h1{font-size:33px}.lead{font-size:18px}.election-list,.locality-links{grid-template-columns:1fr}.party-link-list{columns:1}.metric-band{grid-template-columns:1fr 1fr}.table-scroll{max-height:600px}th,td{padding:9px 10px}.archive-links{columns:1}}
html,body{max-width:100%;overflow-x:hidden}.site-header>*{min-width:0}.language-nav{max-width:100%}.language-nav a{min-width:0;unicode-bidi:isolate}.hero-band{position:relative;isolation:isolate;display:flex;width:100%;min-height:clamp(470px,68vh,650px);margin:0;padding:clamp(48px,8vh,88px) max(18px,calc((100% - 1180px)/2));align-items:flex-end;overflow:hidden;background:#343a35}.hero-background{position:absolute;inset:0;z-index:-2;width:100%;height:100%;object-fit:cover;object-position:center}.hero-shade{position:absolute;inset:0;z-index:-1;background:rgba(10,14,12,.68)}.hero-copy{width:min(820px,100%);color:#fff;text-shadow:0 1px 2px rgba(0,0,0,.55)}.hero-copy h1{font-size:clamp(42px,6vw,76px);max-width:820px}.hero-copy .lead{color:#f4f3ee}.hero-copy .eyebrow{color:#f4b184}.hero-copy .primary-action{background:#fff;color:#171916;text-shadow:none}
@media(max-width:820px){.site-header{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:8px 14px}.brand{width:auto;white-space:normal;overflow-wrap:anywhere}.map-link{order:initial;margin:0;max-width:190px;white-space:normal;text-align:center}.language-nav{grid-column:1/-1;order:initial;display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:2px;width:100%;margin:0}.language-nav a{text-align:center;padding:4px 2px;overflow-wrap:anywhere}.hero-band{min-height:520px;padding:48px 22px}.hero-copy h1{font-size:clamp(38px,10vw,58px)}}
@media(max-width:520px){.site-header{display:block;overflow:hidden;padding:10px 14px}.brand{display:block;width:auto;text-align:center}.language-nav{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));width:auto;margin:8px 0}.map-link{display:flex;width:100%;max-width:none;font-size:12px;min-height:38px;padding:7px 9px}.language-nav a{font-size:12px}.hero-band{width:100%;min-height:500px;padding:42px 18px}.hero-copy h1{font-size:38px}.hero-copy .lead{font-size:18px}.content-band,.page-intro,.metric-band,.notice-band,.breadcrumbs,.table-section{width:min(calc(100% - 28px),1180px)}}
`
