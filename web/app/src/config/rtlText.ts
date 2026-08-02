import rtlTextPluginAssetUrl from 'rtl-text-plugin?url'

export const RTL_TEXT_PLUGIN_URL =
  import.meta.env.VITE_RTL_TEXT_PLUGIN_URL?.trim() || rtlTextPluginAssetUrl

export interface RtlTextPluginApi {
  getRTLTextPluginStatus: () => string
  setRTLTextPlugin: (pluginUrl: string, lazy: boolean) => Promise<void>
}

export function createRtlTextPluginLoader(pluginUrl = RTL_TEXT_PLUGIN_URL) {
  let pendingLoad: Promise<void> | null = null

  return (api: RtlTextPluginApi): Promise<void> => {
    const status = api.getRTLTextPluginStatus()

    if (status === 'loaded') {
      return Promise.resolve()
    }
    if (status === 'error') {
      return Promise.reject(new Error('The map RTL text plugin failed to load.'))
    }
    if (pendingLoad) {
      return pendingLoad
    }
    if (status !== 'unavailable') {
      return Promise.resolve()
    }

    pendingLoad = api.setRTLTextPlugin(pluginUrl, false).catch((error: unknown) => {
      pendingLoad = null
      throw error
    })
    return pendingLoad
  }
}

export const ensureRtlTextSupport = createRtlTextPluginLoader()
