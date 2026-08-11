declare module 'open-nagish' {
  export interface OpenNagishConfig {
    position?: 'bottom-left' | 'bottom-right' | 'top-left' | 'top-right'
    lang?: 'he' | 'en' | 'ar' | 'ru'
    bottomOffset?: number
    mobileBottomOffset?: number
  }

  export interface OpenNagishInstance {
    destroy(): void
  }

  export function init(config?: OpenNagishConfig): OpenNagishInstance
}
