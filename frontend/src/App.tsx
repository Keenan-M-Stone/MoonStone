import React from 'react'
import UlfPanel from './UlfPanel'

export default function App(){
  return (
    <div style={{height: '100vh', display: 'flex', flexDirection: 'column'}}>
      <header style={{padding: 12, background: '#0f172a', color: 'white'}}>
        <h1>MoonStone — Ulf (POC)</h1>
      </header>
      <main style={{flex: 1}}>
        <UlfPanel />
      </main>
    </div>
  )
}
