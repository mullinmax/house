// Cars and the EV charger in the garage, built in three.js like the appliances in equipment.js.
// Same local frame as every builder there: inches, +x to the car's right, +y up, +z out of the front, origin at the
// centre of the back (rear bumper) on the ground.
//
// A car body is a loft: cross sections every fraction of an inch along the length, each one shaped by the car's side
// profile (bottom, beltline, roof) and plan outline (rounded corners), with wheel arches cut into the lower sides.
// Lights, glass, chrome and grille are picked per face of the same surface, so nothing sits flush on the paint.
// The profiles were drawn from each maker's published dimensions and side photos; the overall length, width,
// height, wheelbase, track and tyre sizes are exact, the curves between them are close but not surveyed.
import * as THREE from 'three';
import { mat, labelMat } from './equipment.js';

// ---------------------------------------------------------------- the two cars
// u = inches from the rear bumper. Tables are [u, height] pairs, interpolated with a smooth curve.
// roof: the top of the greenhouse; where it is at or below the belt there is no cabin (hood, trunk).
// The tables were drawn for a 188.58 in body; stretch every u to the car's own length, keeping 0 at the rear bumper.
function squeezeU(c) {
  const k = c.L / 188.58, sq = (t) => t.map(([u, v]) => [u * k, v]);
  return { ...c, bottom: sq(c.bottom), belt: sq(c.belt), roof: sq(c.roof), sideGlass: sq(c.sideGlass), roofGlass: sq(c.roofGlass),
    windshield: c.windshield.map((u) => u * k), mirror: { ...c.mirror, u: c.mirror.u * k } };
}
const CARS = {
  // Tesla Model Y, 2020 to 2024 (Maxwell, 11/17/2026). 187.0 L x 75.6 W x 63.9 H, 113.8 wheelbase, 64.4 track, 255/45 R19.
  // The side profile tables were first drawn at the refresh's 188.6 in and are squeezed to 187.0 in by squeezeU().
  model_y: squeezeU({
    L: 187.0, W: 75.6, H: 63.9, wb: 113.8, rear: 37.6, track: [64.4, 64.4],
    tyre: { w: 10.04, rim: 19, dia: 28.04 }, wheel: 'aero', cornerF: 27, cornerR: 19,
    bottom: [[0, 18], [2, 14], [6, 10.5], [14, 8], [28, 6.6], [160, 6.6], [172, 7.4], [180, 9], [185, 12], [188.58, 16.5]],
    belt: [[0, 31], [1, 36.5], [2.5, 41], [5, 43.6], [9, 44.6], [30, 44.6], [60, 44], [100, 42.8], [125, 42], [140, 41.4], [152, 40.4],
           [165, 39.2], [175, 37.8], [181, 36.4], [184.5, 34], [187, 30], [188.58, 25]],
    roof: [[5, 43.6], [9, 46.5], [16, 51], [26, 56], [38, 60.2], [52, 62.9], [68, 63.9], [92, 63.9], [106, 62.9], [116, 60], [126, 54.5],
           [136, 47.5], [143, 42.5], [146, 40.6]],
    crown: 2.2, deckCrown: 1.4, greenIn: [0.86, 0.69],
    sideGlass: [[27, 92.5], [96.5, 137]], roofGlass: [[6.5, 143.5]], windshield: [116, 143.5],
    mirror: { u: 135.5, h: 45.5, out: 4.1 },
    paint: { color: 0x08090b, metal: 0.08, rough: 0.16, name: 'Solid Black' },
    // which surface faces get a light, lens or trim: (u, x, h) in inches, |x| from the centreline
    look(u, ax, h, L) {
      if (u > L - 16) {                                   // front
        if (h > 11.5 && h < 19.5 && ax < 22) return 'grille';                       // lower intake
      }
      if (u < 12) {                                       // rear
        if (h > 17 && h < 20 && ax > 22) return 'reflector';
        if (h > 13 && h < 17.5 && ax < 30) return 'diffuser';
      }
      return null;
    },
    lamps: [
      { end: 'front', x0: 18.5, x1: 34, lo: (x) => 33.0 + (x - 18.5) * 0.07, hi: (x) => 35.4 + (x - 18.5) * 0.12, m: 'headlamp', both: true },   // swept headlamps at the hood line
      { end: 'front', x0: 26, x1: 31.5, lo: () => 15.2, hi: () => 17.0, m: 'headlamp', both: true },                                     // fog lamps
      { end: 'rear', x0: 20.5, x1: 35, lo: (x) => 38.6 - (x - 20.5) * 0.04, hi: (x) => 41.6 + (x - 20.5) * 0.02, m: 'tail', both: true },     // tail lamps wrap the corners
    ],
    badges: [{ logo: 'T', end: 'front', h: 33.4, w: 3.0, hgt: 3.0, color: '#d6d8db' }, { logo: 'T', end: 'rear', h: 41.2, w: 3.4, hgt: 3.4, color: '#d6d8db' }],
    plate: { end: 'rear', h: 27.5 },
    handles: [],
  }),
  // Honda Insight, 2019 to 2022, Touring. 183.6 L x 71.6 W x 55.6 H, 106.3 wheelbase, 60.9 / 61.6 track, 215/50 R17.
  insight: {
    L: 183.6, W: 71.6, H: 55.6, wb: 106.3, rear: 40.4, track: [60.9, 61.6],
    tyre: { w: 8.46, rim: 17, dia: 25.46 }, wheel: 'split10', cornerF: 25, cornerR: 17,
    bottom: [[0, 16], [2, 12.5], [6, 9], [14, 6.5], [26, 5.5], [160, 5.5], [170, 6.3], [177, 8], [181.5, 10.5], [183.6, 14]],
    belt: [[0, 25], [1, 30.5], [2.5, 35], [5, 38], [9, 39.1], [24, 39.4], [40, 39.1], [70, 38.2], [100, 37], [125, 36], [140, 34.6],
           [155, 32.6], [168, 31], [176, 30], [180, 28.6], [182.5, 25.5], [183.6, 21]],
    roof: [[24, 39.4], [28, 41.4], [36, 45.6], [48, 50.6], [62, 54.1], [80, 55.6], [100, 55.4], [111, 53.6], [120, 49.6],
           [130, 43.8], [139, 38.2], [143, 35.4]],
    crown: 2.0, deckCrown: 1.6, greenIn: [0.87, 0.71],
    sideGlass: [[44, 87.5], [90.5, 128]], roofGlass: [[25, 61], [114, 143]], windshield: [114, 143],
    beltChrome: [44, 128],
    mirror: { u: 126.5, h: 39.5, out: 4.0 },
    paint: { color: 0x07080b, metal: 0.4, rough: 0.2, name: 'Crystal Black Pearl' },
    look(u, ax, h, L) {
      if (u > L - 16) {
        if (h > 14.5 && h < 27.6 && ax < 17 - (27.6 - h) * 0.25) return 'grille';
        if (h > 10.5 && h < 15 && ax > 24 && ax < 31) return 'grille';              // fog light pockets
      }
      if (u < 12) {
        if (h > 16 && h < 18 && ax > 24) return 'reflector';
      }
      return null;
    },
    lamps: [
      { end: 'front', x0: -19, x1: 19, lo: () => 27.7, hi: () => 28.6, m: 'chrome' },               // the chrome wing over the grille
      { end: 'front', x0: 18, x1: 32.5, lo: (x) => 27.6 + (x - 18) * 0.12, hi: (x) => 30.6 + (x - 18) * 0.07, m: 'headlamp', both: true },
      { end: 'rear', x0: 16, x1: 32.5, lo: (x) => 32.0 - (x - 16) * 0.02, hi: (x) => 36.6 - (x - 16) * 0.06, m: 'tail', both: true },
      { end: 'rear', x0: -15.5, x1: 15.5, lo: () => 32.7, hi: () => 33.2, m: 'chrome' },
    ],
    badges: [{ text: 'H', end: 'front', h: 24.5, w: 3.6, hgt: 2.9, font: 'bold 120px Arial Black, Helvetica, Arial, sans-serif', color: '#e2e4e6', frame: true },
             { text: 'H', end: 'rear', h: 34.6, w: 3.6, hgt: 2.9, font: 'bold 120px Arial Black, Helvetica, Arial, sans-serif', color: '#e2e4e6', frame: true },
             { text: 'INSIGHT', end: 'rear', h: 30.6, x: -16, w: 9, hgt: 1.1, font: 'bold 60px Helvetica, Arial, sans-serif', color: '#d9dbde' }],
    plate: { end: 'rear', h: 22.5 },
    handles: [{ u: 108, h: 33.2 }, { u: 70, h: 34.6 }],
  },
};

// ---------------------------------------------------------------- materials
const paintM = (p) => {
  const key = 'car paint ' + p.name;
  if (!MP[key]) {
    MP[key] = new THREE.MeshPhysicalMaterial({ color: p.color, metalness: p.metal, roughness: p.rough, clearcoat: 1, clearcoatRoughness: 0.06 });
    MP[key].name = 'Equip ' + key;
  }
  return MP[key];
};
const MP = {};
export function vehicleMaterials() { return Object.values(MP); }
const LOOK = {
  glass: () => mat('car glass', 0x0a0e12, 0.04, 0.6),
  lightbar: () => mat('car light bar', 0x2b3136, 0.08, 0.8),
  lightbar_rear: () => mat('car tail bar', 0x3a0608, 0.1, 0.3),
  headlamp: () => mat('car headlamp', 0x8e979d, 0.06, 0.9),
  tail: () => mat('car tail lamp', 0x5c0a0c, 0.1, 0.25),
  reflector: () => mat('car reflector', 0x4a0a0b, 0.3, 0.2),
  grille: () => mat('car grille', 0x111214, 0.65, 0.1),
  diffuser: () => mat('car diffuser', 0x15161a, 0.55, 0.1),
  chrome: () => mat('chrome', 0xd8dadc, 0.15, 1),
};
const tyreM = () => mat('tyre rubber', 0x151617, 0.88, 0);

// ---------------------------------------------------------------- profile helpers
function table(pts) {                                  // smooth monotone interpolation through [u, v] pairs (Fritsch Carlson)
  const n = pts.length, xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  const d = [], m = new Array(n).fill(0);
  for (let i = 0; i < n - 1; i++) d.push((ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i]));
  m[0] = d[0]; m[n - 1] = d[n - 2];
  for (let i = 1; i < n - 1; i++) m[i] = d[i - 1] * d[i] <= 0 ? 0 : (d[i - 1] + d[i]) / 2;
  for (let i = 0; i < n - 1; i++) {
    if (d[i] === 0) { m[i] = m[i + 1] = 0; continue; }
    const a = m[i] / d[i], b = m[i + 1] / d[i], s = a * a + b * b;
    if (s > 9) { const t = 3 / Math.sqrt(s); m[i] = t * a * d[i]; m[i + 1] = t * b * d[i]; }
  }
  return (x) => {
    if (x <= xs[0]) return ys[0];
    if (x >= xs[n - 1]) return ys[n - 1];
    let i = 0; while (x > xs[i + 1]) i++;
    const h = xs[i + 1] - xs[i], t = (x - xs[i]) / h, t2 = t * t, t3 = t2 * t;
    return (2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * h * m[i] + (-2 * t3 + 3 * t2) * ys[i + 1] + (t3 - t2) * h * m[i + 1];
  };
}
const inR = (u, rs) => rs.some(([a, b]) => u >= a && u <= b);

function carShape(c) {
  const bottom = table(c.bottom), belt = table(c.belt);
  const roofT = table(c.roof), r0 = c.roof[0][0], r1 = c.roof[c.roof.length - 1][0];
  const roof = (u) => (u <= r0 || u >= r1 ? -1 : roofT(u));
  const hwPlan = (u) => {                               // plan half width with rounded corners
    let hw = c.W / 2;
    const dr = u, df = c.L - u;
    if (dr < c.cornerR) hw += -c.cornerR + Math.sqrt(c.cornerR ** 2 - (c.cornerR - dr) ** 2);
    if (df < c.cornerF) hw += -c.cornerF + Math.sqrt(c.cornerF ** 2 - (c.cornerF - df) ** 2);
    return hw;
  };
  const R = c.tyre.dia / 2, cy = R - 0.25;              // tyres squash a quarter inch under the car's weight
  const axles = [{ u: c.rear, track: c.track[1] }, { u: c.rear + c.wb, track: c.track[0] }];
  const Ra = R + 1.9;                                   // wheel arch radius
  const xin = Math.min(...c.track) / 2 - c.tyre.w / 2 - 1.2;    // inner wall of the wheel well
  const arch = (u) => {
    for (const a of axles) { const d = Math.abs(u - a.u); if (d <= Ra) return cy + Math.sqrt(Ra * Ra - d * d); }
    return null;
  };
  return { bottom, belt, roof, hwPlan, R, cy, axles, Ra, xin, arch };
}

// one half section (right side), from the bottom centre round to the top centre: [x, h, kind]
const NL = 9, NU = 18;
function halfSection(c, S, u) {
  const b = S.bottom(u), t = S.belt(u), rf = S.roof(u), hw = S.hwPlan(u);
  const a = S.arch(u), well = a !== null;
  const pts = [];
  const xb = (x) => (well ? Math.min(x, S.xin) : x);
  pts.push([0, b, 'under'], [xb(hw * 0.6), b, 'under'], [xb(hw * 0.87), b + 0.35, 'under']);
  const span = t - b, yb = b + Math.min(2.6, span * 0.2), ys = t - Math.min(3.8, span * 0.26);
  const sx = (h) => hw * (0.972 + 0.028 * Math.sin(Math.PI * Math.min(1, Math.max(0, (h - yb) / (ys - yb)))));
  const ah = well ? Math.min(Math.max(a, yb), ys - 0.5) : yb;
  for (let i = 0; i < NL; i++) { const h = yb + (ah - yb) * i / (NL - 1); pts.push([well ? S.xin : sx(yb), h, well ? 'well' : 'lower']); }
  for (let i = 0; i < NU; i++) { const h = ah + (ys - ah) * i / (NU - 1); pts.push([sx(h), h, 'lower']); }
  const xs = sx(ys), xt = hw * 0.935;
  for (let k = 1; k <= 5; k++) { const th = k / 5 * Math.PI / 2; pts.push([xt + (xs - xt) * Math.cos(th), ys + (t - ys) * Math.sin(th), 'lower']); }
  const g = Math.max(0, rf - c.crown - t), re = t + g;
  const [gi0, gi1] = c.greenIn;
  for (let k = 0; k <= 6; k++) { const f = k / 6; pts.push([hw * (gi0 + (gi1 - gi0) * f) - (g > 0 ? 0 : 0), t + g * f, 'green']); }
  const crown = g > 0 ? c.crown : c.deckCrown, xr = hw * gi1;
  for (let k = 1; k <= 8; k++) { const th = k / 8 * Math.PI / 2; pts.push([xr * Math.cos(th), re + crown * Math.sin(th), 'top']); }
  return pts;
}

function stations(c, S) {
  const us = new Set();
  const add = (a, b, step) => { for (let u = a; u < b; u += step) us.add(+u.toFixed(3)); };
  add(0, 14, 0.3); add(14, c.L - 18, 1.2); add(c.L - 18, c.L, 0.3); us.add(c.L);
  for (const a of S.axles) {
    add(a.u - S.Ra, a.u + S.Ra, 0.6);
    for (const e of [-S.Ra, S.Ra]) { us.add(+(a.u + e).toFixed(3)); us.add(+(a.u + e + Math.sign(e) * 0.2).toFixed(3)); }
  }
  for (const r of [...c.sideGlass, ...c.roofGlass]) for (const e of r) us.add(e);
  return [...us].sort((p, q) => p - q);
}

// The body: one closed loft, faces sorted into paint, glass, lamps and trim.
function body(g, c) {
  const S = carShape(c);
  const U = stations(c, S);
  const rings = U.map((u) => {
    const h = halfSection(c, S, u);
    const left = h.slice(1, -1).reverse().map(([x, y, k]) => [-x, y, k]);
    return h.concat(left);                            // closed ring: bottom centre, right side, top centre, left side
  });
  const nC = rings[0].length;
  const pos = new Float32Array(U.length * nC * 3);
  U.forEach((u, i) => rings[i].forEach(([x, y], j) => pos.set([x, y, u], (i * nC + j) * 3)));
  const idx = [], quadKind = [];
  for (let i = 0; i < U.length - 1; i++) for (let j = 0; j < nC; j++) {
    const j2 = (j + 1) % nC, a = i * nC + j, b = i * nC + j2, cc = (i + 1) * nC + j, d = (i + 1) * nC + j2;
    idx.push(a, cc, b, b, cc, d);
    quadKind.push([i, j, j2]);
  }
  const full = new THREE.BufferGeometry();
  full.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  full.setIndex(idx);
  full.computeVertexNormals();
  // the right side's winding faces outward only if the ring runs counter clockwise seen from the front: check one normal
  let vol = 0;                                         // signed volume: positive when the faces point outward
  for (let k = 0; k < idx.length; k += 3) {
    const [a, b, cc] = [idx[k], idx[k + 1], idx[k + 2]].map((n) => [pos[n * 3], pos[n * 3 + 1], pos[n * 3 + 2]]);
    vol += a[0] * (b[1] * cc[2] - b[2] * cc[1]) - a[1] * (b[0] * cc[2] - b[2] * cc[0]) + a[2] * (b[0] * cc[1] - b[1] * cc[0]);
  }
  if (vol < 0) { for (let k = 0; k < idx.length; k += 3) { const t = idx[k + 1]; idx[k + 1] = idx[k + 2]; idx[k + 2] = t; } full.setIndex(idx); full.computeVertexNormals(); }
  const nrm = full.attributes.normal;

  const buckets = new Map();
  const put = (key, tri) => { if (!buckets.has(key)) buckets.set(key, []); buckets.get(key).push(...tri); };
  quadKind.forEach(([i, j, j2], q) => {
    const u = (U[i] + U[i + 1]) / 2;
    const p = (k) => [pos[k * 3], pos[k * 3 + 1], pos[k * 3 + 2]];
    const v = [i * nC + j, i * nC + j2, (i + 1) * nC + j, (i + 1) * nC + j2].map(p);
    const ax = Math.abs(v.reduce((s, w) => s + w[0], 0) / 4), h = v.reduce((s, w) => s + w[1], 0) / 4;
    const kind = rings[i][j][2], kind2 = rings[i][j2][2];
    let key = 'paint';
    const t = S.belt(u), rf = S.roof(u), re = t + Math.max(0, rf - c.crown - t);
    if (kind === 'green' && kind2 === 'green') {
      if (inR(u, c.sideGlass) && h > t + 0.7 && h < re - 0.9) key = 'glass';
      else if (c.beltChrome && u > c.beltChrome[0] && u < c.beltChrome[1] && h <= t + 0.7 && rf > t) key = 'chrome';
    } else if (kind === 'top' || kind2 === 'top' || (kind === 'green' && kind2 !== 'lower')) {
      if (inR(u, c.roofGlass) && rf > t + 0.5) key = 'glass';
    }
    if (kind === 'under' || kind2 === 'under' || [rings[i][j], rings[i][j2], rings[i + 1][j], rings[i + 1][j2]].some((r) => r[2] === 'well')) key = 'under';
    const l = c.look(u, ax, h, c.L);
    if (l && key !== 'under') key = l;
    put(key, idx.slice(q * 6, q * 6 + 6));
  });
  for (const [key, list] of buckets) {
    const ge = new THREE.BufferGeometry();
    const P = new Float32Array(list.length * 3), N = new Float32Array(list.length * 3);
    list.forEach((k, n) => { P.set([pos[k * 3], pos[k * 3 + 1], pos[k * 3 + 2]], n * 3); N.set([nrm.getX(k), nrm.getY(k), nrm.getZ(k)], n * 3); });
    ge.setAttribute('position', new THREE.BufferAttribute(P, 3)); ge.setAttribute('normal', new THREE.BufferAttribute(N, 3));
    ge.setAttribute('uv', new THREE.BufferAttribute(new Float32Array(list.length * 2), 2));
    const m = key === 'paint' ? paintM(c.paint) : key === 'under' ? mat('car underbody', 0x0d0e0f, 0.9, 0) : LOOK[key]();
    g.add(new THREE.Mesh(ge, m));
  }
  // flat end caps (the lowest part of each bumper)
  for (const [i, sign] of [[0, -1], [U.length - 1, 1]]) {
    const ring = [];
    for (const [x, y] of rings[i]) { const l = ring[ring.length - 1]; if (!l || Math.hypot(l.x - x, l.y - y) > 0.01) ring.push(new THREE.Vector2(x, y)); }
    if (ring.length > 2 && ring[0].distanceTo(ring[ring.length - 1]) < 0.01) ring.pop();
    if (THREE.ShapeUtils.isClockWise(ring)) ring.reverse();
    const tris = THREE.ShapeUtils.triangulateShape(ring, []);
    const P = [], u = U[i];
    for (const tr of tris) { const o = sign > 0 ? tr : [tr[0], tr[2], tr[1]]; for (const k of o) P.push(ring[k].x, ring[k].y, u); }
    const ge = new THREE.BufferGeometry(); ge.setAttribute('position', new THREE.Float32BufferAttribute(P, 3));
    ge.computeVertexNormals(); ge.setAttribute('uv', new THREE.Float32BufferAttribute(new Float32Array(P.length / 3 * 2), 2));
    g.add(new THREE.Mesh(ge, paintM(c.paint)));
  }
  return S;
}

// Where the body surface is at height h, a given x off the centreline, on the front or rear end: [u, slope du/dh]
function fits(c, S, u, x, h) {                       // is the plan point (x, u) at height h inside the body?
  const sec = halfSection(c, S, u);
  if (h < sec[0][1]) return false;
  let hi = -Infinity;
  for (let k = 0; k < sec.length - 1; k++) {          // the right half outline crosses height h where |x| fits
    const [x0, y0] = sec[k], [x1, y1] = sec[k + 1];
    if ((y0 - h) * (y1 - h) <= 0 && y0 !== y1) hi = Math.max(hi, x0 + (x1 - x0) * (h - y0) / (y1 - y0));
  }
  return hi >= Math.abs(x);
}
// u of the body surface seen from the front or rear end at (x, h): a coarse march, then bisection
function surfU(c, S, end, x, h) {
  const dir = end === 'rear' ? 1 : -1, start = end === 'rear' ? 0 : c.L;
  let prev = start;
  for (let u = start; dir > 0 ? u < c.L / 2 : u > c.L / 2; u += dir * 0.5) {
    if (fits(c, S, u, x, h)) {
      if (u === start) return u;
      let lo = prev, hi = u;
      for (let k = 0; k < 8; k++) { const m = (lo + hi) / 2; if (fits(c, S, m, x, h)) hi = m; else lo = m; }
      return hi;
    }
    prev = u;
  }
  return start;
}
function endPoint(c, S, end, x, h) {
  return [surfU(c, S, end, x, h), (surfU(c, S, end, x, h + 0.6) - surfU(c, S, end, x, h - 0.6)) / 1.2];
}
// A lamp or trim strip laid on the body's end, a hair proud of the paint: x from x0 to x1, between heights lo(x) and hi(x)
function strip(g, c, S, L, m) {
  const n = Math.max(6, Math.round(Math.abs(L.x1 - L.x0) / 0.8)), rows = 4, out = L.end === 'rear' ? -1 : 1, P = [];
  const grid = [];
  for (let i = 0; i <= n; i++) {
    const x = L.x0 + (L.x1 - L.x0) * i / n, row = [];
    for (let r = 0; r <= rows; r++) {
      const h = L.lo(x) + (L.hi(x) - L.lo(x)) * r / rows, u = surfU(c, S, L.end, x, h);
      const du = (surfU(c, S, L.end, x + 0.3, h) - surfU(c, S, L.end, x - 0.3, h)) / 0.6;   // plan slope of the outline
      const dh = (surfU(c, S, L.end, x, h + 0.3) - surfU(c, S, L.end, x, h - 0.3)) / 0.6;
      const nv = new THREE.Vector3(-du * out, -dh * out, 1).normalize().multiplyScalar(out);   // outward normal, roughly
      row.push(new THREE.Vector3(x, h, u).addScaledVector(nv, 0.12));
    }
    grid.push(row);
  }
  for (let i = 0; i < n; i++) for (let r = 0; r < rows; r++) {
    const a = grid[i][r], b = grid[i + 1][r], cc = grid[i][r + 1], d = grid[i + 1][r + 1];
    const quad = out * Math.sign(L.x1 - L.x0) > 0 ? [a, b, cc, cc, b, d] : [a, cc, b, b, cc, d];
    for (const v of quad) P.push(v.x, v.y, v.z);
  }
  const ge = new THREE.BufferGeometry(); ge.setAttribute('position', new THREE.Float32BufferAttribute(P, 3));
  ge.computeVertexNormals(); ge.setAttribute('uv', new THREE.Float32BufferAttribute(new Float32Array(P.length / 3 * 2), 2));
  g.add(new THREE.Mesh(ge, m));
}

function badge(g, c, S, bd, idx) {
  const x = bd.x || 0;
  const [u, slope] = endPoint(c, S, bd.end, x, bd.h);
  const W = 512, Hh = Math.max(64, Math.round(512 * bd.hgt / bd.w));
  const m = labelMat(`car badge ${c.paint.name} ${idx}`, W, Hh, (cx, w, h) => {
    if (bd.logo === 'T') {                              // the Tesla T: a curved bar over a tapering stem
      cx.fillStyle = bd.color; const W2 = w, H2 = h;
      cx.beginPath(); cx.moveTo(W2 * 0.04, H2 * 0.12); cx.quadraticCurveTo(W2 * 0.5, -H2 * 0.02, W2 * 0.96, H2 * 0.12);
      cx.lineTo(W2 * 0.93, H2 * 0.2); cx.quadraticCurveTo(W2 * 0.5, H2 * 0.1, W2 * 0.07, H2 * 0.2); cx.closePath(); cx.fill();
      cx.beginPath(); cx.moveTo(W2 * 0.12, H2 * 0.24); cx.quadraticCurveTo(W2 * 0.5, H2 * 0.16, W2 * 0.88, H2 * 0.24); cx.lineTo(W2 * 0.62, H2 * 0.3);
      cx.lineTo(W2 * 0.53, H2 * 0.98); cx.lineTo(W2 * 0.47, H2 * 0.98); cx.lineTo(W2 * 0.38, H2 * 0.3); cx.closePath(); cx.fill();
      return;
    }
    if (bd.frame) { cx.strokeStyle = bd.color; cx.lineWidth = w * 0.06; cx.beginPath(); cx.ellipse(w / 2, h / 2, w * 0.45, h * 0.44, 0, 0, Math.PI * 2); cx.stroke(); }
    cx.fillStyle = bd.color; cx.font = bd.font; cx.textAlign = 'center'; cx.textBaseline = 'middle';
    const scale = bd.frame ? 0.62 : 1;
    cx.save(); cx.translate(w / 2, h / 2); cx.scale(w / 512 * (bd.frame ? 1.1 : 1), h / Hh * scale * (bd.frame ? 3.4 : 1)); cx.fillText(bd.text, 0, 4); cx.restore();
  });
  const me = new THREE.Mesh(new THREE.PlaneGeometry(bd.w, bd.hgt), m);
  const out = bd.end === 'rear' ? -1 : 1;
  me.position.set(x, bd.h, u + out * 0.22);
  me.rotation.y = bd.end === 'rear' ? Math.PI : 0;
  me.rotation.x = -Math.atan(slope) * out * (bd.end === 'rear' ? -1 : 1);
  g.add(me);
}

function plate(g, c, S) {
  const p = c.plate; if (!p) return;
  const [u, slope] = endPoint(c, S, p.end, 0, p.h);
  const grp = new THREE.Group();
  const m = labelMat('car plate', 384, 192, (cx, w, h) => {
    cx.fillStyle = '#f2f1ea'; cx.fillRect(4, 4, w - 8, h - 8);
    cx.strokeStyle = '#1b2f63'; cx.lineWidth = 6; cx.strokeRect(6, 6, w - 12, h - 12);
    cx.fillStyle = '#b3262e'; cx.font = 'bold 30px Helvetica, Arial, sans-serif'; cx.textAlign = 'center'; cx.fillText('OHIO', w / 2, 42);
    cx.fillStyle = '#1b2f63'; cx.font = 'bold 82px Helvetica, Arial, sans-serif'; cx.fillText('HOME', w / 2, 140);
  });
  const back = new THREE.Mesh(new THREE.BoxGeometry(12.6, 6.6, 0.35), mat('plate frame', 0x0c0d0e, 0.5, 0.1));
  const face = new THREE.Mesh(new THREE.PlaneGeometry(12, 6), m);
  face.position.z = 0.3;
  grp.add(back, face);
  grp.position.set(0, p.h, u - 0.12);
  grp.rotation.y = Math.PI;
  grp.rotation.x = Math.atan(slope);
  g.add(grp);
}

// ---------------------------------------------------------------- wheels
// a solid of revolution; with thick = [dr, dy] an open profile gets a back face that far off and is closed into a solid
function lathe(profile, seg = 48, thick = null) {
  const p = thick ? [...profile, ...profile.slice().reverse().map(([r, y]) => [r + thick[0], y + thick[1]]), profile[0]] : profile;
  return new THREE.LatheGeometry(p.map(([r, y]) => new THREE.Vector2(r, y)), seg);
}
function wheel(c, S) {
  const g = new THREE.Group();                         // built with the axle along +y, outer face at +y, then turned
  const { w, rim } = c.tyre, R = S.R, rr = rim / 2 + 0.6, hw = w / 2;
  const tyre = [[rr, -hw * 0.82], [rr + 0.6, -hw * 0.9], [R - 1.6, -hw], [R - 0.5, -hw + 0.6], [R, -hw + 1.6], [R, hw - 1.6], [R - 0.5, hw - 0.6],
                [R - 1.6, hw], [rr + 0.6, hw * 0.9], [rr, hw * 0.82], [rr, -hw * 0.82]];   // closed, so the tyre is a solid
  const tm = new THREE.Mesh(lathe(tyre, 56), tyreM()); g.add(tm);
  // rim: a dished barrel and a face
  const rimR = rim / 2;
  if (c.wheel === 'aero') {                             // 19 in Tesla aero wheel: a grey, nearly flat cover with five soft spokes
    const face = mat('aero wheel grey', 0x3c4044, 0.35, 0.7), dark = mat('wheel dark', 0x16181a, 0.5, 0.4), silver = mat('wheel silver', 0xb9bcbf, 0.25, 0.9);
    g.add(new THREE.Mesh(lathe([[0.1, hw * 0.55], [rimR * 0.35, hw * 0.62], [rimR * 0.85, hw * 0.7], [rimR + 0.3, hw * 0.78], [rimR + 0.6, hw * 0.8]], 48, [0, -0.4]), face));
    g.add(new THREE.Mesh(lathe([[rimR + 0.5, hw * 0.7], [rimR + 0.5, -hw * 0.7]], 48, [-0.4, 0]), dark));
    for (let k = 0; k < 5; k++) {                       // five spokes in relief, slightly twisted
      const sp = new THREE.Mesh(new THREE.BoxGeometry(2.6, 0.6, rimR * 0.66), silver);
      const a = k * Math.PI * 2 / 5;
      sp.position.set(Math.sin(a) * rimR * 0.52, hw * 0.74, Math.cos(a) * rimR * 0.52); sp.rotation.y = a + 0.18;
      g.add(sp);
    }
    const cap = new THREE.Mesh(new THREE.CylinderGeometry(1.4, 1.4, 0.5, 24), dark); cap.position.y = hw * 0.62; g.add(cap);
  } else {                                              // Insight Touring 17 in: machined silver face, ten split spokes, black pockets
    const pocket = mat('wheel dark', 0x16181a, 0.5, 0.4), silver = mat('wheel machined', 0xc9cbcd, 0.22, 0.95);
    g.add(new THREE.Mesh(lathe([[0.1, hw * 0.35], [rimR + 0.6, hw * 0.55]], 48, [0, -0.4]), pocket));
    g.add(new THREE.Mesh(lathe([[rimR + 0.5, hw * 0.7], [rimR + 0.5, -hw * 0.7]], 48, [-0.4, 0]), pocket));
    g.add(new THREE.Mesh(lathe([[rimR - 0.6, hw * 0.78], [rimR + 0.6, hw * 0.82]], 48, [0, -0.3]), silver));     // the polished lip
    for (let k = 0; k < 10; k++) {
      const a = k * Math.PI * 2 / 10 + (k % 2 ? 0.1 : -0.1);
      const sp = new THREE.Mesh(new THREE.BoxGeometry(1.1, 0.7, rimR * 0.78), silver);
      sp.position.set(Math.sin(a) * rimR * 0.5, hw * 0.62, Math.cos(a) * rimR * 0.5); sp.rotation.y = a; sp.rotation.x = -0.12;
      g.add(sp);
    }
    const hub = new THREE.Mesh(new THREE.CylinderGeometry(2.6, 2.9, 1.2, 28), silver); hub.position.y = hw * 0.5; g.add(hub);
    const cap = new THREE.Mesh(new THREE.CylinderGeometry(1.3, 1.3, 0.3, 24), pocket); cap.position.y = hw * 0.5 + 0.7; g.add(cap);
  }
  // brake disc and caliper behind the spokes
  const disc = new THREE.Mesh(new THREE.CylinderGeometry(rimR * 0.78, rimR * 0.78, 1.1, 36), mat('brake disc', 0x6f7174, 0.45, 0.8)); disc.position.y = -0.5; g.add(disc);
  return g;
}

function mirror(g, c, S, side) {
  const m = c.mirror, t = S.belt(m.u), hw = S.hwPlan(m.u) * 0.9;
  const grp = new THREE.Group();
  const shell = new THREE.Mesh(new THREE.SphereGeometry(1, 24, 14), paintM(c.paint));
  shell.scale.set(m.out * 0.62, 2.7, 3.6); shell.position.set(m.out * 0.55, 0, 0); grp.add(shell);
  const glassM = new THREE.Mesh(new THREE.CircleGeometry(1, 24), LOOK.glass());
  glassM.scale.set(m.out * 0.55, 2.3, 1); glassM.position.set(m.out * 0.55, 0, -1.55); glassM.rotation.y = Math.PI; grp.add(glassM);
  const arm = new THREE.Mesh(new THREE.BoxGeometry(2.4, 1.2, 2.2), paintM(c.paint)); arm.position.set(0.2, -1.2, 0.6); grp.add(arm);
  grp.position.set(side * hw, Math.max(m.h, t + 2.6), m.u);
  if (side < 0) grp.scale.x = -1;
  g.add(grp);
}

export function buildCar(it) {
  const c = CARS[it.car];
  const g = new THREE.Group();
  const S = body(g, c);
  for (const a of S.axles) for (const side of [-1, 1]) {
    const wg = wheel(c, S);
    wg.rotation.z = -side * Math.PI / 2;                 // axle along x, outer face outward
    wg.position.set(side * a.track / 2, S.cy, a.u);
    g.add(wg);
  }
  for (const side of [-1, 1]) mirror(g, c, S, side);
  for (const hd of c.handles) for (const side of [-1, 1]) {
    const sec = halfSection(c, S, hd.u);
    let x = 0; for (const [xx, y] of sec) if (Math.abs(y - hd.h) < 3 && xx > x) x = xx;
    const me = new THREE.Mesh(new THREE.BoxGeometry(0.9, 1.25, 6.2), LOOK.chrome());
    me.position.set(side * (x + 0.25), hd.h, hd.u); g.add(me);
  }
  for (const L of c.lamps) {
    strip(g, c, S, L, LOOK[L.m]());
    if (L.both) strip(g, c, S, { ...L, x0: -L.x0, x1: -L.x1, lo: (x) => L.lo(-x), hi: (x) => L.hi(-x) }, LOOK[L.m]());
  }
  c.badges.forEach((bd, k) => badge(g, c, S, bd, k));
  plate(g, c, S);
  return g;
}

// ---------------------------------------------------------------- Tesla Universal Wall Connector
// 13.6 H x 6.1 W x 5.9 D in (Tesla install manual). White glass faceplate, light bar, 24 ft cable. The cable hangs in
// loops on a hook under a wall holster that holds the NACS handle. The holster and hook are ASSUMED accessories.
export function buildWallConnector(s) {
  const [w, h, d] = s, g = new THREE.Group();
  const UX = -4.5, UY = 22;                             // the unit, left of the holster, its base 22 in above the item origin
  const shellM = mat('UWC shell', 0xe3e4e2, 0.45, 0.05), glassM = mat('UWC white glass', 0xf4f4f1, 0.08, 0.1), dark = mat('UWC dark', 0x2a2c2e, 0.5, 0.2);
  // rounded back shell, tapering slightly toward the wall
  const shape = new THREE.Shape(); const r = 1.6, W = w, H = h;
  shape.moveTo(-W / 2 + r, 0); shape.lineTo(W / 2 - r, 0); shape.quadraticCurveTo(W / 2, 0, W / 2, r); shape.lineTo(W / 2, H - r);
  shape.quadraticCurveTo(W / 2, H, W / 2 - r, H); shape.lineTo(-W / 2 + r, H); shape.quadraticCurveTo(-W / 2, H, -W / 2, H - r);
  shape.lineTo(-W / 2, r); shape.quadraticCurveTo(-W / 2, 0, -W / 2 + r, 0);
  const shellGeo = new THREE.ExtrudeGeometry(shape, { depth: d - 1.0, bevelEnabled: true, bevelThickness: 0.35, bevelSize: 0.35, bevelSegments: 3, curveSegments: 6 });
  shellGeo.scale(0.94, 0.96, 1); shellGeo.translate(UX, UY + h * 0.02, 0.35);
  g.add(new THREE.Mesh(shellGeo, shellM));
  const face = new THREE.Mesh(new THREE.ExtrudeGeometry(shape, { depth: 0.3, bevelEnabled: true, bevelThickness: 0.1, bevelSize: 0.1, bevelSegments: 2, curveSegments: 6 }), glassM);
  face.position.set(UX, UY, d - 0.3); g.add(face);
  // light bar: a thin vertical strip down the faceplate's left edge, lit green while idle and plugged in. ASSUMED placement
  const lb = new THREE.Mesh(new THREE.BoxGeometry(0.28, h * 0.55, 0.12), new THREE.MeshStandardMaterial({ color: 0x5fd17a, emissive: 0x3fbf5f, emissiveIntensity: 0.9, roughness: 0.3 }));
  lb.material.name = 'Equip UWC light'; MP['uwc light'] = lb.material;
  lb.position.set(UX - w / 2 + 0.75, UY + h * 0.52, d + 0.17); g.add(lb);
  // cable gland at the bottom
  const gland = new THREE.Mesh(new THREE.CylinderGeometry(0.65, 0.8, 1.2, 16), dark); gland.position.set(UX, UY - 0.45, d * 0.55); g.add(gland);
  // holster with the NACS handle docked nose down, to the right
  const HX = 7.5, HY = 24;
  const hol = new THREE.Mesh(new THREE.BoxGeometry(3.2, 4.4, 3.4), dark); hol.position.set(HX, HY + 2.2, 1.7); g.add(hol);
  const handleM = mat('NACS handle', 0xd9dad8, 0.4, 0.05), handleDark = mat('NACS handle grip', 0x3a3c3f, 0.6, 0.1);
  const hb = new THREE.Mesh(new THREE.CapsuleGeometry(1.15, 6.2, 6, 14), handleM); hb.position.set(HX, HY + 7.2, 2.4); hb.rotation.z = 0.06; g.add(hb);
  const grip = new THREE.Mesh(new THREE.CapsuleGeometry(1.0, 2.6, 6, 12), handleDark); grip.position.set(HX + 0.25, HY + 9.4, 2.9); grip.scale.z = 0.9; g.add(grip);
  // the cable: out of the unit, down into the loops on the hook, and back up to the handle
  const cableM = mat('charge cable', 0x2b2d30, 0.6, 0.05), hookM = mat('hook steel', 0x2a2b2c, 0.4, 0.6);
  const HK = [3.5, 15.5];
  const hook = new THREE.Mesh(new THREE.BoxGeometry(2.6, 0.7, 3.8), hookM); hook.position.set(HK[0], HK[1], 1.9); g.add(hook);
  const tubeOf = (pts) => g.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts.map(([x, y, z]) => new THREE.Vector3(x, y, z))), 40, 0.42, 8), cableM));
  tubeOf([[UX, UY - 1, d * 0.55], [UX, UY - 4, 3.6], [UX + 1, HK[1] + 1.5, 3.6], [HK[0] - 1, HK[1] + 0.7, 3.4]]);
  for (let k = 0; k < 3; k++) {                         // the hanging loops, each a little longer than the last
    const len = 8.5 + k * 1.6, rx = 3.6 + k * 0.5, z = 2.6 + k * 0.85;
    const curve = new THREE.CatmullRomCurve3([[HK[0] - rx * 0.4, HK[1] + 0.4], [HK[0] - rx, HK[1] - len * 0.45], [HK[0] - rx * 0.4, HK[1] - len], [HK[0] + rx * 0.4, HK[1] - len],
      [HK[0] + rx, HK[1] - len * 0.45], [HK[0] + rx * 0.4, HK[1] + 0.4]].map(([x, y]) => new THREE.Vector3(x, y, z)), false, 'centripetal');
    g.add(new THREE.Mesh(new THREE.TubeGeometry(curve, 48, 0.42, 8), cableM));
  }
  tubeOf([[HK[0] + 1, HK[1] + 0.7, 4.8], [HX - 1.5, HY + 3, 5.4], [HX + 1.6, HY + 10.5, 4.4], [HX + 0.4, HY + 12.4, 2.5]]);
  return g;
}
