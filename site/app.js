// House walkthrough: three.js viewer for the parametric Blender model.
// Model parts and options come from models/manifest.json (written by export_web.py).
// Units are metres, glTF Y up. Plan feet (x east, y south from the NW slab corner) map to (x*F, z, y*F).
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { PointerLockControls } from 'three/addons/controls/PointerLockControls.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { computeBoundsTree, disposeBoundsTree, acceleratedRaycast } from 'three-mesh-bvh';

THREE.BufferGeometry.prototype.computeBoundsTree = computeBoundsTree;
THREE.BufferGeometry.prototype.disposeBoundsTree = disposeBoundsTree;
THREE.Mesh.prototype.raycast = acceleratedRaycast;

const F = 0.3048;
const EYE = 5.33 * F;          // 5'-4" eye height
const RADIUS = 0.9 * F;        // body radius for wall collision
const STEP = 1.2 * F;          // tallest step you can walk up
const REACH = 6 * F;           // how far E reaches
const plan = (x, y, z = 0) => new THREE.Vector3(x * F, z * F, y * F);

// Fallback room spawns in plan feet [x, y, look x, look y], used when the model has no Spawn_<Room> nodes.
const ROOMS = {
  Kitchen: [9, 39.5, 8, 48], Living: [19, 29, 31, 27], Dining: [30, 44, 10, 44], Bed1: [37, 14, 37, 4],
  Bed2: [8, 7, 11, 1], Bed3: [8, 17, 1, 17], Bath1: [36, 27, 36, 32], Bath2: [19, 7, 19, 2],
  Garage: [79, 30, 79, 18], Outside_SW: [-35, 95, 21, 26],
};
const ROOM_LABELS = { Bed1: 'Bedroom 1', Bed2: 'Bedroom 2', Bed3: 'Bedroom 3', Bath1: 'Bath 1', Bath2: 'Bath 2', Outside_SW: 'Outside, southwest' };

// ---------------------------------------------------------------- renderer, scene
// logarithmic depth keeps thin parts (cooktops, wall lights on siding) from flickering through what they sit on
const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance', logarithmicDepthBuffer: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
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
const camera = new THREE.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.1, 3000);

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

async function loadAll() {
  const man = await getManifest();
  manifest = man;
  const parts = man.parts || [];
  const sizes = parts.map((p) => p.bytes || 1);
  const total = sizes.reduce((a, b) => a + b, 0);
  const got = new Array(parts.length).fill(0);
  const upd = (msg) => progress(got.reduce((a, b) => a + b, 0) / total, msg);
  if (man.sky) loadSky(man.sky);
  if (man.sun_direction) {          // Blender world direction toward the sun, Z up
    const [x, y, z] = man.sun_direction; sunDir = new THREE.Vector3(x, z, -y).normalize();
  }
  await Promise.all(parts.map((p, i) => new Promise((resolve) => {
    loader.load(`models/${p.file}`, (g) => {
      g.scene.name = p.name || p.file;
      world.add(g.scene);
      got[i] = sizes[i]; upd(`Loaded ${p.file}`);
      resolve();
    }, (e) => { if (e.total) { got[i] = sizes[i] * e.loaded / e.total; upd(`Loading ${p.file}`); } },
    (err) => { console.warn('failed', p.file, err); got[i] = sizes[i]; upd(`Could not load ${p.file}`); resolve(); });
  })));
  prepare();
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
const RE_ROOF = /roof|seam|fascia|soffit|gutter|downspout|rafter|ceiling|loft floor|ridge/i;
const RE_NOCOLLIDE = /utilit|geothermal|septic|marker|leaf|leaves|crown|canopy|foliage|curtain|shade|rug|towel|light|lamp|glass pane|^Ground$/i;
const roofNodes = [], utilNodes = [], treeMeshes = [];
const LITE = /[?&]lite\b/.test(location.search);
let treeFrac = LITE ? 0.25 : 1;   // share of trees drawn, from the Trees slider

const UPPER_CUT = 2.70;                                   // metres: just under the 9 ft first floor ceilings
const upperPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), 1e6);   // constant 1e6 = nothing clipped
const nightFixtures = [];

function prepare() {
  world.updateMatrixWorld(true);
  const roofSet = new Set(), utilSet = new Set(), opRoots = new Set();
  world.traverse((o) => {
    const n = o.name || '';
    if (/^Spawn_/i.test(n)) { spawns[n.slice(6)] = o; return; }
    if (o.userData && o.userData.operable) { operables.push(makeOperable(o)); opRoots.add(o); }
    if (o !== world && o.parent !== world && RE_ROOF.test(n)) { roofNodes.push(o); roofSet.add(o); }
    if (o !== world && o.parent !== world && (n === 'Utilities' || RE_UTIL.test(n))) { utilNodes.push(o); utilSet.add(o); }
    if ((o.userData && o.userData.emissive_night) || RE_FIXTURE.test(n)) nightFixtures.push(o);
  });
  const merged = mergeStatic(roofSet, utilSet, opRoots);
  world.updateMatrixWorld(true);
  world.traverse((o) => {
    if (o !== world) o.matrixAutoUpdate = false;           // nothing static moves; operables update their own matrix
    if (!o.isMesh) return;
    o.castShadow = true; o.receiveShadow = true;
    const mats = [].concat(o.material);
    if (mats.some((m) => m && m.transparent && m.opacity < 0.99)) o.castShadow = false;
    const part = partOf(o);
    if (part && !/^(site|trees)$/i.test(part.name)) for (const m of mats) if (m) m.clippingPlanes = [upperPlane];
    if (o.isInstancedMesh) {          // instanced trees: drawn only, no collision or picking. Names do not survive gltfpack, so the distant woods are told apart by instance count (a hundred or more vs. a few dozen near the house)
      for (const mm of mats) if (mm && mm.transparent) {
        mm.transparent = false; mm.alphaTest = 0.3; mm.depthWrite = true;   // cutout leaves sort and draw far faster
      }
      if (o.count >= 80) o.castShadow = false;       // distant woods: no shadows
      shuffleInstances(o); o.userData.fullCount = o.count; treeMeshes.push(o);
      return;
    }
    let pass = !!o.userData.pass;
    if (!pass) for (let p = o; p; p = p.parent) if (RE_NOCOLLIDE.test(p.name || '')) { pass = true; break; }
    o.userData.pass = pass;
    o.geometry.computeBoundsTree();
    pickables.push(o);
    if (!pass) colliders.push(o);
  });
  console.log(`merged static meshes into ${merged} draw groups`);
  // room list
  const names = [...new Set([...Object.keys(ROOMS), ...Object.keys(spawns)])];
  for (const k of names) {
    const opt = document.createElement('option'); opt.value = k; opt.textContent = ROOM_LABELS[k] || k.replace(/_/g, ' ');
    $('rooms').append(opt);
  }
  setNight(false);
  setTrees(treeFrac);
  jump(names.includes('Outside_SW') ? 'Outside_SW' : names[0]);
  $('loading').hidden = true;
  if (touch) { $('stick').hidden = false; $('helpDesk').hidden = true; $('helpTouch').hidden = false; }
  else if (mode === 'walk') $('hint').hidden = false;
  $('cross').hidden = mode !== 'walk';
  console.log(`walkthrough ready: ${colliders.length} colliders, ${operables.length} operable, ${Object.keys(spawns).length} spawns`);
}

// ---------------------------------------------------------------- static merge
// Thousands of small meshes cost one draw call each. Static meshes that share a material (and part,
// toggle group and a 20 m grid cell) are baked into one mesh in world space.
const RE_FIXTURE = /pendant|lamp|sconce|wall_light|ceiling_light|fixture|can_light|bulb/i;
function partOf(o) { let p = o; while (p && p.parent && p.parent !== world) p = p.parent; return p && p.parent === world ? p : null; }

function mergeStatic(roofSet, utilSet, opRoots) {
  const buckets = new Map();
  const fixtureSet = new Set(nightFixtures);
  world.traverse((o) => {
    if (!o.isMesh || o.isInstancedMesh || o.isSkinnedMesh || Array.isArray(o.material)) return;
    if (o.geometry.morphAttributes && Object.keys(o.geometry.morphAttributes).length) return;
    if (o.material.vertexColors) return;
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
  if (op.type === 'swing' || op.type === 'bifold') {
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
  if (op.axis) {
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
function opAt(ndc) {
  if (!operables.length) return null;
  ray.setFromCamera(ndc, camera);
  ray.far = mode === 'walk' ? REACH : 60;
  const hits = ray.intersectObjects(pickables, false);
  for (const h of hits) {
    for (let p = h.object; p; p = p.parent) if (p.userData && p.userData._op) return p.userData._op;
    if (!h.object.userData.pass) return null;   // something solid is in the way
  }
  return null;
}
function toggle(op) { if (op) op.target = op.target ? 0 : 1; }

// ---------------------------------------------------------------- camera modes
let mode = 'walk';
let lastRoom = null, jumping = false, noclip = false;
const look = new PointerLockControls(camera, renderer.domElement);
const orbit = new OrbitControls(camera, renderer.domElement);
orbit.enabled = false; orbit.enableDamping = true; orbit.maxPolarAngle = Math.PI * 0.495;
orbit.minDistance = 3; orbit.maxDistance = 600;

function setMode(m) {
  mode = m;
  $('mWalk').setAttribute('aria-pressed', m === 'walk'); $('mOrbit').setAttribute('aria-pressed', m === 'orbit');
  orbit.enabled = m === 'orbit';
  $('cross').hidden = m !== 'walk'; $('stick').hidden = !(touch && m === 'walk');
  $('hint').hidden = !(m === 'walk' && !touch && !look.isLocked);
  if (m === 'orbit') {
    if (look.isLocked) look.unlock();
    const dir = new THREE.Vector3(); camera.getWorldDirection(dir);
    orbit.target.copy(plan(21.5, 26, 4));
    if (camera.position.distanceTo(orbit.target) < 15) camera.position.copy(plan(-60, 110, 70));
    orbit.update();
  } else {
    camera.up.set(0, 1, 0);
    if (!jumping) { jumping = true; jump(lastRoom || 'Outside_SW'); jumping = false; }
  }
}
$('mWalk').onclick = () => setMode('walk');
$('mOrbit').onclick = () => setMode('orbit');

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
  if (!s) pos.y = EYE;
  const feet = groundAt(pos, /^Outside/i.test(name) ? 300 : STEP + EYE);
  pos.y = feet + EYE; at.y = pos.y;
  camera.position.copy(pos); camera.lookAt(at);
  vel.set(0, 0, 0); if (noclip) setNoclip(false);
}
$('rooms').onchange = (e) => { jump(e.target.value); e.target.value = ''; e.target.blur(); };

// ---------------------------------------------------------------- toggles
$('tRoof').onclick = (e) => {
  const off = e.currentTarget.getAttribute('aria-pressed') !== 'true';
  e.currentTarget.setAttribute('aria-pressed', off);
  for (const o of roofNodes) o.visible = !off;
  shadowDirty = true;
};
$('tUtil').onclick = (e) => {
  const on = e.currentTarget.getAttribute('aria-pressed') !== 'true';
  e.currentTarget.setAttribute('aria-pressed', on);
  for (const o of utilNodes) o.visible = on;
};
// Trees slider: draw a share of every species. Instances are shuffled once with the same seed for meshes
// of equal count, so a tree's bark and leaves stay together and thinning is spread evenly.
function shuffleInstances(o) {
  const n = o.count, m = new THREE.Matrix4(), t = new THREE.Matrix4();
  let seed = 1234567 + n;
  const rnd = () => ((seed = (seed * 1103515245 + 12345) >>> 0) / 4294967296);
  for (let i = n - 1; i > 0; i--) {
    const j = Math.floor(rnd() * (i + 1));
    o.getMatrixAt(i, m); o.getMatrixAt(j, t); o.setMatrixAt(i, t); o.setMatrixAt(j, m);
  }
  o.instanceMatrix.needsUpdate = true;
}
function setTrees(frac) {
  treeFrac = frac;
  for (const o of treeMeshes) { o.count = Math.round(o.userData.fullCount * frac); o.visible = o.count > 0; }
  $('treelbl').textContent = `${Math.round(frac * 100)}%`;
  shadowDirty = true;
}
$('trees').value = Math.round(treeFrac * 100);
$('trees').oninput = (e) => setTrees(parseInt(e.target.value, 10) / 100);
if (LITE) renderer.shadowMap.enabled = false;
$('tUp').onclick = (e) => {
  const off = e.currentTarget.getAttribute('aria-pressed') !== 'true';
  e.currentTarget.setAttribute('aria-pressed', off);
  upperPlane.constant = off ? UPPER_CUT : 1e6;
  shadowDirty = true;
};

// ---------------------------------------------------------------- day / night
const NIGHT_POOL = 8;               // the nearest room lights are lit; a fixed count avoids shader rebuilds while walking
const pool = [];
let lightSpots = null;
const WARM = 0xffd6a0;

function roomLights() {
  if (lightSpots) return lightSpots;
  const out = [];
  for (const L of manifest.lights || []) {        // Blender world metres, Z up
    const p = L.pos || [0, 0, 0];
    out.push({ pos: new THREE.Vector3(p[0], p[2], -p[1]), color: L.color || WARM, cd: Math.min(14, Math.max(3, Math.min(L.intensity_lm || 800, 1600) / (L.room === 'lamp' ? 200 : 110))) });
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
  if (on && !pool.length) for (let i = 0; i < NIGHT_POOL; i++) {
    const L = new THREE.PointLight(WARM, 0, 14, 2); pool.push(L); scene.add(L);
  }
  if (!on) { for (const L of pool) scene.remove(L); pool.length = 0; }
  setFixtureGlow(on);
  placeLights(true);
  shadowDirty = true;
}
$('tDay').onclick = () => setNight(false);
$('tNight').onclick = () => setNight(true);

let lastPlace = 0;
function placeLights(force) {
  if (!pool.length) return;
  const now = performance.now(); if (!force && now - lastPlace < 400) return; lastPlace = now;
  const c = mode === 'walk' ? camera.position : orbit.target;
  const spots = roomLights().slice().sort((x, y) => x.pos.distanceToSquared(c) - y.pos.distanceToSquared(c));
  pool.forEach((L, i) => {
    const s2 = spots[i];
    if (!s2) { L.intensity = 0; return; }
    L.position.copy(s2.pos); L.color.set(s2.color); L.intensity = s2.cd;
  });
}
$('collapse').onclick = () => { $('panel').classList.toggle('min'); $('collapse').textContent = $('panel').classList.contains('min') ? '+' : '–'; };

// ---------------------------------------------------------------- walking physics
const keys = new Set();
const vel = new THREE.Vector3();
let vy = 0;
const down = new THREE.Raycaster(); down.firstHitOnly = true;
const side = new THREE.Raycaster(); side.firstHitOnly = true;
const DOWN = new THREE.Vector3(0, -1, 0);

function groundAt(p, from = STEP + EYE) {
  down.set(new THREE.Vector3(p.x, (p.y - EYE) + from, p.z), DOWN);
  down.far = from + 400;
  const h = down.intersectObjects(colliders, false)[0];
  return h ? h.point.y : 0;
}

function blocked(origin, dir, dist) {
  for (const hgt of [0.25 * EYE + STEP * 0.6, 0.55 * EYE, 0.95 * EYE]) {
    side.set(new THREE.Vector3(origin.x, origin.y - EYE + hgt, origin.z), dir);
    side.far = dist + RADIUS;
    const h = side.intersectObjects(colliders, false)[0];
    if (h) return h;
  }
  return null;
}

function setNoclip(on) {
  noclip = on; $('tClip').setAttribute('aria-pressed', on); vy = 0;
  if (!on) {   // land on whatever is below
    const g = groundAt(camera.position, STEP + EYE); camera.position.y = Math.max(camera.position.y, g + EYE);
  }
}
$('tClip').onclick = () => { if (mode !== 'walk') setMode('walk'); setNoclip(!noclip); };

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
  for (let i = 0; i < 2 && move.lengthSq() > 1e-10; i++) {    // slide along walls
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
  const feet = p.y - EYE;
  if (feet > g + 0.01) { vy -= 9.8 * dt; p.y = Math.max(g + EYE, p.y + vy * dt); }
  else { vy = 0; p.y = g + EYE; }
}

// ---------------------------------------------------------------- input
addEventListener('keydown', (e) => {
  if (e.target.tagName === 'SELECT' || e.target.tagName === 'INPUT') return;
  keys.add(e.code);
  if (e.code === 'KeyE') toggle(opAt(center));
  if (e.code === 'KeyN') { if (mode !== 'walk') setMode('walk'); setNoclip(!noclip); }
  if (e.code === 'Space') e.preventDefault();
});
addEventListener('keyup', (e) => keys.delete(e.code));
addEventListener('blur', () => keys.clear());
renderer.domElement.addEventListener('click', (e) => {
  if (touch) return;
  if (mode === 'walk' && !look.isLocked) { look.lock(); return; }
  if (mode === 'orbit') {
    const ndc = new THREE.Vector2((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1);
    toggle(opAt(ndc));
  }
});
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
renderer.domElement.addEventListener('pointerdown', (e) => {
  if (!touch || mode !== 'walk') return;
  lookTouch = { id: e.pointerId, x: e.clientX, y: e.clientY, x0: e.clientX, y0: e.clientY, t: performance.now() };
});
renderer.domElement.addEventListener('pointermove', (e) => {
  if (!lookTouch || e.pointerId !== lookTouch.id) return;
  const eul = new THREE.Euler().setFromQuaternion(camera.quaternion, 'YXZ');
  eul.y -= (e.clientX - lookTouch.x) * 0.005; eul.x -= (e.clientY - lookTouch.y) * 0.005;
  eul.x = THREE.MathUtils.clamp(eul.x, -1.45, 1.45); camera.quaternion.setFromEuler(eul);
  lookTouch.x = e.clientX; lookTouch.y = e.clientY;
});
renderer.domElement.addEventListener('pointerup', (e) => {
  if (touch && (mode === 'walk' || mode === 'orbit')) {
    const t = lookTouch;
    const tap = !t || (Math.hypot(e.clientX - t.x0, e.clientY - t.y0) < 10 && performance.now() - t.t < 350);
    if (tap) {
      const ndc = new THREE.Vector2((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1);
      toggle(opAt(ndc));
    }
  }
  lookTouch = null;
});

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

// ---------------------------------------------------------------- loop
const clock = new THREE.Clock();
let promptFrame = 0;
const snap = new THREE.Vector3(), lastSnap = new THREE.Vector3(1e9, 0, 0);
renderer.setAnimationLoop(() => {
  const raw = clock.getDelta(), dt = Math.min(raw, 0.05);
  if (mode === 'walk' && colliders.length) walk(dt); else orbit.update();
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
    const op = opAt(center);
    $('prompt').hidden = !op;
    if (op) $('promptTxt').textContent = op.target ? 'Close' : 'Open';
  } else if (mode !== 'walk') $('prompt').hidden = true;
  renderer.render(scene, camera);
});

loadAll().catch((e) => { console.error(e); $('loadmsg').textContent = 'The model could not be loaded.'; });
window.__B = THREE.Box3; window.__T = THREE; window.__walk = { setNight, upperPlane, renderer, scene, camera, jump, setMode, operables, colliders, toggle, opAt, setNoclip };
