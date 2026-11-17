// Lets Node import the site's ES modules: maps the browser import map ('three', 'three/addons/', 'three-mesh-bvh') to site/vendor.
import { pathToFileURL } from 'node:url';
import path from 'node:path';
const V = path.resolve(path.dirname(new URL(import.meta.url).pathname), '../site/vendor');
const MAP = { 'three': `${V}/three/build/three.module.js`, 'three-mesh-bvh': `${V}/three-mesh-bvh/index.module.js` };
export async function resolve(spec, ctx, next) {
  if (MAP[spec]) return next(pathToFileURL(MAP[spec]).href, ctx);
  if (spec.startsWith('three/addons/')) return next(pathToFileURL(`${V}/three/examples/jsm/${spec.slice(13)}`).href, ctx);
  return next(spec, ctx);
}
