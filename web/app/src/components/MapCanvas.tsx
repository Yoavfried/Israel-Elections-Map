import { useEffect, useMemo, useRef, useState } from 'react'
import type { FeatureCollection, Point } from 'geojson'
import maplibregl from 'maplibre-gl'
import type {
  CircleLayerSpecification,
  FillLayerSpecification,
  FilterSpecification,
  GeoJSONSource,
  LineLayerSpecification,
  Map as MapLibreMap,
  SymbolLayerSpecification,
} from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { basemapStyle, MAP_CONTEXT_ATTRIBUTION } from '../config/basemaps'
import { ensureRtlTextSupport } from '../config/rtlText'
import {
  buildBackgroundPolygonVisibilityFilter,
  buildMarkerVisibilityFilter,
  buildResultPolygonVisibilityFilter,
  mayHaveDisplayMarker,
} from '../domain/mapPresentation'
import { UNMAPPED_GEOGRAPHY_COLOR } from '../domain/color'
import { coalitionVoteShare } from '../domain/coalitionMap'
import {
  partyComparisonBalance,
  partyComparisonColor,
} from '../domain/partyComparison'
import {
  partyCircleColor,
  partyGradientColor,
  partyVoteCircleRadius,
  partyVoteCount,
  partyVoteShare,
} from '../domain/partyMap'
import type { PartyMapDisplayMode } from '../domain/partyMap'
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
import { PartyMapDisplaySelector } from './PartyMapDisplaySelector'

const SOURCE_ID = 'election-geographies'
const MARKER_SOURCE_ID = 'election-geography-markers'
const BACKDROP_SOURCE_ID = 'election-geography-backdrop'
const BASEMAP_MASK_SOURCE_ID = 'basemap-outside-mask'
const MAP_CONTEXT_SOURCE_ID = 'map-context-footprint'
const PARTY_CIRCLE_SOURCE_ID = 'party-vote-circles'
const BACKGROUND_FILL_LAYER_ID = 'election-background-fill'
const BACKGROUND_LINE_LAYER_ID = 'election-background-line'
const FILL_LAYER_ID = 'election-fill'
const LINE_LAYER_ID = 'election-line'
const MARKER_LAYER_ID = 'election-markers'
const BACKDROP_FILL_LAYER_ID = 'election-backdrop-fill'
const BASEMAP_MASK_LAYER_ID = 'basemap-outside-mask-fill'
const MAP_CONTEXT_LINE_LAYER_ID = 'map-context-boundary'
const PARTY_CIRCLE_LAYER_ID = 'party-vote-circles-layer'
const GEOGRAPHY_BORDER_COLOR = '#4f5651'
const UNMAPPED_AREA_FILL_OPACITY = 0.58
const REMOTE_STYLE_LOAD_TIMEOUT_MS = 8_000
const BASEMAP_OUTSIDE_COLOR = '#c2c8ca'
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

interface PartyMapPresentation {
  partyId: string
  color: string
  upperBoundShare: number
  upperBoundVotes: number
  displayMode: PartyMapDisplayMode
  points: Array<{
    id: string
    coordinates: [number, number]
  }>
}

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
  selectableGeographyIds: string[]
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
  partyMap: PartyMapPresentation | null
  partyComparison: {
    firstPartyId: string
    firstColor: string
    secondPartyId: string
    secondColor: string
  } | null
  coalition: {
    partyIds: string[]
    color: string
    upperBoundShare: number
  } | null
  basemapMode: BasemapMode
  onBasemapModeChange: (mode: BasemapMode) => void
  onPartyMapDisplayModeChange: (mode: PartyMapDisplayMode) => void
  onSelect: (id: string | null) => void
}

type MapContextGeometry =
  | { type: 'Polygon'; coordinates: number[][][] }
  | { type: 'MultiPolygon'; coordinates: number[][][][] }

interface PartyCircleProperties {
  id: string
  color: string
  strokeColor: string
  radius: number
  selected: boolean
}

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
  selectableGeographyIds,
  selectedId,
  focusRequest,
  addressMarker,
  partyMap,
  partyComparison,
  coalition,
  basemapMode,
  onBasemapModeChange,
  onPartyMapDisplayModeChange,
  onSelect,
}: MapCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const onSelectRef = useRef(onSelect)
  const onBasemapModeChangeRef = useRef(onBasemapModeChange)
  const activeBasemapModeRef = useRef(basemapMode)
  const remoteStyleTimerRef = useRef<number | null>(null)
  const attributionControlRef = useRef<maplibregl.AttributionControl | null>(null)
  const addressMarkerRef = useRef<maplibregl.Marker | null>(null)
  const basemapLabelFiltersRef = useRef(new Map<string, FilterSpecification | null>())
  const recordsByIdRef = useRef(new Map<string, ResultRecord>())
  const selectableGeographyIdsRef = useRef(new Set<string>())
  const [mapReady, setMapReady] = useState(false)
  const [styleRevision, setStyleRevision] = useState(0)
  const [mapError, setMapError] = useState<string | null>(null)
  const [mapContextGeometry, setMapContextGeometry] = useState<MapContextGeometry | null>(null)
  const partyById = useMemo(() => new Map(parties.map((party) => [party.id, party])), [parties])
  const recordsById = useMemo(() => new Map(records.map((record) => [record.id, record])), [records])

  onSelectRef.current = onSelect
  onBasemapModeChangeRef.current = onBasemapModeChange
  recordsByIdRef.current = recordsById
  selectableGeographyIdsRef.current = new Set(selectableGeographyIds)

  useEffect(() => {
    if (!containerRef.current) {
      return
    }

    let disposed = false
    if (activeBasemapModeRef.current === 'vector') {
      void ensureRtlTextSupport(maplibregl).catch(() => {
        if (!disposed && activeBasemapModeRef.current === 'vector') {
          onBasemapModeChangeRef.current('neutral')
        }
      })
    }

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
      const attributionControl = new maplibregl.AttributionControl({
        compact: true,
        customAttribution: MAP_CONTEXT_ATTRIBUTION,
      })
      map.addControl(attributionControl, 'bottom-left')
      attributionControlRef.current = attributionControl
      if (isRemoteBasemap(activeBasemapModeRef.current)) {
        remoteStyleTimerRef.current = window.setTimeout(() => {
          if (isRemoteBasemap(activeBasemapModeRef.current)) {
            onBasemapModeChangeRef.current('neutral')
          }
        }, REMOTE_STYLE_LOAD_TIMEOUT_MS)
      }
      map.on('style.load', () => {
        clearRemoteStyleTimer(remoteStyleTimerRef)
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
      clearRemoteStyleTimer(remoteStyleTimerRef)
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
    clearRemoteStyleTimer(remoteStyleTimerRef)

    if (attributionControlRef.current) {
      map.removeControl(attributionControlRef.current)
      attributionControlRef.current = null
    }
    const attributionControl = new maplibregl.AttributionControl({
      compact: true,
      customAttribution: MAP_CONTEXT_ATTRIBUTION,
    })
    map.addControl(attributionControl, 'bottom-left')
    attributionControlRef.current = attributionControl
    if (basemapMode === 'vector') {
      void ensureRtlTextSupport(maplibregl).catch(() => {
        if (activeBasemapModeRef.current === 'vector') {
          onBasemapModeChangeRef.current('neutral')
        }
      })
    }
    if (isRemoteBasemap(basemapMode)) {
      remoteStyleTimerRef.current = window.setTimeout(() => {
        if (isRemoteBasemap(activeBasemapModeRef.current)) {
          onBasemapModeChangeRef.current('neutral')
        }
      }, REMOTE_STYLE_LOAD_TIMEOUT_MS)
    }

    try {
      map.setStyle(basemapStyle(basemapMode), { diff: false })
    } catch (error) {
      if (isRemoteBasemap(basemapMode)) {
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

    if (map.getLayer(PARTY_CIRCLE_LAYER_ID)) {
      map.removeLayer(PARTY_CIRCLE_LAYER_ID)
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
    if (map.getSource(PARTY_CIRCLE_SOURCE_ID)) {
      map.removeSource(PARTY_CIRCLE_SOURCE_ID)
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
            'fill-opacity': basemapMode === 'neutral' ? 0.28 : 0.18,
          },
        },
        basemapDetailAnchor,
      )
    }

    const maskBasemap = basemapMode !== 'neutral' && basemapMaskGeometryUrl
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
            'fill-color': BASEMAP_OUTSIDE_COLOR,
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
    map.addSource(PARTY_CIRCLE_SOURCE_ID, {
      type: 'geojson',
      data: emptyFeatureCollection(),
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
          ['case', ['boolean', ['feature-state', 'selected'], false], 1, 0.12],
          7,
          ['case', ['boolean', ['feature-state', 'selected'], false], 1.2, 0.18],
          9,
          ['case', ['boolean', ['feature-state', 'selected'], false], 1.5, 0.38],
          11,
          ['case', ['boolean', ['feature-state', 'selected'], false], 2, 0.72],
          13,
          ['case', ['boolean', ['feature-state', 'selected'], false], 2.5, 1.05],
        ],
        'line-opacity': [
          'interpolate',
          ['linear'],
          ['zoom'],
          5.4,
          [
            'case',
            ['boolean', ['feature-state', 'selected'], false],
            1,
            geographyMode === 'statistical-area' ? 0.5 : 0,
          ],
          9,
          [
            'case',
            ['boolean', ['feature-state', 'selected'], false],
            1,
            geographyMode === 'statistical-area' ? 0.7 : 0,
          ],
          13,
          [
            'case',
            ['boolean', ['feature-state', 'selected'], false],
            1,
            geographyMode === 'statistical-area' ? 0.9 : 0,
          ],
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
          [
            'case',
            ['boolean', ['feature-state', 'partyCircleMode'], false],
            0.12,
            0.9,
          ],
          [
            'case',
            ['boolean', ['feature-state', 'partyCircleMode'], false],
            0,
            [
              'case',
              ['boolean', ['feature-state', 'analysisMode'], false],
              0.84,
              0.7,
            ],
          ],
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
          ['case', ['boolean', ['feature-state', 'selected'], false], 1, 0.12],
          7,
          ['case', ['boolean', ['feature-state', 'selected'], false], 1.2, 0.18],
          9,
          ['case', ['boolean', ['feature-state', 'selected'], false], 1.5, 0.38],
          11,
          ['case', ['boolean', ['feature-state', 'selected'], false], 2, 0.72],
          13,
          ['case', ['boolean', ['feature-state', 'selected'], false], 2.5, 1.05],
        ],
        'line-opacity': [
          'interpolate',
          ['linear'],
          ['zoom'],
          5.4,
          ['case', ['boolean', ['feature-state', 'selected'], false], 1, 0.5],
          9,
          ['case', ['boolean', ['feature-state', 'selected'], false], 1, 0.7],
          13,
          ['case', ['boolean', ['feature-state', 'selected'], false], 1, 0.9],
        ],
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
    const partyCircleLayer: CircleLayerSpecification = {
      id: PARTY_CIRCLE_LAYER_ID,
      source: PARTY_CIRCLE_SOURCE_ID,
      type: 'circle',
      layout: {
        visibility: 'none',
      },
      paint: {
        'circle-color': ['to-color', ['get', 'color']],
        'circle-opacity': 0.82,
        'circle-radius': ['get', 'radius'],
        'circle-stroke-color': [
          'case',
          ['boolean', ['get', 'selected'], false],
          '#151815',
          ['to-color', ['get', 'strokeColor']],
        ],
        'circle-stroke-opacity': 0.64,
        'circle-stroke-width': [
          'case',
          ['boolean', ['get', 'selected'], false],
          2.5,
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
    map.addLayer(partyCircleLayer, basemapLabelAnchor)
    map.fitBounds(bounds, { padding: 36, duration: 0 })

    const handleClick = (event: maplibregl.MapLayerMouseEvent) => {
      const id = featureId(event)
      if (
        id &&
        (recordsByIdRef.current.has(id) || selectableGeographyIdsRef.current.has(id))
      ) {
        onSelectRef.current(id)
      }
    }
    const updatePointer = (event: maplibregl.MapLayerMouseEvent) => {
      const id = featureId(event)
      map.getCanvas().style.cursor =
        id &&
        (recordsByIdRef.current.has(id) || selectableGeographyIdsRef.current.has(id))
          ? 'pointer'
          : ''
    }
    const hidePointer = () => {
      map.getCanvas().style.cursor = ''
    }
    map.on('click', FILL_LAYER_ID, handleClick)
    map.on('click', BACKGROUND_FILL_LAYER_ID, handleClick)
    map.on('click', MARKER_LAYER_ID, handleClick)
    map.on('click', PARTY_CIRCLE_LAYER_ID, handleClick)
    map.on('mousemove', FILL_LAYER_ID, updatePointer)
    map.on('mousemove', BACKGROUND_FILL_LAYER_ID, updatePointer)
    map.on('mousemove', MARKER_LAYER_ID, updatePointer)
    map.on('mousemove', PARTY_CIRCLE_LAYER_ID, updatePointer)
    map.on('mouseleave', FILL_LAYER_ID, hidePointer)
    map.on('mouseleave', BACKGROUND_FILL_LAYER_ID, hidePointer)
    map.on('mouseleave', MARKER_LAYER_ID, hidePointer)
    map.on('mouseleave', PARTY_CIRCLE_LAYER_ID, hidePointer)

    return () => {
      map.off('click', FILL_LAYER_ID, handleClick)
      map.off('click', BACKGROUND_FILL_LAYER_ID, handleClick)
      map.off('click', MARKER_LAYER_ID, handleClick)
      map.off('click', PARTY_CIRCLE_LAYER_ID, handleClick)
      map.off('mousemove', FILL_LAYER_ID, updatePointer)
      map.off('mousemove', BACKGROUND_FILL_LAYER_ID, updatePointer)
      map.off('mousemove', MARKER_LAYER_ID, updatePointer)
      map.off('mousemove', PARTY_CIRCLE_LAYER_ID, updatePointer)
      map.off('mouseleave', FILL_LAYER_ID, hidePointer)
      map.off('mouseleave', BACKGROUND_FILL_LAYER_ID, hidePointer)
      map.off('mouseleave', MARKER_LAYER_ID, hidePointer)
      map.off('mouseleave', PARTY_CIRCLE_LAYER_ID, hidePointer)
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
      !map.getSource(PARTY_CIRCLE_SOURCE_ID) ||
      !map.getLayer(FILL_LAYER_ID) ||
      !map.getLayer(LINE_LAYER_ID) ||
      !map.getLayer(BACKGROUND_FILL_LAYER_ID) ||
      !map.getLayer(BACKGROUND_LINE_LAYER_ID) ||
      !map.getLayer(MARKER_LAYER_ID) ||
      !map.getLayer(PARTY_CIRCLE_LAYER_ID)
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
    const partyCircleMode = partyMap?.displayMode === 'circles'
    const partyCirclePointIds = new Set(partyMap?.points.map((point) => point.id) ?? [])
    map.setLayoutProperty(
      MARKER_LAYER_ID,
      'visibility',
      partyCircleMode ? 'none' : 'visible',
    )
    map.setLayoutProperty(
      PARTY_CIRCLE_LAYER_ID,
      'visibility',
      partyCircleMode ? 'visible' : 'none',
    )
    const partyCircleSource = map.getSource(PARTY_CIRCLE_SOURCE_ID) as GeoJSONSource
    partyCircleSource.setData(
      buildPartyCircleFeatureCollection(
        partyMap,
        records,
        hiddenGeographyIds,
        selectedId,
      ),
    )

    const featureStates = records.map((record) => {
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
      } else if (coalition) {
        color = partyGradientColor(
          coalition.color,
          coalitionVoteShare(record, coalition.partyIds),
          coalition.upperBoundShare,
        )
      }
      return {
        record,
        state: {
          hasData: true,
          color,
          analysisMode: Boolean(partyMap || partyComparison || coalition),
          partyCircleMode: partyCircleMode && partyCirclePointIds.has(record.id),
          selected: record.id === selectedId,
        },
      }
    })

    const applyPolygonFeatureStates = () => {
      if (!map.getSource(SOURCE_ID)) {
        return
      }
      map.removeFeatureState({ source: SOURCE_ID })
      for (const { record, state } of featureStates) {
        map.setFeatureState(
          { source: SOURCE_ID, id: record.id },
          state,
        )
      }
      if (selectedId && !recordsById.has(selectedId)) {
        map.setFeatureState(
          { source: SOURCE_ID, id: selectedId },
          { hasData: false, selected: true },
        )
      }
    }

    const applyMarkerFeatureStates = () => {
      if (!map.getSource(MARKER_SOURCE_ID)) {
        return
      }
      map.removeFeatureState({ source: MARKER_SOURCE_ID })
      for (const { record, state } of featureStates) {
        if (mayHaveDisplayMarker(record)) {
          map.setFeatureState({ source: MARKER_SOURCE_ID, id: record.id }, state)
        }
      }
    }

    const applyFeatureStates = () => {
      applyPolygonFeatureStates()
      applyMarkerFeatureStates()
    }
    let polygonSourceEventApplied = false
    let markerSourceEventApplied = false
    const handleSourceData = (event: maplibregl.MapSourceDataEvent) => {
      if (event.sourceId === SOURCE_ID) {
        if (!polygonSourceEventApplied || event.isSourceLoaded) {
          applyPolygonFeatureStates()
          polygonSourceEventApplied = true
        }
      } else if (event.sourceId === MARKER_SOURCE_ID) {
        if (!markerSourceEventApplied || event.isSourceLoaded) {
          applyMarkerFeatureStates()
          markerSourceEventApplied = true
        }
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
    coalition,
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
      {partyMap ? (
        <PartyMapDisplaySelector
          language={language}
          mode={partyMap.displayMode}
          onChange={onPartyMapDisplayModeChange}
        />
      ) : null}
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
    sourceId === PARTY_CIRCLE_SOURCE_ID ||
    sourceId === BACKDROP_SOURCE_ID ||
    sourceId === BASEMAP_MASK_SOURCE_ID ||
    sourceId === MAP_CONTEXT_SOURCE_ID
  )
}

function buildPartyCircleFeatureCollection(
  partyMap: PartyMapPresentation | null,
  records: ResultRecord[],
  hiddenGeographyIds: string[],
  selectedId: string | null,
): FeatureCollection<Point, PartyCircleProperties> {
  if (!partyMap || partyMap.displayMode !== 'circles') {
    return emptyFeatureCollection()
  }

  const recordsById = new Map(records.map((record) => [record.id, record]))
  const hiddenIds = new Set(hiddenGeographyIds)
  return {
    type: 'FeatureCollection',
    features: partyMap.points.flatMap((point) => {
      const record = recordsById.get(point.id)
      const votes = record ? partyVoteCount(record, partyMap.partyId) : 0
      if (!record || hiddenIds.has(point.id) || votes <= 0) {
        return []
      }
      return [
        {
          type: 'Feature' as const,
          geometry: {
            type: 'Point' as const,
            coordinates: point.coordinates,
          },
          properties: {
            id: point.id,
            color: partyCircleColor(
              partyMap.color,
              partyVoteShare(record, partyMap.partyId),
              partyMap.upperBoundShare,
            ),
            strokeColor: partyGradientColor(partyMap.color, 1, 1),
            radius: partyVoteCircleRadius(votes, partyMap.upperBoundVotes),
            selected: point.id === selectedId,
          },
        },
      ]
    }),
  }
}

function emptyFeatureCollection(): FeatureCollection<Point, PartyCircleProperties> {
  return {
    type: 'FeatureCollection',
    features: [],
  }
}

function isRemoteBasemap(mode: BasemapMode): boolean {
  return mode === 'vector'
}

function clearRemoteStyleTimer(timerRef: { current: number | null }): void {
  if (timerRef.current !== null) {
    window.clearTimeout(timerRef.current)
    timerRef.current = null
  }
}

function featureId(event: maplibregl.MapLayerMouseEvent): string | null {
  const id = event.features?.[0]?.id
  return typeof id === 'string' ? id : null
}
