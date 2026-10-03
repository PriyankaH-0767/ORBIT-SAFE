/**
 * Base HTTP client for D-DATO REST API.
 * Uses native fetch and normalizes URL and error handling.
 */

const RAW_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
export const API_BASE_URL = RAW_BASE_URL.replace(/\/+$/, '')

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
