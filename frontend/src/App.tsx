import React from 'react'
import UlfPanel from './UlfPanel'
import RunPanel from './RunPanel'

export default function App(){
  return (
    <div style={{height: '100vh', display: 'flex', flexDirection: 'column'}}>
      <header style={{padding: 12, background: '#0f172a', color: 'white'}}>
        <h1>MoonStone — Ulf (POC)</h1>
      </header>
      <main style={{flex: 1, display: 'flex'}}>
        <div style={{flex: 1}}>
          <UlfPanel />
        </div>
        <aside style={{width: 360, borderLeft: '1px solid #ddd'}}>
          <RunPanel />
        </aside>
      </main>
    </div>
  )
}
