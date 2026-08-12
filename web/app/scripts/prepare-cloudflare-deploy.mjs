import { cp, mkdir, readdir, rm, stat } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const buildDirectory = resolve(projectRoot, 'dist')
const assetRoot = resolve(projectRoot, 'cloudflare-dist')
const appDirectory = resolve(assetRoot, 'isr-electionmap')
const maxAssetBytes = 25 * 1024 * 1024
const maxAssetFiles = 20_000

async function collectFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  const nestedFiles = await Promise.all(
    entries.map(async (entry) => {
      const path = resolve(directory, entry.name)
      return entry.isDirectory() ? collectFiles(path) : [path]
    }),
  )

  return nestedFiles.flat()
}

await rm(assetRoot, { force: true, recursive: true })
await mkdir(assetRoot, { recursive: true })
await cp(buildDirectory, appDirectory, { recursive: true })

const files = await collectFiles(assetRoot)
if (files.length > maxAssetFiles) {
  throw new Error(`Cloudflare asset limit exceeded: ${files.length} files`)
}

const fileSizes = await Promise.all(
  files.map(async (path) => ({ path, bytes: (await stat(path)).size })),
)
const oversized = fileSizes.find(({ bytes }) => bytes > maxAssetBytes)
if (oversized) {
  throw new Error(`Cloudflare asset limit exceeded by ${oversized.path}`)
}

const totalBytes = fileSizes.reduce((sum, { bytes }) => sum + bytes, 0)
console.log(
  `Prepared ${files.length} files (${(totalBytes / 1024 / 1024).toFixed(2)} MiB) under /isr-electionmap/.`,
)
