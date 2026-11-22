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
PANEL_U = TD + 0.75 - GO                          # riser panel's front face, from this bracket's nosing: 3/4 in behind the back edge of the tread below
SLOTS = ((-1.85, -0.75), (-7.0, -5.9))            # slot heights below the tread's underside: the panel's ears are 0.9 in tall
WEB_U0, SEAT_U0 = 3.75, 1.0                       # web starts 1/4 in behind the tread below; seat starts 1 in behind the nosing


def tread_bracket(floor=None):
    """flat pattern, origin at the tread's nosing in u, bend line (tread underside) at y = 0, web below, seat above.
    floor: the floor's y for the first tread of the lower flight, whose web is trimmed level 1/8 in above it"""
    A, B = (WEB_U0, 0.0), (TD, 0.0)
    C = (WEB_U0, -(TD - WEB_U0) * SL)             # on the tube's top line, which passes through B
    B2, C2 = (B[0] + NX * LAP, B[1] + NZ * LAP), (C[0] + NX * LAP, C[1] + NZ * LAP)
    web = [A, C, C2, B2, B]
    if floor is not None:
        yc = floor + 0.25                         # inside of the bend to the foot flange
        cl = []
        for p, q in zip(web, web[1:] + web[:1]):  # clip to y >= yc
            if p[1] >= yc:
                cl.append(p)
            if (p[1] - yc) * (q[1] - yc) < 0:
                t = (yc - p[1]) / (q[1] - p[1])
                cl.append((p[0] + t * (q[0] - p[0]), yc))
        i0 = next(i for i in range(len(cl)) if abs(cl[i][1] - yc) < 1e-9 and abs(cl[(i + 1) % len(cl)][1] - yc) < 1e-9)
        (xa, _), (xb, _) = cl[i0], cl[(i0 + 1) % len(cl)]
        cl = cl[:i0 + 1] + [(xa, yc - FL_FLAT), (xb, yc - FL_FLAT)] + cl[i0 + 1:]      # foot flange, bent the same way as the seat, anchored to the slab or landing
        web, foot = cl, ((xa, yc), (xb, yc), ((xa + xb) / 2, yc - 1.25, 0.44))
    out = [(SEAT_U0, FL_FLAT), (SEAT_U0, 0), (WEB_U0 - 0.25, 0), (WEB_U0 - 0.25, 0.3), (WEB_U0, 0.3)] + web + [(TD, FL_FLAT)]
    holes = [(C[0] + DX * s + NX * BOLT_N, C[1] + DZ * s + NZ * BOLT_N, D38) for s in BOLT_S]
    holes += [(2.0, FL_FLAT - 1.25, D14), (7.5, FL_FLAT - 1.25, D14)]
    bends = [((WEB_U0, 0), (TD, 0))]
    if floor is not None:
        holes.append(foot[2]); bends.append((foot[0], foot[1]))
    x0, x1 = PANEL_U - 0.03, PANEL_U + 0.28       # slots for the ears of a 1/4 in slide in riser panel
    cuts = [[(x0, y0), (x1, y0), (x1, y1), (x0, y1)] for y0, y1 in SLOTS]
    return out, holes, bends, cuts


def end_angle():
    """3 x 3 in angle, 4 in long, one at each end of each tube: feet to the slab or the corner landing, heads up into the landing or the balcony"""
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


def frame_clip():
    """3 x 3 in angle, 2 1/2 in long: two at each joint of the landing and balcony tube frames, one bolt per leg"""
    w = 6.0 - 0.25
    return [(0, 0), (2.5, 0), (2.5, w), (0, w)], [(1.25, 1.25, D38), (1.25, w - 1.25, D38)], [((0, w / 2), (2.5, w / 2))]


def rail_plate():
    """flat strap joining a rail to a post: two bolts in each"""
    return [(0, 0), (6.5, 0), (6.5, 1.5), (0, 1.5)], [(x, 0.75, 0.344) for x in (0.75, 2.0, 4.5, 5.75)], []


def brace_gusset():
    """one each side of each end of a knee brace: two bolts through the brace, two through the balcony arm or the wall angle"""
    return [(0, 0), (6, 0), (6, 2.5), (2.5, 6), (0, 6)], [(1.0, 1.0, D38), (4.75, 1.0, D38), (1.0, 4.75, D38), (2.6, 2.6, D38)], []


def riser_panel():
    """1/4 in plywood riser, ears through the bracket slots. Decorate freely: no opening may pass a 4 in sphere, keep 3/4 in of wood around cutouts"""
    w, h, e = WN - 2 * TW - 2 * T_BR - 0.12, RI - TT - 0.55, 0.45
    ys = [(-0.3 - b, -0.3 - a) for a, b in ((0.5, 1.4), (5.65, 6.55))]         # ear heights measured from the panel's top edge, flipped to y up
    out = [(0, 0), (w, 0)]
    for a, b in sorted((h + y0, h + y1) for y0, y1 in ys):
        out += [(w, a), (w + e, a), (w + e, b), (w, b)]
    out += [(w, h), (0, h)]
    for a, b in sorted(((h + y0, h + y1) for y0, y1 in ys), reverse=True):
        out += [(0, b), (-e, b), (-e, a), (0, a)]
    return out, [], []


def norm(part):
    cuts = part[3] if len(part) > 3 else []
    out, holes, bends = part[:3]
    x0, y0 = min(p[0] for p in out), min(p[1] for p in out)
    f = lambda p: (round(p[0] - x0, 4), round(p[1] - y0, 4))
    return [f(p) for p in out], [f(h) + (h[2],) for h in holes], [(f(a), f(b)) for a, b in bends], [[f(p) for p in c] for c in cuts]


def dxf(path, part):
    pts, holes, bends, cuts = part
    w = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "1", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        w += ["0", "LINE", "8", "0", "10", f"{a[0]}", "20", f"{a[1]}", "30", "0", "11", f"{b[0]}", "21", f"{b[1]}", "31", "0"]
    for c in cuts:
        for a, b in zip(c, c[1:] + c[:1]):
            w += ["0", "LINE", "8", "0", "10", f"{a[0]}", "20", f"{a[1]}", "30", "0", "11", f"{b[0]}", "21", f"{b[1]}", "31", "0"]
    for x, y, d in holes:
        w += ["0", "CIRCLE", "8", "0", "10", f"{x}", "20", f"{y}", "30", "0", "40", f"{d / 2}"]
    for a, b in bends:
        w += ["0", "LINE", "8", "BEND", "62", "1", "10", f"{a[0]}", "20", f"{a[1]}", "30", "0", "11", f"{b[0]}", "21", f"{b[1]}", "31", "0"]
    w += ["0", "ENDSEC", "0", "EOF"]
    open(path, "w").write("\n".join(w) + "\n")


n_tr = NR - 2                                   # treads (the landing and the balcony are risers N_LO and NR)
PARTS = [("tread_bracket", norm(tread_bracket()), 2 * n_tr - 4, '1/4" steel', "one 90° bend: half bent up, half bent down (left and right hand)"),
         ("tread_bracket_floor", norm(tread_bracket(floor=-(RI - TT))), 4, '1/4" steel', "first tread of each flight: two 90° bends the same way (seat and foot flange), two bent each way"),
         ("end_angle", norm(end_angle()), 10, '1/4" steel', "one 90° bend: tube heads (4), newel and foot post bases (4), knee brace wall ends (2)"),
         ("frame_clip", norm(frame_clip()), 24, '1/4" steel', "one 90° bend: two at each joint of the landing and balcony frames"),
         ("rail_plate", norm(rail_plate()), 10, '3/16" steel', "flat: rails to posts"),
         ("brace_gusset", norm(brace_gusset()), 8, '1/4" steel', "flat: knee brace ends"),
         ("riser_panel", norm(riser_panel()), 10, '1/4" plywood', "flat: slide in riser, plain blank to decorate"),
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
def tube_len(nr, tuck):
    """level cut at the foot (floor or landing top) and at the head (underside of the platform, tuck below its top)"""
    zl = lambda u: RI + u * SL - TD * SL - TT
    u0 = -zl(0) / SL
    u2 = (nr * RI - tuck - zl(0)) / SL
    pts = [(u0, 0), (u0 + PL / SL, 0), (u2, nr * RI - tuck), (u2 + PL / SL, nr * RI - tuck)]
    s = [u * DX + z * DZ for u, z in pts]
    return max(s) - min(s)


TK = L.get("ladder_platform_in", TT + TDp)        # platform build up: oak deck on a 2 x 3 tube frame
LEN_LO, LEN_UP = tube_len(N_LO, TK), tube_len(NR - N_LO, TK)
print(f"tubes: lower {LEN_LO:.1f} in x2, upper {LEN_UP:.1f} in x2, angle {math.degrees(ANG):.1f}, pitch {PITCH:.3f}")

# ---------------------------------------------------------------- assembly sheet
fig = plt.figure(figsize=(17, 11))
fig.text(0.03, 0.955, "LOFT SHIPS LADDER: TUBE STRINGER KIT WITH LANDING, BALCONY AND RAILS", fontsize=17, fontweight="bold")
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
    pts, holes, bends, cuts = part
    w, h = max(p[0] for p in pts), max(p[1] for p in pts)
    ax2.add_patch(Polygon([(x + a, b) for a, b in pts], fc="#d9be8c" if "ply" in mat else "#c9c9c9", ec="k", lw=0.8))
    for c in cuts:
        ax2.add_patch(Polygon([(x + a, b) for a, b in c], fc="white", ec="k", lw=0.5))
    for hx, hy, d in holes:
        ax2.add_patch(Circle((x + hx, hy), d / 2, fc="white", ec="k", lw=0.5))
    for a, b in bends:
        ax2.plot([x + a[0], x + b[0]], [a[1], b[1]], c="r", lw=0.8, ls="--")
    ax2.text(x, -1.2, f"{name}\nx{qty}\n{w:.1f} x {h:.1f}\"", fontsize=6.3, va="top")
    x += w + 2.8
ax2.set_xlim(-1, x); ax2.set_ylim(-9, 24)
ax2.set_title("LASER CUT PARTS, FLAT (red dashes = bend line; one DXF file each)", fontsize=10, fontweight="bold", loc="left")
rows = ["CUT LIST AND HARDWARE",
        f"Stringers: {TW:.0f} x {TDp:.0f} x 3/16 in rectangular steel tube (A500). Lower flight 2 pieces about {LEN_LO:.1f} in overall, upper flight 2 pieces about {LEN_UP:.1f} in.",
        f"   All 8 cuts are the same level cut, {90 - math.degrees(ANG):.1f}° off square. Lengths are from the model: measure the real rise first.",
        f"Landing and balcony frames: the same {TW:.0f} x {TDp:.0f} x 3/16 tube on edge, square cuts, about 21 ft in all. Knee braces: 2 x 2 x 3/16 square tube, 2 pieces about 25 in, 45° cuts.",
        "Posts: 2 x 2 x 3/16 square tube: corner newel 91 in, balcony newel 57 in, foot post 61 in, guard posts 39 and 47 in. Rails: 1 1/2 x 1 1/2 x 3/16 square tube, about 32 ft.",
        "Guard infill: 1/2 in round bar pickets in 9/16 in holes drilled in the top and bottom rails, 4 3/8 in apart at most (under 4 in clear).",
        f"Treads: {n_tr} white oak, 1 7/16 x {TD} x {WN - 0.1:.2f} in. Decks: 1 7/16 in white oak on both frames, with a {TD - GO:.1f} in nosing past the frame where a flight arrives.",
        f"Bolts: 3/8-16 hex bolts with washers and lock nuts throughout (about {2 * (2 * n_tr) + 100}). Tread and deck screws: 1/4 x 1 1/4 in up through the seats and clips.",
        "Wall: 3/8 in lags or structural screws into blocking (ledgers, wall tabs, brace angles, north east guard post). Slab: 1/2 in wedge anchors at the feet, foot post and newel.",
        "",
        "ASSEMBLY",
        "1. Add solid blocking in both walls before drywall: along both slopes, behind both ledgers, at the knee brace angles and at the wall rail brackets.",
        f"2. Cut the tubes. Clamp the drill jig to a stringer's inner side, top edges flush, and drill 13/32 in holes through both walls. Leapfrog the jig {PITCH:.2f} in up the tube.",
        "3. Bolt on the brackets, seats level and pointing inward. Wall side tubes: put the wall tabs under the bolt heads on the wall side.",
        "4. Frames: lag the ledgers to the walls, bolt the beams together with two clips per joint, stand the corner newel and bolt it to the landing's west beam.",
        "5. Lower flight: feet on the slab (anchor the first brackets' foot flanges), heads tucked under the landing header, bolted up through the head angles. Lag the wall tabs.",
        "6. Upper flight: feet on the landing, heads under the balcony's head arm. Bolt the balcony newel to the west beam and to the stringer below it. Fit the knee braces.",
        "7. Screw on the treads and decks from below. Rails butt the newels with rail plates and sit on top of the foot post and guard posts. Wall rails on brackets 1 1/2 in off the walls.",
        "8. Riser panels: push one end's ears through its bracket slots, swing the other end in, and slide back to centre. A felt dot in each slot stops rattles.",
        "",
        f"CHECKS: see the load analysis sheet (frame model, 23 load cases). Treads {WN - 0.1:.1f} in wide, about 22 1/2 in between rails (20 in min). Riser openings closed to under 4 in by the panels.",
        "Engineer to confirm: all member and bolt sizes, wall lags and blocking, slab anchors, and how the balcony ledger fastens to the loft floor's rim."]
for i, r in enumerate(rows):
    fig.text(0.43, 0.445 - i * 0.0195, r, fontsize=7.6, fontweight="bold" if r.isupper() or r.startswith("CUT") else "normal")
fig.savefig(os.path.join(OUT, "tube_ladder_assembly.png"), dpi=150)
fig.savefig(os.path.join(OUT, "tube_ladder_assembly.pdf"))
