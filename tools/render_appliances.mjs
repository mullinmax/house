// Renders every appliance and piece of equipment alone, front and three quarter views, into one PNG each.
//   node tools/render_appliances.mjs out_dir [id ...]
// Needs Playwright with Chromium. Serves the repo root itself.
import { createRequire } from 'node:module';
const { chromium } = createRequire(import.meta.url)('playwright');
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const out = path.resolve(process.argv[2] || 'appliance_renders');
const only = process.argv.slice(3);
fs.mkdirSync(out, { recursive: true });
const types = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.jpg': 'image/jpeg', '.png': 'image/png' };
const server = http.createServer((req, res) => {
  const f = path.join(root, decodeURIComponent(req.url.split('?')[0]));
  if (!f.startsWith(root) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'content-type': types[path.extname(f)] || 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
}).listen(0);
const port = server.address().port;
const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const VIEWS = { default: [[0, 0], [32, 14]], cooktop: [[0, 89], [25, 40]], disposal: [[0, 5], [35, 15]], heat_pump: [[0, 8], [140, 18]], erv: [[0, 20], [40, 30]] };
const page = await browser.newPage({ viewport: { width: 700, height: 700 }, deviceScaleFactor: 1 });
page.on('pageerror', (e) => console.error('page error:', e.message));
page.on('console', (m) => { if (m.type() === 'error') console.error('console:', m.text()); });
await page.goto(`http://127.0.0.1:${port}/tools/appliance_preview.html`);
await page.waitForFunction('window.__ready', null, { timeout: 60000 });
const ids = only.length ? only : await page.evaluate('window.__preview.ids');
for (const id of ids) {
  if (!(await page.evaluate((i) => window.__preview.show(i), id))) { console.error('no item', id); continue; }
  const shots = [];
  for (const [az, el] of VIEWS[id] || VIEWS.default) shots.push(await page.evaluate(([a, e]) => window.__preview.view(a, e), [az, el]));
  const st = await page.evaluate('window.__preview.stats()');
  // stitch the two views side by side in the page
  const png = await page.evaluate(async (urls) => {
    const imgs = await Promise.all(urls.map((u) => new Promise((r) => { const i = new Image(); i.onload = () => r(i); i.src = u; })));
    const c = document.createElement('canvas'); c.width = imgs.reduce((s, i) => s + i.width, 0); c.height = imgs[0].height;
    let x = 0; const g = c.getContext('2d'); for (const i of imgs) { g.drawImage(i, x, 0); x += i.width; }
    return c.toDataURL('image/png');
  }, shots);
  fs.writeFileSync(path.join(out, id + '.png'), Buffer.from(png.split(',')[1], 'base64'));
  console.log(id, `${st.meshes} meshes, ${st.calls} draw calls, ${Math.round(st.tris)} triangles`);
}
await browser.close(); server.close();
