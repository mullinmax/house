#!/usr/bin/env python3
"""Writes site/models/house.json: the house itself (slab, walls, roof, windows, doors, cabinets, trim, loft, garage,
porch, greenhouse) as records the walkthrough builds in the browser (site/house.js). Plain Python, no Blender.

    python model/make_house.py              (then reload the site)
    python model/make_house.py --check      (also lists coplanar faces the nudge could not move)
    node tools/coplanar_audit.mjs           (finds every visible flicker in the built scene; GitHub runs it on each PR)

Every record has an id, a name, a kind, a layer and an info card, and lists the shapes it is made of. Shapes are in
plan feet (x east, y south from the outside NW slab corner, z up from the slab top):
  ["b", mat, x0, x1, y0, y1, z0, z1]                   axis aligned box
  ["x", mat, [24 numbers], faces?]                       six sided solid: corners 0-3 one ring, 4-7 the opposite ring;
                                                         faces = 6 materials (bottom, top, then the sides) if they differ
  ["w", mat, frame, v0, v1, zbot, top, holes]            wall panel with rectangular openings. frame = [ox, oy, ux, uy, vx, vy]
                                                         maps (u along the wall, v into it) to plan x, y. top = [[u0, z0, u1, z1], ...]
                                                         is the top edge, holes = [[u0, u1, z0, z1], ...]
  ["q", mat, [[x, y, z], ...]]                           flat polygon, seen from both sides
  ["c", mat, cx, cy, z0, z1, r0, r1]                     vertical cylinder (r0 at the bottom, r1 at the top)
Moving parts sit in a record's "ops": {id, name, type: swing|slide|drawer|rollup, pivot [x, y, z], angle (deg, + turns
counterclockwise seen from above), slide [dx, dy, dz] plan ft, parts}.

This is a port of archive/blender/build_house.py and build_details.py (v21, 11/13/2026): same config, same rules,
same numbers. Records marked "placeholder_for" are the plain appliance boxes from the Blender model; the walkthrough
skips them when site/models/equipment.json has the real appliance.
"""
import json, math, os, sys
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("HOUSE_OUT") or os.path.join(HERE, "..", "site", "models", "house.json")
with open(os.path.join(HERE, "config.toml"), "rb") as _f:
    C = tomllib.load(_f)
with open(os.path.join(HERE, C["house"]["int_wall_source"])) as _f:
    G = json.load(_f)

HW, HD, T = C["house"]["width_x"], C["house"]["depth_y"], C["house"]["ext_wall_thickness"]
R = C["roof"]
PN, PS = R["north_pitch"] / 12.0, R["south_pitch"] / 12.0
YC = R["clerestory_wall_y"]                    # north face of the clerestory wall
YC2 = YC + T                                   # its south face
H_N, H_S = R["north_wall_height"], R["south_wall_height"]
H_CL = H_S + (HD - YC2) * PS                   # where the low roof meets the clerestory wall
OH, TH = R["overhang"], R["panel_thickness"]
MM = C["materials"]
FU = C.get("furnishings", {})
CL = C["clerestory"]
EC = C.get("entry_closet", {})                  # entry closet built around the beam posts (Maxwell's builder, 11/19/2026)
EC_STYLE = EC.get("style", "closet")
EC_OPEN = tuple(EC.get("opening", [40.789, 42.289]))
# a built-in in the closet opening and the mudroom unit read as one piece: no oak casing leg between them, the strip of wall
# over the beam posts faced in the cabinet paint (Maxwell 11/19/2026)
EC_MERGE = bool(EC) and EC.get("merge_cubby", True) and EC_STYLE in ("cabinet", "pullout", "coat")
if EC_STYLE == "open":                          # no closet: the cubby runs on east to a short wall of posts at the east wall (Maxwell 11/19/2026)
    _cub = min((p_ for p_ in CL["passages"] if p_[1] <= EC_OPEN[0] + 0.01), key=lambda p_: EC_OPEN[0] - p_[1])
    CL["passages"] = [p_ for p_ in CL["passages"] if abs(p_[0] - EC_OPEN[0]) > 0.01]
    _cub[1] = EC["open_to"]
    EC["posts"], EC["post_plies"] = EC.get("open_posts", [EC["open_to"] + 0.02, EC["open_to"] + 0.395]), EC.get("open_post_plies", 3)
LOFT = C["loft"]
LX0, LY0, LX1, LY1 = LOFT["rect"]
_ft = C.get("floor_trusses")
FLOOR_T = (_ft["depth_in"] + _ft.get("deck_in", 0.75)) / 12 if _ft else 0.86    # attic deck and loft floor build-up
LOFT_FIN = 0.0625          # 3/4" oak finish floor of the loft: it caps the loft edge wall, so the drywall runs right up under the railing
FH = C["ceilings"]["flat_height"]
DECK_T = 0.06                                  # attic decking shown on top of the flat ceilings
GROUND_Z = -0.62                               # graded pad just outside the slab (8 in reveal)


def north_roof_z(y):
    return H_N + y * PN


def south_roof_z(y):
    return H_S + (HD - y) * PS


def roof_under(y):
    return north_roof_z(y) if y <= YC2 + 1e-6 else south_roof_z(y)


def ftin(v):
    t = round(v * 12 * 8) / 8
    ft, inch = int(t // 12), t - 12 * int(t // 12)
    s = f"{inch:g}".replace(".5", " 1/2").replace(".25", " 1/4").replace(".75", " 3/4").replace(".125", " 1/8").replace(".375", " 3/8").replace(".625", " 5/8").replace(".875", " 7/8")
    return f"{ft}' {s}\"" if ft else f"{s}\""


# ------------------------------------------------------------------ records and shapes
RECS, BYID = [], {}
CUR = [None]          # parts list shapes go to


def rnd(v):
    return round(v, 4)


def rec(id, kind, name, layer, info=None, **kw):
    if id in BYID:
        k = 2
        while f"{id}.{k}" in BYID:
            k += 1
        id = f"{id}.{k}"
    r = dict(id=id, kind=kind, name=name, layer=layer, parts=[])
    if info:
        r["info"] = info
    r.update({k: v for k, v in kw.items() if v is not None})
    RECS.append(r); BYID[id] = r
    CUR[0] = r["parts"]
    return r


class into:
    """with into(parts): shapes go to this list (an operable's parts), then back."""
    def __init__(self, parts):
        self.parts = parts

    def __enter__(self):
        self.prev = CUR[0]; CUR[0] = self.parts

    def __exit__(self, *a):
        CUR[0] = self.prev


def op(r, id, name, type, pivot, angle=None, slide=None):
    o = dict(id=id, name=name, type=type, pivot=[rnd(v) for v in pivot], parts=[])
    if angle is not None:
        o["angle"] = angle
    if slide is not None:
        o["slide"] = [rnd(v) for v in slide]
    r.setdefault("ops", []).append(o)
    return o


def box(mat, x0, x1, y0, y1, z0, z1, ztop=None, open_ends=()):
    """open_ends (ztop boxes only): faces left out, by X_FACES index (2 y0, 3 x1, 4 y1, 5 x0): an end buried in the
    piece it butts into, whose edge would otherwise draw a hairline along the wall face"""
    xs, ys = sorted((x0, x1)), sorted((y0, y1))
    zs = sorted((z0, z1)) if ztop is None else (z0, z1)
    if ztop is None:
        if xs[1] - xs[0] < 1e-5 or ys[1] - ys[0] < 1e-5 or zs[1] - zs[0] < 1e-5:
            return
        CUR[0].append(["b", mat] + [rnd(v) for v in (xs[0], xs[1], ys[0], ys[1], zs[0], zs[1])])
        return
    pts = [(xs[0], ys[0], z0), (xs[1], ys[0], z0), (xs[1], ys[1], z0), (xs[0], ys[1], z0),
           (xs[0], ys[0], ztop(xs[0], ys[0])), (xs[1], ys[0], ztop(xs[1], ys[0])),
           (xs[1], ys[1], ztop(xs[1], ys[1])), (xs[0], ys[1], ztop(xs[0], ys[1]))]
    hexa(mat, pts, [None if i in open_ends else mat for i in range(6)] if open_ends else None)


def hexa(mat, pts, faces=None):
    s = ["x", mat, [rnd(c) for p in pts for c in p]]
    if faces:
        s.append(faces)
    CUR[0].append(s)


def prism_x(mat, x0, x1, prof):
    """four point (y, z) profile pushed along x"""
    assert len(prof) == 4
    hexa(mat, [(x0, y, z) for y, z in prof] + [(x1, y, z) for y, z in prof])


def quad(mat, pts):
    CUR[0].append(["q", mat, [[rnd(c) for c in p] for p in pts]])


def cyl(mat, cx, cy, z0, z1, r0, r1=None):
    CUR[0].append(["c", mat, rnd(cx), rnd(cy), rnd(z0), rnd(z1), rnd(r0), rnd(r0 if r1 is None else r1)])


FRAMES = {"N": (0, 0, 1, 0, 0, 1), "S": (0, HD, 1, 0, 0, -1), "W": (0, 0, 0, 1, 1, 0), "E": (HW, 0, 0, 1, -1, 0), "C": (0, YC2, 1, 0, 0, -1)}


def wall_frame(wall):
    """(u, v) -> plan (x, y): u along the wall, v depth inward from the exterior face."""
    ox, oy, ux, uy, vx, vy = FRAMES[wall]
    return lambda u, v: (ox + u * ux + v * vx, oy + u * uy + v * vy)


def wbox(mat, wall, u0, u1, v0, v1, z0, z1):
    f = wall_frame(wall)
    a, b = f(u0, v0), f(u1, v1)
    box(mat, a[0], b[0], a[1], b[1], z0, z1)


WBOX = wbox


def panel(mat, frame, v0, v1, zbot, top, holes):
    CUR[0].append(["w", mat, list(frame), rnd(v0), rnd(v1), rnd(zbot), [[rnd(v) for v in s] for s in top],
                   [[rnd(v) for v in h] for h in holes]])


# ------------------------------------------------------------------ materials (colours as the last Blender export showed them)
K = C["kitchen"]
MATERIALS = {
    "Stained Concrete": dict(color=MM["floor_color"], color2=MM.get("floor_color_2", "#5A2A1A"), rough=MM.get("floor_gloss", 0.35) + 0.05,
                             canvas="slab", cut_pattern=MM.get("floor_cut_pattern", "diamond"), cut_spacing=MM.get("floor_cut_spacing", 9.0),
                             cut_origin=MM.get("floor_cut_origin", [0, 0]), size=[HW, HD]),
    "Concrete": dict(color="#FFFFFF", rough=0.8, map="concrete.jpg", tile=2.0),
    "OSB": dict(color="#C9A46A", rough=0.85),
    "EPS Foam": dict(color="#EEECE2", rough=0.95),
    "Siding": dict(color=MM.get("siding_albedo", MM["siding_color"]), rough=0.735, normal="siding_normal.jpg", normal_scale=0.5, tile=0.9, grain="vertical"),
    "Drywall": dict(color="#FFFFFF", rough=0.84, map="plaster.jpg", tile=1.5),
    "Tile Wall": dict(color="#FFFFFF", rough=0.17, map="tile_wall.jpg", tile=1.0),   # same texture as the baked wet room tile
    "Trim": dict(color=MM.get("trim_albedo", MM["trim_color"]), rough=0.5),
    "Window Frame": dict(color=MM["window_exterior_color"], rough=0.35, metal=0.3),
    "White Oak": dict(color="#FFFFFF", rough=0.425, map="white_oak.jpg", normal="oak_normal.jpg", normal_scale=0.5, tile=0.8, grain="long"),
    # light natural wood of Danielle Gross's 11/19/2026 north wall rendering (tools/make_cabinet_texture.py)
    # Maxwell 11/19/2026: the cabinets use the same white oak as the windows and trim (cabinet_map = "cabinet_natural.jpg" is Danielle's lighter tone)
    "Cabinet Wood": dict(color="#FFFFFF", rough=0.425, map=K.get("cabinet_map", "white_oak.jpg"), normal="oak_normal.jpg", normal_scale=0.5, tile=0.8, grain="long"),
    "Island": dict(color=K["island_color"], rough=0.5),
    "Counter": dict(color="#FFFFFF", rough=0.17, map="quartz.jpg", tile=1.6),
    "Glass": dict(color="#C8D4D6", rough=0.05, metal=0.2, opacity=0.14),
    "Cabinet Glass": dict(color="#B9C9CB", rough=0.04, metal=0.3, opacity=0.32),           # glass door uppers: tinted enough to read as glass
    "Black Glass": dict(color="#0B0B0C", rough=0.05, opacity=0.25),
    "Polycarbonate": dict(color="#F2F2EE", rough=0.2, opacity=0.45),
    "Stainless": dict(color="#C8CACC", rough=0.25, metal=1.0),
    "Brushed Nickel": dict(color=K.get("hardware_color", "#B8B8B4"), rough=0.3, metal=1.0),
    "Spice Red": dict(color="#8E2A1C", rough=0.8), "Spice Yellow": dict(color="#C99A22", rough=0.8), "Spice Green": dict(color="#5E6B32", rough=0.8),
    "Spice Brown": dict(color="#6A4426", rough=0.8), "Spice Orange": dict(color="#B4561E", rough=0.8),
    "Sesame": dict(color="#E2CC96", rough=0.8), "Gold Lid": dict(color="#C9A13A", rough=0.3, metal=1.0),
    "Mug Blue": dict(color="#2F5A8A", rough=0.25), "Mug Mustard": dict(color="#C9952B", rough=0.25), "Mug Sage": dict(color="#8FA285", rough=0.25),
    "Mug Terracotta": dict(color="#B4583A", rough=0.25), "Mug Cream": dict(color="#EFE6D2", rough=0.25),
    "Dishware": dict(color="#F2F0EA", rough=0.2),                                                 # plates and mugs in the glass door upper
    "Cabinet Pull": dict(color=K.get("pull_color", "#C9A465"), rough=0.32, metal=1.0),        # satin brass bar pulls on every kitchen cabinet (Maxwell 11/20/2026)
    "Butcher Block": dict(color="#FFFFFF", rough=0.5, map=K.get("island_top_map", "butcher_block.jpg"), tile=0.8, grain="long"),   # island top (Maxwell 11/20/2026)
    "Black Metal": dict(color="#151515", rough=0.4, metal=0.6),
    "Aluminum": dict(color="#B9BCBE", rough=0.35, metal=1.0),
    "Gutter": dict(color=MM.get("trim_albedo", MM["trim_color"]), rough=0.45, metal=0.4),
    "Standing Seam": dict(color=MM["roof_color"], rough=0.41, metal=0.6),
    "Garage Door": dict(color="#2A2A2A", rough=0.5),
    "Plastic Grey": dict(color="#9A9A96", rough=0.5),
    "Smoked Flap": dict(color="#3B3A36", rough=0.2),
    "Appliance Interior": dict(color="#1A1A1A", rough=0.6),
    "Attic Deck": dict(color="#C8B28A", rough=0.85),
    "Lumber": dict(color="#D9B98A", rough=0.85),                                            # framing (Framing layer)
    "Header": dict(color="#C07A3A", rough=0.8),                                             # door headers in sawn lumber, darker so they read
    "LVL": dict(color="#D98C2B", rough=0.7),                                                # engineered beams
    "Gravel": dict(color="#8A8378", rough=0.95),
    "Lamp Glass": dict(color="#FFF1D6", rough=0.3, opacity=0.7, night_glow=True),
}


def paint(hexc):
    nm = "Paint " + hexc
    MATERIALS.setdefault(nm, dict(color=hexc, rough=0.45))
    return nm


ROOMS = [("Bedroom 1", 31.1, 0.5, 42.6, 15.03), ("Bedroom 2", 5.9, 0.5, 16.1, 10.7), ("Bath 2", 16.1, 0.5, 22.7, 10.7), ("Bedroom 4 / study", 22.7, 0.5, 31.1, 10.7),
         ("Closet 2", 0.5, 0.5, 5.9, 5.5), ("Closet 3", 0.5, 5.5, 5.9, 10.9), ("Bedroom 3", 0.5, 10.95, 12.12, 22.41), ("Hall 2", 12.12, 10.95, 30.25, 15.03),
         ("Linen", 12.12, 15.03, 16.66, 22.87), ("Laundry", 16.66, 15.03, 31.12, 22.87), ("Closet 1", 31.12, 15.49, 42.5, 22.87), ("Utility", 0.5, 22.87, 12.12, 29.03),
         ("Pantry", 0.5, 29.03, 5.6, 34.62), ("Powder", 5.6, 29.03, 12.12, 34.62), ("Hall 1", 12.12, 22.87, 16.66, 34.62), ("Living", 16.66, 22.87, 31.12, 34.62),
         ("Bath 1", 31.12, 22.87, 42.5, 34.62), ("Kitchen", 0.5, 35.16, 16.0, 51.5), ("Dining", 16.0, 35.16, 31.5, 51.5), ("Entry / family", 31.5, 35.16, 42.6, 51.5)]


def room_at(x, y):
    for nm, a0, b0, a1, b1 in ROOMS:
        if a0 <= x <= a1 and b0 <= y <= b1:
            return nm
    return None


# ------------------------------------------------------------------ slab
rec("slab", "slab", "Slab and stained concrete floor", "interior", room="Whole house",
    info=dict(model=f"{ftin(C['house']['slab_thickness'])} slab, stained and sealed concrete",
              specs=[["Size", f"{ftin(HW)} x {ftin(HD)}"], ["Stain", f"Red brown leather, {MM['floor_color']} mottled with {MM.get('floor_color_2', '')}"],
                     ["Saw cuts", f"{MM.get('floor_cut_pattern', 'diamond')}, {ftin(MM.get('floor_cut_spacing', 9.0))} grid, a point at the south door centre"]],
              notes=["Saw cut layout from Maxwell, 11/12/2026."]))
box("Stained Concrete", 0, HW, 0, HD, -C["house"]["slab_thickness"], 0)
for (a0, a1, b0, b1) in ((-0.02, HW + 0.02, -0.02, 0.0), (-0.02, HW + 0.02, HD, HD + 0.02), (-0.02, 0.0, 0, HD), (HW, HW + 0.02, 0, HD)):
    box("Concrete", a0, a1, b0, b1, -0.62, 0.0)                 # exposed slab edge is plain concrete

# ------------------------------------------------------------------ openings
# Exterior wall build up, outside to inside (A-41 wall type 1 and the S.I.P. notes on A-12):
#   LP SmartSide 3/8" + TamlynWrap rain screen | 6 1/2" SIP: 7/16" OSB, 5 5/8" EPS, 7/16" OSB | 1/2" gypsum
# The finished inside face stays at T (6 1/2" in from the slab edge), where the traced A-11 rooms put it,
# so the SIP's outside face lands 1/2" outside the slab edge. ASSUMED: which face the plan dimensions run to.
GYP = 0.5 / 12                                               # gypsum board
OSB = 7 / 192                                                # 7/16" OSB skins
SIP_T = 6.5 / 12                                             # 6 1/2" panel
E0 = T - GYP - SIP_T                                         # outside face of the SIP (frame v, negative = outside the slab)
SKIN = (0.375 + 0.0625) / 12                                 # siding panel + rain screen
VF = E0 - SKIN                                               # outside face of the siding (battens and trim sit on it)
BAT_T = MM.get("batten_thickness_in", 0.75) / 12
BAT_SP, BAT_W = MM["batten_spacing_in"] / 12, MM["batten_width_in"] / 12
TRIM_W = 4 / 12
OPEN = list(C["openings"])
CLER = [{"id": f"W30-30 clerestory {k + 1}", "wall": "C", "kind": "awning",
         "start": CL["first_center_x"] + k * CL["spacing"] - CL["width"] / 2, "end": CL["first_center_x"] + k * CL["spacing"] + CL["width"] / 2,
         "sill": CL["sill"], "head": CL["head"]} for k in range(CL["count"])]
KIND_NAMES = {"casement": "casement window", "casement_pair": "pair of casement windows", "awning": "awning window", "awning_pair": "pair of awning windows",
              "fixed": "fixed window", "door_glass": "full lite door", "slider": "bi-parting sliding door"}
WALL_NAMES = {"N": "north wall", "S": "south wall", "E": "east wall", "W": "west wall", "C": "clerestory wall"}


def is_door(o):
    return o["kind"].startswith("door") or o["kind"] == "slider"


def cuts_for(wall):
    hs = [(o["start"], o["end"], o["sill"], o["head"]) + ((o["head_end"],) if "head_end" in o else ()) for o in OPEN + CLER if o["wall"] == wall]
    if wall == "C":
        hs += [(x0, x1, -0.1, hd) for (x0, x1, hd) in CL["passages"]]
    return hs


def window_unit(o):
    wall, kind = o["wall"], o["kind"]
    u0, u1, z0, z1 = o["start"], o["end"], o["sill"], o["head"]
    z1b = o.get("head_end", z1)                              # head at the end jamb: transoms that follow the roof (A-20)
    door = is_door(o)

    def wbox(mat, wall_, a, b, va, vb, za, zb):
        """the module's wbox, but anything in the upper half of the opening follows a sloped head"""
        if z1b == z1:
            return WBOX(mat, wall_, a, b, va, vb, za, zb)
        f, zm = wall_frame(wall_), (z0 + z1) / 2
        adj = lambda z, u: z + (z1b - z1) * (u - u0) / (u1 - u0) if z > zm else z
        ring = [(a, va), (b, va), (b, vb), (a, vb)]
        hexa(mat, [f(u, v) + (adj(za, u),) for u, v in ring] + [f(u, v) + (adj(zb, u),) for u, v in ring])
    code = o["id"].split()[0]
    where = " ".join(o["id"].split()[1:])
    kn = KIND_NAMES.get(kind, kind.replace("_", " "))
    info = dict(model=f"{code} {kn}", specs=[["Rough opening", f"{ftin(u1 - u0)} wide x {ftin(z1 - z0)} tall"],
                                             ["Sill" if not door else "Threshold", ftin(z0)], ["Head", ftin(z1) if z1b == z1 else f"{ftin(z1)} sloping to {ftin(z1b)} with the roof (A-20, A-21)"], ["Wall", WALL_NAMES[wall]],
                                             ["Finish", "Black clad outside, white oak inside" if not o.get("interior_color") else f"Black clad outside, painted {o['interior_color']} inside"]],
                notes=["Location from the A-11 vector data, heights from the A-20 and A-21 elevations."] if not o["id"].startswith("W30-30 clerestory")
                else ["8 W30-30 awnings, 4' 10 1/2\" on centre (A-12), sill and head from the A-20 south elevation."])
    if where.lower().endswith(" door"):
        where = where[:-5]
    if where.lower() in kn:                                  # "D120-80 Bi-parting": name it by the room instead
        fx_, fy_ = wall_frame(wall)((u0 + u1) / 2, T + 1)
        where = room_at(fx_, fy_) or ""
    r = rec(("door." if door else "window.") + o["id"].lower().replace(" ", "_"), "door" if door else "window", f"{where} {kn}" if where else kn[0].upper() + kn[1:],
            "shell", info=info, room=where or None)
    fw, fd = 0.18, 0.30
    v0 = E0 + 0.05
    vm = v0 + fd * 0.5
    inner = paint(o["interior_color"]) if o.get("interior_color") else "White Oak"
    leaf = None
    if kind == "door_glass":
        fr = wall_frame(wall)
        hu, hd = (u1, -1) if o.get("hinge") == "end" else (u0, 1)   # hinge jamb: the opening's start, or its end when the plan says so
        hx, hy = fr(hu, E0 + 0.2)
        ax = fr(hu + hd, 0); a0 = fr(hu, 0); inn = fr(hu, 1)
        axv, inv = (ax[0] - a0[0], -(ax[1] - a0[1])), (inn[0] - a0[0], -(inn[1] - a0[1]))      # Blender frame (y north)
        sgn = 1 if axv[0] * inv[1] - axv[1] * inv[0] > 0 else -1
        leaf = op(r, r["id"] + ".leaf", r["name"], "swing", (hx, hy, 0), angle=90 * sgn)
    for (va, vb, fm) in ((v0, vm, "Window Frame"), (vm, v0 + fd, inner)):
        with into(leaf["parts"] if leaf else CUR[0]):
            wbox(fm, wall, u0, u0 + fw, va, vb, z0, z1)
            wbox(fm, wall, u1 - fw, u1, va, vb, z0, z1)
            wbox(fm, wall, u0 + fw, u1 - fw, va, vb, z1 - fw, z1)
            zb = z0 + (0.12 if door else fw)
            wbox(fm, wall, u0 + fw, u1 - fw, va, vb, z0, zb)
            if kind == "door_glass":
                wbox(fm, wall, u0 + fw, u1 - fw, va, vb, zb, z0 + 0.9)          # kick rail
        if kind != "slider":
            n_panels = {"casement_pair": 2, "awning_pair": 2}.get(kind, 1)
            for k in range(1, n_panels):
                um = u0 + (u1 - u0) * k / n_panels
                wbox(fm, wall, um - fw / 2, um + fw / 2, va, vb, zb, z1 - fw)
    if kind == "slider":         # two fixed outer panes, two leaves that part and slide over them
        w4 = (u1 - u0) / 4
        fr = wall_frame(wall)
        for (a, b, nm, vv) in ((u0 + 0.09, u0 + w4, "fixed W", 0.4), (u1 - w4, u1 - 0.09, "fixed E", 0.4),
                               (u0 + w4, (u0 + u1) / 2 - 0.01, "leaf W", 0.55), ((u0 + u1) / 2 + 0.01, u1 - w4, "leaf E", 0.55)):
            if nm.startswith("leaf"):
                sg = -1 if nm == "leaf W" else 1
                d = (fr(u0 + sg * w4, 0)[0] - fr(u0, 0)[0], fr(u0 + sg * w4, 0)[1] - fr(u0, 0)[1])
                cx, cy = fr((a + b) / 2, v0 + 0.3 * vv)
                lf = op(r, f"{r['id']}.{nm.split()[1].lower()}", f"{r['name']}, {'west' if sg < 0 else 'east'} leaf", "slide", (cx, cy, 0), slide=(d[0], d[1], 0))
                with into(lf["parts"]):
                    wbox("Glass", wall, a, b, v0 + 0.3 * vv - 0.015, v0 + 0.3 * vv + 0.015, z0 + 0.12, z1 - 0.05)
                    vv0, vv1 = v0 + 0.3 * vv - 0.035, v0 + 0.3 * vv + 0.035
                    wbox("Window Frame", wall, a, b, vv0, vv1, z0 + 0.06, z0 + 0.16)
                    wbox("Window Frame", wall, a, b, vv0, vv1, z1 - 0.12, z1 - 0.04)
                    wbox("Window Frame", wall, a, a + 0.12, vv0, vv1, z0 + 0.06, z1 - 0.04)
                    wbox("Window Frame", wall, b - 0.12, b, vv0, vv1, z0 + 0.06, z1 - 0.04)
                    ha, hb = (b - 0.3, b - 0.2) if nm == "leaf W" else (a + 0.2, a + 0.3)
                    wbox("Brushed Nickel", wall, ha, hb, vv1, vv1 + 0.06, 3.0, 4.2)
            else:
                wbox("Glass", wall, a, b, v0 + 0.3 * vv - 0.015, v0 + 0.3 * vv + 0.015, z0 + 0.12, z1 - 0.05)
    else:
        with into(leaf["parts"] if leaf else CUR[0]):
            wbox("Glass", wall, u0 + fw * 0.5, u1 - fw * 0.5, v0 + fd * 0.45, v0 + fd * 0.55, z0 + 0.05, z1 - 0.05)
    tw = 4 / 12                                             # 4" Abyss Black exterior trim
    wbox("Trim", wall, u0 - tw, u0, VF - BAT_T - 0.02, E0, z0, z1)
    wbox("Trim", wall, u1, u1 + tw, VF - BAT_T - 0.02, E0, z0, z1)
    # under a sloped head the trim's sloped underside would lie in the wall opening's own sloped face: drop it 1/32 in
    wbox("Trim", wall, u0 - tw, u1 + tw, VF - BAT_T - 0.02, E0, z1 - (0.0026 if z1b != z1 else 0), z1 + tw)
    if not door:
        wbox("Trim", wall, u0 - tw, u1 + tw, VF - BAT_T - 0.04, E0, z0 - tw, z0)
    jd0, jd1 = v0 + fd, T                                   # white oak jamb liner, stool, casing, apron
    wbox(inner, wall, u0, u0 + 0.06, jd0, jd1, z0, z1 - 0.06)
    wbox(inner, wall, u1 - 0.06, u1, jd0, jd1, z0, z1 - 0.06)
    wbox(inner, wall, u0, u1, jd0, jd1, z1 - 0.06, z1)
    cw = 3.5 / 12
    if not door:                                            # stool: horns 1" past the casing, nose 2 1/2" proud of the drywall
        horn, nose = cw + 1 / 12, 2.5 / 12
        wbox(inner, wall, u0 - horn, u1 + horn, jd0, jd1 + nose, z0 - 0.07, z0)
    wbox(inner, wall, u0 - cw, u0, jd1, jd1 + 0.06, z0, z1)
    wbox(inner, wall, u1, u1 + cw, jd1, jd1 + 0.06, z0, z1)
    wbox(inner, wall, u0 - cw, u1 + cw, jd1, jd1 + 0.06, z1, z1 + cw)
    if not door:
        wbox(inner, wall, u0 - cw, u1 + cw, jd1, jd1 + 0.05, z0 - 0.32, z0 - 0.07)
    if door and z0 < 0.2 and FU.get("enabled"):
        wbox("Aluminum", wall, u0, u1, -0.12, T + 0.02, 0.0, 0.06)    # threshold


# ------------------------------------------------------------------ exterior walls, siding, battens
def ew_top_segs():
    return [[0, H_N, YC2, north_roof_z(YC2)], [YC2, H_CL, HD, H_S]]


def battens(mat, frame, u_lo, u_hi, z_bot, top, holes, v_face=0.0):
    """vertical battens on a wall face; top(u) gives the wall top, holes = [(u0, u1, z0, z1)] to skip"""
    u = u_lo + BAT_SP / 2
    while u + BAT_W / 2 < u_hi - 0.25:
        ua, ub = u - BAT_W / 2, u + BAT_W / 2
        segs = [(z_bot, min(top(ua), top(ub)))]
        for hh in holes:
            h0, h1, hz0, hz1 = hh[:4]
            if len(hh) > 4:                                  # sloped head: its height at this batten
                hz1 = hz1 + (hh[4] - hz1) * (max(ua, h0) - h0) / (h1 - h0)
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
            ring = []
            for (uu, vv) in ((ua, v_face - BAT_T), (ub, v_face - BAT_T), (ub, v_face), (ua, v_face)):
                ring.append(frame(uu, vv) + (uu,))
            pts = [(x, y, a) for (x, y, _) in ring] + [(x, y, ta if uu == ua else tb) for (x, y, uu) in ring]
            hexa(mat, pts)
        u += BAT_SP


def holes_for(wall, extra=()):
    hs = []
    for o in OPEN + list(extra):
        if o["wall"] != wall:
            continue
        hs.append((o["start"] - TRIM_W, o["end"] + TRIM_W, -1 if is_door(o) else o["sill"] - TRIM_W, o["head"] + TRIM_W)
                  + ((o["head_end"] + TRIM_W,) if "head_end" in o else ()))
    return hs


def ew_top(y):
    return north_roof_z(y) if y < YC2 else H_CL + (y - YC2) * (H_S - H_CL) / (HD - YC2)


SIP = dict(model='6 1/2" structural insulated panel (Insulspan, A-12 S.I.P. notes)',
           specs=[["Build up", 'Outside to inside: LP SmartSide, TamlynWrap rain screen, 7/16" OSB, 5 5/8" EPS foam, 7/16" OSB, 1/2" gypsum (A-41, A-12)'],
                  ["R-value", "R-24 (A-41)"],
                  ["Siding", f"LP SmartSide board and batten, {MM['siding_color']} (Garden Sage)"],
                  ["Battens", f"{MM['batten_width_in']:g}\" wide, {MM['batten_spacing_in']:g}\" on centre (spacing ASSUMED)"], ["Trim", f"LP Abyss Black {MM['trim_color']}"],
                  ["Inside", f"Drywall, {MM['wall_paint']}"]],
           notes=["Layers from the S.I.P. notes on A-12 and wall type 1 on A-41. Siding and rain screen thicknesses are typical values, ASSUMED.",
                  "The inside face sits where the A-11 plan puts it, so the panel's outside face is 1/2\" past the slab edge. ASSUMED until the Insulspan shop drawings."])


def sip_layers(frame, zbot, top, holes, top_in=None, u_ext=(0, 0)):
    """siding, OSB, EPS foam, OSB and gypsum for one exterior wall; top_in is the gypsum's top (it can stop at the roof's underside)"""
    ext = [[s_[0] + (u_ext[0] if k == 0 else 0), s_[1], s_[2] + (u_ext[1] if k == len(top) - 1 else 0), s_[3]] for k, s_ in enumerate(top)]
    panel("Siding", frame, VF, E0, zbot, ext, holes)
    panel("OSB", frame, E0, E0 + OSB, zbot, top, holes)
    panel("EPS Foam", frame, E0 + OSB, E0 + SIP_T - OSB, zbot, top, holes)
    panel("OSB", frame, E0 + SIP_T - OSB, E0 + SIP_T, zbot, top, holes)
    panel("Drywall", frame, T - GYP, T, zbot, top_in or top, holes)


def ext_top(segs, u0, u1, zf):
    """stretch the first and last top segment out to u0 and u1 (siding past the corners), heights from zf"""
    out = [list(s_) for s_ in segs]
    out[0][0], out[0][1] = u0, zf(u0)
    out[-1][2], out[-1][3] = u1, zf(u1)
    return out


for wall, nm, length, top in (("N", "North exterior wall", HW, [[0, H_N, HW, H_N]]), ("S", "South exterior wall", HW, [[0, H_S, HW, H_S]]),
                              ("W", "West exterior wall", HD, ew_top_segs()), ("E", "East exterior wall", HD, ew_top_segs())):
    inf = json.loads(json.dumps(SIP))
    inf["specs"] = [["Length", ftin(length)], ["Height", f"{ftin(H_N)} north, {ftin(H_S)} south (A-30)" if wall in "EW" else ftin(H_N if wall == "N" else H_S) + " panel (A-30)"]] + inf["specs"]
    rec(f"wall.ext.{wall}", "wall", nm, "shell", info=inf)
    holes = cuts_for(wall)
    if wall in "NS":            # the north and south walls run past the corners to close them, the siding on out to its own face
        zc = H_N if wall == "N" else H_S
        sip_layers(FRAMES[wall], 0, [[E0, zc, HW - E0, zc]], holes, top_in=[[0, north_roof_z(T), HW, north_roof_z(T)]] if wall == "N" else [[0, south_roof_z(HD - T), HW, south_roof_z(HD - T)]], u_ext=(VF - E0, E0 - VF))
    else:
        sip_layers(FRAMES[wall], 0, top, holes, u_ext=(VF, -VF))
    if MM["siding_style"] == "board_and_batten":
        topf = (lambda u: H_N) if wall == "N" else (lambda u: H_S) if wall == "S" else ew_top
        battens("Siding", wall_frame(wall), 0, length, 0, topf, holes_for(wall), v_face=VF)
    if MM["siding_style"] == "board_and_batten":            # corner boards at this wall's two corners (N and S walls carry them)
        for (x, y, sx, sy) in ((0, 0, 1, 1), (HW, 0, -1, 1), (HW, HD, -1, -1), (0, HD, 1, -1)):
            if (wall == "N" and y == 0) or (wall == "S" and y == HD):
                zt = H_N if y == 0 else H_S
                box("Trim", x + sx * (VF - BAT_T), x + sx * TRIM_W, y + sy * (VF - BAT_T), y + sy * VF, 0, zt)
                box("Trim", x + sx * (VF - BAT_T), x + sx * VF, y + sy * (VF - BAT_T), y + sy * TRIM_W, 0, zt)

inf = json.loads(json.dumps(SIP))
inf["specs"] = [["Location", f"{ftin(YC)} from the north wall (A-11 and A-12)"], ["Clerestory", f"{CL['count']} W30-30 awnings, sill {ftin(CL['sill'])}"],
                ["Openings below", f"{len(CL['passages'])}: pantry, hall, living (barn door), entry, coat closet"],
                ["Below the low roof", "2x6 stud bearing wall with gypsum both sides (A-41). SIP above it."]] + inf["specs"]
rec("wall.ext.C", "wall", "Clerestory bearing wall", "shell", info=inf)
ZCT = north_roof_z(YC2)
CH = [h for h in cuts_for("C") if h[3] > H_CL]
# above the low roof: a SIP, its siding running out past both ends to cover the east and west walls' end grain
panel("Siding", FRAMES["C"], VF, E0, H_CL, [[VF, ZCT, HW - VF, ZCT]], CH)
panel("OSB", FRAMES["C"], E0, E0 + OSB, H_CL, [[T, ZCT, HW - T, ZCT]], CH)
panel("EPS Foam", FRAMES["C"], E0 + OSB, E0 + SIP_T - OSB, H_CL, [[T, ZCT, HW - T, ZCT]], CH)
panel("OSB", FRAMES["C"], E0 + SIP_T - OSB, T - GYP, H_CL, [[T, ZCT, HW - T, ZCT]], CH)
# below it: the stud wall between the north rooms and the kitchen side, finished both faces
panel("Drywall", FRAMES["C"], 0, T - GYP, 0, [[T, H_CL, HW - T, H_CL]], [h for h in cuts_for("C") if h[2] < H_CL])
panel("Drywall", FRAMES["C"], T - GYP, T, 0, [[T, north_roof_z(YC2 - T), HW - T, north_roof_z(YC2 - T)]], cuts_for("C"))
if MM["siding_style"] == "board_and_batten":
    battens("Siding", wall_frame("C"), T, HW - T, H_CL, lambda u: ZCT, holes_for("C", CLER), v_face=VF)
    for (x, sx) in ((0, 1), (HW, -1)):                       # black corner boards at both ends, like the other corners
        box("Trim", x + sx * (VF - BAT_T), x + sx * TRIM_W, YC2 - VF, YC2 - VF + BAT_T, H_CL, ZCT)
        box("Trim", x + sx * (VF - BAT_T), x + sx * VF, YC2 - TRIM_W, YC2 - VF + BAT_T, H_CL, ZCT)

for o in OPEN:
    window_unit(o)
for o in CLER:
    window_unit(o)

# ------------------------------------------------------------------ interior walls (A-11 vectors)
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
            if pt_in_poly((xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2, poly):
                cells[(i, j)] = True
    rects, used = [], set()
    for (i, j) in sorted(cells):
        if (i, j) in used:
            continue
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
    return rects


def in_flat(x, y):
    for (a0, b0, a1, b1) in C["ceilings"]["flat_rooms"]:
        if a0 - 0.02 <= x <= a1 + 0.02 and b0 - 0.02 <= y <= b1 + 0.02:
            return True
    return False


def wall_between_flats(x0, x1, y0, y1, alongx=None):
    """alongx: the direction the wall runs. Defaults to the long side of the rectangle, but a short gap or junction
    block in a wall line is wider than it is long, so callers that know the wall's direction pass it."""
    def flat_or_out(x, y):
        return in_flat(x, y) or not (T < x < HW - T and T < y < HD - T)
    if alongx is None:
        alongx = (x1 - x0) >= (y1 - y0)
    for k in range(5):
        t = (k + 0.5) / 5
        if alongx:
            x = x0 + (x1 - x0) * t
            if not (flat_or_out(x, y0 - 0.6) and flat_or_out(x, y1 + 0.6)):
                return False
        else:
            y = y0 + (y1 - y0) * t
            if not (flat_or_out(x0 - 0.6, y) and flat_or_out(x1 + 0.6, y)):
                return False
    return True


def wall_top(x0, x1, y0, y1, alongx=None):
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    in_loft = LOFT["enabled"] and LX0 - 0.05 <= cx <= LX1 + 0.05 and LY0 + 0.3 <= cy <= LY1 + 0.6
    if in_loft:
        if abs(cx - (LX0 + 0.23)) < 0.4:                    # loft edge wall (bath 1 west wall): stops level with the loft floor
            return lambda x, y: LOFT["floor_height"] + LOFT["pony_wall_height"] - (LOFT_FIN if not LOFT["pony_wall_height"] else 0)
        return lambda x, y: LOFT["floor_height"] - FLOOR_T
    if C["ceilings"].get("walls_stop_at_attic") and wall_between_flats(x0, x1, y0, y1, alongx):
        return lambda x, y: FH + FLOOR_T - DECK_T               # stops under the attic deck
    return lambda x, y: roof_under(min(y, YC2))


INT_RECTS = []
for poly in G["interior_walls_from_plan_A11"]:
    for r_ in rect_decompose(poly):
        if r_[2] > YC - 0.15 and r_[3] < YC2 + 0.15:          # the clerestory wall is its own record
            continue
        INT_RECTS.append(r_)
for ed in C.get("plan_edits", {}).get("wall_shift", []):      # partitions moved off A-11 by a decision, [[plan_edits]] in config.toml
    px, py = ed["at"]
    for i_, (x0, x1, y0, y1) in enumerate(INT_RECTS):
        if x0 - 0.01 <= px <= x1 + 0.01 and y0 - 0.01 <= py <= y1 + 0.01:
            INT_RECTS[i_] = (x0 + ed.get("dx", 0), x1 + ed.get("dx", 0), y0 + ed.get("dy", 0), y1 + ed.get("dy", 0))
            break
    else:
        raise SystemExit(f"plan_edits.wall_shift: no interior wall at {ed['at']}")
for ed in C.get("plan_edits", {}).get("wall_ends", []):       # a wall end moved to where it is framed (a measured door edge)
    px, py = ed["at"]
    for i_, (x0, x1, y0, y1) in enumerate(INT_RECTS):
        if x0 - 0.01 <= px <= x1 + 0.01 and y0 - 0.01 <= py <= y1 + 0.01:
            INT_RECTS[i_] = (ed.get("x0", x0), ed.get("x1", x1), ed.get("y0", y0), ed.get("y1", y1))
            break
    else:
        raise SystemExit(f"plan_edits.wall_ends: no interior wall at {ed['at']}")
for ed in C.get("plan_edits", {}).get("wall_remove", []):     # partitions taken out by a decision (a built-in panel stands in)
    px, py = ed["at"]
    hit = [r_ for r_ in INT_RECTS if r_[0] - 0.01 <= px <= r_[1] + 0.01 and r_[2] - 0.01 <= py <= r_[3] + 0.01]
    if not hit:
        raise SystemExit(f"plan_edits.wall_remove: no interior wall at {ed['at']}")
    INT_RECTS.remove(hit[0])

# Real drywall on the partitions (Maxwell 11/21/2026: studs showed through the bedroom walls). A-11 draws most bedroom
# and hall partitions 3 1/2 in thick, the bare 2x4, so the drywall box was the stud's own thickness and the studs sat
# 1/16 in behind its faces, close enough to bleed through on screen. Those walls are now a 2x4 plus a sheet of drywall
# each side ([framing] drywall_in, 5/8 in), grown evenly about the A-11 centre line, so each face moves 5/8 in into the
# room. Where a wall end meets another wall it also runs 5/8 in into it, so the corners close up. The 5 1/2 in walls
# already have room for a 2x4 and 5/8 in drywall each side and stay as drawn.
DW = C.get("framing", {}).get("drywall_in", 0.625) / 12
_SD = C.get("framing", {}).get("stud_d_in", 3.5) / 12


def _grow_thin(rects):
    def thin(r_):
        return 3.3 / 12 < min(r_[1] - r_[0], r_[3] - r_[2]) < 3.7 / 12 and max(r_[1] - r_[0], r_[3] - r_[2]) >= 0.5

    def meets_thin(x0, x1, y0, y1, me):
        """does this probe just past a wall end touch a wall that grows? (touching counts: a crossing wall can end flush
        with that wall's far face, and then the end has to follow the face out or it leaves a slit at the corner)"""
        k = 0.005
        return any(o is not me and thin(o) and o[0] < x1 + k and o[1] > x0 - k and o[2] < y1 + k and o[3] > y0 - k for o in rects)

    out, e = [], 0.03
    for r_ in rects:
        x0, x1, y0, y1 = r_
        g = (_SD + 2 * DW - min(x1 - x0, y1 - y0)) / 2 if thin(r_) else 0.0
        if (x1 - x0) >= (y1 - y0):
            out.append((x0 - (DW if meets_thin(x0 - e, x0, y0, y1, r_) else 0), x1 + (DW if meets_thin(x1, x1 + e, y0, y1, r_) else 0), y0 - g, y1 + g))
        else:
            out.append((x0 - g, x1 + g, y0 - (DW if meets_thin(x0, x1, y0 - e, y0, r_) else 0), y1 + (DW if meets_thin(x0, x1, y1, y1 + e, r_) else 0)))
    return out


INT_RECTS_A11 = list(INT_RECTS)                               # as A-11 draws them (tools/drywall_check.py)
INT_RECTS = _grow_thin(INT_RECTS)
DOORS = G.get("door_labels_A11", [])


def nearest_label(x, y):
    best, bd = None, 99
    for dx, dy, lab in DOORS:
        d = math.hypot(dx - x, dy - y)
        if d < bd:
            bd, best = d, lab
    return best if bd < 3.5 else None


def door_head_near(x, y):
    for hx, hy, hh in C.get("framing", {}).get("door_heads", []):     # heads set to clear the as-built headers
        if math.hypot(hx - x, hy - y) < 1.5:
            return hh
    lab = nearest_label(x, y)
    return 8.0 if lab is None else (8.0 if lab.endswith("80") else 6.67)


def between(x0, x1, y0, y1):
    """names of the rooms on either side of a wall rectangle"""
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if (x1 - x0) >= (y1 - y0):
        a, b = room_at(cx, y0 - 0.8), room_at(cx, y1 + 0.8)
    else:
        a, b = room_at(x0 - 0.8, cy), room_at(x1 + 0.8, cy)
    names = [n for n in (a, b) if n]
    if len(names) == 2 and names[0] != names[1]:
        return f"between {names[0]} and {names[1]}"
    return f"in {names[0]}" if names else ""


def split_by_attic(x0, x1, y0, y1):
    """A wall that runs past the edge of a flat ceiling room only stops at the attic deck where both sides are flat.
    Split it at the flat room edges so the part between two flat rooms stops at the deck and the rest runs up to the roof."""
    top = wall_top(x0, x1, y0, y1)
    if not C["ceilings"].get("walls_stop_at_attic"):
        return [((x0, x1, y0, y1), top)]
    alongx = (x1 - x0) >= (y1 - y0)
    a, b = (x0, x1) if alongx else (y0, y1)
    cuts = sorted({e for r_ in C["ceilings"]["flat_rooms"] for e in ((r_[0], r_[2]) if alongx else (r_[1], r_[3])) if a + 0.3 < e < b - 0.3})
    if not cuts:
        return [((x0, x1, y0, y1), top)]
    deck = lambda x, y: FH + FLOOR_T - DECK_T
    pieces, edges = [], [a] + cuts + [b]
    for u0, u1 in zip(edges[:-1], edges[1:]):
        r_ = (u0, u1, y0, y1) if alongx else (x0, x1, u0, u1)
        low = wall_between_flats(*r_) and wall_top(*r_)((r_[0] + r_[1]) / 2, (r_[2] + r_[3]) / 2) <= FH + FLOOR_T
        if pieces and pieces[-1][1] == low:                      # merge neighbours of the same kind
            q = pieces[-1][0]
            pieces[-1] = ((q[0], r_[1], q[2], r_[3]), low)
        else:
            pieces.append((r_, low))
    # a piece that is not between two flat rooms runs up to the roof even when the wall as a whole stops at the deck
    # (the bed 3 / utility wall's east end, where it meets the vaulted hall 1, left a gap above the deck)
    return [(r_, deck if low else wall_top(*r_, alongx=alongx)) for (r_, low) in pieces]


WALL_PIECES = [pc for r_ in INT_RECTS for pc in split_by_attic(*r_)]

# Attic access from the loft: a walk through opening in the loft's north wall onto the attic deck (both sit at the same
# height). A-11's gap in that wall line (the bath 1 / closet 1 opening, x 34.37-37.33) used to run straight up and was the
# way in; it is now walled above the loft floor, and the opening sits with its east edge [loft] attic_access.east_gap off
# the inside face of the east wall (Maxwell, 11/19/2026). The extra pieces go on the end so other wall ids keep their numbers.
ATTIC_ACCESS, LOFT_GAP_FILLS = None, []
if LOFT["enabled"] and LOFT.get("attic_access"):
    _aa = LOFT["attic_access"]
    ax1 = HW - T - _aa["east_gap"]
    ax0 = ax1 - _aa["width"]
    _line = sorted((i for i, ((x0, x1, y0, y1), _) in enumerate(WALL_PIECES)
                    if abs(y1 - LY0) < 0.05 and y1 - y0 < 0.7 and x1 > LX0 + 0.3 and x0 < LX1 - 0.3), key=lambda i: WALL_PIECES[i][0][0])
    for a_, b_ in zip(_line[:-1], _line[1:]):
        g0, g1 = WALL_PIECES[a_][0][1], WALL_PIECES[b_][0][0]
        if g1 - g0 > 0.3:
            LOFT_GAP_FILLS.append((g0, g1, WALL_PIECES[a_][0][2], WALL_PIECES[a_][0][3]))
    for i_ in _line:
        (x0, x1, y0, y1), top = WALL_PIECES[i_]
        if x0 + 0.2 < ax0 and ax1 < x1 - 0.2:
            WALL_PIECES[i_] = ((x0, ax0, y0, y1), top)
            WALL_PIECES.append(((ax1, x1, y0, y1), top))
            ATTIC_ACCESS = (ax0, ax1, y0, y1)
            break
    else:
        raise SystemExit(f"loft attic_access: no solid wall north of the loft spans x {ax0:.2f}-{ax1:.2f}")

# Seams: two drywall boxes that only butt end to end leave a hairline crack on screen where their faces meet (the GPU
# rounds the shared edge a little differently for each), and the dark inside of the wall shows through it, over doors
# most of all (Maxwell 11/21/2026). So each piece runs JOIN past its end into the piece it meets, where that piece is at
# least as tall there, so the overlap stays hidden inside it. Same material, so the overlap never flickers.
JOIN = 0.125 / 12


def piece_top_at(x, y):
    tops = [top(x, y) for (r_, top) in WALL_PIECES if r_[0] - 1e-4 <= x <= r_[1] + 1e-4 and r_[2] - 1e-4 <= y <= r_[3] + 1e-4]
    return max(tops) if tops else None


def sealed(x0, x1, y0, y1, top):
    """the box grown JOIN along its length at each end that runs into a wall piece at least as tall"""
    alongx = (x1 - x0) >= (y1 - y0)
    vm = (y0 + y1) / 2 if alongx else (x0 + x1) / 2
    a, b = (x0, x1) if alongx else (y0, y1)
    def ok(u, u_in):
        p_, q_ = ((u, vm), (u_in, vm)) if alongx else ((vm, u), (vm, u_in))
        t = piece_top_at(*p_)
        return t is not None and t >= top(*q_) - 1e-3
    ja, jb = ok(a - JOIN / 2, a), ok(b + JOIN / 2, b)
    a2, b2 = a - JOIN * ja, b + JOIN * jb
    ends = tuple(f for f, j in zip(((5, 3) if alongx else (2, 4)), (ja, jb)) if j)
    return dict(zip("abcd", (a2, b2, y0, y1) if alongx else (x0, x1, a2, b2)), ends=ends)


def sealed_box(rect, top, z0):
    """a drywall wall box run into the pieces it meets (see JOIN), its buried ends left open"""
    s_ = sealed(*rect, top)
    box("Drywall", s_["a"], s_["b"], s_["c"], s_["d"], z0, 9, ztop=top, open_ends=s_["ends"])


DOOR_GAPS, FIXES = [], []


def attic_gap(x0, x1, y0, y1, crossed, alongx):
    """A short gap between two wall ends. With nothing crossing it, fill it full height. Where a wall that stops at the
    attic deck crosses it, the gap only shows above the deck, so fill from the deck up (the hall 1 west wall had these).
    alongx is the direction of the wall with the gap: the gap itself is often wider than it is long."""
    top = wall_top(x0, x1, y0, y1, alongx)
    if not crossed:
        FIXES.append(("sliver", x0, x1, y0, y1, top, 0))
    elif top((x0 + x1) / 2, (y0 + y1) / 2) > FH + FLOOR_T + 0.2:
        FIXES.append(("sliver", x0, x1, y0, y1, top, FH + FLOOR_T - DECK_T))


NO_GAP = C.get("plan_edits", {}).get("no_gap", [])    # wall gaps not to read as doors: [x, y] near the gap centre


def make_headers():
    rects = INT_RECTS
    for i, a in enumerate(rects):
        for j, b in enumerate(rects):
            if i >= j:
                continue
            for horiz in (True, False):
                if horiz:
                    if abs(a[2] - b[2]) > 0.08 or abs(a[3] - b[3]) > 0.08 or (a[3] - a[2]) > 0.7:
                        continue
                    lo, hi = (a, b) if a[1] <= b[0] else (b, a)
                    gap0, gap1 = lo[1], hi[0]
                    if 0.02 < gap1 - gap0 <= 1.4:
                        crossed = any(r is not a and r is not b and r[0] < gap1 - 0.01 and r[1] > gap0 + 0.01 and r[2] < a[3] and r[3] > a[2] for r in rects)
                        attic_gap(gap0, gap1, min(a[2], b[2]), max(a[3], b[3]), crossed, True)
                        if not crossed:
                            continue
                    if not (1.4 < gap1 - gap0 < 7.0):
                        continue
                    if any(r is not a and r is not b and r[0] < gap1 - 0.01 and r[1] > gap0 + 0.01 and r[2] < a[3] and r[3] > a[2] for r in rects):
                        continue
                    cx, cy = (gap0 + gap1) / 2, (a[2] + a[3]) / 2
                    if any(math.hypot(cx - p_[0], cy - p_[1]) < 1.5 for p_ in NO_GAP):
                        continue                    # a door that [furnishings] door_add already hangs (it brings its own header)
                    h = door_head_near(cx, cy)
                    top = wall_top(gap0, gap1, a[2], a[3])
                    DOOR_GAPS.append(("x", gap0, gap1, a[2], a[3], h))
                    if top(cx, cy) - h > 0.2:
                        FIXES.append(("header", gap0, gap1, a[2], a[3], top, h))
                else:
                    if abs(a[0] - b[0]) > 0.08 or abs(a[1] - b[1]) > 0.08 or (a[1] - a[0]) > 0.7:
                        continue
                    lo, hi = (a, b) if a[3] <= b[2] else (b, a)
                    gap0, gap1 = lo[3], hi[2]
                    if 0.02 < gap1 - gap0 <= 1.4:
                        crossed = any(r is not a and r is not b and r[2] < gap1 - 0.01 and r[3] > gap0 + 0.01 and r[0] < a[1] and r[1] > a[0] for r in rects)
                        attic_gap(min(a[0], b[0]), max(a[1], b[1]), gap0, gap1, crossed, False)
                        if not crossed:
                            continue
                    if not (1.4 < gap1 - gap0 < 7.0):
                        continue
                    if any(r is not a and r is not b and r[2] < gap1 - 0.01 and r[3] > gap0 + 0.01 and r[0] < a[1] and r[1] > a[0] for r in rects):
                        continue
                    cx, cy = (a[0] + a[1]) / 2, (gap0 + gap1) / 2
                    if any(math.hypot(cx - p_[0], cy - p_[1]) < 1.5 for p_ in NO_GAP):
                        continue
                    h = door_head_near(cx, cy)
                    top = wall_top(a[0], a[1], gap0, gap1)
                    DOOR_GAPS.append(("y", gap0, gap1, a[0], a[1], h))
                    if top(cx, cy) - h > 0.2:
                        FIXES.append(("header", a[0], a[1], gap0, gap1, top, h))


make_headers()

for k, ((x0, x1, y0, y1), top) in enumerate(WALL_PIECES):
    ln, th = max(x1 - x0, y1 - y0), min(x1 - x0, y1 - y0)
    zt = top((x0 + x1) / 2, (y0 + y1) / 2)
    rec(f"wall.int.{k}", "wall", f"Interior wall {between(x0, x1, y0, y1)}".strip(), "interior",
        info=dict(model=f"{ftin(th)} interior partition", specs=[["Length", ftin(ln)], ["Height", ftin(zt) if abs(top(x0, y0) - top(x1, y1)) < 0.05 else "Up to the roof"],
                                                                ["Finish", f"Drywall, {MM['wall_paint']}"]],
                  notes=["Traced from the A-11 floor plan vectors."]))
    s_ = sealed(x0, x1, y0, y1, top)
    # an end at a doorway with wall over it: the face above the door head would meet the header piece edge on and draw
    # a hairline up the wall, so leave the end open and close only the part down in the doorway (behind the jamb)
    alongx = (x1 - x0) >= (y1 - y0)
    ends, caps = list(s_["ends"]), []
    for f_ in FIXES:
        if f_[0] != "header":
            continue
        _, hx0, hx1, hy0, hy1, _t, h = f_
        for fi, u in (((5, x0), (3, x1)) if alongx else ((2, y0), (4, y1))):
            if fi in ends:
                continue
            hu0, hu1, hv0, hv1 = (hx0, hx1, hy0, hy1) if alongx else (hy0, hy1, hx0, hx1)
            v0_, v1_ = (y0, y1) if alongx else (x0, x1)
            if (abs(hu0 - u) < 0.01 or abs(hu1 - u) < 0.01) and hv0 < v1_ - 0.01 and hv1 > v0_ + 0.01:
                ends.append(fi)
                # a door's jamb covers the end below the head; an opening left without a door (door_remove) shows it, so close it there
                gcx, gcy = (hx0 + hx1) / 2, (hy0 + hy1) / 2
                if not any(math.hypot(rx - gcx, ry - gcy) < 1.5 for (rx, ry) in C.get("furnishings", {}).get("door_remove", [])):
                    continue
                caps.append([(u, v0_, 0), (u, v1_, 0), (u, v1_, h), (u, v0_, h)] if alongx else [(v0_, u, 0), (v1_, u, 0), (v1_, u, h), (v0_, u, h)])
    box("Drywall", s_["a"], s_["b"], s_["c"], s_["d"], 0, 9, ztop=top, open_ends=tuple(ends))
    for c_ in caps:
        quad("Drywall", c_)

nh = 0
for f_ in FIXES:
    if f_[0] == "sliver":
        _, x0, x1, y0, y1, top, z0 = f_
        rec(f"wall.fill.{nh}", "wall", f"Interior wall {between(x0, x1, y0, y1)}".strip(), "interior",
            info=dict(model="Short wall piece", notes=["Fills a gap of under 1' 5\" between two traced wall ends" + (", above the attic deck." if z0 else ".")]))
        sealed_box((x0, x1, y0, y1), top, z0)
    else:
        _, x0, x1, y0, y1, top, h = f_
        rec(f"wall.header.{nh}", "wall", "Wall over a doorway", "interior",
            info=dict(model="Drywall over the door head", specs=[["Door head", ftin(h)]]))
        sealed_box((x0, x1, y0, y1), top, h)
    nh += 1

for k, (x0, x1, y0, y1) in enumerate(LOFT_GAP_FILLS):
    rec(f"wall.loft_fill.{k}", "wall", "Loft north wall over the closet 1 opening", "interior",
        info=dict(model="Drywall from the ceiling up to the roof", specs=[["Width", ftin(x1 - x0)]],
                  notes=["A-11 leaves this part of the wall open from the slab to the roof. Below the ceiling it is the opening between bath 1 and closet 1, "
                         "which stays. Above it, it was the way into the attic from the loft until the attic access moved east (Maxwell, 11/19/2026)."]))
    sealed_box((x0, x1, y0, y1), wall_top(x0, x1, y0, y1, True), FH)
if ATTIC_ACCESS:
    x0, x1, y0, y1 = ATTIC_ACCESS
    FL_ = LOFT["floor_height"]
    rec("loft.attic_access", "wall", "Attic access from the loft", "interior", room="Loft",
        info=dict(model=f"{ftin(x1 - x0)} wide walk through opening, loft floor level, onto the attic deck",
                  specs=[["Where", f"North wall of the loft, east edge {ftin(HW - T - x1)} off the inside face of the east wall"],
                         ["Opening", f"x {ftin(x0)} to {ftin(x1)} from the west wall"],
                         ["Clear height", f"{ftin(_aa['door']['top_in'] / 12 + 0.0725)} to the head of the short attic door" if _aa.get("door") else f"{ftin(roof_under(y0) - FL_)} on the attic side, up to the roof"],
                         ["Sill", "Flush: the loft floor and the attic deck are both at " + ftin(FL_)]],
                  notes=["Moved from the A-11 gap at x 34' 4 1/2\" to 37' 4\" (Maxwell, 11/19/2026). Width kept from that gap.",
                         "The plans ask for a gasketed attic access panel (general notes)." + (" A short door hangs in it (see its card)." if _aa.get("door") else "")]))
    box("Drywall", x0, x1, y0, y1, 0, 9, ztop=lambda x, y: FL_ - LOFT_FIN)
    box("White Oak", x0, x1, y0, y1, FL_ - LOFT_FIN, FL_)               # threshold, flush with the loft floor and the deck
    _ad = _aa.get("door")
    if _ad:
        # Short door into the attic (Maxwell 11/21/2026): it cannot swing out into the loft (the loveseat and the bookcase sit
        # either side) and a full height leaf swinging into the attic would hit the roof, which drops toward the north. So the
        # leaf is short enough to swing a full 90 degrees north under the roof. Hinged on the east jamb, so it parks along the
        # east side and leaves the walkway to the west clear. Leaf in the attic side of the jambs, casing on the loft side.
        J, G_, LT = 0.0625, 0.01, 1.375 / 12                      # 3/4 in jambs, 1/8 in gaps, 1 3/8 in leaf
        top = _ad["top_in"] / 12                                  # top of the leaf above the loft floor
        head = top + G_ + J                                       # underside of the head jamb is top + gap
        lx0, lx1 = x0 + J + G_, x1 - J - G_
        lw = lx1 - lx0
        hx, hy = x1 - J, y0 + 0.01                                 # hinge on the east jamb, attic face
        reach = hy - lw                                           # where the free edge ends up, open 90 degrees
        clear = roof_under(reach) - FL_ - top
        if clear < 1.0 / 12:
            raise SystemExit(f"attic door: a {_ad['top_in']} in leaf hits the roof when open ({clear * 12:.1f} in clear)")
        door_max = (roof_under(reach) - FL_) * 12
        box("Drywall", x0, x1, y0, y1, FL_ + head, 9, ztop=wall_top(x0, x1, y0, y1, True))    # wall over the short door
        r_ = rec("door.attic", "door", "Attic door from the loft", "interior", room="Loft",
                 info=dict(model=f"Short white oak slab door, {ftin(lw)} x {ftin(top)}, swings into the attic",
                           specs=[["Leaf", f"{ftin(lw)} wide, {ftin(top)} high, 1 3/8 in solid core"], ["Opening", f"{ftin(x1 - x0)} wide, {ftin(head)} to the head jamb"],
                                  ["Swing", "Into the attic, hinged on the east jamb, stops at 90 degrees"],
                                  ["Roof clearance", f"{clear * 12:.1f} in over the leaf when it is open all the way (its free edge is {ftin(hy - reach)} into the attic, where the roof is {ftin(roof_under(reach) - FL_)} above the deck)"],
                                  ["Tallest that swings", f"About {door_max:.0f} in, with nothing to spare"],
                                  ["Seal", "Weatherstrip on the stops and a door sweep (the plans ask for a gasketed attic access)"]],
                           notes=["Maxwell 11/21/2026: it cannot swing out into the loft furniture, and a full height door swinging into the attic would hit the roof, so it is short.",
                                  "Hinged on the east so the open leaf parks against the east side and the walkway west to the heat pump stays clear. A wall stop or a hinge stop keeps it from going past 90 degrees.",
                                  f"Duck through: the head is {ftin(head)} above the loft floor. The attic just inside is about {ftin(roof_under(y0) - FL_)} high at this wall and drops to the north.",
                                  "Size and hardware ASSUMED."]))
        oak = "White Oak"
        box(oak, x0, x0 + J, y0, y1, FL_, FL_ + head); box(oak, x1 - J, x1, y0, y1, FL_, FL_ + head)
        box(oak, x0, x1, y0, y1, FL_ + head - J, FL_ + head)
        box(oak, x0 + J, x0 + J + 0.04, y0 + 0.01 + LT + 0.005, y1, FL_, FL_ + head - J)      # stops on the loft side of the leaf
        box(oak, x1 - J - 0.04, x1 - J, y0 + 0.01 + LT + 0.005, y1, FL_, FL_ + head - J)
        box(oak, x0 + J, x1 - J, y0 + 0.01 + LT + 0.005, y1, FL_ + head - J - 0.04, FL_ + head - J)
        cw = FU.get("casing_width_in", 3.5) / 12
        for (cx0, cx1) in ((x0 - cw, x0 + 0.02), (x1 - 0.02, x1 + cw)):
            box(oak, cx0, cx1, y1, y1 + 0.06, FL_, FL_ + head)
        box(oak, x0 - cw, x1 + cw, y1, y1 + 0.06, FL_ + head, FL_ + head + cw)
        lf = op(r_, "door.attic.leaf", "Attic door from the loft", "swing", (hx, hy, 0), angle=-90)
        with into(lf["parts"]):
            box(oak, lx0, lx1, y0 + 0.01, y0 + 0.01 + LT, FL_ + 0.04, FL_ + top)
            lx = lx0 + 0.25                                       # lever on the free (west) edge, 36 in up
            for (b0, b1, b2) in ((y0 + 0.01, y0 - 0.05, y0 - 0.1), (y0 + 0.01 + LT, y0 + 0.07 + LT, y0 + 0.12 + LT)):
                box("Brushed Nickel", lx - 0.06, lx + 0.06, min(b0, b1), max(b0, b1), FL_ + 2.95, FL_ + 3.12)
                box("Brushed Nickel", lx, lx + 0.32, min(b1, b2), max(b1, b2), FL_ + 3.0, FL_ + 3.06)

# ------------------------------------------------------------------ as-built framing (Framing layer, Maxwell 11/20/2026)
# What the build photos show standing: interior walls framed to the top plates (studs, plates, kings, jacks, headers),
# walls that are still only a bottom plate on the slab, and the stick framed bearing wall on the clerestory line.
# Hidden inside the walls until the Drywall walls layer is off. [framing] in config.toml says which walls are up and what
# each header is; anything not in a photo is typical framing, ASSUMED. FRAMING_META goes to house.json for tools/header_clash.py.
FR = C.get("framing", {})
FRAMING_META = dict(headers=[], kings=[], junctions=[], walls=[])
if FR.get("enabled", True):
    IN = 1 / 12
    SW = FR.get("stud_w_in", 1.5) * IN
    OC = FR.get("stud_oc_in", 16) * IN
    NTOP = FR.get("top_plates", 2)
    PLATE_TOP = FR.get("plate_height_in", 109) * IN         # top of the double top plate, as built
    FACE_IN = FR.get("face_inset_in", 0.0625) * IN          # ends of plates and headers stay just inside the wall box, never flush with the drywall
    HDR = FR.get("header_default", {})
    HOVR = FR.get("headers", [])
    BUILT = FR.get("built", [])
    USED_OVR = set()

    def on_line(ln, alongx, x0, x1, y0, y1):
        """is this wall piece on a built line: ln = {axis 'x' (runs east-west) or 'y', at = its y or x, from, to}"""
        if (ln["axis"] == "x") != alongx:
            return False
        c, u0, u1 = ((y0 + y1) / 2, x0, x1) if alongx else ((x0 + x1) / 2, y0, y1)
        return abs(c - ln["at"]) < ln.get("tol", 0.35) and u1 > ln["from"] + 0.05 and u0 < ln["to"] - 0.05

    ALL_BUILT = FR.get("all_built")          # Maxwell's 11/20/2026 photos: nearly every interior wall is framed

    def is_built(alongx, x0, x1, y0, y1):
        ln = next((ln for ln in BUILT if on_line(ln, alongx, x0, x1, y0, y1)), None)
        return ln or (dict(note=ALL_BUILT) if ALL_BUILT else None)

    def fbox(mat, alongx, u0, u1, v0, v1, z0, z1):
        if z1 - z0 < 1e-3 or u1 - u0 < 1e-3:
            return
        if alongx:
            box(mat, u0, u1, v0, v1, z0, z1)
        else:
            box(mat, v0, v1, u0, u1, z0, z1)

    def band(t0, t1, sd):
        # partitions are now drawn a 2x4 plus 5/8 in drywall each side thick, so the studs, centred, stay a full sheet
        # behind each face; a wall still drawn thinner than its studs squeezes them just inside its faces
        d = sd if t1 - t0 - sd > 2 * FACE_IN else t1 - t0 - 2 * FACE_IN
        vm = (t0 + t1) / 2
        return vm - d / 2, vm + d / 2

    # every opening: model door gaps, the clerestory wall's passages, and openings only a photo shows. A header entry in
    # config matches an opening by its plan point "at"; its "ro" = [u0, u1] is the rough opening seen in the photo
    # (pocket doors run the header over the pocket too).
    OPEN = []
    for (ax, g0, g1, a0, a1, h) in DOOR_GAPS:
        OPEN.append(dict(axis=ax, g0=g0, g1=g1, t0=a0, t1=a1, head=h, wall="int"))
    for (px0, px1, phd) in CL["passages"]:
        OPEN.append(dict(axis="x", g0=px0, g1=px1, t0=YC, t1=YC2, head=phd, wall="clerestory"))
    for o in HOVR:
        if o.get("new"):
            OPEN.append(dict(axis=o["axis"], g0=o["ro"][0], g1=o["ro"][1], t0=o["band"][0], t1=o["band"][1], head=o.get("head", 6.67), wall=o.get("wall", "int"), only=o))
    for op_ in OPEN:
        alongx = op_["axis"] == "x"
        cu, ct = (op_["g0"] + op_["g1"]) / 2, (op_["t0"] + op_["t1"]) / 2
        cx, cy = (cu, ct) if alongx else (ct, cu)
        spec, photo = dict(HDR), False
        for k_, o in enumerate(HOVR):
            if o.get("new") and op_.get("only") is not o:
                continue
            if op_.get("only") is o or math.hypot(o["at"][0] - cx, o["at"][1] - cy) < o.get("r", 1.6):
                spec, photo = dict(HDR, **o), True
                USED_OVR.add(k_)
                break
        if not photo:
            if op_["wall"] == "clerestory":
                spec.update(FR.get("clerestory_default", {}))
            for lim, dep in HDR.get("depth_by_span", []):
                if op_["g1"] - op_["g0"] <= lim:
                    spec["depth_in"] = dep
                    break
        r0, r1 = spec.get("ro", (op_["g0"], op_["g1"]))
        op_.update(spec=spec, photo=photo, r0=r0, r1=r1, cx=cx, cy=cy)
    if FR.get("strict", True):
        unused = [o["at"] for k_, o in enumerate(HOVR) if k_ not in USED_OVR]
        if unused:
            raise SystemExit(f"[[framing.headers]] entries matched no opening: {unused}")

    def bottom_plate(alongx, a, b, v0, v1, cuts):
        """the bottom plate, cut out across each opening"""
        u = a
        for c0, c1 in sorted(cuts):
            if c1 <= a or c0 >= b:
                continue
            fbox("Lumber", alongx, u, max(u, c0), v0, v1, 0.0, SW)
            u = max(u, c1)
        fbox("Lumber", alongx, u, b, v0, v1, 0.0, SW)

    def lines_up(op_, alongx, t0, t1):
        return (op_["axis"] == "x") == alongx and abs((op_["t0"] + op_["t1"]) / 2 - (t0 + t1) / 2) < 0.3

    # ---- interior walls
    PIECES = list(WALL_PIECES)
    if ATTIC_ACCESS:                                      # below the loft floor the attic access is solid wall
        x0, x1, y0, y1 = ATTIC_ACCESS
        PIECES.append(((x0, x1, y0, y1), lambda x, y: LOFT["floor_height"] - LOFT_FIN))
    for k, ((x0, x1, y0, y1), top) in enumerate(PIECES):
        alongx = (x1 - x0) >= (y1 - y0)
        a, b = (x0, x1) if alongx else (y0, y1)
        t0, t1 = (y0, y1) if alongx else (x0, x1)
        ln = is_built(alongx, x0, x1, y0, y1)
        v0, v1 = band(t0, t1, FR.get("stud_d_in", 3.5) * IN)
        nm = between(x0, x1, y0, y1)
        if not ln:
            rec(f"framing.plate.{k}", "framing", f"Bottom plate, interior wall {nm}".strip(), "framing",
                info=dict(model="Bottom plate on the slab, wall not framed yet",
                          specs=[["Length", ftin(b - a)]], notes=["The 11/19/2026 drone photos show only the bottom plate here."]))
            fbox("Lumber", alongx, a + FACE_IN, b - FACE_IN, v0, v1, 0.0, SW)
            FRAMING_META["walls"].append(dict(rect=[x0, x1, y0, y1], built=False))
            continue
        zt = lambda u: min(top(u, (t0 + t1) / 2) if alongx else top((t0 + t1) / 2, u), PLATE_TOP)
        rec(f"framing.wall.{k}", "framing", f"Studs and plates, interior wall {nm}".strip(), "framing",
            info=dict(model=f"2x4 studs at {FR.get('stud_oc_in', 16):g} in o.c., bottom plate, {NTOP} top plates",
                      specs=[["Length", ftin(b - a)], ["Top plate", ftin(min(zt(a), zt(b)))], ["Status", "Needs measuring"]],
                      notes=["NEEDS MEASURING: estimated from the 11/19/2026 drone photos only. Check with a tape before relying on it.", ln.get("note", "Framed in the 11/19/2026 drone photos."),
                             "Stud positions are the typical layout from the wall's west or north end (ASSUMED); the photos are too far away to count studs."]))
        FRAMING_META["walls"].append(dict(rect=[x0, x1, y0, y1], built=True, top=min(zt(a), zt(b))))
        a, b = a + FACE_IN, b - FACE_IN
        for n in range(NTOP):
            fbox("Lumber", alongx, a, b, v0, v1, min(zt(a), zt(b)) - (n + 1) * SW, min(zt(a), zt(b)) - n * SW)
        ztop = min(zt(a), zt(b)) - NTOP * SW
        # skip studs inside any rough opening (and its kings and jacks) on this wall line
        skip = []
        for op_ in OPEN:
            if lines_up(op_, alongx, t0, t1):
                kk = op_["spec"].get("jacks", 1) + op_["spec"].get("kings", 1)
                skip.append((op_["r0"] - kk * SW, op_["r1"] + kk * SW))
        bottom_plate(alongx, a, b, v0, v1, [(op_["r0"] - FACE_IN, op_["r1"] + FACE_IN) for op_ in OPEN if lines_up(op_, alongx, t0, t1)])
        us = [a + OC * i for i in range(0, int((b - a) / OC) + 1)] + [b - SW]
        last = None
        for u in sorted(us):
            u = min(max(u, a), b - SW)
            if last is not None and u - last < SW + 0.01:
                continue
            if any(s0 - 0.001 < u + SW and u < s1 + 0.001 for s0, s1 in skip):
                continue
            fbox("Lumber", alongx, u, u + SW, v0, v1, SW, ztop)
            last = u

    # ---- the clerestory line: stick framed to the top plate in the photos (shown inside the SIP wall's thickness)
    CLB = FR.get("clerestory_wall", {})
    CPT = CLB.get("plate_in", FR.get("plate_height_in", 109)) * IN   # its own measured top plate (9' 0 1/2", Maxwell 11/20/2026)
    if CLB.get("built"):
        a, b = T, HW - T
        v0, v1 = band(YC, YC2, CLB.get("stud_d_in", 5.5) * IN)
        rec("framing.wall.clerestory", "framing", "Studs and plates, bearing wall on the clerestory line", "framing",
            info=dict(model=f"2x{'6' if CLB.get('stud_d_in', 5.5) > 4 else '4'} studs at {FR.get('stud_oc_in', 16):g} in o.c., bottom plate, {NTOP} top plates (stud size ASSUMED)",
                      specs=[["Top plate", ftin(CPT)], ["Length", ftin(b - a)], ["Status", "Top plate measured" if "plate_in" in CLB else "Needs measuring"]],
                      notes=([] if "plate_in" in CLB else ["NEEDS MEASURING: estimated from the 11/19/2026 drone photos only. Check with a tape before relying on it."]) + [CLB.get("note", "Framed to the top plate in the 11/19/2026 drone photos.")]))
        bottom_plate(True, a, b, v0, v1, [(op_["r0"] - FACE_IN, op_["r1"] + FACE_IN) for op_ in OPEN if op_["wall"] == "clerestory"])
        for n in range(NTOP):
            fbox("Lumber", True, a, b, v0, v1, CPT - (n + 1) * SW, CPT - n * SW)
        skip = []
        for op_ in OPEN:
            if op_["wall"] == "clerestory":
                kk = op_["spec"].get("jacks", 1) + op_["spec"].get("kings", 1)
                skip.append((op_["r0"] - kk * SW, op_["r1"] + kk * SW))
        us, last = [a + OC * i for i in range(0, int((b - a) / OC) + 1)] + [b - SW], None
        for u in sorted(us):
            if last is not None and u - last < SW + 0.01:
                continue
            if any(s0 - 0.001 < u + SW and u < s1 + 0.001 for s0, s1 in skip):
                continue
            fbox("Lumber", True, u, u + SW, v0, v1, SW, CPT - NTOP * SW)
            last = u
        FRAMING_META["walls"].append(dict(rect=[a, b, YC, YC2], built=True, top=CPT))

    # ---- headers, kings and jacks for each opening in a built wall; openings in walls not up yet are listed for the clash check
    for op_ in OPEN:
        alongx = op_["axis"] == "x"
        spec, photo = op_["spec"], op_["photo"]
        t0, t1 = op_["t0"], op_["t1"]
        if op_["wall"] == "clerestory":
            built = bool(CLB.get("built"))
            v0, v1 = band(t0, t1, CLB.get("stud_d_in", 5.5) * IN)
        else:
            rx = (op_["r0"], op_["r1"], t0, t1) if alongx else (t0, t1, op_["r0"], op_["r1"])
            built = bool(is_built(alongx, *rx))
            v0, v1 = band(t0, t1, FR.get("stud_d_in", 3.5) * IN)
        r0, r1 = op_["r0"] - FACE_IN, op_["r1"] + FACE_IN       # off the drywall's cut ends, so the faces never flicker
        jk, kg = spec.get("jacks", 1), spec.get("kings", 1)
        ztop = PLATE_TOP - NTOP * SW
        if op_["wall"] != "clerestory":
            top = wall_top(r0, r1, t0, t1) if alongx else wall_top(t0, t1, r0, r1)
            ztop = min(PLATE_TOP, top(op_["cx"], op_["cy"])) - NTOP * SW
        hd = spec.get("depth_in", 3.5) * IN
        if spec.get("bottom_in") is not None:
            hb = spec["bottom_in"] * IN
        else:
            hb = op_["head"] + spec.get("head_gap_in", 0.5) * IN
        if spec.get("tight"):
            hbot, htop = (hb if spec.get("bottom_in") is not None else ztop - hd), ztop
        else:
            hbot, htop = hb, min(hb + hd, ztop)
        flat = spec.get("flat_top", True) and not spec.get("tight") and ztop - htop > 2 * SW
        h0, h1 = r0 - jk * SW, r1 + jk * SW
        hbox = (h0, h1, v0, v1, hbot, htop) if alongx else (v0, v1, h0, h1, hbot, htop)
        k0, k1 = r0 - (jk + kg) * SW, r1 + (jk + kg) * SW
        size = spec.get("label") or ("LVL" if str(spec.get("type", "")).upper().startswith("LVL") else f"({spec.get('plies', 2)}) 2x")
        door = nearest_label(op_["cx"], op_["cy"])
        btw = between(*((r0, r1, t0, t1) if alongx else (t0, t1, r0, r1)))
        if op_["wall"] == "clerestory":
            btw = f"in the clerestory wall, {ftin(r0)} to {ftin(r1)}"
        where = spec.get("name") or f"{btw}" + (f" ({door} door)" if door and op_["wall"] != "clerestory" and not op_.get("only") else "")
        hid = f"framing.header.{len(FRAMING_META['headers'])}"
        FRAMING_META["headers"].append(dict(id=hid, name=where, box=[round(v, 4) for v in hbox], built=built, photo=photo,
                                            ro=[r0, r1], axis=op_["axis"], kings=[k0, k1], band=[t0, t1], top=ztop + NTOP * SW,
                                            confidence=spec.get("confidence", "typical"), wall=op_["wall"], head=op_["head"], gap=[round(op_["g0"], 4), round(op_["g1"], 4)]))
        if not built:
            continue
        rec(hid, "framing", f"Door header {where}".strip(), "framing",
            info=dict(model=f"{spec.get('size', size)} header, about {ftin(htop - hbot)} deep" + ("" if photo else " (typical, ASSUMED)"),
                      specs=[["Rough opening", f"{ftin(r1 - r0)} wide" + (" (door and pocket)" if spec.get("pocket") else "")],
                             ["Header", f"bottom {ftin(hbot)}, top {ftin(htop)} above the slab" + (", tight under the top plates" if htop >= ztop - 1e-3 else ", flat 2x and cripples above")],
                             ["Source", spec.get("source", "Typical framing, ASSUMED until a build photo shows it")],
                             ["Confidence", spec.get("confidence", "typical")],
                             ["Status", ("Measured " + spec["measured"]) if spec.get("measured") else "Needs measuring"]],
                      notes=([f"MEASURED {spec['measured']}. Its position along the wall is still estimated from the photos."] if spec.get("measured") else
                             ["NEEDS MEASURING: estimated from the 11/19/2026 drone photos only. Check with a tape before relying on it."]) + list(spec.get("notes", []))))
        lvl = str(spec.get("type", "")).upper().startswith("LVL")
        fbox("LVL" if lvl else "Header", alongx, h0, h1, v0, v1, hbot, htop)
        for e, sg in ((r0, -1), (r1, 1)):
            for jj in range(jk):
                ua, ub = sorted((e + sg * jj * SW, e + sg * (jj + 1) * SW))
                fbox("Lumber", alongx, ua, ub, v0, v1, SW, hbot)
            for kk in range(kg):
                ua, ub = sorted((e + sg * (jk + kk) * SW, e + sg * (jk + kk + 1) * SW))
                fbox("Lumber", alongx, ua, ub, v0, v1, SW, ztop)
        if flat:                                          # flat 2x on the header, cripples up to the top plates
            fbox("Lumber", alongx, h0, h1, v0, v1, htop, htop + SW)
            nc = max(1, round((h1 - h0) / OC) - 1)
            for i_ in range(1, nc + 1):
                u = h0 + (h1 - h0) * i_ / (nc + 1) - SW / 2
                fbox("Lumber", alongx, u, u + SW, v0, v1, htop + SW, ztop)
    for p_ in FR.get("posts", []):                       # posts and beams seen in the photos
        rec(p_["id"], "framing", p_["name"], "framing", info=dict(model=p_.get("model", ""), notes=p_.get("notes", [])))
        box("Lumber", *p_["box"])

# ------------------------------------------------------------------ roofs and ceilings
def roof_slab(y0, y1, zfun):
    x0, x1 = -OH, HW + OH
    pts = [(x0, y0, zfun(y0)), (x1, y0, zfun(y0)), (x1, y1, zfun(y1)), (x0, y1, zfun(y1)),
           (x0, y0, zfun(y0) + TH), (x1, y0, zfun(y0) + TH), (x1, y1, zfun(y1) + TH), (x0, y1, zfun(y1) + TH)]
    hexa("Trim", pts, ["Trim", "Standing Seam", "Trim", "Trim", "Trim", "Trim"])


SEAM = R.get("seam_spacing_in", 16) / 12


def seam_ribs(x0, x1, y0, y1, ztop):
    x = x0 + SEAM / 2
    while x < x1 - 0.1:
        prism_x("Standing Seam", x - 0.031, x + 0.031, [(y0, ztop(y0) - 0.02), (y1, ztop(y1) - 0.02), (y1, ztop(y1) + 0.083), (y0, ztop(y0) + 0.083)])
        x += SEAM


ROOFINFO = [["Panels", f"{ftin(TH)} roof SIP (A-13)"], ["Roofing", f"Standing seam metal, {MM['roof_color']} charcoal, {R.get('seam_spacing_in', 16):g}\" panels (ASSUMED)"],
            ["Overhang", ftin(OH)]]
rec("roof.north", "roof", "High roof (north)", "roof", info=dict(model=f"{R['north_pitch']}:12 shed roof", specs=[["Pitch", f"{R['north_pitch']}:12 (revised 9/15/2026, was 3.88 on A-30)"]] + ROOFINFO))
roof_slab(-OH, YC2 + OH, north_roof_z)
seam_ribs(-OH, HW + OH, -OH, YC2 + OH, lambda y: north_roof_z(y) + TH)
rec("roof.south", "roof", "Low roof (south)", "roof", info=dict(model=f"{R['south_pitch']:g}:12 shed roof", specs=[["Pitch", f"{R['south_pitch']:g}:12 (A-13)"]] + ROOFINFO))
roof_slab(YC2, HD + OH, south_roof_z)
seam_ribs(-OH, HW + OH, YC2, HD + OH, lambda y: south_roof_z(y) + TH)

rec("ceiling.vault", "ceiling", "Vaulted ceilings", "ceiling", info=dict(model="Drywall on the underside of the roof panels", specs=[["Rooms", "Everything outside the 9' flat ceiling rooms"]]))
quad("Drywall", [(T, T, north_roof_z(T) - 0.01), (HW - T, T, north_roof_z(T) - 0.01), (HW - T, YC, north_roof_z(YC) - 0.01), (T, YC, north_roof_z(YC) - 0.01)])
quad("Drywall", [(T, YC2, south_roof_z(YC2) - 0.01), (HW - T, YC2, south_roof_z(YC2) - 0.01), (HW - T, HD - T, south_roof_z(HD - T) - 0.01), (T, HD - T, south_roof_z(HD - T) - 0.01)])
FR_ = C["ceilings"]["flat_rooms"]
for k, (x0, y0, x1, y1) in enumerate(FR_):
    rec(f"ceiling.flat.{k}", "ceiling", f"Flat ceiling, {room_at((x0 + x1) / 2, (y0 + y1) / 2) or 'room'}", "ceiling",
        info=dict(model=f"{ftin(FH)} flat ceiling (A-11)", specs=[["Above it", f"Floor trusses and the attic deck, top at {ftin(FH + FLOOR_T)}"]]))
    # run JOIN into each flat ceiling it butts against, so their seam does not show as a hairline (see JOIN)
    def _meets(side):
        for j, (a0, b0, a1, b1) in enumerate(FR_):
            if j == k:
                continue
            if side == 0 and abs(a1 - x0) < 0.01 and b0 < y1 and b1 > y0: return True
            if side == 1 and abs(a0 - x1) < 0.01 and b0 < y1 and b1 > y0: return True
            if side == 2 and abs(b1 - y0) < 0.01 and a0 < x1 and a1 > x0: return True
            if side == 3 and abs(b0 - y1) < 0.01 and a0 < x1 and a1 > x0: return True
        return False
    m_ = [_meets(i) for i in range(4)]
    box("Drywall", x0 - JOIN * m_[0], x1 + JOIN * m_[1], y0 - JOIN * m_[2], y1 + JOIN * m_[3], FH, 9, ztop=lambda x, y: FH + FLOOR_T - DECK_T,
        open_ends=tuple(f for f, m in zip((5, 3, 2, 4), m_) if m))      # the buried edges left open, so no hairline at the seam
if C["ceilings"].get("attic_floor"):
    rec("attic.deck", "floor", "Attic deck", "interior",
        info=dict(model="Walkable attic deck over the flat ceilings", specs=[["Top", f"{ftin(FH + FLOOR_T)} above the slab"], ["Build up", f"{_ft['depth_in'] if _ft else ''}\" floor trusses + {_ft['deck_in'] if _ft else ''}\" decking"]],
                  notes=["One continuous attic: the deck bridges the walls between flat ceiling rooms. ASSUMED."]))
    for k, (x0, y0, x1, y1) in enumerate(FR_):
        box("Attic Deck", x0, x1, y0, y1, FH + FLOOR_T - DECK_T, FH + FLOOR_T)
    for i, (a0, b0, a1, b1) in enumerate(FR_):
        for j, (c0, d0, c1, d1) in enumerate(FR_):
            if j <= i:
                continue
            ox0, ox1 = max(a0, c0), min(a1, c1); oy0, oy1 = max(b0, d0), min(b1, d1)
            if ox1 - ox0 > 1.0 and 0 < oy0 - oy1 <= 0.8:
                box("Attic Deck", ox0, ox1, oy1, oy0, FH + FLOOR_T - DECK_T, FH + FLOOR_T)
            elif oy1 - oy0 > 1.0 and 0 < ox0 - ox1 <= 0.8:
                box("Attic Deck", ox1, ox0, oy0, oy1, FH + FLOOR_T - DECK_T, FH + FLOOR_T)

# ------------------------------------------------------------------ loft
if LOFT["enabled"]:
    FL = LOFT["floor_height"]
    rec("loft.floor", "floor", "Loft floor", "interior", room="Loft",
        info=dict(model="134 sq ft loft over bath 1 (A-12)", specs=[["Floor", f"{ftin(FL)} above the slab"], ["Build up", f"9' plate + {_ft['depth_in'] if _ft else ''}\" open web trusses + {_ft['deck_in'] if _ft else ''}\" subfloor"],
                                                                     ["Finish", "White oak"]],
                  notes=["Raised from 9' 10 3/4\" (2x10 floor on A-30) to the 11 7/8\" trusses, Maxwell 11/16/2026."]))
    # The loft edge wall's drywall face runs up to the finish floor. The floor structure and the ceiling under it start
    # inside that wall, so nothing of the floor shows in front of the drywall from the living room (Maxwell 11/17/2026:
    # the floor edge used to stand a hair proud of the wall and read as wood between the drywall and the railing).
    EDGE_X = min([r_[0] for r_ in INT_RECTS if abs(r_[0] - LX0) < 0.3 and r_[3] > LY0 + 1] or [LX0])
    IN_X = EDGE_X + 0.25
    box("White Oak", IN_X, LX1, LY0, LY1, FL - FLOOR_T + 0.04, FL)                       # trusses and subfloor
    box("White Oak", EDGE_X, IN_X, LY0, LY1, FL - LOFT_FIN, FL)                         # finish floor over the edge wall
    rec("ceiling.loft", "ceiling", "Flat ceiling under the loft", "ceiling",
        info=dict(model=f"Drywall on the underside of the loft floor, {ftin(FL - FLOOR_T)}", specs=[["Rooms", "Bath 1, the mudroom cubby and the entry closet"]]))
    box("Drywall", IN_X, LX1, LY0, LY1, FL - FLOOR_T, FL - FLOOR_T + 0.04)
    # Ships ladder, the steepest the RCO / IRC R311.7.12 allows (Maxwell 11/21/2026): risers of 9.5 in or less, 5 in going
    # nosing to nosing, treads 8.5 in deep (going + nosing), 20 in clear width, handrails on both sides 30 to 34 in up.
    # Nosing k (1 = bottom tread) sits at x0 + (k - 1) * going, k * rise up; the loft edge is nosing 13, a 3.5 in oak
    # nosing proud of the bath 1 west wall, and the top tread tucks under it against the wall.
    lx0, ly0, lx1, ly1 = LOFT["ships_ladder"]
    NR = LOFT.get("ladder_risers", 13)
    GO, TD = LOFT.get("ladder_going_in", 5.0) / 12, LOFT.get("ladder_tread_in", 8.5) / 12
    RI = FL / NR
    WALL = EDGE_X - 0.01                                     # backs of the treads and stringers, a hair off the wall
    assert abs((lx0 + (NR - 1) * GO + (TD - GO)) - lx1) < 0.03, "ships_ladder x0 does not match its risers, going and tread"
    assert RI <= 9.5 / 12 + 1e-6 and GO >= 5 / 12 - 1e-6 and TD >= 8.5 / 12 - 1e-6, "ships ladder outside R311.7.12"
    SL = RI / GO                                              # slope of the nosing line
    zn = lambda x: RI + (x - lx0) * SL                       # nosing line
    SW, RW = LOFT.get("ladder_stringer_in", 1.8) / 12, 0.125   # stringer and handrail widths (corner design: ladder_stringer_in, 3/8 in for steel plate stringers)
    HR = LOFT.get("ladder_handrail_in", 32.0) / 12
    assert 2.5 <= HR <= 34 / 12 and (ly1 - ly0 - 2 * SW) * 12 >= 20, "ships ladder handrail height or width"
    DESIGN = os.environ.get("LADDER_DESIGN") or LOFT.get("ladder_design", "code")              # code | pullout | flip | lturn | side | alt: options drawn 11/21/2026 to keep the foot clear of the living room opening
    LADDER_CLIMBS = None                                     # walk mode ramps, when they are not the one straight flight
    RAIL_SPAN = (LY0 + 0.1, ly0 - 0.05)                      # loft guard: everything but where the ladder lands
    if DESIGN == "code":
        rec("loft.ladder", "stair", "Ships ladder to the loft", "interior", room="Loft",
            info=dict(model="White oak ships ladder, steepest to code (IRC R311.7.12, Residential Code of Ohio)",
                      specs=[["Risers", f"{NR} at {ftin(RI)}"], ["Treads", f"{NR - 1}, {ftin(TD)} deep, {ftin(GO)} nosing to nosing"],
                             ["Angle", f"{math.degrees(math.atan(SL)):.0f}\u00b0"], ["Rise", ftin(FL)], ["Footprint", f"{ftin(lx1 - lx0)} long, {ftin(ly1 - ly0)} wide"],
                             ["Clear width", ftin(ly1 - ly0 - 2 * SW)], ["Handrails", f"both sides, {ftin(HR)} above the nosings"]],
                      notes=["Code limits: riser 9 1/2 in max, going 5 in min, going + nosing 8 1/2 in min, 20 in clear at and below the handrails, handrails both sides 30 to 34 in. A ships ladder may serve a loft of 200 sq ft or less (this one is 134).",
                             "A-11 drew it 3' 5\" long with 12 risers of about 10 in and 3 3/4 in going, which is not to code; lengthened to the west 11/21/2026."]))
        for k in range(1, NR):
            xk = lx0 + (k - 1) * GO
            box("White Oak", xk, min(xk + TD, WALL), ly0 + SW + 0.005, ly1 - SW - 0.005, k * RI - 0.12, k * RI)
        box("White Oak", lx1 - (TD - GO), WALL, ly0 + SW + 0.005, ly1 - SW - 0.005, FL - 0.1, FL - 0.004)   # loft edge nosing
        xf = lx0 - 0.04                                           # plumb cut at the toe
        zt = lambda x: zn(x) + 0.1                                # stringer top, just above the nosings
        zb = lambda x: zt(x) - 1.0                                # 12 in deep measured plumb
        xb = lx0 + (0.9 - RI) / SL                                # where the bottom edge meets the slab
        xd = lx0 + (FL - 0.01 - 0.1 - RI) / SL                    # where the top edge reaches the loft floor
        for ya in (ly0, ly1 - SW):
            yb = ya + SW
            def seg(xa, xc, za0, za1, zc0, zc1):
                hexa("White Oak", [(xa, ya, za0), (xc, ya, zc0), (xc, ya, zc1), (xa, ya, za1),
                                   (xa, yb, za0), (xc, yb, zc0), (xc, yb, zc1), (xa, yb, za1)])
            seg(xf, xb, 0.0, zt(xf), 0.0, zt(xb))
            seg(xb, xd, 0.0, zt(xb), zb(xd), FL - 0.01)
            seg(xd, WALL, zb(xd), FL - 0.01, zb(WALL), FL - 0.01)
        # handrails on top of the stringers, parallel to the nosing line, from over the bottom nosing to over the loft edge
        xr0, xr1 = lx0, lx1 - (TD - GO)
        for yc in (ly0 + SW / 2, ly1 - SW / 2):
            y0_, y1_ = yc - RW / 2, yc + RW / 2
            hexa("Black Metal", [(xr0, y0_, zn(xr0) + HR - 0.13), (xr1, y0_, zn(xr1) + HR - 0.13), (xr1, y0_, zn(xr1) + HR), (xr0, y0_, zn(xr0) + HR),
                                 (xr0, y1_, zn(xr0) + HR - 0.13), (xr1, y1_, zn(xr1) + HR - 0.13), (xr1, y1_, zn(xr1) + HR), (xr0, y1_, zn(xr0) + HR)])
            for xp, zp in ((xr0 + 0.05, zt(xr0 + 0.05) - 0.05), (xr1 - 0.05, FL - 0.01)):
                box("Black Metal", xp - 0.05, xp + 0.05, yc - 0.04, yc + 0.04, zp, zn(xp) + HR - 0.06)
    else:
        exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ladder_options.py")).read())
    if LOFT.get("railing"):
        RH = LOFT.get("railing_height", 3.0)
        rec("loft.railing", "railing", "Loft railing", "interior", room="Loft",
            info=dict(model=f"{ftin(RH)} guard, black steel posts and balusters with a white oak cap (ASSUMED)", specs=[["Edge", "Open west edge of the loft, open where the ladder lands"], ["Top", ftin(FL + RH)]]))
        for ya, yb in (RAIL_SPAN if isinstance(RAIL_SPAN, list) else [RAIL_SPAN]):
            rx0, rx1 = LX0, LX0 + 0.12
            box("White Oak", rx0 - 0.04, rx1 + 0.04, ya, yb, FL + RH - 0.12, FL + RH)
            box("Black Metal", rx0, rx1, ya, yb, FL + 0.1, FL + 0.2)
            npost = max(2, int((yb - ya) / 4.0) + 1)
            for k in range(npost):
                yp = ya + (yb - ya) * k / (npost - 1)
                box("Black Metal", rx0, rx1, yp - 0.06, yp + 0.06, FL, FL + RH - 0.12)
            yb_ = ya + 0.33
            while yb_ < yb - 0.2:
                box("Black Metal", rx0 + 0.04, rx0 + 0.08, yb_ - 0.02, yb_ + 0.02, FL + 0.2, FL + RH - 0.12)
                yb_ += 0.33

exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "loft_furniture.py")).read())
# ------------------------------------------------------------------ kitchen (Carter Lumber design start plan, Erin's redline)
BASE_D, CTR_D, FRONT_T, REV = 1.9, 2.08, 0.06, 0.012
KICK, CTR_Z, CTR_T = 0.33, 3.0, 0.125
TALL = K.get("tall_height", 8.0)
RUNS = K["runs"]
UNIT_NAMES = {"blind": "Blind corner base", "door1": "Base cabinet, one door", "doors2": "Sink base, two doors", "drawers2": "Two drawer base",
              "drawers3": "Three drawer base", "drawer_door": "Drawer over a door", "drawer_doors2": "Drawer over two doors", "dishwasher": "Dishwasher bay",
              "pullout": "Pullout base", "oven_tower": "Oven tower", "tall_pantry": "Tall pantry", "fridge": "Fridge bay with over fridge cabinet",
              "tray": "Tray divider base", "beverage": "Beverage fridge bay", "panel": "End panel", "drawer_tall": "Tall utensil drawer",
              "pullout_drawer": "Drawer over a sheet pan pullout", "lazy_susan": "Lazy Susan corner base"}
PULL_NAME = K.get("pull_name", "Satin brass bar pulls")
ISLAND_TOP = "Butcher Block" if K.get("island_top", "butcher") == "butcher" else "Counter"
ISLAND_TOP_NAME = ("Edge grain butcher block, 1 1/2 in staves, oiled (species TBD)" if ISLAND_TOP == "Butcher Block"
                   else f"Quartz {K['counter_color']} (ASSUMED light quartz)")
ISLAND_MAT = "Cabinet Wood" if K.get("island_finish", "paint") == "wood" else "Island"
FINISH = lambda m: "Olive green, painted shaker" if m == "Island" else f"KraftMaid natural wood shaker, same white oak as the windows and trim (species and stain TBD)"
RUN_NAMES = {"south": "sink wall", "west": "cooktop wall", "north": "fridge wall", "island": "island", "island_east": "island, dining side"}


class Run:
    def __init__(self, rn, run):
        self.rn, self.run = rn, run

    def box(self, mat, u0, u1, d0, d1, z0, z1):
        b_, f_ = self.run["back"], self.run["facing"]
        if self.run["axis"] == "x":
            box(mat, u0, u1, b_ + f_ * d0, b_ + f_ * d1, z0, z1)
        else:
            box(mat, b_ + f_ * d0, b_ + f_ * d1, u0, u1, z0, z1)

    def at(self, u, d):
        b_, f_ = self.run["back"], self.run["facing"]
        return (u, b_ + f_ * d) if self.run["axis"] == "x" else (b_ + f_ * d, u)

    def outward(self, dist):
        f_ = self.run["facing"]
        return (0, f_ * dist) if self.run["axis"] == "x" else (f_ * dist, 0)


def pull(run, uc, zc, length, d, vertical=False, mat="Cabinet Pull"):
    """a bar pull. Cabinets get satin brass pulls (Maxwell 11/20/2026); appliances pass their own metal."""
    if vertical:
        run.box(mat, uc - 0.02, uc + 0.02, d, d + 0.07, zc - length / 2, zc + length / 2)
    else:
        run.box(mat, uc - length / 2, uc + length / 2, d, d + 0.07, zc - 0.02, zc + 0.02)


def shaker(run, r, u0, u1, z0, z1, d, mat, kind="door", hinge="L", glass=False, moves=None):
    """five piece shaker front with a recessed panel and a bar pull. moves = 'drawer' | 'door' adds a moving part."""
    u0, u1, z0, z1 = u0 + REV, u1 - REV, z0 + REV, z1 - REV
    w, h = u1 - u0, z1 - z0
    st = min(0.19, w / 4, h / 4)
    tgt = CUR[0]
    if moves == "drawer":
        o_ = op(r, f"{r['id']}.drawer{len(r.get('ops', []))}", "Drawer", "drawer", run.at((u0 + u1) / 2, d) + ((z0 + z1) / 2,), slide=run.outward(1.3) + (0,))
        tgt = o_["parts"]
    elif moves == "door":
        hu = u0 if hinge == "L" else u1
        ang = 100 if hinge == "L" else -100
        # the door turns about its hinge edge, away from the cabinet; the sign depends on which way the run faces
        ax = run.at(1, 0); a0 = run.at(0, 0); out = run.outward(1)
        axv, outv = (ax[0] - a0[0], -(ax[1] - a0[1])), (out[0], -out[1])
        sgn = 1 if axv[0] * outv[1] - axv[1] * outv[0] > 0 else -1
        o_ = op(r, f"{r['id']}.door{len(r.get('ops', []))}", "Cabinet door", "swing", run.at(hu, d + FRONT_T) + (0,), angle=ang * sgn)
        tgt = o_["parts"]
    with into(tgt):
        if h < 0.62 and kind == "drawer":
            run.box(mat, u0, u1, d, d + FRONT_T, z0, z1)
        else:
            run.box("Cabinet Glass" if glass else mat, u0 + st, u1 - st, d, d + FRONT_T * 0.6, z0 + st, z1 - st)
            run.box(mat, u0, u0 + st, d, d + FRONT_T, z0, z1)
            run.box(mat, u1 - st, u1, d, d + FRONT_T, z0, z1)
            run.box(mat, u0 + st, u1 - st, d, d + FRONT_T, z1 - st, z1)
            run.box(mat, u0 + st, u1 - st, d, d + FRONT_T, z0, z0 + st)
        dp = d + FRONT_T
        if kind == "drawer":
            zc = z1 - min(0.25, h / 2) if h > 0.62 else (z0 + z1) / 2
            if w > 2.4 and K.get("wide_drawer_pulls", 2) == 2:
                pull(run, u0 + w * 0.25, zc, 0.5, dp); pull(run, u0 + w * 0.75, zc, 0.5, dp)
            else:      # one bar about half the drawer's width, as on Danielle's 11/19/2026 rendering
                pull(run, (u0 + u1) / 2, zc, max(0.33, min(1.6, w * 0.5)), dp)
        elif kind == "door":
            uc = u1 - 0.12 if hinge == "L" else u0 + 0.12
            zc = z1 - 0.45 if z0 < 3.0 and z1 < 3.5 else z0 + 0.45
            if z1 - z0 > 3.5:
                zc = 3.6 if z0 < 1 else z0 + 0.45
            pull(run, uc, zc, 0.5, dp, vertical=True)


def hollow(run, u0, u1, d, z0, z1, mat, shelves=None):
    """an open cabinet case (back, sides, bottom, top, shelves) behind doors that open, so it reads as storage inside.
    shelves: heights, or None for one shelf when the box is over 1.4 ft tall (Maxwell 11/19/2026)."""
    ct = 0.06
    run.box(mat, u0, u1, 0, ct, z0, z1)
    for (b0, b1) in ((u0, u0 + ct), (u1 - ct, u1)):
        run.box(mat, b0, b1, ct, d, z0, z1)
    run.box(mat, u0 + ct, u1 - ct, ct, d, z0, z0 + ct)
    run.box(mat, u0 + ct, u1 - ct, ct, d, z1 - ct, z1)
    if shelves is None:
        shelves = [(z0 + z1) / 2] if z1 - z0 > 1.4 else []
    for zz in shelves:
        run.box(mat, u0 + ct, u1 - ct, ct, d - 0.05, zz, zz + 0.06)


def stack(run, r, u0, u1, z0, z1, d, mat, heights):
    tot = sum(heights); z = z1
    for hf in heights:
        hz = (z1 - z0) * hf / tot
        shaker(run, r, u0, u1, z - hz, z, d, mat, "drawer", moves="drawer"); z -= hz


def doors(run, r, u0, u1, z0, z1, d, mat, n, glass=False):
    if n == 1:
        shaker(run, r, u0, u1, z0, z1, d, mat, "door", "L", glass, moves="door")
    else:
        um = (u0 + u1) / 2
        shaker(run, r, u0, um, z0, z1, d, mat, "door", "L", glass, moves="door")
        shaker(run, r, um, u1, z0, z1, d, mat, "door", "R", glass, moves="door")


def placeholder(run, rn, k, for_id, name):
    """a plain appliance box from the Blender model, shown only when equipment.json has no real model"""
    return rec(f"cabinet.{rn}.{k}.{for_id}", "appliance", name, "interior", placeholder_for=for_id,
               info=dict(model="Placeholder", notes=["Shown only when the appliance layer is missing."]))


def lazy_susan(run, r, u0, u1, mat):
    """36 x 36 in pie cut lazy Susan in the southwest corner (Maxwell 11/20/2026). It sits at the west end of the sink
    wall run and fills the end of the cooktop wall run too. Two L doors ride the turntable: a tap turns the whole
    carousel 90 degrees, so the cooktop side leaf swings onto the sink wall face and a shelf of pots faces the room."""
    W = Run("west", RUNS["west"])
    xw, ys = RUNS["west"]["back"], run.run["back"]
    leg = u1 - u0                                     # 3 ft on each wall
    y_end = ys - leg                                  # where the cooktop run's last unit now ends
    zt, ct, d = CTR_Z - CTR_T, 0.06, BASE_D
    # case: kick, bottom, deck, backs on both walls, an end panel on each leg (counter over both legs)
    box(mat, xw, u1, ys - d + 0.25, ys, 0, KICK); box(mat, xw, xw + d - 0.25, y_end, ys - d + 0.25, 0, KICK)
    for (z0, z1) in ((KICK, KICK + ct), (zt - ct, zt)):
        box(mat, xw, u1, ys - d, ys, z0, z1); box(mat, xw, xw + d, y_end, ys - d, z0, z1)
    box(mat, xw, u1, ys - ct, ys, KICK + ct, zt - ct); box(mat, xw, xw + ct, y_end, ys - ct, KICK + ct, zt - ct)
    box(mat, u1 - ct, u1, ys - d, ys - ct, KICK + ct, zt - ct); box(mat, xw + ct, xw + d, y_end, y_end + ct, KICK + ct, zt - ct)
    box("Counter", xw, u1, ys - CTR_D, ys, zt, CTR_Z); box("Counter", xw, xw + CTR_D, y_end, ys - CTR_D, zt, CTR_Z)
    px, py = xw + d + FRONT_T / 2, ys - d - FRONT_T / 2      # the turntable pole, at the inside corner of the L doors
    o_ = op(r, f"{r['id']}.susan", "Lazy Susan", "swing", (px, py, 0), angle=-90)
    rad = 1.04                                        # 25 in shelves inside the 36 in box
    with into(o_["parts"]):
        shaker(run, r, xw + d, u1, KICK, zt, d, mat, "door", "R")          # sink wall leaf, pull near the corner
        shaker(W, r, y_end, ys - d - FRONT_T, KICK, zt, d, mat, "panel")    # cooktop wall leaf
        cyl("Brushed Nickel", px, py, KICK + ct, zt - ct, 0.04)
        # three quarter shelves: the missing quarter is the notch the doors sit in, facing the room
        n = 18
        for zz in (KICK + 0.12, KICK + 1.25):
            for i in range(n):
                a0 = math.radians(270 * i / n); a1 = math.radians(270 * (i + 1) / n)     # 0 east round to 270 north (plan y runs south)
                p0 = (px + rad * math.cos(a0), py + rad * math.sin(a0)); p1 = (px + rad * math.cos(a1), py + rad * math.sin(a1))
                ring = [(px, py), p0, p1, (px + 0.001 * math.cos((a0 + a1) / 2), py + 0.001 * math.sin((a0 + a1) / 2))]
                hexa("Cabinet Wood", [(x, y, zz) for x, y in ring] + [(x, y, zz + 0.05) for x, y in ring])
            # pots and mixing bowls round the shelf
            for j, (ang, rr, h, m) in enumerate(((40, 0.3, 0.55, "Stainless"), (110, 0.3, 0.45, "Black Metal"), (175, 0.32, 0.4, "Mug Sage"), (235, 0.28, 0.5, "Stainless"))):
                cx_, cy_ = px + 0.62 * math.cos(math.radians(ang)), py + 0.62 * math.sin(math.radians(ang))
                cyl(m, cx_, cy_, zz + 0.05, zz + 0.05 + h, rr * 0.85, rr)


def base_unit(run, rn, k, u0, u1, typ, mat, depth=BASE_D, counter=True):
    d = depth; zt = CTR_Z - CTR_T
    rid = f"cabinet.{rn}.{k}"
    nm = f"{UNIT_NAMES.get(typ, typ)}, {RUN_NAMES.get(rn, rn)}"
    r = rec(rid, "cabinet", nm, "interior", room="Kitchen",
            info=dict(model=f"{UNIT_NAMES.get(typ, typ)}, {ftin(u1 - u0)} wide", specs=[["Run", RUN_NAMES.get(rn, rn)], ["Finish", FINISH(mat)], ["Hardware", PULL_NAME]],
                      notes=["From the Carter Lumber design start plan (Danielle Gross, 11/10/2026) with Erin's 11/12 redline. Wood, door style and pulls from Danielle's 11/19/2026 north wall rendering."]))
    if typ == "lazy_susan":
        lazy_susan(run, r, u0, u1, mat); return
    if typ in ("oven_tower", "tall_pantry"):
        if typ == "oven_tower":                                   # solid round the oven, an open cabinet above it
            ot_ = K.get("oven_face_bottom", 1.22) + K.get("oven_face_height_in", 50.75) / 12
            run.box(mat, u0, u1, 0.03, BASE_D + 0.1, KICK, ot_ + 0.02)              # off the wall by 3/8 in, clear of the oven's back
            hollow(run, u0, u1, BASE_D + 0.1, ot_ + 0.02, TALL - 0.25, mat)
        else:
            run.box(mat, u0, u1, 0, BASE_D + 0.1, KICK, TALL - 0.25)
        run.box(mat, u0 + 0.05, u1 - 0.05, 0, BASE_D - 0.15, 0, KICK)
        run.box(mat, u0 - 0.05, u1 + 0.05, 0, BASE_D + 0.22, TALL - 0.25, TALL)
        df = BASE_D + 0.1
        if typ == "oven_tower":
            ob = K.get("oven_face_bottom", 1.22); ot = ob + K.get("oven_face_height_in", 50.75) / 12     # the oven's face, floor to top
            stack(run, r, u0, u1, KICK, ob - 0.02, df, mat, [1])
            doors(run, r, u0, u1, ot + 0.02, TALL - 0.25, df, mat, 2)
            placeholder(run, rn, k, "oven", "Double wall oven (placeholder)")
            run.box("Stainless", u0 + 0.1, u1 - 0.1, df - 0.02, df + 0.05, ob, ot)
            for zz in (ob + 0.15, ob + (ot - ob) / 2):
                run.box("Black Glass", u0 + 0.45, u1 - 0.45, df + 0.05, df + 0.06, zz + 0.25, zz + 1.05)
                pull(run, (u0 + u1) / 2, zz + 1.35, u1 - u0 - 0.8, df + 0.06, mat="Brushed Nickel")
        else:
            doors(run, r, u0, u1, KICK, 4.0, df, mat, 2)
            doors(run, r, u0, u1, 4.0, TALL - 0.25, df, mat, 2)
        return
    if typ == "fridge":
        fp = run.run.get("fridge_panels", 0.0)
        a0_, a1_ = (u0 + fp + 0.02, u1 - fp - 0.02) if fp else (u0 + 0.03, u1 - 0.03)
        if fp:
            for (b0, b1) in ((u0, u0 + fp), (u1 - fp, u1)):
                run.box(mat, b0, b1, 0, BASE_D + 0.42, 0, 6.0)
            hollow(run, u0, u1, BASE_D + 0.1, 6.0, TALL - 0.25, mat)
            doors(run, r, u0, u1, 6.0, TALL - 0.25, BASE_D + 0.1, mat, 2)
            run.box(mat, u0 - 0.05, u1 + 0.05, 0, BASE_D + 0.22, TALL - 0.25, TALL)
        else:
            hollow(run, u0 - 0.1, u1 + 0.1, BASE_D + 0.1, 6.0, TALL - 0.25, mat)
            doors(run, r, u0 - 0.1, u1 + 0.1, 6.0, TALL - 0.25, BASE_D + 0.1, mat, 2)
            run.box(mat, u0 - 0.15, u1 + 0.15, 0, BASE_D + 0.22, TALL - 0.25, TALL)
        placeholder(run, rn, k, "fridge", "Refrigerator (placeholder)")
        run.box("Stainless", a0_, a1_, 0.1, BASE_D + 0.35, 0, 5.9)
        run.box("Black Glass", (a0_ + a1_) / 2 - 0.01, (a0_ + a1_) / 2 + 0.01, BASE_D + 0.35, BASE_D + 0.36, 2.15, 5.9)
        run.box("Black Glass", a0_, a1_, BASE_D + 0.35, BASE_D + 0.36, 2.1, 2.15)
        for uc in ((a0_ + a1_) / 2 - 0.12, (a0_ + a1_) / 2 + 0.12):
            pull(run, uc, 4.0, 2.6, BASE_D + 0.36, vertical=True, mat="Brushed Nickel")
        pull(run, (a0_ + a1_) / 2, 1.9, a1_ - a0_ - 0.6, BASE_D + 0.36, mat="Brushed Nickel")
        run.box("Black Glass", a0_ + 0.3, a0_ + 0.8, BASE_D + 0.36, BASE_D + 0.37, 3.6, 4.5)
        return
    if typ == "panel":
        run.box(mat, u0, u1, 0, d + FRONT_T, 0, zt); return
    run.box(mat, u0, u1, 0, d, KICK, zt)
    run.box(mat, u0, u1, 0, d - 0.25, 0, KICK)
    if counter:
        run.box("Counter", u0, u1, 0, d + 0.18, zt, CTR_Z)
    if typ == "blind":
        return
    if typ == "dishwasher":
        placeholder(run, rn, k, "dishwasher", "Dishwasher (placeholder)")
        run.box("Stainless", u0 + REV, u1 - REV, d, d + 0.05, KICK, zt - 0.02)
        pull(run, (u0 + u1) / 2, zt - 0.2, u1 - u0 - 0.4, d + 0.05, mat="Brushed Nickel"); return
    if typ == "beverage":
        placeholder(run, rn, k, "beverage", "Beverage fridge (placeholder)")
        run.box("Stainless", u0 + REV, u1 - REV, d - 0.02, d + 0.03, KICK, zt - 0.02)
        run.box("Black Glass", u0 + 0.12, u1 - 0.12, d + 0.03, d + 0.04, KICK + 0.25, zt - 0.15)
        pull(run, u0 + 0.18, (KICK + zt) / 2, 1.4, d + 0.04, vertical=True, mat="Brushed Nickel"); return
    if typ == "tray":
        shaker(run, r, u0, u1, zt - 0.5, zt, d, mat, "drawer")
        run.box("Appliance Interior", u0 + 0.06, u1 - 0.06, 0.1, 0.15, KICK, zt - 0.5)
        for j in range(1, 5):
            uu = u0 + (u1 - u0) * j / 5
            run.box(mat, uu - 0.02, uu + 0.02, 0.15, d, KICK, zt - 0.52)
        for (b0, b1) in ((u0, u0 + 0.06), (u1 - 0.06, u1)):
            run.box(mat, b0, b1, 0, d + FRONT_T, KICK, zt - 0.5)
        return
    h = {"drawers3": [1, 2, 2], "drawers2": [1, 1]}
    if typ in ("drawers3", "drawers2"):
        stack(run, r, u0, u1, KICK, zt, d, mat, h[typ])
    elif typ in ("drawer_door", "drawer_doors2"):
        stack(run, r, u0, u1, zt - 0.5, zt, d, mat, [1])
        doors(run, r, u0, u1, KICK, zt - 0.5, d, mat, 1 if typ == "drawer_door" else 2)
    elif typ in ("door1", "pullout"):
        doors(run, r, u0, u1, KICK, zt, d, mat, 1)
    elif typ == "drawer_tall":
        stack(run, r, u0, u1, KICK, zt, d, mat, [1])
    elif typ == "pullout_drawer":
        stack(run, r, u0, u1, zt - 0.5, zt, d, mat, [1])
        doors(run, r, u0, u1, KICK, zt - 0.5, d, mat, 1)
    elif typ == "doors2":
        doors(run, r, u0, u1, KICK, zt, d, mat, 2)


for rn, run_ in RUNS.items():
    run = Run(rn, run_)
    mat = ISLAND_MAT if rn.startswith("island") else "Cabinet Wood"
    for k, (u0, u1, typ) in enumerate(run_["units"]):
        base_unit(run, rn, k, u0, u1, typ, mat, run_.get("depth", BASE_D), counter=not rn.startswith("island"))
nr = Run("north", RUNS["north"]); UB = K.get("upper_bottom", 4.6)
for k, up in enumerate(RUNS["north"].get("uppers", [])):
    u0, u1, typ = up[:3]; ud = up[3] if len(up) > 3 else 1.1
    r = rec(f"cabinet.north.upper.{k}", "cabinet", "Glass door upper, fridge wall" if typ == "glass" else "Microwave upper, fridge wall", "interior", room="Kitchen",
            info=dict(model=f"{'Glass door' if typ == 'glass' else 'Microwave'} upper, {ftin(u1 - u0)} wide, {ftin(ud)} deep", specs=[["Underside", ftin(UB)], ["Top", ftin(TALL)], ["Finish", FINISH("Cabinet Wood")]],
                      notes=(["Microwave upper deepened per Erin's redline."] if typ != "glass" else []) + ["Order from Danielle's 11/19/2026 rendering: microwave beside the fridge, glass doors at the east end."]))
    if typ == "glass":
        # a hollow case with two shelves of mugs, glasses and plates behind the glass (Maxwell 11/19/2026, as in Danielle's rendering)
        ct, zt_ = 0.06, TALL - 0.25
        nr.box("Cabinet Wood", u0, u1, 0, ct, UB, zt_)                                   # back
        for (b0, b1) in ((u0, u0 + ct), (u1 - ct, u1)):
            nr.box("Cabinet Wood", b0, b1, ct, ud, UB, zt_)                               # sides
        nr.box("Cabinet Wood", u0 + ct, u1 - ct, ct, ud, UB, UB + ct)                     # bottom
        nr.box("Cabinet Wood", u0 + ct, u1 - ct, ct, ud, zt_ - ct, zt_)                   # top
        shelves = (5.7, 6.75)
        for zz in shelves:
            nr.box("Cabinet Wood", u0 + ct, u1 - ct, ct, ud - 0.05, zz, zz + 0.06)
        n_ = max(2, int((u1 - u0 - 2 * ct) / 0.42))
        MUGS = ["Mug Blue", "Mug Mustard", "Mug Sage", "Mug Terracotta", "Mug Cream"]
        for j in range(n_):                                                              # colored mugs on the bottom, glasses on the first shelf (Maxwell 11/19/2026)
            uc = u0 + ct + (u1 - u0 - 2 * ct) * (j + 0.5) / n_
            cx, cy = nr.at(uc, 0.45)
            cyl(MUGS[j % len(MUGS)], cx, cy, UB + ct, UB + ct + 0.32, 0.15, 0.15)
            nr.box(MUGS[j % len(MUGS)], uc - 0.02, uc + 0.02, 0.6, 0.68, UB + ct + 0.08, UB + ct + 0.25)   # handle, facing out
            cx, cy = nr.at(uc, 0.45)
            cyl("Cabinet Glass", cx, cy, shelves[0] + 0.06, shelves[0] + 0.51, 0.12, 0.14)
        zs_ = shelves[1] + 0.06                                                          # top shelf: nested bowls (plates live in a sink wall drawer)
        for j, mt in enumerate(("Mug Sage", "Mug Cream")):
            cx, cy = nr.at(u0 + (u1 - u0) * (0.27 + 0.46 * j), ud / 2)
            for q in range(4):
                cyl(mt, cx, cy, zs_ + q * 0.09, zs_ + q * 0.09 + 0.25, 0.14, 0.26)
        doors(nr, r, u0, u1, UB, zt_, ud, "Cabinet Wood", 2, glass=True)
    else:
        nr.box("Cabinet Wood", u0, u1, 0, ud, UB, UB + 1.55)                               # microwave cubby
        hollow(nr, u0, u1, ud, UB + 1.55, TALL - 0.25, "Cabinet Wood")                      # open cabinet over it
        nr.box("Stainless", u0 + 0.15, u1 - 0.15, ud - 0.05, ud + 0.02, UB + 0.05, UB + 1.45)
        nr.box("Black Glass", u0 + 0.3, u1 - 0.9, ud + 0.02, ud + 0.03, UB + 0.25, UB + 1.25)
        doors(nr, r, u0, u1, UB + 1.55, TALL - 0.25, ud, "Cabinet Wood", 2)
    nr.box("Cabinet Wood", u0 - 0.03, u1 + 0.03, 0, ud + 0.12, TALL - 0.25, TALL)

PANTRY_STYLE = RUNS["north"].get("pantry_style", "door")
if RUNS["north"].get("pantry_door") and PANTRY_STYLE == "murphy":
    # Danielle Gross's 11/19/2026 north wall rendering: the tall pantry cabinet left of the fridge is a Murphy door. The whole
    # cabinet (case, faux door fronts, crown) swings out into the kitchen on a hinge at its west front corner and parks
    # along the west wall, so the fridge stays reachable; behind it is the 6'-8" passage into the pantry.
    px0, px1, phd = min(CL["passages"], key=lambda p: p[0])
    mx0 = T + 0.02                                            # 1/4 in off the west wall's inside face
    mx1 = RUNS["north"]["units"][0][0] - 0.02                 # 1/4 in short of the fridge bay's side panel
    mdf = BASE_D + 0.1                                        # face in line with the over-fridge doors
    msplit = RUNS["north"].get("murphy_split", UB)            # door line in line with the underside of the uppers
    r = rec("door.pantry", "door", "Pantry Murphy door", "interior", room="Kitchen",
            info=dict(model=f"Murphy door made as a tall pantry cabinet, {ftin(mx1 - mx0)} wide x {ftin(mdf)} deep x {ftin(TALL)} tall",
                      specs=[["Opening behind it", f"{ftin(px1 - px0)} x {ftin(phd)} passage into the pantry"], ["Finish", FINISH("Cabinet Wood")],
                             ["Hardware", f"{PULL_NAME}, heavy duty pivot hinge at the west front corner (ASSUMED)"]],
                      notes=["Danielle Gross's 11/19/2026 north wall rendering shows a tall pantry cabinet here; Maxwell: it is a Murphy door.",
                             "The whole cabinet swings into the kitchen and parks along the west wall. Which side it hinges on and which way it swings is ASSUMED. "
                             "Open, it stands partly in front of the glass kitchen door on the west wall.",
                             "The four doors on its face are drawn shut; whether they open onto shelves is not decided."]))
    nr_ = Run("north", RUNS["north"])
    pv = nr_.at(mx0, mdf + FRONT_T)
    lf = op(r, "door.pantry.leaf", "Pantry Murphy door", "swing", pv + (0,), angle=-RUNS["north"].get("murphy_swing", 92))
    with into(lf["parts"]):
        nr_.box("Cabinet Wood", mx0, mx1, 0.02, mdf, KICK, TALL - 0.25)                       # case, 1/4 in off the wall
        nr_.box("Cabinet Wood", mx0 + 0.05, mx1 - 0.05, 0.02, mdf - 0.15, 0.02, KICK)          # toe kick
        nr_.box("Cabinet Wood", mx0, mx1, 0.02, mdf + 0.12, TALL - 0.25, TALL)                 # crown, flush with the fridge bay crown
        for (z0_, z1_) in ((KICK, msplit), (msplit, TALL - 0.25)):
            um = (mx0 + mx1) / 2
            shaker(nr_, r, mx0, um, z0_, z1_, mdf, "Cabinet Wood", "door", "L")
            shaker(nr_, r, um, mx1, z0_, z1_, mdf, "Cabinet Wood", "door", "R")
    for (a0, a1) in ((px0, px0 + 0.06), (px1 - 0.06, px1)):                                    # oak jambs and head in the wall opening
        box("White Oak", a0, a1, YC, YC2, 0, phd)
    box("White Oak", px0, px1, YC, YC2, phd - 0.06, phd)
elif RUNS["north"].get("pantry_door") and PANTRY_STYLE in ("flush", "pocket", "shelf"):
    # Pantry doorway options after Maxwell found the deep Murphy cabinet could not swing past the fridge and wall (11/19/2026).
    # All three keep the cabinet run reading as one: a wood end panel on the west wall, an upper cabinet over the doorway
    # in line with the fridge cabinet, and the fridge bay's own side panel on the east.
    #   flush:  a 1 3/4 in door dressed as a pair of tall pantry doors, flush with the cabinet faces, swinging out (west hinge)
    #   pocket: a shaker slab pocket door in the wall opening, sliding east into the wall behind the fridge
    #   shelf:  a shallow Murphy door of open shelves in the wall opening, swinging into the pantry
    px0, px1, phd = min(CL["passages"], key=lambda p: p[0])
    nr_ = Run("north", RUNS["north"])
    mx0, mx1 = T + 0.02, RUNS["north"]["units"][0][0] - 0.02
    mdf = BASE_D + 0.1
    ah = RUNS["north"].get("alcove_head", 6.85)              # underside of the upper cabinet over the doorway
    PANTRY_NOTES = {
        "flush": ("Pantry door, cabinet front", "A 1-3/4 in solid door dressed as a pair of tall shaker pantry doors, flush with the cabinet faces. It hinges on the west and swings into the kitchen, lying flat along the west wall when open. Nothing deep swings, so it clears the fridge and the wall."),
        "pocket": ("Pantry pocket door", "A shaker slab door in the wall opening that slides east into the wall behind the fridge. The wall is a 2x6 bearing wall, so the pocket needs a header sized by the builder."),
        "shelf": ("Pantry spice rack Murphy door", "A shallow Murphy door made as a spice rack: jar shelves about 5 in deep, its face nearly flush with the fridge cabinet. It hinges on the west and swings out into the kitchen, parking against the west end panel (Maxwell's pick, 11/19/2026). The latch: push the gold lidded \"Open Sesame\" jar on the east side at hand height; it is fixed over a push-to-open catch."),
    }
    nm_, note_ = PANTRY_NOTES[PANTRY_STYLE]
    HW_ = ("Rockler InvisiDoor pivot bookcase hinge kit, with the Rockler InvisiDoor secret book latch triggered by the Open Sesame jar (Maxwell 11/19/2026)"
           if PANTRY_STYLE == "shelf" else PULL_NAME)
    LINKS_ = ([["Rockler InvisiDoor Pivot Bookcase Hinge Kit", "https://rockler.com/invisidoor-pivot-bookcase-hinge-kit"],
               ["Rockler Secret Book Latch for InvisiDoor", "https://rockler.com/secret-book-latch-for-invisidoortrade-pivot-bookcase-hinge-kit"]]
              if PANTRY_STYLE == "shelf" else [])
    r = rec("door.pantry", "door", nm_, "interior", room="Kitchen",
            info=dict(model=nm_, specs=[["Opening", f"{ftin(px1 - px0)} x {ftin(phd)} passage into the pantry"], ["Finish", FINISH("Cabinet Wood")], ["Hardware", HW_]], links=LINKS_,
                      notes=[note_, "One of three pantry doorway options (config [kitchen.runs.north] pantry_style = flush | pocket | shelf), Maxwell 11/19/2026."]))
    # fixed surround: west end panel, upper cabinet over the doorway, crown
    nr_.box("Cabinet Wood", mx0, mx0 + 0.06, 0, mdf + FRONT_T, 0, TALL - 0.25)
    hollow(nr_, mx0 + 0.06, mx1, mdf, ah, TALL - 0.25, "Cabinet Wood")
    rr_ = rec("cabinet.north.over_pantry", "cabinet", "Upper cabinet over the pantry doorway", "interior", room="Kitchen",
              info=dict(model=f"{ftin(mx1 - mx0)} wide, {ftin(mdf)} deep", specs=[["Finish", FINISH("Cabinet Wood")]]))
    doors(nr_, rr_, mx0 + 0.06, mx1, ah, TALL - 0.25, mdf, "Cabinet Wood", 2)
    nr_.box("Cabinet Wood", mx0, mx1, 0, mdf + 0.12, TALL - 0.25, TALL)
    for (a0, a1) in ((px0, px0 + 0.06), (px1 - 0.06, px1)):                                    # wood jambs and head in the wall opening
        box("Cabinet Wood", a0, a1, YC, YC2, 0, phd)
    box("Cabinet Wood", px0, px1, YC, YC2, phd - 0.06, phd)
    if PANTRY_STYLE == "flush":
        lx0, lx1 = mx0 + 0.07, mx1 - 0.01
        lf = op(r, "door.pantry.leaf", nm_, "swing", nr_.at(lx0, mdf + FRONT_T) + (0,), angle=-95)
        with into(lf["parts"]):
            nr_.box("Cabinet Wood", lx0, lx1, mdf - 0.09, mdf, KICK, ah - 0.02)                 # door core
            nr_.box("Cabinet Wood", lx0 + 0.05, lx1 - 0.05, mdf - 0.09, mdf - 0.06, 0.03, KICK)  # toe kick strip
            um = (lx0 + lx1) / 2
            shaker(nr_, r, lx0, um, KICK, ah - 0.02, mdf, "Cabinet Wood", "door", "L")
            shaker(nr_, r, um, lx1, KICK, ah - 0.02, mdf, "Cabinet Wood", "door", "R")
    elif PANTRY_STYLE == "pocket":
        lx0, lx1 = px0 + 0.06, px1 - 0.04
        lf = op(r, "door.pantry.leaf", nm_, "slide", ((lx0 + lx1) / 2, YC + 0.27, 0), slide=(lx1 - lx0 - 0.3, 0, 0))
        with into(lf["parts"]):
            nr_.box("Cabinet Wood", lx0, lx1, -0.34, -0.26, 0.03, phd - 0.07)
            shaker(nr_, r, lx0, lx1, 0.03, phd - 0.07, -0.26, "Cabinet Wood", "door", "R")
    else:
        # spice rack Murphy door (Maxwell 11/19/2026): 5 in deep, its face nearly flush with the fridge cabinet. shelf_swing = "out"
        # (Maxwell's pick): hinged at its front west corner, it swings out into the kitchen and parks along the west end panel;
        # its back east corner clears the fridge panel by about 5/8 in. "in": hinged at the back west corner, it swings
        # through the alcove and the wall opening into the pantry (checked in plan, no corner crosses the wall).
        sd = 0.42
        lx0, lx1 = px0 + 0.07, mx1 - 0.08                     # about 3 ft wide, 1 in clear of the fridge panel
        f1 = mdf + FRONT_T - 0.02                              # rack face, 1/4 in behind the cabinet faces
        f0 = f1 - sd
        lt = phd - 0.09                                        # it passes under the wood head of the 6-8 wall opening
        out_ = RUNS["north"].get("shelf_swing", "out") == "out"     # Maxwell 11/19/2026: out into the kitchen, simpler hinges
        lf = op(r, "door.pantry.leaf", nm_, "swing", nr_.at(lx0, f1 if out_ else f0) + (0,), angle=-100 if out_ else 90)
        with into(lf["parts"]):
            nr_.box("Cabinet Wood", lx0, lx1, f0, f0 + 0.06, 0.03, lt)                           # back
            for (b0, b1) in ((lx0, lx0 + 0.06), (lx1 - 0.06, lx1)):
                nr_.box("Cabinet Wood", b0, b1, f0, f1, 0.03, lt)                                # stiles
            nr_.box("Cabinet Wood", lx0 + 0.06, lx1 - 0.06, f0, f1, lt - 0.25, lt)              # top rail
            nr_.box("Cabinet Wood", lx0 + 0.06, lx1 - 0.06, f0, f1, 0.03, KICK)                 # bottom rail, like a toe kick line
            zs = [KICK + i_ * 0.62 for i_ in range(10) if KICK + i_ * 0.62 < lt - 0.5]
            cols = ["Spice Red", "Spice Yellow", "Spice Green", "Spice Brown", "Spice Orange", "Spice Green", "Spice Brown"]
            zkey = min(range(len(zs)), key=lambda i_: abs(zs[i_] - 4.0))                                 # the Open Sesame jar's shelf, about hand height
            for k_, zz in enumerate(zs):
                nr_.box("Cabinet Wood", lx0 + 0.06, lx1 - 0.06, f0 + 0.06, f1 - 0.03, zz, zz + 0.05)            # shelf
                nr_.box("Cabinet Pull", lx0 + 0.06, lx1 - 0.06, f1 - 0.04, f1 - 0.02, zz + 0.16, zz + 0.18)    # brass rail that keeps the jars in
                n_ = 8
                for j in range(n_):
                    cx, cy = nr_.at(lx0 + 0.2 + j * (lx1 - lx0 - 0.4) / (n_ - 1), (f0 + f1) / 2 + 0.02)
                    if k_ == zkey and j == n_ - 1:
                        # "Open Sesame": the one fake jar, glued down over a push-to-open catch on the latch edge (Maxwell 11/19/2026)
                        cyl("Sesame", cx, cy, zz + 0.05, zz + 0.33, 0.075)
                        cyl("Gold Lid", cx, cy, zz + 0.33, zz + 0.39, 0.078)
                        lx_, ly_ = nr_.at(lx0 + 0.2 + j * (lx1 - lx0 - 0.4) / (n_ - 1), (f0 + f1) / 2 + 0.02 + 0.074)
                        box("Dishware", lx_ - 0.05, lx_ + 0.05, ly_, ly_ + 0.006, zz + 0.12, zz + 0.25)              # label
                        continue
                    cyl(cols[(j + k_ * 3) % len(cols)], cx, cy, zz + 0.05, zz + 0.33, 0.075)                    # jar of spice
                    cyl("Black Metal", cx, cy, zz + 0.33, zz + 0.39, 0.078)                                      # black lid
elif RUNS["north"].get("pantry_door"):
    px0, px1, phd = min(CL["passages"], key=lambda p: p[0])
    leaf = RUNS["north"].get("pantry_door_leaf", px1 - px0 - 0.2)
    ce, cw = RUNS["north"].get("pantry_casing_east", 0.29), RUNS["north"].get("pantry_casing_west", 0.29)
    lx0 = (px0 + px1) / 2 - leaf / 2; lx1 = lx0 + leaf
    r = rec("door.pantry", "door", "Pantry door", "interior", room="Pantry",
            info=dict(model=f"{ftin(leaf)} x {ftin(phd)} white oak slab door", specs=[["Opening", f"{ftin(px1 - px0)} in the clerestory wall"], ["Hardware", "Brushed nickel lever"]],
                      notes=["Erin's redline: a door into the pantry where Carter drew a tall cabinet. Leaf size ASSUMED so the casing stops 2\" short of the fridge panel."]))
    lf = op(r, "door.pantry.leaf", "Pantry door", "swing", (lx0, YC + 0.27, 0), angle=90)
    with into(lf["parts"]):
        box("White Oak", lx0, lx1, YC + 0.2, YC + 0.34, 0.03, phd - 0.06)
        box("Brushed Nickel", lx1 - 0.3, lx1 - 0.18, YC2 - 0.02, YC2 + 0.02, 3.0, 3.12)
        box("Brushed Nickel", lx1 - 0.55, lx1 - 0.22, YC2 + 0.02, YC2 + 0.08, 3.04, 3.08)
    for (a0, a1) in ((px0, px0 + 0.06), (px1 - 0.06, px1)):
        box("White Oak", a0, a1, YC, YC2, 0, phd)
    box("White Oak", px0, px1, YC, YC2, phd - 0.06, phd)
    for (a0, a1, z0_, z1_) in ((px0 - cw, px0 + 0.02, 0, phd), (px1 - 0.02, px1 + ce, 0, phd), (px0 - cw, px1 + ce, phd, phd + 0.29)):
        box("White Oak", a0, a1, YC2, YC2 + 0.06, z0_, z1_)

# plates in the middle drawer of the easternmost sink wall drawer stack (Maxwell 11/19/2026): an open drawer box that
# slides out with the front, holding a stack of dinner plates and one of salad plates
_pd = K.get("plate_drawer", ["cabinet.south.6", 1])
if _pd and _pd[0] in BYID and len(BYID[_pd[0]].get("ops", [])) > _pd[1]:
    _r = BYID[_pd[0]]; _o = _r["ops"][_pd[1]]
    _k = int(_pd[0].rsplit(".", 1)[1]); _u0, _u1 = RUNS["south"]["units"][_k][:2]
    _rs = Run("south", RUNS["south"]); _zt = CTR_Z - CTR_T
    _zb = KICK + (_zt - KICK) * 2 / 5 + 0.06; _ztop = KICK + (_zt - KICK) * 4 / 5 - 0.12
    _r["name"] += ", plates in the middle drawer"
    with into(_o["parts"]):
        _rs.box("Cabinet Wood", _u0 + 0.1, _u1 - 0.1, 0.2, BASE_D - 0.02, _zb, _zb + 0.04)               # drawer bottom
        for (_b0, _b1) in ((_u0 + 0.1, _u0 + 0.14), (_u1 - 0.14, _u1 - 0.1)):
            _rs.box("Cabinet Wood", _b0, _b1, 0.2, BASE_D - 0.02, _zb, _ztop)                            # sides
        _rs.box("Cabinet Wood", _u0 + 0.14, _u1 - 0.14, 0.2, 0.24, _zb, _ztop)                           # back
        for _j, (_rr, _n) in enumerate(((0.43, 12), (0.36, 10))):
            _cx, _cy = _rs.at(_u0 + (_u1 - _u0) * (0.3 + 0.42 * _j), 1.05)
            for _q in range(_n):
                _z = _zb + 0.04 + _q * 0.045
                cyl("Dishware", _cx, _cy, _z, _z + 0.035, _rr * 0.75, _rr)
            for _a in range(4):                                                                            # pegs round the stack
                _px, _py = _rs.at(_u0 + (_u1 - _u0) * (0.3 + 0.42 * _j) + (_rr + 0.05) * math.cos(_a * math.pi / 2 + 0.6),
                                  1.05 + (_rr + 0.05) * math.sin(_a * math.pi / 2 + 0.6))
                cyl("Cabinet Wood", _px, _py, _zb + 0.04, _zb + 0.5, 0.035)


def disc_u(mat, run, u0, u1, dc, zc, R, n=14):
    """a round disc standing on edge across the run (axis along u): a skillet, pot or lid seen from the drawer front"""
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        ring = [(dc, zc), (dc + R * math.cos(a0), zc + R * math.sin(a0)), (dc + R * math.cos(a1), zc + R * math.sin(a1)),
                (dc + 0.001 * math.cos((a0 + a1) / 2), zc + 0.001 * math.sin((a0 + a1) / 2))]
        hexa(mat, [run.at(u0, d_) + (z_,) for d_, z_ in ring] + [run.at(u1, d_) + (z_,) for d_, z_ in ring])


def bar_u(mat, run, uc, w, d0, z0, d1, z1, t=0.05):
    """a straight bar from (d0, z0) to (d1, z1), w wide across the run: a pan handle"""
    L = math.hypot(d1 - d0, z1 - z0); nd, nz = -(z1 - z0) / L * t / 2, (d1 - d0) / L * t / 2
    prof = [(d0 - nd, z0 - nz), (d1 - nd, z1 - nz), (d1 + nd, z1 + nz), (d0 + nd, z0 + nz)]
    hexa(mat, [run.at(uc - w / 2, d_) + (z_,) for d_, z_ in prof] + [run.at(uc + w / 2, d_) + (z_,) for d_, z_ in prof])


# the deep drawer under the cooktop: wood dividers front to back, skillets and pans on edge, lids at the end
# (Maxwell 11/20/2026, from a photo of a pan drawer "with enough space for lids")
_pn = K.get("pan_drawer", ["cabinet.west.2", 1])
if _pn and _pn[0] in BYID and len(BYID[_pn[0]].get("ops", [])) > _pn[1]:
    _r = BYID[_pn[0]]; _o = _r["ops"][_pn[1]]
    _k = int(_pn[0].rsplit(".", 1)[1]); _u0, _u1 = RUNS["west"]["units"][_k][:2]
    _rw = Run("west", RUNS["west"]); _zt = CTR_Z - CTR_T
    _zb = KICK + 0.08; _ztop = KICK + (_zt - KICK) / 2 - 0.1                       # inside the lower of the two drawers
    _r["name"] += ", pans in the lower drawer"
    _o["slide"] = [rnd(v) for v in _rw.outward(1.6) + (0,)]                                  # full extension slides, so every pan clears the counter
    _r.setdefault("info", {}).setdefault("notes", []).append("Lower drawer: wood pan dividers with skillets and pans on edge and lids at the end (Maxwell 11/20/2026).")
    with into(_o["parts"]):
        _rw.box("Cabinet Wood", _u0 + 0.1, _u1 - 0.1, 0.2, BASE_D - 0.02, _zb, _zb + 0.04)               # drawer bottom
        for (_b0, _b1) in ((_u0 + 0.1, _u0 + 0.14), (_u1 - 0.14, _u1 - 0.1)):
            _rw.box("Cabinet Wood", _b0, _b1, 0.2, BASE_D - 0.02, _zb, _ztop)                            # sides
        _rw.box("Cabinet Wood", _u0 + 0.14, _u1 - 0.14, 0.2, 0.24, _zb, _ztop)                           # back
        _ns = 8; _a, _b = _u0 + 0.14, _u1 - 0.14; _sw = (_b - _a) / _ns
        for _j in range(1, _ns):
            _uu = _a + _sw * _j
            _rw.box("Cabinet Wood", _uu - 0.02, _uu + 0.02, 0.24, BASE_D - 0.25, _zb + 0.04, _ztop - 0.12)   # dividers
        _fl = _zb + 0.04
        _pans = [(0.5, "Black Metal", 0.15), (0.47, "Stainless", 0.17), (0.44, "Black Metal", 0.14), (0.42, "Stainless", 0.2),
                 (0.38, "Black Metal", 0.13), (0.35, "Stainless", 0.16)]
        for _j, (_R, _m, _dp) in enumerate(_pans):
            _uc = _a + _sw * (_j + 0.5); _R = min(_R, (_ztop - _fl) / 2 + 0.02); _dc = 1.1; _zc = _fl + _R
            disc_u(_m, _rw, _uc - _dp / 2, _uc + _dp / 2, _dc, _zc, _R)
            _h0 = (_dc + _R * 0.55, _zc + _R * 0.83)                                                   # handle off the rim, up toward the front
            _h1 = (min(BASE_D - 0.12, _h0[0] + 0.62), min(_ztop + 0.06, _h0[1] + 0.25))
            bar_u("Stainless" if _m == "Stainless" else "Black Metal", _rw, _uc, 0.06, _h0[0], _h0[1], _h1[0], _h1[1])
        for _j in (6, 7):                                                                                  # lids, three to a slot
            for _q in range(3):
                _R = 0.46 - 0.05 * _q - 0.04 * (_j - 6); _uc = _a + _sw * (_j + 0.25 + 0.25 * _q)
                disc_u("Cabinet Glass", _rw, _uc - 0.012, _uc + 0.012, 0.95 + 0.08 * _q, _fl + _R, _R)
                _rw.box("Black Metal", _uc - 0.05, _uc + 0.05, 0.95 + 0.08 * _q - 0.04, 0.95 + 0.08 * _q + 0.04, _fl + 2 * _R - 0.01, _fl + 2 * _R + 0.01)

sr = Run("south", RUNS["south"]); sx0, sx1 = RUNS["south"]["sink_x"]
rec("kitchen.sink", "fixture", "Kitchen sink and faucet", "interior", room="Kitchen",
    info=dict(model="Stainless drop in sink, brushed nickel faucet", specs=[["Width", ftin(sx1 - sx0)]], notes=["Under the kitchen window on the sink wall. Model not picked yet."]))
sr.box("Stainless", sx0, sx1, 0.35, 1.75, CTR_Z + 0.004, CTR_Z + 0.03)
sr.box("Stainless", sx0 + 0.1, sx1 - 0.1, 0.45, 1.65, CTR_Z - 0.7, CTR_Z + 0.031)
sr.box("Brushed Nickel", (sx0 + sx1) / 2 - 0.05, (sx0 + sx1) / 2 + 0.05, 0.15, 0.25, CTR_Z, CTR_Z + 1.2)
sr.box("Brushed Nickel", (sx0 + sx1) / 2 - 0.04, (sx0 + sx1) / 2 + 0.04, 0.15, 0.85, CTR_Z + 1.12, CTR_Z + 1.2)
wr = Run("west", RUNS["west"]); cy0, cy1 = RUNS["west"]["cooktop_y"]
rec("kitchen.cooktop.placeholder", "appliance", "Cooktop (placeholder)", "interior", placeholder_for="cooktop", info=dict(model="Placeholder"))
wr.box("Black Glass", cy0, cy1, 0.15, 1.85, CTR_Z + 0.004, CTR_Z + 0.035)
# Range hood (Maxwell, 11/20/2026): built as a fume hood, following Matt Risinger's style "kitchen exhaust" advice in the video he
# picked (link on the card). Wider than the cooktop, deep enough to cover the front burners, low, hemmed in at the sides (the oven
# tower on the north, a wood cheek on the south), an open box above it to hold the smoke while the fan catches up, and a power pack
# insert with a heat sensor so it runs every time someone cooks. Nothing to store inside it.
HOOD = K.get("hood", {})
HU0, HU1 = HOOD.get("span", [44.5, 49.0])          # along the west wall: from the oven tower's side to 6-1/2 in past the cooktop's south edge
HD_ = HOOD.get("depth_in", 24) / 12
HB = CTR_Z + HOOD.get("above_counter_in", 27) / 12  # underside of the front edge
HT_ = HB + HOOD.get("box_height_in", 24) / 12
CHK = HOOD.get("cheek_drop_in", 6) / 12           # the south cheek hangs this far below the front edge
WT = 0.06
VIDEO = ["Video Maxwell picked: kitchen hood design", "https://www.youtube.com/watch?v=Qs4wis82NAE"]
rec("kitchen.hood", "fixture", "Range hood", "interior", room="Kitchen",
    info=dict(model="Hidden hood: fake white oak cabinet doors over a power pack insert with a heat sensor (Broan PM600SSV suggested)",
              specs=[["Width", f"{ftin(HU1 - HU0)} (cooktop 30-11/16 in)"], ["Depth", f"{ftin(HD_)}, covers the front burners"],
                     ["Underside", f"{ftin(HB - CHK)} above the floor, {round((HB - CHK - CTR_Z) * 12)} in above the cooktop"],
                     ["Sides", f"Oven tower on the north, an end panel on the south; a level {round(CHK * 12)} in valance runs under the doors and round the end"],
                     ["Fan", "Inside the hood, about 0.5 sone on normal, turns itself on and off by sensing heat. 8 in duct out the west wall"]],
              links=[VIDEO],
              notes=["Designed to the advice in the video Maxwell picked (11/20/2026): wider than the cooktop (36 in minimum for a 30 in cooktop, wider is better), "
                     "24 in deep so it covers the front burners, mounted low, sides hemmed in so smoke can only be pushed back toward the wall and up, a big "
                     "inverted bathtub to catch it, quiet enough to run every time, real HVI certified airflow, and it turns on by itself.",
                     "Nothing inside the hood: no shelf, oil or spices. Anything in there gets coated in grease within a week.",
                     "No microwave hood. The microwave lives elsewhere.",
                     "The bottom edge is 24 in over the cooktop, the insert's minimum. Mock it up in cardboard first to check head height for the tallest cook.",
                     "Hidden behind two fixed shaker doors that match the kitchen, with the oven tower's crown carried across (Maxwell, 11/20/2026). "
                     "The doors do not open: behind them is the capture box, lined with stainless. A plain drywall chase above the crown hides the duct.",
                     "Hide the drywall and walls layers to see the duct."]))
# Four looks over the same capture box (Maxwell, 11/20/2026: "very boxy", try 3 or 4 designs). Every style keeps the
# same 54 x 24 in footprint, the 27 in underside, the 24 in tall box and the south cheek, so the airflow is the same.
#   box       plain white oak box and chimney (first version)
#   plaster   sloped front in warm limewash plaster, full width to the ceiling, white oak lip
#   oak       white oak with a 45 degree chamfer into a tapered chimney and black steel straps
#   cabinets  painted hood (island green) with shallow white oak glass door cabinets above it, lit inside
#   steel     blackened steel, sloped front, satin brass band along the bottom edge, slim steel chimney
#   stainless number 4 in appliance stainless with a level lip all round the bottom
#   doors     hidden: fake white oak shaker doors and the oven tower crown carried across, drywall chase above (Maxwell's pick)
FARM = None
WRAP = None
import os as _os
HSTYLE = _os.environ.get("HOOD_STYLE") or HOOD.get("style", "box")
MATERIALS.setdefault("Hood Plaster", dict(color="#E9E2D4", rough=0.9, map="plaster.jpg", tile=1.2))
MATERIALS.setdefault("Hood Steel", dict(color="#1E2021", rough=0.45, metal=0.7))
_cc = (cy0 + cy1) / 2
WX0 = RUNS["west"]["back"]
def _P(u, d, z): return (WX0 + d, u, z)
def ceil_at(u): return south_roof_z(u) - 0.03         # just under the drywall ceiling, so the faces do not flicker
def slab(mat, u0, u1, prof):                       # four point (d, z) profile pushed along the wall from u0 to u1
    hexa(mat, [_P(u0, d, z) for d, z in prof] + [_P(u1, d, z) for d, z in prof])
def to_ceiling(mat, u0, u1, d0, d1, z0):           # a box from z0 up to the sloping ceiling
    hexa(mat, [_P(u0, d0, z0), _P(u0, d1, z0), _P(u0, d1, ceil_at(u0)), _P(u0, d0, ceil_at(u0)),
               _P(u1, d0, z0), _P(u1, d1, z0), _P(u1, d1, ceil_at(u1)), _P(u1, d0, ceil_at(u1))][::1])
def liner(top=HT_ - WT, d_top=HD_ - WT, z_front=None):
    """stainless lining of the capture box. d_top: how far out the underside of the top reaches (less under a sloped front);
    z_front: how high the lining behind the front and on the cheek goes (the top of the vertical part of a sloped front)."""
    zf = top if z_front is None else z_front
    wr.box("Stainless", HU0, HU1 - WT, 0, d_top, top - 0.02, top)                                       # underside of the capture box
    wr.box("Stainless", HU0, HU1 - WT, HD_ - WT - 0.02, HD_ - WT, HB + 0.02, zf - 0.02)                  # behind the front
    wr.box("Stainless", HU1 - WT - 0.02, HU1 - WT, 0, HD_ - WT - 0.02, HB - CHK + 0.02, zf - 0.02)      # on the cheek
def d_on(z, a, b):                                 # d of the line from a = (d, z) to b = (d, z), at height z
    return a[0] + (z - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
def pucks(z, d=HD_ / 2, n=3):                      # LED puck lights in the underside of the box
    for k in range(n):
        uu = HU0 + (HU1 - HU0) * (k + 0.5) / n
        cyl("Lamp Glass", WX0 + d, uu, z - 0.03, z - 0.01, 0.12, 0.12)

if HSTYLE == "doors":
    # Hidden hood (Maxwell, 11/20/2026: "fake cabinet doors, the best hidden way"). From the room it reads as one more white
    # oak upper: two shaker fronts that match the kitchen, the oven tower's crown carried straight across, and an end panel on
    # the south side that drops 6 in lower. The doors are fixed. Behind them is the capture box, taller than before because it
    # now runs right up under the crown, with the power pack at its top, a stainless lining and LED lights in the underside.
    # Above the crown the duct rises in a plain drywall chase, painted like the wall, to the exit high in the west wall.
    rdoor = BYID["kitchen.hood"]
    CRN0, CRN1 = TALL - 0.25, TALL                 # the crown band, level with the oven tower's
    wr.box(K_WOOD := "Cabinet Wood", HU0, HU1, 0, HD_, CRN0 - WT, CRN0)                                 # top of the box
    wr.box(K_WOOD, HU0, HU1 - WT, HD_ - WT, HD_, HB, CRN0 - WT)                                         # face frame behind the doors
    wr.box(K_WOOD, HU1 - WT, HU1, 0, HD_ + FRONT_T, HB - CHK, CRN0)                                      # south end panel
    wr.box(K_WOOD, HU0, HU1 - WT, HD_ - WT, HD_ + FRONT_T, HB - CHK, HB)                                  # valance: one level band under the doors, flush with them, the same depth as the end panel (Maxwell, 11/20/2026)
    um = (HU0 + HU1 - WT) / 2
    shaker(wr, rdoor, HU0, um, HB, CRN0, HD_, K_WOOD, "door", "L")
    shaker(wr, rdoor, um, HU1 - WT, HB, CRN0, HD_, K_WOOD, "door", "R")
    wr.box(K_WOOD, HU0, HU1 + 0.05, 0, BASE_D + 0.22, CRN0, CRN1)                                        # crown, carried on from the oven tower
    liner(top=CRN0 - WT); pucks(CRN0 - WT - 0.02, d=1.2, n=3)
    wr.box("Stainless", HU0, HU1 - WT, HD_ - WT - 0.02, HD_ - WT, HB - CHK + 0.02, HB + 0.02)             # lining behind the valance
    wr.box("Lamp Glass", HU0 + 0.1, HU1 - 0.16, HD_ - 0.2, HD_ - 0.12, HB - CHK + 0.005, HB - CHK + 0.03)  # LED strip just inside the bottom edge
    to_ceiling("Drywall", _cc - 0.6, _cc + 0.6, 0, 1.2, CRN1)                                              # drywall chase for the duct
elif HSTYLE == "plaster":
    SL0, SL1 = HB + 0.42, 9.0                      # the slope runs from just above the lip back to 12 in off the wall
    DT = 1.0
    wr.box("White Oak", HU0, HU1, HD_ - WT, HD_ + 0.02, HB, SL0)                                         # oak lip
    slab("Hood Plaster", HU0, HU1, [(HD_ - WT, SL0), (HD_, SL0), (DT, SL1), (DT - WT, SL1)])             # sloped front
    to_ceiling("Hood Plaster", HU0, HU1, DT - WT, DT, SL1)                                               # upper front
    wr.box("Hood Plaster", HU1 - WT, HU1, 0, HD_, HB - CHK, SL0)                                          # south side, lower
    slab("Hood Plaster", HU1 - WT, HU1, [(0, SL0), (HD_ - WT, SL0), (DT - WT, SL1), (0, SL1)])           # south side, sloped
    to_ceiling("Hood Plaster", HU1 - WT, HU1, 0, DT - WT, SL1)                                            # south side, upper
    to_ceiling("Hood Plaster", HU0, HU0 + WT, 0, DT - WT, 8.0)                                            # north side above the oven tower
    liner(d_top=d_on(HT_ - WT, (HD_ - WT, SL0), (DT - WT, SL1)) - 0.02, z_front=SL0); pucks(HT_ - WT - 0.02, d=0.8)
elif HSTYLE == "oak":
    CH = 0.5                                       # 6 in chamfer along the top front edge
    K_WOOD = "Cabinet Wood"
    wr.box(K_WOOD, HU0, HU1 - WT, HD_ - WT, HD_, HB, HT_ - CH)                          # front
    slab(K_WOOD, HU0, HU1, [(HD_ - WT, HT_ - CH), (HD_, HT_ - CH), (HD_ - CH, HT_), (HD_ - CH - WT * 1.4, HT_)])   # chamfer
    wr.box(K_WOOD, HU0, HU1, 0, HD_ - CH, HT_ - WT, HT_)                                                  # top
    wr.box(K_WOOD, HU1 - WT, HU1, 0, HD_, HB - CHK, HT_ - CH)                                             # south cheek
    slab(K_WOOD, HU1 - WT, HU1, [(0, HT_ - CH), (HD_, HT_ - CH), (HD_ - CH, HT_), (0, HT_)])
    for zb in (HB + 0.12, HT_ - CH - 0.3):                                                                # black steel straps across the front and round the cheek
        wr.box("Hood Steel", HU0, HU1 + 0.01, HD_, HD_ + 0.012, zb, zb + 0.15)
        wr.box("Hood Steel", HU1, HU1 + 0.012, 0.02, HD_ + 0.012, zb, zb + 0.15)
        for uu in (HU0 + 0.25, _cc - 1.2, _cc + 1.2, HU1 - 0.25):
            wr.box("Black Metal", uu - 0.02, uu + 0.02, HD_ + 0.012, HD_ + 0.03, zb + 0.055, zb + 0.095)
    CW0, CW1 = 1.15, 0.75                          # chimney: 27 in wide at the hood, tapering to 18 in at the ceiling
    zc1 = ceil_at(_cc)
    hexa(K_WOOD, [_P(_cc - CW0, 0, HT_), _P(_cc + CW0, 0, HT_), _P(_cc + CW0, 1.25, HT_), _P(_cc - CW0, 1.25, HT_),
                  _P(_cc - CW1, 0, zc1), _P(_cc + CW1, 0, zc1), _P(_cc + CW1, 1.1, zc1), _P(_cc - CW1, 1.1, zc1)])
    wr.box("Hood Steel", _cc - CW0 + 0.03, _cc + CW0 - 0.03, 1.25 - 0.02, 1.262, HT_ + 0.15, HT_ + 0.3)
    liner(d_top=d_on(HT_ - WT, (HD_ - WT, HT_ - CH), (HD_ - CH - WT * 1.4, HT_)) - 0.02, z_front=HT_ - CH); pucks(HT_ - WT - 0.02, d=0.8)
elif HSTYLE == "cabinets":
    MATERIALS.setdefault("Hood Paint", dict(color=K["island_color"], rough=0.5))
    wr.box("Hood Paint", HU0, HU1, 0, HD_, HT_ - WT, HT_)
    wr.box("Hood Paint", HU0, HU1 - WT, HD_ - WT, HD_, HB, HT_ - WT)
    wr.box("Hood Paint", HU1 - WT, HU1, 0, HD_, HB - CHK, HT_ - WT)
    wr.box("Cabinet Pull", HU0, HU1, HD_, HD_ + 0.015, HB, HB + 0.08)                                     # brass edge along the bottom
    liner(); pucks(HT_ - WT - 0.02, n=4)
    rcab = rec("kitchen.hood_cabinets", "cabinet", "Shallow cabinets over the hood", "interior", room="Kitchen",
               info=dict(model="Two 13 in deep white oak glass door cabinets with LED strips, over the hood",
                         specs=[["Depth", "13 in"], ["Height", "1 ft 9 in, to the oven tower's top"], ["Centre", "Fixed panel hides the 8 in duct"]],
                         notes=["Above the capture box, so smoke never reaches them. Keep the dishes you use most out of here anyway, it is still the warmest spot in the kitchen."]))
    CD, CZ0, CZ1 = 13 / 12, HT_, 9.0
    for (a0, a1) in ((HU0, _cc - 0.6), (_cc + 0.6, HU1)):
        hollow(wr, a0, a1, CD, CZ0, CZ1, "Cabinet Wood", shelves=[(CZ0 + CZ1) / 2])
        wr.box("Lamp Glass", a0 + 0.1, a1 - 0.1, CD - 0.2, CD - 0.12, CZ1 - 0.1, CZ1 - 0.07)                # LED strip at the top of each
        wr.box("Lamp Glass", a0 + 0.1, a1 - 0.1, CD - 0.2, CD - 0.12, (CZ0 + CZ1) / 2 - 0.04, (CZ0 + CZ1) / 2 - 0.01)
        doors(wr, rcab, a0, a1, CZ0, CZ1, CD, "Cabinet Wood", 1, glass=True)
    wr.box("Cabinet Wood", _cc - 0.6, _cc + 0.6, 0, CD + FRONT_T, CZ0, CZ1)                               # fixed panel over the duct
    wr.box("Cabinet Wood", HU0 - 0.0, HU1 + 0.05, 0, CD + 0.15, CZ1, CZ1 + 0.25)                         # crown
    CUR[0] = BYID["kitchen.hood"]["parts"]
    to_ceiling("Cabinet Wood", _cc - 0.6, _cc + 0.6, 0, 1.2, CZ1 + 0.25)                                   # chase for the duct to the wall exit
elif HSTYLE == "doors_func":
    # Working cabinet over a slim hood (Maxwell, 11/20/2026: the door version again, but with cabinets you can use, the hood
    # mostly in the band at the bottom and the duct straight out the wall). The power pack fills a 12 in oak band whose
    # underside is 24 in over the cooktop (the PM600SSV minimum), lined with stainless. Above it is an ordinary upper with two
    # doors that open: the 8 in duct rises off the back of the power pack at the back centre of the cabinet floor, turns once
    # and goes straight through the wall, left bare so it is plain how much room is left. Everything else in the cabinet is storage.
    rdoor = BYID["kitchen.hood"]
    K_WOOD = "Cabinet Wood"
    LB = CTR_Z + 24 / 12                           # underside of the band: 24 in over the cooktop
    CB = LB + 1.0                                  # 12 in band, then the cabinet floor
    CRN0, CRN1 = TALL - 0.25, TALL
    UE = HU1 - WT                                  # inside of the south end panel
    wr.box(K_WOOD, UE, HU1, 0, HD_ + FRONT_T, LB, CRN0)                                                  # south end panel, level with the band
    wr.box(K_WOOD, HU0, UE, HD_ - WT, HD_ + FRONT_T, LB, CB)                                              # the band's front: one plain level panel, flush with the doors
    hollow(wr, HU0, UE, HD_, CB, CRN0, K_WOOD, shelves=[])
    if not _os.environ.get("HOOD_DOORS_OFF"):     # renders only: leave the doors off to show inside
        doors(wr, rdoor, HU0, UE, CB, CRN0, HD_, K_WOOD, 2)
    wr.box(K_WOOD, HU0, HU1 + 0.05, 0, BASE_D + 0.22, CRN0, CRN1)                                        # crown, carried on from the oven tower
    # no chase: the bare duct and its elbow show when the doors are open, so the free space is plain (Maxwell, 11/20/2026)
    wr.box("Stainless", HU0, UE, 0, HD_ - WT, CB - 0.025, CB - 0.008)                                    # stainless underside of the band
    wr.box("Stainless", HU0, UE, HD_ - WT - 0.02, HD_ - WT, LB + 0.02, CB - 0.03)                         # lining behind the band front
    wr.box("Lamp Glass", HU0 + 0.1, UE - 0.1, HD_ - 0.2, HD_ - 0.12, LB + 0.005, LB + 0.03)              # LED strip just inside the bottom edge
    IW, ID_, IH = (UE - HU0 - 0.12), HD_ - 0.06, CRN0 - CB - 0.12
    FREE = IW * ID_ * IH - 0.75 * 1.0 * 0.95
    BYID["kitchen.hood"]["info"] = dict(
        model="Cabinet hood: a working white oak upper over a slim band that holds a Broan PM600SSV power pack (suggested)",
        specs=[["Width", f"{ftin(HU1 - HU0)}, from the oven tower to 6-1/2 in past the cooktop"], ["Depth", ftin(HD_)],
               ["Band", f"12 in tall, underside {ftin(LB)} above the floor, 24 in over the cooktop"],
               ["Cabinet", f"Two doors that open, inside about {round(IW * 12)} W x {round(ID_ * 12)} D x {round(IH * 12)} H in, about {FREE:.0f} cu ft free"],
               ["Duct", "8 in round up off the power pack at the back centre, one elbow, straight out the west wall. Left bare inside the cabinet"]],
        links=[VIDEO],
        notes=["Maxwell, 11/20/2026: the cabinet door look, but the cabinets work. Only the 12 in band at the bottom is hood.",
               "Storage: either side of the duct holds tall things (about 19 in), and in front of it about 13 in deep. Keep this cabinet for "
               "things heat will not hurt: sheet pans, cutting boards, trays. No oils or spices.",
               "Trade-off: there is no big box above the fan to hold smoke while it catches up, which the video recommends. Expect more to escape on "
               "high heat searing than with a deep hood; the heat sensor still turns it on every time.",
               "The duct could go away with the PM600SSV's rear 3-1/4 x 10 in outlet straight into the wall, at some cost in airflow."])
elif HSTYLE == "shelf_box":
    # Shelf hood (Maxwell, 11/21/2026: "a shelf with a box behind it"). A thick white oak shelf, 24 in deep, is the hood's
    # underside: 30 in over the cooktop glass, centred on the cooktop and about 6 in past it each side, so it stops short of
    # the oven tower. A white oak box against the wall sits on the shelf and holds the power pack (against the wall, its
    # faceplate flush with the shelf's stainless underside) and the 8 in duct, which turns inside and goes out the west wall.
    # The front of the shelf in front of the box is a real shelf.
    K_WOOD = "Cabinet Wood"
    SW = (30.6875 + 2 * 6) / 12                    # LG CBIH3013BE is 30-11/16 in wide; 6 in past it each side
    S0, S1 = _cc - SW / 2, _cc + SW / 2
    SB = CTR_Z + 0.035 + 30 / 12                   # underside: 30 in over the cooktop glass (Broan: 24 to 30 in)
    ST = 3 / 12                                    # shelf thickness
    BD = 14 / 12                                   # box depth off the wall
    BW = 36 / 12                                   # box width
    B0, B1 = _cc - BW / 2, _cc + BW / 2
    BT = TALL                                      # box top, level with the oven tower's top
    PW = 21.375 / 12
    lu0, lu1 = _cc - PW / 2 - 0.06, _cc + PW / 2 + 0.06
    LF = 0.12 + 11.4375 / 12 + 0.02                # front of the cutout round the power pack (against the wall), inside the box's front wall
    for (a0, a1, e0, e1) in ((S0, lu0, 0, HD_), (lu1, S1, 0, HD_), (lu0, lu1, LF, HD_)):     # the shelf, cut round the power pack
        wr.box(K_WOOD, a0, a1, e0, e1, SB, SB + ST)
        wr.box("Stainless", a0, a1, e0, e1, SB - 0.008, SB - 0.002)                          # stainless underside
    q = 0.0625                                     # 3/4 in box walls
    wr.box(K_WOOD, B0, B0 + q, 0, BD, SB + ST, BT)
    wr.box(K_WOOD, B1 - q, B1, 0, BD, SB + ST, BT)
    wr.box(K_WOOD, B0, B1, BD - q, BD, SB + ST, BT)
    wr.box(K_WOOD, B0 - 0.04, B1 + 0.04, 0, BD + 0.04, BT, BT + 0.08)                          # small cap
    LT = SB + 11.5 / 12                            # liner box round the power pack inside the oak box
    wr.box("Stainless", lu0, lu0 + 0.02, 0.06, LF, SB, LT); wr.box("Stainless", lu1 - 0.02, lu1, 0.06, LF, SB, LT)
    wr.box("Stainless", lu0, lu1, LF - 0.02, LF, SB, LT); wr.box("Stainless", lu0, lu1, 0.06, LF, LT, LT + 0.02)
    BYID["kitchen.hood"]["info"] = dict(
        model="Shelf hood: a white oak shelf with an oak box behind it holding a Broan PM600SSV power pack (suggested)",
        specs=[["Width", f"{ftin(SW)}, centred on the cooktop, about 6 in past it each side; {round((S0 - HU0) * 12)} in clear of the oven tower"],
               ["Depth", f"Shelf {ftin(HD_)}, box {round(BD * 12)} in"], ["Underside", f"30 in over the cooktop glass, {ftin(SB)} above the floor (Broan: 24 to 30 in)"],
               ["Box", f"{round(BW * 12)} in wide, up to the oven tower's top at {ftin(BT)}"],
               ["Fan", "Against the wall in the box, faceplate flush with the shelf's stainless underside, 8 in duct up, one elbow, out the west wall"]],
        links=[VIDEO],
        notes=["Maxwell, 11/21/2026: a shelf with a box behind it, 30 in over the cooktop, narrower so it does not touch the oven tower, centred.",
               "The front 10 in of the shelf is a usable shelf, but it sits over the cooktop: heat proof things only.",
               "Trade-off: a flat shelf with no sides holds less smoke than a box hood, and 30 in is Broan's highest mount. The heat sensor still turns it on."])
elif HSTYLE == "shelf_wrap":
    # Wraparound shelf hood (Maxwell, 11/21/2026). The lower open shelf runs from the sink wall round the corner and along the
    # cooktop wall to the oven tower, its underside level with the hood: 30 in over the cooktop glass. Over the cooktop the same
    # shelf just gets deeper (24 in, counter depth) with a smooth transition, and the power pack drops into it, faceplate flush
    # with a stainless sheet on the underside. Behind it a drywall box, painted like the walls, hugs the power pack and its duct.
    # The shelf is as thin as the other shelves (1.8 in): Broan's guide has no lip, skirt or recess rule, only 24 to 30 in over the
    # cooktop, the unit inside an enclosure, and at least 1/4 in of material round the cutout for the flange screws.
    # Variants (HOOD_WRAP env or [kitchen.hood] wrap_variant):
    #   1  deep from the oven tower to 6 in past the cooktop, one S curve back to shelf depth on the south; box up just past the 8 in elbow
    #   2  deep part centred on the cooktop with S curves both sides; 3-1/4 x 10 in duct off the top, so the box is a low bump
    #   3  deep part centred, straight 45ish degree tapers both sides; the box is a slim chase to the ceiling
    import math as _m
    WV = str(_os.environ.get("HOOD_WRAP") or HOOD.get("wrap_variant", 1))
    K_WOOD = "White Oak"
    SB = CTR_Z + 0.035 + 30 / 12                   # shelf underside, 30 in over the cooktop glass
    ST = 0.15                                      # same thickness as the other open shelves
    D0, DD = K["shelves"]["depth"], HD_            # regular shelf depth, deep part (24 in)
    UC = HD - T - D0                               # west wall run ends where the sink wall shelf begins
    hw = 1.279 + 4 / 12                            # half the deep part for variants 2 and 3: cooktop half width plus 4 in
    if WV == "1":
        E = cy1 + 0.5
        def dep(u):
            if u <= E: return DD
            t = min(1.0, (u - E) / 1.0); return D0 + (DD - D0) * (1 + _m.cos(_m.pi * t)) / 2
        ks = [HU0, E] + [E + k / 12 for k in range(1, 13)] + [UC]
    else:
        L = (_cc - hw) - HU0                       # taper length: from the oven tower to the deep part, mirrored on the south
        def dep(u):
            x = abs(u - _cc)
            if x <= hw: return DD
            t = min(1.0, (x - hw) / L)
            return D0 + (DD - D0) * ((1 + _m.cos(_m.pi * t)) / 2 if WV == "2" else 1 - t)
        ks = [HU0] + [(_cc - hw) - L + L * k / 12 for k in range(1, 12)] + [_cc - hw, _cc + hw] + [_cc + hw + L * k / 12 for k in range(1, 13)] + [UC]
    PW = 21.375 / 12
    lu0, lu1 = _cc - PW / 2 - 0.06, _cc + PW / 2 + 0.06
    LF = 0.12 + 11.4375 / 12 + 0.02                # front of the cutout round the power pack, which sits against the wall
    ks = sorted(set([round(k, 4) for k in ks] + [round(lu0, 4), round(lu1, 4)]))
    SS0, SS1 = cy0 - 0.5, cy1 + 0.5                # stainless underside over the cooktop and 6 in past it
    def seg(mat, ua, ub, d0, z0, z1, dep=dep):
        hexa(mat, [_P(ua, d0, z0), _P(ua, dep(ua), z0), _P(ua, dep(ua), z1), _P(ua, d0, z1),
                   _P(ub, d0, z0), _P(ub, dep(ub), z0), _P(ub, dep(ub), z1), _P(ub, d0, z1)])
    for ua, ub in zip(ks, ks[1:]):
        cut = LF if (ua >= lu0 - 1e-4 and ub <= lu1 + 1e-4) else 0
        seg(K_WOOD, ua, ub, cut, SB, SB + ST)
        if ua >= SS0 - 0.6 and ub <= SS1 + 1.1 and dep(ua) > D0 + 0.01 or (ua >= SS0 and ub <= SS1):
            seg("Stainless", ua, ub, cut, SB - 0.008, SB - 0.002)
    # drywall box round the power pack and its duct
    q = 1 / 12                                     # 1/2 in drywall on light framing
    WG = 1.5 / 12                                  # wiggle room inside the box round the power pack (Maxwell 11/21/2026: room for error)
    BD = 0.12 + 11.4375 / 12 + WG + q
    B0, B1 = _cc - PW / 2 - WG - q, _cc + PW / 2 + WG + q
    PT = SB - 0.015 + 10.5625 / 12                 # top of the power pack
    if WV == "1":
        BT = PT + 0.25 + (0.12 + 11.4375 / 24) * 0.85 + 0.45     # just over the 8 in round elbow
    elif WV == "2":
        BT = PT + 9 / 12                           # 3-1/4 x 10 adapter and damper on top (about 2 in), a flat elbow, the duct's top 7-5/8 in over
                                                   # the unit, and about 1-1/2 in to spare under the upper shelf
    else:
        BT = None
    UP = None
    if BT:
        if WV == "2":
            # Maxwell, 11/21/2026: curve the box to match the shelves. Its sides flare back to the wall in the same S curve as the
            # shelf transitions, outside the fan's clearance, so the box reads as a soft bump between the two shelves.
            BL = 0.75
            def depb(u):
                x = abs(u - _cc) - ((B1 - B0) / 2 - q)
                if x <= 0: return BD
                t = min(1.0, x / BL); return max(0.002, BD * (1 + _m.cos(_m.pi * t)) / 2)
            wr.box("Drywall", B0 + q, B1 - q, BD - q, BD, SB + ST, BT)
            for sgn in (-1, 1):
                us = [_cc + sgn * ((B1 - B0) / 2 - q + BL * k / 10) for k in range(11)]
                for ua, ub in zip(us, us[1:]):
                    a, b = (ua, ub) if sgn > 0 else (ub, ua)
                    seg("Drywall", a, b, 0, SB + ST, BT, dep=depb)
        else:
            wr.box("Drywall", B0, B0 + q, 0, BD, SB + ST, BT)
            wr.box("Drywall", B1 - q, B1, 0, BD, SB + ST, BT)
            wr.box("Drywall", B0 + q, B1 - q, BD - q, BD, SB + ST, BT)
        if WV == "2":
            # Maxwell, 11/21/2026: the upper shelf comes down onto the box and runs right over it, so the box hides between the two
            # shelves. Over the box the upper shelf gets 1 in deeper than the box, with the same S curves as the lower shelf.
            UP = BT
            hb, DU = (B1 - B0) / 2 + 1 / 12, BD + 1 / 12
            def dep2(u):
                x = abs(u - _cc)
                if x <= hb: return DU
                t = min(1.0, (x - hb) / 0.75); return D0 + (DU - D0) * (1 + _m.cos(_m.pi * t)) / 2
            k2 = sorted(set([HU0, _cc - hb - 0.75, _cc - hb, _cc + hb, _cc + hb + 0.75, UC]
                            + [_cc - hb - 0.75 * k / 8 for k in range(1, 8)] + [_cc + hb + 0.75 * k / 8 for k in range(1, 8)]))
            for ua, ub in zip(k2, k2[1:]):
                seg(K_WOOD, ua, ub, 0, UP, UP + ST, dep=dep2)
        else:
            wr.box("Drywall", B0, B1, 0, BD, BT, BT + q)
    else:
        to_ceiling("Drywall", B0, B0 + q, 0, BD, SB + ST)
        to_ceiling("Drywall", B1 - q, B1, 0, BD, SB + ST)
        to_ceiling("Drywall", B0 + q, B1 - q, BD - q, BD, SB + ST)
    LT = SB + 11.5 / 12                            # stainless liner round the power pack inside the box
    wr.box("Stainless", lu0, lu0 + 0.02, 0.06, LF, SB, LT); wr.box("Stainless", lu1 - 0.02, lu1, 0.06, LF, SB, LT)
    wr.box("Stainless", lu0, lu1, LF - 0.02, LF, SB, LT); wr.box("Stainless", lu0, lu1, 0.06, LF, LT, LT + 0.02)
    WRAP = dict(lo=SB, box=(B0, B1), uc=UC, up=UP, big=[(_cc - hw, SB - 0.009), (_cc + hw, SB - 0.009)] if WV != "1" else [])
    vtxt = {"1": "deep from the oven tower to 6 in past the cooktop, one S curve back to shelf depth on the south; 8 in round duct, box just over the elbow",
            "2": "deep part centred on the cooktop with S curves both sides; 3-1/4 x 10 in duct, so the box is a low bump with the upper shelf running right over it",
            "3": "deep part centred on the cooktop with straight tapers both sides; the box is a slim chase to the ceiling"}[WV]
    BYID["kitchen.hood"]["info"] = dict(
        model=f"Wraparound shelf hood {WV}: the lower white oak shelf runs to the oven tower and gets deeper over the cooktop, a drywall box hugs a Broan PM600SSV power pack (suggested)",
        specs=[["Shelf", f"{round(ST * 12, 1)} in thick like the other shelves, {round(D0 * 12, 1)} in deep, {round(DD * 12)} in over the cooktop"],
               ["Underside", f"30 in over the cooktop glass, {ftin(SB)} above the floor, stainless sheet over the cooktop (Broan: 24 to 30 in)"],
               ["Box", f"Drywall painted like the walls, {round((B1 - B0) * 12)} W x {round(BD * 12)} D in" + (f", up to {ftin(BT + (0 if UP else q))}" + (", sides curved back to the wall like the shelves, the upper shelf sits on it" if UP else "") if BT else ", up to the ceiling")],
               ["Version", vtxt]],
        links=[VIDEO],
        notes=["Maxwell, 11/21/2026: the shelves wrap round the kitchen to the ovens and line up with the hood, the hood is just a deeper part of the "
               "shelf, and a minimal box the colour of the wall holds the power pack.",
               "Broan's PM400/600SSV guide has no rule on a lip, skirt, recess or hood size round the insert: the bottom of the hood 24 in minimum and 30 in "
               "recommended maximum over the cooktop, centred side to side over the burners, the unit inside an enclosure, its flange screwed up into at least "
               "1/4 in of material round the cutout, and a metal liner under 30 in. So the lip can be the shelf itself.",
               "Broan also says never use the unit itself as a shelf: keep things off the deep part over the fan.",
               "Trade-off: a flat shelf with nothing hanging down holds less smoke than a box hood, and 30 in is the highest mount. The heat sensor still turns it on."]
              + (["The 3-1/4 x 10 in duct (adapter on top of the unit) keeps the box low, but moves less air than 8 in round, which the video recommends."] if WV == "2" else []))
elif HSTYLE == "doors_flush":
    # Doors level with the oven tower's (Maxwell, 11/20/2026: "bottom of the doors level with the other cabinets ... seamless").
    # The hood cabinet's doors run from the tower's upper door line to the crown, so the two read as one row. The power pack
    # drops into the cabinet floor (the way Broan's cabinet install works) inside a stainless liner box at the back centre;
    # the rest of the cabinet is storage. HOOD_LIP (in) adds a level oak lip under the doors to bring the fan lower.
    rdoor = BYID["kitchen.hood"]
    K_WOOD = "Cabinet Wood"
    DB = K.get("oven_face_bottom", 1.22) + K.get("oven_face_height_in", 50.75) / 12 + 0.02   # the tower's upper door line
    LIP = float(_os.environ.get("HOOD_LIP", HOOD.get("lip_in", 0))) / 12
    LB = DB - LIP                                  # underside of the hood
    CRN0, CRN1 = TALL - 0.25, TALL
    UE = HU1 - WT
    wr.box(K_WOOD, UE, HU1, 0, HD_ + FRONT_T, LB, CRN0)                                                  # south end panel
    if LIP:
        wr.box(K_WOOD, HU0, UE, HD_ - WT, HD_ + FRONT_T, LB, DB)                                          # level lip under the doors
        wr.box("Stainless", HU0, UE, HD_ - WT - 0.012, HD_ - WT - 0.004, LB + 0.004, DB - 0.004)          # stainless lining: behind the lip,
        wr.box("Stainless", UE - 0.012, UE - 0.004, 0, HD_ - WT - 0.004, LB + 0.004, DB - 0.004)           # inside the end panel,
        wr.box("Stainless", HU0 + 0.004, HU0 + 0.012, 0, HD_ - WT - 0.004, LB + 0.004, DB - 0.004)         # against the oven tower side (Maxwell 11/20/2026: line it in stainless)
    PW = 21.375 / 12                               # Broan PM600SSV: 21-3/8 W x 10-9/16 H x 11-7/16 D
    lu0, lu1 = _cc - PW / 2 - 0.06, _cc + PW / 2 + 0.06
    IB = HOOD.get("insert_setback_in", 1.44) / 12        # back of the power pack off the wall
    LF = IB + 11.4375 / 12 + 0.05                  # front of the cutout and the liner box
    ct = 0.06                                      # the case, as hollow() builds it, but with the floor cut round the power pack
    wr.box(K_WOOD, HU0, UE, 0, ct, DB, CRN0)
    for (b0, b1) in ((HU0, HU0 + ct), (UE - ct, UE)):
        wr.box(K_WOOD, b0, b1, ct, HD_, DB, CRN0)
    wr.box(K_WOOD, HU0 + ct, UE - ct, ct, HD_, CRN0 - ct, CRN0)
    for (b0, b1, e0, e1) in ((HU0 + ct, lu0, ct, HD_), (lu1, UE - ct, ct, HD_), (lu0, lu1, LF, HD_), (lu0, lu1, ct, IB - 0.05)):
        wr.box(K_WOOD, b0, b1, e0, e1, DB, DB + ct)
    for (b0, b1, e0, e1) in ((HU0, lu0, 0, HD_), (lu1, UE, 0, HD_), (lu0, lu1, LF, HD_), (lu0, lu1, 0, IB - 0.05)):   # stainless sheet on the underside: the cooktop
        wr.box("Stainless", b0, b1, e0, e1 - (WT if LIP and e1 == HD_ else 0), DB - 0.012, DB - 0.004)          # wants wood over it under 30 in protected
    if not _os.environ.get("HOOD_DOORS_OFF"):
        um, MS = (HU0 + UE) / 2, 1.5 / 12           # a fixed 1-1/2 in centre stile between the doors (Maxwell 11/20/2026)
        wr.box(K_WOOD, um - MS / 2, um + MS / 2, HD_ - WT, HD_ + FRONT_T, DB, CRN0)
        shaker(wr, rdoor, HU0, um - MS / 2, DB, CRN0, HD_, K_WOOD, "door", "L", moves="door")
        shaker(wr, rdoor, um + MS / 2, UE, DB, CRN0, HD_, K_WOOD, "door", "R", moves="door")
        rdoor["ops"][-2]["angle"] = 90 if rdoor["ops"][-2]["angle"] > 0 else -90   # the north door stops square, clear of the deeper oven tower
    wr.box(K_WOOD, HU0, HU1 + 0.05, 0, BASE_D + 0.22, CRN0, CRN1)                                        # crown, carried on from the oven tower
    LT = DB + 11.0 / 12                            # top of the liner box round the power pack, whose faceplate is flush with the underside
    lb = IB - 0.05                                 # liner box: two sides, back, front, top, round the power pack
    wr.box("Stainless", lu0, lu0 + 0.02, lb, LF, DB + 0.004, LT)
    wr.box("Stainless", lu1 - 0.02, lu1, lb, LF, DB + 0.004, LT)
    wr.box("Stainless", lu0, lu1, LF - 0.02, LF, DB + 0.004, LT)
    if lb > 0.1: wr.box("Stainless", lu0, lu1, lb, lb + 0.02, DB + 0.07, LT)
    wr.box("Stainless", lu0, lu1, lb, LF, LT, LT + 0.02)
    above = round((LB - CTR_Z) * 12, 1)
    IW, ID_, IH = (UE - HU0 - 0.12), HD_ - 0.06, CRN0 - DB - 0.12
    FREE = IW * ID_ * IH - (lu1 - lu0) * 1.06 * (LT - DB) - 0.75 * 1.0 * 0.9
    BYID["kitchen.hood"]["info"] = dict(
        model="Cabinet hood, doors level with the oven tower's: a working white oak upper with a Broan PM600SSV power pack in its floor (suggested)",
        specs=[["Width", f"{ftin(HU1 - HU0)}, from the oven tower to 6-1/2 in past the cooktop"], ["Depth", ftin(HD_)],
               ["Underside", f"{ftin(LB)} above the floor, {above} in over the cooktop (Broan: 24 to 30 in)"],
               ["Cabinet", f"Two doors that open, about {round(IW * 12)} W x {round(ID_ * 12)} D x {round(IH * 12)} H in inside, about {FREE:.0f} cu ft free"],
               ["Fan", "In a stainless liner box in the cabinet floor, centred over the cooktop side to side and front to back, 8 in duct up, one elbow, straight out the west wall"]],
        links=[VIDEO],
        notes=["Maxwell, 11/20/2026: the doors line up with the oven tower's upper doors so the row looks seamless.",
               "Broan (PM400/600SSV install guide): bottom of the hood 24 in minimum and 30 in maximum over the cooktop; under 30 in the insert must sit in a "
               "metal liner (the stainless box); centred side to side over the burners; 8 in round goes up only.",
               "Trade-off: the fan sits flush in the cabinet floor with no box below to hold smoke, and higher than the 24 in minimum, so it catches less on "
               "high heat than a deep hood. The heat sensor still turns it on every time.",
               "Lined in stainless (Maxwell, 11/20/2026): the cabinet's whole underside and the inside of the lip, so no bare wood faces the cooktop "
               "(cooktop makers usually want 30 in to unprotected wood above). Worth a look at the LG installation manual too.",
               "Keep heat proof things in this cabinet (sheet pans, boards, trays), not oils or spices."])
elif HSTYLE == "farmhouse":
    # Farmhouse hood (Maxwell, 11/20/2026, from two photos he sent): a painted hood that tapers in on the front and both sides,
    # sitting on a white oak mantel beam (the cabinet and window oak) with a slim curved corbel under each end. The beam's
    # underside is 30 in over the cooktop (his number, also the PM600SSV's recommended maximum). An oak band trims the top.
    # The open shelves wrap round from the sink wall into the hood's south side, and a short shelf joins it to the oven tower.
    # No chimney is needed for the duct: it turns once inside the hood and goes straight out the west wall. Variants
    # (HOOD_FARM env or [kitchen.hood] farm_variant) try paint, taper and what happens above the top:
    #   top     "cab" = level with the cabinet tops (8 ft), a height in ft, or "ceiling" (taper all the way up)
    #   chim    None, or (width in, depth in, paint) for a straight chimney from the top to the ceiling
    FV = {
        "1": dict(paint="wall", top="cab", tw=30, td=14, chim=None),
        "2": dict(paint="sage", top="cab", tw=30, td=14, chim=None),
        "3": dict(paint="wall", top="ceiling", tw=20, td=12, chim=None),
        "4": dict(paint="sage", top="cab", tw=30, td=16, chim=(20, 12, "sage")),
        "5": dict(paint="wall", top=9.25, tw=22, td=12, chim=None),
        "6": dict(paint="sage", top="cab", tw=28, td=14, chim=(24, 14, "wall")),
        "7": dict(paint="steel", top="cab", tw=30, td=14, chim=None),                 # Maxwell 11/20/2026: try it in stainless
        "8": dict(paint="steel", top="ceiling", tw=20, td=12, chim=None),
        "9": dict(paint="plaster", top="ceiling", tw=40, td=23, chim=None),           # straight plaster box to the ceiling, no slopes
        "10": dict(paint="wall", top="cab", tw=30, td=14, chim=("flush", None, "wall")),   # 1 with a straight chimney flush with the oak band's outer edges
        "11": dict(paint="oak", top="cab", tw=40, td=23, chim=None),               # 9 stopped at cabinet height, all white oak
    }
    V = FV[_os.environ.get("HOOD_FARM") or str(HOOD.get("farm_variant", 1))]
    MATERIALS.setdefault("Hood Sage", dict(color="#7B8770", rough=0.8))   # Sherwin-Williams Dried Thyme, the sink window's paint
    MATERIALS.setdefault("Hood Stainless", dict(color="#C4C6C7", rough=0.5, metal=0.55))
    PAINT = {"wall": "Drywall", "sage": "Hood Sage", "steel": "Hood Stainless", "plaster": "Hood Plaster", "oak": "White Oak"}
    PL, OAK = PAINT[V["paint"]], "White Oak"
    FW = HOOD.get("farm_width_in", 42) / 12        # 42 in (Maxwell 11/20/2026: slimmer corbels, so pull the hood in and give the north shelf more room)
    FU0, FU1 = _cc - FW / 2, _cc + FW / 2
    FB = CTR_Z + 30 / 12                           # underside of the beam, 30 in over the cooktop
    BH, BF = 5 / 12, 3.5 / 12                      # beam height, depth of its front piece
    ZB = FB + BH                                   # the paint starts on top of the beam
    if V["top"] == "cab": ZT = TALL
    elif V["top"] == "ceiling": ZT = min(ceil_at(FU0), ceil_at(FU1))
    else: ZT = V["top"]
    IN = 1 / 12                                    # the paint sits this far in from the beam's ends and front
    TW, TD = V["tw"] / 12, V["td"] / 12
    def a0(z): t = (z - ZB) / (ZT - ZB); return FU0 + IN + t * ((_cc - TW / 2) - (FU0 + IN))
    def a1(z): return 2 * _cc - a0(z)
    def df(z): t = (z - ZB) / (ZT - ZB); return HD_ - IN + t * (TD - (HD_ - IN))
    wr.box(OAK, FU0, FU1, HD_ - BF, HD_, FB, ZB)                         # mantel beam: front piece and two ends, open over the power pack
    for u0, u1 in ((FU0, FU0 + 0.25), (FU1 - 0.25, FU1)):
        wr.box(OAK, u0, u1, 0, HD_ - BF, FB, ZB)
    ZC = FB + 15 / 12                              # top of the open capture box
    z0 = ZB - 0.01
    hexa(PL, [_P(a0(z0), df(z0) - WT, z0), _P(a0(z0), df(z0), z0), _P(a0(ZC), df(ZC), ZC), _P(a0(ZC), df(ZC) - WT, ZC),
              _P(a1(z0), df(z0) - WT, z0), _P(a1(z0), df(z0), z0), _P(a1(ZC), df(ZC), ZC), _P(a1(ZC), df(ZC) - WT, ZC)])
    for s in (1, -1):
        def ux(z, inner): return (a0(z) + (WT if inner else 0)) if s > 0 else (a1(z) - (0 if inner else WT))
        hexa(PL, [_P(ux(z0, 0), 0, z0), _P(ux(z0, 0), df(z0) - WT, z0), _P(ux(ZC, 0), df(ZC) - WT, ZC), _P(ux(ZC, 0), 0, ZC),
                  _P(ux(z0, 1), 0, z0), _P(ux(z0, 1), df(z0) - WT, z0), _P(ux(ZC, 1), df(ZC) - WT, ZC), _P(ux(ZC, 1), 0, ZC)])
    BT = 3 / 12                                    # oak band round the top: 3 in tall, 3/4 in proud
    ZT_ = ZT - 0.1
    hexa(PL, [_P(a0(ZC), 0, ZC), _P(a0(ZC), df(ZC), ZC), _P(a0(ZT_), df(ZT_), ZT_), _P(a0(ZT_), 0, ZT_),
              _P(a1(ZC), 0, ZC), _P(a1(ZC), df(ZC), ZC), _P(a1(ZT_), df(ZT_), ZT_), _P(a1(ZT_), 0, ZT_)])
    wr.box(OAK, a0(ZT - BT) - 0.06, a1(ZT - BT) + 0.06, 0, df(ZT - BT) + 0.06, ZT - BT, ZT)
    if V["chim"]:
        cw, cd, cp = V["chim"]
        zc0 = ZT - 0.05
        if cw == "flush":                          # right out to the oak band's edges, standing on it
            cw, cd, zc0 = (a1(ZT - BT) - a0(ZT - BT) + 0.12) * 12, (df(ZT - BT) + 0.06) * 12, ZT
        V["chim_wd"] = (round(cw), round(cd))
        to_ceiling(PAINT[cp], _cc - cw / 24, _cc + cw / 24, 0, cd / 12, zc0)
        wr.box(OAK, _cc - cw / 24 - 0.05, _cc + cw / 24 + 0.05, 0, cd / 12 + 0.05, ceil_at(_cc + cw / 24) - 0.2, ceil_at(_cc + cw / 24) - 0.04)   # oak band at the ceiling
    wr.box("Stainless", a0(ZC) + WT, a1(ZC) - WT, 0, df(ZC) - WT, ZC - 0.025, ZC - 0.008)   # stainless top of the capture box
    import math as _m                              # slim curved corbels under the beam ends: 1-3/4 in thick, 12 in tall, 10 in out
    CH, CD, CMIN = 12 / 12, 10 / 12, 1.5 / 12
    pts = [(CD - (CD - CMIN) * _m.cos(_m.pi / 2 * k / 10), FB - CH + CH * _m.sin(_m.pi / 2 * k / 10)) for k in range(11)]
    pts[-1] = (pts[-1][0], FB - 0.002)
    for u0, u1 in ((FU0 + 0.05, FU0 + 0.05 + 1.75 / 12), (FU1 - 0.05 - 1.75 / 12, FU1 - 0.05)):
        for (d0_, zz0), (d1_, zz1) in zip(pts, pts[1:]):
            slab(OAK, u0, u1, [(0, zz0), (d0_, zz0), (d1_, zz1), (0, zz1)])
    pucks(ZC - 0.03, d=HD_ - 0.6, n=2)
    FARM = dict(lo=FB, beam=(FU0, FU1, ZB), side=lambda z, s: (a1(z) if s > 0 else a0(z)))
    top_txt = {"cab": "level with the cabinet tops at 8 ft", "ceiling": "tapering all the way to the ceiling"}.get(V["top"], f"at {ftin(ZT)}")
    BYID["kitchen.hood"]["info"] = dict(
        model=f"Farmhouse hood: {dict(sage='tapered, painted Dried Thyme sage', wall='tapered, painted to match the walls', steel='tapered brushed stainless', plaster='a straight plaster box to the ceiling', oak='a straight white oak box')[V['paint']] if V['tw'] < 40 or V['paint'] != 'plaster' else 'a straight plaster box to the ceiling'}, white oak mantel beam, "
              "curved corbels and oak band at the top, over a Broan PM600SSV power pack (suggested)",
        specs=[["Width", f"{ftin(FW)} at the beam, tapering to {ftin(TW)} (cooktop 30-11/16 in)"], ["Depth", f"{ftin(HD_)} at the beam, {ftin(TD)} at the top"],
               ["Underside", f"{ftin(FB)} above the floor, 30 in above the cooktop"],
               ["Top", top_txt + (f", then a {V['chim_wd'][0]} x {V['chim_wd'][1]} in chimney to the ceiling" if V["chim"] else "")],
               ["Fan", "Power pack inside, about 0.5 sone on normal, turns itself on by sensing heat. 8 in duct up, one elbow, straight out the west wall"]],
        links=[VIDEO],
        notes=["Mocked up from two photos Maxwell sent (11/20/2026): a painted hood tapering on three sides, a wood mantel beam and curved supports, "
               "in the same white oak as the cabinets and windows.",
               "30 in over the cooktop is the PM600SSV's recommended maximum (24 to 30 in). The open shelves on either side meet the beam.",
               "The duct rises about 10 in off the power pack, turns once inside the hood and goes straight through the wall: the 8 in round outlet "
               "only points up (Broan install guide), and a short run with one elbow performs at least as well as a tall chimney.",
               "The corbels sit about 3 in from the cooktop's sides: fine for induction (no flame), but keep pan handles clear."])
elif HSTYLE.startswith("ss_"):
    # Lower, cleaner stainless shells around the Broan PM600SSV (Maxwell, 11/20/2026: the slope was too steep and looked big;
    # flatter, maybe curved, closer to the kitchen designer's square hood with a right angle into the duct cover). All 60 in
    # wide centred on the cooktop so they meet the oven tower, 24 in deep, one level bottom edge 24 in over the cooktop, a flat
    # top, and a 14 in square duct cover straight up to the ceiling. Profiles are (d, z) from the bottom front edge up to the top.
    MATERIALS.setdefault("Hood Stainless", dict(color="#C4C6C7", rough=0.5, metal=0.55))
    SS = "Hood Stainless"
    S0, S1 = _cc - 2.5, _cc + 2.5                  # 60 in, centred on the cooktop: the north end meets the oven tower
    LB = CTR_Z + 24 / 12
    if HSTYLE == "ss_box":                         # the designer's look: a straight 16 in front, flat top, right angle into the cover
        TOP = LB + 16 / 12; prof = [(HD_, LB), (HD_, TOP)]
    elif HSTYLE == "ss_low":                       # 9 in straight front, then a low 30 degree slope back to the top
        TOP = LB + 15 / 12; prof = [(HD_, LB), (HD_, LB + 9 / 12), (HD_ - 10 / 12, TOP)]
    elif HSTYLE == "ss_curve":                     # 4 in straight front rolling over in a 10 in radius curve into the flat top
        import math as _m
        RC = 10 / 12; TOP = LB + 4 / 12 + RC
        prof = [(HD_, LB), (HD_, LB + 4 / 12)] + [(HD_ - RC + RC * _m.cos(a), LB + 4 / 12 + RC * _m.sin(a)) for a in [_m.pi / 2 * k / 6 for k in range(1, 7)]]
    else:                                          # ss_chamfer: 12 in straight front, a 3 in 45 degree chamfer, flat top
        TOP = LB + 15 / 12; prof = [(HD_, LB), (HD_, LB + 12 / 12), (HD_ - 3 / 12, TOP)]
    for (d0, z0), (d1, z1) in zip(prof, prof[1:]):
        slab(SS, S0, S1, [(d0 - WT, z0), (d0, z0), (d1, z1), (d1 - WT, z1)])                              # front, piece by piece
        for (a0, a1) in ((S0, S0 + WT), (S1 - WT, S1)):                                                   # both ends follow the same outline
            slab(SS, a0, a1, [(0, z0), (d0 - WT, z0), (d1 - WT, z1), (0, z1)])
    dtop = prof[-1][0]
    wr.box(SS, S0, S1, 0, dtop, TOP - WT, TOP)                                                                # flat top
    to_ceiling(SS, _cc - 7 / 12, _cc + 7 / 12, 0, 14 / 12, TOP)                                             # 14 in square duct cover
    for k in range(3):                                                                                    # LED pucks in the underside
        cyl("Lamp Glass", WX0 + 1.4, S0 + 5 * (k + 0.5) / 3, TOP - WT - 0.03, TOP - WT - 0.01, 0.12, 0.12)
elif HSTYLE == "stainless":
    # Number 4 in stainless to match the appliances, with one level lip all the way round the bottom (Maxwell, 11/20/2026):
    # no brass band and no side panel hanging lower than the front.
    MATERIALS.setdefault("Hood Stainless", dict(color="#C4C6C7", rough=0.5, metal=0.55))   # brushed, like the oven and fridge fronts
    LB = HB - CHK                                  # bottom edge, level on the front and the side
    SL0, SL1 = HB + 0.33, HT_ + 0.6
    wr.box("Hood Stainless", HU0, HU1, HD_ - WT, HD_, LB, SL0)                                                 # front lip
    slab("Hood Stainless", HU0, HU1, [(HD_ - WT, SL0), (HD_, SL0), (1.25, SL1), (1.25 - WT, SL1)])             # sloped front
    wr.box("Hood Stainless", HU0, HU1, 0, 1.25, SL1 - WT, SL1)                                                 # top
    wr.box("Hood Stainless", HU1 - WT, HU1, 0, HD_ - WT, LB, SL0)                                              # south side lip, same bottom as the front
    slab("Hood Stainless", HU1 - WT, HU1, [(0, SL0), (HD_ - WT, SL0), (1.25 - WT, SL1), (0, SL1)])
    to_ceiling("Hood Stainless", _cc - 0.55, _cc + 0.55, 0, 1.1, SL1)                                          # slim chimney
    pucks(HT_ - WT - 0.02, d=0.8)
elif HSTYLE == "steel":
    SL0, SL1 = HB + 0.33, HT_ + 0.6
    wr.box("Cabinet Pull", HU0, HU1, HD_ - WT, HD_ + 0.02, HB, HB + 0.1)                                  # satin brass band, like the pulls
    wr.box("Hood Steel", HU0, HU1, HD_ - WT, HD_, HB + 0.1, SL0)
    slab("Hood Steel", HU0, HU1, [(HD_ - WT, SL0), (HD_, SL0), (1.25, SL1), (1.25 - WT, SL1)])
    wr.box("Hood Steel", HU0, HU1, 0, 1.25, SL1 - WT, SL1)                                                # top
    wr.box("Hood Steel", HU1 - WT, HU1, 0, HD_, HB - CHK, SL0)
    slab("Hood Steel", HU1 - WT, HU1, [(0, SL0), (HD_ - WT, SL0), (1.25 - WT, SL1), (0, SL1)])
    to_ceiling("Hood Steel", _cc - 0.55, _cc + 0.55, 0, 1.1, SL1)                                         # slim chimney
    liner(d_top=d_on(HT_ - WT, (HD_ - WT, SL0), (1.25 - WT, SL1)) - 0.02, z_front=SL0); pucks(HT_ - WT - 0.02, d=0.8)
else:
    K_WOOD = "Cabinet Wood"
    wr.box(K_WOOD, HU0, HU1, 0, HD_, HT_ - WT, HT_)        # top
    wr.box(K_WOOD, HU0, HU1 - WT, HD_ - WT, HD_, HB, HT_ - WT)                                          # front
    wr.box(K_WOOD, HU1 - WT, HU1, 0, HD_, HB - CHK, HT_ - WT)                                           # south cheek
    liner()
    wr.box(K_WOOD, _cc - 0.6, _cc + 0.6, 0, 1.2, HT_, south_roof_z(_cc + 0.6) - 0.01)                  # chimney enclosure up to the ceiling, holds the duct
ix0, iy0, ix1, iy1 = K["island"]
ir = RUNS["island"]
rec("kitchen.island", "cabinet", "Kitchen island top and panels", "interior", room="Kitchen",
    info=dict(model=f"{ftin(ix1 - ix0)} x {ftin(iy1 - iy0)} island with a {ftin(K.get('island_overhang', 1.25))} seating overhang",
              specs=[["Top", ISLAND_TOP_NAME], ["Body", FINISH(ISLAND_MAT)]], notes=["Deepened to 45\" for the overhang (Erin's redline)."]))
box(ISLAND_MAT, ir["units"][0][0], RUNS["island_east"]["back"] if "island_east" in RUNS else ir["units"][-1][1], ir["back"] - 0.06, ir["back"], 0, CTR_Z - CTR_T)
box(ISLAND_MAT, ir["units"][0][0] - 0.06, ir["units"][0][0], ir["back"] - 0.06, ir["back"] + ir.get("depth", BASE_D) + FRONT_T, 0, CTR_Z - CTR_T)
box(ISLAND_TOP, ix0, ix1, iy0, iy1, CTR_Z - CTR_T, CTR_Z)
SH = K["shelves"]
rec("kitchen.shelves", "fixture", "Open shelves", "interior", room="Kitchen", info=dict(model="White oak open shelves", specs=[["Length", ftin(SH["x"][1] - SH["x"][0])], ["Heights", ", ".join(ftin(z) for z in SH["heights"])]]))
SHZ = list(SH["heights"])
if WRAP:                                           # the lower shelf is the hood's shelf (built with the hood); the upper one wraps to the oven tower too
    SHZ[0] = WRAP["lo"]
    if WRAP["up"]: SHZ[1] = WRAP["up"]               # version 2: the upper shelf sits on the hood box (built with the hood on the cooktop wall)
if FARM:                                           # the lower shelf lines up with the hood's beam
    SHZ[0] = FARM["lo"]
for z in SHZ:
    box("White Oak", SH["x"][0], SH["x"][1], HD - T - SH["depth"], HD - T, z, z + 0.15)
    if FARM:                                       # wrapped round the corner onto the cooktop wall, into the hood's south side
        fu0, fu1, fzb = FARM["beam"]
        hs = fu1 if z < fzb else FARM["side"](z + 0.15, 1)
        hn = fu0 if z < fzb else FARM["side"](z + 0.15, -1)
        box("White Oak", WX0, WX0 + SH["depth"], hs, HD - T - SH["depth"], z, z + 0.15)
        box("White Oak", WX0, WX0 + SH["depth"], HU0, hn, z, z + 0.15)   # short shelf from the oven tower to the hood's north side
    if WRAP and z > WRAP["lo"] + 0.2 and not WRAP["up"]:              # upper shelf: from the oven tower to the box, and from the box to the corner
        wb0, wb1 = WRAP["box"]
        box("White Oak", WX0, WX0 + SH["depth"], HU0, wb0, z, z + 0.15)
        box("White Oak", WX0, WX0 + SH["depth"], wb1, WRAP["uc"], z, z + 0.15)

if WRAP:
    # Curved white oak corbels under the shelves (Maxwell, 11/21/2026: the curved supports from the farmhouse mockups). The two
    # biggest frame the hood's deep part, about 3-1/2 in clear of the cooktop's sides; smaller ones every 2 ft or so carry the rest.
    import math as _m
    CT = 1.75 / 12                                 # 1-3/4 in thick, like the farmhouse corbels
    def corbel(wall, uc, cd, ch, ztop):
        cmin = 1.5 / 12
        pts = [(cd - (cd - cmin) * _m.cos(_m.pi / 2 * k / 12), ztop - ch + ch * _m.sin(_m.pi / 2 * k / 12)) for k in range(13)]
        pts[-1] = (pts[-1][0], ztop)
        u0, u1 = uc - CT / 2, uc + CT / 2
        P = (lambda u, d, z: (WX0 + d, u, z)) if wall == "W" else (lambda u, d, z: (u, HD - T - d, z))
        for (d0_, z0_), (d1_, z1_) in zip(pts, pts[1:]):
            hexa("White Oak", [P(u0, 0, z0_), P(u0, d0_, z0_), P(u0, d1_, z1_), P(u0, 0, z1_),
                               P(u1, 0, z0_), P(u1, d0_, z0_), P(u1, d1_, z1_), P(u1, 0, z1_)])
    for (uc_, zt) in WRAP["big"]:                  # the big pair under the hood: 20 in out, 14 in tall
        corbel("W", uc_, 20 / 12, 14 / 12, zt)
    small = (8 / 12, 7 / 12)                       # the rest: 8 in out under the 10.8 in shelves, 7 in tall
    for z in SHZ:
        for x in (2.0, 4.25, 6.45):                # sink wall run, x 0.54 to 6.7
            corbel("S", x, *small, z - 0.002)
        corbel("W", 50.15, *small, z - 0.002)      # cooktop wall, between the hood and the corner
    BYID["kitchen.shelves"]["info"] = dict(model="White oak open shelves, wrapping round the kitchen from the sink wall to the oven tower",
        specs=[["Heights", ", ".join(ftin(z) for z in SHZ) + " (the lower one level with the hood's underside, the upper one on the hood box)"],
               ["Depth", f"{round(SH['depth'] * 12, 1)} in, deeper over the cooktop where the lower one is the hood"],
               ["Supports", "Curved white oak corbels, 1-3/4 in thick: a 20 in pair frames the hood, 8 in ones about every 2 ft under the rest"]],
        notes=["Maxwell, 11/21/2026: the shelves wrap round to the ovens and line up with the hood, with the curved supports from the farmhouse mockups."])

# Pantry shelves (Maxwell 11/20/2026: "simple shelving"): 3/4 in white oak on 1x2 cleats, around a chest freezer on the back wall.
# They are built in, so they live with the house; what is on them is in the Belongings layer (make_equipment.py pantry_goods).
PA = C.get("pantry")
if PA:
    px0, px1, py0, py1 = PA["inside"]
    rows = PA["layouts"][PA["layout"]]["shelves"]
    WALLN = {"W": "West wall", "E": "East wall (right as you walk in)", "N": "Back wall, over the freezer"}
    rec("pantry.shelves", "fixture", "Pantry shelves", "interior", room="Pantry",
        info=dict(model="Open white oak shelves on wall cleats, ASSUMED build",
                  specs=[[WALLN[r["wall"]], f"{r['depth']} in deep, tops at {', '.join(str(t) for t in r['tops'])} in"] for r in rows]
                        + [["Layout", f"{PA['layout']} (config [pantry] layout = right | u)"]],
                  notes=["Maxwell asked for simple shelving around the chest freezer (11/20/2026), then for a version with shelves only on the right and "
                         "on the back, deeper, so large items fit (layout right). Depths and heights are placeholders to adjust.",
                         "The back wall shelves start at 64 in so the freezer lid, about 55 in at its top when open, clears them by 8 in."]))
    TH, CL_ = 0.75 / 12, 1.5 / 12
    for row in rows:
        a0, a1 = row["run"]
        d = row["depth"] / 12
        for top in row["tops"]:
            z1 = top / 12
            z0 = z1 - TH
            if row["wall"] == "W":
                box("White Oak", px0, px0 + d, a0, a1, z0, z1)
                box("White Oak", px0, px0 + TH, a0, a1, z0 - CL_, z0)                      # back cleat
            elif row["wall"] == "E":
                box("White Oak", px1 - d, px1, a0, a1, z0, z1)
                box("White Oak", px1 - TH, px1, a0, a1, z0 - CL_, z0)
            else:
                box("White Oak", a0, a1, py0, py0 + d, z0, z1)
                box("White Oak", a0, a1, py0, py0 + TH, z0 - CL_, z0)
        if row["wall"] == "W" and a1 < py1 - 0.1:          # the west run ends in the open: a 3/4 in end panel carries the shelf ends
            box("White Oak", px0, px0 + d, a1, a1 + TH, 0, max(row["tops"]) / 12)

BD = C.get("barn_door", {})
if BD.get("enabled"):
    bx0, bx1, bhd = min(CL["passages"], key=lambda p: abs((p[0] + p[1]) / 2 - BD["center_x"]))
    lw = (bx1 - bx0) / 2 + 0.15
    lh = bhd + 0.2
    yf = YC2 + 0.12 if BD.get("side", "south") == "south" else YC - 0.25
    sgn = 1 if BD.get("side", "south") == "south" else -1
    st = 0.29
    r = rec("door.barn", "door", "Living room barn doors", "interior", room="Living",
            info=dict(model="D60-80 French barn door pair, solid white oak", specs=[["Opening", f"{ftin(bx1 - bx0)} x {ftin(bhd)}"], ["Hardware", "Black steel track and hangers"]],
                      notes=["Maxwell 11/12/2026. Hung on the dining side, ASSUMED."]))
    for side, xc in (("L", bx0 + lw / 2 - 0.15), ("R", bx1 - lw / 2 + 0.15)):
        a0, a1 = xc - lw / 2, xc + lw / 2
        yy0, yy1 = sorted((yf, yf + sgn * 0.15))
        sg = -1 if side == "L" else 1
        lf = op(r, f"door.barn.{side.lower()}", f"Barn door, {'west' if side == 'L' else 'east'} leaf", "slide", (xc, YC2 + 0.2, 0), slide=(sg * lw, 0, 0))
        with into(lf["parts"]):
            box("White Oak", a0, a0 + st, yy0, yy1, 0.05, lh)
            box("White Oak", a1 - st, a1, yy0, yy1, 0.05, lh)
            box("White Oak", a0 + st, a1 - st, yy0, yy1, lh - st, lh)
            box("White Oak", a0 + st, a1 - st, yy0, yy1, 0.05, 0.95)
            nl = int(BD.get("lites_high", 1)); zg0, zg1 = 0.95, lh - st
            for j in range(1, nl):
                zz = zg0 + (zg1 - zg0) * j / nl
                box("White Oak", a0 + st, a1 - st, yy0, yy1, zz - 0.06, zz + 0.06)
            if BD.get("panel", "oak") == "glass":
                box("Glass", a0 + st, a1 - st, yy0 + 0.06, yy1 - 0.06, zg0, zg1)
            else:
                box("White Oak", a0 + st, a1 - st, yy0 + 0.04, yy1 - 0.04, zg0, zg1)
            for hx in (a0 + 0.5, a1 - 0.5):
                box("Black Metal", hx - 0.08, hx + 0.08, yy0 - 0.02, yy1 + 0.02, lh - 0.2, lh + 0.45)
            hxp = a1 - 0.25 if side == "L" else a0 + 0.25
            box("Black Metal", hxp - 0.03, hxp + 0.03, yy0 if sgn > 0 else yy1, yy1 + 0.12 if sgn > 0 else yy0 - 0.12, 3.0, 4.5)
    tl0, tl1 = bx0 - lw - 0.3, bx1 + lw + 0.3
    ty0, ty1 = sorted((YC2 + 0.02 if sgn > 0 else YC - 0.02, YC2 + 0.1 if sgn > 0 else YC - 0.1))
    box("Black Metal", tl0, tl1, ty0, ty1, lh + 0.3, lh + 0.45)

# ------------------------------------------------------------------ interior trim: baseboards, doors, casings (build_details.py)
BB = FU.get("baseboard_height_in", 4.5) / 12
CW = FU.get("casing_width_in", 3.5) / 12
if FU.get("enabled"):
    segs = []
    for (x0, x1, y0, y1) in INT_RECTS:
        if x1 - x0 >= y1 - y0:
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

    door_u = {w_: [(o["start"], o["end"]) for o in OPEN if o["wall"] == w_ and o["sill"] < 0.2] for w_ in "NSEW"}
    segs += [("x", T, T, HW - T, 1, door_u["N"]), ("x", HD - T, T, HW - T, -1, door_u["S"]),
             ("y", T, T, HD - T, 1, door_u["W"]), ("y", HW - T, T, HD - T, -1, door_u["E"])]
    pas = [(p_[0], p_[1]) for p_ in CL["passages"]]
    segs += [("x", YC, T, HW - T, -1, pas), ("x", YC2, T, HW - T, 1, pas)]
    rec("trim.baseboard", "trim", "Baseboards", "interior", info=dict(model=f"{FU.get('baseboard_height_in', 4.5):g}\" white oak baseboard (ASSUMED)", notes=["Runs along every wall face, stopping at door openings."]))
    # no baseboard inside the shower: the wet room is tiled floor to ceiling (Maxwell, 11/21/2026: trim showed in it)
    WET_RECTS = [(it_["x0"], it_["x1"], it_["y0"], it_["y1"]) for it_ in FU.get("items", []) if it_.get("type") == "wetroom"] if FU.get("enabled") else []
    for s_ in segs:
        ax, c0, a0, a1, sgn = s_[:5]
        holes = list(s_[5]) if len(s_) > 5 else []
        for (wx0, wx1, wy0, wy1) in WET_RECTS:
            if ax == "x" and wy0 - 0.1 <= c0 <= wy1 + 0.1 and sgn == (1 if c0 < (wy0 + wy1) / 2 else -1):
                holes.append((wx0 - 0.1, wx1 + 0.1))
            if ax == "y" and wx0 - 0.1 <= c0 <= wx1 + 0.1 and sgn == (1 if c0 < (wx0 + wx1) / 2 else -1):
                holes.append((wy0 - 0.1, wy1 + 0.1))
        for (r0, r1) in cut_runs(a0, a1, holes):
            d0, d1 = sorted((c0, c0 + sgn * 0.045))
            if ax == "x":
                box("White Oak", r0, r1, d0, d1, 0, BB)
            else:
                box("White Oak", d0, d1, r0, r1, 0, BB)
    for (rx, ry) in FU.get("door_remove", []):
        def _near(g):
            ax, g0, g1, t0, t1, h = g
            cx, cy = ((g0 + g1) / 2, (t0 + t1) / 2) if ax == "x" else ((t0 + t1) / 2, (g0 + g1) / 2)
            return math.hypot(cx - rx, cy - ry) < 1.5
        DOOR_GAPS[:] = [g for g in DOOR_GAPS if not _near(g)]
    DOOR_NAMES, DOOR_NOTES, DOOR_LEAF_TOP = {}, {}, {}
    for da in FU.get("door_add", []):
        if da.get("name") == "Door, entry closet":
            if EC_STYLE in ("cabinet", "pullout", "coat", "open"):
                continue                       # a built-in fills the opening instead of a door
            da = dict(da, g0=EC_OPEN[0], g1=EC_OPEN[1])
            if EC_STYLE == "split":
                DOOR_LEAF_TOP[(da["g0"], da["g1"])] = EC.get("split_at", 6.67)
        t0_, t1_ = (YC, YC2) if da.get("t0") == "clerestory" else (da["t0"], da["t1"])
        DOOR_GAPS.append((da["axis"], da["g0"], da["g1"], t0_, t1_, da.get("head", 6.67)))
        if da.get("name"):
            DOOR_NAMES[(da["g0"], da["g1"])] = da["name"]
        if da.get("note"):
            DOOR_NOTES[(da["g0"], da["g1"])] = da["note"]
        if not da.get("header", True):         # a cased opening that already has its wall above: the door only
            continue
        rec(f"wall.header.added.{len(DOOR_GAPS)}", "wall", "Wall over a doorway", "interior", info=dict(model="Drywall over the door head", notes=[da.get("note", "")]))
        if da["axis"] == "y":
            box("Drywall", da["t0"], da["t1"], da["g0"], da["g1"], da.get("head", 6.67), FH + FLOOR_T - DECK_T)
        else:
            box("Drywall", da["g0"], da["g1"], da["t0"], da["t1"], da.get("head", 6.67), FH + FLOOR_T - DECK_T)
    nd_ = 0
    for (ax, g0, g1, t0, t1, h) in DOOR_GAPS:
        wdt = g1 - g0
        gc = ((g0 + g1) / 2, (t0 + t1) / 2) if ax == "x" else ((t0 + t1) / 2, (g0 + g1) / 2)
        pocket_dir = next((pd[2] for pd in FU.get("door_pocket", []) if math.hypot(pd[0] - gc[0], pd[1] - gc[1]) < 1.5), 0)
        lab = nearest_label(*gc)
        a_, b_ = (room_at(gc[0], t0 - 0.8), room_at(gc[0], t1 + 0.8)) if ax == "x" else (room_at(t0 - 0.8, gc[1]), room_at(t1 + 0.8, gc[1]))
        rooms = " and ".join(n_ for n_ in dict.fromkeys([a_, b_]) if n_)
        leaves = [(g0 + 0.07, g1 - 0.07)] if wdt <= 3.3 else [(g0 + 0.07, (g0 + g1) / 2 - 0.01), ((g0 + g1) / 2 + 0.01, g1 - 0.07)]
        dname = DOOR_NAMES.get((g0, g1)) or f"{'Pocket door' if pocket_dir else 'Door'}{', ' + rooms if rooms else ''}"
        r = rec(f"door.int.{nd_ + 1}", "door", dname, "interior",
                info=dict(model=f"{lab + ' ' if lab else ''}white oak {'pocket' if pocket_dir else 'slab'} door{' pair' if len(leaves) > 1 else ''}",
                          specs=[["Opening", f"{ftin(wdt)} x {ftin(h)}"], ["Hardware", "Flush pulls" if pocket_dir else "Brushed nickel levers"]],
                          notes=([DOOR_NOTES[(g0, g1)]] if (g0, g1) in DOOR_NOTES else ["Opening found where two traced A-11 wall ends line up."]) + ["Style ASSUMED (slab doors, white oak casing)."] + (["Pocket door, Maxwell 11/13/2026."] if pocket_dir else [])))

        def B(mat, a0, a1, b0, b1, z0, z1):
            if ax == "x":
                box(mat, a0, a1, b0, b1, z0, z1)
            else:
                box(mat, b0, b1, a0, a1, z0, z1)
        B("White Oak", g0, g0 + 0.06, t0, t1, 0, h); B("White Oak", g1 - 0.06, g1, t0, t1, 0, h); B("White Oak", g0, g1, t0, t1, h - 0.06, h)
        for (b0, b1) in ((t0 - 0.06, t0), (t1, t1 + 0.06)):
            B("White Oak", g0 - CW, g0 + 0.02, b0, b1, 0, h); B("White Oak", g1 - 0.02, g1 + CW, b0, b1, 0, h)
            B("White Oak", g0 - CW, g1 + CW, b0, b1, h, h + CW)
        for k_, (l0, l1) in enumerate(leaves):
            lw = l1 - l0; tm = (t0 + t1) / 2
            suffix = chr(97 + k_) if len(leaves) > 1 else ""
            if pocket_dir:
                d_ = pocket_dir * lw
                lf = op(r, f"{r['id']}.leaf{suffix}", r["name"], "slide", ((l0 + l1) / 2, tm, 0) if ax == "x" else (tm, (l0 + l1) / 2, 0),
                        slide=(d_, 0, 0) if ax == "x" else (0, d_, 0))
                with into(lf["parts"]):
                    B("White Oak", l0, l1, tm - 0.06, tm + 0.06, 0.04, h - 0.08)
                    px_ = l0 + 0.2 if pocket_dir > 0 else l1 - 0.2
                    for sgn in (-1, 1):
                        b0 = tm + sgn * 0.06; b1 = b0 + sgn * 0.01
                        B("Brushed Nickel", px_ - 0.05, px_ + 0.05, min(b0, b1), max(b0, b1), 3.0, 3.4)
            else:
                ha = l0 if k_ == 0 else l1
                sgn_ = (-1 if ax == "x" else 1) * (1 if k_ == 0 else -1)
                sw = next((s_ for s_ in FU.get("door_swing", []) if math.hypot(s_[0] - gc[0], s_[1] - gc[1]) < 1.5), None)
                if sw and len(leaves) == 1:        # hinge side and swing from the A-11 door arcs
                    ha = l1 if sw[2] in ("E", "S") else l0
                    dv = (1, 0) if ax == "x" else (0, 1)
                    if ha == l1:
                        dv = (-dv[0], -dv[1])
                    ov = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}[sw[3]]
                    sgn_ = 1 if dv[0] * (-ov[1]) - (-dv[1]) * ov[0] > 0 else -1     # turn sense in the Blender frame (y north)
                    k_ = 0 if ha == l0 else 1
                hp = (ha, tm) if ax == "x" else (tm, ha)
                lf = op(r, f"{r['id']}.leaf{suffix}", r["name"], "swing", (hp[0], hp[1], 0), angle=90 * sgn_)
                with into(lf["parts"]):
                    B("White Oak", l0, l1, tm - 0.07, tm + 0.07, 0.04, DOOR_LEAF_TOP.get((g0, g1), h) - 0.08)
                    cd_ = FU.get("cat_door")
                    if cd_ and math.hypot(cd_["at"][0] - gc[0], cd_["at"][1] - gc[1]) < 1.5:
                        # flapped cat door through the leaf (Maxwell, 11/20/2026): a frame on each face, a smoked flap inside the
                        # opening, set toward the hinge side so it clears the lever. Sizes in inches from config [furnishings].cat_door
                        fw, fh, ow, oh, zb = (v / 12 for v in (cd_["frame_w_in"], cd_["frame_h_in"], cd_["open_w_in"], cd_["open_h_in"], cd_["bottom_in"]))
                        cc = (l0 + 0.95) if k_ == 0 else (l1 - 0.95)
                        r.setdefault("info", {}).setdefault("notes", []).append(
                            f"Cat flap through the leaf for the litter box (Maxwell, 11/20/2026): about {cd_['open_w_in']:g} x {cd_['open_h_in']:g} in opening in a "
                            f"{cd_['frame_w_in']:g} x {cd_['frame_h_in']:g} in frame, {cd_['bottom_in']:g} in off the floor, toward the hinge side, clear of the lever. "
                            "Pick one rated for a solid core door this thick, with a magnetic or brush seal: the flap keeps most of the room's sound out of the hall, "
                            "and it is one of the ways the air the litter box exhaust pulls out gets back into the room. Size and model ASSUMED.")
                        for sgn in (-1, 1):
                            f0 = tm + sgn * 0.07; f1 = f0 + sgn * 0.03
                            for (a0, a1, z0, z1) in ((cc - fw / 2, cc - ow / 2, zb, zb + fh), (cc + ow / 2, cc + fw / 2, zb, zb + fh),
                                                     (cc - ow / 2, cc + ow / 2, zb, zb + (fh - oh) / 2), (cc - ow / 2, cc + ow / 2, zb + (fh + oh) / 2, zb + fh)):
                                B("Plastic Grey", a0, a1, min(f0, f1), max(f0, f1), z0, z1)
                            fa, fb = tm + sgn * 0.073, tm + sgn * 0.08
                            B("Smoked Flap", cc - ow / 2, cc + ow / 2, min(fa, fb), max(fa, fb), zb + (fh - oh) / 2, zb + (fh + oh) / 2)
                    lx = l1 - 0.25 if k_ == 0 else l0 + 0.25
                    for sgn in (-1, 1):
                        b0 = tm + sgn * 0.07; b1 = b0 + sgn * 0.06
                        B("Brushed Nickel", lx - 0.06, lx + 0.06, min(b0, b1), max(b0, b1), 2.95, 3.12)
                        b2 = b1 + sgn * 0.05
                        B("Brushed Nickel", lx - 0.32 if k_ == 0 else lx, lx if k_ == 0 else lx + 0.32, min(b1, b2), max(b1, b2), 3.0, 3.06)
        nd_ += 1
    rec("trim.passages", "trim", "Cased openings in the clerestory wall", "interior", info=dict(model=f"{FU.get('casing_width_in', 3.5):g}\" white oak casing (ASSUMED)"))
    for (x0, x1, hd) in CL["passages"][1:]:
        if abs((x0 + x1) / 2 - BD.get("center_x", -99)) < 3.5:
            continue
        if (x0, x1) in DOOR_NAMES or (x0, x1) in DOOR_NOTES:
            continue                           # a door was hung in it, and the door brings its own jambs and casing
        # an opening whose jambs are partitions running north (the mudroom cubby) has no wall face on its north side to
        # trim: casings there stood in the cubby and poked through its side walls (Maxwell 11/17/2026)
        abut = lambda xj: (EC_MERGE and abs(xj - EC["posts"][0]) < 0.05) or (EC_STYLE == "open" and abs(xj - EC["open_to"]) < 0.05) or any(r_[1] > r_[0] + 0.1 and r_[0] - 0.05 <= xj <= r_[1] + 0.05 and r_[3] >= YC - 0.05 and r_[2] < YC - 0.3 for r_ in INT_RECTS)
        for (b0, b1) in ((YC - 0.06, YC), (YC2, YC2 + 0.06)):
            if b1 <= YC and abut(x0) and abut(x1):
                continue
            if b1 <= YC and abs(x0 - EC_OPEN[0]) < 0.01:
                continue                       # entry closet built-in: its carcass fills the closet side
            RV = 0.016                         # 3/16" reveal: the casing stops short of the opening, so its edge never shows inside
            cl = x0 - CW - RV                  # left casing edge; it stops at a neighbour opening's casing when the wall between is narrow
            nb = [q[1] for q in CL["passages"] if q[1] < x0 - 0.01]
            if nb and max(nb) + CW + RV > cl:
                cl = max(nb) + CW + RV + 0.003
            cr = x1 + CW + RV
            if EC_MERGE and abs(x0 - EC_OPEN[0]) < 0.01:
                cl = max(nb) + CW + RV         # one head casing runs on from the cubby's; no leg between them
            else:
                box("White Oak", cl, x0 - RV, b0, b1, 0, hd + RV)
            if not (EC_MERGE and b0 >= YC2 - 1e-6 and abs(x1 - EC["posts"][0]) < 0.01):
                box("White Oak", x1 + RV, cr, b0, b1, 0, hd + RV)
            box("White Oak", cl, cr, b0, b1, hd + RV, hd + RV + CW)

# ------------------------------------------------------------------ entry closet around the beam posts (11/19/2026)
def entry_closet():
    """The builder's two 2x4 posts under the east end of the cubby beam, and whatever fills the 18 in closet opening.
    Plan frame: the opening is in the clerestory wall (y YC to YC2), the entry is south of it, the closet north."""
    if not EC:
        return
    ox0, ox1 = EC_OPEN
    ix0, ix1, iy0, iy1 = EC["interior"]
    px0, px1 = EC["posts"]
    ptop = EC.get("post_top", 8.0)
    ym = (YC + YC2) / 2
    if EC_STYLE == "open":
        rec("structure.beam_posts", "structure", f"Beam posts, {int(EC['post_plies'])} 2x4s", "interior",
            info=dict(model=f"({int(EC['post_plies'])}) 2x4 posts, nailed together, under the east end of the header over the mudroom cubby",
                      specs=[["Where", f"In the {ftin(HW - T - EC['open_to'])} of wall between the cubby and the east wall"], ["Height", f"Floor to the header, {ftin(ptop)}"]],
                      notes=["Open version, no entry closet: the cubby runs on east to this short wall (Maxwell, 11/19/2026). Exact position ASSUMED."]))
        npl = int(EC["post_plies"])
        for k in range(npl):
            a = px0 + k * (px1 - px0) / npl
            box("Framing Lumber", a + 0.003, a + (px1 - px0) / npl - 0.003, ym - 0.146, ym + 0.146, 0.01, ptop - 0.01)
        return
    rec("structure.beam_posts", "structure", "Beam posts, two 2x4s", "interior",
        info=dict(model="(2) 2x4 posts, nailed together, under the east end of the (2) 1 3/4 x 11 7/8 in LVL beam over the mudroom cubby",
                  specs=[["Where", "Inside the wall between the mudroom cubby and the entry closet"], ["Height", f"Floor to the beam, {ftin(ptop)}"]],
                  notes=["Added by the builder (Maxwell, 11/19/2026): the drawings had no posts for the beam here. They take room from the closet opening, which is now 18 in wide.",
                         "Shown inside the wall; turn Walls off to see them. Exact position ASSUMED."]))
    npl = int(EC.get("post_plies", 2))
    for k in range(npl):
        a = px0 + k * (px1 - px0) / npl
        box("Framing Lumber", a + 0.003, a + (px1 - px0) / npl - 0.003, ym - 0.146, ym + 0.146, 0.01, ptop - 0.01)
    if EC_STYLE not in ("closet", "split", "cabinet", "pullout", "coat"):
        return
    M, O = "Mudroom Paint", "White Oak"
    W = ox1 - ox0
    yf = YC2                                       # wall face on the entry side

    def knob(x, z, y=yf):
        box("Black Metal", x - 0.03, x + 0.03, y, y + 0.06, z - 0.03, z + 0.03)

    def shaker(mat, x0, x1, y0, z0, z1, rail=0.2):  # flat door with raised stiles and rails, front at y0 + 0.07
        box(mat, x0, x1, y0, y0 + 0.04, z0, z1)
        for (a0, a1, b0, b1) in ((x0, x1, z0, z0 + rail), (x0, x1, z1 - rail, z1), (x0, x0 + rail * 0.75, z0 + rail, z1 - rail), (x1 - rail * 0.75, x1, z0 + rail, z1 - rail)):
            box(mat, a0, a1, y0 + 0.04, y0 + 0.07, b0, b1)

    def hooks(xs, y, z, out):                      # black double hooks on the back wall (out = +1 south)
        for x in xs:
            box("Black Metal", x - 0.025, x + 0.025, y, y + out * 0.2, z, z + 0.05)
            yy = y + out * 0.2
            box("Black Metal", x - 0.025, x + 0.025, min(yy, yy - out * 0.04), max(yy, yy - out * 0.04), z - 0.08, z + 0.18)

    def boot_tray(x0, x1, y0, y1):
        box("Rubber", x0, x1, y0, y1, 0.0, 0.02)
        for (a0, a1, b0, b1) in ((x0, x1, y0, y0 + 0.03), (x0, x1, y1 - 0.03, y1), (x0, x0 + 0.03, y0 + 0.03, y1 - 0.03), (x1 - 0.03, x1, y0 + 0.03, y1 - 0.03)):
            box("Rubber", a0, a1, b0, b1, 0.02, 0.11)

    if EC_STYLE in ("closet", "split"):            # an 18 in door; inside: shelves up top, hooks, a boot tray
        r = rec("furniture.entry_closet", "furniture", "Entry closet fittings", "furniture", room="Entry", tog="finish",
                info=dict(model="Coat closet behind an 18 in door: two shelves up top, coat hooks on three walls, a rubber boot tray",
                          specs=[["Inside", f"{ftin(ix1 - ix0)} wide x {ftin(iy1 - iy0)} deep"], ["Door", f"{ftin(W)} wide"]],
                          notes=["Mockup for the new 18 in opening (11/19/2026). Hooks instead of a rod: at 18 in deep a hanger does not fit across the closet."]))
        sh = (EC.get("split_at", 6.67) + 0.06, 7.35) if EC_STYLE == "split" else (6.3, 7.2)
        for z in sh:
            box(O, ix0 + 0.003, ix1 - 0.003, iy0 + 0.003, iy1 - 0.08, z, z + 0.06)
        box(O, ix0 + 0.003, ix1 - 0.003, iy0 + 0.003, iy0 + 0.06, 4.95, 5.4)            # hook rail on the back wall
        hooks([ix0 + 0.35 + k * (ix1 - ix0 - 0.7) / 4 for k in range(5)], iy0 + 0.06, 5.12, 1)
        for xw, out in ((ix0, 1), (ix1, -1)):                                            # side walls: hooks at the west (deep) end
            box(O, min(xw, xw + out * 0.06), max(xw, xw + out * 0.06), iy0 + 0.2, iy1 - 0.25, 4.95, 5.4)
            for y in (iy0 + 0.45, iy0 + 1.0):
                box("Black Metal", min(xw + out * 0.06, xw + out * 0.26), max(xw + out * 0.06, xw + out * 0.26), y - 0.025, y + 0.025, 5.12, 5.17)
        boot_tray(ix0 + 0.1, ix1 - 0.1, iy0 + 0.08, iy1 - 0.05)
        if EC_STYLE == "split":                    # cabinet over the door, in the same white oak, its own little door
            z0 = EC.get("split_at", 6.67)
            box(O, ox0 + 0.06, ox1 - 0.06, YC, YC2, z0, z0 + 0.06)                     # transom rail between door and cabinet
            box(O, ix0 + 0.003, ix1 - 0.003, iy0 + 0.003, YC, z0 + 0.003, z0 + 0.06)   # cabinet floor across the closet
            lf = op(r, "furniture.entry_closet.upper", "Cabinet over the entry closet door", "swing", (ox1 - 0.07, ym, 0), angle=90)
            with into(lf["parts"]):
                box(O, ox0 + 0.07, ox1 - 0.07, ym - 0.07, ym + 0.07, z0 + 0.08, 7.92)
                knob(ox0 + 0.25, z0 + 0.3, ym + 0.07)
        return

    # built-ins filling the opening: painted to match the mudroom unit next to it
    if EC_MERGE:                                   # filler over the wall between the cubby and the cabinet, floor to the head casing
        RV_ = 0.016
        box(M, EC["posts"][0] + 0.003, ox0 + 0.06, yf - 0.002, yf + 0.05, 0.0, 8.0 + RV_ - 0.003)
    if EC.get("divider"):                          # the partition to the cubby is gone: a 3/4 in cabinet panel divides them and carries the rod
        d0, d1 = EC["divider"]
        box(M, d0, d1, iy0 + 0.003, YC - 0.003, 0.0, EC.get("divider_top", 7.98))
    for (a0, a1) in ((ox0, ox0 + 0.06), (ox1 - 0.06, ox1)):                              # jamb liners
        box(M, a0, a1, YC, yf - 0.002, 0.0, 8.0)
    box(M, ox0 + 0.06, ox1 - 0.06, YC, yf - 0.002, 7.94, 8.0)
    box(M, ox0 + 0.06, ox1 - 0.06, YC, yf - 0.25, 0.0, 0.33)                             # recessed toe kick
    box(M, ix0 + 0.003, ix1 - 0.003, iy0 + 0.003, yf - 0.1, 0.33, 0.38)                  # carcass floor
    if EC_STYLE == "coat":
        r = rec("furniture.entry_closet", "furniture", "Entry coat cabinet", "furniture", room="Entry", tog="finish",
                info=dict(model="Built-in coat cabinet, painted light sage to match the mudroom unit: a pair of tall doors over a coat rod, a pair of small doors over the top shelf",
                          specs=[["Opening", f"{ftin(W)} wide x 8' 0\""], ["Inside", f"{ftin(ix1 - ix0)} wide x {ftin(yf - 0.1 - iy0)} deep, back wall to the doors"],
                                 ["Rod", f"{ftin(ix1 - ix0)} long at {ftin(EC.get('rod_z', 5.6))}, 12 in off the back wall, so 17 1/2 in hangers fit"],
                                 ["Also", "shelf over the rod, top shelf behind the small doors, rubber boot tray on the floor"]]
                         + ([["Divider", "3/4 in cabinet panel to the mudroom cubby, in place of a wall; the rod socket screws into it, with blocking behind for the hooks on the cubby side"]] if EC.get("divider") else []),
                          notes=["Maxwell, 11/19/2026: option B, with most of the wall between the cubby and the closet taken out so the doors are wide enough to get coats in and out. "
                                 "The opening now runs from the beam posts to the east wall; the builder still has to confirm the header over it.",
                                 "The doors sit in the wall's thickness, so the cabinet is about 2 ft deep: enough for coats hung facing the doors."]))
        rz, ry = EC.get("rod_z", 5.6), iy0 + 1.0
        zt = 6.45
        box(M, ix0 + 0.003, ix1 - 0.003, iy0 + 0.003, yf - 0.1, zt, zt + 0.06)                # shelf over the rod
        box(M, ix0 + 0.003, ix1 - 0.003, iy0 + 0.003, yf - 0.1, 7.2, 7.26)                  # top shelf
        box("Brushed Nickel", ix0 + 0.003, ix1 - 0.003, ry - 0.045, ry + 0.045, rz - 0.045, rz + 0.045)   # 1 1/16 in rod
        for xw in (ix0 + 0.003, ix1 - 0.055):
            box("Brushed Nickel", xw, xw + 0.052, ry - 0.1, ry + 0.1, rz - 0.1, rz + 0.1)      # rod sockets
        boot_tray(ix0 + 0.1, ix1 - 0.1, iy0 + 0.08, yf - 0.2)

        def slab(mat, x0, x1, ya, za, yb, zb, t):     # a sloped bar in the y-z plane, x0..x1 thick, t tall
            hexa(mat, [(x0, ya, za), (x1, ya, za), (x1, yb, zb), (x0, yb, zb), (x0, ya, za + t), (x1, ya, za + t), (x1, yb, zb + t), (x0, yb, zb + t)])

        def hanger(x):                                 # 17 1/2 in wooden hanger, hook over the rod
            hw, zs = 0.73, rz - 0.17
            box("Brushed Nickel", x - 0.01, x + 0.01, ry - 0.01, ry + 0.01, zs, rz + 0.07)
            box("Brushed Nickel", x - 0.01, x + 0.01, ry - 0.08, ry + 0.01, rz + 0.06, rz + 0.08)
            box("Brushed Nickel", x - 0.01, x + 0.01, ry - 0.08, ry - 0.06, rz - 0.02, rz + 0.07)
            for sg in (-1, 1):
                slab("Hanger Wood", x - 0.02, x + 0.02, ry, zs - 0.04, ry + sg * hw, zs - 0.3, 0.08)
            box("Hanger Wood", x - 0.012, x + 0.012, ry - hw + 0.05, ry + hw - 0.05, zs - 0.62, zs - 0.58)   # trouser bar
            for sg in (-1, 1):
                box("Hanger Wood", x - 0.012, x + 0.012, min(ry + sg * (hw - 0.05), ry + sg * (hw - 0.09)), max(ry + sg * (hw - 0.05), ry + sg * (hw - 0.09)), zs - 0.62, zs - 0.3)

        def coat(x, mat, length):                      # a coat on a hanger: shoulders, body and hanging sleeves
            th, hw, zs = 0.17, 0.75, rz - 0.21
            for sg in (-1, 1):
                slab(mat, x - th, x + th, ry, zs - 0.02, ry + sg * hw, zs - 0.32, 0.12)
            box(mat, x - th, x + th, ry - 0.62, ry + 0.62, zs - length, zs - 0.2)
            box(mat, x - 0.05, x + 0.05, ry - 0.1, ry + 0.1, zs - 0.05, zs + 0.15)              # collar
            for sg in (-1, 1):
                y0_ = ry + sg * 0.63
                box(mat, x - th + 0.03, x + th - 0.03, min(y0_, y0_ + sg * 0.17), max(y0_, y0_ + sg * 0.17), zs - 2.0, zs - 0.3)

        span = ix1 - ix0 - 0.3
        coats = EC.get("coats", [["Coat Navy", 3.0], ["Coat Olive", 2.4], ["Coat Tan", 3.3], ["Coat Charcoal", 2.6]])
        xs = [ix0 + 0.15 + span * (k + 0.5) / (len(coats) + 3) for k in range(len(coats) + 3)]
        for k, x in enumerate(xs):
            hanger(x)
            if k < len(coats):
                coat(x, *coats[k])
        hw_ = (W - 0.14) / 2
        for (z0, z1, nm, kz) in ((0.38, zt, "lower", 3.4), (zt + 0.03, 7.92, "upper", zt + 0.35)):
            for side, (a0, a1, hx, ang) in (("left", (ox0 + 0.07, ox0 + 0.07 + hw_ - 0.005, ox0 + 0.07, -90)),
                                            ("right", (ox1 - 0.07 - hw_ + 0.005, ox1 - 0.07, ox1 - 0.07, 90))):
                lf = op(r, f"furniture.entry_closet.{nm}_{side}", f"Entry coat cabinet, {nm} {side} door", "swing", (hx, yf - 0.09, 0), angle=ang)
                with into(lf["parts"]):
                    shaker(M, a0, a1, yf - 0.09, z0 + 0.01, z1 - 0.01, rail=0.18)
                    knob(a1 - 0.12 if side == "left" else a0 + 0.12, kz, yf - 0.02)
        return
    if EC_STYLE == "cabinet":
        r = rec("furniture.entry_closet", "furniture", "Entry closet cabinet", "furniture", room="Entry", tog="finish",
                info=dict(model="Built-in tall cabinet, painted light sage to match the mudroom unit: a tall door and a top door, adjustable shelves across the whole closet",
                          specs=[["Opening", f"{ftin(W)} wide x 8' 0\""], ["Shelves", f"5, each {ftin(ix1 - ix0)} wide x {ftin(yf - 0.1 - iy0)} deep"]],
                          notes=["Mockup for the new 18 in opening (11/19/2026). Good for bags, bins, dog gear, cleaning supplies; the shelves run behind the wall on the west side too."]))
        zt = 6.45
        for z in (1.55, 2.75, 3.95, 5.15, zt):
            box(M, ix0 + 0.003, ix1 - 0.003, iy0 + 0.003, yf - 0.1, z, z + 0.06)
        box(M, ix0 + 0.003, ix1 - 0.003, iy0 + 0.003, yf - 0.1, 7.2, 7.26)
        for (z0, z1, nm, kz) in ((0.38, zt, "lower", zt - 2.9), (zt + 0.03, 7.92, "upper", zt + 0.3)):
            lf = op(r, f"furniture.entry_closet.{nm}", f"Entry closet cabinet, {nm} door", "swing", (ox1 - 0.07, yf - 0.09, 0), angle=90)
            with into(lf["parts"]):
                shaker(M, ox0 + 0.07, ox1 - 0.07, yf - 0.09, z0 + 0.01, z1 - 0.01, rail=0.18)
                knob(ox0 + 0.2, kz, yf - 0.02)
        return
    # pullout: a full height coat tower on full extension slides, hooks on both sides of a centre spine
    r = rec("furniture.entry_closet", "furniture", "Pull-out coat tower", "furniture", room="Entry", tog="finish",
            info=dict(model="Full height pull-out coat tower, painted light sage to match the mudroom unit, on heavy full extension slides",
                      specs=[["Front", f"{ftin(W)} wide x 7' 6\""], ["Pulls out", "about 1' 9\" into the entry"],
                             ["Inside", "centre spine with coat hooks on both faces, a hat shelf on top, a boot tray at the bottom; fixed shelves in the closet's west half"]],
                      notes=["Mockup for the new 18 in opening (11/19/2026). Pull it out and every coat is reachable from the side; the west half behind the wall gets shelves you reach from the side when the tower is out."]))
    for z in (1.6, 3.2, 4.8, 6.4):                                                       # fixed shelves behind the wall, west half
        box(M, ix0 + 0.003, ox0 - 0.05, iy0 + 0.003, iy1 - 0.05, z, z + 0.06)
    tx0, tx1, ty0, ty1 = ox0 + 0.08, ox1 - 0.08, iy0 + 0.1, yf - 0.02
    lf = op(r, "furniture.entry_closet.tower", "Pull-out coat tower", "slide", ((tx0 + tx1) / 2, ty1, 0), slide=(0, 1.75, 0))
    with into(lf["parts"]):
        shaker(M, tx0, tx1, ty1 - 0.07, 0.4, 7.9, rail=0.2)                              # front panel
        box("Black Metal", (tx0 + tx1) / 2 - 0.04, (tx0 + tx1) / 2 + 0.04, ty1, ty1 + 0.08, 3.4, 4.6)   # long bar pull
        xm = (tx0 + tx1) / 2
        box(M, xm - 0.03, xm + 0.03, ty0, ty1 - 0.07, 0.45, 7.5)                         # spine
        box(M, tx0, tx1, ty0, ty1 - 0.07, 0.4, 0.46)                                     # bottom
        box(M, tx0, tx1, ty0, ty1 - 0.07, 7.5, 7.56)                                     # hat shelf
        box(M, tx0, tx1, ty0, ty0 + 0.06, 0.46, 7.5)                                     # back panel
        boot_tray(tx0 + 0.04, tx1 - 0.04, ty0 + 0.1, ty1 - 0.12)
        for side in (-1, 1):
            for k, y in enumerate((ty0 + 0.35, ty0 + 0.85, ty0 + 1.35)):
                xa = xm + side * 0.03
                box("Black Metal", min(xa, xa + side * 0.2), max(xa, xa + side * 0.2), y - 0.025, y + 0.025, 5.6 - 0.25 * (k % 2), 5.65 - 0.25 * (k % 2))


entry_closet()
MATERIALS.update({"Framing Lumber": dict(color="#C9A66B", rough=0.8), "Hanger Wood": dict(color="#B07A4A", rough=0.5),
                  "Coat Navy": dict(color="#2A3550", rough=0.9), "Coat Olive": dict(color="#5B6340", rough=0.9),
                  "Coat Tan": dict(color="#A88A64", rough=0.9), "Coat Charcoal": dict(color="#3A3B3D", rough=0.9)})

# ------------------------------------------------------------------ exterior details: fascia, soffits, gutters, fixtures
if FU.get("enabled"):
    FH_ = R.get("fascia_height", 1.0)
    zN = north_roof_z(-OH) + TH; zS = south_roof_z(HD + OH) + TH
    rec("roof.trim", "trim", "Fascia, rakes and soffits", "roof", info=dict(model=f"{ftin(FH_)} fascia (A-20 notes), black", specs=[["Colour", f"LP Abyss Black {MM['trim_color']}"]]))
    box("Trim", -OH - 0.02, HW + OH + 0.02, -OH - 0.1, -OH, zN - FH_, zN + 0.04)
    box("Trim", -OH - 0.02, HW + OH + 0.02, HD + OH, HD + OH + 0.1, zS - FH_, zS + 0.04)
    for xr in (-OH - 0.1, HW + OH):
        prism_x("Trim", xr, xr + 0.1, [(-OH, north_roof_z(-OH) + TH - FH_), (YC2 + OH, north_roof_z(YC2 + OH) + TH - FH_),
                                      (YC2 + OH, north_roof_z(YC2 + OH) + TH + 0.04), (-OH, north_roof_z(-OH) + TH + 0.04)])
        prism_x("Trim", xr, xr + 0.1, [(YC2, south_roof_z(YC2) + TH - FH_), (HD + OH, south_roof_z(HD + OH) + TH - FH_),
                                      (HD + OH, south_roof_z(HD + OH) + TH + 0.04), (YC2, south_roof_z(YC2) + TH + 0.04)])
    box("Trim", -OH, HW + OH, -OH, -0.0, north_roof_z(-OH) - 0.06, north_roof_z(-OH))
    box("Trim", -OH, HW + OH, HD, HD + OH, south_roof_z(HD + OH) - 0.06, south_roof_z(HD + OH))
    if FU.get("gutters", True):
        rec("roof.gutters", "gutter", "Gutters", "roof", info=dict(model="5\" K style gutters at both eaves (ASSUMED)"))
        GUT = []
        for (yg, zg, sgn) in ((-OH - 0.1, zN - FH_ + 0.25, -1), (HD + OH + 0.1, zS - FH_ + 0.25, 1)):
            y0g, y1g = sorted((yg, yg + sgn * 0.42))
            box("Gutter", -OH - 0.05, HW + OH + 0.05, y0g, y1g, zg, zg + 0.04)
            box("Gutter", -OH - 0.05, HW + OH + 0.05, min(y0g, y1g) if sgn < 0 else max(y0g, y1g) - 0.04, min(y0g, y1g) + 0.04 if sgn < 0 else max(y0g, y1g), zg, zg + 0.42)
            GUT.append((y0g, y1g, zg, sgn))
        rec("shell.downspouts", "gutter", "Downspouts and splash blocks", "shell", info=dict(model="3 x 4 downspouts at the four corners with kick outs (ASSUMED)"))
        for (y0g, y1g, zg, sgn) in GUT:
            for xd in (-OH + 0.6, HW + OH - 0.9):
                yd = (y0g + y1g) / 2
                ywall = 0.0 if sgn < 0 else HD
                box("Gutter", xd, xd + 0.33, min(yd, ywall), max(yd, ywall), zg - 0.9, zg - 0.6)
                yy0, yy1 = sorted((ywall + sgn * 0.02, ywall + sgn * 0.27))
                gz = GROUND_Z
                box("Gutter", xd, xd + 0.33, yy0, yy1, gz + 0.6, zg - 0.6)
                b0, b1 = sorted((ywall + sgn * 0.02, ywall + sgn * 0.9))
                box("Gutter", xd, xd + 0.33, b0, b1, gz + 0.35, gz + 0.6)
                c0, c1 = sorted((ywall + sgn * 0.6, ywall + sgn * 2.6))
                box("Concrete", xd - 0.3, xd + 0.63, c0, c1, gz - 0.05, gz + 0.12)
    for k, fx in enumerate(FU.get("exterior_fixtures", [])):
        w_, u_, z_ = fx["wall"], fx["u"], fx["z"]
        t_ = fx["type"]
        if t_ == "light" and not FU.get("exterior_lights", True):
            continue
        nm = {"light": "Exterior wall light", "outlet": "Exterior outlet", "hose_bib": "Hose bib"}.get(t_, t_)
        rec(f"shell.fixture.{k}", "fixture", f"{nm}, {WALL_NAMES[w_]}", "shell",
            info=dict(model={"light": "Black barn style wall light (Blender used Poly Haven industrial_wall_lamp)", "outlet": "Weatherproof GFCI outlet with in use cover",
                             "hose_bib": "Frost free hose bib"}.get(t_, t_), specs=[["Height", ftin(z_)]], notes=[fx["note"]] if fx.get("note") else ["Location ASSUMED."]))
        if t_ == "light":
            fr = wall_frame(w_)
            wbox("Black Metal", w_, u_ - 0.18, u_ + 0.18, -BAT_T - 0.06, -BAT_T, z_ - 0.25, z_ + 0.25)            # back plate
            wbox("Black Metal", w_, u_ - 0.03, u_ + 0.03, -BAT_T - 0.55, -BAT_T - 0.06, z_ + 0.12, z_ + 0.18)   # arm
            cx, cy = fr(u_, -BAT_T - 0.6)
            cyl("Black Metal", cx, cy, z_ - 0.02, z_ + 0.12, 0.42, 0.06)                                     # shade
            cyl("Lamp Glass", cx, cy, z_ - 0.08, z_ - 0.0, 0.12, 0.12)
        elif t_ == "outlet":
            wbox("Plastic Grey", w_, u_ - 0.2, u_ + 0.2, -BAT_T - 0.2, -BAT_T, z_ - 0.25, z_ + 0.25)
            wbox("Plastic Grey", w_, u_ - 0.17, u_ + 0.17, -BAT_T - 0.24, -BAT_T - 0.2, z_ - 0.2, z_ + 0.22)
        elif t_ == "hose_bib":
            wbox("Brushed Nickel", w_, u_ - 0.12, u_ + 0.12, -BAT_T - 0.05, -BAT_T, z_ - 0.12, z_ + 0.12)
            wbox("Brushed Nickel", w_, u_ - 0.05, u_ + 0.05, -BAT_T - 0.4, -BAT_T - 0.05, z_ - 0.05, z_ + 0.05)
            wbox("Brushed Nickel", w_, u_ - 0.04, u_ + 0.04, -BAT_T - 0.42, -BAT_T - 0.34, z_ - 0.2, z_)
            wbox("Brushed Nickel", w_, u_ - 0.1, u_ + 0.1, -BAT_T - 0.28, -BAT_T - 0.24, z_ + 0.05, z_ + 0.15)

# ------------------------------------------------------------------ garage, porch, greenhouse
# Floor levels (Maxwell 11/22/2026): one small step down from the house entry onto the brick breezeway, another down
# into the garage. [grade] in config.toml; model/grade.py regrades the ground to suit.
GR = C["grade"]
PZ = -GR["patio_drop_in"] / 12          # top of the breezeway brick
GF = -GR["garage_drop_in"] / 12         # top of the garage slab; every garage height in [garage] is above this
GA = C["garage"]
PB = GA.get("pole_barn", {})
MATERIALS.update({"Treated Lumber": dict(color="#9C9A6E", rough=0.85), "Barn Post": dict(color="#B8955E", rough=0.85),
                  "Roof Liner": dict(color="#E4E4DE", rough=0.7)})
if GA["enabled"]:
    gx0, gy0, gx1, gy1 = GA["rect"]
    gs = GA["pitch"] / 12
    gtop = lambda y: GF + GA["south_wall_height"] + (gy1 - y) * gs
    GWH = GA.get("north_window_height", 3.0)
    my0, my1 = GA["man_door_y"]
    SID = PB.get("siding_in", 0.75) / 12              # LP board and batten panel on the girts
    GIRT = 1.5 / 12                                   # 2x4 girts laid flat on the outside of the posts
    POST = PB.get("post_in", 5.5) / 12
    PV0, PV1 = SID + GIRT, SID + GIRT + POST          # posts, measured in from the outside face
    rec("garage.walls", "wall", "Garage walls", "shell",
        info=dict(model=f"{ftin(gx1 - gx0)} x {ftin(gy1 - gy0)} pole barn garage (post frame), delegated design (A-11, A-22)",
                  specs=[["South wall", f"{ftin(GA['south_wall_height'])} (A-31 section 2)"], ["Roof", f"{GA['pitch']:g}:12 down to the south"],
                         ["Frame", f"{PB.get('post_name', '6x6 treated posts')} about {ftin(PB.get('post_spacing_ft', 8.0))} apart, 2x4 girts {PB.get('girt_spacing_in', 24):g} in on centre, treated 2x8 splash board"],
                         ["Siding", "Board and batten on the girts, to match the house"]],
                  notes=["Maxwell 11/22/2026: the garage is a pole barn. Post sizes, spacing, girts, trusses and purlins are typical post frame practice, ASSUMED until the barn builder's drawings come in.",
                         "Inside is left unfinished: you see the posts, girts, trusses and purlins."]))
    fN, fS, fW, fE = (gx0, gy0, 1, 0, 0, 1), (gx0, gy1, 1, 0, 0, -1), (gx0, gy0, 0, 1, 1, 0), (gx1, gy0, 0, 1, -1, 0)
    WS, WN = GF + GA["north_window_sill"], GF + GA["north_window_sill"] + GWH
    holesN = [(s0, s0 + 3, WS, WN) for s0 in GA["north_windows"]]
    holesS = [(s0, s0 + w, GF, GF + 8) for (s0, w) in GA["overhead_doors"]]
    holesW = [(my0 - gy0, my1 - gy0, PZ, PZ + 6.67)]
    W_ = gx1 - gx0; D_ = gy1 - gy0
    panel("Siding", fN, 0, SID, GF, [[0, gtop(gy0), W_, gtop(gy0)]], holesN)
    panel("Siding", fS, 0, SID, GF, [[0, gtop(gy1), W_, gtop(gy1)]], holesS)
    panel("Siding", fW, 0, SID, GF, [[0, gtop(gy0), D_, gtop(gy1)]], holesW)
    panel("Siding", fE, 0, SID, GF, [[0, gtop(gy0), D_, gtop(gy1)]], [])
    battens("Siding", lambda u, v: (gx0 + u, gy0 + v), 0, W_, GF, lambda u: gtop(gy0),
            [(s0 - TRIM_W, s0 + 3 + TRIM_W, WS - 0.4, WN + 0.4) for s0 in GA["north_windows"]])
    battens("Siding", lambda u, v: (gx0 + u, gy1 - v), 0, W_, GF, lambda u: gtop(gy1), [(s0 - TRIM_W - 0.05, s0 + w + TRIM_W + 0.05, GF - 1, GF + 8.0 + TRIM_W + 0.05) for (s0, w) in GA["overhead_doors"]])
    battens("Siding", lambda u, v: (gx0 + v, u), gy0, gy1, PZ, gtop, [(my0 - TRIM_W - 0.05, my1 + TRIM_W + 0.05, PZ - 1, PZ + 6.67 + TRIM_W + 0.05)])
    battens("Siding", lambda u, v: (gx1 - v, u), gy0, gy1, GF, gtop, [])
    rec("garage.slab", "slab", "Garage slab", "shell", info=dict(model="Concrete slab poured inside the posts",
        specs=[["Floor", f"{GR['garage_drop_in']:g} in below the house floor, {GR['garage_drop_in'] - GR['patio_drop_in']:g} in below the breezeway brick"],
               ["Grade", f"Ground {GR['garage_grade_in']:g} in below the slab all round"]],
        notes=["Levels set 11/22/2026 (Maxwell): a small step down from the house onto the brick, another into the garage.",
               "The sealed set gives no elevations (S-10 note 7 leaves them to the site and owner). With these steps the house slab had to sit about 7 in higher on the lidar ground than first guessed so the garage slab stays above the existing ground."]))
    box("Concrete", gx0, gx1, gy0, gy1, GF - 0.4, GF)
    box("Concrete", gx0 + SID, gx0 + PV1, my0, my1, GF, PZ - 0.04)       # the step at the man door: a curb up to the threshold
    for k, (s0, w) in enumerate(GA["overhead_doors"]):
        r = rec(f"garage.door.{k + 1}", "door", f"Garage overhead door {k + 1}", "shell", info=dict(model=f"D90-80 overhead door, {ftin(w)} x 8' 0\"", specs=[["Colour", "Black, with a row of lites"]]))
        r["info"]["specs"].append(["Opens", "Sectional, rolls up and back on horizontal tracks under the ceiling"])
        for xt in (gx0 + s0 - 0.12, gx0 + s0 + w + 0.04):         # steel tracks: up the jambs, then back into the garage
            box("Black Metal", xt, xt + 0.08, gy1 - 0.45, gy1 - 0.25, GF, GF + 8.1)
            box("Black Metal", xt, xt + 0.08, gy1 - 8.6, gy1 - 0.25, GF + 8.1, GF + 8.25)
        lf = op(r, f"garage.door.{k + 1}.panel", r["name"], "overhead", (gx0 + s0 + w / 2, gy1 - 0.35, GF))
        lf["height"] = 8.0
        lf["inward"] = [0, -1]                                  # rolls back to the north, into the garage
        with into(lf["parts"]):
            box("Garage Door", gx0 + s0, gx0 + s0 + w, gy1 - 0.4, gy1 - 0.3, GF, GF + 8)
            for j in range(1, 4):
                box("Trim", gx0 + s0 + 0.1, gx0 + s0 + w - 0.1, gy1 - 0.31, gy1 - 0.27, GF + j * 2 - 0.03, GF + j * 2 + 0.03)
            for j in range(4):
                wx = gx0 + s0 + 0.6 + j * (w - 1.2) / 4
                box("Glass", wx + 0.1, wx + (w - 1.2) / 4 - 0.1, gy1 - 0.27, gy1 - 0.25, GF + 6.5, GF + 7.5)
    for (s0, w) in GA["overhead_doors"]:                         # black jamb and head liners in front of the doors hide the post edges
        box("Trim", gx0 + s0, gx0 + s0 + 0.06, gy1 - 0.28, gy1, GF, GF + 8.06)
        box("Trim", gx0 + s0 + w - 0.06, gx0 + s0 + w, gy1 - 0.28, gy1, GF, GF + 8.06)
        box("Trim", gx0 + s0, gx0 + s0 + w, gy1 - 0.28, gy1, GF + 8.0, GF + 8.06)
        # exterior casing on the siding, black like the house trim (Maxwell 11/22/2026), and a vinyl threshold seal on the slab
        for (a0, a1, b0, b1) in ((s0 - TRIM_W, s0, GF, GF + 8.0 + TRIM_W), (s0 + w, s0 + w + TRIM_W, GF, GF + 8.0 + TRIM_W), (s0 - TRIM_W, s0 + w + TRIM_W, GF + 8.0, GF + 8.0 + TRIM_W)):
            box("Trim", gx0 + a0, gx0 + a1, gy1, gy1 + BAT_T + 0.02, b0, b1)
        box("Plastic Grey", gx0 + s0 + 0.06, gx0 + s0 + w - 0.06, gy1 - 0.28, gy1 - 0.02, GF, GF + 0.03)
    for k, s0 in enumerate(GA["north_windows"]):
        rec(f"garage.window.{k + 1}", "window", f"Garage north window {k + 1}", "shell", info=dict(model="W30-30 awning", specs=[["Sill", ftin(GA["north_window_sill"]) + " above the garage floor"]], notes=["A-21 north elevation."]))
        wx0, wx1 = gx0 + s0, gx0 + s0 + 3
        box("Glass", wx0, wx1, gy0 + SID * 0.4, gy0 + SID * 0.6, WS, WN)
        for (a0, a1, b0, b1) in ((wx0 - 0.33, wx0, WS, WN), (wx1, wx1 + 0.33, WS, WN), (wx0 - 0.33, wx1 + 0.33, WN, WN + 0.33), (wx0 - 0.33, wx1 + 0.33, WS - 0.33, WS)):
            box("Trim", a0, a1, gy0 - BAT_T - 0.02, gy0, b0, b1)
    r = rec("garage.man_door", "door", "Garage door to the breezeway", "shell", info=dict(model="D30-68 man door", specs=[["Opening", f"{ftin(my1 - my0)} x 6' 8\""],
        ["Step", f"Threshold level with the brick, {GR['garage_drop_in'] - GR['patio_drop_in']:g} in step down onto the garage floor"]]))
    r["info"]["specs"].append(["Frame", "Jambs and head lining the wall, black casing outside, pine casing inside, aluminium threshold (Maxwell 11/22/2026)"])
    DH, JW = PZ + 6.67, 0.07                                     # rough opening head; jamb thickness
    for (a0, a1) in ((my0, my0 + JW), (my1 - JW, my1)):          # jambs through the full wall
        box("Trim", gx0 + SID, gx0 + PV1, a0, a1, PZ + 0.06, DH - JW)
    box("Trim", gx0 + SID, gx0 + PV1, my0, my1, DH - JW, DH)                                     # head jamb (painted black like the door)
    for (a0, a1) in ((my0 + JW, my0 + JW + 0.04), (my1 - JW - 0.04, my1 - JW)):                  # door stops
        box("Trim", gx0 + 0.18, gx0 + 0.21, a0, a1, PZ + 0.06, DH - JW)
    for (a0, a1, b0, b1) in ((my0 - TRIM_W, my0, PZ, DH + TRIM_W), (my1, my1 + TRIM_W, PZ, DH + TRIM_W), (my0 - TRIM_W, my1 + TRIM_W, DH, DH + TRIM_W)):
        box("Trim", gx0 - BAT_T - 0.02, gx0, a0, a1, b0, b1)                                    # exterior casing
        box("Lumber", gx0 + PV1, gx0 + PV1 + 0.06, a0, a1, b0 if b0 > PZ else GF, b1)            # interior casing, down to the garage floor
    box("Aluminum", gx0 - 0.12, gx0 + PV1, my0, my1, PZ - 0.04, PZ + 0.06)                      # threshold on the curb
    lf = op(r, "garage.man_door.leaf", r["name"], "swing", (gx0 + 0.21, my0 + JW, PZ + 0.06), angle=90)
    with into(lf["parts"]):
        box("Garage Door", gx0 + 0.21, gx0 + 0.36, my0 + JW + 0.01, my1 - JW - 0.01, PZ + 0.07, DH - JW - 0.01)
        box("Brushed Nickel", gx0 + 0.36, gx0 + 0.44, my1 - JW - 0.3, my1 - JW - 0.22, PZ + 3.0, PZ + 3.08)   # lever, garage side
        box("Brushed Nickel", gx0 + 0.13, gx0 + 0.21, my1 - JW - 0.3, my1 - JW - 0.22, PZ + 3.0, PZ + 3.08)   # and breezeway side

    # ---- the post frame (Framing layer look, but part of the garage shell: it is what you see inside)
    rec("garage.frame", "structure", "Garage post frame", "shell", info=dict(model="Pole barn frame: posts, girts, splash board, girders, trusses and purlins",
        specs=[["Posts", f"{PB.get('post_name', '6x6 treated')}, about {ftin(PB.get('post_spacing_ft', 8.0))} on centre, set in the ground"],
               ["Girts", f"2x4 flat, {PB.get('girt_spacing_in', 24):g} in on centre"], ["Splash board", "Treated 2x8 at the bottom"],
               ["Trusses", f"Mono slope {GA['pitch']:g}:12, set between the north windows so none crosses one, about 4 to 6 ft apart"], ["Purlins", f"2x6 on edge, {PB.get('purlin_spacing_in', 24):g} in on centre"]],
        notes=["Typical post frame sizes, ASSUMED until the barn builder's drawings come in (Maxwell 11/22/2026: the garage is a pole barn)."]))
    SP_ = PB.get("post_spacing_ft", 8.0)
    def stations(lo, hi, must):
        n = max(1, math.ceil((hi - lo) / SP_ - 1e-6)); pts = [lo + (hi - lo) * k / n for k in range(n + 1)]
        for m in must:
            pts = [p for p in pts if abs(p - m) > 1.2] + [m]
        return sorted(pts)
    # posts along each wall, u along the wall; jambs of every opening get one
    jS = [s0 - POST / 2 for s0, _ in GA["overhead_doors"]] + [s0 + w + POST / 2 for s0, w in GA["overhead_doors"]]
    walls = [("N", lambda u, v: (gx0 + u, gy0 + v), W_, []), ("S", lambda u, v: (gx0 + u, gy1 - v), W_, jS),
             ("W", lambda u, v: (gx0 + v, gy0 + u), D_, [my0 - gy0 - POST / 2, my1 - gy0 + POST / 2]), ("E", lambda u, v: (gx1 - v, gy0 + u), D_, [])]
    girt_holes = {"N": [(s0 - 0.05, s0 + 3.05, WS - 0.15, WN + 0.15) for s0 in GA["north_windows"]],
                  "S": [(s0, s0 + w, GF - 1, GF + 8.6) for s0, w in GA["overhead_doors"]], "W": [(my0 - gy0, my1 - gy0, GF - 1, PZ + 7.1)], "E": []}
    GS = PB.get("girt_spacing_in", 24) / 12
    for wn, f, L, must in walls:
        topz = (lambda u, f=f: gtop(f(u, 0)[1]))
        opens = [(h0, h1) for (h0, h1, hz0, hz1) in girt_holes[wn] if hz0 < GF + 1]      # door openings: no post in them
        us = stations(PV0 + POST / 2, L - PV0 - POST / 2, must)          # corner posts sit inside both siding planes
        if wn in ("N", "S"):
            us = us[1:-1]                                                # the E and W walls carry the corner posts
        us = [u for u in us if not any(h0 - POST / 2 + 0.01 < u < h1 + POST / 2 - 0.01 for h0, h1 in opens)]
        for u in us:
            (ax, ay), (bx, by) = f(u - POST / 2, PV0), f(u + POST / 2, PV1)
            box("Barn Post", ax, bx, ay, by, GF, topz(u) - 0.05)
        # splash board then girts every GS up the wall, skipping openings
        rows = [(GF, GF + 7.25 / 12, "Treated Lumber")]
        z = GF + 2.0
        while z + 3.5 / 12 < min(topz(0), topz(L)) - 0.9:
            rows.append((z, z + 3.5 / 12, "Lumber")); z += GS
        uL0, uL1 = (PV0, L - PV0) if wn in ("N", "S") else (SID, L - SID)  # corners: N and S girts stop inside the E and W ones, those inside the siding
        for (z0, z1, m) in rows:
            segs = [(uL0, uL1)]
            for (h0, h1, hz0, hz1) in girt_holes[wn]:
                if hz0 < z1 and hz1 > z0:
                    segs = [s for a_, b_ in segs for s in ((a_, min(b_, h0)), (max(a_, h1), b_)) if s[1] - s[0] > 0.2]
            for a_, b_ in segs:
                (ax, ay), (bx, by) = f(a_, SID), f(b_, PV0)
                box(m, ax, bx, ay, by, z0, z1)
        for (h0, h1, hz0, hz1) in girt_holes[wn]:        # headers over the openings
            if hz1 < min(topz(h0), topz(h1)) - 0.5:
                (ax, ay), (bx, by) = f(h0 - 0.1, SID), f(h1 + 0.1, PV0)
                box("Header", ax, bx, ay, by, hz1, hz1 + 11.25 / 12)
    # plywood backer between the two posts of the pier between the overhead doors, for the EV charger
    (s0a, wa), (s0b, _) = GA["overhead_doors"][0], GA["overhead_doors"][1]
    box("OSB", gx0 + s0a + wa + POST, gx0 + s0b - POST, gy1 - PV1, gy1 - PV0, GF + 1.0, GF + 6.0)
    # girders (doubled 2x12) on the inside of the north and south posts, trusses bear on them
    GD = 11.25 / 12
    for y_in, sgn in ((gy0 + PV1, 1), (gy1 - PV1, -1)):
        zt = gtop(y_in) - 0.05
        box("LVL", gx0 + PV0, gx1 - PV0, y_in, y_in + sgn * 3 / 12, zt - GD, zt)
    # mono trusses north-south every truss_spacing_ft: flat bottom chord, sloped top chord, verticals and diagonals
    TS = PB.get("truss_spacing_ft", 4.0); CH = 3.5 / 12; TW = 1.5 / 12
    ys_, yn_ = gy1 - PV1 - 3 / 12, gy0 + PV1 + 3 / 12
    zb = gtop(gy1 - PV1) - 0.05 - GD                      # bottom chord underside: on the south girder's bottom line
    zb += GD - CH                                         # sits at the girder top, flush
    PUR = 5.5 / 12                                         # 2x6 purlins on edge for the up to 6 ft truss bays
    ttop = lambda y: gtop(y) - PUR                         # top chord top: purlins sit on it, roof deck on them
    # trusses clear of the north windows (Maxwell 11/22/2026): one in each gap between windows, plus one at each end wall
    # and one beside the end windows, so none crosses a window and none is more than about 6 ft from the next
    lo, hi = PV0 + TW, W_ - PV0 - TW
    spans = sorted((s0 - TRIM_W - 0.1, s0 + 3 + TRIM_W + 0.1) for s0 in GA["north_windows"])
    us_t = [lo, spans[0][0] - TW, spans[-1][1] + TW, hi] + [(spans[k][1] + spans[k + 1][0]) / 2 for k in range(len(spans) - 1)]
    us_t = sorted(set(round(u, 3) for u in us_t if lo - 1e-6 <= u <= hi + 1e-6))
    xs_t = [gx0 + u for u in us_t]
    for xt in xs_t:
        a0, a1 = xt - TW / 2, xt + TW / 2
        box("Lumber", a0, a1, yn_, ys_, zb, zb + CH)                                       # bottom chord
        hexa("Lumber", [(a0, ys_, ttop(ys_) - CH * 1.1), (a1, ys_, ttop(ys_) - CH * 1.1), (a1, yn_, ttop(yn_) - CH * 1.1), (a0, yn_, ttop(yn_) - CH * 1.1),
                        (a0, ys_, ttop(ys_)), (a1, ys_, ttop(ys_)), (a1, yn_, ttop(yn_)), (a0, yn_, ttop(yn_))])          # top chord
        nb = 6; yk = [ys_ + (yn_ - ys_) * k / nb for k in range(nb + 1)]
        for k, yv in enumerate(yk):                                                       # verticals
            if ttop(yv) - CH * 1.1 - (zb + CH) > 0.2:
                y0v, y1v = sorted((yv - TW / 2, yv + TW / 2))
                y0v, y1v = max(min(y0v, ys_), yn_), min(max(y1v, yn_), ys_)
                box("Lumber", a0, a1, y0v, y1v, zb + CH, ttop(yv) - CH * 1.1)
        for k in range(nb):                                                               # diagonals
            ya, yb = yk[k], yk[k + 1]
            za, zb2 = zb + CH, ttop(yb) - CH * 1.1
            d = 0.06
            hexa("Lumber", [(a0, ya - d, za), (a1, ya - d, za), (a1, ya + d, za), (a0, ya + d, za),
                            (a0, yb - d, zb2), (a1, yb - d, zb2), (a1, yb + d, zb2), (a0, yb + d, zb2)])
    yp = gy1 - 0.5
    while yp > gy0 + 0.5:                                                                  # purlins east-west on the top chords
        box("Lumber", gx0 + SID + 0.01, gx1 - SID - 0.01, yp - TW / 2, yp + TW / 2, ttop(yp) + 0.004, gtop(yp) - 0.004)
        yp -= PB.get("purlin_spacing_in", 24) / 12

    RT = GA.get("roof_thick_in", 3) / 12                            # 16 in like the breezeway (Maxwell 11/22/2026)
    rec("garage.roof", "roof", "Garage roof", "roof", info=dict(model=f"{GA['pitch']:g}:12 standing seam roof, {RT * 12:g} in thick",
        notes=["Maxwell 11/22/2026: 16 in thick like the breezeway roof, and one continuous roof with it: same plane, same thickness, seams lined up."]))
    v0_ = (gx0 - 1, gx1 + 1); yy0, yy1 = gy0 - 1, gy1 + 1
    hexa("Trim", [(v0_[0], yy0, gtop(yy0)), (v0_[1], yy0, gtop(yy0)), (v0_[1], yy1, gtop(yy1)), (v0_[0], yy1, gtop(yy1)),
                  (v0_[0], yy0, gtop(yy0) + RT), (v0_[1], yy0, gtop(yy0) + RT), (v0_[1], yy1, gtop(yy1) + RT), (v0_[0], yy1, gtop(yy1) + RT)],
         ["Roof Liner", "Standing Seam", "Trim", "Trim", "Trim", "Trim"])
    _px0 = C["porch"]["rect"][0] if C["porch"]["enabled"] else v0_[0]      # seams on the breezeway's spacing, so they run on across
    _n = math.ceil((v0_[0] - _px0 - SEAM / 2) / SEAM - 1e-9)
    seam_ribs(_px0 + _n * SEAM, v0_[1], yy0, yy1, lambda y: gtop(y) + RT)

PO = C["porch"]
if PO["enabled"]:
    px0, py0, px1, py1 = PO["rect"]
    ptop = lambda y: PO["high_height"] - (y - py0) * PO["pitch"] / 12
    if GA["enabled"] and abs(GA["pitch"] - PO["pitch"]) < 1e-9:
        ptop = gtop                                            # one continuous roof with the garage: the same plane (Maxwell 11/22/2026)
    PT = PO.get("roof_thick_in", 8.4) / 12
    BL, BW, BT = [v / 12 for v in PO.get("brick_in", [8, 4, 2.25])]
    MATERIALS["Brick Paver"] = dict(color=PO.get("brick_color", "#8E4A35"), rough=0.85, canvas="brick", brick=[BL, BW], pattern=PO.get("brick_pattern", "herringbone"))
    rec("porch.slab", "slab", "Breezeway brick patio", "shell", info=dict(model=f"{ftin(px1 - px0)} x {ftin(py1 - py0)} brick patio under the breezeway roof",
        specs=[["Brick", f"Clay pavers {PO.get('brick_in', [8, 4, 2.25])[0]:g} x {PO.get('brick_in', [8, 4, 2.25])[1]:g} in, {PO.get('brick_pattern', 'herringbone')} (ASSUMED)"],
               ["Level", f"{GR['patio_drop_in']:g} in step down from the house entry, then {GR['garage_drop_in'] - GR['patio_drop_in']:g} in down into the garage"],
               ["Roof", f"{PO['pitch']:g}:12, {PO.get('roof_thick_in', 8.4):g} in thick (Maxwell's builder), continuous with the garage roof, underside {ftin(ptop(py0))} at the house end"],
               ["Posts", f"{len(PO['posts_x'])} per beam"]],
        notes=["Maxwell 11/22/2026: brick floor in the breezeway between the house and the garage, a small step down from the house and another into the garage.",
               "The S-10 foundation detail already shows a slab support ledge on the house wall here for an exterior slab a few inches below the floor."]))
    e = 0.004
    box("Concrete", px0 + e, px1 - e, py0, py1, PZ - BT - 0.33, PZ - BT)
    box("Brick Paver", px0 + e, px1 - e, py0, py1, PZ - BT, PZ)
    for yb in (py0 + 0.2, py1 - 0.6):
        box("Trim", px0, px1 - 1.0 - 0.01, yb, yb + 0.4, ptop(yb) - 1.0, ptop(yb))
        for xp in PO["posts_x"]:
            box("Trim", xp - 0.25, xp + 0.25, yb - 0.05, yb + 0.45, PZ, ptop(yb) - 1.0)
    rec("porch.roof", "roof", "Breezeway roof", "roof", info=dict(model=f"{PO['pitch']:g}:12 standing seam roof, {PO.get('roof_thick_in', 8.4):g} in thick",
        notes=["Maxwell 11/22/2026: his builder says the breezeway roof is 16 in thick. The ceiling stays where it was and the roof grows upward.",
               "It runs on into the garage roof as one roof: the same 2:12 plane and the same 16 in thickness, so the tops meet flush."]))
    rx1 = (GA["rect"][0] - 1.0) if GA["enabled"] else px1
    ry1 = (GA["rect"][3] + 1.0) if GA["enabled"] else py1 + 1
    hexa("Trim", [(px0, py0 - 0.5, ptop(py0 - 0.5)), (rx1, py0 - 0.5, ptop(py0 - 0.5)), (rx1, ry1, ptop(ry1)), (px0, ry1, ptop(ry1)),
                  (px0, py0 - 0.5, ptop(py0 - 0.5) + PT), (rx1, py0 - 0.5, ptop(py0 - 0.5) + PT), (rx1, ry1, ptop(ry1) + PT), (px0, ry1, ptop(ry1) + PT)],
         ["Drywall", "Standing Seam", "Trim", "Trim", "Trim", "Trim"])     # closed (the audit counts on closed solids); its end face sits against the garage roof edge
    seam_ribs(px0, rx1, py0 - 0.5, ry1, lambda y: ptop(y) + PT)

GH = C["greenhouse"]
if GH["enabled"]:
    hx0, hy0, hx1, hy1 = GH["rect"]
    htop = lambda y: GH["north_height"] - (y - hy0) * (GH["north_height"] - GH["south_height"]) / (hy1 - hy0)
    rec("greenhouse", "structure", "Greenhouse", "shell", info=dict(model="Greenhouse, delegated design / deferred submittal", specs=[["Size", f"{ftin(hx1 - hx0)} x {ftin(hy1 - hy0)}"]], notes=["Heights ASSUMED from the A-20 dashed outline."]))
    box("Gravel", hx0, hx1, hy0, hy1, GROUND_Z, -0.3)
    box("Polycarbonate", hx0, hx1, hy1 - 0.05, hy1, 0, GH["south_height"])
    prof = [(hy0, 0), (hy1, 0), (hy1, htop(hy1)), (hy0, htop(hy0))]
    prism_x("Polycarbonate", hx0, hx0 + 0.05, prof)
    prism_x("Polycarbonate", hx1 - 0.05, hx1, prof)
    quad("Polycarbonate", [(hx0, hy0, htop(hy0)), (hx1, hy0, htop(hy0)), (hx1, hy1, htop(hy1)), (hx0, hy1, htop(hy1))])
    for k in range(9):
        x = hx0 + k * (hx1 - hx0) / 8
        prism_x("Black Metal", x - 0.12, x + 0.12, [(hy0, htop(hy0) - 0.45), (hy1, htop(hy1) - 0.45), (hy1, htop(hy1) + 0.05), (hy0, htop(hy0) + 0.05)])
        box("Black Metal", x - 0.12, x + 0.12, hy1 - 0.3, hy1 - 0.06, 0, htop(hy1) - 0.45)

# ------------------------------------------------------------------ furniture the browser builds
# Most furniture is still the baked Blender export (site/models/furniture_*.glb). Pieces marked web = true in
# [furnishings] are built here instead, and meta tells the viewer what to take out of the export: replace_nodes by
# name, cull boxes for pieces that were merged into per material meshes, and move_nodes for pieces that only moved.
MATERIALS.update({
    "Bedding": dict(color="#F1EEE8", rough=0.9),
    "Walnut Laminate": dict(color="#8A6040", rough=0.45, map="cabinet_oak.jpg", tile=0.8, grain="long"),
    "Chair Fabric": dict(color="#2B2D2F", rough=0.85),
    "Lamp Shade": dict(color="#F3EBDD", rough=0.8, opacity=0.92),
})
FURN = FU.get("items", []) if FU.get("enabled") else []
BYFID = {it["id"]: it for it in FURN}
if EC_STYLE == "open" and "entry_bench" in BYFID:   # the mudroom unit stretches east to the post wall
    BYFID["entry_bench"].update(EC.get("open_bench", {}))
WEB_META = dict(replace_nodes=[], cull=[], move_nodes={})
# Baked pieces that sat flush with another and flickered (tools/coplanar_audit.mjs): move_nodes [dx, dy, turn, dz] in plan
# feet. The chairs' rails were flush with the dining table's stretchers (two also with its doors), and the kitchen light's
# lens with its trim ring. Moves are 1/16 to 1/8 in.
# (The Gallinera dining set that needed the same is gone: the Shaker set below replaced it 11/21/2026.)
for _n, _mv in {"Light_Kitchen_1_lens": [0, 0, 0, -0.005]}.items():
    WEB_META["move_nodes"][_n] = _mv
FURN_MATS = ["Bedding", "Fabric #F1EEE8", "Fabric #9A6B4A", "Fabric #7D8A6C", "Fabric #56614A", "White Oak", "Upholstery", "Black Metal",
             "Brushed Nickel", "Cabinet Wood", "Plastic Grey", "painted_wooden_nightstand", "Lamp Shade", "Porcelain"]


def frame_at(cx, cy, facing):
    """Local (a, b) to plan: b runs toward the front (facing, compass degrees), a to the right of it."""
    t = math.radians(facing)
    fx, fy = math.sin(t), -math.cos(t)
    rx, ry = math.cos(t), math.sin(t)
    return lambda a, b: (cx + a * rx + b * fx, cy + a * ry + b * fy)


def lbox(mat, fr, a0, a1, b0, b1, z0, z1):
    p, q = fr(a0, b0), fr(a1, b1)
    box(mat, min(p[0], q[0]), max(p[0], q[0]), min(p[1], q[1]), max(p[1], q[1]), z0, z1)


def top_of(it):
    if it.get("on") and it["on"] in BYFID:
        o = BYFID[it["on"]]
        if o["type"] == "nightstand":
            return o.get("h", 2.0)
        if o["type"] == "l_desk":
            return o.get("height_in", 29.0) / 12
    return it.get("z", 0.0)


def web_bed(it):
    W, L = it.get("w", 5.25), it.get("l", 7.0)
    fr = frame_at(it["x"], it["y"], it["facing"])
    hb = -L / 2
    acc = paint(it.get("accent", "#9A6B4A"))
    lbox("White Oak", fr, -W / 2, W / 2, hb, hb + 0.22, 0.0, 3.5)                       # headboard
    lbox("White Oak", fr, -W / 2, W / 2, hb + 0.22, L / 2, 0.3, 0.95)                    # platform
    for a in (-W / 2 + 0.05, W / 2 - 0.3):
        for b in (hb + 0.25, L / 2 - 0.3):
            lbox("Black Metal", fr, a, a + 0.25, b, b + 0.25, 0.0, 0.3)
    mw, ml = 5.0, 80 / 12                                                                # queen mattress 60 x 80 in
    lbox("Bedding", fr, -mw / 2, mw / 2, hb + 0.27, hb + 0.27 + ml, 0.95, 1.85)
    lbox(acc, fr, -mw / 2 - 0.06, mw / 2 + 0.06, hb + 2.2, hb + 0.33 + ml, 1.25, 1.93)       # duvet over the lower part
    for a0 in (-mw / 2 + 0.15, 0.1):
        lbox("Bedding", fr, a0, a0 + 2.25, hb + 0.4, hb + 1.65, 1.85, 2.25)                # pillows


def web_nightstand(it):
    w, d, h = it.get("w", 1.4), it.get("d", 1.3), it.get("h", 2.0)
    fr = frame_at(it["x"], it["y"], it["facing"])
    lbox("White Oak", fr, -w / 2, w / 2, -d / 2, d / 2, 0.35, h)
    for a in (-w / 2 + 0.05, w / 2 - 0.15):
        for b in (-d / 2 + 0.05, d / 2 - 0.15):
            lbox("White Oak", fr, a, a + 0.1, b, b + 0.1, 0.0, 0.35)
    lbox("Black Metal", fr, -0.25, 0.25, d / 2, d / 2 + 0.05, h - 0.4, h - 0.33)            # drawer pull


def web_tv_console(it):
    """Low white oak media console under the living room TV (Maxwell 11/21/2026): slatted doors at both ends, an open
    middle bay for the network box and a game console, a soundbar on top, short black metal legs. Back against the wall."""
    w, d, h, leg = it.get("w", 5.5), it.get("d", 17 / 12), it.get("h", 22 / 12), it.get("leg", 4 / 12)
    fr = frame_at(it["x"], it["y"], it["facing"])
    b0, b1, t = -d / 2, d / 2, 0.06
    lbox("White Oak", fr, -w / 2, w / 2, b0, b1, h - 0.08, h)                         # top
    lbox("White Oak", fr, -w / 2, w / 2, b0, b1, leg, leg + t)                       # bottom
    lbox("White Oak", fr, -w / 2, w / 2, b0, b0 + 0.05, leg + t, h - 0.08)           # back (cord holes ASSUMED)
    bay = w / 3
    for a in (-w / 2, -w / 2 + bay - t / 2, w / 2 - bay - t / 2, w / 2 - t):         # sides and the two dividers
        lbox("White Oak", fr, a, a + t, b0, b1 - 0.07, leg + t, h - 0.08)
    lbox("White Oak", fr, -bay / 2, bay / 2, b0 + 0.05, b1 - 0.1, (leg + h) / 2 - 0.03, (leg + h) / 2)     # middle shelf
    for sgn in (-1, 1):                                                              # slatted doors on the end bays
        a0, a1 = (-w / 2 + 0.01, -w / 2 + bay - 0.04) if sgn < 0 else (w / 2 - bay + 0.04, w / 2 - 0.01)
        lbox("White Oak", fr, a0, a1, b1 - 0.07, b1 - 0.02, leg + 0.02, h - 0.1)
        k, a = 0, a0 + 0.08
        while a < a1 - 0.1:
            lbox("Walnut Laminate", fr, a, a + 0.02, b1 - 0.02, b1 - 0.015, leg + 0.06, h - 0.14)     # grooves between slats
            a += 0.12
        pa = a1 - 0.12 if sgn < 0 else a0 + 0.08
        lbox("Black Metal", fr, pa, pa + 0.04, b1 - 0.015, b1 + 0.03, h - 0.75, h - 0.3)          # pull at the meeting side
    for a in (-w / 2 + 0.1, w / 2 - 0.18):                                           # legs
        for b in (b0 + 0.08, b1 - 0.16):
            lbox("Black Metal", fr, a, a + 0.08, b, b + 0.08, 0.0, leg)
    lbox("Plastic Grey", fr, -0.55, 0.45, b0 + 0.25, b1 - 0.35, leg + t, leg + t + 0.25)                # router / network box
    lbox("Black Metal", fr, -0.45, 0.35, b0 + 0.2, b1 - 0.3, (leg + h) / 2, (leg + h) / 2 + 0.2)        # game console
    sb = it.get("soundbar", 3.0)
    if sb:
        lbox("Black Metal", fr, -sb / 2, sb / 2, b0 + 0.35, b0 + 0.72, h, h + 0.22)                    # soundbar


def web_table_lamp(it):
    z = top_of(it)
    cyl("Black Metal", it["x"], it["y"], z, z + 0.08, 0.28)
    cyl("Black Metal", it["x"], it["y"], z + 0.08, z + 1.0, 0.04)
    cyl("Lamp Glass", it["x"], it["y"], z + 0.85, z + 1.55, 0.5, 0.36)


def web_desk_lamp(it):
    z = top_of(it)
    cyl("Black Metal", it["x"], it["y"], z, z + 0.06, 0.25)
    cyl("Black Metal", it["x"], it["y"], z + 0.06, z + 1.4, 0.03)
    box("Black Metal", it["x"] - 0.7, it["x"] + 0.02, it["y"] - 0.03, it["y"] + 0.03, z + 1.36, z + 1.42)
    box("Lamp Glass", it["x"] - 0.95, it["x"] - 0.55, it["y"] - 0.12, it["y"] + 0.12, z + 1.3, z + 1.36)


def web_l_desk(it):
    """UPLIFT V2 L-shaped desk. corner = the L's outer corner (plan ft), facing = the way you face sitting at the main top.
    The main top runs from the corner to your left (side right) and the return comes back toward you at the corner end."""
    mL, mD = it["main"][0] / 12, it["main"][1] / 12
    rL, rW = it["ret"][0] / 12, it["ret"][1] / 12
    H, T = it.get("height_in", 29.0) / 12, it.get("top_in", 1.0) / 12
    fr0 = frame_at(it["corner"][0], it["corner"][1], it["facing"])
    s = -1 if it.get("side", "right") == "right" else 1                                  # local a runs away from the corner along the main top
    fr = lambda a, b: fr0(s * a, b)
    def L(mat, a0, a1, b0, b1, z0, z1):
        lbox(mat, fr, a0, a1, b0, b1, z0, z1)
    L("Walnut Laminate", 0, mL, -mD, 0, H - T, H)                                          # main top, back edge at b = 0
    L("Walnut Laminate", 0, rW, -mD - rL, -mD, H - T, H)                                   # return
    LW, LD = 80 / 304.8, 50 / 304.8                                                       # 50 x 80 mm legs
    bm = -mD / 2 + 0.2
    for (la, lb, foot) in ((mL - 0.55, bm, "b"), (rW / 2, bm, "b"), (rW / 2, -mD - rL + 0.55, "a")):
        L("Black Metal", la - LD / 2, la + LD / 2, lb - LW / 2, lb + LW / 2, 0.08, H - T - 0.1)
        if foot == "b":
            L("Black Metal", la - 0.1, la + 0.1, -mD + 0.15, -0.1, 0.0, 0.08)
        else:
            L("Black Metal", 0.1, rW - 0.1, lb - 0.1, lb + 0.1, 0.0, 0.08)
    L("Black Metal", 0.3, mL - 0.4, -mD / 2 + 0.1, -mD / 2 + 0.3, H - T - 0.1, H - T)     # frame under the tops
    L("Black Metal", rW / 2 - 0.1, rW / 2 + 0.1, -mD - rL + 0.4, -mD + 0.6, H - T - 0.1, H - T)
    L("Black Metal", rW + 0.05, rW + 0.35, -mD - 0.02, -mD + 0.25, H - T - 0.07, H - T)   # keypad, front edge
    L("Paint #1E2022", mL - 2.4, mL - 0.6, -mD + 0.2, -mD + 1.4, H, H + 0.01)             # desk pad
    MATERIALS.setdefault("Paint #1E2022", dict(color="#1E2022", rough=0.8))


def web_office_chair(it):
    cx, cy = it["x"], it["y"]
    fr = frame_at(cx, cy, it["facing"])
    for k in range(5):                                                                     # five star base on casters
        t = 2 * math.pi * k / 5
        dx, dy, px, py = math.cos(t), math.sin(t), -math.sin(t) * 0.05, math.cos(t) * 0.05
        a, b = (cx + 0.1 * dx, cy + 0.1 * dy), (cx + 1.05 * dx, cy + 1.05 * dy)
        hexa("Black Metal", [(a[0] - px, a[1] - py, 0.22), (b[0] - px, b[1] - py, 0.18), (b[0] - px, b[1] - py, 0.26), (a[0] - px, a[1] - py, 0.32),
                             (a[0] + px, a[1] + py, 0.22), (b[0] + px, b[1] + py, 0.18), (b[0] + px, b[1] + py, 0.26), (a[0] + px, a[1] + py, 0.32)])
        cyl("Black Metal", b[0], b[1], 0.0, 0.18, 0.08)
    cyl("Black Metal", cx, cy, 0.3, 1.45, 0.09)
    lbox("Chair Fabric", fr, -0.85, 0.85, -0.8, 0.85, 1.45, 1.72)                         # seat
    lbox("Chair Fabric", fr, -0.8, 0.8, -1.0, -0.82, 1.95, 3.45)                          # back
    lbox("Black Metal", fr, -0.1, 0.1, -0.95, -0.75, 1.45, 1.95)
    for a in (-0.95, 0.8):                                                                 # arms
        lbox("Black Metal", fr, a, a + 0.15, -0.1, 0.05, 1.72, 2.3)
        lbox("Black Metal", fr, a - 0.02, a + 0.17, -0.5, 0.45, 2.3, 2.4)


# The baked site has a concrete pad under the kitchen's south service window that is not on the drawings (Maxwell,
# 11/16/2026). The pads at the bi-parting door and the west door stay.
WEB_META["cull"].append(dict(box=[6.9, 51.9, -1.0, 13.1, 56.1, 0.2], materials=["Concrete"], parts="site"))
# The baked pad at the bi-parting door ran x 17-29, 10 in west of the D120-80 rough opening (x 17.81-29.81; Maxwell,
# 11/21/2026). Drop it and pour it here centred on the door, same 12 x 4 ft and same height.
_sl = next(o_ for o_ in C["openings"] if o_["kind"] == "slider" and o_["wall"] == "S")
WEB_META["cull"].append(dict(box=[16.9, 51.9, -1.0, 29.1, 56.1, 0.2], materials=["Concrete"], parts="site"))
_pw, _pd = 12.0, 4.0
_pc = (_sl["start"] + _sl["end"]) / 2
rec("site.slider_pad", "slab", "Concrete pad at the bi-parting door", "shell", room="Yard",
    info=dict(model="Concrete landing pad outside the south bi-parting door (ASSUMED, not on the drawings)",
              specs=[["Size", f"{ftin(_pw)} x {ftin(_pd)}"], ["Position", "centred on the D120-80 door opening"]],
              notes=["Centred on the door (Maxwell, 11/21/2026); the Blender pad sat 10 in to the west."]))
box("Concrete", _pc - _pw / 2, _pc + _pw / 2, HD + 0.0, HD + _pd, -0.6, -0.05)

# ------------------------------------------------------------------ bath 1 wet room, built here (Maxwell, 11/21/2026)
# The baked wet room had its tile behind the drywall on the west and south walls (the partitions grew 5/8 in of drywall
# each side, 11/21/2026), a bench 11 in short of the west wall, a bare vertical bar on the north wall, a rain head on a
# wall arm, a flat disc through the south wall and a black square (an unlit niche) half in the east wall. All of it but
# the floor tile and the trench drain is dropped and rebuilt here to A-11: bench seat across the north end, trench drain,
# rain head in the ceiling over the south half, three valve trims and a handheld on a slide bar on the west wall.
def _wet_faces(it):
    """inner faces of the wet room's walls as built (after the drywall growth): x0, x1, y0, y1"""
    x0w, x1w, y0w, y1w = it["x0"], it["x1"], it["y0"], it["y1"]
    xm, ym = (x0w + x1w) / 2, (y0w + y1w) / 2
    fx0 = max([r_[1] for r_ in INT_RECTS if r_[0] < x0w + 0.2 and r_[1] > x0w - 0.6 and r_[2] < ym + 2 and r_[3] > ym] or [x0w])
    fy0 = max([r_[3] for r_ in INT_RECTS if r_[2] < y0w + 0.2 and r_[3] > y0w - 0.6 and r_[0] < xm and r_[1] > xm] or [y0w])
    fy1 = min([r_[2] for r_ in INT_RECTS if r_[2] < y1w + 0.6 and r_[3] > y1w - 0.2 and r_[0] < xm and r_[1] > xm] or [y1w])
    return fx0, min(x1w, HW - T), fy0, fy1


WET = []
MATERIALS.update({"Shower Chrome": dict(color="#D6D8DA", rough=0.12, metal=1.0), "Hose": dict(color="#C9CBCD", rough=0.25, metal=0.9)})
for it in FURN:
    if it.get("type") != "wetroom":
        continue
    x0w, x1w, y0w, y1w = it["x0"], it["x1"], it["y0"], it["y1"]
    fx0, fx1, fy0, fy1 = _wet_faces(it)
    WET.append((fx0, fx1, fy0, fy1))
    ztop = it.get("ceiling", 9.0) - 0.005                   # just under the ceiling face, so the two never flicker
    tt = 0.03                                                  # tile and setting bed, 3/8 in
    WEB_META["cull"] += [dict(box=[x0w - 0.4, y0w - 0.1, -0.1, x1w + 0.2, y1w + 0.3, ztop + 0.2], materials=["Tile Wall", "Counter"]),
                         dict(box=[x0w - 0.2, y0w - 0.1, 0.3, x1w + 0.2, y1w + 0.3, ztop], materials=["Brushed Nickel"]),
                         dict(box=[x0w, y1w - 0.3, 3.0, x1w + 0.3, y1w + 0.3, 6.0], materials=["Appliance Interior"])]
    room = room_at((fx0 + fx1) / 2, (fy0 + fy1) / 2)
    rec(f"furniture.{it['id']}.tile", "furniture", "Shower wall tile", "furniture", tog="finish", room=room,
        info=dict(model="Wall tile, floor to ceiling on all four wet room walls (finish ASSUMED)",
                  notes=["Stops at the shower side of the walk in opening; the jambs and the bath side stay painted drywall (Maxwell, 11/21/2026: the tile came out of the shower)."]))
    o0, o1 = it.get("walk_in", [0, 0])
    box("Tile Wall", fx0, fx0 + tt, fy0, o0, 0.01, ztop)          # west wall, either side of the walk in opening
    box("Tile Wall", fx0, fx0 + tt, o1, fy1, 0.01, ztop)
    box("Tile Wall", fx1 - tt, fx1, fy0 + tt, fy1 - tt, 0.01, ztop)   # east
    box("Tile Wall", fx0 + tt, fx1 - tt, fy0, fy0 + tt, 0.01, ztop)   # north
    box("Tile Wall", fx0 + tt, fx1 - tt, fy1 - tt, fy1, 0.01, ztop)   # south
    # bench seat across the full width of the north end, tiled, quartz top (A-11 BENCH SEAT)
    bd, bh = it.get("bench_d", 13 / 12), it.get("bench_h", 1.5)
    rec(f"furniture.{it['id']}.bench", "furniture", "Shower bench", "furniture", tog="finish", room=room,
        info=dict(model=f"Built in tiled bench, wall to wall across the north end, {ftin(bd)} deep, seat {ftin(bh)} high, quartz top (A-11 BENCH SEAT; finish ASSUMED)",
                  notes=["Runs the full width of the shower (Maxwell, 11/21/2026: it stopped short of the west wall). It ends at the walk in opening's north jamb, as A-11 draws it."]))
    box("Tile Wall", fx0 + tt, fx1 - tt, fy0 + tt, fy0 + bd - 0.02, 0.01, bh - 0.07)
    box("Counter", fx0 + tt, fx1 - tt, fy0 + tt, fy0 + bd, bh - 0.07, bh)
    # rain head flush with the ceiling over the south half (A-11 RAIN HEAD), on a short ceiling arm
    hx, hy = it.get("head_x", (fx0 + fx1) / 2), it.get("head_y", 29.82)
    rec(f"furniture.{it['id']}.rain", "furniture", "Rain shower head", "furniture", tog="finish", room=room,
        info=dict(model="12 in round ceiling mount rain head, polished chrome (A-11 RAIN HEAD; model ASSUMED)",
                  notes=["Where A-11 draws it, over the south half of the shower. It replaces the wall arm head on the south wall."]))
    cyl("Shower Chrome", hx, hy, ztop - 0.6, ztop, 0.035)
    cyl("Shower Chrome", hx, hy, ztop - 0.62, ztop - 0.58, 0.5, 0.48)
    cyl("Shower Chrome", hx, hy, ztop - 0.02, ztop, 0.12)
    # three valve trims and the handheld on a slide bar, west wall south of the drain (A-11)
    xv = fx0 + tt
    rec(f"furniture.{it['id']}.valves", "furniture", "Shower valves and handheld", "furniture", tog="finish", room=room,
        info=dict(model="Thermostatic valve with two volume controls (rain head, handheld), and a handheld on a 30 in slide bar (A-11; models ASSUMED)",
                  notes=["Valves and handheld on the west wall as A-11 draws them. The bar on the north wall is gone (Maxwell, 11/21/2026: he could not tell what it was)."]))
    for yv in it.get("valves_y", [28.1, 28.6, 29.1]):
        box("Shower Chrome", xv, xv + 0.03, yv - 0.17, yv + 0.17, 3.73, 4.07)       # square trim plate
        box("Shower Chrome", xv + 0.03, xv + 0.2, yv - 0.04, yv + 0.04, 3.86, 3.94)  # lever
    ys0, ys1 = it.get("slide_y", [29.75, 30.95])
    yb = (ys0 + ys1) / 2 + 0.25
    box("Shower Chrome", xv, xv + 0.12, ys0 - 0.06, ys0 + 0.06, 3.2, 3.35)          # supply elbow
    box("Shower Chrome", xv + 0.05, xv + 0.12, yb - 0.025, yb + 0.025, 3.7, 6.2)   # slide bar
    for zb in (3.7, 6.2):
        box("Shower Chrome", xv, xv + 0.12, yb - 0.04, yb + 0.04, zb - 0.05, zb + 0.05)
    box("Shower Chrome", xv + 0.1, xv + 0.2, yb - 0.04, yb + 0.04, 5.35, 5.5)       # holder on the bar
    box("Shower Chrome", xv + 0.17, xv + 0.24, yb - 0.035, yb + 0.035, 4.75, 5.55)  # handle
    cyl("Shower Chrome", xv + 0.27, yb, 5.55, 5.62, 0.16, 0.14)                     # spray face
    for k in range(6):                                                              # hose looping down from the elbow
        a, b = k / 6, (k + 1) / 6
        za, zb = 3.27 - 0.9 * math.sin(math.pi * a), 3.27 - 0.9 * math.sin(math.pi * b)
        ya, yb2 = ys0 + (yb - ys0) * a, ys0 + (yb - ys0) * b
        if k == 5:
            zb = 4.75
        box("Hose", xv + 0.1, xv + 0.15, min(ya, yb2) - 0.02, max(ya, yb2) + 0.02, min(za, zb), max(za, zb))


# ------------------------------------------------------------------ bath 2 tub: fabric shower curtain (Maxwell, 11/21/2026)
def thin_panel(mat, p, q, z0, z1, t=0.01):
    """a thin vertical panel between plan points p and q"""
    dx, dy = q[0] - p[0], q[1] - p[1]
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy / L * t / 2, dx / L * t / 2
    c = [(p[0] - nx, p[1] - ny), (q[0] - nx, q[1] - ny), (q[0] + nx, q[1] + ny), (p[0] + nx, p[1] + ny)]
    hexa(mat, [(x, y, z0) for x, y in c] + [(x, y, z1) for x, y in c])


for it in FURN:
    if it.get("type") != "tub" or not it.get("curtain"):
        continue
    cu = it["curtain"]
    WEB_META["replace_nodes"].append(cu.get("replaces", "tub_glass_panel"))
    x0c, x1c = cu.get("x", [it["x0"], it["x1"]])
    yr, zr = cu.get("y", it["y1"] - 0.12), cu.get("rod_z", 6.6)
    fab = paint(cu.get("color", "#DCD6C8"))
    MATERIALS[fab].update(rough=0.92)
    rec(f"furniture.{it['id']}.curtain", "furniture", "Shower curtain", "furniture", tog="finish", room=room_at((x0c + x1c) / 2, yr),
        info=dict(model="Fabric shower curtain (cotton or linen look, 72 x 72 in class, colour ASSUMED) on a straight brushed nickel rod, wall to wall",
                  notes=["Fabric curtain instead of the fixed glass panel (Maxwell, 11/21/2026). Shown drawn most of the way, open at the faucet end."]))
    box("Brushed Nickel", x0c, x1c, yr - 0.035, yr + 0.035, zr - 0.035, zr + 0.035)
    for xe in (x0c, x1c):                                                           # wall flanges
        cx_ = xe + (0.02 if xe == x0c else -0.02)
        box("Brushed Nickel", min(xe, cx_), max(xe, cx_), yr - 0.1, yr + 0.1, zr - 0.1, zr + 0.1)
    span = cu.get("drawn", 0.7) * (x1c - x0c)                                       # the curtain bunches toward the west end
    n = max(4, int(span / 0.3))
    amp = 0.11
    xs = [x0c + 0.03 + k * (span - 0.03) / n for k in range(n + 1)]
    pts = [(xx, yr + (amp if k % 2 else -amp) * (0.6 + 0.4 * (k % 3 == 1))) for k, xx in enumerate(xs)]
    zb = cu.get("bottom_z", 1.95)
    for k in range(n):
        thin_panel(fab, pts[k], pts[k + 1], zb, zr - 0.12)
    for k in range(0, n + 1, 1):                                                    # rings on the rod
        box("Brushed Nickel", xs[k] - 0.02, xs[k] + 0.02, yr - 0.05, yr + 0.05, zr - 0.13, zr + 0.06)


# ------------------------------------------------------------------ closet 1: shelves, rods and clothes (Maxwell, 11/21/2026)
# A-11 shows clothes shelving along the west room's west wall and around the east bay. Shelf and rod units are fixtures
# (Cabinets, fixtures and trim); the clothes, folded stacks and shoes are Belongings.
CL1 = C.get("closet1", {})
GARMENTS = ["#2F3A4A", "#8C9AA6", "#E9E4DA", "#6B7F5E", "#B5533C", "#3D3D3D", "#C9B89A", "#4E6E8E", "#F2F0EA", "#7A4E3A", "#A7B59A", "#1F2A36", "#D7C3B0", "#5B5F7A"]
if CL1.get("enabled"):
    import random as _rnd
    _rg = _rnd.Random(7)
    sh = paint(CL1.get("color", "#F1EFEA"))
    for u in CL1.get("units", []):
        x0u, y0u, x1u, y1u = u["rect"]
        along_x = (x1u - x0u) >= (y1u - y0u)
        back = u["back"]                                       # N, S, E or W: the wall the unit stands against
        L0, L1 = (x0u, x1u) if along_x else (y0u, y1u)
        dep = (y1u - y0u) if along_x else (x1u - x0u)

        def U(mat, a0, a1, d0, d1, z0, z1):                    # a along the unit, d out from the back wall
            if along_x:
                yy = (y0u + d0, y0u + d1) if back == "N" else (y1u - d1, y1u - d0)
                box(mat, a0, a1, yy[0], yy[1], z0, z1)
            else:
                xx = (x0u + d0, x0u + d1) if back == "W" else (x1u - d1, x1u - d0)
                box(mat, xx[0], xx[1], a0, a1, z0, z1)

        rec(f"closet1.{u['id']}", "furniture", u.get("name", "Closet shelving"), "furniture", tog="finish", room=room_at((x0u + x1u) / 2, (y0u + y1u) / 2),
            info=dict(model=f"Closet system, painted shelves and brushed nickel rods, {ftin(L1 - L0)} long, {ftin(dep)} deep (layout from A-11 CLOTHES SHELVING; details ASSUMED)",
                      specs=[["Hanging", {"double": "double hang, rods at 3'-6\" and 7'-0\"", "long": "long hang, rod at 5'-8\"", "shelves": "no rod"}[u["kind"]]],
                             ["Shelves", "top shelf at 7'-4\" and one over the long hang" if u["kind"] != "shelves" else "seven shelves, 12 in apart"]],
                      notes=["Fills the master closet (Maxwell, 11/21/2026)."]))
        t_ = 0.06
        for a in (L0, L1 - t_):                                 # end panels
            U(sh, a, a + t_, 0, dep, 0, 7.5)
        if u["kind"] == "shelves":
            for k in range(8):
                U(sh, L0 + t_, L1 - t_, 0, dep, 0.3 + k * 1.0, 0.36 + k * 1.0)
        else:
            U(sh, L0 + t_, L1 - t_, 0, dep, 7.3, 7.36)          # top shelf
            rods = [3.5, 7.0] if u["kind"] == "double" else [5.67]
            if u["kind"] == "long":
                U(sh, L0 + t_, L1 - t_, 0, dep, 6.2, 6.26)
            for zr_ in rods:
                U("Brushed Nickel", L0 + t_, L1 - t_, dep / 2 - 0.03, dep / 2 + 0.03, zr_ - 0.03, zr_ + 0.03)
    # belongings: clothes on the rods, folded stacks on the shelves, shoes on the floor of the shelf towers
    rec("closet1.clothes", "furniture", "Clothes", "furniture", room="Closet 1",
        info=dict(model="Hanging clothes, folded stacks and shoes (stand ins)", notes=["Belongings, so they go with that layer."]))
    for u in CL1.get("units", []):
        x0u, y0u, x1u, y1u = u["rect"]
        along_x = (x1u - x0u) >= (y1u - y0u)
        back = u["back"]
        L0, L1 = (x0u, x1u) if along_x else (y0u, y1u)
        dep = (y1u - y0u) if along_x else (x1u - x0u)

        def U(mat, a0, a1, d0, d1, z0, z1):
            if along_x:
                yy = (y0u + d0, y0u + d1) if back == "N" else (y1u - d1, y1u - d0)
                box(mat, a0, a1, yy[0], yy[1], z0, z1)
            else:
                xx = (x0u + d0, x0u + d1) if back == "W" else (x1u - d1, x1u - d0)
                box(mat, xx[0], xx[1], a0, a1, z0, z1)

        if u["kind"] == "shelves":
            for k in range(1, 7):
                z0s = 0.36 + k * 1.0
                a = L0 + 0.12
                while a < L1 - 0.5:
                    w_ = _rg.uniform(0.7, 1.0); h_ = _rg.uniform(0.25, 0.55)
                    U(paint(_rg.choice(GARMENTS)), a, min(a + w_, L1 - 0.1), 0.15, dep - 0.2, z0s, z0s + h_)
                    a += w_ + 0.12
            for k in range(int((L1 - L0 - 0.2) / 0.5)):          # shoes on the bottom shelf
                a = L0 + 0.12 + k * 0.5
                U(paint(_rg.choice(["#2B2420", "#6E4B32", "#E8E6E1", "#1E1E1E"])), a, a + 0.32, 0.3, dep - 0.2, 0.36, 0.7)
            continue
        rods = [3.5, 7.0] if u["kind"] == "double" else [5.67]
        for zr_ in rods:
            a = L0 + 0.15
            while a < L1 - 0.15:
                c_ = paint(_rg.choice(GARMENTS))
                ln = (2.3 if zr_ > 4 and u["kind"] == "double" else 2.4) if u["kind"] == "double" else _rg.choice([2.6, 3.0, 3.6, 4.2])
                ln *= _rg.uniform(0.9, 1.05)
                U("Brushed Nickel", a + 0.03, a + 0.05, dep / 2 - 0.02, dep / 2 + 0.02, zr_ - 0.12, zr_ + 0.04)   # hanger hook
                U(c_, a, a + 0.07, dep / 2 - 0.8, dep / 2 + 0.8, zr_ - 0.12 - ln, zr_ - 0.12)
                a += _rg.uniform(0.13, 0.2)
        for a in [L0 + 0.15 + k * 1.0 for k in range(int((L1 - L0 - 0.3) / 1.0))]:  # folded stacks on the top shelf
            U(paint(_rg.choice(GARMENTS)), a, a + 0.8, 0.2, dep - 0.3, 7.36, 7.36 + _rg.uniform(0.3, 0.6))

MATERIALS.update({
    "Rubber": dict(color="#1F2121", rough=0.95),
    "Mudroom Paint": dict(color="#C7CDBF", rough=0.55),      # light sage, ASSUMED
    "Stone Counter": dict(color="#B8B0A4", rough=0.35),
    "Cabinet Glass": dict(color="#AEB8B6", rough=0.05, metal=0.1, opacity=0.35),
})


def web_bench(it):
    """Built-in mudroom unit filling the entry alcove, after Maxwell's reference photo (11/17/2026). Seen from the
    front, left to right: a base cabinet with a stone counter and a tall cabinet over it, then the bench with open bays
    (a rubber boot tray with a divider in each), a paneled back with coat hooks, open cubbies above the hooks, and glass
    door cabinets across the top. u runs left to right seen from the front, v from the back wall out, z up."""
    W, D, Ztop = it.get("w", 8.0), it.get("alcove_d", 1.5), it.get("top", 7.95)
    h, d = it.get("h", 1.5), it.get("d", 1.25)
    cw = it.get("cab_w", 2.0)                                   # left column: base cabinet + tall cabinet
    fr0 = frame_at(it["x"], it["y"] - d / 2, it["facing"])      # origin at the back wall, centre of the unit
    fr = lambda u, v: fr0(W / 2 - u, v)
    M, P = "Mudroom Paint", 0.06

    def L(mat, u0, u1, v0, v1, z0, z1):
        lbox(mat, fr, u0, u1, v0, v1, z0, z1)

    def knob(u, v, z):
        L("Black Metal", u - 0.04, u + 0.04, v, v + 0.06, z - 0.04, z + 0.04)

    def doors(u0, u1, v, z0, z1, n, glass=False):              # shaker doors on a carcass face at depth v
        dw = (u1 - u0) / n
        for k in range(n):
            a0, a1 = u0 + k * dw + 0.01, u0 + (k + 1) * dw - 0.01
            if glass:
                for (p0, p1, q0, q1) in ((a0, a1, z0, z0 + 0.2), (a0, a1, z1 - 0.2, z1), (a0, a0 + 0.2, z0, z1), (a1 - 0.2, a1, z0, z1)):
                    L(M, p0, p1, v, v + 0.06, q0, q1)
                L("Cabinet Glass", a0 + 0.2, a1 - 0.2, v + 0.02, v + 0.04, z0 + 0.2, z1 - 0.2)
            else:
                L(M, a0, a1, v, v + 0.04, z0, z1)
                for (p0, p1, q0, q1) in ((a0, a1, z0, z0 + 0.2), (a0, a1, z1 - 0.2, z1), (a0, a0 + 0.2, z0, z1), (a1 - 0.2, a1, z0, z1)):
                    L(M, p0, p1, v + 0.04, v + 0.07, q0, q1)  # raised stiles and rails
            knob(a1 - 0.12 if k % 2 == 0 else a0 + 0.12, v + (0.06 if glass else 0.07), z0 + 0.3 if z0 > 4 else z1 - 0.3)

    # ---- left column: base cabinet with a drawer, stone counter, tall cabinet over it
    L(M, 0, cw, 0, D - 0.25, 0.0, 0.33)                                                   # toe kick
    L(M, 0, cw, 0, D - 0.1, 0.33, 2.9)                                                    # base carcass
    L(M, 0.01, cw - 0.01, D - 0.1, D - 0.06, 2.45, 2.88)                                  # drawer front
    knob(cw / 2 - 0.2, D - 0.06, 2.66); knob(cw / 2 + 0.2, D - 0.06, 2.66)
    doors(0, cw, D - 0.1, 0.36, 2.42, 2)
    L("Stone Counter", 0, cw, 0, D, 2.9, 3.0)
    L("Stone Counter", 0, cw, 0, 0.06, 3.0, 3.35)                                         # backsplash
    L(M, 0, cw, 0, 1.0, 4.5, 6.55)                                                        # tall cabinet carcass
    doors(0, cw, 1.0, 4.5, 6.55, 2)
    # ---- bench, open below in bays, a rubber boot tray with a divider in each bay
    b0u = cw
    n = max(1, int(it.get("bays", 3)))
    bw = (W - b0u - (n + 1) * P) / n
    L(M, b0u, W, 0, d, h - 0.12, h)                                                       # seat
    for k in range(n + 1):
        a0 = b0u + k * (bw + P)
        L(M, a0, a0 + P, 0, d - 0.03, 0.0, h - 0.12)                                      # end panels and bay dividers
    lip, rim = 0.11, 0.03                                                                 # 1 1/4 in tall rubber lip
    for k in range(n):
        a0 = b0u + P + k * (bw + P) + 0.04
        a1 = a0 + bw - 0.08
        v0, v1 = 0.05, d - 0.03
        L("Rubber", a0, a1, v0, v1, 0.0, 0.02)
        L("Rubber", a0, a1, v0, v0 + rim, 0.02, lip); L("Rubber", a0, a1, v1 - rim, v1, 0.02, lip)
        L("Rubber", a0, a0 + rim, v0 + rim, v1 - rim, 0.02, lip); L("Rubber", a1 - rim, a1, v0 + rim, v1 - rim, 0.02, lip)
        ns = int(it.get("tray_slots", 2))
        for j in range(1, ns):                                                            # divider across the tray
            am = a0 + j * (a1 - a0) / ns
            L("Rubber", am - rim / 2, am + rim / 2, v0 + rim, v1 - rim, 0.02, lip - 0.02)
        for j in range(1, 4):                                                             # low drain ridges
            vv = v0 + j * (v1 - v0) / 4
            L("Rubber", a0 + rim, a1 - rim, vv - 0.01, vv + 0.01, 0.02, 0.045)
    # ---- paneled back, hooks, open cubbies, glass uppers
    L(M, b0u, W, 0, 0.04, h, 5.75)                                                        # back panel
    for (p0, p1, q0, q1) in ((b0u + 0.25, W - 0.25, h + 0.25, h + 0.4), (b0u + 0.25, W - 0.25, 4.7, 4.85),
                             (b0u + 0.25, b0u + 0.4, h + 0.25, 4.85), (W - 0.4, W - 0.25, h + 0.25, 4.85)):
        L(M, p0, p1, 0.04, 0.07, q0, q1)                                                  # raised panel frame
    L(M, b0u, W, 0.04, 0.09, 5.05, 5.4)                                                   # hook board
    nh = int(it.get("hooks", 5))
    for k in range(nh):
        u = b0u + 0.5 + k * (W - b0u - 1.0) / max(1, nh - 1)
        L("Black Metal", u - 0.03, u + 0.03, 0.09, 0.3, 5.12, 5.18)
        L("Black Metal", u - 0.03, u + 0.03, 0.26, 0.31, 5.0, 5.3)
    L(M, b0u, W, 0, 1.0, 5.75, 5.83)                                                      # cubby bottom
    L(M, b0u, W, 0, 1.0, 6.5, 6.58)                                                       # cubby top
    nc = int(it.get("cubbies", 2))
    for k in range(nc + 1):
        u = b0u + k * (W - b0u - P) / nc
        L(M, u, u + P, 0, 1.0, 5.83, 6.5)
    L(M, 0, W, 0, 1.0, 6.58, Ztop - 0.25)                                                 # upper cabinets
    doors(0, W, 1.0, 6.6, Ztop - 0.27, int(it.get("glass_doors", 8)), glass=True)
    L(M, 0, W, 0, 1.12, Ztop - 0.25, Ztop)                                                # crown band


def web_towel_warmer(it):
    """Ladder towel warmer on a wall that runs N-S (facing W): two posts with standoffs and five rails."""
    xw, y0, y1, z0, z1 = it["x"], it["y0"], it["y1"], it["z0"], it["z1"]
    xr = xw - 0.17
    for y in (y0, y1):
        box("Brushed Nickel", xr - 0.03, xr + 0.03, y - 0.03, y + 0.03, z0, z1)
        for z in (z0 + 0.3, z1 - 0.3):
            box("Brushed Nickel", xr, xw - 0.03, y - 0.02, y + 0.02, z - 0.02, z + 0.02)
    for k in range(5):
        z = z0 + 0.25 + k * (z1 - z0 - 0.4) / 4
        box("Brushed Nickel", xr - 0.025, xr + 0.025, y0, y1, z - 0.025, z + 0.025)


# the old towel bar (merged into the baked Brushed Nickel mesh) hung in the WC pocket door opening
WEB_META["cull"].append(dict(box=[33.0, 28.8, 3.9, 35.6, 29.25, 4.1], materials=["Brushed Nickel"]))

def web_l_couch(it):
    """L sectional in the living room's north east corner, from the ships ladder mockup Maxwell picked (option E,
    11/21/2026): the long leg along the north wall facing south, the short leg along the bath 1 wall facing west, its
    south end under the ladder's upper flight. Plain sage fabric, low black legs. corner = [x, y] of the outside
    corner (east end of the back, against the walls); nl, el = overall lengths along the north and east walls."""
    x1, y0 = it["corner"]
    NL, EL, D = it.get("nl", 9.5), it.get("el", 7.5), it.get("d", 3.1)
    AW, BD, LEG, SEAT, BASE, BACK, ARM = 0.5, 0.75, 0.25, 1.45, 1.05, 2.75, 2.1
    fab, dark = paint(it.get("color", "#8E9388")), paint(it.get("color2", "#7C8177"))
    xw, ys = x1 - NL, y0 + EL                                                      # west end, south end
    for (a0, a1, b0, b1) in ((xw, x1, y0, y0 + D), (x1 - D, x1, y0 + D, ys)):   # legs at the corners of both pieces
        for xa, ya in ((a0 + 0.1, b0 + 0.1), (a1 - 0.18, b0 + 0.1), (a0 + 0.1, b1 - 0.18), (a1 - 0.18, b1 - 0.18)):
            box("Black Metal", xa, xa + 0.08, ya, ya + 0.08, 0.0, LEG)
    box(dark, xw + AW, x1, y0, y0 + D, LEG, BASE)                                  # base, north leg
    box(dark, x1 - D, x1, y0 + D, ys - AW, LEG, BASE)                              # base, east leg
    box(dark, xw + AW, x1, y0, y0 + BD - 0.3, BASE, BACK)                          # back frames
    box(dark, x1 - BD + 0.3, x1, y0 + BD - 0.3, ys - AW, BASE, BACK)
    box(dark, xw, xw + AW, y0, y0 + D, LEG, ARM)                                   # arms
    box(dark, x1 - D, x1, ys - AW, ys, LEG, ARM)
    xs = x1 - BD                                                                   # seat cushions: three along the north leg, a corner one, two on the east leg
    n0 = xw + AW + 0.02
    step = (x1 - D - n0) / 3
    for k in range(3):
        box(fab, n0 + k * step + 0.01, n0 + (k + 1) * step - 0.01, y0 + BD, y0 + D - 0.02, BASE, SEAT)
    box(fab, x1 - D + 0.01, xs, y0 + BD, y0 + D + 0.01, BASE, SEAT)
    e0, e1 = y0 + D + 0.03, ys - AW - 0.02
    for k in range(2):
        box(fab, x1 - D + 0.02, xs, e0 + k * (e1 - e0) / 2 + 0.01, e0 + (k + 1) * (e1 - e0) / 2 - 0.01, BASE, SEAT)
    for k in range(4):                                                             # back cushions
        a = n0 + k * (xs - n0) / 4
        box(fab, a + 0.01, a + (xs - n0) / 4 - 0.01, y0 + BD - 0.3, y0 + BD, SEAT, BACK - 0.12)
    for k in range(3):
        b = y0 + BD + k * (e1 - y0 - BD) / 3
        box(fab, xs, xs + 0.3, b + 0.01, b + (e1 - y0 - BD) / 3 - 0.01, SEAT, BACK - 0.12)
    for (px, py, c) in ((xs - 0.75, y0 + BD + 0.05, "#B9AE9A"), (xs - 1.6, y0 + BD + 0.05, "#5E6D63")):   # two throw pillows in the corner
        box(paint(c), px, px + 0.7, py, py + 0.35, SEAT + 0.02, SEAT + 0.72)


def web_seated_person(it):
    """A 6'-0" adult sitting upright, to check head clearance (Maxwell 11/21/2026: someone on the couch as close to the
    ladder as they can sit). x, y = the middle of the back where it meets the seat back; facing = compass direction
    they face; seat = seat cushion top (ft), they sink 3/4 in. Proportions are typical for a 6 ft man: sitting height
    (seat to crown) 37 1/2 in, shoulders 24 1/2 in over the seat, buttock to knee 24 1/2 in, knee 22 1/2 in up."""
    fr = frame_at(it["x"], it["y"], it.get("facing", 270))
    s = it.get("seat", 1.45) - 0.06
    sit = it.get("sitting_in", 37.5) / 12
    skin, shirt, jeans, shoe = paint("#C99A78"), paint("#5A7896"), paint("#3B4A63"), paint("#2A2A2A")
    lbox(jeans, fr, -0.6, 0.6, 0.04, 0.85, s, s + 0.55)                          # hips
    for sg in (-1, 1):
        a0, a1 = sorted((sg * 0.05, sg * 0.56))
        lbox(jeans, fr, a0, a1, 0.6, 2.04, s + 0.04, s + 0.5)                    # thighs, out to the knee
        b0, b1 = sorted((sg * 0.1, sg * 0.5))
        lbox(jeans, fr, b0, b1, 1.62, 2.0, 0.28, s + 0.46)                       # shins
        lbox(shoe, fr, b0 - 0.02, b1 + 0.02, 1.55, 2.5, 0.0, 0.3)                 # shoes
        c0, c1 = sorted((sg * 0.6, sg * 0.8))
        lbox(shirt, fr, c0, c1, 0.14, 0.6, s + 1.05, s + 2.0)                    # upper arms
        d0, d1 = sorted((sg * 0.45, sg * 0.68))
        lbox(shirt, fr, d0, d1, 0.35, 1.25, s + 0.5, s + 1.08)                   # forearms, hands on the thighs
        lbox(skin, fr, d0, d1, 1.25, 1.65, s + 0.52, s + 0.62)
    lbox(shirt, fr, -0.6, 0.6, 0.04, 0.85, s + 0.55, s + 2.04)                   # torso to the shoulders
    lbox(skin, fr, -0.2, 0.2, 0.25, 0.62, s + 2.04, s + 2.34)                    # neck
    hx, hy = fr(0.0, 0.46)
    cyl(skin, hx, hy, s + 2.3, sit + s - 0.2, 0.31)                              # head
    cyl(paint("#4A3626"), hx, hy, sit + s - 0.2, sit + s, 0.32, 0.16)            # hair, to the crown


MATERIALS.update({
    "Honey Maple": dict(color="#E6B47C", rough=0.4, map="white_oak.jpg", normal="oak_normal.jpg", normal_scale=0.35, tile=0.8, grain="long"),
    "Jute Rug": dict(color="#8C7C66", rough=0.95),
    "Green Apple": dict(color="#8DB43C", rough=0.45),
})


def lhexa(mat, fr, corners):
    """hexahedron in a piece's local frame: corners = 8 (a, b, z), bottom four then top four, both counterclockwise"""
    hexa(mat, [(*fr(a, b), z) for a, b, z in corners])


def web_dining_table(it):
    """Shaker style solid maple table from Maxwell's reference photo (11/21/2026): plain thick top, a deep apron set
    back under it, square legs tapered on their two inside faces. facing = the way the long axis runs (0 = east west)."""
    L, W, H = it.get("l", 7.0), it.get("w", 40 / 12), it.get("h", 30 / 12)
    T, AP, LG, FT, SET = 1.25 / 12, 4 / 12, 2.75 / 12, 1.5 / 12, 1.5 / 12      # top, apron depth, leg at the top and foot, apron setback
    fr = frame_at(it["x"], it["y"], it.get("facing", 0))
    M = "Honey Maple"
    lbox(M, fr, -L / 2, L / 2, -W / 2, W / 2, H - T, H)                                   # top
    a1, b1 = L / 2 - SET, W / 2 - SET                                                     # outer faces of the legs and apron
    za = H - T - AP
    for sa in (-1, 1):
        lbox(M, fr, sa * a1, sa * (a1 - 0.07), -b1 + LG, b1 - LG, za, H - T)                  # end aprons
    for sb in (-1, 1):
        lbox(M, fr, -a1 + LG, a1 - LG, sb * b1, sb * (b1 - 0.07), za, H - T)                 # side aprons
    for sa in (-1, 1):
        for sb in (-1, 1):
            oa, ob = sa * a1, sb * b1                                                      # outer corner of the leg
            ia, ib = sa * (a1 - LG), sb * (b1 - LG)                                         # inner corner at the top
            fa, fb = sa * (a1 - FT), sb * (b1 - FT)                                         # inner corner at the foot
            zt = za - 0.02                                                                  # taper starts just under the apron
            lhexa(M, fr, [(oa, ob, 0.0), (fa, ob, 0.0), (fa, fb, 0.0), (oa, fb, 0.0),
                          (oa, ob, zt), (ia, ob, zt), (ia, ib, zt), (oa, ib, zt)])
            lbox(M, fr, min(oa, ia), max(oa, ia), min(ob, ib), max(ob, ib), zt, H - T)       # square block behind the apron


def web_dining_chair(it):
    """Matching side chair: square legs, the back legs raked back, a wide flat back panel with a lower rail under it,
    a sculpted (dished) seat, low side stretchers and a higher front stretcher. facing = the way the sitter faces."""
    W, D, SH = it.get("w", 18.5 / 12), it.get("d", 19.5 / 12), it.get("seat", 18 / 12)
    BH = it.get("back", 34 / 12)
    LG, RK = 1.5 / 12, 1.4 / 12                                                          # leg size, back rake at the top
    fr = frame_at(it["x"], it["y"], it["facing"])
    M = "Honey Maple"
    a0, a1, b0, b1 = -W / 2, W / 2, -D / 2, D / 2
    zs = SH - 1.25 / 12                                                                  # seat underside
    def bk(z):                                                                           # back face of the back legs at height z
        return b0 - RK * max(0.0, z - zs) / (BH - zs)
    for sa in (-1, 1):
        ao, ai = (a0, a0 + LG) if sa < 0 else (a1 - LG, a1)
        lbox(M, fr, ao, ai, b1 - LG, b1, 0.0, zs)                                          # front leg
        lhexa(M, fr, [(ao, b0, 0.0), (ai, b0, 0.0), (ai, b0 + LG, 0.0), (ao, b0 + LG, 0.0),
                      (ao, b0, zs), (ai, b0, zs), (ai, b0 + LG, zs), (ao, b0 + LG, zs)])  # back leg, straight to the seat
        lhexa(M, fr, [(ao, b0, zs), (ai, b0, zs), (ai, b0 + LG, zs), (ao, b0 + LG, zs),
                      (ao, bk(BH), BH), (ai, bk(BH), BH), (ai, bk(BH) + LG, BH), (ao, bk(BH) + LG, BH)])   # then raked back
        am = (ao + ai) / 2
        lbox(M, fr, am - 0.03, am + 0.03, b0 + LG, b1 - LG, 0.42, 0.53)                  # low side stretcher
    lbox(M, fr, a0 + LG, a1 - LG, b1 - LG / 2 - 0.03, b1 - LG / 2 + 0.03, 0.72, 0.83)    # front stretcher, higher
    lbox(M, fr, a0 + LG, a1 - LG, b0 + LG / 2 - 0.03, b0 + LG / 2 + 0.03, 0.42, 0.53)    # back stretcher
    for (p0, p1, q0, q1) in ((a0 + LG, a1 - LG, b1 - 0.07, b1 - 0.01), (a0 + LG, a1 - LG, b0 + 0.02, b0 + 0.08),
                             (a0 + 0.01, a0 + 0.07, b0 + LG, b1 - LG), (a1 - 0.07, a1 - 0.01, b0 + LG, b1 - LG)):
        lbox(M, fr, p0, p1, q0, q1, zs - 0.2, zs)                                         # seat rails
    # sculpted seat: thick at the back and sides, dished in the middle, rolled down at the front edge
    e, sb0, sb1 = 0.03, b0 - 0.01, b1 + 0.04
    zt, zd, zf = SH, SH - 0.05, SH - 0.04
    bm0, bm1 = sb0 + 0.45, sb1 - 0.3
    for (q0, q1, tq0, tq1) in ((sb0, bm0, zt, zd), (bm0, bm1, zd, zd), (bm1, sb1 - 0.08, zd, zt - 0.01), (sb1 - 0.08, sb1, zt - 0.01, zf)):
        lhexa(M, fr, [(a0 - e, q0, zs), (a1 + e, q0, zs), (a1 + e, q1, zs), (a0 - e, q1, zs),
                      (a0 - e, q0, tq0), (a1 + e, q0, tq0), (a1 + e, q1, tq1), (a0 - e, q1, tq1)])
    def at(z, d=0.0):
        return bk(z) + LG / 2 + d
    def tilted(p0, p1, z0, z1, t):                                                        # a board between the back legs, leaning with them
        lhexa(M, fr, [(p0, at(z0, -t / 2), z0), (p1, at(z0, -t / 2), z0), (p1, at(z0, t / 2), z0), (p0, at(z0, t / 2), z0),
                      (p0, at(z1, -t / 2), z1), (p1, at(z1, -t / 2), z1), (p1, at(z1, t / 2), z1), (p0, at(z1, t / 2), z1)])
    tilted(a0 + LG, a1 - LG, BH - 7.5 / 12, BH - 0.25 / 12, 0.07)                         # wide flat back panel
    tilted(a0 + LG, a1 - LG, BH - 12 / 12, BH - 10.5 / 12, 0.07)                          # lower rail


def web_fruit_bowl(it):
    z = it.get("z", 2.5)
    x, y = it["x"], it["y"]
    cyl("Honey Maple", x, y, z, z + 0.05, 0.28, 0.33)                                     # turned wooden bowl
    cyl("Honey Maple", x, y, z + 0.05, z + 0.3, 0.33, 0.52)
    for k, (dx, dy) in enumerate(((0, 0), (0.22, 0.08), (-0.2, 0.12), (0.05, -0.23), (-0.12, -0.15))):
        ax, ay, az = x + dx, y + dy, z + 0.22 + (0.06 if k == 0 else 0)
        cyl("Green Apple", ax, ay, az - 0.12, az, 0.07, 0.13)
        cyl("Green Apple", ax, ay, az, az + 0.11, 0.13, 0.05)


def web_jute_rug(it):
    fr = frame_at(it["x"], it["y"], it.get("facing", 0))
    lbox("Jute Rug", fr, -it["l"] / 2, it["l"] / 2, -it["w"] / 2, it["w"] / 2, 0.003, 0.033)


MATERIALS.update({
    "Cognac Leather": dict(color="#8A4B2E", rough=0.42),
    "Leather Stitch": dict(color="#5C2F1C", rough=0.6),
})


def web_bar_stool(it):
    """Counter stool after Maxwell's reference photo (11/21/2026): cognac leather seat with a curved low back that wraps
    round the sides, vertical channel stitching on the back, four thin black tapered legs splayed a little, and a square
    footrest ring. Seat height to suit the 36 in island counter (counter height, not bar height). a runs to the sitter's
    right, b toward the front (facing), z up."""
    H = it.get("seat_in", 26.0) / 12
    fr = frame_at(it["x"], it["y"], it.get("facing", 180))
    P = lambda a, b, z: (*fr(a, b), z)
    RS, CB, ST = 0.66, -0.08, 0.17                       # seat radius at the back, centre line of the rounded back, seat thickness
    FB, FW = 0.62, 0.64                                   # seat front edge, half width at the front
    # seat: a rectangle in front of the centre line and a half round behind it, cut in strips across
    hexa("Cognac Leather", [P(-RS, CB, H - ST), P(RS, CB, H - ST), P(FW, FB, H - ST), P(-FW, FB, H - ST),
                            P(-RS, CB, H), P(RS, CB, H), P(FW, FB, H - 0.02), P(-FW, FB, H - 0.02)])
    hexa("Cognac Leather", [P(-FW + 0.02, FB, H - ST + 0.02), P(FW - 0.02, FB, H - ST + 0.02), P(FW - 0.04, FB + 0.06, H - ST + 0.05), P(-FW + 0.04, FB + 0.06, H - ST + 0.05),
                            P(-FW + 0.02, FB, H - 0.02), P(FW - 0.02, FB, H - 0.02), P(FW - 0.04, FB + 0.06, H - 0.06), P(-FW + 0.04, FB + 0.06, H - 0.06)])   # rolled front edge
    n = 8
    for i in range(n):
        a0, a1 = -RS * 0.98 + 1.96 * RS * i / n, -RS * 0.98 + 1.96 * RS * (i + 1) / n
        b0, b1 = CB - math.sqrt(max(RS * RS - a0 * a0, 0)), CB - math.sqrt(max(RS * RS - a1 * a1, 0))
        hexa("Cognac Leather", [P(a0, b0, H - ST), P(a1, b1, H - ST), P(a1, CB, H - ST), P(a0, CB, H - ST),
                                P(a0, b0, H), P(a1, b1, H), P(a1, CB, H), P(a0, CB, H)])
    for a in (-0.22, 0.0, 0.22):                         # channel seams on the seat, front to back
        hexa("Leather Stitch", [P(a - 0.008, CB - math.sqrt(RS * RS - a * a) + 0.08, H - 0.01), P(a + 0.008, CB - math.sqrt(RS * RS - a * a) + 0.08, H - 0.01),
                                P(a + 0.008, FB - 0.05, H - 0.025), P(a - 0.008, FB - 0.05, H - 0.025),
                                P(a - 0.008, CB - math.sqrt(RS * RS - a * a) + 0.08, H + 0.006), P(a + 0.008, CB - math.sqrt(RS * RS - a * a) + 0.08, H + 0.006),
                                P(a + 0.008, FB - 0.05, H - 0.009), P(a - 0.008, FB - 0.05, H - 0.009)])
    # back: an arc of panels round the seat's back, leaning back, highest at the middle and sloping down toward the front
    R, T, LEAN, ZB = RS + 0.04, 0.08, 0.12, H - ST + 0.02
    TH = lambda th: H + 0.9 - 0.62 * (abs(th) / 60) ** 1.5
    ang = [-60 + 12 * k for k in range(11)]

    def ring(th, z, r):
        lean = LEAN * (z - ZB) / (H + 0.88 - ZB)
        t = math.radians(th)
        return P((r + lean) * math.sin(t), CB - (r + lean) * math.cos(t), z)
    for t0, t1 in zip(ang, ang[1:]):
        z0t, z1t = TH(t0), TH(t1)
        hexa("Cognac Leather", [ring(t0, ZB, R - T), ring(t0, ZB, R), ring(t1, ZB, R), ring(t1, ZB, R - T),
                                ring(t0, z0t, R - T), ring(t0, z0t, R), ring(t1, z1t, R), ring(t1, z1t, R - T)])
    for th in (-36, -12, 12, 36):                        # vertical channel stitching on the inside of the back
        z0, z1 = H + 0.26, TH(th) - 0.07
        d = math.degrees(0.008 / R)
        hexa("Leather Stitch", [ring(th - d, z0, R - T - 0.006), ring(th - d, z0, R - T + 0.01), ring(th + d, z0, R - T + 0.01), ring(th + d, z0, R - T - 0.006),
                                ring(th - d, z1, R - T - 0.006), ring(th - d, z1, R - T + 0.01), ring(th + d, z1, R - T + 0.01), ring(th + d, z1, R - T - 0.006)])
    for t0, t1 in zip(ang[1:-2], ang[2:-1]):             # the cross seam under the channels
        z0, z1 = H + 0.24, H + 0.26
        hexa("Leather Stitch", [ring(t0, z0, R - T - 0.006), ring(t0, z0, R - T + 0.01), ring(t1, z0, R - T + 0.01), ring(t1, z0, R - T - 0.006),
                                ring(t0, z1, R - T - 0.006), ring(t0, z1, R - T + 0.01), ring(t1, z1, R - T + 0.01), ring(t1, z1, R - T - 0.006)])
    # black metal: a plate under the seat, four tapered legs splayed out a little, and the footrest ring
    lbox("Black Metal", fr, -0.42, 0.42, -0.42, 0.42, H - ST - 0.04, H - ST)
    TOPA, TOPB, BOTA, BOTB = 0.4, 0.4, 0.55, 0.52
    legs = []
    for sa in (-1, 1):
        for sb in (-1, 1):
            top, bot = (sa * TOPA, sb * TOPB, H - ST - 0.02), (sa * BOTA, sb * BOTB, 0.0)
            legs.append((top, bot))
            w0, w1 = 0.035, 0.014                        # 7/8 in at the top, about 3/8 in at the foot
            pts = []
            for (a, b, z), w in ((bot, w1), (top, w0)):
                pts += [P(a - w, b - w, z), P(a + w, b - w, z), P(a + w, b + w, z), P(a - w, b + w, z)]
            hexa("Black Metal", pts)
    FZ = it.get("foot_in", 9.0) / 12
    f = FZ / (H - ST - 0.02)
    fa, fb = BOTA + (TOPA - BOTA) * f, BOTB + (TOPB - BOTB) * f
    r_ = 0.018
    lbox("Black Metal", fr, -fa, fa, fb - r_, fb + r_, FZ - r_, FZ + r_)          # front bar, the one you rest your feet on
    lbox("Black Metal", fr, -fa, fa, -fb - r_, -fb + r_, FZ - r_ + 0.002, FZ + r_ + 0.002)
    for sa in (-1, 1):
        lbox("Black Metal", fr, sa * fa - r_ - 0.001, sa * fa + r_ - 0.001, -fb + r_, fb - r_, FZ - r_ + 0.001, FZ + r_ + 0.001)
    for top, bot in legs:                                # glides under the feet
        lbox("Plastic Grey", fr, bot[0] - 0.02, bot[0] + 0.02, bot[1] - 0.02, bot[1] + 0.02, 0.003, 0.012)


WEB_BUILD = {"bed": web_bed, "nightstand": web_nightstand, "table_lamp": web_table_lamp, "desk_lamp": web_desk_lamp,
             "l_desk": web_l_desk, "office_chair": web_office_chair, "towel_warmer": web_towel_warmer, "bench": web_bench,
             "tv_console": web_tv_console, "l_couch": web_l_couch, "dining_table": web_dining_table, "dining_chair": web_dining_chair,
             "fruit_bowl": web_fruit_bowl, "jute_rug": web_jute_rug,
             "bar_stool": web_bar_stool, "seated_person": web_seated_person}
WEB_INFO = {
    "dining_table": lambda it: dict(model=f"Shaker style solid maple dining table, honey finish, {round(it.get('l', 7.0) * 12)} x {round(it.get('w', 40 / 12) * 12)} in, {round(it.get('h', 2.5) * 12)} in high (style from Maxwell's reference photo; maker and size ASSUMED)",
                                    specs=[["Seats", "8: three on each side and one at each end"], ["Legs", "square, tapered on the inside faces"], ["Clearance", "about 3 ft or more behind every chair pulled out"]],
                                    notes=["Replaced the Gallinera table and six chairs (Maxwell 11/21/2026, from his reference photo)."]),
    "dining_chair": lambda it: dict(model="Maple side chair to match the table: wide flat back panel and lower rail, sculpted seat, square legs with stretchers (style from Maxwell's reference photo, ASSUMED)",
                                    specs=[["Size", f"{round(it.get('w', 18.5 / 12) * 12, 1)} in wide, {round(it.get('d', 19.5 / 12) * 12, 1)} in deep, seat {round(it.get('seat', 1.5) * 12)} in, back {round(it.get('back', 34 / 12) * 12)} in"]]),
    "fruit_bowl": lambda it: dict(model="Wooden bowl of green apples"),
    "jute_rug": lambda it: dict(model=f"Natural jute rug, {ftin(it['w'])} x {ftin(it['l'])} (ASSUMED)", notes=["Big enough that the chairs stay on it when pulled out."]),
    "bar_stool": lambda it: dict(model="Counter stool, cognac leather with a channel stitched low back and black metal legs (style from Maxwell's photo, exact model ASSUMED)",
                                 specs=[["Seat height", f"{it.get('seat_in', 26.0):g} in, for the 36 in island counter"], ["Footrest", f"{it.get('foot_in', 9.0):g} in off the floor"],
                                        ["Size", "about 18 in wide, 18 in deep, back about 37 in high"]],
                                 notes=["Replaces the round wood bar stools (Maxwell, 11/21/2026). Counter height because the island is a standard 36 in counter; bar height stools (30 in seat) would sit too high."]),
    "seated_person": lambda it: dict(model="A 6'-0\" adult sitting upright, for checking head clearance (mockup)",
                                     specs=[["Crown of the head", f"{ftin(it.get('seat', 1.45) - 0.06 + it.get('sitting_in', 37.5) / 12)} above the floor"],
                                            ["Sitting height", f"{it.get('sitting_in', 37.5):g} in, seat to crown"]],
                                     notes=["Sat as close to the ladder as the couch allows (Maxwell 11/21/2026)."]),
    "l_couch": lambda it: dict(model=f"L sectional, {ftin(it.get('nl', 9.5))} along the north wall by {ftin(it.get('el', 7.5))} along the bath 1 wall, {ftin(it.get('d', 3.1))} deep, seat 17 in, back 33 in (size from the ladder mockup, model ASSUMED)",
                               notes=["The L couch from the corner landing ladder mockup (option E) that Maxwell picked 11/21/2026. Its short leg runs under the ladder's upper flight; the flight's underside is well above the couch back there."]),
    "bed": lambda it: dict(model="Queen bed, 60 x 80 in mattress on a white oak platform (ASSUMED)", notes=["Queen, and placed so the side tables clear both doors (Maxwell, 11/16/2026)."]),
    "nightstand": lambda it: dict(model=f"Nightstand, {ftin(it.get('w', 1.4))} wide (ASSUMED)"),
    "table_lamp": lambda it: dict(model="Table lamp (ASSUMED)"),
    "desk_lamp": lambda it: dict(model="UPLIFT E3 LED desk lamp, black (came with the desk order)"),
    "l_desk": lambda it: dict(model="UPLIFT V2 L-shaped standing desk", price="$1,462.85 (04/2022, order SO778262)",
                              specs=[["Size", "60\" main x 60\" return, return on the right"], ["Top", "1\" walnut laminate, main 59.6 x 30 in, return 30 x 27.5 in"],
                                     ["Frame", "V2 C-frame, 3 legs, black"], ["Controls", "Advanced keypad"], ["Shown at", "29 in, seated height (it stands up to about 50 in)"]],
                              notes=["Maxwell's own desk, from his UPLIFT order. Turned 90 degrees counterclockwise so you sit facing north toward the window (Maxwell, 11/17/2026).",
                                     "The main top stands 6 in off the north wall so it clears the window stool when raised to standing height."]),
    "office_chair": lambda it: dict(model="Office chair (stand in, ASSUMED)"),
    "tv_console": lambda it: dict(model=f"Low white oak media console, {ftin(it.get('w', 5.5))} long (style and size ASSUMED)",
                                  specs=[["Size", f"{ftin(it.get('w', 5.5))} long, {round(it.get('d', 17 / 12) * 12)} in deep, {round(it.get('h', 22 / 12) * 12)} in high on {round(it.get('leg', 4 / 12) * 12)} in legs"],
                                         ["Inside", "Slatted doors at both ends, an open middle bay for the network box and a game console"],
                                         ["On top", f"A {ftin(it.get('soundbar', 3.0))} soundbar" if it.get("soundbar", 3.0) else "Nothing"]],
                                  notes=["Under the 70 in TV, centred on it (Maxwell 11/21/2026). A console a little wider than the TV (about 62 in) reads best.",
                                         "The TV's centre is at 72 in as U-11 draws it, so there is about 2 ft 8 in of wall between the console and the TV. Lowering the TV to 42 to 48 in to its centre would close that up; the mount blocking has to be set before drywall.",
                                         "The 16 in outlet behind it (U-11 #64) is hidden by the console; run cords through holes in its back. The plant that stood here moved to the south wall."]),
    "bench": lambda it: dict(model="Built-in mudroom unit, painted light sage (A-11 bench and cubbies; style from Maxwell's reference photo, details ASSUMED)",
                             specs=[["Size", f"{ftin(it.get('w', 8.0))} wide, up to {ftin(it.get('top', 7.95))}"],
                                    ["Bench", f"{ftin(it.get('w', 8.0) - it.get('cab_w', 2.0))} long, seat {ftin(it.get('h', 1.5))} high, {int(it.get('bays', 3))} open bays, each with a black rubber boot tray split by a divider"],
                                    ["Left side", "base cabinet with a drawer and stone counter, tall cabinet above"],
                                    ["Above the bench", f"paneled back, {int(it.get('hooks', 5))} black coat hooks, {int(it.get('cubbies', 2))} open cubbies, glass door cabinets across the top"]],
                             notes=["Rubber boot trays with dividers instead of shoe cubbies, and the mudroom layout from his reference photo (Maxwell, 11/17/2026)."]),
    "towel_warmer": lambda it: dict(model="Wall mounted towel warmer (A-11, model ASSUMED)", notes=["Moved here from the WC doorway, where it hung in the air (Maxwell, 11/17/2026)."]),
}
# Bolted down pieces show with the cabinets and trim, not with Belongings (Maxwell, 11/20/2026: anything bolted down is
# not a belonging).
BUILT_IN = {"bench", "towel_warmer"}
WEB_NAMES = {"bench": "Mudroom bench and cabinets", "bed": "Queen bed", "nightstand": "Nightstand", "table_lamp": "Table lamp", "desk_lamp": "Desk lamp", "l_desk": "L-shaped standing desk", "office_chair": "Office chair", "towel_warmer": "Towel warmer", "tv_console": "TV console", "l_couch": "L sectional couch",
             "dining_table": "Dining table", "dining_chair": "Dining chair", "fruit_bowl": "Fruit bowl", "jute_rug": "Dining rug", "bar_stool": "Counter stool", "seated_person": "Seated person, 6 ft (mockup)"}
for it in FURN:
    if it.get("moved_from"):
        ox, oy, of = it["moved_from"]
        mv = [rnd(it["x"] - ox), rnd(it["y"] - oy), -(it.get("facing", 0) - of)]
        WEB_META["move_nodes"][it["id"]] = mv
        if it.get("move_node"):
            WEB_META["move_nodes"][it["move_node"]] = mv   # the mesh node when the named node is an empty beside it
    if it.get("removed"):                       # taken out of the house: drop the baked piece, build nothing
        WEB_META["replace_nodes"].append(it["id"])
        if it["type"] in ("table_lamp", "desk_lamp"):            # and its night light
            WEB_META.setdefault("lights_removed", []).append(f"{it['id']} bulb")
        if it.get("cull_old"):                                  # pieces merged into per material meshes go by box
            x0, y0, x1, y1, zt = it["cull_old"]
            WEB_META["cull"].append(dict(box=[x0, y0, 0.02, x1, y1, zt], materials=FURN_MATS))
        continue
    if not it.get("web"):
        continue
    t = it["type"]
    WEB_META["replace_nodes"].append(it["id"])
    if it.get("cull_old"):
        x0, y0, x1, y1, zt = it["cull_old"]
        WEB_META["cull"].append(dict(box=[x0, y0, 0.02, x1, y1, zt], materials=FURN_MATS))
    cx = it.get("x", it.get("x0", it.get("corner", [0, 0])[0] - 1.0))
    cy = it.get("y", it.get("y0", it.get("corner", [0, 0])[1] + 1.0))
    rec(f"furniture.{it['id']}", "furniture", WEB_NAMES.get(t, t), "furniture", room=room_at(cx, cy),
        info=WEB_INFO.get(t, lambda i: dict(model=t))(it), tog="finish" if t in BUILT_IN else None)
    WEB_BUILD[t](it)
    if t in ("table_lamp", "desk_lamp"):                    # the night light for a lamp follows it
        WEB_META.setdefault("lights_moved", {})[f"{it['id']} bulb"] = [it["x"], it["y"], rnd(top_of(it) + 1.2)]

# ------------------------------------------------------------------ spawns (as in export_web.py), eye height above the floor
EYE = C.get("web", {}).get("eye_height_ft", 5.58)       # 5'-7" eyes, for a 5'-10" person (Maxwell, 11/16/2026)
SPAWNS = C.get("web", {}).get("spawns", {
    "Kitchen": [[10.5, 48.5], [3.0, 44.0]], "Living": [[19.5, 28.0], [30.0, 28.0]], "Dining": [[41.5, 43.5], [34.0, 48.0]],
    "Bed1": [[34.0, 10.0], [41.5, 5.0]], "Bed2": [[14.2, 9.4], [7.0, 4.5]], "Bed3": [[3.0, 20.8], [11.0, 15.0]],
    "Bath1": [[35.5, 27.5], [32.0, 25.0]], "Bath2": [[19.0, 7.5], [21.5, 2.0]], "Garage": [[79.0, 25.0], [79.0, 42.0]],
    "Outside_SW": [[-40.0, 110.0], [22.0, 30.0]]})


# ------------------------------------------------------------------ check: coplanar faces facing the same way (they flicker)
def panel_boxes(s):
    """the solid pieces of a "w" wall panel as plan boxes, split the way site/house.js panel() splits them. A strip with a
    sloped top keeps its lower top, so the box stays inside the real piece."""
    _, mat, fr, v0, v1, zbot, top, holes = s
    ox, oy, ux, uy, vx, vy = fr
    P = lambda u, v: (ox + u * ux + v * vx, oy + u * uy + v * vy)
    ulo, uhi = min(t[0] for t in top), max(t[2] for t in top)
    cuts = {ulo, uhi} | {t[0] for t in top} | {t[2] for t in top}
    cuts |= {h[k] for h in holes for k in (0, 1) if ulo < h[k] < uhi}
    us, out = sorted(cuts), []
    for ua, ub in zip(us, us[1:]):
        if ub - ua < 1e-4:
            continue
        um = (ua + ub) / 2
        seg = next((t for t in top if t[0] <= um <= t[2]), None)
        if not seg:
            continue
        zt = lambda u: seg[1] + (seg[3] - seg[1]) * (u - seg[0]) / ((seg[2] - seg[0]) or 1)
        ztop = min(zt(ua), zt(ub))
        head = lambda h, u: h[3] + (h[4] - h[3]) * (u - h[0]) / ((h[1] - h[0]) or 1) if len(h) > 4 else h[3]
        hs = sorted((max(h[2], zbot), min(head(h, ua), head(h, ub))) for h in holes if h[0] < um < h[1])
        z = zbot
        pieces = []
        for h0, h1 in hs:
            if h0 > z + 1e-4:
                pieces.append((z, min(h0, ztop)))
            z = max(z, h1)
        if z < ztop - 1e-4:
            pieces.append((z, ztop))
        for za, zb in pieces:
            (xa, ya), (xb, yb) = P(ua, v0), P(ub, v1)
            out.append((min(xa, xb), max(xa, xb), min(ya, yb), max(ya, yb), za, zb))
    return out


X_FACES = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]   # as HEX_FACES in site/house.js


def x_faces(s):
    """the faces of a six sided solid that lie flat on an axis plane: (axis, sign, plane, rect, corner indices)"""
    a = s[2]
    pts = [a[i * 3:i * 3 + 3] for i in range(8)]
    c = [sum(p[k] for p in pts) / 8 for k in range(3)]
    out = []
    for f in X_FACES:
        q = [pts[k] for k in f]
        for ax in range(3):
            if max(p[ax] for p in q) - min(p[ax] for p in q) < 1e-4:
                o = [k for k in range(3) if k != ax]
                rect = (min(p[o[0]] for p in q), max(p[o[0]] for p in q), min(p[o[1]] for p in q), max(p[o[1]] for p in q))
                if rect[1] - rect[0] > 1e-4 and rect[3] - rect[2] > 1e-4:
                    out.append((ax, 1 if q[0][ax] > c[ax] else -1, q[0][ax], rect, f))
                break
    return out


def faces_of(s):
    """axis aligned faces of box shapes, six sided solids and wall panel pieces: (axis, sign, plane, rect)"""
    if s[0] == "x":
        return [f[:4] for f in x_faces(s)]
    if s[0] == "b":
        bxs = [s[2:8]]
    elif s[0] == "w" and all(abs(c) in (0, 1) for c in s[2][2:]):
        bxs = panel_boxes(s)
    else:
        return []
    out = []
    for x0, x1, y0, y1, z0, z1 in bxs:
        out += [(0, -1, x0, (y0, y1, z0, z1)), (0, 1, x1, (y0, y1, z0, z1)), (1, -1, y0, (x0, x1, z0, z1)), (1, 1, y1, (x0, x1, z0, z1)),
                (2, -1, z0, (x0, x1, y0, y1)), (2, 1, z1, (x0, x1, y0, y1))]
    return out


def zfight_pairs():
    buckets = {}
    for r in RECS:
        if r.get("placeholder_for") or r.get("layer") == "framing":
            continue                                # framing sits inside the walls, flush piece to piece by design
        groups = [("", r.get("parts", []))] + [(o["id"], o["parts"]) for o in r.get("ops", [])]
        for gid, parts in groups:
            for s in parts:
                for (ax, sg, pl, rect) in faces_of(s):
                    if ax == 2 and sg < 0 and pl <= 0.005:
                        continue                    # bottoms resting on the slab are never seen
                    buckets.setdefault((ax, sg, round(pl, 3)), []).append((r["id"] + gid, s[1], rect, s))
    pairs = []
    for key, lst in buckets.items():
        for i in range(len(lst)):
            for j in range(i + 1, len(lst)):
                a, b = lst[i], lst[j]
                if a[1] == b[1]:
                    continue                        # same material: the same pixels whichever wins
                ra, rb = a[2], b[2]
                if min(ra[1], rb[1]) - max(ra[0], rb[0]) > 1e-3 and min(ra[3], rb[3]) - max(ra[2], rb[2]) > 1e-3:
                    pairs.append((key, a, b))
    return pairs


def vol(s):
    if s[0] == "x":
        a = s[2]
        return math.prod(max(a[k::3]) - min(a[k::3]) for k in range(3))
    if s[0] != "b":
        return float("inf")                      # wall panels never move: the box against them does
    return (s[3] - s[2]) * (s[5] - s[4]) * (s[7] - s[6])


def grow(s, ax, sg, pl):
    """move the face of s on plane pl (axis ax, facing sg) 1/32 in outward"""
    if s[0] == "b":
        i = 2 + 2 * ax + (1 if sg > 0 else 0)
        s[i] = rnd(s[i] + sg * 0.0026)
        return
    for f in x_faces(s):
        if f[0] == ax and f[1] == sg and abs(f[2] - pl) < 1e-3:
            for k in f[4]:
                s[2][k * 3 + ax] = rnd(s[2][k * 3 + ax] + sg * 0.0026)
            return


def nudge():
    """coplanar faces of different materials pointing the same way flicker: grow the smaller box 1/32 in past the other"""
    moved = 0
    for _ in range(3):
        pairs = zfight_pairs()
        if not pairs:
            break
        done = set()
        for (ax, sg, pl), a, b in pairs:
            small = a[3] if vol(a[3]) <= vol(b[3]) else b[3]
            if small[0] not in "bx" or (id(small), ax, sg) in done:
                continue
            done.add((id(small), ax, sg))
            grow(small, ax, sg, pl)
            moved += 1
    return moved, len(zfight_pairs())


# Furniture, fixtures and cabinets were placed against the A-11 faces of the partitions. Those faces moved 5/8 in into the
# rooms when the walls got real drywall (_grow_thin), so slide each piece that now sits in the new drywall back out of it,
# the whole record together. tools/drywall_check.py lists anything still buried.
def drywall_slabs():
    out = []
    for a, b in zip(INT_RECTS_A11, INT_RECTS):
        if a == b:
            continue
        for ax, sg, sl in ((1, -1, (b[0], b[1], b[2], a[2])), (1, 1, (b[0], b[1], a[3], b[3])), (0, -1, (b[0], a[0], b[2], b[3])), (0, 1, (a[1], b[1], b[2], b[3]))):
            if sl[1] - sl[0] > 1e-4 and sl[3] - sl[2] > 1e-4:
                out.append((ax, sg, sl, a))
    return out


def shape_bounds(s):
    if s[0] == "b":
        return (s[2], s[3], s[4], s[5]), (s[6], s[7])
    if s[0] == "x":
        a = s[2]
        return (min(a[0::3]), max(a[0::3]), min(a[1::3]), max(a[1::3])), (min(a[2::3]), max(a[2::3]))
    if s[0] == "c":
        return (s[2] - max(s[6], s[7]), s[2] + max(s[6], s[7]), s[3] - max(s[6], s[7]), s[3] + max(s[6], s[7])), (s[4], s[5])
    if s[0] == "q":
        p = s[2]
        return (min(q[0] for q in p), max(q[0] for q in p), min(q[1] for q in p), max(q[1] for q in p)), (min(q[2] for q in p), max(q[2] for q in p))
    return None, None


def buried_in_drywall(s, slabs, eps=0.004):
    """(axis, push) for each new drywall slab this shape sits in but does not run on through (floors and the like do)"""
    bx, z = shape_bounds(s)
    if not bx:
        return []
    out = []
    for ax, sg, sl, a in slabs:
        if min(bx[1], sl[1]) - max(bx[0], sl[0]) > eps and min(bx[3], sl[3]) - max(bx[2], sl[2]) > eps:
            if min(bx[1], a[1]) - max(bx[0], a[0]) > eps and min(bx[3], a[3]) - max(bx[2], a[2]) > eps:
                continue
            lo, hi = (bx[0], bx[1]) if ax == 0 else (bx[2], bx[3])
            out.append((ax, (sl[1 if ax == 0 else 3] - lo) if sg > 0 else -(hi - sl[0 if ax == 0 else 2])))
    return out


def shift_shape(s, d):
    if s[0] == "b":
        for k in range(2):
            s[2 + k] = rnd(s[2 + k] + d[0]); s[4 + k] = rnd(s[4 + k] + d[1])
    elif s[0] == "x":
        for k in range(8):
            s[2][k * 3] = rnd(s[2][k * 3] + d[0]); s[2][k * 3 + 1] = rnd(s[2][k * 3 + 1] + d[1])
    elif s[0] == "c":
        s[2] = rnd(s[2] + d[0]); s[3] = rnd(s[3] + d[1])
    elif s[0] == "q":
        for q in s[2]:
            q[0] = rnd(q[0] + d[0]); q[1] = rnd(q[1] + d[1])


def settle_off_drywall():
    slabs, moved = drywall_slabs(), []
    for r in RECS:
        if r.get("kind") not in ("furniture", "fixture", "cabinet", "appliance"):
            continue
        shapes = list(r.get("parts", [])) + [s for o in r.get("ops", []) for s in o["parts"]]
        push = [0.0, 0.0, 0.0, 0.0]                      # -x, +x, -y, +y
        for s in shapes:
            for ax, d in buried_in_drywall(s, slabs):
                i = ax * 2 + (1 if d > 0 else 0)
                push[i] = max(push[i], abs(d) + 0.0005)
        if not any(push):
            continue
        d = (push[1] - push[0], push[3] - push[2])
        if (push[0] and push[1]) or (push[2] and push[3]):
            print(f"drywall: {r['id']} is squeezed between two walls that grew, moved by the net {d}")
        for s in shapes:
            shift_shape(s, d)
        for o in r.get("ops", []):
            o["pivot"][0] = rnd(o["pivot"][0] + d[0]); o["pivot"][1] = rnd(o["pivot"][1] + d[1])
        moved.append((r["id"], round(d[0] * 12, 2), round(d[1] * 12, 2)))
    return moved


SETTLED = settle_off_drywall()
print("off the new drywall (in):", ", ".join(f"{i} {dx:+g},{dy:+g}" for i, dx, dy in SETTLED))

NUDGED = nudge()

# ------------------------------------------------------------------ write
# the regraded ground near the buildings (model/grade.py): site/app.js adds dz to the baked Terrain mesh
sys.path.insert(0, HERE)
import grade as _grade
GRADE_GRID = dict(note="regraded ground, feet above the slab top, drawn in place of the baked Terrain here (model/grade.py)", **_grade.grid())

out = dict(
    meta=dict(generated_by="model/make_house.py", units="plan feet (x east, y south from the outside NW slab corner, z up from the slab top)",
              source="config.toml and data/traced_geometry.json; port of the v21 Blender model (archive/blender)",
              eye_ft=EYE, floors=dict(main=0.0, loft=LOFT["floor_height"], attic=FH + FLOOR_T),
              rooms=[dict(name=n, rect=[x0, y0, x1, y1]) for (n, x0, y0, x1, y1) in ROOMS]
                    + [dict(name="Loft", rect=list(LOFT["rect"]), floor=LOFT["floor_height"], upper=True)]
                    + ([dict(name="Garage", rect=list(GA["rect"]), floor=rnd(GF))] if GA.get("enabled") else [])
                    + ([dict(name="Porch", rect=list(C["porch"]["rect"]), floor=rnd(PZ), outside=True)] if C.get("porch", {}).get("enabled", True) and C.get("porch", {}).get("rect") else []),
              outline=dict(house=[0, 0, HW, HD], garage=GA["rect"] if GA.get("enabled") else None, porch=C.get("porch", {}).get("rect")),
              climbs=(LADDER_CLIMBS if LADDER_CLIMBS is not None else [dict(id="loft.ladder", rect=list(LOFT["ships_ladder"]), axis="x", z0=0.0, z1=LOFT["floor_height"])]) if LOFT.get("enabled") else [],
              framing=FRAMING_META,
              grade=GRADE_GRID,
              partitions=[dict(a11=[rnd(v) for v in a], built=[rnd(v) for v in b]) for a, b in zip(INT_RECTS_A11, INT_RECTS) if a != b],
              **WEB_META),
    materials=MATERIALS,
    spawns={k: dict(pos=[p[0], p[1], EYE], look=[l[0], l[1], EYE - 0.3]) for k, (p, l) in SPAWNS.items()},
    records=RECS)
for r in RECS:            # drop empty part lists
    if not r["parts"]:
        r.pop("parts")
with open(OUT, "w") as f:
    json.dump(out, f, separators=(",", ":"))
nparts = sum(len(r.get("parts", [])) + sum(len(o["parts"]) for o in r.get("ops", [])) for r in RECS)
nops = sum(len(r.get("ops", [])) for r in RECS)
print(f"wrote {os.path.normpath(OUT)}: {len(RECS)} records, {nparts} shapes, {nops} moving parts, {os.path.getsize(OUT) / 1e3:.0f} kB")
print(f"coplanar faces nudged apart: {NUDGED[0]}, left between wall panels: {NUDGED[1]} (node tools/coplanar_audit.mjs says which can be seen)")
if "--check" in sys.argv:
    for (key, a, b) in zfight_pairs()[:60]:
        print("  ", key, a[0], a[1], b[0], b[1])
