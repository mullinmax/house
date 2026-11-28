"""Find bare wall at the floor: walks every wall face (interior partitions, the exterior walls' inside faces and the
clerestory wall) 1/2 in off the face and 2 in up, and lists runs over 2 in where nothing touches the wall there
(no baseboard, jamb, casing, cabinet, fixture or furniture). Reads site/models/house.json; run make_house.py first.
  python3 tools/baseboard_gaps.py [min_len_in]"""
import json, sys, tomllib, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
C = tomllib.loads((ROOT / "model/config.toml").read_text())
H = json.loads((ROOT / "site/models/house.json").read_text())
HW, HD, T = C["house"]["width_x"], C["house"]["depth_y"], C["house"]["ext_wall_thickness"]
MIN = (float(sys.argv[1]) if len(sys.argv) > 1 else 2.0) / 12
Z, OFF, STEP = 2 / 12, 0.5 / 12, 0.5 / 12

walls, cover = [], []
def bbox(p):
    if p[0] == "b":
        return p[2:8]
    if p[0] in ("x", "p", "c") and isinstance(p[2], list) and len(p[2]) >= 9 and all(isinstance(v, (int, float)) for v in p[2]):
        xs, ys, zs = p[2][0::3], p[2][1::3], p[2][2::3]
        return [min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)]
    return None
def walk(parts, rid, moving=False):
    for p in parts:
        if isinstance(p, dict):
            walk(p.get("parts", []), rid, moving); continue
        b = bbox(p)
        if not b:
            continue
        if p[1] == "Drywall" and b[4] <= 0.01 and b[5] > 1:
            walls.append(b[:4])
        elif b[4] < Z < b[5] and (b[1] - b[0]) * (b[3] - b[2]) < 60 and not moving:
            cover.append((b, rid))
for r in H["records"]:
    walk(r.get("parts", []), r["id"])
    for o in r.get("ops", []):
        walk(o.get("parts", []), r["id"], o.get("type") == "swing")   # a swung leaf is not trim
# the exterior walls as solid outside the inside faces, and the clerestory wall with its drywall
YC = next((t[k] for t in C.values() if isinstance(t, dict) for k in t if k == "clerestory_wall_y"), None)
if YC is not None:
    xs = [T] + [v for p_ in C["clerestory"]["passages"] for v in p_[:2]] + [HW - T]
    open_ec = C.get("entry_closet", {}).get("style") == "open"   # the cubby runs on east: the stub between it and the closet opening is gone
    walls += [[xs[i], xs[i + 1], YC, YC + T, "cl"] for i in range(0, len(xs) - 1, 2) if not (open_ec and xs[i + 1] - xs[i] < 1)]    # the clerestory wall between its passages
    UNTRIM = C["clerestory"].get("untrimmed", [])
    UNTRIM_X = [v for p_ in C["clerestory"]["passages"] if any(abs(p_[0] - u) < 0.01 for u in UNTRIM) for v in p_[:2]]
# the tiled wet room has no baseboard on purpose
WET = [(i["x0"], i["x1"], i["y0"], i["y1"]) for i in C.get("furnishings", {}).get("items", []) if i.get("type") == "wetroom"]
walls += [[-9, T, -9, HD + 9], [HW - T, HW + 9, -9, HD + 9], [-9, HW + 9, -9, T], [-9, HW + 9, HD - T, HD + 9]]
inside = lambda x, y: T < x < HW - T and T < y < HD - T and not any(w[0] - 0.3 < x < w[1] + 0.3 and w[2] - 0.3 < y < w[3] + 0.3 for w in WET)
def solid(x, y):
    return any(w[0] - 0.003 <= x <= w[1] + 0.003 and w[2] - 0.003 <= y <= w[3] + 0.003 for w in walls)
def covered(x, y):
    for b, rid in cover:
        if b[0] - 0.01 <= x <= b[1] + 0.01 and b[2] - 0.01 <= y <= b[3] + 0.01:
            return rid
    return None

gaps = []
for w in walls:
    x0, x1, y0, y1 = w[:4]
    for (ax, c, a0, a1) in (("x", y0 - OFF, x0, x1), ("x", y1 + OFF, x0, x1), ("y", x0 - OFF, y0, y1), ("y", x1 + OFF, y0, y1)):
        if len(w) > 4 and ax == "y" and not any(abs(c - u) < 0.1 for u in UNTRIM_X):
            continue                    # the return in a cased opening: its casing stands on the floor, no baseboard
        n = int((min(a1, HW + 1) - max(a0, -1)) / STEP)
        run = []
        for k in range(n + 1):
            a = max(a0, -1) + k * STEP
            x, y = (a, c) if ax == "x" else (c, a)
            bare = inside(x, y) and not solid(x, y) and not covered(x, y)
            if bare:
                run.append(a)
            if (not bare or k == n) and run:
                if run[-1] - run[0] >= MIN:
                    gaps.append((ax, c, run[0], run[-1]))
                run = []
seen = set()
for ax, c, a, b in sorted(gaps, key=lambda g: (g[0], round(g[1], 2), g[2])):
    key = (ax, round(c, 2), round(a, 1))
    if key in seen:
        continue
    seen.add(key)
    where = f"y {c:.2f}, x {a:.2f} to {b:.2f}" if ax == "x" else f"x {c:.2f}, y {a:.2f} to {b:.2f}"
    print(f"{(b - a) * 12:6.1f} in bare  wall face at {where}")
print(f"{len(seen)} bare runs over {MIN * 12:g} in")
