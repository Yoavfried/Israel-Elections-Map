import { z } from 'zod'

export const LanguageSchema = z.enum(['en', 'he'])
export const GeographyModeSchema = z.enum(['statistical-area', 'locality'])

export const LocalizedTextSchema = z.object({
  en: z.string().min(1),
  he: z.string().min(1),
})

export const CoverageSchema = z.object({
  totalRows: z.number().nonnegative(),
  totalActualVoters: z.number().nonnegative(),
  mappedRows: z.number().nonnegative(),
  mappedActualVoters: z.number().nonnegative(),
  mappedActualVoterShare: z.number().min(0).max(1),
  pendingRows: z.number().nonnegative(),
  pendingActualVoters: z.number().nonnegative(),
  unmappedRows: z.number().nonnegative(),
  unmappedActualVoters: z.number().nonnegative(),
})

const AssetSchema = z.object({
  path: z.string().min(1),
  bytes: z.number().int().nonnegative(),
  sha256: z.string().regex(/^[a-f0-9]{64}$/),
})

const GeographyAssetSchema = z.object({
  vintage: z.number().int().positive(),
  geometryUrl: z.string().min(1),
  markerGeometryUrl: z.string().min(1),
  backdropGeometryUrl: z.string().min(1).optional(),
  featureCount: z.number().int().positive(),
  markerFeatureCount: z.number().int().positive(),
})

const GeographyModeCatalogSchema = GeographyAssetSchema.extend({
  id: GeographyModeSchema,
  label: LocalizedTextSchema,
})

const ElectionCatalogSchema = z.object({
  id: z.string().regex(/^K\d+$/),
  number: z.number().int().positive(),
  statisticalAreaVintage: z.number().int().positive(),
  dateLabel: z.string().min(1),
  label: LocalizedTextSchema,
  coverageByMode: z.object({
    'statistical-area': CoverageSchema,
    locality: CoverageSchema,
  }),
  resultUrls: z.object({
    'statistical-area': z.string().min(1),
    locality: z.string().min(1),
    national: z.string().min(1),
  }),
  geographiesByMode: z.object({
    'statistical-area': GeographyAssetSchema,
    locality: GeographyAssetSchema,
  }),
})

export const AppCatalogSchema = z.object({
  schemaVersion: z.literal(4),
  buildId: z.string().min(8),
  generatedAt: z.string().datetime(),
  source: z.object({
    statisticalAreaVintages: z.array(z.number().int().positive()).min(1),
    localityGeometryVintage: z.number().int().positive(),
    electionRange: z.object({ first: z.string(), last: z.string() }),
    assignmentStatus: z.string().min(1),
    resultColumnExclusions: z.array(
      z.object({
        electionId: z.string().regex(/^K\d+$/),
        column: z.string().min(1),
        reason: z.string().min(1),
      }),
    ),
  }),
  bounds: z.tuple([
    z.tuple([z.number(), z.number()]),
    z.tuple([z.number(), z.number()]),
  ]),
  partyColorPolicy: z.object({
    status: z.string().min(1),
    description: z.string().min(1),
  }),
  geographyModes: z.array(GeographyModeCatalogSchema).min(2),
  elections: z.array(ElectionCatalogSchema).min(1),
  assets: z.array(AssetSchema),
})

export const PartySchema = z.object({
  id: z.string().min(1),
  ballotLetter: z.string().min(1),
  names: LocalizedTextSchema,
  listNameHe: z.string().min(1),
  wikipedia: z.object({
    he: z.url().nullable(),
    en: z.url().nullable(),
  }),
  color: z.string().min(1),
  colorStatus: z.enum(['provisional', 'reviewed']),
})

const ResultRecordSchema = z.object({
  id: z.string().min(1),
  geographyType: z.enum([
    'statistical-area',
    'locality',
    'custom',
    'municipality-fallback',
    'envelope',
  ]),
  names: LocalizedTextSchema,
  notice: LocalizedTextSchema.optional(),
  includedNames: z
    .object({
      en: z.array(z.string().min(1)),
      he: z.array(z.string().min(1)),
    })
    .optional(),
  code: z.string().min(1),
  localityId: z.string().nullable(),
  totals: z.object({
    contributingRows: z.number().nonnegative(),
    contributingKalpis: z.number().nonnegative(),
    eligibleVoters: z.number().nonnegative(),
    actualVoters: z.number().nonnegative(),
    validVotes: z.number().nonnegative(),
    invalidVotes: z.number().nonnegative(),
    turnout: z.number().min(0).nullable(),
  }),
  winner: z.object({
    partyId: z.string(),
    votes: z.number().nonnegative(),
    runnerUpVotes: z.number().nonnegative(),
    marginVotes: z.number(),
    voteShare: z.number().min(0).max(1),
  }),
  partyVotes: z.record(z.string(), z.number().nonnegative()),
})

export const ElectionResultsSchema = z.object({
  schemaVersion: z.literal(2),
  electionId: z.string().regex(/^K\d+$/),
  geographyMode: GeographyModeSchema,
  coverage: CoverageSchema,
  parties: z.array(PartySchema),
  records: z.array(ResultRecordSchema),
  envelope: ResultRecordSchema.nullable(),
  hiddenGeographyIds: z.array(z.string().min(1)),
})

const NationalPartySchema = PartySchema.extend({
  votes: z.number().int().nonnegative(),
  voteShare: z.number().min(0).max(1),
  mandates: z.number().int().nonnegative(),
  passedThreshold: z.boolean(),
})

export const NationalResultsSchema = z.object({
  schemaVersion: z.literal(1),
  electionId: z.string().regex(/^K\d+$/),
  threshold: z.object({
    share: z.number().gt(0).lt(1),
    votes: z.number().int().positive(),
  }),
  totals: z.object({
    validVotes: z.number().int().positive(),
    representedVotes: z.number().int().positive(),
    representedVoteShare: z.number().min(0).max(1),
    mandates: z.number().int().positive(),
    contestingParties: z.number().int().positive(),
    representedParties: z.number().int().positive(),
  }),
  sources: z.object({
    officialResultsUrl: z.url(),
    thresholdSourceUrl: z.url(),
  }),
  parties: z.array(NationalPartySchema).min(1),
})

export type Language = z.infer<typeof LanguageSchema>
export type GeographyMode = z.infer<typeof GeographyModeSchema>
export type Coverage = z.infer<typeof CoverageSchema>
export type AppCatalog = z.infer<typeof AppCatalogSchema>
export type ElectionCatalog = AppCatalog['elections'][number]
export type GeographyModeCatalog = AppCatalog['geographyModes'][number]
export type ElectionResults = z.infer<typeof ElectionResultsSchema>
export type ResultRecord = ElectionResults['records'][number]
export type Party = ElectionResults['parties'][number]
export type NationalResults = z.infer<typeof NationalResultsSchema>
export type NationalParty = NationalResults['parties'][number]
