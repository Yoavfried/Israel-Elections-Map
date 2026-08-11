import { useEffect } from 'react'
import type { OpenNagishConfig, OpenNagishInstance } from 'open-nagish'
import type { Language } from '../domain/schemas'

declare global {
  interface Window {
    OpenNagishConfig?: OpenNagishConfig
  }
}

const themeStyleId = 'election-map-open-nagish-theme'

function applyWidgetTheme() {
  const shadowRoot = document.getElementById('opennagish-widget')?.shadowRoot
  if (!shadowRoot) return

  const style = shadowRoot.getElementById(themeStyleId) ?? document.createElement('style')
  style.id = themeStyleId
  style.textContent = `
    .anid-trigger {
      top: 15px !important;
      right: auto !important;
      bottom: auto !important;
      left: max(22px, env(safe-area-inset-left)) !important;
      width: 42px !important;
      height: 42px !important;
      border: 1px solid #171a17 !important;
      border-radius: 8px !important;
      color: #faf8f1 !important;
      background: #171a17 !important;
      box-shadow: 0 3px 10px rgba(23, 26, 23, 0.16) !important;
    }

    .anid-trigger:hover,
    .anid-trigger:focus-visible {
      background: #1c6457 !important;
      border-color: #1c6457 !important;
    }

    .anid-trigger:focus-visible {
      outline: 3px solid rgba(28, 100, 87, 0.34) !important;
      outline-offset: 3px !important;
    }

    .anid-trigger svg {
      width: 22px !important;
      height: 22px !important;
      fill: currentColor !important;
    }

    .anid-trigger[aria-expanded="true"] {
      color: #faf8f1 !important;
      background: #1c6457 !important;
      border-color: #1c6457 !important;
    }

    @media (max-width: 900px) {
      .anid-panel {
        top: 138px !important;
        right: 12px !important;
        bottom: auto !important;
        left: 12px !important;
        width: auto !important;
        max-width: none !important;
        max-height: calc(100dvh - 150px) !important;
        overflow-y: auto !important;
        overscroll-behavior: contain !important;
        padding-bottom: max(12px, env(safe-area-inset-bottom)) !important;
      }
    }

    @media (max-width: 800px) {
      .anid-trigger {
        top: 10px !important;
      }

      .anid-panel {
        top: 66px !important;
        max-height: calc(100dvh - 78px) !important;
      }
    }
  `

  if (!style.parentElement) shadowRoot.appendChild(style)
}

interface AccessibilityWidgetProps {
  language: Language
}

export function AccessibilityWidget({ language }: AccessibilityWidgetProps) {
  useEffect(() => {
    let instance: OpenNagishInstance | undefined
    let cancelled = false
    const config: OpenNagishConfig = {
      position: 'top-left',
      lang: language === 'he' ? 'he' : 'en',
    }

    window.OpenNagishConfig = config
    void import('open-nagish')
      .then(({ init }) => {
        if (cancelled) return
        instance = init(config)
        applyWidgetTheme()
      })
      .catch((error: unknown) => {
        console.error('OpenNagish failed to load', error)
      })

    return () => {
      cancelled = true
      instance?.destroy()
    }
  }, [language])

  return <div className="accessibility-slot" aria-hidden="true" />
}
