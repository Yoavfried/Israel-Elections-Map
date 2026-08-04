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

const COALITION_AGREEMENTS_URL =
  'https://main.knesset.gov.il/mk/government/Pages/CoalitionAgreements.aspx'
const K21_DISSOLUTION_URL =
  'https://main.knesset.gov.il/News/PressReleases/pages/press30.05.19.aspx'
const K22_DISSOLUTION_URL =
  'https://main.knesset.gov.il/News/PressReleases/pages/press11.12.19f.aspx'

export const COALITION_DEFINITIONS: Readonly<Record<string, CoalitionDefinition>> = {
  K17: {
    kind: 'first',
    memberPartyIds: ['כן', 'אמת', 'שס', 'זך'],
    sourceUrls: [COALITION_AGREEMENTS_URL],
  },
  K18: {
    kind: 'first',
    memberPartyIds: ['מחל', 'ל', 'אמת', 'שס', 'ג', 'ב'],
    sourceUrls: [COALITION_AGREEMENTS_URL],
  },
  K19: {
    kind: 'first',
    memberPartyIds: ['מחל', 'פה', 'טב', 'צפ'],
    sourceUrls: [COALITION_AGREEMENTS_URL],
  },
  K20: {
    kind: 'first',
    memberPartyIds: ['מחל', 'כ', 'טב', 'שס', 'ג'],
    sourceUrls: [COALITION_AGREEMENTS_URL],
  },
  K21: {
    kind: 'transitional',
    memberPartyIds: ['מחל', 'שס', 'ג', 'טב', 'כ', 'נ'],
    partialMembership: {
      טב: {
        en: 'This joint ballot included factions both represented and not represented in the outgoing government; its votes cannot be separated by component.',
        he: 'הפתק המשותף כלל סיעות שיוצגו בממשלת המעבר וסיעות שלא יוצגו בה; לא ניתן להפריד את הקולות בין מרכיביו.',
      },
    },
    sourceUrls: [COALITION_AGREEMENTS_URL, K21_DISSOLUTION_URL],
  },
  K22: {
    kind: 'transitional',
    memberPartyIds: ['מחל', 'שס', 'ג', 'טב'],
    partialMembership: {
      טב: {
        en: 'This joint ballot included factions both represented and not represented in the outgoing government; its votes cannot be separated by component.',
        he: 'הפתק המשותף כלל סיעות שיוצגו בממשלת המעבר וסיעות שלא יוצגו בה; לא ניתן להפריד את הקולות בין מרכיביו.',
      },
    },
    sourceUrls: [COALITION_AGREEMENTS_URL, K22_DISSOLUTION_URL],
  },
  K23: {
    kind: 'first',
    memberPartyIds: ['מחל', 'פה', 'שס', 'ג', 'אמת'],
    partialMembership: {
      פה: {
        en: 'Only part of the Blue and White joint list entered the government; its ballot votes cannot be separated by component.',
        he: 'רק חלק מרשימת כחול לבן נכנס לממשלה; לא ניתן להפריד את קולות הפתק בין מרכיבי הרשימה.',
      },
      אמת: {
        en: 'Meretz members and Merav Michaeli did not join the coalition',
        he: 'חברי מרצ ומרב מיכאלי לא הצטרפו לקואליציה',
      },
    },
    sourceUrls: [COALITION_AGREEMENTS_URL],
  },
  K24: {
    kind: 'first',
    memberPartyIds: ['פה', 'כן', 'ב', 'אמת', 'ל', 'ת', 'מרצ', 'עם'],
    sourceUrls: [COALITION_AGREEMENTS_URL],
  },
  K25: {
    kind: 'first',
    memberPartyIds: ['מחל', 'שס', 'ג', 'ט'],
    sourceUrls: [COALITION_AGREEMENTS_URL],
  },
}

export function coalitionDefinition(electionId: string): CoalitionDefinition | null {
  return COALITION_DEFINITIONS[electionId] ?? null
}
