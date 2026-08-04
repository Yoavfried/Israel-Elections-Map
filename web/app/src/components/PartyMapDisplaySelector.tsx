import { CircleDot, Shapes } from 'lucide-react'
import type { PartyMapDisplayMode } from '../domain/partyMap'
import type { Language } from '../domain/schemas'
import { translate } from '../i18n/translations'

interface PartyMapDisplaySelectorProps {
  language: Language
  mode: PartyMapDisplayMode
  onChange: (mode: PartyMapDisplayMode) => void
}

const OPTIONS: Array<{
  value: PartyMapDisplayMode
  labelKey: 'partyMapAreas' | 'partyMapCircles'
  icon: typeof Shapes
}> = [
  { value: 'areas', labelKey: 'partyMapAreas', icon: Shapes },
  { value: 'circles', labelKey: 'partyMapCircles', icon: CircleDot },
]

export function PartyMapDisplaySelector({
  language,
  mode,
  onChange,
}: PartyMapDisplaySelectorProps) {
  return (
    <div
      className="party-map-display-selector"
      dir={language === 'he' ? 'rtl' : 'ltr'}
      role="group"
      aria-label={translate(language, 'partyMapDisplay')}
    >
      {OPTIONS.map((option) => {
        const Icon = option.icon
        const label = translate(language, option.labelKey)
        return (
          <button
            key={option.value}
            type="button"
            className={mode === option.value ? 'is-active' : undefined}
            aria-pressed={mode === option.value}
            title={label}
            onClick={() => onChange(option.value)}
          >
            <Icon size={16} strokeWidth={2} aria-hidden="true" />
            <span>{label}</span>
          </button>
        )
      })}
    </div>
  )
}
