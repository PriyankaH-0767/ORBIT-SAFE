import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'

// Global mock for ResizeObserver in jsdom
if (typeof window !== 'undefined') {
  ;(globalThis as any).ResizeObserver = class ResizeObserver {
    observe = vi.fn()
    unobserve = vi.fn()
    disconnect = vi.fn()
  } as any
}

// Global mock for Cesium WebGL-dependent classes in jsdom
// Math classes (Cartesian3, Matrix3, Transforms, JulianDate, etc.) remain authentic
vi.mock('cesium', async (importOriginal) => {
  const actual = await importOriginal<typeof import('cesium')>()
  return {
    ...actual,
    Viewer: class MockViewer {
      clock = {
        startTime: null,
        stopTime: null,
        currentTime: new actual.JulianDate(),
        clockRange: 0,
        multiplier: 1,
        shouldAnimate: false,
        onTick: {
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
        },
      }
      entities = {
        add: vi.fn(),
        removeAll: vi.fn(),
        getById: vi.fn(),
      }
      imageryLayers = {
        add: vi.fn(),
      }
      camera = {
        setView: vi.fn(),
        flyTo: vi.fn(),
      }
      scene = {
        canvas: document.createElement('canvas'),
        pick: vi.fn(),
      }
      resize = vi.fn()
      isDestroyed = vi.fn().mockReturnValue(false)
      destroy = vi.fn()
    },
    ScreenSpaceEventHandler: class MockHandler {
      setInputAction = vi.fn()
      destroy = vi.fn()
      isDestroyed = vi.fn().mockReturnValue(false)
    },
    TileMapServiceImageryProvider: {
      fromUrl: vi.fn().mockResolvedValue({}),
    },
  }
})
