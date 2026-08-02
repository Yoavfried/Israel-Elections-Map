import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { MapPin, Search, X } from 'lucide-react'
import {
  ADDRESS_SEARCH_DEBOUNCE_MS,
} from '../config/geocoding'
import {
  searchAddresses,
  shouldSearchAddresses,
} from '../domain/addressSearch'
import type { AddressSearchMatch } from '../domain/addressSearch'
import { searchGeographies } from '../domain/geographySearch'
import type {
  GeographyBounds,
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
  bounds: GeographyBounds
  statisticalGeometryUrl: string
  loading: boolean
  error: string | null
  selectedItem: GeographySearchItem | null
  selectedAddress: AddressSearchMatch | null
  onSelect: (item: GeographySearchItem) => void
  onAddressSelect: (match: AddressSearchMatch) => void
  onClearSelection: () => void
}

type SearchOption =
  | { kind: 'geography'; item: GeographySearchItem }
  | { kind: 'address'; match: AddressSearchMatch }

export function GeographySearch({
  language,
  electionId,
  geographyMode,
  items,
  bounds,
  statisticalGeometryUrl,
  loading,
  error,
  selectedItem,
  selectedAddress,
  onSelect,
  onAddressSelect,
  onClearSelection,
}: GeographySearchProps) {
  const listboxId = useId()
  const previousSelectionRef = useRef<string | null>(null)
  const preserveQueryOnSelectionClearRef = useRef(false)
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const [addressMatches, setAddressMatches] = useState<AddressSearchMatch[]>([])
  const [addressLoading, setAddressLoading] = useState(false)
  const [addressError, setAddressError] = useState(false)
  const geographyMatches = useMemo(
    () => searchGeographies(items, query, language, geographyMode, 6),
    [geographyMode, items, language, query],
  )
  const options = useMemo<SearchOption[]>(
    () => [
      ...geographyMatches.map((item) => ({ kind: 'geography' as const, item })),
      ...addressMatches.map((match) => ({ kind: 'address' as const, match })),
    ],
    [addressMatches, geographyMatches],
  )
  const addressQuery = shouldSearchAddresses(query)

  useEffect(() => {
    setQuery('')
    setOpen(false)
    setActiveIndex(0)
    setAddressMatches([])
    setAddressError(false)
  }, [electionId])

  useEffect(() => {
    const selectionKey = selectedAddress
      ? selectedAddress.id
      : selectedItem
        ? `${selectedItem.geographyMode}:${selectedItem.id}`
        : null
    if (selectedAddress) {
      setQuery(selectedAddress.label)
    } else if (selectedItem) {
      setQuery(selectedItem.names[language])
    } else if (previousSelectionRef.current && !preserveQueryOnSelectionClearRef.current) {
      setQuery('')
    }
    preserveQueryOnSelectionClearRef.current = false
    previousSelectionRef.current = selectionKey
  }, [language, selectedAddress, selectedItem])

  useEffect(() => {
    setAddressMatches([])
    setAddressError(false)
    if (
      loading ||
      !addressQuery ||
      (selectedAddress && query.trim() === selectedAddress.label)
    ) {
      setAddressLoading(false)
      return
    }

    const abortController = new AbortController()
    const timer = window.setTimeout(() => {
      setAddressLoading(true)
      void searchAddresses({
        query,
        language,
        bounds,
        statisticalItems: items,
        geometryUrl: statisticalGeometryUrl,
        signal: abortController.signal,
      })
        .then((matches) => {
          if (!abortController.signal.aborted) {
            setAddressMatches(matches)
          }
        })
        .catch((searchError: unknown) => {
          if (
            !abortController.signal.aborted &&
            !(searchError instanceof DOMException && searchError.name === 'AbortError')
          ) {
            setAddressError(true)
          }
        })
        .finally(() => {
          if (!abortController.signal.aborted) {
            setAddressLoading(false)
          }
        })
    }, ADDRESS_SEARCH_DEBOUNCE_MS)

    return () => {
      window.clearTimeout(timer)
      abortController.abort()
    }
  }, [
    addressQuery,
    bounds,
    items,
    language,
    loading,
    query,
    selectedAddress,
    statisticalGeometryUrl,
  ])

  useEffect(() => {
    setActiveIndex((current) => Math.min(current, Math.max(options.length - 1, 0)))
  }, [options.length])

  const choose = (option: SearchOption) => {
    setOpen(false)
    if (option.kind === 'address') {
      setQuery(option.match.label)
      onAddressSelect(option.match)
      return
    }
    setQuery(option.item.names[language])
    onSelect(option.item)
  }
  const clear = () => {
    setQuery('')
    setOpen(false)
    setActiveIndex(0)
    setAddressMatches([])
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
          dir="auto"
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
            showResults && options[activeIndex]
              ? `${listboxId}-option-${activeIndex}`
              : undefined
          }
          onFocus={() => setOpen(true)}
          onChange={(event) => {
            if (selectedItem || selectedAddress) {
              preserveQueryOnSelectionClearRef.current = true
              onClearSelection()
            }
            setQuery(event.target.value)
            setOpen(true)
            setActiveIndex(0)
          }}
          onKeyDown={(event) => {
            if (event.key === 'ArrowDown' && options.length > 0) {
              event.preventDefault()
              setOpen(true)
              setActiveIndex((current) => (current + 1) % options.length)
            } else if (event.key === 'ArrowUp' && options.length > 0) {
              event.preventDefault()
              setOpen(true)
              setActiveIndex((current) => (current - 1 + options.length) % options.length)
            } else if (event.key === 'Enter' && showResults && options[activeIndex]) {
              event.preventDefault()
              choose(options[activeIndex])
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
          ) : options.length === 0 && addressLoading ? (
            <p className="geography-search__message" role="status">
              {translate(language, 'addressSearchLoading')}
            </p>
          ) : options.length === 0 ? (
            <p className="geography-search__message" role="status">
              {translate(language, 'searchNoResults')}
            </p>
          ) : (
            <ul id={listboxId} role="listbox" aria-label={translate(language, 'searchResults')}>
              {options.map((option, index) => {
                const item = option.kind === 'geography' ? option.item : option.match.area
                return (
                  <li key={option.kind === 'geography' ? `${item.geographyMode}:${item.id}` : option.match.id}>
                    <button
                      id={`${listboxId}-option-${index}`}
                      type="button"
                      role="option"
                      aria-selected={index === activeIndex}
                      className={index === activeIndex ? 'is-active' : undefined}
                      onMouseEnter={() => setActiveIndex(index)}
                      onClick={() => choose(option)}
                    >
                      {option.kind === 'address' ? (
                        <span className="geography-search__result-heading">
                          <MapPin
                            className="geography-search__result-pin"
                            size={17}
                            aria-hidden="true"
                          />
                          <span className="geography-search__result-name" dir="auto">
                            {option.match.label}
                          </span>
                        </span>
                      ) : (
                        <span className="geography-search__result-name" dir="auto">
                          {item.names[language]}
                        </span>
                      )}
                      <span className="geography-search__result-meta">
                        <span dir="auto">
                          {option.kind === 'address'
                            ? item.names[language]
                            : translate(
                                language,
                                item.geographyMode === 'locality'
                                  ? 'localityResultType'
                                  : 'statisticalAreaResultType',
                              )}
                          {option.kind === 'geography' && item.code ? ` · ${item.code}` : ''}
                        </span>
                        {!item.hasResults ? (
                          <span className="geography-search__no-data">
                            {translate(language, 'searchNoMappedResult')}
                          </span>
                        ) : null}
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
          {addressQuery && !error ? (
            <div className="geography-search__address-footer">
              {addressLoading && options.length > 0 ? (
                <span role="status">{translate(language, 'addressSearchLoading')}</span>
              ) : addressError ? (
                <span role="status">{translate(language, 'addressSearchUnavailable')}</span>
              ) : null}
              <span>
                {translate(language, 'addressSearchAttribution')}{' '}
                <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">
                  OpenStreetMap
                </a>{' '}
                · Photon
              </span>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
