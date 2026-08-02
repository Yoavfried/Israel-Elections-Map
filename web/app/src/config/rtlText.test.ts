import { describe, expect, it, vi } from 'vitest'
import { createRtlTextPluginLoader } from './rtlText'

describe('RTL text plugin loader', () => {
  it('loads the configured plugin eagerly when MapLibre has no RTL support', async () => {
    const setRTLTextPlugin = vi.fn().mockResolvedValue(undefined)
    const load = createRtlTextPluginLoader('/assets/rtl-text.js')

    await load({
      getRTLTextPluginStatus: () => 'unavailable',
      setRTLTextPlugin,
    })

    expect(setRTLTextPlugin).toHaveBeenCalledWith('/assets/rtl-text.js', false)
  })

  it('shares one in-flight request across repeated map mounts', async () => {
    let resolveLoad!: () => void
    const pendingLoad = new Promise<void>((resolve) => {
      resolveLoad = resolve
    })
    const setRTLTextPlugin = vi.fn(() => pendingLoad)
    const load = createRtlTextPluginLoader('/assets/rtl-text.js')
    const api = {
      getRTLTextPluginStatus: () => 'loading',
      setRTLTextPlugin,
    }

    const firstLoad = load({ ...api, getRTLTextPluginStatus: () => 'unavailable' })
    const secondLoad = load(api)
    resolveLoad()
    await Promise.all([firstLoad, secondLoad])

    expect(setRTLTextPlugin).toHaveBeenCalledTimes(1)
  })

  it('does not configure MapLibre again after RTL support is loaded', async () => {
    const setRTLTextPlugin = vi.fn().mockResolvedValue(undefined)
    const load = createRtlTextPluginLoader('/assets/rtl-text.js')

    await load({
      getRTLTextPluginStatus: () => 'loaded',
      setRTLTextPlugin,
    })

    expect(setRTLTextPlugin).not.toHaveBeenCalled()
  })
})
