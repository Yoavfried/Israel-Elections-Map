import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { translate } from './i18n/translations'

describe('site identity', () => {
  it.each(['he', 'en'] as const)('uses the English map title in the %s interface', (language) => {
    expect(translate(language, 'appTitle')).toBe('Israeli Election Map')
  })

  it('publishes the same map title before the application loads', async () => {
    const html = await readFile(resolve(process.cwd(), 'index.html'), 'utf8')

    expect(html).toContain('<title>Israeli Election Map</title>')
    expect(html).toContain('<meta property="og:title" content="Israeli Election Map" />')
    expect(html).toContain('<meta name="twitter:title" content="Israeli Election Map" />')
  })

  it('uses the portfolio favicon on the map and privacy page', async () => {
    const html = await readFile(resolve(process.cwd(), 'index.html'), 'utf8')
    const privacy = await readFile(resolve(process.cwd(), 'public/privacy.html'), 'utf8')
    const icon = await readFile(resolve(process.cwd(), 'public/favicon.svg'), 'utf8')

    expect(html).toContain('<link rel="icon" href="/favicon.svg" type="image/svg+xml" />')
    expect(privacy).toContain('<link rel="icon" href="./favicon.svg" type="image/svg+xml" />')
    expect(icon).toContain('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">')
  })
})
