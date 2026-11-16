#!/usr/bin/env python3
"""Writes site/models/house.json: the house itself (slab, walls, roof, windows, doors, cabinets, trim, loft, garage,
porch, greenhouse) as records the walkthrough builds in the browser (site/house.js). Plain Python, no Blender.

    python model/make_house.py              (then reload the site)
    python model/make_house.py --check      (also lists coplanar faces that would flicker)

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
LOFT = C["loft"]
LX0, LY0, LX1, LY1 = LOFT["rect"]
_ft = C.get("floor_trusses")
FLOOR_T = (_ft["depth_in"] + _ft.get("deck_in", 0.75)) / 12 if _ft else 0.86    # attic deck and loft floor build-up
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
    "Siding": dict(color=MM["siding_color"], rough=0.735, normal="siding_normal.jpg", normal_scale=0.5, tile=0.9, grain="vertical"),
    "Drywall": dict(color="#FFFFFF", rough=0.84, map="plaster.jpg", tile=1.5),
    "Trim": dict(color=MM["trim_color"], rough=0.5),
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
    "Gutter": dict(color=MM["trim_color"], rough=0.45, metal=0.4),
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


ROOMS = [("Bedroom 1", 31.1, 0.5, 42.6, 11.0), ("Bedroom 2", 5.9, 0.5, 16.1, 10.7), ("Bath 2", 16.1, 0.5, 22.7, 10.7), ("Bedroom 4 / study", 22.7, 0.5, 31.1, 10.7),
         ("Closet 2", 0.5, 0.5, 5.9, 5.5), ("Closet 3", 0.5, 5.5, 5.9, 10.9), ("Bedroom 3", 0.5, 10.95, 12.12, 22.41), ("Hall 2", 12.12, 10.95, 31.12, 15.03),
         ("Linen", 12.12, 15.03, 16.66, 22.87), ("Laundry", 16.66, 15.03, 31.12, 22.87), ("Closet 1", 31.12, 11.0, 42.5, 22.87), ("Utility", 0.5, 22.87, 12.12, 29.03),
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
SKIN = 0.06                                                  # siding layer
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
    hs = [(o["start"], o["end"], o["sill"], o["head"]) for o in OPEN + CLER if o["wall"] == wall]
    if wall == "C":
        hs += [(x0, x1, -0.1, hd) for (x0, x1, hd) in CL["passages"]]
    return hs


def window_unit(o):
    wall, kind = o["wall"], o["kind"]
    u0, u1, z0, z1 = o["start"], o["end"], o["sill"], o["head"]
    door = is_door(o)
    code = o["id"].split()[0]
    where = " ".join(o["id"].split()[1:])
    kn = KIND_NAMES.get(kind, kind.replace("_", " "))
    info = dict(model=f"{code} {kn}", specs=[["Rough opening", f"{ftin(u1 - u0)} wide x {ftin(z1 - z0)} tall"],
                                             ["Sill" if not door else "Threshold", ftin(z0)], ["Head", ftin(z1)], ["Wall", WALL_NAMES[wall]],
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
    v0 = SKIN + 0.05
    vm = v0 + fd * 0.5
    inner = paint(o["interior_color"]) if o.get("interior_color") else "White Oak"
    leaf = None
    if kind == "door_glass":
        fr = wall_frame(wall)
        hx, hy = fr(u0, SKIN + 0.2)
        ax = fr(u0 + 1, 0); a0 = fr(u0, 0); inn = fr(u0, 1)
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
    wbox("Trim", wall, u0 - tw, u0, -BAT_T - 0.02, SKIN, z0, z1)
    wbox("Trim", wall, u1, u1 + tw, -BAT_T - 0.02, SKIN, z0, z1)
    wbox("Trim", wall, u0 - tw, u1 + tw, -BAT_T - 0.02, SKIN, z1, z1 + tw)
    if not door:
        wbox("Trim", wall, u0 - tw, u1 + tw, -BAT_T - 0.04, SKIN, z0 - tw, z0)
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
        hs.append((o["start"] - TRIM_W, o["end"] + TRIM_W, -1 if is_door(o) else o["sill"] - TRIM_W, o["head"] + TRIM_W))
    return hs


def ew_top(y):
    return north_roof_z(y) if y < YC2 else H_CL + (y - YC2) * (H_S - H_CL) / (HD - YC2)


SIP = dict(model='6 1/2" structural insulated panels (A-11 notes)', specs=[["Siding", f"LP SmartSide board and batten, {MM['siding_color']} (Garden Sage)"],
           ["Battens", f"{MM['batten_width_in']:g}\" wide, {MM['batten_spacing_in']:g}\" on centre (spacing ASSUMED)"], ["Trim", f"LP Abyss Black {MM['trim_color']}"],
           ["Inside", f"Drywall, {MM['wall_paint']}"]])
for wall, nm, length, top in (("N", "North exterior wall", HW, [[0, H_N, HW, H_N]]), ("S", "South exterior wall", HW, [[0, H_S, HW, H_S]]),
                              ("W", "West exterior wall", HD, ew_top_segs()), ("E", "East exterior wall", HD, ew_top_segs())):
    inf = json.loads(json.dumps(SIP))
    inf["specs"] = [["Length", ftin(length)], ["Height", f"{ftin(H_N)} north, {ftin(H_S)} south (A-30)" if wall in "EW" else ftin(H_N if wall == "N" else H_S) + " panel (A-30)"]] + inf["specs"]
    rec(f"wall.ext.{wall}", "wall", nm, "shell", info=inf)
    holes = [(a, b, c, d) for (a, b, c, d) in cuts_for(wall)]
    if wall == "N":
        panel("Siding", FRAMES["N"], 0, SKIN, 0, top, holes)
        panel("Drywall", FRAMES["N"], SKIN, T, 0, [[0, north_roof_z(T), HW, north_roof_z(T)]], holes)
    else:
        panel("Siding", FRAMES[wall], 0, SKIN, 0, top, holes)
        panel("Drywall", FRAMES[wall], SKIN, T, 0, top, holes)
    if MM["siding_style"] == "board_and_batten":
        topf = (lambda u: H_N) if wall == "N" else (lambda u: H_S) if wall == "S" else ew_top
        battens("Siding", wall_frame(wall), 0, length, 0, topf, holes_for(wall))
    if MM["siding_style"] == "board_and_batten":            # corner boards at this wall's two corners (N and S walls carry them)
        for (x, y, sx, sy) in ((0, 0, 1, 1), (HW, 0, -1, 1), (HW, HD, -1, -1), (0, HD, 1, -1)):
            if (wall == "N" and y == 0) or (wall == "S" and y == HD):
                zt = H_N if y == 0 else H_S
                box("Trim", x - sx * BAT_T, x + sx * TRIM_W, y - sy * BAT_T, y, 0, zt)
                box("Trim", x - sx * BAT_T, x, y - sy * BAT_T, y + sy * TRIM_W, 0, zt)

inf = json.loads(json.dumps(SIP))
inf["specs"] = [["Location", f"{ftin(YC)} from the north wall (A-11 and A-12)"], ["Clerestory", f"{CL['count']} W30-30 awnings, sill {ftin(CL['sill'])}"],
                ["Openings below", f"{len(CL['passages'])}: pantry, hall, living (barn door), entry, coat closet"]] + inf["specs"]
rec("wall.ext.C", "wall", "Clerestory bearing wall", "shell", info=inf)
panel("Siding", FRAMES["C"], 0, SKIN, H_CL, [[T, north_roof_z(YC2), HW - T, north_roof_z(YC2)]], [h for h in cuts_for("C") if h[3] > H_CL])
panel("Drywall", FRAMES["C"], SKIN, T, 0, [[T, north_roof_z(YC2 - SKIN), HW - T, north_roof_z(YC2 - SKIN)]], cuts_for("C"))
if MM["siding_style"] == "board_and_batten":
    battens("Siding", wall_frame("C"), T, HW - T, H_CL, lambda u: north_roof_z(YC2), holes_for("C", CLER))

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


def wall_between_flats(x0, x1, y0, y1):
    def flat_or_out(x, y):
        return in_flat(x, y) or not (T < x < HW - T and T < y < HD - T)
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


def wall_top(x0, x1, y0, y1):
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    in_loft = LOFT["enabled"] and LX0 - 0.05 <= cx <= LX1 + 0.05 and LY0 + 0.3 <= cy <= LY1 + 0.6
    if in_loft:
        if abs(cx - (LX0 + 0.23)) < 0.4:                    # loft edge wall (bath 1 west wall): stops level with the loft floor
            return lambda x, y: LOFT["floor_height"] + LOFT["pony_wall_height"]
        return lambda x, y: LOFT["floor_height"] - FLOOR_T
    if C["ceilings"].get("walls_stop_at_attic") and wall_between_flats(x0, x1, y0, y1):
        return lambda x, y: FH + FLOOR_T - DECK_T               # stops under the attic deck
    return lambda x, y: roof_under(min(y, YC2))


INT_RECTS = []
for poly in G["interior_walls_from_plan_A11"]:
    for r_ in rect_decompose(poly):
        if r_[2] > YC - 0.15 and r_[3] < YC2 + 0.15:          # the clerestory wall is its own record
            continue
        INT_RECTS.append(r_)
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


for k, (x0, x1, y0, y1) in enumerate(INT_RECTS):
    top = wall_top(x0, x1, y0, y1)
    ln, th = max(x1 - x0, y1 - y0), min(x1 - x0, y1 - y0)
    zt = top((x0 + x1) / 2, (y0 + y1) / 2)
    rec(f"wall.int.{k}", "wall", f"Interior wall {between(x0, x1, y0, y1)}".strip(), "interior",
        info=dict(model=f"{ftin(th)} interior partition", specs=[["Length", ftin(ln)], ["Height", ftin(zt) if abs(top(x0, y0) - top(x1, y1)) < 0.05 else "Up to the roof"],
                                                                ["Finish", f"Drywall, {MM['wall_paint']}"]],
                  notes=["Traced from the A-11 floor plan vectors."]))
    box("Drywall", x0, x1, y0, y1, 0, 9, ztop=top)

DOOR_GAPS, FIXES = [], []


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
                    if 0.02 < gap1 - gap0 <= 1.4 and not any(r is not a and r is not b and r[0] < gap1 - 0.01 and r[1] > gap0 + 0.01 and r[2] < a[3] and r[3] > a[2] for r in rects):
                        FIXES.append(("sliver", gap0, gap1, min(a[2], b[2]), max(a[3], b[3]), wall_top(gap0, gap1, a[2], a[3])))
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
                    if 0.02 < gap1 - gap0 <= 1.4 and not any(r is not a and r is not b and r[2] < gap1 - 0.01 and r[3] > gap0 + 0.01 and r[0] < a[1] and r[1] > a[0] for r in rects):
                        FIXES.append(("sliver", min(a[0], b[0]), max(a[1], b[1]), gap0, gap1, wall_top(a[0], a[1], gap0, gap1)))
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
        _, x0, x1, y0, y1, top = f_
        rec(f"wall.fill.{nh}", "wall", f"Interior wall {between(x0, x1, y0, y1)}".strip(), "interior",
            info=dict(model="Short wall piece", notes=["Fills a gap of under 1' 5\" between two traced wall ends."]))
        box("Drywall", x0, x1, y0, y1, 0, 9, ztop=top)
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
    box("White Oak", LX0, LX1, LY0, LY1, FL - FLOOR_T, FL)
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
            stack(run, r, u0, u1, KICK, 1.25, df, mat, [1])
            doors(run, r, u0, u1, 4.6, TALL - 0.25, df, mat, 2)
            placeholder(run, rn, k, "oven", "Double wall oven (placeholder)")
            run.box("Stainless", u0 + 0.1, u1 - 0.1, df - 0.02, df + 0.05, 1.3, 4.55)
            for zz in (1.45, 3.05):
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
    info=dict(model="Stainless chimney hood", specs=[["Width", ftin(cy1 - cy0 - 0.2)], ["Underside", "6' 0\""]], notes=["Model not picked yet."]))
wr.box("Stainless", cy0 + 0.1, cy1 - 0.1, 0, 1.9, 6.0, 6.35)
wr.box("Stainless", (cy0 + cy1) / 2 - 0.45, (cy0 + cy1) / 2 + 0.45, 0, 0.9, 6.35, 11.6)
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
    for da in FU.get("door_add", []):
        DOOR_GAPS.append((da["axis"], da["g0"], da["g1"], da["t0"], da["t1"], da.get("head", 6.67)))
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
        r = rec(f"door.int.{nd_ + 1}", "door", f"{'Pocket door' if pocket_dir else 'Door'}{', ' + rooms if rooms else ''}", "interior",
                info=dict(model=f"{lab + ' ' if lab else ''}white oak {'pocket' if pocket_dir else 'slab'} door{' pair' if len(leaves) > 1 else ''}",
                          specs=[["Opening", f"{ftin(wdt)} x {ftin(h)}"], ["Hardware", "Flush pulls" if pocket_dir else "Brushed nickel levers"]],
                          notes=["Opening found where two traced A-11 wall ends line up. Style ASSUMED (slab doors, white oak casing)."] + (["Pocket door, Maxwell 11/13/2026."] if pocket_dir else [])))

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
                hp = (ha, tm) if ax == "x" else (tm, ha)
                sgn_ = (-1 if ax == "x" else 1) * (1 if k_ == 0 else -1)
                lf = op(r, f"{r['id']}.leaf{suffix}", r["name"], "swing", (hp[0], hp[1], 0), angle=90 * sgn_)
                with into(lf["parts"]):
                    B("White Oak", l0, l1, tm - 0.07, tm + 0.07, 0.04, h - 0.08)
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
        for (b0, b1) in ((YC - 0.06, YC), (YC2, YC2 + 0.06)):
            box("White Oak", x0 - CW, x0 + 0.02, b0, b1, 0, hd)
            box("White Oak", x1 - 0.02, x1 + CW, b0, b1, 0, hd)
            box("White Oak", x0 - CW, x1 + CW, b0, b1, hd, hd + CW)

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
                             "hose_bib": "Frost free hose bib"}.get(t_, t_), specs=[["Height", ftin(z_)]], notes=["Location ASSUMED."]))
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
                  specs=[["South wall", f"{ftin(GA['south_wall_height'])} (ASSUMED from the A-20 scale)"], ["Roof", f"{GA['pitch']:g}:12 down to the south"],
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
        lf = op(r, f"garage.door.{k + 1}.panel", r["name"], "rollup", (gx0 + s0 + w / 2, gy1 - 0.35, 0))
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
WEB_META = dict(replace_nodes=[], cull=[], move_nodes={})
FURN_MATS = ["Bedding", "Fabric #F1EEE8", "Fabric #9A6B4A", "Fabric #7D8A6C", "Fabric #56614A", "White Oak", "Upholstery", "Black Metal",
             "Brushed Nickel", "Cabinet Wood", "Plastic Grey", "painted_wooden_nightstand", "Lamp Shade"]


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
    """UPLIFT V2 L-shaped desk. facing 90: you sit facing east, the main top on the east wall, return on the right (south)."""
    x0, y0 = it["x0"], it["y0"]
    mL, mD = it["main"][0] / 12, it["main"][1] / 12
    rL, rW = it["ret"][0] / 12, it["ret"][1] / 12
    H, T = it.get("height_in", 29.0) / 12, it.get("top_in", 1.0) / 12
    mx0, mx1, my0, my1 = x0, x0 + mD, y0, y0 + mL                                       # main top
    if it.get("side", "right") == "right":
        rx0, rx1, ry0, ry1 = x0 - rL, x0, my1 - rW, my1
    else:
        rx0, rx1, ry0, ry1 = x0 - rL, x0, my0, my0 + rW
    box("Walnut Laminate", mx0, mx1, my0, my1, H - T, H)
    box("Walnut Laminate", rx0, rx1, ry0, ry1, H - T, H)
    LW, LD = 80 / 304.8, 50 / 304.8                                                       # 50 x 80 mm legs
    legs = [((mx0 + mx1) / 2 + 0.2, my0 + 0.55, "x"), ((mx0 + mx1) / 2 + 0.2, (ry0 + ry1) / 2, "x"), (rx0 + 0.55, (ry0 + ry1) / 2, "y")]
    for (lx, ly, foot) in legs:
        box("Black Metal", lx - LW / 2, lx + LW / 2, ly - LD / 2, ly + LD / 2, 0.08, H - T - 0.1)
        if foot == "x":
            box("Black Metal", mx0 + 0.15, mx1 - 0.1, ly - 0.1, ly + 0.1, 0.0, 0.08)
        else:
            box("Black Metal", lx - 0.1, lx + 0.1, ry0 + 0.1, ry1 - 0.1, 0.0, 0.08)
    box("Black Metal", (mx0 + mx1) / 2 + 0.1, (mx0 + mx1) / 2 + 0.3, my0 + 0.4, my1 - 0.3, H - T - 0.1, H - T)     # frame under the tops
    box("Black Metal", rx0 + 0.4, mx0 + 0.6, (ry0 + ry1) / 2 - 0.1, (ry0 + ry1) / 2 + 0.1, H - T - 0.1, H - T)
    box("Black Metal", mx0 - 0.02, mx0 + 0.25, ry0 - 0.35, ry0 - 0.05, H - T - 0.07, H - T)                    # keypad, front edge
    box("Paint #1E2022", mx0 + 0.2, mx0 + 1.4, my0 + 0.6, my0 + 2.4, H, H + 0.01)                               # desk pad
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

WEB_BUILD = {"bed": web_bed, "nightstand": web_nightstand, "table_lamp": web_table_lamp, "desk_lamp": web_desk_lamp,
             "l_desk": web_l_desk, "office_chair": web_office_chair}
WEB_INFO = {
    "bed": lambda it: dict(model="Queen bed, 60 x 80 in mattress on a white oak platform (ASSUMED)", notes=["Queen, and placed so the side tables clear both doors (Maxwell, 11/16/2026)."]),
    "nightstand": lambda it: dict(model=f"Nightstand, {ftin(it.get('w', 1.4))} wide (ASSUMED)"),
    "table_lamp": lambda it: dict(model="Table lamp (ASSUMED)"),
    "desk_lamp": lambda it: dict(model="UPLIFT E3 LED desk lamp, black (came with the desk order)"),
    "l_desk": lambda it: dict(model="UPLIFT V2 L-shaped standing desk", price="$1,462.85 (04/2022, order SO778262)",
                              specs=[["Size", "60\" main x 60\" return, return on the right"], ["Top", "1\" walnut laminate, main 59.6 x 30 in, return 30 x 27.5 in"],
                                     ["Frame", "V2 C-frame, 3 legs, black"], ["Controls", "Advanced keypad"], ["Shown at", "29 in, seated height (it stands up to about 50 in)"]],
                              notes=["Maxwell's own desk, from his UPLIFT order. Placed on the east wall, off the window (Maxwell, 11/16/2026)."]),
    "office_chair": lambda it: dict(model="Office chair (stand in, ASSUMED)"),
}
WEB_NAMES = {"bed": "Queen bed", "nightstand": "Nightstand", "table_lamp": "Table lamp", "desk_lamp": "Desk lamp", "l_desk": "L-shaped standing desk", "office_chair": "Office chair"}
for it in FURN:
    if it.get("moved_from"):
        ox, oy, of = it["moved_from"]
        WEB_META["move_nodes"][it["id"]] = [rnd(it["x"] - ox), rnd(it["y"] - oy), -(it.get("facing", 0) - of)]
    if not it.get("web"):
        continue
    t = it["type"]
    WEB_META["replace_nodes"].append(it["id"])
    if it.get("cull_old"):
        x0, y0, x1, y1, zt = it["cull_old"]
        WEB_META["cull"].append(dict(box=[x0, y0, 0.02, x1, y1, zt], materials=FURN_MATS))
    cx = it.get("x", it.get("x0"))
    cy = it.get("y", it.get("y0"))
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
def faces_of(s):
    """axis aligned faces of box shapes: (axis, sign, plane, rect)"""
    if s[0] != "b":
        return []
    x0, x1, y0, y1, z0, z1 = s[2:8]
    return [(0, -1, x0, (y0, y1, z0, z1)), (0, 1, x1, (y0, y1, z0, z1)), (1, -1, y0, (x0, x1, z0, z1)), (1, 1, y1, (x0, x1, z0, z1)),
            (2, -1, z0, (x0, x1, y0, y1)), (2, 1, z1, (x0, x1, y0, y1))]


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
    return (s[3] - s[2]) * (s[5] - s[4]) * (s[7] - s[6])


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
            if (id(small), ax, sg) in done:
                continue
            done.add((id(small), ax, sg))
            i = 2 + 2 * ax + (1 if sg > 0 else 0)
            small[i] = rnd(small[i] + sg * 0.0026)
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
print(f"coplanar faces nudged apart: {NUDGED[0]}, left: {NUDGED[1]}")
if "--check" in sys.argv:
    for (key, a, b) in zfight_pairs()[:60]:
        print("  ", key, a[0], a[1], b[0], b[1])
