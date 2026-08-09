import { describe, expect, it } from 'vitest'
import { normalizeSearchText, searchGeographies } from './geographySearch'
import type { GeographySearchItem } from './schemas'

const items: GeographySearchItem[] = [
  {
    id: 'loc:3000',
    geographyMode: 'locality',
    names: { en: 'Jerusalem', he: 'ירושלים' },
    aliases: { en: [], he: [] },
    code: '3000',
    hasResults: true,
    bounds: [
      [35.1, 31.7],
      [35.3, 31.9],
    ],
  },
  {
    id: 'display:group',
    geographyMode: 'statistical-area',
    names: { en: 'Jerusalem · 1022, 1023, 1024', he: 'ירושלים · 1022, 1023, 1024' },
    aliases: { en: [], he: [] },
    code: '',
    hasResults: true,
    bounds: [
      [35.2, 31.7],
      [35.21, 31.71],
    ],
  },
  {
    id: 'loc:6000',
    geographyMode: 'locality',
    names: { en: 'Baqa-Jatt', he: "באקה-ג'ת" },
    aliases: { en: ['Baqa al-Gharbiyye'], he: ['באקה אל-גרבייה'] },
    code: '6000',
    hasResults: false,
    bounds: [
      [35, 32],
      [35.1, 32.1],
    ],
  },
  {
    id: 'loc:1321',
    geographyMode: 'locality',
    names: { en: 'Khawaled', he: "ח'ואלד" },
    aliases: { en: [], he: [] },
    code: '1321',
    hasResults: true,
    bounds: [
      [35.1, 32.7],
      [35.2, 32.8],
    ],
  },
  {
    id: 'loc:1326',
    geographyMode: 'locality',
    names: { en: 'Basma', he: 'בסמ"ה' },
    aliases: { en: [], he: [] },
    code: '1326',
    hasResults: true,
    bounds: [
      [35.1, 32.4],
      [35.2, 32.5],
    ],
  },
]

describe('geography search', () => {
  it('places an exact code before name matches', () => {
    expect(searchGeographies(items, '3000', 'en', 'statistical-area')[0].id).toBe('loc:3000')
  })

  it('matches every query token across a combined-area name', () => {
    expect(searchGeographies(items, 'Jerusalem 1024', 'en', 'locality')[0].id).toBe(
      'display:group',
    )
  })

  it('matches reviewed aliases despite punctuation differences', () => {
    expect(searchGeographies(items, 'Baqa al Gharbiyye', 'en', 'locality')[0].id).toBe(
      'loc:6000',
    )
  })

  it('matches Hebrew locality names when internal quotes are omitted', () => {
    expect(searchGeographies(items, 'חואלד', 'he', 'locality')[0].id).toBe('loc:1321')
    expect(searchGeographies(items, 'בסמה', 'he', 'locality')[0].id).toBe('loc:1326')
  })

  it('normalizes Hebrew final letters and punctuation', () => {
    expect(normalizeSearchText("מלך-ים")).toBe('מלכימ')
    expect(normalizeSearchText("ח'ואלד")).toBe(normalizeSearchText('חואלד'))
    expect(normalizeSearchText('בסמ"ה')).toBe(normalizeSearchText('בסמה'))
  })
})
