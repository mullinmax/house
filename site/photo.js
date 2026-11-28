// Photo mode: a path-traced still of the current view (three-gpu-pathtracer), for a picture to save.
// The normal view fakes most of its light: a hemisphere light that reaches every surface, a blurred sky reflection and one
// shadow map. Here light is followed for real: it comes in through the windows, bounces off the floor onto the ceiling,
// glass reflects and lets light through, and the room lights at night are the fixtures themselves. It takes seconds to
// minutes instead of a frame, so it is a mode: the walkthrough pauses, samples pile up on the canvas, and Save PNG keeps it.
//
// What the photo is built from is exactly what the normal renderer would draw: every mesh whose own and whose parents'
// visible flags are on and that sits on a camera layer. That means the merged draw batches (with only the pieces of the
// layers that are switched on), the see-through pieces, fan blades and instanced trees, and never the hidden originals.
// The path tracer has no clipping planes, so the height slice is cut into the triangles here (clipTris).
// Not in the photo: fog, the tape measure, and the duct x-ray's "through everything" trick (ducts keep their x-ray
// colours but walls hide them). The hemisphere and ambient lights have no meaning to a path tracer; the sky lights instead.
//
// Indoors the sky gets help. A room sees the sky through a few windows, a percent or two of all directions, so rays sent
// toward the sky nearly all die on a wall and the picture stays speckled for thousands of samples. So when the camera is
// under a roof, the few windows it can see each become a soft light of the window's size, with the sky's average colour,
// shining into the room (a "sky portal", the usual trick for interiors), and the sky itself stops lighting. The path
// tracer aims at those directly and a room clears up in hundreds of samples. The sun still comes through the glass as
// itself. Outdoors, or looking down into a sliced house, the sky lights everything as it is. Two more things keep
// rooms from staying speckled: glowing parts are turned down (photoMat) and bounced light is capped per sample (open).
import * as THREE from 'three';

const SUN_HALF_ANGLE = 0.008;       // radians. A shade over the real sun (0.0047) so shadow edges soften visibly
const MAX_PORTALS = 4, PORTAL_REACH = 18;      // window lights: the few windows that fill most of the camera's sky, within this many metres
const CLAMP = 2.5;                  // the bounced light in one sample may not be brighter than this many times display white (see open)
const KEY = 0.1;                    // exposure without a normal frame to match: the picture's typical (log average) light is brought up to this, never down

// The ray search tree (BVH) over half a million triangles takes a couple of seconds on a laptop and far longer on a
// phone, and built on the page it froze everything, the panel included. three-mesh-bvh ships a self contained worker for
// it; this is the small page side that hands it the triangles and takes the tree back. The time is the same, but the
// page keeps answering, the panel can show how far along it is, and the GPU program compiles meanwhile.
class BVHWorker {
  constructor(url) {
    this.worker = new Worker(url);
    this.ready = new Promise((res, rej) => {
      this.worker.onmessage = (e) => { if (e.data && e.data.type === 'ready') { this.worker.onmessage = null; res(); } };
      this.worker.onerror = (e) => { e.preventDefault(); rej(new Error(e.message || 'the BVH worker did not load')); };
    });
    this.ready.catch(() => {});
  }
  async generate(geometry, options = {}) {
    await this.ready;
    const { MeshBVH } = await import('three-mesh-bvh');
    return new Promise((resolve, reject) => {
      const w = this.worker, onProgress = options.onProgress;
      w.onerror = (e) => { e.preventDefault(); reject(new Error(e.message || 'the BVH worker failed')); };
      w.onmessage = ({ data }) => {
        if (data.error) { w.onmessage = null; reject(new Error(String(data.error))); return; }
        if (!data.serialized) { if (onProgress) onProgress(data.progress); return; }
        w.onmessage = null;
        const ser = data.serialized, bvh = MeshBVH.deserialize(ser, geometry, { setIndex: false });
        if (ser.index && !geometry.index) geometry.setIndex(new THREE.BufferAttribute(ser.index, 1, false));
        else if (ser.index && !bvh.indirect) { geometry.index.array.set(ser.index); geometry.index.needsUpdate = true; }
        if (onProgress) onProgress(1);
        resolve(bvh);
      };
      const position = geometry.attributes.position.array.slice(), index = geometry.index ? geometry.index.array.slice() : null;
      const opts = { ...options, onProgress: null, range: null, includedProgressCallback: !!onProgress, groups: geometry.groups.map((g) => ({ ...g })) };
      w.postMessage({ index, position, normalized: geometry.attributes.position.normalized, options: opts }, index ? [position.buffer, index.buffer] : [position.buffer]);
    });
  }
}
const BVH_WORKER_URL = new URL('./vendor/three-mesh-bvh/generateMeshBVH.worker.js', import.meta.url);

// Fixed picture sizes (Maxwell, 11/28/2026): the picture keeps its size when the window changes, and Save gives it at
// exactly that size. Screen is the window's own size when the photo starts (capped as below).
const SIZES = { screen: null, '1080p': [1920, 1080], '1440p': [2560, 1440], '4k': [3840, 2160] };

export function createPhoto({ renderer, scene, camera, sun, sky = () => null, draw = null, touch = false, toast = () => {}, onOpen = () => {}, onClose = () => {} }) {
  // Limits. A float target of 2 megapixels is about 100 MB with its two blend partners; phones get half of everything.
  const MAX_PIXELS = touch ? 0.6e6 : 2.1e6, MAX_TRIS = touch ? 1.2e6 : 4e6, MAX_SAMPLES = touch ? 200 : 1000;
  const pcam = new THREE.PerspectiveCamera();      // the photo's own camera: the view's, at the picture's shape
  let PT = null, pt = null, pscene = null, psun = null, plights = [], sunDir = new THREE.Vector3();
  let active = false, ready = false, go = false, picking = false, sig = 0, builds = 0, saved = null, skipped = 0, tris = 0;
  let autoExp = 1, stops = 0, expAt = 0, lastShown = -1, lastW = 0, lastH = 0, frameMs = 0, lastT = 0, done = false, token = 0;
  let redos = 0, dirty = false, snap = null, shown = false, W = 0, H = 0, warming = null, bvhWorker = null, size = 'screen', envTex = null, envFrom = null, aim = 0, clampU = { value: 1e9 }, clamped = false, panes = [], skyMean = new THREE.Color(0.5, 0.6, 0.75), portals = 0, inside = false;

  // ---- the small panel, and a sheet over the page that swallows clicks and touches while the photo runs
  const css = document.createElement('style');
  css.textContent = `#photoShield { position: fixed; inset: 0; z-index: 39; touch-action: none; cursor: progress; }
#photoPanel { position: fixed; left: 50%; bottom: max(14px, env(safe-area-inset-bottom)); transform: translateX(-50%); z-index: 40; display: grid; gap: 8px;
  background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 10px 14px; backdrop-filter: blur(6px);
  width: min(360px, calc(100vw - 24px)); touch-action: manipulation; }
#photoPanel .ptop { display: flex; align-items: baseline; gap: 10px; }
#photoPanel b { font: 600 .95rem var(--display); }
#photoPanel .pstat { flex: 1; color: var(--muted); font-size: .82rem; font-variant-numeric: tabular-nums; }
#photoPanel label { font-size: .8rem; color: var(--muted); }
#photoPanel select { margin-left: 6px; }
#photoPanel .row button { flex: 1; }
#photoPanel [data-p="go"] { font-weight: 600; }
body.photo #panel, body.photo #bar, body.photo #info, body.photo #cross, body.photo #prompt, body.photo #stick, body.photo #hint,
body.photo #measure, body.photo #mLabel, body.photo #fCrouch, body.photo #hold { display: none !important; }`;
  document.head.append(css);
  const shield = document.createElement('div'); shield.id = 'photoShield'; shield.hidden = true;
  const panel = document.createElement('div'); panel.id = 'photoPanel'; panel.hidden = true; panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-label', 'Photo');
  panel.innerHTML = `<div class="ptop"><b>Photo</b><span class="pstat"></span></div>
<label>Brightness <input type="range" min="-2" max="2" step="0.1" value="0" aria-label="Brightness"></label>
<label>Size <select aria-label="Picture size"><option value="screen">Screen</option><option value="1080p">1080p (1920 x 1080)</option><option value="1440p">1440p (2560 x 1440)</option>${touch ? '' : '<option value="4k">4K (3840 x 2160)</option>'}</select></label>
<div class="row"><button data-p="go" title="Start the picture at the size above">Render</button></div>
<div class="row"><button data-p="save" title="Save the picture as it is now. More samples make it cleaner">Save PNG</button><button data-p="close" title="Back to the walkthrough (Esc)">Close</button></div>`;
  document.body.append(shield, panel);
  const stat = panel.querySelector('.pstat'), slider = panel.querySelector('input'), sizeSel = panel.querySelector('select');
  try { const v = localStorage.getItem('photoSize'); if (v && v in SIZES && [...sizeSel.options].some((o) => o.value === v)) size = v; } catch (err) { /* private window */ }
  sizeSel.value = size;
  // Nothing renders until Render is pressed, so the menu is never fighting the path tracer for the page (Maxwell,
  // 11/28/2026: the open menu lagged while samples came in). A new size picked mid picture stops it and waits for Render
  // again, and while the menu has focus the tracer stands still, so it opens and scrolls at full speed.
  const goBtn = panel.querySelector('[data-p="go"]');
  const waitForGo = () => { go = false; goBtn.hidden = false; goBtn.textContent = shown ? `Render at ${label()}` : 'Render'; if (ready) say('Pick a size, then press Render'); };
  const label = () => sizeSel.options[sizeSel.selectedIndex].text.replace(/ \(.*/, '');
  sizeSel.onchange = () => {
    size = sizeSel.value; try { localStorage.setItem('photoSize', size); } catch (err) { /* private window */ }
    if (active && go) waitForGo(); else if (active) goBtn.textContent = shown ? `Render at ${label()}` : 'Render';
  };
  sizeSel.addEventListener('focus', () => { picking = true; });
  sizeSel.addEventListener('blur', () => { picking = false; lastT = 0; });
  goBtn.onclick = () => start();
  slider.oninput = () => { stops = parseFloat(slider.value); applyExposure(); };
  panel.querySelector('[data-p="save"]').onclick = () => save();
  panel.querySelector('[data-p="close"]').onclick = () => close();
  for (const ev of ['pointerdown', 'pointermove', 'pointerup', 'wheel', 'contextmenu', 'click']) shield.addEventListener(ev, (e) => { e.stopPropagation(); if (ev !== 'click') e.preventDefault(); }, { passive: false });
  const say = (t) => { if (stat.textContent !== t) stat.textContent = t; };
  // Tone mapping happens when the float picture is put on the canvas, so brightness changes at once and costs no samples.
  const applyExposure = () => { renderer.toneMappingExposure = autoExp * 2 ** stops; dirty = true; };

  // ---- what would be drawn: the same test the renderer makes (visible all the way up, on a camera layer)
  function drawn(cb) {
    const walk = (o) => {
      if (!o.visible) return;
      if (o.isMesh && o.layers.test(camera.layers) && o.geometry && o.geometry.attributes.position) {
        const m = Array.isArray(o.material) ? o.material[0] : o.material;
        if (m && m.visible && m.toneMapped !== false) cb(o, m);        // not tone mapped = a tool overlay (tape measure pins)
      }
      for (const c of o.children) walk(c);
    };
    walk(scene);
  }
  // One number for everything the photo depends on. Same number as last time: the built scene and its BVH are kept
  // and only the camera moves. A door, a layer, the slice, day or night, a fan's angle all change it.
  const f32 = new Float32Array(16), u32 = new Uint32Array(f32.buffer);
  function signature() {
    let h = 2166136261;
    const add = (n) => { h = Math.imul(h ^ (n | 0), 16777619); };
    const addF = (arr, n) => { for (let i = 0; i < n; i++) f32[i] = arr[i]; for (let i = 0; i < n; i++) add(u32[i]); };
    drawn((o, m) => {
      const g = o.geometry, dr = g.drawRange;
      add(o.id); add(g.id); add(g.attributes.position.version); add(g.index ? g.index.version : 0); add(dr.start); add(Math.min(dr.count, 1e9)); add(o.count || 0);
      // the fields the photo reads, not material.version: the ambient occlusion pass bumps that on see-through materials every frame
      add(m.id); add(m.color ? m.color.getHex() : 0); add(m.emissive ? m.emissive.getHex() : 0); add(m.map ? m.map.id : 0); add(m.side); add(m.transparent ? 1 : 0);
      addF([m.opacity, m.emissiveIntensity || 0, m.roughness || 0, m.metalness || 0, m.alphaTest || 0], 5);
      addF(o.matrixWorld.elements, 16);
      for (const p of m.clippingPlanes || []) addF([p.normal.x, p.normal.y, p.normal.z, Math.min(p.constant, 1e5)], 4);
    });
    scene.traverse((o) => { if (o.isLight && o.visible) { add(o.id); addF([o.intensity, o.color.r, o.color.g, o.color.b], 4); addF(o.matrixWorld.elements, 16); } });
    const bg = scene.background; add(bg ? (bg.isColor ? bg.getHex() : bg.id) : 0);
    addF([sunDir.x, sunDir.y, sunDir.z], 3);
    return h;
  }

  // ---- geometry for the path tracer: world space, plain floats, cut at the slice
  // A batch is already world space floats, so it is handed over as it is (only its index is trimmed to what is drawn).
  // Everything else (quantized glTF pieces, instanced trees) is baked here, one copy per instance.
  const _m = new THREE.Matrix4(), _n = new THREE.Matrix3(), _v = new THREE.Vector3(), IDENT = new THREE.Matrix4();
  const plainFloat = (a) => a && a.array instanceof Float32Array && !a.isInterleavedBufferAttribute && !a.normalized;
  function bake(o, planes) {
    const g = o.geometry, P = g.attributes.position, N = g.attributes.normal, U = g.attributes.uv, I = g.index;
    const nv = P.count, total = I ? I.count : nv, i0 = Math.min(g.drawRange.start, total), ni = Math.floor(Math.min(g.drawRange.count, total - i0) / 3) * 3;
    if (ni <= 0) return null;
    const k = o.isInstancedMesh ? o.count : 1;
    let pos, nor = null, uv = null, idx;
    if (k === 1 && !o.isInstancedMesh && o.matrixWorld.equals(IDENT) && plainFloat(P) && (!N || plainFloat(N)) && (!U || plainFloat(U)) && I) {
      pos = P.array; nor = N ? N.array : null; uv = U ? U.array : null; idx = I.array.subarray(i0, i0 + ni);
    } else {
      pos = new Float32Array(nv * k * 3); if (N) nor = new Float32Array(nv * k * 3); if (U) uv = new Float32Array(nv * k * 2); idx = new Uint32Array(ni * k);
      for (let j = 0; j < k; j++) {
        if (o.isInstancedMesh) { o.getMatrixAt(j, _m); _m.premultiply(o.matrixWorld); } else _m.copy(o.matrixWorld);
        _n.getNormalMatrix(_m);
        const v0 = j * nv, flip = _m.determinant() < 0;            // a mirrored piece: restore the winding
        for (let i = 0, a = v0 * 3; i < nv; i++, a += 3) {
          _v.fromBufferAttribute(P, i).applyMatrix4(_m); pos[a] = _v.x; pos[a + 1] = _v.y; pos[a + 2] = _v.z;
          if (N) { _v.fromBufferAttribute(N, i).applyMatrix3(_n).normalize(); nor[a] = _v.x; nor[a + 1] = _v.y; nor[a + 2] = _v.z; }
          if (U) { uv[(v0 + i) * 2] = U.getX(i); uv[(v0 + i) * 2 + 1] = U.getY(i); }
        }
        for (let t = 0, w = j * ni; t < ni; t += 3, w += 3) {
          const a = I ? I.getX(i0 + t) : i0 + t, b = I ? I.getX(i0 + t + 1) : i0 + t + 1, c = I ? I.getX(i0 + t + 2) : i0 + t + 2;
          idx[w] = v0 + a; idx[w + 1] = v0 + (flip ? c : b); idx[w + 2] = v0 + (flip ? b : c);
        }
      }
    }
    let d = { pos, nor, uv, idx };
    for (const p of planes) { d = clipTris(d, p); if (!d.idx.length) return null; }
    const out = new THREE.BufferGeometry();
    out.setAttribute('position', new THREE.BufferAttribute(d.pos, 3));
    if (d.nor) out.setAttribute('normal', new THREE.BufferAttribute(d.nor, 3));
    if (d.uv) out.setAttribute('uv', new THREE.BufferAttribute(d.uv, 2));
    out.setIndex(new THREE.BufferAttribute(d.idx, 1));
    return out;
  }
  // The height slice. The renderer throws away pixels on the far side of the plane; here the triangles are cut instead:
  // one wholly on the kept side stays, one wholly beyond goes, and one that crosses is trimmed along the plane (a
  // corner becomes one triangle, the other case a quad of two), with normals and texture coordinates carried to the new
  // corners. Cut solids are left open, as in the normal view, where the inside faces are shown as the cut face.
  function clipTris({ pos, nor, uv, idx }, plane) {
    const nx = plane.normal.x, ny = plane.normal.y, nz = plane.normal.z, c = plane.constant;
    const dist = (i) => nx * pos[i * 3] + ny * pos[i * 3 + 1] + nz * pos[i * 3 + 2] + c;
    const out = new Uint32Array(idx.length * 2), ep = [], en = [], eu = [];
    let n = 0, nv = pos.length / 3;
    const mid = (a, b, da, db) => {                    // the point where edge a-b meets the plane, as a new vertex
      const t = da / (da - db), s = 1 - t;
      ep.push(pos[a * 3] * s + pos[b * 3] * t, pos[a * 3 + 1] * s + pos[b * 3 + 1] * t, pos[a * 3 + 2] * s + pos[b * 3 + 2] * t);
      if (nor) en.push(nor[a * 3] * s + nor[b * 3] * t, nor[a * 3 + 1] * s + nor[b * 3 + 1] * t, nor[a * 3 + 2] * s + nor[b * 3 + 2] * t);
      if (uv) eu.push(uv[a * 2] * s + uv[b * 2] * t, uv[a * 2 + 1] * s + uv[b * 2 + 1] * t);
      return nv++;
    };
    for (let t = 0; t < idx.length; t += 3) {
      let a = idx[t], b = idx[t + 1], cc = idx[t + 2], da = dist(a), db = dist(b), dc = dist(cc);
      const ins = (da >= 0) + (db >= 0) + (dc >= 0);
      if (ins === 3) { out[n++] = a; out[n++] = b; out[n++] = cc; continue; }
      if (ins === 0) continue;
      // turn the triangle (keeping its winding) until a is kept and c is cut
      for (let r = 0; r < 3 && !(da >= 0 && dc < 0); r++) { const ta = a, tda = da; a = b; da = db; b = cc; db = dc; cc = ta; dc = tda; }
      if (ins === 1) { const ab = mid(a, b, da, db), ac = mid(a, cc, da, dc); out[n++] = a; out[n++] = ab; out[n++] = ac; }
      else { const bc = mid(b, cc, db, dc), ac = mid(a, cc, da, dc); out[n++] = a; out[n++] = b; out[n++] = bc; out[n++] = a; out[n++] = bc; out[n++] = ac; }
    }
    if (!ep.length) return { pos, nor, uv, idx: n === idx.length ? idx : out.slice(0, n) };
    const grow = (src, extra) => { const g = new Float32Array(src.length + extra.length); g.set(src); g.set(extra, src.length); return g; };
    return { pos: grow(pos, ep), nor: nor && grow(nor, en), uv: uv && grow(uv, eu), idx: out.slice(0, n) };
  }

  // ---- materials. The path tracer reads the same fields the renderer does, so nearly every material is used as it is.
  // Glass is the exception: in the normal view it is a faint see-through sheet (real transmission there costs a second
  // pass over the whole scene). For the photo it becomes real glass: all light goes through, tinted a little, and the
  // surface mirrors the room and the sky at grazing angles. No thickness, so a pane does not bend the view behind it.
  // Glowing things are the other exception. Their glow was tuned by eye for the normal view, where it lights nothing.
  // Here anything that glows is a real lamp, and a small one that rays only find by luck: at an indoor exposure a
  // ceiling light lens "off" by day would outshine the windows and fill the room with bright specks. So the glow is
  // turned well down (GLOW): screens and LEDs still read as lit, and at night the room lights do the lighting.
  const GLOW = { day: 0.05, night: 0.3 };
  const glassOf = new Map(), glowOf = new Map();
  let glow = GLOW.day;
  const isGlass = (m) => m.transparent && !m.alphaTest && m.opacity < 0.5 && (m.roughness ?? 1) <= 0.15 && !m.map;
  function photoMat(m) {
    if (!isGlass(m)) {
      if (!(m.emissiveIntensity > 0) || !m.emissive || (!m.emissiveMap && m.emissive.getHex() === 0)) return m;
      const e = m.clone(); e.emissiveIntensity = m.emissiveIntensity * glow; glowOf.set(m, e);
      return e;
    }
    if (!glassOf.has(m)) glassOf.set(m, new THREE.MeshPhysicalMaterial({ name: m.name, side: THREE.DoubleSide }));
    const g = glassOf.get(m);
    g.color.setRGB(1, 1, 1).lerp(m.color, m.opacity);       // what a sheet of this opacity lets through
    g.roughness = m.roughness; g.metalness = 0; g.transmission = 1; g.ior = 1.5; g.thickness = 0;
    return g;
  }

  // ---- the sky as a light. The path tracer wants a float equirect image it can read back (to aim rays at the bright
  // parts); the page's sky is an 8 bit JPEG, so it is converted once. The sun in a JPEG is no brighter than a white
  // cloud, which is right here: the sun itself is the directional light.
  function skyLight() {
    const bg = sky() || (scene.background && scene.background.isTexture ? scene.background : null);
    const from = bg || 'flat';
    if (envTex && envFrom === from) return envTex;
    if (envTex) envTex.dispose();
    let w = 4, h = 2, data;
    if (bg && bg.image) {
      w = 1024; h = 512;
      const cv = document.createElement('canvas'); cv.width = w; cv.height = h;
      const cx = cv.getContext('2d', { willReadFrequently: true }); cx.drawImage(bg.image, 0, 0, w, h);
      const px = cx.getImageData(0, 0, w, h).data; data = new Float32Array(w * h * 4);
      const lin = new Float32Array(256); for (let i = 0; i < 256; i++) { const s = i / 255; lin[i] = s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; }
      let r = 0, g = 0, b = 0, wt = 0;
      for (let y = 0; y < h; y++) {      // a data texture's first row is the bottom of the picture
        const k = Math.sin((y + 0.5) / h * Math.PI);          // rows near the poles cover little of the sphere
        for (let x = 0; x < w; x++) {
          const s = ((h - 1 - y) * w + x) * 4, d = (y * w + x) * 4;
          data[d] = lin[px[s]]; data[d + 1] = lin[px[s + 1]]; data[d + 2] = lin[px[s + 2]]; data[d + 3] = 1;
          r += data[d] * k; g += data[d + 1] * k; b += data[d + 2] * k; wt += k;
        }
      }
      skyMean.setRGB(r / wt, g / wt, b / wt);      // what a window gets on average: sky above, ground below
    } else { data = new Float32Array(w * h * 4); for (let i = 0; i < data.length; i += 4) { data[i] = 0.5; data[i + 1] = 0.62; data[i + 2] = 0.78; data[i + 3] = 1; } skyMean.setRGB(0.5, 0.62, 0.78); }
    envTex = new THREE.DataTexture(data, w, h, THREE.RGBAFormat, THREE.FloatType);
    envTex.mapping = THREE.EquirectangularReflectionMapping; envTex.colorSpace = THREE.LinearSRGBColorSpace;
    envTex.minFilter = envTex.magFilter = THREE.LinearFilter; envTex.wrapS = THREE.RepeatWrapping; envTex.needsUpdate = true;
    envFrom = from;
    return envTex;
  }

  // ---- rays against the model as it is shown: is something solid in the way? (For finding the outdoor side of a pane and
  // whether the camera is under a roof.) The hidden originals carry the click BVHs, and a raycast goes by layers, so this
  // sees what is switched on. Glass does not count, nor anything above the slice.
  const ray = new THREE.Raycaster(); ray.camera = camera;
  function blocked(origin, dir, far) {
    ray.set(origin, dir); ray.far = far; ray.layers.mask = camera.layers.mask;
    for (const h of ray.intersectObjects(scene.children, true)) {
      if (!h.object.isMesh) continue;
      const m = Array.isArray(h.object.material) ? h.object.material[0] : h.object.material;
      if (!m || m.toneMapped === false || isGlass(m)) continue;
      if ((m.clippingPlanes || []).some((p) => p.constant < 1e5 && p.distanceToPoint(h.point) < 0)) continue;
      return true;
    }
    return false;
  }
  // The flat panes in a glass mesh. One mesh can hold many panes (every window of the shell is one mesh), so its
  // triangles are grouped into pieces that touch, and each thin flat piece becomes a rectangle: centre, facing, size.
  function findPanes(g, tint) {
    const pos = g.attributes.position.array, idx = g.index.array, key = new Map(), root = [];
    const find = (i) => { while (root[i] !== i) { root[i] = root[root[i]]; i = root[i]; } return i; };
    const id = (v) => { const k = `${Math.round(pos[v * 3] * 500)},${Math.round(pos[v * 3 + 1] * 500)},${Math.round(pos[v * 3 + 2] * 500)}`; let n = key.get(k); if (n === undefined) { n = root.length; root.push(n); key.set(k, n); } return n; };
    const tri = [];
    for (let t = 0; t < idx.length; t += 3) { const a = id(idx[t]), b = id(idx[t + 1]), c = id(idx[t + 2]); root[find(b)] = find(a); root[find(c)] = find(a); tri.push(a); }
    const groups = new Map();
    for (let t = 0; t < tri.length; t++) { const r = find(tri[t]); if (!groups.has(r)) groups.set(r, []); groups.get(r).push(t * 3); }
    const P = (v, out) => out.set(pos[v * 3], pos[v * 3 + 1], pos[v * 3 + 2]), a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3(), out = [];
    for (const ts of groups.values()) {
      let best = 0; const n = new THREE.Vector3();
      for (const t of ts) { P(idx[t], a); P(idx[t + 1], b); P(idx[t + 2], c); b.sub(a); c.sub(a); b.cross(c); const ar = b.length(); if (ar > best) { best = ar; n.copy(b).divideScalar(ar); } }       // the biggest triangle lies in the pane's face
      if (!best) continue;
      const u = Math.abs(n.y) > 0.9 ? new THREE.Vector3(1, 0, 0) : new THREE.Vector3(0, 1, 0).cross(n).normalize(), v = new THREE.Vector3().crossVectors(n, u).normalize();
      u.crossVectors(v, n);
      const lo = [1e9, 1e9, 1e9], hi = [-1e9, -1e9, -1e9];
      for (const t of ts) for (let k = 0; k < 3; k++) { P(idx[t + k], a); const q = [a.dot(u), a.dot(v), a.dot(n)]; for (let j = 0; j < 3; j++) { lo[j] = Math.min(lo[j], q[j]); hi[j] = Math.max(hi[j], q[j]); } }
      const w = hi[0] - lo[0], h = hi[1] - lo[1], th = hi[2] - lo[2];
      if (w < 0.15 || h < 0.15 || th > 0.12) continue;          // a sliver, or not a flat sheet
      const cen = new THREE.Vector3().addScaledVector(u, (lo[0] + hi[0]) / 2).addScaledVector(v, (lo[1] + hi[1]) / 2).addScaledVector(n, (lo[2] + hi[2]) / 2);
      out.push({ c: cen, n, w, h, th, tint, inward: null });
    }
    return out;
  }
  // A pane is a window if exactly one of its sides looks out at open sky (straight out or a little upward, past the
  // eaves). The other side is the room. Cabinet glass and shower glass have walls on both sides and stay ordinary glass.
  const UP = new THREE.Vector3(0, 1, 0);
  function outdoorSide(p) {
    const open = [1, -1].map((sg) => {
      const o = p.c.clone().addScaledVector(p.n, sg * (p.th / 2 + 0.05));
      return [0, 0.36, 0.84].some((rise) => !blocked(o, _a.copy(p.n).multiplyScalar(sg).addScaledVector(UP, rise).normalize(), 80));
    });
    if (open[0] !== open[1]) p.inward = p.n.clone().multiplyScalar(open[0] ? -1 : 1);
  }

  // Panes side by side in one wall (the lites of a door, a row of windows) become one rectangle around them all, dimmed
  // by how much of it is glass, so the light let in is the same. Fewer, bigger lights is the point: the path tracer
  // picks one light at random for every bounce, so each light added thins the samples of all the others.
  function joinPanes(list) {
    const rects = list.map((p) => {
      const n = p.inward, u = Math.abs(n.y) > 0.9 ? new THREE.Vector3(1, 0, 0) : new THREE.Vector3(0, 1, 0).cross(n).normalize(), v = new THREE.Vector3().crossVectors(n, u).normalize();
      u.crossVectors(v, n);
      const cu = p.c.dot(u), cv = p.c.dot(v);
      return { n, u, v, d: p.c.dot(n), th: p.th, tint: p.tint, glass: p.w * p.h, u0: cu - p.w / 2, u1: cu + p.w / 2, v0: cv - p.h / 2, v1: cv + p.h / 2 };
    });
    const GAP = 0.6;
    for (let merged = true; merged;) {
      merged = false;
      for (let i = 0; i < rects.length && !merged; i++) for (let j = i + 1; j < rects.length; j++) {
        const a = rects[i], b = rects[j];
        if (a.n.dot(b.n) < 0.99 || Math.abs(a.d - b.d) > 0.12 || b.u0 - a.u1 > GAP || a.u0 - b.u1 > GAP || b.v0 - a.v1 > GAP || a.v0 - b.v1 > GAP) continue;
        a.u0 = Math.min(a.u0, b.u0); a.u1 = Math.max(a.u1, b.u1); a.v0 = Math.min(a.v0, b.v0); a.v1 = Math.max(a.v1, b.v1); a.glass += b.glass;
        rects.splice(j, 1); merged = true; break;
      }
    }
    return rects.map((r) => ({ c: new THREE.Vector3().addScaledVector(r.u, (r.u0 + r.u1) / 2).addScaledVector(r.v, (r.v0 + r.v1) / 2).addScaledVector(r.n, r.d),
      n: r.n, inward: r.n, w: r.u1 - r.u0, h: r.v1 - r.v0, th: r.th, tint: r.tint, fill: Math.min(1, r.glass / ((r.u1 - r.u0) * (r.v1 - r.v0))), glass: r.glass }));
  }

  // ---- build the scene the path tracer sees
  function build() {
    const meshes = [], inst = [];
    tris = 0; skipped = 0; panes = []; glowOf.clear();
    glow = sun.visible && sun.intensity > 0 ? GLOW.day : GLOW.night;
    const planesOf = (m) => (m.clippingPlanes || []).filter((p) => p.constant < 1e5);
    const take = (o, m) => {
      const g = bake(o, planesOf(m)); if (!g) return;
      tris += g.index.count / 3;
      const pm = new THREE.Mesh(g, photoMat(m)); pm.matrixAutoUpdate = false; meshes.push(pm);
      if (isGlass(m) && g.index.count <= 30000) panes.push(...findPanes(g, pm.material.color));
    };
    drawn((o, m) => { if (o.isInstancedMesh) inst.push([o, m]); else take(o, m); });
    // Instanced trees: the few near the house first, the far woods (hundreds of copies each) only while the triangle
    // budget lasts. Whatever does not fit is left out and the panel says so.
    const cost = ([o]) => o.count * (o.geometry.index ? o.geometry.index.count : o.geometry.attributes.position.count) / 3;
    inst.sort((a, b) => cost(a) - cost(b));
    for (const e of inst) { if (tris + cost(e) > MAX_TRIS) { skipped++; continue; } take(e[0], e[1]); }
    for (const p of panes) outdoorSide(p);
    // double glazing is two sheets: one light per window, not two
    panes = panes.filter((p, i) => p.inward && !panes.some((q, j) => j < i && q.inward && Math.abs(q.n.dot(p.n)) > 0.99 && q.c.distanceTo(p.c) < 0.15));
    panes = joinPanes(panes);
    pscene = new THREE.Scene();
    for (const m of meshes) pscene.add(m);
    pscene.environment = skyLight();
  }
  // The lights, set for every photo (they depend on where the camera stands, the build does not).
  function setLights() {
    for (const L of plights) { pscene.remove(L); if (L.target) pscene.remove(L.target); }
    plights = []; portals = 0;
    const night = !(sun.visible && sun.intensity > 0);
    inside = blocked(camera.getWorldPosition(new THREE.Vector3()), UP, 40);
    if (!night) {
      psun = new THREE.DirectionalLight(sun.color, sun.intensity); pscene.add(psun, psun.target); plights.push(psun);
      aimSun(0, 0);
    } else psun = null;
    // the room lights that are on (night): the same point lights, where they are
    scene.traverse((o) => {
      if (!o.isPointLight || o.intensity < 0.02) return;
      for (let p = o; p; p = p.parent) if (!p.visible) return;
      const L = new THREE.PointLight(o.color, o.intensity, o.distance, o.decay); o.getWorldPosition(L.position); pscene.add(L); plights.push(L);
    });
    if (inside && !night) {
      const eye = camera.getWorldPosition(new THREE.Vector3());
      // Only windows the camera has a clear line to, and of those the ones that fill most of its view (glass area over
      // distance squared): a window in another room would cost more noise here than the light it lends.
      const near = panes.map((p) => [p.c.distanceTo(eye), p]).filter(([d, p]) => d < PORTAL_REACH && !blocked(eye, _b.copy(p.c).addScaledVector(p.inward, 0.1).sub(eye).normalize(), d - 0.2))
        .sort((x, y) => y[1].glass / (y[0] * y[0]) - x[1].glass / (x[0] * x[0])).slice(0, MAX_PORTALS);
      for (const [, p] of near) {
        const L = new THREE.RectAreaLight(new THREE.Color().copy(skyMean).multiply(p.tint), p.fill, p.w, p.h);
        L.position.copy(p.c).addScaledVector(p.inward, p.th / 2 + 0.03); L.lookAt(_a.copy(L.position).add(p.inward));
        pscene.add(L); plights.push(L); portals++;
      }
    }
    pscene.background = scene.background;
    // under a roof by day the window lights stand in for the sky; at night a trace of sky keeps the outdoors from pitch black
    pscene.environmentIntensity = night ? (inside ? 0 : 0.03) : portals ? 0 : 1;
    pscene.updateMatrixWorld(true);
    plights.sort((a, b) => (a.uuid < b.uuid ? 1 : a.uuid > b.uuid ? -1 : 0));    // the order the path tracer keeps its lights in
  }
  // The sun as a small disc, not a point: every sample comes from a slightly different place on it, and the average
  // of many samples is a soft edged shadow that widens with distance, as outdoors.
  const _a = new THREE.Vector3(), _b = new THREE.Vector3();
  function aimSun(u, v) {
    if (!psun) return;
    _a.set(0, 1, 0).cross(sunDir).normalize(); _b.crossVectors(sunDir, _a);
    const r = Math.sqrt(u) * SUN_HALF_ANGLE, t = v * Math.PI * 2;
    psun.position.copy(sunDir).addScaledVector(_a, r * Math.cos(t)).addScaledVector(_b, r * Math.sin(t)).multiplyScalar(100);
    psun.target.position.set(0, 0, 0); psun.updateMatrixWorld(); psun.target.updateMatrixWorld();
  }

  // ---- exposure. The normal view lights rooms with lights that ignore walls; real daylight indoors is a tiny fraction
  // of outdoors. So, like a camera, the photo is exposed for what is in the frame, and the aim is the normal view itself:
  // just before the photo starts the normal frame is drawn once and its average brightness on screen is measured
  // (meterNormal). A few rows of the float picture are then read back and the exposure is found that puts them, through
  // the same tone curve, at that brightness. The Brightness slider moves it from there.
  const srgbLin = new Float32Array(256); for (let i = 0; i < 256; i++) { const c = i / 255; srgbLin[i] = c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; }
  function meterNormal() {
    draw(); renderer.setRenderTarget(null);
    const gl = renderer.getContext(), w = gl.drawingBufferWidth, h = gl.drawingBufferHeight, rows = Math.min(24, h), buf = new Uint8Array(w * 4);
    let sum = 0;
    for (let r = 0; r < rows; r++) {
      gl.readPixels(0, Math.floor((r + 0.5) * h / rows), w, 1, gl.RGBA, gl.UNSIGNED_BYTE, buf);
      for (let i = 0; i < buf.length; i += 4) sum += 0.2126 * srgbLin[buf[i]] + 0.7152 * srgbLin[buf[i + 1]] + 0.0722 * srgbLin[buf[i + 2]];
    }
    return sum / (rows * w);
  }
  const aces = (L) => { const v = L / 0.6; return Math.min(1, Math.max(0, (v * (v + 0.0245786) - 0.000090537) / (v * (0.983729 * v + 0.432951) + 0.238081))); };     // three.js's ACES fit, on a grey
  function meter() {
    const t = pt.target, w = t.width, h = t.height, rows = Math.min(24, h), buf = new Float32Array(w * 4), Ls = [];
    const CH = Math.max(8, Math.floor(w / 24));       // averaged in runs of pixels first: early on a pixel is black or a speck, a run of them is close to the truth
    for (let r = 0; r < rows; r++) {
      renderer.readRenderTargetPixels(t, 0, Math.floor((r + 0.5) * h / rows), w, 1, buf);
      for (let x = 0; x + CH <= w; x += CH) {
        let L = 0;
        for (let i = x * 4; i < (x + CH) * 4; i += 4) { const l = 0.2126 * buf[i] + 0.7152 * buf[i + 1] + 0.0722 * buf[i + 2]; if (l === l) L += Math.min(l, 8); }
        Ls.push(L / CH);
      }
    }
    if (!Ls.length) return;
    if (aim > 0) {             // halve the range (in stops) until the tone mapped average meets the normal view's
      let lo = Math.log2(0.25), hi = Math.log2(256);       // a daylit room really is a hundredth as bright as outdoors
      for (let i = 0; i < 20; i++) { const e = 2 ** ((lo + hi) / 2); let m = 0; for (const L of Ls) m += aces(L * e); if (m / Ls.length < aim) lo = (lo + hi) / 2; else hi = (lo + hi) / 2; }
      autoExp = 2 ** ((lo + hi) / 2);
    } else { let sum = 0; for (const L of Ls) sum += Math.log(Math.max(L, 1e-3)); autoExp = Math.min(48, Math.max(1, KEY / Math.exp(sum / Ls.length))); }
    applyExposure();
  }

  // The path tracer itself, made once. Its GPU program is the slow part of a first photo (several seconds to compile on
  // Windows and on phones), and nothing in it depends on the scene, so it is made and compiled ahead of time (warm).
  function makeTracer() {
    const warn = console.warn; console.warn = () => {};          // it announces its own deprecation in favour of WebGPU on every start
    try { pt = new PT.WebGLPathTracer(renderer); } finally { console.warn = warn; }
    // Enough for window light to reach a ceiling by way of the floor. A phone stops two bounces sooner: each bounce
    // costs about as much as the first hit, and the light left after four is a few percent of the picture.
    pt.bounces = touch ? 4 : 6; pt.transmissiveBounces = touch ? 5 : 8;
    pt.filterGlossyFactor = 0.5;                      // tames the bright specks shiny things throw onto matte ones
    pt.renderDelay = 0; pt.minSamples = 1; pt.fadeDuration = 0; pt.rasterizeScene = false; pt.dynamicLowRes = false;
    pt.textureSize.set(touch ? 512 : 1024, touch ? 512 : 1024);
    pt._generator.attributes = ['position', 'normal', 'tangent', 'color', 'uv'];      // no second uv set here; it would only be carried around
    // Speck clamp. A room by day is lit mostly by a few small bright things (the patch of floor the sun lands on, a
    // window), and a bounced ray finds one of them only now and then, with a sample worth many times white when it
    // does. Those rare hits are the specks that take thousands of samples to average out. So the bounced part of
    // each sample is capped a little above display white (CLAMP): what the camera sees directly (a sunlit patch,
    // the sky in a window) is untouched, and specks fade several times faster. The price is that bounced light is
    // a little dimmer near the brightest spots. The path tracer has no such setting, so three lines go into its
    // shader: remember what has been gathered when the path leaves the first solid surface, cap the rest at the end.
    const mat = pt._pathTracer.material, F = mat.fragmentShader;
    const k1 = 'bool isTransmissiveRay = ! surf.volumeParticle && dot( scatterRec.direction, surf.faceNormal * surfaceHit.side ) < 0.0;', k2 = 'gl_FragColor.a *= opacity;';
    const a1 = F.indexOf(k1), a2 = F.lastIndexOf(k2);
    if (a1 > 0 && a2 > a1 && !mat.uniforms.photoClamp) {
      mat.uniforms.photoClamp = clampU;
      mat.fragmentShader = 'uniform float photoClamp;\nbool photoSplit = false;\nvec3 photoDirect = vec3( 0.0 );\n' + F.slice(0, a1 + k1.length)
        + '\nif ( ! photoSplit && ! isTransmissiveRay ) { photoSplit = true; photoDirect = gl_FragColor.rgb; }\n' + F.slice(a1 + k1.length, a2)
        + 'if ( photoSplit ) gl_FragColor.rgb = photoDirect + min( gl_FragColor.rgb - photoDirect, vec3( photoClamp ) );\n'
        // a sample that came out as not-a-number or infinite (a phone GPU's lower precision can do it on a grazing hit)
        // would poison that pixel for good, since every later sample is averaged with it. It counts as black instead.
        + 'if ( any( isnan( gl_FragColor.rgb ) ) || any( isinf( gl_FragColor.rgb ) ) ) gl_FragColor.rgb = vec3( 0.0 );\n' + F.slice(a2);
      mat.needsUpdate = true;
    }
    pt.renderToCanvas = false; pt.synchronizeRenderSize = false;
    try { bvhWorker = bvhWorker || new BVHWorker(BVH_WORKER_URL); pt.setBVHWorker(bvhWorker); } catch (err) { bvhWorker = null; }
  }
  // A scene of one small triangle: something to compile the program against, and what a phone keeps loaded between photos.
  function tinyScene() {
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute([0, 0, 0, 0.01, 0, 0, 0, 0.01, 0], 3)); g.computeVertexNormals();
    const t = new THREE.Scene(); t.add(new THREE.Mesh(g, new THREE.MeshStandardMaterial())); t.background = scene.background; return t;
  }
  // Compile ahead: once the walkthrough has loaded and gone quiet, the path tracer is made and its program compiled in
  // the background (the browser compiles on its own thread where it can), so pressing Photo skips that wait.
  function warm(force = false) {
    if (warming || pt || active) return warming;
    if (!force && !renderer.extensions.has('KHR_parallel_shader_compile') || !renderer.extensions.get('EXT_color_buffer_float')) return null;     // without it the compile would freeze the walkthrough instead (force: tests)
    warming = (async () => {
      try {
        if (!PT) PT = await import('three-gpu-pathtracer');
        if (pt || active) return;
        makeTracer(); pt._pathTracer.setSize(16, 16); pt._lowResPathTracer.setSize(4, 4);
        pcam.copy(camera); pt.setScene(tinyScene(), pcam);
        // the program's switches (depth of field, sky picture, fog) set as a photo will have them, then compiled
        // and compiled with the renderer as a photo has it: drawing into the float target, with the photo's tone curve and
        // colour set on the renderer. Any difference makes a different program, and the photo would compile its own.
        // (Setting the switches starts the compile at once, so the renderer is put in that state first.)
        const pm = pt._pathTracer.material, tm = renderer.toneMapping, cs = renderer.outputColorSpace, rt = renderer.getRenderTarget();
        renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.setRenderTarget(pt._pathTracer._primaryTarget);
        let job; try { pm.onBeforeRender(); job = pt._pathTracer._compilePromise || pt._pathTracer.compileMaterial(); } finally { renderer.setRenderTarget(rt); renderer.toneMapping = tm; renderer.outputColorSpace = cs; }
        await job;
      } catch (err) { console.warn('photo: could not prepare ahead', err); }
    })();
    return warming;
  }
  // ---- open, frame by frame, save, close
  async function open() {
    if (active) return;
    const gl = renderer.getContext();
    if (!renderer.capabilities.isWebGL2 && !(gl instanceof WebGL2RenderingContext) || !renderer.extensions.get('EXT_color_buffer_float')) { toast('Photo needs a graphics feature this device does not have'); return; }
    try { aim = draw ? meterNormal() : 0; } catch (err) { aim = 0; }
    active = true; ready = false; go = false; picking = false; shown = false; goBtn.hidden = false; goBtn.textContent = 'Render'; done = false; lastShown = -1; expAt = 0; stops = 0; slider.value = 0; frameMs = 0; lastT = 0;
    const mine = ++token;
    if (document.pointerLockElement) document.exitPointerLock();
    saved = { tm: renderer.toneMapping, exp: renderer.toneMappingExposure, cs: renderer.outputColorSpace, ac: renderer.autoClear };
    document.body.classList.add('photo'); shield.hidden = false; panel.hidden = false;
    say('Building the scene'); onOpen();
    try {
      await new Promise((r) => requestAnimationFrame(() => setTimeout(r, 30)));      // let the panel paint before the page stalls on the build
      if (warming) await warming;
      if (!PT) PT = await import('three-gpu-pathtracer');
      if (mine !== token) return;
      sun.target.updateMatrixWorld(); sun.updateMatrixWorld();
      sunDir.setFromMatrixPosition(sun.matrixWorld).sub(_a.setFromMatrixPosition(sun.target.matrixWorld)).normalize();
      if (!pt) makeTracer();
      sizeUp(false);
      const s = signature();
      if (s !== sig || !pscene) {
        build(); setLights(); builds++;
        if (bvhWorker) {
          say('Building the scene');
          await pt.setSceneAsync(pscene, pcam, { onProgress: (f) => { if (mine === token) say(`Building the scene ${Math.round(f * 100)}%`); } });
        } else pt.setScene(pscene, pcam);
        if (mine !== token) return;
        // The generator keeps its own copies of every mesh so it can update a moving scene. Nothing moves during a photo
        // and the data is on the GPU now, so a fresh generator frees a few hundred megabytes of them.
        const gen = new PT.PathTracingSceneGenerator(); gen.attributes = pt._generator.attributes; if (bvhWorker) gen.setBVHWorker(bvhWorker); pt._generator = gen;
        for (const m of pscene.children) if (m.isMesh) m.geometry = new THREE.BufferGeometry();
        sig = s;
      } else { setLights(); pt.updateLights(); pt.updateEnvironment(); pt.setCamera(pcam); }
      // the canvas is the float picture through the same tone curve as the normal view
      renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.outputColorSpace = THREE.SRGBColorSpace; autoExp = 1; applyExposure();
      clampU.value = 1e9; clamped = false;
      sizeUp(true);
      if (mine !== token) return;
      ready = true;
      if (go) begin(); else say('Pick a size, then press Render');
    } catch (err) {
      console.error(err);
      if (mine === token) { close(); toast('The photo could not be made on this device'); }
    }
  }
  // Render pressed: before the scene is built it only marks the wish, and open() starts the picture once it is ready.
  function start() {
    if (!active) return;
    go = true; goBtn.hidden = true;
    if (ready) begin(); else say('Building the scene, then rendering');
  }
  function begin() {
    sizeUp(true); done = false; lastShown = -1; expAt = 0; clampU.value = 1e9; clamped = false; frameMs = 0; lastT = 0;
    pt.reset(); say('Starting');
  }
  // Picture size: a fixed size from the menu, or the canvas as it is when the photo starts, scaled down if it is more
  // pixels than the cap. Either way it is set here and nowhere else: resizing the window only changes how the picture
  // sits on the canvas (letterboxed), never the picture. Tiles split each sample over several frames so the page stays
  // responsive: more of them for bigger pictures, and more again if frames come slowly (frame()).
  function sizeUp(restart) {
    const gl = renderer.getContext(); lastW = gl.drawingBufferWidth; lastH = gl.drawingBufferHeight;
    if (SIZES[size]) [W, H] = SIZES[size];
    else { const k = Math.min(1, Math.sqrt(MAX_PIXELS / (lastW * lastH))); W = Math.max(16, Math.floor(lastW * k)); H = Math.max(16, Math.floor(lastH * k)); }
    pcam.copy(camera); pcam.aspect = W / H; pcam.updateProjectionMatrix(); pcam.updateMatrixWorld();
    if (!restart) return;
    pt._pathTracer.setSize(W, H); pt._lowResPathTracer.setSize(Math.max(1, Math.floor(W * 0.25)), Math.max(1, Math.floor(H * 0.25)));
    const n = touch ? 3 : W * H > 4.5e6 ? 4 : W * H > 1.2e6 ? 3 : 2; pt.tiles.set(n, n);
    redos = 0; shown = false;
    pt.setCamera(pcam);
  }
  // Sun jitter: one direction per whole pass, not per tile. Changed per tile, each square of the first pass got its own
  // hard shadow edge and its own sun, and those squares stood out until enough passes had averaged them (Maxwell on his
  // phone, 11/28/2026). The directions follow a Halton sequence, which covers the sun's disc more evenly than random.
  const halton = (i, b) => { let f = 1, r = 0; for (; i > 0; i = Math.floor(i / b)) { f /= b; r += f * (i % b); } return r; };
  // Failed squares. A tile that the GPU dropped (a phone can give up on a long draw) comes back pure black. After the
  // first passes the rendered picture is read back at a few rows, and a tile with nothing in it, while the rest of the
  // picture has light, is a failure: the whole pass is thrown away and done again with smaller tiles.
  function failedTile() {
    const t = pt.target, w = t.width, h = t.height, nx = pt.tiles.x, ny = pt.tiles.y, rowsPer = 4, buf = new Float32Array(w * 4);
    const tw = Math.ceil(w / nx), th = Math.ceil(h / ny);          // the path tracer's own tile sizes, so no pixel is counted in the wrong tile
    const sum = new Float64Array(nx * ny), bad = new Uint8Array(nx * ny);
    for (let ty = 0; ty < ny; ty++) for (let r = 0; r < rowsPer; r++) {
      const y = Math.min(h - 1, ty * th + Math.floor((r + 0.5) * th / rowsPer)); if (y >= h) continue;
      renderer.readRenderTargetPixels(t, 0, y, w, 1, buf);
      for (let x = 0; x < w; x++) {
        const v = buf[x * 4] + buf[x * 4 + 1] + buf[x * 4 + 2], k = ty * nx + Math.min(nx - 1, Math.floor(x / tw));
        if (!Number.isFinite(v)) bad[k] = 1; else sum[k] += v;
      }
    }
    const lit = [...sum].filter((v) => v > 0).length;
    return bad.some((b) => b) || (lit >= Math.ceil(nx * ny / 2) && lit < nx * ny);
  }
  // What the canvas shows. The path tracer would put its picture on the canvas after every tile, half way through a
  // pass. Where the GPU cannot blend float pictures (many phones) it then keeps a second copy, and the half done copy
  // mixes the new tiles with stale ones: squares that look wrong until enough passes have gone by (Maxwell, 11/28/2026).
  // So only whole passes are shown: when a pass completes its picture is copied aside, and the canvas is drawn from that
  // copy, once per pass or when Brightness moves (a canvas nobody draws on keeps its picture, so idle frames cost nothing).
  function keepPass() {
    const q = pt._quad, was = renderer.getRenderTarget(), tw = pt.target.width, th = pt.target.height;
    if (!snap || snap.width !== tw || snap.height !== th) { if (snap) snap.dispose(); snap = new THREE.WebGLRenderTarget(tw, th, { type: THREE.HalfFloatType, depthBuffer: false, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter }); }
    q.material.map = pt.target.texture; q.material.opacity = 1; q.material.blending = THREE.NoBlending;
    renderer.setRenderTarget(snap); q.render(renderer); renderer.setRenderTarget(was);
    shown = true; dirty = true;
  }
  function showPass() {
    if (!shown || !dirty) return;
    const q = pt._quad, ac = renderer.autoClear, pr = renderer.getPixelRatio(), gl = renderer.getContext();
    const cw = gl.drawingBufferWidth, ch = gl.drawingBufferHeight, cc = renderer.getClearColor(new THREE.Color()), ca = renderer.getClearAlpha();
    let vw = cw, vh = Math.round(cw * H / W); if (vh > ch) { vh = ch; vw = Math.round(ch * W / H); }      // the whole picture, as large as fits
    q.material.map = snap.texture; q.material.opacity = 1; q.material.blending = THREE.NoBlending;
    renderer.setRenderTarget(null); renderer.setClearColor(0x000000, 1); renderer.clear();
    renderer.setViewport((cw - vw) / 2 / pr, (ch - vh) / 2 / pr, vw / pr, vh / pr);
    renderer.autoClear = false; q.render(renderer); renderer.autoClear = ac;
    renderer.setViewport(0, 0, cw / pr, ch / pr); renderer.setClearColor(cc, ca);
    dirty = false;
  }
  function frame() {
    if (!active || !ready) return;
    const gl = renderer.getContext();
    if (gl.drawingBufferWidth !== lastW || gl.drawingBufferHeight !== lastH) { lastW = gl.drawingBufferWidth; lastH = gl.drawingBufferHeight; dirty = true; }      // the window was resized: the same picture, placed again
    if (!go || picking) { showPass(); return; }      // waiting for Render, or the size menu is open: no samples
    const now = performance.now(); if (lastT) frameMs += ((now - lastT) - frameMs) * 0.2; lastT = now;
    renderer.setRenderTarget(null);
    pt.pausePathTracing = done;
    const atPassStart = Math.abs(pt.samples - Math.round(pt.samples)) < 1e-6;
    if (!done && psun && atPassStart) {
      const k = Math.round(pt.samples);
      if (k === 0) aimSun(0, 0); else aimSun(halton(k, 2), halton(k, 3));       // the first pass (the one shown first) has the sun's centre
      try { pt._pathTracer.material.lights.updateFrom(plights, []); } catch (err) { /* a library change: hard shadows */ }
    }
    pt.renderSample();
    const n = Math.floor(pt.samples);
    if (n !== lastShown) {
      lastShown = n;
      if (n >= 1) keepPass();
      if (n >= 1 && n <= 2 && redos < 2 && failedTile()) {
        redos++; pt.tiles.set(Math.min(8, pt.tiles.x + 1), Math.min(8, pt.tiles.x + 1)); pt.reset(); lastShown = -1; clamped = false; clampU.value = 1e9;
        console.warn('photo: a tile came back empty, pass redone with', pt.tiles.x, 'x', pt.tiles.y, 'tiles'); return;
      }
      // one pass in: enough to meter, so the speck clamp can be set, and the picture starts again with it on. The canvas
      // keeps showing that first pass until the clamped one is whole (no preview this time, so no flash of blur).
      if (n >= 1 && !clamped) {
        meter(); clamped = true; clampU.value = CLAMP / autoExp; pt.reset(); lastShown = -1; return;
      }
      if ([2, 8, 24, 64, 160, 400].some((k) => n >= k && expAt < k)) { expAt = n; meter(); }      // meter early, then again as the noise settles (specks read as brightness at first)
      if (n >= MAX_SAMPLES) done = true;
      // Tile size follows the frame time, between whole passes only (so no tile is left half done): slow frames cut a
      // pass into more tiles so the page keeps answering, quick ones join them up, since every tile costs a full
      // screen redraw and a frame's worth of waiting on top of its own work.
      if (!done && n >= 1) {
        if (frameMs > 160 && pt.tiles.x < 8) { pt.tiles.set(pt.tiles.x + 1, pt.tiles.x + 1); frameMs = 80; }
        else if (frameMs > 0 && frameMs < 45 && pt.tiles.x > 1) { pt.tiles.set(pt.tiles.x - 1, pt.tiles.x - 1); frameMs = 80; }
      }
      const note = skipped ? ' · far trees left out' : '';
      say(pt.isCompiling ? 'Compiling the renderer' : n < 1 || !clamped ? 'Starting' : done ? `Done, ${n} samples${note}` : `${n} of ${MAX_SAMPLES} samples${note}`);
    } else if (n < 1) say(pt.isCompiling ? 'Compiling the renderer' : 'Starting');
    showPass();
  }
  // The canvas keeps no copy of a frame once the browser has shown it, so the picture is drawn again and read in the same breath.
  function save() {
    if (!ready || !shown) { toast('Wait for the first sample'); return null; }
    // drawn once at the picture's own size, read, and the canvas put back (the copy is taken when toBlob is called)
    const pr = renderer.getPixelRatio(), css = renderer.getSize(new THREE.Vector2());
    renderer.setPixelRatio(1); renderer.setSize(W, H, false); dirty = true; showPass();
    const stamp = new Date().toISOString().replace(/[-:]/g, '').replace('T', '-').slice(0, 15);
    renderer.domElement.toBlob((blob) => {
      if (!blob) { toast('The picture could not be saved'); return; }
      const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `house-photo-${stamp}.png`;
      document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 10000);
    }, 'image/png');
    renderer.setPixelRatio(pr); renderer.setSize(css.x, css.y, false); lastW = -1; dirty = true; showPass();
    return stamp;
  }
  function close() {
    if (!active) return;
    active = false; ready = false; token++;
    if (saved) { renderer.toneMapping = saved.tm; renderer.toneMappingExposure = saved.exp; renderer.outputColorSpace = saved.cs; renderer.autoClear = saved.ac; saved = null; }
    renderer.setRenderTarget(null);
    document.body.classList.remove('photo'); shield.hidden = true; panel.hidden = true;
    // A phone has no memory to spare for a BVH and float targets nobody is looking at, so it keeps only the compiled
    // path tracer; a laptop keeps everything so the next photo of the same scene starts at once.
    if (touch && pt) {
      pt.setScene(tinyScene(), pcam); pt._pathTracer.setSize(16, 16); pt._lowResPathTracer.setSize(4, 4);
      pscene = null; sig = 0; if (snap) { snap.dispose(); snap = null; }
    }
    onClose();
  }

  return { open, close, frame, save, warm, start, get size() { return [W, H]; }, redraw() { dirty = true; showPass(); }, get active() { return active; }, get ready() { return ready; }, get started() { return go; },
    get samples() { return pt && ready ? pt.samples : 0; }, get info() { return { builds, tris, skipped, meshes: pscene ? pscene.children.length : 0, panes: panes.length, portals, inside, exposure: renderer.toneMappingExposure, tiles: pt ? pt.tiles.x : 0, size: [W, H] }; },
    get tracer() { return pt; } };
}
