# House walkthrough

An interactive, walkable 3D model of the house, built from the parametric Blender model and hosted with GitHub Pages.

Open the site, then:

- **Walk mode:** click the view, then use W A S D to move and the mouse to look. Hold Shift to go faster. Esc frees the mouse.
- **E** opens and closes whatever you're looking at: doors, the barn doors, the bi-parting slider, the garage doors and drawers.
- **Orbit mode:** drag to rotate around the site, scroll to zoom. Click a door to open it.
- **Panel:** jump to any room, take the roof off for a dollhouse view, show or hide the buried geothermal and septic lines, and move the sun.
- **Phones:** the left stick moves, drag anywhere else to look, tap a door to open it.

## Layout

- `site/index.html`, `site/app.js`: the viewer (three.js 0.160, vendored in `site/vendor`, MIT license).
- `site/models/`: the model, split into `.glb` parts listed in `manifest.json`. These are exported from Blender with `export_web.py` and compressed with meshopt.
- `.github/workflows/pages.yml`: publishes `site/` to GitHub Pages on every push to `main`.

## Model conventions the viewer reads

- Units are metres with Y up. Plan feet (x east, y south from the NW slab corner) map to `(x * 0.3048, height, y * 0.3048)`.
- **Doors and drawers:** any node with glTF extras `operable` becomes interactive.
  - `"swing"` takes `open_angle` in degrees and `axis` ("z" means the vertical hinge).
  - `"slide"` and `"drawer"` take `slide`, a world move in Blender metres `[dx, dy, dz]`.
  - `"rollup"` lifts the door by its own height.
  - Pivots sit at the hinge or track.
- **Spawn points:** `Spawn_<Room>` empty nodes, at eye height, are spawn points. An optional `look` extra gives the Blender world point to face.
- **Toggles:** nodes named `Roof` or matching roof, fascia, gutter and ceiling names hide with "Roof off". Nodes named `Utilities` or matching geothermal or septic names follow "Buried lines".

## Run locally

    cd site && python3 -m http.server 8000

Then open http://localhost:8000.
