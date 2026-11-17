// Appliances, mechanical equipment and HVAC ducts for the walkthrough.
// Everything is built here in three.js from site/models/equipment.json, so it can change without a new Blender export.
// Sizes in the JSON are inches, positions are plan feet (x east, y south from the NW slab corner, z up from the slab).
// Each item is anchored at the centre of its BACK face on its base, and "facing" is the compass direction its
// front faces (0 north, 90 east, 180 south, 270 west).
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

const F = 0.3048, IN = 0.0254;
export const plan = (x, y, z = 0) => new THREE.Vector3(x * F, z * F, y * F);

// ---------------------------------------------------------------- materials
const M = {};
function mat(name, color, rough = 0.5, metal = 0, extra = {}) {
  if (!M[name]) { M[name] = new THREE.MeshStandardMaterial({ color, roughness: rough, metalness: metal, ...extra }); M[name].name = 'Equip ' + name; }
  return M[name];
}
const steel = () => mat('stainless', 0xb7babd, 0.32, 0.85);
const darkSteel = () => mat('dark stainless', 0x55595c, 0.35, 0.8);
const glass = () => mat('black glass', 0x0a0b0c, 0.06, 0.3);
const ceramic = () => mat('ceramic top', 0x0d0e10, 0.12, 0.2);
const zoneLine = () => mat('zone line', 0x6d7276, 0.6, 0);
const white = () => mat('enamel white', 0xeeeeea, 0.35, 0.05);
const greyPlastic = () => mat('grey plastic', 0x8a8d90, 0.55, 0);
const darkPlastic = () => mat('dark plastic', 0x232527, 0.6, 0);
const chrome = () => mat('chrome', 0xd8dadc, 0.15, 1);
const galv = () => mat('galvanized', 0xa8adb1, 0.45, 0.75);
const cabinetGrey = () => mat('unit cabinet', 0x9a9c97, 0.55, 0.25);
const pe = () => mat('PE pipe', 0x1a1a1a, 0.55, 0);
const foam = () => mat('foam insulation', 0x202020, 0.9, 0);
const brass = () => mat('brass', 0xb8933a, 0.3, 1);
const red = () => mat('red', 0xa3221d, 0.45, 0.1);
const blue = () => mat('blue', 0x1f5fa8, 0.45, 0.1);
const copper = () => mat('copper', 0xb8734a, 0.3, 1);
const pumpRed = () => mat('pump red', 0x8f1f1f, 0.4, 0.3);
const plywood = () => mat('plywood', 0xc9a978, 0.8, 0);
const rubber = () => mat('rubber', 0x111111, 0.85, 0);

// ducts get their own materials so the x-ray switch can change them without touching anything else
const DUCT = {
  supply: new THREE.MeshStandardMaterial({ color: 0xa9b8c6, roughness: 0.45, metalness: 0.6 }),
  return: new THREE.MeshStandardMaterial({ color: 0xc6aca9, roughness: 0.45, metalness: 0.6 }),
  transfer: new THREE.MeshStandardMaterial({ color: 0xc9c2a4, roughness: 0.6, metalness: 0.3 }),
  erv: new THREE.MeshStandardMaterial({ color: 0xb4c4a2, roughness: 0.6, metalness: 0.3 }),
  exhaust: new THREE.MeshStandardMaterial({ color: 0xbcb0c6, roughness: 0.5, metalness: 0.5 }),
  grille: new THREE.MeshStandardMaterial({ color: 0xf4f4f0, roughness: 0.5, metalness: 0.1 }),
  slot: new THREE.MeshStandardMaterial({ color: 0x55585a, roughness: 0.7, metalness: 0.2 }),
};
const XRAY = { supply: 0x2f8be0, return: 0xe0503a, transfer: 0xe0b23a, erv: 0x6cbf4a, exhaust: 0x9b59d0, grille: 0xffffff, slot: 0x222222 };
for (const [k, m] of Object.entries(DUCT)) m.name = 'Duct ' + k;

// ---------------------------------------------------------------- geometry helpers (inches, local frame)
// Local frame: +x to the right when facing the front, +y up, +z out of the front. Origin = back centre, bottom.
function box(g, w, h, d, m, x, y, z) {               // x, y, z = centre of the box
  const me = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m);
  me.position.set(x, y, z); g.add(me); return me;
}
function cyl(g, r, h, m, x, y, z, axis = 'y', seg = 28, r2 = r) {
  const me = new THREE.Mesh(new THREE.CylinderGeometry(r, r2, h, seg), m);
  if (axis === 'x') me.rotation.z = Math.PI / 2;
  if (axis === 'z') me.rotation.x = Math.PI / 2;
  me.position.set(x, y, z); g.add(me); return me;
}
function ring(g, r, t, m, x, y, z, axis = 'z') {      // torus in the plane normal to axis
  const me = new THREE.Mesh(new THREE.TorusGeometry(r, t, 10, 40), m);
  if (axis === 'y') me.rotation.x = Math.PI / 2;
  if (axis === 'x') me.rotation.y = Math.PI / 2;
  me.position.set(x, y, z); g.add(me); return me;
}
function bar(g, len, x, y, z, vertical, m = steel()) {   // a stand-off bar handle on a front face at depth z
  const r = 0.4;
  if (vertical) {
    cyl(g, r, len, m, x, y, z + 1.3);
    for (const s of [-1, 1]) cyl(g, 0.3, 1.3, m, x, y + s * (len / 2 - 1), z + 0.65, 'z');
  } else {
    cyl(g, r, len, m, x, y, z + 1.3, 'x');
    for (const s of [-1, 1]) cyl(g, 0.3, 1.3, m, x + s * (len / 2 - 1), y, z + 0.65, 'z');
  }
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

// ---------------------------------------------------------------- builders
// Each returns a THREE.Group in inches (local frame above). s = item.size = [w, h, d].
const BUILD = {
  wall_oven_double(s) {
    const [w, h, d] = s, g = new THREE.Group();
    box(g, w - 1.25, h - 0.5, d - 1.2, darkSteel(), 0, h / 2, (d - 1.2) / 2);               // chassis in the cutout
    const fz = d - 0.6;
    box(g, w, 4.2, 1.2, glass(), 0, h - 2.1, fz);                                            // control panel
    const dh = (h - 4.4) / 2;
    for (let k = 0; k < 2; k++) {
      const y0 = k * dh;
      box(g, w, dh - 0.2, 1.2, steel(), 0, y0 + dh / 2, fz);                                  // door
      box(g, w - 7, dh * 0.5, 0.15, glass(), 0, y0 + dh * 0.45, fz + 0.62);                   // window
      bar(g, w - 5, 0, y0 + dh - 2.6, fz + 0.6, false);
    }
    return g;
  },
  cooktop_induction(s) {
    const [w, , d] = s, g = new THREE.Group();
    box(g, w, 0.25, d, ceramic(), 0, 0.125, d / 2);                                          // glass top on the counter
    box(g, 29.2, 3.4, 20.2, darkPlastic(), 0, -1.7, d / 2);                                  // body below the counter
    const zones = [[-8.3, d - 7, 4.2], [-8.3, 6.5, 3.7], [0, d / 2, 5], [8.3, d - 7, 4.2], [8.3, 6.5, 3.3]];
    for (const [x, z, r] of zones) ring(g, r, 0.08, zoneLine(), x, 0.27, z, 'y');
    box(g, 14, 0.02, 1.4, zoneLine(), 0, 0.26, d - 1.6);                                     // touch control strip
    return g;
  },
  fridge_bottom_freezer(s) {
    const [w, h, d] = s, g = new THREE.Group();
    const body = d - 3.2;
    box(g, w - 0.3, h - 0.6, body, steel(), 0, (h - 0.6) / 2, body / 2);
    box(g, w - 0.4, 0.6, body - 1, darkPlastic(), 0, h - 0.3, body / 2 - 0.5);               // hinge cover
    const fh = 26, dz = body + 1.25;
    box(g, w, fh - 0.3, 2.5, steel(), 0, fh / 2, dz);                                        // freezer drawer
    box(g, w, h - fh - 0.9, 2.5, steel(), 0, fh + (h - fh - 0.9) / 2, dz);                    // fresh food door
    bar(g, w - 6, 0, fh - 3, dz + 1.25, false);
    bar(g, 30, w / 2 - 2.5, fh + 24, dz + 1.25, true);
    box(g, 6.5, 9, 0.1, darkSteel(), -w / 2 + 6, fh + 28, dz + 1.27);                         // filter/controls badge
    box(g, w - 2, 3.5, 0.4, darkPlastic(), 0, 1.75, body + 0.1);                             // toe grille
    return g;
  },
  fridge_french_door(s) {          // two French doors over a freezer drawer, water and ice dispenser in the left door
    const [w, h, d] = s, g = new THREE.Group();
    const body = d - 3.0;
    box(g, w - 0.3, h - 0.6, body, steel(), 0, (h - 0.6) / 2, body / 2);
    box(g, w - 0.4, 0.6, body - 1, darkPlastic(), 0, h - 0.3, body / 2 - 0.5);               // hinge cover
    const fh = 25, dz = body + 1.25, dw = w / 2 - 0.1;
    box(g, w, fh - 0.4, 2.5, steel(), 0, fh / 2, dz);                                        // freezer drawer
    box(g, dw, h - fh - 0.9, 2.5, steel(), -w / 4 - 0.025, fh + (h - fh - 0.9) / 2, dz);       // left door
    box(g, dw, h - fh - 0.9, 2.5, steel(), w / 4 + 0.025, fh + (h - fh - 0.9) / 2, dz);        // right door
    bar(g, w - 8, 0, fh - 3, dz + 1.25, false);
    bar(g, 26, -1.6, fh + 24, dz + 1.25, true);
    bar(g, 26, 1.6, fh + 24, dz + 1.25, true);
    box(g, 7, 12, 0.3, darkSteel(), -w / 4 - 1.5, fh + 21, dz + 1.3);                         // dispenser panel
    box(g, 5.6, 7.5, 0.8, darkPlastic(), -w / 4 - 1.5, fh + 19.2, dz + 1.15);                 // dispenser recess
    box(g, w - 2, 3.5, 0.4, darkPlastic(), 0, 1.75, body + 0.1);                             // toe grille
    return g;
  },
  dishwasher(s) {
    const [w, h, d] = s, g = new THREE.Group();
    box(g, w - 0.4, h - 4, d - 1.3, darkSteel(), 0, (h - 4) / 2 + 4, (d - 1.3) / 2);
    box(g, w, h - 4.4, 1.2, steel(), 0, 4.4 + (h - 4.4) / 2, d - 0.6);                       // door
    box(g, 8, 1.2, 1.0, darkPlastic(), 0, h - 3.2, d + 0.05);                                // pocket handle
    box(g, w - 0.6, 3.8, 0.5, darkPlastic(), 0, 1.9, d - 2.5);                               // toe kick
    box(g, 0.6, 0.6, 0.1, mat('led', 0x2f6fd1, 0.4, 0, { emissive: 0x1f4fb0, emissiveIntensity: 0.6 }), 0, 4.8, d + 0.01); // InfoLight
    return g;
  },
  disposal(s) {
    const [w, h] = s, g = new THREE.Group(), r = w / 2;
    cyl(g, r, h * 0.62, darkPlastic(), 0, h * 0.31, r);                                     // motor housing
    cyl(g, r * 0.92, h * 0.3, greyPlastic(), 0, h * 0.62 + h * 0.15, r);                     // grind chamber
    cyl(g, 3.4, h * 0.08, steel(), 0, h - h * 0.04, r);                                      // mount
    cyl(g, 0.75, 6, greyPlastic(), r + 2.5, h * 0.7, r, 'x');                                // discharge elbow
    return g;
  },
  beverage_center(s) {
    const [w, h, d] = s, g = new THREE.Group();
    box(g, w - 0.4, h - 0.2, d - 1.6, darkSteel(), 0, h / 2, (d - 1.6) / 2);
    box(g, w, h - 4.4, 1.6, steel(), 0, 4.4 + (h - 4.4) / 2, d - 0.8);                       // door frame
    box(g, w - 4, h - 9, 0.2, glass(), 0, 4.4 + (h - 4.4) / 2, d + 0.02);                    // glass
    box(g, w - 0.6, 3.6, 0.5, darkPlastic(), 0, 2.3, d - 1.2);                               // front vent grille
    for (let k = 0; k < 6; k++) box(g, w - 2, 0.3, 0.2, greyPlastic(), 0, 1.2 + k * 0.55, d - 0.9);
    bar(g, 24, -w / 2 + 2, 4.4 + (h - 4.4) / 2, d, true);
    return g;
  },
  front_load_laundry(s, it) {
    const [w, h, d] = s, g = new THREE.Group();
    const dark = it.finish === 'graphite';
    const body = dark ? darkSteel() : white();
    box(g, w, h - 1, d - 2.4, body, 0, (h - 1) / 2 + 1, (d - 2.4) / 2);
    box(g, w - 1, 1, d - 3, darkPlastic(), 0, 0.5, (d - 3) / 2);                              // feet
    box(g, w, 6.5, 1.6, body, 0, h - 3.25, d - 2.4 + 0.8);                                   // control panel
    box(g, 11, 2.8, 0.1, glass(), 2, h - 3.4, d - 0.75);                                     // display
    cyl(g, 1.6, 1.0, chrome(), -8.5, h - 3.3, d - 0.3, 'z');                                 // dial
    const dz = d - 2.4;
    ring(g, 8.6, 1.2, it.kind_ring === 'dark' ? darkSteel() : chrome(), 0, 19, dz + 1.2);    // door ring
    cyl(g, 7.6, 0.6, it.label === 'dryer' ? darkSteel() : glass(), 0, 19, dz + 0.6, 'z');    // dryer door is solid, washer glass
    box(g, 1.3, 4.5, 1.3, chrome(), 7.6, 19, dz + 1.6);                                      // door handle
    return g;
  },
  hpwh(s) {
    const [dia, h] = s, g = new THREE.Group(), r = dia / 2;
    box(g, dia + 4, 2, dia + 4, galv(), 0, 1, r + 2);                                       // 2" drain pan (U-11 detail)
    cyl(g, r, h - 14, white(), 0, 2 + (h - 14) / 2, r + 2, 'y', 40);                         // tank
    cyl(g, r + 0.3, 12, greyPlastic(), 0, h - 6, r + 2, 'y', 40);                            // heat pump section
    cyl(g, r - 1.5, 0.6, darkPlastic(), 0, h + 0.1, r + 2, 'y', 40);                         // top grille, standing proud of the cap (a shared top face flickered)
    box(g, 6, 3.5, 0.6, darkPlastic(), 0, h - 9, dia + 2.2);                                 // display
    for (const [x, m] of [[-5.5, blue()], [5.5, red()]]) {                                   // cold in, hot out
      cyl(g, 0.55, 30, m === blue() ? copper() : copper(), x, h + 15, r + 2);
      ring(g, 0.9, 0.25, m, x, h + 3, r + 2, 'y');
    }
    box(g, 4.2, 4.2, 5.5, pumpRed(), 5.5, h + 14, r + 5.4);                                  // recirculation pump (U-11)
    cyl(g, 4, 9, galv(), -5.5, h + 22, r + 2 - 7.5);                                         // expansion tank (U-11 detail)
    cyl(g, 0.35, h - 6, mat('condensate', 0xe9eef2, 0.4, 0, { transparent: true, opacity: 0.8 }), r - 1, (h - 6) / 2 + 2, r + 2 + r * 0.7); // condensate line
    return g;
  },
  geo_horizontal(s) {
    // GeoComfort ZT 048 horizontal, left hand return, end discharge: [A width, C height, B length] = 21.7 x 21.2 x 56 in.
    // Local: length along x. +x end = supply discharge, -x end = front (water and electrical connections).
    // Left hand return = the return opening is on your left as you face the front end, which is the back (z = 0) side here.
    const [w, h, len] = s, g = new THREE.Group();
    for (const x of [-len / 2 + 4, len / 2 - 4]) box(g, 4, 4, w + 2, rubber(), x, -2, w / 2);   // vibration isolation rails
    box(g, len + 8, 1.5, w + 10, plywood(), 0, -4.75, w / 2);                                // service platform
    box(g, len, h, w, cabinetGrey(), 0, h / 2, w / 2);
    for (const x of [-len / 2 + 10, 6]) box(g, 5, 1.4, 0.4, darkPlastic(), x, h * 0.72, w + 0.2);   // access panel pulls
    box(g, 36, 18, 2.4, galv(), -len / 2 + 2 + 18, h / 2, -1.2);                             // AFR1836A 18 x 36 filter rack on the return side
    box(g, 34.5, 16.5, 0.3, mat('filter media', 0xe8e6da, 0.9), -len / 2 + 2 + 18, h / 2, -2.45);
    box(g, 9, 12.5, 11.6, galv(), len / 2 + 4.5, h - 1.5 - 6.25, w / 2);                     // 15 kW heater on the 11.6 x 12.5 supply opening
    box(g, 4, 5, 0.5, darkPlastic(), len / 2 + 4.5, h - 1.5 - 6.25, w / 2 + 6.05);
    for (const [y, m] of [[5.6, blue()], [17.6, red()]]) {                                   // source water in/out, hose kit and ball valves
      cyl(g, 0.75, 9, rubber(), -len / 2 - 4.5, y, w * 0.3, 'x');
      cyl(g, 0.95, 2.6, brass(), -len / 2 - 10.3, y, w * 0.3, 'x');
      box(g, 0.6, 0.6, 3, m, -len / 2 - 10.3, y + 1.2, w * 0.3);
    }
    box(g, 0.4, 7, 5, darkPlastic(), -len / 2 - 0.2, h - 6, w * 0.72);                       // control box cover
    cyl(g, 0.5, 6, mat('condensate', 0xe9eef2, 0.4, 0, { transparent: true, opacity: 0.8 }), len / 2 - 6, 1.5, w + 3, 'z');   // condensate to the EZ-Trap
    return g;
  },
  flow_center(s) {
    const [w, h, d] = s, g = new THREE.Group();
    box(g, w, h, d, foam(), 0, h / 2, d / 2);                                                 // insulated cabinet
    box(g, w - 2, 1, d - 2, darkPlastic(), 0, h + 0.5, d / 2);                               // fill cap deck
    cyl(g, 1.6, 1.2, darkPlastic(), 0, h + 1.6, d / 2);
    for (const x of [-w / 4, w / 4]) {                                                       // two UPS26-99 pumps under it
      cyl(g, 3.2, 5.5, pumpRed(), x, -4, d / 2 + 1, 'z');
      box(g, 4, 3, 3, darkPlastic(), x, -4, d / 2 + 4.6);
    }
    box(g, w - 2, 2, 4, pe(), 0, -8, d / 2);
    box(g, 3, 3, 0.4, mat('flo link label', 0xd0d4d7, 0.5), 0, h * 0.6, d + 0.2);
    return g;
  },
  pe_manifold(s, it) {
    // Pair of 1-1/4" PE headers, 5 x 3/4" circuits each with a 1" ball valve; loops drop to the slab sweeps.
    const [w, h, d] = s, g = new THREE.Group();
    const R_H = 0.83, R_C = 0.525, n = 5, z = d / 2;
    const rows = [{ y: h - 4, m: blue(), lbl: 'supply' }, { y: h - 16, m: red(), lbl: 'return' }];
    for (const [ri, row] of rows.entries()) {
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
    for (const x of [-w / 3, w / 6]) cyl(g, 2.25, 3, mat('pvc grey', 0x8e9193, 0.6), x, 1.5, z);           // 4" sweeps at the slab
    return g;
  },
  erv(s) {
    const [w, h, d] = s, g = new THREE.Group();
    box(g, w, h, d, mat('erv cabinet', 0xd8d8d2, 0.5, 0.2), 0, h / 2, d / 2);
    for (const [x, z] of [[-w / 4, d / 4], [w / 4, d / 4], [-w / 4, 3 * d / 4], [w / 4, 3 * d / 4]]) cyl(g, 3, 3, galv(), x, h + 1.5, z);
    box(g, 6, 4, 0.5, darkPlastic(), w / 2 - 6, h - 5, d + 0.25);
    return g;
  },
  generic(s) {
    const [w, h, d] = s, g = new THREE.Group();
    box(g, w, h, d, greyPlastic(), 0, h / 2, d / 2); return g;
  },
  microwave_combi(s) {             // Breville Combi Wave: brushed steel box on feet, glass door on the left, controls and dial on the right
    const [w, h, d] = s, g = new THREE.Group();
    const body = d - 0.9, feet = 0.5, ph = h - feet, pw = 5.2;                                  // 0.9 in handle in front of the body
    for (const x of [-w / 2 + 1.5, w / 2 - 1.5]) for (const z of [2, body - 2]) cyl(g, 0.6, feet, rubber(), x, feet / 2, z);
    box(g, w, ph, body - 1.2, steel(), 0, feet + ph / 2, (body - 1.2) / 2);                  // wrap
    const dw = w - pw - 0.2, dx = -w / 2 + dw / 2;
    box(g, dw, ph - 0.3, 1.2, steel(), dx, feet + ph / 2, body - 0.6);                         // door
    box(g, dw - 4.2, ph - 4, 0.12, glass(), dx - 0.6, feet + ph / 2, body + 0.02);                // window
    box(g, pw, ph - 0.3, 1.2, darkSteel(), w / 2 - pw / 2, feet + ph / 2, body - 0.6);         // control panel
    box(g, 3.6, 1.4, 0.1, mat('lcd', 0x0c1a22, 0.2, 0, { emissive: 0x1d3a4a, emissiveIntensity: 0.5 }), w / 2 - pw / 2, feet + ph - 2.4, body + 0.02);
    cyl(g, 1.25, 0.8, steel(), w / 2 - pw / 2, feet + ph / 2 - 0.4, body + 0.4, 'z');         // dial
    for (let k = 0; k < 4; k++) box(g, 1.4, 0.55, 0.12, greyPlastic(), w / 2 - pw / 2 + (k % 2 ? 0.85 : -0.85), feet + 2.0 + Math.floor(k / 2) * 0.9, body + 0.03);
    bar(g, ph - 3.5, dx + dw / 2 - 1.3, feet + ph / 2, body, true);                             // pull handle on the door's right edge
    return g;
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
  const m = run.mat === 'pe' ? pe() : run.mat === 'foam' ? foam() : run.mat === 'copper' ? copper() : run.mat === 'condensate' ? greyPlastic() : pe();
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
    for (let i = 0; i < pts.length - 1; i++) tube(g, pts[i], pts[i + 1], r, m, 18);
    for (let i = 1; i < pts.length - 1; i++) { const s = new THREE.Mesh(new THREE.SphereGeometry(r, 16, 10), m); s.position.copy(pts[i]); g.add(s); }
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
    const n = Math.max(1, Math.round((x1 - x0) / sp)), L = y1 - y0;
    for (let i = 0; i <= n; i++) {
      const x = Math.min(x1 - CW / 2, Math.max(x0 + CW / 2, x0 + i * (x1 - x0) / n));
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
  const layers = { appliances: new THREE.Group(), mechanical: new THREE.Group(), ducts: new THREE.Group(), trusses: buildTrusses(data.trusses) };
  for (const [k, g] of Object.entries(layers)) { g.name = g.name || k; root.add(g); }
  const byId = {};
  for (const it of data.items || []) {
    const fn = BUILD[it.builder] || BUILD.generic;
    const obj = place(fn(it.size, it), it);
    obj.name = it.id;
    obj.traverse((o) => { o.userData.equipId = it.id; });
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

export function equipMaterials() { return [...Object.values(M), ...Object.values(DUCT)]; }

export function setDuctXray(on) {
  for (const [k, m] of Object.entries(DUCT)) {
    if (m.userData.base === undefined) m.userData.base = m.color.getHex();
    m.color.setHex(on ? XRAY[k] : m.userData.base);
    m.depthTest = !on; m.depthWrite = !on; m.transparent = on; m.opacity = on ? 0.8 : 1;
    m.emissive.setHex(on ? XRAY[k] : 0x000000); m.emissiveIntensity = on ? 0.45 : 0;
    m.needsUpdate = true;
  }
}

// ---------------------------------------------------------------- info card
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
export function infoHTML(it) {
  const inf = it.info || {};
  const specs = (inf.specs || []).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('');
  const notes = (inf.notes || []).map((n) => `<li>${esc(n)}</li>`).join('');
  const links = (inf.links || []).map(([t, u]) => `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(t)}</a>`).join(' · ');
  return `<div class="eyebrow">${esc(it.category || it.system || '')}</div>
    <h2>${esc(it.name)}</h2>
    ${inf.model ? `<p class="model">${esc(inf.model)}</p>` : ''}
    ${inf.price ? `<p class="price">${esc(inf.price)}</p>` : ''}
    ${specs ? `<dl>${specs}</dl>` : ''}
    ${notes ? `<ul>${notes}</ul>` : ''}
    ${inf.placement ? `<p class="place"><b>Placement.</b> ${esc(inf.placement)}</p>` : ''}
    ${links ? `<p class="links">${links}</p>` : ''}`;
}
