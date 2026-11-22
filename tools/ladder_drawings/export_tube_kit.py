"""Tube stringer ladder kit: flat patterns (DXF, inches) for the laser cut brackets, plus an assembly sheet.

Geometry matches model/ladder_options.py flight(carriage="tube"): stock rectangular tube stringers under the treads,
top face on the line through the tread backs; 1/4 in bent brackets bolted to the tubes' inner faces carry the treads.
PRELIMINARY: sizes and connections need an engineer's check before anything is cut.
Run: python3 tools/ladder_drawings/export_tube_kit.py OUTDIR
"""
import math, os, sys, tomllib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle

HERE = os.path.dirname(os.path.abspath(__file__))
L = tomllib.load(open(os.path.join(HERE, "..", "..", "model", "config.toml"), "rb"))["loft"]
OUT = sys.argv[1] if len(sys.argv) > 1 else "."
os.makedirs(OUT, exist_ok=True)
assert L.get("ladder_stringer") == "tube"
NR, N_LO = L["ladder_risers"], int(L.get("ladder_lower_risers", 5))
RI, GO, TD, TT = L["floor_height"] * 12 / NR, L["ladder_going_in"], L["ladder_tread_in"], 1.44
TW, TDp = L.get("ladder_tube_in", [2.0, 3.0])
WN = L["ladder_width_in"]
SL = RI / GO
ANG = math.atan(SL)
DX, DZ = math.cos(ANG), math.sin(ANG)             # up the slope
NX, NZ = math.sin(ANG), -math.cos(ANG)            # square to the slope, down and back
PITCH = math.hypot(GO, RI)
PL = TDp / math.cos(ANG)                          # tube depth measured plumb
T_BR, LAP, BOLT_N = 0.25, 2.25, 1.25              # bracket thickness, web lap down the tube's side, bolt line below the tube's top face
BOLT_S = (4.0, 8.5)                               # bolts along the tube, from the web's lower front corner
FL_W, FL_FLAT = 2.5, 2.375                        # seat width, and its flat length (the cutter's bend table sets the exact value)
D38, D14 = 0.406, 0.281                           # holes for 3/8 in bolts or lags, and for 1/4 in tread screws
WEB_U0, SEAT_U0 = 3.75, 1.0                       # web starts 1/4 in behind the tread below; seat starts 1 in behind the nosing


def tread_bracket(floor=None):
    """flat pattern, origin at the tread's nosing in u, bend line (tread underside) at y = 0, web below, seat above.
    floor: the floor's y for the first tread of the lower flight, whose web is trimmed level 1/8 in above it"""
    A, B = (WEB_U0, 0.0), (TD, 0.0)
    C = (WEB_U0, -(TD - WEB_U0) * SL)             # on the tube's top line, which passes through B
    B2, C2 = (B[0] + NX * LAP, B[1] + NZ * LAP), (C[0] + NX * LAP, C[1] + NZ * LAP)
    web = [A, C, C2, B2, B]
    if floor is not None:
        yc = floor + 0.125
        cl = []
        for p, q in zip(web, web[1:] + web[:1]):  # clip to y >= yc
            if p[1] >= yc:
                cl.append(p)
            if (p[1] - yc) * (q[1] - yc) < 0:
                t = (yc - p[1]) / (q[1] - p[1])
                cl.append((p[0] + t * (q[0] - p[0]), yc))
        web = cl
    out = [(SEAT_U0, FL_FLAT), (SEAT_U0, 0), (WEB_U0 - 0.25, 0), (WEB_U0 - 0.25, 0.3), (WEB_U0, 0.3)] + web + [(TD, FL_FLAT)]
    holes = [(C[0] + DX * s + NX * BOLT_N, C[1] + DZ * s + NZ * BOLT_N, D38) for s in BOLT_S]
    holes += [(2.0, FL_FLAT - 1.25, D14), (7.5, FL_FLAT - 1.25, D14)]
    return out, holes, [((WEB_U0, 0), (TD, 0))]


def hanger():
    """head hanger for the upper flight: origin at the balcony's south face (x = 0) and top (y = 0); web to the left, rim flange to the right"""

    zl = lambda u: 3.5 * SL - TD * SL - TT + u * SL          # nosing line is 3.5 * SL above the balcony top at the rim face
    lapv = LAP / math.cos(ANG)
    q1, q2 = (0.0, zl(0) - lapv), (-3.2, zl(-3.2) - lapv)
    q3 = (q2[0] - NX * LAP, q2[1] - NZ * LAP)
    q4 = (-3.0, zl(-3.0))
    out = [(-3.0, -0.75), q4, q3, q2, q1, (0, -5.8), (-0.25, -5.8), (-0.25, -5.5), (FL_FLAT, -5.5), (FL_FLAT, -0.75)]
    holes = [(q3[0] + DX * s + NX * BOLT_N, q3[1] + DZ * s + NZ * BOLT_N, D38) for s in (1.25, 5.0)]
    holes += [(FL_FLAT - 1.25, -1.75, D38), (FL_FLAT - 1.25, -4.25, D38)]
    return out, holes, [((0, -5.5), (0, -0.75))]


def end_angle():
    """3 x 3 in angle, 4 in long: tube foot to the slab, tube head or foot to a landing post"""
    w = 6.0 - 0.25
    return [(0, 0), (4, 0), (4, w), (0, w)], [(1, 1.25, D38), (3, 1.25, D38), (1, w - 1.25, D38), (3, w - 1.25, D38)], [((0, w / 2), (4, w / 2))]


def wall_tab():
    """T shaped tab on the wall side of a wall side tube, under the tread bracket's two bolts, with an ear below the tube for a lag"""
    s0, s1 = BOLT_S
    out = [(s0 - 1, 0.25), (s1 + 1, 0.25), (s1 + 1, 2.25), ((s0 + s1) / 2 + 1.25, 2.25), ((s0 + s1) / 2 + 1.25, 5.5), ((s0 + s1) / 2 - 1.25, 5.5), ((s0 + s1) / 2 - 1.25, 2.25), (s0 - 1, 2.25)]
    return [(x - (s0 - 1), 5.5 - y) for x, y in out], [(s0 - (s0 - 1), 5.5 - BOLT_N, D38), (s1 - (s0 - 1), 5.5 - BOLT_N, D38), ((s0 + s1) / 2 - (s0 - 1), 5.5 - (TDp + 1.25), 0.44)], []


def drill_jig():
    """strip clamped to the tube's side, top edge flush with the tube's top face: bolt holes for two brackets plus the first hole of the next"""
    xs = [1.0, 1.0 + BOLT_S[1] - BOLT_S[0], 1.0 + PITCH, 1.0 + PITCH + BOLT_S[1] - BOLT_S[0], 1.0 + 2 * PITCH]
    return [(0, 0), (xs[-1] + 1, 0), (xs[-1] + 1, 2.25), (0, 2.25)], [(x, 2.25 - BOLT_N, D38) for x in xs], []


def norm(part):
    out, holes, bends = part
    x0, y0 = min(p[0] for p in out), min(p[1] for p in out)
    f = lambda p: (round(p[0] - x0, 4), round(p[1] - y0, 4))
    return [f(p) for p in out], [f(h) + (h[2],) for h in holes], [(f(a), f(b)) for a, b in bends]


def dxf(path, part):
    pts, holes, bends = part
    w = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "1", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        w += ["0", "LINE", "8", "0", "10", f"{a[0]}", "20", f"{a[1]}", "30", "0", "11", f"{b[0]}", "21", f"{b[1]}", "31", "0"]
    for x, y, d in holes:
        w += ["0", "CIRCLE", "8", "0", "10", f"{x}", "20", f"{y}", "30", "0", "40", f"{d / 2}"]
    for a, b in bends:
        w += ["0", "LINE", "8", "BEND", "62", "1", "10", f"{a[0]}", "20", f"{a[1]}", "30", "0", "11", f"{b[0]}", "21", f"{b[1]}", "31", "0"]
    w += ["0", "ENDSEC", "0", "EOF"]
    open(path, "w").write("\n".join(w) + "\n")


n_tr = NR - 2                                   # treads (the landing and the balcony are risers N_LO and NR)
PARTS = [("tread_bracket", norm(tread_bracket()), 2 * n_tr - 2, '1/4" steel', "one 90° bend: half bent up, half bent down (left and right hand)"),
         ("tread_bracket_floor", norm(tread_bracket(floor=-(RI - TT))), 2, '1/4" steel', "first tread of the lower flight, trimmed at the floor: one bent each way"),
         ("head_hanger", norm(hanger()), 2, '1/4" steel', "upper flight tubes to the balcony rim: one bent each way"),
         ("end_angle", norm(end_angle()), 6, '1/4" steel', "one 90° bend: 2 at the slab, 3 at the landing posts, 1 spare"),
         ("wall_tab", norm(wall_tab()), 5, '1/4" steel', "flat: lags the wall side tubes to blocking"),
         ("drill_jig", norm(drill_jig()), 1, '1/8" steel', "flat: clamps to the tube to mark the bolt holes")]
for f_ in os.listdir(OUT):
    if f_.endswith(".dxf"):
        os.remove(os.path.join(OUT, f_))
for name, part, qty, mat, note in PARTS:
    dxf(os.path.join(OUT, f"{name}_qty{qty}.dxf"), part)
    w, h = max(p[0] for p in part[0]), max(p[1] for p in part[0])
    print(f"{name}: {w:.2f} x {h:.2f} in, qty {qty}, {len(part[1])} holes")


# tube cut list: s along the tube's axis, from the four corners of each tube's side view
def tube_len(nr, foot):
    u_end = (nr - 1) * GO + (TD - GO)
    zl = lambda u: RI + u * SL - TD * SL - TT
    if foot == "floor":
        u0 = -zl(0) / SL
        pts = [(u0, 0), (u0 + PL / SL, 0), (u_end, zl(u_end)), (u_end, zl(u_end) - PL)]
    else:
        pts = [(0, zl(0)), (0, zl(0) - PL), (u_end, zl(u_end)), (u_end, zl(u_end) - PL)]
    s = [u * DX + z * DZ for u, z in pts]
    return max(s) - min(s)


LEN_LO, LEN_UP = tube_len(N_LO, "floor"), tube_len(NR - N_LO, "plumb")
print(f"tubes: lower {LEN_LO:.1f} in x2, upper {LEN_UP:.1f} in x2, angle {math.degrees(ANG):.1f}, pitch {PITCH:.3f}")

# ---------------------------------------------------------------- assembly sheet
fig = plt.figure(figsize=(17, 11))
fig.text(0.03, 0.955, "LOFT SHIPS LADDER: TUBE STRINGER KIT", fontsize=17, fontweight="bold")
fig.text(0.03, 0.932, "Stock rectangular steel tube under the treads, laser cut bolt on brackets. PRELIMINARY, NOT FOR CONSTRUCTION: an engineer must check sizes and connections.", fontsize=9, color="#b3261e")
ax = fig.add_axes([0.02, 0.05, 0.40, 0.86]); ax.set_aspect("equal"); ax.axis("off")
# side view of three treads on the tube
zl = lambda u: -TD * SL - TT + u * SL
u_a, u_b = -4.0, 21.0
ax.add_patch(Polygon([(u_a, zl(u_a)), (u_b, zl(u_b)), (u_b, zl(u_b) - PL), (u_a, zl(u_a) - PL)], fc="#9aa0a6", ec="k", lw=1))
for k in range(0, 3):
    ou, oz = k * GO, k * RI
    ax.add_patch(Polygon([(ou, oz - TT), (ou + TD, oz - TT), (ou + TD, oz), (ou, oz)], fc="#d9be8c", ec="k", lw=1, zorder=4))
    A, B = (ou + WEB_U0, oz - TT), (ou + TD, oz - TT)
    C = (A[0], A[1] - (TD - WEB_U0) * SL)
    B2, C2 = (B[0] + NX * LAP, B[1] + NZ * LAP), (C[0] + NX * LAP, C[1] + NZ * LAP)
    ax.add_patch(Polygon([A, C, C2, B2, B], fc="#3a3a3a", ec="k", lw=0.8, alpha=0.9, zorder=3))
    ax.add_patch(Polygon([(ou + SEAT_U0, oz - TT - T_BR), (ou + TD, oz - TT - T_BR), (ou + TD, oz - TT), (ou + SEAT_U0, oz - TT)], fc="#3a3a3a", ec="k", lw=0.6, zorder=5))
    for s in BOLT_S:
        ax.add_patch(Circle((C[0] + DX * s + NX * BOLT_N, C[1] + DZ * s + NZ * BOLT_N), 0.3, fc="white", ec="k", lw=0.8, zorder=6))
ax.plot([-3, 16], [-3 * SL, 16 * SL], c="#b3261e", lw=0.8, ls="--")
ax.annotate(f"nosing line, {math.degrees(ANG):.1f}°", (13.2, 13.2 * SL), (15, 20), fontsize=8, color="#b3261e", arrowprops=dict(arrowstyle="-", color="#b3261e", lw=0.5))
ax.annotate(f'tread 1 7/16" x {TD}" oak\nscrewed up through the seat', (2 * GO + 6, 2 * RI - 0.3), (16, 22), fontsize=8, arrowprops=dict(arrowstyle="-", lw=0.5))
ax.annotate('tread bracket, 1/4" steel:\nweb bolted to the tube\'s inner\nface, bent seat under the tread', (WEB_U0 + 1.2, -6.5), (-9, -1), fontsize=8, arrowprops=dict(arrowstyle="-", lw=0.5))
ax.annotate(f'two 3/8" through bolts\nper bracket, {BOLT_S[1] - BOLT_S[0]:.1f}" apart,\n{BOLT_N}" below the tube\'s top face', (GO + WEB_U0 + DX * 4 + NX * BOLT_N + 0.3, RI - TT - (TD - WEB_U0) * SL + DZ * 4 + NZ * BOLT_N), (14, -3), fontsize=8, arrowprops=dict(arrowstyle="-", lw=0.5))
ax.annotate(f'{TW:.0f}" x {TDp:.0f}" x 3/16" tube,\ntop face touching\nevery tread\'s back edge', (17, zl(17) - 2.5), (18, 3), fontsize=8, arrowprops=dict(arrowstyle="-", lw=0.5))
ax.annotate(f'web stays behind the back\nedge of the tread below', (GO + WEB_U0, RI - TT - 5), (-9, 9), fontsize=8, arrowprops=dict(arrowstyle="-", lw=0.5))
ax.annotate("", (GO, RI + 1.2), (2 * GO, 2 * RI + 1.2), arrowprops=dict(arrowstyle="<->", lw=0.6))
ax.text(GO - 3.6, 1.5 * RI + 1.6, f'{PITCH:.2f}" between\nbrackets along the tube', fontsize=8)
ax.set_xlim(-10, 27); ax.set_ylim(-24, 26)
ax.set_title("SIDE VIEW, THREE TREADS (seen from between the tubes)", fontsize=10, fontweight="bold", loc="left")
# flat patterns
ax2 = fig.add_axes([0.43, 0.47, 0.55, 0.42]); ax2.set_aspect("equal"); ax2.axis("off")
x = 0.0
for name, part, qty, mat, note in PARTS:
    pts, holes, bends = part
    w, h = max(p[0] for p in pts), max(p[1] for p in pts)
    ax2.add_patch(Polygon([(x + a, b) for a, b in pts], fc="#c9c9c9", ec="k", lw=0.8))
    for hx, hy, d in holes:
        ax2.add_patch(Circle((x + hx, hy), d / 2, fc="white", ec="k", lw=0.5))
    for a, b in bends:
        ax2.plot([x + a[0], x + b[0]], [a[1], b[1]], c="r", lw=0.8, ls="--")
    ax2.text(x, -1.2, f"{name}\nx{qty}  {w:.1f} x {h:.1f}\"", fontsize=7.2, va="top")
    x += w + 2.0
ax2.set_xlim(-1, x); ax2.set_ylim(-5, 22)
ax2.set_title("LASER CUT PARTS, FLAT (red dashes = bend line; one DXF file each)", fontsize=10, fontweight="bold", loc="left")
rows = ["CUT LIST AND HARDWARE",
        f"Tube: {TW:.0f} x {TDp:.0f} x 3/16 in rectangular steel tube (A500), about {LEN_LO + LEN_UP:.0f} in per side, 2 sides. Buy two 12 ft or one 24 ft length.",
        f"   Lower flight, 2 pieces about {LEN_LO:.1f} in overall: level cut at the floor ({90 - math.degrees(ANG):.1f}° off square), plumb cut at the landing posts ({math.degrees(ANG):.1f}° off square).",
        f"   Upper flight, 2 pieces about {LEN_UP:.1f} in overall: plumb cuts both ends ({math.degrees(ANG):.1f}° off square). Lengths are from the model: measure the real rise first.",
        f"Treads: {n_tr} white oak, 1 7/16 x {TD} x {WN - 0.1:.2f} in (full width, over the tubes).",
        f"Bolts: {2 * (2 * n_tr) + 4 + 12} of 3/8-16 x 3 in hex bolts with washers and lock nuts (2 per bracket, hanger and angle).",
        f"Tread screws: {4 * n_tr} of 1/4 x 1 1/4 in pan head screws up through the seats, 2 per bracket.",
        "Wall: 3/8 x 3 1/2 in lag screws through the wall tabs into solid blocking, with 1/2 in spacers. Slab: 3/8 in wedge anchors at the 2 floor angles.",
        "",
        "ASSEMBLY",
        "1. Add solid blocking in the bath 1 wall and the clerestory wall along both slopes, and at the wall rail brackets, before drywall.",
        f"2. Cut the tubes. Clamp the drill jig to a tube's inner side, top edges flush, and drill 13/32 in holes through both walls. Leapfrog the jig {PITCH:.2f} in up the tube.",
        "3. Bolt on the brackets, seats level and pointing inward. Wall side tubes: put the wall tabs under the bolt heads on the wall side.",
        "4. Lower flight: stand the tubes up, anchor the floor angles, bolt the heads to the landing posts. Lag the wall tabs.",
        "5. Upper flight: bolt the open side tube's foot to the landing's north west post, hang both heads from the balcony rim, lag the wall tabs.",
        "6. Screw the treads on from below. Rails: wall rails on brackets 1 1/2 in off the walls; open side rail posts bolt to the tube's outer face at brackets.",
        "",
        f"CHECKS (preliminary): 300 lb at mid flight puts about 2,100 psi in the tube. Treads {WN - 0.1:.1f} in wide, 21 7/8 in between rails (20 in min).",
        "Engineer to confirm: tube and bracket sizes, bolts, wall lags and blocking, slab anchors, landing posts and rim, balcony rim and its cantilever."]
for i, r in enumerate(rows):
    fig.text(0.43, 0.43 - i * 0.0205, r, fontsize=8.3, fontweight="bold" if r.isupper() or r.startswith("CUT") else "normal")
fig.savefig(os.path.join(OUT, "tube_ladder_assembly.png"), dpi=150)
fig.savefig(os.path.join(OUT, "tube_ladder_assembly.pdf"))
