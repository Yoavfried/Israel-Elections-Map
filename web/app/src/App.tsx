import { CodeXml, House, Languages, Shield } from 'lucide-react'
import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { AccessibilityWidget } from './components/AccessibilityWidget'
import { ControlPanel } from './components/ControlPanel'
import { CoalitionPanel } from './components/CoalitionPanel'
import { DetailsPanel } from './components/DetailsPanel'
import { EnvelopeSummary } from './components/EnvelopeSummary'
import { GeographySearch } from './components/GeographySearch'
import { LoadingState } from './components/LoadingState'
import { MobileMenu } from './components/MobileMenu'
import { NationalResultsScreen } from './components/NationalResultsScreen'
import { PartyComparisonPanel } from './components/PartyComparisonPanel'
import { PartyMapPanel } from './components/PartyMapPanel'
import { PrimaryTabs } from './components/PrimaryTabs'
import type { AppView } from './components/PrimaryTabs'
import {
  loadCatalog,
  loadElectionResults,
  loadGeographySearchIndex,
  loadNationalResults,
  resolveDataUrl,
} from './data/client'
import type { AddressSearchMatch } from './domain/addressSearch'
import { coalitionDefinition } from './config/coalitions'
import { coalitionVoteShareUpperBound } from './domain/coalitionMap'
import type {
  AppCatalog,
  ElectionResults,
  GeographyMode,
  GeographySearchIndex,
  GeographySearchItem,
  Language,
  NationalResults,
} from './domain/schemas'
import {
  partyVoteCountUpperBound,
  partyVoteShareUpperBound,
  rankPartiesForMap,
} from './domain/partyMap'
import type { PartyMapDisplayMode } from './domain/partyMap'
import { translate } from './i18n/translations'
import { loadPreferences, savePreferences } from './state/preferences'
import {
  applyMapLinkPreferences,
  buildMapLinkSearch,
  parseMapLinkSearch,
} from './state/mapLink'

const MapCanvas = lazy(() => import('./components/MapCanvas'))

type Loadable<T> =
  | { status: 'loading' }
  | { status: 'ready'; data: T }
  | { status: 'error'; message: string }

const storage = safeStorage()

export default function App() {
  const [initialMapLink] = useState(() => parseMapLinkSearch(window.location.search))
  const [preferences, setPreferences] = useState(() =>
    applyMapLinkPreferences(loadPreferences(storage, navigator.language), initialMapLink),
  )
  const [catalogState, setCatalogState] = useState<Loadable<AppCatalog>>({ status: 'loading' })
  const [resultsState, setResultsState] = useState<Loadable<ElectionResults>>({ status: 'loading' })
  const [nationalResultsState, setNationalResultsState] = useState<Loadable<NationalResults>>({
    status: 'loading',
  })
  const [searchState, setSearchState] = useState<Loadable<GeographySearchIndex>>({
    status: 'loading',
  })
  const [activeView, setActiveView] = useState<AppView>(initialMapLink.view)
  const [pendingDeepLinkAreaId, setPendingDeepLinkAreaId] = useState(
    initialMapLink.areaId ?? null,
  )
  const [selectedPartyId, setSelectedPartyId] = useState<string | null>(
    initialMapLink.partyId ?? null,
  )
  const [partyMapDisplayMode, setPartyMapDisplayMode] =
    useState<PartyMapDisplayMode>(initialMapLink.partyMapDisplayMode ?? 'areas')
  const [comparisonPartyIds, setComparisonPartyIds] = useState<
    [string | null, string | null]
  >(initialMapLink.comparisonPartyIds ?? [null, null])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [selectedSearchItem, setSelectedSearchItem] =
    useState<GeographySearchItem | null>(null)
  const [selectedAddress, setSelectedAddress] =
    useState<AddressSearchMatch | null>(null)
  const [focusRequest, setFocusRequest] = useState<{
    id: string
    bounds: GeographySearchItem['bounds']
    requestId: number
  } | null>(null)
  const { language, electionId, geographyMode, basemapMode } = preferences
  const isGeographicView =
    activeView === 'map' ||
    activeView === 'party-map' ||
    activeView === 'party-comparison' ||
    activeView === 'coalition'

  useEffect(() => {
    let active = true
    loadCatalog()
      .then((catalog) => {
        if (!active) {
          return
        }
        setCatalogState({ status: 'ready', data: catalog })
        setPreferences((currentPreferences) => {
          if (catalog.elections.some((election) => election.id === currentPreferences.electionId)) {
            return currentPreferences
          }
          const nextPreferences = {
            ...currentPreferences,
            electionId: catalog.elections[0].id,
          }
          savePreferences(storage, nextPreferences)
          return nextPreferences
        })
      })
      .catch((error: unknown) => {
        if (active) {
          setCatalogState({ status: 'error', message: errorMessage(error) })
        }
      })
    return () => {
      active = false
    }
  }, [])

  const catalog = catalogState.status === 'ready' ? catalogState.data : null
  const selectedElection = catalog?.elections.find((election) => election.id === electionId)
  const selectedMode = catalog?.geographyModes.find((mode) => mode.id === geographyMode)
  const selectedGeography = selectedElection?.geographiesByMode[geographyMode]

  useEffect(() => {
    if (!selectedElection) {
      return
    }
    let active = true
    setResultsState({ status: 'loading' })
    loadElectionResults(
      selectedElection.id,
      geographyMode,
      selectedElection.resultUrls[geographyMode],
    )
      .then((results) => {
        if (active) {
          setResultsState({ status: 'ready', data: results })
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setResultsState({ status: 'error', message: errorMessage(error) })
        }
      })
    return () => {
      active = false
    }
  }, [geographyMode, selectedElection])

  useEffect(() => {
    if (
      !selectedElection ||
      (activeView !== 'national' && activeView !== 'coalition')
    ) {
      return
    }
    let active = true
    setNationalResultsState({ status: 'loading' })
    loadNationalResults(selectedElection.id, selectedElection.resultUrls.national)
      .then((nationalResults) => {
        if (active) {
          setNationalResultsState({ status: 'ready', data: nationalResults })
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setNationalResultsState({ status: 'error', message: errorMessage(error) })
        }
      })
    return () => {
      active = false
    }
  }, [activeView, selectedElection])

  useEffect(() => {
    if (!selectedElection) {
      return
    }
    let active = true
    setSearchState({ status: 'loading' })
    loadGeographySearchIndex(selectedElection.id, selectedElection.resultUrls.search)
      .then((searchIndex) => {
        if (active) {
          setSearchState({ status: 'ready', data: searchIndex })
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setSearchState({ status: 'error', message: errorMessage(error) })
        }
      })
    return () => {
      active = false
    }
  }, [selectedElection])

  useEffect(() => {
    document.documentElement.lang = language
    document.documentElement.dir = language === 'he' ? 'rtl' : 'ltr'
    document.title = translate(language, 'appTitle')
  }, [language])

  const results =
    resultsState.status === 'ready' &&
    resultsState.data.electionId === electionId &&
    resultsState.data.geographyMode === geographyMode
      ? resultsState.data
      : null
  const resultsById = useMemo(
    () =>
      new Map(
        [...(results?.records ?? []), ...(results?.envelope ? [results.envelope] : [])].map(
          (record) => [record.id, record],
        ),
      ),
    [results],
  )
  const selectedRecord = selectedId ? resultsById.get(selectedId) ?? null : null
  const searchIndex =
    searchState.status === 'ready' && searchState.data.electionId === electionId
      ? searchState.data
      : null

  useEffect(() => {
    if (!pendingDeepLinkAreaId || !searchIndex || !results) {
      return
    }
    const item = searchIndex.items.find(
      (candidate) =>
        candidate.id === pendingDeepLinkAreaId && candidate.geographyMode === geographyMode,
    )
    setPendingDeepLinkAreaId(null)
    if (!item) {
      return
    }
    setSelectedId(item.id)
    setSelectedSearchItem(item)
    setSelectedAddress(null)
    setFocusRequest((current) => ({
      id: item.id,
      bounds: item.bounds,
      requestId: (current?.requestId ?? 0) + 1,
    }))
  }, [geographyMode, pendingDeepLinkAreaId, results, searchIndex])
  const selectableMapGeographyIds = useMemo(
    () =>
      (searchIndex?.items ?? [])
        .filter((item) => item.geographyMode === geographyMode)
        .map((item) => item.id),
    [geographyMode, searchIndex],
  )
  const partyMapPoints = useMemo(() => {
    const resultIds = new Set(results?.records.map((record) => record.id) ?? [])
    return (searchIndex?.items ?? [])
      .filter(
        (item) =>
          item.geographyMode === geographyMode && resultIds.has(item.id),
      )
      .map((item) => ({
        id: item.id,
        coordinates: [
          (item.bounds[0][0] + item.bounds[1][0]) / 2,
          (item.bounds[0][1] + item.bounds[1][1]) / 2,
        ] as [number, number],
      }))
  }, [geographyMode, results, searchIndex])
  const nationalResults =
    nationalResultsState.status === 'ready' &&
    nationalResultsState.data.electionId === electionId
      ? nationalResultsState.data
      : null
  const partyMapParties = useMemo(
    () =>
      results
        ? rankPartiesForMap(results.parties, results.records, results.envelope, language)
        : [],
    [language, results],
  )
  const selectedCoalition = coalitionDefinition(electionId)
  const coalitionParties = useMemo(() => {
    const memberPartyIds = new Set(selectedCoalition?.memberPartyIds ?? [])
    const nationalVotes = new Map(
      (nationalResults?.parties ?? []).map((party) => [party.id, party.votes]),
    )
    return partyMapParties
      .filter((party) => memberPartyIds.has(party.id))
      .toSorted(
        (left, right) =>
          (nationalVotes.get(right.id) ?? 0) - (nationalVotes.get(left.id) ?? 0),
      )
  }, [nationalResults, partyMapParties, selectedCoalition])
  const coalitionPartyIds = useMemo(
    () => coalitionParties.map((party) => party.id),
    [coalitionParties],
  )
  const coalitionAnchorParty = coalitionParties[0] ?? null
  const effectivePartyId = partyMapParties.some((party) => party.id === selectedPartyId)
    ? selectedPartyId
    : partyMapParties[0]?.id ?? null
  const selectedParty =
    results?.parties.find((party) => party.id === effectivePartyId) ?? null
  const effectiveComparisonFirstId = partyMapParties.some(
    (party) => party.id === comparisonPartyIds[0],
  )
    ? comparisonPartyIds[0]
    : partyMapParties[0]?.id ?? null
  const effectiveComparisonSecondId = partyMapParties.some(
    (party) =>
      party.id === comparisonPartyIds[1] && party.id !== effectiveComparisonFirstId,
  )
    ? comparisonPartyIds[1]
    : partyMapParties.find((party) => party.id !== effectiveComparisonFirstId)?.id ?? null
  const comparisonFirstParty =
    partyMapParties.find((party) => party.id === effectiveComparisonFirstId) ?? null
  const comparisonSecondParty =
    partyMapParties.find((party) => party.id === effectiveComparisonSecondId) ?? null
  const partyMapUpperBoundShare =
    results && effectivePartyId
      ? partyVoteShareUpperBound(results.records, effectivePartyId)
      : 0
  const partyMapUpperBoundVotes = results
    ? partyVoteCountUpperBound(results.records)
    : 0
  const coalitionUpperBoundShare =
    results && selectedCoalition
      ? coalitionVoteShareUpperBound(results.records, selectedCoalition.memberPartyIds)
      : 0
  const partyMapPresentation = useMemo(
    () =>
      activeView === 'party-map' && selectedParty
        ? {
            partyId: selectedParty.id,
            color: selectedParty.color,
            upperBoundShare: partyMapUpperBoundShare,
            upperBoundVotes: partyMapUpperBoundVotes,
            displayMode: partyMapDisplayMode,
            points: partyMapPoints,
          }
        : null,
    [
      activeView,
      partyMapDisplayMode,
      partyMapPoints,
      partyMapUpperBoundShare,
      partyMapUpperBoundVotes,
      selectedParty,
    ],
  )
  const partyComparisonPresentation = useMemo(
    () =>
      activeView === 'party-comparison' && comparisonFirstParty && comparisonSecondParty
        ? {
            firstPartyId: comparisonFirstParty.id,
            firstColor: comparisonFirstParty.color,
            secondPartyId: comparisonSecondParty.id,
            secondColor: comparisonSecondParty.color,
          }
        : null,
    [activeView, comparisonFirstParty, comparisonSecondParty],
  )
  const coalitionPresentation = useMemo(
    () =>
      activeView === 'coalition'
        ? {
            partyIds: coalitionPartyIds,
            color: coalitionAnchorParty?.color ?? '#D0D2CC',
            upperBoundShare: coalitionUpperBoundShare || 1,
          }
        : null,
    [
      activeView,
      coalitionAnchorParty,
      coalitionPartyIds,
      coalitionUpperBoundShare,
    ],
  )

  const highlightedPartyIds =
    activeView === 'party-comparison' &&
    effectiveComparisonFirstId &&
    effectiveComparisonSecondId
      ? [effectiveComparisonFirstId, effectiveComparisonSecondId]
      : activeView === 'coalition'
        ? coalitionPartyIds
        : []
  const highlightedPartiesLabel =
    activeView === 'coalition'
      ? translate(language, 'coalitionDetails')
      : translate(language, 'partyComparisonDetails')
  const highlightedPartyTotalLabel =
    activeView === 'coalition' ? translate(language, 'coalitionTotal') : undefined
  const highlightedPartyNotes = useMemo(
    () =>
      activeView === 'coalition'
        ? Object.fromEntries(
            Object.entries(selectedCoalition?.partialMembership ?? {}).map(
              ([partyId, note]) => [partyId, note[language]],
            ),
          )
        : {},
    [activeView, language, selectedCoalition],
  )

  useEffect(() => {
    const search = buildMapLinkSearch({
      electionId,
      geographyMode,
      language,
      view: activeView,
      areaId: pendingDeepLinkAreaId ?? selectedSearchItem?.id,
      partyId: results ? effectivePartyId : selectedPartyId,
      comparisonPartyIds: results
        ? [effectiveComparisonFirstId, effectiveComparisonSecondId]
        : comparisonPartyIds,
      partyMapDisplayMode,
    })
    if (window.location.search !== search) {
      window.history.replaceState(
        window.history.state,
        '',
        `${window.location.pathname}${search}${window.location.hash}`,
      )
    }
  }, [
    activeView,
    comparisonPartyIds,
    effectiveComparisonFirstId,
    effectiveComparisonSecondId,
    effectivePartyId,
    electionId,
    geographyMode,
    language,
    partyMapDisplayMode,
    pendingDeepLinkAreaId,
    results,
    selectedPartyId,
    selectedSearchItem?.id,
  ])

  const updatePreferences = (nextPreferences: typeof preferences) => {
    setPreferences(nextPreferences)
    savePreferences(storage, nextPreferences)
  }
  const handleElectionChange = (nextElectionId: string) => {
    setSelectedId(null)
    setSelectedSearchItem(null)
    setSelectedAddress(null)
    setFocusRequest(null)
    setSelectedPartyId(null)
    setComparisonPartyIds([null, null])
    updatePreferences({ ...preferences, electionId: nextElectionId })
  }
  const handleGeographyChange = (nextMode: GeographyMode) => {
    setSelectedId(null)
    setSelectedSearchItem(null)
    setSelectedAddress(null)
    setFocusRequest(null)
    updatePreferences({ ...preferences, geographyMode: nextMode })
  }
  const handleBasemapChange = (nextMode: typeof basemapMode) => {
    updatePreferences({ ...preferences, basemapMode: nextMode })
  }
  const handleComparisonFirstChange = (partyId: string) => {
    setComparisonPartyIds([
      partyId,
      effectiveComparisonSecondId && effectiveComparisonSecondId !== partyId
        ? effectiveComparisonSecondId
        : partyMapParties.find((party) => party.id !== partyId)?.id ?? null,
    ])
  }
  const handleComparisonSecondChange = (partyId: string) => {
    setComparisonPartyIds([
      effectiveComparisonFirstId && effectiveComparisonFirstId !== partyId
        ? effectiveComparisonFirstId
        : partyMapParties.find((party) => party.id !== partyId)?.id ?? null,
      partyId,
    ])
  }
  const toggleLanguage = () => {
    const nextLanguage: Language = language === 'en' ? 'he' : 'en'
    updatePreferences({ ...preferences, language: nextLanguage })
  }
  const handleViewChange = (nextView: AppView) => {
    if (nextView !== 'national' && activeView !== 'national') {
      setSelectedId(null)
      setSelectedSearchItem(null)
      setSelectedAddress(null)
      setFocusRequest(null)
    }
    setActiveView(nextView)
  }
  const clearMapSelection = () => {
    setSelectedId(null)
    setSelectedSearchItem(null)
    setSelectedAddress(null)
    setFocusRequest(null)
  }
  const handleMapSelect = (id: string | null) => {
    setSelectedId(id)
    setSelectedSearchItem(
      id
        ? searchIndex?.items.find(
            (item) => item.id === id && item.geographyMode === geographyMode,
          ) ?? null
        : null,
    )
    setSelectedAddress(null)
    setFocusRequest(null)
  }
  const handleSearchSelect = (item: GeographySearchItem) => {
    setSelectedId(item.id)
    setSelectedSearchItem(item)
    setSelectedAddress(null)
    setFocusRequest((current) => ({
      id: item.id,
      bounds: item.bounds,
      requestId: (current?.requestId ?? 0) + 1,
    }))
    if (item.geographyMode !== geographyMode) {
      updatePreferences({ ...preferences, geographyMode: item.geographyMode })
    }
  }
  const handleAddressSearchSelect = (match: AddressSearchMatch) => {
    setSelectedId(match.area.id)
    setSelectedSearchItem(match.area)
    setSelectedAddress(match)
    setFocusRequest((current) => ({
      id: match.id,
      bounds: match.area.bounds,
      requestId: (current?.requestId ?? 0) + 1,
    }))
    if (geographyMode !== 'statistical-area') {
      updatePreferences({ ...preferences, geographyMode: 'statistical-area' })
    }
  }

  if (catalogState.status === 'loading') {
    return <LoadingState language={language} />
  }
  if (
    catalogState.status === 'error' ||
    !catalog ||
    !selectedElection ||
    !selectedMode ||
    !selectedGeography
  ) {
    return (
      <main className="fatal-state" role="alert">
        <h1>{translate(language, 'dataError')}</h1>
        <p>{catalogState.status === 'error' ? catalogState.message : 'Invalid catalog selection.'}</p>
      </main>
    )
  }

  return (
    <main className="app-shell" data-language={language} data-view={activeView}>
      <header className="app-header">
        <AccessibilityWidget language={language} />
        <PrimaryTabs
          activeView={activeView}
          language={language}
          onChange={handleViewChange}
        />
        <div className="header-actions">
          <a
            className="header-icon-link"
            href="https://yoavfried.com/"
            aria-label={translate(language, 'portfolioAction')}
            title={translate(language, 'portfolioAction')}
          >
            <House size={19} strokeWidth={2} aria-hidden="true" />
          </a>
          <a
            className="header-icon-link"
            href="https://github.com/Yoavfried/israel-election-map"
            target="_blank"
            rel="noreferrer"
            aria-label={translate(language, 'repositoryAction')}
            title={translate(language, 'repositoryAction')}
          >
            <CodeXml size={19} strokeWidth={2} aria-hidden="true" />
          </a>
          <a
            className="header-icon-link"
            href={`${import.meta.env.BASE_URL}privacy.html?lang=${language}`}
            aria-label={translate(language, 'privacyAction')}
            title={translate(language, 'privacyAction')}
          >
            <Shield size={19} strokeWidth={2} aria-hidden="true" />
          </a>
          <button className="language-toggle" type="button" onClick={toggleLanguage}>
            <Languages size={18} strokeWidth={2} aria-hidden="true" />
            <span>{translate(language, 'languageAction')}</span>
          </button>
          <MobileMenu
            language={language}
            activeView={activeView}
            elections={catalog.elections}
            geographyModes={catalog.geographyModes}
            electionId={electionId}
            geographyMode={geographyMode}
            basemapMode={basemapMode}
            partyMapDisplayMode={partyMapDisplayMode}
            parties={partyMapParties}
            selectedPartyId={effectivePartyId}
            firstPartyId={effectiveComparisonFirstId}
            secondPartyId={effectiveComparisonSecondId}
            onViewChange={handleViewChange}
            onElectionChange={handleElectionChange}
            onGeographyModeChange={handleGeographyChange}
            onBasemapModeChange={handleBasemapChange}
            onPartyMapDisplayModeChange={setPartyMapDisplayMode}
            onPartyChange={setSelectedPartyId}
            onFirstPartyChange={handleComparisonFirstChange}
            onSecondPartyChange={handleComparisonSecondChange}
          />
        </div>
      </header>

      <div className="app-content">
        <div
          className={`map-stage${isGeographicView ? '' : ' map-stage--inactive'}`}
          aria-hidden={!isGeographicView}
          inert={!isGeographicView}
        >
          {resultsState.status === 'ready' && results ? (
            <Suspense fallback={<LoadingState language={language} kind="map" />}>
              <MapCanvas
                language={language}
                geographyMode={geographyMode}
                geometryUrl={resolveDataUrl(selectedGeography.geometryUrl)}
                markerGeometryUrl={resolveDataUrl(selectedGeography.markerGeometryUrl)}
                backdropGeometryUrl={
                  selectedGeography.backdropGeometryUrl
                    ? resolveDataUrl(selectedGeography.backdropGeometryUrl)
                    : null
                }
                basemapMaskGeometryUrl={
                  selectedGeography.basemapMaskGeometryUrl
                    ? resolveDataUrl(selectedGeography.basemapMaskGeometryUrl)
                    : null
                }
                mapContextGeometryUrl={
                  selectedGeography.mapContextGeometryUrl
                    ? resolveDataUrl(selectedGeography.mapContextGeometryUrl)
                    : null
                }
                bounds={catalog.bounds}
                records={results.records}
                parties={results.parties}
                hiddenGeographyIds={results.hiddenGeographyIds}
                selectableGeographyIds={selectableMapGeographyIds}
                selectedId={selectedId}
                focusRequest={focusRequest}
                addressMarker={
                  selectedAddress
                    ? {
                        coordinates: selectedAddress.coordinates,
                        label: selectedAddress.label,
                      }
                    : null
                }
                partyMap={partyMapPresentation}
                partyComparison={partyComparisonPresentation}
                coalition={coalitionPresentation}
                basemapMode={basemapMode}
                onBasemapModeChange={handleBasemapChange}
                onPartyMapDisplayModeChange={setPartyMapDisplayMode}
                onSelect={handleMapSelect}
              />
            </Suspense>
          ) : resultsState.status === 'error' ? (
            <div className="map-error" role="alert">
              <strong>{translate(language, 'dataError')}</strong>
              <span>{resultsState.message}</span>
            </div>
          ) : (
            <LoadingState language={language} />
          )}

          <div className="left-rail">
            <ControlPanel
              language={language}
              elections={catalog.elections}
              geographyModes={catalog.geographyModes}
              electionId={electionId}
              geographyMode={geographyMode}
              onElectionChange={handleElectionChange}
              onGeographyModeChange={handleGeographyChange}
            />
            {activeView === 'party-map' ? (
              <PartyMapPanel
                language={language}
                parties={partyMapParties}
                selectedPartyId={effectivePartyId}
                upperBoundShare={partyMapUpperBoundShare}
                upperBoundVotes={partyMapUpperBoundVotes}
                displayMode={partyMapDisplayMode}
                onPartyChange={setSelectedPartyId}
              />
            ) : null}
            {activeView === 'party-comparison' ? (
              <PartyComparisonPanel
                language={language}
                parties={partyMapParties}
                firstPartyId={effectiveComparisonFirstId}
                secondPartyId={effectiveComparisonSecondId}
                onFirstPartyChange={handleComparisonFirstChange}
                onSecondPartyChange={handleComparisonSecondChange}
              />
            ) : null}
            {activeView === 'coalition' && selectedCoalition ? (
              <CoalitionPanel
                language={language}
                anchorParty={coalitionAnchorParty}
                upperBoundShare={coalitionUpperBoundShare}
              />
            ) : null}
            {activeView === 'coalition' && !selectedCoalition ? (
              <section className="coalition-panel" role="status">
                {language === 'he'
                  ? 'טרם הוקמה קואליציה לכנסת זו.'
                  : 'A coalition has not yet been formed for this Knesset.'}
              </section>
            ) : null}
            <GeographySearch
              language={language}
              electionId={electionId}
              geographyMode={geographyMode}
              items={searchIndex?.items ?? []}
              bounds={catalog.bounds}
              statisticalGeometryUrl={resolveDataUrl(
                selectedElection.geographiesByMode['statistical-area'].geometryUrl,
              )}
              loading={searchState.status === 'loading'}
              error={searchState.status === 'error' ? searchState.message : null}
              selectedItem={selectedSearchItem}
              selectedAddress={selectedAddress}
              onSelect={handleSearchSelect}
              onAddressSelect={handleAddressSearchSelect}
              onClearSelection={clearMapSelection}
            />
            <EnvelopeSummary
              language={language}
              record={results?.envelope ?? null}
              parties={results?.parties ?? []}
              selected={selectedId === results?.envelope?.id}
              onSelect={() => handleMapSelect(results?.envelope?.id ?? null)}
            />
            <DetailsPanel
              language={language}
              record={selectedRecord}
              emptySelection={
                selectedId === selectedSearchItem?.id && !selectedRecord
                  ? selectedSearchItem
                  : null
              }
              parties={results?.parties ?? []}
              highlightedPartyIds={highlightedPartyIds}
              highlightedPartiesLabel={highlightedPartiesLabel}
              highlightedPartyTotalLabel={highlightedPartyTotalLabel}
              highlightedPartyNotes={highlightedPartyNotes}
              onClose={selectedId ? clearMapSelection : undefined}
            />
          </div>
        </div>
        {activeView === 'national' ? (
          <NationalResultsScreen
            language={language}
            elections={catalog.elections}
            electionId={electionId}
            results={nationalResults}
            loading={nationalResultsState.status === 'loading'}
            error={
              nationalResultsState.status === 'error' ? nationalResultsState.message : null
            }
            onElectionChange={handleElectionChange}
          />
        ) : null}
      </div>
    </main>
  )
}

function safeStorage(): Storage | undefined {
  try {
    return window.localStorage
  } catch {
    return undefined
  }
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
