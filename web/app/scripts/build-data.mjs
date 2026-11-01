import { createHash } from 'node:crypto'
import { mkdir, readFile, rename, rm, writeFile } from 'node:fs/promises'
import { dirname, isAbsolute, relative, resolve } from 'node:path'
import {
  applyStatisticalDisplayGroups,
  assertUniqueStatisticalDisplayOwnership,
  aliasJoinedCompositeResults,
  buildCoverage,
  buildCompositeMetadataIndex,
  buildCustomMetadataIndex,
  buildDisplayMarkers,
  buildGeographySearchIndex,
  buildHiddenLocalityIds,
  buildMetadataIndex,
  buildMunicipalityFallbackDisplay,
  buildNationalResultsPayload,
  buildPartyRegistryIndex,
  buildResultPayload,
  parseCsv,
  pruneGeography,
} from './lib/compiler.mjs'

const APP_ROOT = resolve(import.meta.dirname, '..')
const REPOSITORY_ROOT = resolve(APP_ROOT, '..', '..')
const DEFAULT_SOURCE_ROOT = resolve(REPOSITORY_ROOT, 'data', 'processed')
const DEFAULT_OUTPUT_ROOT = resolve(APP_ROOT, 'public', 'data', 'v2')
const HISTORICAL_STATISTICAL_AREA_VINTAGES = [1995, 2008, 2011]

async function main() {
  const options = parseArguments(process.argv.slice(2))
  const sourceRoot = resolveOption(options.source, DEFAULT_SOURCE_ROOT)
  const outputRoot = resolveOption(options.output, DEFAULT_OUTPUT_ROOT)
  assertSafeOutputPath(outputRoot)

  const stagingRoot = `${outputRoot}.tmp-${process.pid}`
  await rm(stagingRoot, { force: true, recursive: true })
  await mkdir(stagingRoot, { recursive: true })

  try {
    const [
      electionConfig,
      partyOverrideConfig,
      partyRegistryRows,
      electionRuleRows,
      electionMandateRows,
      localityDisplayOverrideRows,
      statisticalAreaDisplayOverrideRows,
      statisticalAreaDisplayGroupRows,
      statisticalAreaResultAggregateRows,
      summaryRows,
      geographySummary,
      statisticalMetadataRows,
      localityMetadataRows,
      statisticalAreas,
      localities,
      historicalComponentFallbackGeometries,
      historicalLocalityFallbackGeometries,
      statisticalAreaBackdrop,
      mapContextFootprint,
      compositeLocalities,
      customGeographies,
      statisticalAreaResultAggregates,
      statisticalAreaPollingGroupDisplayRows,
      statisticalAreaPollingGroupDisplays,
      statisticalAreaPollingGroupAreaEvidenceRows,
    ] = await Promise.all([
      readJson(resolve(APP_ROOT, 'config', 'elections.json')),
      readJson(resolve(APP_ROOT, 'config', 'party-overrides.json')),
      readCsv(resolve(REPOSITORY_ROOT, 'data', 'manual', 'party_registry.csv')),
      readCsv(resolve(REPOSITORY_ROOT, 'data', 'manual', 'election_rules.csv')),
      readCsv(resolve(REPOSITORY_ROOT, 'data', 'manual', 'election_mandates.csv')),
      readCsv(resolve(REPOSITORY_ROOT, 'data', 'manual', 'locality_display_overrides.csv')),
      readCsv(
        resolve(REPOSITORY_ROOT, 'data', 'manual', 'statistical_area_display_overrides.csv'),
      ),
      readCsv(
        resolve(REPOSITORY_ROOT, 'data', 'manual', 'statistical_area_display_groups.csv'),
      ),
      readCsv(
        resolve(
          sourceRoot,
          'geographies',
          'statistical_area_result_aggregates.metadata.csv',
        ),
      ),
      readCsv(resolve(sourceRoot, 'public', 'election_summary.csv')),
      readJson(resolve(sourceRoot, 'geographies', 'geography_build_summary.json')),
      readCsv(resolve(sourceRoot, 'geographies', 'statistical_areas_2022.metadata.csv')),
      readCsv(resolve(sourceRoot, 'geographies', 'localities_2022.metadata.csv')),
      readJson(
        resolve(sourceRoot, 'geographies', 'statistical_areas_2022.display.simplified.geojson'),
      ),
      readJson(
        resolve(sourceRoot, 'geographies', 'localities_2022_dissolved.display.simplified.geojson'),
      ),
      readJson(
        resolve(
          sourceRoot,
          'geographies',
          'historical_composite_component_display_geometries.geojson',
        ),
      ),
      readJson(
        resolve(
          sourceRoot,
          'geographies',
          'historical_locality_fallback_display_geometries.geojson',
        ),
      ),
      readJson(
        resolve(sourceRoot, 'geographies', 'statistical_area_land_backdrop.simplified.geojson'),
      ),
      readJson(resolve(APP_ROOT, 'data', 'map-context-footprint.geojson')),
      readJson(resolve(sourceRoot, 'geographies', 'composite_localities.simplified.geojson')),
      readJson(resolve(sourceRoot, 'geographies', 'custom_geographies.geojson')),
      readJson(
        resolve(sourceRoot, 'geographies', 'statistical_area_result_aggregates.geojson'),
      ),
      readCsv(
        resolve(sourceRoot, 'public', 'statistical_area_polling_group_displays.csv'),
      ),
      readJson(
        resolve(
          sourceRoot,
          'geographies',
          'statistical_area_polling_group_displays.geojson',
        ),
      ),
      readCsv(
        resolve(
          sourceRoot,
          'audits',
          'statistical_area_polling_group_area_evidence.csv',
        ),
      ),
    ])
    const historicalStatisticalSources = await Promise.all(
      HISTORICAL_STATISTICAL_AREA_VINTAGES.map(async (vintage) => [
        vintage,
        {
          metadataRows: await readCsv(
            resolve(sourceRoot, 'geographies', `statistical_areas_${vintage}.metadata.csv`),
          ),
          geography: await readJson(
            resolve(
              sourceRoot,
              'geographies',
              `statistical_areas_${vintage}.display.simplified.geojson`,
            ),
          ),
        },
      ]),
    )
    const statisticalSourcesByVintage = new Map([
      ...historicalStatisticalSources,
      [2022, { metadataRows: statisticalMetadataRows, geography: statisticalAreas }],
    ])

    validateConfiguration(electionConfig, partyOverrideConfig)
    const partyRegistryByElection = buildPartyRegistryIndex(partyRegistryRows)
    validatePartyRegistryElections(electionConfig, partyRegistryByElection)
    const electionRulesByElection = uniqueRowsByElection(electionRuleRows, 'election rules')
    const electionMandatesByElection = groupRowsByElection(
      electionMandateRows,
      'election mandates',
    )
    validateNationalResultElections(
      electionConfig,
      electionRulesByElection,
      electionMandatesByElection,
    )

    const summaryByElection = new Map(summaryRows.map((row) => [row.election, row]))
    const statisticalMetadataByVintage = new Map(
      [...statisticalSourcesByVintage].map(([vintage, source]) => [
        vintage,
        buildMetadataIndex(source.metadataRows, 'statistical-area'),
      ]),
    )
    const localityMetadata = new Map([
      ...buildMetadataIndex(localityMetadataRows, 'locality'),
      ...buildCompositeMetadataIndex(compositeLocalities),
    ])
    const localityDisplayOverrides = buildLocalityDisplayOverrideIndex(
      localityDisplayOverrideRows,
      electionConfig,
      localityMetadata,
    )
    const statisticalAreaDisplayOverrides = buildStatisticalAreaDisplayOverrideIndex(
      statisticalAreaDisplayOverrideRows,
      electionConfig,
      statisticalMetadataByVintage,
    )
    const statisticalCustomGeographies = mergeFeatureCollections(
      customGeographies,
      statisticalAreaResultAggregates,
      statisticalAreaPollingGroupDisplays,
    )
    const customMetadata = buildCustomMetadataIndex(customGeographies)
    const statisticalCustomMetadata = buildCustomMetadataIndex(statisticalCustomGeographies)
    const statisticalAreaDisplayGroups = buildStatisticalAreaDisplayGroupIndex(
      [...statisticalAreaDisplayGroupRows, ...statisticalAreaResultAggregateRows],
      electionConfig,
      statisticalMetadataByVintage,
      statisticalCustomMetadata,
    )
    const coverageByElection = new Map(
      electionConfig.map((election) => [
        election.id,
        {
          'statistical-area': buildCoverage(summaryByElection.get(election.id), 'statistical-area'),
          locality: buildCoverage(summaryByElection.get(election.id), 'locality'),
        },
      ]),
    )

    const prunedStatisticalAreasByVintage = new Map(
      [...statisticalSourcesByVintage].map(([vintage, source]) => [
        vintage,
        pruneGeography(
          source.geography,
          'statistical-area',
          filterStatisticalCustomGeographiesByVintage(
            statisticalCustomGeographies,
            vintage,
          ),
        ),
      ]),
    )
    const prunedLocalities = pruneGeography(
      localities,
      'locality',
      customGeographies,
      compositeLocalities,
    )
    const electionSourceDataById = new Map(
      await Promise.all(
        electionConfig.map(async (election) => {
          const electionSlug = election.id.toLowerCase()
          const [statisticalRows, localityRows, customRows, envelopeRows, fallbackRows] =
            await Promise.all([
              readCsv(
                resolve(sourceRoot, 'public', 'statistical_area_results', `${electionSlug}.csv`),
              ),
              readCsv(resolve(sourceRoot, 'public', 'locality_results', `${electionSlug}.csv`)),
              readCsv(
                resolve(sourceRoot, 'public', 'custom_geography_results', `${electionSlug}.csv`),
              ),
              readCsv(resolve(sourceRoot, 'public', 'envelope_results', `${electionSlug}.csv`)),
              readCsv(
                resolve(
                  sourceRoot,
                  'public',
                  'municipality_display_fallbacks',
                  `${electionSlug}.csv`,
                ),
              ),
            ])
          return [
            election.id,
            { statisticalRows, localityRows, customRows, envelopeRows, fallbackRows },
          ]
        }),
      ),
    )
    const fallbackFeaturesByVintage = new Map()
    const componentFallbackGeometryIds = new Set(
      historicalComponentFallbackGeometries.features.map((feature) =>
        String(feature.properties?.fallback_geography_id ?? feature.id ?? '').trim(),
      ),
    )
    if (
      componentFallbackGeometryIds.has('') ||
      componentFallbackGeometryIds.size !== historicalComponentFallbackGeometries.features.length
    ) {
      throw new Error('Historical component fallback geography has blank or duplicate IDs')
    }
    const localityFallbackGeometryIds = new Set(
      historicalLocalityFallbackGeometries.features.map((feature) =>
        String(feature.properties?.fallback_geography_id ?? feature.id ?? '').trim(),
      ),
    )
    if (
      localityFallbackGeometryIds.has('') ||
      localityFallbackGeometryIds.size !== historicalLocalityFallbackGeometries.features.length
    ) {
      throw new Error('Historical locality fallback geography has blank or duplicate IDs')
    }
    const referencedComponentFallbackIds = new Set()
    const referencedLocalityFallbackIds = new Set()
    for (const election of electionConfig) {
      const sourceData = electionSourceDataById.get(election.id)
      const vintage = Number(election.statisticalAreaVintage)
      const statisticalGeography = prunedStatisticalAreasByVintage.get(vintage)
      if (!sourceData || !statisticalGeography) {
        throw new Error(`${election.id} is missing municipality fallback build inputs`)
      }
      for (const row of sourceData.fallbackRows) {
        const fallbackId = String(row.fallback_geography_id ?? '').trim()
        if (fallbackId.startsWith('municipality-component-fallback:')) {
          referencedComponentFallbackIds.add(fallbackId)
        }
        if (localityFallbackGeometryIds.has(fallbackId)) {
          referencedLocalityFallbackIds.add(fallbackId)
        }
      }
      const fallbackDisplay = buildMunicipalityFallbackDisplay({
        electionId: election.id,
        vintage,
        fallbackRows: sourceData.fallbackRows,
        localityGeography: prunedLocalities,
        statisticalGeography,
        componentFallbackGeography: historicalComponentFallbackGeometries,
        localityFallbackGeography: filterFallbackGeographiesByVintage(
          historicalLocalityFallbackGeometries,
          vintage,
        ),
      })
      electionSourceDataById.set(election.id, { ...sourceData, fallbackDisplay })

      let fallbackFeatures = fallbackFeaturesByVintage.get(vintage)
      if (!fallbackFeatures) {
        fallbackFeatures = new Map()
        fallbackFeaturesByVintage.set(vintage, fallbackFeatures)
      }
      for (const feature of fallbackDisplay.features) {
        const existing = fallbackFeatures.get(feature.id)
        if (existing && JSON.stringify(existing) !== JSON.stringify(feature)) {
          throw new Error(`Municipality fallback geometry changed across elections: ${feature.id}`)
        }
        fallbackFeatures.set(feature.id, feature)
      }
    }
    const missingComponentFallbackGeometryIds = [...referencedComponentFallbackIds].filter(
      (id) => !componentFallbackGeometryIds.has(id),
    )
    const unusedComponentFallbackGeometryIds = [...componentFallbackGeometryIds].filter(
      (id) => !referencedComponentFallbackIds.has(id),
    )
    if (missingComponentFallbackGeometryIds.length || unusedComponentFallbackGeometryIds.length) {
      throw new Error(
        `Historical component fallback geometry mismatch: missing=${missingComponentFallbackGeometryIds.join(',') || 'none'} unused=${unusedComponentFallbackGeometryIds.join(',') || 'none'}`,
      )
    }
    const unusedLocalityFallbackGeometryIds = [...localityFallbackGeometryIds].filter(
      (id) => !referencedLocalityFallbackIds.has(id),
    )
    if (unusedLocalityFallbackGeometryIds.length) {
      throw new Error(
        `Historical locality fallback geometry is not referenced: ${unusedLocalityFallbackGeometryIds.join(',')}`,
      )
    }
    for (const [vintage, featuresById] of fallbackFeaturesByVintage) {
      prunedStatisticalAreasByVintage.get(vintage)?.features.push(...featuresById.values())
    }
    const statisticalAreaBackdropUrl = 'geographies/statistical-area-backdrop.geojson'
    const basemapMaskGeometryUrl = 'geographies/basemap-outside-mask.geojson'
    const mapContextGeometryUrl = 'geographies/map-context-footprint.geojson'
    const basemapOutsideMask = buildBasemapOutsideMask(mapContextFootprint)
    const statisticalMarkersByVintage = new Map(
      [...prunedStatisticalAreasByVintage].map(([vintage, geography]) => [
        vintage,
        buildDisplayMarkers(geography),
      ]),
    )
    const localityMarkers = buildDisplayMarkers(prunedLocalities)

    const assets = []
    const writeJsonAsset = async (relativePath, payload, pretty = false) => {
      const text = `${JSON.stringify(payload, null, pretty ? 2 : undefined)}\n`
      const assetHash = createHash('sha256').update(text).digest('hex')
      const absolutePath = resolve(stagingRoot, relativePath)
      await mkdir(dirname(absolutePath), { recursive: true })
      await writeFile(absolutePath, text, 'utf8')
      assets.push({ path: relativePath.replaceAll('\\', '/'), bytes: Buffer.byteLength(text), sha256: assetHash })
    }

    const statisticalGeographyAssetsByVintage = new Map(
      [...prunedStatisticalAreasByVintage].map(([vintage, geography]) => {
        const markers = statisticalMarkersByVintage.get(vintage)
        if (!markers) {
          throw new Error(`Missing marker geography for statistical-area vintage ${vintage}`)
        }
        return [
          vintage,
          {
            vintage,
            geometryUrl: `geographies/statistical-areas-${vintage}.geojson`,
            markerGeometryUrl: `geographies/statistical-area-markers-${vintage}.geojson`,
            backdropGeometryUrl: statisticalAreaBackdropUrl,
            basemapMaskGeometryUrl,
            mapContextGeometryUrl,
            featureCount: geography.features.length,
            markerFeatureCount: markers.features.length,
          },
        ]
      }),
    )
    const localityGeographyAsset = {
      vintage: 2022,
      geometryUrl: 'geographies/localities.geojson',
      markerGeometryUrl: 'geographies/locality-markers.geojson',
      backdropGeometryUrl: statisticalAreaBackdropUrl,
      basemapMaskGeometryUrl,
      mapContextGeometryUrl,
      featureCount: prunedLocalities.features.length,
      markerFeatureCount: localityMarkers.features.length,
    }

    await Promise.all([
      ...[...prunedStatisticalAreasByVintage].flatMap(([vintage, geography]) => [
        writeJsonAsset(`geographies/statistical-areas-${vintage}.geojson`, geography),
        writeJsonAsset(
          `geographies/statistical-area-markers-${vintage}.geojson`,
          statisticalMarkersByVintage.get(vintage),
        ),
      ]),
      writeJsonAsset(localityGeographyAsset.geometryUrl, prunedLocalities),
      writeJsonAsset(localityGeographyAsset.markerGeometryUrl, localityMarkers),
      writeJsonAsset(statisticalAreaBackdropUrl, statisticalAreaBackdrop),
      writeJsonAsset(basemapMaskGeometryUrl, basemapOutsideMask),
      writeJsonAsset(mapContextGeometryUrl, mapContextFootprint),
    ])

    const catalogElections = []
    for (const election of electionConfig) {
      const electionSlug = election.id.toLowerCase()
      const statisticalAreaVintage = Number(election.statisticalAreaVintage)
      const statisticalMetadata = statisticalMetadataByVintage.get(statisticalAreaVintage)
      const statisticalGeographyAsset = statisticalGeographyAssetsByVintage.get(
        statisticalAreaVintage,
      )
      if (!statisticalMetadata || !statisticalGeographyAsset) {
        throw new Error(
          `${election.id} references unavailable statistical-area vintage ${election.statisticalAreaVintage}`,
        )
      }
      const sourceData = electionSourceDataById.get(election.id)
      if (!sourceData) {
        throw new Error(`${election.id} is missing compiled source data`)
      }
      const {
        statisticalRows,
        localityRows,
        customRows,
        envelopeRows,
        fallbackDisplay,
      } = sourceData
      const coverageByMode = coverageByElection.get(election.id)
      const displayOverrides = localityDisplayOverrides.get(election.id) ?? new Map()
      const statisticalDisplayOverrides =
        statisticalAreaDisplayOverrides.get(election.id) ?? new Map()
      const configuredHiddenStatisticalIds = [...statisticalDisplayOverrides]
        .filter(([, override]) => override.visibility === 'hidden')
        .map(([statAreaId]) => statAreaId)
      const hiddenLocalityIds = [
        ...new Set([
          ...buildHiddenLocalityIds(prunedLocalities, election.id),
          ...[...displayOverrides]
            .filter(([, override]) => override.visibility === 'hidden')
            .map(([localityId]) => localityId),
        ]),
      ].toSorted()
      const electionLocalityMetadata = applyMetadataNameOverrides(
        localityMetadata,
        displayOverrides,
      )
      const electionStatisticalMetadata = applyPendingAggregateNotices(
        applyMetadataNameOverrides(
          statisticalMetadata,
          statisticalDisplayOverrides,
        ),
        statisticalAreaPollingGroupAreaEvidenceRows,
        election.id,
      )
      const displayedLocalityRows = aliasJoinedCompositeResults(
        localityRows,
        prunedLocalities,
        election.id,
      )
      const pollingGroupRows = statisticalAreaPollingGroupDisplayRows
        .filter((row) => row.election === election.id)
        .map((row) =>
          Object.fromEntries(
            Object.entries(row).filter(([, value]) => String(value ?? '').trim() !== ''),
          ),
        )
      const electionStatisticalDisplayGroups =
        statisticalAreaDisplayGroups.get(election.id) ?? []
      assertUniqueStatisticalDisplayOwnership({
        electionId: election.id,
        displayGroups: electionStatisticalDisplayGroups,
        pollingGroupRows,
      })
      const pollingGroupHiddenIds = pollingGroupRows.flatMap((row) =>
        String(row.component_stat_area_ids ?? '')
          .split('|')
          .map((value) => value.trim())
          .filter(Boolean),
      )
      const statisticalCustomRows = [
        ...customRows.filter(
          (row) => !row.geography_mode || row.geography_mode === 'statistical-area',
        ),
        ...pollingGroupRows,
      ]
      const localityCustomRows = customRows.filter(
        (row) => !row.geography_mode || row.geography_mode === 'locality',
      )
      const statisticalDisplay = applyStatisticalDisplayGroups({
        electionId: election.id,
        primaryRows: statisticalRows,
        customRows,
        groups: electionStatisticalDisplayGroups,
      })
      const pollingGroupHiddenIdSet = new Set(pollingGroupHiddenIds)
      const statisticalPrimaryRows = statisticalDisplay.primaryRows.filter(
        (row) => !pollingGroupHiddenIdSet.has(row.stat_area_id),
      )
      const hiddenStatisticalIds = [
        ...new Set([
          ...configuredHiddenStatisticalIds,
          ...statisticalDisplay.hiddenGeographyIds,
          ...pollingGroupHiddenIds,
          ...fallbackDisplay.hiddenGeographyIds,
        ]),
      ].toSorted()
      const overrides = partyOverrideConfig.elections[election.id] ?? {}
      const partyRegistry = partyRegistryByElection.get(election.id)
      const excludedPartyColumns = Object.keys(
        partyOverrideConfig.ignoredResultColumns[election.id] ?? {},
      )
      const statisticalPayload = buildResultPayload({
        electionId: election.id,
        mode: 'statistical-area',
        primaryRows: statisticalPrimaryRows,
        customRows: [
          ...statisticalCustomRows,
          ...statisticalDisplay.displayRows,
          ...fallbackDisplay.displayRows,
        ],
        envelopeRows,
        metadataById: electionStatisticalMetadata,
        customMetadataById: new Map([
          ...statisticalCustomMetadata,
          ...fallbackDisplay.metadataById,
        ]),
        coverage: coverageByMode['statistical-area'],
        hiddenGeographyIds: hiddenStatisticalIds,
        partyRegistry,
        partyColorsByBallotLetter: partyOverrideConfig.ballotLetterColors,
        partyOverrides: overrides,
        excludedPartyColumns,
      })
      const localityPayload = buildResultPayload({
        electionId: election.id,
        mode: 'locality',
        primaryRows: displayedLocalityRows,
        customRows: localityCustomRows,
        envelopeRows,
        metadataById: electionLocalityMetadata,
        customMetadataById: customMetadata,
        coverage: coverageByMode.locality,
        hiddenGeographyIds: hiddenLocalityIds,
        partyRegistry,
        partyColorsByBallotLetter: partyOverrideConfig.ballotLetterColors,
        partyOverrides: overrides,
        excludedPartyColumns,
        validatePartyTotals: true,
      })
      const nationalPayload = buildNationalResultsPayload({
        electionId: election.id,
        electionRule: electionRulesByElection.get(election.id),
        mandateRows: electionMandatesByElection.get(election.id),
        partyRegistry,
        partyColorsByBallotLetter: partyOverrideConfig.ballotLetterColors,
        partyOverrides: overrides,
        excludedPartyColumns,
      })
      const searchPayload = buildGeographySearchIndex({
        electionId: election.id,
        modes: [
          {
            geographyMode: 'statistical-area',
            geography: prunedStatisticalAreasByVintage.get(statisticalAreaVintage),
            results: statisticalPayload,
            metadataById: electionStatisticalMetadata,
          },
          {
            geographyMode: 'locality',
            geography: prunedLocalities,
            results: localityPayload,
            metadataById: electionLocalityMetadata,
          },
        ],
      })

      const resultUrls = {
        'statistical-area': `results/${electionSlug}/statistical-areas.json`,
        locality: `results/${electionSlug}/localities.json`,
        national: `results/${electionSlug}/national.json`,
        search: `results/${electionSlug}/search.json`,
      }
      await Promise.all([
        writeJsonAsset(resultUrls['statistical-area'], statisticalPayload),
        writeJsonAsset(resultUrls.locality, localityPayload),
        writeJsonAsset(resultUrls.national, nationalPayload),
        writeJsonAsset(resultUrls.search, searchPayload),
      ])

      catalogElections.push({
        ...election,
        coverageByMode,
        resultUrls,
        geographiesByMode: {
          'statistical-area': statisticalGeographyAsset,
          locality: localityGeographyAsset,
        },
      })
    }

    const sortedAssets = assets.toSorted((left, right) => left.path.localeCompare(right.path))
    const buildHash = createHash('sha256')
    for (const asset of sortedAssets) {
      buildHash.update(asset.path).update('\0').update(asset.sha256)
    }
    const buildId = buildHash.digest('hex').slice(0, 16)
    const currentStatisticalGeographyAsset = statisticalGeographyAssetsByVintage.get(2022)
    if (!currentStatisticalGeographyAsset) {
      throw new Error('Missing current 2022 statistical-area geography asset')
    }
    const catalog = {
      schemaVersion: 5,
      buildId,
      generatedAt: new Date().toISOString(),
      source: {
        statisticalAreaVintages: [...statisticalGeographyAssetsByVintage.keys()].toSorted(),
        localityGeometryVintage: 2022,
      electionRange: { first: electionConfig.at(-1).id, last: electionConfig[0].id },
        assignmentStatus: 'official-crosswalk-first-locality-complete-statistical-areas-partial',
        resultColumnExclusions: Object.entries(partyOverrideConfig.ignoredResultColumns).flatMap(
          ([electionId, columns]) =>
            Object.entries(columns).map(([column, reason]) => ({ electionId, column, reason })),
        ),
      },
      bounds: [
        [geographySummary.bounds_wgs84.min_lon, geographySummary.bounds_wgs84.min_lat],
        [geographySummary.bounds_wgs84.max_lon, geographySummary.bounds_wgs84.max_lat],
      ],
      partyColorPolicy: {
        status: 'partial',
        description: 'Reviewed ballot-letter colors stay constant across elections, election-specific overrides take precedence, and unreviewed letters use deterministic placeholders.',
      },
      geographyModes: [
        {
          id: 'statistical-area',
          label: { en: 'Statistical areas', he: 'אזורים סטטיסטיים' },
          ...currentStatisticalGeographyAsset,
        },
        {
          id: 'locality',
          label: { en: 'Localities', he: 'יישובים' },
          ...localityGeographyAsset,
        },
      ],
      elections: catalogElections,
      assets: sortedAssets,
    }
    await writeJsonAsset('catalog.json', catalog, true)

    await publishDirectory(stagingRoot, outputRoot)

    const totalBytes = assets.reduce((sum, asset) => sum + asset.bytes, 0)
    console.log(`web_data_build=${buildId}`)
    console.log(`elections=${catalogElections.length}`)
    console.log(`assets=${assets.length}`)
    console.log(`bytes=${totalBytes}`)
  } catch (error) {
    await rm(stagingRoot, { force: true, recursive: true })
    throw error
  }
}

async function publishDirectory(stagingRoot, outputRoot) {
  const backupRoot = `${outputRoot}.backup-${process.pid}`
  await rm(backupRoot, { force: true, recursive: true })
  await mkdir(dirname(outputRoot), { recursive: true })

  let previousOutputMoved = false
  try {
    await rename(outputRoot, backupRoot)
    previousOutputMoved = true
  } catch (error) {
    if (error?.code !== 'ENOENT') {
      throw error
    }
  }

  try {
    await rename(stagingRoot, outputRoot)
  } catch (publishError) {
    if (previousOutputMoved) {
      try {
        await rename(backupRoot, outputRoot)
      } catch (rollbackError) {
        throw new AggregateError(
          [publishError, rollbackError],
          'Could not publish the generated data bundle or restore the previous bundle.',
        )
      }
    }
    throw publishError
  }

  if (previousOutputMoved) {
    await rm(backupRoot, { force: true, recursive: true })
  }
}

function parseArguments(args) {
  const options = {}
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index]
    if (argument === '--source' || argument === '--output') {
      const value = args[index + 1]
      if (!value) {
        throw new Error(`${argument} requires a path`)
      }
      options[argument.slice(2)] = value
      index += 1
      continue
    }
    throw new Error(`Unknown argument: ${argument}`)
  }
  return options
}

function resolveOption(value, fallback) {
  if (!value) {
    return fallback
  }
  return isAbsolute(value) ? value : resolve(process.cwd(), value)
}

function assertSafeOutputPath(outputRoot) {
  const generatedRoot = resolve(APP_ROOT, 'public', 'data')
  const relativePath = relative(generatedRoot, outputRoot)
  if (relativePath.startsWith('..') || isAbsolute(relativePath) || relativePath === '') {
    throw new Error(`Output must be a versioned directory inside ${generatedRoot}`)
  }
}

async function readJson(path) {
  const text = await readFile(path, 'utf8')
  try {
    return JSON.parse(text.replace(/^\uFEFF/, ''))
  } catch (error) {
    throw new Error(`Invalid JSON in ${path}: ${error.message}`)
  }
}

function buildBasemapOutsideMask(footprint) {
  const geometry = footprint?.features?.[0]?.geometry
  if (!geometry || !['Polygon', 'MultiPolygon'].includes(geometry.type)) {
    throw new Error('The map-context footprint cannot define the basemap mask')
  }

  const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates
  const outerRings = polygons.map((polygon) => orientRing(polygon[0], false))

  const worldRing = [
    [-180, -85],
    [180, -85],
    [180, 85],
    [-180, 85],
    [-180, -85],
  ]

  return {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        id: 'basemap-outside-mask',
        properties: { maskType: 'outside-map-context' },
        geometry: {
          type: 'Polygon',
          coordinates: [orientRing(worldRing, true), ...outerRings],
        },
      },
    ],
  }
}

function orientRing(ring, counterClockwise) {
  const isCounterClockwise = signedRingArea(ring) > 0
  return isCounterClockwise === counterClockwise ? ring : [...ring].reverse()
}

function signedRingArea(ring) {
  return ring.reduce((area, coordinate, index) => {
    const next = ring[(index + 1) % ring.length]
    return area + coordinate[0] * next[1] - next[0] * coordinate[1]
  }, 0) / 2
}

async function readCsv(path) {
  return parseCsv(await readFile(path, 'utf8'), path)
}

function buildLocalityDisplayOverrideIndex(rows, elections, localityMetadata) {
  const configuredElections = new Set(elections.map((election) => election.id))
  const byElection = new Map(elections.map((election) => [election.id, new Map()]))

  for (const row of rows) {
    const localityId = String(row.locality_id ?? '').trim()
    const electionIds = String(row.elections ?? '')
      .split('|')
      .map((value) => value.trim())
      .filter(Boolean)
    const visibility = String(row.visibility ?? '').trim() || 'default'
    const nameHe = String(row.name_he ?? '').trim()
    const nameEn = String(row.name_en ?? '').trim()
    const note = String(row.note ?? '').trim()

    if (!localityMetadata.has(localityId)) {
      throw new Error(`Unknown locality display override: ${localityId || '(blank ID)'}`)
    }
    if (electionIds.length === 0 || electionIds.some((id) => !configuredElections.has(id))) {
      throw new Error(`${localityId} has invalid display-override elections`)
    }
    if (!['default', 'hidden'].includes(visibility)) {
      throw new Error(`${localityId} has invalid display visibility: ${visibility}`)
    }

    for (const electionId of electionIds) {
      const electionOverrides = byElection.get(electionId)
      if (electionOverrides.has(localityId)) {
        throw new Error(`Duplicate locality display override: ${electionId}.${localityId}`)
      }
      electionOverrides.set(localityId, { visibility, nameHe, nameEn, note })
    }
  }

  return byElection
}

function buildStatisticalAreaDisplayOverrideIndex(rows, elections, metadataByVintage) {
  const electionById = new Map(elections.map((election) => [election.id, election]))
  const byElection = new Map(elections.map((election) => [election.id, new Map()]))

  for (const row of rows) {
    const statAreaId = String(row.stat_area_id ?? '').trim()
    const electionIds = String(row.elections ?? '')
      .split('|')
      .map((value) => value.trim())
      .filter(Boolean)
    const visibility = String(row.visibility ?? '').trim()
    const nameHe = String(row.name_he ?? '').trim()
    const nameEn = String(row.name_en ?? '').trim()
    const note = String(row.note ?? '').trim()
    const noticeHe = String(row.notice_he ?? '').trim()
    const noticeEn = String(row.notice_en ?? '').trim()
    const notice =
      noticeHe || noticeEn
        ? {
            he: noticeHe || noticeEn,
            en: noticeEn || noticeHe,
          }
        : undefined

    if (
      !statAreaId ||
      !['default', 'hidden'].includes(visibility) ||
      electionIds.length === 0 ||
      (visibility === 'default' && !nameHe && !nameEn && !notice)
    ) {
      throw new Error(`Invalid statistical-area display override: ${statAreaId || '(blank ID)'}`)
    }
    for (const electionId of electionIds) {
      const election = electionById.get(electionId)
      if (!election) {
        throw new Error(`${statAreaId} has an unknown display-override election: ${electionId}`)
      }
      const metadata = metadataByVintage.get(Number(election.statisticalAreaVintage))
      if (!metadata?.has(statAreaId)) {
        throw new Error(`${electionId} display override references unavailable area ${statAreaId}`)
      }
      const electionOverrides = byElection.get(electionId)
      if (electionOverrides.has(statAreaId)) {
        throw new Error(`Duplicate statistical-area display override: ${electionId}.${statAreaId}`)
      }
      electionOverrides.set(statAreaId, {
        visibility,
        nameHe,
        nameEn,
        note,
        notice,
      })
    }
  }

  return byElection
}

function buildStatisticalAreaDisplayGroupIndex(
  rows,
  elections,
  metadataByVintage,
  customMetadata,
) {
  const electionById = new Map(elections.map((election) => [election.id, election]))
  const groupsByElection = new Map(
    elections.map((election) => [election.id, new Map()]),
  )
  const componentOwnersByElection = new Map(
    elections.map((election) => [election.id, new Map()]),
  )

  for (const row of rows) {
    const displayGeographyId = String(row.display_geography_id ?? '').trim()
    const componentStatAreaIds = [
      ...String(row.component_stat_area_ids ?? '')
        .split('|')
        .map((value) => value.trim())
        .filter(Boolean),
      ...String(row.component_stat_area_id ?? '')
        .split('|')
        .map((value) => value.trim())
        .filter(Boolean),
    ]
    const electionIds = String(row.elections ?? '')
      .split('|')
      .map((value) => value.trim())
      .filter(Boolean)
    const note = String(row.note ?? '').trim()
    const aggregationMethod = String(
      row.aggregation_method ?? 'validated-locality-aggregate',
    ).trim()

    if (!customMetadata.has(displayGeographyId)) {
      throw new Error(
        `Unknown statistical display-group target: ${displayGeographyId || '(blank ID)'}`,
      )
    }
    if (componentStatAreaIds.length === 0 || electionIds.length === 0) {
      throw new Error(`Invalid statistical display-group component: ${displayGeographyId}`)
    }

    for (const electionId of electionIds) {
      const election = electionById.get(electionId)
      if (!election) {
        throw new Error(
          `${displayGeographyId} has an unknown display-group election: ${electionId}`,
        )
      }
      const electionGroups = groupsByElection.get(electionId)
      const group = electionGroups.get(displayGeographyId) ?? {
        displayGeographyId,
        componentIds: [],
        aggregationMethod,
        note,
      }
      if (group.aggregationMethod !== aggregationMethod) {
        throw new Error(
          `${electionId} display group ${displayGeographyId} mixes aggregation methods`,
        )
      }
      const metadata = metadataByVintage.get(Number(election.statisticalAreaVintage))
      const componentOwners = componentOwnersByElection.get(electionId)
      for (const componentStatAreaId of componentStatAreaIds) {
        if (!metadata?.has(componentStatAreaId)) {
          throw new Error(
            `${electionId} display group references unavailable area ${componentStatAreaId}`,
          )
        }
        const existingOwner = componentOwners.get(componentStatAreaId)
        if (existingOwner) {
          throw new Error(
            `${electionId} display component ${componentStatAreaId} is already assigned to ${existingOwner}`,
          )
        }
        componentOwners.set(componentStatAreaId, displayGeographyId)
        group.componentIds.push(componentStatAreaId)
      }
      electionGroups.set(displayGeographyId, group)
    }
  }

  return new Map(
    [...groupsByElection].map(([electionId, groups]) => [
      electionId,
      [...groups.values()]
        .map((group) => ({ ...group, componentIds: group.componentIds.toSorted() }))
        .toSorted((left, right) =>
          left.displayGeographyId.localeCompare(right.displayGeographyId),
        ),
    ]),
  )
}

function mergeFeatureCollections(...collections) {
  const features = []
  for (const collection of collections) {
    if (collection?.type !== 'FeatureCollection' || !Array.isArray(collection.features)) {
      throw new Error('Cannot merge an invalid GeoJSON feature collection')
    }
    features.push(...collection.features)
  }
  return { type: 'FeatureCollection', features }
}

function filterStatisticalCustomGeographiesByVintage(collection, vintage) {
  const prefix = `stat${vintage}:`
  return {
    type: 'FeatureCollection',
    features: collection.features.filter((feature) => {
      const componentIds = String(
        feature.properties?.component_stat_area_ids ?? '',
      )
        .split('|')
        .map((value) => value.trim())
        .filter(Boolean)
      return componentIds.length === 0 || componentIds.every((id) => id.startsWith(prefix))
    }),
  }
}

function filterFallbackGeographiesByVintage(collection, vintage) {
  return {
    type: 'FeatureCollection',
    features: collection.features.filter(
      (feature) => Number(feature.properties?.stat_area_vintage) === vintage,
    ),
  }
}

function applyMetadataNameOverrides(metadataById, overrides) {
  const output = new Map(metadataById)
  for (const [id, override] of overrides) {
    if (!override.nameHe && !override.nameEn && !override.notice) {
      continue
    }
    const metadata = output.get(id)
    output.set(id, {
      ...metadata,
      nameHe: override.nameHe || metadata?.nameHe,
      nameEn: override.nameEn || metadata?.nameEn,
      notice: override.notice ?? metadata?.notice,
    })
  }
  return output
}

const PENDING_AGGREGATE_NOTICE = {
  he: 'לא ניתן לשייך את מלוא תוצאות האזור במדויק. ייתכן שחלק מקולותיו מוצגים באזור אחר או שהתוצאה כוללת קולות מאזורים אחרים.',
  en: 'The complete result for this area cannot be assigned precisely. Some of its votes may be shown elsewhere, or this result may include votes from other areas.',
}

function applyPendingAggregateNotices(metadataById, evidenceRows, electionId) {
  const output = new Map(metadataById)
  for (const row of evidenceRows) {
    if (
      String(row.election ?? '').trim() !== electionId ||
      !(
        String(row.evidence_class ?? '').trim() === 'cannot_show_separately_pending_aggregate_review' ||
        (electionId === 'K26' && String(row.evidence_class ?? '').trim() === 'incomplete_source_coverage')
      )
    ) {
      continue
    }

    const statAreaId = String(row.stat_area_id ?? '').trim()
    const metadata = output.get(statAreaId)
    if (!metadata) {
      throw new Error(`${electionId} pending aggregate references unavailable area ${statAreaId}`)
    }
    output.set(statAreaId, {
      ...metadata,
      notice: metadata.notice ?? PENDING_AGGREGATE_NOTICE,
    })
  }
  return output
}

function validateConfiguration(elections, partyOverrides) {
  if (!Array.isArray(elections) || elections.length === 0) {
    throw new Error('Election configuration must be a non-empty array')
  }
  const ids = new Set()
  for (const election of elections) {
    if (
      !election.id ||
      !election.number ||
      !election.label?.en ||
      !election.label?.he ||
      ![1995, 2008, 2011, 2022].includes(Number(election.statisticalAreaVintage))
    ) {
      throw new Error(
        'Every election needs an ID, number, statistical-area vintage, and English/Hebrew labels',
      )
    }
    if (ids.has(election.id)) {
      throw new Error(`Duplicate election ID: ${election.id}`)
    }
    ids.add(election.id)
  }
  if (
    partyOverrides?.schemaVersion !== 2 ||
    !partyOverrides.ballotLetterColors ||
    typeof partyOverrides.ballotLetterColors !== 'object' ||
    !partyOverrides.elections ||
    typeof partyOverrides.elections !== 'object' ||
    !partyOverrides.ignoredResultColumns ||
    typeof partyOverrides.ignoredResultColumns !== 'object'
  ) {
    throw new Error(
      'party-overrides.json must use schemaVersion 2 and contain ballotLetterColors, elections, and ignoredResultColumns objects',
    )
  }

  for (const [ballotLetter, color] of Object.entries(partyOverrides.ballotLetterColors)) {
    assertHexColor(color, `ballotLetterColors.${ballotLetter}`)
  }
  for (const [electionId, overrides] of Object.entries(partyOverrides.elections)) {
    if (!ids.has(electionId) || !overrides || typeof overrides !== 'object') {
      throw new Error(`Invalid party override election: ${electionId}`)
    }
    for (const [partyId, override] of Object.entries(overrides)) {
      if (!override || typeof override !== 'object') {
        throw new Error(`${electionId}.${partyId} must be an override object`)
      }
      if (override.color) {
        assertHexColor(override.color, `elections.${electionId}.${partyId}.color`)
      }
      for (const field of ['nameHe', 'nameEn']) {
        if (override[field] !== undefined && (typeof override[field] !== 'string' || !override[field].trim())) {
          throw new Error(`elections.${electionId}.${partyId}.${field} must be a non-empty string`)
        }
      }
    }
  }
}

function assertHexColor(color, fieldName) {
  if (typeof color !== 'string' || !/^#[0-9a-f]{6}$/i.test(color)) {
    throw new Error(`${fieldName} must be a six-digit hex color`)
  }
}

function validatePartyRegistryElections(elections, partyRegistryByElection) {
  const configuredIds = new Set(elections.map((election) => election.id))
  const missing = elections
    .map((election) => election.id)
    .filter((electionId) => !partyRegistryByElection.has(electionId))
  const extra = [...partyRegistryByElection.keys()].filter(
    (electionId) => !configuredIds.has(electionId),
  )
  if (missing.length > 0 || extra.length > 0) {
    throw new Error(
      `Party registry election coverage is invalid; missing: ${missing.join(', ') || '(none)'}; ` +
        `extra: ${extra.join(', ') || '(none)'}`,
    )
  }
}

function uniqueRowsByElection(rows, sourceName) {
  const byElection = new Map()
  for (const row of rows) {
    const electionId = String(row.election ?? '').trim()
    if (!/^K\d+$/.test(electionId)) {
      throw new Error(`${sourceName} contains an invalid election ID: ${electionId || '(blank)'}`)
    }
    if (byElection.has(electionId)) {
      throw new Error(`${sourceName} repeats election ${electionId}`)
    }
    byElection.set(electionId, row)
  }
  return byElection
}

function groupRowsByElection(rows, sourceName) {
  const byElection = new Map()
  for (const row of rows) {
    const electionId = String(row.election ?? '').trim()
    if (!/^K\d+$/.test(electionId)) {
      throw new Error(`${sourceName} contains an invalid election ID: ${electionId || '(blank)'}`)
    }
    const electionRows = byElection.get(electionId) ?? []
    electionRows.push(row)
    byElection.set(electionId, electionRows)
  }
  return byElection
}

function validateNationalResultElections(elections, rulesByElection, mandatesByElection) {
  const configuredIds = new Set(elections.map((election) => election.id))
  for (const electionId of configuredIds) {
    if (!rulesByElection.has(electionId) || !mandatesByElection.has(electionId)) {
      throw new Error(`${electionId} is missing national-result rules or mandates`)
    }
  }
  for (const electionId of new Set([
    ...rulesByElection.keys(),
    ...mandatesByElection.keys(),
  ])) {
    if (!configuredIds.has(electionId)) {
      throw new Error(`National-result sources contain unknown election ${electionId}`)
    }
  }
}

await main()
