import React, { useMemo, useState } from 'react'
import { BackendTransportProvider, StarDustApp, createFetchBackendTransport } from '@stardust/ui'

const SPEED_OF_LIGHT_M_S = 299_792_458
type CsvXAxis = 'frequency_hz' | 'wavelength_m' | 'wavelength_um' | 'wavelength_nm'

export default function App(){
  const [showPhotonOverlays, setShowPhotonOverlays] = useState(false)
  const [recalcOnZoom, setRecalcOnZoom] = useState(false)
  const [advancedTensorsOpen, setAdvancedTensorsOpen] = useState(false)
  const [csvXAxisEps, setCsvXAxisEps] = useState<CsvXAxis>('wavelength_nm')
  const [csvXAxisMu, setCsvXAxisMu] = useState<CsvXAxis>('wavelength_nm')

  const transport = useMemo(() => {
    const apiBase = (import.meta as any).env?.VITE_API_BASE as string | undefined
    const base = (apiBase ?? 'http://localhost:8000').replace(/\/+$/, '')
    // MoonStone backend is mounted under /moon
    return createFetchBackendTransport({ basePath: `${base}/moon` })
  }, [])

  return (
    <BackendTransportProvider transport={transport}>
      <StarDustApp
        extensions={{
          toolsExtra: (
            <>
              <h2>MoonStone</h2>
              <label className="check">
                <input
                  type="checkbox"
                  checked={showPhotonOverlays}
                  onChange={(e) => setShowPhotonOverlays(e.target.checked)}
                />
                Photon trajectory overlays
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  checked={recalcOnZoom}
                  onChange={(e) => setRecalcOnZoom(e.target.checked)}
                />
                Recompute on zoom (higher precision)
              </label>
            </>
          ),
          renderCanvas2dOverlays: ({ toScene, sources, monitors, overlayStrokeWidth, overlayAutoscale }) => {
            if (!showPhotonOverlays) return null

            // Placeholder overlay: straight-line rays from each source to each monitor.
            // This validates that MoonStone can render GR overlays in the StarDust view transform.
            const srcs = Array.isArray(sources) ? sources : []
            const mons = Array.isArray(monitors) ? monitors : []
            if (srcs.length === 0 || mons.length === 0) return null

            const stroke = 'rgba(34,211,238,0.85)'

            return (
              <g data-kind="moonstone-photon-overlays" style={{ pointerEvents: 'none' as any }}>
                {srcs.flatMap((s: any) =>
                  mons.map((m: any) => {
                    const sx = toScene(Number(s?.position?.[0] ?? 0))
                    const sy = toScene(Number(s?.position?.[1] ?? 0))
                    const ex = toScene(Number(m?.position?.[0] ?? 0))
                    const ey = toScene(Number(m?.position?.[1] ?? 0))
                    const key = `${String(s?.id ?? 's')}:${String(m?.id ?? 'm')}`
                    return (
                      <line
                        key={key}
                        x1={sx}
                        y1={sy}
                        x2={ex}
                        y2={ey}
                        stroke={stroke}
                        strokeWidth={Math.max(overlayStrokeWidth, overlayStrokeWidth * 0.9)}
                        opacity={0.55}
                        vectorEffect={overlayAutoscale ? undefined : 'non-scaling-stroke'}
                      />
                    )
                  }),
                )}
              </g>
            )
          },

          renderMaterialEditorFields: ({ material, updateMaterial }) => {
            const payload = (material?.payload && typeof material.payload === 'object') ? material.payload : {}

            const massKg = typeof payload.massKg === 'number' ? payload.massKg : ''
            const densityKgM3 = typeof payload.densityKgM3 === 'number' ? payload.densityKgM3 : ''

            const downloadText = (txt: string, filename: string) => {
              try {
                const blob = new Blob([txt], { type: 'text/csv;charset=utf-8' })
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = filename
                document.body.appendChild(a)
                a.click()
                a.remove()
                URL.revokeObjectURL(url)
              } catch (e) {
                console.warn('download failed', e)
              }
            }

            const exportDispersionCsv = (fit: any, filename: string, xAxis: CsvXAxis, valueKey: 'eps_values' | 'mu_values') => {
              const freqs: any[] = Array.isArray(fit?.freqs) ? fit.freqs : []
              const values: any[] = Array.isArray(fit?.[valueKey]) ? fit[valueKey] : []
              if (!freqs.length || freqs.length !== values.length) return

              const lines: string[] = ['x,real,imag']
              for (let i = 0; i < freqs.length; i++) {
                const f = Number(freqs[i])
                if (!Number.isFinite(f) || f <= 0) continue
                const v = values[i]
                const re = typeof v === 'object' && v && 'real' in v ? Number((v as any).real) : Number(v)
                const im = typeof v === 'object' && v && 'imag' in v ? Number((v as any).imag) : 0

                let x = f
                if (xAxis !== 'frequency_hz') {
                  const lam_m = SPEED_OF_LIGHT_M_S / f
                  x = xAxis === 'wavelength_m' ? lam_m : xAxis === 'wavelength_um' ? lam_m * 1e6 : lam_m * 1e9
                }
                lines.push(`${x},${re},${im}`)
              }
              downloadText(lines.join('\n'), filename)
            }

            const importCsvToFit = (file: File | null, xAxis: CsvXAxis, target: 'eps' | 'mu') => {
              if (!file) return
              const reader = new FileReader()
              reader.onload = () => {
                const txt = String(reader.result || '')
                const rows = txt.trim().split(/\r?\n/).map(l => l.split(/,|\s+/).map(s => s.trim()).filter(Boolean))
                const parsed: { f: number; re: number; im: number }[] = []
                for (const r of rows) {
                  if (r.length >= 2) {
                    const x = Number(r[0])
                    const re = Number(r[1])
                    const im = r.length >= 3 ? Number(r[2]) : 0
                    if (!Number.isFinite(x) || !Number.isFinite(re) || !Number.isFinite(im)) continue
                    let f = x
                    if (xAxis !== 'frequency_hz') {
                      const lam_m = xAxis === 'wavelength_m' ? x : xAxis === 'wavelength_um' ? x * 1e-6 : x * 1e-9
                      if (!Number.isFinite(lam_m) || lam_m <= 0) continue
                      f = SPEED_OF_LIGHT_M_S / lam_m
                    }
                    if (Number.isFinite(f) && f > 0) parsed.push({ f, re, im })
                  }
                }
                parsed.sort((a, b) => a.f - b.f)
                const mid = parsed.length ? parsed[Math.floor(parsed.length / 2)] : null

                if (target === 'eps') {
                  updateMaterial({
                    dispersion_fit: {
                      freqs: parsed.map((r) => r.f),
                      eps_values: parsed.map((r) => ({ real: r.re, imag: r.im })),
                    },
                    ...(mid ? { eps: { real: mid.re, imag: mid.im }, center_freq: mid.f, approximate_complex: true } : {}),
                  })
                } else {
                  updateMaterial({
                    mu_dispersion_fit: {
                      freqs: parsed.map((r) => r.f),
                      mu_values: parsed.map((r) => ({ real: r.re, imag: r.im })),
                    },
                    ...(mid ? { mu: { real: mid.re, imag: mid.im }, mu_center_freq: mid.f } : {}),
                  })
                }
              }
              reader.readAsText(file)
            }

            const ensureFlat9 = (v: any): number[] => {
              if (Array.isArray(v) && v.length === 9) {
                const n = v.map((x: any) => (x === '' || x === null || x === undefined ? 0 : Number(x)))
                return n.map((x: any) => (Number.isFinite(x) ? x : 0))
              }
              if (Array.isArray(v) && v.length === 3 && v.every((r: any) => Array.isArray(r) && r.length === 3)) {
                const flat = [
                  Number(v[0][0]),
                  Number(v[0][1]),
                  Number(v[0][2]),
                  Number(v[1][0]),
                  Number(v[1][1]),
                  Number(v[1][2]),
                  Number(v[2][0]),
                  Number(v[2][1]),
                  Number(v[2][2]),
                ]
                return flat.map((x: any) => (Number.isFinite(x) ? x : 0))
              }
              return Array(9).fill(0)
            }

            const renderTensor = (field: 'epsilon' | 'mu' | 'xi' | 'zeta', label: string) => {
              const m: any = material as any
              const fallback =
                field === 'epsilon'
                  ? (m?.epsilon_tensor ?? m?.eps_tensor)
                  : field === 'mu'
                    ? (m?.mu_tensor)
                    : field === 'xi'
                      ? (m?.xi_tensor)
                      : (m?.zeta_tensor)
              const arr = ensureFlat9(m?.[field] ?? fallback)
              return (
                <div style={{ marginTop: 10 }}>
                  <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 6 }}>{label} (3x3, row-major)</div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
                    {Array.from({ length: 9 }).map((_, idx) => (
                      <input
                        key={idx}
                        value={arr[idx]}
                        onChange={(e) => {
                          const next = ensureFlat9((material as any)?.[field])
                          next[idx] = Number(e.currentTarget.value)
                          updateMaterial({ [field]: next })
                        }}
                      />
                    ))}
                  </div>
                </div>
              )
            }

            return (
              <div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                <label>
                  Mass (kg)
                  <input
                    type="number"
                    value={massKg as any}
                    onChange={(e) => {
                      const v = e.currentTarget.valueAsNumber
                      updateMaterial({
                        payload: {
                          ...payload,
                          massKg: Number.isFinite(v) ? v : undefined,
                        },
                      })
                    }}
                  />
                </label>
                <label>
                  Density (kg/m^3)
                  <input
                    type="number"
                    value={densityKgM3 as any}
                    onChange={(e) => {
                      const v = e.currentTarget.valueAsNumber
                      updateMaterial({
                        payload: {
                          ...payload,
                          densityKgM3: Number.isFinite(v) ? v : undefined,
                        },
                      })
                    }}
                  />
                </label>
                </div>

                <div style={{ marginTop: 10 }}>
                  <button onClick={() => setAdvancedTensorsOpen((p) => !p)}>
                    {advancedTensorsOpen ? 'Hide advanced tensors' : 'Advanced tensors'}
                  </button>
                </div>

                {advancedTensorsOpen && (
                  <div style={{ marginTop: 10, padding: 10, borderRadius: 6, background: 'rgba(255,255,255,0.02)' }}>
                    <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 6 }}>
                      Constitutive tensors (optional)
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                      <label>
                        ε (isotropic scalar)
                        {typeof (material as any)?.eps === 'object' && (material as any)?.eps && ('real' in (material as any).eps) ? (
                          <input
                            type="number"
                            value={Number(((material as any).eps as any).real) as any}
                            onChange={(e) => {
                              const v = e.currentTarget.valueAsNumber
                              updateMaterial({ eps: { real: Number.isFinite(v) ? v : 0, imag: Number((((material as any).eps as any).imag) ?? 0) } })
                            }}
                          />
                        ) : (
                          <input
                            type="number"
                            value={typeof (material as any)?.eps === 'number' ? (material as any).eps : ''}
                            onChange={(e) => {
                              const v = e.currentTarget.valueAsNumber
                              updateMaterial({ eps: Number.isFinite(v) ? v : undefined })
                            }}
                          />
                        )}
                      </label>
                      <label>
                        μ (isotropic scalar)
                        {typeof (material as any)?.mu === 'object' && (material as any)?.mu && ('real' in (material as any).mu) ? (
                          <input
                            type="number"
                            value={Number(((material as any).mu as any).real) as any}
                            onChange={(e) => {
                              const v = e.currentTarget.valueAsNumber
                              updateMaterial({ mu: { real: Number.isFinite(v) ? v : 0, imag: Number((((material as any).mu as any).imag) ?? 0) } })
                            }}
                          />
                        ) : (
                          <input
                            type="number"
                            value={typeof (material as any)?.mu === 'number' ? (material as any).mu : ''}
                            onChange={(e) => {
                              const v = e.currentTarget.valueAsNumber
                              updateMaterial({ mu: Number.isFinite(v) ? v : undefined })
                            }}
                          />
                        )}
                      </label>
                    </div>

                    <div style={{ marginTop: 8, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                      <label className="check">
                        <input
                          type="checkbox"
                          checked={typeof (material as any)?.eps === 'object' && (material as any)?.eps && ('real' in (material as any).eps)}
                          onChange={(e) => {
                            const checked = e.currentTarget.checked
                            if (checked) {
                              const re = typeof (material as any)?.eps === 'number' ? (material as any).eps : Number((((material as any).eps as any)?.real) ?? 1)
                              updateMaterial({ eps: { real: Number.isFinite(re) ? re : 1, imag: 0 } })
                            } else {
                              const re = Number((((material as any).eps as any)?.real) ?? 1)
                              updateMaterial({ eps: Number.isFinite(re) ? re : 1 })
                            }
                          }}
                        />
                        <span style={{ fontSize: 12, color: '#9ca3af' }}>Complex ε</span>
                      </label>

                      {typeof (material as any)?.eps === 'object' && (material as any)?.eps && ('real' in (material as any).eps) ? (
                        <label>
                          Im(ε)
                          <input
                            type="number"
                            value={Number((((material as any).eps as any).imag) ?? 0) as any}
                            onChange={(e) => {
                              const v = e.currentTarget.valueAsNumber
                              updateMaterial({ eps: { real: Number((((material as any).eps as any).real) ?? 0), imag: Number.isFinite(v) ? v : 0 } })
                            }}
                          />
                        </label>
                      ) : null}

                      <label className="check">
                        <input
                          type="checkbox"
                          checked={typeof (material as any)?.mu === 'object' && (material as any)?.mu && ('real' in (material as any).mu)}
                          onChange={(e) => {
                            const checked = e.currentTarget.checked
                            if (checked) {
                              const re = typeof (material as any)?.mu === 'number' ? (material as any).mu : Number((((material as any).mu as any)?.real) ?? 1)
                              updateMaterial({ mu: { real: Number.isFinite(re) ? re : 1, imag: 0 } })
                            } else {
                              const re = Number((((material as any).mu as any)?.real) ?? 1)
                              updateMaterial({ mu: Number.isFinite(re) ? re : 1 })
                            }
                          }}
                        />
                        <span style={{ fontSize: 12, color: '#9ca3af' }}>Complex μ</span>
                      </label>

                      {typeof (material as any)?.mu === 'object' && (material as any)?.mu && ('real' in (material as any).mu) ? (
                        <label>
                          Im(μ)
                          <input
                            type="number"
                            value={Number((((material as any).mu as any).imag) ?? 0) as any}
                            onChange={(e) => {
                              const v = e.currentTarget.valueAsNumber
                              updateMaterial({ mu: { real: Number((((material as any).mu as any).real) ?? 0), imag: Number.isFinite(v) ? v : 0 } })
                            }}
                          />
                        </label>
                      ) : null}
                    </div>

                    <div style={{ marginTop: 10, padding: 10, borderRadius: 6, background: 'rgba(255,255,255,0.02)' }}>
                      <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 6 }}>Dispersion CSV (x, real, imag)</div>

                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                        <div>
                          <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 6 }}>ε table</div>
                          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                            <select value={csvXAxisEps} onChange={(e) => setCsvXAxisEps(e.target.value as CsvXAxis)}>
                              <option value="frequency_hz">x = frequency (Hz)</option>
                              <option value="wavelength_m">x = wavelength (m)</option>
                              <option value="wavelength_um">x = wavelength (μm)</option>
                              <option value="wavelength_nm">x = wavelength (nm)</option>
                            </select>
                            <input type="file" accept=".csv,.txt" onChange={(e) => importCsvToFit(e.target.files?.[0] ?? null, csvXAxisEps, 'eps')} />
                            <button
                              onClick={() => exportDispersionCsv((material as any)?.dispersion_fit, `moonstone_${String((material as any)?.id ?? 'mat')}_eps.csv`, csvXAxisEps, 'eps_values')}
                              disabled={!((material as any)?.dispersion_fit && Array.isArray((material as any).dispersion_fit?.freqs))}
                            >
                              Export
                            </button>
                          </div>
                        </div>

                        <div>
                          <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 6 }}>μ table</div>
                          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                            <select value={csvXAxisMu} onChange={(e) => setCsvXAxisMu(e.target.value as CsvXAxis)}>
                              <option value="frequency_hz">x = frequency (Hz)</option>
                              <option value="wavelength_m">x = wavelength (m)</option>
                              <option value="wavelength_um">x = wavelength (μm)</option>
                              <option value="wavelength_nm">x = wavelength (nm)</option>
                            </select>
                            <input type="file" accept=".csv,.txt" onChange={(e) => importCsvToFit(e.target.files?.[0] ?? null, csvXAxisMu, 'mu')} />
                            <button
                              onClick={() => exportDispersionCsv((material as any)?.mu_dispersion_fit, `moonstone_${String((material as any)?.id ?? 'mat')}_mu.csv`, csvXAxisMu, 'mu_values')}
                              disabled={!((material as any)?.mu_dispersion_fit && Array.isArray((material as any).mu_dispersion_fit?.freqs))}
                            >
                              Export
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>

                    {renderTensor('epsilon', 'ε tensor')}
                    {renderTensor('mu', 'μ tensor')}
                    {renderTensor('xi', 'ξ coupling')}
                    {renderTensor('zeta', 'ζ coupling')}
                  </div>
                )}
              </div>
            )
          },
        }}
      />
    </BackendTransportProvider>
  )
}
