// Clash audit: node tools/clash_audit.mjs  (from the repo root, after model/make_house.py and model/make_equipment.py)
// Local review tool, NOT run in CI: many overlaps are on purpose (drywall sheets lapped at corners, trim let into a wall,
// a grille's collar inside its boot), so it lists every place two different objects pass INTO each other and leaves the
// judgement to a person. tools/clash_allow.txt holds the pairs already reviewed and accepted, each with its reason.
//
// It builds the house and the equipment with the walkthrough's own code (as tools/coplanar_audit.mjs does), groups the
// triangles by the object they came from (a house.json record, an equipment item, duct or pipe run, a baked .glb node),
// and for every pair of objects whose bounds overlap finds the triangle pairs that cross. A crossing only counts as a
// clash when a point of one surface lies more than --depth mm INSIDE the other solid, so faces that merely touch (a stud
// standing on a plate, a strap nailed to a plate face, a duct notched through a plate with clearance) pass.
//   --depth <mm>  how far one solid must reach into the other (default 3 mm)
//   --all         also list pairs tools/clash_allow.txt accepts
//   --glb         also check the baked furniture .glb parts (slow, and their meshes are not all closed)
//   --json        print the findings as JSON
//   --only <re>   only pairs whose "a vs b" text matches this regular expression
// Exit code is always 0 unless the build fails: this is a list to read, not a gate.
import { register } from 'node:module';
register('./three_hooks.mjs', import.meta.url);
const fs = await import('node:fs');
const THREE = await import('three');
const el = () => ({ style: {}, getContext: () => new Proxy({}, { get: () => () => ({ addColorStop() {} }) }), addEventListener() {}, removeEventListener() {}, setAttribute() {} });
globalThis.document = { createElement: el, createElementNS: el };
const { buildHouse } = await import('../site/house.js');
const { buildEquipment, cullBaked } = await import('../site/equipment.js');
const { MeshBVH } = await import('three-mesh-bvh');

const _warn = console.warn;                      // three-mesh-bvh warns on every coplanar triangle pair; those are touching faces, not clashes
console.warn = (...m) => { if (!/coplanar/.test(String(m[0]))) _warn(...m); };
const argv = process.argv;
const arg = (k, d) => { const i = argv.indexOf(k); return i > 0 ? argv[i + 1] : d; };
const DEPTH = Number(arg('--depth', 3)) / 1000;
const ONLY = arg('--only', null) ? new RegExp(arg('--only')) : null;
const F = 0.3048;
const hd = JSON.parse(fs.readFileSync('site/models/house.json'));
const eq = JSON.parse(fs.readFileSync('site/models/equipment.json'));
const house = buildHouse(hd, { skip: new Set((eq.items || []).map((it) => it.id)) });
const equip = buildEquipment(eq);
const overlays = []; equip.root.traverse((o) => { if (o.userData.deckOverlay) overlays.push(o); });
for (const o of overlays) o.removeFromParent();

// what each object is, for the report and for the allow list
const KIND = {};
for (const r of hd.records) KIND[r.id] = `house ${r.kind}`;
for (const it of eq.items || []) KIND[it.id] = `equipment ${(it.category || it.builder || '').toLowerCase()}`;
for (const d of eq.ducts || []) KIND[d.id] = 'duct';
for (const r of eq.runs || []) KIND[r.id] = 'pipe';
if (eq.trusses) KIND[eq.trusses.id] = 'floor trusses';

const baked = [];
if (argv.includes('--glb')) {
  const { GLTFLoader } = await import('three/addons/loaders/GLTFLoader.js');
  const { MeshoptDecoder } = await import('three/addons/libs/meshopt_decoder.module.js');
  const loader = new GLTFLoader(); loader.setMeshoptDecoder(MeshoptDecoder);
  loader.register(() => ({ name: 'no_textures', loadTexture: () => Promise.resolve(null) }));
  const man = JSON.parse(fs.readFileSync('site/models/manifest.json'));
  for (const part of man.parts || []) {
    const name = part.name || part.file.replace(/\.glb$/, '');
    if (!/^furniture/i.test(name)) continue;
    const buf = fs.readFileSync(`site/models/${part.file}`);
    const gl = await loader.parseAsync(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength), '');
    const r = gl.scene; r.name = name; baked.push(r);
    const gone = new Set(hd.meta.replace_nodes || []), moves = hd.meta.move_nodes || {}, drop = [];
    r.traverse((o) => {
      if (gone.has(o.name)) drop.push(o);
      const mv = moves[o.name];
      if (mv) { o.position.x += mv[0] * F; o.position.z += mv[1] * F; if (mv[2]) o.rotateY(THREE.MathUtils.degToRad(mv[2])); if (mv[3]) o.position.y += mv[3] * F; }
    });
    for (const o of drop) o.removeFromParent();
    r.updateMatrixWorld(true);
    const culls = (hd.meta.cull || []).filter((c) => new RegExp('^' + (c.parts || 'furniture'), 'i').test(name));
    if (culls.length) cullBaked([r], [{ cull: culls }]);
  }
  if (baked.length) cullBaked(baked, eq.items);
}

// triangles in world metres, grouped by object, each tagged with its material
const groups = new Map();
const va = new THREE.Vector3(), vb = new THREE.Vector3(), vc = new THREE.Vector3();
function collect(root, who) {
  root.updateMatrixWorld(true);
  root.traverse((m) => {
    if (!m.isMesh || !m.geometry) return;
    const g = m.geometry, P = g.attributes.position, I = g.index, n = I ? I.count / 3 : P.count / 3;
    const mats = Array.isArray(m.material) ? m.material : [m.material];
    const inst = m.isInstancedMesh ? m.count : 0, im = new THREE.Matrix4(), mw = new THREE.Matrix4();
    for (let ii = 0; ii < Math.max(1, inst); ii++) {
      mw.copy(m.matrixWorld); if (inst) { m.getMatrixAt(ii, im); mw.multiply(im); }
      for (let t = 0; t < n; t++) {
        const k = (j) => (I ? I.getX(t * 3 + j) : t * 3 + j);
        va.fromBufferAttribute(P, k(0)).applyMatrix4(mw); vb.fromBufferAttribute(P, k(1)).applyMatrix4(mw); vc.fromBufferAttribute(P, k(2)).applyMatrix4(mw);
        let mat = mats[0];
        if (mats.length > 1 && g.groups.length) { const gr = g.groups.find((q) => q.start <= t * 3 && t * 3 < q.start + q.count); if (gr) mat = mats[gr.materialIndex]; }
        const w = who(m, t); if (!w) continue;
        const G = groups.get(w) || groups.set(w, { who: w, pos: [], mats: [] }).get(w);
        G.pos.push(va.x, va.y, va.z, vb.x, vb.y, vb.z, vc.x, vc.y, vc.z); G.mats.push(mat ? mat.name || '?' : '?');
      }
    }
  });
}
collect(house.root, (m, t) => {
  const u = m.userData; if (u.equipId) return u.equipId;
  const st = u.ranges; if (!st) return null; let lo = 0, hi = st.length - 1;
  while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (st[mid] <= t) lo = mid; else hi = mid - 1; }
  return house.recs[u.rangeRecs[lo]].id;
});
collect(equip.root, (m) => m.userData.equipId || m.name || 'equipment');
for (const r of baked) collect(r, (m) => { KIND[`${r.name}.glb ${m.name}`] = 'baked furniture'; return `${r.name}.glb ${m.name}`; });

const G = [...groups.values()];
for (const g of G) {
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(g.pos), 3));
  g.geo = geo; geo.computeBoundingBox(); g.box = geo.boundingBox.clone();
  g.kind = KIND[g.who] || (g.who.includes('.glb') ? 'baked furniture' : '?');
}
const bvhOf = (g) => g.bvh || (g.bvh = new MeshBVH(g.geo, { maxDepth: 64, indirect: true }));

// inside a solid: the winding number along a ray (exits minus entries) is positive. Three skewed rays vote.
const ray = new THREE.Ray(), DIRS = [[1, 0.0131, 0.0071], [-0.0093, 1, 0.0117], [0.0059, -0.0107, -1]].map((d) => new THREE.Vector3(...d).normalize());
const tA = new THREE.Vector3(), tB = new THREE.Vector3(), tC = new THREE.Vector3(), nn = new THREE.Vector3();
function winding(g, p, d) {
  ray.set(p, d);
  let w = 0;
  for (const h of bvhOf(g).raycast(ray, THREE.DoubleSide)) w += Math.sign(h.face.normal.dot(d));
  return w;
}
const inside = (g, p) => DIRS.filter((d) => winding(g, p, d) > 0).length >= 2;
const cp = {};
function depthIn(g, p) {                      // how deep p sits inside g (0 if outside)
  if (!inside(g, p)) return 0;
  bvhOf(g).closestPointToPoint(p, cp);
  return cp.distance;
}

// broad phase: sweep along x over the object bounds
const PAD = 0.0005;
G.sort((a, b) => a.box.min.x - b.box.min.x);
const cand = [];
for (let i = 0; i < G.length; i++) {
  const A = G[i];
  for (let j = i + 1; j < G.length && G[j].box.min.x < A.box.max.x - PAD; j++) {
    const B = G[j];
    if (B.box.min.y < A.box.max.y - PAD && A.box.min.y < B.box.max.y - PAD && B.box.min.z < A.box.max.z - PAD && A.box.min.z < B.box.max.z - PAD) cand.push([A, B]);
  }
}

const allow = (fs.existsSync('tools/clash_allow.txt') ? fs.readFileSync('tools/clash_allow.txt', 'utf8') : '').split('\n')
  .map((l) => l.replace(/\s+#.*$/, '').trim()).filter((l) => l && !l.startsWith('#')).map((l) => new RegExp(l));

// narrow phase: crossing triangle pairs, then probe a few mm along each surface either side of the crossing line
const seg = new THREE.Line3(), dir = new THREE.Vector3(), side = new THREE.Vector3(), mid = new THREE.Vector3(), pr = new THREE.Vector3();
const STEPS = [0.004, 0.012, 0.03, 0.06];
// heights in plan ft: under the flat ceilings (rooms), the truss space up to the attic deck top, and above it
const CEIL = eq.trusses ? eq.trusses.z0 : 9.0, DECK = CEIL + ((eq.trusses ? eq.trusses.depth_in + eq.trusses.deck_in : 12.625) / 12);
const zoneOf = (z) => (z < CEIL - 0.01 ? 'rooms' : z <= DECK + 0.01 ? 'trusses' : 'attic');
const found = [];
for (const [A, B] of cand) {
  const label = `${A.who} [${A.kind}] vs ${B.who} [${B.kind}]`;
  if (ONLY && !ONLY.test(label)) continue;
  const hits = []; let n = 0;
  bvhOf(A).bvhcast(bvhOf(B), new THREE.Matrix4(), {
    intersectsTriangles(t1, t2, i1, i2) {
      if (!t1.intersectsTriangle(t2, seg)) return false;
      if (seg.distance() < 1e-5) return false;
      n++;
      seg.getCenter(mid); dir.subVectors(seg.end, seg.start).normalize();
      for (const [tri, other, mi] of [[t1, B, i1], [t2, A, i2]]) {
        tri.getNormal(nn); side.crossVectors(nn, dir).normalize();
        for (const s of STEPS) for (const sg of [-1, 1]) {
          pr.copy(mid).addScaledVector(side, s * sg);
          if (!tri.containsPoint(pr)) continue;
          const d = depthIn(other, pr);
          if (d > DEPTH) { hits.push({ d, p: pr.clone(), into: other.who, mat: (other === B ? A : B).mats[mi] }); break; }
        }
      }
      return hits.length >= 12 || n > 4000;              // enough to know it is real
    },
  });
  if (!hits.length) continue;
  // one finding per height zone, so a rule can accept a duct inside a wall in the rooms or the truss space but not in the attic
  for (const zone of ['rooms', 'trusses', 'attic']) {
    const zh = hits.filter((h) => zoneOf(h.p.y / F) === zone);
    if (!zh.length) continue;
    const top = zh.reduce((u, v) => (v.d > u.d ? v : u)), lab = `${label} @${zone}`;
    const r = { a: A.who, ak: A.kind, b: B.who, bk: B.kind, zone, label: lab, depth_mm: Math.round(top.d * 1000), mats: [...new Set(zh.map((h) => h.mat))].slice(0, 4),
      at_plan_ft: [top.p.x / F, top.p.z / F, top.p.y / F].map((v) => +v.toFixed(2)) };
    r.allowed = allow.find((re) => re.test(lab)) ? true : false;
    found.push(r);
  }
}
found.sort((u, v) => v.depth_mm - u.depth_mm);
const show = found.filter((r) => argv.includes('--all') || !r.allowed);
if (argv.includes('--json')) console.log(JSON.stringify(show, null, 1));
else {
  for (const r of show) console.log(`${String(r.depth_mm).padStart(5)} mm  ${r.label}${r.allowed ? '  (allowed)' : ''}  near x ${r.at_plan_ft[0]} y ${r.at_plan_ft[1]} z ${r.at_plan_ft[2]}`);
  console.log(`${G.length} objects, ${cand.length} pairs with touching bounds, ${found.length} pass into each other, ${found.length - show.length} accepted in tools/clash_allow.txt, ${show.length} listed`);
}
