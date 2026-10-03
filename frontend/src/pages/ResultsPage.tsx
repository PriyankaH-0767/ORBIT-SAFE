import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { getRun } from '../api/runs'
import { getPlan } from '../api/plans'
import { getRunCandidates } from '../api/candidates'
import { getRunEvents } from '../api/events'
import { getRunHeatmap } from '../api/heatmap'
import { getRunGlobe } from '../api/globe'
import { getRunValidation, createValidation } from '../api/validation'
import { ApiError } from '../api/client'
import { navigateTo } from '../utils/router'
import type { RunStatusResponse } from '../types/run'
import type { PlanResponse } from '../types/plan'
import type { CandidateResultItem } from '../types/candidate'
import type { EventResultItem } from '../types/event'
import type { HeatmapResponse, HeatmapCell } from '../types/heatmap'
import type { GlobeResponse } from '../types/globe'
import type { ValidationResponse, ValidationExecutionRequest } from '../types/validation'

import { ResultsHeader } from '../components/results/ResultsHeader'
import { MissionBriefing } from '../components/results/MissionBriefing'
import { ResultsSummary } from '../components/results/ResultsSummary'
import { CandidateTable } from '../components/results/CandidateTable'
import { CandidateDetailPanel } from '../components/results/CandidateDetailPanel'
import { EventTable } from '../components/results/EventTable'
import { EventDetailPanel } from '../components/results/EventDetailPanel'
import { ConjunctionTimeline } from '../components/results/ConjunctionTimeline'
import { Pagination } from '../components/results/Pagination'
import { ResultsEmptyState } from '../components/results/ResultsEmptyState'
import { HeatmapControls } from '../components/results/HeatmapControls'
import { RiskHeatmap } from '../components/results/RiskHeatmap'
import { GlobeControls } from '../components/results/GlobeControls'
import { GlobeLegend } from '../components/results/GlobeLegend'
import { ValidationSection } from '../components/results/ValidationSection'
import { ExportControls } from '../components/results/ExportControls'
import { DataProvenanceStrip } from '../components/results/DataProvenanceStrip'
import { CandidateComparison } from '../components/results/CandidateComparison'
import { CandidateTradeoffExplorer } from '../components/results/CandidateTradeoffExplorer'
import { JudgeExecutiveSummary } from '../components/results/JudgeExecutiveSummary'

const OrbitGlobe = React.lazy(() =>
  import('../components/results/OrbitGlobe').then((m) => ({ default: m.OrbitGlobe }))
)

interface ResultsPageProps {
  runId: string
}

export const ResultsPage: React.FC<ResultsPageProps> = ({ runId }) => {
  // Authoritative run status
  const [run, setRun] = useState<RunStatusResponse | null>(null)
  const [plan, setPlan] = useState<PlanResponse | null>(null)
  const [isRunLoading, setIsRunLoading] = useState<boolean>(true)
  const [runError, setRunError] = useState<string | null>(null)
  const [runErrorStatus, setRunErrorStatus] = useState<number | null>(null)

  // Candidate pagination & results
  const [candidates, setCandidates] = useState<CandidateResultItem[]>([])
  const [explorerCandidates, setExplorerCandidates] = useState<CandidateResultItem[]>([])
  const [candidateTotal, setCandidateTotal] = useState<number>(0)
  const [candidateOffset, setCandidateOffset] = useState<number>(0)
  const candidateLimit = 20
  const [isCandidatesLoading, setIsCandidatesLoading] = useState<boolean>(true)
  const [candidatesError, setCandidatesError] = useState<string | null>(null)

  // Conjunction events pagination & results
  const [events, setEvents] = useState<EventResultItem[]>([])
  const [timelineEvents, setTimelineEvents] = useState<EventResultItem[]>([])
  const [eventTotal, setEventTotal] = useState<number>(0)
  const [eventOffset, setEventOffset] = useState<number>(0)
  const eventLimit = 20
  const [isEventsLoading, setIsEventsLoading] = useState<boolean>(true)
  const [eventsError, setEventsError] = useState<string | null>(null)

  // Heatmap state
  const [heatmapData, setHeatmapData] = useState<HeatmapResponse | null>(null)
  const [selectedInclination, setSelectedInclination] = useState<number | null>(null)
  const [isHeatmapLoading, setIsHeatmapLoading] = useState<boolean>(true)
  const [heatmapError, setHeatmapError] = useState<string | null>(null)

  // Globe state (Phase P22)
  const [globeData, setGlobeData] = useState<GlobeResponse | null>(null)
  const [isGlobeLoading, setIsGlobeLoading] = useState<boolean>(true)
  const [globeError, setGlobeError] = useState<string | null>(null)
  const [globeSampleStep, setGlobeSampleStep] = useState<number>(300)
  const [globeMaxDebris, setGlobeMaxDebris] = useState<number>(10)
  const [globeMaxCandidates] = useState<number>(5)
  const [showDebris, setShowDebris] = useState<boolean>(true)
  const [isGlobePlaying, setIsGlobePlaying] = useState<boolean>(false)
  const [globePlaybackSpeed, setGlobePlaybackSpeed] = useState<number>(1)
  const [globeCurrentUtcTime, setGlobeCurrentUtcTime] = useState<string>('')
  const globeViewerRef = useRef<any>(null)

  // External Validation state (Phase P23)
  const [validation, setValidation] = useState<ValidationResponse | null>(null)
  const [isValidationLoading, setIsValidationLoading] = useState<boolean>(true)
  const [isValidationRunning, setIsValidationRunning] = useState<boolean>(false)
  const [validationError, setValidationError] = useState<string | null>(null)

  // Selection states
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateResultItem | null>(null)
  const [selectedEvent, setSelectedEvent] = useState<EventResultItem | null>(null)

  // Phase P29.1: Demo View vs Technical View state & collapsibles
  const [viewMode, setViewMode] = useState<'demo' | 'technical'>('demo')
  const [isDemoActive, setIsDemoActive] = useState<boolean>(true)
  const [isCandidateTableExpanded, setIsCandidateTableExpanded] = useState<boolean>(true)
  const [isEventTableExpanded, setIsEventTableExpanded] = useState<boolean>(true)
  const [isTechnicalDetailsExpanded, setIsTechnicalDetailsExpanded] = useState<boolean>(false)

  // Candidate comparison state (Phase P25 Section H)
  const [comparisonCandidates, setComparisonCandidates] = useState<CandidateResultItem[]>([])

  const handleToggleCompare = useCallback((candidate: CandidateResultItem) => {
    setComparisonCandidates((prev) => {
      const exists = prev.some((c) => c.candidate_id === candidate.candidate_id)
      if (exists) {
        return prev.filter((c) => c.candidate_id !== candidate.candidate_id)
      }
      if (prev.length >= 3) {
        return [prev[1], prev[2], candidate]
      }
      return [...prev, candidate]
    })
  }, [])

  const handleRemoveCompare = useCallback((candidateId: string) => {
    setComparisonCandidates((prev) => prev.filter((c) => c.candidate_id !== candidateId))
  }, [])

  const handleClearCompare = useCallback(() => {
    setComparisonCandidates([])
  }, [])

  // Fetch Run Status
  const fetchRunStatus = useCallback(async () => {
    setIsRunLoading(true)
    setRunError(null)
    setRunErrorStatus(null)
    try {
      const data = await getRun(runId)
      setRun(data)
      if (data.plan_id) {
        getPlan(data.plan_id)
          .then((planData) => setPlan(planData))
          .catch(() => {
            // Graceful fallback to default/run parameters
          })
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setRunErrorStatus(err.status)
        if (err.status === 404) {
          setRunError(`Screening run '${runId}' not found. Please verify the run identifier or return to the mission planner.`)
        } else if (err.status === 0) {
          setRunError('Unable to connect to D-DATO backend. Please ensure the backend service is running.')
        } else {
          setRunError(err.message || 'Failed to retrieve screening run status.')
        }
      } else {
        setRunError('An unexpected error occurred while loading the run.')
      }
    } finally {
      setIsRunLoading(false)
    }
  }, [runId])

  // Fetch Candidates
  const fetchCandidates = useCallback(
    async (offset: number) => {
      setIsCandidatesLoading(true)
      setCandidatesError(null)
      try {
        const resp = await getRunCandidates(runId, candidateLimit, offset)
        setCandidates(resp.candidates)
        setCandidateTotal(resp.total)
        setCandidateOffset(resp.offset)
        if (resp.total <= candidateLimit) {
          setExplorerCandidates(resp.candidates)
        } else {
          getRunCandidates(runId, 300, 0)
            .then((all) => setExplorerCandidates(all.candidates))
            .catch(() => setExplorerCandidates(resp.candidates))
        }
      } catch (err) {
        if (err instanceof ApiError) {
          if (err.status === 404) {
            setCandidatesError(`Candidates not found for run '${runId}'.`)
          } else if (err.status === 422) {
            setCandidatesError('Invalid pagination parameters requested for candidates.')
          } else if (err.status === 0) {
            setCandidatesError('Network error while retrieving candidates.')
          } else {
            setCandidatesError(err.message || 'Failed to load candidates.')
          }
        } else {
          setCandidatesError('An unexpected error occurred loading candidates.')
        }
      } finally {
        setIsCandidatesLoading(false)
      }
    },
    [runId]
  )

  // Fetch Events
  const fetchEvents = useCallback(
    async (offset: number) => {
      setIsEventsLoading(true)
      setEventsError(null)
      try {
        const resp = await getRunEvents(runId, eventLimit, offset)
        setEvents(resp.events)
        setEventTotal(resp.total)
        setEventOffset(resp.offset)
        if (resp.total <= eventLimit) {
          setTimelineEvents(resp.events)
        } else {
          getRunEvents(runId, 100, 0)
            .then((all) => setTimelineEvents(all.events))
            .catch(() => setTimelineEvents(resp.events))
        }
      } catch (err) {
        if (err instanceof ApiError) {
          if (err.status === 404) {
            setEventsError(`Conjunction events not found for run '${runId}'.`)
          } else if (err.status === 422) {
            setEventsError('Invalid pagination parameters requested for events.')
          } else if (err.status === 0) {
            setEventsError('Network error while retrieving events.')
          } else {
            setEventsError(err.message || 'Failed to load conjunction events.')
          }
        } else {
          setEventsError('An unexpected error occurred loading events.')
        }
      } finally {
        setIsEventsLoading(false)
      }
    },
    [runId]
  )

  // Fetch Heatmap
  const fetchHeatmap = useCallback(async () => {
    setIsHeatmapLoading(true)
    setHeatmapError(null)
    try {
      const hData = await getRunHeatmap(runId)
      setHeatmapData(hData)
      if (hData.layers.length > 0) {
        setSelectedInclination((prev) =>
          prev != null && hData.layers.some((l) => Math.abs(l.inclination_deg - prev) < 1e-4)
            ? prev
            : hData.layers[0].inclination_deg
        )
      }
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 404) {
          setHeatmapError(`Heatmap data not found for run '${runId}'.`)
        } else if (err.status === 422) {
          setHeatmapError('Invalid parameters requested for heatmap.')
        } else if (err.status === 0) {
          setHeatmapError('Network error while retrieving heatmap data.')
        } else {
          setHeatmapError(err.message || 'Unable to load the screening risk heatmap.')
        }
      } else {
        setHeatmapError('An unexpected error occurred loading the heatmap.')
      }
    } finally {
      setIsHeatmapLoading(false)
    }
  }, [runId])

  // Initial load on mount or runId change
  useEffect(() => {
    let isMounted = true

    const loadInitialData = async () => {
      // 1. Run status
      try {
        const data = await getRun(runId)
        if (isMounted) setRun(data)
        if (data.plan_id) {
          getPlan(data.plan_id)
            .then((planData) => {
              if (isMounted) setPlan(planData)
            })
            .catch(() => {
              // Plan parameters unavailable, MissionBriefing uses fallbacks
            })
        }
      } catch (err) {
        if (isMounted) {
          if (err instanceof ApiError) {
            setRunErrorStatus(err.status)
            if (err.status === 404) {
              setRunError(`Screening run '${runId}' not found. Please verify the run identifier or return to the mission planner.`)
            } else if (err.status === 0) {
              setRunError('Unable to connect to D-DATO backend. Please ensure the backend service is running.')
            } else {
              setRunError(err.message || 'Failed to retrieve screening run status.')
            }
          } else {
            setRunError('An unexpected error occurred while loading the run.')
          }
        }
      } finally {
        if (isMounted) setIsRunLoading(false)
      }

      // 2. Candidates
      try {
        const resp = await getRunCandidates(runId, candidateLimit, 0)
        if (isMounted) {
          setCandidates(resp.candidates)
          setCandidateTotal(resp.total)
          setCandidateOffset(resp.offset)
        }
      } catch (err) {
        if (isMounted) {
          if (err instanceof ApiError) {
            if (err.status === 404) {
              setCandidatesError(`Candidates not found for run '${runId}'.`)
            } else if (err.status === 422) {
              setCandidatesError('Invalid pagination parameters requested for candidates.')
            } else if (err.status === 0) {
              setCandidatesError('Network error while retrieving candidates.')
            } else {
              setCandidatesError(err.message || 'Failed to load candidates.')
            }
          } else {
            setCandidatesError('An unexpected error occurred loading candidates.')
          }
        }
      } finally {
        if (isMounted) setIsCandidatesLoading(false)
      }

      // 3. Events
      try {
        const resp = await getRunEvents(runId, eventLimit, 0)
        if (isMounted) {
          setEvents(resp.events)
          setTimelineEvents(resp.events)
          setEventTotal(resp.total)
          setEventOffset(resp.offset)
        }
      } catch (err) {
        if (isMounted) {
          if (err instanceof ApiError) {
            if (err.status === 404) {
              setEventsError(`Conjunction events not found for run '${runId}'.`)
            } else if (err.status === 422) {
              setEventsError('Invalid pagination parameters requested for events.')
            } else if (err.status === 0) {
              setEventsError('Network error while retrieving events.')
            } else {
              setEventsError(err.message || 'Failed to load conjunction events.')
            }
          } else {
            setEventsError('An unexpected error occurred loading events.')
          }
        }
      } finally {
        if (isMounted) setIsEventsLoading(false)
      }

      // 4. Heatmap
      try {
        const hData = await getRunHeatmap(runId)
        if (isMounted) {
          setHeatmapData(hData)
          if (hData.layers.length > 0) {
            setSelectedInclination(hData.layers[0].inclination_deg)
          }
        }
      } catch (err) {
        if (isMounted) {
          if (err instanceof ApiError) {
            if (err.status === 404) {
              setHeatmapError(`Heatmap data not found for run '${runId}'.`)
            } else if (err.status === 422) {
              setHeatmapError('Invalid parameter for heatmap.')
            } else if (err.status === 0) {
              setHeatmapError('Network error while retrieving heatmap data.')
            } else {
              setHeatmapError(err.message || 'Unable to load the screening risk heatmap.')
            }
          } else {
            setHeatmapError('An unexpected error occurred loading the heatmap.')
          }
        }
      } finally {
        if (isMounted) setIsHeatmapLoading(false)
      }

      // 5. Globe (Phase P22)
      try {
        const gData = await getRunGlobe(runId, {
          sample_step_seconds: 300,
          max_candidates: 5,
          max_debris: 10,
        })
        if (isMounted) {
          setGlobeData(gData)
        }
      } catch (err) {
        if (isMounted) {
          if (err instanceof ApiError) {
            if (err.status === 404) {
              setGlobeError(`Orbital trajectory data not found for run '${runId}'.`)
            } else if (err.status === 0) {
              setGlobeError('Network error while retrieving 3D globe data.')
            } else {
              setGlobeError(err.message || 'Unable to load 3D globe data.')
            }
          } else {
            setGlobeError('Unable to load 3D globe data.')
          }
        }
      } finally {
        if (isMounted) setIsGlobeLoading(false)
      }

      // 6. External Validation (Phase P23)
      try {
        const valData = await getRunValidation(runId)
        if (isMounted) {
          setValidation(valData)
        }
      } catch (err) {
        if (isMounted) {
          if (err instanceof ApiError && err.status === 404) {
            // Normal initial unvalidated state - not an application error
            setValidation(null)
            setValidationError(null)
          } else if (err instanceof ApiError && err.status === 0) {
            setValidationError('Unable to connect to D-DATO backend for validation data.')
          } else {
            setValidationError('Unable to load external reference validation.')
          }
        }
      } finally {
        if (isMounted) setIsValidationLoading(false)
      }
    }

    loadInitialData()

    return () => {
      isMounted = false
    }
  }, [runId])

  // Dedicated Globe data fetcher for control updates & retries
  const fetchGlobeData = useCallback(
    async (step = globeSampleStep, maxDeb = globeMaxDebris) => {
      setIsGlobeLoading(true)
      setGlobeError(null)
      try {
        const data = await getRunGlobe(runId, {
          sample_step_seconds: step,
          max_candidates: globeMaxCandidates,
          max_debris: maxDeb,
        })
        setGlobeData(data)
      } catch (err) {
        if (err instanceof ApiError) {
          if (err.status === 404) {
            setGlobeError(`Orbital trajectory data not found for run '${runId}'.`)
          } else if (err.status === 422) {
            setGlobeError('Invalid query parameters for orbital visualization.')
          } else if (err.status === 0) {
            setGlobeError('Network error while retrieving 3D globe data.')
          } else {
            setGlobeError(err.message || 'Unable to load 3D globe data.')
          }
        } else {
          setGlobeError('Unable to load 3D globe data.')
        }
      } finally {
        setIsGlobeLoading(false)
      }
    },
    [runId, globeSampleStep, globeMaxDebris, globeMaxCandidates]
  )

  const handleChangeSampleStep = (step: number) => {
    setGlobeSampleStep(step)
    fetchGlobeData(step, globeMaxDebris)
  }

  const handleChangeMaxDebris = (maxDeb: number) => {
    setGlobeMaxDebris(maxDeb)
    fetchGlobeData(globeSampleStep, maxDeb)
  }

  const handleResetGlobeView = () => {
    const viewer = globeViewerRef.current
    if (!viewer || viewer.isDestroyed()) return
    if (typeof viewer.camera?.flyHome === 'function') {
      viewer.camera.flyHome(1.0)
    }
  }

  const handleFocusSelectedOnGlobe = () => {
    const viewer = globeViewerRef.current
    if (!viewer || viewer.isDestroyed()) return
    if (selectedCandidate) {
      const entity = viewer.entities.getById(`candidate-marker-${selectedCandidate.candidate_id}`)
      if (entity) {
        viewer.flyTo(entity, { duration: 1.0 })
      }
    } else if (selectedEvent) {
      const entity = viewer.entities.getById(`event-marker-${selectedEvent.id}`)
      if (entity) {
        viewer.flyTo(entity, { duration: 1.0 })
      }
    }
  }

  const handleInspectEventInGlobe = () => {
    const globeSection = document.getElementById('globe-section')
    if (globeSection) {
      globeSection.scrollIntoView({ behavior: 'smooth' })
    }
    handleFocusSelectedOnGlobe()
  }

  // Part 10: Automatic camera focus on selected candidate
  useEffect(() => {
    if (selectedCandidate && globeViewerRef.current && !globeViewerRef.current.isDestroyed()) {
      const viewer = globeViewerRef.current
      try {
        const entity = viewer.entities?.getById?.(`candidate-marker-${selectedCandidate.candidate_id}`)
        if (entity) {
          viewer.flyTo(entity, { duration: 1.0 })
        }
      } catch {
        // Safe fallback in test/mock environments
      }
    }
  }, [selectedCandidate])

  // Part 10: Automatic camera focus on selected conjunction event
  useEffect(() => {
    if (selectedEvent && globeViewerRef.current && !globeViewerRef.current.isDestroyed()) {
      const viewer = globeViewerRef.current
      try {
        const entity = viewer.entities?.getById?.(`event-marker-${selectedEvent.id}`)
        if (entity) {
          viewer.flyTo(entity, { duration: 1.0 })
        }
      } catch {
        // Safe fallback in test/mock environments
      }
    }
  }, [selectedEvent])

  const handleSelectCandidateFromGlobe = (candId: string) => {
    const existing = candidates.find((c) => c.candidate_id === candId)
    if (existing) {
      setSelectedCandidate(existing)
    } else {
      const track = globeData?.candidates.find((c) => c.candidate_id === candId)
      if (track) {
        setSelectedCandidate({
          candidate_id: track.candidate_id,
          altitude_km: track.altitude_km,
          inclination_deg: track.inclination_deg,
          raan_deg: track.raan_deg,
          u0_deg: 0,
          deployment_delay_minutes: track.deployment_delay_minutes,
          delta_v_m_s: 0,
          propellant_mass_kg: 0,
          fuel_fraction: 0,
          within_dv_budget: track.within_dv_budget,
          risk_score: track.risk_score,
          accepted_event_count: 0,
          minimum_miss_distance_km: 0,
          uncertainty_level: 'nominal',
          rank: track.rank ?? undefined,
          deployment_epoch: track.deployment_epoch,
        })
      }
    }
  }

  const handleSelectEventFromGlobe = (eventId: string, candidateId?: string | null) => {
    const existing = events.find((e) => e.id === eventId)
    if (existing) {
      setSelectedEvent(existing)
    } else {
      const marker = globeData?.events.find((e) => e.event_id === eventId)
      if (marker) {
        setSelectedEvent({
          id: marker.event_id,
          candidate_id: marker.candidate_id ?? '',
          debris_object_id: marker.debris_object_id ?? '',
          debris_norad_id: marker.debris_norad_id ?? '',
          tca: marker.tca,
          miss_distance_km: marker.miss_distance_km,
          relative_velocity_km_s: marker.relative_velocity_km_s,
          threshold_km: 25.0,
          screening_source: 'ddato',
        })
      }
    }
    if (candidateId) {
      handleSelectCandidateIdFromEvent(candidateId)
    }
  }

  // Active layer memoized
  const activeLayer = useMemo(() => {
    if (!heatmapData || heatmapData.layers.length === 0) return null
    if (selectedInclination == null) return heatmapData.layers[0]
    return (
      heatmapData.layers.find(
        (l) => Math.abs(l.inclination_deg - selectedInclination) < 1e-4
      ) ?? heatmapData.layers[0]
    )
  }, [heatmapData, selectedInclination])

  // Handlers
  const handleSelectCandidate = (candidate: CandidateResultItem) => {
    setSelectedCandidate((prev) =>
      prev?.candidate_id === candidate.candidate_id ? null : candidate
    )
    if (heatmapData && heatmapData.layers.length > 0 && candidate.inclination_deg != null) {
      const match = heatmapData.layers.find(
        (l) => Math.abs(l.inclination_deg - candidate.inclination_deg) < 1e-4
      )
      if (match) {
        setSelectedInclination(match.inclination_deg)
      }
    }
  }

  const handleSelectCandidateFromHeatmap = (cell: HeatmapCell) => {
    const existing = candidates.find((c) => c.candidate_id === cell.candidate_id)
    if (existing) {
      setSelectedCandidate(existing)
    } else {
      setSelectedCandidate({
        candidate_id: cell.candidate_id,
        altitude_km: cell.altitude_km,
        inclination_deg: cell.inclination_deg,
        raan_deg: 0,
        u0_deg: 0,
        deployment_delay_minutes: cell.delay_minutes,
        delta_v_m_s: cell.delta_v_m_s ?? 0,
        propellant_mass_kg: 0,
        fuel_fraction: 0,
        within_dv_budget: cell.within_dv_budget ?? true,
        risk_score: cell.risk_score ?? 0,
        accepted_event_count: cell.accepted_event_count,
        minimum_miss_distance_km: cell.minimum_miss_distance_km,
        uncertainty_level: cell.uncertainty_level,
        rank: cell.rank,
      })
    }
  }

  const handleSelectCandidateIdFromEvent = (candidateId: string) => {
    const existing = candidates.find((c) => c.candidate_id === candidateId)
    if (existing) {
      setSelectedCandidate(existing)
    } else {
      setSelectedCandidate({
        candidate_id: candidateId,
        altitude_km: 0,
        inclination_deg: 0,
        raan_deg: 0,
        u0_deg: 0,
        deployment_delay_minutes: 0,
        delta_v_m_s: 0,
        propellant_mass_kg: 0,
        fuel_fraction: 0,
        within_dv_budget: true,
        risk_score: 0,
      })
    }
  }

  const handleCandidatePageChange = (newOffset: number) => {
    fetchCandidates(newOffset)
  }

  const handleEventPageChange = (newOffset: number) => {
    fetchEvents(newOffset)
  }

  const handleSelectInclination = (inc: number) => {
    setSelectedInclination(inc)
  }

  // Phase P23: External Validation handlers
  const handleRunValidation = useCallback(
    async (requestPayload: ValidationExecutionRequest) => {
      setIsValidationRunning(true)
      setValidationError(null)
      try {
        const result = await createValidation(runId, requestPayload)
        setValidation(result)
      } catch (err) {
        if (err instanceof ApiError) {
          if (err.status === 503) {
            setValidationError(
              'The external reference source is currently unavailable. Cached/demo validation may still be available.'
            )
          } else if (err.status === 404) {
            setValidationError(`Screening run '${runId}' not found for validation.`)
          } else if (err.status === 422) {
            setValidationError(
              err.message || 'Invalid parameters requested for external reference validation.'
            )
          } else if (err.status === 0) {
            setValidationError('Network error while connecting to validation service.')
          } else {
            setValidationError('Unable to complete external validation.')
          }
        } else {
          setValidationError('Unable to complete external validation.')
        }
      } finally {
        setIsValidationRunning(false)
      }
    },
    [runId]
  )

  const handleRetryValidation = useCallback(async () => {
    setIsValidationLoading(true)
    setValidationError(null)
    try {
      const valData = await getRunValidation(runId)
      setValidation(valData)
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setValidation(null)
      } else {
        setValidationError('Unable to load external reference validation.')
      }
    } finally {
      setIsValidationLoading(false)
    }
  }, [runId])

  const handleSelectCandidateFromValidation = useCallback(
    (candId: string) => {
      const existing = candidates.find((c) => c.candidate_id === candId)
      if (existing) {
        setSelectedCandidate(existing)
      } else {
        const track = globeData?.candidates.find((c) => c.candidate_id === candId)
        if (track) {
          setSelectedCandidate({
            candidate_id: track.candidate_id,
            altitude_km: track.altitude_km,
            inclination_deg: track.inclination_deg,
            raan_deg: track.raan_deg,
            u0_deg: 0,
            deployment_delay_minutes: track.deployment_delay_minutes,
            delta_v_m_s: 0,
            propellant_mass_kg: 0,
            fuel_fraction: 0,
            within_dv_budget: track.within_dv_budget,
            risk_score: track.risk_score,
            accepted_event_count: 0,
            minimum_miss_distance_km: null,
            uncertainty_level: 'nominal',
            composite_score: track.risk_score,
            rank: track.rank,
          })
        }
      }
    },
    [candidates, globeData]
  )

  // Fatal run error (e.g. 404 run not found)
  if (runError && !run) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <div className="p-8 bg-slate-900/80 border border-rose-800/80 rounded-2xl shadow-xl text-center space-y-4 font-mono">
          <div className="w-12 h-12 mx-auto rounded-full bg-rose-950/60 border border-rose-800 flex items-center justify-center text-rose-400">
            {runErrorStatus === 404 ? '404' : '!'}
          </div>
          <h2 className="text-lg font-bold text-white">Screening Run Unavailable</h2>
          <p className="text-xs text-rose-300 max-w-lg mx-auto leading-relaxed">
            {runError}
          </p>
          <div className="flex justify-center space-x-3 pt-2">
            <button
              type="button"
              onClick={() => navigateTo('/')}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold transition-colors cursor-pointer"
            >
              Return to Planner
            </button>
            <button
              type="button"
              onClick={fetchRunStatus}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold border border-slate-700 transition-colors cursor-pointer"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 font-sans">
      {/* Header */}
      <ResultsHeader
        runId={runId}
        planId={run?.plan_id}
        status={run?.status}
        demoMode={isDemoActive && (plan?.demo_mode ?? true)}
        dataSource={plan?.data_source ?? 'celestrak'}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        isDemoActive={isDemoActive}
        onToggleDemoMode={() => setIsDemoActive((prev) => !prev)}
        onBackToPlanner={() => navigateTo('/')}
      />

      {/* Phase P29.1: Demo Overview Summary */}
      {viewMode === 'demo' && (
        <JudgeExecutiveSummary
          run={run}
          plan={plan}
          candidateTotal={candidateTotal}
          eventTotal={eventTotal}
          events={timelineEvents.length > 0 ? timelineEvents : events}
          isDemoActive={isDemoActive}
        />
      )}

      {/* Part 1: Mission Briefing immediately beneath Results Header */}
      <MissionBriefing run={run} plan={plan} validation={validation} />

      {/* Authoritative Run Summary Metrics */}
      <section aria-labelledby="summary-metrics-heading" className="space-y-4">
        <h2 id="summary-metrics-heading" className="sr-only">Screening Summary Metrics</h2>
        <ResultsSummary run={run} isLoading={isRunLoading} />
        {viewMode === 'technical' && (
          <DataProvenanceStrip run={run} validation={validation} globeData={globeData} />
        )}
      </section>

      {/* Selected Candidate Detail Panel */}
      {selectedCandidate && (
        <section aria-labelledby="candidate-detail-heading">
          <h2 id="candidate-detail-heading" className="sr-only">Candidate Details</h2>
          <CandidateDetailPanel
            candidate={selectedCandidate}
            onClose={() => setSelectedCandidate(null)}
          />
        </section>
      )}

      {/* Candidate Comparison Panel (Phase P25 Section H) */}
      {comparisonCandidates.length > 0 && (
        <section aria-labelledby="candidate-comparison-heading">
          <h2 id="candidate-comparison-heading" className="sr-only">Candidate Comparison</h2>
          <CandidateComparison
            candidates={comparisonCandidates}
            onRemoveCandidate={handleRemoveCompare}
            onClear={handleClearCompare}
            onSelectCandidate={handleSelectCandidate}
          />
        </section>
      )}

      {/* CANDIDATE TRADE-OFFS */}
      <section className="space-y-3" aria-labelledby="candidate-table-heading">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-800 pb-2">
          <div>
            <h3 id="candidate-table-heading" className="text-base font-bold text-white font-mono flex flex-wrap items-center gap-2">
              <span className="text-cyan-400">CANDIDATE TRADE-OFFS</span>
              <span className="text-slate-500 hidden sm:inline">•</span>
              <span>Ranked Deployment Candidates</span>
              {candidateTotal > 0 && (
                <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 font-normal">
                  {candidateTotal} total
                </span>
              )}
            </h3>
            <p className="text-xs text-cyan-300/90 font-mono mt-0.5">
              Compare candidate configurations using the persisted ranking, propulsion estimates, event counts and screening-risk indicators.
            </p>
          </div>
        </div>

        {candidatesError ? (
          <div className="p-4 bg-rose-950/40 border border-rose-800 rounded-xl text-xs font-mono text-rose-300 flex justify-between items-center">
            <span>{candidatesError}</span>
            <button
              type="button"
              onClick={() => fetchCandidates(candidateOffset)}
              className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-white rounded border border-slate-700 cursor-pointer"
            >
              Retry
            </button>
          </div>
        ) : !isCandidatesLoading && candidates.length === 0 ? (
          <ResultsEmptyState
            title="No Candidate Results"
            message="No candidate results are available yet."
            icon="candidates"
          />
        ) : (
          <div className="space-y-4">
            <CandidateTradeoffExplorer
              candidates={explorerCandidates.length > 0 ? explorerCandidates : candidates}
              selectedCandidateId={selectedCandidate?.candidate_id}
              comparisonCandidateIds={comparisonCandidates.map((c) => c.candidate_id)}
              onSelectCandidate={handleSelectCandidate}
              isLoading={isCandidatesLoading}
            />

            {viewMode === 'demo' ? (
              <div className="border border-slate-800 rounded-xl p-3 bg-slate-950/60">
                <button
                  type="button"
                  data-testid="toggle-candidate-table-btn"
                  onClick={() => setIsCandidateTableExpanded((prev) => !prev)}
                  className="w-full flex items-center justify-between text-xs font-mono font-bold text-cyan-300 hover:text-white transition-colors cursor-pointer"
                  aria-expanded={isCandidateTableExpanded}
                >
                  <span className="flex items-center gap-2">
                    <span>
                      {isCandidateTableExpanded
                        ? '▲ HIDE CANDIDATE TABLE'
                        : `▼ VIEW DETAILED CANDIDATE TELEMETRY TABLE (${candidateTotal} candidates)`}
                    </span>
                    {!isCandidateTableExpanded && (
                      <span className="text-[10px] font-normal text-slate-400 font-sans hidden sm:inline">
                        — Click to inspect raw numerical telemetry &amp; comparison controls
                      </span>
                    )}
                  </span>
                  <span className="text-[10px] text-slate-500 font-normal">
                    {isCandidateTableExpanded ? 'Collapse' : 'Expand'}
                  </span>
                </button>
                {isCandidateTableExpanded && (
                  <div className="pt-3 space-y-3">
                    <CandidateTable
                      candidates={candidates}
                      selectedCandidateId={selectedCandidate?.candidate_id}
                      onSelectCandidate={handleSelectCandidate}
                      isLoading={isCandidatesLoading}
                      comparisonCandidateIds={comparisonCandidates.map((c) => c.candidate_id)}
                      onToggleCompare={handleToggleCompare}
                    />
                    <Pagination
                      total={candidateTotal}
                      limit={candidateLimit}
                      offset={candidateOffset}
                      onPageChange={handleCandidatePageChange}
                      disabled={isCandidatesLoading}
                      label="candidates"
                    />
                  </div>
                )}
              </div>
            ) : (
              <>
                <CandidateTable
                  candidates={candidates}
                  selectedCandidateId={selectedCandidate?.candidate_id}
                  onSelectCandidate={handleSelectCandidate}
                  isLoading={isCandidatesLoading}
                  comparisonCandidateIds={comparisonCandidates.map((c) => c.candidate_id)}
                  onToggleCompare={handleToggleCompare}
                />
                <Pagination
                  total={candidateTotal}
                  limit={candidateLimit}
                  offset={candidateOffset}
                  onPageChange={handleCandidatePageChange}
                  disabled={isCandidatesLoading}
                  label="candidates"
                />
              </>
            )}
          </div>
        )}
      </section>

      {/* CLOSE-APPROACH SCREENING (Part 13) */}
      <section className="space-y-4" aria-labelledby="event-table-heading">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-800 pb-2">
          <div>
            <h3 id="event-table-heading" className="text-base font-bold text-white font-mono flex flex-wrap items-center gap-2">
              <span className="text-amber-400">CLOSE-APPROACH SCREENING</span>
              <span className="text-slate-500 hidden sm:inline">•</span>
              <span>Close-Approach Conjunction Events</span>
              {eventTotal > 0 && (
                <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-amber-300 border border-slate-700 font-normal">
                  {eventTotal} events
                </span>
              )}
            </h3>
            <p className="text-xs text-amber-300/90 font-mono mt-0.5">
              Inspect the candidate/debris events identified within the configured screening threshold.
            </p>
          </div>
        </div>

        {/* Part 1 & 13: Conjunction Timeline */}
        <ConjunctionTimeline
          events={timelineEvents.length > 0 ? timelineEvents : events}
          selectedEventId={selectedEvent?.id}
          selectedCandidateId={selectedCandidate?.candidate_id}
          plan={plan}
          onSelectEvent={(evt) => {
            setSelectedEvent(evt)
            if (evt.candidate_id) {
              handleSelectCandidateIdFromEvent(evt.candidate_id)
            }
          }}
          onInspectInGlobe={handleInspectEventInGlobe}
          onSelectCandidateId={handleSelectCandidateIdFromEvent}
        />

        {eventsError ? (
          <div className="p-4 bg-rose-950/40 border border-rose-800 rounded-xl text-xs font-mono text-rose-300 flex justify-between items-center">
            <span>{eventsError}</span>
            <button
              type="button"
              onClick={() => fetchEvents(eventOffset)}
              className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-white rounded border border-slate-700 cursor-pointer"
            >
              Retry
            </button>
          </div>
        ) : !isEventsLoading && events.length === 0 ? (
          <ResultsEmptyState
            title="No Conjunction Events"
            message="No close-approach events were detected for this run."
            icon="events"
          />
        ) : viewMode === 'demo' ? (
          <div className="border border-slate-800 rounded-xl p-3 bg-slate-950/60">
            <button
              type="button"
              data-testid="toggle-event-table-btn"
              onClick={() => setIsEventTableExpanded((prev) => !prev)}
              className="w-full flex items-center justify-between text-xs font-mono font-bold text-amber-300 hover:text-white transition-colors cursor-pointer"
              aria-expanded={isEventTableExpanded}
            >
              <span className="flex items-center gap-2">
                <span>
                  {isEventTableExpanded
                    ? '▲ HIDE CONJUNCTION EVENT TABLE'
                    : `▼ VIEW DETAILED CONJUNCTION EVENT TABLE (${eventTotal} events)`}
                </span>
                {!isEventTableExpanded && (
                  <span className="text-[10px] font-normal text-slate-400 font-sans hidden sm:inline">
                    — Click to inspect raw numerical event records
                  </span>
                )}
              </span>
              <span className="text-[10px] text-slate-500 font-normal">
                {isEventTableExpanded ? 'Collapse' : 'Expand'}
              </span>
            </button>
            {isEventTableExpanded && (
              <div className="pt-3 space-y-3">
                <EventTable
                  events={events}
                  selectedCandidateId={selectedCandidate?.candidate_id}
                  selectedEventId={selectedEvent?.id}
                  onSelectEvent={(evt) => setSelectedEvent(evt)}
                  onSelectCandidateId={handleSelectCandidateIdFromEvent}
                  isLoading={isEventsLoading}
                />
                <Pagination
                  total={eventTotal}
                  limit={eventLimit}
                  offset={eventOffset}
                  onPageChange={handleEventPageChange}
                  disabled={isEventsLoading}
                  label="conjunction events"
                />
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            <EventTable
              events={events}
              selectedCandidateId={selectedCandidate?.candidate_id}
              selectedEventId={selectedEvent?.id}
              onSelectEvent={(evt) => setSelectedEvent(evt)}
              onSelectCandidateId={handleSelectCandidateIdFromEvent}
              isLoading={isEventsLoading}
            />
            <Pagination
              total={eventTotal}
              limit={eventLimit}
              offset={eventOffset}
              onPageChange={handleEventPageChange}
              disabled={isEventsLoading}
              label="conjunction events"
            />
          </div>
        )}

        {/* Selected Event Detail Panel (Part 13) */}
        {selectedEvent && (
          <div aria-labelledby="event-detail-heading" className="pt-2">
            <h4 id="event-detail-heading" className="sr-only">Conjunction Event Details</h4>
            <EventDetailPanel
              event={selectedEvent}
              onClose={() => setSelectedEvent(null)}
              onInspectInGlobe={handleInspectEventInGlobe}
            />
          </div>
        )}
      </section>

      {/* RISK LANDSCAPE */}
      <section className="space-y-4" aria-labelledby="heatmap-section-heading">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-800 pb-2">
          <div>
            <h3 id="heatmap-section-heading" className="text-base font-bold text-white font-mono flex flex-wrap items-center gap-2">
              <span className="text-indigo-400">RISK LANDSCAPE</span>
              <span className="text-slate-500 hidden sm:inline">•</span>
              <span>Screening Risk Heatmap</span>
              {selectedInclination != null && (
                <span className="text-xs px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800 font-normal">
                  {selectedInclination.toFixed(1)}° slice
                </span>
              )}
            </h3>
            <p className="text-xs text-indigo-300/90 font-mono mt-0.5">
              Explore how the bounded screening score varies across altitude and deployment delay.
            </p>
          </div>
        </div>

        {heatmapError ? (
          <div className="p-4 bg-rose-950/40 border border-rose-800 rounded-xl text-xs font-mono text-rose-300 flex justify-between items-center">
            <span>{heatmapError}</span>
            <button
              type="button"
              onClick={fetchHeatmap}
              className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-white rounded border border-slate-700 cursor-pointer"
            >
              Retry
            </button>
          </div>
        ) : !isHeatmapLoading && (!heatmapData || heatmapData.layers.length === 0) ? (
          <ResultsEmptyState
            title="No Heatmap Data"
            message={
              run?.status === 'queued' || run?.status === 'running'
                ? "Heatmap data will become available after screening completes."
                : "No heatmap data is available for this run yet."
            }
            icon="candidates"
          />
        ) : (
          <div className="space-y-3">
            {heatmapData && (
              <HeatmapControls
                heatmapData={heatmapData}
                selectedLayer={activeLayer}
                selectedInclination={selectedInclination}
                onSelectInclination={handleSelectInclination}
                isLoading={isHeatmapLoading}
                selectedCandidate={selectedCandidate}
              />
            )}
            <RiskHeatmap
              layer={activeLayer}
              onSelectCandidate={handleSelectCandidateFromHeatmap}
              isLoading={isHeatmapLoading}
            />
          </div>
        )}
      </section>

      {/* 3D ORBIT GEOMETRY */}
      <section id="globe-section" className="space-y-4" aria-labelledby="globe-section-heading">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-800 pb-2">
          <div>
            <h3 id="globe-section-heading" className="text-base font-bold text-white font-mono flex flex-wrap items-center gap-2">
              <span className="text-cyan-400">3D ORBIT GEOMETRY</span>
              <span className="text-slate-500 hidden sm:inline">•</span>
              <span>3D Orbital Trajectory & Conjunction Globe</span>
              {globeData && (
                <span className="text-xs px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800 font-normal">
                  TEME frame • {globeData.candidate_count} cand • {globeData.debris_count} debris
                </span>
              )}
            </h3>
            <p className="text-xs text-cyan-300/90 font-mono mt-0.5">
              Inspect candidate and debris trajectories and the spatial location of screened close approaches. Explore the spatial relationship between candidate trajectories, debris trajectories and screened close-approach events.
            </p>
          </div>
        </div>

        {globeError ? (
          <div className="p-4 bg-rose-950/40 border border-rose-800 rounded-xl text-xs font-mono text-rose-300 flex justify-between items-center">
            <span>{globeError}</span>
            <button
              type="button"
              onClick={() => fetchGlobeData()}
              className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-white rounded border border-slate-700 cursor-pointer"
            >
              Retry
            </button>
          </div>
        ) : !isGlobeLoading && (!globeData || (globeData.candidates.length === 0 && globeData.debris.length === 0)) ? (
          <ResultsEmptyState
            title="No Orbital Data"
            message={
              run?.status === 'queued' || run?.status === 'running'
                ? "Orbital visualization data will become available after screening completes."
                : "No orbital visualization data is available for this run."
            }
            icon="candidates"
          />
        ) : (
          <div className="space-y-3">
            {/* Part 9: Globe Education Banner */}
            <div
              data-testid="globe-education-banner"
              className="p-3.5 bg-slate-950/80 border border-cyan-800/40 rounded-xl space-y-1.5 font-mono text-xs"
            >
              <div className="flex items-center space-x-2 text-cyan-300 font-bold uppercase text-[11px]">
                <span>ℹ</span>
                <span>WHAT YOU ARE SEEING</span>
              </div>
              <p className="text-slate-300 font-sans text-xs leading-relaxed">
                Candidate trajectories, catalog debris trajectories and screened close-approach event locations are displayed using the backend-provided trajectory data.
              </p>
              <div className="flex flex-wrap items-center gap-2.5 text-[10px] text-slate-400 pt-0.5">
                <span>Frame: <strong className="text-slate-200">TEME</strong></span>
                <span>•</span>
                <span>Time: <strong className="text-slate-200">UTC</strong></span>
                <span>•</span>
                <span>Visualization transform: <strong className="text-slate-200">Cesium pseudofixed transform</strong></span>
              </div>
            </div>

            <GlobeControls
              candidateCount={globeData?.candidate_count ?? 0}
              totalCandidates={candidateTotal || (globeData?.candidate_count ?? 0)}
              showDebris={showDebris}
              onToggleDebris={setShowDebris}
              maxDebris={globeMaxDebris}
              onChangeMaxDebris={handleChangeMaxDebris}
              sampleStep={globeSampleStep}
              onChangeSampleStep={handleChangeSampleStep}
              isPlaying={isGlobePlaying}
              onTogglePlay={() => setIsGlobePlaying((p) => !p)}
              currentUtcTime={globeCurrentUtcTime}
              playbackSpeed={globePlaybackSpeed}
              onChangeSpeed={setGlobePlaybackSpeed}
              onResetView={handleResetGlobeView}
              onFocusSelected={handleFocusSelectedOnGlobe}
              hasSelection={Boolean(selectedCandidate || selectedEvent)}
              disabled={isGlobeLoading}
            />

            <React.Suspense
              fallback={
                <div
                  data-testid="globe-loading-placeholder"
                  className="w-full h-[520px] bg-slate-950/90 border border-slate-800 rounded-xl flex flex-col items-center justify-center space-y-3 font-mono text-xs text-slate-400"
                >
                  <div className="w-8 h-8 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
                  <span className="text-white font-bold tracking-wider uppercase">Loading 3D Cesium Orbit Viewer…</span>
                  <span className="text-[11px] text-slate-500">Initializing WebGL context and ephemeris transform pipeline</span>
                </div>
              }
            >
              <OrbitGlobe
                globeData={globeData}
                selectedCandidateId={selectedCandidate?.candidate_id}
                selectedEventId={selectedEvent?.id}
                comparisonCandidateIds={comparisonCandidates.map((c) => c.candidate_id)}
                showDebris={showDebris}
                isPlaying={isGlobePlaying}
                playbackSpeed={globePlaybackSpeed}
                onClockTick={setGlobeCurrentUtcTime}
                onSelectCandidate={handleSelectCandidateFromGlobe}
                onSelectEvent={handleSelectEventFromGlobe}
                onViewerReady={(v) => {
                  globeViewerRef.current = v
                }}
                isLoading={isGlobeLoading}
              />
            </React.Suspense>

            <GlobeLegend />
          </div>
        )}
      </section>

      {/* External Reference Validation Section (Phase P23 & P29) */}
      <section className="space-y-3" aria-labelledby="validation-section-heading">
        {/* Part 10: Validation Education Banner */}
        <div
          data-testid="validation-education-banner"
          className="p-3.5 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1.5 font-mono text-xs"
        >
          <div className="flex items-center space-x-2 text-indigo-300 font-bold uppercase text-[11px]">
            <span>ℹ</span>
            <span>REFERENCE VALIDATION BENCHMARK</span>
          </div>
          <p className="text-slate-300 font-sans text-xs leading-relaxed">
            Reference comparison checks whether D-DATO events can be paired with external reference events using configured temporal and spatial tolerances.
          </p>
          <div className="text-[10px] text-slate-400 pt-0.5">
            <span>Data mode: <strong className="text-cyan-300">{plan?.demo_mode ? 'DEMO DATA' : 'LIVE DATA'}</strong></span>
            <span className="mx-2">•</span>
            <span>Source: <strong className="text-slate-200">{validation?.source || (plan?.demo_mode ? 'socrates_demo_fixture' : 'socrates_live')}</strong></span>
          </div>
        </div>

        <ValidationSection
          validation={validation}
          isLoading={isValidationLoading}
          isRunning={isValidationRunning}
          error={validationError}
          onRunValidation={handleRunValidation}
          onRetry={handleRetryValidation}
          onSelectCandidateId={handleSelectCandidateFromValidation}
        />
      </section>

      {/* Export Results Section (Phase P24) */}
      <ExportControls
        runId={runId}
        disabled={isRunLoading}
      />

      {/* Part 13: Technical Details Collapsible (Demo View) */}
      {viewMode === 'demo' && (
        <section aria-labelledby="technical-details-heading" className="pt-2">
          <div className="border border-slate-800 rounded-xl p-4 bg-slate-950/70 space-y-3 font-mono">
            <button
              type="button"
              data-testid="toggle-technical-details-btn"
              onClick={() => setIsTechnicalDetailsExpanded((prev) => !prev)}
              className="w-full flex items-center justify-between text-xs font-bold text-slate-300 hover:text-white transition-colors cursor-pointer"
              aria-expanded={isTechnicalDetailsExpanded}
            >
              <div className="flex items-center gap-2">
                <span className="text-cyan-400">⚙</span>
                <span id="technical-details-heading">
                  {isTechnicalDetailsExpanded
                    ? '▲ HIDE TECHNICAL PROVENANCE & SCIENTIFIC BOUNDARIES'
                    : '▼ VIEW TECHNICAL PROVENANCE & SCIENTIFIC BOUNDARIES'}
                </span>
              </div>
              <span className="text-[10px] text-slate-500 font-normal">
                {isTechnicalDetailsExpanded ? 'Collapse' : 'Expand detailed metadata'}
              </span>
            </button>

            {isTechnicalDetailsExpanded && (
              <div className="pt-3 border-t border-slate-800/80 space-y-4">
                <DataProvenanceStrip run={run} validation={validation} globeData={globeData} />
                <div className="p-3 bg-slate-900/80 border border-slate-800 rounded-lg text-xs text-slate-400 space-y-1">
                  <span className="text-slate-200 font-bold uppercase text-[11px] block">
                    Scientific Scope &amp; Boundaries:
                  </span>
                  <p className="font-sans text-xs text-slate-300 leading-relaxed">
                    D-DATO is an early-stage screening aid designed for relative trade-off exploration. It does not compute collision probabilities, certify flight maneuvers, generate CDMs, or model high-order gravitational perturbations beyond J2/SGP4.
                  </p>
                </div>
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  )
}
