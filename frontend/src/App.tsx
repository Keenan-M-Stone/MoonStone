import React, { useMemo } from 'react'
import { BackendTransportProvider, StarDustApp, createFetchBackendTransport, loadDefaultScene } from './stardust'
import MoonStoneSpacetimePanel from './moonstone/MoonStoneSpacetimePanel'

import moonstoneDefaultBundle from './defaults/moonstone-default.bundle.json'

const MOONSTONE_DEFAULTS = loadDefaultScene(moonstoneDefaultBundle as Record<string, unknown>)

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
          materials: MOONSTONE_DEFAULTS.materials,
          cellSize: MOONSTONE_DEFAULTS.cellSize,
          geometry: MOONSTONE_DEFAULTS.geometry,
          sources: MOONSTONE_DEFAULTS.sources,
          monitors: MOONSTONE_DEFAULTS.monitors,
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
