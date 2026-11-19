// Ground heights for things set on the site: node tools/ground_grid.mjs  (from the repo root)
// Loads the baked site.glb terrain the walkthrough draws and drops a ray at every point of a grid, so make_equipment.py
// can stand planted trees, the transformer pad and the gravel drive on the very ground you see (not on the raw DEM,
// which the graded pad and the web mesh differ from by a few inches). Writes model/data/terrain/web_ground.json:
// heights in feet above the slab top, on a 2 ft grid in plan feet (x east, y south of the slab's NW corner).
import { register } from 'node:module';
register('./three_hooks.mjs', import.meta.url);
const fs = await import('node:fs');
const THREE = await import('three');
const el = () => ({ style: {}, getContext: () => new Proxy({}, { get: () => () => ({ addColorStop() {} }) }), addEventListener() {}, removeEventListener() {}, setAttribute() {} });
globalThis.document = { createElement: el, createElementNS: el };
const { GLTFLoader } = await import('three/addons/loaders/GLTFLoader.js');
const { MeshoptDecoder } = await import('three/addons/libs/meshopt_decoder.module.js');
const { computeBoundsTree, acceleratedRaycast } = await import('three-mesh-bvh');
THREE.BufferGeometry.prototype.computeBoundsTree = computeBoundsTree;
THREE.Mesh.prototype.raycast = acceleratedRaycast;

const F = 0.3048, STEP = 2, X0 = -60, X1 = 260, Y0 = -420, Y1 = 140;
const loader = new GLTFLoader(); loader.setMeshoptDecoder(MeshoptDecoder);
loader.register(() => ({ name: 'no_textures', loadTexture: () => Promise.resolve(null) }));
const buf = fs.readFileSync('site/models/site.glb');
const gl = await loader.parseAsync(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength), '');
gl.scene.updateMatrixWorld(true);
const terrain = gl.scene.getObjectByName('Terrain');
terrain.geometry.computeBoundsTree();
const ray = new THREE.Raycaster(); ray.firstHitOnly = true;
const down = new THREE.Vector3(0, -1, 0), o = new THREE.Vector3();
const nx = (X1 - X0) / STEP + 1, ny = (Y1 - Y0) / STEP + 1, z = [];
for (let j = 0; j < ny; j++) {
  const row = [];
  for (let i = 0; i < nx; i++) {
    o.set((X0 + i * STEP) * F, 100, (Y0 + j * STEP) * F);
    ray.set(o, down);
    const h = ray.intersectObject(terrain, false)[0];
    row.push(h ? Math.round(h.point.y / F * 100) / 100 : null);
  }
  z.push(row);
}
fs.writeFileSync('model/data/terrain/web_ground.json', JSON.stringify({ note: 'ground height (ft above slab top) of the Terrain mesh in site/models/site.glb, sampled by tools/ground_grid.mjs', x0: X0, y0: Y0, step: STEP, nx, ny, z }));
console.log('wrote', nx, 'x', ny, 'heights; centre', z[(0 - Y0) / STEP][(0 - X0) / STEP]);
