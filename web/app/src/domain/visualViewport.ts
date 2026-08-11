export interface VisualViewportPlacement {
  coveredBottom: number
  visibleHeight: number
}

export function calculateVisualViewportPlacement(
  layoutHeight: number,
  visibleHeight: number,
  visibleTop = 0,
): VisualViewportPlacement {
  return {
    coveredBottom: Math.max(0, layoutHeight - (visibleTop + visibleHeight)),
    visibleHeight,
  }
}
