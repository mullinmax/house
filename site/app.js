// House walkthrough: three.js viewer for the parametric house model.
// The house is built in the browser from models/house.json (model/make_house.py) and the equipment from
// models/equipment.json (model/make_equipment.py). Terrain, trees and furniture are .glb parts listed in
// models/manifest.json, last exported from the archived Blender model. Add ?baked to the address to load the old
// Blender shell.glb and interior.glb instead of the generated house, for comparison.
// Units are metres, glTF Y up. Plan feet (x east, y south from the NW slab corner) map to (x*F, z, y*F).
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { PointerLockControls } from 'three/addons/controls/PointerLockControls.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { computeBoundsTree, disposeBoundsTree, acceleratedRaycast } from 'three-mesh-bvh';
import { buildEquipment, cullBaked, setDuctXray, infoHTML, equipMaterials } from './equipment.js';
import { buildHouse, houseRecordAt } from './house.js';

THREE.BufferGeometry.prototype.computeBoundsTree = computeBoundsTree;
THREE.BufferGeometry.prototype.disposeBoundsTree = disposeBoundsTree;
THREE.Mesh.prototype.raycast = acceleratedRaycast;

const F = 0.3048;
const EYE = 5.58 * F;          // 5'-7" eyes, a 5'-10" person (Maxwell, 11/16/2026)
const CROUCH = 3.2 * F;        // eye height crouched (C)
const DUCK_MIN = 2.4 * F;      // lowest the eyes go when ducking under a sloped roof
const HEAD = 0.35 * F;         // top of the head above the eyes
const RADIUS = 0.9 * F;        // body radius for wall collision
const STEP = 1.2 * F;          // tallest step you can walk up
const REACH = 6 * F;           // how far E reaches
const INFO_REACH = 30 * F;     // how far away you can ask about an appliance or a duct
const plan = (x, y, z = 0) => new THREE.Vector3(x * F, z * F, y * F);

// Fallback room spawns in plan feet [x, y, look x, look y], used when the model has no Spawn_<Room> nodes.
const ROOMS = {
  Kitchen: [9, 39.5, 8, 48], Living: [19, 29, 31, 27], Dining: [30, 44, 10, 44], Bed1: [37, 14, 37, 4],
  Bed2: [8, 7, 11, 1], Bed3: [8, 17, 1, 17], Bath1: [36, 27, 36, 32], Bath2: [19, 7, 19, 2],
  Garage: [79, 30, 79, 18], Outside_SW: [-35, 95, 21, 26],
};
const ROOM_LABELS = { Bed1: 'Bedroom 1', Bed2: 'Bedroom 2', Bed3: 'Bedroom 3', Bath1: 'Bath 1', Bath2: 'Bath 2', Outside_SW: 'Outside, southwest' };

// ---------------------------------------------------------------- renderer, scene
// No logarithmic depth: it writes depth per pixel, which turns off the GPU's early depth test and made every
// hidden surface cost full shading. The model's coplanar faces are nudged apart instead, and a 0.15 m near
// plane keeps enough depth precision. MSAA only where the screen isn't already high density.
const renderer = new THREE.WebGLRenderer({ antialias: window.devicePixelRatio < 1.5, powerPreference: 'high-performance' });
const MAX_DPR = Math.min(window.devicePixelRatio, 1.5);
let dpr = MAX_DPR;
renderer.setPixelRatio(dpr);
renderer.localClippingEnabled = true;
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.shadowMap.autoUpdate = false;     // re-rendered only when the view, a door or the light changes
document.body.prepend(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xbfd3e6);
scene.fog = new THREE.Fog(0xcbd9e6, 250, 1400);
const camera = new THREE.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.15, 2500);

const hemi = new THREE.HemisphereLight(0xdfe8f2, 0x6d6450, 1.1);
scene.add(hemi);
const sun = new THREE.DirectionalLight(0xfff1dc, 2.6);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
Object.assign(sun.shadow.camera, { left: -40, right: 40, top: 40, bottom: -40, near: 1, far: 400 });
sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.02;
scene.add(sun, sun.target);
const fill = new THREE.AmbientLight(0xffffff, 0.25);
scene.add(fill);

// ---------------------------------------------------------------- loading
const $ = (id) => document.getElementById(id);
const touch = matchMedia('(pointer: coarse)').matches;
const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
const world = new THREE.Group(); scene.add(world);
const colliders = [];
const pickables = [];   // every non-instanced mesh, for door picking
const operables = [];
const spawns = {};
let sunDir = new THREE.Vector3(0.35, 0.6, 0.7).normalize();
let manifest = {};
let daySky = null;
let night = false, shadowDirty = true;

async function getManifest() {
  try {
    const r = await fetch('models/manifest.json', { cache: 'no-cache' });
    if (r.ok) return await r.json();
  } catch (e) { /* fall through */ }
  return { parts: [{ file: 'house.glb' }] };
}

function progress(frac, msg) {
  $('bar').style.width = `${Math.round(frac * 100)}%`;
  if (msg) $('loadmsg').textContent = msg;
}

// The house (shell, interior, site) loads first so you can start walking; furniture and trees stream in
// behind it and are prepared one part per idle moment, so the first frame is not held up by them.
const LATER = /^(furniture|trees)/i;
// Appliances, mechanical equipment, ducts and trusses: data in models/equipment.json, geometry built by equipment.js.
let equipData = null, equip = null;
async function getEquipment() {
  try {
    const r = await fetch('models/equipment.json', { cache: 'no-cache' });
    if (r.ok) return await r.json();
  } catch (e) { /* the walkthrough works without it */ }
  return null;
}

// The house: walls, roof, windows, doors, cabinets, trim, loft, garage and porch, from models/house.json.
// It replaces the Blender shell.glb and interior.glb, which ?baked brings back.
const BAKED = /[?&]baked\b/.test(location.search);
const HOUSE_PARTS = /^(shell|interior)$/i;
let house = null, houseMeta = {}, houseSpawns = {};
async function getHouse() {
  if (BAKED) return null;
  try {
    const r = await fetch('models/house.json', { cache: 'no-cache' });
    if (r.ok) return await r.json();
  } catch (e) { /* fall back to the baked parts */ }
  return null;
}

async function loadAll() {
  const [man, eq, hd] = await Promise.all([getManifest(), getEquipment(), getHouse()]);
  manifest = man; equipData = eq;
  setupSlice();
  let parts = man.parts || [];
  if (hd) {
    const skip = new Set((eq && eq.items || []).map((it) => it.id));      // appliances the equipment layer draws for real
    house = buildHouse(hd, { skip });
    houseMeta = hd.meta || {}; houseSpawns = hd.spawns || {};
    world.add(house.root);
    parts = parts.filter((p) => !HOUSE_PARTS.test(p.name || p.file.replace(/\.glb$/, '')));
    console.log(`house: ${house.recs.length} records built from house.json`);
  }
  const sizes = parts.map((p) => p.bytes || 1);
  const got = new Array(parts.length).fill(0);
  const isLater = parts.map((p) => LATER.test(p.name || p.file) && parts.some((q) => !LATER.test(q.name || q.file)));
  const firstTotal = sizes.reduce((a, b, i) => a + (isLater[i] ? 0 : b), 0);
  const upd = (msg) => progress(Math.min(1, got.reduce((a, b, i) => a + (isLater[i] ? 0 : b), 0) / firstTotal), msg);
  if (man.sky) loadSky(man.sky);
  if (man.sun_direction) {          // Blender world direction toward the sun, Z up
    const [x, y, z] = man.sun_direction; sunDir = new THREE.Vector3(x, z, -y).normalize();
  }
  let ready = false;
  const queue = [];
  const loads = parts.map((p, i) => new Promise((resolve) => {
    loader.load(`models/${p.file}`, (g) => {
      g.scene.name = p.name || p.file;
      got[i] = sizes[i];
      if (isLater[i]) { queue.push(g.scene); if (ready) drain(); }
      else { world.add(g.scene); upd(`Loaded ${p.file}`); }
      resolve();
    }, (e) => { if (e.total) { got[i] = sizes[i] * e.loaded / e.total; if (!isLater[i]) upd(`Loading ${p.file}`); } },
    (err) => { console.warn('failed', p.file, err); got[i] = sizes[i]; upd(`Could not load ${p.file}`); resolve(); });
  }));
  await Promise.all(loads.filter((_, i) => !isLater[i]));
  prepare([...world.children], true);
  ready = true;
  let busy = false;
  const idle = window.requestIdleCallback || ((f) => setTimeout(f, 30));
  function drain() {
    if (busy || !queue.length) return;
    busy = true;
    idle(() => {
      const root = queue.shift();
      world.add(root);
      prepare([root], false);
      busy = false; drain();
    }, { timeout: 500 });
  }
  drain();
  await Promise.all(loads);
  await new Promise((r) => { const t = setInterval(() => { if (!queue.length && !busy) { clearInterval(t); r(); } }, 100); });
  window.__allLoaded = true;
  console.log(`all parts in: ${colliders.length} colliders, ${operables.length} operable`);
}

function loadSky(file) {
  new THREE.TextureLoader().load(`models/${file}`, (t) => {
    t.mapping = THREE.EquirectangularReflectionMapping; t.colorSpace = THREE.SRGBColorSpace;
    daySky = t; if (!night) scene.background = t;
    const pm = new THREE.PMREMGenerator(renderer);
    scene.environment = pm.fromEquirectangular(t).texture;
    scene.environmentIntensity = night ? 0.04 : 0.6;
    pm.dispose();
  });
}

const RE_UTIL = /geothermal|septic|utilit|marker/i;
const RE_ROOF = /roof|seam|fascia|soffit|gutter|downspout|rafter|ceiling|loft floor|\bridge/i;   // \b keeps "fridge wall" cabinets out of the roof layer
const RE_NOCOLLIDE = /utilit|geothermal|septic|marker|leaf|leaves|crown|canopy|foliage|curtain|shade|rug|towel|light|lamp|glass pane|^Ground$/i;
const roofNodes = [], utilNodes = [], treeMeshes = [];
const LITE = /[?&]lite\b/.test(location.search);

const upperPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), 1e6);   // the slice: everything above it is cut away. 1e6 = nothing clipped
const houseMats = new Set(), furnitureMeshes = [], bakedDeck = [];
const nightFixtures = [];

// house.json says what of the baked export the generated house replaces: furniture now built in the browser
// (by name, or by box for pieces merged into per material meshes), pieces that only moved, and a stray site pad.
function applyHouseEdits(roots) {
  const gone = new Set(houseMeta.replace_nodes || []), moves = houseMeta.move_nodes || {};
  for (const r of roots) {
    if (!/^(furniture|site)/i.test(r.name)) continue;
    const drop = [];
    r.traverse((o) => {
      if (gone.has(o.name)) drop.push(o);
      const mv = moves[o.name];
      if (mv && !o.userData._moved) {
        o.userData._moved = true;
        o.position.x += mv[0] * F; o.position.z += mv[1] * F;
        if (mv[2]) o.rotateY(THREE.MathUtils.degToRad(mv[2]));
        if (mv[3]) o.position.y += mv[3] * F;              // optional 4th value: up (feet), to part flush faces
      }
    });
    for (const o of drop) o.removeFromParent();
    r.updateMatrixWorld(true);
    const culls = (houseMeta.cull || []).filter((c) => new RegExp('^' + (c.parts || 'furniture'), 'i').test(r.name));
    if (culls.length) cullBaked([r], [{ cull: culls }]);
  }
}

function prepare(roots, first) {
  if (house) applyHouseEdits(roots);
  for (const r of roots) r.updateMatrixWorld(true);
  const roofSet = new Set(), utilSet = new Set(), opRoots = new Set();
  const nFix = nightFixtures.length;
  for (const r of roots) r.traverse((o) => {
    const n = o.name || '';
    if (/^Spawn_/i.test(n)) { spawns[n.slice(6)] = o; return; }
    if (o.userData && o.userData.operable) { operables.push(makeOperable(o)); opRoots.add(o); }
    if (o !== world && o.parent !== world && RE_ROOF.test(n)) { roofNodes.push(o); roofSet.add(o); }
    if (o !== world && o.parent !== world && (n === 'Utilities' || RE_UTIL.test(n))) { utilNodes.push(o); utilSet.add(o); }
    if ((o.userData && o.userData.emissive_night) || RE_FIXTURE.test(n)) nightFixtures.push(o);
  });
  if (equipData) cullBaked(roots, equipData.items);      // the generic appliance boxes make way for the real models
  const merged = mergeStatic(roots, roofSet, utilSet, opRoots, nightFixtures.slice(nFix));
  for (const r of roots) r.updateMatrixWorld(true);
  for (const r of roots) r.traverse((o) => {
    o.matrixAutoUpdate = false;           // nothing static moves; operables update their own matrix
    if (!o.isMesh) return;
    o.castShadow = true; o.receiveShadow = true;
    const mats = [].concat(o.material);
    if (mats.some((m) => m && m.transparent && m.opacity < 0.99)) o.castShadow = false;
    const part = partOf(o);
    if (part && !/^(site|trees)$/i.test(part.name)) for (const m of mats) if (m) { m.clippingPlanes = [upperPlane]; m.clipShadows = true; houseMats.add(m); }
    if ((part && /^furniture/i.test(part.name)) || o.userData.layer === 'furniture') furnitureMeshes.push(o);
    if (!o.isInstancedMesh && mats[0] && mats[0].name === 'Attic Deck') bakedDeck.push(o);
    if (o.isInstancedMesh) {          // instanced trees: drawn only, no collision or picking. Names do not survive gltfpack, so the distant woods are told apart by instance count (a hundred or more vs. a few dozen near the house)
      for (const mm of mats) if (mm && mm.transparent) {
        mm.transparent = false; mm.alphaTest = 0.3; mm.depthWrite = true;   // cutout leaves sort and draw far faster
      }
      if (o.count >= 80) o.castShadow = false;       // distant woods: no shadows
      o.userData.fullCount = o.count; treeMeshes.push(o);
      return;
    }
    let pass = !!o.userData.pass;
    if (!pass) for (let p = o; p; p = p.parent) if (RE_NOCOLLIDE.test(p.name || '')) { pass = true; break; }
    o.userData.pass = pass;
    // The generated house maps a hit's faceIndex to its record through triangle ranges. A plain BVH reorders the
    // triangles, so a click could land on another record's range (the bi-parting door read as a clerestory window).
    // 'indirect' keeps the triangle order.
    o.geometry.computeBoundsTree(o.userData.house ? { indirect: true } : undefined);
    pickables.push(o);
    if (!pass) colliders.push(o);
  });
  console.log(`${roots.map((r) => r.name).join(', ')}: merged static meshes into ${merged} draw groups`);
  applyToggles();
  shadowDirty = true;
  if (!first) {                       // a part that streamed in after the house: match the current settings
    if (night && nightFixtures.length > nFix) setFixtureGlow(true);
    return;
  }
  const names = [...new Set([...Object.keys(ROOMS), ...Object.keys(spawns)])];
  setNight(false);
  addEquipment();
  lastRoom = names.includes('Outside_SW') ? 'Outside_SW' : names[0];
  setMode('orbit');
  $('loading').hidden = true; holdHint();
  if (touch) $('stick').hidden = mode !== 'walk';
  else if (mode === 'walk') $('hint').hidden = false;
  $('cross').hidden = mode !== 'walk';
  console.log(`walkthrough ready: ${colliders.length} colliders, ${operables.length} operable, ${Object.keys(spawns).length} spawns`);
}

// ---------------------------------------------------------------- static merge
// Thousands of small meshes cost one draw call each. Static meshes that share a material (and part,
// toggle group and a 20 m grid cell) are baked into one mesh in world space.
const RE_FIXTURE = /pendant|lamp|sconce|wall_light|ceiling_light|fixture|can_light|bulb/i;
function partOf(o) { let p = o; while (p && p.parent && p.parent !== world) p = p.parent; return p && p.parent === world ? p : null; }

function mergeStatic(roots, roofSet, utilSet, opRoots, fixtures) {
  const buckets = new Map();
  const fixtureSet = new Set(fixtures);
  for (const r of roots) r.traverse((o) => {
    if (!o.isMesh || o.isInstancedMesh || o.isSkinnedMesh || Array.isArray(o.material)) return;
    if (o.geometry.morphAttributes && Object.keys(o.geometry.morphAttributes).length) return;
    if (o.material.vertexColors || o.userData.house) return;   // generated house meshes keep their record ranges
    let tag = '', pass = false;
    for (let p = o; p && p !== world; p = p.parent) {
      if (opRoots.has(p) || fixtureSet.has(p)) return;    // moving parts and night fixtures stay separate
      if (roofSet.has(p)) tag = 'roof';
      else if (utilSet.has(p) && !tag) tag = 'util';
      if (RE_NOCOLLIDE.test(p.name || '')) pass = true;
    }
    const part = partOf(o); if (!part) return;
    const g = o.geometry; if (!g.attributes.position) return;
    if (!g.boundingBox) g.computeBoundingBox();
    const c = g.boundingBox.getCenter(new THREE.Vector3()).applyMatrix4(o.matrixWorld);
    const key = [part.name, tag, pass ? 1 : 0, o.material.uuid, Math.floor(c.x / 20), Math.floor(c.z / 20)].join('|');
    if (!buckets.has(key)) buckets.set(key, { part, tag, pass, mat: o.material, list: [] });
    buckets.get(key).list.push(o);
  });
  let groups = 0;
  for (const bk of buckets.values()) {
    if (bk.list.length < 2) continue;
    const geo = bakeMerge(bk.list);
    if (!geo) continue;
    const m = new THREE.Mesh(geo, bk.mat);
    m.name = `merged ${bk.part.name} ${bk.mat.name || ''}`.trim();
    m.userData.pass = bk.pass;
    bk.part.add(m);              // part scenes sit at the origin, so world-space geometry needs no transform
    for (const o of bk.list) o.removeFromParent();
    if (bk.tag === 'roof') roofNodes.push(m);
    if (bk.tag === 'util') utilNodes.push(m);
    groups++;
  }
  return groups;
}

function bakeMerge(list) {
  const hasUV = list.every((o) => o.geometry.attributes.uv);
  let nv = 0, ni = 0;
  for (const o of list) {
    const g = o.geometry, n = g.attributes.position.count;
    nv += n; ni += g.index ? g.index.count : n;
  }
  const pos = new Float32Array(nv * 3), nor = new Float32Array(nv * 3), uv = hasUV ? new Float32Array(nv * 2) : null;
  const idx = new Uint32Array(ni);
  const v = new THREE.Vector3(), nm = new THREE.Matrix3();
  let ov = 0, oi = 0;
  for (const o of list) {
    const g = o.geometry, P = g.attributes.position;
    if (!g.attributes.normal) g.computeVertexNormals();
    const N = g.attributes.normal, U = g.attributes.uv;
    nm.getNormalMatrix(o.matrixWorld);
    const flip = o.matrixWorld.determinant() < 0;
    for (let i = 0; i < P.count; i++) {
      v.fromBufferAttribute(P, i).applyMatrix4(o.matrixWorld); v.toArray(pos, (ov + i) * 3);
      v.fromBufferAttribute(N, i).applyMatrix3(nm).normalize(); v.toArray(nor, (ov + i) * 3);
      if (uv) { uv[(ov + i) * 2] = U.getX(i); uv[(ov + i) * 2 + 1] = U.getY(i); }
    }
    if (g.index) {
      const I = g.index;
      for (let k = 0; k < I.count; k += 3) {
        const a = I.getX(k), b = I.getX(k + 1), c = I.getX(k + 2);
        idx[oi + k] = ov + a; idx[oi + k + 1] = ov + (flip ? c : b); idx[oi + k + 2] = ov + (flip ? b : c);
      }
      oi += I.count;
    } else {
      for (let k = 0; k < P.count; k += 3) {
        idx[oi + k] = ov + k; idx[oi + k + 1] = ov + k + (flip ? 2 : 1); idx[oi + k + 2] = ov + k + (flip ? 1 : 2);
      }
      oi += P.count;
    }
    ov += P.count;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
  if (uv) geo.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  geo.setIndex(new THREE.BufferAttribute(idx, 1));
  geo.computeBoundingBox(); geo.computeBoundingSphere();
  return geo;
}

// ---------------------------------------------------------------- operable things (E)
// extras: {"operable": "swing"|"slide"|"drawer"|"rollup"|"bifold", "open_angle": deg, "axis": "z", "slide": [dx,dy,dz] (Blender metres, Z up)}
function makeOperable(o) {
  const u = o.userData;
  const op = { obj: o, type: u.operable, t: 0, target: 0, pos0: o.position.clone(), quat0: o.quaternion.clone() };
  if (op.type === 'overhead') {
    // sectional garage door: the bottom edge rides up the jamb track while the top edge runs back along the ceiling track,
    // so the door ends flat under the ceiling instead of lifting through the roof
    op.h = u.door_h; op.dir = new THREE.Vector3(...u.inward).normalize();
    op.tilt = new THREE.Vector3(0, 1, 0).cross(op.dir).normalize();
  } else if (op.type === 'swing' || op.type === 'bifold') {
    const ax = (u.axis || 'z').toLowerCase();
    op.axis = ax === 'x' ? new THREE.Vector3(1, 0, 0) : ax === 'y' ? new THREE.Vector3(0, 0, -1) : new THREE.Vector3(0, 1, 0);
    op.angle = THREE.MathUtils.degToRad(u.open_angle ?? 90);
  } else {
    let d;
    if (u.slide) d = new THREE.Vector3(u.slide[0], u.slide[2], -u.slide[1]);
    else if (op.type === 'rollup') {
      const b = new THREE.Box3().setFromObject(o); d = new THREE.Vector3(0, (b.max.y - b.min.y) * 0.92, 0);
    } else d = new THREE.Vector3(0, 0, 0.4);
    // slide vector is in world space; convert to the parent's space
    if (o.parent) {
      const inv = new THREE.Matrix4().copy(o.parent.matrixWorld).invert();
      const a = new THREE.Vector3().applyMatrix4(inv), b2 = d.clone().applyMatrix4(inv);
      d = b2.sub(a);
    }
    op.slide = d;
  }
  o.userData._op = op;
  return op;
}

function applyOp(op) {
  const e = op.t < 0.5 ? 2 * op.t * op.t : 1 - Math.pow(-2 * op.t + 2, 2) / 2;
  if (op.tilt) {
    const d = op.h * e, rise = op.h - Math.sqrt(Math.max(0, op.h * op.h - d * d));
    op.obj.position.copy(op.pos0).y += rise;
    op.obj.quaternion.copy(op.quat0).premultiply(new THREE.Quaternion().setFromAxisAngle(op.tilt, Math.atan2(d, op.h - rise)));
  } else if (op.axis) {
    op.obj.quaternion.copy(op.quat0).multiply(new THREE.Quaternion().setFromAxisAngle(op.axis, op.angle * e));
  } else {
    op.obj.position.copy(op.pos0).addScaledVector(op.slide, e);
  }
  op.obj.updateMatrix(); op.obj.updateMatrixWorld(true);
  shadowDirty = true;
}

const center = new THREE.Vector2(0, 0);
const ray = new THREE.Raycaster();
ray.firstHitOnly = true;
// What is under the crosshair or the pointer: a door or drawer to operate, or a thing with an info card.
// Hits above the slice are ignored. With the house ghosted or the ducts in x-ray, walls do not block the look.
function targetAt(ndc, info = false) {
  ray.setFromCamera(ndc, camera);
  ray.far = mode === 'walk' ? INFO_REACH : 400;
  ray.firstHitOnly = false;
  const hits = ray.intersectObjects(pickables, false);
  ray.firstHitOnly = true;
  const top = cutY();
  let solid = false;
  for (const h of hits) {
    if (h.point.y > top) continue;
    const u = h.object.userData;
    if (!solid) for (let p = h.object; p; p = p.parent) if (p.userData && p.userData._op) {
      if (!info) return (mode !== 'walk' || h.distance <= REACH) ? { op: p.userData._op } : null;
      const rec = (house && (houseRecordAt(h, house) || house.byId[u.equipId])) || (equip && equip.byId[u.equipId]);     // press and hold on a door: its card
      return rec ? { equip: rec, house: !!u.house } : null;
    }
    if (u.equipId && equip && equip.byId[u.equipId] && (!solid || ghost || (xray && u.duct))) return { equip: equip.byId[u.equipId] };
    if (!u.pass) {
      if (!ghost && !xray) { const rec = houseRecordAt(h, house); return rec ? { equip: rec, house: true } : null; }
      solid = true;
    }
  }
  return null;
}
function opAt(ndc) { const t = targetAt(ndc); return t && t.op ? t.op : null; }
// A tap works doors and drawers and nothing else, so turning the view can never open an info card by accident.
// Press and hold on a thing brings up its card (Maxwell, 11/17/2026). A tap anywhere else puts the card away.
// A mouse click still shows the card, as it always has: a click is deliberate in a way a finger lift is not.
function act(ndc, card = true) {
  const t = targetAt(ndc);
  if (t && t.op) return toggle(t.op);
  if (t && card) showInfo(t.equip); else hideInfo();
}
function inspectAt(ndc) {
  const t = targetAt(ndc, true);
  if (!t) return false;
  showInfo(t.equip);
  return true;
}
let toastTimer = 0;
function toast(msg, ms = 2200) {
  $('toast').textContent = msg; $('toast').hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { $('toast').hidden = true; }, ms);
}
function toggle(op) { if (op) op.target = op.target ? 0 : 1; }

// ---------------------------------------------------------------- camera modes
let mode = 'orbit';             // orbit by default (Maxwell, 11/16/2026); Walk is a button away
let lastRoom = null, jumping = false, noclip = false;
const look = new PointerLockControls(camera, renderer.domElement);
const orbit = new OrbitControls(camera, renderer.domElement);
orbit.enabled = false; orbit.enableDamping = true; orbit.maxPolarAngle = Math.PI * 0.495;
orbit.minDistance = 3; orbit.maxDistance = 600;

function setMode(m) {
  mode = m;
  for (const b of document.querySelectorAll('[data-mode]')) b.setAttribute('aria-pressed', b.dataset.mode === m);
  orbit.enabled = m === 'orbit';
  $('cross').hidden = m !== 'walk'; $('stick').hidden = !(touch && m === 'walk');
  $('hint').hidden = !(m === 'walk' && !touch && !look.isLocked);
  for (const b of document.querySelectorAll('[data-act="crouch"]')) b.hidden = m !== 'walk';
  if (m === 'orbit') {
    if (look.isLocked) look.unlock();
    orbit.target.copy(plan(21.5, 26, 4));
    if (camera.position.distanceTo(orbit.target) < 15) camera.position.copy(plan(-60, 110, 70));
    orbit.update();
  } else {
    camera.up.set(0, 1, 0);
    if (!jumping) { jumping = true; jump(lastRoom || 'Outside_SW'); jumping = false; }
  }
}
for (const b of document.querySelectorAll('[data-mode]')) b.onclick = () => { if (mode !== b.dataset.mode) setMode(b.dataset.mode); openSheet(null); };

function jump(name) {
  if (!name) return;
  lastRoom = name;
  let pos, at;
  const s = spawns[name];
  if (s) {
    pos = new THREE.Vector3(); s.getWorldPosition(pos);
    const lk = s.userData && s.userData.look;            // Blender world point to face, Z up
    if (lk) at = new THREE.Vector3(lk[0], lk[2], -lk[1]);
    else { const q = new THREE.Quaternion(); s.getWorldQuaternion(q); at = pos.clone().add(new THREE.Vector3(0, 0, -1).applyQuaternion(q)); }
  } else if (ROOMS[name]) {
    const r = ROOMS[name]; pos = plan(r[0], r[1]); at = plan(r[2], r[3]);
  } else return;
  if (mode !== 'walk') { jumping = true; setMode('walk'); jumping = false; }
  eyeH = crouch ? CROUCH : EYE;
  if (!s) pos.y = EYE; else pos.y += eyeH - (houseMeta.eye_ft ? houseMeta.eye_ft * F : EYE);
  const feet = groundAt(pos, /^Outside/i.test(name) ? 300 : STEP);
  pos.y = feet + eyeH; at.y = pos.y;
  camera.position.copy(pos); camera.lookAt(at);
  vel.set(0, 0, 0); if (noclip) setNoclip(false);
}

// ---------------------------------------------------------------- layers
// Hidden things move to layer 1: the camera, the shadow pass and every raycast (walking, picking) only see layer 0.
const show = (o, on) => o.traverse((m) => m.layers.set(on ? 0 : 1));
// Every view switch is a layer: Walls off fades the house so the systems read, Duct x-ray colours the ducts and
// shows them through everything, Trees and Distant trees stand in for the old slider.
const LAYERS = ['Roof', 'Walls', 'Furniture', 'Trees', 'FarTrees', 'Appliances', 'Mechanical', 'Ducts', 'Xray', 'Trusses', 'Util'];
const layerOn = (k) => $('l' + k).checked;
let sliced = false;
function applyToggles() {
  for (const o of roofNodes) show(o, layerOn('Roof') && !sliced);     // a slice lifts the roof off too, or it would cover the cut
  for (const o of utilNodes) show(o, layerOn('Util'));
  for (const o of furnitureMeshes) show(o, layerOn('Furniture'));
  // Trees is the master switch (Maxwell, 11/17/2026: trees stayed with it off); Distant trees only thins the woods while it is on
  for (const o of treeMeshes) show(o, layerOn('Trees') && (o.userData.fullCount < 80 || layerOn('FarTrees')));
  if (equip) {
    show(equip.layers.appliances, layerOn('Appliances'));
    show(equip.layers.mechanical, layerOn('Mechanical'));
    show(equip.layers.ducts, layerOn('Ducts'));
    show(equip.layers.trusses, layerOn('Trusses'));
    for (const o of bakedDeck) show(o, house ? true : !layerOn('Trusses'));     // the baked house's thin deck gives way to the trusses' own
  }
  if (ghost !== !layerOn('Walls')) setGhost(!layerOn('Walls'));
  if (xray !== layerOn('Xray')) { xray = layerOn('Xray'); setDuctXray(xray); }
  $('rowXray').classList.toggle('off', !layerOn('Ducts'));
  $('rowFarTrees').classList.toggle('off', !layerOn('Trees'));
  shadowDirty = true;
}
for (const k of LAYERS) $('l' + k).onchange = applyToggles;
if (LITE) $('lFarTrees').checked = false;

// Walls off: walls, floors and furniture go faint so the systems inside read clearly.
let ghost = false, xray = false;
const ghostSaved = new Map();
function setGhost(on) {
  ghost = on;
  for (const m of houseMats) {
    if (on) {
      if (!ghostSaved.has(m)) ghostSaved.set(m, [m.transparent, m.opacity, m.depthWrite]);
      m.transparent = true; m.opacity = Math.min(m.opacity, 0.13); m.depthWrite = false;
    } else if (ghostSaved.has(m)) { [m.transparent, m.opacity, m.depthWrite] = ghostSaved.get(m); }
    m.needsUpdate = true;
  }
  shadowDirty = true;
}


// ---------------------------------------------------------------- modals: rooms, equipment, controls
// The room picker and the equipment finder draw the floor plan from house.json (rooms, outline) in plan feet.
const svgNS = 'http://www.w3.org/2000/svg';
const el = (tag, attrs = {}, parent) => { const e = document.createElementNS(svgNS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); if (parent) parent.append(e); return e; };
const PLAN_ROOMS = [   // used when house.json has no room list (?baked)
  ['Kitchen', 0.5, 34.6, 16.7, 51.5], ['Living', 16.7, 22.9, 31.1, 34.6], ['Dining', 16.7, 34.6, 31.1, 51.5], ['Bedroom 1', 31.1, 0.5, 42.6, 11.0],
  ['Bedroom 2', 5.9, 0.5, 16.1, 10.7], ['Bedroom 3', 0.5, 10.95, 12.12, 22.41], ['Bath 1', 31.6, 22.9, 42.5, 34.6], ['Bath 2', 16.1, 0.5, 22.7, 10.7],
];
function planRooms() {
  const rs = houseMeta.rooms || PLAN_ROOMS.map(([name, a, b, c, d]) => ({ name, rect: [a, b, c, d] }));
  return rs;
}
function planSvg(withGarage = true) {
  const o = houseMeta.outline || { house: [0, 0, 43.0833, 52], garage: [63.0833, 15, 95.0833, 43], porch: [43.0833, 26.7, 63.0833, 42.6] };
  const xs = [o.house, withGarage && o.garage, withGarage && o.porch].filter(Boolean);
  const x0 = Math.min(...xs.map((r) => r[0])) - 3, x1 = Math.max(...xs.map((r) => r[2])) + 3, y0 = -5, y1 = Math.max(...xs.map((r) => r[3])) + 3;
  const svg = el('svg', { viewBox: `${x0} ${y0} ${x1 - x0} ${y1 - y0}`, class: 'plan', role: 'img' });
  for (const r of xs) el('rect', { x: r[0], y: r[1], width: r[2] - r[0], height: r[3] - r[1], class: 'out' }, svg);
  const n = el('g', { transform: `translate(${x0 + 2.5} ${y0 + 3})` }, svg);           // north arrow
  el('path', { d: 'M0 1.6 L0 -1.6 M-0.8 -0.6 L0 -1.6 L0.8 -0.6', class: 'north' }, n);
  const t = el('text', { x: 0, y: 2.6, class: 'small' }, n); t.textContent = 'N';
  return svg;
}
function addRoomShapes(svg, onPick) {
  const rooms = planRooms();
  for (const R of [...rooms.filter((r) => !r.upper), ...rooms.filter((r) => r.upper)]) {    // the loft draws over Bath 1
    const [a, b, c, d] = R.rect;
    const g = el('g', {}, svg);
    const r = el('rect', { x: a, y: b, width: c - a, height: d - b, class: 'rm' + (R.upper ? ' up' : ''), tabindex: 0, 'aria-label': R.name }, g);
    const tl = el('title', {}, r); tl.textContent = R.upper ? `${R.name} (upstairs, over ${'Bath 1'})` : R.name;
    if (onPick) { r.onclick = () => onPick(R); r.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') onPick(R); }; }
    const small = (c - a) < 7 || (d - b) < 5;
    const tx = el('text', { x: (a + c) / 2, y: R.upper ? b + 1.6 : (b + d) / 2, class: small ? 'small' : '' }, g);
    tx.textContent = R.name.replace('Bedroom 4 / study', 'Study').replace('Entry / family', 'Entry');
  }
}
let modalKind = null;
function openModal(kind) {
  modalKind = kind;
  if (look.isLocked) look.unlock();
  const body = $('modalBody'), tools = $('modalTools');
  body.textContent = ''; tools.textContent = '';
  if (kind === 'rooms') {
    $('modalTitle').textContent = 'Go to a room';
    let how = mode === 'walk' ? 'walk' : 'above';
    for (const [k, label] of [['walk', 'Walk in'], ['above', 'View from above']]) {
      const b = document.createElement('button'); b.textContent = label; b.setAttribute('aria-pressed', how === k);
      b.onclick = () => { how = k; for (const x of tools.children) x.setAttribute('aria-pressed', x === b); };
      tools.append(b);
    }
    // on a phone the plan shows the house alone, so the rooms are big enough for a thumb; the garage and porch become buttons
    const pick = (R) => { closeModal(); goRoom(R, how); };
    const svg = planSvg(!compact); addRoomShapes(svg, pick);
    body.append(svg);
    const row = document.createElement('div'); row.className = 'row';
    const hx = (houseMeta.outline || { house: [0, 0, 43.0833, 52] }).house[2];
    if (compact) for (const R of planRooms().filter((r) => r.rect[0] >= hx)) { const b = document.createElement('button'); b.textContent = R.name; b.onclick = () => pick(R); row.append(b); }
    const out = document.createElement('button'); out.textContent = 'Outside, southwest'; out.onclick = () => { closeModal(); if (how === 'walk') jump('Outside_SW'); else { if (mode !== 'orbit') setMode('orbit'); orbitHome(); } };
    row.append(out);
    const p = document.createElement('p'); p.className = 'note'; p.textContent = 'The dashed outline is the loft, upstairs over Bath 1.';
    body.append(row, p);
  } else if (kind === 'equip' && equip) {
    $('modalTitle').textContent = 'Find equipment';
    const grid = document.createElement('div'); grid.className = 'equipgrid';
    const svg = planSvg(false); addRoomShapes(svg, null);
    const list = document.createElement('div'); list.className = 'elist';
    const groups = {};
    for (const it of Object.values(equip.byId)) if (it.name && !it.type) (groups[it.category || 'Other'] ||= []).push(it);
    const PAL = ['#3B82C4', '#C4473B', '#3F9B57', '#B7862C', '#7A5BB5', '#2C9AA0', '#B5507F'];
    Object.entries(groups).forEach(([cat, items], gi) => {
      const col = PAL[gi % PAL.length];
      const sec = document.createElement('div'); const h = document.createElement('h3');
      const sw = document.createElement('i'); sw.style.background = col; h.append(sw, cat); sec.append(h);
      for (const it of items) {
        const pick = () => { closeModal(); showInfo(it); goTo(it); };
        const b = document.createElement('button'); b.textContent = it.name; b.onclick = pick; sec.append(b);
        const bb = it.box ? it.box : it.obj ? new THREE.Box3().setFromObject(it.obj) : null;
        if (bb && !bb.isEmpty()) {
          const c = bb.getCenter(new THREE.Vector3());
          const d = el('circle', { cx: c.x / F, cy: c.z / F, r: 0.75, fill: col, class: 'dot', tabindex: 0 }, svg);
          const tl = el('title', {}, d); tl.textContent = `${it.name}${c.y > 2.8 ? ' (attic)' : ''}`;
          d.onclick = pick; d.onkeydown = (e) => { if (e.key === 'Enter') pick(); };
          b.onmouseenter = () => d.setAttribute('r', 1.3); b.onmouseleave = () => d.setAttribute('r', 0.75);
        }
      }
      list.append(sec);
    });
    grid.append(svg, list); body.append(grid);
  } else if (kind === 'controls') {
    $('modalTitle').textContent = 'Controls';
    const K = (k) => k.split(' ').map((x) => `<kbd>${x}</kbd>`).join(' ');
    const sect = (title, rows) => `<div><h3>${title}</h3><table>${rows.map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join('')}</table></div>`;
    const phone = sect('Phone or tablet', [['Drag', 'Turn the view (Orbit), or look around (Walk)'], ['Pinch', 'Zoom (in Orbit)'], ['Two finger drag', 'Slide the view (in Orbit)'], ['Left stick', 'Move (in Walk)'],
      ['Tap', 'Open or close a door or a drawer'], ['Press and hold', 'Read about what is under your finger. Tap elsewhere to put the card away'], ['Layers', 'Height slice, and show or hide parts of the model'], ['More', 'Find equipment, day and night, no clip']]);
    body.innerHTML = `<div class="keys">${touch || compact ? phone : ''}${
      sect('Orbit (the default)', [['Drag', 'Turn around the house'], ['Right drag', 'Slide the view'], ['Scroll', 'Zoom'], [K('W A S D'), 'Slide the point you turn around'], [K('Shift'), 'Slide faster'], ['Click', 'Open a door, or read about what you click'], ['Press and hold', 'Read about a door instead of opening it']])
    }${
      sect('Walk', [['Click the view', 'Look with the mouse'], [K('W A S D'), 'Move'], [K('Shift'), 'Walk faster'], [K('C'), 'Crouch. You also duck under low roofs on your own'], [K('E'), 'Open or close, or read about what is under the dot'], [K('N'), 'No clip: fly through walls'], [K('Space') + ' ' + K('C'), 'Up and down while flying'], [K('Esc'), 'Free the mouse']])
    }${
      sect('Anywhere', [[K('H'), 'This page'], ['Go to a room', 'Pick a room on the plan'], ['Find equipment', 'Pick a piece of equipment on the plan'], ['Height slice', 'Cut the house at any height'], ['Layers', 'Show or hide parts of the model']])
    }${
touch || compact ? '' : phone}</div><p class="note">Slow? Turn off Distant trees in Layers, or add <kbd>?lite</kbd> to the address.</p>`;
  }
  $('modal').hidden = false;
  $('modalClose').focus();
}
function closeModal() { $('modal').hidden = true; modalKind = null; }
$('modalClose').onclick = closeModal;
$('modal').addEventListener('click', (e) => { if (e.target === $('modal')) closeModal(); });
for (const k of ['rooms', 'equip', 'controls']) for (const b of document.querySelectorAll(`[data-act="${k}"]`)) b.onclick = () => { openSheet(null); openModal(k); };

// ---------------------------------------------------------------- compact layout (phones)
// On a phone the side panel would cover most of the model, so a toolbar runs along the bottom instead and the
// panel's sections open above it as sheets: Layers (height slice and layers) and More.
const compactMQ = matchMedia('(max-width: 700px), (pointer: coarse) and (max-height: 520px)');
let compact = false, sheet = null;
const SHEETS = { layers: 'Layers', more: 'More' };
function openSheet(name) {
  sheet = name && compact ? name : null;
  $('panel').dataset.sheet = sheet || '';
  if (sheet) { $('sheetTitle').textContent = SHEETS[sheet]; $('panel').scrollTop = 0; hideInfo(); }
  for (const b of document.querySelectorAll('#bar [data-sheet]')) b.setAttribute('aria-pressed', b.dataset.sheet === sheet);
}
function setCompact() {
  compact = compactMQ.matches;
  document.body.classList.toggle('compact', compact);
  if (compact) { $('layers').open = true; $('panel').classList.remove('min'); }
  openSheet(null);
}
compactMQ.addEventListener('change', setCompact);
for (const b of document.querySelectorAll('#bar [data-sheet]')) b.onclick = () => openSheet(sheet === b.dataset.sheet ? null : b.dataset.sheet);
$('sheetClose').onclick = () => openSheet(null);
setCompact();

function orbitHome() {
  orbit.target.copy(plan(21.5, 26, 4)); camera.position.copy(plan(-60, 110, 70)); orbit.update();
}
// Walk into a room (a spawn inside it if there is one), or look down into it with the slice at that level.
function goRoom(R, how) {
  const [a, b, c, d] = R.rect, cx = (a + c) / 2, cy = (b + d) / 2, floor = R.floor || 0;
  if (how === 'walk') {
    const sp = Object.entries(houseSpawns).find(([, s2]) => s2.pos[0] >= a && s2.pos[0] <= c && s2.pos[1] >= b && s2.pos[1] <= d && Math.abs((s2.pos[2] - (houseMeta.eye_ft || 5.58)) - floor) < 1);
    if (sp && spawns[sp[0]]) { jump(sp[0]); return; }
    if (mode !== 'walk') { jumping = true; setMode('walk'); jumping = false; }
    const long = (c - a) >= (d - b);
    const from = long ? plan(a + (c - a) * 0.2, cy) : plan(cx, b + (d - b) * 0.2), to = long ? plan(c, cy) : plan(cx, d);
    eyeH = crouch ? CROUCH : EYE; vel.set(0, 0, 0); if (noclip) setNoclip(false);
    from.y = floor * F + eyeH; const feet = groundAt(from, STEP); from.y = feet + eyeH; to.y = from.y;
    camera.position.copy(from); camera.lookAt(to); lastRoom = null;
    return;
  }
  if (mode !== 'orbit') setMode('orbit');
  const lv = (levels || []).find((L) => R.upper ? /loft|attic/i.test(L.name) : /main/i.test(L.name));
  if (!R.outside && R.name !== 'Garage' && lv) setSlice(lv.cut_ft ?? SLICE_MAX); else setSlice(SLICE_MAX);
  const size = Math.max(c - a, d - b);
  orbit.target.copy(plan(cx, cy, floor + 2.5));
  camera.position.copy(plan(cx - size * 0.35, cy + size * 0.9 + 6, floor + size * 1.1 + 10));
  orbit.update();
}

// ---------------------------------------------------------------- height slice
// The slider cuts the house at any height. It catches at each level's detent, set just under that level's ceiling.
const SLICE_MAX = 23, SNAP = 0.35;
let levels = [{ name: 'Main floor', cut_ft: 8.85 }, { name: 'Loft and attic', cut_ft: 16 }, { name: 'Whole house', cut_ft: null }];
const ftIn = (ft) => { const tot = Math.round(ft * 12); return `${Math.floor(tot / 12)}' ${tot % 12}"`; };
function setSlice(ft, snapTo = true) {
  let v = Math.min(SLICE_MAX, Math.max(0.5, ft)), hit = null;
  for (const L of levels) { const c = L.cut_ft ?? SLICE_MAX; if (Math.abs(v - c) <= (snapTo ? SNAP : 0.001)) { v = c; hit = L; } }
  const whole = v >= SLICE_MAX - 0.001;
  upperPlane.constant = whole ? 1e6 : v * F;
  if (sliced !== !whole) { sliced = !whole; applyToggles(); }
  $('slice').value = v;
  $('slicelbl').textContent = whole ? 'Whole house' : `${ftIn(v)}${hit ? ', ' + hit.name.toLowerCase() : ''}`;
  for (const b of $('detents').children) b.setAttribute('aria-pressed', hit ? b.textContent === hit.name : false);
  shadowDirty = true;
}
function setupSlice() {
  if (equipData && equipData.levels) levels = equipData.levels;
  $('detents').textContent = ''; $('sliceticks').textContent = '';
  for (const L of levels) {
    const c = L.cut_ft ?? SLICE_MAX;
    const b = document.createElement('button'); b.textContent = L.name; b.onclick = () => setSlice(c); $('detents').append(b);
    const o = document.createElement('option'); o.value = c; $('sliceticks').append(o);
  }
  $('slice').max = SLICE_MAX; $('slice').oninput = (e) => setSlice(parseFloat(e.target.value));
  setSlice(SLICE_MAX);
}
const cutY = () => upperPlane.constant;

// ---------------------------------------------------------------- equipment, ducts, info card
function addEquipment() {
  if (!equipData || equip) return;
  equip = buildEquipment(equipData);
  if (house) {           // the generated house has the raised deck and loft floor already; the overlays would z-fight it
    const extra = []; equip.root.traverse((o) => { if (o.userData.deckOverlay) extra.push(o); });
    for (const o of extra) o.removeFromParent();
  }
  scene.add(equip.root);
  for (const m of equipMaterials()) { m.clippingPlanes = [upperPlane]; m.clipShadows = true; }
  equip.root.traverse((o) => {
    if (!o.isMesh) return;
    o.castShadow = !o.userData.duct; o.receiveShadow = true;
    // The generated house maps a hit's faceIndex to its record through triangle ranges. A plain BVH reorders the
    // triangles, so a click could land on another record's range (the bi-parting door read as a clerestory window).
    // 'indirect' keeps the triangle order.
    o.geometry.computeBoundsTree(o.userData.house ? { indirect: true } : undefined);
    pickables.push(o);
    if (!o.userData.pass) colliders.push(o);
  });
  for (const b of document.querySelectorAll('[data-act="equip"]')) b.hidden = false;
  applyToggles();
  console.log(`equipment: ${Object.keys(equip.byId).length} things with info`);
}

let selBox = null;
function showInfo(it) {
  $('infoBody').innerHTML = infoHTML(it);
  if (compact) openSheet(null);         // one sheet at a time above the toolbar
  $('info').hidden = false; $('info').scrollTop = 0;
  if (selBox) { scene.remove(selBox); selBox = null; }
  const bb = it.box ? it.box.clone() : it.obj ? new THREE.Box3().setFromObject(it.obj) : null;
  if (bb && !bb.isEmpty() && !it.type && it.id !== 'floor_trusses' && !/^(roof|ceiling|slab)$/.test(it.kind || '')) {   // outline single things, not whole runs
    selBox = new THREE.Box3Helper(bb.expandByScalar(0.015), 0xffb000);
    selBox.material.depthTest = false; selBox.renderOrder = 20; scene.add(selBox);
  }
}
function hideInfo() { $('info').hidden = true; if (selBox) { scene.remove(selBox); selBox = null; } }
$('infoClose').onclick = hideInfo;
function goTo(it) {       // bring the thing into view
  const c = (it.box ? it.box.clone() : new THREE.Box3().setFromObject(it.obj)).getCenter(new THREE.Vector3());
  const a = THREE.MathUtils.degToRad(it.facing || 0), front = new THREE.Vector3(Math.sin(a), 0, -Math.cos(a));
  if (mode === 'orbit') {
    orbit.target.copy(c); camera.position.copy(c).addScaledVector(front, 3.2).add(new THREE.Vector3(0, 2.2, 0)); orbit.update();
  } else {
    const high = c.y > 2.6;
    if (high && !noclip) setNoclip(true);                           // attic equipment: float up to it
    camera.position.copy(c).addScaledVector(front, high ? 2.2 : 1.7); camera.position.y = high ? c.y + 0.5 : EYE;
    camera.lookAt(c); vel.set(0, 0, 0);
  }
}

if (LITE) renderer.shadowMap.enabled = false;
// ---------------------------------------------------------------- day / night
// Night: the outside wall lights and the porch stay lit all the time. Inside, the nearest room lights are lit from a
// fixed pool (a fixed count avoids shader rebuilds). A pool light that is no longer among the nearest fades out before
// it moves, and fades in where it lands, so lights never blink on and off as you move.
const NIGHT_POOL = 6;
const pool = [];      // { L, spot, want }
let lightSpots = null;
const WARM = 0xffd6a0;

function roomLights() {
  if (lightSpots) return lightSpots;
  const out = [], moved = houseMeta.lights_moved || {};
  for (const L of manifest.lights || []) {        // Blender world metres, Z up
    let p = L.pos || [0, 0, 0];
    const mv = moved[L.name];
    const pos = mv ? plan(mv[0], mv[1], mv[2]) : new THREE.Vector3(p[0], p[2], -p[1]);
    out.push({ pos, fixed: L.room === 'exterior' || L.room === 'Porch', color: L.color || WARM, cd: Math.min(14, Math.max(3, Math.min(L.intensity_lm || 800, 1600) / (L.room === 'lamp' ? 200 : 110))) });
  }
  if (!out.length) {                              // fallback: one ceiling light per room plus the fixtures in the model
    for (const [k, r] of Object.entries(ROOMS)) if (!/^Outside/.test(k)) out.push({ pos: plan(r[0], r[1], 8.3), color: WARM, cd: 9 });
    for (const o of nightFixtures) {
      const bb = new THREE.Box3().setFromObject(o); if (bb.isEmpty()) continue;
      const c = bb.getCenter(new THREE.Vector3()); c.y = bb.min.y - 0.05;
      if (!out.some((q) => q.pos.distanceTo(c) < 1.2)) out.push({ pos: c, color: WARM, cd: /lamp/i.test(o.name) ? 4 : 6 });
    }
  }
  return (lightSpots = out);
}

let lastPlace = 0;
function placeLights(force) {
  if (!pool.length) return;
  const now = performance.now();
  if (force || now - lastPlace > 400) {
    lastPlace = now;
    const c = mode === 'walk' ? camera.position : orbit.target;
    const spots = roomLights().filter((q) => !q.fixed).sort((x, y) => x.pos.distanceToSquared(c) - y.pos.distanceToSquared(c));
    const want = new Set(spots.slice(0, pool.filter((e) => !e.fixed).length));
    const lit = new Set(pool.map((e) => e.spot));
    for (const e of pool) {
      if (e.fixed) continue;
      if (e.spot && want.has(e.spot)) { e.want = e.spot.cd; continue; }
      e.want = 0;
      if (!e.spot || e.L.intensity < 0.05 || force) {      // dark now: move it to a spot that should be lit
        const next = [...want].find((q) => !lit.has(q));
        if (next) { lit.delete(e.spot); lit.add(next); e.spot = next; e.L.position.copy(next.pos); e.L.color.set(next.color); e.want = next.cd; if (force) e.L.intensity = next.cd; }
      }
    }
  }
  const k = Math.min(1, (now - (placeLights.t || now)) / 350); placeLights.t = now;
  for (const e of pool) e.L.intensity += (e.want - e.L.intensity) * (force ? 1 : k);
}
$('collapse').onclick = () => { $('panel').classList.toggle('min'); $('collapse').textContent = $('panel').classList.contains('min') ? '+' : '–'; };

const glow = new Map();
function setFixtureGlow(on) {
  for (const o of nightFixtures) o.traverse((m) => {
    if (!m.isMesh) return;
    for (const mat of [].concat(m.material)) {
      if (!mat || !mat.emissive) continue;
      if (!glow.has(mat)) glow.set(mat, [mat.emissive.clone(), mat.emissiveIntensity]);
      if (on && /shade|glass|bulb|diffuser|lens|white/i.test((mat.name || '') + ' ' + m.name)) { mat.emissive.set(WARM); mat.emissiveIntensity = 1.2; }
      else { const [c, i] = glow.get(mat); mat.emissive.copy(c); mat.emissiveIntensity = i; }
    }
  });
}

function setNight(on) {
  night = on;
  $('tDay').setAttribute('aria-pressed', !on); $('tNight').setAttribute('aria-pressed', on);
  if (!manifest.sun_direction) sunDir.set(0.25, 0.55, 0.8).normalize();   // a mid-afternoon sun from the south
  sun.intensity = on ? 0 : 2.6;
  hemi.intensity = on ? 0.06 : 1.1; hemi.color.set(on ? 0x5a6a8a : 0xdfe8f2);
  fill.intensity = on ? 0.03 : 0.25;
  scene.background = on ? new THREE.Color(0x0b1020) : (daySky || new THREE.Color(0xbfd3e6));
  scene.environmentIntensity = on ? 0.04 : 0.6;
  scene.fog.color.set(on ? 0x0b1020 : 0xcbd9e6);
  renderer.toneMappingExposure = 1.0;
  if (on && !pool.length) {
    for (const q of roomLights().filter((q) => q.fixed)) {
      const L = new THREE.PointLight(q.color, q.cd, 14, 2); L.position.copy(q.pos); pool.push({ L, spot: q, want: q.cd, fixed: true }); scene.add(L);
    }
    for (let i = 0; i < NIGHT_POOL; i++) { const L = new THREE.PointLight(WARM, 0, 14, 2); pool.push({ L, spot: null, want: 0 }); scene.add(L); }
  }
  if (!on) { for (const e of pool) scene.remove(e.L); pool.length = 0; }
  setFixtureGlow(on);
  placeLights(true);
  shadowDirty = true;
}
$('tDay').onclick = () => setNight(false);
$('tNight').onclick = () => setNight(true);


// ---------------------------------------------------------------- walking physics
const keys = new Set();
const vel = new THREE.Vector3();
let vy = 0;
const down = new THREE.Raycaster(); down.firstHitOnly = true;
const side = new THREE.Raycaster(); side.firstHitOnly = true;
const DOWN = new THREE.Vector3(0, -1, 0);

// Feet are eyeH below the camera. eyeH is the standing eye height, lower when crouched or ducking under a roof.
let eyeH = EYE, crouch = false;
// The floor under you: cast down from just above a step's height over your feet, so a roof or a ceiling over
// your head is never taken for the floor (that is what lifted you through the attic roof).
function groundAt(p, from = STEP) {
  down.set(new THREE.Vector3(p.x, (p.y - eyeH) + from, p.z), DOWN);
  down.far = from + 400;
  const h = down.intersectObjects(colliders, false)[0];
  return h ? h.point.y : 0;
}
const UP = new THREE.Vector3(0, 1, 0);
let furnSet = new Set();
function ceilingAt(x, feet, z) {         // the first thing above your feet, up to 8 ft
  down.set(new THREE.Vector3(x, feet + 0.5 * F, z), UP);
  down.far = 8 * F; down.firstHitOnly = false;
  if (furnSet.size !== furnitureMeshes.length) furnSet = new Set(furnitureMeshes);   // you duck under roofs and beams, not over chairs
  const furn = furnSet;
  const h = down.intersectObjects(colliders, false).find((q) => !furn.has(q.object));
  down.firstHitOnly = true;
  return h ? h.point.y : feet + 1e3;
}

// Ship's ladders from house.json: inside the footprint (stretched by pad past the top end) your feet follow a ramp
// from the bottom to the landing. Returns the ramp height in metres, or null when you are not on one.
function climbAt(p, pad = 0) {
  for (const c of houseMeta.climbs || []) {
    const [x0, y0, x1, y1] = c.rect, x = p.x / F, y = p.z / F;
    const feet = (p.y - eyeH) / F;
    if (y < y0 || y > y1 || x < x0 - 0.3 || x > x1 + RADIUS / F + pad / F) continue;
    const t = Math.min(1, Math.max(0, (x - x0) / (x1 - x0)));
    const z = c.z0 + (c.z1 - c.z0) * t;
    if (Math.abs(feet - z) > 2.5) continue;              // walking under it or on the loft beside it
    if (x > x1) return null;                              // past the top: the loft floor takes over
    return z * F;
  }
  return null;
}

// Body rays: knee, waist and the crouched head. Anything higher you duck under instead of walking into.
function blocked(origin, dir, dist) {
  const feet = origin.y - eyeH;
  for (const hgt of [1.05 * F, 2.0 * F, Math.min(eyeH, CROUCH) * 0.95]) {
    side.set(new THREE.Vector3(origin.x, feet + hgt, origin.z), dir);
    side.far = dist + RADIUS;
    const h = side.intersectObjects(colliders, false)[0];
    if (h) return h;
  }
  return null;
}

function setCrouch(on) { crouch = on; for (const b of document.querySelectorAll('[data-act="crouch"]')) b.setAttribute('aria-pressed', on); }
function setNoclip(on) {
  noclip = on; $('tClip').setAttribute('aria-pressed', on); vy = 0;
  if (!on) {   // land on whatever is below your eyes
    eyeH = crouch ? CROUCH : EYE;
    const g = groundAt(camera.position, eyeH); camera.position.y = Math.max(camera.position.y, g + eyeH);
  }
}
$('tClip').onclick = () => { if (mode !== 'walk') setMode('walk'); setNoclip(!noclip); };
for (const b of document.querySelectorAll('[data-act="crouch"]')) b.onclick = () => setCrouch(!crouch);

function fly(dt) {
  const fwd = new THREE.Vector3(); camera.getWorldDirection(fwd);
  const right = new THREE.Vector3().crossVectors(fwd, camera.up).normalize();
  const want = new THREE.Vector3();
  if (keys.has('KeyW') || keys.has('ArrowUp')) want.add(fwd);
  if (keys.has('KeyS') || keys.has('ArrowDown')) want.sub(fwd);
  if (keys.has('KeyD') || keys.has('ArrowRight')) want.add(right);
  if (keys.has('KeyA') || keys.has('ArrowLeft')) want.sub(right);
  if (keys.has('Space')) want.y += 1;
  if (keys.has('KeyC') || keys.has('ControlLeft')) want.y -= 1;
  want.addScaledVector(fwd, -stick.y).addScaledVector(right, stick.x);
  if (want.lengthSq() > 1) want.normalize();
  const speed = (keys.has('ShiftLeft') || keys.has('ShiftRight') ? 12 : 4);
  vel.lerp(want.multiplyScalar(speed), Math.min(1, dt * 8));
  camera.position.addScaledVector(vel, dt);
}

// Orbit: W A S D slide the point you orbit around across the ground, relative to the way you face; Shift is faster.
function panOrbit(dt) {
  let f = 0, r = 0;
  if (keys.has('KeyW') || keys.has('ArrowUp')) f++;
  if (keys.has('KeyS') || keys.has('ArrowDown')) f--;
  if (keys.has('KeyD') || keys.has('ArrowRight')) r++;
  if (keys.has('KeyA') || keys.has('ArrowLeft')) r--;
  if (!f && !r) return;
  const fwd = orbit.target.clone().sub(camera.position); fwd.y = 0;
  if (fwd.lengthSq() < 1e-6) camera.getWorldDirection(fwd), fwd.y = 0;
  fwd.normalize();
  const right = new THREE.Vector3().crossVectors(fwd, UP).normalize();
  const dist = camera.position.distanceTo(orbit.target);
  const speed = Math.max(2, dist * 0.6) * (keys.has('ShiftLeft') || keys.has('ShiftRight') ? 3 : 1);
  const mv = fwd.multiplyScalar(f).addScaledVector(right, r).normalize().multiplyScalar(speed * dt);
  orbit.target.add(mv); camera.position.add(mv);
}

function walk(dt) {
  if (noclip) return fly(dt);
  const fwd = new THREE.Vector3(); camera.getWorldDirection(fwd); fwd.y = 0; fwd.normalize();
  const right = new THREE.Vector3().crossVectors(fwd, camera.up).normalize();
  const want = new THREE.Vector3();
  if (keys.has('KeyW') || keys.has('ArrowUp')) want.add(fwd);
  if (keys.has('KeyS') || keys.has('ArrowDown')) want.sub(fwd);
  if (keys.has('KeyD') || keys.has('ArrowRight')) want.add(right);
  if (keys.has('KeyA') || keys.has('ArrowLeft')) want.sub(right);
  want.addScaledVector(fwd, -stick.y).addScaledVector(right, stick.x);
  if (want.lengthSq() > 1) want.normalize();
  const speed = (keys.has('ShiftLeft') || keys.has('ShiftRight') ? 3.4 : 1.6);
  vel.lerp(want.multiplyScalar(speed), Math.min(1, dt * 10));
  let move = vel.clone().multiplyScalar(dt);
  const p = camera.position;
  // On a ship's ladder the treads and the landing edge are too steep to step up one by one, so the climb follows the
  // ladder's slope instead and walls are not checked until you are off it (Maxwell, 11/16/2026: could not step off the top).
  const climbing = climbAt(p, RADIUS) !== null || climbAt(p.clone().add(move), RADIUS) !== null;
  for (let i = 0; i < 2 && !climbing && move.lengthSq() > 1e-10; i++) {    // slide along walls
    const len = move.length(), dir = move.clone().divideScalar(len);
    const h = blocked(p, dir, len);
    if (!h) break;
    const n = h.face ? h.face.normal.clone().transformDirection(h.object.matrixWorld) : dir.clone().negate();
    n.y = 0; n.normalize();
    const allowed = Math.max(0, h.distance - RADIUS);
    move = dir.multiplyScalar(allowed).add(move.clone().sub(dir.clone().multiplyScalar(len)).projectOnPlane(n));
    if (i === 1 && blocked(p, move.clone().normalize(), move.length())) move.set(0, 0, 0);
  }
  p.add(move);
  // gravity and stepping
  const g = groundAt(p);
  let feet = p.y - eyeH;
  const cl = climbAt(p);
  if (cl !== null) { vy = 0; feet = Math.max(cl, g); }                       // on the ship's ladder: ride its slope
  else if (feet > g + 0.01) { vy -= 9.8 * dt; feet = Math.max(g, feet + vy * dt); }
  else { vy = 0; feet = g; }
  // duck under low roofs: the eyes stay a head's height under whatever is overhead
  const room = ceilingAt(p.x, feet, p.z) - feet - HEAD;
  const eyeWant = Math.max(DUCK_MIN, Math.min(crouch ? CROUCH : EYE, room));
  eyeH += (eyeWant - eyeH) * Math.min(1, dt * 10);
  p.y = feet + eyeH;
}

// ---------------------------------------------------------------- input
addEventListener('keydown', (e) => {
  if (e.target.tagName === 'SELECT' || e.target.tagName === 'INPUT') return;
  if (modalKind && e.code !== 'Escape') return;
  keys.add(e.code);
  if (e.code === 'KeyE') act(center);
  if (e.code === 'Escape') { if (modalKind) closeModal(); else if (sheet) openSheet(null); else hideInfo(); }
  if (e.code === 'KeyN') { if (mode !== 'walk') setMode('walk'); setNoclip(!noclip); }
  if (e.code === 'KeyC' && mode === 'walk' && !noclip) setCrouch(!crouch);
  if (e.code === 'KeyH' || e.key === '?') openModal('controls');
  if (e.code === 'Space') e.preventDefault();
});
addEventListener('keyup', (e) => keys.delete(e.code));
addEventListener('blur', () => keys.clear());
// A tap or a click is one pointer that went down and came back up quickly without moving. Anything else is a
// gesture on the view: a swipe that turns it, a pinch, a second finger landing. Those never act on the model.
// (Before 11/17/2026 every finger lift in Orbit counted as a tap, so swiping kept opening doors and cards.)
const canvas = renderer.domElement;
const TAP_MS = 400, HOLD_MS = 450, slop = (type) => (type === 'mouse' ? 4 : 9);
const fingers = new Set();
let gesture = null, clickOK = false, holdTimer = 0;
const ndcOf = (e) => new THREE.Vector2((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1);
// The ring that fills under a finger while it is held, so the wait reads as something happening.
const ring = $('hold');
function endHold() { clearTimeout(holdTimer); holdTimer = 0; ring.hidden = true; }
function startHold(e) {
  endHold();
  const g = gesture, at = mode === 'walk' && look.isLocked ? center : ndcOf(e);
  if (e.pointerType !== 'mouse') { ring.style.left = `${e.clientX}px`; ring.style.top = `${e.clientY}px`; ring.hidden = false; }
  holdTimer = setTimeout(() => {
    ring.hidden = true; holdTimer = 0;
    if (gesture !== g || g.moved || g.multi) return;
    g.held = true;                                // whatever happens next, this press is no longer a tap
    if (inspectAt(at) && navigator.vibrate) navigator.vibrate(12);
  }, HOLD_MS);
}
canvas.addEventListener('pointerdown', (e) => {
  fingers.add(e.pointerId);
  if (fingers.size === 1 && (e.pointerType !== 'mouse' || e.button === 0)) {
    gesture = { id: e.pointerId, x: e.clientX, y: e.clientY, t: performance.now(), moved: false, multi: false, held: false };
    startHold(e);
  } else if (gesture) { gesture.multi = true; endHold(); }
});
canvas.addEventListener('pointermove', (e) => {
  if (gesture && e.pointerId === gesture.id && !gesture.moved && Math.hypot(e.clientX - gesture.x, e.clientY - gesture.y) > slop(e.pointerType)) { gesture.moved = true; endHold(); }
});
canvas.addEventListener('pointerup', (e) => {
  fingers.delete(e.pointerId);
  const g = gesture;
  if (!fingers.size) { gesture = null; endHold(); }
  const tap = !!g && g.id === e.pointerId && !g.moved && !g.multi && !g.held && performance.now() - g.t < TAP_MS;
  if (e.pointerType === 'mouse') { clickOK = tap; return; }       // the click event that follows does the work
  clickOK = false;
  if (tap) act(ndcOf(e), false);
});
canvas.addEventListener('pointercancel', (e) => { fingers.delete(e.pointerId); endHold(); if (gesture) gesture.multi = true; if (!fingers.size) gesture = null; });
canvas.addEventListener('contextmenu', (e) => e.preventDefault());     // a long press must not raise the browser's menu
canvas.addEventListener('click', (e) => {
  if (mode === 'walk' && look.isLocked) { if (clickOK) act(center); clickOK = false; return; }
  if (!clickOK) return;
  clickOK = false;
  if (mode === 'walk') { if (!touch) look.lock(); return; }
  act(ndcOf(e));
});
// Say once how to get the cards on a touch screen, since nothing on screen hints at it.
function holdHint() {
  if (!touch) return;
  try { if (localStorage.getItem('holdHint')) return; localStorage.setItem('holdHint', '1'); } catch (err) { /* private window: show it anyway */ }
  toast('Press and hold anything to read about it', 4500);
}
look.addEventListener('lock', () => { $('hint').hidden = true; });
look.addEventListener('unlock', () => { if (mode === 'walk' && !touch) $('hint').hidden = false; });

// touch: left stick moves, drag elsewhere looks, tap toggles what you tap
const stick = { x: 0, y: 0, id: null };
const stickEl = $('stick'), knob = stickEl.firstElementChild;
let lookTouch = null;
stickEl.addEventListener('pointerdown', (e) => { stick.id = e.pointerId; stickEl.setPointerCapture(e.pointerId); moveStick(e); });
stickEl.addEventListener('pointermove', (e) => { if (e.pointerId === stick.id) moveStick(e); });
const endStick = (e) => { if (e.pointerId === stick.id) { stick.id = null; stick.x = stick.y = 0; knob.style.transform = ''; } };
stickEl.addEventListener('pointerup', endStick); stickEl.addEventListener('pointercancel', endStick);
function moveStick(e) {
  const r = stickEl.getBoundingClientRect();
  let dx = (e.clientX - (r.left + r.width / 2)) / (r.width / 2), dy = (e.clientY - (r.top + r.height / 2)) / (r.height / 2);
  const l = Math.hypot(dx, dy); if (l > 1) { dx /= l; dy /= l; }
  stick.x = dx; stick.y = dy; knob.style.transform = `translate(${dx * 36}px, ${dy * 36}px)`;
}
canvas.addEventListener('pointerdown', (e) => {
  if (e.pointerType === 'mouse' || mode !== 'walk' || lookTouch) return;
  lookTouch = { id: e.pointerId, x: e.clientX, y: e.clientY };
});
canvas.addEventListener('pointermove', (e) => {
  if (!lookTouch || e.pointerId !== lookTouch.id || mode !== 'walk') return;
  const eul = new THREE.Euler().setFromQuaternion(camera.quaternion, 'YXZ');
  eul.y -= (e.clientX - lookTouch.x) * 0.005; eul.x -= (e.clientY - lookTouch.y) * 0.005;
  eul.x = THREE.MathUtils.clamp(eul.x, -1.45, 1.45); camera.quaternion.setFromEuler(eul);
  lookTouch.x = e.clientX; lookTouch.y = e.clientY;
});
const endLook = (e) => { if (lookTouch && e.pointerId === lookTouch.id) lookTouch = null; };
canvas.addEventListener('pointerup', endLook); canvas.addEventListener('pointercancel', endLook);

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

// ---------------------------------------------------------------- loop
const clock = new THREE.Clock();
let promptFrame = 0;
const snap = new THREE.Vector3(), lastSnap = new THREE.Vector3(1e9, 0, 0);
// adaptive resolution: drop the render scale when frames run long, raise it back when there's headroom
let frameAcc = 0, frameN = 0;
function adaptResolution(raw) {
  frameAcc += raw; frameN++;
  if (frameAcc < 1.0) return;
  const ms = (frameAcc / frameN) * 1000; frameAcc = 0; frameN = 0;
  let next = dpr;
  if (ms > 24) next = Math.max(0.6, dpr - 0.15);
  else if (ms < 13) next = Math.min(MAX_DPR, dpr + 0.1);
  if (Math.abs(next - dpr) > 0.01) { dpr = next; renderer.setPixelRatio(dpr); renderer.setSize(innerWidth, innerHeight); }
}
renderer.setAnimationLoop(() => {
  const raw = clock.getDelta(), dt = Math.min(raw, 0.05);
  if (!document.hidden) adaptResolution(raw);
  if (mode === 'walk' && colliders.length) walk(dt); else { panOrbit(dt); orbit.update(); }
  for (const op of operables) {
    if (op.t !== op.target) { op.t = op.target > op.t ? Math.min(1, op.t + raw / 0.4) : Math.max(0, op.t - raw / 0.4); applyOp(op); }
  }
  // the sun and its shadow box follow the viewer
  const c = mode === 'walk' ? camera.position : orbit.target;
  snap.set(Math.round(c.x / 4) * 4, Math.round(c.y / 4) * 4, Math.round(c.z / 4) * 4);
  if (!snap.equals(lastSnap)) { lastSnap.copy(snap); shadowDirty = true; }
  if (shadowDirty && !night) {
    sun.target.position.copy(snap); sun.position.copy(snap).addScaledVector(sunDir, 150);
    sun.target.updateMatrixWorld(); sun.updateMatrixWorld();
    renderer.shadowMap.needsUpdate = true;
  }
  shadowDirty = false;
  placeLights(false);
  if (mode === 'walk' && !touch && (++promptFrame % 6 === 0)) {
    const t = targetAt(center);
    const shown = t && !t.house;                 // walls and trim answer a click, but do not prompt
    $('prompt').hidden = !shown;
    if (shown) $('promptTxt').textContent = t.op ? (t.op.target ? 'Close' : 'Open') : `About: ${t.equip.name}`;
  } else if (mode !== 'walk') $('prompt').hidden = true;
  renderer.render(scene, camera);
});

loadAll().catch((e) => { console.error(e); $('loadmsg').textContent = 'The model could not be loaded.'; });
window.__B = THREE.Box3; window.__T = THREE; window.__walk = { orbit, setSlice, setGhost, applyToggles, goRoom, closeModal,
  simWalk(codes, n, dt = 0.05) { keys.clear(); for (const c of codes) keys.add(c); for (let i = 0; i < n; i++) walk(dt); keys.clear(); const p = camera.position; return [p.x / F, p.z / F, (p.y - eyeH) / F, eyeH / F]; }, get eyeH() { return eyeH; }, setCrouch, openModal, targetAt, openSheet, act, inspectAt, showInfo, goTo, get equip() { return equip; }, get house() { return house; }, getDpr: () => dpr, setNight, upperPlane, renderer, scene, camera, jump, setMode, operables, colliders, toggle, opAt, setNoclip };
