import React, { useEffect, useMemo, useRef, useState } from 'react'

type DisplayMassUnit = 'kg' | 'Msun'
type DisplayVelocityUnit = 'm/s' | 'km/s' | '%c'

type PhotonWorld = {
  id: string
  pts: Array<[number, number]>
  shifts?: number[]
}

type WorldData = {
  gridLines: Array<Array<[number, number]>>
  photons: PhotonWorld[]
}

const SHARED_WORLD_CACHE_LIMIT = 12
const sharedWorldCache = new Map<string, WorldData>()

function getSharedWorld(key: string) {
  const world = sharedWorldCache.get(key)
  if (!world) return null
  sharedWorldCache.delete(key)
  sharedWorldCache.set(key, world)
  return world
}

function setSharedWorld(key: string, world: WorldData) {
  sharedWorldCache.delete(key)
  sharedWorldCache.set(key, world)
  while (sharedWorldCache.size > SHARED_WORLD_CACHE_LIMIT) {
    const oldestKey = sharedWorldCache.keys().next().value
    if (!oldestKey) break
    sharedWorldCache.delete(oldestKey)
  }
}

export type MetricViewportPanelProps = {
  enabled: boolean
  updateMode: 'drag' | 'drop' | 'refresh'
  safeViewBox: string
  toScene: (v: number) => number
  safeCellSize: [number, number, number]
  geometry: any[]
  materials: any[]
  sources: any[]
  monitors: any[]
  displayUnits: any
  displayMassUnits: DisplayMassUnit
  displayVelocityUnits: DisplayVelocityUnit
  isMoveActive: boolean
  isPanning: boolean
  overlayStrokeWidth?: number
  overlayAutoscale?: boolean
  drawCurvature: boolean
  drawPhotons: boolean
  colorShiftOverlays: boolean
  recalcOnZoom: boolean
  recomputeToken: number
}

function toFinite(n: any, fallback: number) {
  const v = Number(n)
  return Number.isFinite(v) ? v : fallback
}

function clamp(v: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, v))
}

function pickTopMasses(arr: Array<{ x: number; y: number; m: number }>, n: number) {
  if (arr.length <= n) return arr
  const top: Array<{ x: number; y: number; m: number }> = []
  for (const mm of arr) {
    if (top.length < n) {
      top.push(mm)
      continue
    }
    let minIdx = 0
    let minM = top[0].m
    for (let i = 1; i < top.length; i++) {
      if (top[i].m < minM) {
        minM = top[i].m
        minIdx = i
      }
    }
    if (mm.m > minM) top[minIdx] = mm
  }
  return top
}

function parseViewBox(viewBox: string): [number, number, number, number] {
  const parts = String(viewBox)
    .trim()
    .split(/\s+/)
    .map((part) => Number(part))
  if (parts.length === 4 && parts.every((part) => Number.isFinite(part))) {
    return [parts[0], parts[1], parts[2], parts[3]]
  }
  return [-1, -1, 2, 2]
}

export default function MetricViewportPanel(p: MetricViewportPanelProps) {
  const {
    enabled,
    updateMode,
    safeViewBox,
    toScene,
    safeCellSize,
    geometry,
    materials,
    sources,
    monitors,
    displayUnits,
    displayMassUnits,
    displayVelocityUnits,
    isMoveActive,
    isPanning,
    overlayStrokeWidth: overlayStrokeWidthRaw,
    drawCurvature,
    drawPhotons,
    colorShiftOverlays,
    recalcOnZoom,
    recomputeToken,
  } = p

  const overlayStrokeWidth = Number.isFinite(Number(overlayStrokeWidthRaw)) ? Number(overlayStrokeWidthRaw) : 1.25
  const interacting = Boolean(isMoveActive || isPanning)
  const freezeDuringInteraction = Boolean(enabled && interacting && updateMode !== 'drag')
  const cacheRef = useRef<null | { key: string; world: WorldData }>(null)
  const lastComputeMsRef = useRef<number>(0)
  const prevMoveRef = useRef<boolean>(false)
  const [dropNonce, setDropNonce] = useState(0)
  const hostRef = useRef<HTMLDivElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 })
  const [docVisible, setDocVisible] = useState(() => (typeof document === 'undefined' ? true : !document.hidden))
  const [hostVisible, setHostVisible] = useState(true)

  useEffect(() => {
    if (typeof document === 'undefined') return
    const handleVisibility = () => setDocVisible(!document.hidden)
    handleVisibility()
    document.addEventListener('visibilitychange', handleVisibility)
    return () => document.removeEventListener('visibilitychange', handleVisibility)
  }, [])

  useEffect(() => {
    if (updateMode !== 'drop') return
    const prev = prevMoveRef.current
    prevMoveRef.current = isMoveActive
    if (prev && !isMoveActive) setDropNonce((n) => n + 1)
  }, [isMoveActive, updateMode])

  useEffect(() => {
    const host = hostRef.current
    if (!host) return

    const update = () => {
      const nextWidth = Math.max(0, Math.floor(host.clientWidth))
      const nextHeight = Math.max(0, Math.floor(host.clientHeight))
      setCanvasSize((prev) => (
        prev.width === nextWidth && prev.height === nextHeight
          ? prev
          : { width: nextWidth, height: nextHeight }
      ))
    }

    update()
    const observer = new ResizeObserver(update)
    observer.observe(host)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const host = hostRef.current
    if (!host || typeof IntersectionObserver === 'undefined') return

    const observer = new IntersectionObserver((entries) => {
      const next = entries.some((entry) => entry.isIntersecting && entry.intersectionRatio > 0)
      setHostVisible(next)
    }, { threshold: [0, 0.01] })

    observer.observe(host)
    return () => observer.disconnect()
  }, [])

  const panelVisible = docVisible && hostVisible

  const materialById = useMemo(() => {
    const map = new Map<string, any>()
    for (const material of Array.isArray(materials) ? materials : []) {
      if (material && typeof material.id === 'string') map.set(material.id, material)
    }
    return map
  }, [materials])

  const massesCacheRef = useRef<Array<{ x: number; y: number; m: number }>>([])
  const masses = useMemo(() => {
    if (interacting) return massesCacheRef.current

    const nowMs = () => (typeof performance !== 'undefined' && typeof performance.now === 'function') ? performance.now() : Date.now()
    const startedMs = nowMs()
    const budgetMs = 18
    const overBudget = () => (nowMs() - startedMs) > budgetMs
    let budgetAborted = false

    const out: Array<{ x: number; y: number; m: number }> = []
    for (const g of Array.isArray(geometry) ? geometry : []) {
      if (overBudget()) {
        budgetAborted = true
        break
      }
      const c = (g as any)?.center
      if (!Array.isArray(c) || c.length < 2) continue
      const x = Number(c[0])
      const y = Number(c[1])
      if (!Number.isFinite(x) || !Number.isFinite(y)) continue

      const matId = String((g as any)?.materialId ?? '')
      const mat = materialById.get(matId)
      const payload = mat?.payload && typeof mat.payload === 'object' ? mat.payload : null

      let mk = payload && typeof (payload as any).massKg === 'number' ? Number((payload as any).massKg) : 0
      if (!(Number.isFinite(mk) && mk > 0)) {
        const rho = payload && typeof (payload as any).densityKgM3 === 'number' ? Number((payload as any).densityKgM3) : 0
        const shape = String((g as any)?.shape ?? '')
        const size = (g as any)?.size
        const sizeZ = Number((g as any)?.sizeZ ?? 0)
        if (Number.isFinite(rho) && rho > 0 && shape === 'sphere' && Array.isArray(size) && size.length >= 2) {
          const r = Math.abs(Number(size[0]) || 0)
          mk = rho * ((4 / 3) * Math.PI * r * r * r)
        } else if (Number.isFinite(rho) && rho > 0 && Number.isFinite(sizeZ) && sizeZ > 0 && Array.isArray(size) && size.length >= 2) {
          mk = rho * Math.abs(Number(size[0]) || 0) * Math.abs(Number(size[1]) || 0) * Math.abs(sizeZ)
        }
      }

      if (Number.isFinite(mk) && mk > 0) out.push({ x, y, m: mk })
    }

    const picked = pickTopMasses(out, 64)
    massesCacheRef.current = picked

    if (budgetAborted && Boolean((import.meta as any)?.env?.DEV)) {
      console.info('[moonstone] masses scan aborted', { total: Array.isArray(geometry) ? geometry.length : 0, picked: picked.length })
    }

    return picked
  }, [geometry, interacting, materialById])

  const computed = useMemo(() => {
    if (!enabled) return null
    if (!drawCurvature && !drawPhotons) return null

    const nowMs = () => (typeof performance !== 'undefined' && typeof performance.now === 'function') ? performance.now() : Date.now()
    const startedMs = nowMs()
    const budgetMs = interacting ? 12 : 28
    const overBudget = () => (nowMs() - startedMs) > budgetMs
    let budgetAborted = false

    const lerp = (a: number, b: number, t: number) => a + (b - a) * t
    const rgb = (r: number, g: number, b: number, a: number) => `rgba(${Math.round(r)},${Math.round(g)},${Math.round(b)},${a})`
    const shiftColor = (s: number, alpha: number) => {
      const t = clamp(s, -1, 1)
      if (t === 0) return rgb(255, 255, 255, alpha)
      if (t < 0) {
        const u = -t
        return rgb(255, lerp(255, 60, u), lerp(255, 60, u), alpha)
      }
      return rgb(lerp(255, 60, t), lerp(255, 140, t), 255, alpha)
    }

    const halfW = Math.abs(toFinite(safeCellSize?.[0], 0)) * 0.5
    const halfH = Math.abs(toFinite(safeCellSize?.[1], 0)) * 0.5

    let allowRecompute = updateMode === 'drag' || !interacting
    if (allowRecompute && updateMode === 'drag' && interacting) {
      const now = Date.now()
      if (now - (lastComputeMsRef.current || 0) < 140) allowRecompute = false
    }

    // Adaptive mass scaling: normalise so the dominant mass produces
    // ~0.3 rad total photon deflection through the gravitational lens region.
    // At astrophysical scales (MLY) the original 1e-30 yields negligible effects.
    const maxMassKg = masses.reduce((mx, mm) => Math.max(mx, mm.m), 0)
    const halfMin = Math.min(halfW || 1, halfH || 1)
    const massScale = maxMassKg > 0
      ? halfMin / (1000 * maxMassKg)
      : 1e-30
    const softening = Math.max(halfMin * 1e-3, 1e-12)

    const phi = (x: number, y: number) => {
      let out = 0
      for (const mm of masses) {
        const dx = x - mm.x
        const dy = y - mm.y
        const r2 = dx * dx + dy * dy + softening * softening
        out += (mm.m * massScale) * (1 / Math.sqrt(r2))
      }
      return out
    }

    const gradPhi = (x: number, y: number) => {
      let gx = 0
      let gy = 0
      for (const mm of masses) {
        const dx = x - mm.x
        const dy = y - mm.y
        const r2 = dx * dx + dy * dy + softening * softening
        const invR = 1 / Math.sqrt(r2)
        const invR3 = invR * invR * invR
        const w = mm.m * massScale
        gx += -w * dx * invR3
        gy += -w * dy * invR3
      }
      return [gx, gy] as [number, number]
    }

    const gridStroke = 'rgba(148,163,184,0.35)'
    const photonStroke = 'rgba(34,211,238,0.85)'
    const strokeWidth = Math.max(overlayStrokeWidth, overlayStrokeWidth * 0.9)

    const MAX_GRID_POINTS = interacting ? 1100 : 2400
    let gridLines = 18
    let samples = 40
    while ((2 * (gridLines + 1) * (samples + 1)) > MAX_GRID_POINTS && samples > 12) {
      samples = Math.max(12, Math.floor(samples * 0.75))
    }
    while ((2 * (gridLines + 1) * (samples + 1)) > MAX_GRID_POINTS && gridLines > 8) {
      gridLines = Math.max(8, Math.floor(gridLines * 0.75))
    }

    const warpK = 0.18 * halfMin
    // Amplified grid warp; tanh-capped so mass centres don't explode.
    const gridWarpK = warpK * halfMin / 3
    const gridWarpCap = 0.15 * 2 * halfMin / gridLines
    const warpDisp = (gx: number, gy: number): [number, number] => {
      const gmag = Math.hypot(gx, gy)
      if (gmag < 1e-40) return [0, 0]
      const capD = gridWarpCap * Math.tanh(gridWarpK * gmag / gridWarpCap)
      return [capD * gx / gmag, capD * gy / gmag]
    }
    const roundKey = (v: number) => (Number.isFinite(v) ? Number(v).toPrecision(6) : 'nan')

    const srcs = (Array.isArray(sources) ? sources : []).slice(0, 8)
    const targets = (Array.isArray(monitors) ? monitors : [])
      .map((m: any) => ({ x: Number(m?.position?.[0] ?? NaN), y: Number(m?.position?.[1] ?? NaN) }))
      .filter((pt) => Number.isFinite(pt.x) && Number.isFinite(pt.y))
      .slice(0, 8)

    const massesKey = masses.map((mm) => `${roundKey(mm.x)}:${roundKey(mm.y)}:${roundKey(mm.m)}`).join('|')
    const sourcesKey = srcs.map((s: any) => `${String(s?.id ?? '')}:${roundKey(Number(s?.position?.[0] ?? NaN))}:${roundKey(Number(s?.position?.[1] ?? NaN))}`).join('|')
    const targetsKey = targets.map((t) => `${roundKey(t.x)}:${roundKey(t.y)}`).join('|')

    const MAX_PHOTON_PATHS = interacting ? 8 : 24
    const aimsPerSource = targets.length
      ? Math.max(1, Math.min(targets.length, Math.floor(MAX_PHOTON_PATHS / Math.max(1, srcs.length))))
      : 1
    const MAX_PHOTON_SEGMENTS_TOTAL = interacting ? 900 : 3200
    const totalPathsTarget = Math.max(1, srcs.length * aimsPerSource)
    const steps = clamp(Math.floor(MAX_PHOTON_SEGMENTS_TOTAL / totalPathsTarget), interacting ? 40 : 60, interacting ? 150 : 220)
    const forceNoColorShift = (srcs.length * aimsPerSource * steps) > 1200
    const useColorShift = Boolean(colorShiftOverlays && !forceNoColorShift)

    const overlayKey = [
      drawCurvature ? 'c1' : 'c0',
      drawPhotons ? 'p1' : 'p0',
      useColorShift ? 's1' : 's0',
      recalcOnZoom ? 'z1' : 'z0',
      `wh:${roundKey(halfW)}:${roundKey(halfH)}`,
      `grid:${gridLines}:${samples}`,
      `ph:${srcs.length}:${targets.length}:${aimsPerSource}:${steps}`,
      `m:${masses.length}:${massesKey}`,
      `src:${sourcesKey}`,
      `tgt:${targetsKey}`,
      `t:${recomputeToken}`,
      `d:${dropNonce}`,
    ].join('~')

    if (!panelVisible && cacheRef.current?.key === overlayKey) {
      return { key: cacheRef.current.key, world: cacheRef.current.world, strokeWidth, gridStroke, photonStroke, shiftColor, useColorShift }
    }

    const sharedWorld = getSharedWorld(overlayKey)
    if (sharedWorld) {
      cacheRef.current = { key: overlayKey, world: sharedWorld }
      return { key: overlayKey, world: sharedWorld, strokeWidth, gridStroke, photonStroke, shiftColor, useColorShift }
    }

    if (freezeDuringInteraction && cacheRef.current) {
      return { key: cacheRef.current.key, world: cacheRef.current.world, strokeWidth, gridStroke, photonStroke, shiftColor, useColorShift }
    }

    if (!allowRecompute && cacheRef.current) {
      return { key: cacheRef.current.key, world: cacheRef.current.world, strokeWidth, gridStroke, photonStroke, shiftColor, useColorShift }
    }

    if (!allowRecompute && !cacheRef.current) return null

    let world = (!recalcOnZoom && cacheRef.current?.key === overlayKey) ? cacheRef.current.world : null

    if (!world) {
      const gridLinesWorld: Array<Array<[number, number]>> = []
      if (drawCurvature) {
        for (let i = 0; i <= gridLines; i++) {
          if (overBudget()) {
            budgetAborted = true
            break
          }
          const t = i / gridLines
          const x0 = -halfW + t * (2 * halfW)
          const y0 = -halfH + t * (2 * halfH)

          const vertical: Array<[number, number]> = []
          for (let j = 0; j <= samples; j++) {
            if (overBudget()) {
              budgetAborted = true
              break
            }
            const s = j / samples
            const y = -halfH + s * (2 * halfH)
            const [gx, gy] = gradPhi(x0, y)
            const [wx, wy] = warpDisp(gx, gy)
            vertical.push([x0 + wx, y + wy])
          }
          gridLinesWorld.push(vertical)

          const horizontal: Array<[number, number]> = []
          for (let j = 0; j <= samples; j++) {
            if (overBudget()) {
              budgetAborted = true
              break
            }
            const s = j / samples
            const x = -halfW + s * (2 * halfW)
            const [gx, gy] = gradPhi(x, y0)
            const [wx, wy] = warpDisp(gx, gy)
            horizontal.push([x + wx, y0 + wy])
          }
          gridLinesWorld.push(horizontal)

          if (budgetAborted) break
        }
      }

      const photonWorld: PhotonWorld[] = []
      if (drawPhotons && !budgetAborted) {
        const rotate = (vx: number, vy: number, ang: number): [number, number] => {
          const c = Math.cos(ang)
          const s = Math.sin(ang)
          return [vx * c - vy * s, vx * s + vy * c]
        }

        const integrate = (sx0: number, sy0: number, vx0: number, vy0: number, nSteps: number, recordShift: boolean, phi0Ref: number) => {
          let x = sx0
          let y = sy0
          let vx = vx0
          let vy = vy0
          const ptsWorld: Array<[number, number]> = [[x, y]]
          const stepLen = (Math.min(halfW || 1, halfH || 1) * 2) / nSteps
          const bendK = 0.9 * warpK
          const shifts: number[] | undefined = (recordShift && useColorShift) ? [] : undefined

          for (let k = 0; k < nSteps; k++) {
            if (overBudget()) {
              budgetAborted = true
              break
            }
            const [gx, gy] = gradPhi(x, y)
            vx += bendK * gx
            vy += bendK * gy
            const v = Math.hypot(vx, vy) || 1
            vx /= v
            vy /= v

            const x2 = x + vx * stepLen
            const y2 = y + vy * stepLen

            if (useColorShift && shifts) {
              const am = (x + x2) * 0.5
              const bm = (y + y2) * 0.5
              const ph = phi(am, bm)
              const kShift = 2.4 * (warpK / (Math.min(halfW || 1, halfH || 1) || 1))
              shifts.push(clamp((ph - phi0Ref) * kShift, -1, 1))
            }

            x = x2
            y = y2
            if (Math.abs(x) > halfW * 1.1 || Math.abs(y) > halfH * 1.1) break
            ptsWorld.push([x, y])
          }

          return { ptsWorld, shifts }
        }

        for (const s of srcs) {
          if (overBudget()) {
            budgetAborted = true
            break
          }
          const sx0 = Number((s as any)?.position?.[0] ?? NaN)
          const sy0 = Number((s as any)?.position?.[1] ?? NaN)
          if (!Number.isFinite(sx0) || !Number.isFinite(sy0)) continue

          const aims = targets.length ? targets : [{ x: sx0 + (halfW || 1), y: sy0 }]
          const scoreSteps = interacting ? clamp(Math.floor(steps * 0.45), 28, 80) : clamp(Math.floor(steps * 0.6), 40, 120)
          const baseAngles = (() => {
            const pairs = Math.max(1, srcs.length * Math.max(1, targets.length))
            const n = interacting ? 5 : (pairs <= 16 ? 9 : pairs <= 32 ? 7 : 5)
            if (n === 9) return [-0.44, -0.28, -0.14, -0.06, 0, 0.06, 0.14, 0.28, 0.44]
            if (n === 7) return [-0.36, -0.18, -0.08, 0, 0.08, 0.18, 0.36]
            return [-0.22, -0.08, 0, 0.08, 0.22]
          })()

          const scored: Array<{ aim: { x: number; y: number }; bestAng: number; bestDist: number; second?: { ang: number; dist: number } }> = []
          for (const aim of aims) {
            if (overBudget()) {
              budgetAborted = true
              break
            }
            let vxBase = aim.x - sx0
            let vyBase = aim.y - sy0
            const d0 = Math.hypot(vxBase, vyBase) || 1
            vxBase /= d0
            vyBase /= d0

            let best = { ang: 0, dist: Number.POSITIVE_INFINITY }
            let second = { ang: 0, dist: Number.POSITIVE_INFINITY }

            for (const ang of baseAngles) {
              if (overBudget()) {
                budgetAborted = true
                break
              }
              const [vx0, vy0] = rotate(vxBase, vyBase, ang)
              const { ptsWorld } = integrate(sx0, sy0, vx0, vy0, scoreSteps, false, 0)
              let minD = Number.POSITIVE_INFINITY
              for (const point of ptsWorld) {
                const d = Math.hypot(point[0] - aim.x, point[1] - aim.y)
                if (d < minD) minD = d
              }
              if (minD < best.dist) {
                second = best
                best = { ang, dist: minD }
              } else if (minD < second.dist) {
                second = { ang, dist: minD }
              }
            }

            if (budgetAborted) break
            scored.push({
              aim,
              bestAng: best.ang,
              bestDist: best.dist,
              second: second.dist < Number.POSITIVE_INFINITY ? { ang: second.ang, dist: second.dist } : undefined,
            })
          }

          scored.sort((a, b) => a.bestDist - b.bestDist)
          const aimsPicked = scored.slice(0, aimsPerSource)
          const phi0 = phi(sx0, sy0)
          let localPathIdx = 0

          for (const entry of aimsPicked) {
            if (overBudget()) {
              budgetAborted = true
              break
            }
            let vx = entry.aim.x - sx0
            let vy = entry.aim.y - sy0
            const d0 = Math.hypot(vx, vy) || 1
            vx /= d0
            vy /= d0

            const [vx1, vy1] = rotate(vx, vy, entry.bestAng)
            const main = integrate(sx0, sy0, vx1, vy1, steps, true, phi0)
            if (main.ptsWorld.length >= 2) {
              photonWorld.push({ id: `ph:${String((s as any)?.id ?? 's')}:${localPathIdx++}`, pts: main.ptsWorld, shifts: main.shifts })
            }

            if (
              entry.second &&
              photonWorld.length < MAX_PHOTON_PATHS &&
              entry.second.dist < entry.bestDist * 1.35 &&
              Math.abs(entry.second.ang - entry.bestAng) > 0.12
            ) {
              const [vx2, vy2] = rotate(vx, vy, entry.second.ang)
              const alt = integrate(sx0, sy0, vx2, vy2, steps, true, phi0)
              if (alt.ptsWorld.length >= 2) {
                photonWorld.push({ id: `ph:${String((s as any)?.id ?? 's')}:${localPathIdx++}`, pts: alt.ptsWorld, shifts: alt.shifts })
              }
            }

            if (budgetAborted || photonWorld.length >= MAX_PHOTON_PATHS) break
          }

          if (budgetAborted || photonWorld.length >= MAX_PHOTON_PATHS) break
        }
      }

      world = { gridLines: gridLinesWorld, photons: photonWorld }
      lastComputeMsRef.current = Date.now()
      cacheRef.current = { key: overlayKey, world }
      setSharedWorld(overlayKey, world)

      if (Boolean((import.meta as any)?.env?.DEV)) {
        console.info('[moonstone] spacetime canvas', {
          ms: Math.round(nowMs() - startedMs),
          aborted: budgetAborted,
          interacting,
          masses: masses.length,
          photons: photonWorld.length,
          steps,
        })
      }
    }

    return { key: overlayKey, world, strokeWidth, gridStroke, photonStroke, shiftColor, useColorShift }
  }, [
    colorShiftOverlays,
    drawCurvature,
    drawPhotons,
    dropNonce,
    enabled,
    freezeDuringInteraction,
    interacting,
    masses,
    monitors,
    overlayStrokeWidth,
    recalcOnZoom,
    recomputeToken,
    safeCellSize,
    sources,
    updateMode,
    panelVisible,
  ])

  const legendText = `${String(displayUnits)} / ${displayMassUnits === 'Msun' ? 'M☉' : 'kg'} / ${displayVelocityUnits}`

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let frame = 0

    const draw = () => {
      if (!panelVisible) return

      const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1))
      const width = Math.max(1, canvasSize.width)
      const height = Math.max(1, canvasSize.height)
      if (canvas.width !== Math.floor(width * dpr) || canvas.height !== Math.floor(height * dpr)) {
        canvas.width = Math.floor(width * dpr)
        canvas.height = Math.floor(height * dpr)
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, width, height)
      ctx.fillStyle = 'rgba(2,6,23,1)'
      ctx.fillRect(0, 0, width, height)

      if (!enabled || !computed) {
        ctx.fillStyle = 'rgba(148,163,184,0.9)'
        ctx.font = '12px system-ui, -apple-system, Segoe UI, Roboto, sans-serif'
        ctx.fillText('Enable curvature or photon rendering to populate this viewport.', 12, 24)
        return
      }

      const [minX, minY, viewWidth, viewHeight] = parseViewBox(safeViewBox)
      const sceneToCanvas = (sx: number, sy: number): [number, number] => {
        const x = ((sx - minX) / (viewWidth || 1)) * width
        const y = ((sy - minY) / (viewHeight || 1)) * height
        return [x, y]
      }
      const worldToCanvas = (pt: [number, number]) => sceneToCanvas(toScene(pt[0]), toScene(pt[1]))

      ctx.lineCap = 'round'
      ctx.lineJoin = 'round'

      if (drawCurvature) {
        ctx.strokeStyle = computed.gridStroke
        ctx.lineWidth = Math.max(1, computed.strokeWidth)
        ctx.globalAlpha = 0.9
        for (const line of computed.world.gridLines) {
          if (line.length < 2) continue
          ctx.beginPath()
          const [x0, y0] = worldToCanvas(line[0])
          ctx.moveTo(x0, y0)
          for (let i = 1; i < line.length; i++) {
            const [x, y] = worldToCanvas(line[i])
            ctx.lineTo(x, y)
          }
          ctx.stroke()
        }
      }

      if (drawPhotons) {
        ctx.lineWidth = Math.max(1.1, computed.strokeWidth)
        ctx.globalAlpha = 0.55
        for (const tr of computed.world.photons) {
          if (tr.pts.length < 2) continue
          if (!tr.shifts || !computed.useColorShift) {
            ctx.strokeStyle = computed.photonStroke
            ctx.beginPath()
            const [x0, y0] = worldToCanvas(tr.pts[0])
            ctx.moveTo(x0, y0)
            for (let i = 1; i < tr.pts.length; i++) {
              const [x, y] = worldToCanvas(tr.pts[i])
              ctx.lineTo(x, y)
            }
            ctx.stroke()
            continue
          }

          for (let i = 0; i < tr.pts.length - 1; i++) {
            const [ax, ay] = worldToCanvas(tr.pts[i])
            const [bx, by] = worldToCanvas(tr.pts[i + 1])
            ctx.strokeStyle = computed.shiftColor(tr.shifts[i] ?? 0, 0.55)
            ctx.beginPath()
            ctx.moveTo(ax, ay)
            ctx.lineTo(bx, by)
            ctx.stroke()
          }
        }
      }

      ctx.globalAlpha = 1
      ctx.fillStyle = 'rgba(226,232,240,0.75)'
      ctx.font = '12px system-ui, -apple-system, Segoe UI, Roboto, sans-serif'
      ctx.fillText(`Units: ${legendText}`, 12, 20)
    }

    frame = window.requestAnimationFrame(draw)
    return () => window.cancelAnimationFrame(frame)
  }, [canvasSize.height, canvasSize.width, computed, drawCurvature, drawPhotons, enabled, legendText, panelVisible, safeViewBox, toScene])

  return (
    <div ref={hostRef} style={{ width: '100%', height: '100%', minHeight: 0 }}>
      <canvas
        ref={canvasRef}
        aria-label="Spacetime metric viewport"
        style={{ width: '100%', height: '100%', display: 'block', background: 'rgba(2,6,23,1)' }}
      />
    </div>
  )
}
