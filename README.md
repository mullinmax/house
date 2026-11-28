# House walkthrough

An interactive, walkable 3D model of the house, built in the browser from the house plans in `model/config.toml` and hosted with GitHub Pages.

Open the site, then:

- **Orbit mode** (the default): drag to rotate, scroll to zoom, W A S D (or the arrow keys) to slide the orbit centre around the site. Click a door to open it.
- **Walk mode:** click the view, then use W A S D to move and the mouse to look. Hold Shift to go faster, Space to jump, C (or the Crouch button) to crouch. Esc frees the mouse. The eye is at 5 ft 7 in, for a 5 ft 10 in person, and you duck on your own under low roof in the attic. The ship's ladder climbs straight onto the loft.
- **N** toggles no clip: fly through walls in the direction you look, Space up, C down.
- **E** opens and closes whatever you're looking at: doors, the barn doors, the bi-parting slider, the garage doors and drawers.
- **Click or E on an appliance, a piece of equipment, a duct, a piece of furniture, or any wall, window, door, cabinet or trim piece** to read what it is: model, price, size, specs, and notes on where the design is still open.
- **Controls** (or H) opens a page that lists every key and touch control.
- **Go to a room** opens a plan of the house. Click a room to walk into it or to look down on it from above. **Find equipment** opens the same plan with every appliance and piece of equipment as a dot, plus a list by category.
- **Height slice:** a slider cuts the house at any height. It catches at detents just under each level's ceiling (main floor, floor trusses, loft and attic), and lifts the roof off while it is cutting.
- **Layers**, each with an icon: roof, walls, furniture, trees, distant trees, appliances, mechanical, ducts, duct x-ray, floor trusses and buried lines. Walls off fades the house so the systems read. Duct x-ray colours the ducts (blue supply, red return, green fresh air) and shows them through everything.
- **Day and Night:** at night the room lights come on. The porch and exterior lights stay on, and the nearest six interior lights fade in as you move.
- **Share this view** (in the menu's View section, or More on a phone) copies a link that opens exactly what you see: orbit, walk or no clip, where the camera is and where it looks, the room, day or night, the height slice, crouching, any layers you changed and an open info card. On a phone it opens the share sheet. The address bar keeps up with the view as you move, so a refresh brings you back to the same view. **Reset view**, next to Share, goes back to the opening view (orbit from the southwest, day, whole house, default layers).
- **Photo** (in the menu's View section, or P): a lifelike still of the view you are looking at. Light is path traced: daylight comes in through the windows and bounces around the room, glass reflects, shadows soften with distance, and at night the fixtures light the rooms. The walkthrough pauses while samples build up on the screen. Brightness adjusts the exposure, Save PNG keeps the picture and Esc goes back. It honours the layers and the height slice. Fog, the tape measure and the duct x-ray's see-through effect are not in the photo.
- **Slow device?** Add `?lite` to the address to start without shadows or the distant trees.
- **Phones:** the left stick moves, drag anywhere else to look, tap a door to open it.

## Layout

- `site/index.html`, `site/app.js`: the viewer (three.js 0.160, vendored in `site/vendor`, MIT license).
- `site/photo.js`: Photo mode (three-gpu-pathtracer 0.0.28, vendored in `site/vendor`, MIT license). It builds the path tracer's scene from exactly the meshes the normal view draws and cuts the height slice into the triangles.
- `model/config.toml`: the house plans as numbers (walls, rooms, windows, doors, roof, kitchen, loft, garage, porch, floor trusses). Everything below is built from it.
- `site/models/house.json`, `site/house.js`: the house itself (see "The house" below).
- `site/models/equipment.json`, `site/equipment.js`: appliances, equipment and ducts (see below).
- `site/models/*.glb`: terrain (`site.glb`), trees and furniture and bath fixtures, listed in `manifest.json`. They were last exported from the old Blender model (laptop export v21, 11/13/2026), which was removed from the repo on 11/24/2026 and lives on in git history. The viewer and `house.json` `meta` edit them in place (nodes dropped, culled or moved) rather than re-exporting.
- `.github/workflows/pages.yml`: publishes `site/` to GitHub Pages on every push to `main`. It must be the only Pages workflow: a second one (such as GitHub's starter `static.yml`, which uploads the whole repo) races it, and whichever finishes last wins. When the starter won, https://mullinmax.github.io/house/ showed a 404 and the viewer was only at `/house/site/`.

- `.github/workflows/coplanar.yml`: on every pull request, `node tools/coplanar_audit.mjs` builds the house and equipment with the viewer's own code, loads the furniture and site `.glb` parts, and fails if two surfaces of different materials lie flush, face the same way and can be seen (they flicker). The log says which records and where, in plan feet. `model/make_house.py` already nudges most flush boxes 1/32 in apart when it builds; fix anything left in the geometry, or list a pair you accept in `tools/coplanar_allow.txt` with the reason.

**Site address:** https://mullinmax.github.io/house/ (Settings, Pages, Source must be "GitHub Actions").

## Performance notes

- On load the viewer bakes static meshes that share a material into one mesh per part, toggle group and 20 m grid cell, cutting about 2000 draw calls to about 550. Operable parts and light fixtures stay separate.
- After that, drawing is split from picking: every mesh (house, equipment, ducts, doors and drawers) stays in the scene for clicks, collisions, measuring and the layer switches but is not drawn itself. One merged mesh per material is drawn instead, its index repacked from the pieces whose layer is on, and a moving door or drawer rewrites its own vertices in it. Spinning fan blades and see-through glass stay separate. Overhead view: about 1,800 draw calls down to about 220; kitchen 600 to 150.
- Shadows are redrawn only when the viewer moves 4 m, a door moves, or a toggle changes.
- The render scale adapts to the frame rate: it starts at the screen's pixel ratio (capped at 1.5), drops in steps to 0.6 when frames take longer than 24 ms, and climbs back when there is headroom. Antialiasing is off on high-DPI screens.
- No logarithmic depth buffer: it disables the GPU's early depth test, which made every hidden pixel cost a full shade.
- The shell, interior and site load first so you can start walking. Furniture and trees stream in behind them and are prepared one part at a time when the browser is idle.
- At night the 6 room lights nearest the viewer are lit, from `manifest.lights` (Blender metres) or one per room as a fallback. A fixed count avoids shader rebuilds while walking.
- KTX2 (GPU compressed) textures would cut video memory further, but need a gltfpack build with BasisU.

## Model conventions the viewer reads

- Units are metres with Y up. Plan feet (x east, y south from the NW slab corner) map to `(x * 0.3048, height, y * 0.3048)`.
- **Doors and drawers:** any node with glTF extras `operable` becomes interactive.
  - `"swing"` takes `open_angle` in degrees and `axis` ("z" means the vertical hinge).
  - `"slide"` and `"drawer"` take `slide`, a world move in Blender metres `[dx, dy, dz]`.
  - `"rollup"` lifts the door by its own height.
  - Pivots sit at the hinge or track.
- **Spawn points:** `Spawn_<Room>` empty nodes, at eye height, are spawn points. An optional `look` extra gives the Blender world point to face.
- **Layers:** nodes named `Roof` or matching roof, fascia, gutter and ceiling names follow the Roof layer. Nodes named `Utilities` or matching geothermal or septic names follow "Buried lines". Parts named `furniture*` follow Furniture.

## The house

`model/make_house.py` (plain Python, no Blender) reads `config.toml` and writes `site/models/house.json`; `site/house.js` builds it in the browser.

```
python model/make_house.py            # add --check to list faces that still overlap
```

- It is a port of the house parts of the Blender scripts: slab with the stained finish and diamond saw cuts, exterior walls with board and batten, clerestory, interior walls, headers, windows and doors with trim, roof, fascia, gutters and soffits, vaulted and flat ceilings, the attic deck, the loft with its rail and ladder, kitchen cabinets and island, baseboards and casings, garage, porch and greenhouse.
- Every piece is a record with an id (`wall.int.3`, `window.w60-60_bed_1`, `cabinet.west.2`, `door.d30-80_entry`, ...), a name, a room, a layer and an `info` block, the same pattern as the equipment. Clicking any of them shows its card.
- Shapes are boxes, eight point solids, polygons, cylinders and wall panels with holes. Openings in walls are holes in the panel, so no boolean cuts are needed. Static shapes are merged into one mesh per material and layer, and the viewer maps a hit back to its record.
- Doors, drawers, cabinet doors, the barn doors, the bi-parting slider and the garage doors are operable pivots, in the same format the Blender export used (below).
- Where `equipment.json` has a real model of an appliance, the placeholder box for it is skipped.
- Coplanar faces are nudged a hair apart when the file is written so nothing flickers.
- Furniture the browser builds (the queen beds and nightstands in bedrooms 2 and 3, the Uplift L desk and office chair in the Study) is listed in `[furnishings]` with `web = true`. Its records go on the furniture layer, and `house.json` `meta` tells the viewer how to edit the Blender furniture and site GLBs to match: `replace_nodes` (named nodes to drop), `cull` (boxes of triangles to drop, by material and part), `move_nodes` (nodes to shift and turn) and `lights_moved`.
- `[plan_edits]` in `config.toml` moves an interior wall off where A-11 draws it (`wall_shift`, by a point inside the wall), for decisions made after the plans. A `[furnishings]` item with `removed = true` drops its baked piece (and a lamp's night light); `cull_old` takes out pieces merged into shared meshes.
- `meta` also carries `rooms` and `outline` for the room picker plan, `climbs` (the ship's ladder ramp) and `eye_ft`.

## Appliances, equipment and ducts

`site/equipment.js` builds them in the browser from `site/models/equipment.json`, which `model/make_equipment.py` writes (plain Python, no Blender):

```
python model/make_equipment.py
```

- Every thing is a record with an id, a name, a `system` (`hvac.supply`, `geothermal.loop`, `plumbing.dhw`, ...), a room, a layer, its geometry (a builder and true size, or a duct or pipe path) and an `info` block for the card. Positions are plan feet, sizes are inches.
- The appliance and equipment builders in `site/equipment.js` follow the makers' product photos at the spec sheet sizes: door and handle style, control panels, finish and visible details. Screens, logos, the cooktop's zone markings and the brushed grain are small canvas drawings made in the browser, so no image files are downloaded. Each item's pieces are merged into one mesh per material, so a detailed appliance costs a handful of draw calls.
- To check a builder without loading the house, `node tools/render_appliances.mjs out_dir [id ...]` renders each item alone, front and three quarter views, using `tools/appliance_preview.html` (needs Playwright with Chromium). The page also opens by hand: serve the repo root and visit `/tools/appliance_preview.html?id=fridge`.
- `cull` boxes and `replaces_nodes` remove the generic appliance boxes from the baked furniture parts so the real ones take their place.
- The duct layout starts from Andy Roehl's M-10 (07/30/2026) and changes two things at Maxwell's direction: the supply trunk runs along the north wall of the attic, and every bedroom gets a ducted return through open web floor trusses in place of transfer grilles. The trusses are 11-7/8 in deep (set in `[floor_trusses]` in `config.toml`, which also raises the attic deck and the loft floor). Truss spacing and direction, duct sizes off the trunk and the heat pump orientation are marked ASSUMED in the data and on the cards.
- The floor trusses sit on one 24 in grid across the house (`grid_x0` in `[floor_trusses]`), so the bays line up from room to room. A duct in the truss space either runs north to south inside a bay, at any size that fits, or crosses the trusses through the web openings as round duct of 6 in or less, unless that one duct carries a `cross_ok` size (the builder confirmed on 11/18/2026 that 6 in fits the installed trusses and 7 in only might; the limit is `max_round_duct_in` in `[floor_trusses]`). A run that needs more air is split into two 6 in runs. `python3 tools/truss_clash.py` checks every duct against that rule and runs with the coplanar check on each pull request.
- `python3 tools/duct_balance.py` prints a Manual D style estimate of how well the ducts balance: each register's share of the air with every damper open, how much of each bedroom's air comes back through its own return, and the total static pressure against the blower. It reads the `cfm`, `parent`, `el`, `k` and `n` fields that `model/make_equipment.py` puts on each duct. It is an estimate with typical fitting and filter allowances, not a design, and it does not gate pull requests. `--set s_living1.size=7` tries a size without editing the model.
- `python3 tools/pipe_clash.py` checks that no pipe passes through a wall, another pipe, a duct or a piece of equipment it does not connect to, that ducts above the ceiling do not pass through each other, and that the mechanical equipment stays inside its room. It runs on each pull request too. The utility room's real wall faces (west 0.497, north 22.866, south 28.241, east 11.664) are at the top of the utility section in `model/make_equipment.py`; the room list rounds the south one.
- `node tools/clash_audit.mjs` is a local review list, not a pull request check: it builds the house and equipment with the viewer's own code and lists every pair of different objects that pass more than 3 mm into each other (faces that only touch pass). The model draws walls, flat ceilings and the truss space as solid blocks and laps drywall at corners on purpose, so `tools/clash_allow.txt` lists the pairs already reviewed and accepted, each with its reason; `--all` shows those too, `--only <regex>` narrows the list. Top plates and the attic deck are cut where a duct or pipe rises through them (`model/make_house.py` reads the last `equipment.json`), so after moving a stack or riser run `make_equipment.py` and then `make_house.py` again.
- The range hood has no fan of its own: an 8 in duct rises inside the chimney cover, through a silencer, to a blower on the roof.

## Run locally

    cd site && python3 -m http.server 8000

Then open http://localhost:8000.
