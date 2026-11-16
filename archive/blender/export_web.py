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
TEX_FURN = WEB.get("furniture_texture_px", 512)
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
        parts = objs_named(o["id"] + " glass") + objs_named(o["id"] + " kick rail")
        hx, hy = fr(o["start"] + 0.18, SKIN + 0.2)
        ax_ = Vector(P(*fr(o["start"] + 1, 0)) - P(*fr(o["start"], 0)))
        in_ = Vector(P(*fr(o["start"], 1)) - P(*fr(o["start"], 0)))
        sgn = 1 if ax_.cross(in_).z > 0 else -1
        ops.append(pivot(o["id"], parts, P(hx, hy, 0), {"operable": "swing", "open_angle": 90 * sgn, "axis": "z"}, c_win))
    elif o["kind"] == "slider":
        # bi-parting: the two middle panes slide outward over the fixed outer panes
        for g_ in objs_named(o["id"] + " glass"):
            bpy.data.objects.remove(g_)
        u0, u1, z0, z1 = o["start"], o["end"], o["sill"], o["head"]
        w4 = (u1 - u0) / 4; v0 = SKIN + 0.05
        for (a, b, nm, vv) in ((u0 + 0.09, u0 + w4, "fixed W", 0.4), (u1 - w4, u1 - 0.09, "fixed E", 0.4),
                               (u0 + w4, (u0 + u1) / 2 - 0.01, "leaf W", 0.55), ((u0 + u1) / 2 + 0.01, u1 - w4, "leaf E", 0.55)):
            g_ = wbox(f"{o['id']} glass {nm}", o["wall"], a, b, v0 + 0.3 * vv - 0.015, v0 + 0.3 * vv + 0.015, z0 + 0.12, z1 - 0.05, "Glass", c_win)
            if nm.startswith("leaf"):
                fx_ = wbox(f"{o['id']} {nm} frame", o["wall"], a, b, v0 + 0.3 * vv - 0.03, v0 + 0.3 * vv + 0.03, z0 + 0.06, z0 + 0.14, "Window Frame", c_win)
                sg = -1 if nm == "leaf W" else 1
                d = Vector(P(*fr(o["start"] + sg * w4, 0)) - P(*fr(o["start"], 0)))
                cx, cy = fr((a + b) / 2, v0 + 0.3 * vv)
                ops.append(pivot(f"{o['id']} {nm}", [g_, fx_], P(cx, cy, 0), {"operable": "slide", "slide": [round(d.x, 3), round(d.y, 3), 0.0]}, c_win))
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
if _have_trees:
    holders = {}
    for e in [o for o in c_sur.objects if o.instance_type == 'COLLECTION' and o.instance_collection and o.instance_collection.name.startswith("tree ")]:
        cc = e.instance_collection
        for so in cc.objects:
            key = so.name
            if key not in holders:
                h_ = bpy.data.objects.new(f"Trees {key}", None); c_sur.objects.link(h_); holders[key] = h_; tree_roots.append(h_)
            inst = bpy.data.objects.new(f"{e.name} {so.name.split()[-1]}", so.data); c_sur.objects.link(inst)
            inst.matrix_world = e.matrix_world
            inst.parent = holders[key]
        bpy.data.objects.remove(e)
    print(f"web: {sum(len(h.children) for h in holders.values())} tree instances under {len(holders)} holders")

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
PARTS = [("site", site | {group_node("Utilities", util_objs, c_site)}),
         ("trees", tree_set),
         ("shell", shell | {group_node("Roof", roof_objs, c_roof)}),
         ("interior", interior | set(c_web.objects))]
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
            "operable": sorted(o.name for o in bpy.data.objects if o.get("operable"))}
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
