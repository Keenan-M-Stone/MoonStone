import React, { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { fetchTrace, fetchMetricSample, exportTrace } from './api'

export default function UlfPanel(){
  const mountRef = useRef<HTMLDivElement | null>(null)
  const [source, setSource] = useState({x: -1e-6, y: 0.0, z: 0.0})
  const sceneRef = useRef<any>()

  // Scenes & objects (tabs)
  const [scenes, setScenes] = useState(() => [{ id: 'scene-1', name: 'Scene 1', solver: 'interactive', quickSolver: 'weak', objects: [] as any[] }])
  const [activeScene, setActiveScene] = useState(0)
  const [selectedObject, setSelectedObject] = useState<string | null>(null)

  function currentScene(){
    return scenes[activeScene]
  }

  function updateScene(update: Partial<any>){
    setScenes((prev)=>{
      const next = [...prev]
      next[activeScene] = { ...next[activeScene], ...update }
      return next
    })
  }

  function addObject(obj: any){
    setScenes((prev)=>{
      const next = [...prev]
      next[activeScene] = { ...next[activeScene], objects: [...next[activeScene].objects, obj] }
      return next
    })
  }

  function updateObject(id: string, patch: any){
    setScenes((prev)=>{
      const next = [...prev]
      next[activeScene] = { ...next[activeScene], objects: next[activeScene].objects.map((o:any)=> o.id === id ? {...o, ...patch} : o) }
      return next
    })
  }

  function removeObject(id: string){
    setScenes((prev)=>{
      const next = [...prev]
      next[activeScene] = { ...next[activeScene], objects: next[activeScene].objects.filter((o:any)=> o.id !== id) }
      return next
    })
    if(selectedObject === id) setSelectedObject(null)
  }


  useEffect(()=>{
    const w = mountRef.current!
    const width = w.clientWidth
    const height = w.clientHeight

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(45, width/height, 1e-9, 1)
    camera.position.set(0.000001, 0.000001, 0.000002)
    camera.lookAt(0,0,0)

    const renderer = new THREE.WebGLRenderer({antialias:true})
    renderer.setSize(width, height)
    w.appendChild(renderer.domElement)

    const light = new THREE.DirectionalLight(0xffffff, 1)
    light.position.set(1,1,1)
    scene.add(light)

    const srcGeom = new THREE.SphereGeometry(5e-8, 16, 12)
    const srcMat = new THREE.MeshStandardMaterial({color: 0xffee66})
    const srcMesh = new THREE.Mesh(srcGeom, srcMat)
    srcMesh.position.set(source.x, source.y, source.z)
    scene.add(srcMesh)

    // scene object meshes map (id -> mesh)
    const objMeshes: Record<string, THREE.Mesh> = {}

    function syncObjects(){
      const objs = currentScene().objects
      // add/update objects
      for(const o of objs){
        let m = objMeshes[o.id]
        if(!m){
          const g = new THREE.SphereGeometry(o.size || 1e-7, 16, 12)
          const mat = new THREE.MeshStandardMaterial({color: o.color || 0x66ccff})
          m = new THREE.Mesh(g, mat)
          objMeshes[o.id] = m
          scene.add(m)
        }
        m.position.set(o.pos[0] || 0, o.pos[1] || 0, o.pos[2] || 0)
        // scale by size
        const s = o.size || 1e-7
        m.scale.set(s, s, s)
      }
      // remove meshes not in list
      for(const id of Object.keys(objMeshes)){
        if(!objs.find((x:any)=>x.id === id)){
          scene.remove(objMeshes[id])
          delete objMeshes[id]
        }
      }
    }

    // call syncObjects periodically (or on scene change via effect below)
    syncObjects()

    const rayMaterial = new THREE.LineBasicMaterial({color: 0xff0000})
    let rayLine: THREE.Line | null = null

    function setRayPoints(pts: THREE.Vector3[]){
      const geom = new THREE.BufferGeometry().setFromPoints(pts)
      if(rayLine) scene.remove(rayLine)
      rayLine = new THREE.Line(geom, rayMaterial)
      scene.add(rayLine)
    }

    async function updateTrace(params: any = {npoints: 256, step: 1e-6}){
      try{
        setLoading(true)
        setCached(false)
        const sceneSolver = currentScene().solver
        const effectiveParams = { ...params }
        // Device preference from solver or scene quickSettings
        const quick = currentScene().quickSolver || 'weak'
        const qsettings = currentScene().quickSettings || {}
        if(sceneSolver === 'gpu' || qsettings.device === 'gpu') effectiveParams.device = 'gpu'
        // method selection
        if(quick === 'rk4_adaptive') effectiveParams.method = 'rk4_adaptive'
        else if(quick === 'rk4') effectiveParams.method = 'rk4'
        else if(quick === 'null' && qsettings.engine === 'formal') effectiveParams.method = 'null_formal'
        else if(quick === 'null') effectiveParams.method = 'null'
        else if(quick === 'kerr_formal'){
          effectiveParams.method = 'kerr_formal'
          if(qsettings.spin) effectiveParams.spin = qsettings.spin
          if(typeof qsettings.use_numba !== 'undefined') effectiveParams.use_numba = qsettings.use_numba
          if(typeof qsettings.analytic_device !== 'undefined'){
            effectiveParams.analytic = qsettings.analytic_device
          }else if(qsettings.device === 'gpu' && qsettings.engine === 'formal'){
            // default to analytic on GPU when using formal engine
            effectiveParams.analytic = true
          }
        }
        // send the trace request
        const resp = await fetchTrace({
          source: {x: source.x, y: source.y, z: source.z},
          directions: [{x:1,y:0,z:0}],
          metric: metric,
          params: effectiveParams
        })
        const pts = resp.points.map((p:any)=> new THREE.Vector3(p.x, p.y, p.z))
        setRayPoints(pts)
        // backend provides meta.cached
        if(resp.meta && resp.meta.cached) setCached(true)
        // capture backend meta (e.g. device_analytic)
        setLastTraceMeta(resp.meta || null)
      }catch(e){
        console.error('trace error', e)
      }finally{
        setLoading(false)
      }
    }

    updateTrace()

    function animate(){
      requestAnimationFrame(animate)
      renderer.render(scene, camera)
    }
    animate()

    sceneRef.current = {scene, camera, renderer, srcMesh, updateTrace, syncObjects, setRayPoints}

    const onResize = ()=>{
      const width = w.clientWidth
      const height = w.clientHeight
      renderer.setSize(width, height)
      camera.aspect = width/height
      camera.updateProjectionMatrix()
    }
    window.addEventListener('resize', onResize)

    return ()=>{
      window.removeEventListener('resize', onResize)
      w.removeChild(renderer.domElement)
    }
  }, [])

  useEffect(()=>{
    // update source mesh and request new trace (debounced)
    const s = sceneRef.current
    if(!s) return
    s.srcMesh.position.set(source.x, source.y, source.z)
    s.syncObjects()
    const id = setTimeout(()=> s.updateTrace(), 80)
    return ()=> clearTimeout(id)
  }, [source, scenes, activeScene])

  // Metric UI and observer
  const [metric, setMetric] = useState({type: 'schwarzschild', mass: 1.0})
  const [observer, setObserver] = useState({x: 1e-6, y: 0.0, z: 0.0})
  const [tensor, setTensor] = useState<any | null>(null)

  // Interactive state
  const [loading, setLoading] = useState(false)
  const [cached, setCached] = useState(false)
  const [fastMode, setFastMode] = useState(true)
  const [gpuAvailable, setGpuAvailable] = useState(false)
  const [streaming, setStreaming] = useState(false)
  const [streamProgress, setStreamProgress] = useState(0)
  const wsRef = useRef<any>(null)
  const [benchResult, setBenchResult] = useState<any | null>(null)
  const [showQuickEditor, setShowQuickEditor] = useState(false)
  const [quickEditorState, setQuickEditorState] = useState<any>({ engine: 'approx', device: 'cpu', spin: [0.0, 0.0, 0.0], use_numba: true, analytic_device: true })
  const [showBenchDashboard, setShowBenchDashboard] = useState(false)  
  const [benchHistory, setBenchHistory] = useState<any | null>(null)
  // meta from last trace (e.g., device_analytic)
  const [lastTraceMeta, setLastTraceMeta] = useState<any | null>(null)
        const r = await fetch((process.env.VITE_API_BASE || 'http://localhost:8000') + '/moon/gpu')
        const j = await r.json()
        setGpuAvailable(Boolean(j.cuda))
      }catch(e){
        setGpuAvailable(false)
      }
    })()
  }, [])

  function stopStream(){
    if(wsRef.current){
      try{ wsRef.current.close() }catch(e){}
      wsRef.current = null
    }
    setStreaming(false)
  }

  async function runBench(){
    try{
      const solverName = currentScene().quickSolver || 'weak'
      const r = await fetch((process.env.VITE_API_BASE || 'http://localhost:8000') + '/moon/bench', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ solver: solverName, params: { npoints: 256, ntest: 3 }}) })
      const j = await r.json()
      setBenchResult(j)
    }catch(e){ console.error('bench error', e); setBenchResult(null) }
  }

  function startStream(params: any = {npoints: 256, step: 1e-6}){
    const sceneSolver = currentScene().solver
    const effectiveParams = { ...params }
    if(sceneSolver === 'gpu') effectiveParams.device = 'gpu'
    setStreamProgress(0)
    const host = (process.env.VITE_API_BASE || 'http://localhost:8000').replace(/^http/, 'ws')
    const ws = new WebSocket(host + '/moon/trace/ws')
    wsRef.current = ws
    ws.onopen = ()=>{
      setStreaming(true)
      // include quick solver selection in streaming requests
      const quick = currentScene().quickSolver || 'weak'
      const qsettings = currentScene().quickSettings || {}
      if(qsettings.device === 'gpu') effectiveParams.device = 'gpu'
      if(quick === 'rk4_adaptive') effectiveParams.method = 'rk4_adaptive'
      else if(quick === 'rk4') effectiveParams.method = 'rk4'
      else if(quick === 'null' && qsettings.engine === 'formal') effectiveParams.method = 'null_formal'
      else if(quick === 'null') effectiveParams.method = 'null'
      else if(quick === 'kerr_formal'){
        effectiveParams.method = 'kerr_formal'
        if(qsettings.spin) effectiveParams.spin = qsettings.spin
        if(typeof qsettings.use_numba !== 'undefined') effectiveParams.use_numba = qsettings.use_numba
        if(typeof qsettings.analytic_device !== 'undefined'){
          effectiveParams.analytic = qsettings.analytic_device
        }else if(qsettings.device === 'gpu' && qsettings.engine === 'formal'){
          effectiveParams.analytic = true
        }
      }
      ws.send(JSON.stringify({ source: {x: source.x, y: source.y, z: source.z}, directions: [{x:1,y:0,z:0}], metric: metric, params: effectiveParams }))
    }
    ws.onmessage = (ev: any)=>{
      try{
        const msg = JSON.parse(ev.data)
        if(msg.type === 'partial'){
          const pts = msg.points.map((p:any)=> new (THREE as any).Vector3(p[0], p[1], p[2]))
          const s = sceneRef.current
          if(s && s.setRayPoints) s.setRayPoints(pts)
          setStreamProgress((p)=>p+1)
          // capture streaming meta (e.g., analytic flag)
          if(msg.meta) setLastTraceMeta(msg.meta)
        }else if(msg.type === 'done'){
          // if server sent meta in done, capture it as well
          if(msg.meta) setLastTraceMeta(msg.meta)
          setStreaming(false)
          try{ ws.close() }catch(e){}
          wsRef.current = null
        }
      }catch(e){ console.error('ws msg', e) }
    }
    ws.onerror = (e: any)=>{ console.error('ws error', e); stopStream() }
    ws.onclose = ()=>{ stopStream() }
  }

  async function sampleAtObserver(){
    try{
      const resp = await fetchMetricSample(observer, metric)
      setTensor(resp)
    }catch(e){
      console.error('metric sample error', e)
    }
  }

  async function refineTrace(){
    const s = sceneRef.current
    if(!s) return
    // request higher resolution trace
    const params = { npoints: 2048, step: 1e-7 }
    s.updateTrace(params)
  }

  async function handleExport(){
    // export the last trace (best-effort: take first trace id from server by asking backend export)
    try{
      // For POC, we'll call export with the last cached id if any stored in meta
      // Backend /moon/export expects a JSON body with trace_id
      // If there's a cached trace (from last query) we can pick it up from scene meta (not stored in this POC)
      alert('Export will be implemented in next iteration. For now use backend /moon/export endpoint directly.')
    }catch(e){
      console.error('export error', e)
    }
  }

  return (
    <div style={{display:'flex', height:'100%'}}>
      <div style={{display:'flex', flexDirection:'column', width:'100%'}}>
        <div style={{padding:8, display:'flex', gap:8}}>
          {scenes.map((s, idx)=> (
            <button key={s.id} style={{padding:6, background: idx===activeScene ? '#0b74da' : '#eee', color: idx===activeScene ? 'white' : 'black'}} onClick={()=>setActiveScene(idx)}>{s.name}</button>
          ))}
          <button onClick={()=>{ setScenes(prev=>[...prev, { id: `scene-${Date.now()}`, name: `Scene ${prev.length+1}`, solver: 'interactive', objects: [] }]); setActiveScene(scenes.length) }}>+ Scene</button>
        </div>
        <div ref={mountRef} style={{flex:1}} />
      </div>
      <aside style={{width: 320, padding: 12, borderLeft: '1px solid #ddd'}}>
        <h3>Source</h3>
        <label>X <input type="number" value={source.x} step={1e-7} onChange={(e)=>setSource({...source, x: parseFloat(e.target.value)})} /></label>
        <label>Y <input type="number" value={source.y} step={1e-7} onChange={(e)=>setSource({...source, y: parseFloat(e.target.value)})} /></label>
        <label>Z <input type="number" value={source.z} step={1e-7} onChange={(e)=>setSource({...source, z: parseFloat(e.target.value)})} /></label>

        <hr/>
        <h4>Metric</h4>
        <label>Type
          <select value={metric.type} onChange={(e)=>setMetric({...metric, type: e.target.value})}>
            <option value="flat">Flat</option>
            <option value="schwarzschild">Schwarzschild</option>
          </select>
        </label>
        {metric.type === 'schwarzschild' && (
          <label>Mass <input type="number" value={metric.mass} step={0.1} onChange={(e)=>setMetric({...metric, mass: parseFloat(e.target.value)})} /></label>
        )}

        <hr/>
        <h4>Observer</h4>
        <label>X <input type="number" value={observer.x} step={1e-7} onChange={(e)=>setObserver({...observer, x: parseFloat(e.target.value)})} /></label>
        <label>Y <input type="number" value={observer.y} step={1e-7} onChange={(e)=>setObserver({...observer, y: parseFloat(e.target.value)})} /></label>
        <label>Z <input type="number" value={observer.z} step={1e-7} onChange={(e)=>setObserver({...observer, z: parseFloat(e.target.value)})} /></label>
        <div style={{marginTop:8}}>
          <button onClick={sampleAtObserver}>Sample Tensor</button>
        </div>

        <hr/>
        <div style={{marginTop:8}}>
          <label>Scene Solver
            <select value={currentScene().solver} onChange={(e)=> updateScene({solver: e.target.value})}>
              <option value="interactive">Interactive</option>
              <option value="reference">Reference</option>
              <option value="gpu" disabled={!gpuAvailable}>GPU {gpuAvailable ? '' : '(not available)'}</option>
            </select>
          </label>
          <label style={{display:'block', marginTop:8}}>Quick Solver
            <select value={currentScene().quickSolver} onChange={(e)=> updateScene({quickSolver: e.target.value})}>
              <option value="weak">Weak (fast)</option>
              <option value="rk4_adaptive">RK4 (adaptive)</option>
              <option value="null">Full null (POC)</option>
              <option value="null_formal">Full null (formal)</option>
              <option value="kerr_formal">Kerr (Lense-Thirring)</option>
            </select>
          </label>

          <div style={{marginTop:6}}>
            <button onClick={()=>{
              const s = sceneRef.current
              if(!s) return
              const params = currentScene().solver === 'interactive' ? {npoints:256, step:1e-6} : {npoints:1024, step:5e-7}
              s.updateTrace(params)
            }} disabled={loading || streaming}>{loading ? 'Working...' : (streaming ? 'Streaming...' : 'Update Trace')}</button>
            <button style={{marginLeft:8}} onClick={refineTrace} disabled={loading || streaming}>Refine Trace</button>
            <button style={{marginLeft:8}} onClick={handleExport}>Export</button>
          </div>
          {lastTraceMeta && (typeof lastTraceMeta.device_analytic_requested !== 'undefined' || typeof lastTraceMeta.device_analytic_executed !== 'undefined' || typeof lastTraceMeta.analytic !== 'undefined') && (
            <div style={{marginTop:8, fontSize:12}}>
              Device analytic kernel: requested <strong>{ (lastTraceMeta.device_analytic_requested || lastTraceMeta.analytic) ? 'Yes' : 'No' }</strong>
              &nbsp;|&nbsp; executed <strong>{ (typeof lastTraceMeta.device_analytic_executed !== 'undefined' ? (lastTraceMeta.device_analytic_executed ? 'Yes' : 'No') : (lastTraceMeta.device_analytic || lastTraceMeta.analytic ? 'Yes' : 'No')) }</strong>
            </div>
          )
              })
              setShowQuickEditor(true)
            }}>Quick Solve Editor</button> 
            {showQuickEditor && (
              <div style={{padding:8, border:'1px solid #eee', marginTop:8}}>
                <label>Engine
                  <select value={quickEditorState.engine} onChange={(e)=> setQuickEditorState({...quickEditorState, engine: e.target.value})}>
                    <option value="approx">Approx</option>
                    <option value="formal">Formal (Christoffel)</option>
                  </select>
                </label>
                <label style={{marginLeft:8}}>Device
                  <select value={quickEditorState.device} onChange={(e)=> setQuickEditorState({...quickEditorState, device: e.target.value})}>
                    <option value="cpu">CPU</option>
                    <option value="gpu" disabled={!gpuAvailable}>GPU {gpuAvailable ? '' : '(not available)'}</option>
                  </select>
                </label>
                <div style={{marginTop:6}}>
                  <label style={{display:'inline-block', width:40}}>Spin</label>
                  <label>X <input type="number" step={0.01} value={quickEditorState.spin[0]} onChange={(e)=> setQuickEditorState({...quickEditorState, spin: [parseFloat(e.target.value), quickEditorState.spin[1], quickEditorState.spin[2]]})} /></label>
                  <label style={{marginLeft:6}}>Y <input type="number" step={0.01} value={quickEditorState.spin[1]} onChange={(e)=> setQuickEditorState({...quickEditorState, spin: [quickEditorState.spin[0], parseFloat(e.target.value), quickEditorState.spin[2]]})} /></label>
                  <label style={{marginLeft:6}}>Z <input type="number" step={0.01} value={quickEditorState.spin[2]} onChange={(e)=> setQuickEditorState({...quickEditorState, spin: [quickEditorState.spin[0], quickEditorState.spin[1], parseFloat(e.target.value)]})} /></label>
                </div>
                <div style={{marginTop:6}}>
                  <label style={{display:'inline-block'}}><input type="checkbox" checked={quickEditorState.use_numba} onChange={(e)=> setQuickEditorState({...quickEditorState, use_numba: e.target.checked})} /> Use Numba (CPU JIT)</label>
                  <label style={{marginLeft:8}}><input type="checkbox" checked={quickEditorState.analytic_device} onChange={(e)=> setQuickEditorState({...quickEditorState, analytic_device: e.target.checked})} /> Use analytic device kernel (GPU)</label>
                </div> 
                <div style={{marginTop:8}}>
                  <button onClick={()=>{ updateScene({ quickSettings: quickEditorState }); setShowQuickEditor(false) }}>Save</button>
                  <button style={{marginLeft:8}} onClick={()=> setShowQuickEditor(false)}>Cancel</button>
                </div>
              </div>
            )}
          </div>

          <div style={{marginTop:8}}>
            <label style={{fontSize:12}}>Stream results <input type="checkbox" checked={streaming} onChange={(e)=>{ if(e.target.checked) startStream({npoints:256, step:1e-6}); else stopStream() }} /></label>
            <button style={{marginLeft:8}} onClick={()=>{ if(!streaming) startStream({npoints:currentScene().solver==='interactive'?256:1024, step: currentScene().solver==='interactive'?1e-6:5e-7}); else stopStream() }}>{streaming ? 'Stop Stream' : 'Start Stream'}</button>
            <span style={{marginLeft:8, fontSize:12}}>Chunks: {streamProgress}</span>
            <div style={{marginTop:8}}>
              <button onClick={runBench}>Run benchmark for quick solver</button>
              <button style={{marginLeft:8}} onClick={async ()=>{
                try{
                  const r = await fetch((process.env.VITE_API_BASE || 'http://localhost:8000') + '/moon/bench/history')
                  const j = await r.json()
                  setBenchHistory(j)
                  setShowBenchDashboard(true)
                }catch(e){ console.error('bench history', e) }
              }}>Bench Dashboard</button>

              {benchResult && (
                <div style={{marginTop:6, fontSize:12}}>
                  Mean: {benchResult.mean_sec.toExponential(2)}s per ray • est 1000 rays: {benchResult.estimate.per_1000_rays.toFixed(2)}s
                </div>
              )}
            </div>
          </div>          </div>
          <div style={{marginTop:6, fontSize:12}}>
            <strong>Status:</strong> {loading ? 'computing...' : (cached ? 'cached' : 'fresh')}
          </div>
          <div style={{marginTop:8}}>
            <button onClick={async ()=>{
              const sceneObj = currentScene()
              // package minimal scene
              const payload = { id: sceneObj.id, name: sceneObj.name, solver: sceneObj.solver, quickSolver: sceneObj.quickSolver, objects: sceneObj.objects }
              try{
                const res = await (await import('./api')).saveScene(payload)
                alert('Scene saved: ' + res.id)
              }catch(e){ console.error('save scene', e) }
            }}>Save Scene</button>
            <button style={{marginLeft:8}} onClick={async ()=>{
              try{
                const { scenes } = await (await import('./api')).listScenes()
                const pick = prompt('Available scenes:\n' + scenes.join('\n') + '\nEnter id to load:')
                if(!pick) return
                const data = await (await import('./api')).loadScene(pick)
                // apply scene
                setScenes(prev=>[...prev, data])
                setActiveScene(scenes.length)
              }catch(e){ console.error('load scene', e) }
            }}>Load Scene</button>
          </div>
        </div>

        <hr/>
        <h4>Objects</h4>
        <div style={{display:'flex', gap:8, marginBottom:8}}>
          <button onClick={()=> addObject({ id: `o-${Date.now()}`, type: 'pointmass', pos: [0,0,0], mass: 1.0, size: 1e-7, color: 0x66ccff, momentum: [0,0,0], spin: 0, name: 'Point Mass' })}>Add PointMass</button>
          <button onClick={()=> addObject({ id: `o-${Date.now()}`, type: 'sphere', pos: [0,0,0], mass: 0.0, size: 5e-7, color: 0xffcc66, name: 'Sphere' })}>Add Sphere</button>
        </div>
        <div>
          {currentScene().objects.map((o:any)=> (
            <div key={o.id} style={{padding:6, border: selectedObject===o.id ? '1px solid #0b74da' : '1px solid #eee', marginBottom:6}} onClick={()=>setSelectedObject(o.id)}>
              <strong>{o.name || o.id}</strong> <small>({o.type})</small>
              <div style={{fontSize:12}}>pos: {o.pos.map((v:number)=>v.toExponential(2)).join(', ')}, mass: {o.mass}</div>
            </div>
          ))}
        </div>

        {selectedObject && (()=>{
          const o = currentScene().objects.find((x:any)=>x.id === selectedObject)
          if(!o) return null
          return (
            <div style={{marginTop:12}}>
              <h4>Inspector</h4>
              <label>Name <input value={o.name} onChange={(e)=> updateObject(o.id, {name: e.target.value})} /></label>
              <label>Mass <input type="number" value={o.mass} step={0.1} onChange={(e)=> updateObject(o.id, {mass: parseFloat(e.target.value)})} /></label>
              <label>Size <input type="number" value={o.size} step={1e-8} onChange={(e)=> updateObject(o.id, {size: parseFloat(e.target.value)})} /></label>
              <label>Pos X <input type="number" value={o.pos[0]} step={1e-7} onChange={(e)=> updateObject(o.id, {pos: [parseFloat(e.target.value), o.pos[1], o.pos[2]]})} /></label>
              <label>Pos Y <input type="number" value={o.pos[1]} step={1e-7} onChange={(e)=> updateObject(o.id, {pos: [o.pos[0], parseFloat(e.target.value), o.pos[2]]})} /></label>
              <label>Pos Z <input type="number" value={o.pos[2]} step={1e-7} onChange={(e)=> updateObject(o.id, {pos: [o.pos[0], o.pos[1], parseFloat(e.target.value)]})} /></label>
              <label>Momentum X <input type="number" value={o.momentum ? o.momentum[0] : 0} step={0.1} onChange={(e)=> updateObject(o.id, {momentum: [parseFloat(e.target.value), (o.momentum ? o.momentum[1] : 0), (o.momentum ? o.momentum[2] : 0)]})} /></label>
              <label>Spin <input type="number" value={o.spin || 0} step={0.1} onChange={(e)=> updateObject(o.id, {spin: parseFloat(e.target.value)})} /></label>
              <label>Density gradient (radial magnitude) <input type="number" value={o.densityGradient || 0} step={0.01} onChange={(e)=> updateObject(o.id, {densityGradient: parseFloat(e.target.value)})} /></label>
              <div style={{marginTop:6}}><button onClick={()=> removeObject(o.id)}>Remove</button></div>
            </div>
          )
        })()}

        {tensor && (
          <div style={{marginTop:12, fontSize:12}}>
            <h5>Constitutive (eps)</h5>
            <pre style={{whiteSpace:'pre-wrap', fontSize:11}}>{JSON.stringify(tensor.eps, null, 2)}</pre>
            <h5>mu</h5>
            <pre style={{whiteSpace:'pre-wrap', fontSize:11}}>{JSON.stringify(tensor.mu, null, 2)}</pre>
            <h5>xi</h5>
            <pre style={{whiteSpace:'pre-wrap', fontSize:11}}>{JSON.stringify(tensor.xi, null, 2)}</pre>
          </div>
        )}

        {showBenchDashboard && benchHistory && (
          <div style={{position:'absolute', right:360, top:40, width:420, padding:12, background:'white', border:'1px solid #ddd', boxShadow:'0 4px 12px rgba(0,0,0,0.08)'}}>
            <h4>Bench Dashboard</h4>
            <div style={{maxHeight:300, overflowY:'auto'}}>
              {Object.keys(benchHistory.by_solver || {}).map((solver)=>{
                const items = benchHistory.by_solver[solver]
                const mean = items.mean_per_ray || items.mean_sec || 0
                return (
                  <div key={solver} style={{marginBottom:8}}>
                    <div style={{display:'flex', justifyContent:'space-between'}}><strong>{solver}</strong><span style={{fontSize:12}}>{mean.toExponential(2)} s/ray</span></div>
                    <div style={{height:8, background:'#eee', marginTop:6}}><div style={{width: Math.min(100, mean*1000) + '%', height:'100%', background:'#0b74da'}} /></div>
                  </div>
                )
              })}
            </div>
            <div style={{marginTop:8}}>
              <button onClick={()=> setShowBenchDashboard(false)}>Close</button>
            </div>
          </div>
        )}

      </aside>
    </div>
  )
}
