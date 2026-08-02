export const UNMAPPED_GEOGRAPHY_COLOR = '#aeb5b0'

export function normalizeHexColor(value: string): string {
  return /^#[0-9a-f]{6}$/i.test(value) ? value : '#69736d'
}

export function mixHexColors(start: string, end: string, ratio: number): string {
  const startChannels = hexChannels(normalizeHexColor(start))
  const endChannels = hexChannels(normalizeHexColor(end))
  const weight = clampUnit(ratio)
  const channels = startChannels.map((channel, index) =>
    Math.round(channel + (endChannels[index] - channel) * weight),
  )
  return `#${channels.map((channel) => channel.toString(16).padStart(2, '0')).join('')}`
}

export function clampUnit(value: number): number {
  return Math.min(Math.max(value, 0), 1)
}

function hexChannels(value: string): [number, number, number] {
  return [
    Number.parseInt(value.slice(1, 3), 16),
    Number.parseInt(value.slice(3, 5), 16),
    Number.parseInt(value.slice(5, 7), 16),
  ]
}
