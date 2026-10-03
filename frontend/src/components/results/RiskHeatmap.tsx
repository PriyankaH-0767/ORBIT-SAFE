import React, { useEffect, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'
import type { HeatmapLayer, HeatmapCell } from '../../types/heatmap'
import { buildHeatmapTrace } from '../../utils/heatmap'

interface RiskHeatmapProps {
  layer: HeatmapLayer | null
  onSelectCandidate?: (cell: HeatmapCell) => void
  isLoading?: boolean
}

export const RiskHeatmap: React.FC<RiskHeatmapProps> = ({
  layer,
  onSelectCandidate,
  isLoading = false,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current || !layer || isLoading) return

    const { hoverText, customData } = buildHeatmapTrace(layer)

    const trace: Plotly.Data = {
      type: 'heatmap',
      x: layer.delay_values_minutes,
      y: layer.altitude_values_km,
      z: layer.values,
      text: hoverText,
      hoverinfo: 'text',
      customdata: customData as unknown as Plotly.Datum[],
      colorscale: 'Viridis',
      zmin: 0,
      zmax: 100,
      connectgaps: false,
      colorbar: {
        title: {
          text: 'Screening Risk Score',
          side: 'right',
          font: {
            family: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
            size: 11,
            color: '#cbd5e1',
          },
        },
        tickfont: {
          family: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
          size: 10,
          color: '#94a3b8',
        },
        len: 0.9,
        thickness: 16,
        outlinewidth: 0,
      },
    }

    const layout: Partial<Plotly.Layout> = {
      title: {
        text: `Screening Risk Heatmap — ${layer.inclination_deg.toFixed(1)}°`,
        font: {
          family: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
          size: 14,
          color: '#f8fafc',
        },
        x: 0.05,
        y: 0.95,
      },
      xaxis: {
        title: {
          text: 'Deployment Delay (minutes)',
          font: {
            family: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
            size: 12,
            color: '#cbd5e1',
          },
        },
        tickfont: {
          family: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
          size: 11,
          color: '#94a3b8',
        },
        gridcolor: '#1e293b',
        zerolinecolor: '#334155',
      },
      yaxis: {
        title: {
          text: 'Altitude (km)',
          font: {
            family: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
            size: 12,
            color: '#cbd5e1',
          },
        },
        tickfont: {
          family: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
          size: 11,
          color: '#94a3b8',
        },
        gridcolor: '#1e293b',
        zerolinecolor: '#334155',
      },
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'rgba(15, 23, 42, 0.6)',
      margin: { t: 50, r: 40, b: 60, l: 70 },
      autosize: true,
      height: 440,
    }

    const config: Partial<Plotly.Config> = {
      responsive: true,
      displaylogo: false,
      modeBarButtonsToRemove: [
        'sendChartToCloud',
        'lasso2d',
        'select2d',
      ],
    }

    const chartEl = containerRef.current

    Plotly.react(chartEl, [trace], layout, config).then(() => {
      // Attach plotly_click listener
      const anyEl = chartEl as unknown as {
        on?: (event: string, callback: (eventData: { points?: Array<{ customdata?: HeatmapCell | null }> }) => void) => void
      }
      if (anyEl.on) {
        anyEl.on('plotly_click', (eventData) => {
          const pt = eventData?.points?.[0]
          if (pt?.customdata && onSelectCandidate) {
            onSelectCandidate(pt.customdata)
          }
        })
      }
    })

    const handleResize = () => {
      if (chartEl) {
        Plotly.Plots.resize(chartEl)
      }
    }

    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      if (chartEl) {
        Plotly.purge(chartEl)
      }
    }
  }, [layer, isLoading, onSelectCandidate])

  if (isLoading) {
    return (
      <div
        data-testid="heatmap-loading"
        className="p-12 text-center text-xs font-mono text-slate-400 bg-slate-900/60 border border-slate-800 rounded-xl space-y-2 h-[440px] flex flex-col items-center justify-center"
      >
        <div className="animate-spin w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full mx-auto" />
        <p>Loading screening risk heatmap…</p>
      </div>
    )
  }

  if (!layer) {
    return null
  }

  return (
    <div
      data-testid="heatmap-chart-container"
      className="rounded-xl border border-slate-800/90 bg-slate-900/80 p-2 shadow-sm"
    >
      <div
        ref={containerRef}
        data-testid="plotly-heatmap"
        className="w-full h-[440px]"
        aria-label={`Risk Heatmap for ${layer.inclination_deg.toFixed(1)} degrees inclination`}
      />
    </div>
  )
}
