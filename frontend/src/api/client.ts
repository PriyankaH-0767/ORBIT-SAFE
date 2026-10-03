/**
 * Base HTTP client for D-DATO REST API.
 * Uses native fetch and normalizes URL and error handling.
 */

function resolveBaseUrl(): string {
  // 1. Explicit runtime override on window (useful for container/cloud injection without rebuilds)
  if (
    typeof window !== 'undefined' &&
    (window as unknown as { __DDATO_API_URL__?: string }).__DDATO_API_URL__
  ) {
    return (window as unknown as { __DDATO_API_URL__: string }).__DDATO_API_URL__!
  }

  const envUrl = import.meta.env.VITE_API_BASE_URL

  // 2. If an explicit environment variable is configured:
  if (envUrl && typeof envUrl === 'string' && envUrl.trim() !== '') {
    const trimmed = envUrl.trim()
    // If the configured URL is localhost/127.0.0.1, but we are running in a production browser
    // on a non-localhost host (like *.up.railway.app), do not send browser requests to localhost!
    // Fall back to same-origin relative URLs so the deployed backend handles the request.
    if (
      typeof window !== 'undefined' &&
      window.location &&
      window.location.hostname &&
      window.location.hostname !== 'localhost' &&
      window.location.hostname !== '127.0.0.1' &&
      (trimmed.includes('localhost') || trimmed.includes('127.0.0.1'))
    ) {
      return ''
    }
    return trimmed
  }

  // 3. In Vite development mode, default to local backend port 8000
  if (import.meta.env.DEV) {
    return 'http://localhost:8000'
  }

  // 4. In production builds, default to relative path (same origin)
  // This allows the full-stack FastAPI app on Railway/Docker to serve both frontend and API seamlessly.
  return ''
}

export const API_BASE_URL = resolveBaseUrl().replace(/\/+$/, '')

export class ApiError extends Error {
  public status: number
  public data: unknown

  constructor(message: string, status: number, data?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

export async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const normalizedEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`
  const url = `${API_BASE_URL}${normalizedEndpoint}`

  const headers = new Headers(options.headers || {})
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json')
  }
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  let response: Response
  try {
    response = await fetch(url, {
      ...options,
      headers,
    })
  } catch (err) {
    const errorMsg = err instanceof Error ? err.message : 'Network error'
    throw new ApiError(
      `Unable to connect to D-DATO backend at ${API_BASE_URL}. (${errorMsg})`,
      0
    )
  }

  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`
    let errorData: unknown = null
    try {
      errorData = await response.json()
      if (errorData && typeof errorData === 'object' && 'detail' in errorData) {
        const detail = (errorData as { detail: unknown }).detail
        if (typeof detail === 'string') {
          errorDetail = detail
        } else if (Array.isArray(detail)) {
          // FastAPI validation error array
          errorDetail = detail.map((d: { msg?: string; loc?: string[] }) => d.msg || JSON.stringify(d)).join(', ')
        } else if (detail && typeof detail === 'object' && 'message' in detail) {
          errorDetail = String((detail as { message: unknown }).message)
        }
      }
    } catch {
      // response wasn't JSON
    }
    throw new ApiError(errorDetail, response.status, errorData)
  }

  return (await response.json()) as T
}
