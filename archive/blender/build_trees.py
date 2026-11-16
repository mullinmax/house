"""Procedural SW-Ohio hardwoods (oak, maple, ash, hickory) for build_house.py (exec'd inside it).

Each species gets 2 seeded variants: a bark mesh (trunk, limbs, branches as tapered tubes with UVs) and a leaf mesh
(alpha-cut leaf cards using ambientCG leaf atlases). Variants live in collections and every tree is a collection
instance, so 300 near trees + 5000 far-ring trees stay light on the 4 GB GPU.
Near trees (data/terrain/trees.json, full-density lidar) use the detailed variants; far-ring trees
(data/terrain/far_trees.json, sparse lidar) use a low-poly version of the same species.
"""
import glob as _glob

_ADIR = os.path.join(HERE, C.get("assets", {}).get("dir", "assets"))
_AC = C.get("assets", {}).get("ambientcg", {})


def _acg(aid, kind):
    f = _glob.glob(os.path.join(_ADIR, "ambientcg", aid or "-", f"*_{kind}.jpg"))
    return f[0] if f else None


SPECIES = {   # ratio = crown radius / height, bole = clear trunk fraction, elev = branch angle above horizontal (deg)
    "oak":     dict(ratio=0.36, bole=0.30, n_main=7, elev=(18, 42), split=0.48, curve=0.25, leaf="leaf_a", tint="#4F6B2C", bark="bark_b", card=0.024),
    "maple":   dict(ratio=0.30, bole=0.30, n_main=10, elev=(38, 60), split=0.60, curve=0.35, leaf="leaf_c", tint="#5C7A2E", bark="bark", card=0.022),
    "ash":     dict(ratio=0.25, bole=0.42, n_main=8, elev=(45, 65), split=0.85, curve=0.4, leaf="leaf_b", tint="#5E7A34", bark="bark_b", card=0.022),
    "hickory": dict(ratio=0.22, bole=0.45, n_main=9, elev=(42, 68), split=0.9, curve=0.45, leaf="leaf_b", tint="#6B7F33", bark="bark_b", card=0.021),
}


def _frame(d):
    d = d.normalized()
    a = Vector((0, 0, 1)) if abs(d.z) < 0.95 else Vector((1, 0, 0))
    u = d.cross(a).normalized(); w = d.cross(u).normalized()
    return u, w


def _tube(V, Fc, UV, pts, radii, sides):
    """append a tapered tube through pts to the lists (one ring per point)."""
    base = len(V); rings = []
    vlen = 0.0
    for i, (p, r) in enumerate(zip(pts, radii)):
        d = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)])
        u, w = _frame(d)
        if i:
            vlen += (pts[i] - pts[i - 1]).length
        ring = []
        for s in range(sides + 1):
            a = 2 * math.pi * s / sides
            V.append(p + (u * math.cos(a) + w * math.sin(a)) * r)
            UV.append((s / sides, vlen / max(2 * math.pi * radii[0], 1e-4) * 0.5))
            ring.append(len(V) - 1)
        rings.append(ring)
    for i in range(len(rings) - 1):
        for s in range(sides):
            Fc.append((rings[i][s], rings[i][s + 1], rings[i + 1][s + 1], rings[i + 1][s]))


def _branch_pts(rng, start, d, length, nseg, curve, droop=0.0):
    pts = [start.copy()]; p = start.copy(); dd = d.normalized()
    for k in range(nseg):
        dd = (dd + Vector((rng.uniform(-.15, .15), rng.uniform(-.15, .15), curve / nseg - droop * k / nseg))).normalized()
        p = p + dd * (length / nseg); pts.append(p.copy())
    return pts


def _rot_about(v, axis, ang):
    from mathutils import Matrix
    return Matrix.Rotation(ang, 3, axis) @ v


def gen_tree(sp, seed, detail=1.0):
    """unit-height tree (1.0 = full height). Returns (bark verts, faces, uvs), (leaf verts, faces, uvs)."""
    rng = random.Random(seed)
    BV, BF, BU = [], [], []
    LV, LF, LU = [], [], []
    r0 = 0.017
    lean = Vector((rng.uniform(-.03, .03), rng.uniform(-.03, .03), 1.0)).normalized()
    top = sp["split"]
    trunk = _branch_pts(rng, Vector((0, 0, -0.03)), lean, top + 0.03, 7, 0.0)
    _tube(BV, BF, BU, trunk, [r0 * (1 - 0.55 * i / 7) for i in range(8)], 10 if detail > 0.5 else 6)
    tips = []

    def leaves_at(p, n, rad, size):
        for _ in range(n):
            c = p + Vector((rng.gauss(0, rad), rng.gauss(0, rad), rng.gauss(0, rad * 0.8)))
            nrm = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.2, 1.0))).normalized()
            u, w = _frame(nrm)
            ang = rng.uniform(0, 6.283); u, w = u * math.cos(ang) + w * math.sin(ang), -u * math.sin(ang) + w * math.cos(ang)
            s = size * rng.uniform(0.75, 1.25)
            b = len(LV)
            for (a_, b_) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                LV.append(c + u * a_ * s / 2 + w * b_ * s / 2)
            LU.extend([(0, 0), (1, 0), (1, 1), (0, 1)])
            LF.append((b, b + 1, b + 2, b + 3))

    R = sp["ratio"]; bole = sp["bole"]
    nm = sp["n_main"]
    ga = math.radians(137.5)
    for i in range(nm):
        t = bole + (0.95 - bole) * (i + 0.5) / nm
        # attach to the trunk polyline at height t (or at the split point for decurrent crowns)
        th = min(t, top)
        k = min(int(th / top * 7), 6); f_ = th / top * 7 - k
        start = trunk[k].lerp(trunk[k + 1], f_)
        az = i * ga + rng.uniform(-.3, .3)
        el = math.radians(rng.uniform(*sp["elev"])) * (0.75 + 0.5 * (t - bole) / (1 - bole))
        d = Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)))
        env = math.sin(math.pi * min(1.0, (t - bole) / (1 - bole) * 0.85 + 0.15))
        L = max(0.12, (R * 1.15 * env) / max(math.cos(el), 0.35) + (1 - t) * 0.25)
        L = min(L, (1.0 - start.z) / max(math.sin(el), 0.2) * 1.05 + R * 0.4)
        pts = _branch_pts(rng, start, d, L, 5, sp["curve"] * L, droop=0.06)
        rr = r0 * 0.55 * (1 - 0.35 * (t - bole))
        _tube(BV, BF, BU, pts, [rr * (1 - 0.8 * j / 5) for j in range(6)], 6 if detail > 0.5 else 4)
        nchild = int(5 * detail) + 1 if detail > 0.5 else 4
        for c in range(nchild):
            u_ = rng.uniform(0.3, 0.95); j = min(int(u_ * 5), 4); g = u_ * 5 - j
            cs = pts[j].lerp(pts[j + 1], g); pd = (pts[j + 1] - pts[j]).normalized()
            axis = _frame(pd)[0]
            cd = _rot_about(pd, axis, math.radians(rng.uniform(30, 55)))
            cd = _rot_about(cd, pd, rng.uniform(0, 6.283))
            cd.z += 0.25; cd.normalize()
            cl = L * rng.uniform(0.35, 0.55) * (1.1 - 0.4 * u_)
            cp = _branch_pts(rng, cs, cd, cl, 3, sp["curve"] * cl * 0.6, droop=0.08)
            cr = rr * 0.45
            if detail > 0.5:
                _tube(BV, BF, BU, cp, [cr, cr * 0.7, cr * 0.45, cr * 0.2], 4)
            for tw in range(3 if detail > 0.5 else 1):
                v_ = rng.uniform(0.35, 1.0); jj = min(int(v_ * 3), 2); gg = v_ * 3 - jj
                ts = cp[jj].lerp(cp[jj + 1], gg)
                td = (cp[-1] - cp[0]).normalized() + Vector((rng.uniform(-.6, .6), rng.uniform(-.6, .6), rng.uniform(0, .5)))
                tl = cl * rng.uniform(0.3, 0.5)
                tip = ts + td.normalized() * tl
                tips.append((ts, tip))
        tips.append((pts[-2], pts[-1]))
    # leader for excurrent species continues to the top
    if top < 0.95:
        lp = _branch_pts(rng, trunk[-1], Vector((0, 0, 1)), 1.0 - top, 4, 0.0)
        _tube(BV, BF, BU, lp, [r0 * 0.4 * (1 - 0.85 * j / 4) for j in range(5)], 6)
        for j in (2, 3, 4):
            tips.append((lp[j - 1], lp[j]))
    # leaf clusters along every twig
    card = sp["card"]; per = int(round(9 * detail)) if detail > 0.5 else 7
    for (a, b) in tips:
        for s in (0.45, 0.8, 1.0):
            leaves_at(a.lerp(b, s), per, 0.03 if detail > 0.5 else 0.05, card * (1.0 if detail > 0.5 else 2.6))
    return (BV, BF, BU), (LV, LF, LU)


def _mesh(name, data, mat):
    V, Fc, UV = data
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in V], [], Fc)
    uvl = me.uv_layers.new(name="UV")
    loops_uv = [UV[i] for f in Fc for i in f]
    uvl.data.foreach_set("uv", [c for uv in loops_uv for c in uv])
    for p_ in me.polygons:
        p_.use_smooth = True
    me.materials.append(mat)
    return me


def _leaf_mat(name, sp):
    m, n, l, b = node_mat(name)
    aid = _AC.get(sp["leaf"])
    uv = n.new("ShaderNodeUVMap"); uv.uv_map = "UV"
    ci = n.new("ShaderNodeTexImage"); ci.image = bpy.data.images.load(_acg(aid, "Color"), check_existing=True); l.new(uv.outputs[0], ci.inputs[0])
    oi = n.new("ShaderNodeTexImage"); oi.image = bpy.data.images.load(_acg(aid, "Opacity"), check_existing=True)
    oi.image.colorspace_settings.name = 'Non-Color'; l.new(uv.outputs[0], oi.inputs[0])
    info = n.new("ShaderNodeObjectInfo")
    hs = n.new("ShaderNodeHueSaturation"); l.new(ci.outputs["Color"], hs.inputs["Color"])
    hs.inputs["Saturation"].default_value = 0.95
    mr = n.new("ShaderNodeMapRange"); mr.inputs["To Min"].default_value = 0.47; mr.inputs["To Max"].default_value = 0.53
    l.new(info.outputs["Random"], mr.inputs["Value"]); l.new(mr.outputs["Result"], hs.inputs["Hue"])
    mv = n.new("ShaderNodeMapRange"); mv.inputs["To Min"].default_value = 0.75; mv.inputs["To Max"].default_value = 1.05
    l.new(info.outputs["Random"], mv.inputs["Value"]); l.new(mv.outputs["Result"], hs.inputs["Value"])
    tint = n.new("ShaderNodeMix"); tint.data_type = 'RGBA'; tint.blend_type = 'MULTIPLY'; tint.inputs[0].default_value = 0.35
    l.new(hs.outputs[0], tint.inputs[6]); tint.inputs[7].default_value = hexcol(sp["tint"])
    l.new(tint.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.55
    nf = _acg(aid, "NormalGL")
    if nf:
        ni = n.new("ShaderNodeTexImage"); ni.image = bpy.data.images.load(nf, check_existing=True); ni.image.colorspace_settings.name = 'Non-Color'
        l.new(uv.outputs[0], ni.inputs[0]); nm_ = n.new("ShaderNodeNormalMap"); nm_.inputs["Strength"].default_value = 0.6
        l.new(ni.outputs["Color"], nm_.inputs["Color"]); l.new(nm_.outputs[0], b.inputs["Normal"])
    tr = n.new("ShaderNodeBsdfTranslucent"); l.new(tint.outputs[2], tr.inputs["Color"])
    mx = n.new("ShaderNodeMixShader"); mx.inputs[0].default_value = 0.3
    l.new(b.outputs[0], mx.inputs[1]); l.new(tr.outputs[0], mx.inputs[2])
    tp = n.new("ShaderNodeBsdfTransparent")
    cut = n.new("ShaderNodeMath"); cut.operation = 'GREATER_THAN'; cut.inputs[1].default_value = 0.5
    l.new(oi.outputs["Color"], cut.inputs[0])
    m2 = n.new("ShaderNodeMixShader"); l.new(cut.outputs[0], m2.inputs[0]); l.new(tp.outputs[0], m2.inputs[1]); l.new(mx.outputs[0], m2.inputs[2])
    out = n["Material Output"]; l.new(m2.outputs[0], out.inputs["Surface"])
    MATS[name] = m
    return m


def _bark_mat(name, aid):
    m, n, l, b = node_mat(name)
    uv = n.new("ShaderNodeUVMap"); uv.uv_map = "UV"
    mp = n.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (2.0, 6.0, 1.0)
    l.new(uv.outputs[0], mp.inputs[0])
    if _acg(aid, "Color"):
        ci = n.new("ShaderNodeTexImage"); ci.image = bpy.data.images.load(_acg(aid, "Color"), check_existing=True)
        l.new(mp.outputs[0], ci.inputs[0]); l.new(ci.outputs["Color"], b.inputs["Base Color"])
        ni = n.new("ShaderNodeTexImage"); ni.image = bpy.data.images.load(_acg(aid, "NormalGL"), check_existing=True)
        ni.image.colorspace_settings.name = 'Non-Color'; l.new(mp.outputs[0], ni.inputs[0])
        nm_ = n.new("ShaderNodeNormalMap"); nm_.inputs["Strength"].default_value = 1.2
        l.new(ni.outputs["Color"], nm_.inputs["Color"]); l.new(nm_.outputs[0], b.inputs["Normal"])
    else:
        b.inputs["Base Color"].default_value = hexcol("#4A3B2E")
    b.inputs["Roughness"].default_value = 0.9
    MATS[name] = m
    return m


scene.cycles.transparent_max_bounces = 32       # stacked leaf cards
_lib_t = bpy.data.collections.new("Tree Library"); scene.collection.children.link(_lib_t)
bpy.context.view_layer.layer_collection.children[_lib_t.name].exclude = True
VARIANTS = {}       # (species, lod) -> [collections]
for spn, sp in SPECIES.items():
    lm = _leaf_mat(f"Leaves {spn}", sp)
    bm_ = _bark_mat(f"Bark {spn}", _AC.get(sp["bark"]))
    for lod, det, nvar in (("near", 1.0, 2), ("far", 0.35, 1)):
        for vi in range(nvar):
            bark, leaf = gen_tree(sp, hash((spn, vi, lod)) & 0xffff, det)
            cc = bpy.data.collections.new(f"tree {spn} {lod} {vi}"); _lib_t.children.link(cc)
            for nm_, data, mt in (("bark", bark, bm_), ("leaves", leaf, lm)):
                ob = bpy.data.objects.new(f"{spn} {lod} {vi} {nm_}", _mesh(f"{spn} {lod} {vi} {nm_}", data, mt)); cc.objects.link(ob)
            VARIANTS.setdefault((spn, lod), []).append(cc)
print("tree variants:", {f"{k[0]}/{k[1]}": len(v) for k, v in VARIANTS.items()},
      "near tris ~", sum(len(o.data.polygons) for c in VARIANTS[("oak", "near")] for o in c.objects) // 2 * 2)

_wts = TER.get("tree_species", {"oak": .35, "maple": .3, "ash": .15, "hickory": .2})
_names = list(_wts); _cum = []
_acc = 0
for k_ in _names:
    _acc += _wts[k_]; _cum.append(_acc)


def _pick(rr):
    v = rr.random() * _acc
    for k_, c_ in zip(_names, _cum):
        if v <= c_:
            return k_
    return _names[-1]


def _place(name, coll, x, y, h, crown_r, sp, rr):
    e = bpy.data.objects.new(name, None); e.instance_type = 'COLLECTION'; e.instance_collection = coll
    c_sur.objects.link(e)
    s = h * F
    sxy = max(0.75, min(1.35, crown_r / max(SPECIES[sp]["ratio"] * h, 1)))
    e.location = P(x, y, ground_z(x, y) - 0.2); e.scale = (s * sxy, s * sxy, s)
    e.rotation_euler = (0, 0, rr.uniform(0, 6.283))
    return e


_rr = random.Random(23)
n_near = n_far = n_under = 0
_near = json.load(open(os.path.join(_tdir, "trees.json"))) if os.path.exists(os.path.join(_tdir, "trees.json")) else []
for k, (x, y, h, r) in enumerate(_near):
    if _rr.random() > dens or h < TER.get("min_tree_height_ft", 12.0):
        continue
    h = min(h, TER.get("max_tree_height_ft", 95.0))
    if -r - 3 < x < HW + r + 3 and -r - 3 < y < HD + r + 3:
        continue
    sp = _pick(_rr)
    _place(f"Tree {k} {sp}", _rr.choice(VARIANTS[(sp, "near")]), x, y, h, r, sp, _rr); n_near += 1
    if h > 40:      # understory saplings under the canopy
        ux, uy = x + _rr.uniform(-.35, .35) * h * 0.3, y + _rr.uniform(-.35, .35) * h * 0.3
        sp2 = _pick(_rr)
        _place(f"Sapling {k}", _rr.choice(VARIANTS[(sp2, "far")]), ux, uy, _rr.uniform(12, 22), 5, sp2, _rr); n_under += 1
_farp = os.path.join(_tdir, "far_trees.json")
if os.path.exists(_farp):
    for k, (x, y, h, r) in enumerate(json.load(open(_farp))):
        if _rr.random() > dens:
            continue
        sp = _pick(_rr)
        _place(f"Far tree {k}", VARIANTS[(sp, "far")][0], x, y, h, r, sp, _rr); n_far += 1
keep = n_near + n_far
print(f"trees: {n_near} near (detailed), {n_under} understory, {n_far} far ring (low poly)")
