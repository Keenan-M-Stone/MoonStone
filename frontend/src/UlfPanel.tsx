import React, { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { fetchTrace, fetchMetricSample } from './api'

export default function UlfPanel(){
  const mountRef = useRef<HTMLDivElement | null>(null)
  const [source, setSource] = useState({x: -1e-6, y: 0.0, z: 0.0})
  const sceneRef = useRef<any>()

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

    const rayMaterial = new THREE.LineBasicMaterial({color: 0xff0000})
    let rayLine: THREE.Line | null = null

    async function updateTrace(){
      try{
        const resp = await fetchTrace({
          source: {x: source.x, y: source.y, z: source.z},
          directions: [{x:1,y:0,z:0}],
          metric: {type: 'schwarzschild', mass: 1.0}
        })
        const pts = resp.points.map((p:any)=> new THREE.Vector3(p.x, p.y, p.z))
        const geom = new THREE.BufferGeometry().setFromPoints(pts)
        if(rayLine) scene.remove(rayLine)
        rayLine = new THREE.Line(geom, rayMaterial)
        scene.add(rayLine)
      }catch(e){
        console.error('trace error', e)
      }
    }

    updateTrace()

    function animate(){
      requestAnimationFrame(animate)
      renderer.render(scene, camera)
    }
    animate()

    sceneRef.current = {scene, camera, renderer, srcMesh, updateTrace}

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
    const id = setTimeout(()=> s.updateTrace(), 80)
    return ()=> clearTimeout(id)
  }, [source])

  // Metric UI and observer
  const [metric, setMetric] = useState({type: 'schwarzschild', mass: 1.0})
  const [observer, setObserver] = useState({x: 1e-6, y: 0.0, z: 0.0})
  const [tensor, setTensor] = useState<any | null>(null)

  async function sampleAtObserver(){
    try{
      const resp = await fetchMetricSample(observer, metric)
      setTensor(resp)
    }catch(e){
      console.error('metric sample error', e)
    }
  }

  return (
    <div style={{display:'flex', height:'100%'}}>
      <div ref={mountRef} style={{flex:1}} />
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

      </aside>
    </div>
  )
}
