import React from 'react'
import { AppFrame, ToolsPanel, CADCanvas, InspectorBase, RunPanelBase } from '@stardust/ui'
import UlfPanel from './UlfPanel'

export default function App(){
  // We render the MoonStone canvas using the existing UlfPanel (it mounts its own canvas)
  return (
    <AppFrame
      tools={<ToolsPanel>
        <div style={{display:'flex', flexDirection:'column', gap:8}}>
          <button>Insert Sphere</button>
          <button>Insert Box</button>
          <button>Quick Solve</button>
        </div>
      </ToolsPanel>}
      inspector={<InspectorBase obj={null} onChange={()=>{}} />}
      run={<RunPanelBase solvers={['interactive','reference','gpu','kerr_formal']} onQuick={(solver)=> console.log('quick solver selected', solver)} />}
      canvas={<CADCanvas onMount={(el)=>{
        // mount the existing Ulf three.js scene inside the CAD canvas element
        // UlfPanel already manages its own mount target; we'll render it here instead
        // For now we simply render the UlfPanel which will claim its own area
      }}><div style={{height:'100%'}}><UlfPanel /></div></CADCanvas>}
    />
  )
}
