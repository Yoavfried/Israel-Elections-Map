import { useEffect, useMemo, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import type {
  CircleLayerSpecification,
  FillLayerSpecification,
  LineLayerSpecification,
  Map as MapLibreMap,
} from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
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
import type {
  GeographyBounds,
  GeographyMode,
  Language,
  Party,
  ResultRecord,
} from '../domain/schemas'
import { translate } from '../i18n/translations'

const SOURCE_ID = 'election-geographies'
const MARKER_SOURCE_ID = 'election-geography-markers'
const BACKDROP_SOURCE_ID = 'election-geography-backdrop'
const BACKGROUND_FILL_LAYER_ID = 'election-background-fill'
const BACKGROUND_LINE_LAYER_ID = 'election-background-line'
const FILL_LAYER_ID = 'election-fill'
const LINE_LAYER_ID = 'election-line'
const MARKER_LAYER_ID = 'election-markers'
const BACKDROP_FILL_LAYER_ID = 'election-backdrop-fill'
const MAP_BACKGROUND_COLOR = '#f3f0e8'
const GEOGRAPHY_BORDER_COLOR = '#626a65'
const UNMAPPED_AREA_FILL_OPACITY = 0.58

interface MapCanvasProps {
  language: Language
  geographyMode: GeographyMode
  geometryUrl: string
  markerGeometryUrl: string
  backdropGeometryUrl: string | null
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
  onSelect: (id: string | null) => void
}

const baseStyle = {
  version: 8 as const,
  sources: {},
  layers: [
    {
      id: 'paper-background',
      type: 'background' as const,
      paint: { 'background-color': MAP_BACKGROUND_COLOR },
    },
  ],
}

export default function MapCanvas({
  language,
  geographyMode,
  geometryUrl,
  markerGeometryUrl,
  backdropGeometryUrl,
  bounds,
  records,
  parties,
  hiddenGeographyIds,
  selectedId,
  focusRequest,
  partyMap,
  partyComparison,
  onSelect,
}: MapCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const onSelectRef = useRef(onSelect)
  const recordsByIdRef = useRef(new Map<string, ResultRecord>())
  const [mapReady, setMapReady] = useState(false)
  const [mapError, setMapError] = useState<string | null>(null)
  const partyById = useMemo(() => new Map(parties.map((party) => [party.id, party])), [parties])
  const recordsById = useMemo(() => new Map(records.map((record) => [record.id, record])), [records])

  onSelectRef.current = onSelect
  recordsByIdRef.current = recordsById

  useEffect(() => {
    if (!containerRef.current) {
      return
    }

    try {
      const map = new maplibregl.Map({
        container: containerRef.current,
        style: baseStyle,
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
      map.once('load', () => setMapReady(true))
      map.on('error', (event) => {
        if (event.error) {
          setMapError(event.error.message)
        }
      })
    } catch (error) {
      setMapError(error instanceof Error ? error.message : String(error))
    }

    return () => {
      mapRef.current?.remove()
      mapRef.current = null
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady) {
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
    if (map.getSource(SOURCE_ID)) {
      map.removeSource(SOURCE_ID)
    }
    if (map.getSource(MARKER_SOURCE_ID)) {
      map.removeSource(MARKER_SOURCE_ID)
    }
    if (map.getSource(BACKDROP_SOURCE_ID)) {
      map.removeSource(BACKDROP_SOURCE_ID)
    }

    if (backdropGeometryUrl) {
      map.addSource(BACKDROP_SOURCE_ID, {
        type: 'geojson',
        data: backdropGeometryUrl,
      })
      map.addLayer({
        id: BACKDROP_FILL_LAYER_ID,
        source: BACKDROP_SOURCE_ID,
        type: 'fill',
        filter: buildBackgroundPolygonVisibilityFilter([], []),
        paint: {
          'fill-color': UNMAPPED_GEOGRAPHY_COLOR,
          'fill-opacity': 0.28,
        },
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
    map.addLayer(backgroundFillLayer)
    map.addLayer(backgroundLineLayer)
    map.addLayer(fillLayer)
    map.addLayer(lineLayer)
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
    bounds,
    geographyMode,
    geometryUrl,
    hiddenGeographyIds,
    mapReady,
    markerGeometryUrl,
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
  }, [focusRequest, geographyMode, geometryUrl, mapReady])

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
      ref={containerRef}
      className="map-canvas"
      role="region"
      aria-label={translate(language, 'mapLabel')}
    />
  )
}

function featureId(event: maplibregl.MapLayerMouseEvent): string | null {
  const id = event.features?.[0]?.id
  return typeof id === 'string' ? id : null
}
