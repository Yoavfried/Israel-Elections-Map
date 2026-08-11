import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const privacyPath = resolve(process.cwd(), 'public', 'privacy.html')

describe('privacy notice', () => {
  it('publishes Hebrew and English versions', async () => {
    const html = await readFile(privacyPath, 'utf8')

    expect(html).toContain('\u05d4\u05d5\u05d3\u05e2\u05ea \u05e4\u05e8\u05d8\u05d9\u05d5\u05ea')
    expect(html).toContain('Privacy Notice')
    expect(html).toContain('operated by Yoav Fried')
    expect(html).toContain('data-language-panel="he"')
    expect(html).toContain('data-language-panel="en"')
  })

  it('discloses current external services and storage without claiming ads are active', async () => {
    const html = await readFile(privacyPath, 'utf8')

    expect(html).toContain('https://photon.komoot.io/')
    expect(html).toContain('https://openfreemap.org/')
    expect(html).toContain('Local storage')
    expect(html).toContain('the site contains no advertising')
    expect(html).not.toContain('pagead2.googlesyndication.com')
  })
})
