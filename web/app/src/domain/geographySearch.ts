import type { GeographyMode, GeographySearchItem, Language } from './schemas'

interface RankedItem {
  item: GeographySearchItem
  score: number
}

const HEBREW_FINAL_LETTERS: Record<string, string> = {
  ך: 'כ',
  ם: 'מ',
  ן: 'נ',
  ף: 'פ',
  ץ: 'צ',
}

export function searchGeographies(
  items: GeographySearchItem[],
  query: string,
  language: Language,
  preferredMode: GeographyMode,
  limit = 8,
): GeographySearchItem[] {
  const normalizedQuery = normalizeSearchText(query)
  if (!normalizedQuery || limit <= 0) {
    return []
  }

  const otherLanguage: Language = language === 'he' ? 'en' : 'he'
  const queryTokens = normalizedQuery.split(' ')
  const ranked: RankedItem[] = []

  for (const item of items) {
    const fields = [
      { value: item.code, weight: -4 },
      { value: item.names[language], weight: 0 },
      { value: item.names[otherLanguage], weight: 1 },
      ...item.aliases[language].map((value) => ({ value, weight: 2 })),
      ...item.aliases[otherLanguage].map((value) => ({ value, weight: 3 })),
      { value: item.id, weight: 5 },
    ]
    let bestScore = Number.POSITIVE_INFINITY
    for (const field of fields) {
      const normalizedField = normalizeSearchText(field.value)
      if (!normalizedField) {
        continue
      }
      const score = fieldScore(normalizedField, normalizedQuery, queryTokens) + field.weight
      bestScore = Math.min(bestScore, score)
    }
    if (Number.isFinite(bestScore)) {
      ranked.push({ item, score: bestScore })
    }
  }

  const collator = new Intl.Collator(language === 'he' ? 'he-IL' : 'en-IL')
  return ranked
    .toSorted(
      (left, right) =>
        left.score - right.score ||
        Number(right.item.geographyMode === preferredMode) -
          Number(left.item.geographyMode === preferredMode) ||
        Number(right.item.hasResults) - Number(left.item.hasResults) ||
        collator.compare(left.item.names[language], right.item.names[language]) ||
        left.item.id.localeCompare(right.item.id),
    )
    .slice(0, limit)
    .map(({ item }) => item)
}

export function normalizeSearchText(value: string): string {
  return value
    .normalize('NFKD')
    .replace(/\p{M}/gu, '')
    .toLocaleLowerCase()
    .replace(/[ךםןףץ]/g, (character) => HEBREW_FINAL_LETTERS[character] ?? character)
    .replace(/[^\p{L}\p{N}\s]+/gu, '')
    .trim()
    .replace(/\s+/g, ' ')
}

function fieldScore(field: string, query: string, queryTokens: string[]): number {
  if (field === query) {
    return 0
  }
  if (field.startsWith(query)) {
    return 20
  }
  if (queryTokens.every((token) => field.includes(token))) {
    return 40
  }
  if (field.includes(query)) {
    return 60
  }
  return Number.POSITIVE_INFINITY
}
