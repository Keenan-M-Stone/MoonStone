import React, { useEffect, useMemo, useState } from 'react'
import { BackendTransportProvider, StarDustApp, createFetchBackendTransport } from '@stardust/ui'

import RunPanel from './RunPanel'
import GwPolarizationEditor from './polarization/GwPolarizationEditor'

const SPEED_OF_LIGHT_M_S = 299_792_458
const SOLAR_MASS_KG = 1.98847e30
const LY_M = 9.4607304725808e15
const MLY_M = LY_M * 1e6
type CsvXAxis = 'frequency_hz' | 'wavelength_m' | 'wavelength_um' | 'wavelength_nm'

const MOONSTONE_DEFAULT_MATERIALS: any[] = [
  { id: 'vac', label: 'Vacuum', color: '#94a3b8' },
  { id: 'avg_star', label: 'Average star', color: '#e2e8f0', payload: { massKg: 1.0 * SOLAR_MASS_KG } },
  { id: 'pulsar', label: 'Pulsar', color: '#38bdf8', payload: { massKg: 1.4 * SOLAR_MASS_KG, densityKgM3: 1e17 } },
  { id: 'white_dwarf', label: 'White dwarf', color: '#a78bfa', payload: { massKg: 0.6 * SOLAR_MASS_KG, densityKgM3: 1e9 } },
  { id: 'black_hole_static', label: 'Black hole (static)', color: '#94a3b8', payload: { massKg: 10 * SOLAR_MASS_KG } },
  { id: 'black_hole_rotating', label: 'Black hole (rotating)', color: '#94a3b8', payload: { massKg: 10 * SOLAR_MASS_KG, spinRps: 50 } },
  { id: 'cosmic_string', label: 'Cosmic string', color: '#e2e8f0', payload: { tension: 1 } },
  { id: 'white_hole', label: 'White hole', color: '#e2e8f0', payload: { massKg: 10 * SOLAR_MASS_KG } },
  { id: 'tipler_cylinder', label: 'Tipler cylinder', color: '#f97316', payload: { massKg: 1e28, densityKgM3: 1e4 } },
  { id: 'magnani_gas_cloud', label: 'Magnani gas cloud', color: '#38bdf8', payload: { massKg: 1e25, densityKgM3: 1e-18 } },
]

const MOONSTONE_DEFAULT_SCENE: {
  cellSize: [number, number, number]
  geometry: any[]
  sources: any[]
  monitors: any[]
} = (() => {
  // A simple lensing vignette: two stars (sources) far left, a black hole pair near origin,
  // and an observer (monitor) far right.
  const cellSize: [number, number, number] = [8 * MLY_M, 6 * MLY_M, 2 * MLY_M]

  const bhSep = 0.08 * MLY_M
  const bhR = 0.05 * MLY_M
  const starR = 0.08 * MLY_M

  const star1: [number, number] = [-3.2 * MLY_M, -0.6 * MLY_M]
  const star2: [number, number] = [-3.2 * MLY_M, 0.6 * MLY_M]
  const bh1: [number, number] = [-0.5 * bhSep, 0]
  const bh2: [number, number] = [0.5 * bhSep, 0]
  const observer: [number, number] = [3.2 * MLY_M, 0]

  const geometry: any[] = [
    { id: 'geom-star-1', shape: 'sphere', center: star1, centerZ: 0, size: [starR, starR], sizeZ: starR, materialId: 'avg_star' },
    { id: 'geom-star-2', shape: 'sphere', center: star2, centerZ: 0, size: [starR, starR], sizeZ: starR, materialId: 'avg_star' },
    { id: 'geom-bh-1', shape: 'sphere', center: bh1, centerZ: 0, size: [bhR, bhR], sizeZ: bhR, materialId: 'black_hole_static' },
    { id: 'geom-bh-2', shape: 'sphere', center: bh2, centerZ: 0, size: [bhR, bhR], sizeZ: bhR, materialId: 'black_hole_static' },
  ]

  const mkSource = (id: string, position: [number, number]) => ({
    id,
    position,
    z: 0,
    component: 'Ez',
    centerFreq: 4.0e14,
    fwidth: 6.0e13,
  })

  const mkMonitor = (id: string, position: [number, number]) => ({
    id,
    position,
    z: 0,
    components: ['Ez'],
    dt: 1e-16,
    shape: 'point',
    size: [0.3 * MLY_M, 0.3 * MLY_M],
    sampling: { mode: 'points', nx: 5, ny: 5, fallbackToPoints: true },
  })

  return {
    cellSize,
    geometry,
    sources: [mkSource('src-star-1', star1), mkSource('src-star-2', star2)],
    monitors: [mkMonitor('mon-observer', observer)],
  }
})()

export default function App(){
  const [spacetimePreview, setSpacetimePreview] = useState(false)
  const [showPhotonOverlays, setShowPhotonOverlays] = useState(false)
  const [colorShiftOverlays, setColorShiftOverlays] = useState(true)
  const [recalcOnZoom, setRecalcOnZoom] = useState(false)
  const [backendMode, setBackendMode] = useState<'realtime' | 'backend'>(() => {
    try {
      const v = window.localStorage.getItem('moonstone.computeMode')
      return v === 'backend' ? 'backend' : 'realtime'
    } catch {
      return 'realtime'
    }
  })
  const [advancedTensorsOpen, setAdvancedTensorsOpen] = useState(false)
  const [csvXAxisEps, setCsvXAxisEps] = useState<CsvXAxis>('wavelength_nm')
  const [csvXAxisMu, setCsvXAxisMu] = useState<CsvXAxis>('wavelength_nm')

  useEffect(() => {
    try {
      window.localStorage.setItem('moonstone.computeMode', backendMode)
    } catch {
      // ignore
    }
  }, [backendMode])

  const transport = useMemo(() => {
    const apiBase = (import.meta as any).env?.VITE_API_BASE as string | undefined
    const base = (apiBase ?? 'http://localhost:8000').replace(/\/+$/, '')
    // MoonStone backend is mounted under /moon
    return createFetchBackendTransport({ basePath: `${base}/moon` })
  }, [])

  return (
    <BackendTransportProvider transport={transport}>
      <StarDustApp
        branding={{
          title: 'MoonStone',
          subtitle: 'built from StarDust',
        }}
        initial={{
          materials: MOONSTONE_DEFAULT_MATERIALS,
          cellSize: MOONSTONE_DEFAULT_SCENE.cellSize,
          geometry: MOONSTONE_DEFAULT_SCENE.geometry,
          sources: MOONSTONE_DEFAULT_SCENE.sources,
          monitors: MOONSTONE_DEFAULT_SCENE.monitors,
        }}
        initialDisplayUnits="MLY"
        materialEditor={{
          showExtraJson: false,
        }}
        cad2d={{
          showBaseGrid: !spacetimePreview,
        }}
        extensions={{
          toolsExtra: (
            <>
              <h2>MoonStone</h2>

              <label>
                Compute
                <select value={backendMode} onChange={(e) => setBackendMode(e.target.value as any)}>
                  <option value="realtime">Realtime (overlay)</option>
                  <option value="backend">Backend run (precise)</option>
                </select>
              </label>

              <label className="check">
                <input
                  type="checkbox"
                  checked={spacetimePreview}
                  onChange={(e) => setSpacetimePreview(e.target.checked)}
                />
                Spacetime preview (curvature grid)
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  checked={showPhotonOverlays}
                  onChange={(e) => setShowPhotonOverlays(e.target.checked)}
                />
                Photon trajectory overlays
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  checked={colorShiftOverlays}
                  onChange={(e) => setColorShiftOverlays(e.target.checked)}
                  disabled={!showPhotonOverlays}
                />
                Color photons by red/blue shift (approx.)
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  checked={recalcOnZoom}
                  onChange={(e) => setRecalcOnZoom(e.target.checked)}
                />
                Recompute on zoom (higher precision)
              </label>

              {backendMode === 'backend' ? (
                <RunPanel />
              ) : null}
            </>
          ),
          layoutPresets: [
            {
              id: 'moonstone.spacetime',
              label: 'Spacetime (lensing)',
              preset: {
                showTools: true,
                showProperties: false,
                showRunPanel: false,
                canvasMaximized: false,
                cadViewsLayout: 'stack',
              },
            },
          ],
          onApplyLayoutPreset: (id) => {
            if (id === 'moonstone.spacetime') {
              setSpacetimePreview(true)
              setShowPhotonOverlays(true)
            }
          },
          renderCanvas2dOverlays: ({
            toScene,
            sources,
            monitors,
            overlayStrokeWidth,
            overlayAutoscale,
            displayUnits,
            displayMassUnits,
            displayVelocityUnits,
            geometry,
            materials,
            safeCellSize,
            plane2dActive,
          }) => {
            const drawCurvature = spacetimePreview
            const drawPhotons = showPhotonOverlays
            if (!drawCurvature && !drawPhotons) return null
            if (plane2dActive) return null

            const geoms = Array.isArray(geometry) ? geometry : []
            const mats = Array.isArray(materials) ? materials : []

            const materialById = new Map<string, any>()
            for (const m of mats) {
              if (m && typeof m.id === 'string') materialById.set(m.id, m)
            }

            const masses: Array<{ x: number; y: number; m: number }> = []
            for (const g of geoms) {
              const c = (g as any)?.center
              if (!Array.isArray(c) || c.length < 2) continue
              const x = Number(c[0])
              const y = Number(c[1])
              if (!Number.isFinite(x) || !Number.isFinite(y)) continue

              const matId = String((g as any)?.materialId ?? '')
              const mat = materialById.get(matId)
              const payload = (mat?.payload && typeof mat.payload === 'object') ? mat.payload : null
              let mk = payload && typeof (payload as any).massKg === 'number' ? Number((payload as any).massKg) : 0

              // Small tightening: if a material has no explicit mass but does provide density,
              // approximate mass from geometry volume (currently only sphere supported).
              if (!(Number.isFinite(mk) && mk > 0)) {
                const rho = payload && typeof (payload as any).densityKgM3 === 'number' ? Number((payload as any).densityKgM3) : 0
                const shape = String((g as any)?.shape ?? '')
                if (Number.isFinite(rho) && rho > 0 && shape === 'sphere') {
                  const size = (g as any)?.size
                  const sizeZ = Number((g as any)?.sizeZ ?? NaN)
                  const rx = Array.isArray(size) ? Number(size[0] ?? NaN) : NaN
                  const ry = Array.isArray(size) ? Number(size[1] ?? NaN) : NaN
                  const r = [rx, ry, sizeZ].filter((v) => Number.isFinite(v) && v > 0)
                  const rMean = r.length ? (r.reduce((a, b) => a + b, 0) / r.length) : 0
                  if (rMean > 0) mk = rho * ((4 / 3) * Math.PI * Math.pow(rMean, 3))
                }
              }

              if (Number.isFinite(mk) && mk > 0) masses.push({ x, y, m: mk })
            }

            // If no explicit masses exist, still render something stable.
            const eps2 = Math.max(1e-24, Math.pow(Math.max(safeCellSize?.[0] ?? 1, safeCellSize?.[1] ?? 1) * 0.01, 2))
            const massScale = masses.length ? (1 / (masses.reduce((a, b) => a + b.m, 0) || 1)) : 0

            const gradPhi = (x: number, y: number): [number, number] => {
              if (!masses.length) return [0, 0]
              let gx = 0
              let gy = 0
              for (const mm of masses) {
                const dx = x - mm.x
                const dy = y - mm.y
                const r2 = dx * dx + dy * dy + eps2
                const r = Math.sqrt(r2)
                const invR3 = 1 / (r2 * r)
                const w = (mm.m * massScale)
                // ∇(1/r) = -r_vec/r^3 ; we use a scaled negative potential, so bend towards masses.
                gx += -w * dx * invR3
                gy += -w * dy * invR3
              }
              return [gx, gy]
            }

            const phi = (x: number, y: number): number => {
              if (!masses.length) return 0
              let out = 0
              for (const mm of masses) {
                const dx = x - mm.x
                const dy = y - mm.y
                const r2 = dx * dx + dy * dy + eps2
                const r = Math.sqrt(r2)
                const w = (mm.m * massScale)
                out += w * (1 / r)
              }
              return out
            }

            const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v))
            const lerp = (a: number, b: number, t: number) => a + (b - a) * t
            const rgb = (r: number, g: number, b: number, a: number) => `rgba(${Math.round(r)},${Math.round(g)},${Math.round(b)},${a})`
            const shiftColor = (s: number, alpha: number) => {
              // s in [-1,1]: -1 = red, 0 = white, +1 = blue
              const t = clamp(s, -1, 1)
              if (t === 0) return rgb(255, 255, 255, alpha)
              if (t < 0) {
                const u = -t
                return rgb(255, lerp(255, 60, u), lerp(255, 60, u), alpha)
              }
              return rgb(lerp(255, 60, t), lerp(255, 140, t), 255, alpha)
            }

            const worldToScene = (p: [number, number]) => [toScene(p[0]), toScene(p[1])] as [number, number]

            const gridStroke = 'rgba(148,163,184,0.35)'
            const photonStroke = 'rgba(34,211,238,0.85)'
            const strokeWidth = Math.max(overlayStrokeWidth, overlayStrokeWidth * 0.9)

            const halfW = Math.abs(Number(safeCellSize?.[0] ?? 0)) * 0.5
            const halfH = Math.abs(Number(safeCellSize?.[1] ?? 0)) * 0.5
            const gridLines = 18
            const samples = 40

            const warpK = 0.18 * Math.min(halfW || 1, halfH || 1)

            const gridPaths: React.ReactNode[] = []
            if (drawCurvature) {
              for (let i = 0; i <= gridLines; i++) {
                const t = (i / gridLines)
                const x0 = -halfW + t * (2 * halfW)
                const y0 = -halfH + t * (2 * halfH)

                // vertical line at x=x0
                {
                  const pts: Array<[number, number]> = []
                  for (let j = 0; j <= samples; j++) {
                    const s = (j / samples)
                    const y = -halfH + s * (2 * halfH)
                    const [gx, gy] = gradPhi(x0, y)
                    const wx = x0 + warpK * gx
                    const wy = y + warpK * gy
                    pts.push(worldToScene([wx, wy]))
                  }
                  const d = pts.map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${p[0]} ${p[1]}`).join(' ')
                  gridPaths.push(
                    <path
                      key={`gv:${i}`}
                      d={d}
                      fill="none"
                      stroke={gridStroke}
                      strokeWidth={strokeWidth}
                      opacity={0.9}
                      vectorEffect={overlayAutoscale ? undefined : 'non-scaling-stroke'}
                    />,
                  )
                }

                // horizontal line at y=y0
                {
                  const pts: Array<[number, number]> = []
                  for (let j = 0; j <= samples; j++) {
                    const s = (j / samples)
                    const x = -halfW + s * (2 * halfW)
                    const [gx, gy] = gradPhi(x, y0)
                    const wx = x + warpK * gx
                    const wy = y0 + warpK * gy
                    pts.push(worldToScene([wx, wy]))
                  }
                  const d = pts.map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${p[0]} ${p[1]}`).join(' ')
                  gridPaths.push(
                    <path
                      key={`gh:${i}`}
                      d={d}
                      fill="none"
                      stroke={gridStroke}
                      strokeWidth={strokeWidth}
                      opacity={0.9}
                      vectorEffect={overlayAutoscale ? undefined : 'non-scaling-stroke'}
                    />,
                  )
                }
              }
            }

            const legend: React.ReactNode[] = []
            if (drawCurvature || drawPhotons) {
              const halfW = Math.abs(Number(safeCellSize?.[0] ?? 0)) * 0.5
              const halfH = Math.abs(Number(safeCellSize?.[1] ?? 0)) * 0.5
              const x = toScene(-halfW * 0.98)
              const y = toScene(-halfH * 0.92)
              const massSuffix = displayMassUnits === 'Msun' ? 'M☉' : 'kg'
              legend.push(
                <text
                  key="legend"
                  x={x}
                  y={y}
                  fill="rgba(226,232,240,0.75)"
                  fontSize={12}
                  fontFamily="system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
                >
                  {`Units: ${displayUnits} / ${massSuffix} / ${displayVelocityUnits}`}
                </text>,
              )
            }

            const photonPaths: React.ReactNode[] = []
            if (drawPhotons) {
              const srcs = Array.isArray(sources) ? sources : []
              const mons = Array.isArray(monitors) ? monitors : []

              const targets: Array<{ x: number; y: number }> = mons
                .map((m: any) => ({ x: Number(m?.position?.[0] ?? NaN), y: Number(m?.position?.[1] ?? NaN) }))
                .filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y))

              for (const s of srcs) {
                const sx0 = Number(s?.position?.[0] ?? NaN)
                const sy0 = Number(s?.position?.[1] ?? NaN)
                if (!Number.isFinite(sx0) || !Number.isFinite(sy0)) continue

                // If there are monitors, aim at them. Otherwise, shoot a default ray +X.
                const aims = targets.length ? targets : [{ x: sx0 + (halfW || 1), y: sy0 }]

                for (let ti = 0; ti < aims.length; ti++) {
                  const aim = aims[ti]
                  let dx = aim.x - sx0
                  let dy = aim.y - sy0
                  const d0 = Math.hypot(dx, dy) || 1
                  dx /= d0
                  dy /= d0

                  let x = sx0
                  let y = sy0
                  let vx = dx
                  let vy = dy

                  const ptsWorld: Array<[number, number]> = [[x, y]]
                  const steps = 220
                  const stepLen = (Math.min(halfW || 1, halfH || 1) * 2) / steps
                  const bendK = 0.9 * warpK

                  const phi0 = phi(x, y)

                  for (let k = 0; k < steps; k++) {
                    const [gx, gy] = gradPhi(x, y)
                    vx += bendK * gx
                    vy += bendK * gy
                    const v = Math.hypot(vx, vy) || 1
                    vx /= v
                    vy /= v

                    x += vx * stepLen
                    y += vy * stepLen

                    if (Math.abs(x) > halfW * 1.1 || Math.abs(y) > halfH * 1.1) break
                    ptsWorld.push([x, y])
                  }

                  if (ptsWorld.length >= 2) {
                    if (!colorShiftOverlays) {
                      const pts = ptsWorld.map((p) => worldToScene(p))
                      const d = pts.map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${p[0]} ${p[1]}`).join(' ')
                      photonPaths.push(
                        <path
                          key={`ph:${String(s?.id ?? 's')}:${ti}`}
                          d={d}
                          fill="none"
                          stroke={photonStroke}
                          strokeWidth={strokeWidth}
                          opacity={0.55}
                          vectorEffect={overlayAutoscale ? undefined : 'non-scaling-stroke'}
                        />,
                      )
                    } else {
                      const alpha = 0.55
                      const kShift = 2.4 * (warpK / (Math.min(halfW || 1, halfH || 1) || 1))
                      for (let pi = 0; pi < ptsWorld.length - 1; pi++) {
                        const aW = ptsWorld[pi]
                        const bW = ptsWorld[pi + 1]
                        const am = (aW[0] + bW[0]) * 0.5
                        const bm = (aW[1] + bW[1]) * 0.5
                        const ph = phi(am, bm)
                        const shift = clamp((ph - phi0) * kShift, -1, 1)

                        const aS = worldToScene(aW)
                        const bS = worldToScene(bW)
                        photonPaths.push(
                          <line
                            key={`phs:${String(s?.id ?? 's')}:${ti}:${pi}`}
                            x1={aS[0]}
                            y1={aS[1]}
                            x2={bS[0]}
                            y2={bS[1]}
                            stroke={shiftColor(shift, alpha)}
                            strokeWidth={strokeWidth}
                            vectorEffect={overlayAutoscale ? undefined : 'non-scaling-stroke'}
                          />,
                        )
                      }
                    }
                  }
                }
              }
            }

            return (
              <g data-kind="moonstone-spacetime" style={{ pointerEvents: 'none' as any }}>
                {legend}
                {gridPaths}
                {photonPaths}
              </g>
            )
          },

          renderMaterialEditorFields: ({ material, updateMaterial, displayMassUnits }) => {
            const payload = (material?.payload && typeof material.payload === 'object') ? material.payload : {}

            const massKg = typeof payload.massKg === 'number' ? payload.massKg : ''
            const densityKgM3 = typeof payload.densityKgM3 === 'number' ? payload.densityKgM3 : ''

            const massLabel = displayMassUnits === 'Msun' ? 'Mass (M☉)' : 'Mass (kg)'
            const massValue = typeof massKg === 'number'
              ? (displayMassUnits === 'Msun' ? (massKg / SOLAR_MASS_KG) : massKg)
              : ''

            const downloadText = (txt: string, filename: string) => {
              try {
                const blob = new Blob([txt], { type: 'text/csv;charset=utf-8' })
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = filename
                document.body.appendChild(a)
                a.click()
                a.remove()
                URL.revokeObjectURL(url)
              } catch (e) {
                console.warn('download failed', e)
              }
            }

            const exportDispersionCsv = (fit: any, filename: string, xAxis: CsvXAxis, valueKey: 'eps_values' | 'mu_values') => {
              const freqs: any[] = Array.isArray(fit?.freqs) ? fit.freqs : []
              const values: any[] = Array.isArray(fit?.[valueKey]) ? fit[valueKey] : []
              if (!freqs.length || freqs.length !== values.length) return

              const lines: string[] = ['x,real,imag']
              for (let i = 0; i < freqs.length; i++) {
                const f = Number(freqs[i])
                if (!Number.isFinite(f) || f <= 0) continue
                const v = values[i]
                const re = typeof v === 'object' && v && 'real' in v ? Number((v as any).real) : Number(v)
                const im = typeof v === 'object' && v && 'imag' in v ? Number((v as any).imag) : 0

                let x = f
                if (xAxis !== 'frequency_hz') {
                  const lam_m = SPEED_OF_LIGHT_M_S / f
                  x = xAxis === 'wavelength_m' ? lam_m : xAxis === 'wavelength_um' ? lam_m * 1e6 : lam_m * 1e9
                }
                lines.push(`${x},${re},${im}`)
              }
              downloadText(lines.join('\n'), filename)
            }

            const importCsvToFit = (file: File | null, xAxis: CsvXAxis, target: 'eps' | 'mu') => {
              if (!file) return
              const reader = new FileReader()
              reader.onload = () => {
                const txt = String(reader.result || '')
                const rows = txt.trim().split(/\r?\n/).map(l => l.split(/,|\s+/).map(s => s.trim()).filter(Boolean))
                const parsed: { f: number; re: number; im: number }[] = []
                for (const r of rows) {
                  if (r.length >= 2) {
                    const x = Number(r[0])
                    const re = Number(r[1])
                    const im = r.length >= 3 ? Number(r[2]) : 0
                    if (!Number.isFinite(x) || !Number.isFinite(re) || !Number.isFinite(im)) continue
                    let f = x
                    if (xAxis !== 'frequency_hz') {
                      const lam_m = xAxis === 'wavelength_m' ? x : xAxis === 'wavelength_um' ? x * 1e-6 : x * 1e-9
                      if (!Number.isFinite(lam_m) || lam_m <= 0) continue
                      f = SPEED_OF_LIGHT_M_S / lam_m
                    }
                    if (Number.isFinite(f) && f > 0) parsed.push({ f, re, im })
                  }
                }
                parsed.sort((a, b) => a.f - b.f)
                const mid = parsed.length ? parsed[Math.floor(parsed.length / 2)] : null

                if (target === 'eps') {
                  updateMaterial({
                    dispersion_fit: {
                      freqs: parsed.map((r) => r.f),
                      eps_values: parsed.map((r) => ({ real: r.re, imag: r.im })),
                    },
                    ...(mid ? { eps: { real: mid.re, imag: mid.im }, center_freq: mid.f, approximate_complex: true } : {}),
                  })
                } else {
                  updateMaterial({
                    mu_dispersion_fit: {
                      freqs: parsed.map((r) => r.f),
                      mu_values: parsed.map((r) => ({ real: r.re, imag: r.im })),
                    },
                    ...(mid ? { mu: { real: mid.re, imag: mid.im }, mu_center_freq: mid.f } : {}),
                  })
                }
              }
              reader.readAsText(file)
            }

            const ensureFlat9 = (v: any): number[] => {
              if (Array.isArray(v) && v.length === 9) {
                const n = v.map((x: any) => (x === '' || x === null || x === undefined ? 0 : Number(x)))
                return n.map((x: any) => (Number.isFinite(x) ? x : 0))
              }
              if (Array.isArray(v) && v.length === 3 && v.every((r: any) => Array.isArray(r) && r.length === 3)) {
                const flat = [
                  Number(v[0][0]),
                  Number(v[0][1]),
                  Number(v[0][2]),
                  Number(v[1][0]),
                  Number(v[1][1]),
                  Number(v[1][2]),
                  Number(v[2][0]),
                  Number(v[2][1]),
                  Number(v[2][2]),
                ]
                return flat.map((x: any) => (Number.isFinite(x) ? x : 0))
              }
              return Array(9).fill(0)
            }

            const renderTensor = (field: 'epsilon' | 'mu' | 'xi' | 'zeta', label: string) => {
              const m: any = material as any
              const fallback =
                field === 'epsilon'
                  ? (m?.epsilon_tensor ?? m?.eps_tensor)
                  : field === 'mu'
                    ? (m?.mu_tensor)
                    : field === 'xi'
                      ? (m?.xi_tensor)
                      : (m?.zeta_tensor)
              const arr = ensureFlat9(m?.[field] ?? fallback)
              return (
                <div style={{ marginTop: 10 }}>
                  <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 6 }}>{label} (3x3, row-major)</div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
                    {Array.from({ length: 9 }).map((_, idx) => (
                      <input
                        key={idx}
                        value={arr[idx]}
                        onChange={(e) => {
                          const next = ensureFlat9((material as any)?.[field])
                          next[idx] = Number(e.currentTarget.value)
                          updateMaterial({ [field]: next })
                        }}
                      />
                    ))}
                  </div>
                </div>
              )
            }

            return (
              <div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                <label>
                  {massLabel}
                  <input
                    type="number"
                    value={massValue as any}
                    onChange={(e) => {
                      const v = e.currentTarget.valueAsNumber
                      const nextKg = displayMassUnits === 'Msun' ? v * SOLAR_MASS_KG : v
                      updateMaterial({
                        payload: {
                          ...payload,
                          massKg: Number.isFinite(nextKg) ? nextKg : undefined,
                        },
                      })
                    }}
                  />
                </label>
                <label>
                  Density (kg/m^3)
                  <input
                    type="number"
                    value={densityKgM3 as any}
                    onChange={(e) => {
                      const v = e.currentTarget.valueAsNumber
                      updateMaterial({
                        payload: {
                          ...payload,
                          densityKgM3: Number.isFinite(v) ? v : undefined,
                        },
                      })
                    }}
                  />
                </label>
                </div>

                <div style={{ marginTop: 10 }}>
                  <button onClick={() => setAdvancedTensorsOpen((p) => !p)}>
                    {advancedTensorsOpen ? 'Hide advanced tensors' : 'Advanced tensors'}
                  </button>
                </div>

                {advancedTensorsOpen && (
                  <div style={{ marginTop: 10, padding: 10, borderRadius: 6, background: 'rgba(255,255,255,0.02)' }}>
                    <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 6 }}>
                      Constitutive tensors (optional)
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                      <label>
                        ε (isotropic scalar)
                        {typeof (material as any)?.eps === 'object' && (material as any)?.eps && ('real' in (material as any).eps) ? (
                          <input
                            type="number"
                            value={Number(((material as any).eps as any).real) as any}
                            onChange={(e) => {
                              const v = e.currentTarget.valueAsNumber
                              updateMaterial({ eps: { real: Number.isFinite(v) ? v : 0, imag: Number((((material as any).eps as any).imag) ?? 0) } })
                            }}
                          />
                        ) : (
                          <input
                            type="number"
                            value={typeof (material as any)?.eps === 'number' ? (material as any).eps : ''}
                            onChange={(e) => {
                              const v = e.currentTarget.valueAsNumber
                              updateMaterial({ eps: Number.isFinite(v) ? v : undefined })
                            }}
                          />
                        )}
                      </label>
                      <label>
                        μ (isotropic scalar)
                        {typeof (material as any)?.mu === 'object' && (material as any)?.mu && ('real' in (material as any).mu) ? (
                          <input
                            type="number"
                            value={Number(((material as any).mu as any).real) as any}
                            onChange={(e) => {
                              const v = e.currentTarget.valueAsNumber
                              updateMaterial({ mu: { real: Number.isFinite(v) ? v : 0, imag: Number((((material as any).mu as any).imag) ?? 0) } })
                            }}
                          />
                        ) : (
                          <input
                            type="number"
                            value={typeof (material as any)?.mu === 'number' ? (material as any).mu : ''}
                            onChange={(e) => {
                              const v = e.currentTarget.valueAsNumber
                              updateMaterial({ mu: Number.isFinite(v) ? v : undefined })
                            }}
                          />
                        )}
                      </label>
                    </div>

                    <div style={{ marginTop: 8, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                      <label className="check">
                        <input
                          type="checkbox"
                          checked={typeof (material as any)?.eps === 'object' && (material as any)?.eps && ('real' in (material as any).eps)}
                          onChange={(e) => {
                            const checked = e.currentTarget.checked
                            if (checked) {
                              const re = typeof (material as any)?.eps === 'number' ? (material as any).eps : Number((((material as any).eps as any)?.real) ?? 1)
                              updateMaterial({ eps: { real: Number.isFinite(re) ? re : 1, imag: 0 } })
                            } else {
                              const re = Number((((material as any).eps as any)?.real) ?? 1)
                              updateMaterial({ eps: Number.isFinite(re) ? re : 1 })
                            }
                          }}
                        />
                        <span style={{ fontSize: 12, color: '#9ca3af' }}>Complex ε</span>
                      </label>

                      {typeof (material as any)?.eps === 'object' && (material as any)?.eps && ('real' in (material as any).eps) ? (
                        <label>
                          Im(ε)
                          <input
                            type="number"
                            value={Number((((material as any).eps as any).imag) ?? 0) as any}
                            onChange={(e) => {
                              const v = e.currentTarget.valueAsNumber
                              updateMaterial({ eps: { real: Number((((material as any).eps as any).real) ?? 0), imag: Number.isFinite(v) ? v : 0 } })
                            }}
                          />
                        </label>
                      ) : null}

                      <label className="check">
                        <input
                          type="checkbox"
                          checked={typeof (material as any)?.mu === 'object' && (material as any)?.mu && ('real' in (material as any).mu)}
                          onChange={(e) => {
                            const checked = e.currentTarget.checked
                            if (checked) {
                              const re = typeof (material as any)?.mu === 'number' ? (material as any).mu : Number((((material as any).mu as any)?.real) ?? 1)
                              updateMaterial({ mu: { real: Number.isFinite(re) ? re : 1, imag: 0 } })
                            } else {
                              const re = Number((((material as any).mu as any)?.real) ?? 1)
                              updateMaterial({ mu: Number.isFinite(re) ? re : 1 })
                            }
                          }}
                        />
                        <span style={{ fontSize: 12, color: '#9ca3af' }}>Complex μ</span>
                      </label>

                      {typeof (material as any)?.mu === 'object' && (material as any)?.mu && ('real' in (material as any).mu) ? (
                        <label>
                          Im(μ)
                          <input
                            type="number"
                            value={Number((((material as any).mu as any).imag) ?? 0) as any}
                            onChange={(e) => {
                              const v = e.currentTarget.valueAsNumber
                              updateMaterial({ mu: { real: Number((((material as any).mu as any).real) ?? 0), imag: Number.isFinite(v) ? v : 0 } })
                            }}
                          />
                        </label>
                      ) : null}
                    </div>

                    <div style={{ marginTop: 10, padding: 10, borderRadius: 6, background: 'rgba(255,255,255,0.02)' }}>
                      <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 6 }}>Dispersion CSV (x, real, imag)</div>

                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                        <div>
                          <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 6 }}>ε table</div>
                          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                            <select value={csvXAxisEps} onChange={(e) => setCsvXAxisEps(e.target.value as CsvXAxis)}>
                              <option value="frequency_hz">x = frequency (Hz)</option>
                              <option value="wavelength_m">x = wavelength (m)</option>
                              <option value="wavelength_um">x = wavelength (μm)</option>
                              <option value="wavelength_nm">x = wavelength (nm)</option>
                            </select>
                            <input type="file" accept=".csv,.txt" onChange={(e) => importCsvToFit(e.target.files?.[0] ?? null, csvXAxisEps, 'eps')} />
                            <button
                              onClick={() => exportDispersionCsv((material as any)?.dispersion_fit, `moonstone_${String((material as any)?.id ?? 'mat')}_eps.csv`, csvXAxisEps, 'eps_values')}
                              disabled={!((material as any)?.dispersion_fit && Array.isArray((material as any).dispersion_fit?.freqs))}
                            >
                              Export
                            </button>
                          </div>
                        </div>

                        <div>
                          <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 6 }}>μ table</div>
                          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                            <select value={csvXAxisMu} onChange={(e) => setCsvXAxisMu(e.target.value as CsvXAxis)}>
                              <option value="frequency_hz">x = frequency (Hz)</option>
                              <option value="wavelength_m">x = wavelength (m)</option>
                              <option value="wavelength_um">x = wavelength (μm)</option>
                              <option value="wavelength_nm">x = wavelength (nm)</option>
                            </select>
                            <input type="file" accept=".csv,.txt" onChange={(e) => importCsvToFit(e.target.files?.[0] ?? null, csvXAxisMu, 'mu')} />
                            <button
                              onClick={() => exportDispersionCsv((material as any)?.mu_dispersion_fit, `moonstone_${String((material as any)?.id ?? 'mat')}_mu.csv`, csvXAxisMu, 'mu_values')}
                              disabled={!((material as any)?.mu_dispersion_fit && Array.isArray((material as any).mu_dispersion_fit?.freqs))}
                            >
                              Export
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>

                    {renderTensor('epsilon', 'ε tensor')}
                    {renderTensor('mu', 'μ tensor')}
                    {renderTensor('xi', 'ξ coupling')}
                    {renderTensor('zeta', 'ζ coupling')}
                  </div>
                )}
              </div>
            )
          },

          renderSourceEditorFields: ({ source, updateSource }) => (
            <div style={{ marginTop: 12 }}>
              <h4>Polarization (GW)</h4>
              <GwPolarizationEditor
                value={(source as any)?.polarization}
                onChange={(next) => updateSource({ polarization: next })}
              />
            </div>
          ),
        }}
      />
    </BackendTransportProvider>
  )
}
