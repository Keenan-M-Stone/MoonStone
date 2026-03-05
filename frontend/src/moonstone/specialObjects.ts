import { SpecialObject } from '../stardust'

export class Observer extends SpecialObject {
  constructor(init: { id: string; position: [number, number]; z?: number; label?: string }) {
    super({
      id: init.id,
      kind: "observer",
      position: init.position,
      z: init.z,
      label: init.label ?? init.id,
      marker: { kind: "point", color: "#22d3ee", radiusScene: 7 },
    });
  }
}

export class LightSource extends SpecialObject {
  constructor(init: { id: string; position: [number, number]; z?: number; label?: string }) {
    super({
      id: init.id,
      kind: "lightSource",
      position: init.position,
      z: init.z,
      label: init.label ?? init.id,
      marker: { kind: "point", color: "#f59e0b", radiusScene: 7 },
    });
  }
}
