import axios from 'axios'

function computeApiBase(): string {
  const fromVite = (import.meta as any).env?.VITE_API_BASE as string | undefined
  const fromProcess = (typeof process !== 'undefined' ? (process as any).env?.VITE_API_BASE : undefined) as string | undefined
  const base = (fromVite ?? fromProcess ?? 'http://localhost:8000').replace(/\/+$/, '')
  return base
}

export const API_BASE = computeApiBase()

export async function fetchTrace(payload: any){
  const r = await axios.post(`${API_BASE}/moon/trace`, payload)
  return r.data
}

export async function fetchMetricSample(point: any, metric: any){
  const r = await axios.post(`${API_BASE}/moon/metric`, point, { params: { metric: JSON.stringify(metric) } })
  return r.data
}

export async function exportTrace(traceId: string){
  const r = await axios.post(`${API_BASE}/moon/export`, { trace_id: traceId })
  return r.data
}

export async function fetchPlebanskiGrid(params: {
  metric: any
  bounds: { xmin: number; xmax: number; ymin: number; ymax: number }
  nx: number
  ny: number
  z?: number
}) {
  const r = await axios.post(`${API_BASE}/moon/plebanski-grid`, params)
  return r.data
}

export async function saveScene(scene: any){
  const r = await axios.post(`${API_BASE}/moon/scene`, scene)
  return r.data
}

export async function loadScene(id: string){
  const r = await axios.get(`${API_BASE}/moon/scene/${id}`)
  return r.data
}

export async function listScenes(){
  const r = await axios.get(`${API_BASE}/moon/scenes`)
  return r.data
}

export default {}
