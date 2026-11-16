# Archived Blender generator

This is the Blender version of the house model, kept for reference. It is no longer how the walkthrough is
built: `model/make_house.py` and `site/house.js` now build the walls, roof, windows, doors, cabinets, trim, loft,
garage, porch and greenhouse in the browser from `model/config.toml`, like the equipment layer.

What is still only here:

- the photo-real still and fly-through renders (Cycles),
- the terrain, trees, furniture and bath fixtures in `site/models/site.glb`, `trees.glb` and `furniture_*.glb`,
  which were last exported from these scripts (laptop export v21, 11/13/2026),
- the old `shell.glb` and `interior.glb`, which the site still loads with `?baked` in the address.

These are the v21 scripts from the laptop (`C:\Users\mulli\claude\house-model`), with two changes: they read
`config.toml` and `data/` from `model/`, and the attic deck and loft floor thickness comes from `[floor_trusses]`.

## Running it

You need Blender 4.2 or newer (or `pip install bpy`) and, for the realism pass, the CC0 assets.

    python archive/blender/fetch_assets.py                              # Poly Haven and ambientCG downloads into archive/blender/assets/
    blender --background --python archive/blender/build_house.py -- --save house.blend
    blender --background --python archive/blender/build_house.py -- --render stills --out renders/preview --res 1280x720 --samples 24
    blender --background --python archive/blender/export_web.py         # writes model/web/*.glb and manifest.json

The scripts find `config.toml` next to themselves first, then in `model/`. Real terrain needs the raw data from
`model/make_terrain.py` (the large `dem.npy` and `ortho.jpg` live on the laptop); without it the ground is flat.

To put a new export on the site, shrink and pack the parts as described in the main README, then copy them to
`site/models/`.

## Files

- `build_house.py`: the whole scene from the config: shell, interior walls (A-11 vectors), roof, windows and doors,
  kitchen, loft, garage, porch, greenhouse, terrain, utilities, cameras and render setup.
- `build_details.py`: furniture, bath fixtures, interior trim and doors, exterior details, light fixtures, PBR materials.
- `build_trees.py`: procedural hardwoods.
- `export_web.py`: the glTF export for the walkthrough (operable pivots, spawns, baked floor and terrain, z-fight nudges).
- `export_web_draft.py`: a cloud fallback export with pip `bpy` (closes every door, bakes the stained slab, flat colours elsewhere): `python archive/blender/export_web_draft.py --model /path/to/house-model --out site/models --gltfpack /path/to/gltfpack`.
- `fetch_assets.py`, `assets/SOURCES.md`: CC0 asset downloads and credits.
- `render_queue.ps1`, `make_contact_sheet.py`: resumable renders on the laptop and contact sheets.
- `web_*.py`: checks on an export (bounds, node counts, previews, attic walls, chunking for upload).
