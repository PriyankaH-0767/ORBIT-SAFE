import React, { useState } from 'react'
import { downloadRunCsv, downloadRunPdf } from '../../api/exports'
import { ApiError } from '../../api/client'

export interface ExportControlsProps {
  runId: string
  disabled?: boolean
}

export const ExportControls: React.FC<ExportControlsProps> = ({
  runId,
  disabled = false,
}) => {
  const [isCsvDownloading, setIsCsvDownloading] = useState<boolean>(false)
  const [isPdfDownloading, setIsPdfDownloading] = useState<boolean>(false)
  const [csvError, setCsvError] = useState<string | null>(null)
  const [pdfError, setPdfError] = useState<string | null>(null)
  const [lastDownloadedFile, setLastDownloadedFile] = useState<string | null>(null)

  const handleDownloadCsv = async () => {
    if (isCsvDownloading || disabled) return
    setIsCsvDownloading(true)
    setCsvError(null)
    setLastDownloadedFile(null)

    try {
      const filename = await downloadRunCsv(runId)
      setLastDownloadedFile(filename)
    } catch (err) {
      if (err instanceof ApiError) {
        setCsvError(err.message || 'CSV export is temporarily unavailable.')
      } else {
        setCsvError('Unable to generate the requested export.')
      }
    } finally {
      setIsCsvDownloading(false)
    }
  }

  const handleDownloadPdf = async () => {
    if (isPdfDownloading || disabled) return
    setIsPdfDownloading(true)
    setPdfError(null)
    setLastDownloadedFile(null)

    try {
      const filename = await downloadRunPdf(runId)
      setLastDownloadedFile(filename)
    } catch (err) {
      if (err instanceof ApiError) {
        setPdfError(err.message || 'PDF report is temporarily unavailable.')
      } else {
        setPdfError('Unable to generate the requested export.')
      }
    } finally {
      setIsPdfDownloading(false)
    }
  }

  return (
    <section
      aria-labelledby="export-section-heading"
      className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4 font-sans"
    >
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-800/80 pb-3">
        <div>
          <h3
            id="export-section-heading"
            className="text-base font-bold text-white font-mono flex items-center gap-2"
          >
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400"></span>
            Export Results
          </h3>
          <p className="text-xs text-slate-400 mt-0.5 font-mono">
            Download backend-generated data artifacts and executive summary reports.
          </p>
        </div>

        {lastDownloadedFile && (
          <div className="text-xs font-mono text-emerald-400 bg-emerald-950/60 border border-emerald-800/60 rounded px-2.5 py-1 flex items-center gap-1.5 self-start sm:self-auto">
            <span>✓</span>
            <span>Downloaded {lastDownloadedFile}</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* CSV Export Card */}
        <div className="bg-slate-950/70 border border-slate-800 rounded-lg p-4 flex flex-col justify-between space-y-3">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-200 font-mono flex items-center gap-1.5">
                <svg className="w-4 h-4 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                CSV Data Package
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-950/80 text-cyan-300 border border-cyan-800">
                .ZIP (Multi-CSV)
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-2 leading-relaxed">
              Machine-readable ZIP containing plan, candidates, conjunction events, and validation data when available.
            </p>
          </div>

          {csvError && (
            <div className="text-xs text-rose-400 bg-rose-950/40 border border-rose-900/60 rounded p-2 font-mono flex items-center justify-between">
              <span>{csvError}</span>
              <button
                type="button"
                onClick={handleDownloadCsv}
                className="text-[11px] underline text-rose-300 hover:text-white cursor-pointer ml-2"
              >
                Retry
              </button>
            </div>
          )}

          <button
            type="button"
            onClick={handleDownloadCsv}
            disabled={isCsvDownloading || disabled}
            aria-label="Download CSV Package"
            className="w-full px-4 py-2.5 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-800 disabled:text-slate-500 text-white text-xs font-mono font-medium rounded-lg transition-colors flex items-center justify-center gap-2 cursor-pointer disabled:cursor-not-allowed shadow"
          >
            {isCsvDownloading ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white/80 border-t-transparent rounded-full animate-spin"></div>
                <span>Preparing CSV…</span>
              </>
            ) : (
              <>
                <span>Download CSV Package</span>
              </>
            )}
          </button>
        </div>

        {/* PDF Export Card */}
        <div className="bg-slate-950/70 border border-slate-800 rounded-lg p-4 flex flex-col justify-between space-y-3">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-200 font-mono flex items-center gap-1.5">
                <svg className="w-4 h-4 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                </svg>
                PDF Executive Screening Report
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-950/80 text-indigo-300 border border-indigo-800">
                .PDF
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-2 leading-relaxed">
              Printable screening summary generated by the D-DATO backend.
            </p>
          </div>

          {pdfError && (
            <div className="text-xs text-rose-400 bg-rose-950/40 border border-rose-900/60 rounded p-2 font-mono flex items-center justify-between">
              <span>{pdfError}</span>
              <button
                type="button"
                onClick={handleDownloadPdf}
                className="text-[11px] underline text-rose-300 hover:text-white cursor-pointer ml-2"
              >
                Retry
              </button>
            </div>
          )}

          <button
            type="button"
            onClick={handleDownloadPdf}
            disabled={isPdfDownloading || disabled}
            aria-label="Download PDF Report"
            className="w-full px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-500 text-white text-xs font-mono font-medium rounded-lg transition-colors flex items-center justify-center gap-2 cursor-pointer disabled:cursor-not-allowed shadow"
          >
            {isPdfDownloading ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white/80 border-t-transparent rounded-full animate-spin"></div>
                <span>Preparing PDF…</span>
              </>
            ) : (
              <>
                <span>Download PDF Report</span>
              </>
            )}
          </button>
        </div>
      </div>
    </section>
  )
}
