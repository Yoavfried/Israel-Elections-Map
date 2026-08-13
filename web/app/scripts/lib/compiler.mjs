import Papa from 'papaparse'

const RESULT_CORE_LAST_COLUMN = 'winning_vote_share'
const ADDITIVE_RESULT_COLUMNS = [
  'contributing_rows',
  'contributing_kalpis',
  'eligible_voters',
  'actual_voters',
  'valid_votes',
  'invalid_votes',
]
const DEFAULT_PARTY_SATURATION = 58
const DEFAULT_PARTY_LIGHTNESS = 46
const POINT_PROXY_MAX_VERTICES = 12
const SPECIAL_POINT_PROXY_LOCALITY_CODES = new Set(['1791', '1792', '1793', '1794', '3488'])
const MUNICIPALITY_FALLBACK_NOTICE = {
  he: 'אין נתוני שיוך של קלפיות לאזורים סטטיסטיים ביישוב זה בבחירות האלה. מוצגת תוצאת היישוב כולו כאזור אחד.',
  en: 'No ballot-to-statistical-area assignments are available for this locality in this election. The whole-locality result is shown as one area.',
}
const HISTORICAL_GEOMETRY_PROXY_NOTICE = {
  he: 'היישוב אינו מופיע כאזור נפרד במפת האזורים הסטטיסטיים ההיסטורית. תוצאת היישוב מוצגת על גבול יישוב עדכני.',
  en: 'This locality does not appear as a separate area in the historical statistical-area map. Its result is shown on a current locality boundary.',
}
const SINGLE_AREA_FALLBACK_NOTICE = {
  he: 'היישוב מופיע כאזור סטטיסטי היסטורי יחיד, אך אין שיוך ישיר של הקלפי אליו. תוצאת היישוב מוצגת כיחידה אחת.',
  en: 'The locality has one historical statistical area, but the ballot is not directly assigned to it. The whole-locality result is shown as one unit.',
}

export function parseCsv(text, sourceName = 'CSV input') {
  const parsed = Papa.parse(text, {
    header: true,
    skipEmptyLines: 'greedy',
    transformHeader: (header) => header.replace(/^\uFEFF/, '').trim(),
  })

  if (parsed.errors.length > 0) {
    const message = parsed.errors
      .slice(0, 5)
      .map((error) => `row ${error.row ?? '?'}: ${error.message}`)
      .join('; ')
    throw new Error(`${sourceName} could not be parsed: ${message}`)
  }

  return parsed.data
}

export function numberValue(value, fieldName = 'value') {
  if (value === '' || value === null || value === undefined) {
    return 0
  }

  const parsed = Number(String(value).replaceAll(',', '').trim())
  if (!Number.isFinite(parsed)) {
    throw new Error(`Expected a number for ${fieldName}, received ${JSON.stringify(value)}`)
  }
  return parsed
}

export function buildPartyRegistryIndex(rows) {
  const byElection = new Map()

  for (const row of rows) {
    const electionId = String(row.election ?? '').trim()
    const sourceColumn = String(row.source_column ?? '').trim()
    const ballotLetter = String(row.ballot_letter ?? '').trim()
    const listNameHe = String(row.list_name_he ?? '').trim()
    const displayNameHe = String(row.display_name_he ?? '').trim() || listNameHe
    const displayNameEn = String(row.display_name_en ?? '').trim()
    const wikipediaHeUrl = optionalHttpsUrl(
      row.wikipedia_he_url,
      `${electionId}.${sourceColumn}.wikipedia_he_url`,
    )
    const wikipediaEnUrl = optionalHttpsUrl(
      row.wikipedia_en_url,
      `${electionId}.${sourceColumn}.wikipedia_en_url`,
    )
    const totalVotes = numberValue(
      row.total_votes,
      `${electionId}.${sourceColumn}.total_votes`,
    )

    if (!/^K\d+$/.test(electionId) || !sourceColumn || !ballotLetter || !listNameHe) {
      throw new Error(
        'Every party-registry row needs an election, source column, ballot letter, and Hebrew list name',
      )
    }
    if (!Number.isInteger(totalVotes) || totalVotes < 0) {
      throw new Error(`${electionId}.${sourceColumn}.total_votes must be a nonnegative integer`)
    }
    if (totalVotes > 0 && (!displayNameEn || /[\u0590-\u05ff]/u.test(displayNameEn))) {
      throw new Error(
        `${electionId}.${sourceColumn}.display_name_en must be a reviewed English name`,
      )
    }

    let election = byElection.get(electionId)
    if (!election) {
      election = new Map()
      byElection.set(electionId, election)
    }
    if (election.has(sourceColumn)) {
      throw new Error(`Duplicate party-registry key: ${electionId}.${sourceColumn}`)
    }
    election.set(sourceColumn, {
      electionId,
      sourceColumn,
      ballotLetter,
      totalVotes,
      listNameHe,
      displayNameHe,
      displayNameEn,
      wikipediaHeUrl,
      wikipediaEnUrl,
    })
  }

  return byElection
}

export function buildNationalResultsPayload({
  electionId,
  electionRule,
  mandateRows,
  partyRegistry,
  partyColorsByBallotLetter = {},
  partyOverrides = {},
  excludedPartyColumns = [],
}) {
  if (!(partyRegistry instanceof Map) || partyRegistry.size === 0) {
    throw new Error(`${electionId} is missing its party-registry map`)
  }
  const excludedColumns = new Set(excludedPartyColumns)
  const registryEntries = [...partyRegistry.entries()]
  const invalidExclusions = registryEntries.filter(
    ([partyId, party]) => excludedColumns.has(partyId) && party.totalVotes !== 0,
  )
  if (invalidExclusions.length > 0) {
    throw new Error(
      `${electionId} cannot exclude nonzero parties: ${invalidExclusions
        .map(([partyId]) => partyId)
        .join(', ')}`,
    )
  }
  const undeclaredZeroVoteParties = registryEntries.filter(
    ([partyId, party]) => party.totalVotes === 0 && !excludedColumns.has(partyId),
  )
  if (undeclaredZeroVoteParties.length > 0) {
    throw new Error(
      `${electionId} zero-vote parties must be declared as result-column exclusions: ${undeclaredZeroVoteParties
        .map(([partyId]) => partyId)
        .join(', ')}`,
    )
  }
  const activePartyEntries = registryEntries.filter(
    ([partyId]) => !excludedColumns.has(partyId),
  )

  const thresholdShare = numberValue(
    electionRule?.electoral_threshold_share,
    `${electionId}.electoral_threshold_share`,
  )
  const totalMandates = numberValue(
    electionRule?.total_mandates,
    `${electionId}.total_mandates`,
  )
  const officialResultsUrl = optionalHttpsUrl(
    electionRule?.official_results_url,
    `${electionId}.official_results_url`,
  )
  const thresholdSourceUrl = optionalHttpsUrl(
    electionRule?.threshold_source_url,
    `${electionId}.threshold_source_url`,
  )

  if (thresholdShare <= 0 || thresholdShare >= 1) {
    throw new Error(`${electionId}.electoral_threshold_share must be between zero and one`)
  }
  if (!Number.isInteger(totalMandates) || totalMandates <= 0) {
    throw new Error(`${electionId}.total_mandates must be a positive integer`)
  }

  const mandatesByParty = new Map()
  for (const row of mandateRows) {
    const partyId = String(row.source_column ?? '').trim()
    const mandates = numberValue(row.mandates, `${electionId}.${partyId}.mandates`)
    if (!partyRegistry.has(partyId)) {
      throw new Error(`${electionId} mandate allocation references unknown party ${partyId}`)
    }
    if (excludedColumns.has(partyId)) {
      throw new Error(`${electionId} mandate allocation references excluded party ${partyId}`)
    }
    if (!Number.isInteger(mandates) || mandates <= 0) {
      throw new Error(`${electionId}.${partyId}.mandates must be a positive integer`)
    }
    if (mandatesByParty.has(partyId)) {
      throw new Error(`${electionId} mandate allocation repeats party ${partyId}`)
    }
    mandatesByParty.set(partyId, mandates)
  }

  const allocatedMandates = [...mandatesByParty.values()].reduce(
    (total, mandates) => total + mandates,
    0,
  )
  if (allocatedMandates !== totalMandates) {
    throw new Error(
      `${electionId} mandate allocation sums to ${allocatedMandates}, expected ${totalMandates}`,
    )
  }

  const totalValidVotes = activePartyEntries.reduce(
    (total, [, party]) => total + party.totalVotes,
    0,
  )
  if (!Number.isInteger(totalValidVotes) || totalValidVotes <= 0) {
    throw new Error(`${electionId} national valid-vote total must be positive`)
  }
  const thresholdVotes = Math.ceil(totalValidVotes * thresholdShare)

  const parties = activePartyEntries
    .map(([partyId, registryEntry]) => {
      const mandates = mandatesByParty.get(partyId) ?? 0
      const passedThreshold = registryEntry.totalVotes >= thresholdVotes
      if ((mandates > 0) !== passedThreshold) {
        throw new Error(
          `${electionId}.${partyId} threshold status and mandate allocation disagree`,
        )
      }
      return {
        ...buildPartyDefinition(
          partyId,
          registryEntry,
          partyOverrides[partyId],
          partyColorsByBallotLetter,
        ),
        votes: registryEntry.totalVotes,
        voteShare: registryEntry.totalVotes / totalValidVotes,
        mandates,
        passedThreshold,
      }
    })
    .toSorted(
      (left, right) =>
        right.votes - left.votes ||
        left.ballotLetter.localeCompare(right.ballotLetter, 'he-IL'),
    )

  const representedVotes = parties
    .filter((party) => party.passedThreshold)
    .reduce((total, party) => total + party.votes, 0)

  return {
    schemaVersion: 1,
    electionId,
    threshold: {
      share: thresholdShare,
      votes: thresholdVotes,
    },
    totals: {
      validVotes: totalValidVotes,
      representedVotes,
      representedVoteShare: representedVotes / totalValidVotes,
      mandates: totalMandates,
      contestingParties: parties.length,
      representedParties: parties.filter((party) => party.passedThreshold).length,
    },
    sources: {
      officialResultsUrl,
      thresholdSourceUrl,
    },
    parties,
  }
}

export function cleanNumericCode(value) {
  return String(value ?? '').trim().replace(/\.0+$/, '')
}

export function isWestBankSettlementCode(value) {
  const code = Number(cleanNumericCode(value))
  return Number.isInteger(code) && code >= 3500 && code < 4000
}

export function isPointProxyLocalityCode(value) {
  const code = cleanNumericCode(value)
  return SPECIAL_POINT_PROXY_LOCALITY_CODES.has(code) || isWestBankSettlementCode(code)
}

export function isPointLikeGeometry(geometry) {
  return coordinatePositionCount(geometry?.coordinates) <= POINT_PROXY_MAX_VERTICES
}

export function buildMetadataIndex(rows, mode) {
  const index = new Map()
  for (const row of rows) {
    const id = mode === 'statistical-area' ? row.stat_area_id : row.locality_id
    if (!id) {
      throw new Error(`Missing ${mode} ID in geography metadata`)
    }
    const statAreaNumber = cleanNumericCode(row.stat_area_number || row.stat_2022)
    const yishuvStat = cleanNumericCode(
      row.yishuv_stat || row.stat_area_yishuv_stat || row.yishuv_stat_2022,
    )
    index.set(id, {
      id,
      localityId: row.locality_id,
      localityCode: cleanNumericCode(row.locality_code),
      nameHe: row.locality_name_he || '',
      nameEn: row.locality_name_en || row.locality_name_he || '',
      statAreaNumber,
      yishuvStat,
      yishuvStat2022: cleanNumericCode(row.yishuv_stat_2022) || yishuvStat,
      statAreaVintage: numberValue(row.stat_area_vintage || (mode === 'statistical-area' ? 2022 : 0)),
    })
  }
  return index
}

export function buildCustomMetadataIndex(featureCollection) {
  assertFeatureCollection(featureCollection, 'custom geography')
  const index = new Map()
  for (const feature of featureCollection.features) {
    const properties = feature.properties ?? {}
    const id = properties.custom_id
    if (!id) {
      throw new Error('Custom geography feature is missing custom_id')
    }
    if (index.has(id)) {
      throw new Error(`Custom geography contains duplicate ID: ${id}`)
    }
    const noticeHe = String(properties.notice_he ?? '').trim()
    const noticeEn = String(properties.notice_en ?? '').trim()
    const nameHe = properties.name_he || id
    const nameEn = properties.name_en || properties.name_he || id
    const includedNames = {
      he: splitPipeValues(properties.component_locality_names_he).filter(
        (name) => name !== nameHe,
      ),
      en: splitPipeValues(properties.component_locality_names_en).filter(
        (name) => name !== nameEn,
      ),
    }
    if ((noticeHe && !noticeEn) || (!noticeHe && noticeEn)) {
      throw new Error(`${id} must provide both Hebrew and English notices`)
    }
    index.set(id, {
      id,
      customKey: properties.custom_key || id,
      nameHe,
      nameEn,
      includedNames,
      note: properties.note || '',
      ...(noticeHe && noticeEn ? { notice: { he: noticeHe, en: noticeEn } } : {}),
    })
  }
  return index
}

export function buildCompositeMetadataIndex(featureCollection) {
  assertFeatureCollection(featureCollection, 'composite locality')
  const index = new Map()
  for (const feature of featureCollection.features) {
    const properties = feature.properties ?? {}
    const id = properties.composite_locality_id
    if (!id) {
      throw new Error('Composite locality feature is missing composite_locality_id')
    }
    index.set(id, {
      id,
      localityId: id,
      localityCode: cleanNumericCode(properties.host_locality_code),
      nameHe: properties.name_he || id,
      nameEn: properties.name_en || properties.name_he || id,
      includedNames: {
        he: splitPipeValues(properties.included_locality_names_he),
        en: splitPipeValues(properties.included_locality_names_en),
      },
      statAreaNumber: '',
      yishuvStat2022: '',
      isComposite: true,
    })
  }
  return index
}

export function pruneGeography(
  featureCollection,
  mode,
  customFeatureCollection,
  compositeFeatureCollection = { type: 'FeatureCollection', features: [] },
) {
  assertFeatureCollection(featureCollection, mode)
  assertFeatureCollection(customFeatureCollection, 'custom geography')
  assertFeatureCollection(compositeFeatureCollection, 'composite locality')

  const features = featureCollection.features.map((feature) => {
    const properties = feature.properties ?? {}
    const id = mode === 'statistical-area' ? properties.stat_area_id : properties.locality_id
    if (!id) {
      throw new Error(`${mode} feature is missing its stable ID`)
    }

    const statAreaNumber = cleanNumericCode(
      properties.stat_area_number ?? properties.stat_2022,
    )
    const hasDetailedDisplayGeometry = String(
      properties.display_geometry_source ?? '',
    ).startsWith('arcgis_')
    const requestedDisplayMode = String(properties.display_mode ?? '').trim()
    if (requestedDisplayMode && !['polygon', 'marker'].includes(requestedDisplayMode)) {
      throw new Error(`${id} has invalid display mode: ${requestedDisplayMode}`)
    }
    const displayMode = requestedDisplayMode ||
      (isPointProxyLocalityCode(properties.locality_code) &&
      !hasDetailedDisplayGeometry &&
      isPointLikeGeometry(feature.geometry)
        ? 'marker'
        : 'polygon')
    return {
      type: 'Feature',
      id,
      properties: {
        id,
        geographyType: mode,
        localityId: properties.locality_id,
        localityCode: cleanNumericCode(properties.locality_code),
        nameHe: properties.locality_name_he || '',
        nameEn: properties.locality_name_en || properties.locality_name_he || '',
        displayMode,
        isComposite: false,
        ...(mode === 'statistical-area' ? { statAreaNumber } : {}),
        ...(mode === 'statistical-area'
          ? { statAreaVintage: numberValue(properties.stat_area_vintage ?? 2022) }
          : {}),
      },
      geometry: roundGeometry(feature.geometry),
    }
  })

  if (mode === 'locality') {
    const markerLocalityCodes = new Set(
      features
        .filter((feature) => feature.properties.displayMode === 'marker')
        .map((feature) => feature.properties.localityCode),
    )
    for (const feature of compositeFeatureCollection.features) {
      const properties = feature.properties ?? {}
      const id = properties.composite_locality_id
      if (!id) {
        throw new Error('Composite locality feature is missing composite_locality_id')
      }
      const componentCodes = splitPipeValues(properties.component_locality_codes)
      const inferredDisplayMode =
        componentCodes.length > 0 &&
        componentCodes.every((code) => markerLocalityCodes.has(cleanNumericCode(code)))
          ? 'marker'
          : 'polygon'
      const displayMode = properties.display_mode || inferredDisplayMode
      if (!['polygon', 'marker'].includes(displayMode)) {
        throw new Error(`${id} has invalid composite display mode: ${displayMode}`)
      }
      const hostLocalityCode = cleanNumericCode(properties.host_locality_code)
      features.push({
        type: 'Feature',
        id,
        properties: {
          id,
          geographyType: 'locality',
          localityId: id,
          localityCode: hostLocalityCode,
          nameHe: properties.name_he || id,
          nameEn: properties.name_en || properties.name_he || id,
          displayMode,
          isComposite: true,
          compositeKind: properties.composite_kind || 'historical_municipality',
          activeElections: splitPipeValues(properties.elections),
          componentLocalityIds: splitPipeValues(properties.component_locality_ids),
          hostLocalityId: hostLocalityCode ? `loc:${hostLocalityCode}` : null,
          includedNames: {
            he: splitPipeValues(properties.included_locality_names_he),
            en: splitPipeValues(properties.included_locality_names_en),
          },
          evidenceStatus: properties.evidence_status || '',
          evidenceMethod: properties.evidence_method || '',
        },
        geometry: roundGeometry(feature.geometry),
      })
    }
  }

  for (const feature of customFeatureCollection.features) {
    const properties = feature.properties ?? {}
    const id = properties.custom_id
    if (!id) {
      throw new Error('Custom geography feature is missing custom_id')
    }
    const displayMode = String(properties.display_mode || 'marker').trim()
    if (!['polygon', 'marker'].includes(displayMode)) {
      throw new Error(`${id} has invalid custom display mode: ${displayMode}`)
    }
    features.push({
      type: 'Feature',
      id,
      properties: {
        id,
        geographyType: 'custom',
        customKey: properties.custom_key || id,
        nameHe: properties.name_he || id,
        nameEn: properties.name_en || properties.name_he || id,
        displayMode,
      },
      geometry: roundGeometry(feature.geometry),
    })
  }

  return {
    type: 'FeatureCollection',
    features,
  }
}

export function buildMunicipalityFallbackDisplay({
  electionId,
  vintage,
  fallbackRows,
  localityGeography,
  statisticalGeography,
  componentFallbackGeography = { type: 'FeatureCollection', features: [] },
  localityFallbackGeography = { type: 'FeatureCollection', features: [] },
}) {
  assertFeatureCollection(localityGeography, 'municipality fallback locality geography')
  assertFeatureCollection(statisticalGeography, 'municipality fallback statistical geography')
  assertFeatureCollection(componentFallbackGeography, 'historical component fallback geography')
  assertFeatureCollection(localityFallbackGeography, 'historical locality fallback geography')

  const localityFeaturesById = new Map(
    localityGeography.features.map((feature) => [feature.properties?.localityId || feature.id, feature]),
  )
  const statisticalFeatures = statisticalGeography.features.filter(
    (feature) => feature.properties?.geographyType === 'statistical-area',
  )
  const componentFallbackFeaturesById = new Map()
  for (const feature of componentFallbackGeography.features) {
    const id = String(feature.properties?.fallback_geography_id ?? feature.id ?? '').trim()
    if (!id || !feature.geometry) {
      throw new Error('Historical component fallback feature is missing its ID or geometry')
    }
    if (componentFallbackFeaturesById.has(id)) {
      throw new Error(`Duplicate historical component fallback geometry: ${id}`)
    }
    componentFallbackFeaturesById.set(id, feature)
  }
  const localityFallbackFeaturesById = new Map()
  for (const feature of localityFallbackGeography.features) {
    const id = String(feature.properties?.fallback_geography_id ?? feature.id ?? '').trim()
    if (!id || !feature.geometry) {
      throw new Error('Historical locality fallback feature is missing its ID or geometry')
    }
    if (
      !id.startsWith(`municipality-fallback:${vintage}:`) ||
      numberValue(feature.properties?.stat_area_vintage, `${id}.stat_area_vintage`) !== vintage
    ) {
      throw new Error(`Historical locality fallback geometry has the wrong vintage: ${id}`)
    }
    if (localityFallbackFeaturesById.has(id)) {
      throw new Error(`Duplicate historical locality fallback geometry: ${id}`)
    }
    localityFallbackFeaturesById.set(id, feature)
  }
  const seenFallbackIds = new Set()
  const displayRows = []
  const features = []
  const metadataById = new Map()
  const hiddenGeographyIds = new Set()

  for (const row of fallbackRows) {
    const id = String(row.fallback_geography_id ?? '').trim()
    const localityId = String(row.locality_id ?? '').trim()
    const rowElection = String(row.election ?? '').trim()
    const rowVintage = numberValue(row.stat_area_vintage, `${id}.stat_area_vintage`)
    if (!id || !localityId || rowElection !== electionId || rowVintage !== vintage) {
      throw new Error(`${electionId} has an invalid municipality display fallback: ${id || '(blank ID)'}`)
    }
    if (seenFallbackIds.has(id)) {
      throw new Error(`${electionId} has a duplicate municipality display fallback: ${id}`)
    }
    seenFallbackIds.add(id)

    const localityFeature = localityFeaturesById.get(localityId)
    if (!localityFeature) {
      throw new Error(`${electionId} municipality display fallback lacks geometry: ${localityId}`)
    }
    const isComponentFallback = id.startsWith('municipality-component-fallback:')
    const componentFallbackFeature = componentFallbackFeaturesById.get(id)
    const localityFallbackFeature = localityFallbackFeaturesById.get(id)
    if (isComponentFallback && !componentFallbackFeature) {
      throw new Error(`${electionId} component display fallback lacks reviewed geometry: ${id}`)
    }
    const localityProperties = localityFeature.properties ?? {}
    const componentLocalityIds = localityProperties.isComposite
      ? localityProperties.componentLocalityIds ?? []
      : [localityId]
    const componentIdSet = new Set(componentLocalityIds)
    const matchingStatisticalFeatures = statisticalFeatures.filter((feature) =>
      componentIdSet.has(feature.properties?.localityId),
    )
    for (const feature of matchingStatisticalFeatures) {
      hiddenGeographyIds.add(feature.id)
    }

    const notice = isComponentFallback
      ? MUNICIPALITY_FALLBACK_NOTICE
      : matchingStatisticalFeatures.length === 0
        ? HISTORICAL_GEOMETRY_PROXY_NOTICE
        : matchingStatisticalFeatures.length === 1
          ? undefined
          : MUNICIPALITY_FALLBACK_NOTICE
    const fallbackNoticeType = isComponentFallback
      ? 'multi-area-unsplit'
      : matchingStatisticalFeatures.length === 0
        ? 'historical-geometry-proxy'
        : matchingStatisticalFeatures.length === 1
          ? 'single-historical-area-exact'
          : 'multi-area-unsplit'

    const nameHe = String(row.locality_name || localityProperties.nameHe || localityId).trim()
    const nameEn = String(localityProperties.nameEn || nameHe).trim()
    const localityCode = cleanNumericCode(row.locality_code || localityProperties.localityCode)
    const includedNames = localityProperties.includedNames
    const boundarySource = String(
      localityFallbackFeature?.properties?.boundary_source ?? row.boundary_source ?? '',
    ).trim()
    metadataById.set(id, {
      id,
      geographyType: 'municipality-fallback',
      localityId,
      localityCode,
      customKey: localityCode || id,
      nameHe,
      nameEn,
      includedNames,
      ...(notice ? { notice } : {}),
      fallbackNoticeType,
    })
    displayRows.push({
      ...row,
      custom_geography_id: id,
      geography_id: id,
      geography_mode: 'statistical-area',
    })
    features.push({
      type: 'Feature',
      id,
      properties: {
        ...localityProperties,
        id,
        geographyType: 'municipality-fallback',
        localityId,
        localityCode,
        nameHe,
        nameEn,
        displayMode: 'polygon',
        fallbackReason: String(row.fallback_reason ?? '').trim(),
        fallbackNoticeType,
        boundarySource,
        ...(componentFallbackFeature?.properties?.historical_footprint_locality_code
          ? {
              historicalFootprintLocalityCode: cleanNumericCode(
                componentFallbackFeature.properties.historical_footprint_locality_code,
              ),
            }
          : {}),
      },
      geometry: roundGeometry(
        componentFallbackFeature?.geometry ??
          localityFallbackFeature?.geometry ??
          localityFeature.geometry,
      ),
    })
  }

  return {
    displayRows,
    features,
    metadataById,
    hiddenGeographyIds: [...hiddenGeographyIds].toSorted(),
  }
}

export function buildHiddenLocalityIds(featureCollection, electionId) {
  assertFeatureCollection(featureCollection, 'locality display geography')
  const hidden = new Set()
  for (const feature of featureCollection.features) {
    const properties = feature.properties ?? {}
    if (!properties.isComposite) {
      continue
    }
    const active = (properties.activeElections ?? []).includes(electionId)
    if (active) {
      for (const componentId of properties.componentLocalityIds ?? []) {
        hidden.add(componentId)
      }
    } else if (properties.id) {
      hidden.add(properties.id)
    }
  }
  return [...hidden].toSorted()
}

export function aliasJoinedCompositeResults(primaryRows, featureCollection, electionId) {
  assertFeatureCollection(featureCollection, 'locality display geography')
  const rowsById = new Map()
  for (const row of primaryRows) {
    const id = row.locality_id
    if (!id || rowsById.has(id)) {
      throw new Error(`${electionId} has a missing or duplicate locality result ID: ${id || '(blank)'}`)
    }
    rowsById.set(id, row)
  }

  const aliasesByHostId = new Map()
  for (const feature of featureCollection.features) {
    const properties = feature.properties ?? {}
    if (
      properties.compositeKind !== 'joined_polling_register' ||
      !(properties.activeElections ?? []).includes(electionId)
    ) {
      continue
    }

    const compositeId = properties.id
    const hostId = properties.hostLocalityId
    const componentIds = properties.componentLocalityIds ?? []
    if (!compositeId || !hostId || !componentIds.includes(hostId)) {
      throw new Error(`${electionId} has an invalid joined-locality composite: ${compositeId || '(blank)'}`)
    }
    if (aliasesByHostId.has(hostId)) {
      throw new Error(`${electionId} host locality ${hostId} has more than one joined composite`)
    }
    if (!rowsById.has(hostId)) {
      throw new Error(`${electionId} joined composite ${compositeId} has no host result for ${hostId}`)
    }
    const unexpectedComponentResult = componentIds.find(
      (componentId) => componentId !== hostId && rowsById.has(componentId),
    )
    if (unexpectedComponentResult) {
      throw new Error(
        `${electionId} joined composite ${compositeId} would hide standalone result ${unexpectedComponentResult}`,
      )
    }
    aliasesByHostId.set(hostId, compositeId)
  }

  return primaryRows.map((row) => {
    const compositeId = aliasesByHostId.get(row.locality_id)
    return compositeId ? { ...row, locality_id: compositeId } : row
  })
}

export function buildDisplayMarkers(featureCollection) {
  assertFeatureCollection(featureCollection, 'display geography')

  return {
    type: 'FeatureCollection',
    features: featureCollection.features
      .filter((feature) => feature.properties?.displayMode === 'marker')
      .map((feature) => ({
        type: 'Feature',
        id: feature.id,
        properties: { ...feature.properties },
        geometry: displayMarkerGeometry(feature.geometry),
      })),
  }
}

function displayMarkerGeometry(geometry) {
  const coordinates = markerCoordinates(geometry)
  if (coordinates.length === 0) {
    throw new Error('Display marker geometry has no coordinates')
  }
  return coordinates.length === 1
    ? { type: 'Point', coordinates: coordinates[0] }
    : { type: 'MultiPoint', coordinates }
}

function markerCoordinates(geometry) {
  if (!geometry) {
    return []
  }
  if (geometry.type === 'Point') {
    return [roundCoordinates(geometry.coordinates)]
  }
  if (geometry.type === 'MultiPoint') {
    return roundCoordinates(geometry.coordinates)
  }
  if (geometry.type === 'MultiPolygon') {
    return geometry.coordinates.map((coordinates) =>
      geometryBoundsCenter({ type: 'Polygon', coordinates }),
    )
  }
  if (geometry.type === 'GeometryCollection') {
    return geometry.geometries.flatMap(markerCoordinates)
  }
  return [geometryBoundsCenter(geometry)]
}

export function buildCoverage(summaryRow, mode) {
  if (!summaryRow) {
    throw new Error('Missing election coverage summary')
  }

  const prefix = mode === 'locality' ? 'locality_mode' : 'statistical_mode'

  return {
    totalRows: numberValue(summaryRow.geographic_scope_rows, 'geographic_scope_rows'),
    totalActualVoters: numberValue(
      summaryRow.geographic_scope_actual_voters,
      'geographic_scope_actual_voters',
    ),
    mappedRows: numberValue(summaryRow[`${prefix}_mapped_rows`], `${prefix}_mapped_rows`),
    mappedActualVoters: numberValue(
      summaryRow[`${prefix}_mapped_actual_voters`],
      `${prefix}_mapped_actual_voters`,
    ),
    mappedActualVoterShare: numberValue(
      summaryRow[`${prefix}_mapped_actual_voter_share`],
      `${prefix}_mapped_actual_voter_share`,
    ),
    pendingRows: numberValue(summaryRow[`${prefix}_pending_rows`], `${prefix}_pending_rows`),
    pendingActualVoters: numberValue(
      summaryRow[`${prefix}_pending_actual_voters`],
      `${prefix}_pending_actual_voters`,
    ),
    unmappedRows: numberValue(summaryRow[`${prefix}_pending_rows`], `${prefix}_pending_rows`),
    unmappedActualVoters: numberValue(
      summaryRow[`${prefix}_pending_actual_voters`],
      `${prefix}_pending_actual_voters`,
    ),
  }
}

export function buildResultPayload({
  electionId,
  mode,
  primaryRows,
  customRows,
  envelopeRows = [],
  metadataById,
  customMetadataById,
  coverage,
  hiddenGeographyIds = [],
  partyRegistry,
  partyColorsByBallotLetter = {},
  partyOverrides = {},
  excludedPartyColumns = [],
  validatePartyTotals = false,
}) {
  const primaryType = mode === 'statistical-area' ? 'statistical-area' : 'locality'
  const records = []
  const excludedColumns = new Set(excludedPartyColumns)
  const partyIds = inferPartyColumns(primaryRows, customRows, envelopeRows).filter(
    (partyId) => !excludedColumns.has(partyId),
  )
  assertPartyRegistryCoverage(electionId, partyIds, partyRegistry, excludedColumns)

  for (const row of primaryRows) {
    const id = mode === 'statistical-area' ? row.stat_area_id : row.locality_id
    const metadata = metadataById.get(id)
    if (!id || !metadata) {
      throw new Error(`${electionId} ${mode} result has no matching metadata for ${id || '(blank ID)'}`)
    }
    records.push(buildResultRecord(row, id, primaryType, metadata, partyIds))
  }

  for (const row of customRows) {
    const id = row.custom_geography_id || row.geography_id
    const metadata = customMetadataById.get(id)
    if (!id || !metadata) {
      throw new Error(`${electionId} custom result has no matching geometry for ${id || '(blank ID)'}`)
    }
    records.push(
      buildResultRecord(row, id, metadata.geographyType || 'custom', metadata, partyIds),
    )
  }

  if (envelopeRows.length > 1) {
    throw new Error(`${electionId} envelope results contain more than one aggregate row`)
  }
  const envelopeRow = envelopeRows[0]
  const envelope = envelopeRow
    ? buildResultRecord(
        envelopeRow,
        envelopeRow.envelope_id || 'envelope:official',
        'envelope',
        {
          id: envelopeRow.envelope_id || 'envelope:official',
          customKey: 'envelope',
          nameHe: 'מעטפות כפולות',
          nameEn: 'Double envelopes',
        },
        partyIds,
      )
    : null

  const duplicateIds = findDuplicateIds(records)
  if (duplicateIds.length > 0) {
    throw new Error(`${electionId} ${mode} results contain duplicate IDs: ${duplicateIds.join(', ')}`)
  }

  const hiddenIds = new Set(hiddenGeographyIds)
  const hiddenResultIds = records
    .filter((record) => hiddenIds.has(record.id))
    .map((record) => record.id)
  if (hiddenResultIds.length > 0) {
    throw new Error(
      `${electionId} ${mode} hides geographies that also have results: ${hiddenResultIds.join(', ')}`,
    )
  }

  if (validatePartyTotals) {
    assertPartyTotalsMatchRegistry(electionId, partyIds, partyRegistry, records, envelope)
  }

  const parties = partyIds.map((partyId) =>
    buildPartyDefinition(
      partyId,
      partyRegistry.get(partyId),
      partyOverrides[partyId],
      partyColorsByBallotLetter,
    ),
  )

  return {
    schemaVersion: 2,
    electionId,
    geographyMode: mode,
    coverage,
    parties,
    records,
    envelope,
    hiddenGeographyIds: [...hiddenIds].toSorted(),
  }
}

export function buildGeographySearchIndex({ electionId, modes }) {
  if (!/^K\d+$/.test(electionId)) {
    throw new Error(`Invalid search-index election ID: ${electionId}`)
  }
  if (!Array.isArray(modes) || modes.length === 0) {
    throw new Error(`${electionId} search index has no geography modes`)
  }

  const items = []
  for (const { geographyMode, geography, results, metadataById } of modes) {
    assertFeatureCollection(geography, `${electionId} ${geographyMode} search geography`)
    if (results?.electionId !== electionId || results?.geographyMode !== geographyMode) {
      throw new Error(`${electionId} ${geographyMode} search results do not match the index`)
    }

    const hiddenIds = new Set(results.hiddenGeographyIds)
    const recordsById = new Map(results.records.map((record) => [record.id, record]))
    const featuresById = new Map(
      geography.features.map((feature) => [String(feature.id ?? feature.properties?.id ?? ''), feature]),
    )

    for (const feature of geography.features) {
      const properties = feature.properties ?? {}
      const id = String(feature.id ?? properties.id ?? '').trim()
      if (!id || hiddenIds.has(id)) {
        continue
      }
      const activeElections = Array.isArray(properties.activeElections)
        ? properties.activeElections
        : []
      if (activeElections.length > 0 && !activeElections.includes(electionId)) {
        continue
      }

      const record = recordsById.get(id)
      const isBaseGeography =
        (geographyMode === 'locality' && properties.geographyType === 'locality') ||
        (geographyMode === 'statistical-area' &&
          properties.geographyType === 'statistical-area')
      if (!record && !isBaseGeography) {
        continue
      }

      const names = record?.names ?? searchNamesForFeature(properties, geographyMode)
      if (!names.he || !names.en) {
        throw new Error(`${electionId} search feature ${id} has incomplete names`)
      }
      const aliases = { he: new Set(), en: new Set() }
      addSearchAlias(aliases.he, properties.nameHe, names.he)
      addSearchAlias(aliases.en, properties.nameEn, names.en)
      for (const language of ['he', 'en']) {
        for (const alias of properties.includedNames?.[language] ?? []) {
          addSearchAlias(aliases[language], alias, names[language])
        }
        for (const alias of record?.includedNames?.[language] ?? []) {
          addSearchAlias(aliases[language], alias, names[language])
        }
      }
      for (const componentId of properties.componentLocalityIds ?? []) {
        const component = featuresById.get(String(componentId))
        addSearchAlias(aliases.he, component?.properties?.nameHe, names.he)
        addSearchAlias(aliases.en, component?.properties?.nameEn, names.en)
      }

      const rawCode = String(
        record?.code ??
          (geographyMode === 'statistical-area'
            ? id.split(':').at(-1)
            : properties.localityCode ?? ''),
      ).trim()
      const notice = record?.notice ?? metadataById?.get(id)?.notice
      items.push({
        id,
        geographyMode,
        names,
        aliases: {
          he: [...aliases.he].toSorted(),
          en: [...aliases.en].toSorted(),
        },
        code: rawCode.includes(':') ? '' : rawCode,
        hasResults: Boolean(record),
        bounds: geometryBounds(feature.geometry),
        ...(notice?.he && notice?.en ? { notice } : {}),
      })
    }
  }

  return {
    schemaVersion: 1,
    electionId,
    items: items.toSorted(
      (left, right) =>
        left.geographyMode.localeCompare(right.geographyMode) ||
        left.names.en.localeCompare(right.names.en) ||
        left.id.localeCompare(right.id),
    ),
  }
}

function searchNamesForFeature(properties, geographyMode) {
  const nameHe = String(properties.nameHe ?? '').trim()
  const nameEn = String(properties.nameEn ?? '').trim()
  if (geographyMode !== 'statistical-area') {
    return { he: nameHe, en: nameEn || nameHe }
  }
  const areaNumber = String(properties.statAreaNumber ?? '').trim()
  return {
    he: areaNumber ? `${nameHe} · ${areaNumber}` : nameHe,
    en: areaNumber ? `${nameEn || nameHe} · ${areaNumber}` : nameEn || nameHe,
  }
}

function addSearchAlias(target, value, primaryName) {
  const alias = String(value ?? '').trim()
  if (alias && alias !== primaryName) {
    target.add(alias)
  }
}

export function applyStatisticalDisplayGroups({
  electionId,
  primaryRows,
  customRows,
  groups = [],
}) {
  if (groups.length === 0) {
    return { primaryRows, displayRows: [], hiddenGeographyIds: [] }
  }

  const primaryRowsById = new Map()
  for (const row of primaryRows) {
    const id = String(row.stat_area_id ?? '').trim()
    if (!id) {
      throw new Error(`${electionId} statistical display grouping found a row without an ID`)
    }
    const rows = primaryRowsById.get(id) ?? []
    rows.push(row)
    primaryRowsById.set(id, rows)
  }

  const claimedComponentIds = new Set()
  const hiddenGeographyIds = new Set()
  const displayRows = []
  const partyColumns = inferPartyColumns(primaryRows)

  for (const group of groups) {
    const displayGeographyId = String(group.displayGeographyId ?? '').trim()
    const componentIds = [...new Set(group.componentIds ?? [])]
    const aggregationMethod = String(
      group.aggregationMethod ?? 'validated-locality-aggregate',
    ).trim()
    if (!displayGeographyId || componentIds.length === 0) {
      throw new Error(`${electionId} has an invalid statistical display group`)
    }
    if (!['validated-locality-aggregate', 'sum-components'].includes(aggregationMethod)) {
      throw new Error(
        `${electionId} display group ${displayGeographyId} has invalid aggregation method ${aggregationMethod}`,
      )
    }

    for (const componentId of componentIds) {
      if (claimedComponentIds.has(componentId)) {
        throw new Error(`${electionId} statistical display component is reused: ${componentId}`)
      }
      claimedComponentIds.add(componentId)
      hiddenGeographyIds.add(componentId)
    }

    const sourceRows = componentIds.flatMap((componentId) => {
      const rows = primaryRowsById.get(componentId) ?? []
      if (rows.length > 1) {
        throw new Error(`${electionId} has duplicate statistical result ${componentId}`)
      }
      return rows
    })
    if (sourceRows.length === 0) {
      throw new Error(`${electionId} display group ${displayGeographyId} has no source results`)
    }

    if (aggregationMethod === 'sum-components') {
      const targetRow = {
        ...sourceRows[0],
        custom_geography_id: displayGeographyId,
        geography_id: displayGeographyId,
        geography_mode: 'statistical-area',
      }
      for (const column of [...ADDITIVE_RESULT_COLUMNS, ...partyColumns]) {
        targetRow[column] = sourceRows.reduce(
          (sum, row) => sum + numberValue(row[column], `${row.stat_area_id}.${column}`),
          0,
        )
      }
      displayRows.push(targetRow)
      continue
    }

    const targetRows = customRows.filter(
      (row) =>
        (row.custom_geography_id || row.geography_id) === displayGeographyId &&
        (!row.geography_mode || row.geography_mode === 'locality'),
    )
    if (targetRows.length !== 1) {
      throw new Error(
        `${electionId} display group ${displayGeographyId} requires exactly one locality aggregate`,
      )
    }
    const targetRow = targetRows[0]

    const mismatches = []
    for (const column of [...ADDITIVE_RESULT_COLUMNS, ...partyColumns]) {
      const sourceTotal = sourceRows.reduce(
        (sum, row) => sum + numberValue(row[column], `${row.stat_area_id}.${column}`),
        0,
      )
      const targetTotal = numberValue(targetRow[column], `${displayGeographyId}.${column}`)
      if (sourceTotal !== targetTotal) {
        mismatches.push(`${column}=${sourceTotal}/${targetTotal}`)
      }
    }
    if (mismatches.length > 0) {
      throw new Error(
        `${electionId} display group ${displayGeographyId} does not equal its components: ${mismatches.join(', ')}`,
      )
    }

    displayRows.push({ ...targetRow, geography_mode: 'statistical-area' })
  }

  return {
    primaryRows: primaryRows.filter((row) => !claimedComponentIds.has(row.stat_area_id)),
    displayRows,
    hiddenGeographyIds: [...hiddenGeographyIds].toSorted(),
  }
}

export function assertUniqueStatisticalDisplayOwnership({
  electionId,
  displayGroups = [],
  pollingGroupRows = [],
}) {
  const ownersByComponent = new Map()

  const claim = (ownerId, componentIds) => {
    for (const componentId of componentIds) {
      const existingOwner = ownersByComponent.get(componentId)
      if (existingOwner && existingOwner !== ownerId) {
        throw new Error(
          `${electionId} statistical display component ${componentId} is reused by ${existingOwner} and ${ownerId}`,
        )
      }
      ownersByComponent.set(componentId, ownerId)
    }
  }

  for (const group of displayGroups) {
    claim(String(group.displayGeographyId ?? '').trim(), group.componentIds ?? [])
  }
  for (const row of pollingGroupRows) {
    const ownerId = String(row.custom_geography_id || row.geography_id || '').trim()
    claim(ownerId, splitPipeValues(row.component_stat_area_ids))
  }
}

function buildResultRecord(row, id, geographyType, metadata, partyColumns) {
  const partyVotes = Object.fromEntries(
    partyColumns.map((partyId) => [partyId, numberValue(row[partyId], `${id}.${partyId}`)]),
  )
  const eligibleVoters = numberValue(row.eligible_voters, `${id}.eligible_voters`)
  const actualVoters = numberValue(row.actual_voters, `${id}.actual_voters`)
  const validVotes = numberValue(row.valid_votes, `${id}.valid_votes`)
  const partyVoteTotal = Object.values(partyVotes).reduce((sum, votes) => sum + votes, 0)
  if (partyVoteTotal !== validVotes) {
    throw new Error(
      `${id} party-vote total (${partyVoteTotal}) does not match valid_votes (${validVotes})`,
    )
  }
  const rankedParties = Object.entries(partyVotes).toSorted((left, right) => right[1] - left[1])
  const [winningPartyId = '', winningVotes = 0] = rankedParties[0] ?? []
  const runnerUpVotes = rankedParties[1]?.[1] ?? 0
  const statAreaNumber = cleanNumericCode(metadata.statAreaNumber)
  const names =
    geographyType === 'statistical-area'
      ? {
          he: `${metadata.nameHe} · ${statAreaNumber}`,
          en: `${metadata.nameEn} · ${statAreaNumber}`,
        }
      : { he: metadata.nameHe, en: metadata.nameEn }
  const includedNames = metadata.includedNames
  const hasIncludedNames = includedNames?.he?.length > 0 || includedNames?.en?.length > 0
  const notice = metadata.notice
  const hasNotice = notice?.he && notice?.en

  return {
    id,
    geographyType,
    names,
    code:
      geographyType === 'statistical-area'
        ? metadata.yishuvStat || metadata.yishuvStat2022 || id
        : metadata.localityCode || metadata.customKey || id,
    localityId: metadata.localityId || null,
    ...(hasIncludedNames ? { includedNames } : {}),
    ...(hasNotice ? { notice } : {}),
    totals: {
      contributingRows: numberValue(row.contributing_rows, `${id}.contributing_rows`),
      contributingKalpis: numberValue(row.contributing_kalpis, `${id}.contributing_kalpis`),
      eligibleVoters,
      actualVoters,
      validVotes,
      invalidVotes: numberValue(row.invalid_votes, `${id}.invalid_votes`),
      turnout:
        geographyType === 'envelope'
          ? null
          : eligibleVoters > 0
            ? actualVoters / eligibleVoters
            : null,
    },
    winner: {
      partyId: winningPartyId,
      votes: winningVotes,
      runnerUpVotes,
      marginVotes: winningVotes - runnerUpVotes,
      voteShare: validVotes > 0 ? winningVotes / validVotes : 0,
    },
    partyVotes,
  }
}

function splitPipeValues(value) {
  return String(value ?? '')
    .split('|')
    .map((part) => part.trim())
    .filter(Boolean)
}

function inferPartyColumns(...rowGroups) {
  const partyIds = new Set()
  for (const rows of rowGroups) {
    const firstRow = rows[0]
    if (!firstRow) {
      continue
    }
    const columns = Object.keys(firstRow)
    const coreEnd = columns.indexOf(RESULT_CORE_LAST_COLUMN)
    if (coreEnd < 0) {
      throw new Error(`Results are missing required column ${RESULT_CORE_LAST_COLUMN}`)
    }
    for (const column of columns.slice(coreEnd + 1)) {
      if (column) {
        partyIds.add(column)
      }
    }
  }
  return [...partyIds]
}

function buildPartyDefinition(
  partyId,
  registryEntry,
  override = {},
  partyColorsByBallotLetter = {},
) {
  const nameHe = override.nameHe || registryEntry.displayNameHe || registryEntry.listNameHe
  const nameEn = override.nameEn || registryEntry.displayNameEn || nameHe
  const reviewedColor = override.color || partyColorsByBallotLetter[registryEntry.ballotLetter]
  return {
    id: partyId,
    ballotLetter: registryEntry.ballotLetter,
    names: {
      he: nameHe,
      en: nameEn,
    },
    listNameHe: registryEntry.listNameHe,
    wikipedia: {
      he: registryEntry.wikipediaHeUrl || null,
      en: registryEntry.wikipediaEnUrl || null,
    },
    color: reviewedColor || stablePartyColor(registryEntry.ballotLetter),
    colorStatus: reviewedColor ? 'reviewed' : 'provisional',
  }
}

function assertPartyRegistryCoverage(electionId, partyIds, partyRegistry, excludedColumns = new Set()) {
  if (!(partyRegistry instanceof Map)) {
    throw new Error(`${electionId} is missing its party-registry map`)
  }
  const sourceColumns = new Set(partyIds)
  const missing = partyIds.filter((partyId) => !partyRegistry.has(partyId))
  const extra = [...partyRegistry.keys()].filter(
    (partyId) => !sourceColumns.has(partyId) && !excludedColumns.has(partyId),
  )
  if (missing.length > 0 || extra.length > 0) {
    throw new Error(
      `${electionId} party registry does not match result columns; ` +
        `missing: ${missing.join(', ') || '(none)'}; extra: ${extra.join(', ') || '(none)'}`,
    )
  }
}

function assertPartyTotalsMatchRegistry(electionId, partyIds, partyRegistry, records, envelope) {
  const totals = Object.fromEntries(partyIds.map((partyId) => [partyId, 0]))
  for (const record of envelope ? [...records, envelope] : records) {
    for (const partyId of partyIds) {
      totals[partyId] += record.partyVotes[partyId]
    }
  }

  const mismatches = partyIds
    .filter((partyId) => totals[partyId] !== partyRegistry.get(partyId).totalVotes)
    .map(
      (partyId) =>
        `${partyId}: aggregate ${totals[partyId]}, registry ${partyRegistry.get(partyId).totalVotes}`,
    )
  if (mismatches.length > 0) {
    throw new Error(`${electionId} party totals do not match the registry: ${mismatches.join('; ')}`)
  }
}

function optionalHttpsUrl(value, fieldName) {
  const text = String(value ?? '').trim()
  if (!text) {
    return ''
  }
  let parsed
  try {
    parsed = new URL(text)
  } catch {
    throw new Error(`${fieldName} is not a valid URL`)
  }
  if (parsed.protocol !== 'https:') {
    throw new Error(`${fieldName} must use HTTPS`)
  }
  return parsed.href
}

export function stablePartyColor(ballotLetter) {
  let hash = 2166136261
  for (const character of ballotLetter) {
    hash ^= character.codePointAt(0)
    hash = Math.imul(hash, 16777619)
  }
  const hue = Math.abs(hash) % 360
  return `hsl(${hue} ${DEFAULT_PARTY_SATURATION}% ${DEFAULT_PARTY_LIGHTNESS}%)`
}

function findDuplicateIds(records) {
  const seen = new Set()
  const duplicates = new Set()
  for (const record of records) {
    if (seen.has(record.id)) {
      duplicates.add(record.id)
    }
    seen.add(record.id)
  }
  return [...duplicates]
}

export function geometryBounds(geometry) {
  const bounds = {
    minX: Number.POSITIVE_INFINITY,
    minY: Number.POSITIVE_INFINITY,
    maxX: Number.NEGATIVE_INFINITY,
    maxY: Number.NEGATIVE_INFINITY,
  }

  const visit = (coordinates) => {
    if (!Array.isArray(coordinates)) {
      return
    }
    if (
      coordinates.length >= 2 &&
      typeof coordinates[0] === 'number' &&
      typeof coordinates[1] === 'number'
    ) {
      bounds.minX = Math.min(bounds.minX, coordinates[0])
      bounds.minY = Math.min(bounds.minY, coordinates[1])
      bounds.maxX = Math.max(bounds.maxX, coordinates[0])
      bounds.maxY = Math.max(bounds.maxY, coordinates[1])
      return
    }
    for (const child of coordinates) {
      visit(child)
    }
  }

  if (geometry?.type === 'GeometryCollection') {
    for (const child of geometry.geometries ?? []) {
      const [[minX, minY], [maxX, maxY]] = geometryBounds(child)
      visit([minX, minY])
      visit([maxX, maxY])
    }
  } else {
    visit(geometry?.coordinates)
  }
  if (![bounds.minX, bounds.minY, bounds.maxX, bounds.maxY].every(Number.isFinite)) {
    throw new Error('Geometry has no coordinates')
  }
  return [
    [Number(bounds.minX.toFixed(6)), Number(bounds.minY.toFixed(6))],
    [Number(bounds.maxX.toFixed(6)), Number(bounds.maxY.toFixed(6))],
  ]
}

function geometryBoundsCenter(geometry) {
  const [[minX, minY], [maxX, maxY]] = geometryBounds(geometry)
  return [
    Number(((minX + maxX) / 2).toFixed(6)),
    Number(((minY + maxY) / 2).toFixed(6)),
  ]
}

function coordinatePositionCount(coordinates) {
  if (!Array.isArray(coordinates)) {
    return Number.POSITIVE_INFINITY
  }
  if (
    coordinates.length >= 2 &&
    typeof coordinates[0] === 'number' &&
    typeof coordinates[1] === 'number'
  ) {
    return 1
  }

  let count = 0
  for (const child of coordinates) {
    count += coordinatePositionCount(child)
    if (count > POINT_PROXY_MAX_VERTICES) {
      return count
    }
  }
  return count
}

function roundGeometry(geometry) {
  if (!geometry) {
    return geometry
  }
  if (geometry.type === 'GeometryCollection') {
    return { ...geometry, geometries: geometry.geometries.map(roundGeometry) }
  }
  return { ...geometry, coordinates: roundCoordinates(geometry.coordinates) }
}

function roundCoordinates(value) {
  if (!Array.isArray(value)) {
    return value
  }
  if (value.length > 0 && typeof value[0] === 'number') {
    return value.map((coordinate) => Number(coordinate.toFixed(6)))
  }
  return value.map(roundCoordinates)
}

function assertFeatureCollection(value, label) {
  if (!value || value.type !== 'FeatureCollection' || !Array.isArray(value.features)) {
    throw new Error(`${label} input is not a GeoJSON FeatureCollection`)
  }
}
