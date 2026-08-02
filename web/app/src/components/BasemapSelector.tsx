import { Map } from 'lucide-react'
import type { BasemapMode, Language } from '../domain/schemas'
import { translate } from '../i18n/translations'

interface BasemapSelectorProps {
  language: Language
  mode: BasemapMode
  onChange: (mode: BasemapMode) => void
}

const BASEMAP_OPTIONS: Array<{ value: BasemapMode; labelKey: 'basemapNeutral' | 'basemapVector' }> = [
  { value: 'neutral', labelKey: 'basemapNeutral' },
  { value: 'vector', labelKey: 'basemapVector' },
]

export function BasemapSelector({ language, mode, onChange }: BasemapSelectorProps) {
  const label = translate(language, 'basemapLabel')

  return (
    <label
      className="basemap-selector"
      dir={language === 'he' ? 'rtl' : 'ltr'}
      title={label}
    >
      <Map size={18} strokeWidth={2} aria-hidden="true" />
      <select
        value={mode}
        aria-label={label}
        onChange={(event) => onChange(event.target.value as BasemapMode)}
      >
        {BASEMAP_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {translate(language, option.labelKey)}
          </option>
        ))}
      </select>
    </label>
  )
}
