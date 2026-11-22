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
assert L.get("ladder_stringer_in", 1.8) < 1 and not L.get("ladder_wall_stringer_under"), "config is not the steel side plate design"
TT = 0.12                                   # tread thickness, ft
CLIP = dict(leg=2.0, t=0.1875, len=7.0, u0=0.75, bolt_dz=1.125, bolts=(1.0, 6.0))    # inches, as draw_ladder.py
D_BOLT, D_END = 0.406, 0.531                # holes for 3/8 in clip bolts and 1/2 in foot and head bolts


def plate(nr):
    """outline and holes in the flight's own (u, z) plane (feet, z from the flight's base), then laid flat along X in inches"""
    u_lo, u_end = -0.04, (nr - 1) * GO + (TD - GO)
    u_hi = u_end - 0.01
    zn = lambda u: RI + u * SL
    zt = lambda u: min(zn(u) + 0.1, nr * RI - 0.01)
    zb = lambda u: max(0.004, zn(u) - TD * SL - 0.22)
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
    holes = []
    for k in range(1, nr):                           # two clip bolts under each tread
        for ub in CLIP["bolts"]:
            holes.append(((k - 1) * GO + (CLIP["u0"] + ub) / 12, k * RI - TT - CLIP["bolt_dz"] / 12, D_BOLT))
    holes += [(1.0 / 12, 1.5 / 12, D_END), (4.0 / 12, 1.5 / 12, D_END)]                     # foot angle
    holes += [(u_hi - 1.25 / 12, nr * RI - 3.0 / 12, D_END), (u_hi - 1.25 / 12, nr * RI - 8.0 / 12, D_END)]   # head angle
    for hu, hz, d in holes:                          # every hole at least 2 diameters of steel from the edge, measured plumb
        assert zb(hu) + 2 * d / 12 / math.cos(ANG) <= hz <= zt(hu) - 2 * d / 12 / math.cos(ANG) or hz <= 0.2, (hu, hz)
    c, s = math.cos(-ANG), math.sin(-ANG)
    rot = lambda u, z: ((u * c - z * s) * 12, (u * s + z * c) * 12)
    r = [rot(u, z) for u, z in out]
    x0, y0 = min(p[0] for p in r), min(p[1] for p in r)
    return [(round(x - x0, 4), round(y - y0, 4)) for x, y in r], [(round(rot(u, z)[0] - x0, 4), round(rot(u, z)[1] - y0, 4), d) for u, z, d in holes]


def dxf(path, pts, holes=(), bends=()):
    w = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "1", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        w += ["0", "LINE", "8", "0", "10", f"{a[0]}", "20", f"{a[1]}", "30", "0", "11", f"{b[0]}", "21", f"{b[1]}", "31", "0"]
    for x, y, d in holes:
        w += ["0", "CIRCLE", "8", "0", "10", f"{x}", "20", f"{y}", "30", "0", "40", f"{d / 2}"]
    for a, b in bends:
        w += ["0", "LINE", "8", "BEND", "62", "1", "10", f"{a[0]}", "20", f"{a[1]}", "30", "0", "11", f"{b[0]}", "21", f"{b[1]}", "31", "0"]
    w += ["0", "ENDSEC", "0", "EOF"]
    open(path, "w").write("\n".join(w) + "\n")


for f_ in os.listdir(OUT):
    if f_.startswith("stringer_") and f_.endswith(".dxf"):
        os.remove(os.path.join(OUT, f_))
parts = [("lower_flight", N_LO), ("upper_flight", NR - N_LO)]
fig, axs = plt.subplots(3, 1, figsize=(11, 8.5), gridspec_kw=dict(height_ratios=[1, 1, 0.8]))
for ax, (name, nr) in zip(axs, parts):
    pts, holes = plate(nr)
    dxf(os.path.join(OUT, f"stringer_{name}_qty2.dxf"), pts, holes)
    w, h = max(p[0] for p in pts), max(p[1] for p in pts)
    area = abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))) / 2
    lb = area * 0.375 * 0.2836
    print(f"{name}: {w:.2f} x {h:.2f} in, {len(pts)} corners, {len(holes)} holes, about {lb:.0f} lb each")
    ax.fill([p[0] for p in pts], [p[1] for p in pts], fc="#3a3a3a", ec="k", lw=0.8)
    for x, y, d in holes:
        ax.add_patch(plt.Circle((x, y), d / 2 * 1.6, fc="white", ec="k", lw=0.4))
    ax.set_aspect("equal"); ax.set_xlim(-2, 92); ax.set_ylim(-2, 12); ax.axis("off")
    ax.set_title(f"stringer_{name}_qty2.dxf   {w:.2f} x {h:.2f} in, 3/8 in plate, quantity 2, about {lb:.0f} lb each, {len(holes)} holes (drawn oversize here)", fontsize=8.5, loc="left")
# tread clip, flat pattern: 2 x 2 x 3/16 angle, 7 in long, one 90 degree bend (flat width is approximate, the cutter's bend table sets it)
FW = 2 * CLIP["leg"] - 0.33
bl = FW / 2
ch = [(1.0, bl - (CLIP["bolt_dz"] - 0.165), D_BOLT), (6.0, bl - (CLIP["bolt_dz"] - 0.165), D_BOLT), (1.5, bl + 1.0, 0.281), (5.5, bl + 1.0, 0.281)]
cp = [(0, 0), (CLIP["len"], 0), (CLIP["len"], round(FW, 3)), (0, round(FW, 3))]
n_clips = 2 * (NR - 2)
dxf(os.path.join(OUT, f"tread_clip_qty{n_clips}.dxf"), cp, ch, bends=[((0, bl), (CLIP["len"], bl))])
ax = axs[2]
ax.fill([p[0] for p in cp], [p[1] for p in cp], fc="#b5b5b5", ec="k", lw=0.8)
ax.plot([0, CLIP["len"]], [bl, bl], c="r", lw=0.8, ls="--")
for x, y, d in ch:
    ax.add_patch(plt.Circle((x, y), d / 2, fc="white", ec="k", lw=0.4))
ax.set_aspect("equal"); ax.set_xlim(-2, 40); ax.set_ylim(-0.5, 4.5); ax.axis("off")
ax.set_title(f"tread_clip_qty{n_clips}.dxf   {CLIP['len']:.0f} x {FW:.2f} in flat, 3/16 in steel, one 90 degree bend on the red line, quantity {n_clips}", fontsize=8.5, loc="left")
print("clips", n_clips, "flat", FW)
fig.suptitle("Loft ladder: plate stringers and tread clips, flat patterns for a cutting quote (not for fabrication)", fontsize=11)
fig.savefig(os.path.join(OUT, "stringer_plates_preview.png"), dpi=150)
