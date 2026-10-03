import React, { useEffect, useRef, useState, useCallback } from 'react'
import * as Cesium from 'cesium'
import type { GlobeResponse, GlobeCandidateTrack, GlobeDebrisTrack, GlobeEventMarker } from '../../types/globe'
import { temeKmToCesiumFixed } from '../../utils/cesiumFrames'

export interface OrbitGlobeProps {
  globeData: GlobeResponse | null
  selectedCandidateId?: string | null
  selectedEventId?: string | null
  showDebris: boolean
  isPlaying: boolean
  playbackSpeed: number
  onClockTick?: (isoTime: string) => void
  onSelectCandidate?: (candidateId: string) => void
  onSelectEvent?: (eventId: string, candidateId?: string | null) => void
  onViewerReady?: (viewer: Cesium.Viewer) => void
  isLoading?: boolean
}

export const OrbitGlobe: React.FC<OrbitGlobeProps> = ({
  globeData,
  selectedCandidateId,
  selectedEventId,
  showDebris,
  isPlaying,
  playbackSpeed,
  onClockTick,
  onSelectCandidate,
  onSelectEvent,
  onViewerReady,
  isLoading = false,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const viewerRef = useRef<Cesium.Viewer | null>(null)
  const clickHandlerRef = useRef<Cesium.ScreenSpaceEventHandler | null>(null)
  const [selectedEntityInfo, setSelectedEntityInfo] = useState<{
    type: 'candidate' | 'debris' | 'event'
    title: string
    details: { label: string; value: string }[]
  } | null>(null)

  const onClockTickRef = useRef(onClockTick)
  const onSelectCandidateRef = useRef(onSelectCandidate)
  const onSelectEventRef = useRef(onSelectEvent)
  const onViewerReadyRef = useRef(onViewerReady)

  useEffect(() => {
    onClockTickRef.current = onClockTick
    onSelectCandidateRef.current = onSelectCandidate
    onSelectEventRef.current = onSelectEvent
    onViewerReadyRef.current = onViewerReady
  })

  // 1. Initialize Cesium Viewer once
  useEffect(() => {
    if (!containerRef.current) return

    // Ensure no Ion account network requests
    Cesium.Ion.defaultAccessToken = ''

    // Construct Viewer with no default online terrain/imagery
    const viewer = new Cesium.Viewer(containerRef.current, {
      baseLayer: false,
      terrainProvider: new Cesium.EllipsoidTerrainProvider(),
      animation: false,
      timeline: false,
      geocoder: false,
      homeButton: false,
      sceneModePicker: false,
      baseLayerPicker: false,
      navigationHelpButton: false,
      fullscreenButton: false,
      infoBox: false,
      selectionIndicator: false,
    })

    // Load offline local NaturalEarthII imagery without external network dependency
    try {
      const assetUrl = Cesium.buildModuleUrl('Assets/Textures/NaturalEarthII')
      Cesium.TileMapServiceImageryProvider.fromUrl(assetUrl)
        .then((provider) => {
          if (!viewer.isDestroyed()) {
            viewer.imageryLayers.add(new Cesium.ImageryLayer(provider))
          }
        })
        .catch(() => {
          // Gracefully fallback to base globe ellipsoid if texture cannot load
        })
    } catch {
      // Fallback
    }

    // Set initial camera overview of Earth in space (~25,000 km overview)
    viewer.camera.setView({
      destination: Cesium.Cartesian3.fromDegrees(0.0, 15.0, 24000000.0),
    })

    // Setup click selection handler
    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas)
    handler.setInputAction((movement: { position: Cesium.Cartesian2 }) => {
      const pickedObject = viewer.scene.pick(movement.position)
      if (Cesium.defined(pickedObject) && pickedObject.id) {
        const entity = pickedObject.id as Cesium.Entity
        const entityId = entity.id

        if (entityId.startsWith('candidate-')) {
          const candId = entity.properties?.getValue(viewer.clock.currentTime)?.candidate_id
          if (candId) {
            onSelectCandidateRef.current?.(candId)
            const meta = entity.properties?.getValue(viewer.clock.currentTime)
            setSelectedEntityInfo({
              type: 'candidate',
              title: `Candidate ${candId}`,
              details: [
                { label: 'Rank', value: meta?.rank != null ? `Rank ${meta.rank}` : 'Unranked' },
                { label: 'Altitude', value: `${meta?.altitude_km?.toFixed(1)} km` },
                { label: 'Inclination', value: `${meta?.inclination_deg?.toFixed(1)}°` },
                { label: 'Risk Score', value: `${meta?.risk_score?.toFixed(2)}` },
                { label: 'Delta-V', value: meta?.within_dv_budget ? 'Within budget' : 'Exceeds budget' },
              ],
            })
          }
        } else if (entityId.startsWith('event-')) {
          const props = entity.properties?.getValue(viewer.clock.currentTime)
          if (props?.event_id) {
            onSelectEventRef.current?.(props.event_id, props.candidate_id)
            setSelectedEntityInfo({
              type: 'event',
              title: `Event ${props.event_id}`,
              details: [
                { label: 'Candidate', value: props.candidate_id || '—' },
                { label: 'Debris NORAD', value: props.debris_norad_id ? `NORAD ${props.debris_norad_id}` : '—' },
                { label: 'TCA (UTC)', value: props.tca || '—' },
                { label: 'Miss Distance', value: `${props.miss_distance_km?.toFixed(3)} km` },
                { label: 'Relative Velocity', value: `${props.relative_velocity_km_s?.toFixed(2)} km/s` },
              ],
            })
          }
        } else if (entityId.startsWith('debris-')) {
          const props = entity.properties?.getValue(viewer.clock.currentTime)
          setSelectedEntityInfo({
            type: 'debris',
            title: `Debris NORAD ${props?.norad_id || 'Unknown'}`,
            details: [
              { label: 'Object Name', value: props?.object_name || 'Debris' },
              { label: 'NORAD ID', value: props?.norad_id || '—' },
            ],
          })
        }
      }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK)
    clickHandlerRef.current = handler

    // Clock tick listener for synchronization
    const onTickCallback = (clock: Cesium.Clock) => {
      if (onClockTickRef.current) {
        const iso = Cesium.JulianDate.toIso8601(clock.currentTime)
        onClockTickRef.current(iso)
      }
    }
    viewer.clock.onTick.addEventListener(onTickCallback)

    // Handle container resize
    const resizeObserver = new ResizeObserver(() => {
      if (!viewer.isDestroyed()) {
        viewer.resize()
      }
    })
    resizeObserver.observe(containerRef.current)

    viewerRef.current = viewer
    onViewerReadyRef.current?.(viewer)

    return () => {
      resizeObserver.disconnect()
      if (clickHandlerRef.current && !clickHandlerRef.current.isDestroyed()) {
        clickHandlerRef.current.destroy()
        clickHandlerRef.current = null
      }
      if (!viewer.isDestroyed()) {
        viewer.clock.onTick.removeEventListener(onTickCallback)
        viewer.destroy()
      }
      viewerRef.current = null
    }
  }, []) // Mount once

  // 2. Update Clock playback state & multiplier
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || viewer.isDestroyed()) return

    viewer.clock.shouldAnimate = isPlaying
    viewer.clock.multiplier = playbackSpeed
  }, [isPlaying, playbackSpeed])

  // 3. Render Trajectories and Markers when data changes
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || viewer.isDestroyed() || !globeData) return

    // Clear previous entities
    viewer.entities.removeAll()

    // Setup time bounds from backend epoch window
    const startIso = globeData.epoch_start
    const endIso = globeData.epoch_end

    if (startIso && endIso) {
      const startJulian = Cesium.JulianDate.fromIso8601(startIso)
      const stopJulian = Cesium.JulianDate.fromIso8601(endIso)
      viewer.clock.startTime = startJulian
      viewer.clock.stopTime = stopJulian
      if (
        !viewer.clock.currentTime ||
        Cesium.JulianDate.lessThan(viewer.clock.currentTime, startJulian) ||
        Cesium.JulianDate.greaterThan(viewer.clock.currentTime, stopJulian)
      ) {
        viewer.clock.currentTime = startJulian
      }
      viewer.clock.clockRange = Cesium.ClockRange.LOOP_STOP
    }

    // A. Render Candidate Tracks
    globeData.candidates.forEach((track: GlobeCandidateTrack) => {
      const isSelected = selectedCandidateId === track.candidate_id
      const positions: Cesium.Cartesian3[] = []
      const positionProp = new Cesium.SampledPositionProperty()

      track.trajectory.forEach((pt) => {
        const julian = Cesium.JulianDate.fromIso8601(pt.t)
        const fixedPos = temeKmToCesiumFixed(pt.x_km, pt.y_km, pt.z_km, julian)
        positions.push(fixedPos)
        positionProp.addSample(julian, fixedPos)
      })

      // Full static trajectory loop
      viewer.entities.add({
        id: `candidate-orbit-${track.candidate_id}`,
        polyline: {
          positions,
          width: isSelected ? 3.5 : 1.8,
          material: isSelected
            ? Cesium.Color.WHITE
            : Cesium.Color.CYAN.withAlpha(0.85),
        },
        properties: {
          candidate_id: track.candidate_id,
          rank: track.rank,
          altitude_km: track.altitude_km,
          inclination_deg: track.inclination_deg,
          risk_score: track.risk_score,
          within_dv_budget: track.within_dv_budget,
          trajectory_start: track.trajectory_start,
          trajectory_end: track.trajectory_end,
          point_count: track.point_count,
        },
      })

      // Time-dynamic current position marker and label
      viewer.entities.add({
        id: `candidate-marker-${track.candidate_id}`,
        position: positionProp,
        point: {
          pixelSize: isSelected ? 9 : 6,
          color: isSelected ? Cesium.Color.WHITE : Cesium.Color.CYAN,
          outlineColor: Cesium.Color.BLACK,
          outlineWidth: 1.5,
        },
        label: {
          text: track.rank != null ? `Rank ${track.rank}` : `Cand ${track.candidate_id}`,
          font: '11px monospace',
          fillColor: isSelected ? Cesium.Color.WHITE : Cesium.Color.CYAN,
          pixelOffset: new Cesium.Cartesian2(0, -12),
          showBackground: true,
          backgroundColor: Cesium.Color.BLACK.withAlpha(0.75),
        },
        properties: {
          candidate_id: track.candidate_id,
          rank: track.rank,
          altitude_km: track.altitude_km,
          inclination_deg: track.inclination_deg,
          risk_score: track.risk_score,
          within_dv_budget: track.within_dv_budget,
          trajectory_start: track.trajectory_start,
          trajectory_end: track.trajectory_end,
          point_count: track.point_count,
        },
      })
    })

    // B. Render Debris Tracks (if enabled)
    if (showDebris) {
      globeData.debris.forEach((track: GlobeDebrisTrack) => {
        const positions: Cesium.Cartesian3[] = []
        const positionProp = new Cesium.SampledPositionProperty()

        track.trajectory.forEach((pt) => {
          const julian = Cesium.JulianDate.fromIso8601(pt.t)
          const fixedPos = temeKmToCesiumFixed(pt.x_km, pt.y_km, pt.z_km, julian)
          positions.push(fixedPos)
          positionProp.addSample(julian, fixedPos)
        })

        // Debris orbit path
        viewer.entities.add({
          id: `debris-orbit-${track.norad_id}`,
          polyline: {
            positions,
            width: 1.2,
            material: Cesium.Color.ORANGE.withAlpha(0.65),
          },
          properties: {
            norad_id: track.norad_id,
            object_name: track.object_name,
            debris_db_id: track.debris_db_id,
            point_count: track.point_count,
          },
        })

        // Time-dynamic current debris position
        viewer.entities.add({
          id: `debris-marker-${track.norad_id}`,
          position: positionProp,
          point: {
            pixelSize: 4.5,
            color: Cesium.Color.ORANGE,
            outlineColor: Cesium.Color.BLACK,
            outlineWidth: 1,
          },
          label: {
            text: `NORAD ${track.norad_id}`,
            font: '10px monospace',
            fillColor: Cesium.Color.ORANGE,
            pixelOffset: new Cesium.Cartesian2(0, 12),
            showBackground: true,
            backgroundColor: Cesium.Color.BLACK.withAlpha(0.7),
            distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 25000000),
          },
          properties: {
            norad_id: track.norad_id,
            object_name: track.object_name,
            debris_db_id: track.debris_db_id,
            point_count: track.point_count,
          },
        })
      })
    }

    // C. Render Conjunction Event Markers
    globeData.events.forEach((evt: GlobeEventMarker) => {
      if (evt.x_km == null || evt.y_km == null || evt.z_km == null) {
        throw new Error(
          `Event marker '${evt.event_id}' is missing required TEME coordinates (x_km, y_km, z_km).`
        )
      }
      const isSelected = selectedEventId === evt.event_id
      const eventJulian = Cesium.JulianDate.fromIso8601(evt.tca)
      // Transform exact backend TCA event position
      const eventFixedPos = temeKmToCesiumFixed(evt.x_km, evt.y_km, evt.z_km, eventJulian)

      viewer.entities.add({
        id: `event-marker-${evt.event_id}`,
        position: eventFixedPos,
        point: {
          pixelSize: isSelected ? 12 : 8,
          color: isSelected ? Cesium.Color.YELLOW : Cesium.Color.MAGENTA,
          outlineColor: Cesium.Color.WHITE,
          outlineWidth: isSelected ? 2.5 : 1.5,
        },
        label: {
          text: `Event: ${evt.miss_distance_km.toFixed(2)}km`,
          font: '10px monospace',
          fillColor: isSelected ? Cesium.Color.YELLOW : Cesium.Color.MAGENTA,
          pixelOffset: new Cesium.Cartesian2(0, -14),
          showBackground: true,
          backgroundColor: Cesium.Color.BLACK.withAlpha(0.8),
        },
        properties: {
          event_id: evt.event_id,
          candidate_id: evt.candidate_id,
          debris_norad_id: evt.debris_norad_id,
          tca: evt.tca,
          miss_distance_km: evt.miss_distance_km,
          relative_velocity_km_s: evt.relative_velocity_km_s,
          x_km: evt.x_km,
          y_km: evt.y_km,
          z_km: evt.z_km,
        },
      })
    })
  }, [globeData, selectedCandidateId, selectedEventId, showDebris])

  // Camera reset helper
  const handleResetCamera = useCallback(() => {
    const viewer = viewerRef.current
    if (!viewer || viewer.isDestroyed()) return
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(0.0, 15.0, 24000000.0),
      duration: 1.0,
    })
  }, [])

  return (
    <div className="relative w-full h-[520px] md:h-[600px] bg-slate-950 rounded-xl overflow-hidden border border-slate-800 shadow-xl">
      {/* Cesium Viewer Canvas Mount Container */}
      <div
        ref={containerRef}
        className="w-full h-full"
        role="region"
        aria-label="3D Orbital Visualization Globe"
      />

      {/* Loading Overlay */}
      {isLoading && (
        <div className="absolute inset-0 bg-slate-950/70 backdrop-blur-sm flex flex-col items-center justify-center space-y-3 z-20">
          <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
          <span className="text-xs font-mono text-cyan-300">Loading 3D orbital visualization…</span>
        </div>
      )}

      {/* Reset View Button floating on globe */}
      <div className="absolute top-3 right-3 z-10">
        <button
          type="button"
          onClick={handleResetCamera}
          className="px-2.5 py-1 bg-slate-900/80 hover:bg-slate-800 text-slate-200 border border-slate-700/80 rounded text-xs font-mono backdrop-blur cursor-pointer transition-colors"
          title="Reset camera to overview"
        >
          Reset View
        </button>
      </div>

      {/* Selected Entity Popup/Info Overlay */}
      {selectedEntityInfo && (
        <div className="absolute bottom-3 left-3 z-10 max-w-xs bg-slate-900/90 border border-slate-700/80 rounded-lg p-3 text-xs font-mono shadow-xl backdrop-blur">
          <div className="flex items-center justify-between border-b border-slate-800 pb-1.5 mb-2">
            <span className="font-semibold text-white">{selectedEntityInfo.title}</span>
            <button
              type="button"
              onClick={() => setSelectedEntityInfo(null)}
              className="text-slate-400 hover:text-white px-1 text-sm font-bold cursor-pointer"
              aria-label="Close entity info"
            >
              ×
            </button>
          </div>
          <div className="space-y-1">
            {selectedEntityInfo.details.map((d, i) => (
              <div key={i} className="flex justify-between text-[11px]">
                <span className="text-slate-400">{d.label}:</span>
                <span className="text-slate-200 font-medium">{d.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
