# model/

The house as numbers and the scripts that turn them into the walkthrough's data. The main README at the repo root
says how each piece is used; in short:

- `config.toml`: the plans as numbers (walls, rooms, openings, roof, kitchen, loft, garage, porch, trusses, framing, grade).
  Values not read off the plans are marked ASSUMED.
- `make_house.py` writes `site/models/house.json` (the house). `ladder_options.py` and `loft_furniture.py` run inside it.
- `make_equipment.py` writes `site/models/equipment.json` (appliances, mechanical, ducts, pipes, electrical, plantings).
- `make_bom.py` writes the HVAC bill of materials (`site/models/bom.json`, `docs/hvac-bom.*`).
- `grade.py`: finished grade around the buildings, read by the scripts above.
- `make_terrain.py`: downloads the USGS ground model into `data/terrain/` (needs numpy, pyproj, tifffile, pillow,
  laspy[lazrs]). Only `dem.npy` and `meta.json` are kept in the repo; its other outputs fed the old Blender build.
- `data/`: traced plan geometry, the electrical plan read off U-11 and U-12, and terrain heights.
