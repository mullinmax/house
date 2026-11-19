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
OUT = os.path.join(HERE, "..", "site", "models", "house.json")
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


def box(mat, x0, x1, y0, y1, z0, z1, ztop=None):
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
    hexa(mat, pts)


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
    "Cabinet Wood": dict(color="#FFFFFF", rough=0.45, map="cabinet_oak.jpg", normal="oak_normal.jpg", normal_scale=0.5, tile=0.8, grain="long"),
    "Island": dict(color=K["island_color"], rough=0.5),
    "Counter": dict(color="#FFFFFF", rough=0.17, map="quartz.jpg", tile=1.6),
    "Glass": dict(color="#C8D4D6", rough=0.05, metal=0.2, opacity=0.14),
    "Black Glass": dict(color="#0B0B0C", rough=0.05, opacity=0.25),
    "Polycarbonate": dict(color="#F2F2EE", rough=0.2, opacity=0.45),
    "Stainless": dict(color="#C8CACC", rough=0.25, metal=1.0),
    "Brushed Nickel": dict(color=K.get("hardware_color", "#B8B8B4"), rough=0.3, metal=1.0),
    "Black Metal": dict(color="#151515", rough=0.4, metal=0.6),
    "Aluminum": dict(color="#B9BCBE", rough=0.35, metal=1.0),
    "Gutter": dict(color=MM.get("trim_albedo", MM["trim_color"]), rough=0.45, metal=0.4),
    "Standing Seam": dict(color=MM["roof_color"], rough=0.41, metal=0.6),
    "Garage Door": dict(color="#2A2A2A", rough=0.5),
    "Plastic Grey": dict(color="#9A9A96", rough=0.5),
    "Appliance Interior": dict(color="#1A1A1A", rough=0.6),
    "Attic Deck": dict(color="#C8B28A", rough=0.85),
    "Gravel": dict(color="#8A8378", rough=0.95),
    "Lamp Glass": dict(color="#FFF1D6", rough=0.3, opacity=0.7, night_glow=True),
}


def paint(hexc):
    nm = "Paint " + hexc
    MATERIALS.setdefault(nm, dict(color=hexc, rough=0.45))
    return nm


ROOMS = [("Bedroom 1", 31.1, 0.5, 42.6, 15.03), ("Bedroom 2", 5.9, 0.5, 16.1, 10.7), ("Bath 2", 16.1, 0.5, 22.7, 10.7), ("Bedroom 4 / study", 22.7, 0.5, 31.1, 10.7),
         ("Closet 2", 0.5, 0.5, 5.9, 5.5), ("Closet 3", 0.5, 5.5, 5.9, 10.9), ("Bedroom 3", 0.5, 10.95, 12.12, 22.41), ("Hall 2", 12.12, 10.95, 28.12, 15.03),
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
    if not door:
        wbox(inner, wall, u0 - 0.15, u1 + 0.15, jd0, jd1 + 0.12, z0 - 0.07, z0)
    cw = 3.5 / 12
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
for ed in C.get("plan_edits", {}).get("wall_remove", []):     # partitions taken out by a decision (a built-in panel stands in)
    px, py = ed["at"]
    hit = [r_ for r_ in INT_RECTS if r_[0] - 0.01 <= px <= r_[1] + 0.01 and r_[2] - 0.01 <= py <= r_[3] + 0.01]
    if not hit:
        raise SystemExit(f"plan_edits.wall_remove: no interior wall at {ed['at']}")
    INT_RECTS.remove(hit[0])
DOORS = G.get("door_labels_A11", [])


def nearest_label(x, y):
    best, bd = None, 99
    for dx, dy, lab in DOORS:
        d = math.hypot(dx - x, dy - y)
        if d < bd:
            bd, best = d, lab
    return best if bd < 3.5 else None


def door_head_near(x, y):
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
for k, ((x0, x1, y0, y1), top) in enumerate(WALL_PIECES):
    ln, th = max(x1 - x0, y1 - y0), min(x1 - x0, y1 - y0)
    zt = top((x0 + x1) / 2, (y0 + y1) / 2)
    rec(f"wall.int.{k}", "wall", f"Interior wall {between(x0, x1, y0, y1)}".strip(), "interior",
        info=dict(model=f"{ftin(th)} interior partition", specs=[["Length", ftin(ln)], ["Height", ftin(zt) if abs(top(x0, y0) - top(x1, y1)) < 0.05 else "Up to the roof"],
                                                                ["Finish", f"Drywall, {MM['wall_paint']}"]],
                  notes=["Traced from the A-11 floor plan vectors."]))
    box("Drywall", x0, x1, y0, y1, 0, 9, ztop=top)

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
                    h = door_head_near(cx, cy)
                    top = wall_top(a[0], a[1], gap0, gap1)
                    DOOR_GAPS.append(("y", gap0, gap1, a[0], a[1], h))
                    if top(cx, cy) - h > 0.2:
                        FIXES.append(("header", a[0], a[1], gap0, gap1, top, h))


make_headers()
nh = 0
for f_ in FIXES:
    if f_[0] == "sliver":
        _, x0, x1, y0, y1, top, z0 = f_
        rec(f"wall.fill.{nh}", "wall", f"Interior wall {between(x0, x1, y0, y1)}".strip(), "interior",
            info=dict(model="Short wall piece", notes=["Fills a gap of under 1' 5\" between two traced wall ends" + (", above the attic deck." if z0 else ".")]))
        box("Drywall", x0, x1, y0, y1, z0, 9, ztop=top)
    else:
        _, x0, x1, y0, y1, top, h = f_
        rec(f"wall.header.{nh}", "wall", "Wall over a doorway", "interior",
            info=dict(model="Drywall over the door head", specs=[["Door head", ftin(h)]]))
        box("Drywall", x0, x1, y0, y1, h, 9, ztop=top)
    nh += 1

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
    box("Drywall", x0, x1, y0, y1, FH, FH + FLOOR_T - DECK_T)
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
    lx0, ly0, lx1, ly1 = LOFT["ships_ladder"]
    n = 11
    rec("loft.ladder", "stair", "Ships ladder to the loft", "interior", room="Loft",
        info=dict(model="White oak ships ladder (A-11 footprint)", specs=[["Treads", f"{n}, rising {ftin(FL / (n + 1))} each"], ["Rise", ftin(FL)], ["Run", ftin(lx1 - lx0)]]))
    for k in range(n):
        x = lx0 + (lx1 - lx0) * k / n
        z = FL * (k + 1) / (n + 1)
        box("White Oak", x, x + 0.75, ly0 + 0.15, ly1 - 0.15, z - 0.12, z)
    for yy in (ly0, ly1 - 0.15):
        hexa("White Oak", [(lx0, yy, 0), (lx0 + 0.35, yy, 0), (lx1, yy, FL), (lx1 - 0.35, yy, FL),
                           (lx0, yy + 0.15, 0), (lx0 + 0.35, yy + 0.15, 0), (lx1, yy + 0.15, FL), (lx1 - 0.35, yy + 0.15, FL)])
    if LOFT.get("railing"):
        RH = LOFT.get("railing_height", 3.0)
        rec("loft.railing", "railing", "Loft railing", "interior", room="Loft",
            info=dict(model=f"{ftin(RH)} guard, black steel posts and balusters with a white oak cap (ASSUMED)", specs=[["Edge", "Open west edge of the loft, open where the ladder lands"], ["Top", ftin(FL + RH)]]))
        ya, yb = LY0 + 0.1, ly0 - 0.05
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
        for yy in (ly0 - 0.08, ly1 + 0.02):                 # sloped handrails along the ladder, 34" above the treads
            hexa("Black Metal", [(lx0 + 0.3, yy, 2.83), (lx1 + 0.3, yy, FL + 2.83), (lx1 + 0.3, yy, FL + 2.95), (lx0 + 0.3, yy, 2.95),
                                 (lx0 + 0.3, yy + 0.06, 2.83), (lx1 + 0.3, yy + 0.06, FL + 2.83), (lx1 + 0.3, yy + 0.06, FL + 2.95), (lx0 + 0.3, yy + 0.06, 2.95)])
            for (xa, za) in ((lx0 + 0.3, 0.0), (lx1 + 0.3, FL)):
                box("Black Metal", xa - 0.05, xa + 0.05, yy, yy + 0.06, za, za + 2.95)

# ------------------------------------------------------------------ kitchen (Carter Lumber design start plan, Erin's redline)
BASE_D, CTR_D, FRONT_T, REV = 1.9, 2.08, 0.06, 0.012
KICK, CTR_Z, CTR_T = 0.33, 3.0, 0.125
TALL = K.get("tall_height", 8.0)
RUNS = K["runs"]
UNIT_NAMES = {"blind": "Blind corner base", "door1": "Base cabinet, one door", "doors2": "Sink base, two doors", "drawers2": "Two drawer base",
              "drawers3": "Three drawer base", "drawer_door": "Drawer over a door", "drawer_doors2": "Drawer over two doors", "dishwasher": "Dishwasher bay",
              "pullout": "Pullout base", "oven_tower": "Oven tower", "tall_pantry": "Tall pantry", "fridge": "Fridge bay with over fridge cabinet",
              "tray": "Tray divider base", "beverage": "Beverage fridge bay", "panel": "End panel", "drawer_tall": "Tall utensil drawer",
              "pullout_drawer": "Drawer over a sheet pan pullout"}
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


def pull(run, uc, zc, length, d, vertical=False):
    if vertical:
        run.box("Brushed Nickel", uc - 0.02, uc + 0.02, d, d + 0.07, zc - length / 2, zc + length / 2)
    else:
        run.box("Brushed Nickel", uc - length / 2, uc + length / 2, d, d + 0.07, zc - 0.02, zc + 0.02)


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
            run.box("Glass" if glass else mat, u0 + st, u1 - st, d, d + FRONT_T * 0.6, z0 + st, z1 - st)
            run.box(mat, u0, u0 + st, d, d + FRONT_T, z0, z1)
            run.box(mat, u1 - st, u1, d, d + FRONT_T, z0, z1)
            run.box(mat, u0 + st, u1 - st, d, d + FRONT_T, z1 - st, z1)
            run.box(mat, u0 + st, u1 - st, d, d + FRONT_T, z0, z0 + st)
        dp = d + FRONT_T
        if kind == "drawer":
            zc = z1 - min(0.25, h / 2) if h > 0.62 else (z0 + z1) / 2
            if w > 2.4 and K.get("wide_drawer_pulls", 2) == 2:
                pull(run, u0 + w * 0.25, zc, 0.5, dp); pull(run, u0 + w * 0.75, zc, 0.5, dp)
            elif w > 2.4:
                pull(run, (u0 + u1) / 2, zc, min(1.6, w * 0.6), dp)
            else:
                pull(run, (u0 + u1) / 2, zc, min(0.5, w * 0.5), dp)
        elif kind == "door":
            uc = u1 - 0.12 if hinge == "L" else u0 + 0.12
            zc = z1 - 0.45 if z0 < 3.0 and z1 < 3.5 else z0 + 0.45
            if z1 - z0 > 3.5:
                zc = 3.6 if z0 < 1 else z0 + 0.45
            pull(run, uc, zc, 0.5, dp, vertical=True)


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


def base_unit(run, rn, k, u0, u1, typ, mat, depth=BASE_D, counter=True):
    d = depth; zt = CTR_Z - CTR_T
    rid = f"cabinet.{rn}.{k}"
    nm = f"{UNIT_NAMES.get(typ, typ)}, {RUN_NAMES.get(rn, rn)}"
    r = rec(rid, "cabinet", nm, "interior", room="Kitchen",
            info=dict(model=f"{UNIT_NAMES.get(typ, typ)}, {ftin(u1 - u0)} wide", specs=[["Run", RUN_NAMES.get(rn, rn)], ["Finish", "Olive green, painted" if mat == "Island" else f"KraftMaid natural wood {K['cabinet_wood']} (species and stain TBD)"],
                                                                                      ["Hardware", "Brushed nickel bar pulls"]],
                      notes=["From the Carter Lumber design start plan (Danielle Gross, 11/10/2026) with Erin's 11/12 redline."]))
    if typ in ("oven_tower", "tall_pantry"):
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
                pull(run, (u0 + u1) / 2, zz + 1.35, u1 - u0 - 0.8, df + 0.06)
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
            run.box(mat, u0, u1, 0, BASE_D + 0.1, 6.0, TALL - 0.25)
            doors(run, r, u0, u1, 6.0, TALL - 0.25, BASE_D + 0.1, mat, 2)
            run.box(mat, u0 - 0.05, u1 + 0.05, 0, BASE_D + 0.22, TALL - 0.25, TALL)
        else:
            run.box(mat, u0 - 0.1, u1 + 0.1, 0, BASE_D + 0.1, 6.0, TALL - 0.25)
            doors(run, r, u0 - 0.1, u1 + 0.1, 6.0, TALL - 0.25, BASE_D + 0.1, mat, 2)
            run.box(mat, u0 - 0.15, u1 + 0.15, 0, BASE_D + 0.22, TALL - 0.25, TALL)
        placeholder(run, rn, k, "fridge", "Refrigerator (placeholder)")
        run.box("Stainless", a0_, a1_, 0.1, BASE_D + 0.35, 0, 5.9)
        run.box("Black Glass", (a0_ + a1_) / 2 - 0.01, (a0_ + a1_) / 2 + 0.01, BASE_D + 0.35, BASE_D + 0.36, 2.15, 5.9)
        run.box("Black Glass", a0_, a1_, BASE_D + 0.35, BASE_D + 0.36, 2.1, 2.15)
        for uc in ((a0_ + a1_) / 2 - 0.12, (a0_ + a1_) / 2 + 0.12):
            pull(run, uc, 4.0, 2.6, BASE_D + 0.36, vertical=True)
        pull(run, (a0_ + a1_) / 2, 1.9, a1_ - a0_ - 0.6, BASE_D + 0.36)
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
        pull(run, (u0 + u1) / 2, zt - 0.2, u1 - u0 - 0.4, d + 0.05); return
    if typ == "beverage":
        placeholder(run, rn, k, "beverage", "Beverage fridge (placeholder)")
        run.box("Stainless", u0 + REV, u1 - REV, d - 0.02, d + 0.03, KICK, zt - 0.02)
        run.box("Black Glass", u0 + 0.12, u1 - 0.12, d + 0.03, d + 0.04, KICK + 0.25, zt - 0.15)
        pull(run, u0 + 0.18, (KICK + zt) / 2, 1.4, d + 0.04, vertical=True); return
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
    mat = "Island" if rn.startswith("island") else "Cabinet Wood"
    for k, (u0, u1, typ) in enumerate(run_["units"]):
        base_unit(run, rn, k, u0, u1, typ, mat, run_.get("depth", BASE_D), counter=not rn.startswith("island"))
nr = Run("north", RUNS["north"]); UB = K.get("upper_bottom", 4.6)
for k, up in enumerate(RUNS["north"].get("uppers", [])):
    u0, u1, typ = up[:3]; ud = up[3] if len(up) > 3 else 1.1
    r = rec(f"cabinet.north.upper.{k}", "cabinet", "Glass door upper, fridge wall" if typ == "glass" else "Microwave upper, fridge wall", "interior", room="Kitchen",
            info=dict(model=f"{'Glass door' if typ == 'glass' else 'Microwave'} upper, {ftin(u1 - u0)} wide, {ftin(ud)} deep", specs=[["Underside", ftin(UB)], ["Top", ftin(TALL)]],
                      notes=["Microwave upper deepened per Erin's redline."] if typ != "glass" else []))
    nr.box("Cabinet Wood", u0, u1, 0, ud, UB, TALL - 0.25)
    if typ == "glass":
        doors(nr, r, u0, u1, UB, TALL - 0.25, ud, "Cabinet Wood", 2, glass=True)
        for zz in (5.7, 6.75):
            nr.box("Cabinet Wood", u0 + 0.06, u1 - 0.06, 0.05, ud - 0.05, zz, zz + 0.06)
    else:
        nr.box("Stainless", u0 + 0.15, u1 - 0.15, ud - 0.05, ud + 0.02, UB + 0.05, UB + 1.45)
        nr.box("Black Glass", u0 + 0.3, u1 - 0.9, ud + 0.02, ud + 0.03, UB + 0.25, UB + 1.25)
        doors(nr, r, u0, u1, UB + 1.55, TALL - 0.25, ud, "Cabinet Wood", 2)
    nr.box("Cabinet Wood", u0 - 0.03, u1 + 0.03, 0, ud + 0.12, TALL - 0.25, TALL)

if RUNS["north"].get("pantry_door"):
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
rec("kitchen.hood", "fixture", "Range hood", "interior", room="Kitchen",
    info=dict(model="Stainless chimney hood, remote blower", specs=[["Width", ftin(cy1 - cy0 - 0.2)], ["Underside", "6' 0\""], ["Chimney cover", "14-3/8 in square, to the ceiling"],
              ["Fan", "On the roof, with a silencer in the chimney (Maxwell, 11/17/2026)"]],
              notes=["Model not picked yet. It needs to be a liner or insert sold for a remote blower, with no fan inside the hood, so the kitchen stays quiet.",
                     "The chimney cover is wider than a stock one so the duct silencer fits inside it. Hide the duct x-ray or use no clip to see the duct, silencer and roof blower."]))
wr.box("Stainless", cy0 + 0.1, cy1 - 0.1, 0, 1.9, 6.0, 6.35)
_cc = (cy0 + cy1) / 2
wr.box("Stainless", _cc - 0.6, _cc + 0.6, 0, 1.2, 6.35, south_roof_z(_cc + 0.6) - 0.01)
ix0, iy0, ix1, iy1 = K["island"]
ir = RUNS["island"]
rec("kitchen.island", "cabinet", "Kitchen island top and panels", "interior", room="Kitchen",
    info=dict(model=f"{ftin(ix1 - ix0)} x {ftin(iy1 - iy0)} island with a {ftin(K.get('island_overhang', 1.25))} seating overhang",
              specs=[["Top", f"Quartz {K['counter_color']} (ASSUMED light quartz)"], ["Body", f"Olive green {K['island_color']}"]], notes=["Deepened to 45\" for the overhang (Erin's redline)."]))
box("Island", ir["units"][0][0], RUNS["island_east"]["back"] if "island_east" in RUNS else ir["units"][-1][1], ir["back"] - 0.06, ir["back"], 0, CTR_Z - CTR_T)
box("Island", ir["units"][0][0] - 0.06, ir["units"][0][0], ir["back"] - 0.06, ir["back"] + ir.get("depth", BASE_D) + FRONT_T, 0, CTR_Z - CTR_T)
box("Counter", ix0, ix1, iy0, iy1, CTR_Z - CTR_T, CTR_Z)
SH = K["shelves"]
rec("kitchen.shelves", "fixture", "Open shelves", "interior", room="Kitchen", info=dict(model="White oak open shelves", specs=[["Length", ftin(SH["x"][1] - SH["x"][0])], ["Heights", ", ".join(ftin(z) for z in SH["heights"])]]))
for z in SH["heights"]:
    box("White Oak", SH["x"][0], SH["x"][1], HD - T - SH["depth"], HD - T, z, z + 0.15)

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
    for s_ in segs:
        ax, c0, a0, a1, sgn = s_[:5]
        holes = s_[5] if len(s_) > 5 else []
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
        r = rec("furniture.entry_closet", "furniture", "Entry closet fittings", "furniture", room="Entry",
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
        r = rec("furniture.entry_closet", "furniture", "Entry coat cabinet", "furniture", room="Entry",
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
        r = rec("furniture.entry_closet", "furniture", "Entry closet cabinet", "furniture", room="Entry",
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
    r = rec("furniture.entry_closet", "furniture", "Pull-out coat tower", "furniture", room="Entry",
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
GA = C["garage"]
if GA["enabled"]:
    gx0, gy0, gx1, gy1 = GA["rect"]
    gs = GA["pitch"] / 12
    gtop = lambda y: GA["south_wall_height"] + (gy1 - y) * gs
    GWH = GA.get("north_window_height", 3.0)
    my0, my1 = GA["man_door_y"]
    rec("garage.walls", "wall", "Garage walls", "shell",
        info=dict(model=f"{ftin(gx1 - gx0)} x {ftin(gy1 - gy0)} detached garage, delegated design (A-11, A-22)",
                  specs=[["South wall", f"{ftin(GA['south_wall_height'])} (A-31 section 2)"], ["Roof", f"{GA['pitch']:g}:12 down to the south"],
                         ["Siding", "Board and batten to match the house"]]))
    fN, fS, fW, fE = (gx0, gy0, 1, 0, 0, 1), (gx0, gy1, 1, 0, 0, -1), (gx0, gy0, 0, 1, 1, 0), (gx1, gy0, 0, 1, -1, 0)
    holesN = [(s0, s0 + 3, GA["north_window_sill"], GA["north_window_sill"] + GWH) for s0 in GA["north_windows"]]
    holesS = [(s0, s0 + w, 0, 8) for (s0, w) in GA["overhead_doors"]]
    holesW = [(my0 - gy0, my1 - gy0, 0, 6.67)]
    W_ = gx1 - gx0; D_ = gy1 - gy0
    panel("Siding", fN, 0, 0.5, 0, [[0, gtop(gy0), W_, gtop(gy0)]], holesN)
    panel("Siding", fS, 0, 0.5, 0, [[0, gtop(gy1), W_, gtop(gy1)]], holesS)
    panel("Siding", fW, 0, 0.5, 0, [[0, gtop(gy0), D_, gtop(gy1)]], holesW)
    panel("Siding", fE, 0, 0.5, 0, [[0, gtop(gy0), D_, gtop(gy1)]], [])
    battens("Siding", lambda u, v: (gx0 + u, gy0 + v), 0, W_, 0, lambda u: gtop(gy0),
            [(s0 - TRIM_W, s0 + 3 + TRIM_W, GA["north_window_sill"] - 0.4, GA["north_window_sill"] + GWH + 0.4) for s0 in GA["north_windows"]])
    battens("Siding", lambda u, v: (gx0 + u, gy1 - v), 0, W_, 0, lambda u: gtop(gy1), [(s0 - 0.1, s0 + w + 0.1, -1, 8.1) for (s0, w) in GA["overhead_doors"]])
    battens("Siding", lambda u, v: (gx0 + v, u), gy0, gy1, 0, gtop, [(my0 - 0.1, my1 + 0.1, -1, 6.8)])
    battens("Siding", lambda u, v: (gx1 - v, u), gy0, gy1, 0, gtop, [])
    rec("garage.slab", "slab", "Garage slab", "shell", info=dict(model="Concrete slab"))
    box("Concrete", gx0, gx1, gy0, gy1, -0.4, -0.05)
    for k, (s0, w) in enumerate(GA["overhead_doors"]):
        r = rec(f"garage.door.{k + 1}", "door", f"Garage overhead door {k + 1}", "shell", info=dict(model=f"D90-80 overhead door, {ftin(w)} x 8' 0\"", specs=[["Colour", "Black, with a row of lites"]]))
        r["info"]["specs"].append(["Opens", "Sectional, rolls up and back on horizontal tracks under the ceiling"])
        for xt in (gx0 + s0 - 0.12, gx0 + s0 + w + 0.04):         # steel tracks: up the jambs, then back into the garage
            box("Black Metal", xt, xt + 0.08, gy1 - 0.45, gy1 - 0.25, 0, 8.1)
            box("Black Metal", xt, xt + 0.08, gy1 - 8.6, gy1 - 0.25, 8.1, 8.25)
        lf = op(r, f"garage.door.{k + 1}.panel", r["name"], "overhead", (gx0 + s0 + w / 2, gy1 - 0.35, 0))
        lf["height"] = 8.0
        lf["inward"] = [0, -1]                                  # rolls back to the north, into the garage
        with into(lf["parts"]):
            box("Garage Door", gx0 + s0, gx0 + s0 + w, gy1 - 0.4, gy1 - 0.3, 0, 8)
            for j in range(1, 4):
                box("Trim", gx0 + s0 + 0.1, gx0 + s0 + w - 0.1, gy1 - 0.31, gy1 - 0.27, j * 2 - 0.03, j * 2 + 0.03)
            for j in range(4):
                wx = gx0 + s0 + 0.6 + j * (w - 1.2) / 4
                box("Glass", wx + 0.1, wx + (w - 1.2) / 4 - 0.1, gy1 - 0.27, gy1 - 0.25, 6.5, 7.5)
    for k, s0 in enumerate(GA["north_windows"]):
        rec(f"garage.window.{k + 1}", "window", f"Garage north window {k + 1}", "shell", info=dict(model="W30-30 awning", specs=[["Sill", ftin(GA["north_window_sill"])]], notes=["A-21 north elevation."]))
        ws, wx0, wx1 = GA["north_window_sill"], gx0 + s0, gx0 + s0 + 3
        box("Glass", wx0, wx1, gy0 + 0.2, gy0 + 0.25, ws, ws + GWH)
        for (a0, a1, b0, b1) in ((wx0 - 0.33, wx0, ws, ws + GWH), (wx1, wx1 + 0.33, ws, ws + GWH), (wx0 - 0.33, wx1 + 0.33, ws + GWH, ws + GWH + 0.33), (wx0 - 0.33, wx1 + 0.33, ws - 0.33, ws)):
            box("Trim", a0, a1, gy0 - BAT_T - 0.02, gy0, b0, b1)
    r = rec("garage.man_door", "door", "Garage door to the porch", "shell", info=dict(model="D30-68 man door", specs=[["Opening", f"{ftin(my1 - my0)} x 6' 8\""]]))
    lf = op(r, "garage.man_door.leaf", r["name"], "swing", (gx0 + 0.25, my0, 0), angle=90)
    with into(lf["parts"]):
        box("Trim", gx0 + 0.2, gx0 + 0.3, my0, my1, 0, 6.67)
    rec("garage.roof", "roof", "Garage roof", "roof", info=dict(model=f"{GA['pitch']:g}:12 standing seam roof"))
    v0_ = (gx0 - 1, gx1 + 1); yy0, yy1 = gy0 - 1, gy1 + 1
    hexa("Trim", [(v0_[0], yy0, gtop(yy0)), (v0_[1], yy0, gtop(yy0)), (v0_[1], yy1, gtop(yy1)), (v0_[0], yy1, gtop(yy1)),
                  (v0_[0], yy0, gtop(yy0) + 0.8), (v0_[1], yy0, gtop(yy0) + 0.8), (v0_[1], yy1, gtop(yy1) + 0.8), (v0_[0], yy1, gtop(yy1) + 0.8)],
         ["Drywall", "Standing Seam", "Trim", "Trim", "Trim", "Trim"])
    seam_ribs(v0_[0], v0_[1], yy0, yy1, lambda y: gtop(y) + 0.8)

PO = C["porch"]
if PO["enabled"]:
    px0, py0, px1, py1 = PO["rect"]
    ptop = lambda y: PO["high_height"] - (y - py0) * PO["pitch"] / 12
    rec("porch.slab", "slab", "Covered porch", "shell", info=dict(model=f"{ftin(px1 - px0)} x {ftin(py1 - py0)} covered porch, delegated design",
                                                                   specs=[["Roof", f"{PO['pitch']:g}:12, high side {ftin(PO['high_height'])} (ASSUMED)"], ["Posts", f"{len(PO['posts_x'])} per beam"]]))
    box("Concrete", px0, px1, py0, py1, -0.35, -0.05)
    for yb in (py0 + 0.2, py1 - 0.6):
        box("Trim", px0, px1, yb, yb + 0.4, ptop(yb) - 1.0, ptop(yb))
        for xp in PO["posts_x"]:
            box("Trim", xp - 0.25, xp + 0.25, yb - 0.05, yb + 0.45, 0, ptop(yb) - 1.0)
    rec("porch.roof", "roof", "Porch roof", "roof", info=dict(model=f"{PO['pitch']:g}:12 standing seam roof"))
    hexa("Trim", [(px0, py0 - 0.5, ptop(py0 - 0.5)), (px1, py0 - 0.5, ptop(py0 - 0.5)), (px1, py1 + 1, ptop(py1 + 1)), (px0, py1 + 1, ptop(py1 + 1)),
                  (px0, py0 - 0.5, ptop(py0 - 0.5) + 0.7), (px1, py0 - 0.5, ptop(py0 - 0.5) + 0.7), (px1, py1 + 1, ptop(py1 + 1) + 0.7), (px0, py1 + 1, ptop(py1 + 1) + 0.7)],
         ["Drywall", "Standing Seam", "Trim", "Trim", "Trim", "Trim"])
    seam_ribs(px0, px1, py0 - 0.5, py1 + 1, lambda y: ptop(y) + 0.7)

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
for _n, _mv in {"gallinera_chair": [0, 0, 0, -0.005], "gallinera_chair_1": [0, -0.01, 0, -0.005], "gallinera_chair_2": [0, 0, 0, -0.005],
                "gallinera_chair_3": [0, 0, 0, -0.005], "gallinera_chair_4": [0, 0.01, 0, -0.005], "gallinera_chair_5": [0, 0, 0, -0.005],
                "Light_Kitchen_1_lens": [0, 0, 0, -0.005]}.items():
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

# The baked bath 1 wet room tiled its whole west wall, straight across the A-11 walk in opening (x 38.12-38.41,
# y 23.59-26.95; Maxwell, 11/17/2026). Drop that slab and tile the wall here with the opening left open.
for it in FURN:
    if it.get("type") != "wetroom" or not it.get("walk_in"):
        continue
    x0w, y0w, y1w = it["x0"], it["y0"], it["y1"]
    o0, o1 = it["walk_in"]
    WEB_META["cull"].append(dict(box=[x0w - 0.02, y0w - 0.05, -0.1, x0w + 0.04, y1w + 0.05, 9.2], materials=["Tile Wall"]))
    rec(f"furniture.{it['id']}.west_tile", "furniture", "Shower wall tile", "furniture", room=room_at(x0w + 1, (o0 + o1) / 2),
        info=dict(model="Wall tile, wet room west wall (ASSUMED finish)", notes=["Open between the jambs per A-11 so you can walk into the shower."]))
    for a, b_ in ((y0w, o0), (o1, y1w)):
        box("Tile Wall", x0w, x0w + 0.02, a, b_, 0.02, it.get("ceiling", 9.0))
    for yj, d_ in ((o0, 1), (o1, -1)):                       # tile wraps the jambs, back to the drywall face
        box("Tile Wall", x0w - 0.31, x0w + 0.02, yj, yj + d_ * 0.02, 0.02, it.get("walk_in_head", 8.0))

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

WEB_BUILD = {"bed": web_bed, "nightstand": web_nightstand, "table_lamp": web_table_lamp, "desk_lamp": web_desk_lamp,
             "l_desk": web_l_desk, "office_chair": web_office_chair, "towel_warmer": web_towel_warmer, "bench": web_bench}
WEB_INFO = {
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
    "bench": lambda it: dict(model="Built-in mudroom unit, painted light sage (A-11 bench and cubbies; style from Maxwell's reference photo, details ASSUMED)",
                             specs=[["Size", f"{ftin(it.get('w', 8.0))} wide, up to {ftin(it.get('top', 7.95))}"],
                                    ["Bench", f"{ftin(it.get('w', 8.0) - it.get('cab_w', 2.0))} long, seat {ftin(it.get('h', 1.5))} high, {int(it.get('bays', 3))} open bays, each with a black rubber boot tray split by a divider"],
                                    ["Left side", "base cabinet with a drawer and stone counter, tall cabinet above"],
                                    ["Above the bench", f"paneled back, {int(it.get('hooks', 5))} black coat hooks, {int(it.get('cubbies', 2))} open cubbies, glass door cabinets across the top"]],
                             notes=["Rubber boot trays with dividers instead of shoe cubbies, and the mudroom layout from his reference photo (Maxwell, 11/17/2026)."]),
    "towel_warmer": lambda it: dict(model="Wall mounted towel warmer (A-11, model ASSUMED)", notes=["Moved here from the WC doorway, where it hung in the air (Maxwell, 11/17/2026)."]),
}
WEB_NAMES = {"bench": "Mudroom bench and cabinets", "bed": "Queen bed", "nightstand": "Nightstand", "table_lamp": "Table lamp", "desk_lamp": "Desk lamp", "l_desk": "L-shaped standing desk", "office_chair": "Office chair", "towel_warmer": "Towel warmer"}
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
        info=WEB_INFO.get(t, lambda i: dict(model=t))(it))
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
        if r.get("placeholder_for"):
            continue
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


NUDGED = nudge()

# ------------------------------------------------------------------ write
out = dict(
    meta=dict(generated_by="model/make_house.py", units="plan feet (x east, y south from the outside NW slab corner, z up from the slab top)",
              source="config.toml and data/traced_geometry.json; port of the v21 Blender model (archive/blender)",
              eye_ft=EYE, floors=dict(main=0.0, loft=LOFT["floor_height"], attic=FH + FLOOR_T),
              rooms=[dict(name=n, rect=[x0, y0, x1, y1]) for (n, x0, y0, x1, y1) in ROOMS]
                    + [dict(name="Loft", rect=list(LOFT["rect"]), floor=LOFT["floor_height"], upper=True)]
                    + ([dict(name="Garage", rect=list(GA["rect"]))] if GA.get("enabled") else [])
                    + ([dict(name="Porch", rect=list(C["porch"]["rect"]), outside=True)] if C.get("porch", {}).get("enabled", True) and C.get("porch", {}).get("rect") else []),
              outline=dict(house=[0, 0, HW, HD], garage=GA["rect"] if GA.get("enabled") else None, porch=C.get("porch", {}).get("rect")),
              climbs=[dict(id="loft.ladder", rect=list(LOFT["ships_ladder"]), axis="x", z0=0.0, z1=LOFT["floor_height"])] if LOFT.get("enabled") else [],
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
