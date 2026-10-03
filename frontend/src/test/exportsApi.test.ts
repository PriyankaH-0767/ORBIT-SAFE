import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { downloadRunCsv, downloadRunPdf } from '../api/exports'
import { ApiError } from '../api/client'
import * as downloadUtils from '../utils/download'

describe('Exports API Client (Phase P24)', () => {
  let mockTriggerDownload: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    vi.clearAllMocks()
    mockTriggerDownload = vi
      .spyOn(downloadUtils, 'triggerBrowserDownload')
      .mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('1. requests correct CSV URL and triggers browser download with backend filename', async () => {
    const mockBlob = new Blob(['sample-zip-bytes'], { type: 'application/zip' })
    const mockResponse = {
      ok: true,
      status: 200,
      headers: new Headers({
        'Content-Disposition': 'attachment; filename="d-dato-custom-run-export.zip"',
        'Content-Type': 'application/zip',
      }),
      blob: vi.fn().mockResolvedValue(mockBlob),
    } as unknown as Response

    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse)

    const filename = await downloadRunCsv('test-run-123')

    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
    const [url, options] = (globalThis.fetch as any).mock.calls[0]
    expect(url).toContain('/api/v1/runs/test-run-123/exports/csv')
    expect(options.method).toBe('GET')
    expect(filename).toBe('d-dato-custom-run-export.zip')
    expect(mockTriggerDownload).toHaveBeenCalledWith(mockBlob, 'd-dato-custom-run-export.zip')
  })

  it('2. requests correct PDF URL and triggers browser download with fallback filename if header missing', async () => {
    const mockBlob = new Blob(['sample-pdf-bytes'], { type: 'application/pdf' })
    const mockResponse = {
      ok: true,
      status: 200,
      headers: new Headers({
        'Content-Type': 'application/pdf',
      }),
      blob: vi.fn().mockResolvedValue(mockBlob),
    } as unknown as Response

    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse)

    const filename = await downloadRunPdf('test-run-456')

    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
    const [url, options] = (globalThis.fetch as any).mock.calls[0]
    expect(url).toContain('/api/v1/runs/test-run-456/exports/pdf')
    expect(options.method).toBe('GET')
    expect(filename).toBe('d-dato-test-run-456-report.pdf')
    expect(mockTriggerDownload).toHaveBeenCalledWith(mockBlob, 'd-dato-test-run-456-report.pdf')
  })

  it('3. handles 404 run not found error on CSV export', async () => {
    const mockResponse = {
      ok: false,
      status: 404,
      json: vi.fn().mockResolvedValue({
        detail: {
          code: 'RUN_NOT_FOUND',
          message: "Run 'unknown-run' was not found.",
        },
      }),
    } as unknown as Response

    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse)

    await expect(downloadRunCsv('unknown-run')).rejects.toThrow(ApiError)
    expect(mockTriggerDownload).not.toHaveBeenCalled()
  })

  it('4. handles 500 export generation error with clean message', async () => {
    const mockResponse = {
      ok: false,
      status: 500,
      json: vi.fn().mockResolvedValue({
        detail: {
          code: 'EXPORT_GENERATION_ERROR',
          message: 'Failed to generate PDF screening report.',
        },
      }),
    } as unknown as Response

    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse)

    await expect(downloadRunPdf('test-run-789')).rejects.toThrow(
      'PDF report is temporarily unavailable.'
    )
    expect(mockTriggerDownload).not.toHaveBeenCalled()
  })

  it('5. handles network failure gracefully without exposing raw traces', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('Failed to fetch'))

    await expect(downloadRunCsv('test-run-999')).rejects.toThrow(ApiError)
    expect(mockTriggerDownload).not.toHaveBeenCalled()
  })
})
