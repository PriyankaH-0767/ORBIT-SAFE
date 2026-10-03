import React, { useEffect, useRef, useState, useMemo } from 'react'
import Plotly from 'plotly.js-dist-min'
import type { CandidateResultItem } from '../../types/candidate'

export type YAxisMetric = 'risk_score' | 'accepted_event_count' | 'minimum_miss_distance_km'

interface CandidateTradeoffExplorerProps {
  candidates: CandidateResultItem[]
  selectedCandidateId?: string | null
  comparisonCandidateIds?: string[]
  onSelectCandidate: (candidate: CandidateResultItem) => void
  isLoading?: boolean
}

const COMPARISON_PALETTE = ['#00F0FF', '#10B981', '#F59E0B', '#A855F7', '#EC4899']

export const CandidateTradeoffExplorer: React.FC<CandidateTradeoffExplorerProps> = ({
  candidates,
  selectedCandidateId,
  comparisonCandidateIds = [],
  onSelectCandidate,
  isLoading = false,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const [yMetric, setYMetric] = useState<YAxisMetric>('risk_score')

  const metricConfig = useMemo(() => {
    switch (yMetric) {
      case 'accepted_event_count':
        return {
          label: 'Close-Approach Events',
          axisTitle: 'Screened Close-Approach Events (count)',
          extractY: (c: CandidateResultItem) => c.accepted_event_count ?? 0,
        }
      case 'minimum_miss_distance_km':
        return {
          label: 'Minimum Miss Distance',
          axisTitle: 'Minimum Miss Distance (km)',
          extractY: (c: CandidateResultItem) => c.minimum_miss_distance_km ?? null,
        }
      case 'risk_score':
      default:
        return {
          label: 'Screening Risk Score',
          axisTitle: 'Screening Risk Score (/100)',
          extractY: (c: CandidateResultItem) => c.risk_score,
        }
    }
  }, [yMetric])

  // Selected candidate object for text equivalent
  const selectedCandidate = useMemo(
    () => candidates.find((c) => c.candidate_id === selectedCandidateId) ?? null,
    [candidates, selectedCandidateId]
  )

  useEffect(() => {
    if (!containerRef.current || isLoading || candidates.length === 0) return

    // Build hover text strictly using backend-provided values without analytical interpolation
    const formatTooltip = (c: CandidateResultItem): string => {
      const rankStr = c.rank != null ? `#${c.rank}` : 'Not available'
      const altStr = c.altitude_km != null ? `${c.altitude_km.toFixed(1)} km` : 'Not available'
      const incStr = c.inclination_deg != null ? `${c.inclination_deg.toFixed(2)}°` : 'Not available'
      const delayStr =
        c.deployment_delay_minutes != null
          ? `${c.deployment_delay_minutes.toFixed(1)} min`
          : 'Not available'
      const dvStr = c.delta_v_m_s != null ? `${c.delta_v_m_s.toFixed(2)} m/s` : 'Not available'
      const riskStr = c.risk_score != null ? `${c.risk_score.toFixed(1)} / 100` : 'Not available'
      const eventStr =
        c.accepted_event_count != null ? `${c.accepted_event_count}` : 'Not available'
      const missStr =
        c.minimum_miss_distance_km != null
          ? `${c.minimum_miss_distance_km.toFixed(2)} km`
          : 'Not available'

      return [
        `<b>Candidate:</b> ${c.candidate_id}`,
        `<b>Rank:</b> ${rankStr}`,
        `<b>Altitude:</b> ${altStr}`,
        `<b>Inclination:</b> ${incStr}`,
        `<b>Deployment Delay:</b> ${delayStr}`,
        `<b>Estimated Δv:</b> ${dvStr}`,
        `<b>Screening Risk Score:</b> ${riskStr}`,
        `<b>Event Count:</b> ${eventStr}`,
        `<b>Minimum Miss Distance:</b> ${missStr}`,
      ].join('<br>')
    }

    const xValues: number[] = []
    const yValues: (number | null)[] = []
    const hoverTexts: string[] = []
    const customData: CandidateResultItem[] = []
    const markerColors: string[] = []
    const markerSizes: number[] = []
    const markerLineColors: string[] = []
    const markerLineWidths: number[] = []
    const markerOpacities: number[] = []

    candidates.forEach((c) => {
      xValues.push(c.delta_v_m_s)
      yValues.push(metricConfig.extractY(c))
      hoverTexts.push(formatTooltip(c))
      customData.push(c)

      const isSelected = c.candidate_id === selectedCandidateId
      const compareIndex = comparisonCandidateIds.indexOf(c.candidate_id)
      const isComparing = compareIndex >= 0

      if (isSelected) {
        markerColors.push('#00F0FF')
        markerSizes.push(14)
        markerLineColors.push('#ffffff')
        markerLineWidths.push(2.5)
        markerOpacities.push(1.0)
      } else if (isComparing) {
        const color = COMPARISON_PALETTE[compareIndex % COMPARISON_PALETTE.length]
        markerColors.push(color)
        markerSizes.push(12)
        markerLineColors.push('#ffffff')
        markerLineWidths.push(1.8)
        markerOpacities.push(0.95)
      } else {
        markerColors.push(c.within_dv_budget ? '#38bdf8' : '#f43f5e')
        markerSizes.push(8)
        markerLineColors.push('#0f172a')
        markerLineWidths.push(1.0)
        markerOpacities.push(0.7)
      }
    })

    const trace: Plotly.Data = {
      type: 'scatter',
      mode: 'markers',
      x: xValues,
      y: yValues as number[],
      text: hoverTexts,
      hoverinfo: 'text',
      customdata: customData as unknown as Plotly.Datum[],
      marker: {
        size: markerSizes,
        color: markerColors,
        opacity: markerOpacities,
        line: {
          color: markerLineColors,
          width: markerLineWidths,
        },
      },
    }

    const layout: Partial<Plotly.Layout> = {
      title: {
        text: `Candidate Trade-Offs: Estimated Δv vs. ${metricConfig.label}`,
        font: {
          family: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
          size: 13,
          color: '#f8fafc',
        },
        x: 0.04,
        y: 0.96,
      },
      xaxis: {
        title: {
          text: 'Estimated Δv (m/s)',
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
          text: metricConfig.axisTitle,
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
      margin: { t: 45, r: 30, b: 55, l: 65 },
      autosize: true,
      height: 420,
      hoverlabel: {
        bgcolor: '#090d16',
        bordercolor: '#38bdf8',
        font: {
          family: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
          size: 11,
          color: '#f8fafc',
        },
      },
    }

    const config: Partial<Plotly.Config> = {
      responsive: true,
      displaylogo: false,
      modeBarButtonsToRemove: ['sendChartToCloud', 'lasso2d', 'select2d'],
    }

    const chartEl = containerRef.current

    Plotly.react(chartEl, [trace], layout, config).then(() => {
      const anyEl = chartEl as unknown as {
        on?: (
          event: string,
          callback: (eventData: { points?: Array<{ customdata?: CandidateResultItem | null }> }) => void
        ) => void
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
  }, [
    candidates,
    isLoading,
    metricConfig,
    onSelectCandidate,
    selectedCandidateId,
    comparisonCandidateIds,
  ])

  return (
    <div
      data-testid="candidate-tradeoff-explorer"
      className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 sm:p-5 shadow-sm space-y-4"
    >
      {/* Header and Explanatory Copy */}
      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-3 border-b border-slate-800 pb-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-bold text-white font-mono uppercase tracking-wider flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
              CANDIDATE TRADE-OFF EXPLORER
            </h4>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-950/60 text-cyan-300 border border-cyan-800">
              {candidates.length} evaluated
            </span>
          </div>
          <p className="text-xs text-slate-300 font-mono">
            Each point represents one candidate configuration from the evaluated search space.
          </p>
          <p className="text-xs text-slate-400 font-mono">
            Use this view to explore relative trade-offs between estimated propulsion demand and screening indicators.
          </p>
          <p className="text-[11px] text-amber-400/90 font-mono">
            Screening heuristic • Backend-derived values • Non-operational
          </p>
        </div>

        {/* Y-Axis Metric Switcher */}
        <div className="flex flex-wrap items-center gap-1.5 self-start md:self-auto bg-slate-950/80 p-1.5 rounded-lg border border-slate-800">
          <span className="text-[10px] font-mono uppercase text-slate-400 px-1">Y-Axis:</span>
          <button
            type="button"
            data-testid="tradeoff-metric-risk"
            onClick={() => setYMetric('risk_score')}
            aria-pressed={yMetric === 'risk_score'}
            className={`px-2.5 py-1 text-xs font-mono rounded transition-colors cursor-pointer ${
              yMetric === 'risk_score'
                ? 'bg-cyan-500 text-slate-950 font-bold shadow-sm'
                : 'text-slate-300 hover:text-white hover:bg-slate-800'
            }`}
          >
            Risk Score
          </button>
          <button
            type="button"
            data-testid="tradeoff-metric-events"
            onClick={() => setYMetric('accepted_event_count')}
            aria-pressed={yMetric === 'accepted_event_count'}
            className={`px-2.5 py-1 text-xs font-mono rounded transition-colors cursor-pointer ${
              yMetric === 'accepted_event_count'
                ? 'bg-cyan-500 text-slate-950 font-bold shadow-sm'
                : 'text-slate-300 hover:text-white hover:bg-slate-800'
            }`}
          >
            Event Count
          </button>
          <button
            type="button"
            data-testid="tradeoff-metric-miss"
            onClick={() => setYMetric('minimum_miss_distance_km')}
            aria-pressed={yMetric === 'minimum_miss_distance_km'}
            className={`px-2.5 py-1 text-xs font-mono rounded transition-colors cursor-pointer ${
              yMetric === 'minimum_miss_distance_km'
                ? 'bg-cyan-500 text-slate-950 font-bold shadow-sm'
                : 'text-slate-300 hover:text-white hover:bg-slate-800'
            }`}
          >
            Minimum Miss Distance
          </button>
        </div>
      </div>

      {/* Chart Canvas or Loading State */}
      {isLoading ? (
        <div
          data-testid="tradeoff-loading"
          className="p-12 text-center text-xs font-mono text-slate-400 bg-slate-950/40 border border-slate-800 rounded-lg space-y-2 h-[420px] flex flex-col items-center justify-center"
        >
          <div className="animate-spin w-6 h-6 border-2 border-cyan-400 border-t-transparent rounded-full mx-auto" />
          <p>Loading candidate trade-off data…</p>
        </div>
      ) : candidates.length === 0 ? (
        <div className="p-8 text-center text-xs font-mono text-slate-400 bg-slate-950/40 border border-slate-800 rounded-lg">
          No evaluated candidate data available to plot.
        </div>
      ) : (
        <div className="space-y-2">
          <div
            ref={containerRef}
            data-testid="plotly-tradeoff-scatter"
            className="w-full h-[420px]"
            aria-label={`Interactive 2D trade-off scatter plot of Estimated Delta-V vs ${metricConfig.label}`}
          />

          {/* Accessible Text Equivalent & Point Summary */}
          <div className="flex flex-wrap items-center justify-between text-[11px] font-mono text-slate-400 pt-1 border-t border-slate-800/80 px-1 gap-2">
            <div>
              {selectedCandidate ? (
                <span className="text-cyan-300">
                  Selected: <strong className="text-white font-bold">{selectedCandidate.candidate_id}</strong>
                  {selectedCandidate.rank != null && ` (Rank #${selectedCandidate.rank})`} — Δv:{' '}
                  {selectedCandidate.delta_v_m_s.toFixed(2)} m/s, Risk:{' '}
                  {selectedCandidate.risk_score.toFixed(1)}/100
                </span>
              ) : (
                <span>Click any point on the scatter plot to select and synchronize candidate inspection.</span>
              )}
            </div>
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1">
                <span className="w-2.5 h-2.5 rounded-full bg-sky-400 inline-block" /> Budget OK
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2.5 h-2.5 rounded-full bg-rose-500 inline-block" /> Over Budget
              </span>
              <span className="flex items-center gap-1">
                <span className="w-3 h-3 rounded-full border-2 border-white bg-cyan-400 inline-block" /> Selected
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
