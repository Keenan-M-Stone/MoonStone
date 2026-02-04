import React, { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls'
import { TransformControls } from 'three/examples/jsm/controls/TransformControls'
import { fetchTrace, fetchMetricSample, exportTrace } from './api' 

export default function UlfPanel(){
  const mountRef = useRef<HTMLDivElement | null>(null)
  const [source, setSource] = useState({x: -1e-6, y: 0.0, z: 0.0})
  const sceneRef = useRef<any>()
  const gridRef = useRef<any>(null)

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
    const cameraPersp = new THREE.PerspectiveCamera(45, width/height, 1e-9, 1)
    cameraPersp.position.set(0.000001, 0.000001, 0.000002)
    cameraPersp.lookAt(0,0,0)
    // orthographic alternative for CAD views
    const aspect = width/height
    const d = 0.001
    const cameraOrtho = new THREE.OrthographicCamera(-d*aspect, d*aspect, d, -d, 1e-9, 1)
    cameraOrtho.position.set(0.000003, 0.000003, 0.000003)
    cameraOrtho.lookAt(0,0,0)

    let activeCamera: THREE.Camera = cameraPersp

    const renderer = new THREE.WebGLRenderer({antialias:true})
    renderer.setSize(width, height)
    // CAD dark background
    renderer.setClearColor(0x071021)
    w.appendChild(renderer.domElement)

    const light = new THREE.DirectionalLight(0xffffff, 1)
    light.position.set(1,1,1)
    scene.add(light)

    const srcGeom = new THREE.SphereGeometry(5e-8, 16, 12)
    const srcMat = new THREE.MeshStandardMaterial({color: 0xffee66})
    const srcMesh = new THREE.Mesh(srcGeom, srcMat)
    srcMesh.position.set(source.x, source.y, source.z)
    scene.add(srcMesh)

    // CAD helpers: grid, orbit + transform controls, and selection
    // create a GridHelper and store it in a ref so we can update it later
    const grid = new THREE.GridHelper(gridSize, gridDivs, 0x888888, 0x222222)
    grid.rotation.x = Math.PI / 2
    grid.position.set(0,0,0)
    grid.visible = showGrid
    scene.add(grid)
    gridRef.current = grid

    // controls & transform bound to the active camera (cameraPersp by default)
    let controls = new OrbitControls(activeCamera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.05
    controls.screenSpacePanning = false
    controls.target.set(0,0,0)

    let transform = new TransformControls(activeCamera, renderer.domElement)
    scene.add(transform)

    const attachTransformListeners = () => {
      transform.addEventListener('dragging-changed', (event: any) => { controls.enabled = !event.value })
      transform.addEventListener('objectChange', () => {
        const obj = transform.object as any
        if(obj && obj.userData && obj.userData.id){
          updateObject(obj.userData.id, { pos: [obj.position.x, obj.position.y, obj.position.z], size: obj.scale.x })
        }
      })
    }
    attachTransformListeners()

    // swap camera helper: dispose & create controls/transform bound to new camera
    function swapCamera(cam: THREE.Camera){
      try{ transform.detach() }catch(e){}
      try{ controls.dispose() }catch(e){}
      // remove old transform and create new using the new camera
      try{ scene.remove(transform) }catch(e){}
      controls = new OrbitControls(cam, renderer.domElement)
      controls.enableDamping = true
      controls.dampingFactor = 0.05
      controls.screenSpacePanning = false
      controls.target.set(0,0,0)
      transform = new TransformControls(cam, renderer.domElement)
      scene.add(transform)
      attachTransformListeners()
      activeCamera = cam
      // publish the active camera and controls so other hooks can access them
      sceneRef.current = { ...(sceneRef.current || {}), scene, camera: activeCamera, cameraPersp, cameraOrtho, renderer, srcMesh, updateTrace, syncObjects, setRayPoints, swapCamera }
    }

    // scene object meshes map (id -> mesh)
    const objMeshes: Record<string, THREE.Mesh> = {}

    const raycaster = new THREE.Raycaster()
    const pointer = new THREE.Vector2()

    const onPointerDown = (ev: PointerEvent) => {
      const rect = renderer.domElement.getBoundingClientRect()
      pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1
      pointer.y = - ((ev.clientY - rect.top) / rect.height) * 2 + 1
      raycaster.setFromCamera(pointer, activeCamera as any)
      const meshes = Object.values(objMeshes)
      const ints = raycaster.intersectObjects(meshes, true)
      if(ints.length){
        const picked = ints[0].object as any
        const id = picked.userData && picked.userData.id
        if(id){
          setSelectedObject(id)
          const m = objMeshes[id]
          transform.attach(m)
        }
      } else {
        setSelectedObject(null)
        try{ transform.detach() }catch(e){}
      }
    }

    function animate(){
      requestAnimationFrame(animate)
      if(controls && (controls as any).update) (controls as any).update()
      renderer.render(scene, activeCamera)
    }
    animate()

    sceneRef.current = {scene, camera: activeCamera, cameraPersp, cameraOrtho, renderer, srcMesh, updateTrace, syncObjects, setRayPoints, swapCamera }

    renderer.domElement.addEventListener('pointerdown', onPointerDown)

    function syncObjects(){
      const objs = currentScene().objects
      // add/update objects
      for(const o of objs){
        let m = objMeshes[o.id]
        if(!m){
          // choose geometry by type to reflect simple CAD primitives
          let g: THREE.BufferGeometry
          if(o.type === 'sphere') g = new THREE.SphereGeometry(o.size || 1e-7, 16, 12)
          else if(o.type === 'box') g = new THREE.BoxGeometry(o.size || 1e-7, o.size || 1e-7, o.size || 1e-7)
          else if(o.type === 'cylinder') g = new THREE.CylinderGeometry((o.size||1e-7)*0.5, (o.size||1e-7)*0.5, o.size || 1e-7, 16)
          else g = new THREE.SphereGeometry(o.size || 1e-7, 16, 12)
          const mat = new THREE.MeshStandardMaterial({color: o.color || 0x66ccff, transparent: (typeof o.opacity !== 'undefined' && o.opacity < 1) || false, opacity: (typeof o.opacity !== 'undefined' ? o.opacity : 1)})
          m = new THREE.Mesh(g, mat)
          m.userData = { id: o.id }
          m.name = o.id
          objMeshes[o.id] = m
          scene.add(m)
        }
        m.position.set(o.pos[0] || 0, o.pos[1] || 0, o.pos[2] || 0)
        // scale by size
        const s = o.size || 1e-7
        m.scale.set(s, s, s)

        // selection outline
          // update material properties (color/opacity) dynamically
        if(m.material){
          try{
            const mat: any = m.material
            if(typeof o.color !== 'undefined') mat.color.setHex(o.color)
            mat.transparent = (typeof o.opacity !== 'undefined' && o.opacity < 1)
            mat.opacity = (typeof o.opacity !== 'undefined' ? o.opacity : 1)
            mat.needsUpdate = true
          }catch(e){}
        }

        if(selectedObject === o.id){
          if(!(m.userData && m.userData.box)){
            m.userData.box = new THREE.BoxHelper(m, 0x0b74da)
            scene.add(m.userData.box)
          }
          m.userData.box.update()
        } else {
          if(m.userData && m.userData.box){ scene.remove(m.userData.box); delete m.userData.box }
        }
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
        const qsettings = (currentScene() as any).quickSettings || {}
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

    sceneRef.current = {scene, camera: activeCamera, cameraPersp, cameraOrtho, renderer, srcMesh, updateTrace, syncObjects, setRayPoints, swapCamera };

    const onResize = ()=>{
      const width = w.clientWidth
      const height = w.clientHeight
      renderer.setSize(width, height)
      if(activeCamera instanceof THREE.PerspectiveCamera){ (activeCamera as any).aspect = width / height; (activeCamera as any).updateProjectionMatrix() } else if(activeCamera instanceof THREE.OrthographicCamera){ const aspect = width/height; const d = 0.001; const ortho = activeCamera as any; ortho.left = -d * aspect; ortho.right = d * aspect; ortho.top = d; ortho.bottom = -d; ortho.updateProjectionMatrix() }
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

  // CAD UI state
  const [transformMode, setTransformMode] = useState<'translate'|'rotate'|'scale'>('translate')
  const [snapEnabled, setSnapEnabled] = useState(true)
  const [snapValue, setSnapValue] = useState(1e-7)
  const [showGrid, setShowGrid] = useState(true)
  const [viewMode, setViewMode] = useState<'perspective'|'top'|'front'|'side'>('perspective')

  // Panel visibility & floating
  const [toolsVisible, setToolsVisible] = useState(true)
  const [propsVisible, setPropsVisible] = useState(true)
  const [toolsFloating, setToolsFloating] = useState(false)
  const [propsFloating, setPropsFloating] = useState(false)
  const [toolsPos, setToolsPos] = useState<{x:number,y:number}>({x:10,y:60})
  const [propsPos, setPropsPos] = useState<{x:number,y:number}>({x:window.innerWidth - 380,y:60})

  // Grid settings (size in meters, divisions)
  const [gridSize, setGridSize] = useState(2e-5)
  const [gridDivs, setGridDivs] = useState(40)

  // Probe backend for GPU availability once on mount
  useEffect(()=>{
    (async ()=>{
      try{
        const r = await fetch((process.env.VITE_API_BASE || 'http://localhost:8000') + '/moon/gpu')
        const j = await r.json()
        setGpuAvailable(Boolean(j.cuda))
      }catch(e){
        setGpuAvailable(false)
      }
    })()
  }, [])

  // Sync transform control settings (mode / snapping)
  useEffect(()=>{
    const s = sceneRef.current as any
    if(!s || !s.transform) return
    try{
      s.transform.setMode(transformMode)
      if(snapEnabled){
        s.transform.setTranslationSnap(snapValue)
        s.transform.setScaleSnap(snapValue)
        s.transform.setRotationSnap(snapValue)
      }else{
        s.transform.setTranslationSnap(null)
        s.transform.setScaleSnap(null)
        s.transform.setRotationSnap(null)
      }
    }catch(e){}
  }, [transformMode, snapEnabled, snapValue])

  // Attach/detach transform when the selected object changes (e.g., from inspector)
  useEffect(()=>{
    const s = sceneRef.current as any
    if(!s || !s.transform) return
    const { transform, scene: sc } = s
    if(selectedObject){
      const mesh = sc.getObjectByName(selectedObject)
      if(mesh) transform.attach(mesh)
    }else{
      try{ transform.detach() }catch(e){}
    }
  }, [selectedObject])

  // Adjust camera for simple view modes
  useEffect(()=>{
    const s = sceneRef.current as any
    if(!s) return
    const { camera, controls } = s
    try{
      if(viewMode === 'perspective'){
        camera.position.set(0.000001, 0.000001, 0.000002)
        camera.up.set(0,1,0)
        camera.fov = 45
        camera.updateProjectionMatrix()
      }else if(viewMode === 'top'){
        camera.position.set(0, 0.000003, 0)
        camera.up.set(0,0,-1)
        camera.lookAt(0,0,0)
      }else if(viewMode === 'front'){
        camera.position.set(0.000003, 0, 0)
        camera.up.set(0,1,0)
        camera.lookAt(0,0,0)
      }else if(viewMode === 'side'){
        camera.position.set(0, 0, 0.000003)
        camera.up.set(0,1,0)
        camera.lookAt(0,0,0)
      }
      controls.update()
    }catch(e){}
  }, [viewMode])

  // Keyboard shortcuts for CAD workflow: W/E/R for translate/rotate/scale, G to toggle grid, S to toggle snap
  useEffect(()=>{
    const onKey = (ev: KeyboardEvent)=>{
      const tag = (ev.target as HTMLElement)?.tagName || ''
      if(tag === 'INPUT' || tag === 'TEXTAREA' || (ev as any).isComposing) return
      if(ev.key === 'w' || ev.key === 'W') setTransformMode('translate')
      if(ev.key === 'e' || ev.key === 'E') setTransformMode('rotate')
      if(ev.key === 'r' || ev.key === 'R') setTransformMode('scale')
      if(ev.key === 'g' || ev.key === 'G') setShowGrid(s=>!s)
      if(ev.key === 's' || ev.key === 'S') setSnapEnabled(s=>!s)
    }
    window.addEventListener('keydown', onKey)
    return ()=> window.removeEventListener('keydown', onKey)
  }, [])

  // Grid update effect: recreate GridHelper when size/divs change
  useEffect(()=>{
    try{
      const gcur = gridRef.current
      if(!gcur) return
      const sc = sceneRef.current
      if(!sc || !sc.scene) return
      // remove old
      try{ sc.scene.remove(gcur) }catch(e){}
      // create new grid
      const newGrid = new THREE.GridHelper(gridSize, gridDivs, 0x888888, 0x222222)
      newGrid.rotation.x = Math.PI/2
      newGrid.visible = showGrid
      sc.scene.add(newGrid)
      gridRef.current = newGrid
    }catch(e){/* ignore in POC */}
  }, [gridSize, gridDivs, showGrid])

  // Simple drag support for floating panels
  const toolsDragging = useRef(false)
  const propsDragging = useRef(false)
  useEffect(()=>{
    const onMove = (ev: MouseEvent)=>{
      if(toolsDragging.current){
        setToolsPos({x: ev.clientX - 140, y: ev.clientY - 12})
      }
      if(propsDragging.current){
        setPropsPos({x: ev.clientX - 160, y: ev.clientY - 12})
      }
    }
    const onUp = ()=>{ toolsDragging.current = false; propsDragging.current = false }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return ()=>{ window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp) }
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
      const qsettings = (currentScene() as any).quickSettings || {}
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
    <div style={{display:'flex', height: '100%'}}>
      {toolsVisible && (
        <aside style={toolsFloating ? {position:'absolute', left:toolsPos.x, top:toolsPos.y, width:280, padding:12, border:'1px solid #222', background:'#0b1116', color:'#dfe7f2', zIndex:1100} : {width:280, padding:12, borderRight:'1px solid #222', background:'#0b1116', color:'#dfe7f2'}}>
          <div style={{display:'flex', justifyContent:'space-between', alignItems:'center'}} onMouseDown={(e)=>{ if(toolsFloating){ toolsDragging.current = true } }}>
            <h3 style={{marginTop:0, color:'#fff'}}>Tools</h3>
            <div style={{display:'flex', gap:6}}>
              <button onClick={()=> setToolsFloating(f=>!f)}>{toolsFloating ? 'Dock' : 'Float'}</button>
            </div>
          </div>
          <div style={{fontSize:11, color:'#9fb6cf', marginTop:6}}>Shortcuts: W/E/R = Translate/Rotate/Scale • G = Grid • S = Snap</div>
          <div style={{fontSize:12, marginBottom:8}}>Project</div>
          <div style={{display:'flex', gap:8, marginBottom:12}}>
            <input placeholder="Scene name" style={{flex:1, padding:6, background:'#0f1720', border:'1px solid #222', color:'#dfe7f2'}} />
            <button>Create</button>
          </div>

          <div style={{fontSize:12, marginBottom:6}}>CAD Tools</div>
          <div style={{display:'flex', flexDirection:'column', gap:8, marginBottom:12}}>
            <button onClick={()=> setTransformMode('translate')}>Select / Transform</button>
            <button onClick={()=> addObject({ id: `o-${Date.now()}`, type: 'sphere', pos: [0,0,0], mass: 0.0, size: 5e-7, color: 0x66ccff, name: 'Sphere' })}>Insert Sphere</button>
            <button onClick={()=> addObject({ id: `o-${Date.now()}`, type: 'box', pos: [0,0,0], mass: 0.0, size: 5e-7, color: 0x99cc99, name: 'Box' })}>Insert Box</button>
            <button onClick={()=> addObject({ id: `o-${Date.now()}`, type: 'cylinder', pos: [0,0,0], mass: 0.0, size: 5e-7, color: 0xcc6699, name: 'Cylinder' })}>Insert Cylinder</button>
          </div>

          <div style={{fontSize:12, marginBottom:6}}>View</div>
          <div style={{display:'flex', gap:8, marginBottom:12}}>
            <button onClick={()=> setViewMode('top')}>Top</button>
            <button onClick={()=> setViewMode('front')}>Front</button>
            <button onClick={()=> setViewMode('side')}>Side</button>
            <button onClick={()=> setViewMode('perspective')}>Perspective</button>
          </div>

          <div style={{fontSize:12, marginBottom:6}}>Grid</div>
          <div style={{display:'flex', gap:8, marginBottom:12, alignItems:'center'}}>
            <label>Size <input type="number" value={gridSize} step={1e-7} onChange={(e)=> setGridSize(parseFloat(e.target.value))} /></label>
            <label>Div <input type="number" value={gridDivs} onChange={(e)=> setGridDivs(parseInt(e.target.value) || 0)} /></label>
            <label>Visible <input type="checkbox" checked={showGrid} onChange={(e)=> setShowGrid(e.target.checked)} /></label>
          </div>

        </aside>
      )}

      <div style={{flex:1, display:'flex', flexDirection:'column'}}>
        <div style={{padding:8, display:'flex', gap:8, alignItems:'center', justifyContent:'space-between'}}>
          <div>
            {scenes.map((s, idx)=> (
              <button key={s.id} style={{padding:6, background: idx===activeScene ? '#0b74da' : '#eee', color: idx===activeScene ? 'white' : 'black'}} onClick={()=>setActiveScene(idx)}>{s.name}</button>
            ))}
            <button onClick={()=>{ setScenes(prev=>[...prev, { id: `scene-${Date.now()}`, name: `Scene ${prev.length+1}`, solver: 'interactive', quickSolver: 'weak', objects: [] }]); setActiveScene(scenes.length) }}>+ Scene</button>
          </div>

          <div style={{display:'flex', gap:8, alignItems:'center'}}>
            <div style={{display:'flex', gap:6, alignItems:'center'}}>
              <button onClick={()=> setTransformMode('translate')} style={{background: transformMode==='translate' ? '#0b74da' : undefined, color: transformMode==='translate' ? 'white' : undefined}}>Translate</button>
              <button onClick={()=> setTransformMode('rotate')} style={{background: transformMode==='rotate' ? '#0b74da' : undefined, color: transformMode==='rotate' ? 'white' : undefined}}>Rotate</button>
              <button onClick={()=> setTransformMode('scale')} style={{background: transformMode==='scale' ? '#0b74da' : undefined, color: transformMode==='scale' ? 'white' : undefined}}>Scale</button>
            </div>
            <label style={{marginLeft:8}}>Snap <input type="checkbox" checked={snapEnabled} onChange={(e)=> setSnapEnabled(e.target.checked)} /></label>
            <label style={{marginLeft:6}}>Step <input type="number" value={snapValue} step={1e-8} onChange={(e)=> setSnapValue(parseFloat(e.target.value))} /></label>
            <button style={{marginLeft:12}} onClick={()=>{ addObject({ id: `o-${Date.now()}`, type: 'box', pos: [0,0,0], mass: 0.0, size: 5e-7, color: 0x99cc99, name: 'Box' }) }}>Add Box</button>
            <button style={{marginLeft:8}} onClick={()=>{ addObject({ id: `o-${Date.now()}`, type: 'cylinder', pos: [0,0,0], mass: 0.0, size: 5e-7, color: 0xcc6699, name: 'Cylinder' }) }}>Add Cylinder</button>
            <label style={{marginLeft:8}}>View
              <select value={viewMode} onChange={(e)=> setViewMode(e.target.value as any)}>
                <option value="perspective">Perspective</option>
                <option value="top">Top</option>
                <option value="front">Front</option>
                <option value="side">Side</option>
              </select>
            </label>
            <label style={{marginLeft:8}}>Grid <input type="checkbox" checked={showGrid} onChange={(e)=>{ setShowGrid(e.target.checked); const s = sceneRef.current; if(s && s.scene){ const g = s.scene.getObjectByProperty('type','GridHelper') as any; if(g) g.visible = e.target.checked }}} /></label>
          </div>
        </div> 
        <div ref={mountRef} style={{flex:1}} />
      </div>


      {propsVisible && (
        <aside style={propsFloating ? {position:'absolute', right: propsPos.x, top: propsPos.y, width: 320, padding: 12, borderLeft: '1px solid #222', background:'#0b1116', color:'#dfe7f2', zIndex:1100} : {width: 320, padding: 12, borderLeft: '1px solid #ddd'}} onMouseDown={(e)=>{ if(propsFloating){ propsDragging.current = true } }}>
          <div style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
            <h3>Properties</h3>
            <div style={{display:'flex', gap:6}}>
              <button onClick={()=> setPropsFloating(f=>!f)}>{propsFloating ? 'Dock' : 'Float'}</button>
            </div>
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
                <div style={{marginTop:6, display:'flex', gap:8, alignItems:'center'}}>
                  <label style={{fontSize:12}}>Color <input type="color" value={(o.color ? ('#' + (o.color as number).toString(16).padStart(6,'0')) : '#66ccff')} onChange={(e)=> updateObject(o.id, { color: parseInt(e.target.value.replace('#','0x')) })} /></label>
                  <label style={{fontSize:12}}>Opacity <input type="range" min={0} max={1} step={0.01} value={typeof o.opacity === 'undefined' ? 1 : o.opacity} onChange={(e)=> updateObject(o.id, { opacity: parseFloat(e.target.value) })} /></label>
                </div>
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
                  <div style={{marginTop:8}}>
                    <strong>Gradient</strong>
                    <div style={{display:'flex', gap:8, alignItems:'center', marginTop:6}}>
                      <label>Color A <input type="color" value={(o.gradient && o.gradient.a) ? ('#' + (o.gradient.a as number).toString(16).padStart(6,'0')) : '#ffffff'} onChange={(e)=> updateObject(o.id, { gradient: { ...(o.gradient||{}), a: parseInt(e.target.value.replace('#','0x')) } })} /></label>
                      <label>Color B <input type="color" value={(o.gradient && o.gradient.b) ? ('#' + (o.gradient.b as number).toString(16).padStart(6,'0')) : '#000000'} onChange={(e)=> updateObject(o.id, { gradient: { ...(o.gradient||{}), b: parseInt(e.target.value.replace('#','0x')) } })} /></label>
                      <label>Dir
                        <select value={(o.gradient && o.gradient.dir) || 'horizontal'} onChange={(e)=> updateObject(o.id, { gradient: { ...(o.gradient||{}), dir: e.target.value } })}>
                          <option value="horizontal">Horizontal</option>
                          <option value="vertical">Vertical</option>
                          <option value="radial">Radial</option>
                        </select>
                      </label>
                    </div>
                  </div>
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
      )}
    </div>
  )
}
