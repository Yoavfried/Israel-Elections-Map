import { describe, expect, it } from 'vitest'
import { calculateVisualViewportPlacement } from './visualViewport'

describe('calculateVisualViewportPlacement', () => {
  it('tracks a keyboard that covers the bottom of an unchanged layout viewport', () => {
    expect(calculateVisualViewportPlacement(932, 500)).toEqual({
      coveredBottom: 432,
      visibleHeight: 500,
    })
  })

  it('accounts for a visual viewport that the browser also pans', () => {
    expect(calculateVisualViewportPlacement(932, 500, 84)).toEqual({
      coveredBottom: 348,
      visibleHeight: 500,
    })
  })

  it('does not double-offset browsers that resize the layout viewport', () => {
    expect(calculateVisualViewportPlacement(500, 500)).toEqual({
      coveredBottom: 0,
      visibleHeight: 500,
    })
  })
})
