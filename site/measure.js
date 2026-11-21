// Tape measure: pick two points on the model and read the distance between them in feet and inches.
// Each pick snaps to the nearest corner (mesh vertex) within a few pixels of the pointer, searched across every
// pickable mesh near the hit with its BVH, so a wall corner snaps even when the click lands on the next panel over.
// A corner only counts if the camera can see it and it is below the height slice. With no corner close by, the
// exact spot under the pointer is used. Units are metres inside, feet and inches on screen (1/8 in).
import * as THREE from 'three';

const IN = 0.0254;
const SNAP_PX = 14;               // how close, in screen pixels, a corner has to be to win the snap
const DOT_PX = 5;                 // marker radius on screen

// 3.6576 m -> 12' 0". Rounded to the nearest 1/8 in, fractions reduced (4/8 -> 1/2).
export function feetInches(m) {
  let e = Math.round(Math.abs(m) / IN * 8);          // eighths of an inch
  const ft = Math.floor(e / 96); e -= ft * 96;
  const whole = Math.floor(e / 8); let n = e - whole * 8, d = 8;
  while (n && n % 2 === 0) { n /= 2; d /= 2; }
  const inch = `${whole}${n ? ` ${n}/${d}` : ''}"`;
  return ft ? `${ft}' ${inch}` : inch;
}

export function createMeasure({ scene, camera, renderer, pickables, cutY, F, onChange, noSnap = () => false, touch = false }) {
  const Click = touch ? 'Tap' : 'Click';
  const ray = new THREE.Raycaster(); ray.firstHitOnly = false;
  const vis = new THREE.Raycaster(); vis.firstHitOnly = true;
  const group = new THREE.Group(); group.name = 'measure'; group.renderOrder = 50; scene.add(group);
  const dotGeo = new THREE.SphereGeometry(1, 16, 12);
  const mat = (c) => new THREE.MeshBasicMaterial({ color: c, depthTest: false, depthWrite: false, transparent: true, toneMapped: false });
  const pinMat = mat(0xffb000), snapMat = mat(0xffb000), freeMat = mat(0xffffff);
  freeMat.opacity = 0.9;
  const pins = [0, 1].map(() => { const m = new THREE.Mesh(dotGeo, pinMat); m.renderOrder = 52; m.visible = false; group.add(m); return m; });
  const cursor = new THREE.Mesh(dotGeo, snapMat); cursor.renderOrder = 53; cursor.visible = false; group.add(cursor);
  const lineGeo = new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(6), 3));
  const line = new THREE.Line(lineGeo, new THREE.LineBasicMaterial({ color: 0xffb000, depthTest: false, depthWrite: false, transparent: true, toneMapped: false }));
  line.renderOrder = 51; line.frustumCulled = false; line.visible = false; group.add(line);
  // the dashed rubber band from the first pin to the pointer while choosing the second
  const bandGeo = new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(6), 3));
  const band = new THREE.Line(bandGeo, new THREE.LineDashedMaterial({ color: 0xffffff, dashSize: 0.08, gapSize: 0.06, depthTest: false, depthWrite: false, transparent: true, toneMapped: false }));
  band.renderOrder = 51; band.frustumCulled = false; band.visible = false; group.add(band);

  // faint edges of the model that meet at each picked corner (orange) and at the corner under the pointer (white),
  // so turning the view shows exactly which corner was taken (Maxwell, 11/21/2026)
  const edgeMat = (c, o) => new THREE.LineBasicMaterial({ color: c, opacity: o, depthTest: false, depthWrite: false, transparent: true, toneMapped: false });
  const pinEdges = new THREE.LineSegments(new THREE.BufferGeometry(), edgeMat(0xffc94d, 0.7));
  const hoverEdges = new THREE.LineSegments(new THREE.BufferGeometry(), edgeMat(0xffffff, 0.45));
  for (const e of [pinEdges, hoverEdges]) { e.renderOrder = 50; e.frustumCulled = false; e.visible = false; group.add(e); }
  const setSegs = (obj, segs) => {
    const a = new Float32Array(segs.length * 6);
    segs.forEach(([p, q], i) => { a.set(p.toArray(), i * 6); a.set(q.toArray(), i * 6 + 3); });
    obj.geometry.dispose(); obj.geometry = new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(a, 3));
    obj.visible = segs.length > 0;
  };
  const edgeCache = new Map();

  const label = document.getElementById('mLabel'), card = document.getElementById('measure');
  let on = false, pts = [], snappedPins = [], hoverNdc = null, hover = null, dirty = false;

  const pxToWorld = (d) => (2 * d * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2)) / renderer.domElement.clientHeight;
  const toScreen = (p) => { const v = p.clone().project(camera); return [(v.x + 1) / 2 * innerWidth, (1 - v.y) / 2 * innerHeight, v.z]; };

  // the first hit below the slice: the surface the pointer is on
  function surfaceAt(ndc) {
    ray.setFromCamera(ndc, camera); ray.far = 600;
    const top = cutY() + 1e-4;
    for (const h of ray.intersectObjects(pickables, false)) if (h.point.y <= top) return h;
    return null;
  }
  function visible(p) {
    const d = p.distanceTo(camera.position); if (d < 1e-3) return true;
    vis.set(camera.position, p.clone().sub(camera.position).divideScalar(d)); vis.far = d - 0.004;
    const top = cutY() + 1e-4;
    vis.firstHitOnly = false;
    for (const h of vis.intersectObjects(pickables, false)) if (h.point.y <= top) return false;
    return true;
  }
  const _inv = new THREE.Matrix4(), _sph = new THREE.Sphere(), _ls = new THREE.Sphere(), _bs = new THREE.Sphere(), _w = new THREE.Vector3();
  // nearest visible corner to the pointer, or null
  function cornerNear(hit, ndc) {
    const r = pxToWorld(hit.distance) * SNAP_PX * 1.5;
    _sph.set(hit.point, r);
    const px = [(ndc.x + 1) / 2 * innerWidth, (1 - ndc.y) / 2 * innerHeight];
    const top = cutY() + 1e-4, seen = new Map();
    for (const o of pickables) {
      const g = o.geometry; if (!g.boundsTree || !o.layers.test(ray.layers) || noSnap(o)) continue;
      if (!g.boundingSphere) g.computeBoundingSphere();
      _bs.copy(g.boundingSphere).applyMatrix4(o.matrixWorld);
      if (!_bs.intersectsSphere(_sph)) continue;
      _inv.copy(o.matrixWorld).invert();
      _ls.copy(_sph).applyMatrix4(_inv);       // local sphere (radius scaled by the largest axis, which is generous enough)
      const add = (v) => {
        _w.copy(v).applyMatrix4(o.matrixWorld);
        if (_w.y > top || _w.distanceToSquared(hit.point) > r * r) return;
        const k = `${Math.round(_w.x * 2000)},${Math.round(_w.y * 2000)},${Math.round(_w.z * 2000)}`;
        if (seen.has(k)) return;
        const [sx, sy, sz] = toScreen(_w);
        if (sz > 1) return;
        const dpx = Math.hypot(sx - px[0], sy - px[1]);
        if (dpx <= SNAP_PX) seen.set(k, { p: _w.clone(), dpx });
      };
      g.boundsTree.shapecast({
        intersectsBounds: (box) => box.intersectsSphere(_ls),
        intersectsTriangle: (tri) => { add(tri.a); add(tri.b); add(tri.c); return false; },
      });
    }
    const list = [...seen.values()].sort((a, b) => a.dpx - b.dpx);
    for (const c of list.slice(0, 10)) if (visible(c.p)) return c.p;
    return null;
  }
  // The real edges that meet at a corner: every triangle edge from the corner, less the diagonals that only split a
  // flat face (both triangles on it lie in one plane). Faces are compared without their facing, so a face and its
  // back face read as one plane. Edges stop at the height slice.
  function cornerEdges(c) {
    const key = `${Math.round(c.x * 2000)},${Math.round(c.y * 2000)},${Math.round(c.z * 2000)}`;
    if (edgeCache.has(key)) return edgeCache.get(key);
    const EPS = 0.001, top = cutY() + 1e-4, edges = new Map();
    _sph.set(c, EPS);
    const A = new THREE.Vector3(), B = new THREE.Vector3(), C = new THREE.Vector3(), n = new THREE.Vector3();
    for (const o of pickables) {
      const g = o.geometry; if (!g.boundsTree || !o.layers.test(ray.layers) || noSnap(o)) continue;
      if (!g.boundingSphere) g.computeBoundingSphere();
      _bs.copy(g.boundingSphere).applyMatrix4(o.matrixWorld);
      if (!_bs.intersectsSphere(_sph)) continue;
      _inv.copy(o.matrixWorld).invert();
      _ls.copy(_sph).applyMatrix4(_inv);
      g.boundsTree.shapecast({
        intersectsBounds: (box) => box.intersectsSphere(_ls),
        intersectsTriangle: (tri) => {
          A.copy(tri.a).applyMatrix4(o.matrixWorld); B.copy(tri.b).applyMatrix4(o.matrixWorld); C.copy(tri.c).applyMatrix4(o.matrixWorld);
          const vs = [A, B, C], i = vs.findIndex((v) => v.distanceTo(c) < EPS);
          if (i < 0) return false;
          n.subVectors(B, A).cross(C.clone().sub(A)); if (n.lengthSq() < 1e-14) return false;
          n.normalize();
          for (const v of [vs[(i + 1) % 3], vs[(i + 2) % 3]]) {
            const k = `${Math.round(v.x * 2000)},${Math.round(v.y * 2000)},${Math.round(v.z * 2000)}`;
            if (!edges.has(k)) edges.set(k, { end: v.clone(), normals: [] });
            edges.get(k).normals.push(n.clone());
          }
          return false;
        },
      });
    }
    const segs = [];
    for (const { end, normals } of edges.values()) {
      const crease = normals.length === 1 || normals.some((m) => Math.abs(m.dot(normals[0])) < 0.985);
      if (!crease) continue;
      let q = end;
      if (c.y > top) continue;
      if (q.y > top) q = c.clone().lerp(q, (top - c.y) / (q.y - c.y));
      segs.push([c.clone(), q.clone()]);
    }
    if (edgeCache.size > 200) edgeCache.clear();
    edgeCache.set(key, segs);
    return segs;
  }
  function snapAt(ndc) {
    const hit = surfaceAt(ndc);
    if (!hit) return null;
    const c = cornerNear(hit, ndc);
    return c ? { p: c, snapped: true } : { p: hit.point.clone(), snapped: false };
  }

  function parts(a, b) {
    const d = b.clone().sub(a);
    return { total: d.length(), level: Math.hypot(d.x, d.z), rise: Math.abs(d.y), ew: Math.abs(d.x), ns: Math.abs(d.z) };
  }
  function render() {
    for (let i = 0; i < 2; i++) { pins[i].visible = on && !!pts[i]; if (pts[i]) pins[i].position.copy(pts[i]); }
    line.visible = on && pts.length === 2;
    if (line.visible) { lineGeo.attributes.position.setXYZ(0, ...pts[0].toArray()); lineGeo.attributes.position.setXYZ(1, ...pts[1].toArray()); lineGeo.attributes.position.needsUpdate = true; }
    if (!on) { card.hidden = true; label.hidden = true; return; }
    card.hidden = false;
    const live = pts.length === 1 && hover ? hover.p : null;
    const b = pts.length === 2 ? pts[1] : live;
    if (pts.length && b) {
      const m = parts(pts[0], b);
      card.innerHTML = `<div class="mtot">${feetInches(m.total)}</div><dl>`
        + `<dt>Level</dt><dd>${feetInches(m.level)}</dd><dt>Up or down</dt><dd>${feetInches(m.rise)}</dd>`
        + `<dt>East to west</dt><dd>${feetInches(m.ew)}</dd><dt>North to south</dt><dd>${feetInches(m.ns)}</dd></dl>`
        + `<p class="mhint">${pts.length === 2 ? `${Click} again to start a new measurement.${touch ? '' : ' Esc clears.'}` : `${Click} the second point.`}</p>`;
    } else {
      card.innerHTML = `<div class="mtot">Measure</div><p class="mhint">${pts.length ? `${Click} the second point.` : `${Click} a corner to start. Points snap to the nearest corner.`}${touch ? ' Turn it off under More.' : ' Esc clears, M turns it off.'}</p>`;
    }
  }
  function setActive(v) {
    on = !!v; if (!on) { pts = []; snappedPins = []; hover = null; hoverNdc = null; setSegs(pinEdges, []); setSegs(hoverEdges, []); }
    edgeCache.clear();          // the slice may have moved since last time
    group.visible = on; cursor.visible = false; band.visible = false;
    render(); onChange && onChange(on);
  }
  function pick(ndc) {
    const s = snapAt(ndc);
    if (!s) return false;
    edgeCache.clear();          // the slice may have moved
    if (pts.length >= 2) { pts = []; snappedPins = []; }
    pts.push(s.p); snappedPins.push(s.snapped);
    setSegs(pinEdges, pts.flatMap((p, i) => (snappedPins[i] ? cornerEdges(p) : [])));
    hover = null; render();
    return true;
  }
  function clear() { if (!pts.length) return false; pts = []; snappedPins = []; setSegs(pinEdges, []); render(); return true; }
  function hoverAt(ndc) { if (on) { hoverNdc = ndc ? ndc.clone() : null; dirty = true; } }
  // once a frame: run the pending hover snap, keep markers a fixed size on screen, place the distance label
  function update(lockedNdc) {
    if (!on) return;
    if (lockedNdc) { hoverNdc = lockedNdc; dirty = true; }
    if (dirty) {
      dirty = false;
      const was = hover && hover.snapped ? hover.p : null;
      hover = hoverNdc ? snapAt(hoverNdc) : null;
      const now = hover && hover.snapped && pts.length < 2 ? hover.p : null;
      if (!now) { if (hoverEdges.visible) setSegs(hoverEdges, []); } else if (!was || !was.equals(now) || !hoverEdges.visible) setSegs(hoverEdges, cornerEdges(now));
      render();
    }
    const showCursor = !!hover && pts.length < 2;
    if (!showCursor && hoverEdges.visible) setSegs(hoverEdges, []);
    cursor.visible = showCursor;
    if (showCursor) { cursor.position.copy(hover.p); cursor.material = hover.snapped ? snapMat : freeMat; }
    band.visible = showCursor && pts.length === 1;
    if (band.visible) {
      bandGeo.attributes.position.setXYZ(0, ...pts[0].toArray()); bandGeo.attributes.position.setXYZ(1, ...hover.p.toArray());
      bandGeo.attributes.position.needsUpdate = true; band.computeLineDistances();
    }
    for (const m of [...pins, cursor]) if (m.visible) m.scale.setScalar(pxToWorld(m.position.distanceTo(camera.position)) * (m === cursor && !hover.snapped ? DOT_PX * 0.7 : DOT_PX));
    const b = pts.length === 2 ? pts[1] : (pts.length === 1 && hover ? hover.p : null);
    if (pts.length && b) {
      const mid = pts[0].clone().add(b).multiplyScalar(0.5), [x, y, z] = toScreen(mid);
      label.hidden = z > 1 || x < -50 || y < -50 || x > innerWidth + 50 || y > innerHeight + 50;
      if (!label.hidden) { label.textContent = feetInches(pts[0].distanceTo(b)); label.style.left = `${x}px`; label.style.top = `${y}px`; }
    } else label.hidden = true;
  }
  // plan feet of the picked points, for tests and the console
  const picked = () => pts.map((p) => [p.x / F, p.z / F, p.y / F]);
  group.visible = false;
  return { cornerEdges, get on() { return on; }, setActive, toggle: () => setActive(!on), pick, clear, hoverAt, update, picked, snapAt };
}
