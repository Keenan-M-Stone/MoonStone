import React, { useMemo } from 'react'
import { BackendTransportProvider, StarDustApp, createFetchBackendTransport } from './stardust'
import MoonStoneSpacetimePanel from './moonstone/MoonStoneSpacetimePanel'

const SOLAR_MASS_KG = 1.98847e30
const LY_M = 9.4607304725808e15
const MLY_M = LY_M * 1e6

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

export default function App() {
  const transport = useMemo(() => {
    const apiBase = (import.meta as any).env?.VITE_API_BASE as string | undefined
    const base = (apiBase ?? 'http://localhost:8000').replace(/\/+$/, '')
    return createFetchBackendTransport({ basePath: `${base}/moon` })
  }, [])

  return (
    <BackendTransportProvider transport={transport}>
      <StarDustApp
        branding={{
          title: 'MoonStone',
          subtitle: 'StarDust CAD + synced spacetime canvas',
        }}
        initial={{
          materials: MOONSTONE_DEFAULT_MATERIALS,
          cellSize: MOONSTONE_DEFAULT_SCENE.cellSize,
          geometry: MOONSTONE_DEFAULT_SCENE.geometry,
          sources: MOONSTONE_DEFAULT_SCENE.sources,
          monitors: MOONSTONE_DEFAULT_SCENE.monitors,
        }}
        initialDisplayUnits="MLY"
        storageNamespace="moonstone-v3"
        autoFrameOnInit={true}
        cad2d={{
          disableWheelZoom: false,
          alwaysShowZoomHud: true,
        }}
        extensions={{
          renderCadSectionPanel: (ctx) => <MoonStoneSpacetimePanel {...ctx} />,
        }}
      />
    </BackendTransportProvider>
  )
}
