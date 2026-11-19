// Snap wall devices onto the finished wall: node tools/electrical/snap.mjs [--write]  (from the repo root)
// Builds the house with site/house.js, casts a ray from 8 in in front of each outlet, switch and data plate back along
// its facing, and reports how far the plate's back is from the first house surface it meets (+ = buried in it,
// - = floating off it). --write saves the corrections to model/data/electrical_snap.json; rerun make_equipment.py after.
import { register } from 'node:module';
register('../three_hooks.mjs', import.meta.url);
const fs = await import('node:fs');
const THREE = await import('three');
const el = () => ({ style: {}, getContext: () => new Proxy({}, { get: () => () => ({ addColorStop() {} }) }), addEventListener() {}, removeEventListener() {}, setAttribute() {} });
globalThis.document = { createElement: el, createElementNS: el };
const { buildHouse } = await import('../../site/house.js');
const { plan } = await import('../../site/equipment.js');
const F = 0.3048, IN = F / 12;
const hd = JSON.parse(fs.readFileSync('site/models/house.json'));
const eq = JSON.parse(fs.readFileSync('site/models/equipment.json'));
const house = buildHouse(hd, { skip: new Set((eq.items || []).map((it) => it.id)) });
house.root.updateMatrixWorld(true);
const meshes = []; house.root.traverse((o) => { if (o.isMesh) { o.material && (o.material.side = THREE.DoubleSide); meshes.push(o); } });
const U = { 0: [0, -1], 90: [1, 0], 180: [0, 1], 270: [-1, 0] };
const snapP = 'model/data/electrical_snap.json';
const old = fs.existsSync(snapP) ? JSON.parse(fs.readFileSync(snapP)) : {};
const rc = new THREE.Raycaster(), out = { ...old }, rows = [];
for (const it of eq.items) {
  if (!it.id.startsWith('elec_') || !['outlet', 'switch_plate', 'data_jack'].includes(it.builder) || !(it.facing in U)) continue;
  const [ux, uy] = U[it.facing], [x, y, z] = it.at, zc = z + it.size[1] / 24;
  const p0 = plan(x, y, zc), dir = plan(x + ux, y + uy, zc).sub(p0).normalize();
  rc.set(p0.clone().addScaledVector(dir, 8 * IN), dir.clone().negate()); rc.far = 14 * IN;
  const hit = rc.intersectObjects(meshes, false).find((h) => !/furniture/i.test(h.object.name));   // a bed or a bench in front is not the wall
  if (!hit) { rows.push([it.id, it.src, null]); continue; }
  const gap = (8 * IN - hit.distance) / F;                 // ft from the plate's back to the surface, along the facing
  rows.push([it.id, it.src, gap * 12, hit.object.name + '/' + (hit.object.material.name || '')]);
  if (Math.abs(gap) > 0.002) out[it.src] = Math.round(((old[it.src] || 0) + gap) * 1000) / 1000;
}
const bad = rows.filter((r) => r[2] === null || Math.abs(r[2]) > 0.05);
for (const r of rows) if (bad.includes(r)) console.log(`${r[0].padEnd(18)} ${String(r[1]).padEnd(14)} ${r[2] === null ? 'no wall within 6 in' : r[2].toFixed(2) + ' in  ' + r[3]}`);
console.log(`${rows.length} wall devices, ${bad.length} off their wall by more than 0.05 in`);
if (process.argv.includes('--write')) { fs.writeFileSync(snapP, JSON.stringify(out, null, 1) + '\n'); console.log('wrote', snapP); }
