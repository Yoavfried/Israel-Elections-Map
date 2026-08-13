# Website Launch, SEO, and Advertising Plan

Last updated: 2026-08-13

This plan covers the three active public-website workstreams:

1. production hosting and domain launch;
2. search-engine discoverability and crawlable result pages;
3. Google AdSense integration and reviewed ad placement.

The hosting foundation, owned-domain launch, and multilingual SEO surfaces are
implemented. Search-engine submission and observation come next; advertising
remains a separate final phase that requires issued AdSense identifiers and a
live consent configuration.

## Current Technical Baseline

The map is a Vite/React application served from Cloudflare Workers Static
Assets. It does not require a database, user accounts, a private API, or
server-side election computation. A small Worker renders crawlable content
routes from the same validated JSON assets used by the browser application.
The current deployment build contains 82 files totaling about 103.56 MiB.

The build reads ignored `data/processed/` inputs, so a normal fresh-clone cloud
build intentionally cannot reproduce the deployed map. Production releases
are compiled and tested locally before upload.

The production plan must preserve the repository boundary: public data remains
downloadable under `public-data/`, while locally generated web payloads remain
disposable deployment artifacts rather than a second committed data release.

## Recommended Production Architecture

The deployed architecture uses **Cloudflare Workers Static Assets with
Wrangler Direct Upload**. It requires no paid storage and preserves the local
build workflow.

1. `npm run build:deploy` compiles the complete application under the
   `/isr-electionmap/` base path and prepares `cloudflare-dist/`.
2. `wrangler deploy` uploads the static files and `worker/index.mjs` to the
   `israel-election-map-origin` Worker.
3. `https://yoavfried.com/isr-electionmap` proxies that origin through the
   existing canonical Vercel domain.
4. `assets.run_worker_first` invokes the Worker only for the ten language
   families, robots, and sitemap routes. Map assets remain static.
5. The Worker reads validated election JSON through the `ASSETS` binding and
   caches only the catalog and most recently used result payload within an
   isolate, bounding memory while preserving locality/sitemap batch reuse.

No D1 database, KV namespace, R2 bucket, paid server, or paid object storage is
required.

### Deployment Shape

The production implementation consists of:

- `wrangler.jsonc`, including the static-asset binding and selective Worker
  route patterns;
- `worker/index.mjs`, which delegates ordinary assets and renders SEO routes;
- `seo/config.mjs`, `seo/translations.mjs`, and `seo/render.mjs`;
- a Worker-generated real 404, robots response, sitemap index, and split data
  sitemaps;
- `npm run deploy`, which builds and uploads the reviewed release.

Wrangler Direct Upload is intentional because private working inputs are not in
the public repository. The release procedure runs the local data compiler and
full test suite before invoking the deployment command; `npm run deploy`
rebuilds the production payload before upload.

### Domain And Network Setup

- The canonical public base is `https://yoavfried.com/isr-electionmap` and
  follows the host's no-trailing-slash convention.
- SEO responses always emit that owned-domain canonical rather than the Worker
  origin URL.
- The Worker development hostname is an origin, not an indexable canonical
  content surface.
- Keep the existing neutral-map fallback. OpenFreeMap remains an external
  basemap dependency.
- The public Photon endpoint permits reasonable use but may throttle extensive
  traffic and provides no availability guarantee. Keep the configurable
  endpoint, client debounce, request bounds, and session cache. At meaningful
  traffic, use a contracted or self-hosted endpoint or temporarily disable
  numbered-address lookup; a proxy alone does not solve upstream capacity.

## SEO Architecture

### Crawlable Routes

The Worker serves useful initial HTML in Hebrew (`he`), English (`en`), French
(`fr`), Spanish (`es`), Russian (`ru`), Simplified Chinese (`zh`), Arabic
(`ar`), German (`de`), Ukrainian (`uk`), and Polish (`pl`). The route families
are identical in every language:

- `/{lang}` - project and map overview;
- `/{lang}/elections/2026` - truthful future-election and official-voter
  information without invented results;
- `/{lang}/elections/{year}` - national historical election result;
- `/{lang}/elections/{year}/localities/{encoded-result-id}` - one election
  and locality;
- `/{lang}/elections/{year}/statistical-areas/{encoded-result-id}` - one
  election and displayed statistical result unit.

Each result page links to the interactive application with validated query
state for the exact election, mode, language, and selected result. Party pages
and localized data-catalog pages are not currently generated and are not
claimed as completed SEO surfaces.

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
- reciprocal hreflang links for all ten languages plus `x-default`, including
  a self-reference on every page;
- `lang` and `dir` set in the initial HTML;
- Open Graph and social-card metadata;
- a stable election-map preview image;
- descriptive link text and semantic tables/headings.

Do not add a meta-keywords tag or repeat keyword variants mechanically.

Implemented title patterns are localized equivalents of:

- Hebrew election: `תוצאות בחירות {year} לכנסת ה-{number} | מפת הבחירות`;
- Hebrew locality: `תוצאות הבחירות ב{locality} ב-{year} | מפה ונתונים`;
- Hebrew area: `תוצאות הבחירות ב{locality}, אזור {area}, ב-{year}`;
- English locality: `{locality} election results, {year} | Israel Election Map`.

The Hebrew overview and FAQ naturally cover local intent such as `מה הצביעו
בשכונה שלי`, `מה הצביעו`, and `איפה מצביעים`. The last query is answered with
an explicit limitation: this historical results map does not assign a polling
station, and the page links to official voter information. Broad news phrases
are not targeted because this is not a news service.

### Structured Data

- Use `WebSite` for the project surface and `WebPage` where appropriate.
- Use `BreadcrumbList` on content routes.
- Use `Dataset` for election and result pages, with the MIT data-license URL,
  temporal coverage, spatial coverage, and creator.
- Do not invent unsupported election-specific schema types.
- Validate representative pages with Google's Rich Results Test before Search
  Console submission.

### Crawling And Sitemaps

- The application publishes `/isr-electionmap/robots.txt`; the canonical
  host's root `/robots.txt` must also add
  `Sitemap: https://yoavfried.com/isr-electionmap/sitemap.xml`.
- The Worker publishes one sitemap index, one core sitemap, and result
  sitemaps split by language, election, and geography mode. Each remains below
  50,000 URLs and 50 MB uncompressed.
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

Complete. The canonical subpath, Wrangler configuration, local build/deploy
commands, Worker origin, static assets, real SEO 404s, and owned-domain proxy
are live.

### Phase 2: SEO Surfaces

1. Complete: URL-based application state and stable routes in all ten
   languages.
2. Complete: Worker rendering from the validated compiled web assets.
3. Complete: crawlable HTML with meaningful tables and geographic notices.
4. Complete: metadata, canonical/hreflang links, structured data, preview
   image, robots response, and split sitemaps.
5. Complete locally: route, status, deep-link, RTL, desktop/mobile visual,
   application, and build checks. Production indexing metrics remain
   observational rather than a release blocker.
6. Pending owner-account operation: add the root robots sitemap declaration,
   verify the domain in Search Console, submit the sitemap index, and inspect
   representative URLs.

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

No paid storage account is required. The hosting/domain inputs are complete.
The remaining external inputs are:

- a Google account for Search Console and AdSense;
- the AdSense publisher ID and slot IDs after Google issues them.

## Completion Criteria

The three workstreams are complete when:

- the canonical HTTPS domain serves the tested production build and can roll
  back to a prior deployment;
- all approved ten-language content routes return crawlable HTML, correct
  metadata, real status codes, and working map deep links;
- sitemap and representative URL inspection succeed in Search Console;
- Core Web Vitals and ad-slot layout are acceptable on representative phones
  and desktops;
- the privacy notice and certified CMP match the live ad behavior;
- AdSense is approved and only the reviewed placements are active.

## Official References

- Cloudflare Workers Static Assets:
  https://developers.cloudflare.com/workers/static-assets/
- Cloudflare selective Worker-first asset routing:
  https://developers.cloudflare.com/workers/static-assets/routing/worker-script/
- Cloudflare Workers limits:
  https://developers.cloudflare.com/workers/platform/limits/
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
