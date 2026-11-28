// Coplanar face audit: node tools/coplanar_audit.mjs  (from the repo root)
// Builds the house (site/models/house.json) and the equipment layer (site/models/equipment.json) with the same code the
// walkthrough runs, loads the baked furniture and site .glb parts it still draws, then looks for triangles of different materials that lie in the same plane, face the same way and
// overlap. Those pairs flicker (z-fighting). Exits 1 if any are found, so a GitHub Action can fail on them.
//   --tol <mm>   planes closer than this count as the same (default 0.5 mm)
//   --min <cm2>  ignore overlaps smaller than this (default 1 cm2)
//   --json       print the findings as JSON
//   --no-glb     leave out the baked furniture and site .glb parts
//   --all        also list pairs buried inside other solids (never seen)
import { register } from 'node:module';
register('./three_hooks.mjs', import.meta.url);
const fs = await import('node:fs');
const THREE = await import('three');
// just enough of a DOM for the slab canvas and texture loads (images never arrive, geometry is all that matters here)
const el = () => ({ style: {}, getContext: () => new Proxy({}, { get: () => () => ({ addColorStop() {} }) }), addEventListener() {}, removeEventListener() {}, setAttribute() {} });
globalThis.document = { createElement: el, createElementNS: el };
const { buildHouse } = await import('../site/house.js');
const { buildEquipment, cullBaked } = await import('../site/equipment.js');
const { MeshBVH } = await import('three-mesh-bvh');
// three r187 made Ray.intersectTriangle watertight. The hidden-or-not vote below samples points that often sit exactly on
// another solid's face or edge, where the two methods round differently, so the audit keeps the r160 test it was tuned
// with (the geometry and what the walkthrough draws are the same either way).
{
  const _edge1 = new THREE.Vector3(), _edge2 = new THREE.Vector3(), _normal$1 = new THREE.Vector3(), _diff = new THREE.Vector3();
  THREE.Ray.prototype.intersectTriangle = function intersectTriangle( a, b, c, backfaceCulling, target ) {

		// Compute the offset origin, edges, and normal.

		// from https://github.com/pmjoniak/GeometricTools/blob/master/GTEngine/Include/Mathematics/GteIntrRay3Triangle3.h

		_edge1.subVectors( b, a );
		_edge2.subVectors( c, a );
		_normal$1.crossVectors( _edge1, _edge2 );

		// Solve Q + t*D = b1*E1 + b2*E2 (Q = kDiff, D = ray direction,
		// E1 = kEdge1, E2 = kEdge2, N = Cross(E1,E2)) by
		//   |Dot(D,N)|*b1 = sign(Dot(D,N))*Dot(D,Cross(Q,E2))
		//   |Dot(D,N)|*b2 = sign(Dot(D,N))*Dot(D,Cross(E1,Q))
		//   |Dot(D,N)|*t = -sign(Dot(D,N))*Dot(Q,N)
		let DdN = this.direction.dot( _normal$1 );
		let sign;

		if ( DdN > 0 ) {

			if ( backfaceCulling ) return null;
			sign = 1;

		} else if ( DdN < 0 ) {

			sign = - 1;
			DdN = - DdN;

		} else {

			return null;

		}

		_diff.subVectors( this.origin, a );
		const DdQxE2 = sign * this.direction.dot( _edge2.crossVectors( _diff, _edge2 ) );

		// b1 < 0, no intersection
		if ( DdQxE2 < 0 ) {

			return null;

		}

		const DdE1xQ = sign * this.direction.dot( _edge1.cross( _diff ) );

		// b2 < 0, no intersection
		if ( DdE1xQ < 0 ) {

			return null;

		}

		// b1+b2 > 1, no intersection
		if ( DdQxE2 + DdE1xQ > DdN ) {

			return null;

		}

		// Line intersects triangle, check if ray does.
		const QdN = - sign * _diff.dot( _normal$1 );

		// t < 0, no intersection
		if ( QdN < 0 ) {

			return null;

		}

		// Ray intersects triangle.
		return this.at( QdN / DdN, target );

	}
}
const { GLTFLoader } = await import('three/addons/loaders/GLTFLoader.js');
const { MeshoptDecoder } = await import('three/addons/libs/meshopt_decoder.module.js');

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? Number(process.argv[i + 1]) : d; };
const TOL = arg('--tol', 0.5) / 1000, MIN = arg('--min', 1) / 1e4;
const hd = JSON.parse(fs.readFileSync('site/models/house.json'));
const eq = JSON.parse(fs.readFileSync('site/models/equipment.json'));
const house = buildHouse(hd, { skip: new Set((eq.items || []).map((it) => it.id)) });
const equip = buildEquipment(eq);
// as app.js addEquipment() does: the generated house has its own deck and loft floor, so the truss overlays go
const overlays = []; equip.root.traverse((o) => { if (o.userData.deckOverlay) overlays.push(o); });
for (const o of overlays) o.removeFromParent();

// The baked .glb parts still drawn next to the generated house: furniture and the site (trees are left out). Textures
// are skipped, and house.json's edits are applied the way app.js applyHouseEdits() and prepare() apply them.
const F = 0.3048;
const loader = new GLTFLoader(); loader.setMeshoptDecoder(MeshoptDecoder);
loader.register(() => ({ name: 'no_textures', loadTexture: () => Promise.resolve(null) }));
const man = JSON.parse(fs.readFileSync('site/models/manifest.json'));
const baked = [];
for (const part of man.parts || []) {
  const name = part.name || part.file.replace(/\.glb$/, '');
  if (!/^(furniture|site)/i.test(name) || process.argv.includes('--no-glb')) continue;
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

// every triangle in world metres, tagged with its material and the record it came from
const tris = [];
const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
function collect(root, who) {
  root.updateMatrixWorld(true);
  root.traverse((m) => {
    if (!m.isMesh || m.isInstancedMesh || !m.geometry) return;
    const g = m.geometry, P = g.attributes.position, I = g.index, n = I ? I.count / 3 : P.count / 3;
    const mats = Array.isArray(m.material) ? m.material : [m.material];
    const flip = m.matrixWorld.determinant() < 0;            // mirrored: three.js turns the winding round, so do the same
    for (let t = 0; t < n; t++) {
      const k = (j) => (I ? I.getX(t * 3 + j) : t * 3 + j);
      a.fromBufferAttribute(P, k(0)).applyMatrix4(m.matrixWorld); b.fromBufferAttribute(P, k(1)).applyMatrix4(m.matrixWorld); c.fromBufferAttribute(P, k(2)).applyMatrix4(m.matrixWorld);
      let mat = mats[0];
      if (mats.length > 1 && g.groups.length) { const gr = g.groups.find((q) => q.start <= t * 3 && t * 3 < q.start + q.count); if (gr) mat = mats[gr.materialIndex]; }
      tris.push({ p: flip ? [a.clone(), c.clone(), b.clone()] : [a.clone(), b.clone(), c.clone()], mat: mat ? mat.name || mat.uuid : '?', who: who(m, t), transparent: !!(mat && mat.transparent) });
    }
  });
}
collect(house.root, (m, t) => {
  const u = m.userData; if (u.equipId) return u.equipId;
  const st = u.ranges; let lo = 0, hi = st.length - 1;
  while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (st[mid] <= t) lo = mid; else hi = mid - 1; }
  return house.recs[u.rangeRecs[lo]].id;
});
collect(equip.root, (m) => m.userData.equipId || m.name || 'equipment');
for (const r of baked) collect(r, (m) => `${r.name}.glb ${m.name}${m.parent && m.parent !== r ? ` in ${m.parent.name}` : ''}`);

// bucket by plane: normal rounded to 0.001 and offset in TOL steps (neighbouring steps are checked too)
const n = new THREE.Vector3(), e1 = new THREE.Vector3(), e2 = new THREE.Vector3();
const buckets = new Map();
for (const t of tris) {
  e1.subVectors(t.p[1], t.p[0]); e2.subVectors(t.p[2], t.p[0]); n.crossVectors(e1, e2);
  const L = n.length(); if (L < 1e-10) continue;
  n.divideScalar(L); t.area = L / 2; t.n = n.clone(); t.d = n.dot(t.p[0]);
  if (n.y < -0.999 && Math.abs(t.p[0].y) < 0.0015) continue;   // bottoms resting on the slab or the ground are never seen
  t.key = [Math.round(n.x * 1000), Math.round(n.y * 1000), Math.round(n.z * 1000)].join(',');
  const s = Math.round(t.d / TOL);
  t.s = s; const k = `${t.key}|${s}`;
  (buckets.get(k) || buckets.set(k, []).get(k)).push(t);
}
// 2D overlap area of two triangles in their shared plane (convex clip)
function lift(t, ax, u, v) {           // point on t's plane whose projection is (u, v)
  const { n: N, d } = t;
  if (ax === 0) return new THREE.Vector3((d - N.y * u - N.z * v) / N.x, u, v);
  if (ax === 1) return new THREE.Vector3(u, (d - N.x * u - N.z * v) / N.y, v);
  return new THREE.Vector3(u, v, (d - N.x * u - N.y * v) / N.z);
}
function proj(t, ax) { return t.p.map((p) => (ax === 0 ? [p.y, p.z] : ax === 1 ? [p.x, p.z] : [p.x, p.y])); }
function area2(poly) { let s = 0; for (let i = 0; i < poly.length; i++) { const [x0, y0] = poly[i], [x1, y1] = poly[(i + 1) % poly.length]; s += x0 * y1 - x1 * y0; } return s / 2; }
function clip(subj, clipP) {
  if (area2(clipP) < 0) clipP = clipP.slice().reverse();
  let out = subj;
  for (let i = 0; i < clipP.length && out.length; i++) {
    const [ax, ay] = clipP[i], [bx, by] = clipP[(i + 1) % clipP.length];
    const side = ([x, y]) => (bx - ax) * (y - ay) - (by - ay) * (x - ax);
    const inp = out; out = [];
    for (let j = 0; j < inp.length; j++) {
      const P = inp[j], Q = inp[(j + 1) % inp.length], sp = side(P), sq = side(Q);
      if (sp >= 0) out.push(P);
      if ((sp >= 0) !== (sq >= 0)) { const r = sp / (sp - sq); out.push([P[0] + (Q[0] - P[0]) * r, P[1] + (Q[1] - P[1]) * r]); }
    }
  }
  return out.length >= 3 ? out : null;
}
const pairs = new Map();
for (const [k, list] of buckets) {
  const [key, s] = k.split('|');
  const near = [...list, ...(buckets.get(`${key}|${+s + 1}`) || [])];
  for (let i = 0; i < list.length; i++) {
    const A = list[i];
    for (let j = i + 1; j < near.length; j++) {
      const B = near[j];
      if (A.mat === B.mat || Math.abs(A.d - B.d) > TOL) continue;
      const ax = Math.abs(A.n.x) > Math.abs(A.n.y) ? (Math.abs(A.n.x) > Math.abs(A.n.z) ? 0 : 2) : (Math.abs(A.n.y) > Math.abs(A.n.z) ? 1 : 2);
      const pa = proj(A, ax), pb = proj(B, ax);
      // quick bounds reject
      if (Math.max(...pa.map((q) => q[0])) <= Math.min(...pb.map((q) => q[0])) || Math.max(...pb.map((q) => q[0])) <= Math.min(...pa.map((q) => q[0]))) continue;
      if (Math.max(...pa.map((q) => q[1])) <= Math.min(...pb.map((q) => q[1])) || Math.max(...pb.map((q) => q[1])) <= Math.min(...pa.map((q) => q[1]))) continue;
      const poly = clip(pa, pb); if (!poly) continue;
      const ov = Math.abs(area2(poly)); if (ov <= 1e-8) continue;
      const [x, y] = [A, B].sort((u, v) => (u.who + u.mat < v.who + v.mat ? -1 : 1));
      const pk = `${x.who}|${x.mat}|${y.who}|${y.mat}`;
      const r = pairs.get(pk) || pairs.set(pk, { a: x.who, am: x.mat, b: y.who, bm: y.mat, area: 0, gap: 0, n: A.n, samples: [] }).get(pk);
      r.area += ov; r.gap = Math.max(r.gap, Math.abs(A.d - B.d));
      // sample points over the overlap (centre and corners pulled 25% inward), lifted back into 3D on A's plane
      const cx = poly.reduce((u, q) => u + q[0], 0) / poly.length, cy = poly.reduce((u, q) => u + q[1], 0) / poly.length;
      for (const [u, v] of [[cx, cy], ...poly.map((q) => [cx + (q[0] - cx) * 0.75, cy + (q[1] - cy) * 0.75])]) r.samples.push(lift(A, ax, u, v));
    }
  }
}
// Hidden or not: a sample counts as seen when a point 3 mm in front of it is not inside some other solid. Every shape here
// is closed with outward faces, so the winding number along a ray (exits minus entries) tells inside from outside even
// where solids overlap. Three slightly skewed rays vote, so a ray grazing along an edge cannot decide it alone.
const merged = new THREE.BufferGeometry();
const pos = new Float32Array(tris.length * 9);
tris.forEach((t, i) => t.p.forEach((p, j) => pos.set([p.x, p.y, p.z], i * 9 + j * 3)));
merged.setAttribute('position', new THREE.BufferAttribute(pos, 3));
const bvh = new MeshBVH(merged, { maxDepth: 64, verbose: false });
const ray = new THREE.Ray(), DIRS = [[1, 0.0131, 0.0071], [-0.0093, 1, 0.0117], [0.0059, -0.0107, -1]].map((d) => new THREE.Vector3(...d).normalize());
function winding(p, d) {
  ray.set(p, d);
  let w = 0;
  for (const h of bvh.raycast(ray, THREE.DoubleSide)) {
    const t = tris[merged.index.getX(h.faceIndex * 3) / 3];      // the BVH reorders faces through its index
    if (t.n) w += Math.sign(t.n.dot(d));
  }
  return w;
}
const inside = (p) => DIRS.filter((d) => winding(p, d) > 0).length >= 2;
const q = new THREE.Vector3();
for (const r of pairs.values()) {
  r.seen = r.samples.filter((p) => !inside(q.copy(p).addScaledVector(r.n, 0.003)));
  r.at = (r.seen[0] || r.samples[0]);
}
const ALL = process.argv.includes('--all');
// tools/coplanar_allow.txt: pairs accepted on purpose, one regular expression per line, tested against "a (mat) vs b (mat)"
const allow = (fs.existsSync('tools/coplanar_allow.txt') ? fs.readFileSync('tools/coplanar_allow.txt', 'utf8') : '').split('\n')
  .map((l) => l.trim()).filter((l) => l && !l.startsWith('#')).map((l) => new RegExp(l));
const allowed = (r) => allow.some((re) => re.test(`${r.a} (${r.am}) vs ${r.b} (${r.bm})`));
const found = [...pairs.values()].filter((r) => r.area >= MIN && (ALL || (r.seen.length && !allowed(r)))).sort((u, v) => v.area - u.area)
  
  .map(({ samples, seen, n, ...r }) => ({ ...r, normal: [n.x, n.z, n.y].map((v) => +v.toFixed(3)), area_cm2: Math.round(r.area * 1e4), at_plan_ft: [r.at.x / F, r.at.z / F, r.at.y / F].map((v) => +v.toFixed(2)) }));
if (process.argv.includes('--json')) console.log(JSON.stringify(found, null, 1));
else {
  for (const r of found) console.log(`${String(r.area_cm2).padStart(6)} cm2  ${r.a} (${r.am})  vs  ${r.b} (${r.bm})  near x ${r.at_plan_ft[0]} y ${r.at_plan_ft[1]} z ${r.at_plan_ft[2]}`);
  console.log(`${tris.length} triangles checked, ${found.length} flickering pairs (planes within ${TOL * 1000} mm, overlap at least ${MIN * 1e4} cm2)`);
}
process.exit(found.length ? 1 : 0);
