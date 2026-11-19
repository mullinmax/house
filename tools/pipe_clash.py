#!/usr/bin/env python3
"""Pipe, duct and equipment clash check (python3 tools/pipe_clash.py from the repo root, after model/make_equipment.py).

Reads site/models/equipment.json and site/models/house.json and reports:
  - a pipe that passes through a wall below the flat ceiling,
  - two pipes that pass through each other (a tee, where one run ends on the other, is fine),
  - a pipe or duct that passes through a piece of equipment it does not connect to,
  - a pipe that passes through a duct, and two ducts that pass through each other above the ceiling
    (a branch, where one duct ends on or starts from the other, is fine).
Prints every offender and exits 1 if there is one.
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "site", "models", "equipment.json")))
H = json.load(open(os.path.join(HERE, "..", "site", "models", "house.json")))
CEIL = D["trusses"]["z0"]
TOL = 0.004                                        # ft, so parts that just touch do not count
bad = []


def sub(a, b): return [a[i] - b[i] for i in range(3)]
def dot(a, b): return sum(a[i] * b[i] for i in range(3))
def lerp(a, b, t): return [a[i] + (b[i] - a[i]) * t for i in range(3)]
def dist(a, b): return math.sqrt(dot(sub(a, b), sub(a, b)))


def seg_seg(p1, q1, p2, q2):
    """Closest points between two segments (Ericson, Real-Time Collision Detection 5.1.9)."""
    d1, d2, r = sub(q1, p1), sub(q2, p2), sub(p1, p2)
    a, e, f = dot(d1, d1), dot(d2, d2), dot(d2, r)
    if a < 1e-12 and e < 1e-12: return p1, p2
    if a < 1e-12: s, t = 0.0, min(1.0, max(0.0, f / e))
    else:
        c = dot(d1, r)
        if e < 1e-12: t, s = 0.0, min(1.0, max(0.0, -c / a))
        else:
            b = dot(d1, d2); den = a * e - b * b
            s = min(1.0, max(0.0, (b * f - c * e) / den)) if den > 1e-12 else 0.0
            t = (b * s + f) / e
            if t < 0: t, s = 0.0, min(1.0, max(0.0, -c / a))
            elif t > 1: t, s = 1.0, min(1.0, max(0.0, (b - c) / a))
    return lerp(p1, q1, s), lerp(p2, q2, t)


def segs(pts): return list(zip(pts, pts[1:]))


def box_of(a, b, hx, hy, hz):
    return [min(a[0], b[0]) - hx, min(a[1], b[1]) - hy, min(a[2], b[2]) - hz, max(a[0], b[0]) + hx, max(a[1], b[1]) + hy, max(a[2], b[2]) + hz]


def duct_boxes(dc):
    """One axis aligned box per segment. A rect duct's size is [across, tall] for a level run and [along x, along y] for a riser."""
    out = []
    for a, b in segs(dc["points"]):
        d = [abs(b[i] - a[i]) for i in range(3)]
        if isinstance(dc["size"], (int, float)):
            r = dc["size"] / 24
            ax = d.index(max(d))
            h = [r, r, r]
            if max(d) > 1e-6 and sorted(d)[1] < 1e-3: h[ax] = 0.0       # axis aligned: no padding along its length
            out.append(box_of(a, b, *h))
        else:
            w, t = dc["size"][0] / 24, dc["size"][1] / 24
            if d[2] > max(d[0], d[1]): out.append(box_of(a, b, w, t, 0.0))
            elif d[0] >= d[1]: out.append(box_of(a, b, 0.0, w, t))
            else: out.append(box_of(a, b, w, 0.0, t))
    return out


def overlap(b1, b2, tol=TOL):
    return all(b1[i] < b2[i + 3] - tol and b2[i] < b1[i + 3] - tol for i in range(3))


def inside(p, b, pad=0.0):
    return all(b[i] - pad <= p[i] <= b[i + 3] + pad for i in range(3))


def seg_hits_box(a, b, r, bx):
    n = max(2, int(dist(a, b) / 0.03) + 1)
    return any(inside(lerp(a, b, k / n), bx, r - TOL) for k in range(n + 1))


# ---- equipment keep out boxes, from each item's size, facing and builder frame (local +x right, +y up, +z out of the front)
def item_box(it):
    s, b = it["size"], it["builder"]
    if b in ("hpwh", "storage_tank"): lo, hi = [-s[0] / 2, 0, 2], [s[0] / 2, s[1], 2 + s[0]]
    elif b == "geo_horizontal": lo, hi = [-s[2] / 2, 0, 0], [s[2] / 2, s[1], s[0]]
    elif b in ("erv", "flow_center", "big_blue", "spin_down", "uv_system"): lo, hi = [-s[0] / 2, 0, 0], [s[0] / 2, s[1], s[2]]
    elif b == "pressure_tank": lo, hi = [-s[0] / 2, 0, 1], [s[0] / 2, s[1], 1 + s[0]]
    elif b == "expansion_tank": lo, hi = [-s[0] / 2, -3 - s[1], -s[0] / 2], [s[0] / 2, -3, s[0] / 2]
    else: return None
    th = math.radians(180 - it.get("facing", 0)); c, sn = math.cos(th), math.sin(th)
    xs, ys = [], []
    for lx in (lo[0], hi[0]):
        for lz in (lo[2], hi[2]):
            x = -lx if it.get("mirror") else lx
            xs.append(it["at"][0] + (x * c + lz * sn) / 12); ys.append(it["at"][1] + (-x * sn + lz * c) / 12)
    return [min(xs), min(ys), it["at"][2] + lo[1] / 12, max(xs), max(ys), it["at"][2] + hi[1] / 12]


BOXES = {it["id"]: bx for it in D["items"] if it.get("layer") == "mechanical" for bx in [item_box(it)] if bx}
ROUND = {it["id"] for it in D["items"] if it["builder"] in ("hpwh", "storage_tank", "expansion_tank", "pressure_tank")}   # tanks: test the circle, not its square


def hits_item(a, b, r, iid):
    bx = BOXES[iid]
    if iid not in ROUND: return seg_hits_box(a, b, r, bx)
    cx, cy, rad = (bx[0] + bx[3]) / 2, (bx[1] + bx[4]) / 2, (bx[3] - bx[0]) / 2
    n = max(2, int(dist(a, b) / 0.03) + 1)
    for k in range(n + 1):
        p = lerp(a, b, k / n)
        if bx[2] - r + TOL <= p[2] <= bx[5] + r - TOL and math.hypot(p[0] - cx, p[1] - cy) < rad + r - TOL: return True
    return False

# ---- interior and exterior wall boxes below the flat ceiling near the pipes
WALLS = []
for rec in H["records"]:
    if rec["kind"] != "wall": continue
    for p in rec["parts"]:
        if p[0] == "x":
            v = p[2]; xs, ys, zs = v[0::3], v[1::3], v[2::3]
            WALLS.append((rec["name"], [min(xs), min(ys), min(zs), max(xs), max(ys), min(max(zs), CEIL)]))
        elif p[0] == "b":
            WALLS.append((rec["name"], [p[2], p[4], p[6], p[3], p[5], min(p[7], CEIL)]))

RUNS = D["runs"]
for r in RUNS:
    rad = r.get("dia", 1.66) / 24
    ends = [r["points"][0], r["points"][-1]]
    for a, b in segs(r["points"]):
        # walls
        for name, bx in WALLS:
            if bx[5] - bx[2] > 1.0 and seg_hits_box(a, b, rad, bx):
                bad.append(f"{r['id']}: passes through {name} near x {a[0]:.2f}, y {a[1]:.2f}"); break
        # equipment: allowed where the run starts or ends at the item
        for iid, bx in BOXES.items():
            if any(inside(e, bx, rad + 0.35) for e in ends): continue
            if hits_item(a, b, rad, iid): bad.append(f"{r['id']}: passes through {iid}")
        # ducts
        for dc in D["ducts"]:
            for bx in duct_boxes(dc):
                if seg_hits_box(a, b, rad, bx): bad.append(f"{r['id']}: passes through duct {dc['id']} near x {a[0]:.2f}, y {a[1]:.2f}")
for i, r1 in enumerate(RUNS):
    for r2 in RUNS[i + 1:]:
        need = (r1.get("dia", 1.66) + r2.get("dia", 1.66)) / 24
        ends = [(r1["points"][0], r2), (r1["points"][-1], r2), (r2["points"][0], r1), (r2["points"][-1], r1)]
        for a, b in segs(r1["points"]):
            for c, d in segs(r2["points"]):
                p, q = seg_seg(a, b, c, d)
                if dist(p, q) >= need - TOL: continue
                # a tee: one run's end sits on the other run, at this spot
                if any(dist(e, p) < need + 0.05 and min(dist(e, x) for s in segs(o["points"]) for x in [seg_seg(e, e, *s)[1]]) < need for e, o in ends): continue
                bad.append(f"{r1['id']} and {r2['id']}: pipes {dist(p, q) * 12:.1f} in apart on centre near x {p[0]:.2f}, y {p[1]:.2f}, z {p[2]:.2f} (need {need * 12:.1f})")

# ---- ducts against ducts and equipment, above the ceiling only (below it there are only grilles and wall stacks)
DUCTS = [(dc, duct_boxes(dc)) for dc in D["ducts"]]
def joined(d1, d2, b2s):
    """d1 ends on d2, or starts from it: a branch, a collar into a plenum, or two pieces of one run."""
    if d1.get("system", "").startswith("plumbing") != d2.get("system", "").startswith("plumbing"):
        return False                                # the water heater's air ducts never tie into the house ductwork
    return any(inside(e, bx, 0.45) for e in (d1["points"][0], d1["points"][-1]) for bx in b2s)
for i, (d1, b1s) in enumerate(DUCTS):
    for d2, b2s in DUCTS[i + 1:]:
        if joined(d1, d2, b2s) or joined(d2, d1, b1s): continue
        hit = next(((x, y) for x in b1s for y in b2s if min(x[5], y[5]) > CEIL and overlap(x, y, 0.02)), None)
        if hit: bad.append(f"ducts {d1['id']} and {d2['id']} pass through each other near x {max(hit[0][0], hit[1][0]):.2f}, y {max(hit[0][1], hit[1][1]):.2f}")
    for iid, bx in BOXES.items():
        if any(inside(e, bx, 0.6) for e in (d1["points"][0], d1["points"][-1])): continue
        if any(overlap(x, bx, 0.02) for x in b1s): bad.append(f"duct {d1['id']} passes through {iid}")

# ---- equipment against the walls and against each other
for iid, bx in BOXES.items():
    for name, wb in WALLS:
        if wb[5] - wb[2] > 1.0 and overlap(bx, wb): bad.append(f"{iid} sticks into {name}"); break
ids = list(BOXES)
for i, a in enumerate(ids):
    for b in ids[i + 1:]:
        if overlap(BOXES[a], BOXES[b]): bad.append(f"{a} and {b} overlap")

for b in sorted(set(bad)):
    print(b)
print(f"{len(set(bad))} pipe, duct and equipment clashes")
sys.exit(1 if bad else 0)
