/**
 * Browser download helper utilities for D-DATO exports (Phase P24).
 */

/**
 * Extracts the filename from a Content-Disposition header string if present.
 * Supports standard format: attachment; filename="d-dato-run-123-export.zip"
 * as well as unquoted: attachment; filename=report.pdf
 * and UTF-8 encoded: filename*=UTF-8''...
 */
export function extractFilenameFromContentDisposition(
  contentDisposition: string | null | undefined
): string | null {
  if (!contentDisposition) return null

  // Check RFC 5987 / RFC 6266 filename* parameter first
  const starMatch = contentDisposition.match(/filename\*\s*=\s*(?:UTF-8''|utf-8'')([^;]+)/i)
  if (starMatch && starMatch[1]) {
    try {
      return decodeURIComponent(starMatch[1].trim().replace(/^["']|["']$/g, ''))
    } catch {
      return starMatch[1].trim().replace(/^["']|["']$/g, '')
    }
  }

  // Check standard filename parameter
  const match = contentDisposition.match(/filename\s*=\s*("([^"]+)"|([^;]+))/i)
  if (match) {
    const raw = match[2] || match[3]
    if (raw) {
      return raw.trim()
    }
  }

  return null
}

/**
 * Triggers a native browser file download using a temporary object URL.
 * Immediately registers and simulates an anchor click, then cleans up.
 * Does not open a new tab by default.
 */
export function triggerBrowserDownload(blob: Blob, filename: string): void {
  if (typeof window === 'undefined') return

  const objectUrl = window.URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = filename
  anchor.style.display = 'none'

  document.body.appendChild(anchor)
  anchor.click()

  // Clean up DOM and revoke temporary object URL
  document.body.removeChild(anchor)
  setTimeout(() => {
    try {
      window.URL.revokeObjectURL(objectUrl)
    } catch {
      // safe fallback in environments without object URL support
    }
  }, 100)
}
