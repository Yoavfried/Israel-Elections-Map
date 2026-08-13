import { APP_PATH } from '../seo/config.mjs'
import { handleSeoRequest } from '../seo/render.mjs'

let catalogPromise
let recentJsonPath
let recentJsonPromise

export default {
  async fetch(request, env) {
    const response = await handleSeoRequest(request, {
      readJson: (relativePath) => readAssetJson(request, env.ASSETS, relativePath),
    })
    return response ?? env.ASSETS.fetch(request)
  },
}

async function readAssetJson(request, assets, relativePath) {
  const normalizedPath = String(relativePath).replace(/^\/+/, '')
  if (normalizedPath.endsWith('/catalog.json')) {
    if (!catalogPromise) {
      const pendingCatalog = fetchAssetJson(request, assets, normalizedPath)
      catalogPromise = pendingCatalog
      pendingCatalog.catch(() => {
        if (catalogPromise === pendingCatalog) {
          catalogPromise = undefined
        }
      })
    }
    return catalogPromise
  }

  if (recentJsonPath === normalizedPath && recentJsonPromise) {
    return recentJsonPromise
  }

  const pending = fetchAssetJson(request, assets, normalizedPath)
  recentJsonPath = normalizedPath
  recentJsonPromise = pending
  pending.catch(() => {
    if (recentJsonPromise === pending) {
      recentJsonPath = undefined
      recentJsonPromise = undefined
    }
  })
  return pending
}

async function fetchAssetJson(request, assets, normalizedPath) {
  const response = await assets.fetch(new Request(new URL(`${APP_PATH}/${normalizedPath}`, request.url), {
    headers: { Accept: 'application/json' },
  }))
  if (!response.ok) {
    throw new Error(`Could not load SEO source ${normalizedPath} (HTTP ${response.status})`)
  }
  return response.json()
}
