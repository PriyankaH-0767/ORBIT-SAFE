/**
 * Export API client (Phase P24).
 * Downloads backend-generated CSV archives and PDF executive screening reports.
 * Strictly read-only serialization over persisted backend results.
 * ZERO client-side CSV or PDF generation.
 */

import { API_BASE_URL, ApiError } from './client'
import { extractFilenameFromContentDisposition, triggerBrowserDownload } from '../utils/download'

/**
 * Downloads the machine-readable CSV export package (ZIP archive containing plan,
 * candidates, events, and validation data).
 *
 * Endpoint: GET /api/v1/runs/{run_id}/exports/csv
 * Returns the downloaded filename.
 */
export async function downloadRunCsv(runId: string): Promise<string> {
  const normalizedRunId = encodeURIComponent(runId.trim())
  const endpoint = `${API_BASE_URL}/api/v1/runs/${normalizedRunId}/exports/csv`

  let response: Response
  try {
    response = await fetch(endpoint, {
      method: 'GET',
      headers: {
        Accept: 'application/zip, application/octet-stream',
      },
    })
  } catch (err) {
    const errorMsg = err instanceof Error ? err.message : 'Network error'
    throw new ApiError(
      `Unable to connect to D-DATO backend at ${API_BASE_URL}. (${errorMsg})`,
      0
    )
  }

  if (!response.ok) {
    let errorDetail = 'CSV export is temporarily unavailable.'
    try {
      const errorJson = await response.json()
      if (errorJson && typeof errorJson === 'object' && 'detail' in errorJson) {
        const detail = (errorJson as { detail: unknown }).detail
        if (response.status === 404) {
          errorDetail = 'Screening run was not found.'
        } else if (typeof detail === 'string') {
          errorDetail = detail
        } else if (detail && typeof detail === 'object' && 'message' in detail) {
          // If code is EXPORT_GENERATION_ERROR or generic error, provide user-facing message
          const msg = String((detail as { message: unknown }).message)
          if (msg.toLowerCase().includes('failed') || msg.toLowerCase().includes('error')) {
            errorDetail = 'CSV export is temporarily unavailable.'
          } else {
            errorDetail = msg
          }
        }
      }
    } catch {
      // response wasn't JSON
    }
    throw new ApiError(errorDetail, response.status)
  }

  const contentDisposition = response.headers.get('Content-Disposition')
  const filename =
    extractFilenameFromContentDisposition(contentDisposition) ||
    `d-dato-${runId}-export.zip`

  const blob = await response.blob()
  triggerBrowserDownload(blob, filename)
  return filename
}

/**
 * Downloads the backend-generated executive PDF screening report.
 *
 * Endpoint: GET /api/v1/runs/{run_id}/exports/pdf
 * Returns the downloaded filename.
 */
export async function downloadRunPdf(runId: string): Promise<string> {
  const normalizedRunId = encodeURIComponent(runId.trim())
  const endpoint = `${API_BASE_URL}/api/v1/runs/${normalizedRunId}/exports/pdf`

  let response: Response
  try {
    response = await fetch(endpoint, {
      method: 'GET',
      headers: {
        Accept: 'application/pdf',
      },
    })
  } catch (err) {
    const errorMsg = err instanceof Error ? err.message : 'Network error'
    throw new ApiError(
      `Unable to connect to D-DATO backend at ${API_BASE_URL}. (${errorMsg})`,
      0
    )
  }

  if (!response.ok) {
    let errorDetail = 'PDF report is temporarily unavailable.'
    try {
      const errorJson = await response.json()
      if (errorJson && typeof errorJson === 'object' && 'detail' in errorJson) {
        const detail = (errorJson as { detail: unknown }).detail
        if (response.status === 404) {
          errorDetail = 'Screening run was not found.'
        } else if (typeof detail === 'string') {
          errorDetail = detail
        } else if (detail && typeof detail === 'object' && 'message' in detail) {
          const msg = String((detail as { message: unknown }).message)
          if (msg.toLowerCase().includes('failed') || msg.toLowerCase().includes('error')) {
            errorDetail = 'PDF report is temporarily unavailable.'
          } else {
            errorDetail = msg
          }
        }
      }
    } catch {
      // response wasn't JSON
    }
    throw new ApiError(errorDetail, response.status)
  }

  const contentDisposition = response.headers.get('Content-Disposition')
  const filename =
    extractFilenameFromContentDisposition(contentDisposition) ||
    `d-dato-${runId}-report.pdf`

  const blob = await response.blob()
  triggerBrowserDownload(blob, filename)
  return filename
}
