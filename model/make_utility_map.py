"""Measured site map of the buried geothermal and septic lines.
Reads config.toml + data/traced_geometry.json, writes renders/utility_map.pdf and .png.
Run:  python3 make_utility_map.py
Coordinates are feet from the OUTSIDE NW corner of the house slab, +x east, +y south.
"""
import json, os, tomllib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
C = tomllib.load(open(os.path.join(HERE, "config.toml"), "rb"))
G = json.load(open(os.path.join(HERE, "data", "traced_geometry.json")))
U = C["utilities"]
HW, HD = C["house"]["width_x"], C["house"]["depth_y"]

fig, ax = plt.subplots(figsize=(11, 15))
ax.set_aspect("equal")
ax.set_xlim(-150, 110); ax.set_ylim(280, -40)   # y grows south (down the page), north up


def rect(r, **kw):
    x0, y0, x1, y1 = r
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, **kw))


# grid
for x in range(-150, 111, 10):
    ax.axvline(x, color="#000", lw=0.6 if x % 50 == 0 else 0.2, alpha=0.35 if x % 50 == 0 else 0.15, zorder=0)
for y in range(-40, 281, 10):
    ax.axhline(y, color="#000", lw=0.6 if y % 50 == 0 else 0.2, alpha=0.35 if y % 50 == 0 else 0.15, zorder=0)

# structures
rect((0, 0, HW, HD), fc="#C9CFC0", ec="k", lw=1.5, zorder=3)
ax.text(HW / 2, HD / 2, "HOUSE SLAB\n43'-1\" x 52'-0\"", ha="center", va="center", fontsize=9, zorder=4)
if C["garage"]["enabled"]:
    rect(C["garage"]["rect"], fc="#DDD", ec="k", lw=1, zorder=3)
    g = C["garage"]["rect"]; ax.text((g[0] + g[2]) / 2, (g[1] + g[3]) / 2, "GARAGE", ha="center", va="center", fontsize=8, zorder=4)
if C["porch"]["enabled"]:
    rect(C["porch"]["rect"], fc="none", ec="k", lw=0.8, ls="--", zorder=3)
if C["greenhouse"]["enabled"]:
    rect(C["greenhouse"]["rect"], fc="none", ec="k", lw=0.8, ls="--", zorder=3)
    ax.text(HW / 2, 62, "greenhouse (future)", ha="center", fontsize=7, zorder=4)
for (x, y, lab) in [(0, 0, "NW"), (HW, 0, "NE"), (HW, HD, "SE"), (0, HD, "SW")]:
    ax.plot(x, y, "ks", ms=5, zorder=5)
    ax.annotate(f"{lab} slab corner", (x, y), xytext=(6 if x else -6, -6 if y == 0 else 12),
                textcoords="offset points", ha="left" if x else "right", fontsize=8, weight="bold", zorder=6)

GC, SC = U["geothermal_color"], U["septic_color"]


def label_pt(x, y, txt, color, dx=6, dy=0, ha="left"):
    ax.plot(x, y, "o", color=color, ms=4, zorder=7, mec="k", mew=0.5)
    ax.annotate(txt, (x, y), xytext=(dx, dy), textcoords="offset points", fontsize=7, color="k", ha=ha,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=color, lw=0.6, alpha=0.9), zorder=8)


def fmt(x, y):
    ew = f"{abs(x):.0f}' {'W' if x < 0 else 'E'}"
    return f"{ew}, {y:.0f}' S"


geo = G["geothermal"]
t = geo["trunk"]
ax.plot(*zip(*t), color=GC, lw=3, zorder=6, solid_capstyle="round")
label_pt(*t[0], f"trunk leaves slab\n{t[0][1]:.0f}' S of NW corner", GC, dx=-8, dy=-18, ha="right")
label_pt(*t[-1], f"trunk west end\n{fmt(*t[-1])}", GC, dx=-8, dy=-20, ha="right")
names = {"1_east_dug": "Loop 1 (dug, traced)", "2_dug": "Loop 2 (dug)",
         "3_dug_open_on_9_9": "Loop 3 (open trench 9/9)", "4_planned_stub_only": "Loop 4 (planned, stub only)",
         "5_planned_stub_only": "Loop 5 (planned, stub only)"}
rows = []
for k, (nm, pts) in enumerate(geo["branches"].items()):
    planned = "planned" in nm
    ax.plot(*zip(*pts), color=GC, lw=2, ls="--" if planned else "-", zorder=6)
    ax.plot(*pts[0], "o", color=GC, ms=4, zorder=7, mec="k", mew=0.5)
    ex, ey = pts[-1]
    ax.text(ex, ey + 6, str(k + 1), ha="center", va="top", fontsize=9, weight="bold", color=GC, zorder=8)
    rows.append(f"{k + 1}  {names.get(nm, nm)}: tie-in {fmt(*pts[0])}, ends {fmt(ex, ey)}")
ax.text(-147, 262, "Geothermal loops\n" + "\n".join(rows), fontsize=7, va="top", ha="left",
        bbox=dict(fc="white", ec=GC, lw=0.8), zorder=9)
# tie-in x positions along the trunk
xs = ", ".join(f"{abs(p[0][0]):.0f}'" for p in geo["branches"].values())
ax.text(-60, 5, f"Loop tie-ins on trunk, feet W of slab:\n{xs}", fontsize=7.5, ha="center",
        bbox=dict(fc="white", ec=GC, lw=0.8), zorder=8)

sep = G["septic"]
srows = []
for k, (nm, pts) in enumerate(sep["laterals"].items()):
    ax.plot(*zip(*pts), color=SC, lw=2.5, zorder=6)
    lab = "ABC"[k]
    for (px, py) in (pts[0], pts[-1]):
        ax.plot(px, py, "o", color=SC, ms=4, zorder=7, mec="k", mew=0.5)
    ax.text(pts[0][0] - 2, pts[0][1] - 3, lab, ha="right", fontsize=9, weight="bold", color=SC, zorder=8)
    ax.text(pts[-1][0] + 2, pts[-1][1], lab, ha="left", va="center", fontsize=9, weight="bold", color=SC, zorder=8)
    srows.append(f"{lab}  {nm.replace('_', ' ')}: north end {fmt(*pts[0])}, east end {fmt(*pts[-1])}")
ax.text(-147, 70, "Septic laterals\n" + "\n".join(srows) + "\nTank location not traced yet", fontsize=7, va="top", ha="left",
        bbox=dict(fc="white", ec=SC, lw=0.8), zorder=9)
h = sep["header_pvc"]
ax.plot(*zip(*h), color=SC, lw=1.5, ls=":", zorder=6)
label_pt(*h[0], "PVC header (visible in photo)", SC, dx=-8, dy=10, ha="right")

ax.set_xlabel("feet east (+) / west (-) of the NW slab corner")
ax.set_ylabel("feet south of the NW slab corner")
ax.annotate("N", xy=(-130, -35), xytext=(-130, -15), ha="center", fontsize=14, weight="bold",
            arrowprops=dict(arrowstyle="-|>", lw=2, color="k"))
ax.set_title("1671 SR 343: buried geothermal and septic lines, traced from drone photos (accuracy about 2 ft)\n"
             "Geothermal loops parallel to loop 1, equal total length from the slab (loops 2 to 5 derived).\n"
             f"Grid 10 ft. Plan north = true north. Depths not measured: geothermal shown at {U['geothermal_depth']} ft, "
             f"septic at {U['septic_depth']} ft (both assumed).", fontsize=11)
ax.plot([], [], color=GC, lw=2, label="geothermal (dug)")
ax.plot([], [], color=GC, lw=2, ls="--", label="geothermal (planned)")
ax.plot([], [], color=SC, lw=2.5, label="septic laterals")
ax.legend(loc="upper right", fontsize=8)
out = os.path.join(HERE, "renders")
os.makedirs(out, exist_ok=True)
fig.tight_layout()
fig.savefig(os.path.join(out, "utility_map.pdf"))
fig.savefig(os.path.join(out, "utility_map.png"), dpi=110)
print("wrote", out)
