import {
  PolarizationEditor,
  normalizeSourcePolarization,
  type PolarizationPreset,
  type PolarizationEditorProps,
  type SourcePolarization,
} from '@stardust/ui'

export type GwPolarizationEditorProps = Omit<
  PolarizationEditorProps,
  'axisLabels' | 'modeLabels'
> & {
  value: unknown
  onChange: (next: SourcePolarization) => void
}

// GW-flavor wrapper for the shared two-component polarization editor.
// This is intentionally a scaffold: it reuses the existing two-component (a/b)
// machinery but labels the basis as + / ×.
export default function GwPolarizationEditor(props: GwPolarizationEditorProps) {
  const presets: PolarizationPreset[] = [
    {
      label: '+ only',
      apply: (current) => {
        const base = current.kind === 'jones' ? current : normalizeSourcePolarization(current)
        return {
          kind: 'jones',
          plane: base.kind === 'jones' ? base.plane : 'xy',
          wrt: base.kind === 'jones' ? base.wrt : 'global-xyz',
          u: { amp: 1, phaseDeg: 0 },
          v: { amp: 0, phaseDeg: 0 },
        }
      },
    },
    {
      label: '× only',
      apply: (current) => {
        const base = current.kind === 'jones' ? current : normalizeSourcePolarization(current)
        return {
          kind: 'jones',
          plane: base.kind === 'jones' ? base.plane : 'xy',
          wrt: base.kind === 'jones' ? base.wrt : 'global-xyz',
          u: { amp: 0, phaseDeg: 0 },
          v: { amp: 1, phaseDeg: 0 },
        }
      },
    },
    {
      label: 'R',
      title: 'Right-handed ( + leads × by 90° )',
      apply: (current) => {
        const base = current.kind === 'jones' ? current : normalizeSourcePolarization(current)
        return {
          kind: 'jones',
          plane: base.kind === 'jones' ? base.plane : 'xy',
          wrt: base.kind === 'jones' ? base.wrt : 'global-xyz',
          u: { amp: 1, phaseDeg: 0 },
          v: { amp: 1, phaseDeg: -90 },
        }
      },
    },
    {
      label: 'L',
      title: 'Left-handed ( + lags × by 90° )',
      apply: (current) => {
        const base = current.kind === 'jones' ? current : normalizeSourcePolarization(current)
        return {
          kind: 'jones',
          plane: base.kind === 'jones' ? base.plane : 'xy',
          wrt: base.kind === 'jones' ? base.wrt : 'global-xyz',
          u: { amp: 1, phaseDeg: 0 },
          v: { amp: 1, phaseDeg: 90 },
        }
      },
    },
  ]

  return (
    <PolarizationEditor
      {...props}
      axisLabels={{ a: '+', b: '×' }}
      allowedKinds={['jones']}
      showPresets={true}
      presets={presets}
      renderPreview={() => null}
      showPlane={false}
      showWrt={false}
    />
  )
}
