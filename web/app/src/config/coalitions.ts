import coalitionDefinitions from '../../config/coalitions.json'

export type CoalitionKind = 'first' | 'transitional'

interface LocalizedNote {
  en: string
  he: string
}

export interface CoalitionDefinition {
  kind: CoalitionKind
  memberPartyIds: readonly string[]
  partialMembership?: Readonly<Record<string, LocalizedNote>>
  sourceUrls: readonly string[]
}

export const COALITION_DEFINITIONS = coalitionDefinitions as Readonly<
  Record<string, CoalitionDefinition>
>

export function coalitionDefinition(electionId: string): CoalitionDefinition | null {
  return COALITION_DEFINITIONS[electionId] ?? null
}
