import type { HeatmapLayer, HeatmapCell } from '../types/heatmap'

/**
 * Builds tooltip text and customdata matrices matching layer [altitude][delay] dimensions.
 */
export function buildHeatmapTrace(layer: HeatmapLayer) {
  const cellMap = new Map<string, HeatmapCell>()
  for (const cell of layer.cells) {
    const key = `${cell.altitude_km.toFixed(2)}_${cell.delay_minutes.toFixed(2)}`
    cellMap.set(key, cell)
  }

  const hoverText: string[][] = []
  const customData: (HeatmapCell | null)[][] = []

  for (let r = 0; r < layer.altitude_values_km.length; r++) {
    const rowHover: string[] = []
    const rowCustom: (HeatmapCell | null)[] = []
    const alt = layer.altitude_values_km[r]

    for (let c = 0; c < layer.delay_values_minutes.length; c++) {
      const delay = layer.delay_values_minutes[c]
      const key = `${alt.toFixed(2)}_${delay.toFixed(2)}`
      const cell = cellMap.get(key)
      const val = layer.values[r]?.[c]

      if (cell && val != null) {
        rowCustom.push(cell)
        const rankStr = cell.rank != null ? `Rank ${cell.rank}` : '—'
        const riskStr = cell.risk_score != null ? cell.risk_score.toFixed(1) : '—'
        const dvStr = cell.delta_v_m_s != null ? `${cell.delta_v_m_s.toFixed(2)} m/s` : '—'
        const missStr =
          cell.minimum_miss_distance_km != null
            ? `${cell.minimum_miss_distance_km.toFixed(2)} km`
            : '—'
        const eventsCount = cell.accepted_event_count ?? 0
        const uncertainty = cell.uncertainty_level || 'nominal'

        rowHover.push(
          `<b>Candidate:</b> ${cell.candidate_id}<br>` +
          `<b>Rank:</b> ${rankStr}<br>` +
          `<b>Altitude:</b> ${cell.altitude_km.toFixed(1)} km<br>` +
          `<b>Inclination:</b> ${cell.inclination_deg.toFixed(2)}°<br>` +
          `<b>Delay:</b> ${cell.delay_minutes.toFixed(1)} min<br>` +
          `<b>Risk Score:</b> ${riskStr}<br>` +
          `<b>Delta-V:</b> ${dvStr}<br>` +
          `<b>Events:</b> ${eventsCount}<br>` +
          `<b>Min Miss:</b> ${missStr}<br>` +
          `<b>Uncertainty:</b> ${uncertainty}`
        )
      } else {
        rowCustom.push(null)
        rowHover.push(
          `<b>Altitude:</b> ${alt.toFixed(1)} km<br>` +
          `<b>Delay:</b> ${delay.toFixed(1)} min<br>` +
          `<i>No persisted candidate at this grid location.</i>`
        )
      }
    }
    hoverText.push(rowHover)
    customData.push(rowCustom)
  }

  return { hoverText, customData }
}
