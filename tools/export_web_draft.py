"""Draft web export of the house model, runnable in the cloud with pip bpy (no downloaded assets needed).

Usage:  python export_web_draft.py --model /path/to/house-model --out site/models
  1. copies the model sources to a temp folder, closes every door (web wants doors closed),
     fills in materials that need downloaded assets with flat stand-ins, and builds the scene;
  2. replaces procedural shaders with flat colors (glTF can't carry them), bakes a stained
     concrete floor texture with the diamond saw cuts from config.toml;
  3. groups door leaves, sliders, garage doors and drawers under pivots with glTF extras
     ("operable": swing | slide | drawer | rollup) that the viewer animates with E;
  4. exports house.glb and runs gltfpack (meshopt) if it is on PATH or given with --gltfpack.
The full export with baked PBR textures, terrain and trees is export_web.py on the render machine.
"""
import argparse, json, math, os, re, shutil, subprocess, sys, tempfile, tomllib

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--gltfpack", default="gltfpack")
ap.add_argument("--blender-python", default=sys.executable)
ap.add_argument("--stage", default="all", choices=["all", "post"])
ap.add_argument("--blend", default="")
A = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
OUT = os.path.abspath(A.out)
os.makedirs(OUT, exist_ok=True)

if A.stage == "all":
    # ------------------------------------------------------------ 1. build with doors closed
    tmp = tempfile.mkdtemp(prefix="house_web_")
    for f in ("build_house.py", "build_details.py", "config.toml"):
        shutil.copy(os.path.join(A.model, f), tmp)
    shutil.copytree(os.path.join(A.model, "data"), os.path.join(tmp, "data"))
    cfg = open(os.path.join(tmp, "config.toml"), encoding="utf-8").read()
    cfg = re.sub(r"(\[barn_door\][^\[]*?\nopen\s*=\s*)[0-9.]+", r"\g<1>0.0", cfg, flags=re.S)
    open(os.path.join(tmp, "config.toml"), "w", encoding="utf-8").write(cfg)
    bd = open(os.path.join(tmp, "build_details.py"), encoding="utf-8").read()
    bd = bd.replace("            if on_path:", "            if False:")          # every interior door closed
    stand_ins = ('for _nm, _hx in (("Bedding", "#ECE8E0"), ("Rug", "#B9A98E"), ("Tile Wall", "#E8E6E1"), '
                 '("Tile Floor", "#BDB8AE"), ("Upholstery", "#CFC6B6"), ("Curtain", "#E6E0D4")):\n'
                 '    if _nm not in MATS:\n        simple(_nm, _hx, 0.85)\n')
    bd = stand_ins + bd
    open(os.path.join(tmp, "build_details.py"), "w", encoding="utf-8").write(bd)
    blend = os.path.join(tmp, "web.blend")
    r = subprocess.run([A.blender_python, os.path.join(tmp, "build_house.py"), "--", "--config",
                        os.path.join(tmp, "config.toml"), "--save", blend], capture_output=True, text=True, cwd=tmp)
    fails = [ln for ln in r.stdout.splitlines() if "failed" in ln and "CUEW" not in ln]
    print("\n".join(fails) or "build: every furnishing placed")
    if "BUILD OK" not in r.stdout:
        print(r.stdout[-3000:], r.stderr[-3000:]); sys.exit(1)
    r = subprocess.run([A.blender_python, os.path.abspath(__file__), "--", "--model", tmp, "--out", OUT,
                        "--gltfpack", A.gltfpack, "--stage", "post", "--blend", blend], text=True)
    sys.exit(r.returncode)

# ---------------------------------------------------------------- 2..4 inside Blender
import bpy, mathutils
from mathutils import Vector, Matrix

bpy.ops.wm.open_mainfile(filepath=A.blend)
C = tomllib.load(open(os.path.join(A.model, "config.toml"), "rb"))
F = 0.3048
HW, HD = C["house"]["width_x"], C["house"]["depth_y"]
MC = C["materials"]


def hexcol(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [1.0]


# ---- 2. flat colors for procedural materials, image texture for the floor
FLAT = {"Siding": MC.get("siding_color", "#7D8A6C"), "White Oak": "#C9A57C", "Grass": "#6F8F4E", "Gravel": "#8E8A82",
        "Cabinet Wood": C.get("kitchen", {}).get("cabinet_wood", "#B98B5A")}


def flatten(m, color, rough=0.6):
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    for inp in ("Base Color", "Roughness", "Normal", "Metallic"):
        for lk in list(b.inputs[inp].links):
            nt.links.remove(lk)
    b.inputs["Base Color"].default_value = hexcol(color)
    b.inputs["Roughness"].default_value = rough


for m in bpy.data.materials:
    if not m.use_nodes:
        continue
    b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if b is None:
        continue
    if m.name in FLAT:
        flatten(m, FLAT[m.name])
    elif b.inputs["Base Color"].is_linked and m.name != "Stained Concrete":
        flatten(m, "#BBBBBB")


def floor_texture(path, ppf=40):
    """stained concrete with diamond saw cuts, covering the slab; row 0 = north edge."""
    import numpy as np
    W, H = int(HW * ppf), int(HD * ppf)
    x = (np.arange(W) + 0.5) / ppf; y = (np.arange(H) + 0.5) / ppf
    X, Y = np.meshgrid(x, y)
    rng = np.random.default_rng(7)
    def noise(scale, amp):
        g = rng.random((int(H / ppf / scale) + 3, int(W / ppf / scale) + 3))
        gy, gx = Y / scale, X / scale
        i, j = gy.astype(int), gx.astype(int); fy, fx = gy - i, gx - j
        fy = fy * fy * (3 - 2 * fy); fx = fx * fx * (3 - 2 * fx)
        v = (g[i, j] * (1 - fx) + g[i, j + 1] * fx) * (1 - fy) + (g[i + 1, j] * (1 - fx) + g[i + 1, j + 1] * fx) * fy
        return (v - 0.5) * amp
    t = 0.5 + noise(6, 0.9) + noise(2, 0.5) + noise(0.6, 0.25)
    t = np.clip(t, 0, 1)[..., None]
    c1 = np.array([int(MC.get("floor_color", "#7A3B26").lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)], float)
    c2 = np.array([int(MC.get("floor_color_2", "#5A2A1A").lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)], float)
    img = c2 + (c1 - c2) * t
    if MC.get("floor_cut_pattern", "diamond") != "none":
        sp = MC.get("floor_cut_spacing", 9.0) * math.sqrt(2)
        ox, oy = MC.get("floor_cut_origin", [HW / 2, HD])
        half = 0.09                                   # cut line half width in ft (about 2 px)
        for u in ((X - ox) + (Y - oy), (X - ox) - (Y - oy)):
            d = np.abs(((u / sp + 0.5) % 1.0) - 0.5) * sp / math.sqrt(2)
            k = np.clip(1 - d / half, 0, 1)[..., None]
            img = img * (1 - 0.55 * k)
    from PIL import Image
    Image.fromarray(np.clip(img, 0, 255).astype("uint8")).save(path, quality=88)


floor_img = os.path.join(os.path.dirname(A.blend), "floor_diamond.jpg")
floor_texture(floor_img)
fm = bpy.data.materials.get("Stained Concrete")
if fm:
    nt = fm.node_tree
    for n in list(nt.nodes):
        if n.type not in ('BSDF_PRINCIPLED', 'OUTPUT_MATERIAL'):
            nt.nodes.remove(n)
    b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = bpy.data.images.load(floor_img)
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = MC.get("floor_gloss", 0.35)
    for ob in bpy.data.objects:
        if ob.type == 'MESH' and any(s.material == fm for s in ob.material_slots):
            me = ob.data
            uv = me.uv_layers.get("floor") or me.uv_layers.new(name="floor")
            me.uv_layers.active = uv
            mw = ob.matrix_world
            for poly in me.polygons:
                for li in poly.loop_indices:
                    v = mw @ me.vertices[me.loops[li].vertex_index].co
                    uv.data[li].uv = (v.x / F / HW, 1 + v.y / F / HD)   # Blender y = -plan y

# ---- 3. operable things
OPS = []


def wbox(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    return Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))), \
        Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))


def pivot(name, loc, objs, extras):
    e = bpy.data.objects.new(name, None)
    (objs[0].users_collection[0] if objs[0].users_collection else bpy.context.scene.collection).objects.link(e)
    e.location = loc
    bpy.context.view_layer.update()
    inv = e.matrix_world.inverted()
    for o in objs:
        mw = o.matrix_world.copy()
        o.parent = e
        o.matrix_parent_inverse = inv
        o.matrix_world = mw
    for k, v in extras.items():
        e[k] = v
    OPS.append(name)
    return e


HOUSE_C = Vector((HW / 2 * F, -HD / 2 * F, 0))


def swing(name, leaf_objs, hinge_end, inward_to=None, angle=90):
    lo, hi = wbox(leaf_objs)
    along_x = (hi.x - lo.x) >= (hi.y - lo.y)
    mid_thin = (lo.y + hi.y) / 2 if along_x else (lo.x + hi.x) / 2
    if along_x:
        hx = lo.x if hinge_end == "min" else hi.x
        hinge = Vector((hx, mid_thin, lo.z))
    else:
        hy = lo.y if hinge_end == "min" else hi.y
        hinge = Vector((mid_thin, hy, lo.z))
    c = (lo + hi) / 2; c.z = lo.z
    best = angle
    if inward_to is not None:      # pick the swing direction that ends nearer the target point
        def end(a):
            r = Matrix.Rotation(math.radians(a), 3, 'Z')
            return hinge + r @ (c - hinge)
        best = min((angle, -angle), key=lambda a: (end(a) - inward_to).length)
    return pivot(name, hinge, leaf_objs, {"operable": "swing", "open_angle": float(best), "axis": "z"})


objs = [o for o in bpy.data.objects if o.type == 'MESH']
by_name = {}
for o in objs:
    by_name.setdefault(re.sub(r"\.\d+$", "", o.name), []).append(o)


def center(o):
    lo, hi = wbox([o]); return (lo + hi) / 2


# interior door leaves with their levers and roses
levers = [o for o in objs if re.sub(r"\.\d+$", "", o.name) in ("Door lever", "Door lever rose")]
for i, leaf in enumerate(by_name.get("Door leaf", [])):
    lo, hi = wbox([leaf])
    along_x = (hi.x - lo.x) >= (hi.y - lo.y)
    near = []
    for lv in levers:
        c = center(lv)
        if along_x and lo.x - 0.02 <= c.x <= hi.x + 0.02 and lo.y - 0.12 <= c.y <= hi.y + 0.12 and lo.z <= c.z <= hi.z:
            near.append(lv)
        elif not along_x and lo.y - 0.02 <= c.y <= hi.y + 0.02 and lo.x - 0.12 <= c.x <= hi.x + 0.12 and lo.z <= c.z <= hi.z:
            near.append(lv)
    for lv in near:
        levers.remove(lv)
    if near:
        lc = sum((center(lv) for lv in near), Vector()) / len(near)
        mid = (lo + hi) / 2
        hinge_end = "max" if ((lc.x < mid.x) if along_x else (lc.y < mid.y)) else "min"
    else:
        hinge_end = "min"
    c = (lo + hi) / 2
    # swing toward the side of the wall with more room: away from the house centre for most hall doors
    side = Vector((0, 0.6, 0)) if along_x else Vector((0.6, 0, 0))
    target = c + side if (c + side - HOUSE_C).length > (c - side - HOUSE_C).length else c - side
    swing(f"Op door {i}", [leaf] + near, hinge_end, inward_to=target)

# pantry door
pd = by_name.get("Pantry door", [])
if pd:
    pl = by_name.get("Pantry door lever", []) + by_name.get("Pantry door lever rose", [])
    lo, hi = wbox(pd)
    swing("Op pantry door", pd + pl, "min", inward_to=Vector(((lo.x + hi.x) / 2, hi.y + 0.6, 0)))

# exterior glass doors: the leaf is the clad/oak frame, glass and kick rail of the unit
for op in C["openings"]:
    if op.get("kind") != "door_glass":
        continue
    parts = [o for o in objs if o.name.startswith(op["id"] + " ") and re.search(r"frame|glass|kick rail", o.name)]
    if parts:
        swing("Op " + op["id"], parts, "min", inward_to=HOUSE_C)

# garage man door
gm = by_name.get("Garage man door", [])
if gm:
    g = C["garage"]["rect"]
    swing("Op garage man door", gm, "min", inward_to=Vector(((g[0] + g[2]) / 2 * F, -(g[1] + g[3]) / 2 * F, 0)))

# garage overhead doors roll up
for k, o in enumerate([o for o in objs if any(s.material and s.material.name == "Garage Door" for s in o.material_slots)]):
    lo, hi = wbox([o])
    pivot(f"Op garage door {k}", Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z)), [o], {"operable": "rollup"})

# barn door leaves slide apart along the track
for side_, sgn in (("L", -1), ("R", 1)):
    parts = [o for o in objs if o.name.startswith(f"Barn door {side_} ")]
    if parts:
        lo, hi = wbox(parts)
        pivot(f"Op barn door {side_}", Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z)), parts,
              {"operable": "slide", "slide": [sgn * (hi.x - lo.x) * 0.98, 0.0, 0.0]})

# kitchen drawers: everything named "<cabinet> drawer N ..." slides out of its cabinet
groups = {}
for o in objs:
    m = re.match(r"^(Kitchen .+? (?:tray )?drawer(?: \d+)?)(?: (?:panel|pull|rail [TB]|stile [LR]|front))?(?:\.\d+)?$", o.name)
    if m and "carcass" not in o.name:
        groups.setdefault(m.group(1), []).append(o)
for k, (gname, parts) in enumerate(sorted(groups.items())):
    cab = re.sub(r" (?:tray )?drawer(?: \d+)?$", "", gname)
    carc = [o for o in objs if o.name.startswith(cab) and "carcass" in o.name]
    lo, hi = wbox(parts); c = (lo + hi) / 2
    if carc:
        cl, ch = wbox(carc); cc = (cl + ch) / 2
        d = c - cc; d.z = 0
    else:
        d = Vector((0, 1, 0))
    d = Vector((math.copysign(1, d.x), 0, 0)) if abs(d.x) > abs(d.y) else Vector((0, math.copysign(1, d.y), 0))
    pivot(f"Op drawer {k}", Vector((c.x, c.y, lo.z)), parts, {"operable": "drawer", "slide": [d.x * 0.38, d.y * 0.38, 0.0]})

print(f"operable: {len(OPS)}")

# room spawn points (eye height 5'-4"), facing into each room
ROOMS = {"Kitchen": (9, 39.5, 8, 48), "Living": (19, 29, 31, 27), "Dining": (30, 44, 10, 44), "Bed1": (34, 9, 40, 4),
         "Bed2": (13, 8, 8, 4), "Bed3": (5, 19, 9, 13), "Bath1": (36, 26, 40, 30), "Bath2": (19, 9, 19, 3),
         "Garage": (79, 38, 79, 20), "Outside_SW": (-35, 95, 21, 26)}
spawn_col = bpy.data.collections.new("Spawns"); bpy.context.scene.collection.children.link(spawn_col)
for nm, (x, y, lx, ly) in ROOMS.items():
    e = bpy.data.objects.new("Spawn_" + nm, None); spawn_col.objects.link(e)
    e.location = (x * F, -y * F, 5.33 * F)
    e["look"] = [lx * F, -ly * F, 5.33 * F]

# ---- 4. export
skip = ("cutters", "Opening Cutters", "Cameras and Lights")
for o in bpy.data.objects:
    o.select_set(False)
keep = set()
for col in bpy.data.collections:
    if any(col.name.startswith(s) for s in skip):
        continue
    for o in col.objects:
        if (o.type == 'MESH' and not o.hide_render) or o.type == 'EMPTY':
            keep.add(o)
for o in list(keep):
    p = o.parent
    while p is not None:
        keep.add(p); p = p.parent
for o in keep:
    o.hide_set(False); o.hide_viewport = False
    o.select_set(True)
raw = os.path.join(os.path.dirname(A.blend), "house_raw.glb")
bpy.ops.export_scene.gltf(filepath=raw, export_format='GLB', use_selection=True, export_apply=True,
                          export_extras=True, export_yup=True, export_image_format='JPEG')
dst = os.path.join(OUT, "house.glb")
try:
    subprocess.run([A.gltfpack, "-i", raw, "-o", dst, "-cc", "-kn", "-ke"], check=True, capture_output=True)
except Exception as ex:
    print("gltfpack not used:", ex); shutil.copy(raw, dst)
size = os.path.getsize(dst)
man = {"note": "Draft model exported in the cloud with export_web_draft.py: flat colors, baked floor, flat ground.",
       "units": "metres, glTF Y up", "parts": [{"file": "house.glb", "name": "house", "bytes": size}],
       "sun_direction": [0.34, -0.81, 0.47]}
json.dump(man, open(os.path.join(OUT, "manifest.json"), "w"), indent=2)
print(f"wrote {dst}  {size / 1e6:.1f} MB")
