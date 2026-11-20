#!/usr/bin/env python3
"""Door header and framing clash check (python3 tools/header_clash.py from the repo root, after model/make_house.py and
model/make_equipment.py).

Reads the framing that make_house.py lists in site/models/house.json (meta.framing: every opening's header, its king and
jack studs, which walls are standing) and the ducts and wall grilles in site/models/equipment.json. Flags:
  - a duct or wall stack that runs through a header, the framing over a door, or a door's king and jack studs (pocket
    doors include the pocket),
  - a wall grille or boot that cuts into a header or the top plates, or sits within 2 in of them,
  - a wall stack where another wall meets its wall (the corner studs or blocking fill that bay).
Headers in walls that are not framed yet are typical sizes (ASSUMED); those findings say "planned".
Prints every finding and exits 1 if any is a clash. --all also prints the near misses that pass.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
H = json.load(open(os.path.join(HERE, "..", "site", "models", "house.json")))
D = json.load(open(os.path.join(HERE, "..", "site", "models", "equipment.json")))
FM = H["meta"].get("framing") or {}
IN = 1 / 12
NEAR = 2 * IN                       # a grille this close to a header or the plates is called tight
SHOW_ALL = "--all" in sys.argv


def ovl(a0, a1, b0, b1, pad=0.0):
    return min(a1, b1) - max(a0, b0) > -pad


def duct_boxes(dc):
    """axis aligned boxes (x0, x1, y0, y1, z0, z1) for each straight run of a duct"""
    if isinstance(dc["size"], (int, float)):
        w = h = dc["size"] * IN
    else:
        w, h = dc["size"][0] * IN, dc["size"][1] * IN
    out = []
    for a, b in zip(dc["points"], dc["points"][1:]):
        dx, dy, dz = abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2])
        if dz >= max(dx, dy):                        # vertical: a wall stack. Its width lies along the wall it is in
            ww, dd = (w, h) if not isinstance(dc["size"], (int, float)) else (w, w)
            along_x = stack_along_x(a)
            hx, hy = (ww / 2, dd / 2) if along_x else (dd / 2, ww / 2)
            hz = 0
        elif dx >= dy:
            hx, hy, hz = 0, w / 2, h / 2
        else:
            hx, hy, hz = w / 2, 0, h / 2
        out.append((min(a[0], b[0]) - hx, max(a[0], b[0]) + hx, min(a[1], b[1]) - hy, max(a[1], b[1]) + hy,
                    min(a[2], b[2]) - hz, max(a[2], b[2]) + hz))
    return out


def stack_along_x(p):
    """a vertical stack sits in the wall that contains its plan point; True if that wall runs east-west"""
    for w in FM.get("walls", []):
        x0, x1, y0, y1 = w["rect"]
        if x0 - 0.05 <= p[0] <= x1 + 0.05 and y0 - 0.05 <= p[1] <= y1 + 0.05:
            return (x1 - x0) >= (y1 - y0)
    return True


def header_zones(hd):
    """(label, box) zones of one opening's framing: the header and the framing over it up to the plates, and the king and jack studs"""
    x0, x1, y0, y1, z0, z1 = hd["box"]
    k0, k1 = hd["kings"]
    r0, r1 = hd["ro"]
    t0, t1 = hd["band"]
    top = hd["top"]
    ax = hd["axis"]
    def bx(u0, u1, za, zb):
        return (u0, u1, t0, t1, za, zb) if ax == "x" else (t0, t1, u0, u1, za, zb)
    return [("header and the framing over it", bx(k0, k1, z0, top), z0, z1),
            ("king and jack studs", bx(k0, r0, 0, z0), None, None),
            ("king and jack studs", bx(r1, k1, 0, z0), None, None),
            ("rough opening (door or pocket)", bx(r0, r1, 0, z0), None, None)]


finds = []


def add(kind, dc_id, hd, text):
    finds.append((kind, dc_id, hd, text))


for dc in D["ducts"]:
    for b in duct_boxes(dc):
        for hd in FM.get("headers", []):
            for label, z, hb, ht in header_zones(hd):
                if ovl(b[0], b[1], z[0], z[1], -1e-3) and ovl(b[2], b[3], z[2], z[3], -1e-3) and ovl(b[4], b[5], z[4], z[5], -1e-3):
                    add("CLASH", dc["id"], hd, f"{dc['id']} ({dc['size']} in) runs through the {label} of {hd['name']}")
                    break
    # wall grilles: the grille face and its boot sit in the wall at the grille's height
    for g in dc.get("grilles", []):
        if not g.get("wall"):
            continue
        gx, gy, gz = g["at"]
        gw, gh = g["size"][0] * IN, g["size"][1] * IN
        for hd in FM.get("headers", []):
            t0, t1 = hd["band"]
            c = gy if hd["axis"] == "x" else gx
            u = gx if hd["axis"] == "x" else gy
            if not (t0 - 0.35 <= c <= t1 + 0.35):
                continue
            k0, k1 = hd["kings"]
            if not ovl(u - gw / 2, u + gw / 2, k0, k1):
                continue
            z0, z1 = hd["box"][4], hd["box"][5]
            top = hd["top"]
            lo, hi = gz - gh / 2, gz + gh / 2
            if ovl(lo, hi, z0, top, -1e-3):
                add("CLASH", dc["id"], hd, f"{dc['id']} grille ({g['size'][0]} x {g['size'][1]}, centre {gz:.2f} ft) cuts into {hd['name']} (header {z0:.2f} to {z1:.2f} ft, plates to {top:.2f} ft)")
            elif lo - top < NEAR and lo >= top:
                add("TIGHT", dc["id"], hd, f"{dc['id']} grille bottom is {12 * (lo - top):.1f} in above the top plates over {hd['name']} (plates top {top:.2f} ft)")
            elif SHOW_ALL:
                add("ok", dc["id"], hd, f"{dc['id']} grille clears {hd['name']} by {12 * min(abs(lo - top), abs(z0 - hi)):.1f} in")

# headers and studs that would show: a header whose bottom is below the opening's head pokes through the drywall
# over the door, and a jack or king inside the door opening stands in the doorway.
for hd in FM.get("headers", []):
    if not hd.get("built") or "gap" not in hd:
        continue
    g0, g1 = hd["gap"]
    r0, r1 = hd["ro"]
    if hd["box"][4] < hd["head"] - 1e-3:
        add("CLASH", "framing", hd, f"the header over {hd['name']} (bottom {12 * hd['box'][4]:.1f} in) is below the opening's head ({12 * hd['head']:.1f} in): it shows through")
    if r0 > g0 + 0.01 or r1 < g1 - 0.01:
        add("CLASH", "framing", hd, f"the studs of {hd['name']} stand in the doorway (rough opening {r0:.2f} to {r1:.2f}, door opening {g0:.2f} to {g1:.2f})")

# wall grilles against the top plates of the wall they sit in (standing walls only; the plates of the rest are not up yet)
PLATES = FM.get("plates_in", 3.0) * IN
for dc in D["ducts"]:
    for g in dc.get("grilles", []):
        if not g.get("wall"):
            continue
        gx, gy, gz = g["at"]
        gw, gh = g["size"][0] * IN, g["size"][1] * IN
        lo, hi = gz - gh / 2, gz + gh / 2
        for wl in FM.get("walls", []):
            if not wl.get("built"):
                continue
            x0, x1, y0, y1 = wl["rect"]
            ax = (x1 - x0) >= (y1 - y0)
            u, c = (gx, gy) if ax else (gy, gx)
            u0, u1, c0, c1 = (x0, x1, y0, y1) if ax else (y0, y1, x0, x1)
            if not (c0 - 0.35 <= c <= c1 + 0.35 and ovl(u - gw / 2, u + gw / 2, u0, u1, -1e-3)):
                continue
            top = wl["top"]
            if ovl(lo, hi, top - PLATES, top, -1e-3):
                add("CLASH", dc["id"], None, f"{dc['id']} grille ({g['size'][0]} x {g['size'][1]}, {lo:.2f} to {hi:.2f} ft) cuts the top plates of a standing wall (plates {top - PLATES:.2f} to {top:.2f} ft)")
            elif 0 <= lo - top < NEAR:
                add("TIGHT", dc["id"], None, f"{dc['id']} grille bottom is {12 * (lo - top):.1f} in above the top plates of a standing wall ({top:.2f} ft): the boot goes through whatever sits on those plates (truss ends, rim or blocking)")

# wall stacks against walls that meet theirs
for dc in D["ducts"]:
    for a, b in zip(dc["points"], dc["points"][1:]):
        if abs(a[0] - b[0]) > 1e-3 or abs(a[1] - b[1]) > 1e-3 or abs(a[2] - b[2]) < 1:
            continue
        w = (dc["size"] if isinstance(dc["size"], (int, float)) else dc["size"][0]) * IN
        ax = stack_along_x(a)
        u, c = (a[0], a[1]) if ax else (a[1], a[0])
        for wl in FM.get("walls", []):
            x0, x1, y0, y1 = wl["rect"]
            wax = (x1 - x0) >= (y1 - y0)
            if wax == ax:
                continue
            wu0, wu1, wc0, wc1 = (x0, x1, y0, y1) if ax else (y0, y1, x0, x1)
            if ovl(u - w / 2, u + w / 2, wu0, wu1, -1e-3) and (abs(wc0 - c) < 0.35 or abs(wc1 - c) < 0.35 or wc0 <= c <= wc1):
                add("CLASH", dc["id"], None, f"{dc['id']} stack at {'x' if ax else 'y'} {u:.2f} sits where a wall meets its wall ({'built' if wl['built'] else 'not framed yet'}, {wu0:.2f} to {wu1:.2f}): corner studs fill that bay")

# wall stacks against the studs Maxwell measured ([framing] stud_lines in config.toml)
import tomllib
CFGT = tomllib.load(open(os.path.join(HERE, "..", "model", "config.toml"), "rb"))
for sl in CFGT.get("framing", {}).get("stud_lines", []):
    studs = [(sl["x0"] + e / 12 - 1.5 / 12, sl["x0"] + e / 12) for e in sl["right_edges_in"]]
    for dc in D["ducts"]:
        for a, b in zip(dc["points"], dc["points"][1:]):
            if abs(a[0] - b[0]) > 1e-3 or abs(a[1] - b[1]) > 1e-3 or abs(a[2] - b[2]) < 1 or abs(a[1] - sl["at"]) > 0.3:
                continue
            w = (dc["size"] if isinstance(dc["size"], (int, float)) else dc["size"][0]) * IN
            if a[0] - w / 2 > studs[-1][1]:
                continue                               # past the measured part of the wall
            hit = [s0 for s0, s1 in studs if ovl(a[0] - w / 2, a[0] + w / 2, s0, s1, -1e-3)]
            if hit:
                add("CLASH", dc["id"], None, f"{dc['id']} stack at x {a[0]:.2f} ({w * 12:.0f} in wide) hits a measured stud at x {hit[0]:.2f}")

seen, n_bad = set(), 0
for kind, did, hd, text in finds:
    if text in seen:
        continue
    seen.add(text)
    tag = ""
    if hd is not None:
        tag = (" [built, from photos, " + hd["confidence"] + " confidence]") if hd["built"] and hd["photo"] else (" [built, typical size]" if hd["built"] else " [planned wall, typical framing]")
    print(f"{kind:5} {text}{tag}")
    n_bad += kind == "CLASH"
print(f"{n_bad} clashes, {sum(1 for f in finds if f[0] == 'TIGHT')} tight")
sys.exit(1 if n_bad else 0)
