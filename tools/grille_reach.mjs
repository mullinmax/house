// Grille reach check: node tools/grille_reach.mjs  (from the repo root)
// Every register and grille in equipment.json should sit on the finished surface it serves: its back just behind the
// drywall face and its front standing proud, so it shows from the room. This builds the house with site/house.js,
// casts a ray from in front of each grille back toward the wall or ceiling, and reports how far the grille's front
// face is from that surface. Exit 1 if any front face is behind the surface (hidden) or floats off it.
//   --json   print every grille as JSON
import { register } from 'node:module';
register('./three_hooks.mjs', import.meta.url);
const fs = await import('node:fs');
const THREE = await import('three');
const el = () => ({ style: {}, getContext: () => new Proxy({}, { get: () => () => ({ addColorStop() {} }) }), addEventListener() {}, removeEventListener() {}, setAttribute() {} });
globalThis.document = { createElement: el, createElementNS: el };
const { buildHouse } = await import('../site/house.js');
const { plan } = await import('../site/equipment.js');

const F = 0.3048, IN = F / 12, T = 0.7 * IN;          // grille thickness, as equipment.js draws it
const hd = JSON.parse(fs.readFileSync('site/models/house.json'));
const eq = JSON.parse(fs.readFileSync('site/models/equipment.json'));
const house = buildHouse(hd, { skip: new Set((eq.items || []).map((it) => it.id)) });
house.root.updateMatrixWorld(true);
const meshes = []; house.root.traverse((o) => { if (o.isMesh) { o.material && (o.material.side = THREE.DoubleSide); meshes.push(o); } });
const DIR = { S: [0, 0, 1], N: [0, 0, -1], E: [1, 0, 0], W: [-1, 0, 0] };
const rc = new THREE.Raycaster();
const rows = [];
for (const dc of eq.ducts || []) for (const gr of dc.grilles || []) {
  // a wall grille faces its compass side; a flat one faces down from a 9 ft ceiling, or up from a floor above that (the loft, the attic deck)
  const up = !gr.wall && gr.at[2] > 9.5;
  const dirs = [gr.wall ? DIR[gr.wall] : up ? [0, 1, 0] : [0, -1, 0]];
  let best = null;
  for (const d of dirs) {
    const out = new THREE.Vector3(...d), front = plan(...gr.at).addScaledVector(out, T / 2);
    // start 4 in out in the room and look back: the first house surface hit is the face the grille should sit on
    rc.set(front.clone().addScaledVector(out, 4 * IN), out.clone().negate()); rc.far = 10 * IN;
    const hit = rc.intersectObjects(meshes, false)[0];
    if (!hit) continue;
    const gap = (hit.distance - 4 * IN) / IN;                // in: + = front face stands proud of the surface, - = behind it
    best = { gap, mat: Array.isArray(hit.object.material) ? '?' : hit.object.material.name, d };
  }
  const gap = best ? best.gap : null, mat = best ? best.mat : '';
  rows.push({ id: dc.id, at: gr.at, wall: gr.wall || (up ? 'floor' : 'ceiling'), gap, mat });
}
const bad = rows.filter((r) => r.gap !== null && (r.gap < 0.05 || r.gap > 1.0));
if (process.argv.includes('--json')) console.log(JSON.stringify(rows, null, 1));
else for (const r of rows) console.log(`${bad.includes(r) ? '!!' : 'ok'} ${r.id.padEnd(22)} ${r.wall.padEnd(7)} ${r.gap === null ? 'no surface' : r.gap.toFixed(2) + ' in'}  ${r.mat}`);
console.log(`${rows.length} grilles, ${bad.length} hidden behind or floating off their surface`);
process.exit(bad.length ? 1 : 0);
