// Seat every ceiling light on its ceiling: node tools/electrical/ceiling.mjs  (from the repo root)
// Most ceilings here slope (the north and south roofs), so a light needs both the ceiling height and its tilt. For each
// baked ceiling light in site/models/manifest.json ("Light <room> <n>") this casts a ray straight up from just above that
// level's floor and takes the first drywall face pointing down. It writes model/data/ceiling_lights.json:
//   name: [ceiling z in ft, slope] where slope is the ceiling's rise per foot going north (the ceiling fans use the same).
// Rerun make_equipment.py after.
import { register } from 'node:module';
register('../three_hooks.mjs', import.meta.url);
const fs = await import('node:fs');
const THREE = await import('three');
const el = () => ({ style: {}, getContext: () => new Proxy({}, { get: () => () => ({ addColorStop() {} }) }), addEventListener() {}, removeEventListener() {}, setAttribute() {} });
globalThis.document = { createElement: el, createElementNS: el };
const { buildHouse } = await import('../../site/house.js');
const { plan } = await import('../../site/equipment.js');
const F = 0.3048;
const hd = JSON.parse(fs.readFileSync('site/models/house.json'));
const man = JSON.parse(fs.readFileSync('site/models/manifest.json'));
const house = buildHouse(hd, {});
house.root.updateMatrixWorld(true);
const meshes = []; house.root.traverse((o) => { if (o.isMesh) { o.material && (o.material.side = THREE.DoubleSide); meshes.push(o); } });
const loftFloor = (hd.meta.rooms.find((r) => r.name === 'Loft') || {}).floor || 10;
const rc = new THREE.Raycaster(), out = {};
for (const L of man.lights || []) {
  if (!/^Light /.test(L.name)) continue;
  const x = L.pos[0] / F, y = -L.pos[1] / F, z0 = L.room === 'Loft' ? loftFloor + 0.5 : 0.5;
  rc.set(plan(x, y, z0), new THREE.Vector3(0, 1, 0)); rc.far = 40;
  const hit = rc.intersectObjects(meshes, false).find((h) => {
    if (!/drywall/i.test(h.object.material.name || '')) return false;
    const n = h.face.normal.clone().transformDirection(h.object.matrixWorld);
    return n.y < -0.5;
  });
  if (!hit) { console.log(L.name, 'no ceiling found'); continue; }
  const n = hit.face.normal.clone().transformDirection(hit.object.matrixWorld);
  const z = hit.point.y / F, slope = n.z / n.y;          // plan y runs along three z, so going north is -z
  out[L.name] = [Math.round(z * 1000) / 1000, Math.round(slope * 10000) / 10000];
  const was = L.pos[2] / F;
  console.log(`${L.name.padEnd(24)} ceiling ${z.toFixed(2)} ft, slope ${(slope * 12).toFixed(2)}:12` + (Math.abs(was - z) > 0.3 ? `  (baked light was at ${was.toFixed(2)})` : ''));
}
fs.writeFileSync('model/data/ceiling_lights.json', JSON.stringify(out, null, 1) + '\n');
console.log('wrote model/data/ceiling_lights.json');
