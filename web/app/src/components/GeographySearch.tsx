import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { Search, X } from 'lucide-react'
import { searchGeographies } from '../domain/geographySearch'
import type {
  GeographyMode,
  GeographySearchItem,
  Language,
} from '../domain/schemas'
import { translate } from '../i18n/translations'

interface GeographySearchProps {
  language: Language
  electionId: string
  geographyMode: GeographyMode
  items: GeographySearchItem[]
  loading: boolean
  error: string | null
  selectedItem: GeographySearchItem | null
  onSelect: (item: GeographySearchItem) => void
  onClearSelection: () => void
}

export function GeographySearch({
  language,
  electionId,
  geographyMode,
  items,
  loading,
  error,
  selectedItem,
  onSelect,
  onClearSelection,
}: GeographySearchProps) {
  const listboxId = useId()
  const previousSelectionRef = useRef<string | null>(null)
  const preserveQueryOnSelectionClearRef = useRef(false)
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const matches = useMemo(
    () => searchGeographies(items, query, language, geographyMode),
    [geographyMode, items, language, query],
  )

  useEffect(() => {
    setQuery('')
    setOpen(false)
    setActiveIndex(0)
  }, [electionId])

  useEffect(() => {
    const selectionKey = selectedItem
      ? `${selectedItem.geographyMode}:${selectedItem.id}`
      : null
    if (selectedItem) {
      setQuery(selectedItem.names[language])
    } else if (previousSelectionRef.current && !preserveQueryOnSelectionClearRef.current) {
      setQuery('')
    }
    preserveQueryOnSelectionClearRef.current = false
    previousSelectionRef.current = selectionKey
  }, [language, selectedItem])

  useEffect(() => {
    setActiveIndex((current) => Math.min(current, Math.max(matches.length - 1, 0)))
  }, [matches.length])

  const choose = (item: GeographySearchItem) => {
    setQuery(item.names[language])
    setOpen(false)
    onSelect(item)
  }
  const clear = () => {
    setQuery('')
    setOpen(false)
    setActiveIndex(0)
    onClearSelection()
  }
  const showResults = open && query.trim().length > 0 && !loading

  return (
    <div
      className="geography-search"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
          setOpen(false)
        }
      }}
    >
      <label htmlFor={`${listboxId}-input`}>{translate(language, 'searchLabel')}</label>
      <div className="geography-search__input-wrap">
        <Search className="geography-search__icon" size={18} aria-hidden="true" />
        <input
          id={`${listboxId}-input`}
          type="search"
          role="combobox"
          autoComplete="off"
          value={query}
          disabled={loading}
          placeholder={
            loading
              ? translate(language, 'searchLoading')
              : translate(language, 'searchPlaceholder')
          }
          aria-autocomplete="list"
          aria-controls={listboxId}
          aria-expanded={showResults}
          aria-activedescendant={
            showResults && matches[activeIndex]
              ? `${listboxId}-option-${activeIndex}`
              : undefined
          }
          onFocus={() => setOpen(true)}
          onChange={(event) => {
            if (selectedItem) {
              preserveQueryOnSelectionClearRef.current = true
              onClearSelection()
            }
            setQuery(event.target.value)
            setOpen(true)
            setActiveIndex(0)
          }}
          onKeyDown={(event) => {
            if (event.key === 'ArrowDown' && matches.length > 0) {
              event.preventDefault()
              setOpen(true)
              setActiveIndex((current) => (current + 1) % matches.length)
            } else if (event.key === 'ArrowUp' && matches.length > 0) {
              event.preventDefault()
              setOpen(true)
              setActiveIndex((current) => (current - 1 + matches.length) % matches.length)
            } else if (event.key === 'Enter' && showResults && matches[activeIndex]) {
              event.preventDefault()
              choose(matches[activeIndex])
            } else if (event.key === 'Escape') {
              setOpen(false)
            }
          }}
        />
        {query ? (
          <button
            className="geography-search__clear"
            type="button"
            title={translate(language, 'clearSearch')}
            aria-label={translate(language, 'clearSearch')}
            onClick={clear}
          >
            <X size={17} aria-hidden="true" />
          </button>
        ) : null}
      </div>

      {showResults ? (
        <div className="geography-search__popover">
          {error ? (
            <p className="geography-search__message" role="alert">
              {translate(language, 'searchError')}
            </p>
          ) : matches.length === 0 ? (
            <p className="geography-search__message" role="status">
              {translate(language, 'searchNoResults')}
            </p>
          ) : (
            <ul id={listboxId} role="listbox" aria-label={translate(language, 'searchResults')}>
              {matches.map((item, index) => (
                <li key={`${item.geographyMode}:${item.id}`}>
                  <button
                    id={`${listboxId}-option-${index}`}
                    type="button"
                    role="option"
                    aria-selected={index === activeIndex}
                    className={index === activeIndex ? 'is-active' : undefined}
                    onMouseEnter={() => setActiveIndex(index)}
                    onClick={() => choose(item)}
                  >
                    <span className="geography-search__result-name">
                      {item.names[language]}
                    </span>
                    <span className="geography-search__result-meta">
                      <span>
                        {translate(
                          language,
                          item.geographyMode === 'locality'
                            ? 'localityResultType'
                            : 'statisticalAreaResultType',
                        )}
                        {item.code ? ` · ${item.code}` : ''}
                      </span>
                      {!item.hasResults ? (
                        <span className="geography-search__no-data">
                          {translate(language, 'searchNoMappedResult')}
                        </span>
                      ) : null}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  )
}
