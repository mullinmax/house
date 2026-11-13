# House walkthrough

An interactive, walkable 3D model of the house, built from the parametric Blender model and hosted with GitHub Pages.

Open the site, then:

- **Walk mode:** click the view, then use W A S D to move and the mouse to look. Hold Shift to go faster. Esc frees the mouse.
- **N** toggles no clip: fly through walls in the direction you look, Space up, C down.
- **E** opens and closes whatever you're looking at: doors, the barn doors, the bi-parting slider, the garage doors and drawers.
- **Orbit mode:** drag to rotate around the site, scroll to zoom. Click a door to open it.
- **Panel:** jump to any room, take the roof off for a dollhouse view, cut away the loft and attic with Upstairs off, switch between Day and Night (room lights on), show or hide the buried geothermal and septic lines, and thin the trees with the Trees slider on slow devices.
- **Slow device?** Add `?lite` to the address to start without shadows and with a quarter of the trees.
- **Phones:** the left stick moves, drag anywhere else to look, tap a door to open it.

## Layout

- `site/index.html`, `site/app.js`: the viewer (three.js 0.160, vendored in `site/vendor`, MIT license).
- `site/models/`: the model, split into `.glb` parts listed in `manifest.json`. These are exported from Blender (full materials, real terrain and instanced trees) and compressed with gltfpack:

      gltfpack -i part.glb -o site/models/part.glb -cc -kn -ke        # furniture, interior, shell
      gltfpack -i site.glb -o site/models/site.glb -cc -kn -ke -vpf  # float positions keep terrain heights exact
      gltfpack -i trees.glb -o site/models/trees.glb -cc -kn -ke     # keeps EXT_mesh_gpu_instancing

  Without `-vpf` the site's kilometre-wide ground skirt makes the shared quantization grid coarse enough to push the terrain up through the slab.
- `.github/workflows/pages.yml`: publishes `site/` to GitHub Pages on every push to `main`. It must be the only Pages workflow: a second one (such as GitHub's starter `static.yml`, which uploads the whole repo) races it, and whichever finishes last wins. When the starter won, https://mullinmax.github.io/house/ showed a 404 and the viewer was only at `/house/site/`.

**Site address:** https://mullinmax.github.io/house/ (Settings, Pages, Source must be "GitHub Actions").

## Performance notes

- On load the viewer bakes static meshes that share a material into one mesh per part, toggle group and 20 m grid cell, cutting about 2000 draw calls to about 550. Operable parts and light fixtures stay separate.
- Shadows are redrawn only when the viewer moves 4 m, a door moves, or a toggle changes. Pixel ratio is capped at 1.5. A logarithmic depth buffer reduces flicker on thin parts.
- At night the 8 room lights nearest the viewer are lit, from `manifest.lights` (Blender metres) or one per room as a fallback.

## Model conventions the viewer reads

- Units are metres with Y up. Plan feet (x east, y south from the NW slab corner) map to `(x * 0.3048, height, y * 0.3048)`.
- **Doors and drawers:** any node with glTF extras `operable` becomes interactive.
  - `"swing"` takes `open_angle` in degrees and `axis` ("z" means the vertical hinge).
  - `"slide"` and `"drawer"` take `slide`, a world move in Blender metres `[dx, dy, dz]`.
  - `"rollup"` lifts the door by its own height.
  - Pivots sit at the hinge or track.
- **Spawn points:** `Spawn_<Room>` empty nodes, at eye height, are spawn points. An optional `look` extra gives the Blender world point to face.
- **Toggles:** nodes named `Roof` or matching roof, fascia, gutter and ceiling names hide with "Roof off". Nodes named `Utilities` or matching geothermal or septic names follow "Buried lines".

## Draft export (cloud)

A fallback when the laptop export isn't available. `tools/export_web_draft.py` builds the model with pip `bpy` and writes `site/models/house.glb`.
- It closes every door and wires them up as operable.
- It bakes the stained concrete floor with its diamond saw cuts. Other materials are flat colors.

To run it:

    python tools/export_web_draft.py --model /path/to/house-model --out site/models --gltfpack /path/to/gltfpack

## Run locally

    cd site && python3 -m http.server 8000

Then open http://localhost:8000.
