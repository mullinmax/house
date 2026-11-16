"""Realism pass for build_house.py: run inside it (exec) so it shares its helpers and scene.

Config driven:
  [assets]       CC0 downloads (fetch_assets.py): PBR sets, HDRI sky, Poly Haven furniture models
  [furnishings]  every furniture piece, bath fixture, window treatment and exterior fixture (positions ASSUMED)
Also adds trim that is not in the plans as geometry yet: baseboards, interior doors with casings and levers,
fascia and soffit, gutters and downspouts, door thresholds.
"""
import glob, random

AS = C.get("assets", {})
ADIR = os.path.join(SRC, AS.get("dir", "assets"))
FU = C.get("furnishings", {})
c_furn = col("Furniture and Fixtures", c_house)
c_trim = col("Interior Trim and Doors", c_house)
c_xdet = col("Exterior Details", c_house)
RND = random.Random(11)


def _rad(d):
    return math.radians(d)


# ================================================================== PBR materials (ambientCG, box projected)
def acg_file(aid, kind):
    f = glob.glob(os.path.join(ADIR, "ambientcg", aid, f"*_{kind}.jpg"))
    return f[0] if f else None


def img_node(n, path, noncolor=False):
    t = n.new("ShaderNodeTexImage")
    t.image = bpy.data.images.load(path, check_existing=True)
    if noncolor:
        t.image.colorspace_settings.name = 'Non-Color'
    t.projection = 'BOX'; t.projection_blend = 0.25
    return t


def pbr(mat_name, aid, scale_m=1.0, tint=None, tint_amount=1.0, keep_color=False, hsv=None,
        rough=None, rough_scale=1.0, normal=1.0, vertical_grain=False):
    """Upgrade (or create) a material with an ambientCG set. tint: hex color multiplied over the map's
    detail (keeps grain/variation, takes the config color). keep_color uses the map color (optionally hsv=(h,s,v))."""
    if not AS.get("enabled") or not aid or not acg_file(aid, "Color"):
        return MATS.get(mat_name)
    m = MATS.get(mat_name)
    if m is None:
        m, n, l, b = node_mat(mat_name); MATS[mat_name] = m
    n, l = m.node_tree.nodes, m.node_tree.links
    b = n["Principled BSDF"]
    for inp in ("Base Color", "Roughness", "Normal"):
        for lk in list(b.inputs[inp].links):
            l.remove(lk)
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1 / scale_m,) * 3
    if vertical_grain:   # box projection: feed (z, z, x+y) so the map's x axis runs up every vertical face
        sx = n.new("ShaderNodeSeparateXYZ"); l.new(tc.outputs["Object"], sx.inputs[0])
        ad = n.new("ShaderNodeMath"); ad.operation = 'ADD'; l.new(sx.outputs[0], ad.inputs[0]); l.new(sx.outputs[1], ad.inputs[1])
        cb = n.new("ShaderNodeCombineXYZ"); l.new(sx.outputs[2], cb.inputs[0]); l.new(sx.outputs[2], cb.inputs[1]); l.new(ad.outputs[0], cb.inputs[2])
        l.new(cb.outputs[0], mp.inputs[0])
    else:
        l.new(tc.outputs["Object"], mp.inputs[0])
    col_t = img_node(n, acg_file(aid, "Color")); l.new(mp.outputs[0], col_t.inputs[0])
    if tint:
        # detail = map luminance / its mean; color = tint * mix(1, detail, tint_amount)
        bw = n.new("ShaderNodeRGBToBW"); l.new(col_t.outputs["Color"], bw.inputs[0])
        px = col_t.image.pixels[:]  # 1K map: fast enough
        lum = sum(0.2126 * px[i] + 0.7152 * px[i + 1] + 0.0722 * px[i + 2] for i in range(0, len(px), 4 * 97)) / (len(px) / (4 * 97))
        dv = n.new("ShaderNodeMath"); dv.operation = 'DIVIDE'; dv.inputs[1].default_value = max(lum, 0.02)
        l.new(bw.outputs[0], dv.inputs[0])
        mx = n.new("ShaderNodeMix"); mx.data_type = 'FLOAT'; mx.inputs["Factor"].default_value = tint_amount
        mx.inputs["A"].default_value = 1.0; l.new(dv.outputs[0], mx.inputs["B"])
        mul = n.new("ShaderNodeMix"); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs[0].default_value = 1.0
        mul.inputs[6].default_value = hexcol(tint)
        cv = n.new("ShaderNodeCombineColor"); l.new(mx.outputs[0], cv.inputs[0]); l.new(mx.outputs[0], cv.inputs[1]); l.new(mx.outputs[0], cv.inputs[2])
        l.new(cv.outputs[0], mul.inputs[7])
        l.new(mul.outputs[2], b.inputs["Base Color"])
    else:
        out = col_t.outputs["Color"]
        if hsv:
            hs = n.new("ShaderNodeHueSaturation"); hs.inputs["Hue"].default_value, hs.inputs["Saturation"].default_value, hs.inputs["Value"].default_value = hsv
            l.new(out, hs.inputs["Color"]); out = hs.outputs[0]
        l.new(out, b.inputs["Base Color"])
    rf = acg_file(aid, "Roughness")
    if rough is not None and rf:
        rt = img_node(n, rf, True); l.new(mp.outputs[0], rt.inputs[0])
        mr = n.new("ShaderNodeMapRange"); mr.inputs["To Min"].default_value = rough[0]; mr.inputs["To Max"].default_value = rough[1]
        l.new(rt.outputs["Color"], mr.inputs["Value"]); l.new(mr.outputs["Result"], b.inputs["Roughness"])
    elif rough is not None:
        b.inputs["Roughness"].default_value = (rough[0] + rough[1]) / 2
    nf = acg_file(aid, "NormalGL")
    if nf and normal > 0:
        nt = img_node(n, nf, True); l.new(mp.outputs[0], nt.inputs[0])
        nm = n.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = normal
        l.new(nt.outputs["Color"], nm.inputs["Color"]); l.new(nm.outputs[0], b.inputs["Normal"])
    return m


AC = AS.get("ambientcg", {})
PHT = AS.get("polyhaven_textures", {})
try:
    PH_SIZES = json.load(open(os.path.join(ADIR, "polyhaven_tex", "sizes.json")))
except Exception:
    PH_SIZES = {}


def wood_uv(mat_name, tid, tint=None, tint_amount=1.0, hsv=None, rough=(0.35, 0.55), normal=0.4, color=True, solid=None):
    """real-scale wood from a Poly Haven scan on UVs (made by wood_unwrap below: V runs along the grain)."""
    d = os.path.join(ADIR, "polyhaven_tex", tid or "-")
    cf = os.path.join(d, f"{tid}_Color.jpg")
    if not (AS.get("enabled") and os.path.exists(cf)):
        return False
    tile = PH_SIZES.get(tid, [1.0, 1.0])[0]
    m = MATS[mat_name]; n, l = m.node_tree.nodes, m.node_tree.links
    b = n["Principled BSDF"]
    for inp in ("Base Color", "Roughness", "Normal"):
        for lk in list(b.inputs[inp].links):
            l.remove(lk)
    uv = n.new("ShaderNodeUVMap"); uv.uv_map = "WoodUV"
    mp = n.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1 / tile, 1 / tile, 1)
    l.new(uv.outputs[0], mp.inputs[0])
    ct = n.new("ShaderNodeTexImage"); ct.image = bpy.data.images.load(cf, check_existing=True); l.new(mp.outputs[0], ct.inputs[0])
    out = ct.outputs["Color"]
    if hsv:
        hs = n.new("ShaderNodeHueSaturation"); hs.inputs["Hue"].default_value, hs.inputs["Saturation"].default_value, hs.inputs["Value"].default_value = hsv
        l.new(out, hs.inputs["Color"]); out = hs.outputs[0]
    if tint:
        mx = n.new("ShaderNodeMix"); mx.data_type = 'RGBA'; mx.blend_type = 'COLOR' if color else 'MULTIPLY'
        mx.inputs[0].default_value = tint_amount; l.new(out, mx.inputs[6]); mx.inputs[7].default_value = hexcol(tint)
        out = mx.outputs[2]
    if solid:
        b.inputs["Base Color"].default_value = hexcol(solid)     # painted: keep the paint color, grain only in relief
    else:
        l.new(out, b.inputs["Base Color"])
    rf = os.path.join(d, f"{tid}_Roughness.jpg")
    if os.path.exists(rf):
        rt = n.new("ShaderNodeTexImage"); rt.image = bpy.data.images.load(rf, check_existing=True); rt.image.colorspace_settings.name = 'Non-Color'
        l.new(mp.outputs[0], rt.inputs[0])
        mr = n.new("ShaderNodeMapRange"); mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = rough
        l.new(rt.outputs["Color"], mr.inputs["Value"]); l.new(mr.outputs["Result"], b.inputs["Roughness"])
    nf = os.path.join(d, f"{tid}_NormalGL.jpg")
    if os.path.exists(nf) and normal:
        nt = n.new("ShaderNodeTexImage"); nt.image = bpy.data.images.load(nf, check_existing=True); nt.image.colorspace_settings.name = 'Non-Color'
        l.new(mp.outputs[0], nt.inputs[0]); nm = n.new("ShaderNodeNormalMap"); nm.uv_map = "WoodUV"; nm.inputs["Strength"].default_value = normal
        l.new(nt.outputs["Color"], nm.inputs["Color"]); l.new(nm.outputs[0], b.inputs["Normal"])
    return True


def wood_unwrap(objs, vertical=False):
    """per-face planar UVs in metres, V along the piece's long axis (or world Z for siding) so grain follows the board."""
    import numpy as np
    n_ = 0
    for ob in objs:
        me = ob.data
        if not me.polygons:
            continue
        co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
        dims = co.max(0) - co.min(0)
        long_ax = 2 if vertical else int(np.argmax(dims))
        uvl = me.uv_layers.get("WoodUV") or me.uv_layers.new(name="WoodUV")
        data = []
        for p in me.polygons:
            nrm = np.abs(np.array(p.normal))
            ax = int(np.argmax(nrm))                 # face plane is perpendicular to this axis
            inplane = [a for a in range(3) if a != ax]
            if long_ax in inplane:
                va = long_ax; ua = [a for a in inplane if a != long_ax][0]
            else:
                va, ua = inplane[1], inplane[0]
            for li in p.loop_indices:
                v = co[me.loops[li].vertex_index]
                data += [v[ua], v[va]]
        uvl.data.foreach_set("uv", data)
        n_ += 1
    return n_
MM = C["materials"]; KK = C["kitchen"]
if AS.get("enabled"):
    pbr("Siding", AC.get("siding"), 0.9, tint=MM["siding_color"], tint_amount=0.35, rough=(0.62, 0.85), normal=0.5, vertical_grain=True)
    pbr("White Oak", AC.get("oak"), 0.8, keep_color=True, hsv=(0.535, 0.5, 1.4), rough=(0.38, 0.55), normal=0.3, vertical_grain=True)
    pbr("Cabinet Wood", AC.get("oak"), 0.8, tint=KK["cabinet_wood"], tint_amount=0.6, rough=(0.4, 0.55), normal=0.25, vertical_grain=True)
    pbr("Counter", AC.get("quartz"), 1.6, keep_color=True, hsv=(0.5, 0.25, 1.45), rough=(0.12, 0.22), normal=0.05)
    pbr("Standing Seam", None)
    pbr("Gravel", AC.get("gravel"), 1.2, keep_color=True, rough=(0.8, 0.98), normal=1.0)
    pbr("Asphalt", AC.get("asphalt"), 2.0, keep_color=True, hsv=(0.5, 0.8, 0.75), rough=(0.75, 0.95), normal=0.6)
    pbr("Drywall", AC.get("plaster"), 1.5, tint=MM["wall_paint"], tint_amount=0.12, rough=(0.78, 0.9), normal=0.12)
    pbr("Concrete", AC.get("floor"), 2.0, tint="#A7A49E", tint_amount=0.5, rough=(0.7, 0.9), normal=0.5)
    pbr("Tile Wall", AC.get("tile_wall"), 0.9, keep_color=True, hsv=(0.5, 0.5, 1.0), rough=(0.08, 0.25), normal=0.6)
    pbr("Tile Floor", AC.get("tile_floor"), 0.45, keep_color=True, hsv=(0.5, 0.3, 0.92), rough=(0.2, 0.45), normal=0.8)
    pbr("Curtain Linen", AC.get("curtain"), 0.25, tint="#E8E2D6", tint_amount=0.5, rough=(0.8, 0.95), normal=0.4)
    pbr("Bedding", AC.get("bedding"), 0.3, tint="#F1EEE8", tint_amount=0.3, rough=(0.8, 0.95), normal=0.35)
    pbr("Rug", AC.get("rug"), 0.6, tint="#B9AE9A", tint_amount=0.6, rough=(0.85, 1.0), normal=0.8)
    # metal roof: keep the charcoal paint and seam bump, add PaintedMetal roughness breakup
    m = MATS["Standing Seam"]; n, l = m.node_tree.nodes, m.node_tree.links
    rf = acg_file(AC.get("roof", ""), "Roughness") if AC.get("roof") else None
    if rf:
        b = n["Principled BSDF"]; tc = n.new("ShaderNodeTexCoord"); mp = n.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (0.5, 0.5, 0.5)
        l.new(tc.outputs["Object"], mp.inputs[0]); rt = img_node(n, rf, True); l.new(mp.outputs[0], rt.inputs[0])
        mr = n.new("ShaderNodeMapRange"); mr.inputs["To Min"].default_value = 0.32; mr.inputs["To Max"].default_value = 0.5
        l.new(rt.outputs["Color"], mr.inputs["Value"]); l.new(mr.outputs["Result"], b.inputs["Roughness"])
    # stained concrete floor: concrete roughness/normal breakup under the stain + cuts
    m = MATS["Stained Concrete"]; n, l = m.node_tree.nodes, m.node_tree.links
    rf, nf = acg_file(AC.get("floor", ""), "Roughness"), acg_file(AC.get("floor", ""), "NormalGL")
    if rf and nf:
        b = n["Principled BSDF"]
        tc = n.new("ShaderNodeTexCoord"); mp = n.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (0.4, 0.4, 0.4)
        l.new(tc.outputs["Object"], mp.inputs[0])
        rt = img_node(n, rf, True); l.new(mp.outputs[0], rt.inputs[0])
        old = b.inputs["Roughness"].links[0].from_socket if b.inputs["Roughness"].links else None
        mr = n.new("ShaderNodeMapRange"); mr.inputs["To Min"].default_value = MM["floor_gloss"] - 0.12; mr.inputs["To Max"].default_value = MM["floor_gloss"] + 0.15
        l.new(rt.outputs["Color"], mr.inputs["Value"]); l.new(mr.outputs["Result"], b.inputs["Roughness"])
        nt = img_node(n, nf, True); l.new(mp.outputs[0], nt.inputs[0])
        nmp = n.new("ShaderNodeNormalMap"); nmp.inputs["Strength"].default_value = 0.25; l.new(nt.outputs["Color"], nmp.inputs["Color"])
        bump = [x for x in n if x.bl_idname == "ShaderNodeBump"]
        if bump:
            l.new(nmp.outputs[0], bump[0].inputs["Normal"])
        else:
            l.new(nmp.outputs[0], b.inputs["Normal"])
else:
    for nm_, c_ in (("Tile Wall", "#F2F2F0"), ("Tile Floor", "#D9D6D0"), ("Curtain Linen", "#E8E2D6"), ("Bedding", "#F1EEE8"), ("Rug", "#B9AE9A")):
        simple(nm_, c_, 0.6)
simple("Mirror", "#E8ECEE", 0.02, 1.0)
simple("Enamel White", "#F3F3F1", 0.25)
simple("Upholstery", "#8C8B84", 0.85)
simple("Aluminum", "#B9BCBE", 0.35, 1.0)
simple("Gutter", C["materials"]["trim_color"], 0.45, 0.4)
simple("Plastic Grey", "#9A9A96", 0.5)
simple("Lamp Shade", "#F2EBDD", 0.8)
MATS["Lamp Shade"].node_tree.nodes["Principled BSDF"].inputs["Transmission Weight"].default_value = 0.35
simple("Bulb Glow", "#FFE2B8", 0.5)
_bg = MATS["Bulb Glow"].node_tree.nodes["Principled BSDF"]
_bg.inputs["Emission Color"].default_value = hexcol("#FFD9A8"); _bg.inputs["Emission Strength"].default_value = 6.0
for nm_, hx in (("Accent 1", "#56614A"),):
    simple(nm_, hx, 0.85)


def fabric(name, hexc):
    """bedding/curtain fabric in a given color (shares the PBR detail when available)."""
    key = "Fabric " + hexc
    if key in MATS:
        return key
    base = MATS.get("Bedding")
    if base is not None:
        m = base.copy(); m.name = key
        for nd in m.node_tree.nodes:
            if nd.bl_idname == "ShaderNodeMix" and nd.data_type == 'RGBA' and nd.blend_type == 'MULTIPLY':
                nd.inputs[6].default_value = hexcol(hexc)
        MATS[key] = m
    else:
        simple(key, hexc, 0.85)
    return key


# ================================================================== HDRI sky (Poly Haven)
if AS.get("enabled") and AS.get("hdri"):
    hp = glob.glob(os.path.join(ADIR, "polyhaven", "hdri", AS["hdri"] + "*.hdr"))
    if hp:
        wn, wl = world.node_tree.nodes, world.node_tree.links
        bgn = wn["Background"]
        env = wn.new("ShaderNodeTexEnvironment"); env.image = bpy.data.images.load(hp[0])
        # find the HDRI's sun (brightest pixel) and rotate it to the configured azimuth
        import numpy as np
        w_, h_ = env.image.size
        px = np.empty(w_ * h_ * 4, np.float32); env.image.pixels.foreach_get(px)
        lum = px.reshape(-1, 4)[:, :3].sum(1)
        k = int(lum.argmax()); col_, row_ = k % w_, k // w_
        u = (col_ + 0.5) / w_
        sun_el = (row_ + 0.5) / h_ * 180 - 90                    # pixels() start at the bottom row
        # Cycles equirect: u = 0.5 - atan2(d.y, d.x) / (2 pi)  ->  atan2(d.y, d.x) = (0.5 - u) 2 pi
        a = (0.5 - u) * 2 * math.pi
        cur = (math.cos(a), math.sin(a))                        # (dx, dy) of the sun direction in Blender
        az = math.radians(RC["sun_azimuth_deg"])
        want = (math.sin(az), math.cos(az))                     # compass azimuth -> Blender (east = +X, north = +Y)
        rot = math.atan2(want[1], want[0]) - math.atan2(cur[1], cur[0]) + math.radians(AS.get("hdri_rotation_deg", 0.0))
        tc = wn.new("ShaderNodeTexCoord"); mp = wn.new("ShaderNodeMapping")
        mp.inputs["Rotation"].default_value = (0, 0, -rot)
        wl.new(tc.outputs["Generated"], mp.inputs[0]); wl.new(mp.outputs[0], env.inputs[0])
        for lk in list(bgn.inputs[0].links):
            wl.remove(lk)
        wl.new(env.outputs["Color"], bgn.inputs[0]); bgn.inputs[1].default_value = AS.get("hdri_strength", 0.9)
        # the HDRI carries the sun: turn the sun lamp into a gentle fill that matches it, so shadows stay crisp
        el = max(5.0, sun_el)
        dsun = Vector((math.sin(az) * math.cos(math.radians(el)), math.cos(az) * math.cos(math.radians(el)), math.sin(math.radians(el))))
        sun.rotation_euler = (-dsun).to_track_quat('-Z', 'Y').to_euler()
        sun.data.energy = AS.get("sun_lamp_energy", 2.2); sun.data.angle = math.radians(0.8)
        print(f"HDRI {os.path.basename(hp[0])}: sun at {sun_el:.1f} deg elevation, rotated {math.degrees(rot):.1f} deg to azimuth {RC['sun_azimuth_deg']}")


# ================================================================== Poly Haven models (glTF -> collection instances)
_lib = None
_LIBC = {}


def model_collection(mid):
    """import a Poly Haven glTF once; returns (collection, size_xyz_ft) with the instance origin at bottom center."""
    global _lib
    if mid in _LIBC:
        return _LIBC[mid]
    files = glob.glob(os.path.join(ADIR, "polyhaven", mid, "*.gltf"))
    if not files:
        print("  missing model", mid); _LIBC[mid] = None; return None
    if _lib is None:
        _lib = bpy.data.collections.new("Asset Library"); scene.collection.children.link(_lib)
        bpy.context.view_layer.layer_collection.children[_lib.name].exclude = True   # sources only; the instances render
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=files[0])
    new = [o for o in bpy.data.objects if o not in before]
    cc = bpy.data.collections.new("asset " + mid); _lib.children.link(cc)
    for o in new:
        for c_ in list(o.users_collection):
            c_.objects.unlink(o)
        cc.objects.link(o)
    # picture frames: swap the placeholder artwork card for one of the generated prints
    if "picture_frame" in mid:
        k_ = 1 + sum(1 for m_ in _LIBC if "picture_frame" in m_) % 3
        artf = os.path.join(ADIR, "art", f"art_{k_}.jpg")
        for o in new:
            for s_ in getattr(o, "material_slots", []):
                if s_.material and s_.material.name.endswith("glass"):      # imported glass renders opaque black
                    bs = [nd for nd in s_.material.node_tree.nodes if nd.bl_idname == "ShaderNodeBsdfPrincipled"]
                    for bsd in bs:
                        for lk in list(bsd.inputs["Alpha"].links):
                            s_.material.node_tree.links.remove(lk)
                        bsd.inputs["Alpha"].default_value = 0.06; bsd.inputs["Roughness"].default_value = 0.03
                        bsd.inputs["Base Color"].default_value = (1, 1, 1, 1)
                if s_.material and s_.material.name.endswith("artwork") and os.path.exists(artf):
                    for nd in s_.material.node_tree.nodes:
                        if nd.bl_idname == "ShaderNodeTexImage" and nd.image and "diff" in nd.image.name:
                            nd.image = bpy.data.images.load(artf, check_existing=True)
    pts = [o.matrix_world @ Vector(c_) for o in new if o.type == 'MESH' for c_ in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    cc.instance_offset = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z)
    size = ((hi.x - lo.x) / F, (hi.y - lo.y) / F, (hi.z - lo.z) / F)
    _LIBC[mid] = (cc, size)
    return _LIBC[mid]


TOPS = {}          # id -> top height (ft) of placed pieces, for "on = ..."


def place_model(it):
    r = model_collection(it["model"])
    if r is None:
        return None
    cc, (sx, sy, sz) = r
    s = it["len"] / max(sx, sy) if it.get("len") else it.get("scale", 1.0)
    z = it.get("z", TOPS.get(it.get("on"), 0.0))
    e = bpy.data.objects.new(it["id"], None)
    e.instance_type = 'COLLECTION'; e.instance_collection = cc
    c_furn.objects.link(e)
    yy = it["y"]
    if it.get("wall"):   # wall hung: back against the wall plane at (x, y)
        f_ = math.radians(it.get("facing", 180)); d = sy * s / 2 + 0.05   # 5/8" off the wall: no coplanar back plate
        x_ = it["x"] + math.sin(f_) * d; yy = it["y"] - math.cos(f_) * d
        e.location = P(x_, yy, z)
    else:
        e.location = P(it["x"], yy, z)
    e.rotation_euler = (0, 0, _rad(180 - it.get("facing", 180) + AS.get("model_turn", {}).get(it["model"], 0)))
    e.scale = (s, s, s)
    TOPS[it["id"]] = z + sz * s
    return e


# ================================================================== procedural pieces (built at the origin, front = plan +y)
def group(name, parts, x, y, z=0.0, facing=180):
    e = bpy.data.objects.new(name, None); c_furn.objects.link(e)
    for p_ in parts:
        if p_ is None:
            continue
        for c_ in list(p_.users_collection):
            c_.objects.unlink(p_)
        c_furn.objects.link(p_)
        p_.parent = e
    e.location = P(x, y, z); e.rotation_euler = (0, 0, _rad(180 - facing))
    return e


def bevel(ob, w=0.03, seg=3):
    md = ob.modifiers.new("bevel", 'BEVEL'); md.width = w * F; md.segments = seg; md.limit_method = 'ANGLE'
    return ob


def cyl(name, r1, r2, h, mat, z0=0.0, seg=24, sx=1.0, sy=1.0, cx=0.0, cy=0.0, collection=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r1 * F, radius2=r2 * F, depth=h * F)
    for v in bm.verts:
        v.co.x = v.co.x * sx + cx * F; v.co.y = v.co.y * sy - cy * F; v.co.z += (z0 + h / 2) * F
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p_ in me.polygons:
        p_.use_smooth = True
    ob = bpy.data.objects.new(name, me); (collection or c_furn).objects.link(ob); me.materials.append(MATS[mat])
    return ob


def lamp_light(name, x, y, z, w, color=(1.0, 0.83, 0.62), radius=0.15):
    ld = bpy.data.lights.new(name, 'POINT'); ld.energy = w; ld.shadow_soft_size = radius * F; ld.color = color
    lo = bpy.data.objects.new(name, ld); lo.location = P(x, y, z); c_furn.objects.link(lo)
    return lo


def make_bed(it):
    w, l = it.get("w", 5.3), it.get("l", 7.0)
    bed_col = fabric(it["id"], it.get("color", "#F1EEE8")); acc = fabric(it["id"] + " accent", it.get("accent", "#56614A"))
    p = []
    p.append(bevel(box("frame", -w / 2 - 0.1, w / 2 + 0.1, -l / 2, l / 2, 0.45, 1.0, "White Oak", c_furn), 0.02))
    for (lx, ly) in ((-w / 2, -l / 2 + 0.1), (w / 2 - 0.15, -l / 2 + 0.1), (-w / 2, l / 2 - 0.25), (w / 2 - 0.15, l / 2 - 0.25)):
        p.append(box("leg", lx, lx + 0.15, ly, ly + 0.15, 0, 0.45, "White Oak", c_furn))
    p.append(bevel(box("mattress", -w / 2, w / 2, -l / 2 + 0.15, l / 2 - 0.05, 1.0, 1.85, "Bedding", c_furn), 0.12, 4))
    p.append(bevel(box("duvet", -w / 2 - 0.12, w / 2 + 0.12, -l / 2 + 1.55, l / 2 + 0.06, 1.25, 1.98, bed_col, c_furn), 0.1, 4))
    p.append(bevel(box("duvet fold", -w / 2 - 0.13, w / 2 + 0.13, -l / 2 + 1.55, -l / 2 + 2.05, 1.3, 2.04, bed_col, c_furn), 0.1, 4))
    p.append(bevel(box("throw", -w / 2 - 0.14, w / 2 + 0.14, l / 2 - 1.5, l / 2 - 0.4, 1.35, 2.03, acc, c_furn), 0.06, 3))
    for k in range(2):
        x0 = -w / 2 + 0.2 + k * (w / 2 - 0.1)
        p.append(bevel(box("pillow", x0, x0 + w / 2 - 0.3, -l / 2 + 0.25, -l / 2 + 1.35, 1.85, 2.35, "Bedding", c_furn), 0.18, 5))
    p.append(bevel(box("headboard", -w / 2 - 0.15, w / 2 + 0.15, -l / 2 - 0.18, -l / 2, 0.45, 4.2, "Upholstery", c_furn), 0.06, 3))
    return group(it["id"], p, it["x"], it["y"], 0, it.get("facing", 180))


def make_toilet(it):
    """elongated bowl, two-piece with tank. Local: back (tank) at -y."""
    p = []
    p.append(cyl("pedestal", 0.42, 0.36, 1.0, "Porcelain", 0, sy=1.35, cy=0.15))
    p.append(cyl("bowl", 0.62, 0.72, 0.42, "Porcelain", 0.95, sy=1.32, cy=0.35))
    p.append(cyl("seat", 0.72, 0.72, 0.07, "Enamel White", 1.37, sy=1.32, cy=0.35))
    p.append(cyl("lid", 0.7, 0.7, 0.05, "Enamel White", 1.44, sy=1.3, cy=0.37))
    p.append(bevel(box("tank", -0.82, 0.82, -1.15, -0.55, 1.45, 2.65, "Porcelain", c_furn), 0.06, 3))
    p.append(bevel(box("tank lid", -0.86, 0.86, -1.18, -0.52, 2.65, 2.75, "Porcelain", c_furn), 0.03, 2))
    p.append(box("flush lever", -0.78, -0.52, -0.54, -0.5, 2.38, 2.43, "Brushed Nickel", c_furn))
    p.append(cyl("supply", 0.03, 0.03, 0.9, "Brushed Nickel", 0.3, cx=-0.5, cy=-1.05))
    return group(it["id"], p, it["x"], it["y"], 0, it.get("facing", 180))


def make_vanity(it):
    """vanity cabinet against the wall at -y, quartz top, undermount basins, faucets. Local front = +y."""
    w, d, ns = it.get("w", 3.0), it.get("d", 1.75), it.get("sinks", 1)
    p = []
    p.append(box("carcass", -w / 2, w / 2, -d / 2, d / 2 - 0.06, 0.35, 2.8, "Cabinet Wood", c_furn))
    p.append(box("toe", -w / 2 + 0.05, w / 2 - 0.05, -d / 2, d / 2 - 0.3, 0, 0.35, "Cabinet Wood", c_furn))
    nd = max(2, int(round(w / 1.4)))
    for k in range(nd):
        a0 = -w / 2 + k * w / nd + 0.012; a1 = -w / 2 + (k + 1) * w / nd - 0.012
        p.append(box("front", a0, a1, d / 2 - 0.06, d / 2, 0.37, 2.0, "Cabinet Wood", c_furn))
        p.append(box("drawer", a0, a1, d / 2 - 0.06, d / 2, 2.03, 2.78, "Cabinet Wood", c_furn))
        p.append(box("pull", (a0 + a1) / 2 - 0.3, (a0 + a1) / 2 + 0.3, d / 2, d / 2 + 0.06, 2.4, 2.44, "Brushed Nickel", c_furn))
    p.append(bevel(box("top", -w / 2 - 0.03, w / 2 + 0.03, -d / 2, d / 2 + 0.06, 2.8, 2.92, "Counter", c_furn), 0.015, 2))
    p.append(box("backsplash", -w / 2 - 0.03, w / 2 + 0.03, -d / 2, -d / 2 + 0.06, 2.92, 3.3, "Counter", c_furn))
    for k in range(ns):
        sx = -w / 2 + (k + 0.5) * w / ns
        p.append(cyl("basin", 0.62, 0.55, 0.42, "Porcelain", 2.5, sy=0.72, cx=sx, cy=0.08))
        p.append(cyl("basin water dark", 0.5, 0.5, 0.01, "Appliance Interior", 2.925, sy=0.7, cx=sx, cy=0.08))
        p.append(cyl("faucet", 0.06, 0.05, 0.85, "Brushed Nickel", 2.92, cx=sx, cy=-d / 2 + 0.25))
        p.append(box("spout", sx - 0.04, sx + 0.04, -d / 2 + 0.22, -d / 2 + 0.75, 3.7, 3.77, "Brushed Nickel", c_furn))
        p.append(box("handle", sx + 0.2, sx + 0.38, -d / 2 + 0.2, -d / 2 + 0.3, 3.0, 3.25, "Brushed Nickel", c_furn))
    return group(it["id"], p, it["x"], it["y"], 0, it.get("facing", 180))


def make_mirror(it):
    w, h = it.get("w", 3.0), it.get("h", 3.0)
    p = [box("mirror glass", -w / 2 + 0.06, w / 2 - 0.06, -0.06, -0.03, 0.06, h - 0.06, "Mirror", c_furn)]
    for (a0, a1, b0, b1) in ((-w / 2, w / 2, 0, 0.06), (-w / 2, w / 2, h - 0.06, h), (-w / 2, -w / 2 + 0.06, 0, h), (w / 2 - 0.06, w / 2, 0, h)):
        p.append(box("mirror frame", a0, a1, -0.07, 0.0, b0, b1, "Black Metal", c_furn))
    f_ = math.radians(it.get("facing", 180))
    return group(it["id"], p, it["x"] + math.sin(f_) * 0.07, it["y"] - math.cos(f_) * 0.07, it.get("z", 3.9), it.get("facing", 180))


def make_towel(it):
    w = it.get("w", 2.0); colk = fabric(it["id"], it.get("color", "#E9E4DA"))
    p = [box("towel bar", -w / 2 - 0.15, w / 2 + 0.15, 0.19, 0.25, -0.03, 0.03, "Brushed Nickel", c_furn)]
    p.append(box("bar post", -w / 2 - 0.2, -w / 2 - 0.15, -0.0, 0.25, -0.05, 0.05, "Brushed Nickel", c_furn))
    p.append(box("bar post", w / 2 + 0.15, w / 2 + 0.2, -0.0, 0.25, -0.05, 0.05, "Brushed Nickel", c_furn))
    p.append(bevel(box("towel", -w / 2 + 0.15, w / 2 - 0.15, 0.15, 0.3, -2.0, 0.05, colk, c_furn), 0.04, 3))
    f_ = math.radians(it.get("facing", 180))
    return group(it["id"], p, it["x"], it["y"], it.get("z", 4.0), it.get("facing", 180))


def make_desk(it):
    w, d = it.get("w", 5.0), it.get("d", 2.3)
    p = [bevel(box("desk top", -w / 2, w / 2, -d / 2, d / 2, 2.38, 2.5, "White Oak", c_furn), 0.015, 2)]
    for sx in (-w / 2 + 0.15, w / 2 - 0.25):
        p.append(box("desk leg", sx, sx + 0.1, -d / 2 + 0.1, d / 2 - 0.1, 0, 0.08, "Black Metal", c_furn))
        p.append(box("desk leg", sx, sx + 0.1, -0.05, 0.05, 0.08, 2.38, "Black Metal", c_furn))
    TOPS[it["id"]] = 2.5
    return group(it["id"], p, it["x"], it["y"], 0, it.get("facing", 180))


def make_table_lamp(it):
    z = it.get("z", TOPS.get(it.get("on"), 2.2))
    p = [cyl("lamp base", 0.25, 0.18, 0.9, "Porcelain", 0), cyl("lamp neck", 0.03, 0.03, 0.35, "Brushed Nickel", 0.9),
         cyl("lamp shade", 0.42, 0.33, 0.62, "Lamp Shade", 1.2)]
    g_ = group(it["id"], p, it["x"], it["y"], z, 180)
    lamp_light(it["id"] + " bulb", it["x"], it["y"], z + 1.45, it.get("watts", 25))
    return g_


def make_floor_lamp(it):
    p = [cyl("floor lamp base", 0.45, 0.45, 0.06, "Black Metal", 0), cyl("floor lamp pole", 0.035, 0.035, 4.6, "Black Metal", 0.06),
         cyl("floor lamp shade", 0.75, 0.6, 0.95, "Lamp Shade", 4.6)]
    g_ = group(it["id"], p, it["x"], it["y"], 0, 180)
    lamp_light(it["id"] + " bulb", it["x"], it["y"], 5.0, it.get("watts", 45))
    return g_


def make_pendant(it):
    e = place_model(it)
    if e is None:
        return None
    top = TOPS[it["id"]]; ceil = roof_under(it["y"]) - 0.02
    if ceil > top:
        p = [cyl("pendant cord", 0.012, 0.012, ceil - top, "Black Metal", 0, seg=8), cyl("pendant canopy", 0.22, 0.22, 0.08, "Black Metal", ceil - top - 0.08)]
        group(it["id"] + " cord", p, it["x"], it["y"], top, 180)
    lamp_light(it["id"] + " bulb", it["x"], it["y"], it.get("z", 6.5) + 0.25, it.get("watts", 35))
    return e


def make_rug(it):
    w, l = it.get("w", 6.0), it.get("l", 9.0)
    k = "Rug" if it.get("color") in (None, "#B9AE9A") else fabric(it["id"], it["color"])
    ob = bevel(box(it["id"], -w / 2, w / 2, -l / 2, l / 2, 0.004, 0.045, k, c_furn), 0.02, 2)
    return group(it["id"] + " grp", [ob], it["x"], it["y"], 0, it.get("facing", 180))


def make_laundry(it, dryer=False):
    p = [bevel(box("cabinet", -1.12, 1.12, -1.15, 1.15, 0.05, 3.15, "Enamel White", c_furn), 0.03, 2),
         box("control panel", -1.1, 1.1, 0.95, 1.16, 2.6, 3.12, "Plastic Grey", c_furn),
         cyl("door ring", 0.75, 0.75, 0.1, "Aluminum", 0, seg=40), cyl("door glass", 0.58, 0.58, 0.12, "Black Glass", 0, seg=40)]
    for k_ in (2, 3):
        p[k_].rotation_euler = (math.pi / 2, 0, 0); p[k_].location = P(0, 1.18, 1.45)
    p.append(cyl("dial", 0.13, 0.13, 0.06, "Aluminum", 0, seg=20)); p[-1].rotation_euler = (math.pi / 2, 0, 0); p[-1].location = P(0.7, 1.18, 2.85)
    return group(it["id"], p, it["x"], it["y"], 0, it.get("facing", 180))


def tile_wall(name, x0, x1, y0, y1, z0, z1, mat="Tile Wall"):
    return box(name, x0, x1, y0, y1, z0, z1, mat, c_furn)


def make_tub(it):
    x0, x1, y0, y1 = it["x0"], it["x1"], it["y0"], it["y1"]
    p = []
    p.append(box("tub base", x0, x1, y0, y1, 0, 0.35, "Porcelain", c_furn))
    for (a0, a1, b0, b1) in ((x0, x1, y1 - 0.28, y1), (x0, x1, y0, y0 + 0.22), (x0, x0 + 0.25, y0, y1), (x1 - 0.25, x1, y0, y1)):
        p.append(bevel(box("tub wall", a0, a1, b0, b1, 0.35, 1.7, "Porcelain", c_furn), 0.03, 2))
    p.append(box("tub water dark", x0 + 0.25, x1 - 0.25, y0 + 0.22, y1 - 0.28, 0.35, 0.37, "Porcelain", c_furn))
    # tile surround: back (north) to just under the window sill, both ends to 7 ft
    sill = min([o["sill"] for o in C["openings"] if o["wall"] == "N" and o["start"] < x1 and o["end"] > x0] or [7.0])
    p.append(tile_wall("tub tile back", x0, x1, y0, y0 + 0.02, 1.7, min(7.0, sill - 0.1)))
    p.append(tile_wall("tub tile west", x0, x0 + 0.02, y0, y1, 1.7, 7.0))
    p.append(tile_wall("tub tile east", x1 - 0.02, x1, y0, y1, 1.7, 7.0))
    p.append(box("tub glass panel", x0 + 0.3, x0 + 2.6, y1 - 0.16, y1 - 0.12, 1.7, 7.0, "Glass", c_furn))
    p.append(cyl("shower head", 0.22, 0.25, 0.06, "Brushed Nickel", 6.6, cx=x1 - 0.35, cy=(y0 + y1) / 2))
    p.append(box("shower arm", x1 - 0.45, x1, (y0 + y1) / 2 - 0.03, (y0 + y1) / 2 + 0.03, 6.66, 6.72, "Brushed Nickel", c_furn))
    p.append(cyl("valve", 0.22, 0.22, 0.04, "Brushed Nickel", 3.6, cx=x1 - 0.04, cy=(y0 + y1) / 2))
    p.append(box("tub spout", x1 - 0.5, x1, (y0 + y1) / 2 - 0.05, (y0 + y1) / 2 + 0.05, 2.1, 2.2, "Brushed Nickel", c_furn))
    return p


def make_shower(it):
    x0, x1, y0, y1 = it["x0"], it["x1"], it["y0"], it["y1"]
    gx = it.get("glass_x", x0 - 0.12)
    if it.get("curbless"):     # flush tile floor sloping to a linear drain at the back wall, no curb
        p = [box("shower floor tile", min(gx, x0) - 0.3, x1, y0, y1, 0.003, 0.012, "Tile Floor", c_furn),
             box("shower linear drain", x1 - 0.42, x1 - 0.12, y0 + 0.15, y1 - 0.15, 0.012, 0.016, "Brushed Nickel", c_furn)]
    else:
        p = [box("shower floor tile", min(gx, x0), x1, y0, y1, 0.0, 0.06, "Tile Floor", c_furn),
             box("shower curb", gx - 0.18, gx + 0.18, y0, y1, 0, 0.35, "Counter", c_furn)]
    p += [tile_wall("shower tile north", x0, x1, y0 + 0.003, y0 + 0.023, 0.012, 7.5),
          tile_wall("shower tile east", x1 - 0.023, x1 - 0.003, y0, y1, 0.012, 7.5),
          tile_wall("shower tile south", x0, x1, y1 - 0.023, y1 - 0.003, 0.012, 7.5)]
    if not it.get("doorless"):
        p += [box("shower glass", gx - 0.02, gx + 0.02, y0 + 0.05, y1 - 0.05, 0.35, 7.2, "Glass", c_furn),
              box("shower glass hinge", gx - 0.04, gx + 0.04, y1 - 0.3, y1 - 0.2, 5.5, 5.8, "Brushed Nickel", c_furn),
              box("shower handle", gx + 0.02, gx + 0.08, y0 + 0.3, y0 + 0.36, 3.0, 4.2, "Brushed Nickel", c_furn)]
    p += [cyl("rain head", 0.4, 0.4, 0.04, "Brushed Nickel", 7.4, cx=(x0 + x1) / 2 + 0.4, cy=(y0 + y1) / 2),
         box("rain arm", (x0 + x1) / 2 + 0.4, x1, (y0 + y1) / 2 - 0.03, (y0 + y1) / 2 + 0.03, 7.44, 7.5, "Brushed Nickel", c_furn),
         cyl("valve", 0.22, 0.22, 0.04, "Brushed Nickel", 3.8, cx=x1 - 0.04, cy=(y0 + y1) / 2),
         box("shower niche", x1 - 0.06, x1 - 0.025, y0 + 1.2, y0 + 2.4, 4.4, 5.5, "Appliance Interior", c_furn)]
    return p


def make_wetroom(it):
    """open, curbless wet zone: flush tile floor, linear drain across the entry, tiled walls floor to ceiling,
    tiled bench, shower head and valve on the south wall."""
    x0, x1, y0, y1 = it["x0"], it["x1"], it["y0"], it["y1"]
    top = it.get("ceiling", 9.0); dy = it.get("drain_y", y0 + 0.35); hx = it.get("head_x", (x0 + x1) / 2)
    yw = it.get("wet_from", y0)          # tiled walls from here south; the floor is tiled over the whole room
    p = [box("wet zone floor tile", x0, x1, y0, y1, 0.003, 0.012, "Tile Floor", c_furn),
         box("wet zone linear drain", x0 + 0.15, x1 - 0.15, dy - 0.12, dy + 0.12, 0.012, 0.016, "Brushed Nickel", c_furn),
         tile_wall("wet zone tile west", x0 + 0.003, x0 + 0.023, yw, y1, 0.012, top - 0.01),
         tile_wall("wet zone tile south", x0, x1, y1 - 0.023, y1 - 0.003, 0.012, top - 0.01),
         tile_wall("wet zone tile east", x1 - 0.023, x1 - 0.003, yw, y1, 0.012, top - 0.01)]
    if it.get("entry_tile", True):       # inside faces of the entry wall either side of the open doorway
        for (a0, a1) in ((x0, 34.37), (37.04, x1)):
            if a1 - a0 > 0.1:
                p.append(tile_wall("wet zone tile entry wall", a0, a1, y0 + 0.003, y0 + 0.023, 0.012, top - 0.01))
    if it.get("bench") == "north":    # tiled bench along the room's north wall, full width
        bd, bh = it.get("bench_d", 1.25), it.get("bench_h", 1.5)
        bx0 = x0 + it.get("bench_clear_w", 0.9)      # keep the doorway (west side) clear
        p += [box("wet zone bench", bx0, x1 - 0.023, y0 + 0.023, y0 + bd, 0.012, bh, "Tile Wall", c_furn),
              box("wet zone bench top", bx0 - 0.03, x1 - 0.023, y0 + 0.023, y0 + bd + 0.03, bh, bh + 0.08, "Counter", c_furn)]
        print(f"wet room bench: x {bx0:.2f}-{x1 - 0.023:.2f}, y {y0 + 0.023:.2f}-{y0 + bd + 0.03:.2f}, top {bh + 0.08:.2f} ft")
        p.append(tile_wall("wet zone tile north", x0, x1, y0 + 0.003, y0 + 0.023, 0.012, top - 0.01))
    if it.get("bench") == "east":
        bd, bh = it.get("bench_d", 1.25), it.get("bench_h", 1.5)
        p += [box("wet zone bench", x1 - bd, x1 - 0.023, dy + 0.5, y1 - 0.023, 0.012, bh, "Tile Wall", c_furn),
              box("wet zone bench top", x1 - bd - 0.03, x1 - 0.023, dy + 0.47, y1 - 0.023, bh, bh + 0.08, "Counter", c_furn)]
    p += [box("shower arm", hx - 0.03, hx + 0.03, y1 - 0.5, y1 - 0.023, 6.95, 7.01, "Brushed Nickel", c_furn),
          cyl("shower head", 0.33, 0.33, 0.04, "Brushed Nickel", 6.9, cx=hx, cy=y1 - 0.5),
          cyl("shower valve", 0.22, 0.22, 0.04, "Brushed Nickel", 3.8, cx=hx, cy=y1 - 0.03),
          box("hand shower bar", x1 - 0.06, x1 - 0.026, y1 - 1.2, y1 - 1.15, 2.4, 5.4, "Brushed Nickel", c_furn) if it.get("bench") == "east" else box("hand shower bar", x0 + 1.4, x0 + 1.45, y0 + 0.026, y0 + 0.06, 2.4, 5.4, "Brushed Nickel", c_furn),
          box("wet zone niche", hx + 1.0, hx + 2.2, y1 - 0.06, y1 - 0.025, 4.4, 5.5, "Appliance Interior", c_furn)]
    return p


def make_bookshelf(it):
    """compact white oak bookcase with books (coloured blocks). Local back at -y."""
    w, d, h = it.get("w", 2.0), it.get("d", 1.0), it.get("h", 3.5)
    p = [box("shelf side", -w / 2, -w / 2 + 0.06, -d / 2, d / 2, 0, h, "White Oak", c_furn),
         box("shelf side", w / 2 - 0.06, w / 2, -d / 2, d / 2, 0, h, "White Oak", c_furn),
         box("shelf back", -w / 2, w / 2, -d / 2, -d / 2 + 0.03, 0, h, "White Oak", c_furn)]
    rng_ = random.Random(len(it["id"]))
    cols = ["#7A3B26", "#2F4858", "#C9B68E", "#56614A", "#1E2022", "#9A6B4A", "#E9E2D3"]
    nsh = 4
    for k in range(nsh + 1):
        z = 0.1 + k * (h - 0.16) / nsh
        p.append(box("shelf board", -w / 2 + 0.06, w / 2 - 0.06, -d / 2 + 0.03, d / 2, z, z + 0.06, "White Oak", c_furn))
        if k < nsh:
            x = -w / 2 + 0.1
            while x < w / 2 - 0.25 and rng_.random() > 0.08:
                bw = rng_.uniform(0.06, 0.14); bh = rng_.uniform(0.55, 0.8) * ((h - 0.16) / nsh - 0.08)
                c_ = cols[rng_.randrange(len(cols))]
                if "Book " + c_ not in MATS:
                    simple("Book " + c_, c_, 0.7)
                p.append(box("book", x, x + bw, -d / 2 + 0.06, d / 2 - 0.1, z + 0.06, z + 0.06 + bh, "Book " + c_, c_furn))
                x += bw + 0.005
    return group(it["id"], p, it["x"], it["y"], 0, it.get("facing", 180))


def make_bench(it):
    """built-in white oak bench with open shoe cubbies below. Local: back against the wall at -y, front +y."""
    w, d, h = it.get("w", 4.0), it.get("d", 1.25), it.get("h", 1.5)
    p = [box("bench seat", -w / 2, w / 2, -d / 2, d / 2, h - 0.12, h, "White Oak", c_furn),
         box("bench bottom", -w / 2, w / 2, -d / 2, d / 2 - 0.05, 0.0, 0.25, "White Oak", c_furn),
         box("bench shelf", -w / 2 + 0.06, w / 2 - 0.06, -d / 2, d / 2 - 0.05, 0.62, 0.7, "White Oak", c_furn),
         box("bench back", -w / 2 + 0.06, w / 2 - 0.06, -d / 2, -d / 2 + 0.04, 0.25, h - 0.12, "White Oak", c_furn)]
    n = max(2, int(round(w / 1.0)))
    for k in range(n + 1):        # cubby dividers
        x_ = -w / 2 + k * (w - 0.06) / n
        p.append(box("bench divider", x_, x_ + 0.06, -d / 2, d / 2 - 0.05, 0.25, h - 0.12, "White Oak", c_furn))
    cush = fabric(it["id"] + " cushion", it.get("cushion", "#56614A"))
    p.append(bevel(box("bench cushion", -w / 2 + 0.05, w / 2 - 0.05, -d / 2 + 0.05, d / 2 - 0.05, h, h + 0.2, cush, c_furn), 0.05, 3))
    for k in range(4):            # coat hooks on a rail above
        x_ = -w / 2 + 0.5 + k * (w - 1.0) / 3
        p.append(box("bench hook", x_ - 0.03, x_ + 0.03, -d / 2, -d / 2 + 0.25, 5.4, 5.5, "Black Metal", c_furn))
    p.append(box("bench hook rail", -w / 2 + 0.2, w / 2 - 0.2, -d / 2, -d / 2 + 0.05, 5.3, 5.8, "White Oak", c_furn))
    return group(it["id"], p, it["x"], it["y"], 0, it.get("facing", 180))


BUILDERS = {"bench": make_bench, "bookshelf": make_bookshelf, "bed": make_bed,"toilet": make_toilet, "vanity": make_vanity, "mirror": make_mirror, "towel": make_towel,
            "desk": make_desk, "table_lamp": make_table_lamp, "floor_lamp": make_floor_lamp, "pendant": make_pendant,
            "rug": make_rug, "washer": make_laundry, "dryer": lambda it: make_laundry(it, True)}

if FU.get("enabled"):
    # pieces others sit on go first
    items = [it for it in FU.get("items", []) if it.get("enabled", True)]
    items.sort(key=lambda it: 1 if it.get("on") else 0)
    n_ok = 0
    for it in items:
        try:
            t = it["type"]
            if t == "model":
                place_model(it)
            elif t in ("tub", "shower", "wetroom"):
                for p_ in (make_tub(it) if t == "tub" else make_shower(it) if t == "shower" else make_wetroom(it)):
                    for c_ in list(p_.users_collection):
                        c_.objects.unlink(p_)
                    c_furn.objects.link(p_)
            else:
                BUILDERS[t](it)
            n_ok += 1
        except Exception as ex:
            print("  furnishing failed:", it.get("id"), ex)
    print(f"furnishings: {n_ok}/{len(items)} placed, {len([k for k, v in _LIBC.items() if v])} models imported")

    # ---- window treatments
    OPN = {o["id"]: o for o in C["openings"]}
    for sh in FU.get("shades", []):
        o = OPN.get(sh["opening"])
        if not o:
            continue
        fm = fabric("shade " + sh.get("color", "#E6E0D4"), sh.get("color", "#E6E0D4"))
        zt = o["head"] - 0.08; zb = zt - sh.get("drop", 0.3) * (o["head"] - o["sill"])
        wbox(o["id"] + " roller shade", o["wall"], o["start"] + 0.12, o["end"] - 0.12, T - 0.06, T - 0.045, zb, zt - 0.2, fm, c_furn)
        wbox(o["id"] + " shade roller", o["wall"], o["start"] + 0.1, o["end"] - 0.1, T - 0.12, T - 0.02, zt - 0.2, zt, "Enamel White", c_furn)
        wbox(o["id"] + " shade bar", o["wall"], o["start"] + 0.12, o["end"] - 0.12, T - 0.07, T - 0.03, zb - 0.06, zb, "Aluminum", c_furn)
    for cu in FU.get("curtains", []):
        o = OPN.get(cu["opening"])
        if not o:
            continue
        fm = fabric("curtain " + cu.get("color", "#E8E2D6"), cu.get("color", "#E8E2D6"))
        fr = wall_frame(o["wall"]); top = o["head"] + 0.55
        wbox(o["id"] + " curtain rod", o["wall"], o["start"] - 1.2, o["end"] + 1.2, T + 0.3, T + 0.36, top + 0.05, top + 0.11, "Black Metal", c_furn)
        for (a0, a1) in ((o["start"] - 1.1, o["start"] + 0.15), (o["end"] - 0.15, o["end"] + 1.1)):
            nfold = 7; amp = 0.1; v, f = [], []
            steps = 28
            for i in range(steps + 1):
                uu = a0 + (a1 - a0) * i / steps
                vv = T + 0.42 + amp * math.sin(i / steps * nfold * 2 * math.pi)
                x_, y_ = fr(uu, vv)
                v += [P(x_, y_, 0.08), P(x_, y_, top)]
                if i:
                    f.append((2 * i - 2, 2 * i - 1, 2 * i + 1, 2 * i))
            ob = mesh_obj(o["id"] + " curtain", v, f, fm, c_furn)
            for p_ in ob.data.polygons:
                p_.use_smooth = True
            md = ob.modifiers.new("thick", 'SOLIDIFY'); md.thickness = 0.02 * F

def make_pivot(name, objs, loc, extras, collection):
    """empty at loc (Blender coords) parenting objs, carrying glTF extras (custom properties)."""
    e = bpy.data.objects.new(name, None); collection.objects.link(e); e.location = loc
    bpy.context.view_layer.update()
    for o in objs:
        if o is None:
            continue
        mw = o.matrix_world.copy(); o.parent = e; o.matrix_parent_inverse = e.matrix_world.inverted(); o.matrix_world = mw
    for k, v in extras.items():
        e[k] = v
    return e


# ================================================================== interior trim: baseboards, doors, casings
BB = FU.get("baseboard_height_in", 4.5) / 12
CW = FU.get("casing_width_in", 3.5) / 12
if FU.get("enabled"):
    segs = []      # (axis, fixed coord, a0, a1, outward sign)
    for (x0, x1, y0, y1) in INT_RECTS:
        if x1 - x0 >= y1 - y0:     # runs in x: faces at y0 (north, outward -y) and y1
            if x1 - x0 > 0.35:
                segs += [("x", y0, x0, x1, -1), ("x", y1, x0, x1, 1)]
        else:
            if y1 - y0 > 0.35:
                segs += [("y", x0, y0, y1, -1), ("y", x1, y0, y1, 1)]

    def cut_runs(a0, a1, holes):
        runs = [(a0, a1)]
        for (h0, h1) in holes:
            nxt = []
            for (r0, r1) in runs:
                if h1 <= r0 or h0 >= r1:
                    nxt.append((r0, r1)); continue
                if h0 > r0: nxt.append((r0, h0))
                if h1 < r1: nxt.append((h1, r1))
            runs = nxt
        return [r for r in runs if r[1] - r[0] > 0.25]

    door_u = {w_: [(o["start"], o["end"]) for o in C["openings"] if o["wall"] == w_ and o["sill"] < 0.2] for w_ in "NSEW"}
    segs += [("x", T, T, HW - T, 1, door_u["N"]), ("x", HD - T, T, HW - T, -1, door_u["S"]),
             ("y", T, T, HD - T, 1, door_u["W"]), ("y", HW - T, T, HD - T, -1, door_u["E"])]
    pas = [(p_[0], p_[1]) for p_ in CL["passages"]]
    segs += [("x", YC, T, HW - T, -1, pas), ("x", YC2, T, HW - T, 1, pas)]
    nb = 0
    for s_ in segs:
        ax, c0, a0, a1, sgn = s_[:5]
        holes = s_[5] if len(s_) > 5 else []
        for (r0, r1) in cut_runs(a0, a1, holes):
            d0, d1 = sorted((c0, c0 + sgn * 0.045))
            if ax == "x":
                box("Baseboard", r0, r1, d0, d1, 0, BB, "White Oak", c_trim)
            else:
                box("Baseboard", d0, d1, r0, r1, 0, BB, "White Oak", c_trim)
            nb += 1
    # interior doors: casing both faces, jambs, white oak slab leaf (open 90 deg where the camera walks through), levers
    walk = [(54, 39.5), (45.5, 39.5), (37, 41.6), (25, 45.5), (13.6, 40.2), (15.5, 39), (23.9, 37.5), (23.5, 30.5), (19.5, 25.2),
            (14.4, 24.0), (14.4, 16.2), (24.5, 13.0), (31.5, 12.6), (35.0, 9.9)]

    def seg_cross(p1, p2, q1, q2):
        def ccw(a, b, c):
            return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])
        return ccw(p1, q1, q2) != ccw(p2, q1, q2) and ccw(p1, p2, q1) != ccw(p1, p2, q2)

    nd_ = 0
    # config door changes: drop detected openings near given points, add ones the A-11 trace does not pair up
    for (rx, ry) in FU.get("door_remove", []):
        def _near(g):
            ax, g0, g1, t0, t1, h = g
            cx, cy = ((g0 + g1) / 2, (t0 + t1) / 2) if ax == "x" else ((t0 + t1) / 2, (g0 + g1) / 2)
            return math.hypot(cx - rx, cy - ry) < 1.5
        DOOR_GAPS[:] = [g for g in DOOR_GAPS if not _near(g)]
    for da in FU.get("door_add", []):
        DOOR_GAPS.append((da["axis"], da["g0"], da["g1"], da["t0"], da["t1"], da.get("head", 6.67)))
        ztop_ = C["ceilings"]["flat_height"] + FLOOR_T
        if da["axis"] == "y":
            box("Header (added door)", da["t0"], da["t1"], da["g0"], da["g1"], da.get("head", 6.67), ztop_, "Drywall", c_int)
        else:
            box("Header (added door)", da["g0"], da["g1"], da["t0"], da["t1"], da.get("head", 6.67), ztop_, "Drywall", c_int)
    for (ax, g0, g1, t0, t1, h) in DOOR_GAPS:
        wdt = g1 - g0
        if ax == "x":
            span = ((g0, (t0 + t1) / 2), (g1, (t0 + t1) / 2))
        else:
            span = (((t0 + t1) / 2, g0), ((t0 + t1) / 2, g1))
        on_path = any(seg_cross(walk[i], walk[i + 1], span[0], span[1]) for i in range(len(walk) - 1)) and not ARGS.get("web")
        _gc = ((g0 + g1) / 2, (t0 + t1) / 2) if ax == "x" else ((t0 + t1) / 2, (g0 + g1) / 2)
        pocket_dir = next((pd[2] for pd in FU.get("door_pocket", []) if math.hypot(pd[0] - _gc[0], pd[1] - _gc[1]) < 1.5), 0)
        if pocket_dir:
            on_path = False

        def B(name, a0, a1, b0, b1, z0, z1, mat="White Oak"):
            """box in door coords: a along the opening, b across the wall."""
            if ax == "x":
                return box(name, a0, a1, b0, b1, z0, z1, mat, c_trim)
            return box(name, b0, b1, a0, a1, z0, z1, mat, c_trim)
        # jambs and casings
        B("Door jamb", g0, g0 + 0.06, t0, t1, 0, h); B("Door jamb", g1 - 0.06, g1, t0, t1, 0, h); B("Door head jamb", g0, g1, t0, t1, h - 0.06, h)
        for (b0, b1) in ((t0 - 0.06, t0), (t1, t1 + 0.06)):
            B("Door casing", g0 - CW, g0 + 0.02, b0, b1, 0, h); B("Door casing", g1 - 0.02, g1 + CW, b0, b1, 0, h)
            B("Door casing", g0 - CW, g1 + CW, b0, b1, h, h + CW)
        leaves = [(g0 + 0.07, g1 - 0.07)] if wdt <= 3.3 else [(g0 + 0.07, (g0 + g1) / 2 - 0.01), ((g0 + g1) / 2 + 0.01, g1 - 0.07)]
        for k_, (l0, l1) in enumerate(leaves):
            lw = l1 - l0; tm = (t0 + t1) / 2
            if on_path:     # swung all the way back flat against the wall beside the opening (clears the hall)
                if k_ == 0:
                    a0_, a1_ = g0 - 0.02 - lw, g0 - 0.02 - CW * 0.0
                else:
                    a0_, a1_ = g1 + 0.02, g1 + 0.02 + lw
                b0_ = t1 + 0.06 + 0.02
                B("Door leaf (open)", a0_, a1_, b0_, b0_ + 0.14, 0.04, h - 0.08)
                lx_ = a0_ + 0.25 if k_ == 0 else a1_ - 0.25
                B("Door lever", lx_ - 0.06, lx_ + 0.06, b0_ + 0.14, b0_ + 0.2, 2.95, 3.12, "Brushed Nickel")
            elif pocket_dir:      # pocket door: leaf slides into the wall beside the opening, flush pulls, no levers
                parts_ = [B("Pocket door leaf", l0, l1, tm - 0.06, tm + 0.06, 0.04, h - 0.08)]
                px_ = l0 + 0.2 if pocket_dir > 0 else l1 - 0.2
                for sgn in (-1, 1):
                    b0 = tm + sgn * 0.06; b1 = b0 + sgn * 0.01
                    parts_.append(B("Pocket door pull", px_ - 0.05, px_ + 0.05, min(b0, b1), max(b0, b1), 3.0, 3.4, "Brushed Nickel"))
                if ARGS.get("web"):
                    d_ = pocket_dir * lw * F
                    make_pivot(f"Pocket door {nd_ + 1}", parts_, P((l0 + l1) / 2, tm, 0) if ax == "x" else P(tm, (l0 + l1) / 2, 0),
                               {"operable": "slide", "slide": [round(d_, 3), 0.0, 0.0] if ax == "x" else [0.0, round(-d_, 3), 0.0]}, c_trim)
            else:
                parts_ = [B("Door leaf", l0, l1, tm - 0.07, tm + 0.07, 0.04, h - 0.08)]
                lx = l1 - 0.25 if k_ == 0 else l0 + 0.25
                for sgn in (-1, 1):
                    b0 = tm + sgn * 0.07; b1 = b0 + sgn * 0.06
                    parts_.append(B("Door lever rose", lx - 0.06, lx + 0.06, min(b0, b1), max(b0, b1), 2.95, 3.12, "Brushed Nickel"))
                    b2 = b1 + sgn * 0.05
                    parts_.append(B("Door lever", lx - 0.32 if k_ == 0 else lx, lx if k_ == 0 else lx + 0.32, min(b1, b2), max(b1, b2), 3.0, 3.06, "Brushed Nickel"))
                if ARGS.get("web"):   # operable node: pivot on the hinge line, swings toward the +b side of the wall
                    ha = l0 if k_ == 0 else l1
                    hp = (ha, tm) if ax == "x" else (tm, ha)
                    sgn_ = (-1 if ax == "x" else 1) * (1 if k_ == 0 else -1)
                    suffix_ = chr(97 + k_) if len(leaves) > 1 else ""
                    make_pivot(f"Door {nd_ + 1}{suffix_}", parts_, P(hp[0], hp[1], 0),
                               {"operable": "swing", "open_angle": 90 * sgn_, "axis": "z"}, c_trim)
        nd_ += 1
    # clerestory wall passages (except the barn door and pantry): cased openings
    for (x0, x1, hd) in CL["passages"][1:]:
        if abs((x0 + x1) / 2 - C.get("barn_door", {}).get("center_x", -99)) < 3.5:
            continue
        for (b0, b1) in ((YC - 0.06, YC), (YC2, YC2 + 0.06)):
            box("Passage casing", x0 - CW, x0 + 0.02, b0, b1, 0, hd, "White Oak", c_trim)
            box("Passage casing", x1 - 0.02, x1 + CW, b0, b1, 0, hd, "White Oak", c_trim)
            box("Passage casing", x0 - CW, x1 + CW, b0, b1, hd, hd + CW, "White Oak", c_trim)
    print(f"trim: {nb} baseboard runs, {nd_} interior doors")

# ================================================================== exterior details
if FU.get("enabled"):
    FH_ = R.get("fascia_height", 1.0)
    zN = north_roof_z(-OH) + TH; zS = south_roof_z(HD + OH) + TH
    # fascia boards at both eaves and the four rakes, level soffits under the eaves
    box("Fascia north", -OH - 0.02, HW + OH + 0.02, -OH - 0.1, -OH, zN - FH_, zN + 0.04, "Trim", c_xdet)
    box("Fascia south", -OH - 0.02, HW + OH + 0.02, HD + OH, HD + OH + 0.1, zS - FH_, zS + 0.04, "Trim", c_xdet)
    for xr in (-OH - 0.1, HW + OH):
        prism_x("Rake fascia north roof", xr, xr + 0.1, [(-OH, north_roof_z(-OH) + TH - FH_), (YC2 + OH, north_roof_z(YC2 + OH) + TH - FH_),
                                                         (YC2 + OH, north_roof_z(YC2 + OH) + TH + 0.04), (-OH, north_roof_z(-OH) + TH + 0.04)], "Trim", c_xdet)
        prism_x("Rake fascia south roof", xr, xr + 0.1, [(YC2, south_roof_z(YC2) + TH - FH_), (HD + OH, south_roof_z(HD + OH) + TH - FH_),
                                                         (HD + OH, south_roof_z(HD + OH) + TH + 0.04), (YC2, south_roof_z(YC2) + TH + 0.04)], "Trim", c_xdet)
    box("Soffit north", -OH, HW + OH, -OH, -0.0, north_roof_z(-OH) - 0.06, north_roof_z(-OH), "Trim", c_xdet)
    box("Soffit south", -OH, HW + OH, HD, HD + OH, south_roof_z(HD + OH) - 0.06, south_roof_z(HD + OH), "Trim", c_xdet)
    if FU.get("gutters", True):
        # 5" K-style gutters at both eaves, 3x4 downspouts at the corners with a kick-out and splash block
        for (yg, zg, sgn) in ((-OH - 0.1, zN - FH_ + 0.25, -1), (HD + OH + 0.1, zS - FH_ + 0.25, 1)):
            y0g, y1g = sorted((yg, yg + sgn * 0.42))
            box("Gutter", -OH - 0.05, HW + OH + 0.05, y0g, y1g, zg, zg + 0.04, "Gutter", c_xdet)
            box("Gutter face", -OH - 0.05, HW + OH + 0.05, min(y0g, y1g) if sgn < 0 else max(y0g, y1g) - 0.04,
                min(y0g, y1g) + 0.04 if sgn < 0 else max(y0g, y1g), zg, zg + 0.42, "Gutter", c_xdet)
            for xd in (-OH + 0.6, HW + OH - 0.9):
                yd = (y0g + y1g) / 2
                ywall = 0.0 if sgn < 0 else HD
                box("Downspout offset", xd, xd + 0.33, min(yd, ywall), max(yd, ywall), zg - 0.9, zg - 0.6, "Gutter", c_xdet)
                yy0, yy1 = sorted((ywall + sgn * 0.02, ywall + sgn * 0.27))
                gz = ground_z(xd, ywall)
                box("Downspout", xd, xd + 0.33, yy0, yy1, gz + 0.6, zg - 0.6, "Gutter", c_xdet)
                b0, b1 = sorted((ywall + sgn * 0.02, ywall + sgn * 0.9))
                box("Downspout kick-out", xd, xd + 0.33, b0, b1, gz + 0.35, gz + 0.6, "Gutter", c_xdet)
                c0, c1 = sorted((ywall + sgn * 0.6, ywall + sgn * 2.6))
                box("Splash block", xd - 0.3, xd + 0.63, c0, c1, gz - 0.05, gz + 0.12, "Concrete", c_xdet)
    # thresholds at every exterior door
    for o in C["openings"]:
        if o["sill"] < 0.2:
            wbox(o["id"] + " threshold", o["wall"], o["start"], o["end"], -0.12, T + 0.02, 0.0, 0.06, "Aluminum", c_xdet)
    # wall lights, outlets, hose bibs
    for fx in FU.get("exterior_fixtures", []):
        w_, u_, z_ = fx["wall"], fx["u"], fx["z"]
        fr = wall_frame(w_)
        face = {"N": 0, "S": 180, "E": 90, "W": 270}[w_]
        x_, y_ = fr(u_, -BAT_T - 0.01)
        if fx["type"] == "light" and FU.get("exterior_lights", True):
            e = place_model({"id": f"Wall light {w_} {u_}", "model": "industrial_wall_lamp", "x": x_, "y": y_, "z": z_ - 0.5,
                             "facing": face, "len": 0.9, "wall": True})
            if e is not None:
                for c_ in list(e.users_collection):
                    c_.objects.unlink(e)
                c_xdet.objects.link(e)
            dx, dy = fr(u_, -BAT_T - 0.6)
            ld = bpy.data.lights.new(f"Wall light {w_} {u_}", 'POINT'); ld.energy = 30; ld.color = (1.0, 0.82, 0.6); ld.shadow_soft_size = 0.1 * F
            lo = bpy.data.objects.new(f"Wall light {w_} {u_} bulb", ld); lo.location = P(dx, dy, z_); c_xdet.objects.link(lo)
        elif fx["type"] == "outlet":
            wbox("Exterior outlet box", w_, u_ - 0.2, u_ + 0.2, -BAT_T - 0.2, -BAT_T, z_ - 0.25, z_ + 0.25, "Plastic Grey", c_xdet)
            wbox("Exterior outlet cover", w_, u_ - 0.17, u_ + 0.17, -BAT_T - 0.24, -BAT_T - 0.2, z_ - 0.2, z_ + 0.22, "Plastic Grey", c_xdet)
        elif fx["type"] == "hose_bib":
            wbox("Hose bib flange", w_, u_ - 0.12, u_ + 0.12, -BAT_T - 0.05, -BAT_T, z_ - 0.12, z_ + 0.12, "Brushed Nickel", c_xdet)
            wbox("Hose bib body", w_, u_ - 0.05, u_ + 0.05, -BAT_T - 0.4, -BAT_T - 0.05, z_ - 0.05, z_ + 0.05, "Brushed Nickel", c_xdet)
            wbox("Hose bib spout", w_, u_ - 0.04, u_ + 0.04, -BAT_T - 0.42, -BAT_T - 0.34, z_ - 0.2, z_, "Brushed Nickel", c_xdet)
            wbox("Hose bib handle", w_, u_ - 0.1, u_ + 0.1, -BAT_T - 0.28, -BAT_T - 0.24, z_ + 0.05, z_ + 0.15, "Brushed Nickel", c_xdet)
    print("exterior details: fascia, soffits, gutters, thresholds, fixtures")

# ================================================================== room light fixtures (night) -> LIGHTS registry
LIGHTS = []        # dicts for the web manifest: name, room, pos (Blender m), kind, color, intensity_lm
LG = C.get("lighting", {})
if LG.get("enabled"):
    for o in [o for o in c_cam.objects if o.name.startswith("Can ")]:
        bpy.data.objects.remove(o)               # generic render fill lights replaced by real fixtures
    simple("Light Lens", "#FFF4E0", 0.4)
    _ll = MATS["Light Lens"].node_tree.nodes["Principled BSDF"]
    _ll.inputs["Emission Color"].default_value = hexcol("#FFE6C2"); _ll.inputs["Emission Strength"].default_value = 3.0

    def ceiling_at(x, y):
        for (a0, b0, a1, b1) in C["ceilings"]["flat_rooms"]:
            if a0 <= x <= a1 and b0 <= y <= b1:
                return C["ceilings"]["flat_height"]
        if LOFT["enabled"] and LX0 <= x <= LX1 and LY0 <= y <= LY1:
            return roof_under(y)               # the loft sees the roof
        if 63 <= x <= 96 and 15 <= y <= 43:
            return C["garage"]["south_wall_height"] - 0.6
        if 43 <= x <= 63 and 26 <= y <= 43:
            return C["porch"]["high_height"] - 1.2
        if 0 <= x <= HW and 52 <= y <= 72:
            return C["greenhouse"]["south_height"] + 1.0
        return roof_under(y)
    for k, (room, x, y, kind, lm) in enumerate(LG.get("fixtures", [])):
        if room == "Greenhouse" and not C["greenhouse"]["enabled"]:
            continue
        zc = ceiling_at(x, y) - 0.02
        nm = f"Light {room} {k}"
        if kind == "can":
            fx = [cyl(nm + " trim", 0.3, 0.3, 0.03, "Enamel White", zc - 0.03, cx=x, cy=y, collection=c_furn),
                  cyl(nm + " lens", 0.22, 0.22, 0.01, "Light Lens", zc - 0.035, cx=x, cy=y, collection=c_furn)]
        else:
            fx = [cyl(nm + " base", 0.45, 0.45, 0.06, "Enamel White", zc - 0.06, cx=x, cy=y, collection=c_furn),
                  cyl(nm + " lens", 0.42, 0.34, 0.18, "Light Lens", zc - 0.24, cx=x, cy=y, collection=c_furn)]
        for f_ in fx:
            f_["emissive_night"] = True
        zl = zc - (0.5 if kind == "flush" else 0.3)
        ld = bpy.data.lights.new(nm, 'POINT'); ld.energy = lm / 683 * 4 * math.pi / 8; ld.color = (1.0, 0.86, 0.7); ld.shadow_soft_size = 0.2 * F
        lo = bpy.data.objects.new(nm, ld); lo.location = P(x, y, zl); c_cam.objects.link(lo)
        LIGHTS.append({"name": nm, "room": room, "pos": [round(v, 3) for v in P(x, y, zl)], "kind": "spot" if kind == "can" else "point",
                       "color": "#FFDBB3", "intensity_lm": lm})
    # lamps, pendants, exterior wall lights already in the scene
    for o in bpy.data.objects:
        if o.type == 'LIGHT' and o.data.type == 'POINT' and not o.name.startswith(("Light ", "Can ")):
            kind_ = "exterior" if "Wall light" in o.name else ("garage" if "Garage light" in o.name else "lamp")
            LIGHTS.append({"name": o.name, "room": kind_, "pos": [round(v, 3) for v in o.location], "kind": "point",
                           "color": "#FFD9A8", "intensity_lm": int(round(o.data.energy * 683 / (4 * math.pi) * 8 / 2))})
    for o in bpy.data.objects:     # fixture meshes that glow at night
        if o.type == 'MESH' and any(s.material and s.material.name in ("Bulb Glow", "Light Lens", "Lamp Shade") for s in o.material_slots):
            o["emissive_night"] = True
    print(f"lighting: {len(LG.get('fixtures', []))} room fixtures, {len(LIGHTS)} lights total")

# ================================================================== real-scale wood with the grain along each piece
if AS.get("enabled") and PHT:
    wood_mats = {"White Oak": dict(tid=PHT.get("white_oak"), hsv=(0.5, 0.85, 1.12), tint="#C9AE84", tint_amount=0.25, rough=(0.35, 0.5), normal=0.35),
                 "Cabinet Wood": dict(tid=PHT.get("cabinet_oak"), tint=KK["cabinet_wood"], tint_amount=0.35, rough=(0.38, 0.52), normal=0.3),
                 "Siding": dict(tid=PHT.get("siding_grain"), solid=MM["siding_color"], rough=(0.62, 0.85), normal=0.9)}
    vertical = {"Siding"}
    by_mat = {k: [] for k in wood_mats}
    for ob in bpy.data.objects:
        if ob.type != 'MESH' or ob.library:
            continue
        for k in wood_mats:
            if any(s.material and s.material.name == k for s in ob.material_slots):
                by_mat[k].append(ob)
    for k, cfg in wood_mats.items():
        if wood_uv(k, cfg.pop("tid"), color=(k == "Siding"), **cfg):
            nobj = wood_unwrap(by_mat[k], vertical=k in vertical)
            print(f"wood: {k} on {nobj} objects, real-scale UVs")
