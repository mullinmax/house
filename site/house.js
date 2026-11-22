// The house itself (slab, walls, roof, windows, doors, cabinets, trim, loft, garage, porch) for the walkthrough.
// Built here in three.js from site/models/house.json, which model/make_house.py writes from model/config.toml.
// Every record has an id and an info card: static shapes are merged into one mesh per layer and material, and each
// mesh keeps a list of which triangles belong to which record, so a click can still tell them apart.
// Plan feet: x east, y south from the outside NW slab corner, z up from the slab. Three.js: (x, z, y) * 0.3048.
import * as THREE from 'three';

const F = 0.3048;
const V = (x, y, z) => new THREE.Vector3(x * F, z * F, y * F);

// ---------------------------------------------------------------- materials
const KIND_LABEL = {
  wall: 'Wall', window: 'Window', door: 'Door', cabinet: 'Kitchen cabinet', roof: 'Roof', ceiling: 'Ceiling', floor: 'Floor', slab: 'Slab',
  trim: 'Trim', fixture: 'Fixture', gutter: 'Roof drainage', stair: 'Stair', railing: 'Railing', appliance: 'Appliance', structure: 'Structure', furniture: 'Furniture',
};

function slabCanvas(m) {
  // stained concrete: two tone mottling plus the saw cuts, drawn to plan scale (flipY off: canvas row 0 is plan y 0)
  const [W, D] = m.size, px = 2048, py = Math.round(px * D / W);
  const cv = document.createElement('canvas'); cv.width = px; cv.height = py;
  const g = cv.getContext('2d');
  g.fillStyle = m.color; g.fillRect(0, 0, px, py);
  let seed = 7; const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  const c2 = new THREE.Color(m.color2), c1 = new THREE.Color(m.color);
  for (const [n, r0, r1, a] of [[260, 30, 110, 0.10], [700, 10, 40, 0.08], [1600, 3, 12, 0.06]]) {
    for (let i = 0; i < n; i++) {
      const x = rnd() * px, y = rnd() * py, r = r0 + rnd() * (r1 - r0);
      const c = rnd() < 0.55 ? c2 : c1.clone().lerp(new THREE.Color(0xffffff), 0.12);
      const gr = g.createRadialGradient(x, y, 0, x, y, r);
      gr.addColorStop(0, `rgba(${c.r * 255 | 0},${c.g * 255 | 0},${c.b * 255 | 0},${a * 2})`); gr.addColorStop(1, 'rgba(0,0,0,0)');
      g.fillStyle = gr; g.fillRect(x - r, y - r, 2 * r, 2 * r);
    }
  }
  // saw cuts: both diagonals of a square grid with a point at cut_origin
  const s = m.cut_spacing, [ox, oy] = m.cut_origin, k = px / W;
  g.strokeStyle = 'rgba(25,12,8,0.55)'; g.lineWidth = Math.max(1, 0.012 * k);
  const L = W + D, step = s * Math.SQRT2;            // diamonds: lines at 45 degrees through points spaced s*sqrt2 apart
  g.beginPath();
  for (let t = -Math.ceil(L / step) - 1; t <= Math.ceil(L / step) + 1; t++) {
    const c = ox + oy + t * step;                     // x + y = c
    g.moveTo((c - 0) * k, 0); g.lineTo((c - D) * k, D * k);
    const d = ox - oy + t * step;                     // x - y = d
    g.moveTo(d * k, 0); g.lineTo((d + D) * k, D * k);
  }
  if (m.cut_pattern !== 'diamond') { g.beginPath(); for (let x = ox % s; x < W; x += s) { g.moveTo(x * k, 0); g.lineTo(x * k, D * k); } for (let y = oy % s; y < D; y += s) { g.moveTo(0, y * k); g.lineTo(W * k, y * k); } }
  g.stroke();
  const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; t.flipY = false; t.anisotropy = 4;
  t.repeat.set(1 / (W * F), 1 / (D * F));
  return t;
}

// brick pavers: a 90 degree herringbone (the default) or running bond, drawn in metres so the face UVs (metres) tile it.
// One canvas holds 4 x 4 pattern repeats with every brick a slightly different clay colour.
function brickCanvas(m) {
  const [L, W] = m.brick, per = 2 * L, reps = 4, S = per * reps;          // herringbone repeats every 2 brick lengths (L = 2W)
  const px = 1024, k = px / S, joint = Math.max(1, 0.012 * k);
  const cv = document.createElement('canvas'); cv.width = cv.height = px;
  const g = cv.getContext('2d');
  g.fillStyle = '#6b6156'; g.fillRect(0, 0, px, px);                     // sand in the joints
  let seed = 11; const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  const base = new THREE.Color(m.color);
  const brick = (x, y, w, h) => {
    const c = base.clone().offsetHSL((rnd() - 0.5) * 0.02, (rnd() - 0.5) * 0.12, (rnd() - 0.5) * 0.12);
    g.fillStyle = `#${c.getHexString()}`;
    for (const ox of [-px, 0, px]) for (const oy of [-px, 0, px])         // wrap round the edges so the canvas tiles
      g.fillRect(x * k + ox + joint / 2, y * k + oy + joint / 2, w * k - joint, h * k - joint);
  };
  const n = Math.round(S / W);
  if (m.pattern === 'herringbone') {
    // cells of W: H_k covers x [k, k+2], y [k, k+1]; V_k covers x [k, k+1], y [k+1, k+3]; the strip repeats every 4 cells down
    for (let s = -n; s < 2 * n; s += 4) for (let c = -n; c < 2 * n; c++) {
      const x = c * W, y = (c + s) * W;
      if (x > S + L || y > S + L || x < -L - W || y < -L - W) continue;
      brick(x, y, L, W); brick(x, y + W, W, L);
    }
  } else {
    for (let r = 0; r < n; r++) for (let c = -1; c < S / L + 1; c++) brick(c * L + (r % 2) * L / 2, r * W, L, W);
  }
  const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 8;
  t.repeat.set(1 / (S * F), 1 / (S * F));                                 // UVs are metres
  return t;
}

const texCache = {};
function tex(file, srgb, tile) {
  const key = `${file}|${tile}`;
  if (texCache[key]) return texCache[key];
  const t = new THREE.TextureLoader().load(`models/textures/${file}`);
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 4;
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  t.repeat.set(1 / tile, 1 / tile);                         // UVs are in metres, tile is metres per repeat
  return (texCache[key] = t);
}

function makeMaterials(defs) {
  const out = {};
  for (const [name, d] of Object.entries(defs)) {
    const p = { color: new THREE.Color(d.color), roughness: d.rough ?? 0.5, metalness: d.metal ?? 0, side: THREE.DoubleSide };
    if (d.opacity !== undefined && d.opacity < 1) Object.assign(p, { transparent: true, opacity: d.opacity, depthWrite: false });
    if (d.canvas === 'slab') { p.map = slabCanvas(d); p.color = new THREE.Color(0xffffff); }   // the canvas already holds the stain colour
    else if (d.canvas === 'brick') { p.map = brickCanvas(d); p.color = new THREE.Color(0xffffff); }
    else if (d.map) p.map = tex(d.map, true, d.tile || 1);
    if (d.normal) { p.normalMap = tex(d.normal, false, d.tile || 1); p.normalScale = new THREE.Vector2(d.normal_scale ?? 1, d.normal_scale ?? 1); }
    const m = new THREE.MeshStandardMaterial(p);
    m.name = name; m.userData.grain = d.grain || '';
    out[name] = m;
  }
  return out;
}

// ---------------------------------------------------------------- geometry sink
// One bucket per (group, material). Triangles are pushed in metres, flat shaded, with UVs in metres projected on the
// face's dominant plane; wood grain (the texture's v) runs along the piece's longest side.
class Bucket {
  constructor(mat) { this.mat = mat; this.pos = []; this.nor = []; this.uv = []; this.starts = []; this.recs = []; this.tris = 0; }
  mark(ri) { if (this.recs[this.recs.length - 1] !== ri) { this.starts.push(this.tris); this.recs.push(ri); } }
}
const _e1 = new THREE.Vector3(), _e2 = new THREE.Vector3(), _n = new THREE.Vector3();
function tri(bk, a, b, c, long) {
  _e1.subVectors(b, a); _e2.subVectors(c, a); _n.crossVectors(_e1, _e2);
  const len = _n.length(); if (len < 1e-12) return;
  _n.divideScalar(len);
  const ax = Math.abs(_n.x), ay = Math.abs(_n.y), az = Math.abs(_n.z);
  let uA, vA;                                          // axes (0 x, 1 y, 2 z) for u and v
  if (ay >= ax && ay >= az) { uA = 0; vA = 2; } else if (ax >= az) { uA = 2; vA = 1; } else { uA = 0; vA = 1; }
  if (long !== undefined && long !== vA && long === uA) { const t = uA; uA = vA; vA = t; }
  for (const p of [a, b, c]) {
    bk.pos.push(p.x, p.y, p.z); bk.nor.push(_n.x, _n.y, _n.z);
    bk.uv.push(p.getComponent(uA), p.getComponent(vA));
  }
  bk.tris++;
}
const HEX_FACES = [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]];
function longAxis(pts) {
  const bb = new THREE.Box3().setFromPoints(pts), s = bb.getSize(new THREE.Vector3());
  return s.x >= s.y && s.x >= s.z ? 0 : s.y >= s.z ? 1 : 2;
}
// six sided solid: faces turned outward from the centroid, so corner order does not matter
function hexa(get, pts, mats, grainOf) {
  const c = new THREE.Vector3(); for (const p of pts) c.add(p); c.divideScalar(8);
  const long = longAxis(pts);
  HEX_FACES.forEach((f, i) => {
    if (mats[i] === null) return;            // a face left out: a wall end buried in the piece it butts into
    const bk = get(mats[i]);
    const q = f.map((k) => pts[k]);
    const fc = new THREE.Vector3(); for (const p of q) fc.add(p); fc.divideScalar(4);
    _e1.subVectors(q[1], q[0]); _e2.subVectors(q[2], q[0]); _n.crossVectors(_e1, _e2);
    if (_n.lengthSq() < 1e-14) { _e1.subVectors(q[2], q[0]); _e2.subVectors(q[3], q[0]); _n.crossVectors(_e1, _e2); }
    const flip = _n.dot(fc.sub(c)) < 0;
    const lg = grainOf(mats[i]) === 'vertical' ? 1 : grainOf(mats[i]) === 'long' ? long : undefined;
    if (flip) { tri(bk, q[0], q[2], q[1], lg); tri(bk, q[0], q[3], q[2], lg); }
    else { tri(bk, q[0], q[1], q[2], lg); tri(bk, q[0], q[2], q[3], lg); }
  });
}
function boxPts(x0, x1, y0, y1, z0, z1) {
  return [V(x0, y0, z0), V(x1, y0, z0), V(x1, y1, z0), V(x0, y1, z0), V(x0, y0, z1), V(x1, y0, z1), V(x1, y1, z1), V(x0, y1, z1)];
}
// wall panel with openings: split into vertical strips at every hole edge and top vertex, solid between the holes
function panel(get, mat, fr, v0, v1, zbot, top, holes, grainOf) {
  const [ox, oy, ux, uy, vx, vy] = fr;
  const P = (u, v, z) => V(ox + u * ux + v * vx, oy + u * uy + v * vy, z);
  const uLo = Math.min(...top.map((s) => s[0])), uHi = Math.max(...top.map((s) => s[2]));
  const cuts = new Set([uLo, uHi]);
  for (const s of top) { cuts.add(s[0]); cuts.add(s[2]); }
  for (const h of holes) { if (h[0] > uLo && h[0] < uHi) cuts.add(h[0]); if (h[1] > uLo && h[1] < uHi) cuts.add(h[1]); }
  const us = [...cuts].sort((a, b) => a - b);
  for (let i = 0; i < us.length - 1; i++) {
    const ua = us[i], ub = us[i + 1];
    if (ub - ua < 1e-4) continue;
    const um = (ua + ub) / 2;
    const seg = top.find((s) => s[0] <= um && um <= s[2]);
    if (!seg) continue;
    const zAt = (u) => seg[1] + (seg[3] - seg[1]) * (u - seg[0]) / ((seg[2] - seg[0]) || 1);
    const zta = zAt(ua), ztb = zAt(ub);
    // a hole's optional 5th value is its head at h[1]: the head then slopes from h[3] at h[0] (transoms under the roof)
    const hTop = (h, u) => (h.length > 4 ? h[3] + (h[4] - h[3]) * (u - h[0]) / ((h[1] - h[0]) || 1) : h[3]);
    const hs = holes.filter((h) => h[0] < um && h[1] > um).map((h) => [Math.max(h[2], zbot), hTop(h, ua), hTop(h, ub)]).sort((a, b) => a[0] - b[0]);
    let ca = zbot, cb = zbot;
    const piece = (za0, zb0, za1, zb1) => hexa(get, [P(ua, v0, za0), P(ub, v0, zb0), P(ub, v1, zb0), P(ua, v1, za0),
      P(ua, v0, za1), P(ub, v0, zb1), P(ub, v1, zb1), P(ua, v1, za1)], Array(6).fill(mat), grainOf);
    for (const [h0, ta, tb] of hs) {
      if (h0 > Math.max(ca, cb) + 1e-4) piece(ca, cb, Math.min(h0, zta), Math.min(h0, ztb));
      ca = Math.max(ca, ta); cb = Math.max(cb, tb);
    }
    // compare each end on its own: a sloped head can sit higher than the wall top at the strip's other end (loft W40-40*)
    if (ca < zta - 1e-4 && cb < ztb - 1e-4) piece(ca, cb, zta, ztb);
  }
}
function polygon(get, mat, pts) {
  const bk = get(mat), q = pts.map((p) => V(...p));
  for (let i = 1; i < q.length - 1; i++) { tri(bk, q[0], q[i], q[i + 1]); tri(bk, q[0], q[i + 1], q[i]); }
}
function cylinder(get, mat, cx, cy, z0, z1, r0, r1, seg = 20) {
  const bk = get(mat), b = [], t = [];
  for (let i = 0; i < seg; i++) {
    const a = (i / seg) * Math.PI * 2;
    b.push(V(cx + Math.cos(a) * r0, cy + Math.sin(a) * r0, z0)); t.push(V(cx + Math.cos(a) * r1, cy + Math.sin(a) * r1, z1));
  }
  const cb = V(cx, cy, z0), ct = V(cx, cy, z1);
  for (let i = 0; i < seg; i++) {
    const j = (i + 1) % seg;
    tri(bk, b[i], t[i], t[j]); tri(bk, b[i], t[j], b[j]);
    tri(bk, cb, b[i], b[j]); tri(bk, ct, t[j], t[i]);            // caps wound to face out (down, up), like the sides
  }
}
function shape(get, s, grainOf) {
  switch (s[0]) {
    case 'b': hexa(get, boxPts(...s.slice(2, 8)), Array(6).fill(s[1]), grainOf); break;
    case 'x': {
      const a = s[2], pts = []; for (let i = 0; i < 8; i++) pts.push(V(a[i * 3], a[i * 3 + 1], a[i * 3 + 2]));
      hexa(get, pts, s[3] || Array(6).fill(s[1]), grainOf); break;
    }
    case 'w': panel(get, s[1], s[2], s[3], s[4], s[5], s[6], s[7], grainOf); break;
    case 'q': polygon(get, s[1], s[2]); break;
    case 'c': cylinder(get, s[1], ...s.slice(2, 8)); break;
  }
}

function bucketMesh(bk, name) {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(bk.pos, 3));
  g.setAttribute('normal', new THREE.Float32BufferAttribute(bk.nor, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(bk.uv, 2));
  g.computeBoundingBox(); g.computeBoundingSphere();
  const m = new THREE.Mesh(g, bk.mat);
  m.name = name;
  m.userData.house = true;
  m.userData.ranges = Int32Array.from(bk.starts);
  m.userData.rangeRecs = bk.recs.slice();
  return m;
}

// ---------------------------------------------------------------- view layers
// Which Layers checkbox a record answers to, so the finishes can come off and leave the framing (Maxwell, 11/20/2026).
// '' = always shown (slab, floors, loft ladder and railing).
export function toggleOf(r) {
  if (r.tog) return r.tog;
  if (r.layer === 'framing') return 'framing';
  if (r.kind === 'wall') return r.layer === 'shell' ? 'extwalls' : 'drywall';
  if (r.kind === 'door' || r.kind === 'window') return 'openings';
  if (r.kind === 'fixture' && r.layer === 'shell') return 'extwalls';     // wall lights, outlets and hose bibs on the siding
  if (r.kind === 'structure') return 'framing';
  if (['floor', 'stair', 'railing'].includes(r.kind)) return 'finish';    // attic deck, loft floor, ladder and railing: not built yet
  if (['cabinet', 'trim', 'fixture', 'appliance'].includes(r.kind) && r.layer !== 'shell' && r.layer !== 'roof') return 'finish';
  return '';
}

// ---------------------------------------------------------------- build
// skip: placeholder appliances to leave out (the equipment layer has the real ones).
// Returns { root, byId }: root holds the meshes, moving parts (glTF style "operable" pivots) and Spawn_<Room> nodes.
export function buildHouse(data, { skip = new Set() } = {}) {
  const mats = makeMaterials(data.materials);
  const grainOf = (m) => (mats[m] && mats[m].userData.grain) || '';
  const root = new THREE.Group(); root.name = 'house';
  const recs = [], byId = {};
  const LAYER_NAME = { roof: 'Roof', ceiling: 'ceiling', shell: 'House shell', interior: 'House interior', furniture: 'House furniture' };
  const buckets = new Map();
  let ri = -1;
  const getter = (group, tog) => (m) => {
    const key = `${group}|${tog}|${m}`;
    let bk = buckets.get(key);
    if (!bk) { bk = new Bucket(mats[m] || mats.Drywall); bk.group = group; bk.tog = tog; buckets.set(key, bk); }
    bk.mark(ri);
    return bk;
  };
  const opBuckets = [];
  for (const r of data.records) {
    if (r.placeholder_for && skip.has(r.placeholder_for)) continue;
    ri = recs.length;
    const rec = { ...r, category: KIND_LABEL[r.kind] || r.kind, box: new THREE.Box3() };
    delete rec.parts; delete rec.ops;
    recs.push(rec); byId[r.id] = rec;
    const tog = toggleOf(r);
    const get = getter(r.layer, tog);
    for (const s of r.parts || []) shape(get, s, grainOf);
    for (const o of r.ops || []) {
      const local = new Map();
      const getL = (m) => { let bk = local.get(m); if (!bk) { bk = new Bucket(mats[m] || mats.Drywall); local.set(m, bk); } bk.mark(ri); return bk; };
      for (const s of o.parts) shape(getL, s, grainOf);
      opBuckets.push({ o, r, local, ri });
    }
  }
  for (const bk of buckets.values()) {
    if (!bk.tris) continue;
    const m = bucketMesh(bk, `${LAYER_NAME[bk.group] || 'House'} ${bk.mat.name}`);
    m.userData.layer = bk.group;
    if (bk.tog) m.userData.tog = bk.tog;
    root.add(m);
  }
  // moving parts: a pivot node carrying the same extras the Blender export wrote (slide in Blender metres, Z up)
  for (const { o, r, local, ri: k } of opBuckets) {
    const piv = new THREE.Group(); piv.name = o.id;
    piv.position.copy(V(...o.pivot));
    const u = { operable: o.type };
    if (o.angle !== undefined) { u.open_angle = o.angle; u.axis = 'z'; }
    if (o.slide) u.slide = [o.slide[0] * F, -o.slide[1] * F, o.slide[2] * F];
    if (o.type === 'overhead') { u.door_h = o.height * F; u.inward = [o.inward[0], 0, o.inward[1]]; }
    Object.assign(piv.userData, u);
    for (const bk of local.values()) {
      if (!bk.tris) continue;
      const m = bucketMesh(bk, `${r.name} ${bk.mat.name}`);
      m.geometry.translate(-piv.position.x, -piv.position.y, -piv.position.z);
      m.userData.equipId = r.id; m.userData.layer = r.layer;
      const tg = toggleOf(r); if (tg) m.userData.tog = tg;
      piv.add(m);
    }
    root.add(piv);
  }
  // record bounds for the selection box and "go to"
  root.updateMatrixWorld(true);
  const p = new THREE.Vector3();
  root.traverse((m) => {
    if (!m.isMesh) return;
    const P = m.geometry.attributes.position, st = m.userData.ranges, rr = m.userData.rangeRecs;
    for (let s = 0; s < st.length; s++) {
      const box = recs[rr[s]].box, t0 = st[s], t1 = s + 1 < st.length ? st[s + 1] : P.count / 3;
      for (let v = t0 * 3; v < t1 * 3; v++) box.expandByPoint(p.fromBufferAttribute(P, v).applyMatrix4(m.matrixWorld));
    }
  });
  for (const [name, s] of Object.entries(data.spawns || {})) {
    const e = new THREE.Object3D(); e.name = `Spawn_${name}`;
    e.position.copy(V(s.pos[0], s.pos[1], s.pos[2]));
    e.userData.look = [s.look[0] * F, -s.look[1] * F, s.look[2] * F];      // Blender world point, as the viewer expects
    root.add(e);
  }
  return { root, byId, recs, materials: mats };
}

// Which record a ray hit: meshes merged from many records keep sorted triangle starts.
export function houseRecordAt(hit, house) {
  const u = hit.object.userData;
  if (!u.house || !house) return null;
  if (u.equipId) return house.byId[u.equipId] || null;
  const st = u.ranges; if (!st || hit.faceIndex === undefined || hit.faceIndex === null) return null;
  let lo = 0, hi = st.length - 1;
  while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (st[mid] <= hit.faceIndex) lo = mid; else hi = mid - 1; }
  return house.recs[u.rangeRecs[lo]] || null;
}
