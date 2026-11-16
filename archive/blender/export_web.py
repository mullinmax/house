"""Export the model for the browser walkthrough (three.js viewer in github.com/mullinmax/house, site/).

Run:  blender --background --python export_web.py -- --config config.toml
Builds the full scene with build_house.py in web mode (doors closed, operable items as pivot nodes with glTF extras),
bakes the procedural surfaces (stained concrete floor with saw cuts, lawn/photo terrain) to images, converts every
material to plain glTF PBR on real-scale UVs, downsizes textures and writes web/:
  site.glb        terrain (baked), roads, gravel, neighbor buildings, node "Utilities" (buried lines + markers)
  trees.glb       one mesh per tree variant + EXT_mesh_gpu_instancing placements (near detailed, far ring light)
  shell.glb       house/garage/porch/greenhouse exterior, windows, node "Roof", exterior operable doors
  interior.glb    walls, floors, ceilings, trim, kitchen; interior doors, pantry door, drawers (operable)
  furniture.glb   furniture and fixtures
  manifest.json   parts, sizes, axis convention, spawn points, sun direction;  sky.jpg  equirect sky
Conventions (as the viewer expects): glTF Y-up metres; Spawn_<Room> empties at eye height with extra
"look" = Blender world point; operable extras:
  {"operable": "swing", "open_angle": deg (signed), "axis": "z"}   pivot on the hinge line
  {"operable": "slide"|"drawer", "slide": [dx, dy, dz]}            Blender world metres, Z up
  {"operable": "rollup"}                                            lifts by its own height
Meshopt compression is a separate step:  gltfpack -i part.glb -o part.glb -cc -kn -ke  (-mi for trees.glb)
"""
import os, sys, json, math

HERE = os.path.dirname(os.path.abspath(__file__))
extra = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if "--web" not in extra:
    extra += ["--web", "1"]
sys.argv = [sys.argv[0], "--"] + extra
_src = os.path.join(HERE, "build_house.py")
exec(compile(open(_src, encoding="utf-8").read(), _src, "exec"))      # builds the scene (no render in web mode)

import bpy, bmesh
import numpy as np
from mathutils import Vector

WEB = C.get("web", {})
OUTD = os.path.join(HERE, WEB.get("out_dir", "web"))
os.makedirs(OUTD, exist_ok=True)
TEX = WEB.get("texture_px", 1024)
TEX_FURN = WEB.get("furniture_texture_px", 256)
EYE = WEB.get("eye_height_ft", 5.33)
ONLY = set(a for a in (ARGS.get("parts") or "").split(",") if a)


def pivot(name, objs, loc, extras, coll):
    return make_pivot(name, [o for o in objs if o], loc, extras, coll)


def objs_named(prefix):
    return [o for o in bpy.data.objects if o.name.startswith(prefix) and o.type == 'MESH']


# ================================================================== operable items (all start closed)
ops = []
for o in C["openings"]:
    fr = wall_frame(o["wall"])
    if o["kind"] == "door_glass":
        # the whole leaf moves: sash frame ring (clad + oak halves), glass, kick rail; trim, jambs, casing stay
        parts = objs_named(o["id"] + " glass") + objs_named(o["id"] + " kick rail") + objs_named(o["id"] + " frame ")
        hx, hy = fr(o["start"], SKIN + 0.2)
        ax_ = Vector(P(*fr(o["start"] + 1, 0)) - P(*fr(o["start"], 0)))
        in_ = Vector(P(*fr(o["start"], 1)) - P(*fr(o["start"], 0)))
        sgn = 1 if ax_.cross(in_).z > 0 else -1
        ops.append(pivot(o["id"], parts, P(hx, hy, 0), {"operable": "swing", "open_angle": 90 * sgn, "axis": "z"}, c_win))
    elif o["kind"] == "slider":
        # bi-parting: the two middle panes slide outward over the fixed outer panes
        for g_ in objs_named(o["id"] + " glass") + objs_named(o["id"] + " mullion"):
            bpy.data.objects.remove(g_)
        u0, u1, z0, z1 = o["start"], o["end"], o["sill"], o["head"]
        w4 = (u1 - u0) / 4; v0 = SKIN + 0.05
        for (a, b, nm, vv) in ((u0 + 0.09, u0 + w4, "fixed W", 0.4), (u1 - w4, u1 - 0.09, "fixed E", 0.4),
                               (u0 + w4, (u0 + u1) / 2 - 0.01, "leaf W", 0.55), ((u0 + u1) / 2 + 0.01, u1 - w4, "leaf E", 0.55)):
            g_ = wbox(f"{o['id']} glass {nm}", o["wall"], a, b, v0 + 0.3 * vv - 0.015, v0 + 0.3 * vv + 0.015, z0 + 0.12, z1 - 0.05, "Glass", c_win)
            if nm.startswith("leaf"):
                vv0, vv1 = v0 + 0.3 * vv - 0.035, v0 + 0.3 * vv + 0.035
                fr_ = [wbox(f"{o['id']} {nm} sash bottom", o["wall"], a, b, vv0, vv1, z0 + 0.06, z0 + 0.16, "Window Frame", c_win),
                       wbox(f"{o['id']} {nm} sash top", o["wall"], a, b, vv0, vv1, z1 - 0.12, z1 - 0.04, "Window Frame", c_win),
                       wbox(f"{o['id']} {nm} sash stile a", o["wall"], a, a + 0.12, vv0, vv1, z0 + 0.06, z1 - 0.04, "Window Frame", c_win),
                       wbox(f"{o['id']} {nm} sash stile b", o["wall"], b - 0.12, b, vv0, vv1, z0 + 0.06, z1 - 0.04, "Window Frame", c_win),
                       wbox(f"{o['id']} {nm} handle", o["wall"], (b - 0.3 if nm == "leaf W" else a + 0.2), (b - 0.2 if nm == "leaf W" else a + 0.3),
                            vv1, vv1 + 0.06, 3.0, 4.2, "Brushed Nickel", c_win)]
                sg = -1 if nm == "leaf W" else 1
                d = Vector(P(*fr(o["start"] + sg * w4, 0)) - P(*fr(o["start"], 0)))
                cx, cy = fr((a + b) / 2, v0 + 0.3 * vv)
                ops.append(pivot(f"{o['id']} {nm}", [g_] + fr_, P(cx, cy, 0), {"operable": "slide", "slide": [round(d.x, 3), round(d.y, 3), 0.0]}, c_win))
BDc = C.get("barn_door", {})
if BDc.get("enabled"):
    bx0, bx1, bhd = min(CL["passages"], key=lambda p: abs((p[0] + p[1]) / 2 - BDc["center_x"]))
    lw = (bx1 - bx0) / 2 + 0.15
    for side, sg in (("L", -1), ("R", 1)):
        parts = [o for o in bpy.data.objects if o.name.startswith(f"Barn door {side}") and o.type == 'MESH']
        cx = bx0 + lw / 2 - 0.15 if side == "L" else bx1 - lw / 2 + 0.15
        ops.append(pivot(f"Barn door {side}", parts, P(cx, YC2 + 0.2, 0), {"operable": "slide", "slide": [round(sg * lw * F, 3), 0.0, 0.0]}, c_win))
pp = [o for o in objs_named("Pantry door") if not o.name.startswith(("Pantry door casing", "Pantry door jamb", "Pantry door head"))]
if pp:
    px0_, px1_, _ = min(CL["passages"], key=lambda p: p[0])
    leaf_ = RUNS["north"].get("pantry_door_leaf", px1_ - px0_ - 0.2)
    lx0_ = (px0_ + px1_) / 2 - leaf_ / 2
    ops.append(pivot("Pantry door", pp, P(lx0_, YC + 0.27, 0), {"operable": "swing", "open_angle": 90, "axis": "z"}, c_kit))
GA_ = C["garage"]
if GA_["enabled"]:
    gx0_ = GA_["rect"][0]
    for k_, (s0, w) in enumerate(GA_["overhead_doors"]):
        parts = [o for o in bpy.data.objects if o.name.startswith("Overhead door") and o.type == 'MESH' and o.parent is None
                 and gx0_ + s0 - 0.2 <= (sum((o.matrix_world @ Vector(c)).x for c in o.bound_box) / 8) / F <= gx0_ + s0 + w + 0.2]
        ops.append(pivot(f"Garage door {k_ + 1}", parts, P(gx0_ + s0 + w / 2, GA_["rect"][3] - 0.35, 0), {"operable": "rollup"}, c_out))
    md_ = objs_named("Garage man door")
    my0_, my1_ = GA_["man_door_y"]
    ops.append(pivot("Garage man door", md_, P(gx0_ + 0.25, my0_, 0), {"operable": "swing", "open_angle": 90, "axis": "z"}, c_out))
# kitchen drawers slide out of their runs
import re
drawers = {}
for o in bpy.data.objects:
    mm = re.match(r"^(Kitchen (\w+) \d+ \S+(?: pullout)? drawer \d+)", o.name)
    if mm and o.type == 'MESH':
        drawers.setdefault((mm.group(1), mm.group(2)), []).append(o)
for (dn, rn), parts in drawers.items():
    run = RUNS.get(rn)
    if not run:
        continue
    pull = 1.3 * run["facing"]
    d = (0.0, -pull * F, 0.0) if run["axis"] == "x" else (pull * F, 0.0, 0.0)
    c_ = sum((Vector(p.matrix_world @ Vector(cc)) for p in parts for cc in p.bound_box), Vector()) / (8 * len(parts))
    ops.append(pivot(dn.replace("Kitchen ", "Drawer "), parts, c_, {"operable": "drawer", "slide": [round(v, 3) for v in d]}, c_kit))
print(f"web: {len(ops)} operable nodes outside the interior doors (+ {sum(1 for o in bpy.data.objects if o.get('operable') == 'swing' and o.name.startswith('Door '))} interior doors)")

# ================================================================== spawn points
SPAWNS = WEB.get("spawns", {
    "Kitchen": [[10.5, 48.5], [3.0, 44.0]], "Living": [[19.5, 28.0], [30.0, 28.0]], "Dining": [[41.5, 43.5], [34.0, 48.0]],
    "Bed1": [[34.0, 10.0], [41.5, 5.0]], "Bed2": [[14.2, 9.4], [7.0, 4.5]], "Bed3": [[3.0, 20.8], [11.0, 15.0]],
    "Bath1": [[35.5, 27.5], [32.0, 25.0]], "Bath2": [[19.0, 7.5], [21.5, 2.0]], "Garage": [[79.0, 25.0], [79.0, 42.0]],
    "Outside_SW": [[-40.0, 110.0], [22.0, 30.0]]})
c_web = col("Web Markers")
spawn_info = {}
for nm, ((x, y), (lx, ly)) in SPAWNS.items():
    outdoor = (x < 0 or y < 0 or x > HW or y > HD) and not (63 <= x <= 96 and 15 <= y <= 43)
    gz = ground_z(x, y) if outdoor else 0.0
    e = bpy.data.objects.new(f"Spawn_{nm}", None); c_web.objects.link(e)
    e.location = P(x, y, gz + EYE)
    lk = P(lx, ly, gz + EYE - 0.3)
    look = [round(lk.x, 3), round(lk.y, 3), round(lk.z, 3)]
    e["look"] = look
    spawn_info[nm] = {"pos": [round(v, 3) for v in e.location], "look": look}


def group_node(name, objects, coll):
    g = bpy.data.objects.new(name, None); coll.objects.link(g)
    for o in objects:
        if o.parent is None and o.name in bpy.data.objects:
            o.parent = g
    return g


roof_objs = list(c_roof.all_objects) + [o for o in c_out.objects if any(w in o.name for w in ("roof", "Roof", "seam"))] + \
            [o for o in bpy.data.objects if o.name.startswith(("Fascia", "Rake", "Soffit", "Gutter"))]
util_objs = list(c_util.all_objects) + list(c_mark.all_objects)
upper_objs = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith(("Loft floor", "Loft railing", "Attic floor"))]

# ================================================================== bakes (procedural -> images), GPU if free
scene.render.engine = 'CYCLES'
scene.cycles.samples = 16
scene.render.bake.use_pass_direct = False; scene.render.bake.use_pass_indirect = False


def bake_color(ob, name, px, uv_name):
    me = ob.data
    if uv_name not in me.uv_layers:
        return None
    me.uv_layers.active = me.uv_layers[uv_name]
    img = bpy.data.images.new(name, px, px)
    mats = [s.material for s in ob.material_slots if s.material]
    nodes = []
    for m_ in mats:
        nd = m_.node_tree.nodes.new("ShaderNodeTexImage"); nd.image = img
        m_.node_tree.nodes.active = nd; nodes.append((m_, nd))
    bpy.ops.object.select_all(action='DESELECT')
    ob.hide_set(False); ob.select_set(True); bpy.context.view_layer.objects.active = ob
    bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, target='IMAGE_TEXTURES', margin=4, uv_layer=uv_name)
    img.pack()
    for m_, nd in nodes:
        m_.node_tree.nodes.remove(nd)
    return img


def planar_uv(ob, name="WebUV", top_only_xy=False):
    """per-face planar UVs in metres (world axes)."""
    me = ob.data
    co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    mw = np.array(ob.matrix_world); co = co @ mw[:3, :3].T + mw[:3, 3]
    uvl = me.uv_layers.get(name) or me.uv_layers.new(name=name)
    data = []
    for p in me.polygons:
        ax = int(np.argmax(np.abs(np.array(p.normal)))) if not top_only_xy else 2
        ua, va = [a for a in range(3) if a != ax]
        for li in p.loop_indices:
            v = co[me.loops[li].vertex_index]; data += [v[ua], v[va]]
    uvl.data.foreach_set("uv", data)


BAKED = {}
for oname, px in (("Slab", 2048),):
    ob = bpy.data.objects.get(oname)
    if ob:
        planar_uv(ob, "BakeUV", top_only_xy=True)
        me = ob.data
        # normalise to 0..1 over the slab
        uvl = me.uv_layers["BakeUV"]; a = np.empty(len(uvl.data) * 2); uvl.data.foreach_get("uv", a); a = a.reshape(-1, 2)
        lo, hi = a.min(0), a.max(0); a = (a - lo) / (hi - lo).max(); uvl.data.foreach_set("uv", a.ravel())
        BAKED[oname] = (bake_color(ob, f"{oname} baked", px, "BakeUV"), "BakeUV")
for oname, px in (("Terrain", 2048), ("Terrain far", 1024)):
    ob = bpy.data.objects.get(oname)
    if ob:
        BAKED[oname] = (bake_color(ob, f"{oname} baked", px, "UV"), "UV")
print("web: baked", list(BAKED))

# ================================================================== materials -> plain glTF PBR
asset_mats = set()
for c_ in bpy.data.collections:
    if c_.name.startswith("asset "):
        for o in c_.all_objects:
            for s in getattr(o, "material_slots", []):
                if s.material:
                    asset_mats.add(s.material.name)


def img_array(img):
    px = np.empty(img.size[0] * img.size[1] * 4, np.float32); img.pixels.foreach_get(px)
    return px.reshape(img.size[1], img.size[0], 4)


def adjusted_image(img, hsv=None, tint=None, amount=1.0, mode='MULTIPLY_DETAIL'):
    """bake the node-tree color adjustments (hsv value/saturation, tint) into a new image."""
    a = img_array(img).copy()
    rgb = a[..., :3]
    if hsv:
        g = rgb.mean(-1, keepdims=True); rgb = (g + (rgb - g) * hsv[1]) * hsv[2]
    if tint is not None:
        t = np.array(tint[:3], np.float32)
        if mode == 'MULTIPLY_DETAIL':
            lum = (rgb * [0.2126, 0.7152, 0.0722]).sum(-1, keepdims=True); mean = max(float(lum.mean()), 0.02)
            rgb = t * (1 - amount + amount * lum / mean)
        else:   # mix multiply
            rgb = rgb * (1 - amount) + rgb * t * amount
    a[..., :3] = np.clip(rgb, 0, 1)
    out = bpy.data.images.new(img.name + " web", img.size[0], img.size[1]); out.pixels.foreach_set(a.ravel()); out.pack()
    return out


need_uv = {}      # material -> uv layer name it reads
for m in list(bpy.data.materials):
    if not m.use_nodes or m.name in asset_mats:
        continue
    nt = m.node_tree; n, l = nt.nodes, nt.links
    b = next((x for x in n if x.bl_idname == "ShaderNodeBsdfPrincipled"), None)
    out = next((x for x in n if x.bl_idname == "ShaderNodeOutputMaterial"), None)
    if b is None or out is None:
        continue
    for lk in list(out.inputs["Surface"].links):
        l.remove(lk)
    l.new(b.outputs[0], out.inputs["Surface"])
    imgs = [x for x in n if x.bl_idname == "ShaderNodeTexImage" and x.image]
    col_i = next((x for x in imgs if x.image.colorspace_settings.name != 'Non-Color' and "Opacity" not in x.image.name), None)
    op_i = next((x for x in imgs if "Opacity" in x.image.name), None)
    nrm_i = next((x for x in imgs if "Normal" in x.image.name or "nor_gl" in x.image.name.lower()), None)
    uvn = next((x for x in n if x.bl_idname == "ShaderNodeUVMap"), None)
    mp = next((x for x in n if x.bl_idname == "ShaderNodeMapping"), None)
    # what the tree did to the color
    hs = next((x for x in n if x.bl_idname == "ShaderNodeHueSaturation"), None)
    tint = None; amount = 1.0; mode = 'MIX'
    for x in n:
        if x.bl_idname == "ShaderNodeMix" and x.data_type == 'RGBA' and x.blend_type == 'MULTIPLY' and not x.inputs[7].links:
            tint = tuple(x.inputs[7].default_value); amount = x.inputs[0].default_value
        if x.bl_idname == "ShaderNodeMix" and x.data_type == 'RGBA' and x.blend_type == 'MULTIPLY' and not x.inputs[6].links and x.inputs[7].links:
            tint = tuple(x.inputs[6].default_value); mode = 'MULTIPLY_DETAIL'
            fm = next((y for y in n if y.bl_idname == "ShaderNodeMix" and y.data_type == 'FLOAT'), None)
            amount = fm.inputs["Factor"].default_value if fm else 1.0
    solid = None if b.inputs["Base Color"].links else tuple(b.inputs["Base Color"].default_value)
    rough = b.inputs["Roughness"].default_value
    for x in n:
        if x.bl_idname == "ShaderNodeMapRange" and x.outputs[0].links and any(lk.to_socket == b.inputs["Roughness"] for lk in x.outputs[0].links):
            rough = (x.inputs["To Min"].default_value + x.inputs["To Max"].default_value) / 2
    for inp in ("Base Color", "Roughness", "Normal", "Alpha", "Metallic"):
        for lk in list(b.inputs[inp].links):
            l.remove(lk)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Emission Strength"].default_value = min(b.inputs["Emission Strength"].default_value, 2.0)
    uvname = uvn.uv_map if uvn else "WebUV"
    if uvn is None:
        uvn = n.new("ShaderNodeUVMap"); uvn.uv_map = uvname
    vec = uvn.outputs[0]
    if mp is not None:
        for lk in list(mp.inputs[0].links):
            l.remove(lk)
        l.new(uvn.outputs[0], mp.inputs[0]); vec = mp.outputs[0]
    if col_i is not None and solid is None:
        hsvv = (hs.inputs["Hue"].default_value, hs.inputs["Saturation"].default_value, hs.inputs["Value"].default_value) if hs else None
        if hsvv or tint:
            col_i.image = adjusted_image(col_i.image, hsvv, tint, amount, mode)
        col_i.projection = 'FLAT'
        for lk in list(col_i.inputs[0].links):
            l.remove(lk)
        l.new(vec, col_i.inputs[0]); l.new(col_i.outputs["Color"], b.inputs["Base Color"])
        need_uv[m.name] = uvname
    elif solid is not None:
        b.inputs["Base Color"].default_value = solid
    if nrm_i is not None and (col_i is not None or solid is not None) and uvname != "WebUV" or (nrm_i is not None and m.name == "Siding"):
        nrm_i.projection = 'FLAT'
        for lk in list(nrm_i.inputs[0].links):
            l.remove(lk)
        l.new(vec, nrm_i.inputs[0])
        nmn = n.new("ShaderNodeNormalMap"); nmn.uv_map = uvname; nmn.inputs["Strength"].default_value = 0.5
        l.new(nrm_i.outputs["Color"], nmn.inputs["Color"]); l.new(nmn.outputs[0], b.inputs["Normal"])
        need_uv[m.name] = uvname
    if m.name.startswith("Leaves ") and op_i is not None:
        l.new(op_i.outputs["Color"], b.inputs["Alpha"])
        try:
            m.blend_method = 'CLIP'
        except Exception:
            pass
    if "Glass" in m.name or m.name in ("Polycarbonate",):
        b.inputs["Alpha"].default_value = 0.25 if m.name != "Polycarbonate" else 0.4
        try:
            m.blend_method = 'BLEND'
        except Exception:
            pass
# baked objects get their own simple material
for oname, (img, uvname) in BAKED.items():
    if img is None:
        continue
    ob = bpy.data.objects[oname]
    m = bpy.data.materials.new(f"{oname} web"); m.use_nodes = True
    n, l = m.node_tree.nodes, m.node_tree.links; b = n["Principled BSDF"]
    t = n.new("ShaderNodeTexImage"); t.image = img; u = n.new("ShaderNodeUVMap"); u.uv_map = uvname
    l.new(u.outputs[0], t.inputs[0]); l.new(t.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.4 if oname == "Slab" else 0.95
    for s in ob.material_slots:
        s.material = m
# real-scale planar UVs on every object whose material now reads WebUV
nuv = 0
for ob in bpy.data.objects:
    if ob.type != 'MESH' or ob.name in BAKED:
        continue
    if any(s.material and need_uv.get(s.material.name) == "WebUV" for s in ob.material_slots):
        planar_uv(ob); nuv += 1
print(f"web: materials converted, {nuv} objects got WebUV")

# downsize images: furniture smaller
for img in bpy.data.images:
    try:
        lim = TEX_FURN if any(img.name.startswith(p) for p in [m_.split("_")[0] for m_ in C["assets"]["polyhaven_models"]]) else TEX
        if "baked" in img.name:
            lim = 2048
        if img.size[0] > lim or img.size[1] > lim:
            s = lim / max(img.size)
            img.scale(max(1, int(img.size[0] * s)), max(1, int(img.size[1] * s)))
    except Exception:
        pass

# ================================================================== terrain: lighter mesh for the browser
for oname, ratio in (("Terrain", WEB.get("terrain_ratio", 0.25)), ("Terrain far", 0.45)):
    ob = bpy.data.objects.get(oname)
    if ob:
        md = ob.modifiers.new("web decimate", 'DECIMATE'); md.ratio = ratio

# ================================================================== trees: one mesh per variant, GPU-instanced placements
tree_roots = []
try:
    VARIANTS
    _have_trees = True
except NameError:
    _have_trees = False
def gen_web_tree(sp, seed, near=True):
    """browser tree: trunk + a few limbs + leaf clumps of big alpha cards. ~1.5k tris near, ~400 far."""
    import random as _r
    rng = _r.Random(seed)
    BV, BF, BU, LV, LF, LU = [], [], [], [], [], []
    top = sp["split"]; r0 = 0.017
    trunk = _branch_pts(rng, Vector((0, 0, -0.03)), Vector((rng.uniform(-.03, .03), rng.uniform(-.03, .03), 1)), top + 0.03, 5 if near else 3, 0.0)
    _tube(BV, BF, BU, trunk, [r0 * (1 - 0.55 * i / (len(trunk) - 1)) for i in range(len(trunk))], 6 if near else 4)
    nm = 7 if near else 4; clumps = 5 if near else 3; cards = 11 if near else 9
    R = sp["ratio"]; bole = sp["bole"]
    for i in range(nm):
        t = bole + (0.95 - bole) * (i + 0.5) / nm
        k = min(int(min(t, top) / top * (len(trunk) - 1)), len(trunk) - 2)
        start = trunk[k]
        az = i * math.radians(137.5) + rng.uniform(-.3, .3)
        el = math.radians(rng.uniform(*sp["elev"]))
        d = Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)))
        L = max(0.15, R * 1.1 * math.sin(math.pi * min(1, (t - bole) / (1 - bole) * 0.85 + 0.15)) / max(math.cos(el), 0.35) + (1 - t) * 0.2)
        L = min(L, (1.0 - start.z) / max(math.sin(el), 0.2) * 1.05 + R * 0.4)
        pts = _branch_pts(rng, start, d, L, 3, sp["curve"] * L, 0.06)
        _tube(BV, BF, BU, pts, [r0 * 0.5, r0 * 0.35, r0 * 0.2, r0 * 0.08], 4 if near else 3)
        for c in range(clumps):
            u_ = 0.35 + 0.65 * c / max(1, clumps - 1)
            p = pts[0].lerp(pts[-1], u_) + Vector((rng.gauss(0, .04), rng.gauss(0, .04), rng.gauss(0.02, .03)))
            size = sp["card"] * (4.2 if near else 5.5) * rng.uniform(0.8, 1.2)
            for _ in range(cards):
                c_ = p + Vector((rng.gauss(0, .045), rng.gauss(0, .045), rng.gauss(0, .035)))
                nrm = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.3, 1))).normalized()
                u, w = _frame(nrm); b = len(LV)
                for (a_, b_) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    LV.append(c_ + u * a_ * size / 2 + w * b_ * size / 2)
                LU.extend([(0, 0), (1, 0), (1, 1), (0, 1)]); LF.append((b, b + 1, b + 2, b + 3))
    return (BV, BF, BU), (LV, LF, LU)


WEB_TREE = {}
if _have_trees:
    for spn, sp in SPECIES.items():
        for lod in ("near", "far"):
            bark, leaf = gen_web_tree(sp, hash((spn, lod, "web")) & 0xffff, lod == "near")
            WEB_TREE[(spn, lod, "bark")] = _mesh(f"web {spn} {lod} bark", bark, MATS[f"Bark {spn}"])
            WEB_TREE[(spn, lod, "leaves")] = _mesh(f"web {spn} {lod} leaves", leaf, MATS[f"Leaves {spn}"])
    print("web trees:", {f"{k[0]} {k[1]} {k[2]}": len(m.polygons) * 2 for k, m in WEB_TREE.items() if k[2] == "leaves"},
          "bark tris near/far", len(WEB_TREE[("oak", "near", "bark")].polygons) * 2, len(WEB_TREE[("oak", "far", "bark")].polygons) * 2)
if _have_trees:
    holders = {}
    import random as _rnd
    _tree_es = [o for o in c_sur.objects if o.instance_type == 'COLLECTION' and o.instance_collection and o.instance_collection.name.startswith("tree ")]
    _rnd.Random(5).shuffle(_tree_es)      # random order: a viewer density slider (first N instances) thins evenly
    for _ti, e in enumerate(_tree_es):
        e.name = f"T{_ti:05d} {e.name}"
        cc = e.instance_collection
        spn_, lod_ = cc.name.split()[1], ("far" if (" Far tree" in e.name or " Sapling" in e.name) else "near")
        for so in cc.objects:
            kind_ = "leaves" if "leaves" in so.name else "bark"
            key = f"{spn_} {lod_} {kind_}"
            if key not in holders:
                h_ = bpy.data.objects.new(f"Trees {key}", None); c_sur.objects.link(h_); holders[key] = h_; tree_roots.append(h_)
            inst = bpy.data.objects.new(f"{e.name} {kind_}", WEB_TREE[(spn_, lod_, kind_)]); c_sur.objects.link(inst)
            inst.matrix_world = e.matrix_world
            inst.parent = holders[key]
        bpy.data.objects.remove(e)
    print(f"web: {sum(len(h.children) for h in holders.values())} tree instances under {len(holders)} holders")

# ================================================================== z-fighting: coplanar overlapping faces from different objects
def zfight_scan(objs, tol=0.001):
    """axis-aligned faces bucketed by (axis, direction, plane); returns overlapping pairs from different objects."""
    dg = bpy.context.evaluated_depsgraph_get()
    buckets = {}
    for ob in objs:
        try:
            me = ob.evaluated_get(dg).to_mesh()
        except Exception:
            continue
        mw = ob.matrix_world
        for p in me.polygons:
            nrm = (mw.to_3x3() @ p.normal).normalized()
            ax = max(range(3), key=lambda a: abs(nrm[a]))
            if abs(nrm[ax]) < 0.999 or p.area < 1e-6:
                continue
            vs = [mw @ me.vertices[i].co for i in p.vertices]
            if ax == 2 and nrm[2] < 0 and vs[0][2] <= 0.005:
                continue                 # bottoms resting on the slab are never seen
            pl = round(vs[0][ax] / tol)
            ua, va = [a for a in range(3) if a != ax]
            rect = (min(v[ua] for v in vs), max(v[ua] for v in vs), min(v[va] for v in vs), max(v[va] for v in vs))
            buckets.setdefault((ax, 1 if nrm[ax] > 0 else -1, pl), []).append((ob.name, rect))
        ob.evaluated_get(dg).to_mesh_clear()
    pairs = set()
    for key, lst in buckets.items():
        if len(lst) < 2:
            continue
        lst.sort(key=lambda r: r[1][0])
        for i, (na, ra) in enumerate(lst):
            for nb, rb in lst[i + 1:]:
                if rb[0] >= ra[1] - 1e-4:
                    break
                if na != nb and min(ra[3], rb[3]) - max(ra[2], rb[2]) > 1e-3 and min(ra[1], rb[1]) - max(ra[0], rb[0]) > 1e-3:
                    pairs.add((min(na, nb), max(na, nb), key[0], key[1]))
    return pairs


def obj_size(name):
    o = bpy.data.objects[name]; d = o.dimensions
    return d.x * d.y * d.z + 1e-9 * (d.x + d.y + d.z)


zf_objs = [o for o in bpy.data.objects if o.type == 'MESH' and not o.hide_render and o.visible_get()
           and not o.name.startswith(("Terrain", "Ground", "Trees", "Far tree", "Tree ", "Sapling", "Road", "Neighbor", "cut "))
           and not any(c_.name.startswith(("asset ", "tree ", "Asset Library", "Tree Library")) for c_ in o.users_collection)]
zf_before = zfight_scan(zf_objs)
moved = set(); pairs_ = zf_before
for pass_ in range(3):
    for (a, b, ax, sg) in sorted(pairs_):
        small = a if obj_size(a) < obj_size(b) else b
        if (small, ax, sg) in moved:
            small = b if small == a else a                     # already nudged this way: move the other one
            if (small, ax, sg) in moved:
                continue
        o = bpy.data.objects[small]
        off = Vector((0, 0, 0)); off[ax] = 0.0025 * sg        # 2.5 mm out along the shared face normal
        mw = o.matrix_world.copy(); mw.translation += off; o.matrix_world = mw
        moved.add((small, ax, sg))
    bpy.context.view_layer.update()
    pairs_ = zfight_scan(zf_objs)
    if not pairs_:
        break
zf_after = pairs_
print(f"z-fighting: {len(zf_before)} coplanar overlapping pairs before, {len(zf_after)} after ({len(moved)} parts nudged 2.5 mm)")
json.dump({"before": sorted([list(p) for p in zf_before])[:400], "after": sorted([list(p) for p in zf_after])[:400]},
          open(os.path.join(OUTD, "zfight_report.json"), "w"), indent=0)

# ================================================================== parts and export
def all_in(*colls):
    s = set()
    for c_ in colls:
        s |= set(c_.all_objects)
    return s


tree_set = set(tree_roots) | {ch for h in tree_roots for ch in h.children}
site = all_in(c_site) | all_in(c_util) | all_in(c_mark) | ({o for o in c_sur.objects} - tree_set)
furn = all_in(c_furn)
shell = all_in(c_ext) | all_in(c_roof) | all_in(c_win) | all_in(c_out) | all_in(c_xdet)
interior = (all_in(c_house) - shell - furn) | all_in(c_int) | all_in(c_ceil) | all_in(c_kit) | all_in(c_trim)
upper_node = group_node("SecondStory", upper_objs, c_ceil)


# ------------------------------------------------------------------ fewer draw calls: merge static meshes per material
def merge_static(objs, label):
    """join meshes that never move (not operable, not under a toggle node) into one mesh per material set."""
    dg = bpy.context.evaluated_depsgraph_get()

    def movable(o):
        p = o
        while p is not None:
            if p.get("operable"):
                return True
            p = p.parent
        return False
    groups = {}
    for o in objs:
        if o.type != 'MESH' or movable(o) or o.get("emissive_night") or o.name.startswith(("Spawn_",)):
            continue
        root = o.parent.name if o.parent is not None and o.parent.type == 'EMPTY' and o.parent.name in ("Roof", "Utilities", "SecondStory") else ""
        if o.parent is not None and not root:
            continue                     # parented to something else: keep as is
        mats = tuple(s.material.name if s.material else "" for s in o.material_slots)
        ceil_ = "ceiling" in o.name.lower()
        groups.setdefault((root, mats, ceil_), []).append(o)
    made = []
    for (root, mats, ceil_), lst in groups.items():
        if len(lst) < 2:
            continue
        bm = bmesh.new()
        for o in lst:
            me = o.evaluated_get(dg).to_mesh()
            tmp = me.copy(); tmp.transform(o.matrix_world)
            bm.from_mesh(tmp); bpy.data.meshes.remove(tmp)
            o.evaluated_get(dg).to_mesh_clear()
        nm_ = f"{label} {'ceiling ' if ceil_ else ''}{mats[0] if mats else 'mesh'}"
        me = bpy.data.meshes.new(nm_); bm.to_mesh(me); bm.free()
        for m_ in mats:
            me.materials.append(bpy.data.materials.get(m_) if m_ else None)
        ob = bpy.data.objects.new(nm_, me); lst[0].users_collection[0].objects.link(ob)
        if root:
            ob.parent = bpy.data.objects[root]
        for o in lst:
            bpy.data.objects.remove(o)
        made.append(ob)
    return made


roof_node = group_node("Roof", roof_objs, c_roof)
util_node = group_node("Utilities", util_objs, c_site)
# ---- performance: lighter furniture models, merged procedural furniture, lighter site
FURN_TRIS = WEB.get("furniture_model_tris", 6000)
for c_ in bpy.data.collections:
    if c_.name.startswith("asset "):
        for o in c_.all_objects:
            if o.type == 'MESH':
                t_ = sum(len(p.vertices) - 2 for p in o.data.polygons)
                if t_ > FURN_TRIS:
                    md = o.modifiers.new("web decimate", 'DECIMATE'); md.ratio = max(0.05, FURN_TRIS / t_)
for o in list(c_furn.all_objects):         # flatten procedural furniture groups so they can merge per material
    if o.type == 'MESH' and o.parent is not None and o.parent.type == 'EMPTY' and not o.parent.get("operable") and o.parent.instance_type != 'COLLECTION':
        mw = o.matrix_world.copy(); o.parent = None; o.matrix_world = mw
for o in [o for o in bpy.data.objects if o.type == 'CURVE' and (o.name.startswith(("Geothermal", "Septic")))]:
    o.data.bevel_resolution = 0            # 4-sided pipes are plenty in the browser
for oname, ratio in (("Terrain", WEB.get("terrain_ratio_perf", 0.15)), ("Terrain far", 0.3)):
    ob = bpy.data.objects.get(oname)
    if ob and "web decimate" in ob.modifiers:
        ob.modifiers["web decimate"].ratio = ratio
n0 = sum(1 for o in bpy.data.objects if o.type == 'MESH')
_fw_pre = [o for o in c_furn.objects if o.type == 'MESH' and o.parent is None and o.matrix_world.translation.x < (HW / 2) * F]
_fe_pre = [o for o in c_furn.objects if o.type == 'MESH' and o.parent is None and o.matrix_world.translation.x >= (HW / 2) * F]
merge_static(list(shell | set(roof_objs)), "Shell")
merge_static(list(interior | set(upper_objs)), "Interior")
merge_static(list(site | set(util_objs)), "Site")
# procedural furniture: merge per material in each half (west/east of the centre line), lamps' glowing parts stay separate
for o in _fw_pre + _fe_pre:
    if o.name in bpy.data.objects and (o.matrix_world @ Vector()).x < (HW / 2) * F:
        o["_half"] = "W"
merge_static([o for o in _fw_pre if o.name in bpy.data.objects and o.get("_half") == "W"], "Furniture W")
merge_static([o for o in _fe_pre if o.name in bpy.data.objects and o.get("_half") != "W"], "Furniture E")
print(f"web: merged static meshes {n0} -> {sum(1 for o in bpy.data.objects if o.type == 'MESH')} objects")
tree_set = set(tree_roots) | {ch for h in tree_roots for ch in h.children}
site = all_in(c_site) | all_in(c_util) | all_in(c_mark) | ({o for o in c_sur.objects} - tree_set)
shell = all_in(c_ext) | all_in(c_roof) | all_in(c_win) | all_in(c_out) | all_in(c_xdet)
furn = all_in(c_furn)
interior = (all_in(c_house) - shell - furn) | all_in(c_int) | all_in(c_ceil) | all_in(c_kit) | all_in(c_trim)
PARTS = [("site", site | {util_node}),
         ("trees", tree_set),
         ("shell", shell | {roof_node}),
         ("interior", interior | set(c_web.objects) | {upper_node})]
# furniture in two halves (west / east of the house centre line) to stay under the per-file limit
_fw, _fe = set(), set()
for o in c_furn.objects:
    if o.parent is not None:
        continue
    (_fw if o.matrix_world.translation.x < (HW / 2) * F else _fe).add(o)
PARTS += [("furniture_west", _fw), ("furniture_east", _fe)]


def with_family(objs):
    out = set()
    for o in objs:
        out.add(o)
        p = o.parent
        while p is not None:
            out.add(p); p = p.parent
        out |= set(o.children_recursive)
    return out


manifest = {"units": "metres", "up": "glTF Y-up (Blender Z-up converted by the exporter); extras use Blender world coords",
            "parts": [], "sky": "sky.jpg", "spawns": spawn_info, "eye_height_m": round(EYE * F, 3),
            "operable": sorted(o.name for o in bpy.data.objects if o.get("operable")),
            "floors": {"main": 0.0, "loft": round(C["loft"]["floor_height"] * F, 3),
                       "attic": round((C["ceilings"]["flat_height"] + FLOOR_T) * F, 3), "toggle_node": "SecondStory"},
            "lights": globals().get("LIGHTS", []),
            "trees": {"instance_order": "shuffled", "note": "show the first round(N*density) instances of each tree mesh for a density slider"},
            "zfight": {"before": len(zf_before), "after": len(zf_after)}}
if globals().get("DRIVE_ROUTE"):
    manifest["drive_route_plan_ft"] = DRIVE_ROUTE
az, el = math.radians(RC["sun_azimuth_deg"]), math.radians(RC["sun_elevation_deg"])
manifest["sun_direction"] = [round(math.sin(az) * math.cos(el), 4), round(math.cos(az) * math.cos(el), 4), round(math.sin(el), 4)]
for name, objs in PARTS:
    if ONLY and name not in ONLY:
        continue
    objs = {o for o in with_family(objs) if o.type in ('MESH', 'EMPTY', 'CURVE') and (o.type == 'EMPTY' or not o.hide_render)}
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        try:
            o.hide_set(False); o.select_set(True)
        except Exception:
            pass
    fp = os.path.join(OUTD, f"{name}.glb")
    kw = dict(filepath=fp, export_format='GLB', use_selection=True, export_apply=True, export_extras=True, export_yup=True,
              export_image_format='JPEG', export_jpeg_quality=WEB.get("jpeg_quality", 82), export_lights=False,
              export_cameras=False, export_animations=False, export_materials='EXPORT')
    if name == "trees":
        kw["export_gpu_instances"] = True
        kw["export_image_format"] = 'AUTO'      # leaf alpha needs PNG
    try:
        bpy.ops.export_scene.gltf(**kw)
    except TypeError:
        kw.pop("export_gpu_instances", None); bpy.ops.export_scene.gltf(**kw)
    sz = os.path.getsize(fp)
    manifest["parts"].append({"file": f"{name}.glb", "name": name, "bytes": sz})
    print(f"web part {name}: {len(objs)} objects, {sz / 1e6:.1f} MB")

# sky.jpg from the HDRI (Reinhard tone-mapped equirect)
try:
    hp = [i for i in bpy.data.images if i.filepath.lower().endswith(".hdr")][0]
    a = img_array(hp)[..., :3]
    a = a / (1 + a); a = np.clip(a ** (1 / 2.2) * 1.1, 0, 1)
    step = max(1, a.shape[1] // 2048)
    a = a[::step, ::step]
    sk = bpy.data.images.new("sky_out", a.shape[1], a.shape[0])
    sk.pixels.foreach_set(np.concatenate([a, np.ones(a.shape[:2] + (1,), np.float32)], -1).astype(np.float32).ravel())
    sk.filepath_raw = os.path.join(OUTD, "sky.jpg"); sk.file_format = 'JPEG'; sk.save()
except Exception as ex:
    print("sky export failed:", ex)
json.dump(manifest, open(os.path.join(OUTD, "manifest.json"), "w"), indent=1)
print("WEB EXPORT OK", OUTD, sum(p["bytes"] for p in manifest["parts"]) / 1e6, "MB")
