// Layer check: node tools/layer_check.mjs  (from the repo root)
// Turning the Drywall layer off should take every bit of drywall with it. Builds the house the way the walkthrough does
// and fails (exit 1) on:
//   1. a drywall surface (material in house.js DRYWALL_MATS) that lands on any layer but Drywall,
//   2. a house.json material that looks like drywall (the plaster texture) but is not in DRYWALL_MATS,
//   3. a drywall looking material in the baked furniture or site .glb parts, which no layer can switch off.
// Added 11/27/2026 after the clerestory wall's drywall stayed up around the barn doors with Drywall off.
import { register } from 'node:module';
register('./three_hooks.mjs', import.meta.url);
const fs = await import('node:fs');
const el = () => ({ style: {}, getContext: () => new Proxy({}, { get: () => () => ({ addColorStop() {} }) }), addEventListener() {}, removeEventListener() {}, setAttribute() {} });
globalThis.document = { createElement: el, createElementNS: el };
const { buildHouse, DRYWALL_MATS } = await import('../site/house.js');
const { GLTFLoader } = await import('three/addons/loaders/GLTFLoader.js');
const { MeshoptDecoder } = await import('three/addons/libs/meshopt_decoder.module.js');

const hd = JSON.parse(fs.readFileSync('site/models/house.json'));
const eq = JSON.parse(fs.readFileSync('site/models/equipment.json'));
const bad = [];

// 1. every generated house mesh carrying a drywall material sits on the Drywall layer
const house = buildHouse(hd, { skip: new Set((eq.items || []).map((it) => it.id)) });
let drywallMeshes = 0;
house.root.traverse((m) => {
  if (!m.isMesh) return;
  for (const mt of [].concat(m.material)) {
    if (!DRYWALL_MATS.has(mt.name)) continue;
    drywallMeshes++;
    if (m.userData.tog !== 'drywall') {
      const recs = [...new Set((m.userData.rangeRecs || []).map((i) => house.recs[i] && house.recs[i].id))].filter(Boolean);
      bad.push(`${m.name}: on layer "${m.userData.tog || '(none)'}", not Drywall. Records: ${(recs.length ? recs : [m.userData.equipId]).join(', ')}`);
    }
  }
});

// 2. a new material with the drywall plaster texture has to join DRYWALL_MATS (or use another texture)
const RE_DRY = /drywall|plaster|gypsum|sheetrock|wallboard/i;
for (const [name, m] of Object.entries(hd.materials || {})) {
  if ((/plaster/i.test(m.map || '') || RE_DRY.test(name)) && !DRYWALL_MATS.has(name)) {
    bad.push(`material "${name}" looks like drywall (${m.map || name}) but is not in DRYWALL_MATS in site/house.js`);
  }
}

// 3. the baked .glb parts: nothing there can follow the Drywall layer, so no drywall may live there
const loader = new GLTFLoader(); loader.setMeshoptDecoder(MeshoptDecoder);
loader.register(() => ({ name: 'no_textures', loadTexture: () => Promise.resolve(null) }));
const man = JSON.parse(fs.readFileSync('site/models/manifest.json'));
const gone = new Set(hd.meta.replace_nodes || []);
for (const part of man.parts || []) {
  if (!/\.glb$/.test(part.file) || /^trees/i.test(part.file)) continue;
  const buf = fs.readFileSync(`site/models/${part.file}`);
  const gl = await loader.parseAsync(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength), '');
  gl.scene.traverse((o) => {
    if (!o.isMesh) return;
    for (let p = o; p; p = p.parent) if (gone.has(p.name)) return;      // replaced by the generated house
    for (const mt of [].concat(o.material)) if (mt && RE_DRY.test(mt.name || '')) bad.push(`${part.file} ${o.name || '(unnamed)'}: baked material "${mt.name}" looks like drywall`);
  });
}

for (const b of bad) console.log(b);
console.log(`${drywallMeshes} drywall meshes checked, ${bad.length} problem${bad.length === 1 ? '' : 's'}`);
process.exit(bad.length ? 1 : 0);
