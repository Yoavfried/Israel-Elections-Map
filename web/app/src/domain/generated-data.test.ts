import { createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { coalitionDefinition } from '../config/coalitions'
import {
  AppCatalogSchema,
  ElectionResultsSchema,
  GeographySearchIndexSchema,
  NationalResultsSchema,
} from './schemas'

const dataRoot = resolve(import.meta.dirname, '..', '..', 'public', 'data', 'v2')

describe('generated web data', () => {
  it('matches the runtime schemas and asset checksums', async () => {
    const catalog = AppCatalogSchema.parse(await readJson(resolve(dataRoot, 'catalog.json')))

    await Promise.all(
      catalog.assets.map(async (asset) => {
        const bytes = await readFile(resolve(dataRoot, asset.path))
        expect(bytes.byteLength, asset.path).toBe(asset.bytes)
        expect(createHash('sha256').update(bytes).digest('hex'), asset.path).toBe(asset.sha256)
      }),
    )

    expect(catalog.elections).toHaveLength(9)
    expect(catalog.buildId).toHaveLength(16)
  })

  it('resolves every configured coalition member to an election ballot', async () => {
    const catalog = AppCatalogSchema.parse(await readJson(resolve(dataRoot, 'catalog.json')))

    for (const election of catalog.elections) {
      const definition = coalitionDefinition(election.id)
      expect(definition, election.id).not.toBeNull()
      const results = ElectionResultsSchema.parse(
        await readJson(resolve(dataRoot, election.resultUrls.locality)),
      )
      const partyIds = new Set(results.parties.map((party) => party.id))
      for (const partyId of definition?.memberPartyIds ?? []) {
        expect(partyIds.has(partyId), `${election.id}:${partyId}`).toBe(true)
      }
    }
  })

  it('publishes an election-aware search index for every visible geography', async () => {
    const catalog = AppCatalogSchema.parse(await readJson(resolve(dataRoot, 'catalog.json')))
    let emptyVisibleGeographies = 0

    for (const election of catalog.elections) {
      const searchIndex = GeographySearchIndexSchema.parse(
        await readJson(resolve(dataRoot, election.resultUrls.search)),
      )
      expect(searchIndex.electionId).toBe(election.id)
      expect(catalog.assets.some((asset) => asset.path === election.resultUrls.search)).toBe(true)
      expect(new Set(searchIndex.items.map((item) => `${item.geographyMode}:${item.id}`)).size)
        .toBe(searchIndex.items.length)

      for (const item of searchIndex.items) {
        expect(item.bounds[0][0], `${election.id}/${item.id}/west`).toBeLessThanOrEqual(
          item.bounds[1][0],
        )
        expect(item.bounds[0][1], `${election.id}/${item.id}/south`).toBeLessThanOrEqual(
          item.bounds[1][1],
        )
        if (!item.hasResults) {
          emptyVisibleGeographies += 1
        }
      }

      for (const mode of ['statistical-area', 'locality'] as const) {
        const payload = ElectionResultsSchema.parse(
          await readJson(resolve(dataRoot, election.resultUrls[mode])),
        )
        const searchItems = new Map(
          searchIndex.items
            .filter((item) => item.geographyMode === mode)
            .map((item) => [item.id, item]),
        )
        for (const hiddenId of payload.hiddenGeographyIds) {
          expect(searchItems.has(hiddenId), `${election.id}/${mode}/${hiddenId}`).toBe(false)
        }
        for (const record of payload.records) {
          expect(searchItems.get(record.id)?.hasResults, `${election.id}/${mode}/${record.id}`)
            .toBe(true)
        }
      }
    }

    expect(emptyVisibleGeographies).toBeGreaterThan(0)
  })

  it('publishes complete national results with thresholds and exactly 120 mandates', async () => {
    const catalog = AppCatalogSchema.parse(await readJson(resolve(dataRoot, 'catalog.json')))
    const expectedPartyCounts: Record<string, number> = {
      K17: 31,
      K18: 33,
      K19: 32,
      K20: 25,
      K21: 40,
      K22: 29,
      K23: 29,
      K24: 38,
      K25: 40,
    }

    for (const election of catalog.elections) {
      const payload = NationalResultsSchema.parse(
        await readJson(resolve(dataRoot, election.resultUrls.national)),
      )
      const expectedThreshold = election.number >= 20 ? 0.0325 : 0.02

      expect(payload.electionId).toBe(election.id)
      expect(payload.threshold.share, election.id).toBe(expectedThreshold)
      expect(payload.threshold.votes, election.id).toBe(
        Math.ceil(payload.totals.validVotes * expectedThreshold),
      )
      expect(payload.parties, election.id).toHaveLength(payload.totals.contestingParties)
      expect(payload.parties, election.id).toHaveLength(expectedPartyCounts[election.id])
      expect(payload.parties.every((party) => party.votes > 0), election.id).toBe(true)
      expect(
        payload.parties.reduce((total, party) => total + party.votes, 0),
        election.id,
      ).toBe(payload.totals.validVotes)
      expect(
        payload.parties.reduce((total, party) => total + party.mandates, 0),
        election.id,
      ).toBe(120)
      expect(payload.totals.mandates, election.id).toBe(120)
      expect(
        payload.parties.filter((party) => party.passedThreshold),
        election.id,
      ).toHaveLength(payload.totals.representedParties)
      expect(
        payload.parties.every(
          (party) => party.passedThreshold === (party.mandates > 0),
        ),
        election.id,
      ).toBe(true)
      expect(
        payload.parties.map((party) => party.votes),
        election.id,
      ).toEqual(payload.parties.map((party) => party.votes).toSorted((a, b) => b - a))
      expect(catalog.assets.some((asset) => asset.path === election.resultUrls.national)).toBe(true)
    }
  })

  it('keeps reviewed Wikipedia links across repeated party appearances', async () => {
    const catalog = AppCatalogSchema.parse(await readJson(resolve(dataRoot, 'catalog.json')))
    const payloads = new Map(
      await Promise.all(
        catalog.elections.map(async (election) => [
          election.id,
          NationalResultsSchema.parse(
            await readJson(resolve(dataRoot, election.resultUrls.national)),
          ),
        ] as const),
      ),
    )
    const byName = new Map<
      string,
      Array<{
        electionId: string
        wikipedia: { he: string | null; en: string | null }
      }>
    >()

    for (const [electionId, payload] of payloads) {
      for (const party of payload.parties) {
        const appearances = byName.get(party.names.he) ?? []
        appearances.push({ electionId, wikipedia: party.wikipedia })
        byName.set(party.names.he, appearances)
      }
    }

    const reviewedLinkPresenceExceptions = new Set(['כח להשפיע/he'])
    for (const [name, appearances] of byName) {
      if (appearances.length < 2) {
        continue
      }
      for (const language of ['he', 'en'] as const) {
        if (reviewedLinkPresenceExceptions.has(`${name}/${language}`)) {
          continue
        }
        const linked = appearances.filter((appearance) => appearance.wikipedia[language])
        expect(
          linked.length === 0 || linked.length === appearances.length,
          `${name}/${language}: ${linked.map((appearance) => appearance.electionId).join(', ')}`,
        ).toBe(true)
      }
    }

    const party = (electionId: string, ballotLetter: string) =>
      payloads.get(electionId)?.parties.find(
        (candidate) => candidate.ballotLetter === ballotLetter,
      )
    const shasUrls = {
      he: 'https://he.wikipedia.org/wiki/%D7%9E%D7%A4%D7%9C%D7%92%D7%AA_%D7%A9%22%D7%A1',
      en: 'https://en.wikipedia.org/wiki/Shas',
    }
    const unitedTorahJudaismUrls = {
      he: 'https://he.wikipedia.org/wiki/%D7%99%D7%94%D7%93%D7%95%D7%AA_%D7%94%D7%AA%D7%95%D7%A8%D7%94',
      en: 'https://en.wikipedia.org/wiki/United_Torah_Judaism',
    }

    for (const electionId of catalog.elections.map((election) => election.id)) {
      expect(party(electionId, 'שס')?.wikipedia, `${electionId}/שס`).toEqual(shasUrls)
      expect(party(electionId, 'ג')?.wikipedia, `${electionId}/ג`).toEqual(
        unitedTorahJudaismUrls,
      )
    }
    for (const electionId of ['K17', 'K18', 'K19']) {
      expect(party(electionId, 'עם')?.wikipedia.en, `${electionId}/עם`).toBe(
        'https://en.wikipedia.org/wiki/United_Arab_List',
      )
    }

    expect(party('K17', 'אמת')?.wikipedia.en).toBe(
      'https://en.wikipedia.org/wiki/Israeli_Labor_Party',
    )
    expect(party('K17', 'טב')?.wikipedia.en).toBe(
      'https://en.wikipedia.org/wiki/National_Union_(Israel)',
    )
    expect(party('K18', 'ט')?.wikipedia).toEqual({
      he: 'https://he.wikipedia.org/wiki/%D7%94%D7%90%D7%99%D7%97%D7%95%D7%93_%D7%94%D7%9C%D7%90%D7%95%D7%9E%D7%99',
      en: 'https://en.wikipedia.org/wiki/National_Union_(Israel)',
    })
    expect(party('K21', 'דעם')?.wikipedia.en).toBe(
      'https://en.wikipedia.org/wiki/United_Arab_List',
    )
    expect(party('K21', 'ין')?.wikipedia).toEqual({
      he: 'https://he.wikipedia.org/wiki/%D7%90%D7%99%D7%97%D7%95%D7%93_%D7%91%D7%A0%D7%99_%D7%94%D7%91%D7%A8%D7%99%D7%AA',
      en: 'https://en.wikipedia.org/wiki/Ihud_Bnei_HaBrit',
    })
    const otzmaYehuditUrls = {
      he: 'https://he.wikipedia.org/wiki/%D7%A2%D7%95%D7%A6%D7%9E%D7%94_%D7%99%D7%94%D7%95%D7%93%D7%99%D7%AA',
      en: 'https://en.wikipedia.org/wiki/Otzma_Yehudit',
    }
    for (const [electionId, ballotLetter] of [
      ['K17', 'כ'],
      ['K22', 'כף'],
      ['K23', 'נץ'],
    ] as const) {
      expect(
        party(electionId, ballotLetter)?.wikipedia,
        `${electionId}/${ballotLetter}`,
      ).toEqual(otzmaYehuditUrls)
    }
    expect(party('K19', 'נץ')?.wikipedia).toEqual({
      he: 'https://he.wikipedia.org/wiki/%D7%A2%D7%95%D7%A6%D7%9E%D7%94_%D7%9C%D7%99%D7%A9%D7%A8%D7%90%D7%9C',
      en: 'https://en.wikipedia.org/wiki/Otzma_Yehudit',
    })
    const religiousZionistPartyUrls = {
      he: 'https://he.wikipedia.org/wiki/%D7%94%D7%A6%D7%99%D7%95%D7%A0%D7%95%D7%AA_%D7%94%D7%93%D7%AA%D7%99%D7%AA_(%D7%A1%D7%99%D7%A2%D7%94)',
      en: 'https://en.wikipedia.org/wiki/Religious_Zionist_Party',
    }
    for (const electionId of ['K24', 'K25']) {
      expect(party(electionId, 'ט')?.wikipedia, `${electionId}/ט`).toEqual(
        religiousZionistPartyUrls,
      )
    }
    expect(party('K17', 'פ')?.wikipedia).toEqual({
      he: 'https://he.wikipedia.org/wiki/%D7%A2%D7%95%D7%96%D7%99_%D7%93%D7%99%D7%99%D7%9F',
      en: 'https://en.wikipedia.org/wiki/Tafnit',
    })
    expect(party('K17', 'זה')?.wikipedia).toEqual({
      he: 'https://he.wikipedia.org/wiki/%D7%90%D7%91%D7%A8%D7%94%D7%9D_%D7%A0%D7%92%D7%95%D7%A1%D7%94',
      en: 'https://en.wikipedia.org/wiki/Atid_Ehad',
    })
    expect(party('K18', 'חי')?.wikipedia).toEqual({
      he: 'https://he.wikipedia.org/wiki/%D7%90%D7%A4%D7%A8%D7%99%D7%9D_%D7%A1%D7%A0%D7%94#%D7%99%D7%A9%D7%A8%D7%90%D7%9C_%D7%97%D7%96%D7%A7%D7%94',
      en: 'https://en.wikipedia.org/wiki/Efraim_Sneh',
    })
    expect(party('K18', 'צי')?.wikipedia).toEqual({
      he: 'https://he.wikipedia.org/wiki/%D7%91%D7%95%D7%A2%D7%96_%D7%98%D7%95%D7%A4%D7%95%D7%A8%D7%95%D7%91%D7%A1%D7%A7%D7%99',
      en: 'https://en.wikipedia.org/wiki/Boaz_Toporovsky',
    })
    for (const [electionId, ballotLetter] of [
      ['K18', 'ים'],
      ['K19', 'יק'],
      ['K24', 'ז'],
    ] as const) {
      expect(party(electionId, ballotLetter)?.wikipedia.he).toBe(
        'https://he.wikipedia.org/wiki/%D7%92%D7%93%D7%A2%D7%95%D7%9F_%D7%93%D7%95%D7%A8%D7%95%D7%9F',
      )
    }
    expect(party('K18', 'נפ')?.wikipedia.he).toBe(
      'https://he.wikipedia.org/wiki/%D7%99%D7%A2%D7%A7%D7%91_%D7%97%D7%A1%D7%93%D7%90%D7%99',
    )
    for (const [electionId, ballotLetter] of [
      ['K18', 'אר'],
      ['K19', 'ני'],
      ['K20', 'ני'],
    ] as const) {
      expect(party(electionId, ballotLetter)?.wikipedia.he).toBe(
        'https://he.wikipedia.org/wiki/%D7%99%D7%A8%D7%95%D7%9F_%D7%99%D7%93%D7%A2%D7%9F',
      )
    }
    expect(party('K17', 'ז')?.wikipedia.he).toBe(
      'https://he.wikipedia.org/wiki/%D7%99%D7%A9%D7%A8%D7%90%D7%9C_%D7%98%D7%95%D7%95%D7%99%D7%98%D7%95',
    )
    expect(party('K19', 'ץ')?.wikipedia.en).toBe(
      'https://en.wikipedia.org/wiki/Haim_Amsalem',
    )
    expect(party('K19', 'ז')?.wikipedia.he).toBe(
      'https://he.wikipedia.org/wiki/%D7%90%D7%9C%D7%93%D7%93_%D7%99%D7%A0%D7%99%D7%91',
    )
    expect(party('K19', 'זך')?.wikipedia).toEqual({
      he: 'https://he.wikipedia.org/wiki/%D7%92%D7%99%D7%9C_-_%D7%92%D7%9E%D7%9C%D7%90%D7%99_%D7%99%D7%A9%D7%A8%D7%90%D7%9C_%D7%9C%D7%9B%D7%A0%D7%A1%D7%AA',
      en: 'https://en.wikipedia.org/wiki/Dor_(political_party)',
    })
    expect(party('K20', 'נז')?.wikipedia.he).toBe(
      'https://he.wikipedia.org/wiki/%D7%A8%D7%95%D7%AA_%D7%A7%D7%95%D7%9C%D7%99%D7%90%D7%9F',
    )
    expect(party('K20', 'יז')?.wikipedia).toEqual(party('K19', 'הי')?.wikipedia)
    expect(party('K21', 'ן')?.wikipedia.he).toBe(
      'https://he.wikipedia.org/wiki/%D7%A1%D7%9E%D7%99%D7%95%D7%9F_%D7%92%D7%A8%D7%A4%D7%9E%D7%9F#%D7%A4%D7%A2%D7%99%D7%9C%D7%95%D7%AA_%D7%A4%D7%95%D7%9C%D7%99%D7%98%D7%99%D7%AA',
    )
    expect(party('K21', 'נץ')?.wikipedia).toEqual({
      he: 'https://he.wikipedia.org/wiki/%D7%92%D7%9C_%D7%94%D7%99%D7%A8%D7%A9',
      en: 'https://en.wikipedia.org/wiki/Gal_Hirsch',
    })
    expect(party('K21', 'י')?.wikipedia.he).toBe(
      'https://he.wikipedia.org/wiki/%D7%A2%D7%A8%D7%9F_%D7%A2%D7%A6%D7%99%D7%95%D7%9F',
    )
    expect(party('K21', 'קף')?.wikipedia).toEqual({
      he: 'https://he.wikipedia.org/wiki/%D7%90%D7%9C%D7%9C%D7%99_%D7%90%D7%93%D7%9E%D7%A1%D7%95',
      en: 'https://en.wikipedia.org/wiki/Alali_Adamso',
    })
    expect(party('K21', 'יץ')?.wikipedia).toEqual({
      he: 'https://he.wikipedia.org/wiki/%D7%97%D7%99%D7%99%D7%9D_%D7%93%D7%99%D7%99%D7%9F',
      en: 'https://en.wikipedia.org/wiki/Haim_Dayan',
    })
    expect(party('K22', 'רק')?.wikipedia).toEqual({
      he: 'https://he.wikipedia.org/wiki/%D7%A8%D7%95%D7%9F_%D7%A7%D7%95%D7%91%D7%99',
      en: 'https://en.wikipedia.org/wiki/Ron_Cobi',
    })
    const ihudBneiHaBritUrls = {
      he: 'https://he.wikipedia.org/wiki/%D7%90%D7%99%D7%97%D7%95%D7%93_%D7%91%D7%A0%D7%99_%D7%94%D7%91%D7%A8%D7%99%D7%AA',
      en: 'https://en.wikipedia.org/wiki/Ihud_Bnei_HaBrit',
    }
    for (const [electionId, ballotLetter] of [
      ['K21', 'ין'],
      ['K22', 'ינ'],
      ['K23', 'ינ'],
      ['K24', 'ינ'],
      ['K25', 'ינ'],
    ] as const) {
      expect(party(electionId, ballotLetter)?.wikipedia).toEqual(ihudBneiHaBritUrls)
    }
    for (const electionId of ['K24', 'K25']) {
      expect(party(electionId, 'יז')?.wikipedia).toEqual({
        he: 'https://he.wikipedia.org/wiki/%D7%99%D7%A8%D7%95%D7%9F_%D7%96%D7%9C%D7%99%D7%9B%D7%94',
        en: 'https://en.wikipedia.org/wiki/Yaron_Zelekha',
      })
    }
    expect(party('K24', 'ר')?.wikipedia.he).toBe(
      'https://he.wikipedia.org/wiki/%D7%90%D7%A8%D7%99%D7%94_%D7%90%D7%91%D7%A0%D7%99',
    )
    expect(party('K25', 'אצ')?.wikipedia).toEqual({
      he: 'https://he.wikipedia.org/wiki/%D7%90%D7%91%D7%99%D7%A8_%D7%A7%D7%90%D7%A8%D7%94',
      en: 'https://en.wikipedia.org/wiki/Abir_Kara',
    })
    expect(party('K25', 'נק')?.wikipedia.he).toBe(
      'https://he.wikipedia.org/wiki/%D7%A2%D7%9E%D7%95%D7%A1_%D7%93%D7%91_%D7%A1%D7%99%D7%9C%D7%91%D7%A8',
    )
    expect(party('K25', 'זנ')?.wikipedia.he).toBe(
      'https://he.wikipedia.org/wiki/%D7%91%D7%A0%D7%99_%D7%90%D7%9C%D7%91%D7%96',
    )
  })

  it('joins every result record to a stable feature ID', async () => {
    const catalog = AppCatalogSchema.parse(await readJson(resolve(dataRoot, 'catalog.json')))

    for (const mode of catalog.geographyModes) {
      await readAndValidateGeography(mode)
    }

    for (const election of catalog.elections) {
      for (const mode of catalog.geographyModes) {
        const geography = election.geographiesByMode[mode.id]
        const geometryIds = await readAndValidateGeography(geography)
        const payload = ElectionResultsSchema.parse(
          await readJson(resolve(dataRoot, election.resultUrls[mode.id])),
        )
        expect(payload.electionId).toBe(election.id)
        expect(payload.geographyMode).toBe(mode.id)
        if (mode.id === 'statistical-area') {
          expect(geography.vintage).toBe(election.statisticalAreaVintage)
        }
        expect(payload.envelope?.geographyType).toBe('envelope')
        expect(new Set(payload.records.map((record) => record.id)).size).toBe(payload.records.length)
        for (const record of payload.records) {
          expect(geometryIds.has(record.id), `${election.id}/${mode.id}/${record.id}`).toBe(true)
        }
        for (const hiddenId of payload.hiddenGeographyIds) {
          expect(geometryIds.has(hiddenId), `${election.id}/${mode.id}/${hiddenId}`).toBe(true)
          expect(payload.records.some((record) => record.id === hiddenId)).toBe(false)
        }
        if (mode.id === 'locality') {
          expect(payload.coverage.mappedActualVoterShare).toBe(1)
          expect(payload.coverage.pendingRows).toBe(0)
        }
      }
    }
  })

  it('renders reviewed one-area locality joins as exact statistical-area unions', async () => {
    const catalog = AppCatalogSchema.parse(await readJson(resolve(dataRoot, 'catalog.json')))
    const cases = [
      {
        electionId: 'K17',
        recordId: 'display:joined-locality:K17:385:1211',
        components: ['stat1995:385001', 'stat1995:1211001'],
        includedName: 'קדרים',
        actualVoters: 284,
      },
      {
        electionId: 'K17',
        recordId: 'display:joined-locality:K17:677:1257',
        components: ['stat1995:677001', 'stat1995:1257001'],
        includedName: 'חנתון',
        actualVoters: 385,
      },
      {
        electionId: 'K17',
        recordId: 'display:joined-locality:K17:1258:1225',
        components: ['stat1995:1258001', 'stat1995:1225001'],
        includedName: 'רביד',
        actualVoters: 194,
      },
      {
        electionId: 'K17',
        recordId: 'display:joined-locality:K17:1224:1306',
        components: ['stat1995:1224001', 'stat1995:1306001'],
        includedName: 'צור יגאל',
        actualVoters: 5463,
      },
      {
        electionId: 'K17',
        recordId: 'display:joined-locality:K17:195:1308',
        components: ['stat1995:195001', 'stat1995:1308001'],
        includedName: 'צורן',
        actualVoters: 6878,
      },
      {
        electionId: 'K18',
        recordId: 'display:joined-locality:K18:385:1211',
        components: ['stat2008:3850001', 'stat2008:12110001'],
        includedName: 'קדרים',
        actualVoters: 278,
      },
      {
        electionId: 'K18',
        recordId: 'display:joined-locality:K18:1258:1225',
        components: ['stat2008:12580001', 'stat2008:12250001'],
        includedName: 'רביד',
        actualVoters: 246,
      },
      {
        electionId: 'K19',
        recordId: 'display:joined-locality:K19:1258:1225',
        components: ['stat2011:12580001', 'stat2011:12250001'],
        includedName: 'רביד',
        actualVoters: 261,
      },
      {
        electionId: 'K20',
        recordId: 'display:joined-locality:K20:1258:1225',
        components: ['stat2011:12580001', 'stat2011:12250001'],
        includedName: 'רביד',
        actualVoters: 278,
      },
      {
        electionId: 'K21',
        recordId: 'display:joined-locality:K21:1258:1225',
        components: ['stat2011:12580001', 'stat2011:12250001'],
        includedName: 'רביד',
        actualVoters: 295,
      },
      {
        electionId: 'K22',
        recordId: 'display:joined-locality:K22:1258:1225',
        components: ['stat2011:12580001', 'stat2011:12250001'],
        includedName: 'רביד',
        actualVoters: 268,
      },
      {
        electionId: 'K23',
        recordId: 'display:joined-locality:K23:1258:1225',
        components: ['stat2011:12580001', 'stat2011:12250001'],
        includedName: 'רביד',
        actualVoters: 266,
      },
      {
        electionId: 'K24',
        recordId: 'display:joined-locality:K24:1258:1225',
        components: ['stat2011:12580001', 'stat2011:12250001'],
        includedName: 'רביד',
        actualVoters: 286,
      },
      {
        electionId: 'K25',
        recordId: 'display:joined-locality:K25:1258:1225',
        components: ['stat2011:12580001', 'stat2011:12250001'],
        includedName: 'רביד',
        actualVoters: 284,
      },
    ] as const

    for (const testCase of cases) {
      const election = catalog.elections.find((entry) => entry.id === testCase.electionId)
      expect(election, testCase.electionId).toBeDefined()
      const payload = ElectionResultsSchema.parse(
        await readJson(resolve(dataRoot, election?.resultUrls['statistical-area'] ?? '')),
      )
      const searchIndex = GeographySearchIndexSchema.parse(
        await readJson(resolve(dataRoot, election?.resultUrls.search ?? '')),
      )
      const record = payload.records.find((candidate) => candidate.id === testCase.recordId)
      const searchItem = searchIndex.items.find(
        (candidate) =>
          candidate.geographyMode === 'statistical-area' && candidate.id === testCase.recordId,
      )

      expect(record?.totals.actualVoters, testCase.recordId).toBe(testCase.actualVoters)
      expect(record?.notice, testCase.recordId).toBeUndefined()
      expect(searchItem?.aliases.he, testCase.recordId).toContain(testCase.includedName)
      for (const componentId of testCase.components) {
        expect(payload.hiddenGeographyIds, `${testCase.electionId}/${componentId}`).toContain(
          componentId,
        )
        expect(
          payload.records.some((candidate) => candidate.id === componentId),
          `${testCase.electionId}/${componentId}`,
        ).toBe(false)
      }
    }

    const k17 = catalog.elections.find((entry) => entry.id === 'K17')
    const k17Localities = ElectionResultsSchema.parse(
      await readJson(resolve(dataRoot, k17?.resultUrls.locality ?? '')),
    )
    const ravidComposite = k17Localities.records.find(
      (record) => record.id === 'composite:joined-k17-1258',
    )
    expect(ravidComposite?.includedNames?.he).toContain('רביד')
    expect(ravidComposite?.totals.actualVoters).toBe(194)
  })

  it('publishes zero-assignment result units as documented display-only totals', async () => {
    const catalog = AppCatalogSchema.parse(await readJson(resolve(dataRoot, 'catalog.json')))
    const expectedFallbackCounts: Record<string, number> = {
      K17: 52,
      K18: 36,
      K19: 33,
      K20: 33,
      K21: 32,
      K22: 32,
      K23: 32,
      K24: 32,
      K25: 32,
    }
    const expectedComponentFallbackIds = new Set([
      'municipality-component-fallback:1995:loc:494',
      'municipality-component-fallback:1995:loc:6000',
      'municipality-component-fallback:2008:loc:483',
      'municipality-component-fallback:2008:loc:490',
      'municipality-component-fallback:2008:loc:494',
      'municipality-component-fallback:2008:loc:516',
      'municipality-component-fallback:2008:loc:534',
      'municipality-component-fallback:2008:loc:6000',
      'municipality-component-fallback:2008:loc:628',
    ])

    for (const election of catalog.elections) {
      const statisticalPayload = ElectionResultsSchema.parse(
        await readJson(resolve(dataRoot, election.resultUrls['statistical-area'])),
      )
      const localityPayload = ElectionResultsSchema.parse(
        await readJson(resolve(dataRoot, election.resultUrls.locality)),
      )
      const geography = (await readJson(
        resolve(dataRoot, election.geographiesByMode['statistical-area'].geometryUrl),
      )) as {
        features: Array<{
          id?: string
          properties?: {
            geographyType?: string
            localityId?: string
            componentLocalityIds?: string[]
            fallbackNoticeType?: string
          }
        }>
      }
      const featuresById = new Map(geography.features.map((feature) => [feature.id, feature]))
      const localityRecordsById = new Map(
        localityPayload.records.map((record) => [record.id, record]),
      )
      const hiddenIds = new Set(statisticalPayload.hiddenGeographyIds)
      const fallbackRecords = statisticalPayload.records.filter(
        (record) => record.geographyType === 'municipality-fallback',
      )

      expect(fallbackRecords, election.id).toHaveLength(expectedFallbackCounts[election.id])
      for (const record of fallbackRecords) {
        const feature = featuresById.get(record.id)
        expect(feature?.properties?.geographyType, `${election.id}/${record.id}`).toBe(
          'municipality-fallback',
        )
        const noticeType = feature?.properties?.fallbackNoticeType
        expect(
          [
            'historical-geometry-proxy',
            'single-historical-area-exact',
            'multi-area-unsplit',
          ],
          `${election.id}/${record.id}`,
        ).toContain(noticeType)
        const expectedNoticeText =
          record.id.startsWith('municipality-component-fallback:')
            ? 'No ballot-to-statistical-area assignments'
            : noticeType === 'historical-geometry-proxy'
              ? 'does not appear as a separate area'
              : 'No ballot-to-statistical-area assignments'
        if (noticeType === 'single-historical-area-exact') {
          expect(record.notice, `${election.id}/${record.id}`).toBeUndefined()
        } else {
          expect(record.notice?.en, `${election.id}/${record.id}`).toContain(expectedNoticeText)
        }
        if (record.id.startsWith('municipality-component-fallback:')) {
          expect(expectedComponentFallbackIds.delete(record.id), record.id).toBe(true)
          expect(noticeType, record.id).toBe('multi-area-unsplit')
          expect(
            Object.values(record.partyVotes).reduce((sum, votes) => sum + votes, 0),
            record.id,
          ).toBe(record.totals.validVotes)
        } else {
          const localityRecord =
            localityRecordsById.get(record.localityId ?? '') ??
            localityPayload.records.find((candidate) => candidate.code === record.code)
          expect(localityRecord, `${election.id}/${record.localityId}`).toBeDefined()
          expect(record.totals, `${election.id}/${record.id}`).toEqual(localityRecord?.totals)
          expect(record.partyVotes, `${election.id}/${record.id}`).toEqual(
            localityRecord?.partyVotes,
          )
        }

        const componentLocalityIds = feature?.properties?.componentLocalityIds?.length
          ? feature.properties.componentLocalityIds
          : [record.localityId]
        for (const component of geography.features.filter(
          (candidate) =>
            candidate.properties?.geographyType === 'statistical-area' &&
            componentLocalityIds.includes(candidate.properties.localityId ?? null),
        )) {
          expect(hiddenIds.has(component.id ?? ''), `${election.id}/${component.id}`).toBe(true)
        }
      }
    }
    expect([...expectedComponentFallbackIds]).toEqual([])
  })

  it('publishes reviewed resolutions for the remaining populated empty areas', async () => {
    const catalog = AppCatalogSchema.parse(await readJson(resolve(dataRoot, 'catalog.json')))

    for (const electionId of ['K18', 'K20']) {
      const election = catalog.elections.find((entry) => entry.id === electionId)
      expect(election, electionId).toBeDefined()
      const searchIndex = GeographySearchIndexSchema.parse(
        await readJson(resolve(dataRoot, election?.resultUrls.search ?? '')),
      )
      const group = searchIndex.items.find(
        (item) => item.id === `display:reviewed-continuity:${electionId}:4201-4502`,
      )

      expect(group?.hasResults, electionId).toBe(true)
      expect(group?.aliases.en, electionId).toContain('EIN QINIYYE')
      expect(group?.notice?.en, electionId).toContain('No source supports a reliable internal split')
    }

    const populatedNoResultCases = [
      ['K20', 'stat2011:30002511', 'no eligible voters'],
      ['K20', 'stat2011:30002611', 'no eligible voters'],
      ['K20', 'stat2011:30002612', 'no eligible voters'],
      ['K20', 'stat2011:30002711', 'no eligible voters'],
      ['K20', 'stat2011:30002812', 'no eligible voters'],
      ['K21', 'stat2011:30002611', 'absent from the final register'],
      ['K22', 'stat2011:30002611', 'absent from the final register'],
      ['K23', 'stat2011:30002611', 'absent from the final register'],
    ] as const

    for (const [electionId, geographyId, expectedNotice] of populatedNoResultCases) {
      const election = catalog.elections.find((entry) => entry.id === electionId)
      expect(election, electionId).toBeDefined()
      const searchIndex = GeographySearchIndexSchema.parse(
        await readJson(resolve(dataRoot, election?.resultUrls.search ?? '')),
      )
      const area = searchIndex.items.find((item) => item.id === geographyId)

      expect(area?.hasResults, `${electionId}/${geographyId}`).toBe(false)
      expect(area?.notice?.en, `${electionId}/${geographyId}`).toContain(expectedNotice)
    }
  })

  it('keeps Maale Adumim historical election areas separate', async () => {
    const catalog = AppCatalogSchema.parse(await readJson(resolve(dataRoot, 'catalog.json')))
    const cases = [
      { electionId: 'K18', vintage: 2008, ballotCounts: [null, 4, 2] },
      { electionId: 'K20', vintage: 2011, ballotCounts: [1, 4, 6] },
    ]

    for (const testCase of cases) {
      const election = catalog.elections.find((entry) => entry.id === testCase.electionId)
      if (!election) {
        throw new Error(`Missing ${testCase.electionId} catalog entry`)
      }
      const geography = (await readJson(
        resolve(dataRoot, election.geographiesByMode['statistical-area'].geometryUrl),
      )) as { features: Array<{ id?: string }> }
      const payload = ElectionResultsSchema.parse(
        await readJson(resolve(dataRoot, election.resultUrls['statistical-area'])),
      )
      const geometryIds = new Set(geography.features.map((feature) => feature.id))
      const recordsById = new Map(payload.records.map((record) => [record.id, record]))

      for (const [index, expectedBallots] of testCase.ballotCounts.entries()) {
        const areaNumber = index + 1
        const id = `stat${testCase.vintage}:3616000${areaNumber}`
        expect(geometryIds.has(id), `${testCase.electionId}/${id}`).toBe(true)
        if (expectedBallots !== null) {
          expect(recordsById.get(id)?.totals.contributingKalpis, id).toBe(expectedBallots)
        }
      }
    }
  })

  it('retains neutral Israeli land footprints in locality geometry', async () => {
    const geometry = (await readJson(
      resolve(dataRoot, 'geographies', 'localities.geojson'),
    )) as {
      features: Array<{
        id?: string
        properties?: { displayMode?: string; nameEn?: string }
      }>
    }
    const featuresById = new Map(geometry.features.map((feature) => [feature.id, feature]))

    for (const id of ['loc:9971', 'loc:9936', 'loc:5568', 'loc:5569', 'loc:9920']) {
      const feature = featuresById.get(id)
      expect(feature, id).toBeDefined()
      expect(feature?.properties?.displayMode, id).toBe('polygon')
      expect(feature?.properties?.nameEn, id).not.toBe('nan')
    }
  })

  it('ships one shared lightweight land backdrop for both map modes', async () => {
    const catalog = AppCatalogSchema.parse(await readJson(resolve(dataRoot, 'catalog.json')))
    const backdropUrls = new Set(
      catalog.elections.flatMap((election) => [
        election.geographiesByMode['statistical-area'].backdropGeometryUrl,
        election.geographiesByMode.locality.backdropGeometryUrl,
      ]),
    )

    expect(backdropUrls.size).toBe(1)
    const backdropUrl = [...backdropUrls][0]
    expect(backdropUrl).toBe('geographies/statistical-area-backdrop.geojson')
    if (!backdropUrl) {
      throw new Error('Missing shared map backdrop URL')
    }
    expect(catalog.assets.some((asset) => asset.path === backdropUrl)).toBe(true)

    const backdrop = (await readJson(resolve(dataRoot, backdropUrl))) as {
      features: Array<{
        id?: string
        geometry?: { type?: string; coordinates?: unknown[] }
      }>
    }
    expect(backdrop.features).toHaveLength(1)
    expect(backdrop.features[0].geometry?.type).toMatch(/^(Multi)?Polygon$/)
    expect(backdrop.features[0].geometry?.coordinates?.length).toBeGreaterThan(0)

    const contextUrls = new Set(
      catalog.elections.flatMap((election) => [
        election.geographiesByMode['statistical-area'].mapContextGeometryUrl,
        election.geographiesByMode.locality.mapContextGeometryUrl,
      ]),
    )
    expect(contextUrls).toEqual(new Set(['geographies/map-context-footprint.geojson']))
    const contextUrl = [...contextUrls][0]
    if (!contextUrl) {
      throw new Error('Missing shared map-context URL')
    }
    expect(catalog.assets.some((asset) => asset.path === contextUrl)).toBe(true)

    const context = (await readJson(resolve(dataRoot, contextUrl))) as {
      features: Array<{
        properties?: { context_id?: string }
        geometry?: { type?: string; coordinates?: number[][][] }
      }>
    }
    expect(context.features).toHaveLength(1)
    expect(context.features[0].properties?.context_id).toBe(
      'israel-west-bank-statistical-land',
    )
    expect(context.features[0].geometry?.type).toBe('Polygon')
    const contextCoordinates = context.features[0].geometry?.coordinates
    if (!contextCoordinates) {
      throw new Error('Missing map-context coordinates')
    }
    expect(polygonContainsPoint(contextCoordinates, [35.18, 32.1])).toBe(true)
    expect(polygonContainsPoint(contextCoordinates, [35.2, 31.9])).toBe(true)
    expect(polygonContainsPoint(contextCoordinates, [34.95, 29.56])).toBe(true)
    expect(polygonContainsPoint(contextCoordinates, [34.45, 31.5])).toBe(false)
    expect(polygonContainsPoint(contextCoordinates, [34.7, 32])).toBe(false)
    expect(polygonContainsPoint(contextCoordinates, [34.92, 29.47])).toBe(false)
    expect(polygonContainsPoint(contextCoordinates, [35.63205, 33.2763])).toBe(false)
    expect(polygonContainsPoint(contextCoordinates, [35.633, 33.268])).toBe(true)

    const maskUrls = new Set(
      catalog.elections.flatMap((election) => [
        election.geographiesByMode['statistical-area'].basemapMaskGeometryUrl,
        election.geographiesByMode.locality.basemapMaskGeometryUrl,
      ]),
    )
    expect(maskUrls).toEqual(new Set(['geographies/basemap-outside-mask.geojson']))
    const maskUrl = [...maskUrls][0]
    if (!maskUrl) {
      throw new Error('Missing shared basemap mask URL')
    }
    expect(catalog.assets.some((asset) => asset.path === maskUrl)).toBe(true)

    const mask = (await readJson(resolve(dataRoot, maskUrl))) as {
      features: Array<{ properties?: { maskType?: string }; geometry?: { type?: string } }>
    }
    expect(mask.features).toHaveLength(1)
    expect(mask.features[0].properties?.maskType).toBe('outside-map-context')
  })

  it('uses detailed West Bank footprints while preserving reviewed proxy markers', async () => {
    const geometry = (await readJson(
      resolve(dataRoot, 'geographies', 'localities.geojson'),
    )) as {
      features: Array<{
        id?: string
        properties?: { displayMode?: string }
        geometry?: { type?: string }
      }>
    }
    const markers = (await readJson(
      resolve(dataRoot, 'geographies', 'locality-markers.geojson'),
    )) as {
      features: Array<{ id?: string; geometry?: { type?: string; coordinates?: unknown[] } }>
    }
    const featuresById = new Map(geometry.features.map((feature) => [feature.id, feature]))
    const markersById = new Map(markers.features.map((feature) => [feature.id, feature]))

    for (const id of [
      'loc:3488',
      'loc:3570',
      'loc:3605',
      'loc:3607',
      'loc:3649',
      'loc:3654',
      'loc:3784',
      'loc:3824',
      'loc:3782',
      'loc:3785',
      'loc:3786',
      'loc:3825',
      'composite:shaar-shomron',
    ]) {
      expect(featuresById.get(id)?.properties?.displayMode, id).toBe('polygon')
      expect(markersById.has(id), id).toBe(false)
    }

    for (const id of ['loc:1794']) {
      expect(featuresById.get(id)?.properties?.displayMode, id).toBe('marker')
      expect(markersById.get(id)?.geometry?.type, id).toBe('Point')
    }

    const yitavJoin = featuresById.get('composite:joined-k25-3607')
    expect(['Polygon', 'MultiPolygon']).toContain(yitavJoin?.geometry?.type)
    expect(markersById.has('composite:joined-k25-3607')).toBe(false)
  })

  it('uses one combined tribal marker and shows only result-bearing statistical markers', async () => {
    const catalog = AppCatalogSchema.parse(await readJson(resolve(dataRoot, 'catalog.json')))
    const tribalAreaIds = [
      'stat2011:9390001',
      'stat2011:9560001',
      'stat2011:9570001',
      'stat2011:9580001',
      'stat2011:9600001',
      'stat2011:9610001',
      'stat2011:9630001',
      'stat2011:9640001',
      'stat2011:9650001',
      'stat2011:9660001',
      'stat2011:9670001',
      'stat2011:9680001',
      'stat2011:9690001',
      'stat2011:9700001',
      'stat2011:9720001',
      'stat2011:9760001',
      'stat2011:9860001',
      'stat2011:10410001',
      'stat2011:11690001',
      'stat2011:11700001',
      'stat2011:12340001',
    ]
    const evacuatedGazaAreaIds = [
      'stat1995:5405001',
      'stat1995:5407001',
      'stat1995:5408001',
      'stat1995:5410001',
      'stat1995:5423001',
      'stat1995:5424001',
      'stat1995:5425001',
      'stat1995:5426001',
      'stat1995:5427001',
      'stat1995:5428001',
      'stat1995:5429001',
      'stat1995:5431001',
      'stat1995:5432001',
      'stat1995:5433001',
      'stat1995:5434001',
      'stat1995:5435001',
    ]
    const expectedActiveMarkers: Record<string, string[]> = {
      K17: ['custom:tribal_negev'],
      K18: ['custom:tribal_negev'],
      K19: ['custom:tribal_negev'],
      K20: ['custom:tribal_negev'],
      K21: ['custom:tribal_negev'],
      K22: ['custom:tribal_negev'],
      K23: ['custom:tribal_negev'],
      K24: ['custom:tribal_negev'],
      K25: ['custom:tribal_negev'],
    }

    for (const election of catalog.elections) {
      const asset = election.geographiesByMode['statistical-area']
      const geometry = (await readJson(resolve(dataRoot, asset.geometryUrl))) as {
        features: Array<{
          id?: string
          properties?: { displayMode?: string }
        }>
      }
      const markers = (await readJson(resolve(dataRoot, asset.markerGeometryUrl))) as {
        features: Array<{ id?: string }>
      }
      const payload = ElectionResultsSchema.parse(
        await readJson(resolve(dataRoot, election.resultUrls['statistical-area'])),
      )
      const featuresById = new Map(geometry.features.map((feature) => [feature.id, feature]))
      const markerIds = new Set(markers.features.map((feature) => feature.id))
      const resultIds = new Set(payload.records.map((record) => record.id))
      const activeMarkerIds = [...markerIds]
        .filter((id): id is string => Boolean(id))
        .filter((id) => resultIds.has(id) && !payload.hiddenGeographyIds.includes(id))
        .toSorted()

      expect(activeMarkerIds, election.id).toEqual(expectedActiveMarkers[election.id])
      expect(featuresById.get('custom:hebron')?.properties?.displayMode, election.id).toBe(
        'polygon',
      )
      expect(markerIds.has('custom:hebron'), election.id).toBe(false)
      expect(featuresById.get('custom:tribal_negev')?.properties?.displayMode, election.id).toBe(
        'marker',
      )
      expect(markerIds.has('custom:tribal_negev'), election.id).toBe(true)
      expect(resultIds.has('custom:tribal_negev'), election.id).toBe(true)

      if (Number(election.id.slice(1)) <= 18) {
        expect(resultIds.has('custom:hebron'), election.id).toBe(true)
      } else {
        expect(resultIds.has('custom:hebron'), election.id).toBe(false)
        expect(featuresById.get('stat2011:38230001')?.properties?.displayMode).toBe('polygon')
        expect(markerIds.has('stat2011:38230001'), election.id).toBe(false)
        for (const id of tribalAreaIds) {
          expect(featuresById.get(id)?.properties?.displayMode, `${election.id}/${id}`).toBe('marker')
          expect(markerIds.has(id), `${election.id}/${id}`).toBe(true)
          expect(resultIds.has(id), `${election.id}/${id}`).toBe(false)
          expect(payload.hiddenGeographyIds, `${election.id}/${id}`).toContain(id)
        }
      }
      if (election.id === 'K17') {
        for (const id of evacuatedGazaAreaIds) {
          expect(payload.hiddenGeographyIds, id).toContain(id)
          expect(resultIds.has(id), id).toBe(false)
        }
      }
    }
  })

  it('renders K17 Yehud area 8 on the reviewed historical component polygon', async () => {
    const catalog = AppCatalogSchema.parse(await readJson(resolve(dataRoot, 'catalog.json')))
    const election = catalog.elections.find((candidate) => candidate.id === 'K17')
    if (!election) {
      throw new Error('Missing K17 catalog entry')
    }
    const geometry = (await readJson(
      resolve(dataRoot, 'geographies', 'statistical-areas-1995.geojson'),
    )) as {
      features: Array<{
        id?: string
        properties?: { displayMode?: string }
        geometry?: { type?: string; coordinates?: unknown }
      }>
    }
    const markers = (await readJson(
      resolve(dataRoot, 'geographies', 'statistical-area-markers-1995.geojson'),
    )) as {
      features: Array<{ id?: string }>
    }
    const payload = ElectionResultsSchema.parse(
      await readJson(resolve(dataRoot, election.resultUrls['statistical-area'])),
    )
    const component = geometry.features.find((feature) => feature.id === 'stat1995:1062001')
    const target = geometry.features.find((feature) => feature.id === 'stat1995:9400008')
    const markerIds = new Set(markers.features.map((feature) => feature.id))
    const result = payload.records.find((record) => record.id === 'stat1995:9400008')

    expect(target?.properties?.displayMode).toBe('polygon')
    expect(target?.geometry?.type).toMatch(/Polygon/)
    expect(target?.geometry).toEqual(component?.geometry)
    expect(component?.properties?.displayMode).toBe('marker')
    expect(markerIds.has('stat1995:9400008')).toBe(false)
    expect(markerIds.has('stat1995:1062001')).toBe(true)
    expect(payload.hiddenGeographyIds).toContain('stat1995:1062001')
    expect(result?.names.he).toBe('יהוד · 8')
    expect(result?.names.en).toBe('Yehud · 8')
  })

  it('applies reviewed election-specific locality display rules', async () => {
    const catalog = AppCatalogSchema.parse(await readJson(resolve(dataRoot, 'catalog.json')))
    const geometry = (await readJson(
      resolve(dataRoot, 'geographies', 'localities.geojson'),
    )) as {
      features: Array<{
        id?: string
        properties?: { nameHe?: string }
      }>
    }
    const featuresById = new Map(geometry.features.map((feature) => [feature.id, feature]))

    expect(featuresById.get('loc:3620')?.properties?.nameHe).toBe('נערן')
    expect(featuresById.has('loc:3786')).toBe(true)
    expect(featuresById.has('loc:3825')).toBe(true)

    for (const election of catalog.elections) {
      const payload = ElectionResultsSchema.parse(
        await readJson(resolve(dataRoot, election.resultUrls.locality)),
      )
      expect(payload.hiddenGeographyIds, election.id).toContain('loc:3786')
      expect(payload.hiddenGeographyIds, election.id).toContain('loc:3825')

      const naranRecord = payload.records.find((record) => record.id === 'loc:3620')
      if (Number(election.id.slice(1)) <= 21) {
        expect(naranRecord?.names, election.id).toEqual({ he: 'נירן', en: 'NIRAN' })
      } else {
        expect(naranRecord, election.id).toBeUndefined()
      }
    }
  })

  it('shows reviewed joined-register unions in every source-supported election', async () => {
    const catalog = AppCatalogSchema.parse(await readJson(resolve(dataRoot, 'catalog.json')))
    const payloads = new Map(
      await Promise.all(
        catalog.elections.map(async (election) => [
          election.id,
          ElectionResultsSchema.parse(
            await readJson(resolve(dataRoot, election.resultUrls.locality)),
          ),
        ] as const),
      ),
    )

    for (const electionId of catalog.elections.map((election) => election.id)) {
      const payload = payloads.get(electionId)
      const composite = payload?.records.find(
        (record) => record.code === '567' && record.id.startsWith('composite:'),
      )
      expect(composite, electionId).toMatchObject({
        names: { he: 'צרעה', en: "ZOR'A" },
        includedNames: {
          he: ['דייר ראפאת', 'גבעת שמש'],
          en: ['DEIR RAFAT', "GIV'AT SHEMESH"],
        },
        code: '567',
      })
      for (const componentId of ['loc:567', 'loc:493', 'loc:566']) {
        expect(payload?.hiddenGeographyIds, `${electionId}/${componentId}`).toContain(componentId)
      }
    }

    const k21 = payloads.get('K21')
    expect(k21?.records.find((record) => record.id === 'composite:joined-k21-1172')).toMatchObject({
      names: { en: 'TUVAL' },
      includedNames: { en: ['PELEKH'] },
      code: '1172',
    })
    expect(k21?.hiddenGeographyIds).toContain('loc:1172')
    expect(k21?.hiddenGeographyIds).toContain('loc:1185')
    expect(k21?.records.some((record) => record.id === 'loc:567')).toBe(false)
  })

  it('keeps Ganne Modiin inside Modiin Illit through K20', async () => {
    const catalog = AppCatalogSchema.parse(await readJson(resolve(dataRoot, 'catalog.json')))

    for (const election of catalog.elections) {
      const localityPayload = ElectionResultsSchema.parse(
        await readJson(resolve(dataRoot, election.resultUrls.locality)),
      )
      const statisticalPayload = ElectionResultsSchema.parse(
        await readJson(resolve(dataRoot, election.resultUrls['statistical-area'])),
      )
      const historicalElection = Number(election.id.slice(1)) <= 20
      const compositeId = `composite:joined-${election.id.toLowerCase()}-3797`

      if (historicalElection) {
        expect(localityPayload.records.find((record) => record.id === compositeId)).toMatchObject({
          code: '3797',
          includedNames: { he: ['גני מודיעין'], en: ["GANNE MODI'IN"] },
        })
        expect(localityPayload.hiddenGeographyIds).toContain('loc:3797')
        expect(localityPayload.hiddenGeographyIds).toContain('loc:3823')
      } else {
        expect(localityPayload.records.some((record) => record.id === compositeId)).toBe(false)
      }

      if (election.id === 'K19' || election.id === 'K20') {
        expect(statisticalPayload.hiddenGeographyIds).toContain('stat2011:38230001')
        expect(statisticalPayload.hiddenGeographyIds).not.toContain('stat2011:37970001')
        expect(
          statisticalPayload.records.some((record) => record.id === 'stat2011:37970001'),
        ).toBe(true)
      } else if (Number(election.id.slice(1)) >= 21) {
        expect(statisticalPayload.hiddenGeographyIds).not.toContain('stat2011:38230001')
        expect(statisticalPayload.hiddenGeographyIds).toContain('stat2011:37970001')
        expect(
          statisticalPayload.records.some((record) => record.id === 'stat2011:38230001'),
        ).toBe(true)
        expect(
          statisticalPayload.records.some((record) => record.id === 'stat2011:37970001'),
        ).toBe(false)
      } else {
        expect(statisticalPayload.hiddenGeographyIds).not.toContain('stat2011:38230001')
        expect(statisticalPayload.hiddenGeographyIds).not.toContain('stat2011:37970001')
      }
    }
  })

  it('keeps reviewed party colors scoped away from reused ballot letters', async () => {
    const catalog = AppCatalogSchema.parse(await readJson(resolve(dataRoot, 'catalog.json')))
    const payloads = new Map(
      await Promise.all(
        catalog.elections.map(async (election) => [
          election.id,
          ElectionResultsSchema.parse(
            await readJson(resolve(dataRoot, election.resultUrls.locality)),
          ),
        ] as const),
      ),
    )
    const party = (electionId: string, ballotLetter: string) =>
      payloads.get(electionId)?.parties.find((candidate) => candidate.ballotLetter === ballotLetter)

    expect(party('K17', 'טב')).toMatchObject({ color: '#F4A261', colorStatus: 'reviewed' })
    expect(party('K17', 'זך')).toMatchObject({ color: '#8BC34A', colorStatus: 'reviewed' })
    expect(party('K17', 'עם')).toMatchObject({ color: '#0B5D3B', colorStatus: 'reviewed' })
    expect(party('K17', 'קנ')).toMatchObject({ color: '#00A651', colorStatus: 'reviewed' })
    expect(party('K17', 'רק')).toMatchObject({ color: '#00A651', colorStatus: 'reviewed' })
    expect(party('K17', 'פ')).toMatchObject({ color: '#2455A4', colorStatus: 'reviewed' })
    expect(party('K17', 'חץ')).toMatchObject({ color: '#7B2CBF', colorStatus: 'reviewed' })
    expect(party('K17', 'ק')).toMatchObject({ color: '#8B1E1E', colorStatus: 'reviewed' })
    expect(party('K17', 'קז')).toMatchObject({ color: '#202020', colorStatus: 'reviewed' })
    expect(party('K17', 'נץ')).toMatchObject({ color: '#F5B800', colorStatus: 'reviewed' })
    expect(party('K17', 'ה')).toMatchObject({ color: '#4B5563', colorStatus: 'reviewed' })
    expect(party('K19', 'ו')).toMatchObject({ color: '#8B1E1E', colorStatus: 'reviewed' })
    expect(party('K23', 'נץ')).toMatchObject({ color: '#F5B800', colorStatus: 'reviewed' })
    expect(party('K25', 'ל')).toMatchObject({ color: '#5DADE2', colorStatus: 'reviewed' })
    expect(party('K25', 'ד')).toMatchObject({ color: '#EE9140', colorStatus: 'reviewed' })
    expect(party('K25', 'ת')).toMatchObject({ color: '#00A651', colorStatus: 'reviewed' })

    const newlyReviewedColors = [
      ['K17', 'ז', '#8B1E1E'],
      ['K17', 'כץ', '#7B2CBF'],
      ['K17', 'פכ', '#8B1E1E'],
      ['K17', 'פץ', '#8B1E1E'],
      ['K17', 'ף', '#5DADE2'],
      ['K17', 'קפ', '#0B5D3B'],
      ['K18', 'ב', '#B08D00'],
      ['K18', 'אר', '#4B5563'],
      ['K18', 'ה', '#00A651'],
      ['K18', 'חי', '#4B5563'],
      ['K18', 'ים', '#4B5563'],
      ['K18', 'ינ', '#4B5563'],
      ['K18', 'יק', '#00A651'],
      ['K18', 'עם', '#0B5D3B'],
      ['K18', 'נ', '#5DADE2'],
      ['K18', 'נפ', '#4B5563'],
      ['K18', 'נץ', '#4B5563'],
      ['K18', 'נר', '#8B1E1E'],
      ['K18', 'פ', '#4B5563'],
      ['K18', 'פי', '#4B5563'],
      ['K18', 'פק', '#202020'],
      ['K18', 'צי', '#B54E12'],
      ['K18', 'ק', '#8B1E1E'],
      ['K18', 'קפ', '#8B1E1E'],
      ['K18', 'קץ', '#5DADE2'],
      ['K18', 'ץ', '#7B2CBF'],
      ['K19', 'טב', '#B08D00'],
      ['K19', 'הי', '#4B5563'],
      ['K19', 'הפ', '#4B5563'],
      ['K19', 'הק', '#20A4A8'],
      ['K19', 'ז', '#C62828'],
      ['K19', 'זך', '#8BC34A'],
      ['K19', 'יק', '#4B5563'],
      ['K19', 'נ', '#4B5563'],
      ['K19', 'ני', '#4B5563'],
      ['K19', 'נק', '#5DADE2'],
      ['K19', 'נץ', '#F5B800'],
      ['K19', 'עם', '#0B5D3B'],
      ['K19', 'פ', '#202020'],
      ['K19', 'פה', '#B54E12'],
      ['K19', 'פז', '#4B5563'],
      ['K19', 'פי', '#F4D96B'],
      ['K19', 'פנ', '#4B5563'],
      ['K19', 'פץ', '#202020'],
      ['K19', 'ץ', '#202020'],
      ['K19', 'צפ', '#D94888'],
      ['K19', 'צק', '#8B1E1E'],
      ['K19', 'ק', '#8B1E1E'],
      ['K20', 'ודעם', '#20A4A8'],
      ['K20', 'ז', '#F4D96B'],
      ['K20', 'זך', '#4B5563'],
      ['K20', 'זץ', '#4B5563'],
      ['K20', 'טב', '#B08D00'],
      ['K20', 'י', '#4B5563'],
      ['K20', 'יז', '#4B5563'],
      ['K20', 'יץ', '#20A4A8'],
      ['K20', 'נז', '#202020'],
      ['K20', 'ני', '#4B5563'],
      ['K20', 'נץ', '#4B5563'],
      ['K20', 'כ', '#7B2CBF'],
      ['K20', 'ע', '#0B5D3B'],
      ['K20', 'פה', '#B54E12'],
      ['K20', 'ף', '#202020'],
      ['K20', 'ףץ', '#202020'],
      ['K20', 'קץ', '#202020'],
      ['K21', 'דעם', '#0B5D3B'],
      ['K21', 'ום', '#8B1E1E'],
      ['K21', 'ז', '#F5B800'],
      ['K21', 'זי', '#8BC34A'],
      ['K21', 'זך', '#4B5563'],
      ['K21', 'זץ', '#7B2CBF'],
      ['K21', 'טב', '#F5B800'],
      ['K21', 'כ', '#7B2CBF'],
      ['K21', 'נ', '#B08D00'],
      ['K21', 'נץ', '#2455A4'],
      ['K21', 'נר', '#7B2CBF'],
      ['K21', 'ןנ', '#4B5563'],
      ['K21', 'פה', '#7B2CBF'],
      ['K21', 'ףז', '#202020'],
      ['K21', 'ףץ', '#202020'],
      ['K21', 'צק', '#8B1E1E'],
      ['K21', 'ץ', '#8B1E1E'],
      ['K21', 'קי', '#F5B800'],
      ['K21', 'ר', '#0B5D3B'],
      ['K22', 'ודעם', '#20A4A8'],
      ['K22', 'ז', '#F4D96B'],
      ['K22', 'זכ', '#4B5563'],
      ['K22', 'זץ', '#7B2CBF'],
      ['K22', 'טב', '#B08D00'],
      ['K22', 'יז', '#C62828'],
      ['K22', 'י', '#4B5563'],
      ['K22', 'כף', '#F5B800'],
      ['K22', 'כי', '#8B1E1E'],
      ['K22', 'נ', '#5DADE2'],
      ['K22', 'פה', '#7B2CBF'],
      ['K22', 'ףז', '#202020'],
      ['K22', 'ץ', '#8B1E1E'],
      ['K22', 'רק', '#2455A4'],
      ['K23', 'ודעם', '#20A4A8'],
      ['K23', 'ז', '#F4D96B'],
      ['K23', 'טב', '#B08D00'],
      ['K23', 'יז', '#C62828'],
      ['K23', 'יר', '#4B5563'],
      ['K23', 'נ', '#D94888'],
      ['K23', 'נז', '#4B5563'],
      ['K23', 'נץ', '#F5B800'],
      ['K23', 'נק', '#5DADE2'],
      ['K23', 'פה', '#7B2CBF'],
      ['K23', 'ףז', '#202020'],
      ['K23', 'ץ', '#8B1E1E'],
      ['K23', 'קץ', '#F5B800'],
      ['K24', 'ב', '#B08D00'],
      ['K24', 'ודעם', '#20A4A8'],
      ['K24', 'ז', '#4B5563'],
      ['K24', 'זץ', '#7B2CBF'],
      ['K24', 'ט', '#F5B800'],
      ['K24', 'י', '#8BC34A'],
      ['K24', 'יז', '#F4D96B'],
      ['K24', 'יר', '#4B5563'],
      ['K24', 'כן', '#7B2CBF'],
      ['K24', 'עם', '#0B5D3B'],
      ['K24', 'פה', '#B54E12'],
      ['K24', 'ףז', '#202020'],
      ['K24', 'צי', '#F4D96B'],
      ['K24', 'צכ', '#0B5D3B'],
      ['K24', 'צף', '#7B2CBF'],
      ['K24', 'ץ', '#8B1E1E'],
      ['K24', 'קץ', '#F5B800'],
      ['K24', 'ר', '#202020'],
      ['K24', 'רף', '#202020'],
      ['K24', 'ת', '#173F7A'],
      ['K25', 'אצ', '#F4D96B'],
      ['K25', 'ב', '#B08D00'],
      ['K25', 'ום', '#8B1E1E'],
      ['K25', 'זנ', '#4B5563'],
      ['K25', 'זץ', '#7B2CBF'],
      ['K25', 'ט', '#F5B800'],
      ['K25', 'יז', '#F4D96B'],
      ['K25', 'כן', '#7B2CBF'],
      ['K25', 'עם', '#0B5D3B'],
      ['K25', 'פה', '#B54E12'],
      ['K25', 'ף', '#202020'],
      ['K25', 'ק', '#00A651'],
      ['K25', 'נק', '#00A651'],
      ['K25', 'נץ', '#F4D96B'],
      ['K25', 'רז', '#7B2CBF'],
      ['K25', 'ץ', '#4B5563'],
    ] as const
    for (const [electionId, ballotLetter, color] of newlyReviewedColors) {
      expect(party(electionId, ballotLetter)).toMatchObject({
        color,
        colorStatus: 'reviewed',
      })
    }

    const grayIdsByElection = {
      K21: ['ן', 'ק', 'י', 'נז', 'קף', 'ףי', 'קן', 'ךק', 'ףך', 'יץ', 'ןך', 'ףנ', 'ןנ', 'ץי', 'יז', 'ין', 'זך'],
      K22: ['צ', 'נך', 'ק', 'קץ', 'קך', 'זכ', 'צן', 'ינ', 'יף', 'יק', 'י'],
      K23: ['ק', 'כן', 'ינ', 'קך', 'נז', 'כ', 'קי', 'יק', 'ני', 'י', 'יר', 'יף', 'זך'],
      K24: ['כך', 'רנ', 'קך', 'נ', 'ק', 'כ', 'יק', 'ני', 'ינ', 'ז', 'קי', 'יר', 'נר', 'יף'],
      K25: ['קץ', 'צ', 'ני', 'קנ', 'י', 'קך', 'ץ', 'ך', 'ז', 'קי', 'יק', 'נז', 'נר', 'יץ', 'נף', 'ינ', 'זך', 'זנ'],
    } as const
    for (const [electionId, ballotLetters] of Object.entries(grayIdsByElection)) {
      for (const ballotLetter of ballotLetters) {
        expect(party(electionId, ballotLetter), `${electionId}/${ballotLetter}`).toMatchObject({
          color: '#4B5563',
          colorStatus: 'reviewed',
        })
      }
    }

    for (const [electionId, payload] of payloads) {
      expect(
        payload.parties.every((candidate) => candidate.colorStatus === 'reviewed'),
        electionId,
      ).toBe(true)
    }

    const k17DarkGrayNames = new Set(
      payloads
        .get('K17')
        ?.parties.filter((candidate) => candidate.color === '#4B5563')
        .map((candidate) => candidate.names.he),
    )
    expect([...k17DarkGrayNames].toSorted()).toEqual(
      [
        'ברית עולם',
        'הציונות החדשה',
        'לב',
      ].toSorted(),
    )
    for (const [electionId, payload] of payloads) {
      if (electionId === 'K17') {
        continue
      }
      for (const candidate of payload.parties.filter((entry) =>
        k17DarkGrayNames.has(entry.names.he),
      )) {
        expect(candidate, `${electionId}/${candidate.names.he}`).toMatchObject({
          color: '#4B5563',
          colorStatus: 'reviewed',
        })
      }
    }

    expect(
      payloads.get('K18')?.parties.every((candidate) => candidate.colorStatus === 'reviewed'),
    ).toBe(true)
    expect(
      payloads.get('K19')?.parties.every((candidate) => candidate.colorStatus === 'reviewed'),
    ).toBe(true)
    expect(
      payloads.get('K20')?.parties.every((candidate) => candidate.colorStatus === 'reviewed'),
    ).toBe(true)
    const k18DarkGrayNames = new Set(
      payloads
        .get('K18')
        ?.parties.filter((candidate) => candidate.color === '#4B5563')
        .map((candidate) => candidate.names.he),
    )
    expect([...k18DarkGrayNames].toSorted()).toEqual(
      [
        'אור בראשון',
        'אחריות',
        'ברית עולם',
        'הישראלים',
        'ישראל חזקה',
        'כח להשפיע',
        'לב',
        'לזוז',
      ].toSorted(),
    )
    for (const [electionId, payload] of payloads) {
      if (Number(electionId.slice(1)) <= 18) {
        continue
      }
      for (const candidate of payload.parties.filter((entry) =>
        k18DarkGrayNames.has(entry.names.he),
      )) {
        expect(candidate, `${electionId}/${candidate.names.he}`).toMatchObject({
          color: '#4B5563',
          colorStatus: 'reviewed',
        })
      }
    }

  })

  it('applies the reviewed K17-K25 Hebrew display names', async () => {
    const catalog = AppCatalogSchema.parse(await readJson(resolve(dataRoot, 'catalog.json')))
    const payloadFor = async (electionId: string) => {
      const election = catalog.elections.find((candidate) => candidate.id === electionId)
      if (!election) {
        throw new Error(`Missing ${electionId} in generated catalog`)
      }
      return ElectionResultsSchema.parse(
        await readJson(resolve(dataRoot, election.resultUrls.locality)),
      )
    }
    const k17 = await payloadFor('K17')
    const k18 = await payloadFor('K18')
    const k19 = await payloadFor('K19')
    const laterPayloads = {
      K20: await payloadFor('K20'),
      K21: await payloadFor('K21'),
      K22: await payloadFor('K22'),
      K23: await payloadFor('K23'),
      K24: await payloadFor('K24'),
      K25: await payloadFor('K25'),
    }
    const expectedK17 = {
      אמת: 'העבודה-מימד', ג: 'יהדות התורה', ד: 'בל"ד', ה: 'ברית עולם', ו: 'חד"ש',
      ז: 'לחם', זה: 'עתיד אחד', זך: 'גיל', חץ: 'חץ', טב: 'האיחוד הלאומי-מפד"ל',
      יש: 'שינוי', כ: 'חזית יהודית לאומית', כן: 'קדימה', כץ: 'צומת', ל: 'ישראל ביתנו',
      מחל: 'הליכוד', מרצ: 'מרצ', נץ: 'חרות', עם: 'רע"מ-תע"ל', פ: 'תפנית', פז: 'לב',
      פכ: 'עוז לעניים', פץ: 'כוח הכסף', ף: 'מתקדמת', צה: 'הציונות החדשה', ק: 'דע"ם',
      קז: 'רע"ש', קנ: 'עלה ירוק', קפ: 'המפלגה הלאומית הערבית', רק: 'הירוקים', שס: 'ש"ס',
    }
    const expectedK18 = {
      אמת: 'העבודה', אר: 'אור בראשון', ב: 'הבית היהודי', ג: 'יהדות התורה', ד: 'בל"ד',
      ה: 'המפלגה הירוקה', ו: 'חד"ש', זך: 'גיל', חי: 'ישראל חזקה', ט: 'האיחוד הלאומי',
      ים: 'הישראלים', ינ: 'לב', יק: 'ניצולי השואה', כן: 'קדימה', ל: 'ישראל ביתנו',
      מחל: 'הליכוד-אח"י', מרצ: 'מרצ', נ: 'עלי"ה', נפ: 'אחריות', נץ: 'לזוז',
      נר: 'לוחמי חברה', עם: 'רע"מ-תע"ל', פ: 'כח להשפיע', פי: 'ברית עולם', פק: 'רע"ש',
      ץ: 'צומת', צי: 'צבר', ק: 'דע"ם', קנ: 'עלה ירוק', קפ: 'כוח הכסף', קץ: 'מתקדמת',
      רק: 'הירוקים', שס: 'ש"ס',
    }
    const expectedK19 = {
      אמת: 'העבודה', ד: 'בל"ד', הי: 'מורשת אבות', ו: 'חד"ש', ז: 'ארץ חדשה',
      זך: 'דור בוני הארץ', כן: 'קדימה', ני: 'אור בראשון', נק: 'מתקדמת',
      פ: 'הפיראטים', פז: 'כח להשפיע', פי: 'מפלגת כלכלה', צק: 'צדק חברתי',
      ק: 'דע"ם', קנ: 'עלה ירוק', רק: 'הירוקים', שס: 'ש"ס',
    }
    const expectedLaterNames = {
      K20: {
        ז: 'מפלגת כלכלה', זך: 'דמוקראטורה', יז: 'מנהיגות חברתית', יץ: "אלאמל לתג'ייר - התקווה לשינוי",
        נז: 'ובזכותן', נץ: 'פרח', ף: 'הפיראטים', קנ: 'עלה ירוק', קץ: 'יחד - העם איתנו',
        רק: 'הירוקים', שס: 'ש"ס',
      },
      K21: {
        אמת: 'העבודה', ז: 'זהות', זץ: 'צומת', י: 'ישר', יז: 'הגוש התנ"כי', ין: 'איחוד בני הברית',
        יץ: 'אחריות למייסדים', נץ: 'מגן', נר: 'גשר', ן: 'בט"ח', ןנ: 'מנהיגות חברתית',
        פה: 'כחול לבן', ףז: 'הפיראטים', צק: 'צדק חברתי', ץ: 'כלכלה ירוקה', ץי: 'אני ואתה',
        ק: 'צדק לכל', ר: 'הרשימה הערבית', שס: 'ש"ס',
      },
      K22: {
        ז: 'עוצמה כלכלית', זכ: 'דמוקראטורה', זץ: 'צומת', י: 'מנהיגות חברתית', יז: 'אדום לבן',
        ינ: 'התנועה הליברלית הנוצרית',
        יק: 'הגוש התנ"כי', כי: 'האחדות העממית - אלוחדה אלשעביה', כף: 'עוצמה יהודית',
        נ: 'מתקדמת', פה: 'כחול לבן', ףז: 'הפיראטים', צ: 'צדק', ץ: 'דע"ם', קך: 'סדר חדש',
        קץ: 'קמ"ה', רק: 'הימין החילוני', שס: 'ש"ס',
      },
      K23: {
        ז: 'עוצמה ליברלית', י: 'החזון', יז: 'אדום לבן', ינ: 'איחוד הברית והשותפות', יף: 'כבוד האדם', יק: 'הגוש התנ"כי',
        יר: 'מנהיגות חברתית', כ: 'הלב היהודי', כן: 'אני ואתה', נז: 'הכח להשפיע', ני: 'קמ"ה',
        נץ: 'עוצמה יהודית', נק: 'מתקדמת', פה: 'כחול לבן', ףז: 'הפיראטים', ץ: 'דע"ם',
        ק: 'ישראליסט', קי: 'שמע', קך: 'סדר חדש', קץ: 'משפט צדק', שס: 'ש"ס',
      },
      K24: {
        אמת: 'העבודה', ג: 'יהדות התורה', זץ: 'צומת', ט: 'הציונות הדתית', יז: 'הכלכלית החדשה',
        ינ: 'ברית השותפות', יף: 'כבוד האדם', יק: 'הגוש התנ"כי', יר: 'מנהיגות חברתית',
        כ: 'הלב היהודי', כך: 'אני ואתה', כן: 'כחול לבן', נ: 'קמ"ה', ני: 'עולם חדש',
        נר: 'אנחנו', עם: 'רע"מ', ףז: 'הפיראטים', צכ: 'מד"ע', צף: 'חץ', ץ: 'דע"ם',
        ק: 'הבלתי אפשרי, אפשרי', קי: 'שמע', קך: 'סדר חדש', קץ: 'משפט צדק', ר: 'רפא', שס: 'ש"ס',
      },
      K25: {
        אמת: 'העבודה', אצ: 'חופש כלכלי', ג: 'יהדות התורה', ד: 'בל"ד', ז: 'שחר כוח חברתי',
        זך: 'קמ"ה', זנ: 'כח להשפיע', זץ: 'צומת', ט: 'הציונות הדתית - עוצמה יהודית',
        י: 'ישראל חופשית דמוקרטית', יז: 'הכלכלית החדשה', יק: 'הגוש התנ"כי', נז: 'כבוד האדם',
        ני: 'נתיב', נף: 'שמע', נץ: 'העצמאים החדשים', נק: 'יש כיוון', נר: 'אנחנו', עם: 'רע"מ',
        ף: 'הפיראטים', צ: 'צעירים בוערים', ץ: 'מנהיגות חברתית', קי: 'הלב היהודי',
        קך: 'סדר חדש', קנ: 'כל קול קובע', רז: 'שלושים ארבעים', שס: 'ש"ס', ת: 'עלה ירוק',
      },
    }

    expect(k17.parties).toHaveLength(31)
    expect(k18.parties).toHaveLength(33)
    for (const [partyId, nameHe] of Object.entries(expectedK17)) {
      expect(k17.parties.find((party) => party.id === partyId)?.names.he, `K17/${partyId}`).toBe(nameHe)
    }
    for (const [partyId, nameHe] of Object.entries(expectedK18)) {
      expect(k18.parties.find((party) => party.id === partyId)?.names.he, `K18/${partyId}`).toBe(nameHe)
    }
    for (const [partyId, nameHe] of Object.entries(expectedK19)) {
      expect(k19.parties.find((party) => party.id === partyId)?.names.he, `K19/${partyId}`).toBe(nameHe)
    }
    for (const electionId of Object.keys(expectedLaterNames) as Array<keyof typeof expectedLaterNames>) {
      const expectedNames = expectedLaterNames[electionId]
      for (const [partyId, nameHe] of Object.entries(expectedNames)) {
        expect(
          laterPayloads[electionId].parties.find((party) => party.id === partyId)?.names.he,
          `${electionId}/${partyId}`,
        ).toBe(nameHe)
      }
    }
    expect(k18.parties.some((party) => party.id === 'פח')).toBe(false)
    expect(k19.parties.some((party) => party.id === 'זה')).toBe(false)
    expect(k19.parties.some((party) => party.id === 'פך')).toBe(false)
    expect(catalog.source.resultColumnExclusions).toContainEqual({
      electionId: 'K18',
      column: 'פח',
      reason: expect.stringContaining('did not run'),
    })
    for (const column of ['זה', 'פך']) {
      expect(catalog.source.resultColumnExclusions).toContainEqual({
        electionId: 'K19',
        column,
        reason: expect.stringContaining('did not run'),
      })
    }
    const laterExclusions = {
      K20: ['יך'],
      K21: ['זנ', 'נך', 'ץז'],
      K22: ['זן', 'כ', 'נץ'],
      K23: ['זץ'],
      K24: ['רק'],
    }
    for (const electionId of Object.keys(laterExclusions) as Array<keyof typeof laterExclusions>) {
      const columns = laterExclusions[electionId]
      for (const column of columns) {
        expect(laterPayloads[electionId].parties.some((party) => party.id === column)).toBe(false)
        expect(catalog.source.resultColumnExclusions).toContainEqual({
          electionId,
          column,
          reason: expect.stringContaining('did not run'),
        })
      }
    }
    expect(
      [k17, k18, k19, ...Object.values(laterPayloads)]
        .reduce((total, payload) => total + payload.parties.length, 0),
    ).toBe(297)
  })

  it('publishes recovered K17 turnout while keeping envelope turnout unavailable', async () => {
    const catalog = AppCatalogSchema.parse(await readJson(resolve(dataRoot, 'catalog.json')))
    const payloadFor = async (electionId: string) => {
      const election = catalog.elections.find((candidate) => candidate.id === electionId)
      if (!election) {
        throw new Error(`Missing ${electionId} in generated catalog`)
      }
      return ElectionResultsSchema.parse(
        await readJson(resolve(dataRoot, election.resultUrls.locality)),
      )
    }
    const k17 = await payloadFor('K17')
    const k18 = await payloadFor('K18')

    expect(k17.records.length).toBeGreaterThan(0)
    expect(
      k17.records.every(
        (record) =>
          record.totals.eligibleVoters >= record.totals.actualVoters &&
          record.totals.turnout !== null,
      ),
    ).toBe(true)
    expect(k17.envelope?.totals.turnout).toBeNull()
    expect(k18.records.some((record) => record.totals.turnout !== null)).toBe(true)
  })

  it('publishes nationwide polling-group placement only where evidence qualifies', async () => {
    const catalog = AppCatalogSchema.parse(await readJson(resolve(dataRoot, 'catalog.json')))
    const expectedRepresentativeCounts: Record<string, number> = {
      K21: 92,
      K22: 429,
      K23: 426,
      K24: 382,
      K25: 399,
    }
    const expectedExactClosedCounts: Record<string, number> = {
      K21: 134,
      K22: 4,
      K23: 2,
      K24: 204,
      K25: 192,
    }

    for (const election of catalog.elections) {
      const payload = ElectionResultsSchema.parse(
        await readJson(resolve(dataRoot, election.resultUrls['statistical-area'])),
      )
      const pollingGroupRecords = payload.records.filter(
        (record) =>
          record.id.startsWith('display:polling-group:') ||
          record.id.startsWith('display:polling-partition:') ||
          record.id.startsWith('display:polling-continuity-partition:') ||
          record.id.startsWith('display:polling-exact:') ||
          record.id.startsWith('display:polling-topology:') ||
          record.id.startsWith('display:reviewed-set:') ||
          record.id.startsWith('display:reviewed-closed:'),
      )
      const representativeRecords = pollingGroupRecords.filter((record) => record.notice)
      const exactClosedRecords = pollingGroupRecords.filter((record) => !record.notice)
      const fallbackRecords = payload.records.filter((record) =>
        record.id.startsWith('display:polling-network-fallback:'),
      )
      expect(representativeRecords, election.id).toHaveLength(
        expectedRepresentativeCounts[election.id] ?? 0,
      )
      expect(exactClosedRecords, election.id).toHaveLength(
        expectedExactClosedCounts[election.id] ?? 0,
      )
      expect(fallbackRecords, election.id).toHaveLength(
        0,
      )
      for (const record of representativeRecords) {
        expect(record.geographyType, record.id).toBe('custom')
        expect(record.notice?.en, record.id).toContain(
          'Votes cannot be assigned to this area precisely.',
        )
        expect(record.names.en, record.id).toMatch(/ · \d/)
        expect(record.names.en, record.id).not.toContain('Polling group')
      }
      for (const record of exactClosedRecords) {
        expect(record.geographyType, record.id).toBe('custom')
        expect(record.notice, record.id).toBeUndefined()
        expect(record.names.en, record.id).toMatch(/ · \d/)
        expect(record.names.en, record.id).not.toContain('Polling group')
      }
      for (const record of fallbackRecords) {
        expect(record.geographyType, record.id).toBe('custom')
        expect(record.notice?.en, record.id).toContain('exact sum')
        expect(record.names.en, record.id).toMatch(/ · \d/)
        expect(record.names.en, record.id).not.toContain('Statistical areas')
      }
    }

    const k24Catalog = catalog.elections.find((election) => election.id === 'K24')
    if (!k24Catalog) {
      throw new Error('Missing K24 catalog entry')
    }
    const k24Payload = ElectionResultsSchema.parse(
      await readJson(resolve(dataRoot, k24Catalog.resultUrls['statistical-area'])),
    )
    expect(
      k24Payload.records.find(
        (record) => record.id === 'display:polling-partition:K24:1031:aggregate:1:1',
      )?.notice?.en,
    ).toContain('This result may also include votes from areas 4.')
    expect(
      k24Payload.records.find(
        (record) => record.id === 'display:polling-partition:K24:1034:aggregate:1:3',
      )?.notice?.en,
    ).toContain('This result may include votes from areas 2, 5.')
    const k24AraraClosedDisplay = k24Payload.records.find(
      (record) => record.id === 'display:reviewed-closed:K24:1192:1-3',
    )
    expect(k24AraraClosedDisplay).toMatchObject({
      names: { he: expect.stringContaining('1, 3') },
      totals: {
        contributingRows: 14,
        contributingKalpis: 14,
        eligibleVoters: 7_174,
        actualVoters: 3_198,
        validVotes: 3_178,
      },
    })
    expect(k24AraraClosedDisplay?.notice).toBeUndefined()

    const k22Catalog = catalog.elections.find((election) => election.id === 'K22')
    if (!k22Catalog) {
      throw new Error('Missing K22 catalog entry')
    }
    const k22Payload = ElectionResultsSchema.parse(
      await readJson(resolve(dataRoot, k22Catalog.resultUrls['statistical-area'])),
    )
    const northTelAvivClosedDisplay = k22Payload.records.find(
      (record) => record.id === 'display:reviewed-closed:K22:5000:313-315',
    )
    expect(northTelAvivClosedDisplay).toMatchObject({
      names: { he: expect.stringContaining('313, 314, 315') },
      totals: {
        eligibleVoters: 14_024,
        actualVoters: 8_723,
        validVotes: 8_703,
      },
    })
    expect(northTelAvivClosedDisplay?.notice).toBeUndefined()

    const k21Catalog = catalog.elections.find((election) => election.id === 'K21')
    if (!k21Catalog) {
      throw new Error('Missing K21 catalog entry')
    }
    const k21Payload = ElectionResultsSchema.parse(
      await readJson(resolve(dataRoot, k21Catalog.resultUrls['statistical-area'])),
    )
    const southTelAvivDisplay = k21Payload.records.find(
      (record) => record.id === 'display:polling-topology:K21:5000:aggregate:14:1',
    )
    expect(southTelAvivDisplay).toMatchObject({
      names: { he: expect.stringContaining('811, 812, 813') },
      totals: {
        contributingRows: 14,
        contributingKalpis: 14,
        eligibleVoters: 8_887,
        actualVoters: 5_352,
        validVotes: 5_332,
      },
    })
    expect(southTelAvivDisplay?.notice).toBeUndefined()
    const k21Search = GeographySearchIndexSchema.parse(
      await readJson(resolve(dataRoot, k21Catalog.resultUrls.search)),
    )
    expect(
      k21Search.items.find(
        (item) => item.id === 'display:polling-topology:K21:5000:aggregate:14:1',
      )?.names.he,
    ).toContain('811, 812, 813')

    const k25Catalog = catalog.elections.find((election) => election.id === 'K25')
    if (!k25Catalog) {
      throw new Error('Missing K25 catalog entry')
    }
    const k25Payload = ElectionResultsSchema.parse(
      await readJson(resolve(dataRoot, k25Catalog.resultUrls['statistical-area'])),
    )
    const telNordauDisplay = k25Payload.records.find(
      (record) => record.id === 'display:polling-partition:K25:5000:aggregate:6:1',
    )
    expect(telNordauDisplay).toMatchObject({
      names: { he: expect.stringContaining('334, 335, 336, 337') },
      totals: {
        contributingRows: 21,
        contributingKalpis: 21,
        eligibleVoters: 12_889,
        actualVoters: 5_941,
        validVotes: 5_926,
      },
    })
    expect(telNordauDisplay?.notice?.en).toContain(
      'This result may include votes from areas 512.',
    )
    const k25Search = GeographySearchIndexSchema.parse(
      await readJson(resolve(dataRoot, k25Catalog.resultUrls.search)),
    )
    expect(
      k25Search.items.find(
        (item) => item.id === 'display:polling-partition:K25:5000:aggregate:6:1',
      )?.names.he,
    ).toContain('335')
    const safedClosedDisplay = k25Payload.records.find(
      (record) => record.id === 'display:reviewed-closed:K25:8000:3-4-5',
    )
    expect(safedClosedDisplay).toMatchObject({
      names: { he: expect.stringContaining('3, 4, 5') },
      totals: {
        eligibleVoters: 5_827,
        actualVoters: 3_366,
        validVotes: 3_353,
      },
    })
    expect(safedClosedDisplay?.notice).toBeUndefined()
    const k25AraraClosedDisplay = k25Payload.records.find(
      (record) => record.id === 'display:reviewed-closed:K25:1192:1-3',
    )
    expect(k25AraraClosedDisplay).toMatchObject({
      names: { he: expect.stringContaining('1, 3') },
      totals: {
        contributingRows: 15,
        contributingKalpis: 15,
        eligibleVoters: 7_697,
        actualVoters: 4_114,
        validVotes: 4_087,
      },
    })
    expect(k25AraraClosedDisplay?.notice).toBeUndefined()

    const area1024Displays = {
      K21: {
        id: 'display:polling-partition:K21:3000:aggregate:4:2',
        totals: { eligibleVoters: 2_421, actualVoters: 1_528, validVotes: 1_524 },
        geometryType: 'Polygon',
        geometryPartCount: 1,
      },
      K22: {
        id: 'display:polling-continuity-partition:continuity:K22:3000:component:20:2',
        totals: { eligibleVoters: 2_439, actualVoters: 1_438, validVotes: 1_437 },
        geometryType: 'Polygon',
        geometryPartCount: 1,
      },
      K23: {
        id: 'display:polling-continuity-partition:continuity:K23:3000:component:20:2',
        totals: { eligibleVoters: 2_491, actualVoters: 1_448, validVotes: 1_446 },
        geometryType: 'Polygon',
        geometryPartCount: 1,
      },
      K24: {
        id: 'display:polling-partition:K24:3000:aggregate:11:4',
        totals: { eligibleVoters: 2_544, actualVoters: 1_473, validVotes: 1_469 },
        geometryType: 'MultiPolygon',
        geometryPartCount: 2,
      },
      K25: {
        id: 'display:polling-partition:K25:3000:aggregate:10:4',
        totals: { eligibleVoters: 3_290, actualVoters: 1_825, validVotes: 1_821 },
        geometryType: 'MultiPolygon',
        geometryPartCount: 2,
      },
    }

    for (const [electionId, expected] of Object.entries(area1024Displays)) {
      const election = catalog.elections.find((candidate) => candidate.id === electionId)
      if (!election) {
        throw new Error(`Missing ${electionId} catalog entry`)
      }
      const payload = ElectionResultsSchema.parse(
        await readJson(resolve(dataRoot, election.resultUrls['statistical-area'])),
      )
      const displayRecord = payload.records.find((record) => record.id === expected.id)
      expect(displayRecord, expected.id).toMatchObject({
        totals: expected.totals,
        notice: {
          en: expect.stringContaining('Votes cannot be assigned to this area precisely.'),
        },
      })
      expect(payload.hiddenGeographyIds, electionId).toContain('stat2011:30001024')
      expect(
        payload.records.some((record) => record.id === 'stat2011:30001024'),
        electionId,
      ).toBe(false)

      const geography = (await readJson(
        resolve(dataRoot, election.geographiesByMode['statistical-area'].geometryUrl),
      )) as {
        features: Array<{
          id?: string
          geometry?: { type?: string; coordinates?: unknown[] }
        }>
      }
      const displayFeature = geography.features.find((feature) => feature.id === expected.id)
      expect(displayFeature?.geometry?.type, expected.id).toBe(expected.geometryType)
      const geometryPartCount =
        displayFeature?.geometry?.type === 'Polygon'
          ? 1
          : displayFeature?.geometry?.coordinates?.length
      expect(geometryPartCount, expected.id).toBe(expected.geometryPartCount)
    }

    const k19Election = catalog.elections.find((candidate) => candidate.id === 'K19')
    const k20Election = catalog.elections.find((candidate) => candidate.id === 'K20')
    if (!k19Election || !k20Election) {
      throw new Error('Missing K19 or K20 catalog entry')
    }
    const k19Payload = ElectionResultsSchema.parse(
      await readJson(resolve(dataRoot, k19Election.resultUrls['statistical-area'])),
    )
    expect(k19Payload.hiddenGeographyIds).toContain('stat2011:30001024')
    expect(
      k19Payload.records.some(
        (record) => record.id === 'display:reviewed-attachment:K19:3000:1021-1024',
      ),
    ).toBe(true)

    const k20Payload = ElectionResultsSchema.parse(
      await readJson(resolve(dataRoot, k20Election.resultUrls['statistical-area'])),
    )
    expect(k20Payload.hiddenGeographyIds).not.toContain('stat2011:30001024')
    expect(k20Payload.records.some((record) => record.id === 'stat2011:30001024')).toBe(true)
  })
})

async function readAndValidateGeography(asset: {
  geometryUrl: string
  markerGeometryUrl: string
  featureCount: number
  markerFeatureCount: number
}): Promise<Set<string>> {
  const geometry = (await readJson(resolve(dataRoot, asset.geometryUrl))) as {
    type: string
    features: Array<{ id?: string }>
  }
  expect(geometry.type).toBe('FeatureCollection')
  expect(geometry.features).toHaveLength(asset.featureCount)
  const ids = new Set(geometry.features.map((feature) => feature.id).filter(Boolean) as string[])
  expect(ids.size).toBe(geometry.features.length)

  const markers = (await readJson(resolve(dataRoot, asset.markerGeometryUrl))) as {
    type: string
    features: Array<{
      id?: string
      properties?: { displayMode?: string }
      geometry?: { type?: string }
    }>
  }
  expect(markers.type).toBe('FeatureCollection')
  expect(markers.features).toHaveLength(asset.markerFeatureCount)
  expect(new Set(markers.features.map((feature) => feature.id)).size).toBe(
    markers.features.length,
  )
  for (const marker of markers.features) {
    expect(ids.has(marker.id ?? '')).toBe(true)
    expect(marker.properties?.displayMode).toBe('marker')
    expect(['Point', 'MultiPoint']).toContain(marker.geometry?.type)
  }
  return ids
}
async function readJson(path: string): Promise<unknown> {
  return JSON.parse(await readFile(path, 'utf8'))
}

function polygonContainsPoint(polygon: number[][][], point: [number, number]): boolean {
  return ringContainsPoint(polygon[0], point) &&
    !polygon.slice(1).some((ring) => ringContainsPoint(ring, point))
}

function ringContainsPoint(ring: number[][], [longitude, latitude]: [number, number]): boolean {
  let inside = false
  for (let index = 0, previous = ring.length - 1; index < ring.length; previous = index++) {
    const [currentLongitude, currentLatitude] = ring[index]
    const [previousLongitude, previousLatitude] = ring[previous]
    const crossesLatitude = currentLatitude > latitude !== previousLatitude > latitude
    const crossingLongitude =
      ((previousLongitude - currentLongitude) * (latitude - currentLatitude)) /
        (previousLatitude - currentLatitude) +
      currentLongitude
    if (crossesLatitude && longitude < crossingLongitude) {
      inside = !inside
    }
  }
  return inside
}
