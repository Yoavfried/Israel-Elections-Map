import { useEffect, useMemo, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import type {
  CircleLayerSpecification,
  FillLayerSpecification,
  FilterSpecification,
  LineLayerSpecification,
  Map as MapLibreMap,
  SymbolLayerSpecification,
} from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { basemapStyle } from '../config/basemaps'
import { ensureRtlTextSupport } from '../config/rtlText'
import {
  buildBackgroundPolygonVisibilityFilter,
  buildMarkerVisibilityFilter,
  buildResultPolygonVisibilityFilter,
  mayHaveDisplayMarker,
} from '../domain/mapPresentation'
import { UNMAPPED_GEOGRAPHY_COLOR } from '../domain/color'
import {
  partyComparisonBalance,
  partyComparisonColor,
} from '../domain/partyComparison'
import { partyGradientColor, partyVoteShare } from '../domain/partyMap'
import type { MapPosition } from '../domain/addressSearch'
import type {
  BasemapMode,
  GeographyBounds,
  GeographyMode,
  Language,
  Party,
  ResultRecord,
} from '../domain/schemas'
import { translate } from '../i18n/translations'
import { BasemapSelector } from './BasemapSelector'

const SOURCE_ID = 'election-geographies'
const MARKER_SOURCE_ID = 'election-geography-markers'
const BACKDROP_SOURCE_ID = 'election-geography-backdrop'
const BASEMAP_MASK_SOURCE_ID = 'basemap-outside-mask'
const MAP_CONTEXT_SOURCE_ID = 'map-context-footprint'
const BACKGROUND_FILL_LAYER_ID = 'election-background-fill'
const BACKGROUND_LINE_LAYER_ID = 'election-background-line'
const FILL_LAYER_ID = 'election-fill'
const LINE_LAYER_ID = 'election-line'
const MARKER_LAYER_ID = 'election-markers'
const BACKDROP_FILL_LAYER_ID = 'election-backdrop-fill'
const BASEMAP_MASK_LAYER_ID = 'basemap-outside-mask-fill'
const MAP_CONTEXT_LINE_LAYER_ID = 'map-context-boundary'
const GEOGRAPHY_BORDER_COLOR = '#626a65'
const UNMAPPED_AREA_FILL_OPACITY = 0.58
const VECTOR_STYLE_LOAD_TIMEOUT_MS = 8_000
const VECTOR_WATER_COLOR = '#c2c8ca'
const SUPPRESSED_BASEMAP_LABELS = [
  'Israel',
  'ISRAEL',
  'ישראל',
  'إسرائيل',
  'Palestinian Territories',
  'PALESTINIAN TERRITORIES',
  'Palestinian Territory',
  'State of Palestine',
  'השטחים הפלסטיניים',
  'מדינת פלסטין',
  'الأراضي الفلسطينية',
]
const BASEMAP_LABEL_NAME_FIELDS = [
  'name',
  'name:en',
  'name:he',
  'name:ar',
  'name:latin',
  'name:nonlatin',
]

interface MapCanvasProps {
  language: Language
  geographyMode: GeographyMode
  geometryUrl: string
  markerGeometryUrl: string
  backdropGeometryUrl: string | null
  basemapMaskGeometryUrl: string | null
  mapContextGeometryUrl: string | null
  bounds: [[number, number], [number, number]]
  records: ResultRecord[]
  parties: Party[]
  hiddenGeographyIds: string[]
  selectedId: string | null
  focusRequest: {
    id: string
    bounds: GeographyBounds
    requestId: number
  } | null
  addressMarker: {
    coordinates: MapPosition
    label: string
  } | null
  partyMap: {
    partyId: string
    color: string
    upperBoundShare: number
  } | null
  partyComparison: {
    firstPartyId: string
    firstColor: string
    secondPartyId: string
    secondColor: string
  } | null
  basemapMode: BasemapMode
  onBasemapModeChange: (mode: BasemapMode) => void
  onSelect: (id: string | null) => void
}

type MapContextGeometry =
  | { type: 'Polygon'; coordinates: number[][][] }
  | { type: 'MultiPolygon'; coordinates: number[][][][] }

export default function MapCanvas({
  language,
  geographyMode,
  geometryUrl,
  markerGeometryUrl,
  backdropGeometryUrl,
  basemapMaskGeometryUrl,
  mapContextGeometryUrl,
  bounds,
  records,
  parties,
  hiddenGeographyIds,
  selectedId,
  focusRequest,
  addressMarker,
  partyMap,
  partyComparison,
  basemapMode,
  onBasemapModeChange,
  onSelect,
}: MapCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const onSelectRef = useRef(onSelect)
  const onBasemapModeChangeRef = useRef(onBasemapModeChange)
  const activeBasemapModeRef = useRef(basemapMode)
  const vectorStyleTimerRef = useRef<number | null>(null)
  const attributionControlRef = useRef<maplibregl.AttributionControl | null>(null)
  const addressMarkerRef = useRef<maplibregl.Marker | null>(null)
  const basemapLabelFiltersRef = useRef(new Map<string, FilterSpecification | null>())
  const recordsByIdRef = useRef(new Map<string, ResultRecord>())
  const [mapReady, setMapReady] = useState(false)
  const [styleRevision, setStyleRevision] = useState(0)
  const [mapError, setMapError] = useState<string | null>(null)
  const [mapContextGeometry, setMapContextGeometry] = useState<MapContextGeometry | null>(null)
  const partyById = useMemo(() => new Map(parties.map((party) => [party.id, party])), [parties])
  const recordsById = useMemo(() => new Map(records.map((record) => [record.id, record])), [records])

  onSelectRef.current = onSelect
  onBasemapModeChangeRef.current = onBasemapModeChange
  recordsByIdRef.current = recordsById

  useEffect(() => {
    if (!containerRef.current) {
      return
    }

    let disposed = false
    void ensureRtlTextSupport(maplibregl).catch(() => {
      if (!disposed && activeBasemapModeRef.current === 'vector') {
        onBasemapModeChangeRef.current('neutral')
      }
    })

    try {
      const map = new maplibregl.Map({
        container: containerRef.current,
        style: basemapStyle(activeBasemapModeRef.current),
        center: [35.05, 31.55],
        zoom: 6.4,
        minZoom: 5.4,
        maxZoom: 15,
        attributionControl: false,
        dragRotate: false,
        pitchWithRotate: false,
      })
      mapRef.current = map
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right')
      if (activeBasemapModeRef.current === 'vector') {
        const attributionControl = new maplibregl.AttributionControl({
          compact: true,
        })
        map.addControl(attributionControl, 'bottom-left')
        attributionControlRef.current = attributionControl
        vectorStyleTimerRef.current = window.setTimeout(() => {
          if (activeBasemapModeRef.current === 'vector') {
            onBasemapModeChangeRef.current('neutral')
          }
        }, VECTOR_STYLE_LOAD_TIMEOUT_MS)
      }
      map.on('style.load', () => {
        clearVectorStyleTimer(vectorStyleTimerRef)
        basemapLabelFiltersRef.current.clear()
        setMapError(null)
        setStyleRevision((current) => current + 1)
        setMapReady(true)
      })
      map.on('error', (event) => {
        const sourceId = 'sourceId' in event ? event.sourceId : undefined
        if (event.error && isElectionSource(sourceId)) {
          setMapError(event.error.message)
        }
      })
    } catch (error) {
      setMapError(error instanceof Error ? error.message : String(error))
    }

    return () => {
      disposed = true
      clearVectorStyleTimer(vectorStyleTimerRef)
      addressMarkerRef.current?.remove()
      addressMarkerRef.current = null
      mapRef.current?.remove()
      mapRef.current = null
      attributionControlRef.current = null
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map || activeBasemapModeRef.current === basemapMode) {
      return
    }

    activeBasemapModeRef.current = basemapMode
    setMapReady(false)
    setMapError(null)
    clearVectorStyleTimer(vectorStyleTimerRef)

    if (attributionControlRef.current) {
      map.removeControl(attributionControlRef.current)
      attributionControlRef.current = null
    }
    if (basemapMode === 'vector') {
      void ensureRtlTextSupport(maplibregl).catch(() => {
        if (activeBasemapModeRef.current === 'vector') {
          onBasemapModeChangeRef.current('neutral')
        }
      })
      const attributionControl = new maplibregl.AttributionControl({
        compact: true,
      })
      map.addControl(attributionControl, 'bottom-left')
      attributionControlRef.current = attributionControl
      vectorStyleTimerRef.current = window.setTimeout(() => {
        if (activeBasemapModeRef.current === 'vector') {
          onBasemapModeChangeRef.current('neutral')
        }
      }, VECTOR_STYLE_LOAD_TIMEOUT_MS)
    }

    try {
      map.setStyle(basemapStyle(basemapMode), { diff: false })
    } catch (error) {
      if (basemapMode === 'vector') {
        onBasemapModeChangeRef.current('neutral')
      } else {
        setMapError(error instanceof Error ? error.message : String(error))
      }
    }
  }, [basemapMode])

  useEffect(() => {
    const abortController = new AbortController()
    setMapContextGeometry(null)
    if (!mapContextGeometryUrl) {
      return () => abortController.abort()
    }

    void fetch(mapContextGeometryUrl, { signal: abortController.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Map-context request failed with ${response.status}`)
        }
        return response.json()
      })
      .then((payload: unknown) => {
        if (abortController.signal.aborted) {
          return
        }
        const geometry = readMapContextGeometry(payload)
        if (geometry) {
          setMapContextGeometry(geometry)
        }
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return
        }
      })

    return () => abortController.abort()
  }, [mapContextGeometryUrl])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady || !map.getStyle() || basemapMode !== 'vector') {
      return
    }
    localizeBasemapLabels(
      map,
      language,
      mapContextGeometry,
      basemapLabelFiltersRef.current,
    )
  }, [basemapMode, language, mapContextGeometry, mapReady, styleRevision])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady || !map.getStyle()) {
      return
    }

    if (map.getLayer(MARKER_LAYER_ID)) {
      map.removeLayer(MARKER_LAYER_ID)
    }
    if (map.getLayer(LINE_LAYER_ID)) {
      map.removeLayer(LINE_LAYER_ID)
    }
    if (map.getLayer(FILL_LAYER_ID)) {
      map.removeLayer(FILL_LAYER_ID)
    }
    if (map.getLayer(BACKGROUND_LINE_LAYER_ID)) {
      map.removeLayer(BACKGROUND_LINE_LAYER_ID)
    }
    if (map.getLayer(BACKGROUND_FILL_LAYER_ID)) {
      map.removeLayer(BACKGROUND_FILL_LAYER_ID)
    }
    if (map.getLayer(BACKDROP_FILL_LAYER_ID)) {
      map.removeLayer(BACKDROP_FILL_LAYER_ID)
    }
    if (map.getLayer(BASEMAP_MASK_LAYER_ID)) {
      map.removeLayer(BASEMAP_MASK_LAYER_ID)
    }
    if (map.getLayer(MAP_CONTEXT_LINE_LAYER_ID)) {
      map.removeLayer(MAP_CONTEXT_LINE_LAYER_ID)
    }
    if (map.getSource(SOURCE_ID)) {
      map.removeSource(SOURCE_ID)
    }
    if (map.getSource(MARKER_SOURCE_ID)) {
      map.removeSource(MARKER_SOURCE_ID)
    }
    if (map.getSource(BACKDROP_SOURCE_ID)) {
      map.removeSource(BACKDROP_SOURCE_ID)
    }
    if (map.getSource(BASEMAP_MASK_SOURCE_ID)) {
      map.removeSource(BASEMAP_MASK_SOURCE_ID)
    }
    if (map.getSource(MAP_CONTEXT_SOURCE_ID)) {
      map.removeSource(MAP_CONTEXT_SOURCE_ID)
    }

    const basemapDetailAnchor = findBasemapDetailAnchor(map)
    const basemapLabelAnchor = findBasemapLabelAnchor(map)

    if (backdropGeometryUrl) {
      map.addSource(BACKDROP_SOURCE_ID, {
        type: 'geojson',
        data: backdropGeometryUrl,
      })
      map.addLayer(
        {
          id: BACKDROP_FILL_LAYER_ID,
          source: BACKDROP_SOURCE_ID,
          type: 'fill',
          filter: buildBackgroundPolygonVisibilityFilter([], []),
          paint: {
            'fill-color': UNMAPPED_GEOGRAPHY_COLOR,
            'fill-opacity': basemapMode === 'vector' ? 0.18 : 0.28,
          },
        },
        basemapDetailAnchor,
      )
    }

    const maskBasemap = basemapMode === 'vector' && basemapMaskGeometryUrl
    if (maskBasemap) {
      map.addSource(BASEMAP_MASK_SOURCE_ID, {
        type: 'geojson',
        data: basemapMaskGeometryUrl,
      })
      map.addLayer(
        {
          id: BASEMAP_MASK_LAYER_ID,
          source: BASEMAP_MASK_SOURCE_ID,
          type: 'fill',
          paint: {
            'fill-antialias': false,
            'fill-color': VECTOR_WATER_COLOR,
            'fill-opacity': 1,
          },
        },
        basemapLabelAnchor,
      )
    }

    if (mapContextGeometryUrl) {
      map.addSource(MAP_CONTEXT_SOURCE_ID, {
        type: 'geojson',
        data: mapContextGeometryUrl,
      })
    }

    map.addSource(SOURCE_ID, {
      type: 'geojson',
      data: geometryUrl,
      promoteId: 'id',
    })
    map.addSource(MARKER_SOURCE_ID, {
      type: 'geojson',
      data: markerGeometryUrl,
      promoteId: 'id',
    })

    const resultPolygonVisibilityFilter = buildResultPolygonVisibilityFilter(
      hiddenGeographyIds,
      [...recordsByIdRef.current.values()],
    )
    const backgroundPolygonVisibilityFilter = buildBackgroundPolygonVisibilityFilter(
      hiddenGeographyIds,
      [...recordsByIdRef.current.values()],
    )

    const backgroundFillLayer: FillLayerSpecification = {
      id: BACKGROUND_FILL_LAYER_ID,
      source: SOURCE_ID,
      type: 'fill',
      filter: backgroundPolygonVisibilityFilter,
      paint: {
        'fill-color': UNMAPPED_GEOGRAPHY_COLOR,
        'fill-opacity': [
          'case',
          ['boolean', ['feature-state', 'selected'], false],
          geographyMode === 'statistical-area' ? 0.78 : 0.42,
          geographyMode === 'statistical-area' ? UNMAPPED_AREA_FILL_OPACITY : 0,
        ],
      },
    }
    const backgroundLineLayer: LineLayerSpecification = {
      id: BACKGROUND_LINE_LAYER_ID,
      source: SOURCE_ID,
      type: 'line',
      filter: backgroundPolygonVisibilityFilter,
      paint: {
        'line-color': [
          'case',
          ['boolean', ['feature-state', 'selected'], false],
          '#151815',
          GEOGRAPHY_BORDER_COLOR,
        ],
        'line-width': [
          'interpolate',
          ['linear'],
          ['zoom'],
          5.4,
          ['case', ['boolean', ['feature-state', 'selected'], false], 1, 0.15],
          7,
          ['case', ['boolean', ['feature-state', 'selected'], false], 1.2, 0.25],
          9,
          ['case', ['boolean', ['feature-state', 'selected'], false], 1.5, 0.5],
          11,
          ['case', ['boolean', ['feature-state', 'selected'], false], 2, 0.75],
          13,
          ['case', ['boolean', ['feature-state', 'selected'], false], 2.5, 1],
        ],
        'line-opacity': [
          'case',
          ['boolean', ['feature-state', 'selected'], false],
          1,
          geographyMode === 'statistical-area' ? 1 : 0,
        ],
      },
    }
    const fillLayer: FillLayerSpecification = {
      id: FILL_LAYER_ID,
      source: SOURCE_ID,
      type: 'fill',
      filter: resultPolygonVisibilityFilter,
      paint: {
        'fill-color': ['to-color', ['coalesce', ['feature-state', 'color'], '#69736d']],
        'fill-opacity': [
          'case',
          ['boolean', ['feature-state', 'selected'], false],
          0.9,
          ['case', ['boolean', ['feature-state', 'analysisMode'], false], 0.84, 0.7],
        ],
      },
    }
    const lineLayer: LineLayerSpecification = {
      id: LINE_LAYER_ID,
      source: SOURCE_ID,
      type: 'line',
      filter: resultPolygonVisibilityFilter,
      paint: {
        'line-color': [
          'case',
          ['boolean', ['feature-state', 'selected'], false],
          '#151815',
          GEOGRAPHY_BORDER_COLOR,
        ],
        'line-width': [
          'interpolate',
          ['linear'],
          ['zoom'],
          5.4,
          ['case', ['boolean', ['feature-state', 'selected'], false], 1, 0.15],
          7,
          ['case', ['boolean', ['feature-state', 'selected'], false], 1.2, 0.25],
          9,
          ['case', ['boolean', ['feature-state', 'selected'], false], 1.5, 0.5],
          11,
          ['case', ['boolean', ['feature-state', 'selected'], false], 2, 0.75],
          13,
          ['case', ['boolean', ['feature-state', 'selected'], false], 2.5, 1],
        ],
        'line-opacity': 1,
      },
    }
    const markerLayer: CircleLayerSpecification = {
      id: MARKER_LAYER_ID,
      source: MARKER_SOURCE_ID,
      type: 'circle',
      filter: buildMarkerVisibilityFilter(
        [...recordsByIdRef.current.values()],
        hiddenGeographyIds,
      ),
      paint: {
        'circle-color': [
          'case',
          ['boolean', ['feature-state', 'hasData'], false],
          ['to-color', ['coalesce', ['feature-state', 'color'], '#69736d']],
          '#aeb2ac',
        ],
        'circle-opacity': [
          'case',
          ['boolean', ['feature-state', 'hasData'], false],
          ['case', ['boolean', ['feature-state', 'analysisMode'], false], 0.9, 0.82],
          0.42,
        ],
        'circle-radius': [
          'case',
          ['boolean', ['feature-state', 'selected'], false],
          6.5,
          4.5,
        ],
        'circle-stroke-color': [
          'case',
          ['boolean', ['feature-state', 'selected'], false],
          '#151815',
          '#faf8f1',
        ],
        'circle-stroke-width': [
          'case',
          ['boolean', ['feature-state', 'selected'], false],
          2,
          1,
        ],
      },
    }
    map.addLayer(backgroundFillLayer, basemapDetailAnchor)
    map.addLayer(backgroundLineLayer, basemapLabelAnchor)
    map.addLayer(fillLayer, basemapDetailAnchor)
    map.addLayer(lineLayer, basemapLabelAnchor)
    if (mapContextGeometryUrl) {
      map.addLayer(
        {
          id: MAP_CONTEXT_LINE_LAYER_ID,
          source: MAP_CONTEXT_SOURCE_ID,
          type: 'line',
          paint: {
            'line-color': '#747b77',
            'line-opacity': 0.9,
            'line-width': [
              'interpolate',
              ['linear'],
              ['zoom'],
              5.4,
              0.65,
              8,
              1,
              11,
              1.4,
            ],
          },
        },
        basemapLabelAnchor,
      )
    }
    map.addLayer(markerLayer)
    map.fitBounds(bounds, { padding: 36, duration: 0 })

    const handleClick = (event: maplibregl.MapLayerMouseEvent) => {
      const id = featureId(event)
      if (id && recordsByIdRef.current.has(id)) {
        onSelectRef.current(id)
      }
    }
    const updatePointer = (event: maplibregl.MapLayerMouseEvent) => {
      const id = featureId(event)
      map.getCanvas().style.cursor = id && recordsByIdRef.current.has(id) ? 'pointer' : ''
    }
    const hidePointer = () => {
      map.getCanvas().style.cursor = ''
    }
    map.on('click', FILL_LAYER_ID, handleClick)
    map.on('click', MARKER_LAYER_ID, handleClick)
    map.on('mousemove', FILL_LAYER_ID, updatePointer)
    map.on('mousemove', MARKER_LAYER_ID, updatePointer)
    map.on('mouseleave', FILL_LAYER_ID, hidePointer)
    map.on('mouseleave', MARKER_LAYER_ID, hidePointer)

    return () => {
      map.off('click', FILL_LAYER_ID, handleClick)
      map.off('click', MARKER_LAYER_ID, handleClick)
      map.off('mousemove', FILL_LAYER_ID, updatePointer)
      map.off('mousemove', MARKER_LAYER_ID, updatePointer)
      map.off('mouseleave', FILL_LAYER_ID, hidePointer)
      map.off('mouseleave', MARKER_LAYER_ID, hidePointer)
    }
  }, [
    backdropGeometryUrl,
    basemapMaskGeometryUrl,
    basemapMode,
    bounds,
    geographyMode,
    geometryUrl,
    hiddenGeographyIds,
    mapReady,
    mapContextGeometryUrl,
    markerGeometryUrl,
    styleRevision,
  ])

  useEffect(() => {
    const map = mapRef.current
    if (
      !map ||
      !mapReady ||
      !map.getSource(SOURCE_ID) ||
      !map.getSource(MARKER_SOURCE_ID) ||
      !map.getLayer(FILL_LAYER_ID) ||
      !map.getLayer(LINE_LAYER_ID) ||
      !map.getLayer(BACKGROUND_FILL_LAYER_ID) ||
      !map.getLayer(BACKGROUND_LINE_LAYER_ID) ||
      !map.getLayer(MARKER_LAYER_ID)
    ) {
      return
    }

    const resultPolygonVisibilityFilter = buildResultPolygonVisibilityFilter(
      hiddenGeographyIds,
      records,
    )
    const backgroundPolygonVisibilityFilter = buildBackgroundPolygonVisibilityFilter(
      hiddenGeographyIds,
      records,
    )
    map.setFilter(FILL_LAYER_ID, resultPolygonVisibilityFilter)
    map.setFilter(LINE_LAYER_ID, resultPolygonVisibilityFilter)
    map.setFilter(BACKGROUND_FILL_LAYER_ID, backgroundPolygonVisibilityFilter)
    map.setFilter(BACKGROUND_LINE_LAYER_ID, backgroundPolygonVisibilityFilter)
    map.setFilter(MARKER_LAYER_ID, buildMarkerVisibilityFilter(records, hiddenGeographyIds))

    const applyFeatureStates = () => {
      if (!map.isSourceLoaded(SOURCE_ID) || !map.isSourceLoaded(MARKER_SOURCE_ID)) {
        return
      }
      map.removeFeatureState({ source: SOURCE_ID })
      map.removeFeatureState({ source: MARKER_SOURCE_ID })
      for (const record of records) {
        const party = partyById.get(record.winner.partyId)
        let color = party?.color ?? '#69736d'
        if (partyMap) {
          color = partyGradientColor(
            partyMap.color,
            partyVoteShare(record, partyMap.partyId),
            partyMap.upperBoundShare,
          )
        } else if (partyComparison) {
          color = partyComparisonColor(
            partyComparison.firstColor,
            partyComparison.secondColor,
            partyComparisonBalance(
              record,
              partyComparison.firstPartyId,
              partyComparison.secondPartyId,
            ),
          )
        }
        const state = {
          hasData: true,
          color,
          analysisMode: Boolean(partyMap || partyComparison),
          selected: record.id === selectedId,
        }
        map.setFeatureState(
          { source: SOURCE_ID, id: record.id },
          state,
        )
        if (mayHaveDisplayMarker(record)) {
          map.setFeatureState({ source: MARKER_SOURCE_ID, id: record.id }, state)
        }
      }
      if (selectedId && !recordsById.has(selectedId)) {
        map.setFeatureState(
          { source: SOURCE_ID, id: selectedId },
          { hasData: false, selected: true },
        )
      }
    }
    const handleSourceData = (event: maplibregl.MapSourceDataEvent) => {
      if (
        (event.sourceId === SOURCE_ID || event.sourceId === MARKER_SOURCE_ID) &&
        event.isSourceLoaded
      ) {
        applyFeatureStates()
      }
    }

    map.on('sourcedata', handleSourceData)
    applyFeatureStates()
    return () => {
      map.off('sourcedata', handleSourceData)
    }
  }, [
    geometryUrl,
    hiddenGeographyIds,
    mapReady,
    markerGeometryUrl,
    partyById,
    partyComparison,
    partyMap,
    records,
    selectedId,
    styleRevision,
  ])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady || !focusRequest || !map.getSource(SOURCE_ID)) {
      return
    }

    const containerWidth = containerRef.current?.clientWidth ?? 0
    const wideLayout = containerWidth >= 800
    map.resize()
    map.fitBounds(focusRequest.bounds, {
      padding: wideLayout
        ? { top: 68, right: 56, bottom: 68, left: Math.min(540, containerWidth * 0.42) }
        : { top: 250, right: 28, bottom: 52, left: 28 },
      duration: 550,
      maxZoom: geographyMode === 'statistical-area' ? 13 : 11,
    })
  }, [focusRequest, geographyMode, geometryUrl, mapReady, styleRevision])

  useEffect(() => {
    const map = mapRef.current
    addressMarkerRef.current?.remove()
    addressMarkerRef.current = null
    if (!map || !mapReady || !addressMarker) {
      return
    }

    const marker = new maplibregl.Marker({ color: '#1c6457' })
      .setLngLat(addressMarker.coordinates)
      .addTo(map)
    const markerElement = marker.getElement()
    markerElement.classList.add('address-map-marker')
    markerElement.title = addressMarker.label
    markerElement.setAttribute('aria-label', addressMarker.label)
    addressMarkerRef.current = marker

    return () => {
      if (addressMarkerRef.current === marker) {
        addressMarkerRef.current = null
      }
      marker.remove()
    }
  }, [addressMarker, mapReady, styleRevision])

  if (mapError) {
    return (
      <div className="map-error" role="alert">
        <strong>{translate(language, 'dataError')}</strong>
        <span>{mapError}</span>
      </div>
    )
  }

  return (
    <div
      className="map-canvas"
      role="region"
      aria-label={translate(language, 'mapLabel')}
    >
      <div ref={containerRef} className="map-canvas__viewport" />
      <BasemapSelector
        language={language}
        mode={basemapMode}
        onChange={onBasemapModeChange}
      />
    </div>
  )
}

const BASEMAP_NAME_LAYER_PATTERN = /(airport|label|name|poi)/

const SUPPRESSED_BASEMAP_LABEL_FILTER = [
  'all',
  ...BASEMAP_LABEL_NAME_FIELDS.map((field) => [
    '!',
    [
      'in',
      ['coalesce', ['get', field], ''],
      ['literal', SUPPRESSED_BASEMAP_LABELS],
    ],
  ]),
] as FilterSpecification

function localizeBasemapLabels(
  map: MapLibreMap,
  language: Language,
  mapContextGeometry: MapContextGeometry | null,
  originalFilters: Map<string, FilterSpecification | null>,
): void {
  const textField =
    language === 'he'
      ? [
          'coalesce',
          ['get', 'name:he'],
          ['get', 'name:nonlatin'],
          ['get', 'name'],
          ['get', 'name:latin'],
        ]
      : [
          'coalesce',
          ['get', 'name:en'],
          ['get', 'name:latin'],
          ['get', 'name'],
          ['get', 'name:nonlatin'],
        ]

  for (const layer of map.getStyle()?.layers ?? []) {
    if (layer.type !== 'symbol' || !BASEMAP_NAME_LAYER_PATTERN.test(layer.id)) {
      continue
    }
    const symbolLayer = layer as SymbolLayerSpecification
    if (symbolLayer.source !== 'openmaptiles' || !symbolLayer.layout?.['text-field']) {
      continue
    }
    map.setLayoutProperty(layer.id, 'text-field', textField)
    if (!originalFilters.has(layer.id)) {
      originalFilters.set(layer.id, map.getFilter(layer.id) ?? null)
    }
    const filters = [
      originalFilters.get(layer.id),
      mapContextGeometry
        ? (['within', mapContextGeometry] as FilterSpecification)
        : null,
      SUPPRESSED_BASEMAP_LABEL_FILTER,
    ].filter((filter): filter is FilterSpecification => Boolean(filter))
    map.setFilter(layer.id, ['all', ...filters] as FilterSpecification)
  }
}

function readMapContextGeometry(payload: unknown): MapContextGeometry | null {
  if (!payload || typeof payload !== 'object' || !('features' in payload)) {
    return null
  }
  const features = (payload as { features?: unknown }).features
  if (!Array.isArray(features) || !features[0] || typeof features[0] !== 'object') {
    return null
  }
  const geometry = (features[0] as { geometry?: unknown }).geometry
  if (!geometry || typeof geometry !== 'object' || !('type' in geometry)) {
    return null
  }
  const type = (geometry as { type?: unknown }).type
  if (type !== 'Polygon' && type !== 'MultiPolygon') {
    return null
  }
  return geometry as MapContextGeometry
}

function findBasemapDetailAnchor(map: MapLibreMap): string | undefined {
  const layers = map.getStyle()?.layers ?? []
  const firstDetailLayer = layers.find((layer) => {
    const sourceLayer = 'source-layer' in layer ? layer['source-layer'] : undefined
    return (
      sourceLayer === 'building' ||
      sourceLayer === 'transportation' ||
      sourceLayer === 'boundary' ||
      layer.type === 'symbol'
    )
  })
  return firstDetailLayer?.id
}

function findBasemapLabelAnchor(map: MapLibreMap): string | undefined {
  return map.getStyle()?.layers?.find((layer) => layer.type === 'symbol')?.id
}

function isElectionSource(sourceId: unknown): boolean {
  return (
    sourceId === SOURCE_ID ||
    sourceId === MARKER_SOURCE_ID ||
    sourceId === BACKDROP_SOURCE_ID ||
    sourceId === BASEMAP_MASK_SOURCE_ID ||
    sourceId === MAP_CONTEXT_SOURCE_ID
  )
}

function clearVectorStyleTimer(timerRef: { current: number | null }): void {
  if (timerRef.current !== null) {
    window.clearTimeout(timerRef.current)
    timerRef.current = null
  }
}

function featureId(event: maplibregl.MapLayerMouseEvent): string | null {
  const id = event.features?.[0]?.id
  return typeof id === 'string' ? id : null
}
