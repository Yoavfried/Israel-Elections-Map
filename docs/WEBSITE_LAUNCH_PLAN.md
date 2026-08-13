# Website Launch, SEO, and Advertising Plan

Last updated: 2026-08-11

This plan covers the three active public-website workstreams:

1. production hosting and domain launch;
2. search-engine discoverability and crawlable result pages;
3. Google AdSense integration and reviewed ad placement.

The implementation order is hosting foundation, SEO surfaces, public launch,
and only then advertising. AdSense should not be added to the current single-
URL application before crawlable content, privacy controls, and a production
domain are in place.

## Current Technical Baseline

The map is a static Vite/React application. It does not require a database,
user accounts, a private API, or server-side election computation. The local
build produces 84 deployable files totaling about 106.28 MiB; the largest file
is 13.51 MiB. Public source maps account for part of that total and should be
disabled for production deployments.

The current application has two important launch constraints:

- almost all useful content is rendered by JavaScript under one URL, which is
  a weak SEO structure even though Google can render JavaScript;
- the build reads ignored `data/processed/` inputs, so a normal fresh-clone
  cloud build cannot reproduce the deployed map.

The production plan must preserve the repository boundary: public data remains
downloadable under `public-data/`, while locally generated web payloads remain
disposable deployment artifacts rather than a second committed data release.

## Recommended Production Architecture

Use **Cloudflare Pages with Wrangler Direct Upload** for the initial launch.
This requires no paid storage and matches the current local-build workflow.

1. Build the complete application locally with `npm run build`.
2. Deploy `web/app/dist/` with Wrangler from `web/app/`.
3. Attach the owned domain in the Cloudflare Pages dashboard.
4. Use Pages Functions only for crawlable SEO HTML routes.
5. Keep map assets, election JSON, JavaScript, CSS, and images as static files.

The current build fits the documented free Pages limits of 20,000 files and
25 MiB per file. Static asset requests are free and unlimited. Pages Function
requests use the Workers Free quota, currently 100,000 requests per day. A
`_routes.json` file must restrict Function invocation to SEO routes so normal
map and asset requests remain static.

The SEO Function can read compact build-generated indexes through
`env.ASSETS.fetch()`. No D1 database, KV namespace, R2 bucket, paid server, or
paid object storage is required for the initial site.

### Deployment Shape

Add these production-only artifacts during implementation:

- `wrangler.toml` or the current Wrangler JSON configuration;
- `functions/` handlers for crawlable result routes;
- `_routes.json` limiting Function execution to those routes;
- `_headers` for reviewed security and cache headers;
- `_redirects` for one canonical host and legacy aliases;
- `404.html` or a Function-generated real 404 for unknown content routes;
- `robots.txt`, a sitemap index, and generated sitemap files;
- a local `deploy` command that builds, validates, and uploads `dist/`.

Wrangler Direct Upload is intentional because private working inputs are not in
the public repository. The deployment command should fail unless the local data
compiler and full test suite pass.

### Domain And Network Setup

- Select one canonical HTTPS host, preferably the apex domain.
- Redirect `www` and the production `pages.dev` hostname to that canonical
  host. Do not allow duplicate production content on several hosts.
- An apex domain on Pages requires the domain to use Cloudflare nameservers. A
  subdomain can instead use a CNAME after it is associated with the Pages
  project.
- Keep the existing neutral-map fallback. OpenFreeMap remains an external
  basemap dependency.
- The public Photon endpoint permits reasonable use but may throttle extensive
  traffic and provides no availability guarantee. Keep the configurable
  endpoint, client debounce, request bounds, and session cache. At meaningful
  traffic, use a contracted or self-hosted endpoint or temporarily disable
  numbered-address lookup; a proxy alone does not solve upstream capacity.

## SEO Architecture

### Crawlable Routes

Serve useful HTML for both Hebrew and English. Every route must return its
title, description, heading, key result facts, links, and structured data in
the initial response rather than waiting for React to render them.

Recommended route families:

- `/{lang}/` - project and map overview;
- `/{lang}/elections/{year}/` - national election result;
- `/{lang}/elections/{year}/localities/{code}-{slug}/` - one election and
  locality;
- `/{lang}/elections/{year}/statistical-areas/{vintage}/{code}/` - one
  election and displayed statistical result unit;
- `/{lang}/elections/{year}/parties/{party-id}-{slug}/` - one party/list in one
  election;
- `/{lang}/data/` - public data catalog and download landing page;
- `/{lang}/map/...` - interactive deep links for the existing application.

Only result-bearing, useful pages belong in the sitemap. Empty polygons,
duplicate map-state URLs, arbitrary party comparisons, and combinatorial UI
states should not become indexable pages. A result with disclosed geographic
uncertainty may be indexed only when the same notice is visible in its HTML.

Each content page needs an **Open in map** link that restores the exact
election, geography mode, result, and selected party where relevant. Search
results in the application should link back to the corresponding stable URL.

### Page Content

Programmatic pages must contain useful facts, not generated filler. Depending
on the page type, include:

- election name and date;
- locality or area identity and statistical vintage;
- actual voters, valid votes, turnout where available, winner, and leading
  party shares;
- complete or appropriately scoped result tables;
- national threshold and mandate information on election/party pages;
- geographic-assignment or unsplit-locality notices exactly where applicable;
- links to related elections, adjacent hierarchy levels, party pages, the
  methodology, the downloadable data, and the interactive map;
- visible source and update information.

This prevents mass creation of thin or near-duplicate pages and aligns the SEO
surface with the project's real data value.

### Metadata And Internationalization

Every indexable page must have:

- one unique, descriptive `<title>` and meta description in the page language;
- a visible, matching H1;
- a self-referencing canonical URL;
- reciprocal `hreflang="he"` and `hreflang="en"` links;
- `lang` and `dir` set in the initial HTML;
- Open Graph and social-card metadata;
- a stable preview image, initially one general image plus one per election;
- descriptive link text and semantic tables/headings.

Do not add a meta-keywords tag or repeat keyword variants mechanically.

Suggested title patterns:

- Hebrew election: `תוצאות בחירות {year} לכנסת ה-{number} | מפת הבחירות`;
- Hebrew locality: `תוצאות הבחירות ב{locality} ב-{year} | מפה ונתונים`;
- Hebrew area: `תוצאות הבחירות ב{locality}, אזור {area}, ב-{year}`;
- English locality: `{locality} election results, {year} | Israel Election Map`.

### Structured Data

- Use `WebSite` and `WebApplication` for the project surface.
- Use `BreadcrumbList` on content routes.
- Use `Dataset`, `DataCatalog`, and `DataDownload` on the public-data landing
  pages, including version, licence URL, formats, temporal coverage, spatial
  coverage, provenance links, and direct download URLs.
- Do not invent unsupported election-specific schema types.
- Validate representative pages with Google's Rich Results Test before launch.

### Crawling And Sitemaps

- Put `robots.txt` at the canonical host root and reference the sitemap index.
- Split sitemaps by language and page family or election. Each sitemap must
  remain below 50,000 URLs and 50 MB uncompressed.
- Include only canonical URLs that return `200` and contain useful content.
- Return a real `404` for unknown entity IDs instead of the generic SPA shell.
- Add the domain property to Google Search Console with DNS verification, then
  submit the sitemap index and inspect representative URLs.
- Exclude preview deployments and the production `pages.dev` alias from
  indexing.

### Performance

- Keep MapLibre and map geometry lazy on text-first SEO pages; load the map only
  after the user opens it.
- Disable public production source maps.
- Reserve exact space for ads to prevent layout shifts.
- Avoid loading AdSense on routes where no ad can render.
- Preserve hashed filenames for long-lived JavaScript/CSS caching and avoid
  long browser caching for mutable catalog URLs unless their paths become
  content-addressed.
- Validate mobile and desktop LCP, INP, and CLS. Google currently recommends
  LCP within 2.5 seconds, INP under 200 ms, and CLS under 0.1.

## AdSense Plan

### Preconditions

Do not request final AdSense review until the following are live on the custom
domain:

- original crawlable election content and reliable navigation;
- the privacy notice, repository/data links, and a working contact path;
- canonical HTTPS, real 404 handling, and no broken primary routes;
- a Google-certified consent management platform configured for the EEA, UK,
  and Switzerland;
- the AdSense verification code and, once the publisher ID exists, a root
  `ads.txt` entry.

The existing privacy notice accurately says that advertising is not currently
active. It must be updated before any AdSense tag is enabled to name Google,
describe advertising purposes and storage, explain choices, and link to the
live consent controls.

### Placements And Formats

Start with manual responsive display units. Do not let Auto Ads choose
locations inside the interactive application.

| Surface | Initial placement | Format and behavior |
|---|---|---|
| Election, locality, area, party, and data pages | After the opening summary and before the main detailed section | Responsive banner. Reserve approximately 90 px on wide screens and 100 px on phones before the ad loads. |
| Long content/result pages | After the primary result table or analysis, before related links | Responsive rectangle, typically fitting 300x250 or 336x280. Maximum one second unit at launch. |
| National-results view | Between the national summary metrics and the result table | One responsive banner with fixed reserved space; the table header must remain sticky and visible after scrolling. |
| Desktop interactive map | Optional experiment only when no result panel is open and the viewport is at least 1280x800 | Separate 300x250 rail slot below controls. Remove it immediately when a result opens or available height becomes constrained. |
| Mobile interactive map | None | Preserve the map viewport and touch controls. |
| Result sheets, map canvas, search, menus, zoom controls, party selectors | Never | These are dense interactive click targets and create unacceptable usability and accidental-click risk. |

Additional rules:

- no anchor, vignette, sticky, floating, pop-up, or interstitial formats at
  launch;
- exclude all map routes from Auto Ads if Auto Ads is tested later;
- keep visible separation from navigation and controls;
- never style content to resemble an ad or an ad to resemble a result row;
- rely on Google's ad disclosure, or use only Google's permitted labels;
- never click live ads during testing;
- begin with one unit per page and add a second only after real usability,
  viewability, and Core Web Vitals measurements support it.

### Technical Integration

- Keep publisher and slot IDs in production environment configuration.
- Load the AdSense script once, asynchronously, only on eligible routes and
  only after the required consent state permits the request.
- Use Google's Privacy & Messaging CMP rather than building an uncertified
  custom consent framework.
- Expose a persistent privacy/consent-settings link after the first decision.
- Keep advertising disabled in local development and automated browser tests.
- Add regression tests for route exclusions, one-time script loading, consent
  gating, reserved dimensions, and absence of ads in interactive controls.
- Use AdSense reporting and Search Console first. Do not add Google Analytics
  merely for launch; it would add another privacy and consent surface.

## Exact Delivery Sequence

### Phase 1: Hosting Foundation

1. Receive the real domain and choose apex versus `www` canonical form.
2. Add Wrangler configuration and local preview/deploy scripts.
3. Disable production source maps and add deployment-size validation.
4. Add headers, redirects, canonical-host enforcement, and real 404 handling.
5. Deploy to a temporary `pages.dev` URL and run the complete application QA.
6. Attach the custom domain, verify HTTPS, and redirect aliases.

### Phase 2: SEO Surfaces

1. Add URL-based application state and stable Hebrew/English routes.
2. Generate the compact SEO index from the same validated web compiler.
3. Add crawlable route HTML with meaningful tables and notices.
4. Add metadata, canonical/hreflang links, structured data, social images,
   robots, and split sitemaps.
5. Run link, 404, structured-data, accessibility, and Core Web Vitals checks.
6. Verify the domain in Search Console and submit the sitemap index.

### Phase 3: AdSense

1. Apply with the live custom domain after its content is crawlable.
2. Add the issued publisher verification and `ads.txt` values.
3. Configure Google's certified CMP and update the privacy notice.
4. Implement the first manual content-page and national-page slots.
5. Keep interactive map routes excluded until a separately reviewed desktop
   rail experiment is approved.
6. Review policy status, layout shifts, accidental-click risk, and revenue
   before adding any second placement.

## Inputs Needed From The Owner

No paid storage account is required. Implementation eventually needs only:

- the real domain;
- the chosen canonical host (`example.com` or `www.example.com`);
- access to a Cloudflare account for DNS and Pages deployment;
- a Google account for Search Console and AdSense;
- the AdSense publisher ID and slot IDs after Google issues them.

## Completion Criteria

The three workstreams are complete when:

- the canonical HTTPS domain serves the tested production build and can roll
  back to a prior deployment;
- all approved Hebrew/English content routes return crawlable HTML, correct
  metadata, real status codes, and working map deep links;
- sitemap and representative URL inspection succeed in Search Console;
- Core Web Vitals and ad-slot layout are acceptable on representative phones
  and desktops;
- the privacy notice and certified CMP match the live ad behavior;
- AdSense is approved and only the reviewed placements are active.

## Official References

- Cloudflare Pages Direct Upload:
  https://developers.cloudflare.com/pages/get-started/direct-upload/
- Cloudflare Pages limits:
  https://developers.cloudflare.com/pages/platform/limits/
- Cloudflare Pages Functions pricing:
  https://developers.cloudflare.com/pages/functions/pricing/
- Cloudflare Pages custom domains:
  https://developers.cloudflare.com/pages/configuration/custom-domains/
- Cloudflare Pages Functions asset access:
  https://developers.cloudflare.com/pages/functions/api-reference/
- Google SEO Starter Guide:
  https://developers.google.com/search/docs/fundamentals/seo-starter-guide
- Google JavaScript SEO basics:
  https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics
- Google sitemap guidance:
  https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap
- Google localized-page guidance:
  https://developers.google.com/search/docs/specialty/international/localized-versions
- Google Dataset structured data:
  https://developers.google.com/search/docs/appearance/structured-data/dataset
- Google Core Web Vitals:
  https://developers.google.com/search/docs/appearance/core-web-vitals
- AdSense eligibility:
  https://support.google.com/adsense/answer/9724
- AdSense placement policies:
  https://support.google.com/adsense/answer/1346295
- AdSense placement best practices:
  https://support.google.com/adsense/answer/1282097
- AdSense site connection and `ads.txt`:
  https://support.google.com/adsense/answer/7584263
- Google-certified CMP requirement:
  https://support.google.com/adsense/answer/13554020
- Photon public endpoint terms:
  https://photon.komoot.io/
