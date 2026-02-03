import axios from 'axios'

const API_BASE = process.env.VITE_API_BASE || 'http://localhost:8000'

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

export default {}
