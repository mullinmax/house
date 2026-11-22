"""Flat outlines of the corner ladder's steel plate stringers as DXF (inches), for a laser cutting quote.

Same formulas as model/ladder_options.py flight(carriage=True). Each plate is rotated so its slope runs along X.
QUOTE ONLY: no tread clip holes, mounting tabs or connection details; an engineer has to size the plates first.
Run: python3 tools/ladder_drawings/export_stringers.py OUTDIR
"""
import math, os, sys, tomllib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
C = tomllib.load(open(os.path.join(HERE, "..", "..", "model", "config.toml"), "rb"))
L = C["loft"]
OUT = sys.argv[1] if len(sys.argv) > 1 else "."
os.makedirs(OUT, exist_ok=True)
FL, NR = L["floor_height"], L["ladder_risers"]
RI, GO, TD = FL / NR, L["ladder_going_in"] / 12, L["ladder_tread_in"] / 12
N_LO = int(L.get("ladder_lower_risers", 5))
SL = RI / GO
ANG = math.atan(SL)
assert L.get("ladder_wall_stringer_under") and L.get("ladder_stringer_in", 1.8) < 1, "config is not the steel plate design"


def outline(nr, kind):
    """plate outline in the flight's own (u, z) plane, feet, z from the flight's base"""
    u_lo, u_end = -0.04, (nr - 1) * GO + (TD - GO)
    u_hi = u_end - 0.01
    zn = lambda u: RI + u * SL
    if kind == "open":
        zt = lambda u: min(zn(u) + 0.1, nr * RI - 0.01)
        zb = lambda u: max(0.004, zn(u) - TD * SL - 0.22)
    else:
        zt = lambda u: max(0.35, min(zn(u) - TD * SL - 0.12, nr * RI - 0.13))
        zb = lambda u: max(0.004, zn(u) - TD * SL - 0.12 - 1.2)
    n = 4000
    us = [u_lo + (u_hi - u_lo) * i / n for i in range(n + 1)]
    pts = [(u, zt(u)) for u in us] + [(u, zb(u)) for u in reversed(us)]
    out = []
    for p in pts:                                    # drop collinear and repeated points
        if out and math.dist(p, out[-1]) < 1e-9:
            continue
        while len(out) >= 2 and abs((out[-1][0] - out[-2][0]) * (p[1] - out[-2][1]) - (out[-1][1] - out[-2][1]) * (p[0] - out[-2][0])) < 1e-7:
            out.pop()
        out.append(p)
    if math.dist(out[0], out[-1]) < 1e-9:
        out.pop()
    c, s = math.cos(-ANG), math.sin(-ANG)             # lay the slope along X, inches
    rot = [((u * c - z * s) * 12, (u * s + z * c) * 12) for u, z in out]
    x0, y0 = min(p[0] for p in rot), min(p[1] for p in rot)
    return [(round(x - x0, 4), round(y - y0, 4)) for x, y in rot]


def dxf(path, pts):
    w = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "1", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        w += ["0", "LINE", "8", "0", "10", f"{a[0]}", "20", f"{a[1]}", "30", "0", "11", f"{b[0]}", "21", f"{b[1]}", "31", "0"]
    w += ["0", "ENDSEC", "0", "EOF"]
    open(path, "w").write("\n".join(w) + "\n")


parts = [("lower_open_side", N_LO, "open"), ("lower_wall_side", N_LO, "wall"), ("upper_open_side", NR - N_LO, "open"), ("upper_wall_side", NR - N_LO, "wall")]
fig, axs = plt.subplots(len(parts), 1, figsize=(11, 8.5))
for ax, (name, nr, kind) in zip(axs, parts):
    pts = outline(nr, kind)
    dxf(os.path.join(OUT, f"stringer_{name}.dxf"), pts)
    w, h = max(p[0] for p in pts), max(p[1] for p in pts)
    area = abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))) / 2
    lb = area * 0.375 * 0.2836
    print(f"{name}: {w:.2f} x {h:.2f} in, {len(pts)} corners, {area:.0f} sq in, about {lb:.0f} lb")
    ax.fill([p[0] for p in pts], [p[1] for p in pts], fc="#3a3a3a", ec="k", lw=0.8)
    ax.set_aspect("equal"); ax.set_xlim(-2, 92); ax.set_ylim(-2, 14); ax.axis("off")
    ax.set_title(f"stringer_{name}.dxf   {w:.2f} x {h:.2f} in, 3/8 in plate, about {lb:.0f} lb", fontsize=9, loc="left")
fig.suptitle("Loft ladder plate stringers, flat outlines for a cutting quote (not for fabrication)", fontsize=11)
fig.savefig(os.path.join(OUT, "stringer_plates_preview.png"), dpi=150)
