/**
 * Format ISO datetime string as clear UTC: YYYY-MM-DD HH:MM:SS UTC
 */
export function formatTCAtoUTC(isoString: string): string {
  try {
    const d = new Date(isoString)
    if (isNaN(d.getTime())) {
      return isoString.replace('T', ' ').replace('Z', ' UTC')
    }
    const year = d.getUTCFullYear()
    const month = String(d.getUTCMonth() + 1).padStart(2, '0')
    const day = String(d.getUTCDate()).padStart(2, '0')
    const hours = String(d.getUTCHours()).padStart(2, '0')
    const mins = String(d.getUTCMinutes()).padStart(2, '0')
    const secs = String(d.getUTCSeconds()).padStart(2, '0')
    return `${year}-${month}-${day} ${hours}:${mins}:${secs} UTC`
  } catch {
    return isoString
  }
}

export const formatIsoUtc = formatTCAtoUTC

