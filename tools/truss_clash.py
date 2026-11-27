#!/usr/bin/env python3
"""Duct and truss clash check (python3 tools/truss_clash.py from the repo root, after model/make_equipment.py).

Reads site/models/equipment.json and lays out the open web floor trusses the same way site/equipment.js does.
A duct in the truss space may:
  - run parallel to the trusses (north to south) or straight up and down, if it stays clear of every truss in a bay,
  - cross the trusses (any run that is not north to south) only if it is round and no bigger than MAX_CROSS in, through the web openings
    (a duct's own cross_ok field raises that limit for that one run), and clear of every chord and web it passes, with the webs
    laid out as site/equipment.js draws them (model/make_equipment.py _thread_ducts moves each crossing run into an opening).
Prints every offender and exits 1 if there is one.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, "..", "site", "models", "equipment.json")))
T = D["trusses"]
MAX_CROSS = T.get("max_cross_in", 6.0)               # largest round duct that passes the web openings ([floor_trusses] in config.toml)
DEP, SP, Z0 = T["depth_in"] / 12, T["spacing_in"] / 12, T["z0"]
CW, E = T.get("chord_w_in", 3.5) / 12, 0.05


def truss_xs(r):
    rx0, ry0, rx1, ry1 = r
    x0, x1 = rx0 + E, rx1 - E
    if T.get("grid_x0") is not None:               # one grid for the whole house: trusses run continuous over the walls
        g, sp = T["grid_x0"], SP
        k0 = int((x0 + CW / 2 - g) // sp) - 1
        return [g + k * sp for k in range(k0, k0 + 200) if x0 + CW / 2 - 1e-6 <= g + k * sp <= x1 - CW / 2 + 1e-6]
    n = max(1, round((x1 - x0) / SP))
    return [min(x1 - CW / 2, max(x0 + CW / 2, x0 + i * (x1 - x0) / n)) for i in range(n + 1)]


REG = [(r, T["xs"][i] if "xs" in T else truss_xs(r)) for i, r in enumerate(T["regions"] + T.get("loft_regions", []))]
bad = []
for dc in D["ducts"]:
    rnd = dc.get("shape") == "round" or isinstance(dc["size"], (int, float))
    size = dc["size"] if isinstance(dc["size"], (int, float)) else dc["size"][0]
    hw = size / 24
    for a, b in zip(dc["points"], dc["points"][1:]):
        zlo, zhi = min(a[2], b[2]), max(a[2], b[2])
        if zhi < Z0 + 0.05 or zlo > Z0 + DEP - 0.05:
            continue                               # not in the truss space
        ns = abs(a[0] - b[0]) < 1e-3
        for (rx0, ry0, rx1, ry1), xs in REG:
            ylo, yhi = min(a[1], b[1]), max(a[1], b[1])
            xlo, xhi = min(a[0], b[0]), max(a[0], b[0])
            if yhi < ry0 or ylo > ry1 or xhi < rx0 or xlo > rx1:
                continue
            if ns:
                for x in xs:
                    if abs(a[0] - x) < hw + CW / 2 - 1e-3:
                        bad.append(f"{dc['id']}: {size} in run at x {a[0]:.2f} hits the truss at x {x:.2f} (y {ylo:.1f} to {yhi:.1f})")
            else:
                pad = hw if rnd else 0.0                # a rect run's width lies across its length
                crossed = [x for x in xs if xlo - pad - CW / 2 < x < xhi + pad + CW / 2]
                for ex, ey0, ey1 in T.get("solid_ends", []):   # a solid trimmable end has no web openings at all
                    if ex in crossed and ey0 - hw < a[1] < ey1 + hw and a[1] == b[1]:
                        bad.append(f"{dc['id']}: {size} in run at y {a[1]:.2f} crosses the solid end of the truss at x {ex:.2f} (solid to y {ey1:.2f})")
                if crossed and (not rnd or size > dc.get("cross_ok", MAX_CROSS)):   # cross_ok: a run the owner has allowed to cross at a bigger size
                    bad.append(f"{dc['id']}: {'round ' if rnd else 'rect '}{dc['size']} crosses {len(crossed)} trusses at y {a[1]:.1f} (max {MAX_CROSS} in round)")

# The web triangles as site/equipment.js draws them (measured 21 in triangles, lined up from web_y0): a round run that
# crosses the trusses must clear every chord and web it passes (Maxwell, 11/27/2026: the ducts follow the trusses).
import math
def planes():
    t = T; D_, CH_, WW_ = t["depth_in"] / 12, 1.5 / 12, t.get("web_in", 1.5) / 12
    P_ = (t.get("web_pitch_in") or 0) / 24
    lo_, hi_ = t["z0"] + 0.07 + CH_, t["z0"] + D_ - 0.01 - CH_
    out = []
    for ri, (rx0, ry0, rx1, ry1) in enumerate(t["regions"] + t.get("loft_regions", [])):
        y0_, y1_ = ry0 + 0.05, ry1 - 0.05
        for x in (t["xs"][ri] if "xs" in t else truss_xs((rx0, ry0, rx1, ry1))):
            w0, w1, sol = y0_, y1_, []
            for ex, ey0, ey1 in t.get("solid_ends", []):
                if abs(ex - x) > 0.01 or ey1 <= y0_ or ey0 >= y1_:
                    continue
                atN, atS = ey0 <= y0_ + 0.2, ey1 >= y1_ - 0.2
                if not (atN or atS):
                    continue
                e0, e1 = (y0_, min(ey1, y1_)) if atN else (max(ey0, y0_), y1_)
                sol.append((e0, e1))
                if atN: w0 = max(w0, e1)
                else: w1 = min(w1, e0)
            o = [w for w in t.get("web_y0", []) if abs(w[0] - x) < 0.01 and w[2] < ry1]
            rg = (t.get("web_y0_region") or [None] * 99)[ri]
            if not o and rg is not None:
                o = [[x, rg]]
            nodes = []
            if o and P_:
                k = math.ceil((w0 - o[0][1]) / P_ - 1e-6)
                while o[0][1] + k * P_ <= w1 + 1e-6:
                    nodes.append((o[0][1] + k * P_, hi_ if k % 2 == 0 else lo_)); k += 1
            else:
                n_ = max(2, round((w1 - w0) / (P_ or D_ * 1.5)))
                nodes = [(w0 + k * (w1 - w0) / n_, hi_ if k % 2 else lo_) for k in range(n_ + 1)]
            out.append(dict(x=x, y0=y0_, y1=y1_, solids=sol, segs=list(zip(nodes, nodes[1:])) if w1 - w0 > 0.3 else []))
    return out, lo_, hi_, WW_
PL, LO_, HI_, WW_ = planes()
for dc in D["ducts"]:
    if not isinstance(dc["size"], (int, float)):
        continue
    r = dc["size"] / 24
    for a, b in zip(dc["points"], dc["points"][1:]):
        if abs(a[1] - b[1]) > 1e-3 or abs(a[2] - b[2]) > 1e-3 or abs(a[0] - b[0]) < 1e-3 or not (Z0 < a[2] < Z0 + DEP):
            continue
        y, z = a[1], a[2]; xl, xh = sorted((a[0], b[0]))
        for p_ in PL:
            if not (xl - r < p_["x"] < xh + r and p_["y0"] <= y <= p_["y1"]):
                continue
            c = min(z - r - LO_, HI_ - z - r)
            for (ya, za), (yb, zb) in p_["segs"]:
                dy_, dz_ = yb - ya, zb - za
                u = max(0.0, min(1.0, ((y - ya) * dy_ + (z - za) * dz_) / (dy_ * dy_ + dz_ * dz_)))
                c = min(c, math.hypot(y - ya - u * dy_, z - za - u * dz_) - WW_ / 2 - r)
            if c < -0.005:
                bad.append(f"{dc['id']}: {dc['size']} in run at y {y:.2f}, z {z:.2f} hits a chord or web of the truss at x {p_['x']:.2f} by {-c * 12:.2f} in")
for b in bad:
    print(b)
print(f"{len(bad)} duct and truss clashes")
sys.exit(1 if bad else 0)
