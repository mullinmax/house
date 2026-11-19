// Appliances, mechanical equipment and HVAC ducts for the walkthrough.
// Everything is built here in three.js from site/models/equipment.json, so it can change without a new Blender export.
// Sizes in the JSON are inches, positions are plan feet (x east, y south from the NW slab corner, z up from the slab).
// Each item is anchored at the centre of its BACK face on its base, and "facing" is the compass direction its
// front faces (0 north, 90 east, 180 south, 270 west).
// The builders follow the makers' product photos (finish, handles, controls, proportions) at the spec sheet sizes.
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { buildCar, buildWallConnector, vehicleMaterials } from './vehicles.js';

const F = 0.3048, IN = 0.0254;
export const plan = (x, y, z = 0) => new THREE.Vector3(x * F, z * F, y * F);

// ---------------------------------------------------------------- materials
const M = {};
export function mat(name, color, rough = 0.5, metal = 0, extra = {}) {
  if (!M[name]) { M[name] = new THREE.MeshStandardMaterial({ color, roughness: rough, metalness: metal, ...extra }); M[name].name = 'Equip ' + name; }
  return M[name];
}
// A canvas drawn once and used as a texture: control panels, logos, zone markings, brushed grain.
const TEX = {};
function canvasTex(key, w, h, draw) {
  if (!TEX[key]) {
    const c = document.createElement('canvas'); c.width = w; c.height = h;
    draw(c.getContext('2d'), w, h);
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4;
    TEX[key] = t;
  }
  return TEX[key];
}
// brushed grain: every column is one shade, so the texture tiles and stretches along the grain without seams
function grain(key, horizontal = false) {
  const t = canvasTex('grain ' + key, 512, 4, (c, w, h) => {
    let v = 0.5, seed = 7;
    const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    for (let x = 0; x < w; x++) {
      v = Math.min(1, Math.max(0, v + (rnd() - 0.5) * 0.6)); v += (0.5 - v) * 0.3;
      const s = Math.round(228 + v * 27); c.fillStyle = `rgb(${s},${s},${s})`; c.fillRect(x, 0, 1, h);
    }
  });
  if (horizontal && !TEX['grain h ' + key]) { const r = t.clone(); r.rotation = Math.PI / 2; r.center.set(0.5, 0.5); r.needsUpdate = true; TEX['grain h ' + key] = r; }
  const tex = horizontal ? TEX['grain h ' + key] : t;
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  return tex;
}
const steel = () => mat('stainless', 0xd6d8da, 0.34, 0.72, { map: grain('steel') });
const steelH = () => mat('stainless handle', 0xd2d4d6, 0.24, 0.95);
const steelSide = () => mat('fridge side grey', 0x8d9093, 0.5, 0.35);
const darkSteel = () => mat('dark stainless', 0x55595c, 0.35, 0.8);
const graphite = () => mat('carbon graphite', 0x6c7077, 0.4, 0.45, { map: grain('graphite') });
const graphiteDark = () => mat('carbon graphite trim', 0x2c2e31, 0.45, 0.5);
const glass = () => mat('black glass', 0x08090a, 0.05, 0.4);
const smoked = () => mat('smoked glass', 0x0b1016, 0.04, 0.6);
const white = () => mat('enamel white', 0xeeeeea, 0.35, 0.05);
const whitePlastic = () => mat('white plastic', 0xe9e9e4, 0.5, 0);
const greyPlastic = () => mat('grey plastic', 0x8a8d90, 0.55, 0);
const darkPlastic = () => mat('dark plastic', 0x232527, 0.6, 0);
const blackMolded = () => mat('black molded', 0x161718, 0.5, 0.05);
const charcoal = () => mat('disposer charcoal', 0x3b3f44, 0.45, 0.35);
const tankGrey = () => mat('tank grey', 0x9a9c9c, 0.42, 0.55);
const chrome = () => mat('chrome', 0xd8dadc, 0.15, 1);
const galv = () => mat('galvanized', 0xb1b6ba, 0.42, 0.8);
const cabinetGrey = () => mat('unit cabinet', 0xa7a8a3, 0.5, 0.3);
const seam = () => mat('panel seam', 0x4b4d4c, 0.7, 0.2);
const pe = () => mat('PE pipe', 0x1a1a1a, 0.55, 0);
const foam = () => mat('foam insulation', 0x202020, 0.9, 0);
const brass = () => mat('brass', 0xb8933a, 0.3, 1);
const red = () => mat('red', 0xa3221d, 0.45, 0.1);
const blue = () => mat('blue', 0x1f5fa8, 0.45, 0.1);
const copper = () => mat('copper', 0xb8734a, 0.3, 1);
const pumpRed = () => mat('pump red', 0x8f1f1f, 0.4, 0.3);
const plywood = () => mat('plywood', 0xc9a978, 0.8, 0);
const rubber = () => mat('rubber', 0x111111, 0.85, 0);
// a lit screen or printed panel: the drawing is both the colour and the glow
function screenMat(key, w, h, draw, glow = 0.9, rough = 0.12) {
  if (!M[key]) {
    const t = canvasTex(key, w, h, draw);
    M[key] = new THREE.MeshStandardMaterial({ map: t, emissive: 0xffffff, emissiveMap: t, emissiveIntensity: glow, roughness: rough, metalness: 0.2 });
    M[key].name = 'Equip ' + key;
  }
  return M[key];
}
// a logo or label with a clear background, laid a hair in front of a face
export function labelMat(key, w, h, draw) {
  if (!M[key]) {
    M[key] = new THREE.MeshStandardMaterial({ map: canvasTex(key, w, h, draw), transparent: true, alphaTest: 0.35, roughness: 0.5, metalness: 0.1,
      polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
    M[key].name = 'Equip ' + key;
  }
  return M[key];
}
const word = (text, color = '#fff', font = 'bold 44px Helvetica, Arial, sans-serif') => (c, w, h) => {
  c.fillStyle = color; c.font = font; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(text, w / 2, h / 2 + 2, w - 6);
};

// ducts get their own materials so the x-ray switch can change them without touching anything else
const DUCT = {
  supply: new THREE.MeshStandardMaterial({ color: 0xa9b8c6, roughness: 0.45, metalness: 0.6 }),
  return: new THREE.MeshStandardMaterial({ color: 0xc6aca9, roughness: 0.45, metalness: 0.6 }),
  transfer: new THREE.MeshStandardMaterial({ color: 0xc9c2a4, roughness: 0.6, metalness: 0.3 }),
  erv: new THREE.MeshStandardMaterial({ color: 0xb4c4a2, roughness: 0.6, metalness: 0.3 }),
  exhaust: new THREE.MeshStandardMaterial({ color: 0xbcb0c6, roughness: 0.5, metalness: 0.5 }),
  grille: new THREE.MeshStandardMaterial({ color: 0xf4f4f0, roughness: 0.5, metalness: 0.1 }),
  slot: new THREE.MeshStandardMaterial({ color: 0x55585a, roughness: 0.7, metalness: 0.2 }),
  flex_return: new THREE.MeshStandardMaterial({ color: 0x8f9396, roughness: 0.55, metalness: 0.35 }),    // uninsulated flex: silver grey jacket
};
const XRAY = { supply: 0x2f8be0, return: 0xe0503a, flex_return: 0xe0503a, transfer: 0xe0b23a, erv: 0x6cbf4a, exhaust: 0x9b59d0, grille: 0xffffff, slot: 0x222222 };
for (const [k, m] of Object.entries(DUCT)) m.name = 'Duct ' + k;

// ---------------------------------------------------------------- geometry helpers (inches, local frame)
// Local frame: +x to the right when facing the front, +y up, +z out of the front. Origin = back centre, bottom.
function add(g, geo, m, x, y, z) { const me = new THREE.Mesh(geo, m); me.position.set(x, y, z); g.add(me); return me; }
function box(g, w, h, d, m, x, y, z) {               // x, y, z = centre of the box
  return add(g, new THREE.BoxGeometry(w, h, d), m, x, y, z);
}
function cyl(g, r, h, m, x, y, z, axis = 'y', seg = 28, r2 = r) {
  const me = add(g, new THREE.CylinderGeometry(r, r2, h, seg), m, x, y, z);
  if (axis === 'x') me.rotation.z = Math.PI / 2;
  if (axis === 'z') me.rotation.x = Math.PI / 2;
  return me;
}
function ring(g, r, t, m, x, y, z, axis = 'z', seg = 40) {      // torus in the plane normal to axis
  const me = add(g, new THREE.TorusGeometry(r, t, 10, seg), m, x, y, z);
  if (axis === 'y') me.rotation.x = Math.PI / 2;
  if (axis === 'x') me.rotation.y = Math.PI / 2;
  return me;
}
function rrShape(w, h, r) {                           // rounded rectangle centred on the origin
  const s = new THREE.Shape(), x = -w / 2, y = -h / 2; r = Math.min(r, w / 2, h / 2);
  s.moveTo(x + r, y); s.lineTo(x + w - r, y); s.absarc(x + w - r, y + r, r, -Math.PI / 2, 0);
  s.lineTo(x + w, y + h - r); s.absarc(x + w - r, y + h - r, r, 0, Math.PI / 2);
  s.lineTo(x + r, y + h); s.absarc(x + r, y + h - r, r, Math.PI / 2, Math.PI);
  s.lineTo(x, y + r); s.absarc(x + r, y + r, r, Math.PI, 1.5 * Math.PI);
  return s;
}
function unitUV(geo) {                                // extrusions carry UVs in inches: stretch them to 0..1 like a box face
  geo.computeBoundingBox(); const b = geo.boundingBox, uv = geo.attributes.uv, p = geo.attributes.position, nrm = geo.attributes.normal;
  for (let i = 0; i < uv.count; i++) {
    const facesZ = Math.abs(nrm.getZ(i)) > 0.5;
    uv.setXY(i, facesZ ? (p.getX(i) - b.min.x) / (b.max.x - b.min.x || 1) : (p.getX(i) + p.getY(i) - b.min.x - b.min.y) / ((b.max.x - b.min.x) + (b.max.y - b.min.y) || 1),
      facesZ ? (p.getY(i) - b.min.y) / (b.max.y - b.min.y || 1) : (p.getZ(i) - b.min.z) / (b.max.z - b.min.z || 1));
  }
  return geo;
}
// a panel facing the front with rounded corners (doors, glass, badges): w x h, t thick, centred on x, y, z
function slab(g, w, h, t, m, x, y, z, r = 0.4) {
  const geo = unitUV(new THREE.ExtrudeGeometry(rrShape(w, h, r), { depth: t, bevelEnabled: false, curveSegments: 5 }));
  geo.translate(0, 0, -t / 2);
  return add(g, geo, m, x, y, z);
}
// a body with rounded vertical corners: w wide, h tall, d deep, centred on x, y, z
function column(g, w, h, d, m, x, y, z, r = 0.8) {
  const geo = unitUV(new THREE.ExtrudeGeometry(rrShape(w, d, r), { depth: h, bevelEnabled: false, curveSegments: 5 }));
  geo.translate(0, 0, -h / 2); geo.rotateX(-Math.PI / 2);
  return add(g, geo, m, x, y, z);
}
// a flat picture facing the front (or lying flat, facing up)
function plate(g, w, h, m, x, y, z, up = false) {
  const me = add(g, new THREE.PlaneGeometry(w, h), m, x, y, z);
  if (up) me.rotation.x = -Math.PI / 2;
  return me;
}
// a shallow dome facing the front, R across and bulge deep
function dome(g, R, bulge, m, x, y, z) {
  const geo = new THREE.SphereGeometry(R, 40, 8, 0, Math.PI * 2, 0, Math.PI / 2);
  geo.scale(1, bulge / R, 1); geo.rotateX(Math.PI / 2);
  return add(g, geo, m, x, y, z);
}
// a patch wrapped on a vertical cylinder of radius r: arc inches wide, h tall, centred at angle a (0 = front)
function wrap(g, r, arc, h, m, x, y, z, a = 0, seg = 10) {
  const th = arc / r;
  const geo = new THREE.CylinderGeometry(r, r, h, seg, 1, true, a - th / 2, th);
  return add(g, geo, m, x, y, z);
}
function bar(g, len, x, y, z, vertical, m = steelH(), r = 0.42, off = 1.5) {   // a stand-off bar handle on a front face at depth z
  if (vertical) {
    cyl(g, r, len, m, x, y, z + off, 'y', 14);
    for (const s of [-1, 1]) cyl(g, r * 0.8, off, m, x, y + s * (len / 2 - 1.4), z + off / 2, 'z', 10);
  } else {
    cyl(g, r, len, m, x, y, z + off, 'x', 14);
    for (const s of [-1, 1]) cyl(g, r * 0.8, off, m, x + s * (len / 2 - 1.4), y, z + off / 2, 'z', 10);
  }
}
// a strap handle that leaves the door at both ends and bows out between them
function bowHandle(g, x, y0, y1, z, bow, m, r = 0.42) {
  const c = new THREE.CubicBezierCurve3(new THREE.Vector3(x, y0, z - 0.2), new THREE.Vector3(x, y0 + (y1 - y0) * 0.12, z + bow * 1.25),
    new THREE.Vector3(x, y1 - (y1 - y0) * 0.12, z + bow * 1.25), new THREE.Vector3(x, y1, z - 0.2));
  const geo = new THREE.TubeGeometry(c, 20, r, 8);
  const me = add(g, geo, m, 0, 0, 0); me.scale.x = 1.5; me.position.x = x - x * 1.5;
  return me;
}
// tube between two points (any frame), radius r
function tube(g, a, b, r, m, seg = 14) {
  const d = new THREE.Vector3().subVectors(b, a), len = d.length();
  if (len < 1e-6) return null;
  const me = new THREE.Mesh(new THREE.CylinderGeometry(r, r, len, seg), m);
  me.position.copy(a).addScaledVector(d, 0.5);
  me.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.normalize());
  g.add(me); return me;
}
const V = (x, y, z) => new THREE.Vector3(x, y, z);
// rectangular duct between two points, w across (horizontal), h vertical; for vertical runs w and h are both horizontal
function rectDuct(g, a, b, w, h, m) {
  const d = new THREE.Vector3().subVectors(b, a), len = d.length();
  if (len < 1e-6) return null;
  const me = new THREE.Mesh(new THREE.BoxGeometry(w, h, len), m);
  me.position.copy(a).addScaledVector(d, 0.5);
  const dir = d.clone().normalize();
  if (Math.abs(dir.y) > 0.99) { me.rotation.x = Math.PI / 2; }        // vertical riser
  else me.lookAt(me.position.clone().add(new THREE.Vector3(dir.x, 0, dir.z)));
  g.add(me); return me;
}
// Every builder makes many small meshes. They are merged into one mesh per material when the item is placed,
// so a detailed appliance costs a handful of draw calls.
function bake(g) {
  g.updateMatrixWorld(true);
  const by = new Map();
  g.traverse((o) => { if (o.isMesh) { if (!by.has(o.material)) by.set(o.material, []); by.get(o.material).push(o); } });
  const out = new THREE.Group();
  for (const [m, list] of by) {
    const geos = list.map((o) => {
      const ge = o.geometry.index ? o.geometry.toNonIndexed() : o.geometry.clone();
      for (const k of Object.keys(ge.attributes)) if (!['position', 'normal', 'uv'].includes(k)) ge.deleteAttribute(k);
      ge.applyMatrix4(o.matrixWorld);
      if (o.matrixWorld.determinant() < 0) {                       // a mirrored piece: restore the winding
        const p = ge.attributes.position.array, n = ge.attributes.normal.array, u = ge.attributes.uv.array;
        for (let i = 0; i < p.length / 9; i++) for (const [arr, k] of [[p, 3], [n, 3], [u, 2]]) for (let c = 0; c < k; c++) { const a = i * 3 * k + k + c, b = a + k; const t = arr[a]; arr[a] = arr[b]; arr[b] = t; }
      }
      return ge;
    });
    out.add(new THREE.Mesh(mergeGeometries(geos), m));
    for (const ge of geos) ge.dispose();
  }
  return out;
}

// ---------------------------------------------------------------- drawings for screens and markings
const ink = (c, s, lw = 1) => { c.strokeStyle = s; c.lineWidth = lw; };
function drawCombo(c, w, h) {                         // GE Profile UltraFast Combo touch panel
  c.fillStyle = '#060708'; c.fillRect(0, 0, w, h);
  const cx = w * 0.3, cy = h * 0.56, R = h * 0.3;
  const g = c.createLinearGradient(cx - R, 0, cx + R, 0); g.addColorStop(0, '#19b5e6'); g.addColorStop(1, '#e6198f');
  ink(c, g, 7); c.beginPath(); c.arc(cx, cy, R, 0, Math.PI * 2); c.stroke();
  c.fillStyle = '#fff'; c.textAlign = 'center'; c.textBaseline = 'middle';
  c.font = '15px Helvetica, Arial, sans-serif'; c.fillText('NORMAL', cx, cy - R * 0.5);
  c.font = 'bold 36px Helvetica, Arial, sans-serif'; c.fillText('1:55', cx, cy - R * 0.12);
  c.fillStyle = '#1773c9'; c.fillRect(cx - R * 0.7, cy + R * 0.22, R * 0.68, R * 0.26);
  c.fillStyle = '#d81b79'; c.fillRect(cx + R * 0.02, cy + R * 0.22, R * 0.68, R * 0.26);
  c.fillStyle = '#fff'; c.font = '12px Helvetica, Arial, sans-serif'; c.fillText('Wash', cx - R * 0.36, cy + R * 0.36); c.fillText('Sensor Dry', cx + R * 0.36, cy + R * 0.36);
  c.font = '11px Helvetica, Arial, sans-serif'; c.fillText('SELECT', cx, cy + R * 0.7);
  ink(c, '#fff', 3); c.beginPath(); c.arc(w * 0.1, h * 0.14, 11, -Math.PI * 0.35, Math.PI * 1.35); c.moveTo(w * 0.1, h * 0.14 - 14); c.lineTo(w * 0.1, h * 0.14 - 2); c.stroke();
  c.font = 'bold 13px Helvetica, Arial, sans-serif';
  ink(c, '#19b5e6', 2); c.strokeRect(w * 0.18, h * 0.08, w * 0.11, h * 0.12); c.fillText('WASH', w * 0.235, h * 0.142);
  ink(c, '#e6198f', 2); c.strokeRect(w * 0.31, h * 0.08, w * 0.11, h * 0.12); c.fillText('DRY', w * 0.365, h * 0.142);
  c.beginPath(); c.moveTo(w * 0.46, h * 0.09); c.lineTo(w * 0.495, h * 0.14); c.lineTo(w * 0.46, h * 0.19); c.fill(); c.fillRect(w * 0.505, h * 0.09, 5, h * 0.1); c.fillRect(w * 0.525, h * 0.09, 5, h * 0.1);
  c.font = '11px Helvetica, Arial, sans-serif'; c.fillStyle = '#e8e8e8';
  const L = ['NORMAL', 'DELICATES', 'TOWELS', 'BULKY Bedding', 'SANITIZE with Oxi', 'DOWNLOADED'], Rr = ['ACTIVE WEAR', 'QUICK CYCLE', 'WHITES', 'RINSE & DRY', 'ECO COOL', 'SELF CLEAN'];
  for (let i = 0; i < 6; i++) {
    const y = h * (0.3 + i * 0.105);
    c.textAlign = 'left'; c.fillText(L[i], w * 0.025, y); c.textAlign = 'right'; c.fillText(Rr[i], w * 0.575, y);
  }
  c.textAlign = 'left';
  for (const [i, t] of ['Menu', 'SOIL', 'TEMP', 'SPIN'].entries()) { const x = w * (0.025 + (i ? 0.13 + i * 0.09 : 0)); c.fillText(t, x, h * 0.93); c.fillRect(x, h * 0.965, c.measureText(t).width, 1.5); }
  ink(c, '#19b5e6', 2); c.beginPath(); c.moveTo(w * 0.63, h * 0.27); c.lineTo(w * 0.63, h * 0.82); c.stroke();
  ink(c, '#e6198f', 2); c.beginPath(); c.moveTo(w * 0.975, h * 0.27); c.lineTo(w * 0.975, h * 0.82); c.stroke();
  c.font = 'bold 11px Helvetica, Arial, sans-serif'; c.fillStyle = '#19b5e6'; c.fillText('Wash Options', w * 0.65, h * 0.28);
  c.fillStyle = '#e6198f'; c.textAlign = 'right'; c.fillText('Dry Options', w * 0.96, h * 0.28);
  c.font = '10px Helvetica, Arial, sans-serif'; c.fillStyle = '#e8e8e8';
  const A = ['Smart Dispense Detergent', 'Smart Dispense Softener', 'PreWash', 'More Water', 'Extra Rinse'], B = ['Timed Dry', 'Dewrinkle', 'Wash Complete', 'More Dry', 'Wrinkle Care'];
  for (let i = 0; i < 5; i++) { const y = h * (0.38 + i * 0.105); c.textAlign = 'left'; c.fillText(A[i], w * 0.65, y); c.textAlign = 'right'; c.fillText(B[i], w * 0.96, y); }
}
function drawOvenPanel(c, w, h) {                     // Frigidaire Gallery wall oven: black glass with a small lit display in the middle
  c.fillStyle = '#050607'; c.fillRect(0, 0, w, h);
  const dw = h * 1.75, dh = h * 0.62, x0 = (w - dw) / 2, y0 = (h - dh) / 2;
  c.fillStyle = '#1b2026'; c.fillRect(x0, y0, dw, dh);
  c.fillStyle = '#f4f6f8'; c.textAlign = 'center'; c.textBaseline = 'middle';
  c.font = `${Math.round(h * 0.36)}px Helvetica, Arial, sans-serif`; c.fillText('6:04', w / 2, h / 2 + 1);
  c.strokeStyle = '#d7dadd'; c.lineWidth = 1.5;
  for (const sx of [-1, 1]) for (const k of [-1, 0, 1]) { c.beginPath(); c.arc(w / 2 + sx * (dw / 2 + h * 0.3), h / 2 + k * h * 0.2, h * 0.055, 0, Math.PI * 2); c.stroke(); }
}
function drawCooktop(c, w, h) {                       // LG CBIH3013BE zone markings, seen from above with the front at the bottom
  c.fillStyle = '#0b0b0c'; c.fillRect(0, 0, w, h);
  const X = (px) => (px - 12) / 566 * w, Y = (py) => (py - 8) / 388 * h, S = w / 566;
  ink(c, '#85888b', 1.5);
  for (const [x, y, r] of [[122, 101, 58], [327, 138, 91], [128, 275, 67], [480, 262, 60]]) {
    c.beginPath(); c.arc(X(x), Y(y), r * S, 0, Math.PI * 2); c.stroke();
    for (const [dx, dy] of [[1, 0], [0, 1]]) { c.beginPath(); c.moveTo(X(x) - dx * 5 * S, Y(y) - dy * 5 * S); c.lineTo(X(x) + dx * 5 * S, Y(y) + dy * 5 * S); c.stroke(); }   // centre cross
  }
  c.textBaseline = 'middle'; c.textAlign = 'center';
  c.fillStyle = '#e2392c'; c.font = `bold ${Math.round(11 * S)}px Helvetica, Arial, sans-serif`;
  for (const x of [262, 296, 330, 364]) c.fillText('5', X(x), Y(308));                         // one power level per zone
  c.fillStyle = '#a4a7aa'; c.font = `${Math.round(6.5 * S)}px Helvetica, Arial, sans-serif`;
  for (let i = 0; i < 10; i++) c.fillText(String(i), X(250 + i * 11.4), Y(328));              // level row
  c.fillText('Boost', X(374), Y(328));
  ink(c, '#a4a7aa', 1);
  for (const x of [262, 296, 330, 364]) { c.beginPath(); c.moveTo(X(x - 9), Y(317)); c.lineTo(X(x + 9), Y(317)); c.stroke(); }
  for (const x of [256, 284, 340, 368]) { c.beginPath(); c.arc(X(x), Y(343), 3.2 * S, 0, Math.PI * 2); c.stroke(); }   // power, lock, timer, pause
  c.fillText('0:00', X(312), Y(343));
  c.fillStyle = '#b9bcbf'; c.textAlign = 'left';
  c.font = `bold ${Math.round(11 * S)}px Helvetica, Arial, sans-serif`; c.fillText('LG', X(30), Y(378));
  c.textAlign = 'right'; c.font = `${Math.round(7.5 * S)}px Helvetica, Arial, sans-serif`; c.fillText('ThinQ', X(562), Y(378));
  c.textAlign = 'left'; c.font = `${Math.round(5.5 * S)}px Helvetica, Arial, sans-serif`; c.fillText('INDUCTION', X(26), Y(22));
}
function drawDispenser(c, w, h) {                     // Frigidaire Gallery in-door display: silver panel, white temperatures
  const g = c.createLinearGradient(0, 0, 0, h); g.addColorStop(0, '#8f9499'); g.addColorStop(1, '#7c8186');
  c.fillStyle = g; c.fillRect(0, 0, w, h);
  c.fillStyle = '#ffffff'; c.textAlign = 'center'; c.textBaseline = 'middle';
  c.font = `${Math.round(h * 0.3)}px Helvetica, Arial, sans-serif`;
  c.fillText('0°', w * 0.3, h * 0.36); c.fillText('37°', w * 0.7, h * 0.36);
  c.font = `${Math.round(h * 0.085)}px Helvetica, Arial, sans-serif`;
  const L = ['Water', 'Cubes', 'Crush', 'Light', 'Lock'];
  for (let i = 0; i < 5; i++) c.fillText(L[i], w * (0.14 + i * 0.18), h * 0.78);
}
function drawBeverage(c, w, h) {                      // what shows through the glass door: lit shelves of cans
  const g = c.createLinearGradient(0, 0, 0, h); g.addColorStop(0, '#16222e'); g.addColorStop(1, '#070b10');
  c.fillStyle = g; c.fillRect(0, 0, w, h);
  const rows = 5, top = h * 0.09, rh = (h * 0.9) / rows;
  for (let r = 0; r < rows; r++) {
    const y1 = top + (r + 1) * rh - 6, ch = rh * 0.66, cw = w / 9.4;
    for (let k = 0; k < 9; k++) {
      const x = w * 0.02 + k * (cw + 1.2), redCan = r % 2 === 0;
      const cg = c.createLinearGradient(x, 0, x + cw, 0);
      cg.addColorStop(0, redCan ? '#4a0d10' : '#0d2450'); cg.addColorStop(0.45, redCan ? '#b3212a' : '#2a62c4'); cg.addColorStop(1, redCan ? '#3a0a0c' : '#0a1b3d');
      c.fillStyle = cg; c.fillRect(x, y1 - ch, cw, ch);
      c.fillStyle = '#9aa0a6'; c.fillRect(x + 1, y1 - ch - 2, cw - 2, 3);
    }
    c.fillStyle = '#c9cdd1'; c.fillRect(0, y1, w, 3);
    c.fillStyle = '#20262c'; c.fillRect(0, y1 + 3, w, 3);
  }
  c.fillStyle = '#0a0c0e'; c.fillRect(0, 0, w, top * 0.8);
  c.fillStyle = '#e9e9e9'; c.font = 'bold 15px Helvetica, Arial, sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText('Hisense', w / 2, top * 0.4);
}
function drawFan(c, w, h) {                           // round fan guard on the water heater's heat pump section
  c.fillStyle = '#8f9192'; c.fillRect(0, 0, w, h);
  c.fillStyle = '#17181a'; c.beginPath(); c.arc(w / 2, h / 2, w * 0.46, 0, Math.PI * 2); c.fill();
  ink(c, '#55585b', 3);
  for (const r of [0.12, 0.22, 0.32, 0.42]) { c.beginPath(); c.arc(w / 2, h / 2, w * r, 0, Math.PI * 2); c.stroke(); }
  for (let k = 0; k < 12; k++) { const a = k * Math.PI / 6; c.beginPath(); c.moveTo(w / 2 + Math.cos(a) * w * 0.06, h / 2 + Math.sin(a) * w * 0.06); c.lineTo(w / 2 + Math.cos(a + 0.5) * w * 0.44, h / 2 + Math.sin(a + 0.5) * w * 0.44); c.stroke(); }
}
function drawHeaterPanel(c, w, h) {
  c.fillStyle = '#131416'; c.fillRect(0, 0, w, h);
  c.fillStyle = '#24313a'; c.fillRect(w * 0.14, h * 0.1, w * 0.72, h * 0.3);
  c.fillStyle = '#9fd8ff'; c.font = 'bold 22px Helvetica, Arial, sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText('120°F', w / 2, h * 0.25);
  c.fillStyle = '#d9d9d9'; c.font = '9px Helvetica, Arial, sans-serif';
  for (const [i, t] of ['Energy Saver', 'Heat Pump', 'High Demand', 'Electric', 'Vacation'].entries()) c.fillText(t, w / 2, h * (0.5 + i * 0.09));
}
const roundBadge = (bg, fg, text, font) => (c, w, h) => {
  c.fillStyle = bg; c.beginPath(); c.arc(w / 2, h / 2, w / 2 - 1, 0, Math.PI * 2); c.fill();
  c.fillStyle = fg; c.font = font; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(text, w / 2, h / 2 + 1, w - 10);
};
function printMat(key, w, h, draw, rough = 0.12, metal = 0.3) {      // a printed, unlit surface (cooktop glass, fan guard)
  if (!M[key]) { M[key] = new THREE.MeshStandardMaterial({ map: canvasTex(key, w, h, draw), roughness: rough, metalness: metal }); M[key].name = 'Equip ' + key; }
  return M[key];
}

// ---------------------------------------------------------------- builders
// Each returns a THREE.Group in inches (local frame above). s = item.size = [w, h, d].
// Proportions, handles, controls and finishes follow the makers' product photos; overall sizes are the spec sheet sizes.
// Ceiling fan (Maxwell, 11/19/2026). Local inches: origin at the canopy on the ceiling, everything hangs below it
// (negative y). size = [blade sweep, canopy to blade plane]; it.slope = ceiling rise per foot toward local +z (north).
// The blades are a separate "rotor" that buildEquipment keeps apart from the bake, so the walkthrough can spin them.
function ceilingFan(s, it) {
  const [sweep, drop] = s, g = new THREE.Group();
  const black = mat('fan matte black', 0x1b1c1d, 0.55, 0.25), oak = mat('fan blade oak', 0xb89468, 0.6, 0);
  const opal = mat('fan light opal', 0xf4f1ea, 0.4, 0, { emissive: 0xfff3dc, emissiveIntensity: 0.25 });
  const cnp = new THREE.Group(); cnp.rotation.x = Math.atan(-(it.slope || 0)); g.add(cnp);
  cyl(cnp, 2.9, 3.6, black, 0, -1.3, 0, 'y', 28, 2.6);                 // canopy, its top tucked half an inch into the ceiling
  const motorTop = -drop + 2.6;
  cyl(g, 0.5, Math.max(0.1, -2.6 - motorTop), black, 0, (motorTop - 2.6) / 2, 0, 'y', 12);   // downrod from the ball joint
  cyl(g, 1.2, 1.4, black, 0, -2.4, 0, 'y', 16);                         // ball joint
  cyl(g, 1.6, 1.0, black, 0, motorTop + 0.5, 0, 'y', 16);              // coupler
  cyl(g, 5.2, 2.6, black, 0, -drop + 1.3, 0, 'y', 36, 5.6);            // flat DC motor housing above the blades
  cyl(g, 5.6, 1.4, black, 0, -drop - 0.7, 0, 'y', 36, 4.6);             // and below them
  if (it.light) { cyl(g, 4.4, 0.8, black, 0, -drop - 1.7, 0, 'y', 32); cyl(g, 4.0, 0.5, opal, 0, -drop - 2.25, 0, 'y', 32); }
  const rotor = new THREE.Group(); rotor.name = 'rotor';
  const n = it.blades || 3, len = sweep / 2 - 5.2, bw = Math.min(5.5, 3.2 + sweep / 24);
  for (let k = 0; k < n; k++) {
    const arm = new THREE.Group(); arm.rotation.y = (k / n) * Math.PI * 2; rotor.add(arm);
    box(arm, 3.2, 0.5, 1.6, black, 5.6 + 1.2, 0, 0);                    // blade iron
    const b = box(arm, len, 0.3, bw, oak, 5.6 + len / 2, 0, 0); b.rotation.x = THREE.MathUtils.degToRad(12);   // pitched blade
  }
  rotor.userData.hub = [0, -drop, 0];
  g.userData.rotor = rotor;
  return g;
}

const BUILD = {
  ceiling_fan: ceilingFan,
  inline_fan(s) {                  // EC mixed flow inline duct fan: black round body along the duct (local z, air out the front), 8 in collars, mounting feet
    const [D, L] = s, g = new THREE.Group(), R = D / 2, blk = mat('booster black', 0x202224, 0.5, 0.2);
    cyl(g, R, L - 4.6, blk, 0, R, L / 2, 'z', 32);
    for (const z of [1.6, L - 1.6]) cyl(g, R - 0.7, 1.4, blk, 0, R, z + (z < L / 2 ? 0.7 : -0.7), 'z', 32, R - 1.6);
    for (const z of [0.5, L - 0.5]) cyl(g, 4.1, 1.0, galv(), 0, R, z, 'z', 24);
    ring(g, R + 0.1, 0.25, greyPlastic(), 0, R, L * 0.62, 'z', 36);
    box(g, 3.0, 1.4, 4.0, greyPlastic(), 0, D + 0.5, L * 0.45);              // terminal box on top
    box(g, 2.6, 2.0, 1.2, darkPlastic(), -R - 0.2, R, L * 0.7);              // speed control head on the room side
    return g;
  },
  zone_damper(s) {                 // 8 in round motorized damper: galvanized sleeve, bead rings, 24 V actuator on the side (room side, local -x)
    const [dia, L] = s, g = new THREE.Group(), r = dia / 2 + 0.15;
    cyl(g, r, L, galv(), 0, r, L / 2, 'z', 28);
    for (const z of [1.2, L - 1.2]) ring(g, r, 0.18, galv(), 0, r, z, 'z', 28);
    box(g, 2.4, 4.6, 3.6, mat('actuator grey', 0x5f6366, 0.5, 0.1), -r - 1.2, r, L / 2);
    box(g, 0.6, 1.2, 1.2, darkPlastic(), -r - 2.7, r + 1.0, L / 2);
    return g;
  },
  wall_box(s, it = {}) {           // a device on the wall: white cover plate, a receptacle face or a sensor dome
    const [w, h, d] = s, g = new THREE.Group();
    box(g, w, h, d, whitePlastic(), 0, h / 2, d / 2);
    if (it.sensor) cyl(g, w * 0.3, 0.4, greyPlastic(), 0, h / 2, d + 0.2, 'z', 20);
    else for (const x of [-w / 4, w / 4]) box(g, 1.3, 1.8, 0.25, greyPlastic(), x, h / 2, d + 0.12);
    return g;
  },
  wall_oven_double(s) {            // Frigidaire Gallery GCWD3067AF: stainless doors with wide black windows, flat bar handles, black glass control strip
    const [w, h, d] = s, g = new THREE.Group(), k = h / 50.75;
    const cz = d - 1.7, face = d - 0.2, dz = (cz + face) / 2, dt = face - cz;
    box(g, w - 1.37, h - 1.9, cz, darkSteel(), 0, h / 2, cz / 2);                              // chassis in the 28.5 in cutout
    box(g, w, 0.5 * k, dt, steel(), 0, 0.25 * k, dz);                                        // bottom trim
    const lower = [0.55 * k, 22.4 * k], upper = [23.15 * k, 45.1 * k], py0 = 45.6 * k;
    for (const [ya, yb] of [[lower[1], upper[0]], [upper[1], py0]]) box(g, w - 0.6, yb - ya, 0.6, darkPlastic(), 0, (ya + yb) / 2, cz + 0.3);   // vent gaps
    for (const [y0, y1] of [lower, upper]) {
      slab(g, w, y1 - y0, dt, steel(), 0, (y0 + y1) / 2, dz, 0.12);                            // door
      const gy0 = y0 + 2.05 * k, gh = 16.5 * k;
      slab(g, w - 4.4, gh + 0.3, 0.1, graphiteDark(), 0, gy0 + gh / 2, face + 0.02, 0.12);     // window trim
      slab(g, w - 4.6, gh, 0.14, glass(), 0, gy0 + gh / 2, face + 0.06, 0.1);                  // window
      slab(g, w - 4.7, 1.5, 0.7, steelH(), 0, y1 - 1.5 * k, face + 1.75, 0.3);                 // flat bar handle
      for (const sx of [-1, 1]) box(g, 1.2, 0.9, 1.5, steelH(), sx * (w / 2 - 3.6), y1 - 1.5 * k, face + 0.75);
    }
    plate(g, 4.2, 0.95, labelMat('frigidaire badge', 256, 60, (c, cw, ch) => {
      c.strokeStyle = '#4a4d50'; c.lineWidth = 3; c.strokeRect(3, 3, cw - 6, ch - 6);
      c.fillStyle = '#3a3d40'; c.font = 'bold 30px Helvetica, Arial, sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText('FRIGIDAIRE', cw / 2, ch / 2 + 2, cw - 16);
    }), 0, lower[0] + 1.05 * k, face + 0.02);
    const ph = h - py0;
    slab(g, w, ph, dt, steel(), 0, py0 + ph / 2, dz, 0.12);                                    // control panel frame
    slab(g, w - 2.2, ph - 1.5, 0.1, glass(), 0, py0 + ph / 2, face + 0.03, 0.1);
    plate(g, w - 2.6, ph - 1.9, screenMat('oven panel', 1024, 120, drawOvenPanel, 0.85), 0, py0 + ph / 2, face + 0.12);   // 1 mm in front of the glass
    return g;
  },
  cooktop_induction(s) {           // LG CBIH3013BE: frameless black glass, 10 in centre zone with three smaller zones around it, touch controls at the front
    const [w, , d] = s, g = new THREE.Group();
    box(g, w, 0.25, d, glass(), 0, 0.125, d / 2);                                            // glass on the counter
    plate(g, w - 0.1, d - 0.1, printMat('cooktop markings', 1024, 702, drawCooktop, 0.1, 0.35), 0, 0.29, d / 2, true);   // 1 mm over the glass so it never flickers
    box(g, 28.0, 3.4, 19.2, darkPlastic(), 0, -1.7, d / 2);                                  // body below the counter, inside the 28 1/2 x 19 5/8 in cutout
    return g;
  },
  fridge_french_door(s) {          // Frigidaire Gallery GRFC2353AF: two doors with flat bar handles, silver dispenser in the left door, bar handle on the freezer drawer
    const [w, h, d] = s, g = new THREE.Group();
    const dt = 4.1, zf = d - 2.3, cd = zf - dt, dzc = cd + dt / 2;                            // 30.8 in deep with handles, 28.5 without
    box(g, w - 0.3, h - 2.0, cd, steelSide(), 0, 1.1 + (h - 2.0) / 2, cd / 2);                // case
    for (const x of [-1, 1]) {
      box(g, 4.2, 0.9, 3.4, darkPlastic(), x * (w / 2 - 2.4), h - 0.45, cd - 0.9);            // hinge covers
      cyl(g, 0.8, 1.2, darkPlastic(), x * (w / 2 - 2.2), 0.6, cd + 0.6, 'y', 10);             // front feet
    }
    const fy0 = 1.3, fy1 = 26.5, dy0 = 27.4, dy1 = h - 0.4;
    slab(g, w, fy1 - fy0, dt, steel(), 0, (fy0 + fy1) / 2, dzc, 0.3);                         // freezer drawer
    box(g, w - 0.5, dy0 - fy1, dt - 1.3, graphiteDark(), 0, (fy1 + dy0) / 2, cd + (dt - 1.3) / 2);   // shadow gap between drawer and doors
    const flat = (len, x, y, vertical) => {                                                   // flat bar handle on two posts
      const a = vertical ? [1.5, len, 0.6] : [len, 1.5, 0.6];
      slab(g, a[0], a[1], a[2], steelH(), x, y, zf + 2.0, 0.22);
      for (const k of [-1, 1]) {
        const o = k * (len / 2 - 2.2);
        box(g, 1.0, 1.0, 1.7, steelH(), x + (vertical ? 0 : o), y + (vertical ? o : 0), zf + 0.85);
      }
    };
    flat(32.5, 0, 23.9, false);
    const dw = w / 2 - 0.12;
    for (const sx of [-1, 1]) {
      slab(g, dw, dy1 - dy0, dt, steel(), sx * (dw / 2 + 0.12), (dy0 + dy1) / 2, dzc, 0.3);   // doors
      flat(28.7, sx * 2.4, 48.25, true);
    }
    const px = -10.6, py = 44.4;                                                              // dispenser, 9.4 x 16.4 in, silver throughout
    slab(g, 9.4, 16.4, 0.24, mat('dispenser bezel', 0x9a9fa4, 0.4, 0.55), px, py, zf + 0.1, 0.5);
    plate(g, 8.8, 4.6, screenMat('fridge dispenser', 256, 134, drawDispenser, 0.55), px, py + 5.6, zf + 0.26);   // 1 mm in front of the bezel
    slab(g, 8.2, 10.4, 0.1, mat('dispenser cavity', 0x6c7176, 0.45, 0.45), px, py - 2.6, zf + 0.2, 0.4);
    box(g, 2.6, 5.4, 0.5, mat('dispenser paddle', 0xb4b8bc, 0.35, 0.4), px, py - 2.2, zf + 0.4);
    cyl(g, 0.5, 1.2, greyPlastic(), px, py + 2.0, zf + 0.6, 'y', 10);                         // spout
    box(g, 8.2, 0.5, 1.0, greyPlastic(), px, py - 7.6, zf + 0.5);                             // drip tray
    plate(g, 3.1, 1.2, labelMat('frigidaire logo', 256, 100, word('FRIGIDAIRE', '#f4f5f6', 'bold 34px Helvetica, Arial, sans-serif')), 14.6, 66, zf + 0.02);
    return g;
  },
  dishwasher(s) {                  // Bosch 500 Series SHP65DM5N: flat stainless door with a recessed pocket handle, controls hidden on the top edge
    const [w, h, d] = s, g = new THREE.Group();
    box(g, w - 0.4, h - 4.2, d - 1.4, darkSteel(), 0, 4.2 + (h - 4.2) / 2, (d - 1.4) / 2);
    const y0 = 4.4, y1 = h - 0.45;
    slab(g, w, y1 - y0, 1.3, steel(), 0, (y0 + y1) / 2, d - 0.65, 0.2);                      // door
    box(g, w - 0.2, 0.45, 1.3, glass(), 0, h - 0.225, d - 0.65);                             // top control strip
    slab(g, 17.6, 1.9, 0.08, graphiteDark(), 0, h - 3.2, d + 0.03, 0.9);                      // pocket handle recess
    slab(g, 17.0, 0.5, 0.2, steelH(), 0, h - 2.42, d + 0.1, 0.2);                             // its grip edge
    box(g, w - 0.6, 4.0, 0.5, blackMolded(), 0, 2.0, d - 3.0);                               // toe kick
    plate(g, 2.6, 0.6, labelMat('bosch logo', 192, 48, word('BOSCH', '#2f3235', 'bold 36px Helvetica, Arial, sans-serif')), -w / 2 + 2.3, h - 1.25, d + 0.02);
    box(g, 0.5, 0.05, 0.5, mat('info light', 0xd12f2f, 0.4, 0, { emissive: 0xc01f1f, emissiveIntensity: 0.8 }), w / 2 - 4, 0.03, d + 1.2);   // InfoLight on the floor
    return g;
  },
  disposal(s) {                    // InSinkErator Evolution Septic Assist: charcoal body, stainless mount, Bio-Charge bottle on the front
    const [w, h] = s, g = new THREE.Group(), r = w / 2, k = h / 12.63;
    const prof = [[0, 0], [3.2, 0], [4.1, 0.5], [4.5, 1.6], [4.5, 5.6], [4.3, 6.1], [4.3, 6.6], [4.5, 7.0], [4.5, 9.6], [3.9, 10.6], [2.7, 11.2], [2.5, 11.5], [0, 11.5]];
    add(g, new THREE.LatheGeometry(prof.map(([a, b]) => new THREE.Vector2(a / 4.5 * r, b * k)), 32), charcoal(), 0, 0, r);
    cyl(g, 4.34 / 4.5 * r, 0.3 * k, mat('disposer band', 0x9a9da0, 0.35, 0.8), 0, 6.35 * k, r, 'y', 32);
    cyl(g, 2.9, 0.45 * k, steelH(), 0, 11.72 * k, r); cyl(g, 2.2, 0.5 * k, steelH(), 0, 12.15 * k, r);     // quick lock mount
    cyl(g, 3.3, 0.16 * k, chrome(), 0, h - 0.08 * k, r);                                       // sink flange
    cyl(g, 0.8, 0.12, chrome(), 0, 8.6 * k, 2 * r + 0.02, 'z', 20);                           // badge
    box(g, 3.8, 1.3, 2.4, greyPlastic(), 0, 1.25 * k, 2 * r + 0.9);                            // bottle holder
    box(g, 3.0, 4.0, 1.8, mat('bio charge bottle', 0x3d8fd1, 0.3, 0, { transparent: true, opacity: 0.85 }), 0, 4.0 * k, 2 * r + 1.0);
    box(g, 3.04, 2.2, 1.84, mat('bio charge label', 0x4f9a3a, 0.5), 0, 3.5 * k, 2 * r + 1.0);
    cyl(g, 0.55, 0.9, whitePlastic(), 0, 6.3 * k, 2 * r + 1.0, 'y', 12);                       // bottle cap
    tube(g, V(r - 0.3, 7.8 * k, r), V(r + 2.6, 7.8 * k, r), 0.8, blackMolded());               // discharge elbow
    tube(g, V(r + 2.6, 7.8 * k, r), V(r + 3.2, 5.6 * k, r), 0.8, blackMolded());
    return g;
  },
  beverage_center(s) {             // Hisense HBC164N6SS: black cabinet, stainless framed glass door, bar handle, front vent
    const [w, h, d] = s, g = new THREE.Group();
    box(g, w - 0.3, h - 0.3, d - 2.0, blackMolded(), 0, 0.3 + (h - 0.3) / 2, (d - 2.0) / 2);
    const y0 = 4.3, dh = h - y0;
    slab(g, w, dh, 1.9, steel(), 0, y0 + dh / 2, d - 0.95, 0.2);                             // door frame
    slab(g, w - 4.0, dh - 4.0, 0.1, smoked(), 0, y0 + dh / 2, d + 0.01, 0.2);                // glass edge
    plate(g, w - 4.4, dh - 4.4, screenMat('beverage inside', 256, 384, drawBeverage, 0.22, 0.05), 0, y0 + dh / 2, d + 0.1);   // 1 mm in front of the glass edge
    bar(g, 20, -w / 2 + 1.1, y0 + dh / 2, d, true, steelH(), 0.45, 1.6);
    box(g, w - 0.4, y0 - 0.5, 0.6, blackMolded(), 0, y0 / 2 + 0.1, d - 1.7);                 // front vent grille
    for (let k = 0; k < 5; k++) box(g, w - 2.4, 0.22, 0.25, mat('vent slat', 0x3c3f42, 0.6), 0, 1.0 + k * 0.62, d - 1.32);
    return g;
  },
  front_load_laundry(s) {          // GE Profile UltraFast Combo PFQ97HSPVDS, Carbon Graphite
    const [w, h, d] = s, g = new THREE.Group();
    const bd = d - 2.2, mh = 11.8, band = 1.4, yT = h - mh, z1 = bd + 0.35;
    box(g, w - 2.4, 0.6, bd - 3, blackMolded(), 0, 0.3, (bd - 3) / 2 + 1);                    // levelling feet zone
    column(g, w, yT - band - 0.6, bd, graphite(), 0, 0.6 + (yT - band - 0.6) / 2, bd / 2, 1.1);   // lower body
    box(g, w - 0.5, band, bd - 0.4, graphiteDark(), 0, yT - band / 2, (bd - 0.4) / 2);        // recessed band under the control module
    column(g, w, mh - 0.25, z1, graphite(), 0, yT + (mh - 0.25) / 2, z1 / 2, 1.3);            // dispenser and control module
    slab(g, w - 3.2, z1 - 3.6, 0.25, graphiteDark(), 0, 0, 0, 1.2).rotation.x = -Math.PI / 2; // raised top panel
    g.children[g.children.length - 1].position.set(0, h - 0.125, z1 / 2);
    // door: 25.8 in across, smoked glass bowl in a dark bezel
    const cy = 19.5, R = 12.9;
    cyl(g, R, 1.2, graphiteDark(), 0, cy, bd + 0.6, 'z', 48);
    ring(g, R - 0.25, 0.3, darkSteel(), 0, cy, bd + 1.2, 'z', 56);
    const bowl = printMat('combo door glass', 4, 64, (c, cw, ch) => {
      const gr = c.createLinearGradient(0, 0, 0, ch);
      gr.addColorStop(0, '#0e1c38'); gr.addColorStop(0.5, '#0a1428'); gr.addColorStop(0.62, '#010203'); gr.addColorStop(0.66, '#0a0c10'); gr.addColorStop(1, '#050607');
      c.fillStyle = gr; c.fillRect(0, 0, cw, ch);
    }, 0.04, 0.55);
    dome(g, R - 0.55, 1.0, bowl, 0, cy, bd + 1.2);
    // control module front: two dispenser drawers and a pocket handle on the left, glass touch panel on the right
    const sx = -3.86;
    box(g, 0.1, mh - 1.2, 0.06, graphiteDark(), sx, yT + mh / 2 - 0.1, z1 + 0.01);            // seam beside the drawers
    box(g, w / 2 + sx - 1.4 - 1.0, 0.1, 0.06, graphiteDark(), (-w / 2 + 0.8 + (-6.9)) / 2, yT + 4.9, z1 + 0.01);   // seam between the drawers
    slab(g, 1.7, 8.8, 0.08, glass(), -6.0, yT + 6.1, z1 + 0.03, 0.8);                         // pocket handle
    slab(g, 0.8, 7.9, 0.08, graphite(), -6.0, yT + 6.1, z1 + 0.08, 0.4);
    plate(g, 5.0, 1.25, labelMat('profile logo', 256, 64, (c, cw, ch) => {
      c.strokeStyle = '#e6e7e8'; c.lineWidth = 3; c.beginPath(); c.arc(30, ch / 2, 20, 0, Math.PI * 2); c.stroke();
      c.fillStyle = '#e6e7e8'; c.font = 'italic bold 20px Georgia, serif'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText('GE', 30, ch / 2 + 1);
      c.font = '34px Helvetica, Arial, sans-serif'; c.textAlign = 'left'; c.fillText('Profile', 62, ch / 2 + 2);
    }), -10.6, yT + 9.2, z1 + 0.02);
    const pw = 12.6, pH = 7.1, pcx = sx + 0.35 + pw / 2, pcy = yT + 1.6 + pH / 2;
    slab(g, pw, pH, 0.12, glass(), pcx, pcy, z1 + 0.04, 0.45);
    plate(g, pw - 0.5, pH - 0.5, screenMat('combo panel', 768, 420, drawCombo, 0.9), pcx, pcy, z1 + 0.12);
    slab(g, 1.5, 1.5, 0.06, mat('combo badge', 0xe8e9ea, 0.4, 0.1), 11.2, 30.4, bd + 0.03, 0.25);   // FlexDispense badge
    slab(g, 5.2, 2.9, 0.06, graphiteDark(), 3.95, 2.2, bd + 0.02, 0.2);                       // lint filter door outline
    slab(g, 4.9, 2.6, 0.06, graphite(), 3.95, 2.2, bd + 0.05, 0.15);
    return g;
  },
  hpwh(s, it = {}) {               // Rheem ProTerra hybrid: grey tank, heat pump section on top with a fan guard and control panel, side water connections
    // flip puts the water connections on the other side (they face the preheat tank), with the relief valve opposite them
    const [dia, h] = s, g = new THREE.Group(), r = dia / 2, cz = r + 2, split = h - 15.5, sx = it.flip ? -1 : 1;
    cyl(g, r + 2, 2, galv(), 0, 1, cz, 'y', 40);                                             // 2" round drain pan (U-11 detail)
    cyl(g, r, h - 0.9, tankGrey(), 0, 0.6 + (h - 0.9) / 2, cz, 'y', 48);                      // tank and heat pump jacket
    cyl(g, r - 2.2, 0.3, blackMolded(), 0, h - 0.15, cz, 'y', 40);                            // top air intake
    cyl(g, r + 0.06, 0.3, seam(), 0, split, cz, 'y', 48);                                     // joint between the tank and the heat pump section
    cyl(g, r + 0.06, 1.2, mat('tank base ring', 0x55585a, 0.6, 0.3), 0, 1.2, cz, 'y', 48);
    wrap(g, r + 0.1, 5.2, 8, screenMat('hpwh panel', 128, 192, drawHeaterPanel, 0.6, 0.2), 0, h - 7.5, cz, 0);
    wrap(g, r + 0.1, 9.5, 9.5, printMat('hpwh fan', 128, 128, drawFan, 0.6, 0.2), 0, h - 7.5, cz, 0.95);
    wrap(g, r + 0.12, 2.8, 2.8, labelMat('rheem badge', 128, 128, roundBadge('#c8102e', '#fff', 'Rheem', 'italic bold 34px Georgia, serif')), 0, split - 4, cz, 0, 6);
    for (const y of [15, 38]) wrap(g, r + 0.08, 5.6, 7.6, mat('tank cover', 0x8a8c8c, 0.5, 0.5), 0, y, cz, 0);   // element access covers
    cyl(g, 0.5, 2.2, brass(), -4.6, 5.2, cz + r * 0.92 + 0.6, 'z', 12);                       // drain valve
    // side connections: cold in low, hot out high (brass unions); the piping itself is drawn as pipe runs
    for (const [y, m, zo] of [[9, blue(), -1.6], [split - 4, red(), 1.6]]) {
      cyl(g, 0.7, 2.8, brass(), -sx * (r + 1.2), y, cz + zo, 'x', 12);
      ring(g, 0.9, 0.25, m, -sx * (r + 2.2), y, cz + zo, 'x', 20);
    }
    cyl(g, 0.7, 2.6, brass(), sx * (r + 1.1), split - 3, cz, 'x', 12);                          // T&P relief valve and its drop
    cyl(g, 0.4, split - 9, copper(), sx * (r + 2.2), (split - 3 + 6) / 2, cz, 'y', 10);
    cyl(g, 0.35, h - 6, mat('condensate', 0xe9eef2, 0.4, 0, { transparent: true, opacity: 0.8 }), sx * (r - 1), (h - 6) / 2 + 2, cz - r * 0.75); // condensate line, on the wall side
    return g;
  },
  storage_tank(s) {                // plain electric tank used as the desuperheater preheat tank: white jacket, top connections, drain on the east side
    const [dia, h] = s, g = new THREE.Group(), r = dia / 2, cz = r + 2;
    cyl(g, r + 2, 2, galv(), 0, 1, cz, 'y', 40);                                             // round drain pan
    cyl(g, r, h - 0.9, mat('tank white', 0xe9e8e3, 0.55, 0.05), 0, 0.6 + (h - 0.9) / 2, cz, 'y', 48);
    cyl(g, r - 0.4, 0.4, mat('tank top', 0xd9d8d3, 0.6, 0.05), 0, h - 0.1, cz, 'y', 40);
    cyl(g, r + 0.06, 1.2, mat('tank base ring', 0x55585a, 0.6, 0.3), 0, 1.2, cz, 'y', 48);
    for (const y of [15, 42]) wrap(g, r + 0.08, 5.6, 7.6, mat('tank cover', 0xb9bab6, 0.5, 0.3), 0, y, cz, 0);   // element covers (not wired)
    wrap(g, r + 0.12, 2.8, 2.8, labelMat('rheem badge', 128, 128, roundBadge('#c8102e', '#fff', 'Rheem', 'italic bold 34px Georgia, serif')), 0, h - 10, cz, 0, 6);
    cyl(g, 0.5, 2.6, brass(), -(r + 1.0), 5.4, cz - 4.8, 'x', 12);                           // drain port, tee to the desuperheater supply
    for (const [x, m] of [[3.6, blue()], [-3.6, red()]]) {                                     // cold in, hot out on top: short nipples, the pipe runs carry on
      cyl(g, 0.7, 3, brass(), x, h + 1.5, cz, 'y', 12);
      ring(g, 0.9, 0.25, m, x, h + 2.2, cz, 'y', 20);
    }
    cyl(g, 0.7, 2.6, brass(), r + 1.1, h - 8, cz, 'x', 12);                                   // T&P relief valve and its drop, on the far side from the water heater
    cyl(g, 0.4, h - 14, copper(), r + 2.2, (h - 8 + 6) / 2, cz, 'y', 10);
    return g;
  },
  circ_pump(s) {                   // inline hot water recirculation pump on a vertical pipe (U-11): red volute, motor and box off the side
    const g = new THREE.Group();
    cyl(g, 1.0, 5.5, brass(), 0, 0, 0, 'y', 14);                                             // flanges and body on the pipe
    cyl(g, 2.1, 2.6, pumpRed(), 0, 0, 0, 'y', 24);                                           // volute
    cyl(g, 1.7, 4.2, pumpRed(), 0, 0, 2.6, 'z', 20);                                         // motor sticking out from the wall side
    box(g, 2.4, 2.0, 1.6, mat('pump box', 0x2c2c2c, 0.6, 0.1), 0, 2.0, 3.4);
    return g;
  },
  expansion_tank(s) {              // thermal expansion tank hanging under the cold line
    const [d, h] = s, g = new THREE.Group();
    cyl(g, 0.4, 3, brass(), 0, -1.5, 0, 'y', 10);
    cyl(g, d / 2, h, galv(), 0, -3 - h / 2, 0, 'y', 28);
    cyl(g, 0.4, 0.8, brass(), 0, -3 - h - 0.4, 0, 'y', 8);                                   // air valve
    return g;
  },
  pressure_tank(s) {               // well pressure tank, stand type: blue steel shell, domed top with the air valve, black base ring with a cut out for the pipe
    const [dia, h] = s, g = new THREE.Group(), r = dia / 2, cz = r + 1, base = 5;
    const shell = mat('pressure tank blue', 0x1d4f9c, 0.38, 0.35);
    cyl(g, r * 0.86, base, blackMolded(), 0, base / 2, cz, 'y', 40);                         // base ring
    cyl(g, r, h - base - r * 0.3, shell, 0, base + (h - base - r * 0.3) / 2, cz, 'y', 48);
    const top = new THREE.SphereGeometry(r, 40, 10, 0, Math.PI * 2, 0, Math.PI / 2); top.scale(1, 0.3, 1);
    add(g, top, shell, 0, h - r * 0.3, cz);
    cyl(g, r + 0.05, 1.4, mat('tank seam', 0x173f7d, 0.45, 0.3), 0, base + 1, cz, 'y', 48);
    cyl(g, 0.5, 1.6, brass(), 0, h + 0.4, cz, 'y', 10);                                        // air valve
    wrap(g, r + 0.06, 9, 5, labelMat('pressure tank label', 192, 96, (c, w, hh) => {
      c.fillStyle = '#f2f2ee'; c.fillRect(0, 0, w, hh); c.fillStyle = '#1d4f9c'; c.font = 'bold 26px Helvetica, Arial, sans-serif';
      c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText('WELL TANK', w / 2, hh * 0.38); c.font = '15px Helvetica, Arial, sans-serif'; c.fillText('Pre-charge 38 PSI', w / 2, hh * 0.74);
    }), 0, h * 0.55, cz, 0, 8);
    return g;
  },
  tank_tee(s) {                    // tank tee at the pressure tank: brass body, pressure switch, gauge, relief valve and drain
    const g = new THREE.Group();
    cyl(g, 0.75, 10, brass(), 0, 0, 0, 'x', 12);
    box(g, 3.2, 3.6, 2.6, greyPlastic(), -1.5, 2.8, 0.2);                                     // pressure switch
    cyl(g, 1.2, 0.6, white(), 2.2, 2.2, 0.5, 'z', 20); cyl(g, 0.3, 1.5, brass(), 2.2, 1.0, 0, 'y', 8);   // gauge
    cyl(g, 0.45, 2.4, brass(), 3.8, -1.4, 0, 'y', 8);                                         // relief valve
    cyl(g, 0.4, 2, brass(), -4, -1.2, 0, 'y', 8);                                             // drain cock
    return g;
  },
  spin_down(s) {                   // flushable spin down sediment screen: black head, clear bowl, white mesh screen, flush valve at the bottom
    const [w, h, d] = s, g = new THREE.Group(), cz = d / 2 + 0.5;
    box(g, w, 0.4, 2, blackMolded(), 0, h - 2, 0.2);                                          // wall bracket
    box(g, w, 2.6, d - 1, blackMolded(), 0, h - 1.3, cz);
    cyl(g, 2.2, h - 4.2, mat('clear bowl', 0xd7e6ee, 0.1, 0, { transparent: true, opacity: 0.45 }), 0, (h - 2.6) / 2 + 0.8, cz, 'y', 28);
    cyl(g, 1.4, h - 5.4, whitePlastic(), 0, (h - 2.6) / 2 + 0.8, cz, 'y', 18);
    cyl(g, 0.5, 1.4, brass(), 0, 0.2, cz, 'y', 8);
    for (const sx of [-1, 1]) cyl(g, 0.6, 1.4, brass(), sx * (w / 2 + 0.4), h - 1.3, cz, 'x', 10);
    return g;
  },
  big_blue(s, it = {}) {           // 20 in whole house filter housing (4.5 in cartridge): wall bracket, black head with the ports and the pressure release, blue sump
    const [w, h, d] = s, g = new THREE.Group(), cz = d / 2 + 0.5, r = Math.min(w, d - 1) / 2 - 0.2;
    box(g, w * 0.8, 1.2, 0.5, galv(), 0, h - 2, 0.25);                                        // bracket
    box(g, w, 3.4, d - 1, blackMolded(), 0, h - 1.7, cz);
    cyl(g, 0.45, 0.8, mat('release button', 0xc7342b, 0.5, 0), 1.6, h + 0.4, cz, 'y', 10);
    const sump = mat(it.sump === 'grey' ? 'filter sump grey' : 'filter sump blue', it.sump === 'grey' ? 0x6f7478 : 0x2560b8, 0.35, 0.05);
    cyl(g, r, h - 3.4, sump, 0, (h - 3.4) / 2, cz, 'y', 32);
    for (let k = 0; k < 6; k++) cyl(g, r + 0.12, 0.35, sump, 0, 3 + k * (h - 8) / 5, cz, 'y', 32);    // ribs
    for (const sx of [-1, 1]) cyl(g, 0.6, 1.4, brass(), sx * (w / 2 + 0.4), h - 1.7, cz, 'x', 10);
    return g;
  },
  uv_system(s) {                   // UV sterilizer: vertical stainless chamber on two clamps, lamp cap and cord on top, controller box to the left
    const [w, h, d] = s, g = new THREE.Group(), cz = d / 2;
    for (const y of [6, h - 8]) box(g, 4.6, 1.2, cz, galv(), 0, y, cz / 2);
    cyl(g, 1.75, h - 4, steel(), 0, (h - 4) / 2 + 1, cz, 'y', 28);
    cyl(g, 1.2, 2.4, darkPlastic(), 0, h - 1.8, cz, 'y', 18);
    for (const y of [4.5, h - 6.5]) cyl(g, 0.6, 2.4, steel(), 2.6, y, cz, 'x', 10);              // inlet low, outlet high, both on the right
    box(g, 4.2, 7.5, 2.4, mat('uv controller', 0xdedfdc, 0.5, 0.05), -6.5, h * 0.62, 1.2);
    plate(g, 2.2, 1.0, screenMat('uv screen', 64, 32, (c, ww, hh) => { c.fillStyle = '#0e2a14'; c.fillRect(0, 0, ww, hh); c.fillStyle = '#5cff7a'; c.font = 'bold 18px Helvetica'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText('365', ww / 2, hh / 2); }, 0.7), -6.5, h * 0.62 + 2, 2.45);
    cyl(g, 0.25, 8, blackMolded(), -3, h - 3.5, cz, 'x', 6);                                  // lamp cord
    return g;
  },
  floor_drain(s) {                 // round floor drain: a low chrome ring and a slotted grate just proud of the slab
    const [d] = s, g = new THREE.Group();
    cyl(g, d / 2, 0.3, chrome(), 0, 0.15, d / 2, 'y', 32);
    cyl(g, d / 2 - 0.8, 0.12, darkPlastic(), 0, 0.33, d / 2, 'y', 28);
    for (let k = -2; k <= 2; k++) box(g, 0.35, 0.1, d - 2.4 - Math.abs(k) * 0.7, chrome(), k * 0.75, 0.42, d / 2);
    return g;
  },
  softener_cabinet(s) {            // cabinet softener, shown as a reserved spot: grey box, salt lid on top at the front, control head at the back
    const [w, h, d] = s, g = new THREE.Group();
    const body = mat('softener reserved', 0xc9cbc6, 0.6, 0, { transparent: true, opacity: 0.55, depthWrite: false });
    column(g, w, h - 2, d, body, 0, (h - 2) / 2, d / 2, 1.2);
    box(g, w - 2, 1.2, d * 0.55, mat('salt lid', 0x7d8287, 0.5, 0.05), 0, h - 1.4, d * 0.68);
    box(g, w * 0.6, 4, d * 0.32, blackMolded(), 0, h - 0.2, d * 0.2);
    plate(g, w * 0.7, 3, labelMat('softener tag', 192, 64, word('SPACE RESERVED', '#2b2e31', 'bold 22px Helvetica, Arial, sans-serif')), 0, h * 0.6, d + 0.05);
    return g;
  },
  stick_vacuum(s) {               // Dyson V8 class stick vacuum hanging on its wall dock: purple wand down to the floor head, clear bin, nickel cyclone,
    const [w, , d] = s, g = new THREE.Group();     // motor and grip at the top, battery in the dock's cradle, two tools on the dock, charger in an outlet to the left
    const nickel = mat('vacuum nickel', 0xa9adb1, 0.32, 0.75), purple = mat('vacuum purple', 0x6a2c8e, 0.38, 0.35);
    const iron = mat('vacuum iron', 0x3d4044, 0.45, 0.4), red = mat('vacuum red', 0xc4262e, 0.4, 0.05);
    const clear = mat('vacuum clear bin', 0xdfe6ea, 0.08, 0, { transparent: true, opacity: 0.28, depthWrite: false });
    const CZ = 5.2;                                                                           // wand and bin axis, in from the wall
    box(g, 3.4, 10, 0.6, darkPlastic(), 0, 42, 0.4);                                         // dock back plate
    box(g, 2.4, 1.2, 1.9, darkPlastic(), 0, 36.0, 1.65);                                     // cradle under the battery
    for (const sx of [-1, 1]) box(g, 1.6, 1, 0.7, darkPlastic(), sx * 2.4, 37.6, 1.05);       // tool clips
    cyl(g, 0.5, 11, greyPlastic(), -3.3, 31.5, 1.3, 'y', 12);                                 // crevice tool
    box(g, 1.8, 6, 1.6, greyPlastic(), 3.4, 34, 1.4);                                         // combination tool
    box(g, 2.6, 5.5, 2.2, iron, 0, 39.15, 2.1);                                               // battery pack
    cyl(g, 0.8, 4.3, iron, 0, 43.95, 2.0, 'y', 14);                                           // grip
    box(g, 0.5, 1.4, 0.8, red, 0, 43.2, 2.9);                                                 // trigger
    cyl(g, 1.6, 4.0, nickel, 0, 47.4, 3.4, 'z', 24);                                          // motor, across the top
    cyl(g, 1.65, 0.3, purple, 0, 47.4, 1.3, 'z', 24);                                         // rear filter cap
    cyl(g, 2.1, 2.3, purple, 0, 44.65, CZ, 'y', 24, 2.4);                                     // cyclone crown
    cyl(g, 2.4, 4.0, nickel, 0, 41.5, CZ, 'y', 28);                                           // cyclone shroud
    cyl(g, 2.4, 7.3, clear, 0, 35.85, CZ, 'y', 28);                                           // clear bin
    cyl(g, 1.3, 6.5, galv(), 0, 36.25, CZ, 'y', 16);                                          // dust shroud seen through the bin
    cyl(g, 2.45, 0.4, iron, 0, 32.2, CZ, 'y', 28);                                            // bin base
    box(g, 0.8, 1.6, 0.6, red, 0, 39.1, CZ + 2.55);                                           // bin release
    cyl(g, 0.75, 29.1, purple, 0, 17.85, CZ, 'y', 16);                                        // wand
    cyl(g, 0.95, 2.2, iron, 0, 3.7, CZ, 'y', 16);                                             // neck
    box(g, w, 2.4, 3.4, iron, 0, 2.25, 6.0);                                                  // floor head
    cyl(g, 1.05, w - 0.6, darkPlastic(), 0, 2.2, d - 1.2, 'x', 18);                            // brush bar
    for (const sx of [-1, 1]) cyl(g, 1.18, 0.25, purple, sx * (w / 2 - 0.3), 2.2, d - 1.2, 'x', 18);   // brush bar end caps
    // outlet for the charger, to the left (the open door is to the right): duplex cover plate about 18 in up, charger in the top receptacle, cord up to the dock
    const OX = -7;
    box(g, 2.75, 4.5, 0.22, whitePlastic(), OX, 18, 0.17);
    for (const y of [16.9, 19.1]) box(g, 1.4, 1.3, 0.14, whitePlastic(), OX, y, 0.33);
    for (const x of [OX - 0.25, OX + 0.25]) box(g, 0.1, 0.42, 0.08, darkPlastic(), x, 16.95, 0.42);
    box(g, 1.6, 2.2, 1.2, blackMolded(), OX, 19.3, 0.96);                                      // charger
    const cord = [[OX, 20.4, 0.9], [OX, 24, 0.5], [OX + 1.8, 34.4, 0.5], [-1.2, 37.4, 0.5]].map((p) => new THREE.Vector3(...p));
    for (let i = 0; i < cord.length - 1; i++) tube(g, cord[i], cord[i + 1], 0.12, blackMolded(), 6);
    return g;
  },
  ro_unit(s) {                     // tankless under sink reverse osmosis: tall white box, filter caps on top, small status ring on the front
    const [w, h, d] = s, g = new THREE.Group();
    column(g, w, h - 1, d, whitePlastic(), 0, (h - 1) / 2, d / 2, 1.2);
    for (const z of [d * 0.25, d * 0.5, d * 0.75]) cyl(g, 1.6, 1, greyPlastic(), 0, h - 0.5, z, 'y', 18);
    ring(g, 1.3, 0.2, mat('ro ring', 0x3aa7e6, 0.3, 0, { emissive: 0x3aa7e6, emissiveIntensity: 0.6 }), 0, h * 0.7, d + 0.1, 'z', 24);
    return g;
  },
  mixing_valve(s) {                // thermostatic mixing valve on the hot riser, tempered water out the top
    const g = new THREE.Group();
    box(g, 2.6, 3.2, 2.2, brass(), 0, 0, 0);
    cyl(g, 1.1, 0.8, mat('valve knob', 0x2f6db5, 0.5, 0.1), 0, 0, 1.5, 'z', 18);
    return g;
  },
  geo_horizontal(s, it = {}) {
    // GeoComfort ZT 048 horizontal, end discharge: [A width, C height, B length] = 21.7 x 21.2 x 56 in.
    // Local: length along x. +x end = supply discharge, -x end = front (water and electrical connections).
    // As built here it is a left hand return: the return opening is on your left as you face the front end, which is the back
    // (z = 0) side. mirror: true on the item makes it the right hand return unit.
    const [w, h, len] = s, g = new THREE.Group();
    for (const x of [-len / 2 + 4, len / 2 - 4]) box(g, 4, 4, w + 2, rubber(), x, -2, w / 2);   // vibration isolation rails
    box(g, len + 8, 1.5, w + 10, plywood(), 0, -4.75, w / 2);                                // service platform
    box(g, len, h, w, cabinetGrey(), 0, h / 2, w / 2);
    // service side: three access panels with seams and pulls, corner posts, maker's badge
    for (const x of [-len / 2 + 0.6, -len / 2 + 19, 7, len / 2 - 0.6]) box(g, 0.25, h - 0.6, 0.12, seam(), x, h / 2, w + 0.03);
    for (const y of [0.4, h - 0.4]) box(g, len - 0.6, 0.25, 0.12, seam(), 0, y, w + 0.03);
    for (const x of [-len / 2 + 10, -6, 20]) {
      box(g, 4.6, 1.3, 0.35, darkPlastic(), x, h - 3.2, w + 0.18);                           // panel pulls
      for (const sx of [-1, 1]) for (const y of [1.6, h - 1.6]) cyl(g, 0.28, 0.14, galv(), x + sx * 7.2, y, w + 0.05, 'z', 8);   // panel screws
    }
    const badge = plate(g, 5.2, 5.2, labelMat('geocomfort badge', 160, 160, roundBadge('#f4f5f2', '#1f6b3a', 'GeoComfort', 'bold 24px Helvetica, Arial, sans-serif')), -len / 2 + 9.6, h * 0.5, w + 0.2);
    if (it.mirror) badge.scale.x = -1;                                                       // keep the lettering readable on a mirrored unit
    box(g, 9, 3.2, 0.06, mat('rating label', 0xe9e9e2, 0.6), 20, 5, w + 0.06);                // rating plate
    box(g, 36, 18, 2.4, galv(), -len / 2 + 2 + 18, h / 2, -1.2);                             // AFR1836A 18 x 36 filter rack on the return side
    box(g, 34.5, 16.5, 0.3, mat('filter media', 0xe8e6da, 0.9), -len / 2 + 2 + 18, h / 2, -2.45);
    box(g, 1.2, 13.7, 12.8, galv(), len / 2 + 0.6, h - 1.5 - 6.25, w / 2);                   // supply collar flange
    box(g, 9, 12.5, 11.6, galv(), len / 2 + 4.5, h - 1.5 - 6.25, w / 2);                     // 15 kW heater on the 11.6 x 12.5 supply opening
    box(g, 4, 5, 0.5, darkPlastic(), len / 2 + 4.5, h - 1.5 - 6.25, w / 2 + 6.05);
    for (const [y, m] of [[5.6, blue()], [17.6, red()]]) {                                   // source water in/out, hose kit and ball valves
      cyl(g, 1.25, 0.8, brass(), -len / 2 - 0.4, y, w * 0.3, 'x', 6);                         // FPT fitting on the cabinet
      cyl(g, 0.75, 9, rubber(), -len / 2 - 4.5, y, w * 0.3, 'x');
      cyl(g, 0.95, 2.6, brass(), -len / 2 - 10.3, y, w * 0.3, 'x');
      box(g, 0.6, 0.6, 3, m, -len / 2 - 10.3, y + 1.2, w * 0.3);
    }
    for (const y of [9.6, 13.6]) cyl(g, 0.8, 0.9, brass(), -len / 2 - 0.45, y, w * 0.3, 'x', 6);   // hot water generator ports, capped
    for (const y of [h - 3, h - 6.5]) cyl(g, 0.7, 0.2, darkPlastic(), -len / 2 - 0.1, y, w * 0.2, 'x', 12);   // electrical knockouts
    box(g, 0.4, 7, 5, darkPlastic(), -len / 2 - 0.2, h - 6, w * 0.72);                       // control box cover
    cyl(g, 0.5, 6, mat('condensate', 0xe9eef2, 0.4, 0, { transparent: true, opacity: 0.8 }), len / 2 - 6, 1.5, w + 3, 'z');   // condensate to the EZ-Trap
    return g;
  },
  flow_center(s) {                 // Geo-Flo NP series: black moulded canister, pumps and brass ports on the front, fill cap on top
    const [w, h, d] = s, g = new THREE.Group();
    column(g, w - 1, h, d - 1, blackMolded(), 0, h / 2, d / 2, 1.6);
    box(g, w - 3, 0.6, d - 3, blackMolded(), 0, h + 0.3, d / 2);                              // lid
    cyl(g, 2.3, 1.3, blackMolded(), 0, h + 1.2, d / 2, 'y', 8);                               // fill cap
    const fz = d - 0.5;
    for (const [x, y] of [[-2.9, h * 0.6], [2.9, h * 0.28]]) {                               // two circulators
      cyl(g, 2.5, 0.9, blackMolded(), x, y, fz + 0.45, 'z', 20);
      cyl(g, 2.05, 3.4, blackMolded(), x, y, fz + 2.5, 'z', 20);
      cyl(g, 1.35, 0.1, chrome(), x, y, fz + 4.22, 'z', 20);
      box(g, 2.4, 2.6, 2.6, blackMolded(), x + (x < 0 ? -2.6 : 2.6), y, fz + 2.2);            // terminal box
    }
    for (const x of [-3.2, 3.2]) { cyl(g, 1.15, 0.9, brass(), x, h - 2.4, fz + 0.4, 'z', 16); cyl(g, 0.75, 0.95, blackMolded(), x, h - 2.4, fz + 0.47, 'z', 16); }   // loop ports
    for (const [y, z] of [[20, 2.6], [8, 5.4]]) {                                             // loop ports on the side facing the manifolds, level with its two headers
      cyl(g, 1.15, 0.9, brass(), w / 2 - 0.05, y, z, 'x', 16); cyl(g, 0.75, 0.95, blackMolded(), w / 2 - 0.02, y, z, 'x', 16);
    }
    plate(g, 4.6, 2.3, labelMat('np series logo', 256, 128, (c, cw, ch) => {
      c.fillStyle = '#f2f2f2'; c.textAlign = 'center'; c.textBaseline = 'middle';
      c.font = 'bold 62px Helvetica, Arial, sans-serif'; c.fillText('NP', cw / 2, ch * 0.36);
      c.font = 'bold 30px Helvetica, Arial, sans-serif'; c.fillText('SERIES', cw / 2, ch * 0.78);
    }), 2.6, h * 0.62, fz + 0.03);
    return g;
  },
  pe_manifold(s, it) {
    // Pair of 1-1/4" PE headers, 5 x 3/4" circuits each with a 1" ball valve. The supply header sits on the wall and the return
    // header in front of it, so the supply legs pass behind the return header. Each leg ends at the bottom (y = 0), where the loop
    // pipe from the slab sleeve is fused on; those pipes are drawn as runs.
    const [w, h, d] = s, g = new THREE.Group();
    const R_H = 0.83, R_C = 0.525, n = 5;
    const rows = [{ y: h - 4, z: 2.6, m: blue(), lbl: 'supply' }, { y: h - 16, z: 5.4, m: red(), lbl: 'return' }];
    for (const [ri, row] of rows.entries()) {
      const z = row.z;
      cyl(g, R_H, w, pe(), 0, row.y, z, 'x');
      for (let k = 0; k < n; k++) {
        const x = -w / 2 + 3 + k * ((w - 6) / (n - 1)) + (ri ? 1.4 : 0);
        cyl(g, 0.9, 2.2, brass(), x, row.y - 2.2, z);                                       // valve body
        box(g, 3.2, 0.5, 0.7, row.m, x + 1.3, row.y - 2.0, z + 1.1);                         // lever
        cyl(g, R_C, row.y - 3.3, pe(), x, (row.y - 3.3) / 2, z);                             // circuit down to the slab
        cyl(g, R_C + 0.35, (row.y - 3.3) * 0.55, foam(), x, (row.y - 3.3) * 0.35, z);        // insulation
      }
      cyl(g, R_H, 6, pe(), w / 2 + 3, row.y, z, 'x');                                        // main out toward the flow center
    }
    for (const x of [-w / 4, w / 4]) box(g, 1.2, h, 1.6, mat('strut', 0x9fa3a6, 0.5, 0.7), x, h / 2, 0.8);   // unistrut
    for (const row of rows) for (const x of [-9, 9]) box(g, 1.4, 1.4, row.z, mat('strut', 0x9fa3a6, 0.5, 0.7), x, row.y, row.z / 2);   // header brackets
    return g;
  },
  erv(s, it = {}) {                // ERV (was drawn for the Panasonic Intelli-Balance 100): galvanized steel box, two white duct adapters on each end
    const [w, h, d] = s, g = new THREE.Group();
    if (it.hang) {                                                                           // hung level on four chains from the roof framing, hang = chain length in inches
      for (const x of [-w / 2 - 0.7, w / 2 + 0.7]) for (const z of [2.5, d - 2.5]) cyl(g, 0.16, it.hang, darkSteel(), x, h + it.hang / 2, z, 'y', 6);
    }
    box(g, w, h, d, galv(), 0, h / 2, d / 2);
    for (const z of [-1.0, d + 1.0]) for (const x of [-w / 4, w / 4]) {
      cyl(g, 3.0, 2.0, whitePlastic(), x, h / 2, z, 'z', 24);                                // 6 in adapters
      cyl(g, 3.6, 0.25, whitePlastic(), x, h / 2, z < 0 ? -0.12 : d + 0.12, 'z', 24);
    }
    box(g, 0.14, h - 1.6, d * 0.62, mat('erv access panel', 0xc3c7ca, 0.38, 0.8), w / 2 + 0.09, h / 2, d / 2);   // core and filter access panel
    for (const z of [d / 2 - d * 0.24, d / 2 + d * 0.24]) box(g, 0.3, 1.6, 1.0, darkPlastic(), w / 2 + 0.2, h / 2, z);   // latches
    box(g, 0.3, 3.2, 4.2, darkPlastic(), w / 2 + 0.15, h - 2.4, d - 3.2);                     // airflow dials
    box(g, 0.05, 2.6, 4.4, mat('rating label', 0xe9e9e2, 0.6), w / 2 + 0.16, 2.2, d / 2);
    for (const x of [-1, 1]) for (const z of [2.5, d - 2.5]) box(g, 1.4, 0.2, 2.2, galv(), x * (w / 2 + 0.7), h - 0.1, z);   // hanging brackets
    for (const x of [-w / 4, 0, w / 4]) for (const z of [d * 0.25, d * 0.75]) cyl(g, 0.22, 0.1, darkSteel(), x, h + 0.02, z, 'y', 8);   // cover screws
    return g;
  },
  silencer(s) {                    // round duct silencer: galvanized shell, rolled end rings, 8 in collars each end. Vertical, base at the origin.
    const [od, len] = s, g = new THREE.Group(), r = od / 2;
    cyl(g, r, len - 4, galv(), 0, len / 2, 0, 'y', 28);
    for (const y of [2.6, len - 2.6]) cyl(g, r - 0.6, 1.4, galv(), 0, y, 0, 'y', 28, r - 1.6);   // tapered shoulders
    for (const y of [1, len - 1]) cyl(g, r - 2.0, 2, galv(), 0, y, 0, 'y', 24);                   // duct collars
    for (const y of [len * 0.3, len * 0.7]) ring(g, r + 0.05, 0.18, galv(), 0, y, 0, 'y', 32);  // seams
    box(g, 0.05, 3.2, 5.2, mat('rating label', 0xe9e9e2, 0.6), r + 0.03, len / 2, 0);
    return g;
  },
  roof_blower(s) {                 // low profile exterior range hood blower on a roof curb: square curb, flat base, louvred band, domed hood
    const [w, h, d] = s, g = new THREE.Group(), flash = mat('curb flashing', 0x2a2d2f, 0.5, 0.4);
    box(g, w + 3, 9, d + 3, flash, 0, 0.5, 0);                                                // curb, flashed into the standing seam (runs into the roof on the uphill side)
    box(g, w + 1.2, 0.6, d + 1.2, darkSteel(), 0, 5.3, 0);                                     // base flange
    box(g, w - 2, 3.0, d - 2, darkSteel(), 0, 7.1, 0);                                         // fan housing
    box(g, w - 2.2, 1.6, d - 2.2, mat('louvre shadow', 0x111213, 0.8), 0, 9.3, 0);             // discharge band
    cyl(g, (w - 7) / 2, h - 10.6, darkSteel(), 0, 10.1 + (h - 10.6) / 2, 0, 'y', 4, (w - 1.5) / 2).rotation.y = Math.PI / 4;   // hood
    return g;
  },
  tote_stacks(s, it) {
    // 27 gal hardware store totes, stacked: black base tapering toward the bottom, a rim with end handles, a yellow snap lid with a
    // raised centre the next tote sits on. it.stacks = [[dx, dy, facing, count]] in plan feet from the item's anchor; each stack's
    // origin is the centre of its back edge, like any item, so its front faces the aisle.
    const [w, h, d] = s, g = new THREE.Group();
    const black = mat('tote black', 0x18191a, 0.55, 0.02), yellow = mat('tote yellow', 0xf2c11a, 0.48, 0.02);
    const body = new THREE.CylinderGeometry(Math.SQRT1_2, Math.SQRT1_2 * 0.91, 1, 4, 1).rotateY(Math.PI / 4);
    const hb = h - 2.4;                                                   // base height under the rim
    for (const [dx, dy, f, n] of it.stacks) {
      const st = new THREE.Group();
      st.position.set(dx * 12, 0, dy * 12); st.rotation.y = THREE.MathUtils.degToRad(180 - f);
      for (let k = 0; k < n; k++) {
        const y = k * h;
        const b = add(st, body, black, 0, y + hb / 2, d / 2); b.scale.set(w - 0.9, hb, d - 0.9);
        box(st, w - 0.3, 0.9, d - 0.3, black, 0, y + hb + 0.15, d / 2);                       // rim
        for (const z of [-0.15, d + 0.15]) box(st, 8.5, 1.4, 1.1, black, 0, y + hb - 0.9, z < 0 ? 0.45 : d - 0.45);   // end handles
        box(st, w, 1.3, d, yellow, 0, y + hb + 0.6 + 0.65, d / 2);                            // lid
        box(st, w - 4.2, 0.5, d - 5.5, yellow, 0, y + h - 0.25 - 0.01, d / 2);                // raised centre
        for (const x of [-w / 2 - 0.12, w / 2 + 0.12]) for (const z of [d * 0.28, d * 0.72]) box(st, 0.5, 1.7, 2.6, yellow, x, y + hb + 0.35, z);   // snap tabs
      }
      g.add(st);
    }
    return g;
  },
  car(s, it) { return buildCar(it); },                 // Tesla Model Y and Honda Insight, in vehicles.js
  wall_connector(s) { return buildWallConnector(s); },
  generic(s) {
    const [w, h, d] = s, g = new THREE.Group();
    box(g, w, h, d, greyPlastic(), 0, h / 2, d / 2); return g;
  },
};

// ---------------------------------------------------------------- placement
function place(g, it) {
  const wrap = new THREE.Group();
  g.scale.set(it.mirror ? -IN : IN, IN, IN);
  wrap.add(g);
  const [x, y, z] = it.at;
  wrap.position.copy(plan(x, y, z || 0));
  wrap.rotation.y = THREE.MathUtils.degToRad(180 - (it.facing || 0));
  return wrap;
}

// polyline runs (pipes): points in plan feet, radius in inches
function buildRun(run) {
  const g = new THREE.Group();
  const m = run.mat === 'pe' ? pe() : run.mat === 'foam' ? foam() : run.mat === 'copper' ? copper() : run.mat === 'condensate' ? greyPlastic() : run.mat === 'pvc' ? whitePlastic() : pe();
  const r = (run.dia || 1.66) / 2 * IN;
  const pts = run.points.map((p) => plan(p[0], p[1], p[2]));
  for (let i = 0; i < pts.length - 1; i++) tube(g, pts[i], pts[i + 1], r, m);
  for (let i = 1; i < pts.length - 1; i++) { const s = new THREE.Mesh(new THREE.SphereGeometry(r * 1.15, 12, 8), m); s.position.copy(pts[i]); g.add(s); }
  return g;
}

// ducts: { type: supply|return|transfer|erv|exhaust, shape: rect|round, size: [w, h] or dia (in), points: [[x,y,z], ...] plan ft }
function buildDuct(dc) {
  const g = new THREE.Group();
  const m = DUCT[dc.type] || DUCT.supply;
  const pts = dc.points.map((p) => plan(p[0], p[1], p[2]));
  if (dc.shape === 'round' || typeof dc.size === 'number') {
    const r = (typeof dc.size === 'number' ? dc.size : dc.size[0]) / 2 * IN;
    const fm = dc.flex ? (DUCT['flex_' + dc.type] || m) : m;
    for (let i = 0; i < pts.length - 1; i++) tube(g, pts[i], pts[i + 1], dc.flex ? r * 0.94 : r, fm, 18);
    for (let i = 1; i < pts.length - 1; i++) { const s = new THREE.Mesh(new THREE.SphereGeometry(dc.flex ? r * 0.94 : r, 16, 10), fm); s.position.copy(pts[i]); g.add(s); }
    if (dc.flex) {                                  // flex duct: the wire helix shows as a rib every 3 in or so
      const rib = new THREE.TorusGeometry(r * 0.97, r * 0.06, 4, 16), z = new THREE.Vector3(0, 0, 1);
      for (let i = 0; i < pts.length - 1; i++) {
        const d = pts[i + 1].clone().sub(pts[i]), len = d.length(), n = Math.floor(len / (3 * IN));
        if (!n) continue;
        const q = new THREE.Quaternion().setFromUnitVectors(z, d.clone().normalize());
        for (let k = 1; k <= n; k++) { const me = new THREE.Mesh(rib, fm); me.position.copy(pts[i]).addScaledVector(d, k / (n + 1)); me.quaternion.copy(q); g.add(me); }
      }
    }
  } else {
    const [w, h] = dc.size.map((v) => v * IN);
    for (let i = 0; i < pts.length - 1; i++) {
      const a = pts[i].clone(), b = pts[i + 1].clone(), dir = b.clone().sub(a).normalize();
      // lengthen horizontal pieces by half the duct width so corners close
      if (Math.abs(dir.y) < 0.99) { a.addScaledVector(dir, i > 0 ? -w / 2 : 0); b.addScaledVector(dir, i < pts.length - 2 ? w / 2 : 0); }
      rectDuct(g, a, b, w, h, m);
    }
  }
  // registers and grilles: ceiling ones lie flat, wall ones face a compass side (N, S, E or W)
  for (const gr of dc.grilles || []) {
    const [x, y, z] = gr.at, [gw, gh] = (gr.size || [10, 6]).map((v) => v * IN), t = 0.7 * IN;
    const dims = !gr.wall ? [gw, t, gh] : /[NS]/.test(gr.wall) ? [gw, gh, t] : [t, gh, gw];
    const me = new THREE.Mesh(new THREE.BoxGeometry(...dims), DUCT.grille);
    me.position.copy(plan(x, y, z));
    g.add(me);
    const sl = new THREE.Mesh(new THREE.BoxGeometry(dims[0] * (dims[0] > t * 2 ? 0.86 : 1.5), dims[1] * (dims[1] > t * 2 ? 0.8 : 1.5), dims[2] * (dims[2] > t * 2 ? 0.86 : 1.5)), DUCT.slot);
    sl.position.copy(me.position); g.add(sl);
  }
  return g;
}

// ---------------------------------------------------------------- baked geometry removal
// The Blender model has generic appliance boxes (stainless fridge, oven fronts, washer, ...). Triangles of those
// materials whose centre falls inside an item's cull box are dropped at load, so the real models replace them.
export function cullBaked(roots, items) {
  const names = new Set(items.flatMap((it) => it.replaces_nodes || []));
  if (names.size) for (const r of roots) { const gone = []; r.traverse((o) => { if (names.has(o.name)) gone.push(o); }); for (const o of gone) o.removeFromParent(); }
  const boxes = [];
  for (const it of items) for (const c of it.cull || []) {
    const [x0, y0, z0, x1, y1, z1] = c.box;
    boxes.push({ b: new THREE.Box3(plan(Math.min(x0, x1), Math.min(y0, y1), Math.min(z0, z1)), plan(Math.max(x0, x1), Math.max(y0, y1), Math.max(z0, z1))), mats: new Set(c.materials) });
  }
  if (!boxes.length) return 0;
  let dropped = 0;
  const emptied = [];
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3(), ctr = new THREE.Vector3();
  for (const r of roots) r.traverse((o) => {
    if (!o.isMesh || o.isInstancedMesh || Array.isArray(o.material) || o.userData.house) return;
    const mn = o.material.name || '';
    const hits = boxes.filter((bx) => bx.mats.has(mn));
    if (!hits.length) return;
    const g = o.geometry; if (!g.boundingBox) g.computeBoundingBox();
    const wb = g.boundingBox.clone().applyMatrix4(o.matrixWorld);
    const near = hits.filter((bx) => bx.b.intersectsBox(wb));
    if (!near.length) return;
    const P = g.attributes.position, I = g.index;
    const n = I ? I.count : P.count, keep = [];
    for (let k = 0; k < n; k += 3) {
      const ia = I ? I.getX(k) : k, ib = I ? I.getX(k + 1) : k + 1, ic = I ? I.getX(k + 2) : k + 2;
      a.fromBufferAttribute(P, ia).applyMatrix4(o.matrixWorld);
      b.fromBufferAttribute(P, ib).applyMatrix4(o.matrixWorld);
      c.fromBufferAttribute(P, ic).applyMatrix4(o.matrixWorld);
      ctr.copy(a).add(b).add(c).divideScalar(3);
      if (near.some((bx) => bx.b.containsPoint(ctr))) { dropped++; continue; }
      keep.push(ia, ib, ic);
    }
    if (keep.length === n) return;
    if (!keep.length) { emptied.push(o); return; }           // nothing left of it
    g.setIndex(keep);
    g.computeBoundingBox(); g.computeBoundingSphere();
  });
  for (const o of emptied) o.removeFromParent();
  return dropped;
}

// ---------------------------------------------------------------- open web floor trusses
// data.trusses = { regions: [[x0, y0, x1, y1], ...] plan ft, z0 ft (ceiling), depth_in, spacing_in, deck_in }
// Trusses span north-south (an assumption until the truss drawings exist): 2x4 flat chords, W pattern webs.
function buildTrusses(t) {
  const g = new THREE.Group(); g.name = 'Floor trusses';
  if (!t) return g;
  const wood = mat('truss lumber', 0xd9bf8f, 0.8), deckM = mat('attic deck', 0xc9a978, 0.85);
  const geos = [];
  const D = t.depth_in / 12, CH = 1.5 / 12, CW = 3.5 / 12, sp = t.spacing_in / 12, z0 = t.z0;
  const push = (geo, m4) => { geo.applyMatrix4(m4); geos.push(geo); };
  const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), one = new THREE.Vector3(1, 1, 1);
  // Held just inside each region and above the ceiling drywall, so no truss face lands on a wall, the ceiling or the
  // loft edge (coplanar faces showed the chords and webs through the drywall).
  const E = 0.05, zb = 0.07, zt = 0.01;
  for (const [rx0, ry0, rx1, ry1] of [...t.regions, ...(t.loft_regions || [])]) {
    const x0 = rx0 + E, x1 = rx1 - E, y0 = ry0 + E, y1 = ry1 - E;
    const L = y1 - y0, xs = [];
    if (t.grid_x0 != null) {                       // one grid across the house: trusses run continuous over the walls, so the bays line up
      for (let k = Math.ceil((x0 + CW / 2 - t.grid_x0) / sp - 1e-6); t.grid_x0 + k * sp <= x1 - CW / 2 + 1e-6; k++) xs.push(t.grid_x0 + k * sp);
    } else {
      const n = Math.max(1, Math.round((x1 - x0) / sp));
      for (let i = 0; i <= n; i++) xs.push(Math.min(x1 - CW / 2, Math.max(x0 + CW / 2, x0 + i * (x1 - x0) / n)));
    }
    for (const x of xs) {
      for (const zc of [z0 + zb + CH / 2, z0 + D - zt - CH / 2]) {                         // bottom and top chords
        m4.makeTranslation(...plan(x, y0 + L / 2, zc).toArray());
        push(new THREE.BoxGeometry(CW * F, CH * F, L * F), m4.clone());
      }
      const panels = Math.max(2, Math.round(L / (D * 1.5))), pl = L / panels;     // webs zigzag between the chords
      for (let k = 0; k < panels; k++) {
        const lo = z0 + zb + CH, hi = z0 + D - zt - CH;
        const a = plan(x, y0 + k * pl, k % 2 ? hi : lo), b = plan(x, y0 + (k + 1) * pl, k % 2 ? lo : hi);
        const d = b.clone().sub(a), len = d.length();
        q.setFromUnitVectors(new THREE.Vector3(0, 0, 1), d.clone().normalize());
        m4.compose(a.clone().addScaledVector(d, 0.5), q, one);
        push(new THREE.BoxGeometry(CW * F, CH * F, len), m4.clone());
      }
    }
  }
  if (geos.length) {
    const me = new THREE.Mesh(mergeGeometries(geos), wood); me.name = 'Open web floor trusses';
    me.userData.pass = true; me.userData.equipId = t.id; g.add(me);
  }
  const dt = (t.deck_in || 0.75) / 12, decks = [];
  for (const [x0, y0, x1, y1] of t.regions) {
    m4.makeTranslation(...plan((x0 + x1) / 2, (y0 + y1) / 2, z0 + D + dt / 2).toArray());
    const geo = new THREE.BoxGeometry((x1 - x0) * F, dt * F, (y1 - y0) * F); geo.applyMatrix4(m4); decks.push(geo);
  }
  if (decks.length) { const me = new THREE.Mesh(mergeGeometries(decks), deckM); me.name = 'Attic deck on trusses'; me.userData.equipId = t.id; me.userData.deckOverlay = true; g.add(me); }
  const lofts = [];                                                   // the loft's finished floor rides up with its trusses
  for (const [x0, y0, x1, y1] of t.loft_regions || []) {
    m4.makeTranslation(...plan((x0 + x1) / 2, (y0 + y1) / 2, z0 + D + dt / 2).toArray());
    const geo = new THREE.BoxGeometry((x1 - x0) * F, dt * F, (y1 - y0) * F); geo.applyMatrix4(m4); lofts.push(geo);
  }
  if (lofts.length) { const me = new THREE.Mesh(mergeGeometries(lofts), mat('loft floor oak', 0xc8a57a, 0.6)); me.name = 'Loft floor on trusses'; me.userData.equipId = t.id; me.userData.deckOverlay = true; g.add(me); }
  return g;
}

// ---------------------------------------------------------------- build everything
// Returns one group per layer plus byId, the semantic record behind every clickable thing.
export function buildEquipment(data) {
  const root = new THREE.Group(); root.name = 'Equipment';
  const layers = { appliances: new THREE.Group(), vehicles: new THREE.Group(), storage: new THREE.Group(), mechanical: new THREE.Group(), ducts: new THREE.Group(), fans: new THREE.Group(), trusses: buildTrusses(data.trusses) };
  for (const [k, g] of Object.entries(layers)) { g.name = g.name || k; root.add(g); }
  const byId = {};
  for (const it of data.items || []) {
    const fn = BUILD[it.builder] || BUILD.generic;
    const built = fn(it.size, it), rotor = built.userData.rotor;
    const obj = place(bake(built), it);
    if (rotor) {                     // a ceiling fan's blades stay their own mesh so they can turn (E or a tap, like a door)
      const r = bake(rotor); r.name = it.id + ' blades'; r.position.set(...rotor.userData.hub);
      r.userData.operable = 'spin'; obj.children[0].add(r);
    }
    obj.name = it.id;
    obj.traverse((o) => { o.userData.equipId = it.id; if (it.layer === 'fans') o.userData.pass = true; });
    (layers[it.layer] || layers.mechanical).add(obj);
    byId[it.id] = { ...it, obj };
  }
  for (const run of data.runs || []) {
    const g = buildRun(run); g.name = run.id;
    g.traverse((o) => { o.userData.equipId = run.info_of || run.id; o.userData.pass = true; });
    layers.mechanical.add(g);
    if (!run.info_of) byId[run.id] = { ...run, obj: g };
  }
  for (const dc of data.ducts || []) {
    const g = buildDuct(dc); g.name = dc.id;
    g.traverse((o) => { o.userData.equipId = dc.info_of || dc.id; o.userData.pass = true; o.userData.duct = true; o.renderOrder = 5; });
    layers.ducts.add(g);
    if (!dc.info_of) byId[dc.id] = { ...dc, obj: g };
  }
  if (data.trusses) byId[data.trusses.id] = { ...data.trusses, obj: layers.trusses };
  root.updateMatrixWorld(true);
  return { root, layers, byId };
}

export function equipMaterials() { return [...Object.values(M), ...vehicleMaterials(), ...Object.values(DUCT)]; }

// Duct x-ray: the ducts show through the house, but they still hide each other by depth, so the nearer duct is always
// the one on top. They draw after everything else (renderOrder in the transparent list), and a marker drawn just before
// them clears the depth buffer, so the house no longer hides them while duct to duct depth testing stays on. With depth
// testing off, as before, whichever duct three.js happened to sort last won, and runs crossed over and under at random.
const XRAY_ORDER = 1000;
const xrayMarker = new THREE.Mesh(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute([0, 0, 0, 0, 0, 0, 0, 0, 0], 3)),
  new THREE.MeshBasicMaterial({ transparent: true, colorWrite: false, depthWrite: false, depthTest: false }));
xrayMarker.name = 'Duct x-ray depth clear'; xrayMarker.frustumCulled = false; xrayMarker.renderOrder = XRAY_ORDER - 1; xrayMarker.visible = false;
xrayMarker.raycast = () => {}; xrayMarker.userData.pass = true;
// gl.clear only clears depth while depth writes are on, and three.js leaves the mask as the last drawn material set it.
// After a material with depthWrite off (glass, faded walls) the clear silently did nothing, so turn writes on first.
xrayMarker.onBeforeRender = (renderer) => { renderer.state.buffers.depth.setMask(true); renderer.clearDepth(); };
export function setDuctXray(on, ducts) {
  if (ducts && xrayMarker.parent !== ducts) ducts.add(xrayMarker);
  xrayMarker.visible = on;
  for (const [k, m] of Object.entries(DUCT)) {
    if (m.userData.base === undefined) m.userData.base = m.color.getHex();
    m.color.setHex(on ? XRAY[k] : m.userData.base);
    // opaque colour, but in the transparent list so it comes after glass and the faded walls
    m.depthTest = true; m.depthWrite = true; m.transparent = on; m.opacity = 1;
    m.emissive.setHex(on ? XRAY[k] : 0x000000); m.emissiveIntensity = on ? 0.45 : 0;
    m.needsUpdate = true;
  }
  if (ducts) ducts.traverse((o) => { if (o !== xrayMarker && o !== ducts) o.renderOrder = on ? XRAY_ORDER : 5; });
}

// ---------------------------------------------------------------- info card
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
// The card leads with what matters day to day: what it is, the model, the price, sizes and specs, and a way to the
// product. Where a fact came from, what was assumed and why it sits where it does are kept, folded away under
// "Notes and sources" (Maxwell, 11/17/2026).
export function infoHTML(it) {
  const inf = it.info || {};
  const specs = (inf.specs || []).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('');
  const notes = (inf.notes || []).map((n) => `<li>${esc(n)}</li>`).join('');
  const linkList = (inf.links || []).map(([t, u]) => `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(t)}</a>`);
  // a bought product with no link on file yet: offer a web search for its model
  if (!linkList.length && inf.model && !it.kind && it.builder) linkList.push(`<a href="https://www.google.com/search?q=${encodeURIComponent(inf.model.split(',')[0])}" target="_blank" rel="noopener">Search the web for this model</a>`);
  const links = linkList.join(' · ');
  const place = inf.placement ? `<p class="place"><b>Placement.</b> ${esc(inf.placement)}</p>` : '';
  return `<div class="eyebrow">${esc(it.category || it.system || '')}</div>
    <h2>${esc(it.name)}</h2>
    ${inf.model ? `<p class="model">${esc(inf.model)}</p>` : ''}
    ${inf.price ? `<p class="price">${esc(inf.price)}</p>` : ''}
    ${specs ? `<dl>${specs}</dl>` : ''}
    ${links ? `<p class="links">${links}</p>` : ''}
    ${notes || place ? `<details><summary>Notes and sources</summary>${place}${notes ? `<ul>${notes}</ul>` : ''}</details>` : ''}`;
}
