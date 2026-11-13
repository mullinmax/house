# Heilman-Mullin Residence 3D model

Everything is driven by `config.toml`. Change a number or color there, then rebuild.

Build and save the Blender file:
    python build_house.py -- --save house.blend          (pip bpy)
    blender --background --python build_house.py -- --save house.blend

Preview stills (writes renders/preview):
    ... build_house.py -- --render stills --out renders/preview --res 1280x720 --samples 24

Fly-throughs (PNG frames, then join with ffmpeg):
    ... build_house.py -- --render exterior --out renders
    ... build_house.py -- --render interior --out renders

Dollhouse cutaways (roof and ceilings off, looking down into the rooms):
    ... build_house.py -- --render dollhouse --out renders/dollhouse_cfg          ([dollhouse] in config.toml: 4 corners + plan)
    ... build_house.py -- --render stills --out renders/dollhouse --only dollhouse_southwest,dollhouse_southeast,dollhouse_northeast,dollhouse_northwest,dollhouse_kitchen_closeup,dollhouse_bedrooms_closeup,dollhouse_plan_topdown   (8.6 ft cut, --cut N to change)

Realism pass (furniture, bath fixtures, trim, PBR materials, HDRI sky), all CC0 assets:
    python fetch_assets.py          (downloads [assets] from Poly Haven and ambientCG into assets/, writes assets/SOURCES.md)
    build_details.py is run by build_house.py when [furnishings] or [assets] is enabled; every placement is in
    [furnishings] in config.toml (ASSUMED positions). Set both enabled = false for the plain v1 model.
    render_queue.ps1 renders resumable fly-throughs and stills with a stall watchdog, then joins MP4s:
    powershell -File render_queue.ps1 -Out renders\v2_realism -Jobs exterior,interior -Samples 64

Buried utilities map (PDF and PNG in renders/):
    python3 make_utility_map.py

Real terrain (USGS 3DEP DEM + lidar trees, NAIP photo, OpenStreetMap roads), writes data/terrain/:
    python make_terrain.py          (needs numpy, pyproj, tifffile, pillow, laspy[lazrs]; [terrain] in config.toml)
    Set [terrain] enabled = false for the old flat lawn. Add --gpu 1 to any render to use the GPU.

Files
- config.toml: dimensions, openings, finishes, assumptions (search for ASSUMED)
- make_terrain.py: downloads and converts the site terrain data
- build_details.py: furniture, fixtures, trim, PBR materials and HDRI (run from build_house.py)
- fetch_assets.py, assets/SOURCES.md: CC0 asset downloads and their sources
- data/terrain/: dem.npy, chm.npy, ortho.jpg, trees.json, osm.json, meta.json (terrain_10ft.json is a shareable downsample)
- data/traced_geometry.json: interior walls from sheet A-11 and the geothermal and septic routes traced from the drone photos
- house.blend: last built model, organized in collections (House, Garage Porch Greenhouse, Buried Utilities, Cameras)
