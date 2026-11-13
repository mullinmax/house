"""
Heilman-Mullin Residence: parametric Blender model.

Everything comes from config.toml (dimensions, openings, finishes, utilities) and
data/traced_geometry.json (interior walls from the A-11 vector data, traced utility lines).

Run:
  blender --background --python build_house.py -- --config config.toml --save house.blend
  blender --background --python build_house.py -- --render stills          (preview stills)
  blender --background --python build_house.py -- --render exterior        (fly-around video)
  blender --background --python build_house.py -- --render interior        (walk-through video)
Options: --out DIR  --frames START:END  --samples N  --res WxH  --step N
Plan coordinates are feet: origin = outside NW slab corner, +x east, +y SOUTH.
Blender scene is meters: X east, Y north, Z up.
"""
import bpy, bmesh, math, json, os, sys, tomllib
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
F = 0.3048


# ------------------------------------------------------------------ args / config
def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    a = {"config": os.path.join(HERE, "config.toml"), "save": None, "render": None,
         "out": os.path.join(HERE, "renders"), "frames": None, "samples": None, "res": None, "step": 1}
    i = 0
    while i < len(argv):
        k = argv[i].lstrip("-")
        a[k] = argv[i + 1] if i + 1 < len(argv) else True
        i += 2
    a["out"] = os.path.abspath(a["out"])   # Blender resolves relative render paths oddly with no .blend open
    return a


ARGS = parse_args()
with open(ARGS["config"], "rb") as fh:
    C = tomllib.load(fh)
with open(os.path.join(HERE, C["house"]["int_wall_source"])) as fh:
    G = json.load(fh)

HW, HD, T = C["house"]["width_x"], C["house"]["depth_y"], C["house"]["ext_wall_thickness"]
R = C["roof"]
PN = R["north_pitch"] / 12.0
PS = R["south_pitch"] / 12.0
YC = R["clerestory_wall_y"]          # north face of clerestory wall
YC2 = YC + T                          # south face
H_N = R["north_wall_height"]
H_S = R["south_wall_height"]
H_CL = H_S + (HD - YC2) * PS          # where the low roof meets the clerestory wall


def north_roof_z(y):  # underside of the high roof
    return H_N + y * PN


def south_roof_z(y):  # underside of the low roof
    return H_S + (HD - y) * PS


def roof_under(y):
    return north_roof_z(y) if y <= YC2 + 1e-6 else south_roof_z(y)


def P(x, y, z=0.0):
    return Vector((x * F, -y * F, z * F))


def hexcol(h, a=1.0):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c]
    return (*c, a)


# ------------------------------------------------------------------ scene reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'IMPERIAL'
scene.unit_settings.length_unit = 'FEET'
COLS = {}


def col(name, parent=None):
    if name in COLS:
        return COLS[name]
    c = bpy.data.collections.new(name)
    (parent or scene.collection).children.link(c)
    COLS[name] = c
    return c


# ------------------------------------------------------------------ materials
MATS = {}


def node_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, m.node_tree.nodes, m.node_tree.links, m.node_tree.nodes["Principled BSDF"]


def simple(name, color, rough=0.5, metal=0.0, **kw):
    m, n, l, b = node_mat(name)
    b.inputs["Base Color"].default_value = hexcol(color) if isinstance(color, str) else color
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    for k, v in kw.items():
        if k in b.inputs:
            b.inputs[k].default_value = v
    MATS[name] = m
    return m


def mat_siding():
    M = C["materials"]
    m, n, l, b = node_mat("Siding")
    b.inputs["Base Color"].default_value = hexcol(M["siding_color"])
    b.inputs["Roughness"].default_value = 0.75
    # LP SmartSide cedar-grain embossing: noise stretched vertically (grain runs up the boards)
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (30.0, 30.0, 1.2)
    l.new(tc.outputs["Object"], mp.inputs["Vector"])
    grain = n.new("ShaderNodeTexNoise"); grain.inputs["Scale"].default_value = 6.0
    grain.inputs["Detail"].default_value = 6.0; grain.inputs["Roughness"].default_value = 0.6
    l.new(mp.outputs["Vector"], grain.inputs["Vector"])
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.35; bump.inputs["Distance"].default_value = 0.004
    l.new(grain.outputs["Fac"], bump.inputs["Height"])
    l.new(bump.outputs[0], b.inputs["Normal"])
    # slight tone variation so large walls do not look flat
    var = n.new("ShaderNodeTexNoise"); var.inputs["Scale"].default_value = 1.5
    l.new(tc.outputs["Object"], var.inputs["Vector"])
    mix = n.new("ShaderNodeMix"); mix.data_type = 'RGBA'; mix.inputs["Factor"].default_value = 0.0
    fac = n.new("ShaderNodeMath"); fac.operation = 'MULTIPLY'; fac.inputs[1].default_value = 0.12
    l.new(var.outputs["Fac"], fac.inputs[0]); l.new(fac.outputs[0], mix.inputs["Factor"])
    mix.inputs[6].default_value = hexcol(M["siding_color"]); mix.inputs[7].default_value = (0.05, 0.06, 0.04, 1)
    l.new(mix.outputs[2], b.inputs["Base Color"])
    MATS["Siding"] = m


def mat_floor():
    M = C["materials"]
    m, n, l, b = node_mat("Stained Concrete")
    tc = n.new("ShaderNodeTexCoord")
    noise = n.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 0.6; noise.inputs["Detail"].default_value = 8
    l.new(tc.outputs["Object"], noise.inputs["Vector"])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = hexcol(M["floor_color_2"]); ramp.color_ramp.elements[1].color = hexcol(M["floor_color"])
    ramp.color_ramp.elements[0].position = 0.35; ramp.color_ramp.elements[1].position = 0.7
    l.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    # diagonal saw cuts in object space (meters)
    sep = n.new("ShaderNodeSeparateXYZ"); l.new(tc.outputs["Object"], sep.inputs[0])
    sp = C["materials"]["floor_cut_spacing"] * F * math.sqrt(2)
    def diag(sign):
        a = n.new("ShaderNodeMath"); a.operation = 'MULTIPLY'; a.inputs[1].default_value = sign
        l.new(sep.outputs[1], a.inputs[0])
        s = n.new("ShaderNodeMath"); s.operation = 'ADD'; l.new(sep.outputs[0], s.inputs[0]); l.new(a.outputs[0], s.inputs[1])
        # shift so a diamond point lands on floor_cut_origin (plan feet); Blender Y = -plan y
        ox, oy = C["materials"].get("floor_cut_origin", [0.0, 0.0])
        off = n.new("ShaderNodeMath"); off.operation = 'ADD'; l.new(s.outputs[0], off.inputs[0])
        off.inputs[1].default_value = -(ox * F + sign * (-oy * F)) + 1000 * sp   # +1000 periods keeps the value positive
        d = n.new("ShaderNodeMath"); d.operation = 'PINGPONG'; l.new(off.outputs[0], d.inputs[0]); d.inputs[1].default_value = sp / 2
        lt = n.new("ShaderNodeMath"); lt.operation = 'LESS_THAN'; l.new(d.outputs[0], lt.inputs[0]); lt.inputs[1].default_value = 0.005
        return lt
    c1 = diag(1.0)
    cuts = c1
    if C["materials"]["floor_cut_pattern"] == "diamond":
        c2 = diag(-1.0)
        mx = n.new("ShaderNodeMath"); mx.operation = 'MAXIMUM'; l.new(c1.outputs[0], mx.inputs[0]); l.new(c2.outputs[0], mx.inputs[1])
        cuts = mx
    mix = n.new("ShaderNodeMix"); mix.data_type = 'RGBA'
    l.new(cuts.outputs[0], mix.inputs[0]); l.new(ramp.outputs[0], mix.inputs[6]); mix.inputs[7].default_value = (0.03, 0.015, 0.01, 1)
    l.new(mix.outputs[2], b.inputs["Base Color"])
    rough = n.new("ShaderNodeMath"); rough.operation = 'ADD'; rough.inputs[1].default_value = M["floor_gloss"]
    rn = n.new("ShaderNodeMath"); rn.operation = 'MULTIPLY'; rn.inputs[1].default_value = 0.25
    l.new(noise.outputs["Fac"], rn.inputs[0]); l.new(rn.outputs[0], rough.inputs[0])
    l.new(rough.outputs[0], b.inputs["Roughness"])
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.5; bump.inputs["Distance"].default_value = 0.003
    inv = n.new("ShaderNodeMath"); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0; l.new(cuts.outputs[0], inv.inputs[1])
    l.new(inv.outputs[0], bump.inputs["Height"]); l.new(bump.outputs[0], b.inputs["Normal"])
    MATS["Stained Concrete"] = m


def mat_oak(name="White Oak"):
    m, n, l, b = node_mat(name)
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1, 1, 18)
    l.new(tc.outputs["Object"], mp.inputs[0])
    wave = n.new("ShaderNodeTexWave"); wave.inputs["Scale"].default_value = 6; wave.inputs["Distortion"].default_value = 6
    wave.inputs["Detail"].default_value = 3
    l.new(mp.outputs[0], wave.inputs[0])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = hexcol("#B89466"); ramp.color_ramp.elements[1].color = hexcol("#D7BE96")
    l.new(wave.outputs["Fac"], ramp.inputs[0]); l.new(ramp.outputs[0], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.45
    MATS[name] = m


def mat_grass():
    m, n, l, b = node_mat("Grass")
    tc = n.new("ShaderNodeTexCoord")
    noise = n.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 0.08; noise.inputs["Detail"].default_value = 10
    l.new(tc.outputs["Object"], noise.inputs["Vector"])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = hexcol("#4E6B2E"); ramp.color_ramp.elements[1].color = hexcol("#7C8F45")
    l.new(noise.outputs["Fac"], ramp.inputs[0]); l.new(ramp.outputs[0], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.95
    n2 = n.new("ShaderNodeTexNoise"); n2.inputs["Scale"].default_value = 40
    l.new(tc.outputs["Object"], n2.inputs["Vector"])
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.4
    l.new(n2.outputs["Fac"], bump.inputs["Height"]); l.new(bump.outputs[0], b.inputs["Normal"])
    MATS["Grass"] = m


def mat_gravel():
    m, n, l, b = node_mat("Gravel")
    b.inputs["Roughness"].default_value = 0.95
    tc = n.new("ShaderNodeTexCoord")
    vor = n.new("ShaderNodeTexVoronoi"); vor.inputs["Scale"].default_value = 90.0
    l.new(tc.outputs["Object"], vor.inputs["Vector"])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = hexcol("#6E675D"); ramp.color_ramp.elements[1].color = hexcol("#B9B2A6")
    l.new(vor.outputs["Distance"], ramp.inputs["Fac"]); l.new(ramp.outputs[0], b.inputs["Base Color"])
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.8; bump.inputs["Distance"].default_value = 0.01
    l.new(vor.outputs["Distance"], bump.inputs["Height"]); l.new(bump.outputs[0], b.inputs["Normal"])
    MATS["Gravel"] = m


def mat_roof():
    m, n, l, b = node_mat("Standing Seam")
    b.inputs["Base Color"].default_value = hexcol(C["materials"]["roof_color"])
    b.inputs["Metallic"].default_value = 0.6; b.inputs["Roughness"].default_value = 0.4
    tc = n.new("ShaderNodeTexCoord"); sep = n.new("ShaderNodeSeparateXYZ"); l.new(tc.outputs["Object"], sep.inputs[0])
    dv = n.new("ShaderNodeMath"); dv.operation = 'DIVIDE'; dv.inputs[1].default_value = 16 / 12 * F
    l.new(sep.outputs[0], dv.inputs[0])
    fr = n.new("ShaderNodeMath"); fr.operation = 'FRACT'; l.new(dv.outputs[0], fr.inputs[0])
    lt = n.new("ShaderNodeMath"); lt.operation = 'LESS_THAN'; lt.inputs[1].default_value = 0.05; l.new(fr.outputs[0], lt.inputs[0])
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 1.0; bump.inputs["Distance"].default_value = 0.03
    l.new(lt.outputs[0], bump.inputs["Height"]); l.new(bump.outputs[0], b.inputs["Normal"])
    MATS["Standing Seam"] = m


def mat_glass(name="Glass", rough=0.0, tint="#DDE6E8"):
    m, n, l, b = node_mat(name)
    b.inputs["Base Color"].default_value = hexcol(tint)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["IOR"].default_value = 1.45
    MATS[name] = m


def mat_emit(name, color, strength=1.0, alpha=1.0):
    m, n, l, b = node_mat(name)
    b.inputs["Base Color"].default_value = hexcol(color)
    b.inputs["Emission Color"].default_value = hexcol(color)
    b.inputs["Emission Strength"].default_value = strength
    b.inputs["Alpha"].default_value = alpha
    MATS[name] = m


M = C["materials"]
mat_siding(); mat_floor(); mat_oak(); mat_grass(); mat_roof(); mat_glass(); mat_glass("Polycarbonate", 0.2, "#F2F2EE"); MATS["Polycarbonate"].node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = 0.45
simple("Trim", M["trim_color"], 0.5)
simple("Window Frame", M["window_exterior_color"], 0.35, 0.3)
simple("Drywall", M["wall_paint"], 0.85)
simple("Concrete", "#A7A49E", 0.8)
mat_gravel()
simple("Stainless", "#C8CACC", 0.25, 1.0)
simple("Porcelain", "#F4F4F2", 0.15)
simple("Counter", C["kitchen"]["counter_color"], 0.25)
simple("Island", C["kitchen"]["island_color"], 0.5)
simple("Cabinet Wood", C["kitchen"]["cabinet_wood"], 0.5)
simple("Garage Door", "#2A2A2A", 0.5)
simple("Black Metal", "#151515", 0.4, 0.6)
mat_emit("Geothermal Marker", C["utilities"]["geothermal_color"], 2.0)
mat_emit("Septic Marker", C["utilities"]["septic_color"], 2.0)
mat_emit("Geothermal Pipe", C["utilities"]["geothermal_color"], 0.5)
mat_emit("Septic Pipe", C["utilities"]["septic_color"], 0.5)
simple("Soil", "#5B4632", 0.95)


# ------------------------------------------------------------------ geometry helpers
def mesh_obj(name, verts, faces, mat, collection, mats=None, face_mats=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.validate()
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    for mm in (mats or [mat]):
        ob.data.materials.append(MATS[mm] if isinstance(mm, str) else mm)
    if face_mats:
        for i, p in enumerate(me.polygons):
            p.material_index = face_mats[i]
    if len(faces) > 1:
        fix_normals(ob)   # plan y is mirrored into Blender -Y, so winding must be recomputed
    return ob


def box(name, x0, x1, y0, y1, z0, z1, mat, collection, ztop=None):
    """Axis-aligned box in plan feet. ztop(x, y) optional to slope the top."""
    xs, ys = sorted((x0, x1)), sorted((y0, y1))
    zt = (lambda x, y: z1) if ztop is None else ztop
    v = [P(xs[0], ys[0], z0), P(xs[1], ys[0], z0), P(xs[1], ys[1], z0), P(xs[0], ys[1], z0),
         P(xs[0], ys[0], zt(xs[0], ys[0])), P(xs[1], ys[0], zt(xs[1], ys[0])),
         P(xs[1], ys[1], zt(xs[1], ys[1])), P(xs[0], ys[1], zt(xs[0], ys[1]))]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return mesh_obj(name, v, f, mat, collection)


def prism_x(name, x0, x1, prof, mat, collection):
    """Extrude a (y, z) profile polygon along x."""
    n = len(prof)
    v = [P(x0, y, z) for y, z in prof] + [P(x1, y, z) for y, z in prof]
    f = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        f.append((i, j, n + j, n + i))
    ob = mesh_obj(name, v, f, mat, collection)
    fix_normals(ob)
    return ob


def fix_normals(ob):
    bm = bmesh.new(); bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data); bm.free()


def tube(name, pts, z, radius, mat, collection):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'
    sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
    for i, (x, y) in enumerate(pts):
        p = P(x, y, z); sp.points[i].co = (p.x, p.y, p.z, 1)
    cu.bevel_depth = radius * F; cu.bevel_resolution = 3; cu.use_fill_caps = True
    ob = bpy.data.objects.new(name, cu); collection.objects.link(ob)
    ob.data.materials.append(MATS[mat])
    return ob


def ribbon(name, pts, z, width, mat, collection):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '2D'
    sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
    for i, (x, y) in enumerate(pts):
        sp.points[i].co = (x * F, -y * F, 0, 1)
    cu.extrude = 0.0; cu.offset = 0.0
    ob = bpy.data.objects.new(name, cu)
    collection.objects.link(ob)
    # use a thin tube flattened in z as a painted ribbon
    cu.dimensions = '3D'; cu.bevel_depth = width / 2 * F; cu.bevel_resolution = 0
    ob.scale = (1, 1, 1)
    ob.location.z = z * F
    ob.data.materials.append(MATS[mat])
    return ob


# ------------------------------------------------------------------ collections
c_house = col("House")
c_ext = col("Exterior Walls", c_house); c_int = col("Interior Walls", c_house)
c_roof = col("Roof", c_house); c_win = col("Windows and Doors", c_house)
c_ceil = col("Ceilings and Loft", c_house); c_kit = col("Kitchen and Fixtures", c_house)
c_out = col("Garage Porch Greenhouse"); c_site = col("Site")
c_util = col("Buried Utilities"); c_mark = col("Utility Surface Markers")
c_cut = col("Opening Cutters"); c_cam = col("Cameras and Lights")
c_cut.hide_render = True

# ------------------------------------------------------------------ slab & site
GROUND_Z = -0.6
box("Slab", 0, HW, 0, HD, -C["house"]["slab_thickness"], 0, "Stained Concrete", c_house)
# exposed slab edge outside the walls is plain concrete, not the stained interior finish
for (a0, a1, b0, b1) in ((-0.02, HW + 0.02, -0.02, 0.0), (-0.02, HW + 0.02, HD, HD + 0.02), (-0.02, 0.0, 0, HD), (HW, HW + 0.02, 0, HD)):
    box("Slab edge", a0, a1, b0, b1, -0.62, 0.0, "Concrete", c_house)

# ------------------------------------------------------------------ terrain (real ground, see make_terrain.py)
TER = C.get("terrain", {})
TERRAIN = None
_tdir = os.path.join(HERE, "data", "terrain")
if TER.get("enabled") and os.path.exists(os.path.join(_tdir, "dem.npy")):
    import numpy as np
    _meta = json.load(open(os.path.join(_tdir, "meta.json")))
    _dem = np.load(os.path.join(_tdir, "dem.npy")).astype(np.float64)
    TX0, TY0, TX1, TY1 = _meta["extent_plan_ft"]; TSTEP = _meta["grid_ft"]
    SLAB_ELEV = TER.get("slab_top_elev_ft") or _meta["suggested_slab_top_elev_ft"]
    _Z = _dem - SLAB_ELEV                       # plan z: feet above slab top
    _xs = TX0 + np.arange(_dem.shape[1]) * TSTEP; _ys = TY0 + np.arange(_dem.shape[0]) * TSTEP
    _GX, _GY = np.meshgrid(_xs, _ys)
    # graded pads: flat ground just under the slab edge around every structure, blended back to natural grade
    _pads = [(0, 0, HW, HD), (-4, 37.4, 0, 41.4), (7, 52, 13, 56), (17, 52, 29, 56)]
    for _k in ("garage", "porch", "greenhouse"):
        if C[_k]["enabled"]:
            _pads.append(tuple(C[_k]["rect"]))
    if C["garage"]["enabled"]:
        _g = C["garage"]["rect"]; _pads.append((_g[0], _g[3], _g[2], _g[3] + C["garage"]["driveway_depth"]))
    _buf, _blend = TER.get("grade_buffer_ft", 3.0), TER.get("grade_blend_ft", 25.0)
    _d = np.full(_Z.shape, 1e9)
    for (a0, b0, a1, b1) in _pads:
        dx = np.maximum(np.maximum(a0 - _buf - _GX, _GX - a1 - _buf), 0)
        dy = np.maximum(np.maximum(b0 - _buf - _GY, _GY - b1 - _buf), 0)
        _d = np.minimum(_d, np.hypot(dx, dy))
    _w = np.clip(_d / _blend, 0, 1); _w = _w * _w * (3 - 2 * _w)
    PAD_Z = GROUND_Z - 0.02
    _Z = PAD_Z + (_Z - PAD_Z) * _w
    TERRAIN = {"Z": _Z, "x0": TX0, "y0": TY0, "x1": TX1, "y1": TY1, "step": TSTEP, "far": None}
    if os.path.exists(os.path.join(_tdir, "far_dem.npy")) and TER.get("far_area_ft"):
        _fm = json.load(open(os.path.join(_tdir, "far_meta.json")))
        _fz = np.load(os.path.join(_tdir, "far_dem.npy")).astype(np.float64) - SLAB_ELEV
        fx0_, fy0_, fx1_, fy1_ = _fm["extent_plan_ft"]
        TERRAIN["far"] = {"Z": _fz, "x0": fx0_, "y0": fy0_, "x1": fx1_, "y1": fy1_, "step": _fm["grid_ft"]}
    print(f"terrain: {_Z.shape} grid, slab top {SLAB_ELEV:.2f} ft NAVD88, local z {_Z.min():.1f}..{_Z.max():.1f} ft")


def ground_z(x, y):
    """finished ground height (plan ft above slab top) at plan x, y."""
    if TERRAIN is None:
        return GROUND_Z
    T_ = TERRAIN
    if T_.get("far") and not (T_["x0"] <= x <= T_["x1"] and T_["y0"] <= y <= T_["y1"]):
        T_ = T_["far"]               # outside the detailed square: coarse far-ring DEM
    Z, s = T_["Z"], T_["step"]
    fx = min(max((x - T_["x0"]) / s, 0), Z.shape[1] - 1.001)
    fy = min(max((y - T_["y0"]) / s, 0), Z.shape[0] - 1.001)
    i, j = int(fy), int(fx); dx, dy = fx - j, fy - i
    return float(Z[i, j] * (1 - dx) * (1 - dy) + Z[i, j + 1] * dx * (1 - dy) + Z[i + 1, j] * (1 - dx) * dy + Z[i + 1, j + 1] * dx * dy)


def densify(pts, step=4.0):
    out = [tuple(pts[0])]
    for (a, b) in zip(pts[:-1], pts[1:]):
        n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / step))
        out += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(1, n + 1)]
    return out


def drape_rect(name, x0, x1, y0, y1, lift, mat, collection, step=2.0):
    """flat-topped patch (driveway, gravel) that follows the terrain."""
    nx, ny = max(1, int(round((x1 - x0) / step))), max(1, int(round((y1 - y0) / step)))
    v = [P(x0 + (x1 - x0) * i / nx, y0 + (y1 - y0) * j / ny, ground_z(x0 + (x1 - x0) * i / nx, y0 + (y1 - y0) * j / ny) + lift)
         for j in range(ny + 1) for i in range(nx + 1)]
    f = [(j * (nx + 1) + i, (j + 1) * (nx + 1) + i, (j + 1) * (nx + 1) + i + 1, j * (nx + 1) + i + 1) for j in range(ny) for i in range(nx)]
    return mesh_obj(name, v, f, mat, collection)


def drape_ribbon(name, pts, width, lift, mat, collection, offset=0.0):
    """flat strip of given width along a plan polyline, following the terrain."""
    pts = densify(pts, 3.0)
    v, f = [], []
    for k, (x, y) in enumerate(pts):
        a = pts[max(k - 1, 0)]; b = pts[min(k + 1, len(pts) - 1)]
        tx, ty = b[0] - a[0], b[1] - a[1]; L = math.hypot(tx, ty) or 1.0
        nx, ny = -ty / L, tx / L
        for s in (-1, 1):
            px, py = x + nx * (offset + s * width / 2), y + ny * (offset + s * width / 2)
            v.append(P(px, py, ground_z(px, py) + lift))
        if k:
            f.append((2 * k - 2, 2 * k - 1, 2 * k + 1, 2 * k))
    return mesh_obj(name, v, f, mat, collection) if f else None


def mat_terrain():
    m, n, l, b = node_mat("Terrain")
    b.inputs["Roughness"].default_value = 0.95
    uv = n.new("ShaderNodeUVMap"); uv.uv_map = "UV"
    img = n.new("ShaderNodeTexImage"); img.image = bpy.data.images.load(os.path.join(_tdir, "ortho.jpg"))
    img.interpolation = 'Cubic'; img.extension = 'EXTEND'
    l.new(uv.outputs[0], img.inputs[0])
    # mowed lawn near the house (the 2023 photo shows a crop field there)
    g = MATS["Grass"].node_tree.nodes
    tc = n.new("ShaderNodeTexCoord")
    noise = n.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 0.08; noise.inputs["Detail"].default_value = 10
    l.new(tc.outputs["Object"], noise.inputs["Vector"])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = hexcol("#4E6B2E"); ramp.color_ramp.elements[1].color = hexcol("#7C8F45")
    l.new(noise.outputs["Fac"], ramp.inputs[0])
    # NAIP is hazy and blue-ish under the sky light: warm it, add saturation and contrast
    hsv = n.new("ShaderNodeHueSaturation"); hsv.inputs["Saturation"].default_value = 1.15; hsv.inputs["Value"].default_value = 0.85
    hsv.inputs["Hue"].default_value = 0.46
    l.new(img.outputs["Color"], hsv.inputs["Color"])
    bc = n.new("ShaderNodeBrightContrast"); bc.inputs["Contrast"].default_value = 0.25
    l.new(hsv.outputs[0], bc.inputs["Color"])
    at = n.new("ShaderNodeAttribute"); at.attribute_name = "lawn"
    # ragged lawn edge instead of a clean circle
    en = n.new("ShaderNodeTexNoise"); en.inputs["Scale"].default_value = 0.35; en.inputs["Detail"].default_value = 4
    l.new(tc.outputs["Object"], en.inputs["Vector"])
    e1 = n.new("ShaderNodeMath"); e1.operation = 'SUBTRACT'; e1.inputs[1].default_value = 0.5; l.new(en.outputs["Fac"], e1.inputs[0])
    e2 = n.new("ShaderNodeMath"); e2.operation = 'MULTIPLY_ADD'; e2.inputs[1].default_value = 0.9
    l.new(e1.outputs[0], e2.inputs[0]); l.new(at.outputs["Fac"], e2.inputs[2])
    e3 = n.new("ShaderNodeMapRange"); e3.inputs["From Min"].default_value = 0.2; e3.inputs["From Max"].default_value = 0.8
    l.new(e2.outputs[0], e3.inputs["Value"])
    mix = n.new("ShaderNodeMix"); mix.data_type = 'RGBA'
    l.new(e3.outputs["Result"], mix.inputs[0]); l.new(bc.outputs[0], mix.inputs[6]); l.new(ramp.outputs[0], mix.inputs[7])
    l.new(mix.outputs[2], b.inputs["Base Color"])
    n2 = n.new("ShaderNodeTexNoise"); n2.inputs["Scale"].default_value = 40
    l.new(tc.outputs["Object"], n2.inputs["Vector"])
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.3
    l.new(n2.outputs["Fac"], bump.inputs["Height"]); l.new(bump.outputs[0], b.inputs["Normal"])
    MATS["Terrain"] = m


def build_terrain():
    Z = TERRAIN["Z"]; R_, C_ = Z.shape; s = TERRAIN["step"]
    import numpy as np
    jj, ii = np.meshgrid(np.arange(C_), np.arange(R_))
    X = TERRAIN["x0"] + jj * s; Y = TERRAIN["y0"] + ii * s
    verts = np.stack([X * F, -Y * F, Z * F], -1).reshape(-1, 3)
    idx = (ii * C_ + jj)[:-1, :-1].ravel()
    faces = np.stack([idx, idx + C_, idx + C_ + 1, idx + 1], -1)
    me = bpy.data.meshes.new("Terrain")
    me.from_pydata(verts.tolist(), [], faces.tolist())
    uvv = np.stack([(X - TERRAIN["x0"]) / (TERRAIN["x1"] - TERRAIN["x0"]),
                    1 - (Y - TERRAIN["y0"]) / (TERRAIN["y1"] - TERRAIN["y0"])], -1).reshape(-1, 2)
    uvl = me.uv_layers.new(name="UV")
    uvl.data.foreach_set("uv", uvv[faces.ravel()].ravel())
    lr, lb = TER.get("lawn_radius_ft", 90.0), TER.get("lawn_blend_ft", 40.0)
    dx = np.maximum(np.maximum(-X, X - HW), 0); dy = np.maximum(np.maximum(-Y, Y - HD), 0)
    if C["garage"]["enabled"]:
        g_ = C["garage"]["rect"]
        dx2 = np.maximum(np.maximum(g_[0] - X, X - g_[2]), 0); dy2 = np.maximum(np.maximum(g_[1] - Y, Y - g_[3]), 0)
        dist = np.minimum(np.hypot(dx, dy), np.hypot(dx2, dy2))
    else:
        dist = np.hypot(dx, dy)
    lawn = 1 - np.clip((dist - lr) / lb, 0, 1)
    at = me.attributes.new("lawn", 'FLOAT', 'POINT'); at.data.foreach_set("value", lawn.ravel().astype(np.float32))
    me.polygons.foreach_set("use_smooth", np.ones(len(faces), bool))
    me.update()
    ob = bpy.data.objects.new("Terrain", me); c_site.objects.link(ob)
    mat_terrain(); ob.data.materials.append(MATS["Terrain"])
    FT = TERRAIN.get("far")
    if FT is not None:
        # far ring: real coarse DEM + NAIP photo out to ~3000 ft, the detailed square sits on top of it
        fz = FT["Z"]; fs = FT["step"]; fr_, fc_ = fz.shape
        jj2, ii2 = np.meshgrid(np.arange(fc_), np.arange(fr_))
        FX = FT["x0"] + jj2 * fs; FY = FT["y0"] + ii2 * fs
        inside = (FX > TERRAIN["x0"] + 0.01) & (FX < TERRAIN["x1"] - 0.01) & (FY > TERRAIN["y0"] + 0.01) & (FY < TERRAIN["y1"] - 0.01)
        edge = (FX >= TERRAIN["x0"] - 0.01) & (FX <= TERRAIN["x1"] + 0.01) & (FY >= TERRAIN["y0"] - 0.01) & (FY <= TERRAIN["y1"] + 0.01) & ~inside
        FZ = fz.copy()
        FZ[inside] -= 4.0
        for (r_, c_) in np.argwhere(edge):
            FZ[r_, c_] = ground_z(float(FX[r_, c_]), float(FY[r_, c_])) - 0.05
        fv = np.stack([FX * F, -FY * F, FZ * F], -1).reshape(-1, 3)
        fidx = (ii2 * fc_ + jj2)[:-1, :-1].ravel()
        ff = np.stack([fidx, fidx + fc_, fidx + fc_ + 1, fidx + 1], -1)
        fme = bpy.data.meshes.new("Terrain far"); fme.from_pydata(fv.tolist(), [], ff.tolist())
        fuv = np.stack([(FX - FT["x0"]) / (FT["x1"] - FT["x0"]), 1 - (FY - FT["y0"]) / (FT["y1"] - FT["y0"])], -1).reshape(-1, 2)
        ul = fme.uv_layers.new(name="UV"); ul.data.foreach_set("uv", fuv[ff.ravel()].ravel())
        fme.polygons.foreach_set("use_smooth", np.ones(len(ff), bool)); fme.update()
        fob = bpy.data.objects.new("Terrain far", fme); c_site.objects.link(fob)
        fm_ = MATS["Terrain"].copy(); fm_.name = "Terrain far"
        for nd in fm_.node_tree.nodes:
            if nd.bl_idname == "ShaderNodeTexImage":
                nd.image = bpy.data.images.load(os.path.join(_tdir, "far_ortho.jpg"))
            if nd.bl_idname == "ShaderNodeAttribute":
                nd.attribute_name = "none"          # no lawn out here
        MATS["Terrain far"] = fm_; fob.data.materials.append(fm_)
        TERRAIN["x0f"], TERRAIN["x1f"], TERRAIN["y0f"], TERRAIN["y1f"] = FT["x0"], FT["x1"], FT["y0"], FT["y1"]
    # coarse skirt out to the horizon at the edge elevation so the square does not end in a cliff
    big, st = 4000.0, 100.0
    if FT is not None:     # skirt now rings the far square instead
        big, st = 16000.0, 500.0
        TERRAIN_SK = (FT["x0"], FT["x1"], FT["y0"], FT["y1"])
    else:
        TERRAIN_SK = (TERRAIN["x0"], TERRAIN["x1"], TERRAIN["y0"], TERRAIN["y1"])
    sx0, sx1, sy0, sy1 = TERRAIN_SK
    gx = np.arange(sx0 - big, sx1 + big + 1, st); gy = np.arange(sy0 - big, sy1 + big + 1, st)
    v, f = [], []
    for y in gy:
        for x in gx:
            cxl = min(max(x, sx0), sx1); cyl = min(max(y, sy0), sy1)
            inside = sx0 < x < sx1 and sy0 < y < sy1
            v.append(P(x, y, ground_z(cxl, cyl) - (6.0 if inside else 0.25)))
    nx = len(gx)
    for j in range(len(gy) - 1):
        for i in range(nx - 1):
            f.append((j * nx + i, (j + 1) * nx + i, (j + 1) * nx + i + 1, j * nx + i + 1))
    sk = mesh_obj("Ground skirt", v, f, "Grass", c_site)
    return ob


if TERRAIN is not None:
    build_terrain()
else:
    bpy.ops.mesh.primitive_plane_add(size=600 * F, location=P(40, 40, GROUND_Z))
    g = bpy.context.active_object; g.name = "Ground"
    for c in g.users_collection: c.objects.unlink(g)
    c_site.objects.link(g); g.data.materials.append(MATS["Grass"])

# exterior concrete pads (A-11): 4x12 at south doors, 4x4 at west/east doors
box("Pad south kitchen", 7.0, 13.0, 52, 56, GROUND_Z, -0.05, "Concrete", c_site)
box("Pad south bi-part", 17.0, 29.0, 52, 56, GROUND_Z, -0.05, "Concrete", c_site)
box("Pad west door", -4, 0, 37.4, 41.4, GROUND_Z, -0.05, "Concrete", c_site)

# ------------------------------------------------------------------ exterior walls
SKIN = 0.06   # siding layer thickness (ft)
BAT_T = C["materials"].get("batten_thickness_in", 0.75) / 12   # batten projection


def wall_profile_EW():
    return [(0, 0), (HD, 0), (HD, H_S), (YC2, H_CL), (YC2, north_roof_z(YC2)), (0, H_N)]


def make_ext_walls():
    walls = {}
    # north
    walls["N"] = [box("Wall N siding", 0, HW, 0, SKIN, 0, H_N, "Siding", c_ext),
                  box("Wall N core", 0, HW, SKIN, T, 0, H_N, "Drywall", c_ext, ztop=lambda x, y: north_roof_z(y))]
    walls["S"] = [box("Wall S siding", 0, HW, HD - SKIN, HD, 0, H_S, "Siding", c_ext),
                  box("Wall S core", 0, HW, HD - T, HD - SKIN, 0, H_S, "Drywall", c_ext)]
    prof = wall_profile_EW()
    walls["W"] = [prism_x("Wall W siding", 0, SKIN, prof, "Siding", c_ext),
                  prism_x("Wall W core", SKIN, T, prof, "Drywall", c_ext)]
    walls["E"] = [prism_x("Wall E siding", HW - SKIN, HW, prof, "Siding", c_ext),
                  prism_x("Wall E core", HW - T, HW - SKIN, prof, "Drywall", c_ext)]
    # clerestory wall: siding on the south (exterior above the low roof), drywall north
    ztop = lambda x, y: north_roof_z(y)
    walls["C"] = [box("Clerestory wall siding", T, HW - T, YC2 - SKIN, YC2, H_CL, north_roof_z(YC2), "Siding", c_ext, ztop=ztop),
                  box("Clerestory wall core", T, HW - T, YC, YC2 - SKIN, 0, 20, "Drywall", c_ext, ztop=ztop)]
    return walls


WALLS = make_ext_walls()


def wall_frame(wall):
    """returns function (u, v) -> plan (x, y): u along wall, v depth inward from exterior face."""
    if wall == "N": return lambda u, v: (u, v)
    if wall == "S": return lambda u, v: (u, HD - v)
    if wall == "W": return lambda u, v: (v, u)
    if wall == "E": return lambda u, v: (HW - v, u)
    if wall == "C": return lambda u, v: (u, YC2 - v)


def wbox(name, wall, u0, u1, v0, v1, z0, z1, mat, collection):
    f = wall_frame(wall)
    a, b = f(u0, v0), f(u1, v1)
    return box(name, a[0], b[0], a[1], b[1], z0, z1, mat, collection)


def add_cutter(wall, u0, u1, z0, z1, name):
    th = T if wall != "C" else T
    ob = wbox("cut " + name, wall, u0, u1, -0.5, th + 0.5, z0, z1, "Trim", c_cut)
    ob.display_type = 'WIRE'
    return ob


def attach_booleans():
    for wall, objs in WALLS.items():
        cutters = [o for o in c_cut.objects if o.get("wall") == wall]
        if not cutters:
            continue
        sub = bpy.data.collections.new("cutters " + wall); c_cut.children.link(sub)
        for o in cutters:
            sub.objects.link(o)
        for w in objs:
            md = w.modifiers.new("openings", 'BOOLEAN'); md.operation = 'DIFFERENCE'
            md.operand_type = 'COLLECTION'; md.collection = sub
            try:
                md.solver = 'EXACT'
            except Exception:
                pass


def window_unit(o, wall, depth_wall):
    """frame, glass, interior white-oak jamb + casing, exterior black trim."""
    name, kind = o["id"], o["kind"]
    u0, u1, z0, z1 = o["start"], o["end"], o["sill"], o["head"]
    fw = 0.18  # frame face width (ft)
    fd = 0.30  # frame depth
    v0 = SKIN + 0.05
    cut = add_cutter(wall, u0, u1, z0, z1, name); cut["wall"] = wall
    is_door = kind.startswith("door") or kind == "slider"
    # frame ring: aluminum clad (black) on the exterior half, white oak on the interior half.
    # Pieces butt together instead of overlapping so no coincident faces render dark.
    vm = v0 + fd * 0.5
    for (va, vb, fm) in ((v0, vm, "Window Frame"), (vm, v0 + fd, "White Oak")):
        tag = "clad" if fm == "Window Frame" else "oak"
        wbox(f"{name} frame L {tag}", wall, u0, u0 + fw, va, vb, z0, z1, fm, c_win)
        wbox(f"{name} frame R {tag}", wall, u1 - fw, u1, va, vb, z0, z1, fm, c_win)
        wbox(f"{name} frame T {tag}", wall, u0 + fw, u1 - fw, va, vb, z1 - fw, z1, fm, c_win)
        zb = z0 + (0.12 if is_door else fw)
        wbox(f"{name} frame B {tag}", wall, u0 + fw, u1 - fw, va, vb, z0, zb, fm, c_win)
        n_panels = {"casement_pair": 2, "awning_pair": 2, "slider": 4}.get(kind, 1)
        for k in range(1, n_panels):
            um = u0 + (u1 - u0) * k / n_panels
            wbox(f"{name} mullion {k} {tag}", wall, um - fw / 2, um + fw / 2, va, vb, zb, z1 - fw, fm, c_win)
        if kind == "door_glass":   # door bottom rail
            wbox(f"{name} kick rail {tag}", wall, u0 + fw, u1 - fw, va, vb, zb, z0 + 0.9, fm, c_win)
    glass = wbox(name + " glass", wall, u0 + fw * 0.5, u1 - fw * 0.5, v0 + fd * 0.45, v0 + fd * 0.55, z0 + 0.05, z1 - 0.05, "Glass", c_win)
    glass.visible_shadow = True
    # exterior trim 4" Abyss Black
    tw = 4 / 12
    wbox(name + " trim L", wall, u0 - tw, u0, -BAT_T - 0.02, SKIN, z0, z1, "Trim", c_win)
    wbox(name + " trim R", wall, u1, u1 + tw, -BAT_T - 0.02, SKIN, z0, z1, "Trim", c_win)
    wbox(name + " trim T", wall, u0 - tw, u1 + tw, -BAT_T - 0.02, SKIN, z1, z1 + tw, "Trim", c_win)
    if not is_door:
        wbox(name + " trim B", wall, u0 - tw, u1 + tw, -BAT_T - 0.04, SKIN, z0 - tw, z0, "Trim", c_win)
    # interior white oak jamb liner and casing (3.5")
    jd0, jd1 = v0 + fd, depth_wall
    oak = "White Oak"
    wbox(name + " jamb L", wall, u0, u0 + 0.06, jd0, jd1, z0, z1 - 0.06, oak, c_win)
    wbox(name + " jamb R", wall, u1 - 0.06, u1, jd0, jd1, z0, z1 - 0.06, oak, c_win)
    wbox(name + " jamb T", wall, u0, u1, jd0, jd1, z1 - 0.06, z1, oak, c_win)
    if not is_door:
        wbox(name + " stool", wall, u0 - 0.15, u1 + 0.15, jd0, jd1 + 0.12, z0 - 0.07, z0, oak, c_win)
    cw = 3.5 / 12
    wbox(name + " casing L", wall, u0 - cw, u0, jd1, jd1 + 0.06, z0, z1, oak, c_win)
    wbox(name + " casing R", wall, u1, u1 + cw, jd1, jd1 + 0.06, z0, z1, oak, c_win)
    wbox(name + " casing T", wall, u0 - cw, u1 + cw, jd1, jd1 + 0.06, z1, z1 + cw, oak, c_win)
    if not is_door:
        wbox(name + " apron", wall, u0 - cw, u1 + cw, jd1, jd1 + 0.05, z0 - 0.32, z0 - 0.07, oak, c_win)


for o in C["openings"]:
    window_unit(o, o["wall"], T)

CL = C["clerestory"]
for k in range(CL["count"]):
    cx = CL["first_center_x"] + k * CL["spacing"]
    window_unit({"id": f"W30-30 clerestory {k + 1}", "kind": "awning", "start": cx - CL["width"] / 2,
                 "end": cx + CL["width"] / 2, "sill": CL["sill"], "head": CL["head"]}, "C", T)
for (x0, x1, head) in CL["passages"]:
    c = add_cutter("C", x0, x1, -0.1, head, f"passage {x0}"); c["wall"] = "C"
attach_booleans()

# ------------------------------------------------------------------ board and batten (real geometry)
BAT_SP = C["materials"]["batten_spacing_in"] / 12
BAT_W = C["materials"]["batten_width_in"] / 12
TRIM_W = 4 / 12


def battens(name, frame, u_lo, u_hi, z_bot, top, holes, collection, v_face=0.0):
    """Vertical battens on a wall face. frame(u, v) -> plan (x, y), v < 0 is outward.
    top(u) gives the wall top at u. holes = [(u0, u1, z0, z1)] trimmed openings to skip."""
    verts, faces = [], []
    u = u_lo + BAT_SP / 2
    while u + BAT_W / 2 < u_hi - 0.25:
        ua, ub = u - BAT_W / 2, u + BAT_W / 2
        segs = [(z_bot, min(top(ua), top(ub)))]
        for (h0, h1, hz0, hz1) in holes:
            if h0 < ub and h1 > ua:
                nxt = []
                for (a, b) in segs:
                    if hz1 <= a or hz0 >= b:
                        nxt.append((a, b)); continue
                    if hz0 > a: nxt.append((a, hz0))
                    if hz1 < b: nxt.append((hz1, b))
                segs = nxt
        for (a, b) in segs:
            if b - a < 0.15:
                continue
            ta, tb = (b, b) if b < min(top(ua), top(ub)) - 1e-6 else (top(ua), top(ub))
            base = len(verts)
            corners = []
            for vv in (v_face - BAT_T, v_face):
                for (uu, zt) in ((ua, ta), (ub, tb)):
                    x, y = frame(uu, vv)
                    corners.append((P(x, y, a), P(x, y, zt)))
            # order: 0..3 bottom, 4..7 top in a ring
            ring = [corners[0], corners[1], corners[3], corners[2]]
            verts += [c[0] for c in ring] + [c[1] for c in ring]
            faces += [(base + 0, base + 1, base + 2, base + 3), (base + 4, base + 5, base + 6, base + 7),
                      (base + 0, base + 1, base + 5, base + 4), (base + 1, base + 2, base + 6, base + 5),
                      (base + 2, base + 3, base + 7, base + 6), (base + 3, base + 0, base + 4, base + 7)]
        u += BAT_SP
    if faces:
        return mesh_obj(name, verts, faces, "Siding", collection)


def holes_for(wall, extra=()):
    hs = []
    for o in list(C["openings"]) + list(extra):
        if o["wall"] != wall:
            continue
        door = o["kind"].startswith("door") or o["kind"] == "slider"
        hs.append((o["start"] - TRIM_W, o["end"] + TRIM_W, -1 if door else o["sill"] - TRIM_W, o["head"] + TRIM_W))
    return hs


def ew_top(y):
    return north_roof_z(y) if y < YC2 else H_CL + (y - YC2) * (H_S - H_CL) / (HD - YC2)


CLER_WINS = [{"wall": "C", "kind": "awning", "start": CL["first_center_x"] + k * CL["spacing"] - CL["width"] / 2,
              "end": CL["first_center_x"] + k * CL["spacing"] + CL["width"] / 2, "sill": CL["sill"], "head": CL["head"]}
             for k in range(CL["count"])]
if C["materials"]["siding_style"] == "board_and_batten":
    battens("Battens N", wall_frame("N"), 0, HW, 0, lambda u: H_N, holes_for("N"), c_ext)
    battens("Battens S", wall_frame("S"), 0, HW, 0, lambda u: H_S, holes_for("S"), c_ext)
    battens("Battens W", wall_frame("W"), 0, HD, 0, ew_top, holes_for("W"), c_ext)
    battens("Battens E", wall_frame("E"), 0, HD, 0, ew_top, holes_for("E"), c_ext)
    battens("Battens clerestory", wall_frame("C"), T, HW - T, H_CL, lambda u: north_roof_z(YC2), holes_for("C", CLER_WINS), c_ext)
    # corner boards (Abyss Black trim), 4" each way
    for (x, y, sx, sy) in ((0, 0, 1, 1), (HW, 0, -1, 1), (HW, HD, -1, -1), (0, HD, 1, -1)):
        zt = H_N if y == 0 else H_S
        box("Corner board", x - sx * BAT_T, x + sx * TRIM_W, y - sy * BAT_T, y, 0, zt, "Trim", c_ext)
        box("Corner board", x - sx * BAT_T, x, y - sy * BAT_T, y + sy * TRIM_W, 0, zt, "Trim", c_ext)

# ------------------------------------------------------------------ interior walls (A-11 vectors)
LOFT = C["loft"]
LX0, LY0, LX1, LY1 = LOFT["rect"]


def pt_in_poly(x, y, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if xi > x:
                inside = not inside
    return inside


def rect_decompose(poly):
    xs = sorted(set(round(p[0], 3) for p in poly)); ys = sorted(set(round(p[1], 3) for p in poly))
    cells = {}
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
            if pt_in_poly(cx, cy, poly):
                cells[(i, j)] = True
    rects = []
    used = set()
    for (i, j) in sorted(cells):
        if (i, j) in used:
            continue
        # grow along the longer direction: try x first then y
        i2 = i
        while (i2 + 1, j) in cells and (i2 + 1, j) not in used:
            i2 += 1
        j2 = j
        while all((ii, j2 + 1) in cells and (ii, j2 + 1) not in used for ii in range(i, i2 + 1)):
            j2 += 1
        for ii in range(i, i2 + 1):
            for jj in range(j, j2 + 1):
                used.add((ii, jj))
        rects.append((xs[i], xs[i2 + 1], ys[j], ys[j2 + 1]))
    # split long-in-x merges that are really thin walls in y (keep as is: fine for boxes)
    return rects


def wall_top(x0, x1, y0, y1):
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    in_loft = LOFT["enabled"] and LX0 - 0.05 <= cx <= LX1 + 0.05 and LY0 + 0.3 <= cy <= LY1 + 0.6
    if in_loft:
        if abs(cx - (LX0 + 0.23)) < 0.4:      # loft edge pony wall (bath 1 west wall)
            return lambda x, y: LOFT["floor_height"] + LOFT["pony_wall_height"]
        return lambda x, y: LOFT["floor_height"] - 0.9
    return lambda x, y: roof_under(min(y, YC2))


INT_RECTS = []
for poly in G["interior_walls_from_plan_A11"]:
    for r in rect_decompose(poly):
        # the clerestory wall is modeled on its own (with passages), skip traced pieces on that line
        if r[2] > YC - 0.15 and r[3] < YC2 + 0.15:
            continue
        INT_RECTS.append(r)
for k, (x0, x1, y0, y1) in enumerate(INT_RECTS):
    box(f"Int wall {k}", x0, x1, y0, y1, 0, 9, "Drywall", c_int, ztop=wall_top(x0, x1, y0, y1))

# headers over door gaps: pair collinear wall ends 1.5-7 ft apart
DOORS = G.get("door_labels_A11", [])


def door_head_near(x, y):
    best, bd = 6.67, 99
    for dx, dy, lab in DOORS:
        d = math.hypot(dx - x, dy - y)
        if d < bd:
            bd, best = d, (8.0 if lab.endswith("80") else 6.67)
    return best if bd < 3.5 else 8.0


def make_headers():
    made = 0
    rects = INT_RECTS
    for i, a in enumerate(rects):
        for j, b in enumerate(rects):
            if i >= j:
                continue
            for horiz in (True, False):
                if horiz:   # walls running in x with identical y span
                    if abs(a[2] - b[2]) > 0.02 or abs(a[3] - b[3]) > 0.02 or (a[3] - a[2]) > 0.7:
                        continue
                    lo, hi = (a, b) if a[1] <= b[0] else (b, a)
                    gap0, gap1 = lo[1], hi[0]
                    if not (1.4 < gap1 - gap0 < 7.0):
                        continue
                    if any(r is not a and r is not b and r[0] < gap1 - 0.01 and r[1] > gap0 + 0.01 and r[2] < a[3] and r[3] > a[2] for r in rects):
                        continue
                    cx, cy = (gap0 + gap1) / 2, (a[2] + a[3]) / 2
                    h = door_head_near(cx, cy)
                    top = wall_top(gap0, gap1, a[2], a[3])
                    DOOR_GAPS.append(("x", gap0, gap1, a[2], a[3], h))   # opening along x, wall thickness in y
                    if top(cx, cy) - h > 0.2:
                        box(f"Header {i}-{j}", gap0, gap1, a[2], a[3], h, 9, "Drywall", c_int, ztop=top); made += 1
                else:
                    if abs(a[0] - b[0]) > 0.02 or abs(a[1] - b[1]) > 0.02 or (a[1] - a[0]) > 0.7:
                        continue
                    lo, hi = (a, b) if a[3] <= b[2] else (b, a)
                    gap0, gap1 = lo[3], hi[2]
                    if not (1.4 < gap1 - gap0 < 7.0):
                        continue
                    if any(r is not a and r is not b and r[2] < gap1 - 0.01 and r[3] > gap0 + 0.01 and r[0] < a[1] and r[1] > a[0] for r in rects):
                        continue
                    cx, cy = (a[0] + a[1]) / 2, (gap0 + gap1) / 2
                    h = door_head_near(cx, cy)
                    top = wall_top(a[0], a[1], gap0, gap1)
                    DOOR_GAPS.append(("y", gap0, gap1, a[0], a[1], h))   # opening along y, wall thickness in x
                    if top(cx, cy) - h > 0.2:
                        box(f"Header {i}-{j}", a[0], a[1], gap0, gap1, h, 9, "Drywall", c_int, ztop=top); made += 1
    return made


DOOR_GAPS = []
print("headers:", make_headers())

# ------------------------------------------------------------------ roofs
OH = R["overhang"]; TH = R["panel_thickness"]


def roof_slab(name, y0, y1, zfun, collection):
    x0, x1 = -OH, HW + OH
    cosn = 1.0
    v = [P(x0, y0, zfun(y0)), P(x1, y0, zfun(y0)), P(x1, y1, zfun(y1)), P(x0, y1, zfun(y1)),
         P(x0, y0, zfun(y0) + TH), P(x1, y0, zfun(y0) + TH), P(x1, y1, zfun(y1) + TH), P(x0, y1, zfun(y1) + TH)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    ob = mesh_obj(name, v, f, None, collection, mats=["Trim", "Standing Seam"], face_mats=[0, 1, 0, 0, 0, 0])
    return ob


roof_slab("Roof north (high)", -OH, YC2 + OH, north_roof_z, c_roof)
roof_slab("Roof south (low)", YC2, HD + OH, south_roof_z, c_roof)
SEAM = R.get("seam_spacing_in", 16) / 12


def seam_ribs(name, x0, x1, y0, y1, ztop, collection):
    """Standing seam ribs (1" tall, 3/4" wide) running down the slope (plan y)."""
    x = x0 + SEAM / 2
    k = 0
    while x < x1 - 0.1:
        prof = [(y0, ztop(y0) - 0.02), (y1, ztop(y1) - 0.02), (y1, ztop(y1) + 0.083), (y0, ztop(y0) + 0.083)]
        prism_x(f"{name} seam {k}", x - 0.031, x + 0.031, prof, "Standing Seam", collection)
        x += SEAM; k += 1


seam_ribs("Roof north", -OH, HW + OH, -OH, YC2 + OH, lambda y: north_roof_z(y) + TH, c_roof)
seam_ribs("Roof south", -OH, HW + OH, YC2, HD + OH, lambda y: south_roof_z(y) + TH, c_roof)
# interior vaulted ceiling skins (drywall under the roof)
box("Vault ceiling north", T, HW - T, T, YC, 0, 0, "Drywall", c_ceil)
bpy.data.objects.remove(bpy.data.objects["Vault ceiling north"])
v = [P(T, T, north_roof_z(T) - 0.01), P(HW - T, T, north_roof_z(T) - 0.01), P(HW - T, YC, north_roof_z(YC) - 0.01), P(T, YC, north_roof_z(YC) - 0.01)]
mesh_obj("Vault ceiling north", v, [(0, 1, 2, 3)], "Drywall", c_ceil)
v = [P(T, YC2, south_roof_z(YC2) - 0.01), P(HW - T, YC2, south_roof_z(YC2) - 0.01), P(HW - T, HD - T, south_roof_z(HD - T) - 0.01), P(T, HD - T, south_roof_z(HD - T) - 0.01)]
mesh_obj("Vault ceiling south", v, [(0, 1, 2, 3)], "Drywall", c_ceil)

# flat 9' ceilings + attic floor
FH = C["ceilings"]["flat_height"]
for k, (x0, y0, x1, y1) in enumerate(C["ceilings"]["flat_rooms"]):
    box(f"Flat ceiling {k}", x0, x1, y0, y1, FH, FH + 0.8, "Drywall", c_ceil)

# loft
if LOFT["enabled"]:
    box("Loft floor", LX0, LX1, LY0, LY1, LOFT["floor_height"] - 0.9, LOFT["floor_height"], "White Oak", c_ceil)
    lx0, ly0, lx1, ly1 = LOFT["ships_ladder"]
    n = 11
    for k in range(n):
        x = lx0 + (lx1 - lx0) * k / n
        z = LOFT["floor_height"] * (k + 1) / (n + 1)
        box(f"Ladder tread {k}", x, x + 0.75, ly0 + 0.15, ly1 - 0.15, z - 0.12, z, "White Oak", c_ceil)
    for yy in (ly0, ly1 - 0.15):
        v = [P(lx0, yy, 0), P(lx0 + 0.35, yy, 0), P(lx1, yy, LOFT["floor_height"]), P(lx1 - 0.35, yy, LOFT["floor_height"]),
             P(lx0, yy + 0.15, 0), P(lx0 + 0.35, yy + 0.15, 0), P(lx1, yy + 0.15, LOFT["floor_height"]), P(lx1 - 0.35, yy + 0.15, LOFT["floor_height"])]
        f = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
        mesh_obj(f"Ladder stringer {yy}", v, f, "White Oak", c_ceil)

# ------------------------------------------------------------------ kitchen & fixtures
# Built from the Carter Lumber elevations (see [kitchen] in config.toml).
K = C["kitchen"]
simple("Brushed Nickel", K.get("hardware_color", "#B8B8B4"), 0.3, 1.0)
simple("Black Glass", "#0B0B0C", 0.05, 0.0)
simple("Appliance Interior", "#1A1A1A", 0.6)
BASE_D, CTR_D, FRONT_T, REV = 1.9, 2.08, 0.06, 0.012     # depths (ft), door thickness, reveal
KICK, CTR_Z, CTR_T = 0.33, 3.0, 0.125
TALL = K.get("tall_height", 8.0)


def rbox(run, name, u0, u1, d0, d1, z0, z1, mat):
    """Box in run coordinates: u along the wall, d out from the wall toward the room."""
    b_, f_ = run["back"], run["facing"]
    if run["axis"] == "x":
        return box(name, u0, u1, b_ + f_ * d0, b_ + f_ * d1, z0, z1, mat, c_kit)
    return box(name, b_ + f_ * d0, b_ + f_ * d1, u0, u1, z0, z1, mat, c_kit)


def pull(run, name, uc, zc, length, d, vertical=False):
    if vertical:
        rbox(run, name, uc - 0.02, uc + 0.02, d, d + 0.07, zc - length / 2, zc + length / 2, "Brushed Nickel")
    else:
        rbox(run, name, uc - length / 2, uc + length / 2, d, d + 0.07, zc - 0.02, zc + 0.02, "Brushed Nickel")


def shaker(run, name, u0, u1, z0, z1, d, mat, kind="door", hinge="L", glass=False):
    """Shaker 5 piece front with a recessed center panel and a bar pull."""
    u0, u1, z0, z1 = u0 + REV, u1 - REV, z0 + REV, z1 - REV
    w, h = u1 - u0, z1 - z0
    st = min(0.19, w / 4, h / 4)
    if h < 0.62 and kind == "drawer":      # short drawer fronts are slab
        rbox(run, name, u0, u1, d, d + FRONT_T, z0, z1, mat)
    else:
        rbox(run, name + " panel", u0 + st, u1 - st, d, d + FRONT_T * 0.6, z0 + st, z1 - st, "Glass" if glass else mat)
        rbox(run, name + " stile L", u0, u0 + st, d, d + FRONT_T, z0, z1, mat)
        rbox(run, name + " stile R", u1 - st, u1, d, d + FRONT_T, z0, z1, mat)
        rbox(run, name + " rail T", u0 + st, u1 - st, d, d + FRONT_T, z1 - st, z1, mat)
        rbox(run, name + " rail B", u0 + st, u1 - st, d, d + FRONT_T, z0, z0 + st, mat)
    dp = d + FRONT_T
    if kind == "drawer":
        zc = z1 - min(0.25, h / 2) if h > 0.62 else (z0 + z1) / 2
        if w > 2.4 and K.get("wide_drawer_pulls", 2) == 2:
            pull(run, name + " pull a", u0 + w * 0.25, zc, 0.5, dp); pull(run, name + " pull b", u0 + w * 0.75, zc, 0.5, dp)
        elif w > 2.4:
            pull(run, name + " pull", (u0 + u1) / 2, zc, min(1.6, w * 0.6), dp)
        else:
            pull(run, name + " pull", (u0 + u1) / 2, zc, min(0.5, w * 0.5), dp)
    elif kind == "door":
        uc = u1 - 0.12 if hinge == "L" else u0 + 0.12
        zc = z1 - 0.45 if z0 < 3.0 and z1 < 3.5 else z0 + 0.45
        if z1 - z0 > 3.5:
            zc = 3.6 if z0 < 1 else z0 + 0.45
        pull(run, name + " pull", uc, zc, 0.5, dp, vertical=True)


def stack(run, name, u0, u1, z0, z1, d, mat, heights):
    """Drawer stack, heights listed top to bottom as fractions."""
    tot = sum(heights); z = z1
    for k, hf in enumerate(heights):
        hz = (z1 - z0) * hf / tot
        shaker(run, f"{name} drawer {k}", u0, u1, z - hz, z, d, mat, "drawer"); z -= hz


def doors(run, name, u0, u1, z0, z1, d, mat, n, glass=False):
    if n == 1:
        shaker(run, name + " door", u0, u1, z0, z1, d, mat, "door", "L", glass)
    else:
        um = (u0 + u1) / 2
        shaker(run, name + " door L", u0, um, z0, z1, d, mat, "door", "L", glass)
        shaker(run, name + " door R", um, u1, z0, z1, d, mat, "door", "R", glass)


def base_unit(run, name, u0, u1, typ, mat, depth=BASE_D, counter=True):
    d = depth; zt = CTR_Z - CTR_T
    if typ in ("oven_tower", "tall_pantry"):
        rbox(run, name + " carcass", u0, u1, 0, BASE_D + 0.1, KICK, TALL - 0.25, mat)
        rbox(run, name + " toe", u0 + 0.05, u1 - 0.05, 0, BASE_D - 0.15, 0, KICK, mat)
        rbox(run, name + " crown", u0 - 0.05, u1 + 0.05, 0, BASE_D + 0.22, TALL - 0.25, TALL, mat)
        df = BASE_D + 0.1
        if typ == "oven_tower":
            stack(run, name, u0, u1, KICK, 1.25, df, mat, [1])
            rbox(run, name + " double wall oven", u0 + 0.1, u1 - 0.1, df - 0.02, df + 0.05, 1.3, 4.55, "Stainless")
            for zz in (1.45, 3.05):
                rbox(run, name + " oven window", u0 + 0.45, u1 - 0.45, df + 0.05, df + 0.06, zz + 0.25, zz + 1.05, "Black Glass")
                pull(run, name + " oven handle", (u0 + u1) / 2, zz + 1.35, u1 - u0 - 0.8, df + 0.06)
            doors(run, name + " upper", u0, u1, 4.6, TALL - 0.25, df, mat, 2)
        else:
            doors(run, name + " lower", u0, u1, KICK, 4.0, df, mat, 2)
            doors(run, name + " upper", u0, u1, 4.0, TALL - 0.25, df, mat, 2)
        return
    if typ == "fridge":
        fp = run.get("fridge_panels", 0.0)
        if fp:   # built-in look: oak side panels inside the bay, over-fridge cabinet flush with them
            for (a0, a1) in ((u0, u0 + fp), (u1 - fp, u1)):
                rbox(run, name + " fridge side panel", a0, a1, 0, BASE_D + 0.42, 0, 6.0, mat)
            rbox(run, name + " over-fridge cabinet", u0, u1, 0, BASE_D + 0.1, 6.0, TALL - 0.25, mat)
            doors(run, name + " over-fridge", u0, u1, 6.0, TALL - 0.25, BASE_D + 0.1, mat, 2)
            rbox(run, name + " crown", u0 - 0.05, u1 + 0.05, 0, BASE_D + 0.22, TALL - 0.25, TALL, mat)
            u0, u1 = u0 + fp + 0.02, u1 - fp - 0.02
            rbox(run, name + " refrigerator", u0, u1, 0.1, BASE_D + 0.35, 0, 5.9, "Stainless")
            rbox(run, name + " french door seam", (u0 + u1) / 2 - 0.01, (u0 + u1) / 2 + 0.01, BASE_D + 0.35, BASE_D + 0.36, 2.15, 5.9, "Black Glass")
            rbox(run, name + " freezer seam", u0, u1, BASE_D + 0.35, BASE_D + 0.36, 2.1, 2.15, "Black Glass")
            for uc in ((u0 + u1) / 2 - 0.12, (u0 + u1) / 2 + 0.12):
                pull(run, name + " fridge handle", uc, 4.0, 2.6, BASE_D + 0.36, vertical=True)
            pull(run, name + " freezer handle", (u0 + u1) / 2, 1.9, u1 - u0 - 0.6, BASE_D + 0.36)
            rbox(run, name + " dispenser", u0 + 0.32, u0 + 0.82, BASE_D + 0.36, BASE_D + 0.37, 3.6, 4.5, "Black Glass")
            return
        rbox(run, name + " refrigerator", u0 + 0.03, u1 - 0.03, 0.1, BASE_D + 0.35, 0, 5.9, "Stainless")
        rbox(run, name + " french door seam", (u0 + u1) / 2 - 0.01, (u0 + u1) / 2 + 0.01, BASE_D + 0.35, BASE_D + 0.36, 2.15, 5.9, "Black Glass")
        rbox(run, name + " freezer seam", u0 + 0.03, u1 - 0.03, BASE_D + 0.35, BASE_D + 0.36, 2.1, 2.15, "Black Glass")
        for uc in ((u0 + u1) / 2 - 0.12, (u0 + u1) / 2 + 0.12):
            pull(run, name + " fridge handle", uc, 4.0, 2.6, BASE_D + 0.36, vertical=True)
        pull(run, name + " freezer handle", (u0 + u1) / 2, 1.9, u1 - u0 - 0.6, BASE_D + 0.36)
        rbox(run, name + " dispenser", u0 + 0.35, u0 + 0.85, BASE_D + 0.36, BASE_D + 0.37, 3.6, 4.5, "Black Glass")
        rbox(run, name + " over-fridge cabinet", u0 - 0.1, u1 + 0.1, 0, BASE_D + 0.1, 6.0, TALL - 0.25, mat)
        doors(run, name + " over-fridge", u0 - 0.1, u1 + 0.1, 6.0, TALL - 0.25, BASE_D + 0.1, mat, 2)
        rbox(run, name + " crown", u0 - 0.15, u1 + 0.15, 0, BASE_D + 0.22, TALL - 0.25, TALL, mat)
        return
    if typ == "panel":   # solid end/filler panel, no carcass behind it
        rbox(run, name + " end panel", u0, u1, 0, d + FRONT_T, 0, zt, mat); return
    # standard base cabinet
    rbox(run, name + " carcass", u0, u1, 0, d, KICK, zt, mat)
    rbox(run, name + " toe", u0, u1, 0, d - 0.25, 0, KICK, mat)
    if counter:
        rbox(run, name + " counter", u0, u1, 0, d + 0.18, zt, CTR_Z, "Counter")
    if typ == "blind":
        return
    if typ == "panel":
        rbox(run, name + " end panel", u0, u1, 0, d + FRONT_T, 0, zt, mat); return
    if typ == "dishwasher":
        rbox(run, name + " dishwasher", u0 + REV, u1 - REV, d, d + 0.05, KICK, zt - 0.02, "Stainless")
        pull(run, name + " dw handle", (u0 + u1) / 2, zt - 0.2, u1 - u0 - 0.4, d + 0.05); return
    if typ == "beverage":
        rbox(run, name + " beverage fridge", u0 + REV, u1 - REV, d - 0.02, d + 0.03, KICK, zt - 0.02, "Stainless")
        rbox(run, name + " beverage glass", u0 + 0.12, u1 - 0.12, d + 0.03, d + 0.04, KICK + 0.25, zt - 0.15, "Black Glass")
        pull(run, name + " beverage handle", u0 + 0.18, (KICK + zt) / 2, 1.4, d + 0.04, vertical=True); return
    if typ == "tray":   # top drawer over an open bay with vertical tray dividers
        shaker(run, name + " drawer", u0, u1, zt - 0.5, zt, d, mat, "drawer")
        rbox(run, name + " bay back", u0 + 0.06, u1 - 0.06, 0.1, 0.15, KICK, zt - 0.5, "Appliance Interior")
        for k in range(1, 5):
            uu = u0 + (u1 - u0) * k / 5
            rbox(run, f"{name} divider {k}", uu - 0.02, uu + 0.02, 0.15, d, KICK, zt - 0.52, mat)
        for (a0, a1) in ((u0, u0 + 0.06), (u1 - 0.06, u1)):
            rbox(run, name + " bay side", a0, a1, 0, d + FRONT_T, KICK, zt - 0.5, mat)
        return
    h = {"drawers3": [1, 2, 2], "drawers2": [1, 1], "drawer_door": None, "drawer_doors2": None}
    if typ in ("drawers3", "drawers2"):
        stack(run, name, u0, u1, KICK, zt, d, mat, h[typ])
    elif typ in ("drawer_door", "drawer_doors2"):
        stack(run, name, u0, u1, zt - 0.5, zt, d, mat, [1])
        doors(run, name, u0, u1, KICK, zt - 0.5, d, mat, 1 if typ == "drawer_door" else 2)
    elif typ in ("door1", "pullout"):
        doors(run, name, u0, u1, KICK, zt, d, mat, 1)
    elif typ == "drawer_tall":          # one full height drawer (utensils)
        stack(run, name, u0, u1, KICK, zt, d, mat, [1])
    elif typ == "pullout_drawer":       # drawer over a vertical sheet pan pullout
        stack(run, name, u0, u1, zt - 0.5, zt, d, mat, [1])
        doors(run, name + " pullout", u0, u1, KICK, zt - 0.5, d, mat, 1)
    elif typ == "doors2":
        doors(run, name, u0, u1, KICK, zt, d, mat, 2)


RUNS = K["runs"]
for rn, run in RUNS.items():
    mat = "Island" if rn.startswith("island") else "Cabinet Wood"
    for k, (u0, u1, typ) in enumerate(run["units"]):
        base_unit(run, f"Kitchen {rn} {k} {typ}", u0, u1, typ, mat, run.get("depth", BASE_D), counter=not rn.startswith("island"))
# uppers on the fridge wall
nr = RUNS["north"]; UB = K.get("upper_bottom", 4.6)
for k, up in enumerate(nr.get("uppers", [])):
    u0, u1, typ = up[:3]; ud = up[3] if len(up) > 3 else 1.1
    rbox(nr, f"Upper {k} carcass", u0, u1, 0, ud, UB, TALL - 0.25, "Cabinet Wood")
    if typ == "glass":
        doors(nr, f"Upper {k} glass", u0, u1, UB, TALL - 0.25, ud, "Cabinet Wood", 2, glass=True)
        for zz in (5.7, 6.75):
            rbox(nr, f"Upper {k} shelf", u0 + 0.06, u1 - 0.06, 0.05, ud - 0.05, zz, zz + 0.06, "Cabinet Wood")
    else:
        rbox(nr, f"Upper {k} microwave", u0 + 0.15, u1 - 0.15, ud - 0.05, ud + 0.02, UB + 0.05, UB + 1.45, "Stainless")
        rbox(nr, f"Upper {k} microwave window", u0 + 0.3, u1 - 0.9, ud + 0.02, ud + 0.03, UB + 0.25, UB + 1.25, "Black Glass")
        doors(nr, f"Upper {k}", u0, u1, UB + 1.55, TALL - 0.25, ud, "Cabinet Wood", 2)
    rbox(nr, f"Upper {k} crown", u0 - 0.03, u1 + 0.03, 0, ud + 0.12, TALL - 0.25, TALL, "Cabinet Wood")
# pantry door in the clerestory wall opening where Carter drew a tall cabinet (redline)
if nr.get("pantry_door"):
    px0, px1, phd = min(CL["passages"], key=lambda p: p[0])
    leaf = nr.get("pantry_door_leaf", px1 - px0 - 0.2)
    ce, cw = nr.get("pantry_casing_east", 0.29), nr.get("pantry_casing_west", 0.29)
    lx0 = (px0 + px1) / 2 - leaf / 2; lx1 = lx0 + leaf
    box("Pantry door", lx0, lx1, YC + 0.2, YC + 0.34, 0.03, phd - 0.06, "White Oak", c_kit)
    # jamb liners through the wall, then casing on the kitchen face (west leg trimmed to meet the west wall)
    for (a0, a1) in ((px0, px0 + 0.06), (px1 - 0.06, px1)):
        box("Pantry door jamb", a0, a1, YC, YC2, 0, phd, "White Oak", c_kit)
    box("Pantry door head jamb", px0, px1, YC, YC2, phd - 0.06, phd, "White Oak", c_kit)
    for (a0, a1, z0_, z1_) in ((px0 - cw, px0 + 0.02, 0, phd), (px1 - 0.02, px1 + ce, 0, phd), (px0 - cw, px1 + ce, phd, phd + 0.29)):
        box("Pantry door casing", a0, a1, YC2, YC2 + 0.06, z0_, z1_, "White Oak", c_kit)
    box("Pantry door lever rose", lx1 - 0.3, lx1 - 0.18, YC2 - 0.02, YC2 + 0.02, 3.0, 3.12, "Brushed Nickel", c_kit)
    box("Pantry door lever", lx1 - 0.55, lx1 - 0.22, YC2 + 0.02, YC2 + 0.08, 3.04, 3.08, "Brushed Nickel", c_kit)
    print(f"pantry door: opening {px0:.3f}-{px1:.3f}, leaf {leaf:.2f} ft, casing {px0 - cw:.3f}-{px1 + ce:.3f}")
# sink, cooktop, hood
sr = RUNS["south"]; sx0, sx1 = sr["sink_x"]
rbox(sr, "Drop-in sink rim", sx0, sx1, 0.35, 1.75, CTR_Z, CTR_Z + 0.03, "Stainless")
rbox(sr, "Sink bowl", sx0 + 0.1, sx1 - 0.1, 0.45, 1.65, CTR_Z - 0.7, CTR_Z + 0.031, "Stainless")
rbox(sr, "Faucet", (sx0 + sx1) / 2 - 0.05, (sx0 + sx1) / 2 + 0.05, 0.15, 0.25, CTR_Z, CTR_Z + 1.2, "Brushed Nickel")
rbox(sr, "Faucet spout", (sx0 + sx1) / 2 - 0.04, (sx0 + sx1) / 2 + 0.04, 0.15, 0.85, CTR_Z + 1.12, CTR_Z + 1.2, "Brushed Nickel")
wr = RUNS["west"]; cy0, cy1 = wr["cooktop_y"]
rbox(wr, "Cooktop", cy0, cy1, 0.15, 1.85, CTR_Z, CTR_Z + 0.03, "Black Glass")
rbox(wr, "Hood", cy0 + 0.1, cy1 - 0.1, 0, 1.9, 6.0, 6.35, "Stainless")
rbox(wr, "Hood chimney", (cy0 + cy1) / 2 - 0.45, (cy0 + cy1) / 2 + 0.45, 0, 0.9, 6.35, 11.6, "Stainless")
# island top with seating overhang on the north side
ix0, iy0, ix1, iy1 = K["island"]
ir = RUNS["island"]
box("Island back panel", ir["units"][0][0], RUNS["island_east"]["back"] if "island_east" in RUNS else ir["units"][-1][1], ir["back"] - 0.06, ir["back"], 0, CTR_Z - CTR_T, "Island", c_kit)
for (e0, e1) in ((ir["units"][0][0] - 0.06, ir["units"][0][0]),):
    box("Island end panel", e0, e1, ir["back"] - 0.06, ir["back"] + ir.get("depth", BASE_D) + FRONT_T, 0, CTR_Z - CTR_T, "Island", c_kit)
box("Island top", ix0, ix1, iy0, iy1, CTR_Z - CTR_T, CTR_Z, "Counter", c_kit)
# open shelves
SH = K["shelves"]
for k, z in enumerate(SH["heights"]):
    box(f"Open shelf {k}", SH["x"][0], SH["x"][1], HD - T - SH["depth"], HD - T, z, z + 0.15, "White Oak", c_kit)
# living room French barn door: D60-80 in the clerestory wall between living and dining (A-11)
BD = C.get("barn_door", {})
if BD.get("enabled"):
    bx0, bx1, bhd = min(CL["passages"], key=lambda p: abs((p[0] + p[1]) / 2 - BD["center_x"]))
    lw = (bx1 - bx0) / 2 + 0.15                     # each leaf laps the opening 0.15 ft
    lh = bhd + 0.2
    op = 0.0 if ARGS.get("web") else BD.get("open", 1.0)   # 0 = closed, 1 = fully open (web export starts closed)
    yf = YC2 + 0.12 if BD.get("side", "south") == "south" else YC - 0.25
    sgn = 1 if BD.get("side", "south") == "south" else -1
    st = 0.29
    for side, xc in (("L", bx0 + lw / 2 - 0.15 - op * lw), ("R", bx1 - lw / 2 + 0.15 + op * lw)):
        a0, a1 = xc - lw / 2, xc + lw / 2
        yy0, yy1 = sorted((yf, yf + sgn * 0.15))
        nm = f"Barn door {side}"
        box(nm + " stile a", a0, a0 + st, yy0, yy1, 0.05, lh, "White Oak", c_win)
        box(nm + " stile b", a1 - st, a1, yy0, yy1, 0.05, lh, "White Oak", c_win)
        box(nm + " top rail", a0 + st, a1 - st, yy0, yy1, lh - st, lh, "White Oak", c_win)
        box(nm + " bottom rail", a0 + st, a1 - st, yy0, yy1, 0.05, 0.95, "White Oak", c_win)
        nl = int(BD.get("lites_high", 1))
        zg0, zg1 = 0.95, lh - st
        for k in range(1, nl):
            zz = zg0 + (zg1 - zg0) * k / nl
            box(nm + f" muntin {k}", a0 + st, a1 - st, yy0, yy1, zz - 0.06, zz + 0.06, "White Oak", c_win)
        if BD.get("panel", "oak") == "glass":
            box(nm + " glass", a0 + st, a1 - st, yy0 + 0.06, yy1 - 0.06, zg0, zg1, "Glass", c_win)
        else:   # solid recessed white oak panel
            box(nm + " panel", a0 + st, a1 - st, yy0 + 0.04, yy1 - 0.04, zg0, zg1, "White Oak", c_win)
        for hx in (a0 + 0.5, a1 - 0.5):
            box(nm + " hanger", hx - 0.08, hx + 0.08, yy0 - 0.02, yy1 + 0.02, lh - 0.2, lh + 0.45, "Black Metal", c_win)
        hxp = a1 - 0.25 if side == "L" else a0 + 0.25
        box(nm + " pull", hxp - 0.03, hxp + 0.03, (yy0 if sgn > 0 else yy1) - 0.0, yy1 + 0.12 if sgn > 0 else yy0 - 0.12, 3.0, 4.5, "Black Metal", c_win)
    tl0, tl1 = bx0 - lw - 0.3, bx1 + lw + 0.3
    ty0, ty1 = sorted((YC2 + 0.02 if sgn > 0 else YC - 0.02, YC2 + 0.1 if sgn > 0 else YC - 0.1))
    box("Barn door track", tl0, tl1, ty0, ty1, lh + 0.3, lh + 0.45, "Black Metal", c_win)

# baths (simple placeholders, A-11 positions); replaced by real fixtures when [furnishings] is on (build_details.py)
FURN = C.get("furnishings", {})
if not FURN.get("enabled"):
    box("Tub Bath 2", 16.66, 21.83, 0.57, 3.0, 0, 1.7, "Porcelain", c_kit)
    box("Vanity Bath 2", 20.0, 22.58, 7.0, 10.5, 0, 2.9, "Cabinet Wood", c_kit)
    box("Vanity Bath 1", 31.58, 33.6, 23.3, 29.0, 0, 2.9, "Cabinet Wood", c_kit)
    box("Shower glass Bath 1", 38.1, 38.16, 24.0, 28.9, 0, 7.0, "Glass", c_kit)
    box("Vanity Powder", 6.0, 9.0, 28.55, 30.6, 0, 2.9, "Cabinet Wood", c_kit)
    for nm, x, y in (("Toilet Bath 2", 22.0, 5.8), ("Toilet Bath 1", 32.3, 30.8), ("Toilet Powder", 6.6, 32.4)):
        box(nm, x - 0.7, x + 0.7, y - 0.9, y + 0.9, 0, 1.4, "Porcelain", c_kit)
    box("Washer", 24.9, 27.4, 20.0, 22.4, 0, 3.2, "Porcelain", c_kit)
    box("Dryer", 27.5, 30.0, 20.0, 22.4, 0, 3.2, "Porcelain", c_kit)

# ------------------------------------------------------------------ garage, porch, greenhouse
GA = C["garage"]
if GA["enabled"]:
    gx0, gy0, gx1, gy1 = GA["rect"]
    gs = GA["pitch"] / 12
    gtop = lambda y: GA["south_wall_height"] + (gy1 - y) * gs
    prof = [(gy0, 0), (gy1, 0), (gy1, gtop(gy1)), (gy0, gtop(gy0))]
    gw = []
    gw.append(prism_x("Garage wall W", gx0, gx0 + 0.5, prof, "Siding", c_out))
    gw.append(prism_x("Garage wall E", gx1 - 0.5, gx1, prof, "Siding", c_out))
    gw.append(box("Garage wall N", gx0, gx1, gy0, gy0 + 0.5, 0, gtop(gy0), "Siding", c_out))
    gw.append(box("Garage wall S", gx0, gx1, gy1 - 0.5, gy1, 0, gtop(gy1), "Siding", c_out))
    box("Garage slab", gx0, gx1, gy0, gy1, -0.4, -0.05, "Concrete", c_out)
    sub = bpy.data.collections.new("cutters garage"); c_cut.children.link(sub)

    def gcut(x0, x1, y0, y1, z0, z1):
        o = box("cut garage", x0, x1, y0, y1, z0, z1, "Trim", sub); o.display_type = 'WIRE'

    for (s0, w) in GA["overhead_doors"]:
        gcut(gx0 + s0, gx0 + s0 + w, gy1 - 1, gy1 + 1, 0, 8)
        box("Overhead door", gx0 + s0, gx0 + s0 + w, gy1 - 0.4, gy1 - 0.3, 0, 8, "Garage Door", c_out)
        for k in range(1, 4):
            box("Overhead door panel line", gx0 + s0 + 0.1, gx0 + s0 + w - 0.1, gy1 - 0.31, gy1 - 0.27, k * 2 - 0.03, k * 2 + 0.03, "Trim", c_out)
        for k in range(4):
            wx = gx0 + s0 + 0.6 + k * (w - 1.2) / 4
            box("Overhead door glass", wx + 0.1, wx + (w - 1.2) / 4 - 0.1, gy1 - 0.27, gy1 - 0.25, 6.5, 7.5, "Glass", c_out)
    GWH = GA.get("north_window_height", 3.0)
    for s0 in GA["north_windows"]:
        gcut(gx0 + s0, gx0 + s0 + 3, gy0 - 1, gy0 + 1, GA["north_window_sill"], GA["north_window_sill"] + GWH)
        box("Garage awning glass", gx0 + s0, gx0 + s0 + 3, gy0 + 0.2, gy0 + 0.25, GA["north_window_sill"], GA["north_window_sill"] + GWH, "Glass", c_out)
        ws, wx0, wx1 = GA["north_window_sill"], gx0 + s0, gx0 + s0 + 3
        for (a0, a1, b0, b1) in ((wx0 - 0.33, wx0, ws, ws + GWH), (wx1, wx1 + 0.33, ws, ws + GWH),
                                 (wx0 - 0.33, wx1 + 0.33, ws + GWH, ws + GWH + 0.33), (wx0 - 0.33, wx1 + 0.33, ws - 0.33, ws)):
            box("Garage awning trim", a0, a1, gy0 - BAT_T - 0.02, gy0, b0, b1, "Trim", c_out)
    my0, my1 = GA["man_door_y"]
    gcut(gx0 - 1, gx0 + 1, my0, my1, 0, 6.67)
    box("Garage man door", gx0 + 0.2, gx0 + 0.3, my0, my1, 0, 6.67, "Trim", c_out)
    for w in gw:
        md = w.modifiers.new("openings", 'BOOLEAN'); md.operation = 'DIFFERENCE'; md.operand_type = 'COLLECTION'; md.collection = sub
    v0 = (gx0 - 1, gx1 + 1); yy0, yy1 = gy0 - 1, gy1 + 1
    v = [P(v0[0], yy0, gtop(yy0)), P(v0[1], yy0, gtop(yy0)), P(v0[1], yy1, gtop(yy1)), P(v0[0], yy1, gtop(yy1)),
         P(v0[0], yy0, gtop(yy0) + 0.8), P(v0[1], yy0, gtop(yy0) + 0.8), P(v0[1], yy1, gtop(yy1) + 0.8), P(v0[0], yy1, gtop(yy1) + 0.8)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    mesh_obj("Garage roof", v, f, None, c_out, mats=["Trim", "Standing Seam", "Drywall"], face_mats=[2, 1, 0, 0, 0, 0])
    seam_ribs("Garage roof", v0[0], v0[1], yy0, yy1, lambda y: gtop(y) + 0.8, c_out)
    battens("Garage battens N", lambda u, v: (gx0 + u, gy0 + v), 0, gx1 - gx0, 0, lambda u: gtop(gy0),
            [(s0 - TRIM_W, s0 + 3 + TRIM_W, GA["north_window_sill"] - 0.4, GA["north_window_sill"] + GWH + 0.4) for s0 in GA["north_windows"]], c_out)
    battens("Garage battens S", lambda u, v: (gx0 + u, gy1 - v), 0, gx1 - gx0, 0, lambda u: gtop(gy1),
            [(s0 - 0.1, s0 + w + 0.1, -1, 8.1) for (s0, w) in GA["overhead_doors"]], c_out)
    battens("Garage battens W", lambda u, v: (gx0 + v, u), gy0, gy1, 0, gtop, [(my0 - 0.1, my1 + 0.1, -1, 6.8)], c_out)
    battens("Garage battens E", lambda u, v: (gx1 - v, u), gy0, gy1, 0, gtop, [], c_out)
    for k_, (lx, ly) in enumerate(((gx0 + 8, gy0 + 9), (gx1 - 8, gy0 + 9), (gx0 + 8, gy1 - 9), (gx1 - 8, gy1 - 9))):
        ld = bpy.data.lights.new(f"Garage light {k_}", 'AREA'); ld.energy = 400; ld.size = 4 * F; ld.color = (1.0, 0.95, 0.88)
        lo = bpy.data.objects.new(f"Garage light {k_}", ld); lo.location = P(lx, ly, 9.0); c_out.objects.link(lo)
    # gravel drive (approximate, from drone photos): runs east then north to the road
    drive_n = -150
    if TERRAIN is not None and TER.get("show_roads", True) and os.path.exists(os.path.join(_tdir, "osm.json")):
        # with real terrain, run the north leg up to where SR 343 actually is (OpenStreetMap)
        xm = gx1 + 15; best = None
        for rd in json.load(open(os.path.join(_tdir, "osm.json")))["roads"]:
            for (a, b) in zip(rd["pts"][:-1], rd["pts"][1:]):
                if min(a[0], b[0]) <= xm <= max(a[0], b[0]) and a[0] != b[0]:
                    yy = a[1] + (xm - a[0]) * (b[1] - a[1]) / (b[0] - a[0])
                    if yy < gy0 and (best is None or yy > best[0]):
                        best = (yy, rd["width_ft"])
        if best:
            drive_n = best[0] + best[1] / 2 - 1
    if TERRAIN is None:
        box("Driveway", gx0, gx1, gy1, gy1 + GA["driveway_depth"], GROUND_Z, GROUND_Z + 0.12, GA.get("driveway_material", "Gravel"), c_site)
        for k, (a, b) in enumerate([((gx1, gy1 + 5), (gx1 + 22, gy1 + 20)), ((gx1 + 8, drive_n), (gx1 + 22, gy1 + 20))]):
            box(f"Gravel drive {k}", min(a[0], b[0]), max(a[0], b[0]), min(a[1], b[1]), max(a[1], b[1]), GROUND_Z, GROUND_Z + 0.05 + 0.03 * k, "Gravel", c_site)
    else:
        drape_rect("Driveway", gx0, gx1, gy1, gy1 + GA["driveway_depth"], 0.12, GA.get("driveway_material", "Gravel"), c_site)
        drape_rect("Gravel drive 0", gx1, gx1 + 22, gy1 + 5, gy1 + 20, 0.10, "Gravel", c_site)
        drape_rect("Gravel drive 1", gx1 + 8, gx1 + 22, drive_n, gy1 + 5, 0.13, "Gravel", c_site, step=3.0)

PO = C["porch"]
if PO["enabled"]:
    px0, py0, px1, py1 = PO["rect"]
    ptop = lambda y: PO["high_height"] - (y - py0) * PO["pitch"] / 12
    box("Porch slab", px0, px1, py0, py1, -0.35, -0.05, "Concrete", c_out)
    v = [P(px0, py0 - 0.5, ptop(py0 - 0.5)), P(px1, py0 - 0.5, ptop(py0 - 0.5)), P(px1, py1 + 1, ptop(py1 + 1)), P(px0, py1 + 1, ptop(py1 + 1)),
         P(px0, py0 - 0.5, ptop(py0 - 0.5) + 0.7), P(px1, py0 - 0.5, ptop(py0 - 0.5) + 0.7), P(px1, py1 + 1, ptop(py1 + 1) + 0.7), P(px0, py1 + 1, ptop(py1 + 1) + 0.7)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    mesh_obj("Porch roof", v, f, None, c_out, mats=["Trim", "Standing Seam", "Drywall"], face_mats=[2, 1, 0, 0, 0, 0])
    seam_ribs("Porch roof", px0, px1, py0 - 0.5, py1 + 1, lambda y: ptop(y) + 0.7, c_out)
    for yb in (py0 + 0.2, py1 - 0.6):
        box("Porch beam", px0, px1, yb, yb + 0.4, ptop(yb) - 1.0, ptop(yb), "Trim", c_out)
        for xp in PO["posts_x"]:
            box("Porch post", xp - 0.25, xp + 0.25, yb - 0.05, yb + 0.45, 0, ptop(yb) - 1.0, "Trim", c_out)

GH = C["greenhouse"]
if GH["enabled"]:
    hx0, hy0, hx1, hy1 = GH["rect"]
    htop = lambda y: GH["north_height"] - (y - hy0) * (GH["north_height"] - GH["south_height"]) / (hy1 - hy0)
    box("Greenhouse floor", hx0, hx1, hy0, hy1, GROUND_Z, -0.3, "Gravel", c_out)
    box("Greenhouse south glazing", hx0, hx1, hy1 - 0.05, hy1, 0, GH["south_height"], "Polycarbonate", c_out)
    prof = [(hy0, 0), (hy1, 0), (hy1, htop(hy1)), (hy0, htop(hy0))]
    prism_x("Greenhouse west glazing", hx0, hx0 + 0.05, prof, "Polycarbonate", c_out)
    prism_x("Greenhouse east glazing", hx1 - 0.05, hx1, prof, "Polycarbonate", c_out)
    v = [P(hx0, hy0, htop(hy0)), P(hx1, hy0, htop(hy0)), P(hx1, hy1, htop(hy1)), P(hx0, hy1, htop(hy1))]
    mesh_obj("Greenhouse roof glazing", v, [(0, 1, 2, 3)], "Polycarbonate", c_out)
    for k in range(9):
        x = hx0 + k * (hx1 - hx0) / 8
        rp = [(hy0, htop(hy0) - 0.45), (hy1, htop(hy1) - 0.45), (hy1, htop(hy1) + 0.05), (hy0, htop(hy0) + 0.05)]
        prism_x(f"Greenhouse rafter {k}", x - 0.12, x + 0.12, rp, "Black Metal", c_out)
        box(f"Greenhouse post {k}", x - 0.12, x + 0.12, hy1 - 0.3, hy1 - 0.06, 0, htop(hy1) - 0.45, "Black Metal", c_out)
    box("Greenhouse door gap", 22.5, 22.6, hy1 - 0.1, hy1 + 0.02, 0, 0, "Trim", c_out)

# ------------------------------------------------------------------ surroundings from the terrain data
c_sur = col("Surroundings")


def mat_leaves():
    m, n, l, b = node_mat("Tree Leaves")
    oi = n.new("ShaderNodeObjectInfo")
    tc = n.new("ShaderNodeTexCoord")
    noise = n.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 3.0; noise.inputs["Detail"].default_value = 6
    l.new(tc.outputs["Object"], noise.inputs["Vector"])
    add = n.new("ShaderNodeMath"); add.operation = 'ADD'
    mul = n.new("ShaderNodeMath"); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = 0.5
    l.new(oi.outputs["Random"], mul.inputs[0]); l.new(mul.outputs[0], add.inputs[0]); l.new(noise.outputs["Fac"], add.inputs[1])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = hexcol("#22361A"); ramp.color_ramp.elements[1].color = hexcol("#5E7A33")
    ramp.color_ramp.elements[0].position = 0.25; ramp.color_ramp.elements[1].position = 1.0
    l.new(add.outputs[0], ramp.inputs[0]); l.new(ramp.outputs[0], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.85
    n2 = n.new("ShaderNodeTexVoronoi"); n2.inputs["Scale"].default_value = 25
    l.new(tc.outputs["Object"], n2.inputs["Vector"])
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.8
    l.new(n2.outputs["Distance"], bump.inputs["Height"]); l.new(bump.outputs[0], b.inputs["Normal"])
    MATS["Tree Leaves"] = m


def crown_meshes(k=4):
    import random
    out = []
    for s in range(k):
        rnd = random.Random(100 + s)
        bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
        blobs = [Vector((rnd.uniform(-.5, .5), rnd.uniform(-.5, .5), rnd.uniform(-.3, .4))) for _ in range(5)]
        for v in bm.verts:
            d = v.co.normalized()
            bulge = sum(max(0.0, d.dot(bb.normalized())) ** 3 * 0.25 for bb in blobs)
            v.co = d * (0.85 + bulge + rnd.uniform(-0.05, 0.05))
        me = bpy.data.meshes.new(f"Crown {s}"); bm.to_mesh(me); bm.free()
        for p in me.polygons: p.use_smooth = True
        me.materials.append(MATS["Tree Leaves"]); out.append(me)
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=1.0, radius2=0.6, depth=1.0)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, 0.5))
    tm = bpy.data.meshes.new("Trunk"); bm.to_mesh(tm); bm.free(); tm.materials.append(MATS["Bark"])
    return out, tm


if TERRAIN is not None:
    import random
    simple("Asphalt", "#3A3A3C", 0.85)
    simple("Road Paint Yellow", "#D9A521", 0.6)
    simple("Bark", "#4A3B2E", 0.9)
    simple("Neighbor Siding", "#B9B4AA", 0.8)
    mat_leaves()
    osm_p = os.path.join(_tdir, "osm.json")
    osm = json.load(open(osm_p)) if os.path.exists(osm_p) else {"roads": [], "buildings": []}

    EX0, EX1, EY0, EY1 = (TERRAIN["x0f"], TERRAIN["x1f"], TERRAIN["y0f"], TERRAIN["y1f"]) if "x0f" in TERRAIN else (TX0, TX1, TY0, TY1)

    def clip_runs(pts, m=4.0):
        runs, cur = [], []
        for (x, y) in densify(pts, 5.0):
            if EX0 + m < x < EX1 - m and EY0 + m < y < EY1 - m:
                cur.append((x, y))
            elif cur:
                runs.append(cur); cur = []
        if cur: runs.append(cur)
        return [r for r in runs if len(r) > 1]

    if TER.get("show_roads", True):
        for rd in osm["roads"]:
            for k, run in enumerate(clip_runs(rd["pts"])):
                nm = f"Road {rd.get('name') or rd['highway']} {k}"
                surf = "Gravel" if (rd.get("surface") in ("gravel", "unpaved", "dirt") or rd["highway"] == "track") else "Asphalt"
                drape_ribbon(nm, run, rd["width_ft"], 0.18, surf, c_sur)
                if rd["highway"] in ("primary", "secondary", "tertiary") and surf == "Asphalt":
                    for off in (-0.3, 0.3):
                        drape_ribbon(nm + " center line", run, 0.35, 0.2, "Road Paint Yellow", c_sur, offset=off)
    if TER.get("show_osm_buildings", True):
        for bd in osm["buildings"]:
            pts = bd["pts"][:-1] if bd["pts"][0] == bd["pts"][-1] else bd["pts"]
            if not all(EX0 < x < EX1 and EY0 < y < EY1 for x, y in pts) or len(pts) < 3:
                continue
            bx, by = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
            if -40 < bx < 140 and -40 < by < 110:
                continue      # our own house/garage if OSM already has them
            zb = min(ground_z(x, y) for x, y in pts) - 0.3; zt = zb + bd["height_ft"]
            n_ = len(pts)
            v = [P(x, y, zb) for x, y in pts] + [P(x, y, zt) for x, y in pts]
            f = [tuple(range(n_)), tuple(range(n_, 2 * n_))] + [(i, (i + 1) % n_, n_ + (i + 1) % n_, n_ + i) for i in range(n_)]
            mesh_obj(f"Neighbor building {bd['id']}", v, f, "Neighbor Siding", c_sur)
    tp = os.path.join(_tdir, "trees.json")
    trees = json.load(open(tp)) if os.path.exists(tp) else []
    rnd = random.Random(7)
    dens = TER.get("tree_density", 1.0)
    crowns, trunk = crown_meshes()
    keep = 0
    if TER.get("tree_style", "blobs") == "procedural":
        _bt = os.path.join(HERE, "build_trees.py")
        exec(compile(open(_bt, encoding="utf-8").read(), _bt, "exec"))
        trees = []          # placed by build_trees.py
    for k, (x, y, h, r) in enumerate(trees):
        if rnd.random() > dens:
            continue
        if h < TER.get("min_tree_height_ft", 12.0):
            continue
        h = min(h, TER.get("max_tree_height_ft", 95.0))
        if -r - 3 < x < HW + r + 3 and -r - 3 < y < HD + r + 3:
            continue   # nothing grows through the house
        z0 = ground_z(x, y)
        cr = max(min(r * 1.1, 0.32 * h), 0.22 * h, 4.0); ch = max(h * 0.7, cr * 1.3)   # crowns down to ~30% of height
        tr = bpy.data.objects.new(f"Tree {k} trunk", trunk); c_sur.objects.link(tr)
        tw = max(0.35, h * 0.012)
        tr.location = P(x, y, z0 - 0.5); tr.scale = (tw * F, tw * F, (h - ch * 0.6 + 0.5) * F)
        cro = bpy.data.objects.new(f"Tree {k} crown", crowns[k % len(crowns)]); c_sur.objects.link(cro)
        cro.location = P(x, y, z0 + h - ch / 2); cro.scale = (cr * F, cr * F, ch / 2 * F)
        cro.rotation_euler = (0, 0, rnd.uniform(0, 6.283))
        # understory (saplings and brush) so the woods do not read as bare poles under a lid
        if h > 30:
            for u in range(2):
                ux, uy = x + rnd.uniform(-0.6, 0.6) * cr, y + rnd.uniform(-0.6, 0.6) * cr
                us = rnd.uniform(0.12, 0.2) * h; uz = ground_z(ux, uy)
                ub = bpy.data.objects.new(f"Tree {k} understory {u}", crowns[(k + u + 1) % len(crowns)]); c_sur.objects.link(ub)
                ub.location = P(ux, uy, uz + us * 0.6); ub.scale = (us * F, us * F, us * 0.75 * F)
                ub.rotation_euler = (0, 0, rnd.uniform(0, 6.283))
        keep += 1
    print(f"surroundings: {keep} trees, {len(osm['roads'])} roads, {len(osm['buildings'])} OSM buildings")

# ------------------------------------------------------------------ utilities
U = C["utilities"]
geo = G["geothermal"]; sep = G["septic"]


def util_line(name, pts, depth, radius, mat):
    if TERRAIN is None:
        return tube(name, pts, -depth, radius, mat, c_util)
    pts = densify(pts, 4.0)          # depths are below the local ground surface
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'
    sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
    for i, (x, y) in enumerate(pts):
        p = P(x, y, ground_z(x, y) - depth); sp.points[i].co = (p.x, p.y, p.z, 1)
    cu.bevel_depth = radius * F; cu.bevel_resolution = 3; cu.use_fill_caps = True
    ob = bpy.data.objects.new(name, cu); c_util.objects.link(ob); ob.data.materials.append(MATS[mat])
    return ob


def marker(name, pts, width, mat):
    if TERRAIN is None:
        return ribbon(name, pts, GROUND_Z + 0.04, width, mat, c_mark)
    return drape_ribbon(name, pts, width, 0.12, mat, c_mark)


util_line("Geothermal trunk", geo["trunk"], U["geothermal_depth"], 0.25, "Geothermal Pipe")
for nm, pts in geo["branches"].items():
    util_line("Geothermal branch " + nm, pts, U["geothermal_depth"], 0.25, "Geothermal Pipe")
for nm, pts in sep["laterals"].items():
    util_line("Septic lateral " + nm, pts, U["septic_depth"], 0.4, "Septic Pipe")
util_line("Septic header", sep["header_pvc"], U["septic_depth"], 0.25, "Septic Pipe")
if U["show_surface_markers"]:
    marker("Marker geothermal trunk", geo["trunk"], 1.2, "Geothermal Marker")
    for nm, pts in geo["branches"].items():
        marker("Marker geothermal " + nm, pts, 1.2, "Geothermal Marker")
    for nm, pts in sep["laterals"].items():
        marker("Marker septic " + nm, pts, 1.6, "Septic Marker")
    marker("Marker septic header", sep["header_pvc"], 1.0, "Septic Marker")
else:
    c_mark.hide_render = True

# ------------------------------------------------------------------ lighting & world
RC = C["render"]
world = bpy.data.worlds.new("Sky"); scene.world = world; world.use_nodes = True
wn = world.node_tree.nodes; wl = world.node_tree.links
bg = wn["Background"]
sky = wn.new("ShaderNodeTexSky")
az, el = math.radians(RC["sun_azimuth_deg"]), math.radians(RC["sun_elevation_deg"])
for t in ('MULTIPLE_SCATTERING', 'SINGLE_SCATTERING', 'NISHITA', 'HOSEK_WILKIE'):
    try:
        sky.sky_type = t; break
    except Exception:
        continue
try:
    sky.sun_elevation = el; sky.sun_rotation = math.pi / 2 - az + math.pi
    sky.sun_disc = False
except Exception:
    pass
wl.new(sky.outputs[0], bg.inputs[0]); bg.inputs[1].default_value = 0.35
sun_d = bpy.data.lights.new("Sun", 'SUN'); sun_d.energy = 4.0; sun_d.angle = math.radians(1.5)
sun_d.color = (1.0, 0.96, 0.9)
sun = bpy.data.objects.new("Sun", sun_d); c_cam.objects.link(sun)
# direction: light travels from (az, el) toward the ground; plan y is south so north = +Y
d = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
sun.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()

# interior fill lights (like recessed cans)
for k, (x, y, z) in enumerate([(8, 44, 8.4), (22, 44, 8.4), (36, 44, 8.4), (22, 29, 12), (6, 16, 8.6), (36, 7, 9.5),
                               (26, 6, 9.5), (14, 13, 8.6), (36, 28, 8.6), (24, 19, 8.6), (14.4, 30, 12)]):
    ld = bpy.data.lights.new(f"Can {k}", 'POINT'); ld.energy = C["render"].get("interior_light_w", 250); ld.shadow_soft_size = 0.3; ld.color = (1.0, 0.86, 0.7)
    lo = bpy.data.objects.new(f"Can {k}", ld); lo.location = P(x, y, z); c_cam.objects.link(lo)

# ------------------------------------------------------------------ realism pass: furniture, fixtures, trim, PBR, HDRI
if FURN.get("enabled") or C.get("assets", {}).get("enabled"):
    _bd = os.path.join(HERE, "build_details.py")
    exec(compile(open(_bd, encoding="utf-8").read(), _bd, "exec"))

# ------------------------------------------------------------------ cameras
def add_camera(name, lens=24):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.clip_start = 0.05; cd.clip_end = 2000
    co = bpy.data.objects.new(name, cd); c_cam.objects.link(co)
    return co


def look(cam, frm, to):
    cam.location = P(*frm)
    cam.rotation_euler = (P(*to) - P(*frm)).to_track_quat('-Z', 'Y').to_euler()


STILLS = {
    "exterior_southwest": ((-40, 110, 28), (24, 36, 8), 26),
    "exterior_southeast": ((115, 100, 24), (45, 34, 8), 26),
    "exterior_northeast": ((105, -55, 30), (40, 25, 8), 26),
    "exterior_northwest": ((-45, -45, 22), (22, 25, 9), 26),
    "exterior_west_closeup": ((-14, 30, 6), (0, 18, 6), 30),
    "interior_dining_kitchen": ((41.8, 43.4, 5.4), (6, 45, 6.5), 16) if FURN.get("enabled") else ((38, 49, 5.4), (6, 41, 7.5), 16),
    "interior_living_clerestory": ((24, 26, 5.0), (22, 44, 13.5), 15),
    "interior_kitchen": ((22, 40, 5.4), (2, 47, 4.5), 18),
    "interior_fridge_wall": ((10.5, 49.5, 5.3), (6, 36, 4.6), 16),
    "interior_island_cooktop": ((17.5, 47.5, 5.0), (3, 45.5, 3.6), 18),
    "closeup_cabinets": ((9.6, 47.4, 3.9), (9.2, 51.4, 2.0), 30),
    "closeup_barn_door": ((25.5, 41.5, 4.6), (24.6, 35.2, 4.2), 30),
    "closeup_siding": ((-5.5, 21.0, 4.5), (0, 17.5, 5.5), 35),
    "interior_living_sofa":((19.5, 27.0, 4.6), (31, 28.2, 2.6), 20),
    "interior_pantry_fridge":((4.3, 41.6, 5.0), (2.7, 35.2, 3.6), 20),
    "interior_island_front":((10.5, 50.6, 4.6), (10, 44, 1.8), 18),
    "interior_barn_door": ((24, 47, 5.2), (23.9, 35, 5.5), 18),
    "interior_bed1": ((32.2, 10.1, 5.2), (41, 4, 4.5), 16) if FURN.get("enabled") else ((30.5, 13.5, 5.2), (40, 2, 6), 16),
    "utilities_topdown": None,
    # dollhouse cutaways: everything above the cut height removed (roofs, ceilings, upper walls), looking down into the rooms
    "dollhouse_southwest": ((-30, 88, 62), (22, 27, 0), 24),
    "dollhouse_southeast": ((80, 92, 60), (24, 28, 0), 24),
    "dollhouse_northeast": ((82, -38, 64), (22, 24, 0), 24),
    "dollhouse_northwest": ((-36, -34, 60), (21, 25, 0), 24),
    "dollhouse_living_closeup": ((22.5, 42.0, 24), (25.5, 28.8, 1.5), 26),
    "dollhouse_kitchen_closeup":((-9, 67, 27), (9, 45, 1.5), 26),
    "dollhouse_bedrooms_closeup": ((54, -22, 36), (24, 9, 2), 24),
    "dollhouse_plan_topdown": "plan",
}
DOLL_CUT = 8.6      # ft above slab; below the 9' flat ceilings, above the 8' tall cabinets


def apply_dollhouse_cut():
    """boolean away everything above DOLL_CUT on the house, garage, porch and greenhouse."""
    cut = float(ARGS.get("cut", DOLL_CUT))
    ob = box("cut dollhouse", -30, HW + 80, -30, HD + 50, cut, 80, "Trim", c_cut)
    ob.display_type = 'WIRE'
    n_ = 0
    roots = [c_house, c_out]
    seen = set()

    def walk(c):
        for o in c.objects:
            if o.type in ('MESH', 'CURVE') and o.name not in seen and not o.name.startswith("cut "):
                seen.add(o.name)
                yield o
        for ch in c.children:
            yield from walk(ch)
    for root in roots:
        for o in list(walk(root)):
            if o.type != 'MESH':
                continue
            if o.name.startswith(("Greenhouse roof", "Greenhouse rafter", "Porch roof", "Porch beam")):
                o.hide_render = True; n_ += 1; continue   # sloped roofs that would hide the rooms below
            zs = [(o.matrix_world @ Vector(v)).z for v in o.bound_box]
            if max(zs) <= cut * F + 1e-4:
                continue
            if min(zs) >= cut * F - 1e-4:
                o.hide_render = True; n_ += 1; continue   # entirely above the cut (roofs, seams, clerestory sash)
            md = o.modifiers.new("dollhouse cut", 'BOOLEAN'); md.operation = 'DIFFERENCE'; md.object = ob
            try:
                md.solver = 'EXACT'
            except Exception:
                pass
            n_ += 1
    # ceiling lights would float in the open air: keep them but soften
    print(f"dollhouse cut at {cut} ft: {n_} objects trimmed or hidden")


def setup_render(res=None, samples=None):
    scene.render.engine = 'CYCLES'
    try:
        scene.cycles.device = 'CPU'
    except Exception:
        pass
    scene.cycles.samples = int(samples or RC["samples"])
    scene.cycles.use_denoising = True
    try:
        scene.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    scene.cycles.max_bounces = 6; scene.cycles.transmission_bounces = 6; scene.cycles.glossy_bounces = 3
    scene.cycles.diffuse_bounces = 3
    scene.cycles.use_adaptive_sampling = True
    # temporal stability: fixed seed (noise does not crawl between frames), tighter noise threshold, denoiser guided by
    # albedo + normal passes with the accurate prefilter
    scene.cycles.adaptive_threshold = RC.get("adaptive_threshold", 0.01)
    scene.cycles.seed = 0; scene.cycles.use_animated_seed = False
    for k_, v_ in (("denoising_input_passes", 'RGB_ALBEDO_NORMAL'), ("denoising_prefilter", 'ACCURATE'), ("denoising_quality", 'HIGH')):
        try:
            setattr(scene.cycles, k_, v_)
        except Exception:
            pass
    # animations: keep the synced scene/BVH between frames (only the camera moves) instead of rebuilding on the CPU
    scene.render.use_persistent_data = True
    w, h = (map(int, res.split("x")) if res else RC["resolution"])
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = 'AgX'
    try:
        scene.view_settings.look = RC.get("look", 'AgX - Base Contrast')
    except Exception:
        pass
    scene.render.fps = RC["fps"]
    if ARGS.get("gpu"):   # --gpu 1 : use the first GPU backend Blender finds (OptiX, CUDA, HIP, oneAPI, Metal)
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for t in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
            try:
                prefs.compute_device_type = t
                prefs.get_devices()
                gpus = [d for d in prefs.devices if d.type == t]
                if gpus:
                    for d in prefs.devices:
                        d.use = d.type == t
                    scene.cycles.device = 'GPU'
                    try:
                        scene.cycles.denoising_use_gpu = True   # same OpenImageDenoise, run on the GPU
                    except Exception:
                        pass
                    print("GPU render:", t, [d.name for d in gpus])
                    break
            except Exception:
                continue
        else:
            print("No GPU found, rendering on CPU")


def _catmull(pts, n_out):
    """centripetal-ish Catmull-Rom through pts (plan ft tuples), densely sampled."""
    P_ = [Vector(p) for p in pts]
    P_ = [P_[0] + (P_[0] - P_[1])] + P_ + [P_[-1] + (P_[-1] - P_[-2])]
    out = []
    for i in range(1, len(P_) - 2):
        p0, p1, p2, p3 = P_[i - 1], P_[i], P_[i + 1], P_[i + 2]
        for s in range(n_out):
            t = s / n_out
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P_[-2])
    return out


def keyframe_path(cam, target, keys, fps):
    """keys: list of (t_seconds, eye(x,y,z), look(x,y,z)). Smooth constant-speed camera: Catmull-Rom spline through the
    eye points, re-timed by arc length (eased in/out at the ends), keyed on every frame with linear interpolation.
    The look target follows its own spline at the same parameter, so the view turns smoothly too."""
    if C.get("render", {}).get("smooth_camera", True):
        nseg = 60
        eyes = _catmull([k[1] for k in keys], nseg); looks = _catmull([k[2] for k in keys], nseg)
        seglen = [0.0]
        for a, b in zip(eyes[:-1], eyes[1:]):
            seglen.append(seglen[-1] + (b - a).length)
        total = seglen[-1]
        f0 = int(round(keys[0][0] * fps)) + 1; f1 = int(round(keys[-1][0] * fps)) + 1
        j = 0
        for f in range(f0, f1 + 1):
            u = (f - f0) / max(1, f1 - f0)
            ease = 0.08                                   # 8% ease-in and ease-out, constant speed between
            if u < ease:
                w = (u * u) / (2 * ease * (1 - ease))
            elif u > 1 - ease:
                w = 1 - ((1 - u) ** 2) / (2 * ease * (1 - ease))
            else:
                w = (u - ease / 2) / (1 - ease)
            d = w * total
            while j < len(seglen) - 2 and seglen[j + 1] < d:
                j += 1
            g = (d - seglen[j]) / max(seglen[j + 1] - seglen[j], 1e-9)
            e = eyes[j].lerp(eyes[j + 1], g); t_ = looks[j].lerp(looks[j + 1], g)
            cam.location = P(*e); cam.keyframe_insert("location", frame=f)
            target.location = P(*t_); target.keyframe_insert("location", frame=f)
        for ob in (cam, target):
            ad = ob.animation_data
            try:
                fcs = ad.action.fcurves
            except AttributeError:
                fcs = [fc for layer in ad.action.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves]
            for fc in fcs:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
        return
    for t, eye, to in keys:
        f = int(round(t * fps)) + 1
        cam.location = P(*eye); cam.keyframe_insert("location", frame=f)
        target.location = P(*to); target.keyframe_insert("location", frame=f)
    for ob in (cam, target):
        ad = ob.animation_data
        if ad and ad.action:
            try:
                fcs = ad.action.fcurves
            except AttributeError:
                fcs = [fc for layer in ad.action.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves]
            for fc in fcs:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'BEZIER'; kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'


def track(cam, target):
    c = cam.constraints.new('TRACK_TO'); c.target = target; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'


def anim_exterior():
    fps = RC["fps"]; dur = RC["exterior_seconds"]
    cam = add_camera("Cam exterior orbit", 22)
    tgt = bpy.data.objects.new("Target exterior", None); c_cam.objects.link(tgt)
    track(cam, tgt)
    cx, cy = 50, 35
    keys = []
    steps = 16 if TERRAIN is None else 32
    trees = []
    if TERRAIN is not None and os.path.exists(os.path.join(_tdir, "trees.json")):
        trees = json.load(open(os.path.join(_tdir, "trees.json")))
    for i in range(steps + 1):
        t = dur * i / steps
        a = math.radians(225 - 360 * i / steps)      # start southwest, go around clockwise seen from above
        rad = 115 - 20 * math.sin(math.pi * i / steps)
        h = 14 + 26 * (i / steps) ** 2
        # real terrain: pull the orbit in where it would fly through a tree crown, keep height above local ground
        while trees and rad > 60 and any(math.hypot(cx + rad * math.cos(a) - x, cy - rad * math.sin(a) - y) < r + 10
                                         and h + ground_z(cx + rad * math.cos(a), cy - rad * math.sin(a)) < ground_z(x, y) + th + 6
                                         for (x, y, th, r) in trees):
            rad -= 3
        ex, ey = cx + rad * math.cos(a), cy - rad * math.sin(a)
        h += max(0.0, ground_z(ex, ey) - GROUND_Z)
        keys.append((t, (ex, ey, h), (cx - 8, cy, 9)))
    keyframe_path(cam, tgt, keys, fps)
    scene.frame_start, scene.frame_end = 1, int(dur * fps)
    return cam


def anim_interior():
    fps = RC["fps"]; dur = RC["interior_seconds"]
    cam = add_camera("Cam interior walk", 16)
    tgt = bpy.data.objects.new("Target interior", None); c_cam.objects.link(tgt)
    track(cam, tgt)
    E = 5.4
    pts = [((54, 39.5, E), (42, 39.5, 6)), ((45.5, 39.5, E), (34, 42, 6)), ((37, 43, E), (24, 46, 6)),
           ((25, 45.5, E), (8, 46, 5.5)), ((13, 41.5, E), (2, 46.5, 4.5)), ((15.5, 39, E), (24, 33, 7)),
           ((23.9, 37.5, E), (23.9, 27, 7)), ((23.5, 30.5, E), (23, 37.5, 16.5)), ((19.5, 25.2, E), (12, 24.6, 6)),
           ((14.4, 24.0, E), (14.4, 14, 6)), ((14.4, 16.2, E), (26, 13, 6)), ((24.5, 13.0, E), (34, 12.5, 6)),
           ((31.5, 12.6, E), (38, 3, 5.5)), ((36.0, 8.5, E), (43, 8, 6))]
    if FURN.get("enabled"):   # keep the walk clear of the furniture: past the dining chairs, island stools and bed 1
        pts[2] = ((37, 41.6, E), (24, 46, 6))
        pts[4] = ((13.6, 40.2, E), (2, 46.5, 4.5))
        pts[13] = ((35.0, 9.9, E), (43, 5.5, 4.5))
    n = len(pts) - 1
    keys = [(dur * i / n, e, t) for i, (e, t) in enumerate(pts)]
    keyframe_path(cam, tgt, keys, fps)
    scene.frame_start, scene.frame_end = 1, int(dur * fps)
    return cam


def render_stills(out):
    os.makedirs(out, exist_ok=True)
    only = ARGS.get("only")
    cut_done = False
    for name, spec in STILLS.items():
        if only and name not in only.split(","):
            continue
        if not only and name.startswith("dollhouse"):
            continue          # dollhouse stills only when asked for: --only dollhouse_... (they remove the roof for good)
        if name.startswith("dollhouse") and not cut_done:
            apply_dollhouse_cut(); cut_done = True
        if spec == "plan":
            cam = add_camera("Cam plan top")
            cam.data.type = 'ORTHO'; cam.data.ortho_scale = 130 * F
            cam.location = P(48, 36, 300); cam.rotation_euler = (0, 0, 0)
            scene.camera = cam
            scene.render.filepath = os.path.join(out, name + ".png")
            bpy.ops.render.render(write_still=True)
            continue
        if spec is None:
            cam = add_camera("Cam utilities top")
            cam.data.type = 'ORTHO'; cam.data.ortho_scale = 470 * F
            look(cam, (-20, 120, 400), (-20, 120.01, 0))
            cam.rotation_euler = (0, 0, 0)
            scene.camera = cam
            vis = []
            for c_ in (c_roof,):
                c_.hide_render = True; vis.append(c_)
            scene.render.filepath = os.path.join(out, name + ".png")
            bpy.ops.render.render(write_still=True)
            for c_ in vis:
                c_.hide_render = False
            continue
        frm, to, lens = spec
        cam = add_camera("Cam " + name, lens); look(cam, frm, to); scene.camera = cam
        scene.render.filepath = os.path.join(out, name + ".png")
        bpy.ops.render.render(write_still=True)


def render_dollhouse(out):
    """Cutaway stills: roofs and ceilings hidden, walls sliced at cut height (config [dollhouse])."""
    DH = C.get("dollhouse", {})
    cz = DH.get("cut_height", 9.25)
    os.makedirs(out, exist_ok=True)
    for c_ in (c_roof,):
        c_.hide_render = True
    hide_words = ("Flat ceiling", "Vault ceiling", "roof", "seam", "rafter", "Hood chimney", "Barn door track",
                  "Fascia", "Rake", "Soffit", "Gutter", "Downspout offset", "pendant")
    extra = [o for c_ in bpy.data.collections if c_.name in ("Exterior Details", "Furniture and Fixtures") for o in c_.objects]
    for ob in list(c_ceil.objects) + list(c_out.objects) + list(c_kit.objects) + list(c_win.objects) + extra:
        if any(w.lower() in ob.name.lower() for w in hide_words):
            ob.hide_render = True
    # anything in windows/doors that sits entirely above the cut (clerestory, loft, transom) is hidden
    for ob in c_win.objects:
        zs = [(ob.matrix_world @ v.co).z / F for v in ob.data.vertices] if ob.type == 'MESH' else [0]
        if min(zs) > cz - 0.05:
            ob.hide_render = True
    # slice walls with one big box
    bpy.ops.mesh.primitive_cube_add(size=1)
    cutter = bpy.context.active_object; cutter.name = "Dollhouse cut"
    for c in cutter.users_collection: c.objects.unlink(cutter)
    c_cut.objects.link(cutter)
    cutter.scale = (1000 * F, 1000 * F, 100 * F); cutter.location = (0, 0, (cz + 50) * F)
    targets = list(c_ext.objects) + list(c_int.objects) + list(c_win.objects) + \
        [o for o in c_out.objects if o.name.startswith(("Garage wall", "Garage battens", "Greenhouse"))]
    for ob in targets:
        if ob.type != 'MESH' or ob.hide_render:
            continue
        md = ob.modifiers.new("dollhouse cut", 'BOOLEAN'); md.operation = 'DIFFERENCE'; md.object = cutter
        for sv in ("FLOAT", "FAST", "EXACT"):
            try:
                md.solver = sv; break
            except Exception:
                continue
    cx, cy = HW / 2, HD / 2
    views = DH.get("views", {
        "dollhouse_southwest": [-38, 95, 70, 30],
        "dollhouse_southeast": [82, 95, 70, 30],
        "dollhouse_northeast": [82, -45, 70, 30],
        "dollhouse_northwest": [-38, -45, 70, 30],
    })
    for name, (x, y, z, lens) in views.items():
        cam = add_camera("Cam " + name, lens); look(cam, (x, y, z), (cx, cy, 1.5)); scene.camera = cam
        scene.render.filepath = os.path.join(out, name + ".png")
        bpy.ops.render.render(write_still=True)
    if DH.get("plan_view", True):
        pcz = DH.get("plan_cut_height", 4.5)      # lower slice so door openings read in plan
        cutter.location = (0, 0, (pcz + 50) * F)
        for ob in c_ceil.objects:                 # loft floor and ladder would cover Bath 1
            ob.hide_render = True
        for ob in c_win.objects:
            if ob.type == 'MESH' and min((ob.matrix_world @ v.co).z / F for v in ob.data.vertices) > pcz - 0.05:
                ob.hide_render = True
        cam = add_camera("Cam dollhouse plan")
        cam.data.type = 'ORTHO'; cam.data.ortho_scale = 62 * F
        look(cam, (cx, cy, 200), (cx, cy + 0.01, 0)); cam.rotation_euler = (0, 0, 0)
        scene.camera = cam
        r = scene.render; rx, ry = r.resolution_x, r.resolution_y
        r.resolution_x, r.resolution_y = int(ry * 1.0), ry
        r.filepath = os.path.join(out, "dollhouse_plan.png")
        bpy.ops.render.render(write_still=True)
        r.resolution_x, r.resolution_y = rx, ry


# ------------------------------------------------------------------ main
setup_render(ARGS.get("res"), ARGS.get("samples"))
cam_ext = anim_exterior()
scene.frame_set(1)
if ARGS["save"]:
    scene.camera = cam_ext
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(ARGS["save"]))
mode = ARGS.get("render")
if mode == "stills":
    render_stills(ARGS["out"])
elif mode == "dollhouse":
    render_dollhouse(ARGS["out"])
elif mode in ("exterior", "interior"):
    cam = cam_ext if mode == "exterior" else anim_interior()
    scene.camera = cam
    if ARGS.get("frames"):
        a, b = map(int, ARGS["frames"].split(":")); scene.frame_start, scene.frame_end = a, b
    scene.frame_step = int(ARGS.get("step", 1))
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = os.path.join(ARGS["out"], mode, "f_")
    scene.render.use_overwrite = False      # resume: frames already on disk are skipped
    scene.render.use_placeholder = True
    bpy.ops.render.render(animation=True)
print("BUILD OK")
