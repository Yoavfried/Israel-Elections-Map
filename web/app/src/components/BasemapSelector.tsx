import { Layers, Map } from 'lucide-react'
import type { BasemapMode, Language } from '../domain/schemas'
import { translate } from '../i18n/translations'

interface BasemapSelectorProps {
  language: Language
  mode: BasemapMode
  onChange: (mode: BasemapMode) => void
}

const BASEMAP_OPTIONS: Array<{
  value: BasemapMode
  labelKey: 'basemapNeutral' | 'basemapVector'
  icon: typeof Map
}> = [
  { value: 'neutral', labelKey: 'basemapNeutral', icon: Layers },
  { value: 'vector', labelKey: 'basemapVector', icon: Map },
]

export function BasemapSelector({ language, mode, onChange }: BasemapSelectorProps) {
  const label = translate(language, 'basemapLabel')

  return (
    <div
      className="basemap-selector"
      dir={language === 'he' ? 'rtl' : 'ltr'}
      role="group"
      aria-label={label}
    >
      {BASEMAP_OPTIONS.map((option) => {
        const Icon = option.icon
        const optionLabel = translate(language, option.labelKey)
        return (
          <button
            key={option.value}
            type="button"
            className={mode === option.value ? 'is-active' : undefined}
            aria-pressed={mode === option.value}
            title={optionLabel}
            onClick={() => onChange(option.value)}
          >
            <Icon size={16} strokeWidth={2} aria-hidden="true" />
            <span>{optionLabel}</span>
          </button>
        )
      })}
    </div>
  )
}
