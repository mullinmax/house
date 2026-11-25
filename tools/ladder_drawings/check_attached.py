"""Find ladder parts that are not attached to anything.

Builds the CAD (ladder_cad.py), then follows every drawn fastener (bolt head, nut, lag or anchor head) into the model: a thin probe along
the fastener's axis, from its head inward to its paired nut (or 4 in for a lag or anchor with no nut). Every part the probe passes through is
joined by that fastener. A probe that runs out of the model into the slab (z = 0) or a wall (east wall a = 0, south wall b = 0) also joins
the ground. Then it reports:

  1. parts no fastener passes through (only touching, sitting or resting on something)
  2. groups of parts that are bolted to each other but not, through any chain, to the slab or a wall
  3. parts held by a single fastener (a pin: free to rotate about it)

Contact alone never counts as attached: a part that only bears on another one (a tube end against a plate) is listed in 1.

Usage:  python3 check_attached.py [--strict]      (env such as LADDER_TREAD_STRIPS passes through to the CAD)
--strict exits 1 when anything is listed in 1 or 2, so it can gate a commit or a CI job. ALLOW below names parts that are meant to be held
by contact or glue only.
"""
import sys, os, math, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)
strict = "--strict" in sys.argv
sys.argv = ["ladder_cad.py", os.environ.get("LADDER_CAD_OUT", "/tmp/ladder_check")]
import cadquery as cq
import ladder_cad as C

ALLOW = {}            # name -> reason, for parts deliberately held without a drawn fastener
PROBE_R = 0.12        # probe radius (a 3/8 in bolt is 0.1875)
LAG_LEN = 4.0         # how far an unpaired fastener reaches
PAIR_TOL = 0.2        # a nut counts as this bolt's pair when its centre is this close to the bolt line
MAX_THROUGH = 12.0    # longest through bolt looked for


def axis_of(s):
    """the fastener's axis: the normal of its end face (a cylinder's round cap or a hex prism's hexagon)"""
    for f in s.Faces():
        if f.geomType() == "PLANE" and len(f.Edges()) != 4:
            return f.normalAt()
    raise ValueError("no end face")


def centre(s):
    bb = s.BoundingBox()
    return cq.Vector((bb.xmin + bb.xmax) / 2, (bb.ymin + bb.ymax) / 2, (bb.zmin + bb.zmax) / 2)


parts = [(n, s) for g, n, s, col, m in C.PARTS]
pbb = [s.BoundingBox() for n, s in parts]


def hits(seg_solid):
    bb = seg_solid.BoundingBox()
    out = []
    for (n, s), b in zip(parts, pbb):
        if bb.xmax < b.xmin or bb.xmin > b.xmax or bb.ymax < b.ymin or bb.ymin > b.ymax or bb.zmax < b.zmin or bb.zmin > b.zmax:
            continue
        try:
            v = seg_solid.intersect(s).Volume()
        except Exception:
            v = 0
        if v > 1e-4:
            out.append(n)
    return out


fast = []
for s in C.FAST:
    try:
        n = axis_of(s)
    except ValueError:
        continue
    c = centre(s)
    fast.append(dict(c=c, n=n, h=max(abs((cq.Vector(v.toTuple()) - c).dot(n)) for v in s.Vertices())))

edges = []           # (set of part names, grounded, label)
for i, f in enumerate(fast):
    c, n, h = f["c"], f["n"], f["h"]
    inward = None
    for sg in (1, -1):                                    # which side of the head the parts are on
        d = n * sg
        if hits(cq.Solid.makeCylinder(PROBE_R, 0.2, c + d * (h + 0.02), d)):
            inward = d
            break
    if inward is None:
        edges.append((set(), False, f"fastener at {tuple(round(x, 2) for x in c.toTuple())} touches nothing"))
        continue
    # paired nut: the nearest other fastener on this line, inward
    best = None
    for j, g in enumerate(fast):
        if j == i:
            continue
        r = g["c"] - c
        t = r.dot(inward)
        if 0.2 < t < MAX_THROUGH and (r - inward * t).Length < PAIR_TOL and (best is None or t < best):
            best = t
    L = (best - h) if best else LAG_LEN
    start = c + inward * (h + 0.02)
    names = set(hits(cq.Solid.makeCylinder(PROBE_R, L, start, inward)))
    grounded = False
    if not best:                                         # a lag or an anchor: does it run into the slab or a wall?
        end = start + inward * L
        grounded = end.z < 0.01 or end.x > -0.01 or end.y < 0.01
    edges.append((names, grounded, None))

# union find over parts plus the ground
par = {n: n for n, s in parts}
par["GROUND"] = "GROUND"


def find(x):
    while par[x] != x:
        par[x] = par[par[x]]
        x = par[x]
    return x


def union(a, b):
    par[find(a)] = find(b)


count = {n: 0 for n, s in parts}
for names, grounded, _ in edges:
    names = sorted(names)
    for n in names:
        count[n] += 1
    for n in names[1:]:
        union(names[0], n)
    if grounded and names:
        union(names[0], "GROUND")

loose = [n for n, k in count.items() if k == 0 and n not in ALLOW]
groups = {}
for n, s in parts:
    if count[n] and find(n) != find("GROUND"):
        groups.setdefault(find(n), []).append(n)
pins = [n for n, k in count.items() if k == 1]
stray = [e[2] for e in edges if e[2]]

print(f"{len(parts)} parts, {len(fast)} fasteners")
print(f"\n1. Not attached by any fastener ({len(loose)}):")
for n in loose:
    print("   ", n)
print(f"\n2. Bolted together but not to the slab or a wall ({len(groups)} groups):")
for g in groups.values():
    print("    ", ", ".join(sorted(g)))
print(f"\n3. Held by one fastener only, free to pivot ({len(pins)}):")
for n in pins:
    print("   ", n)
if stray:
    print(f"\nFasteners that go into nothing ({len(stray)}):")
    for s in stray:
        print("   ", s)
json.dump(dict(loose=loose, floating=list(groups.values()), single=pins, stray=stray),
          open(os.environ.get("CHECK_OUT", "/tmp/ladder_check_attached.json"), "w"), indent=1)
sys.exit(1 if strict and (loose or groups) else 0)
