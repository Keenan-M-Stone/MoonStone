import React, { useState } from 'react'
import axios from 'axios'

import { API_BASE } from './api'

export default function RunPanel(){
  const [solver, setSolver] = useState('interactive')
  const [solverMethod, setSolverMethod] = useState('weak')
  const [nDirs, setNDirs] = useState(128)
  const [runningId, setRunningId] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [log, setLog] = useState<string[]>([])

  const [benching, setBenching] = useState(false)
  const [benchData, setBenchData] = useState<any|null>(null)

  async function runBenchPanel(){
    setBenching(true)
    try{
      const solvers = ['weak','rk4','rk4_adaptive','null','null_formal']
      const r = await axios.post(`${API_BASE}/moon/bench`, { solvers: solvers, params: { npoints: 256, ntest: 3 } })
      setBenchData(r.data)
      // persist bench results to the server-side store for future predictions
      try{
        if(r.data && r.data.results){
          // push each solver summary
          for(const [name, info] of Object.entries(r.data.results)){
            await axios.post(`${API_BASE}/moon/bench/save`, { solver: name, mean_sec: (info as any).mean_sec, per_1000_rays: (info as any).per_1000_rays, npoints: r.data.npoints, ntest: r.data.ntest })
          }
        }
      }catch(e){ console.error('bench save error', e) }
    }catch(e){ console.error('bench error', e); setBenchData(null) }
  }

  async function submit(){
    const body = { solver: solver, solver_method: solverMethod, n_dirs: nDirs, source: {x: -1e-6, y: 0, z:0}, metric: {type:'schwarzschild', mass: 1.0} }
    const r = await axios.post(`${API_BASE}/moon/run`, body)
    setRunningId(r.data.run_id)
    setStatus('queued')
    pollStatus(r.data.run_id)
  }

  async function pollStatus(id: string){
    const check = async ()=>{
      const r = await axios.get(`${API_BASE}/moon/run/${id}/log`)
      setLog(r.data.log || [])
      setStatus(r.data.status)
      if(r.data.status && r.data.status !== 'finished' && r.data.status !== 'failed'){
        setTimeout(check, 1000)
      }
    }
    check()
  }

  return (
    <div style={{padding: 12, borderLeft: '1px solid #ddd'}}>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <label>
          Run mode
          <select value={solver} onChange={(e) => setSolver(e.target.value)} style={{ marginLeft: 6 }}>
            <option value="interactive">Interactive (quick)</option>
            <option value="batch">Backend (batch)</option>
          </select>
        </label>

        <label>
          Rays (max 4096)
          <input
            type="number"
            min={1}
            max={4096}
            step={1}
            value={nDirs}
            onChange={(e) => {
              const v = e.currentTarget.valueAsNumber
              const vNorm = Number.isFinite(v) ? Math.max(1, Math.min(4096, Math.floor(v))) : nDirs
              setNDirs(vNorm)
            }}
            style={{ width: 110, marginLeft: 6 }}
          />
        </label>

        <button onClick={submit}>Submit</button>
      </div>

      <div style={{marginTop:8}}>
        <label>Solver method
          <select value={solverMethod} onChange={(e)=>setSolverMethod(e.target.value)}>
            <option value="weak">Weak (fast)</option>
            <option value="rk4">RK4 (fixed)</option>
            <option value="rk4_adaptive">RK4 adaptive (accurate)</option>
            <option value="null">Null (POC)</option>
            <option value="null_formal">Null (formal)</option>
          </select>
        </label>
        <div style={{marginTop:8}}>
          <button onClick={runBenchPanel} disabled={benching}>{benching ? 'Benchmarking...' : 'Run Benchmark'}</button>
          {benchData && (
            <div style={{marginTop:8}}>
              <strong>Benchmark (mean sec)</strong>
              <div style={{display:'flex', gap:8, marginTop:6}}>
                {Object.entries(benchData.results).map(([name, info]: any)=> (
                  <div key={name} style={{textAlign:'center'}}>
                    <div style={{height: 24, width: Math.max(8, (info.mean_sec / 0.005) * 80), background: '#0b74da'}}></div>
                    <div style={{fontSize:11}}>{name}</div>
                    <div style={{fontSize:11}}>{info.mean_sec.toExponential(2)}s</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
      <div style={{marginTop:8}}>
        {benchData && benchData.results && benchData.results[solverMethod] && (
          <div><strong>Predicted runtime (local bench):</strong> {(benchData.results[solverMethod].mean_sec * nDirs).toFixed(2)} s ({nDirs} rays)</div>
        )}
        <div style={{marginTop:6}}>
          <button onClick={async ()=>{
            try{
              const r = await axios.get(`${API_BASE}/moon/bench/history`)
              if(r.data && r.data.results && r.data.results[solverMethod]){
                const per = r.data.results[solverMethod].mean_per_ray
                alert(`History-based prediction: ${ (per * nDirs).toFixed(2) } s for ${nDirs} rays`)
              }else{ alert('No history data for this solver') }
            }catch(e){ console.error('history err', e); alert('Error fetching history') }
          }}>Predict from history</button>
        </div>
      </div>

      {runningId && (
        <div style={{marginTop:8}}>
          <strong>Run:</strong> {runningId}
          <div><strong>Status:</strong> {status}</div>
          <pre style={{whiteSpace:'pre-wrap'}}>{log.join('\n')}</pre>
        </div>
      )}
    </div>
  )
}
