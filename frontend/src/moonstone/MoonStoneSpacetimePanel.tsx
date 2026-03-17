import React, { useMemo, useState } from 'react'
import MetricViewportPanel from './MetricViewportPanel'

type DisplayMassUnit = 'kg' | 'Msun'
type DisplayVelocityUnit = 'm/s' | 'km/s' | '%c'
type DisplayAngleUnit = 'deg' | 'rad'

type Props = {
  safeViewBox: string
  toScene: (v: number) => number
  safeCellSize: [number, number, number]
  geometry: any[]
  materials: any[]
  sources: any[]
  monitors: any[]
  displayUnits: any
  displayAngleUnits: DisplayAngleUnit
  displayMassUnits: DisplayMassUnit
  displayVelocityUnits: DisplayVelocityUnit
  isMoveActive: boolean
  isPanning: boolean
  safeZoom: number
  viewCenter: [number, number]
}

export default function MoonStoneSpacetimePanel(props: Props) {
  const [drawCurvature, setDrawCurvature] = useState(true)
  const [drawPhotons, setDrawPhotons] = useState(true)
  const [colorShiftOverlays, setColorShiftOverlays] = useState(true)
  const [recalcOnZoom, setRecalcOnZoom] = useState(false)
  const [updateMode, setUpdateMode] = useState<'drag' | 'drop' | 'refresh'>('drop')
  const [recomputeToken, setRecomputeToken] = useState(0)

  const statusText = useMemo(() => {
    if (updateMode === 'drag') return 'Updating during interaction.'
    if (props.isMoveActive || props.isPanning) {
      return updateMode === 'drop'
        ? 'Frozen while interacting. Refreshes on drop.'
        : 'Frozen while interacting. Refresh manually when needed.'
    }
    return 'Synced to the active StarDust CAD view.'
  }, [props.isMoveActive, props.isPanning, updateMode])

  const modeLabel = useMemo(() => {
    if (updateMode === 'drag') return 'live'
    if (updateMode === 'drop') return 'deferred'
    return 'manual'
  }, [updateMode])

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', background: 'rgba(2,6,23,1)', display: 'grid', gridTemplateRows: 'auto minmax(0, 1fr)' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 10,
          flexWrap: 'wrap',
          padding: '8px 10px',
          borderBottom: '1px solid rgba(148,163,184,0.12)',
          background: 'rgba(2,6,23,0.92)',
        }}
      >
        <div style={{ minWidth: 0 }}>
          <div style={{ color: 'rgba(226,232,240,0.92)', fontSize: 12, fontWeight: 600 }}>Spacetime canvas</div>
          <div style={{ color: 'rgba(148,163,184,0.88)', fontSize: 11, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {statusText} Viewport stays aligned with this tab; heavy recompute stays throttled.
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          <label style={{ display: 'inline-flex', gap: 6, alignItems: 'center', margin: 0, color: 'rgba(226,232,240,0.92)', fontSize: 12 }}>
            <input type="checkbox" checked={drawCurvature} onChange={(e) => setDrawCurvature(e.target.checked)} />
            Grid
          </label>
          <label style={{ display: 'inline-flex', gap: 6, alignItems: 'center', margin: 0, color: 'rgba(226,232,240,0.92)', fontSize: 12 }}>
            <input type="checkbox" checked={drawPhotons} onChange={(e) => setDrawPhotons(e.target.checked)} />
            Photons
          </label>
          <label style={{ display: 'inline-flex', gap: 6, alignItems: 'center', margin: 0, color: 'rgba(226,232,240,0.92)', fontSize: 12, opacity: drawPhotons ? 1 : 0.55 }}>
            <input
              type="checkbox"
              checked={colorShiftOverlays}
              disabled={!drawPhotons}
              onChange={(e) => setColorShiftOverlays(e.target.checked)}
            />
            Shift
          </label>
          <label style={{ display: 'inline-flex', gap: 6, alignItems: 'center', margin: 0, color: 'rgba(226,232,240,0.92)', fontSize: 12 }}>
            <input type="checkbox" checked={recalcOnZoom} onChange={(e) => setRecalcOnZoom(e.target.checked)} />
            Zoom recalc
          </label>
          <select
            value={updateMode}
            onChange={(e) => setUpdateMode(e.target.value as 'drag' | 'drop' | 'refresh')}
            title="Spacetime recompute mode"
            style={{ minWidth: 96, fontSize: 12 }}
          >
            <option value="drag">Live</option>
            <option value="drop">Deferred</option>
            <option value="refresh">Manual</option>
          </select>
          <button onClick={() => setRecomputeToken((t) => t + 1)} disabled={!drawCurvature && !drawPhotons} title="Refresh spacetime canvas">
            Refresh
          </button>
          <div style={{ color: 'rgba(148,163,184,0.82)', fontSize: 11 }}>
            {props.safeZoom.toFixed(2)}× · {modeLabel}
          </div>
        </div>
      </div>

      <div style={{ position: 'relative', minHeight: 0 }}>
        <MetricViewportPanel
          enabled={drawCurvature || drawPhotons}
          updateMode={updateMode}
          safeViewBox={props.safeViewBox}
          toScene={props.toScene}
          safeCellSize={props.safeCellSize}
          geometry={props.geometry}
          materials={props.materials}
          sources={props.sources}
          monitors={props.monitors}
          displayUnits={props.displayUnits}
          displayMassUnits={props.displayMassUnits}
          displayVelocityUnits={props.displayVelocityUnits}
          isMoveActive={props.isMoveActive}
          isPanning={props.isPanning}
          drawCurvature={drawCurvature}
          drawPhotons={drawPhotons}
          colorShiftOverlays={colorShiftOverlays}
          recalcOnZoom={recalcOnZoom}
          recomputeToken={recomputeToken}
        />
      </div>
    </div>
  )
}
