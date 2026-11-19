// Things on the site that are there now: the trees Maxwell planted, the pad mounted transformer and the gravel drive.
// Built in three.js like the appliances in equipment.js, from items in models/equipment.json (model/make_equipment.py,
// positions in config.toml [site_plantings], traced from the 10/29/2026 drone photo).
// Same local frame as every builder there: inches, +x to the right, +y up, +z out of the front, origin at the centre of
// the back on the ground. Trees and shrubs are centred on their trunk instead.
//
// These materials stay out of equipMaterials(), so the height slice never cuts them (the site is not sliced either).
import * as THREE from 'three';

const MS = {};
function smat(name, color, rough = 0.9, metal = 0, extra = {}) {
  if (!MS[name]) { MS[name] = new THREE.MeshStandardMaterial({ color, roughness: rough, metalness: metal, ...extra }); MS[name].name = 'Site ' + name; }
  return MS[name];
}
export function plantingMaterials() { return Object.values(MS); }

// a small repeatable random number source, so every tree keeps its shape from load to load
function rng(seed) {
  let s = (seed * 2654435761) >>> 0 || 1;
  return () => { s ^= s << 13; s >>>= 0; s ^= s >>> 17; s ^= s << 5; s >>>= 0; return s / 4294967296; };
}
// value noise on a position, so vertices that share a spot (seams of a cone) move together and the surface stays closed
function hash3(x, y, z, seed) {
  const h = Math.sin(x * 12.9898 + y * 78.233 + z * 37.719 + seed * 4.581) * 43758.5453;
  return h - Math.floor(h);
}
function roughen(geo, amount, seed, radialOnly = true) {
  const p = geo.attributes.position, v = new THREE.Vector3();
  for (let i = 0; i < p.count; i++) {
    v.fromBufferAttribute(p, i);
    const k = (hash3(Math.round(v.x * 4) / 4, Math.round(v.y * 4) / 4, Math.round(v.z * 4) / 4, seed) - 0.5) * 2 * amount;
    const r = Math.hypot(v.x, v.z);
    if (radialOnly) { if (r > 1e-3) { v.x *= 1 + k / Math.max(r, 1); v.z *= 1 + k / Math.max(r, 1); } }
    else { const len = v.length() || 1; v.multiplyScalar(1 + k / len); }
    p.setXYZ(i, v.x, v.y, v.z);
  }
  geo.computeVertexNormals();
  return geo;
}
function put(g, geo, m, x = 0, y = 0, z = 0) {
  if (!geo.attributes.uv) geo.setAttribute('uv', new THREE.Float32BufferAttribute(new Float32Array(geo.attributes.position.count * 2), 2));
  const me = new THREE.Mesh(geo, m); me.position.set(x, y, z); g.add(me); return me;
}

// a low mound of bare soil and mulch round a new planting (the photo shows a dirt ring at each one). Its rim sinks
// 4 in, so it meets the ground on a slope without a gap.
function mulchRing(g, r) {
  const geo = new THREE.CylinderGeometry(r * 0.75, r, 6, 20, 1);
  put(g, roughen(geo, 1.2, 3), smat('mulch', 0x5b4a3a, 1), 0, -1.0, 0);
}

const BUILD = {
  // Norway spruce, white pine or yew at planting size. s = [crown width, height] inches
  conifer(s, it) {
    const g = new THREE.Group(), R = rng(it.seed || 1), W = s[0], H = s[1];
    const bark = smat('bark', 0x4a3a2c, 0.95);
    if (it.kind === 'yew') {                       // dense, rounded, a little wider than tall
      const leaf = smat('yew foliage', 0x1d3a22, 0.85);
      for (let k = 0; k < 4; k++) {
        const a = k * 1.7 + R() * 0.8, d = k ? W * 0.16 : 0;
        const rr = W * (k ? 0.3 : 0.38) * (0.9 + R() * 0.2);
        const geo = new THREE.IcosahedronGeometry(rr, 2); geo.scale(1, H / W * 1.25, 1);
        put(g, roughen(geo, rr * 0.12, (it.seed || 1) * 10 + k, false), leaf, Math.cos(a) * d, H * (k ? 0.38 : 0.5) * (0.95 + R() * 0.1), Math.sin(a) * d);
      }
      mulchRing(g, W * 0.6);
      return g;
    }
    put(g, new THREE.CylinderGeometry(0.55, 0.9, H * 0.35, 8), bark, 0, H * 0.13, 0);
    if (it.kind === 'pine') {                      // eastern white pine: soft, open whorls of long blue green needles
      const leaf = smat('white pine foliage', 0x3f6146, 0.8);
      const whorls = 5;
      for (let w = 0; w < whorls; w++) {
        const y = H * (0.16 + 0.66 * w / (whorls - 1)), spread = W * 0.5 * (1 - 0.7 * w / (whorls - 1));
        const n = w === whorls - 1 ? 1 : 6;
        for (let k = 0; k < n; k++) {
          const a = (k / n) * Math.PI * 2 + R() * 0.6 + w;
          const rr = Math.max(3.5, spread * 0.62) * (0.85 + R() * 0.3);
          const geo = new THREE.IcosahedronGeometry(rr, 1); geo.scale(1, 0.8, 1);
          const d = n === 1 ? 0 : spread * 0.5;
          put(g, roughen(geo, rr * 0.18, (it.seed || 1) * 31 + w * 7 + k, false), leaf, Math.cos(a) * d, y, Math.sin(a) * d);
        }
      }
      put(g, new THREE.ConeGeometry(2.2, H * 0.16, 6), leaf, 0, H * 0.92, 0);      // leader
      mulchRing(g, Math.max(12, W * 0.4));
      return g;
    }
    // Norway spruce: a dark green cone of stacked tiers, branch tips drooping a little
    const leaf = smat('spruce foliage', 0x1e3b27, 0.85);
    const tiers = 5;
    for (let t = 0; t < tiers; t++) {
      const f = t / tiers;
      const rBot = W * 0.5 * (1 - f * 0.82) * (0.94 + R() * 0.12);
      const h = H * 0.34, y0 = H * (0.12 + f * 0.7);
      const geo = new THREE.ConeGeometry(rBot, h, 12, 2);
      geo.rotateY(R() * Math.PI);
      put(g, roughen(geo, rBot * 0.16, (it.seed || 1) * 17 + t), leaf, 0, y0 + h / 2, 0);
    }
    mulchRing(g, Math.max(12, W * 0.4));
    return g;
  },

  // single phase pad mounted transformer: a green steel cabinet with two front doors on a concrete pad.
  // s = [width, height, depth] inches of the cabinet. The pad runs 5 in past it all round and sits 6 in into the ground.
  pad_transformer(s) {
    const g = new THREE.Group(), [W, H, D] = s;
    const green = smat('transformer green', 0x3c5a3e, 0.55, 0.2), conc = smat('pad concrete', 0xa9a7a1, 0.9);
    const PW = W + 10, PD = D + 10, PT = 10;
    put(g, new THREE.BoxGeometry(PW, PT, PD), conc, 0, 4 - PT / 2, D / 2);              // top of the pad 4 in above the ground
    const y0 = 4;
    put(g, new THREE.BoxGeometry(W, H - 1.5, D), green, 0, y0 + (H - 1.5) / 2, D / 2);
    put(g, new THREE.BoxGeometry(W + 0.8, 1.5, D + 0.8), green, 0, y0 + H - 0.75, D / 2);   // lid lip
    const dark = smat('transformer hardware', 0x22262a, 0.5, 0.6);
    const doorH = H - 6, dw = W / 2 - 0.4;
    for (const sx of [-1, 1]) {                                                         // the two doors, proud of the cabinet face
      put(g, new THREE.BoxGeometry(dw, doorH, 0.25), green, sx * (dw / 2 + 0.2), y0 + 2.5 + doorH / 2, D + 0.125);
    }
    put(g, new THREE.BoxGeometry(1.2, 5, 1.2), dark, 1.6, y0 + H * 0.55, D + 0.85);       // latch handle and pentahead bolt
    put(g, new THREE.CylinderGeometry(0.6, 0.6, 0.8, 10).rotateX(Math.PI / 2), dark, -1.6, y0 + H * 0.55, D + 0.65);
    const warn = smat('warning label', 0xd8b31c, 0.6);
    put(g, new THREE.BoxGeometry(6, 4, 0.1), warn, -dw / 2 - 0.2, y0 + H - 10, D + 0.3);  // "Warning, high voltage" label on the left door
    return g;
  },

  // the gravel drive: rows of cross sections laid on the ground, in plan feet (make_equipment.py samples the terrain)
  drive(s, it) {
    const g = new THREE.Group(), rows = it.rows || [];
    if (rows.length < 2) return g;
    const n = rows[0].length, pos = [], uv = [], idx = [];
    let along = 0;
    for (let r = 0; r < rows.length; r++) {
      if (r) { const a = rows[r][n >> 1], b = rows[r - 1][n >> 1]; along += Math.hypot(a[0] - b[0], a[1] - b[1]); }
      for (let c = 0; c < n; c++) {
        const [x, y, z] = rows[r][c];
        pos.push(x * 12, z * 12, y * 12);                        // place() scales inches to metres; facing 180 leaves plan axes as they are
        uv.push(c / (n - 1) * 3, along / 4);
      }
    }
    for (let r = 0; r < rows.length - 1; r++) for (let c = 0; c < n - 1; c++) {
      const a = r * n + c, b = a + 1, d = a + n, e = d + 1;
      idx.push(a, d, b, b, d, e);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
    geo.setIndex(idx); geo.computeVertexNormals();
    // which way is up: flip the winding if the first quad faces down
    if (geo.attributes.normal.getY(0) < 0) { for (let i = 0; i < idx.length; i += 3) { const t = idx[i + 1]; idx[i + 1] = idx[i + 2]; idx[i + 2] = t; } geo.setIndex(idx); geo.computeVertexNormals(); }
    put(g, geo, smat('drive gravel', 0xb1ab9f, 1, 0, { map: gravelTexture() }));
    return g;
  },
};
export { BUILD as plantingBuilders };

// crushed limestone: speckled grey, made once from random numbers (no canvas, so it builds in Node for the audits too)
let gravelTex = null;
function gravelTexture() {
  if (gravelTex) return gravelTex;
  const N = 128, d = new Uint8Array(N * N * 4), R = rng(99);
  for (let i = 0; i < N * N; i++) {
    const v = 175 + Math.floor((R() - 0.5) * 90) + (R() < 0.08 ? -60 : 0);
    d[i * 4] = v; d[i * 4 + 1] = v - 3; d[i * 4 + 2] = v - 9; d[i * 4 + 3] = 255;
  }
  gravelTex = new THREE.DataTexture(d, N, N);
  gravelTex.wrapS = gravelTex.wrapT = THREE.RepeatWrapping; gravelTex.colorSpace = THREE.SRGBColorSpace;
  gravelTex.magFilter = THREE.LinearFilter; gravelTex.minFilter = THREE.LinearMipmapLinearFilter; gravelTex.generateMipmaps = true;
  gravelTex.needsUpdate = true;
  return gravelTex;
}
