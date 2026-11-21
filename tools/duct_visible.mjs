// Visible duct check: node tools/duct_visible.mjs  (from the repo root, after model/make_equipment.py)
// A duct belongs inside the walls, the truss space or the attic. This builds the house with site/house.js and the ducts with
// site/equipment.js, then looks around every room from a grid of points at several heights. Any ray whose first hit is a
// duct (not its grille) means that duct shows in the room: an elbow poking through the drywall, a stack wider than its wall,
// a run under a ceiling. Ducts that are exposed on purpose are listed in EXPOSED. Exit 1 if anything else shows.
//   --all   also list the exposed-on-purpose ones
import { register } from 'node:module';
register('./three_hooks.mjs', import.meta.url);
const fs = await import('node:fs');
const THREE = await import('three');
const { computeBoundsTree, acceleratedRaycast } = await import('three-mesh-bvh');
THREE.BufferGeometry.prototype.computeBoundsTree = computeBoundsTree;
THREE.Mesh.prototype.raycast = acceleratedRaycast;
const el = () => ({ style: {}, getContext: () => new Proxy({}, { get: () => () => ({ addColorStop() {} }) }), addEventListener() {}, removeEventListener() {}, setAttribute() {} });
globalThis.document = { createElement: el, createElementNS: el };
const { buildHouse } = await import('../site/house.js');
const { plan, buildEquipment } = await import('../site/equipment.js');

// Exposed by design: the study's supply along its sloped ceiling (Maxwell picked it, 11/18/2026), closet 2's run along
// closet 3's ceiling, the range hood duct in its chase, the water heater's intake and exhaust above the tank.
const EXPOSED = new Set(['s_study', 's_closet2', 'ex_hood', 'hpwh_intake', 'hpwh_exhaust']);
const ALL = process.argv.includes('--all');
const F = 0.3048;
const hd = JSON.parse(fs.readFileSync('site/models/house.json'));
const eq = JSON.parse(fs.readFileSync('site/models/equipment.json'));
const house = buildHouse(hd, { skip: new Set((eq.items || []).map((it) => it.id)) });
const { root } = buildEquipment({ ducts: eq.ducts });
house.root.updateMatrixWorld(true); root.updateMatrixWorld(true);
const meshes = [];
const grab = (o) => {
  if (!o.isMesh || o.visible === false) return;
  o.geometry.computeBoundsTree(); o.material && (o.material = o.material.clone(), o.material.side = THREE.DoubleSide);
  o.userData.box = new THREE.Box3().setFromObject(o); meshes.push(o);
};
house.root.traverse(grab); root.traverse(grab);
const ductOf = (o) => { for (let p = o; p; p = p.parent) if (p.parent && p.parent.name === 'ducts') return p.name; return null; };
const isGrille = (o) => o.geometry.type === 'BoxGeometry' && /grille|slot/i.test(o.material.name || '') ;

// directions: a Fibonacci sphere
const DIRS = [], ND = 1500;
for (let i = 0; i < ND; i++) { const y = 1 - 2 * (i + 0.5) / ND, r = Math.sqrt(1 - y * y), t = i * 2.399963; DIRS.push(new THREE.Vector3(Math.cos(t) * r, y, Math.sin(t) * r)); }
const rc = new THREE.Raycaster(); rc.firstHitOnly = true;
const found = new Map();
const rooms = hd.meta.rooms.filter((r) => !r.outside && r.name !== 'Garage');
for (const R of rooms) {
  const [x0, y0, x1, y1] = R.rect, f = R.floor || 0;
  const xs = [], ys = [];
  for (let t = 0.2; t < 0.85; t += 0.3) { xs.push(x0 + (x1 - x0) * t); ys.push(y0 + (y1 - y0) * t); }
  // only what is in or around this room, so a ray that leaves through a door finds nothing beyond it
  const box = new THREE.Box3(plan(x0 - 1, y0 - 1, f - 1), plan(x1 + 1, y1 + 1, f + 30)), near = meshes.filter((m) => m.userData.box.intersectsBox(box));
  for (const x of xs) for (const y of ys) for (const z of [f + 1.5, f + 5, f + 8]) {
    const o = plan(x, y, z);
    for (const d of DIRS) {
      rc.set(o, d); rc.far = 40 * F;
      const h = rc.intersectObjects(near, false)[0];
      if (!h) continue;
      const id = ductOf(h.object);
      if (!id || isGrille(h.object)) continue;
      const k = id + ' | ' + R.name, p = h.point;
      const e = found.get(k) || { n: 0, at: null };
      e.n++; e.at = [+(p.x / F).toFixed(2), +(p.z / F).toFixed(2), +(p.y / F).toFixed(2)]; found.set(k, e);
    }
  }
}
let bad = 0;
for (const [k, e] of [...found].sort()) {
  const id = k.split(' | ')[0], ok = EXPOSED.has(id);
  if (ok && !ALL) continue;
  if (!ok) bad++;
  console.log(`${ok ? 'exposed ' : 'SHOWS   '} ${k}: ${e.n} rays, e.g. at plan ${e.at.join(', ')}`);
}
console.log(bad ? `${bad} duct / room pairs show through` : 'no duct shows through a wall or ceiling');
process.exit(bad ? 1 : 0);
