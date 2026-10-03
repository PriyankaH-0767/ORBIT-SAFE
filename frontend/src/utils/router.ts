import { useState, useEffect, useCallback } from 'react'

export type AppRoute =
  | { name: 'planner' }
  | { name: 'results'; runId: string }

export function parseRoute(path: string): AppRoute {
  const cleanPath = path.split('?')[0].replace(/\/+$/, '') || '/'

  const resultsMatch = cleanPath.match(/^\/results\/([^/]+)$/)
  if (resultsMatch) {
    return { name: 'results', runId: decodeURIComponent(resultsMatch[1]) }
  }

  return { name: 'planner' }
}

export function navigateTo(path: string): void {
  if (typeof window !== 'undefined') {
    window.history.pushState(null, '', path)
    window.dispatchEvent(new PopStateEvent('popstate'))
  }
}

export function useAppRoute(): {
  route: AppRoute
  navigate: (path: string) => void
} {
  const [route, setRoute] = useState<AppRoute>(() => {
    if (typeof window !== 'undefined') {
      return parseRoute(window.location.pathname)
    }
    return { name: 'planner' }
  })

  useEffect(() => {
    const handlePopState = () => {
      setRoute(parseRoute(window.location.pathname))
    }

    window.addEventListener('popstate', handlePopState)
    return () => {
      window.removeEventListener('popstate', handlePopState)
    }
  }, [])

  const navigate = useCallback((path: string) => {
    navigateTo(path)
  }, [])

  return { route, navigate }
}
