"""Dimensioned drawing set of the loft ships ladder, design "corner", exactly as model/ladder_options.py builds it.

Every number is read from model/config.toml or recomputed with the same formulas as make_house.py / ladder_options.py.
Local drawing frame, in inches: origin at the inside corner of the living room where the bath 1 west wall face
(plan x 31.122 ft) meets the clerestory wall north face (plan y 34.616 ft). X runs east (negative = west of the bath 1
wall), Y runs north (positive = north of the clerestory wall), Z is height above the slab.
Run: python3 tools/ladder_drawings/draw_ladder.py OUTDIR
"""
import math, os, sys, textwrap, tomllib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Polygon, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
C = tomllib.load(open(os.path.join(HERE, "..", "..", "model", "config.toml"), "rb"))
L, R = C["loft"], C["roof"]
OUT = sys.argv[1] if len(sys.argv) > 1 else "."
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- model numbers (feet in the model, inches here)
EDGE_X = 31.122                    # bath 1 west wall face (make_house EDGE_X, from INT_RECTS wall x 31.122 to 31.581)
BATH_T = (31.581 - 31.122) * 12    # 5 1/2 in wall
YC = R["clerestory_wall_y"]        # clerestory wall north face 34.616
CW_T = C["house"]["ext_wall_thickness"] * 12
FL = L["floor_height"] * 12        # finished loft floor above the slab
NR = L["ladder_risers"]
RI = FL / NR
GO = L["ladder_going_in"]
TD = L["ladder_tread_in"]
NOS = TD - GO                      # tread overlap / loft edge nosing
HR = L["ladder_handrail_in"]
SW, RW = 0.15 * 12, 0.125 * 12     # stringer and handrail widths in the model
RH_T = 0.13 * 12                   # handrail depth in the model
TT = 0.12 * 12                     # tread thickness in the model
STR_D = 12.0                       # stringer depth measured plumb
WN = L.get("ladder_width_in", 24.0)  # overall ladder width ("corner": wn)
N_LO = int(L.get("ladder_lower_risers", 5))
wnf = WN / 12
N_UP = NR - N_LO
ly1 = L["ships_ladder"][3]
DOOR_X = [p for p in C["clerestory"]["passages"] if p[0] < 26 < p[1] + 1][0]
WALL = EDGE_X - 0.01
XLf = WALL - wnf - 0.1
X = lambda xf: (xf - EDGE_X) * 12
Y = lambda yf: (YC - yf) * 12
X_XL = X(XLf)                                        # west edge of the upper flight and both landings
UL = (N_LO - 1) * GO + NOS                           # lower flight run, first nosing to landing face
X_FOOT = X_XL - UL                                   # first nosing of the lower flight
X_JAMB = X(DOOR_X[1])                                # living room opening, east jamb
X_JAMB_W = X(DOOR_X[0])
Y_LO0, Y_LO1 = Y(ly1), Y(ly1 - wnf)                  # lower flight band (south, north edge)
Y_LD0, Y_LD1 = Y(ly1 + 0.12), Y(ly1 - wnf - 0.1)           # corner landing
Z_LD = N_LO * RI
UU = (N_UP - 1) * GO + NOS
Y_BAL0 = Y_LD1 + UU                                  # balcony south edge (top riser line)
Y_BAL1 = Y_BAL0 + WN + 1.2                               # yt0 = yt1 - wn - 0.1
X_UP0, X_UP1 = X_XL, X_XL + WN
yt1f, yt0f = YC - Y_BAL0 / 12, YC - Y_BAL1 / 12
yl0f = ly1 - wnf - 0.1
RAIL_GAP = (Y(yt1f + 0.06), Y(yt0f - 0.05))
PERSON = next((f for f in C["furnishings"]["items"] if f.get("type") == "seated_person" and f.get("web")), None) if isinstance(C.get("furnishings"), dict) and "items" in C["furnishings"] else None
N_UP_T = N_UP - 1
TAG = "" if N_LO == 5 else f" ({N_LO - 1} TREAD OPTION)"                    # loft railing opening, from RAIL_SPAN
RAIL_H = L["railing_height"] * 12
ANG = math.degrees(math.atan(RI / GO))
roof_under = lambda Yin: (17.617 + ((YC - Yin / 12) - 27.07) * R["north_pitch"] / 12) * 12   # north roof underside (make_house roof_under)
SWITCH = dict(Y=Y(31.45), z=44)                      # electrical_plan.json 4 gang plate on the bath 1 west wall
COUCH = dict(x0=X(31.06 - 3.1), Y0=Y(30.45), Y1=Y(22.95))


def overhead(hx, hy, r, crown):
    """lowest part of the ladder over a head disc (plan ft), in inches above the slab: upper treads, the loft edge
    nosing, the balcony and its knee braces, as the model builds them"""
    best = 1e9
    for i in range(-8, 9):
        for j in range(-8, 9):
            x, y = hx + r * i / 8, hy + r * j / 8
            if (x - hx) ** 2 + (y - hy) ** 2 > r * r:
                continue
            Xi, Yi = X(x), Y(y)
            zs = []
            if X_UP0 + SW <= Xi <= X_UP1 - SW:
                for k in range(1, N_UP):
                    y0 = Y_LD1 + (k - 1) * GO
                    if y0 <= Yi <= min(y0 + TD, Y_BAL0):
                        zs.append(Z_LD + k * RI - TT)
                if Y_BAL0 - NOS <= Yi <= Y_BAL0:
                    zs.append(FL - 1.2)
            if X_XL <= Xi <= 0 and Y_BAL0 <= Yi <= Y_BAL1:
                zs.append(FL - 6)
            for yb in (yt0f + 0.2, yt1f - 0.2):
                if yb <= y <= yb + 0.12 and XLf + 0.2 <= x <= EDGE_X:
                    t = (x - (XLf + 0.2)) / (EDGE_X - XLf - 0.2)
                    zs.append((L["floor_height"] - 0.62 - t * (2.5 - 0.62)) * 12)
            zs = [z for z in zs if z > crown]
            if zs:
                best = min(best, min(zs))
    return best


if PERSON:
    P_S = (PERSON.get("seat", 1.45) - 0.06) * 12
    P_CROWN = P_S + PERSON.get("sitting_in", 37.5)
    P_HX, P_HY = PERSON["x"] - 0.46, PERSON["y"]
    P_OVER = overhead(P_HX, P_HY, 0.31, P_CROWN)
    P_CLR = P_OVER - P_CROWN


# ---------------------------------------------------------------- number formatting (architectural, no dashes inside inches)
def fin(v, den=16):
    """inches only, e.g. 9 9/32\" """
    t = round(abs(v) * den)
    whole, num = divmod(t, den)
    g = math.gcd(num, den) if num else 1
    if not num:
        return f"{whole}\""
    return f"{whole} {num // g}/{den // g}\"" if whole else f"{num // g}/{den // g}\""


def frac(v, den=16):
    """feet and inches, e.g. 10'-0 5/8\" (the hyphen is the drafting separator between feet and inches)"""
    t = round(abs(v) * den)
    ft, rem = divmod(t, 12 * den)
    if not ft:
        return fin(v, den)
    s_ = fin(rem / den, den)
    if rem and rem < den:
        s_ = "0 " + s_
    return f"{ft}'-{s_}"


# ---------------------------------------------------------------- drawing helpers
INK, GREY, LIGHT, OAK, TREAD, STEEL, RED = "#111111", "#777777", "#c4c4c4", "#efe2c4", "#d9be8c", "#2b2b2b", "#b3261e"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7})
W_, H_ = 17.0, 11.0
SHEETS = []
COS = math.cos(math.radians(ANG))
SD_P = 11.25                              # stringer board drawn (2x12 class), see field note
STR_PLUMB = SD_P / COS                    # its depth measured plumb
STR_TOP = 1.2                             # stringer top above the nosing line, plumb (model)


def scaled_axes(fig, left, bottom, xr, yr, den):
    w, h = (xr[1] - xr[0]) / den, (yr[1] - yr[0]) / den
    ax = fig.add_axes([left / W_, bottom / H_, w / W_, h / H_])
    ax.set_xlim(*xr); ax.set_ylim(*yr); ax.set_aspect("equal"); ax.axis("off")
    ax._den = den
    return ax


def poly(ax, pts, fc="none", ec=INK, lw=0.8, ls="-", z=2, hatch=None):
    ax.add_patch(Polygon(pts, closed=True, fc=fc, ec=ec, lw=lw, ls=ls, zorder=z, hatch=hatch))


def rect(ax, x0, y0, x1, y1, **k):
    poly(ax, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], **k)


def line(ax, pts, c=INK, lw=0.6, ls="-", z=3):
    ax.plot([p[0] for p in pts], [p[1] for p in pts], color=c, lw=lw, ls=ls, zorder=z, solid_capstyle="butt")


def txt(ax, x, y, s, size=6.5, ha="center", va="center", rot=0, c=INK, w="normal", z=8, bg=False):
    ax.text(x, y, s, fontsize=size, ha=ha, va=va, rotation=rot, color=c, fontweight=w, zorder=z, rotation_mode="anchor",
            bbox=dict(fc="white", ec="none", pad=0.4) if bg else None, linespacing=1.15)


def P(ax, paper_in):
    """paper inches to building inches on this axes"""
    return paper_in * ax._den


def dim(ax, p1, p2, off, label=None, size=6.2, ext=True, den=16, tpos="end"):
    """architectural dimension. off: signed offset of the dimension line along the left normal of p1 -> p2 (building in)."""
    (x1, y1), (x2, y2) = p1, p2
    L_ = math.hypot(x2 - x1, y2 - y1)
    dx, dy = (x2 - x1) / L_, (y2 - y1) / L_
    nx, ny = -dy, dx
    a, b = (x1 + nx * off, y1 + ny * off), (x2 + nx * off, y2 + ny * off)
    s = P(ax, 0.05)
    if ext and abs(off) > 1e-6:
        sg = 1 if off > 0 else -1
        for (px, py) in (p1, p2):
            line(ax, [(px + nx * sg * s, py + ny * sg * s), (px + nx * (off + sg * 1.6 * s), py + ny * (off + sg * 1.6 * s))], c=GREY, lw=0.3)
    line(ax, [(a[0] - dx * 1.6 * s, a[1] - dy * 1.6 * s), (b[0] + dx * 1.6 * s, b[1] + dy * 1.6 * s)], c=INK, lw=0.4)
    t = 1.1 * s
    for (px, py) in (a, b):
        line(ax, [(px - (dx + nx) * t, py - (dy + ny) * t), (px + (dx + nx) * t, py + (dy + ny) * t)], c=INK, lw=0.9)
    ang = math.degrees(math.atan2(dy, dx))
    flip = ang > 90.01 or ang < -89.99
    if flip:
        ang -= 180
    lab = label if label is not None else frac(L_, den)
    tw = P(ax, len(lab) * size * 0.56 / 72)                   # text width in building inches
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    if tw > L_ - 4 * s:                                       # too tight: put the text past the p2 end
        k = (L_ / 2 + 2.5 * s + tw / 2) * (1 if tpos == "end" else -1)
        mx, my = mx + dx * k, my + dy * k
    sg = 1 if off >= 0 else -1
    up = 1.9 * s
    # put the text on the outer side of the dimension line, reading from below or the right
    tx, ty = mx + nx * up * sg, my + ny * up * sg
    txt(ax, tx, ty, lab, size=size, rot=ang, bg=True)


def key(ax, x, y, n, r=0.085):
    rr = P(ax, r)
    ax.add_patch(plt.Circle((x, y), rr, fc="white", ec=INK, lw=0.7, zorder=11))
    txt(ax, x, y, str(n), size=5.6 if len(str(n)) < 2 else 5.0, w="bold", z=12)


def keyline(ax, p, q, n):
    line(ax, [p, q], c=INK, lw=0.4, z=10)
    ax.plot([p[0]], [p[1]], marker="o", ms=1.5, color=INK, zorder=10)
    key(ax, q[0], q[1], n)


def ftxt(fig, x, y, s, **k):
    k.setdefault("va", "top")
    fig.text(x / W_, y / H_, s, **k)


def fline(fig, x0, y0, x1, y1, lw=0.8, c=INK):
    fig.add_artist(matplotlib.lines.Line2D([x0 / W_, x1 / W_], [y0 / H_, y1 / H_], transform=fig.transFigure, lw=lw, color=c))


def view_title(fig, x, y, num, name, scale):
    fig.add_artist(plt.Circle(((x + 0.2) / W_, (y + 0.02) / H_), 0.18 / W_, transform=fig.transFigure, fill=False, lw=0.9))
    ftxt(fig, x + 0.2, y + 0.02, num, fontsize=8, ha="center", va="center", fontweight="bold")
    ftxt(fig, x + 0.5, y + 0.04, name, fontsize=9, fontweight="bold", va="bottom")
    fline(fig, x + 0.5, y, x + 0.5 + max(3.2, len(name) * 0.075), y)
    ftxt(fig, x + 0.5, y - 0.04, f"SCALE: {scale}", fontsize=6.5)


def keynotes(fig, x, y, title_, notes, width=4.8):
    ftxt(fig, x, y, title_, fontsize=8.5, fontweight="bold")
    yy = y - 0.3
    for n, s in notes:
        fig.add_artist(plt.Circle(((x + 0.09) / W_, (yy - 0.06) / H_), 0.075 / W_, transform=fig.transFigure, fill=False, lw=0.6))
        ftxt(fig, x + 0.09, yy - 0.06, str(n), fontsize=5.2, ha="center", va="center", fontweight="bold")
        lines = textwrap.wrap(s, int(width * 17))
        for j, ln in enumerate(lines):
            ftxt(fig, x + 0.28, yy - j * 0.145, ln, fontsize=6.4)
        yy -= 0.145 * len(lines) + 0.07
    return yy


def sheet(num, name):
    fig = plt.figure(figsize=(W_, H_))
    fig.patch.set_facecolor("white")
    fig.add_artist(Rectangle((0.25 / W_, 0.25 / H_), (W_ - 0.5) / W_, (H_ - 0.5) / H_, transform=fig.transFigure, fill=False, lw=1.4))
    tx = W_ - 2.65
    fline(fig, tx, 0.25, tx, H_ - 0.25, lw=1.0)
    ftxt(fig, tx + 0.15, H_ - 0.5, "LOFT SHIPS LADDER", fontsize=12, fontweight="bold")
    ftxt(fig, tx + 0.15, H_ - 0.8, "Corner landing design, as modeled" if not TAG else f"Corner landing, {N_LO - 1} treads below it (option)", fontsize=7.5)
    ftxt(fig, tx + 0.15, H_ - 0.98, "Heilman Mullin residence", fontsize=7.5)
    fline(fig, tx, H_ - 1.3, W_ - 0.25, H_ - 1.3)
    gen = ["Drawn from the owner's 3D house model",
           "(config.toml [loft] and ladder_options.py,",
           "design \"corner\", as of 11/21/2026) for",
           "the architect to redraw into the",
           "permit set.", "",
           "NOT FOR CONSTRUCTION.",
           "Architect and engineer of record to",
           "confirm structure, code and every",
           "field dimension.", "",
           "Plan dimensions are to finished wall",
           "faces. Heights are above the finished",
           "slab (stained concrete, no topping).", "",
           "Treads are numbered by riser:",
           f"1 to {N_LO - 1} lower flight, {N_LO} corner landing,",
           f"{N_LO + 1} to 12 upper flight, 13 balcony."]
    for i, s in enumerate(gen):
        ftxt(fig, tx + 0.15, H_ - 1.5 - i * 0.155, s, fontsize=6.6, fontweight="bold" if s.startswith("NOT") else "normal")
    fline(fig, tx, 2.05, W_ - 0.25, 2.05)
    ftxt(fig, tx + 0.15, 1.88, "SHEETS", fontsize=7, fontweight="bold")
    for i, (n_, s_) in enumerate([("L-1", "Plan"), ("L-2", "Sections"), ("L-3", "Details"), ("L-4", "Schedule, code check, field verify")]):
        ftxt(fig, tx + 0.15, 1.68 - i * 0.15, f"{n_}    {s_}", fontsize=6.8, fontweight="bold" if n_ == num else "normal")
    fline(fig, tx, 0.98, W_ - 0.25, 0.98)
    ftxt(fig, tx + 0.15, 0.85, "Date: 11/21/2026", fontsize=6.8)
    ftxt(fig, tx + 0.15, 0.66, name, fontsize=8, fontweight="bold")
    ftxt(fig, W_ - 0.42, 0.72, num, fontsize=22, fontweight="bold", ha="right")
    SHEETS.append((num, fig))
    return fig


# ---------------------------------------------------------------- flight side profile
def nosing_z(z0, u):
    return z0 + RI + u * RI / GO


def stringer_poly(mapu, u0, u1, z0, ztop):
    zt = lambda u: min(nosing_z(z0, u) + STR_TOP, ztop)
    zb = lambda u: max(z0, nosing_z(z0, u) + STR_TOP - STR_PLUMB)
    us = [u0 + (u1 - u0) * i / 300 for i in range(301)]
    return [(mapu(u), zt(u)) for u in us] + [(mapu(u), zb(u)) for u in reversed(us)]


def flight_profile(ax, mapu, z0, nr, ztop, u_end, rail=True, landing_nosing=True):
    poly(ax, stringer_poly(mapu, -0.5, u_end, z0, ztop), fc=OAK, ec=INK, lw=0.7, z=2)
    for k in range(1, nr):
        uk = (k - 1) * GO
        zk = z0 + k * RI
        h0, h1 = mapu(uk), mapu(uk + TD)
        rect(ax, min(h0, h1), zk - TT, max(h0, h1), zk, fc=TREAD, ec=INK, lw=0.6, z=4)
    if landing_nosing:
        h0, h1 = mapu(u_end - NOS), mapu(u_end)
        rect(ax, min(h0, h1), z0 + nr * RI - TT, max(h0, h1), z0 + nr * RI, fc=TREAD, ec=INK, lw=0.6, z=4)
    line(ax, [(mapu(-5), nosing_z(z0, -5)), (mapu(u_end + 3), nosing_z(z0, u_end + 3))], c=RED, lw=0.45, ls=(0, (6, 3)), z=5)
    if rail:
        r0, r1 = 0.0, u_end - NOS
        zr = lambda u: nosing_z(z0, u) + HR
        poly(ax, [(mapu(r0), zr(r0)), (mapu(r1), zr(r1)), (mapu(r1), zr(r1) - RH_T), (mapu(r0), zr(r0) - RH_T)], fc=STEEL, ec=INK, lw=0.4, z=6)
        for up in (r0 + 0.6, r1 - 0.6):
            zb_ = min(nosing_z(z0, up) + STR_TOP, ztop)
            h0, h1 = mapu(up - 0.6), mapu(up + 0.6)
            rect(ax, min(h0, h1), zb_, max(h0, h1), zr(up) - RH_T, fc=STEEL, ec=INK, lw=0.3, z=6)


def slab(ax, h0, h1):
    rect(ax, h0, -5, h1, 0, fc="#e2e2e2", ec=INK, lw=0.9, hatch="....", z=1)


WALLSTYLE = dict(fc="#d4d4d4", ec=INK, lw=1.0, hatch="////", z=1)
CUTSTYLE = dict(fc="#ead6a8", ec=INK, lw=0.9, hatch="xxx", z=3)
HEAD_BAL = roof_under(Y_BAL1) - FL
HEAD_TOP = roof_under(Y_BAL0 - NOS) - FL
RAIL_CLR_UP = -(X_UP1 - SW / 2 + RW / 2)            # upper flight east rail to the bath 1 wall
RAIL_CLR_LO = Y_LO0 + SW / 2 - RW / 2               # lower flight south rail to the clerestory wall

# ================================================================ L-1 PLAN
fig = sheet("L-1", "Plan")
den = 16
xr, yr = (-114, 18), (-38, 113)
ax = scaled_axes(fig, 0.5, 1.15, xr, yr, den)
view_title(fig, 0.6, 0.78, "1", "LADDER PLAN", "3/4\" = 1'-0\"")
# walls
rect(ax, 0, -CW_T, BATH_T, 113, **WALLSTYLE)
rect(ax, X_JAMB, -CW_T, BATH_T, 0, **WALLSTYLE)
rect(ax, xr[0], -CW_T, X_JAMB - 72 if X_JAMB - 72 > xr[0] else xr[0], 0, **WALLSTYLE) if False else None
line(ax, [(xr[0], 0), (X_JAMB, 0)], c=GREY, lw=0.4, ls=(0, (5, 3)))
line(ax, [(xr[0], -CW_T), (X_JAMB, -CW_T)], c=GREY, lw=0.4, ls=(0, (5, 3)))
txt(ax, (xr[0] + X_JAMB) / 2, -CW_T / 2, "LIVING ROOM OPENING", size=5.8, c=GREY)
txt(ax, -25, -CW_T / 2, "CLERESTORY WALL", size=5.8, w="bold", bg=True)
txt(ax, BATH_T + 3.2, 108, "BATH 1 WEST WALL", size=5.8, w="bold", rot=90, ha="right")
txt(ax, BATH_T + 7.5, 108, "LOFT ABOVE", size=5.8, rot=90, ha="right", c=GREY)
txt(ax, -104, 60, "LIVING ROOM", size=8, w="bold", c="#666", rot=90)
# couch outline
poly(ax, [(COUCH["x0"], COUCH["Y0"]), (X(31.06), COUCH["Y0"]), (X(31.06), 113), (COUCH["x0"], 113)], ec=GREY, lw=0.5, ls=(0, (3, 2)), z=1)
if PERSON:
    rect(ax, X(PERSON["x"] - 2.0), Y(PERSON["y"] + 0.8), X(PERSON["x"]), Y(PERSON["y"] - 0.8), fc="none", ec="#3B5A80", lw=0.7, ls=(0, (2, 1.5)), z=9)
    ax.add_patch(plt.Circle((X(P_HX), Y(P_HY)), 0.31 * 12, fc="none", ec="#3B5A80", lw=0.8, ls=(0, (2, 1.5)), zorder=9))
# lower flight
for y0_, y1_ in ((Y_LO0, Y_LO0 + SW), (Y_LO1 - SW, Y_LO1)):
    rect(ax, X_FOOT - 0.48, y0_, X_XL, y1_, fc=OAK, ec=INK, lw=0.6, z=3)
for k in range(1, N_LO):
    x0 = X_FOOT + (k - 1) * GO
    rect(ax, x0, Y_LO0 + SW, min(x0 + TD, X_XL), Y_LO1 - SW, fc=TREAD if k % 2 else "#e8d2a4", ec=INK, lw=0.5, z=2 + k * 0.01)
    txt(ax, x0 + 2.5, Y_LO1 - 5, str(k), size=5.2, z=5)
rect(ax, X_XL - NOS, Y_LO0 + SW, X_XL, Y_LO1 - SW, fc="#e8d2a4", ec=INK, lw=0.5, z=3)
# corner landing
rect(ax, X_XL, Y_LD0, 0, Y_LD1, fc="#f3e8cf", ec=INK, lw=0.9, z=3)
for (py0, py1) in ((Y(ly1 + 0.09), Y(ly1 - 0.2)), (Y(yl0f + 0.29), Y(yl0f))):
    rect(ax, X_XL, py0, X_XL + 3.48, py1, fc="none", ec=INK, lw=0.5, ls=(0, (2, 1.5)), z=4)
txt(ax, X_XL / 2, 15, f"CORNER\nLANDING\nTOP {frac(Z_LD)}", size=5.6, w="bold")
# upper flight
for x0_, x1_ in ((X_UP0, X_UP0 + SW), (X_UP1 - SW, X_UP1)):
    rect(ax, x0_, Y_LD1, x1_, Y_BAL0, fc=OAK, ec=INK, lw=0.6, z=3)
for k in range(1, N_UP):
    y0 = Y_LD1 + (k - 1) * GO
    rect(ax, X_UP0 + SW, y0, X_UP1 - SW, min(y0 + TD, Y_BAL0), fc=TREAD if k % 2 else "#e8d2a4", ec=INK, lw=0.5, z=2 + k * 0.01)
    txt(ax, X_UP0 + 4.5, y0 + 2.5, str(N_LO + k), size=5.2, z=5)
rect(ax, X_UP0 + SW, Y_BAL0 - NOS, X_UP1 - SW, Y_BAL0, fc="#e8d2a4", ec=INK, lw=0.5, z=3)
# handrails
for yc in (Y_LO0 + SW / 2, Y_LO1 - SW / 2):
    rect(ax, X_FOOT, yc - RW / 2, X_XL - NOS, yc + RW / 2, fc=STEEL, ec=STEEL, lw=0.3, z=5)
for xc in (X_UP0 + SW / 2, X_UP1 - SW / 2):
    rect(ax, xc - RW / 2, Y_LD1, xc + RW / 2, Y_BAL0 - NOS, fc=STEEL, ec=STEEL, lw=0.3, z=5)
# up arrows
ax.annotate("", xy=(X_XL - 5, Y_LO0 + 8), xytext=(X_FOOT + 1.5, Y_LO0 + 8), arrowprops=dict(arrowstyle="-|>", lw=0.7, color=INK), zorder=8)
txt(ax, X_FOOT + 9, Y_LO0 + 11.5, f"UP {N_LO}R", size=5.6, w="bold", bg=True)
ax.annotate("", xy=(X_UP0 + 15, Y_BAL0 - 5), xytext=(X_UP0 + 15, Y_LD1 + 1.5), arrowprops=dict(arrowstyle="-|>", lw=0.7, color=INK), zorder=8)
txt(ax, X_UP0 + 18.5, Y_LD1 + 10, f"UP {N_UP}R", size=5.6, w="bold", rot=90, bg=True)
# balcony and its guards
rect(ax, X_XL, Y_BAL0, 0, Y_BAL1, fc="#f3e8cf", ec=INK, lw=0.9, z=3)
rect(ax, X(XLf + 0.02), Y(yt1f - 0.1), X(XLf + 0.1), Y(yt0f + 0.05), fc=STEEL, ec=INK, lw=0.4, z=5)
rect(ax, X(XLf + 0.1), Y(yt0f + 0.1), X(31.07), Y(yt0f + 0.02), fc=STEEL, ec=INK, lw=0.4, z=5)
txt(ax, X_XL / 2, (Y_BAL0 + Y_BAL1) / 2 - 1, f"BALCONY\nTOP {frac(FL)}\n(LOFT FLOOR)", size=5.6, w="bold")
# loft guard above (dashed)
for a, b in ((0.5, RAIL_GAP[0]), (RAIL_GAP[1], 113)):
    rect(ax, 0.1, a, 1.44, b, fc="none", ec=INK, lw=0.6, ls=(0, (4, 2)), z=6)
# switch
rect(ax, -0.9, SWITCH["Y"] - 2.3, 0, SWITCH["Y"] + 2.3, fc=RED, ec=RED, lw=0.3, z=7)
# section cuts
for (pa, pb, lab) in (((-74, 13), (11, 13), "A"), ((-13, -35), (-13, 110), "B")):
    line(ax, [pa, pb], c=INK, lw=0.5, ls=(0, (9, 2, 2, 2)), z=8)
    for p in (pa, pb):
        ax.add_patch(plt.Circle(p, P(ax, 0.11), fc="white", ec=INK, lw=0.8, zorder=9))
        txt(ax, p[0], p[1], lab, size=6.5, w="bold", z=10)
# north arrow
ax.annotate("", xy=(-104, 112), xytext=(-104, 96), arrowprops=dict(arrowstyle="-|>", lw=1.0, color=INK))
txt(ax, -104, 92, "N", size=8, w="bold")
# dimension strings, south side (below the clerestory wall)
yb = -CW_T
dim(ax, (X_JAMB, yb), (X_FOOT, yb), -7, fin(X_FOOT - X_JAMB, 16), tpos="start")
dim(ax, (X_FOOT, yb), (X_XL - NOS, yb), -7, frac((N_LO - 1) * GO) + f" ({N_LO - 1} x 5\")")
dim(ax, (X_XL - NOS, yb), (X_XL, yb), -7, fin(NOS))
dim(ax, (X_XL, yb), (0, yb), -7)
dim(ax, (X_FOOT, yb), (0, yb), -14, frac(-X_FOOT) + " FIRST NOSING TO BATH 1 WALL")
dim(ax, (X_JAMB, yb), (0, yb), -21, frac(-X_JAMB) + " OPENING JAMB TO BATH 1 WALL")
# lower flight width, west of the foot
xw = X_FOOT - 0.48
dim(ax, (xw, 0), (xw, Y_LO0), 6, fin(Y_LO0))
dim(ax, (xw, Y_LO0), (xw, Y_LO1), 6, frac(WN))
dim(ax, (xw, Y_LO0 + SW), (xw, Y_LO1 - SW), 13, fin(WN - 2 * SW) + " CLEAR")
# north south string west of the upper flight
xs = X_XL
dim(ax, (xs, 0), (xs, Y_LD1), 50, frac(Y_LD1))
dim(ax, (xs, Y_LD1), (xs, Y_BAL0 - NOS), 50, frac((N_UP - 1) * GO) + f" ({N_UP - 1} x 5\")")
dim(ax, (xs, Y_BAL0 - NOS), (xs, Y_BAL0), 50, fin(NOS))
dim(ax, (xs, Y_BAL0), (xs, Y_BAL1), 50)
dim(ax, (xs, 0), (xs, Y_BAL1), 57, frac(Y_BAL1) + " CLERESTORY WALL TO BALCONY EDGE")
# east west across the top
yq = Y_LD1 + 2.6 * GO
dim(ax, (X_UP0, yq), (X_UP1, yq), 0, frac(WN) + " UPPER FLIGHT", size=5.6, ext=False)
# keynotes
keyline(ax, (X_JAMB, -CW_T / 2), (X_JAMB - 9, -25), 1)
keyline(ax, (X_FOOT + 6, Y_LO0 + 3), (-44, 36), 2)
keyline(ax, (X_XL + 1.7, Y(34.57) + 1.6), (-26, -28) if False else (-6, -26), 3) if False else keyline(ax, (-6, 6), (11, 6), 3)
keyline(ax, (X_UP0 + 12, Y_LD1 + 24), (-40, 50) if False else (-36, 54), 4) if False else keyline(ax, (X_UP0 + 10, Y_LD1 + 22), (-42, 52), 4)
keyline(ax, (X_XL + 6, Y_BAL0 + 6), (-42, 70), 5)
keyline(ax, (X(XLf + 0.06), (Y_BAL0 + Y_BAL1) / 2), (-42, 86), 6)
keyline(ax, (0.8, 100), (-8, 106), 7)
keyline(ax, (X_UP1 - SW / 2, Y_LD1 + 30), (8, 70) if False else (-5, 78) if False else (9, 46), 8) if False else keyline(ax, (X_UP0 + SW / 2, Y_LD1 + 30), (-42, 60) if False else (-34, 44), 8)
keyline(ax, (-0.5, SWITCH["Y"]), (9, 38), 9)
keyline(ax, (COUCH["x0"] + 2, 108), (-42, 104), 10)
keyline(ax, (X_UP1 + 0.6, Y_LD1 + 14), (9, 28), 11)
if PERSON:
    keyline(ax, (X(PERSON["x"] - 2.0), Y(PERSON["y"])), (-56, 74), 12)

kn = [(1, f"Living room opening, east jamb. The first nosing is {fin(X_FOOT - X_JAMB)} east of it. Barn doors are assumed hung on the dining (south) side."),
      (2, f"Lower flight: {N_LO} risers up east along the clerestory wall, treads 1 to {N_LO - 1}. Stringers {fin(Y_LO0)} off the wall."),
      (3, f"Corner landing (riser {N_LO}), top {frac(Z_LD)} above slab, {frac(-X_XL)} E-W x {frac(Y_LD1 - Y_LD0)} N-S. Two 3 1/2\" x 3 1/2\" oak posts at its west corners (dashed); east and south edges on the walls."),
      (4, f"Upper flight: {N_UP} risers up north along the bath 1 wall, treads {N_LO + 1} to 12."),
      (5, f"Balcony at loft floor level (riser 13), {frac(-X_XL)} E-W x {frac(Y_BAL1 - Y_BAL0)} N-S, 6\" deep, carried on two steel knee braces off the bath 1 wall. Opens east into the loft."),
      (6, f"{fin(RAIL_H)} guards on the balcony's west and north sides, black steel with a white oak cap."),
      (7, f"Loft guard above, {fin(RAIL_H)}, along the loft edge over the bath 1 wall (dashed). Open {frac(RAIL_GAP[1] - RAIL_GAP[0])} where the balcony meets the loft."),
      (8, f"Handrails both sides of both flights, on top of the stringers, {fin(HR)} above the nosing line, first nosing to landing nosing."),
      (9, "Existing 4 gang switch plate (U-11 #8 to 11) at 44\" on the bath 1 wall sits under the upper flight. Relocate."),
      (10, "L couch, owner furniture, dashed for clearance only. Its short leg runs under the balcony and upper flight."),
      (12, f"Seated 6'-0\" person (dashed, under the upper flight) at the couch's south end. Head clearance {fin(P_CLR)}, see section B." if PERSON else ""),
      (11, f"Upper flight stringer stands {fin(-X_UP1)} off the bath 1 wall; its handrail is {fin(RAIL_CLR_UP, 32)} off the wall (1 1/2\" required, see F4).")]
kn = sorted([k for k in kn if k[1]]); yy = keynotes(fig, 9.25, 10.5, "KEYNOTES", kn, width=4.6)
ftxt(fig, 9.25, yy - 0.15, "LADDER DATA (from the model)", fontsize=8.5, fontweight="bold")
rows = [("Total rise", f"{frac(FL)} slab to finished loft floor"),
        ("Risers", f"{NR} equal at {fin(RI, 32)} ({N_LO} lower, {N_UP} upper)"),
        ("Going / tread", f"{fin(GO)} nosing to nosing / {fin(TD)} deep"),
        ("Angle", f"{ANG:.1f} degrees"),
        ("Width", f"{frac(WN)} overall, {fin(WN - 2 * SW)} clear"),
        ("Handrails", f"both sides, {fin(HR)} above nosing line"),
        ("Plan footprint", f"{frac(-X_FOOT)} E-W x {frac(Y_BAL1)} N-S")]
for i, (a, b) in enumerate(rows):
    ftxt(fig, 9.25, yy - 0.45 - i * 0.16, a, fontsize=6.6, fontweight="bold")
    ftxt(fig, 10.45, yy - 0.45 - i * 0.16, b, fontsize=6.6)

# ================================================================ L-2 SECTIONS
fig = sheet("L-2", "Sections")
den = 24
# Section A, looking south: h = -X (east, the bath 1 wall, on the left)
xrA, zrA = (-14, 92), (-14, 214)
ax = scaled_axes(fig, 0.5, 1.1, xrA, zrA, den)
view_title(fig, 0.6, 0.72, "A", "SECTION A, LOWER FLIGHT, LOOKING SOUTH", "1/2\" = 1'-0\"")
slab(ax, -14, 92)
rect(ax, -BATH_T, 0, 0, FL - 12.625, **WALLSTYLE)
rect(ax, -14, FL - 12.625, 0, FL, fc="#e7e1d4", ec=INK, lw=0.9, z=1)
txt(ax, -7, FL - 6.3, "LOFT\nFLOOR", size=5)
hd = C["clerestory"]["passages"][2][2] * 12
line(ax, [(-X_JAMB, 0), (-X_JAMB, hd), (92, hd)], c=GREY, lw=0.6, ls=(0, (4, 2)), z=1)
txt(ax, -X_JAMB + 18, hd - 10, "LIVING ROOM\nOPENING BEYOND", size=5.4, c=GREY)
mapA = lambda u: -(X_FOOT + u)
flight_profile(ax, mapA, 0.0, N_LO, Z_LD, UL)
rect(ax, 0, Z_LD - 4.8, -X_XL, Z_LD, fc="#f3e8cf", ec=INK, lw=0.8, z=3)
rect(ax, -X_XL - 3.48, 0, -X_XL, Z_LD - 4.8, fc="#f3e8cf", ec=INK, lw=0.6, z=3)
txt(ax, -X_XL / 2, Z_LD + 22, "UPPER FLIGHT RISES\nTOWARD THE VIEWER\n(SEE SECTION B)", size=5.2, c=GREY)
for k in range(N_LO + 1):
    hk = mapA((k - 1) * GO) if k else -X_FOOT
    line(ax, [(hk, k * RI), (72, k * RI)], c=LIGHT, lw=0.3, z=1)
for k in range(N_LO):
    dim(ax, (72, k * RI), (72, (k + 1) * RI), 0, fin(RI, 32), size=5.4, ext=False)
dim(ax, (84, 0), (84, Z_LD), 0, frac(Z_LD) + " TO LANDING", size=5.6, ext=False)
dim(ax, (-X_XL, 0), (-X_FOOT, 0), -7.5, frac(UL))
dim(ax, (0, 0), (-X_XL, 0), -7.5)
dim(ax, (-X_FOOT, 0), (-X_JAMB, 0), -7.5, fin(X_FOOT - X_JAMB))
dim(ax, (mapA(0), RI), (mapA(0), RI + HR), -5, fin(HR), size=5.6)
txt(ax, 40, 190, f"Roof underside over this flight is about\n{frac(roof_under(Y_LO1))} above the slab; headroom is not a limit here.", size=5.4, c="#444")
keyline(ax, (mapA(GO * 2.5), nosing_z(0, GO * 2.5) + HR - 0.8), (40, 110), 1)
keyline(ax, (mapA(5.2), nosing_z(0, 5.2)), (62, 70) if False else (60, 34), 2)
keyline(ax, (mapA(14), nosing_z(0, 14) - 12), (30, 8), 3)
keyline(ax, (-X_XL - 1.7, 22), (6, 14), 4)
keyline(ax, (-X_XL / 2, Z_LD - 2.4), (10, 30), 5)

# Section B, looking east: h = -Y (north on the left, clerestory wall on the right)
xrB, zrB = (-112, 30), (-14, 214)
ax = scaled_axes(fig, 5.05, 1.1, xrB, zrB, den)
view_title(fig, 5.1, 0.72, "B", "SECTION B, UPPER FLIGHT AND BALCONY, LOOKING EAST", "1/2\" = 1'-0\"")
slab(ax, -112, 30)
rect(ax, 0, 0, CW_T, 214, **WALLSTYLE)
rect(ax, -112, 0, 0, FL - 12.625, fc="#f4f4f4", ec=GREY, lw=0.5, z=0)
rect(ax, -112, FL - 12.625, 0, FL, fc="#e7e1d4", ec=GREY, lw=0.5, z=0)
txt(ax, -100, 34, "BATH 1 WEST\nWALL BEYOND", size=5.2, c=GREY)
for a, b in ((0.5, RAIL_GAP[0]), (RAIL_GAP[1], 112)):
    rect(ax, -b, FL, -a, FL + RAIL_H, fc="none", ec=GREY, lw=0.5, ls=(0, (4, 2)), z=1)
txt(ax, -30, FL + RAIL_H + 4, "LOFT GUARD BEYOND", size=5.2, c=GREY)
ys = [i * 0.5 for i in range(-224, 1)]
line(ax, [(h, roof_under(-h)) for h in ys if roof_under(-h) < 213.5], c=INK, lw=1.0, z=2)
txt(ax, -40, roof_under(40) + 5, "NORTH ROOF UNDERSIDE", size=5.2, rot=math.degrees(math.atan(-R["north_pitch"] / 12)), c="#333")
rect(ax, -SWITCH["Y"] - 2.3, SWITCH["z"] - 2.3, -SWITCH["Y"] + 2.3, SWITCH["z"] + 2.3, fc=RED, ec=RED, z=6)
rect(ax, -Y_LD1, Z_LD - 4.8, -Y_LD0, Z_LD, **CUTSTYLE)
rect(ax, -Y_LD1, 0, -Y_LD1 + 3.48, Z_LD - 4.8, fc="#f3e8cf", ec=INK, lw=0.5, z=2)
mapB = lambda u: -(Y_LD1 + u)
flight_profile(ax, mapB, Z_LD, N_UP, FL, UU)
rect(ax, -Y_BAL1, FL - 6, -Y_BAL0, FL, **CUTSTYLE)
# balcony guards: north (cut) and west (in elevation)
rect(ax, -Y_BAL1, FL, -Y_BAL1 + 0.96, FL + RAIL_H - 1.44, fc=STEEL, ec=INK, lw=0.5, z=5)
rect(ax, -Y_BAL1 - 0.5, FL + RAIL_H - 1.44, -Y_BAL0 + 0.6, FL + RAIL_H, fc=OAK, ec=INK, lw=0.6, z=6)
rect(ax, -Y_BAL1, FL + 1.2, -Y_BAL0 - 0.6, FL + 2.4, fc=STEEL, ec=INK, lw=0.4, z=5)
nb = 7
sp = (Y_BAL1 - Y_BAL0 - 1.44) / nb
for i in range(1, nb):
    hb = -Y_BAL1 + 0.96 + i * sp
    rect(ax, hb - 0.24, FL + 2.4, hb + 0.24, FL + RAIL_H - 1.44, fc=STEEL, ec=STEEL, lw=0.2, z=5)
rect(ax, -Y_BAL0 - 1.44, FL, -Y_BAL0, FL + RAIL_H - 1.44, fc=STEEL, ec=INK, lw=0.4, z=5)
for yb_ in (Y(yt0f + 0.2), Y(yt1f - 0.2)):
    poly(ax, [(-yb_ - 0.7, FL - 6), (-yb_ + 0.7, FL - 6), (-yb_ + 0.7, FL - 30), (-yb_ - 0.7, FL - 26.4)], fc=STEEL, ec=INK, lw=0.4, z=2)
for k in range(N_UP + 1):
    zk = Z_LD + k * RI
    hk = mapB(max(k - 1, 0) * GO) if k else -Y_LD1
    line(ax, [(hk, zk), (0, zk)], c=LIGHT, lw=0.3, z=1)
for k in range(N_UP):
    dim(ax, (-3, Z_LD + k * RI), (-3, Z_LD + (k + 1) * RI), 0, fin(RI, 32), size=4.8, ext=False)
dim(ax, (CW_T + 6, 0), (CW_T + 6, Z_LD), 0, frac(Z_LD), size=5.6, ext=False)
dim(ax, (CW_T + 6, Z_LD), (CW_T + 6, FL), 0, frac(FL - Z_LD), size=5.6, ext=False)
dim(ax, (CW_T + 14, 0), (CW_T + 14, FL), 0, frac(FL) + " TOTAL RISE, 13 RISERS", size=5.8, ext=False)
for k in (0, N_LO, NR):
    line(ax, [(CW_T, k * RI), (CW_T + 16, k * RI)], c=GREY, lw=0.3, z=1)
dim(ax, (-Y_BAL0, 0), (-Y_LD1, 0), -7.5, frac(UU) + " RUN")
dim(ax, (-Y_LD1, 0), (0, 0), -7.5)
dim(ax, (-Y_BAL1, 0), (-Y_BAL0, 0), -7.5)
dim(ax, (-Y_BAL1, FL), (-Y_BAL1, FL + RAIL_H), 5, fin(RAIL_H), size=5.6)
dim(ax, (-Y_BAL1 + 3, FL), (-Y_BAL1 + 3, roof_under(Y_BAL1 - 3)), 0, frac(HEAD_BAL) + " HEADROOM", size=5.6, ext=False)
dim(ax, (-(Y_BAL0 - NOS), FL), (-(Y_BAL0 - NOS), roof_under(Y_BAL0 - NOS)), 0, frac(HEAD_TOP), size=5.6, ext=False)
txt(ax, -64, 40, f"{ANG:.1f}° NOSING LINE", size=5.4, c=RED) if False else None
keyline(ax, (mapB(20), nosing_z(Z_LD, 20) + HR - 0.8), (-22, 150), 1)
keyline(ax, (mapB(12), nosing_z(Z_LD, 12)), (-40, 76), 2)
keyline(ax, (mapB(24), nosing_z(Z_LD, 24) - 14), (-60, 70) if False else (-48, 104), 3)
keyline(ax, (-(Y_BAL0 + Y_BAL1) / 2, FL - 3), (-100, 112), 5)
keyline(ax, (-Y(yt0f + 0.2) - 0.7, FL - 18), (-104, 90), 6)
keyline(ax, (-Y_BAL1 + 12, FL + 20), (-50, 186), 7)
keyline(ax, (-SWITCH["Y"] - 2.3, SWITCH["z"]), (-70, 44), 8)
keyline(ax, (-Y_LD0 / 2 - 8, Z_LD - 2.4), (-6, 26) if False else (-22, 30), 9)

if PERSON:
    cs = COUCH["Y0"]
    rect(ax, -112, 0, -cs - 6, 17.4, fc="#c9cdc4", ec=INK, lw=0.6, z=2)
    rect(ax, -cs - 6, 0, -cs, 25.2, fc="#b9beb3", ec=INK, lw=0.6, z=2)
    rect(ax, -112, 17.4, -cs - 6, 33, fc="#dfe2dc", ec=GREY, lw=0.4, z=1)
    hc = -Y(PERSON["y"])
    pb = "#5A7896"
    rect(ax, hc - 6, 0, hc - 1.2, P_S + 5.5, fc="#3B4A63", ec=INK, lw=0.4, z=3)
    rect(ax, hc + 1.2, 0, hc + 6, P_S + 5.5, fc="#3B4A63", ec=INK, lw=0.4, z=3)
    rect(ax, hc - 7.2, P_S, hc + 7.2, P_S + 24.5, fc=pb, ec=INK, lw=0.5, z=3)
    rect(ax, hc - 9.6, P_S + 12.6, hc - 7.2, P_S + 24, fc=pb, ec=INK, lw=0.4, z=3)
    rect(ax, hc + 7.2, P_S + 12.6, hc + 9.6, P_S + 24, fc=pb, ec=INK, lw=0.4, z=3)
    rect(ax, hc - 2.4, P_S + 24.5, hc + 2.4, P_S + 28, fc="#C99A78", ec=INK, lw=0.4, z=3)
    rect(ax, hc - 3.7, P_S + 27.6, hc + 3.7, P_CROWN, fc="#C99A78", ec=INK, lw=0.5, z=3)
    rect(ax, hc - 3.8, P_CROWN - 2.4, hc + 3.8, P_CROWN, fc="#4A3626", ec=INK, lw=0.4, z=3)
    dim(ax, (hc + 11, P_CROWN), (hc + 11, P_OVER), 0, fin(P_CLR) + " CLEAR", size=5.8, ext=False)
    line(ax, [(hc, P_OVER), (hc + 13, P_OVER)], c=RED, lw=0.5, z=6)
    line(ax, [(hc, P_CROWN), (hc + 13, P_CROWN)], c=RED, lw=0.5, z=6)
    dim(ax, (hc - 12, 0), (hc - 12, P_CROWN), 0, frac(P_CROWN), size=5.4, ext=False)
    keyline(ax, (hc - 5, P_CROWN - 8), (-104, 60), 10)
kn2 = [(1, f"Handrails both sides, {fin(HR)} above the nosing line, from over the first nosing to over the landing nosing of each flight. Black steel, posts at the ends only."),
       (2, f"Nosing line (dashed red), {ANG:.1f}°. Risers {fin(RI, 32)}, going {fin(GO)}, treads {fin(TD)}, open risers."),
       (3, f"Stringers: white oak in the model, {fin(SW, 16)} thick. Drawn here as {fin(SD_P)} boards (2x12 class); the model's 12\" plumb depth is too shallow to house the {fin(TD)} treads. Size by designer."),
       (4, "3 1/2\" x 3 1/2\" oak posts under the corner landing's west corners."),
       (5, f"Corner landing (A) and balcony (B), cut. Landing 4 3/4\" deep in the model, balcony 6\". Framing by engineer."),
       (6, "Two steel knee braces from the balcony down to the bath 1 wall, about 2'-6\" below the loft floor. Size and anchorage by engineer."),
       (7, f"{fin(RAIL_H)} balcony guards (west in elevation, north cut). Loft guard beyond is open where the balcony meets the loft."),
       (8, "Existing 4 gang switch plate at 44\", under the upper flight. Relocate."),
       (9, "Corner landing, cut, with its west post beyond.")]
if PERSON:
    kn2.append((10, f"6'-0\" person sitting upright at the south end of the couch, as close to the ladder as anyone can sit. Crown {frac(P_CROWN)} above the floor; lowest ladder part over the head {frac(P_OVER)}: {fin(P_CLR)} of clearance. Couch dashed in plan."))
keynotes(fig, 11.15, 10.5, "KEYNOTES", kn2, width=3.05)

# ================================================================ L-3 DETAILS
fig = sheet("L-3", "Details")
# Detail 1: tread and riser profile, 1 1/2" = 1'-0"
den = 12
xr1, zr1 = (-12, 30), (-28, 56)
ax = scaled_axes(fig, 0.6, 1.4, xr1, zr1, den)
view_title(fig, 0.6, 1.0, "1", "TREAD AND RISER DETAIL, TYPICAL", "1\" = 1'-0\"")
mapD = lambda u: u
zb0 = -2 * RI                                       # nosing of tread n sits at (0, 0); treads n-1 .. n+2 drawn
poly(ax, [(u, max(z, -25.5)) for u, z in stringer_poly(mapD, -10 + 0.01, 27, zb0, 99)], fc=OAK, ec=GREY, lw=0.5, z=1)
for j in range(-1, 4):
    rect(ax, j * GO, j * RI - TT, j * GO + TD, j * RI, fc=TREAD, ec=INK, lw=0.9, z=4)
line(ax, [(-10, -10 * RI / GO), (14.5, 14.5 * RI / GO)], c=RED, lw=0.6, ls=(0, (6, 3)), z=5)
poly(ax, [(-3, -3 * RI / GO + HR), (3 * GO, 3 * RI + HR), (3 * GO, 3 * RI + HR - RH_T), (-3, -3 * RI / GO + HR - RH_T)], fc=STEEL, ec=INK, lw=0.5, z=6)
dim(ax, (2 * GO + TD, RI), (2 * GO + TD, 2 * RI), -3.5, fin(RI, 32), size=6)
dim(ax, (GO, RI), (2 * GO, RI), 6, fin(GO), size=6)
dim(ax, (0, -TT), (TD, -TT), -4.5, fin(TD), size=6)
dim(ax, (TD - NOS, 0), (TD, 0), 2.3, fin(NOS), size=5.6)
dim(ax, (-0.5 + 0, -TT), (-0.5, 0), 2.0, fin(TT), size=5.6)
dim(ax, (2 * GO, 2 * RI), (2 * GO, 2 * RI + HR), 8.5, fin(HR), size=6)
dim(ax, (3 * GO + TD + 1.5, 2 * RI), (3 * GO + TD + 1.5, 3 * RI - TT), -1.5, fin(RI - TT), size=5.6)
ax.add_patch(matplotlib.patches.Arc((-6, -6 * RI / GO), 12, 12, theta1=0, theta2=ANG, lw=0.5, zorder=6))
line(ax, [(-6, -6 * RI / GO), (2, -6 * RI / GO)], c=GREY, lw=0.4)
txt(ax, 3.5, -6 * RI / GO + 2.6, f"{ANG:.1f}°", size=6, ha="left")
keyline(ax, (TD / 2, -TT / 2), (16, -14), 1)
keyline(ax, (2 * GO + TD + 0.5, 2 * RI + 4), (24, 26), 2)
keyline(ax, (-3, -3 * RI / GO + 1), (-7, 12), 3)
keyline(ax, (10, 10 * RI / GO - 14), (22, -6) if False else (24, 4), 4)
keyline(ax, (3 * GO - 3, 3 * RI + HR - 0.8), (4, 44), 5)

# Detail 2: across a flight, 1 1/2" = 1'-0"
den = 12
xr2, zr2 = (-12, 44), (-26, 44)
ax = scaled_axes(fig, 5.0, 1.4, xr2, zr2, den)
view_title(fig, 5.0, 1.0, "2", "SECTION ACROSS A FLIGHT AT A NOSING", "1\" = 1'-0\"")
rect(ax, -12, -28, -1.32, 46, **WALLSTYLE)
for v0 in (0, WN - SW):
    rect(ax, v0, STR_TOP - STR_PLUMB, v0 + SW, STR_TOP, fc=OAK, ec=INK, lw=0.8, z=2)
rect(ax, SW, -TT, WN - SW, 0, fc=TREAD, ec=INK, lw=0.8, z=3)
for vc in (SW / 2, WN - SW / 2):
    rect(ax, vc - RW / 2, HR - RH_T, vc + RW / 2, HR, fc=STEEL, ec=INK, lw=0.6, z=4)
    rect(ax, vc - 0.6, STR_TOP, vc + 0.6, HR - RH_T, fc="none", ec=GREY, lw=0.5, ls=(0, (3, 2)), z=2)
dim(ax, (0, STR_TOP - STR_PLUMB), (WN, STR_TOP - STR_PLUMB), -3, frac(WN) + " OVERALL")
dim(ax, (SW, 0), (WN - SW, 0), 5, fin(WN - 2 * SW) + " CLEAR, 20\" MIN")
dim(ax, (WN - SW, -10), (WN, -10), -2.5 if False else 3, fin(SW), size=5.6)
dim(ax, (-1.32, 38), (0, 38), 3, fin(1.32), size=5.6)
dim(ax, (-1.32, HR + 3.5), (SW / 2 - RW / 2, HR + 3.5), 2.0, fin(RAIL_CLR_UP, 32), size=5.6)
dim(ax, (WN + 2, 0), (WN + 2, HR), 0, fin(HR) + " (30\" TO 34\")", size=5.8, ext=False)
line(ax, [(WN - SW, 0), (WN + 3.2, 0)], c=GREY, lw=0.3)
line(ax, [(WN, HR), (WN + 3.2, HR)], c=GREY, lw=0.3)
keyline(ax, (WN - SW / 2, HR - 0.8), (WN + 6, HR + 8), 5)
keyline(ax, (WN - SW / 2, -14), (WN + 6, -16), 4)
keyline(ax, (-6, 10), (-6, 10), 6) if False else keyline(ax, (-1.4, 10), (-6, 16), 6)
keyline(ax, (8, -TT / 2), (10, -10), 1)

# Detail 3: balcony west guard, 3/4" = 1'-0"
den = 16
L3 = Y_BAL1 - Y_BAL0
xr3, zr3 = (-6, 36), (-36, 46)
ax = scaled_axes(fig, 11.4, 1.4, xr3, zr3, den)
view_title(fig, 10.9, 1.0, "3", "BALCONY GUARD, WEST SIDE", "3/4\" = 1'-0\"")
rect(ax, -2, -6, L3 + 2, 0, **CUTSTYLE)
for h0 in (0, L3 - 1.44):
    rect(ax, h0, 0, h0 + 1.44, RAIL_H - 1.44, fc=STEEL, ec=INK, lw=0.5, z=3)
rect(ax, -0.5, RAIL_H - 1.44, L3 + 0.5, RAIL_H, fc=OAK, ec=INK, lw=0.6, z=4)
rect(ax, 0, 1.2, L3, 2.4, fc=STEEL, ec=INK, lw=0.4, z=3)
nb = 7
sp = (L3 - 1.44) / nb
for i in range(1, nb):
    hb = 0.72 + i * sp
    rect(ax, hb - 0.24, 2.4, hb + 0.24, RAIL_H - 1.44, fc=STEEL, ec=STEEL, lw=0.2, z=3)
for yb_ in (Y(yt1f - 0.2) - Y_BAL0, Y(yt0f + 0.2) - Y_BAL0):
    poly(ax, [(yb_ - 0.7, -6), (yb_ + 0.7, -6), (yb_ + 0.7, -30), (yb_ - 0.7, -26.4)], fc=STEEL, ec=INK, lw=0.4, z=2)
dim(ax, (L3 + 2, 0), (L3 + 2, RAIL_H), 0, fin(RAIL_H), size=5.8, ext=False)
dim(ax, (0, -6), (L3, -6), -9 if False else 0, None, ext=False) if False else None
dim(ax, (-2, -6), (L3 + 2, -6), 0, None, ext=False) if False else dim(ax, (0, -30), (L3, -30), -3, frac(L3))
txt(ax, L3 / 2, 21, "BALUSTERS:\n4\" SPHERE\nMUST NOT PASS", size=5.2, bg=True)
ftxt(fig, 10.9, 7.3, "The model draws 5 balusters in this guard, about\n4 1/4\" clear. Space them so a 4\" sphere cannot\npass (R312.1.3). 7 bays shown, about 3 3/16\" clear.", fontsize=6.2, color=RED)
kn3 = [(1, f"White oak tread, {fin(TT)} thick in the model (species and thickness by designer), housed in the stringers, open riser."),
       (2, f"Open riser: {fin(RI - TT)} clear between treads. See code check C6."),
       (3, f"Nosing line, {ANG:.1f}°. The 3 1/2\" overlap is the tread nosing over the tread below."),
       (4, f"Stringer {fin(SW)} thick (model), drawn as an {fin(SD_P)} board. The model's 12\" plumb depth (about {fin(12 * COS)} board) cannot house the treads. Size by designer."),
       (5, f"Handrail, black steel {fin(RW)} x {fin(RH_T)} bar in the model, on top of the stringer. Specify a graspable section per R311.7.8.5."),
       (6, "Wall: bath 1 west wall at the upper flight, clerestory wall at the lower flight (stringer gap 1 5/8\" there).")]
keynotes(fig, 0.6, 10.5, "KEYNOTES", kn3[:3], width=5.0)
keynotes(fig, 6.0, 10.5, " ", kn3[3:], width=5.0)

# ================================================================ L-4 SCHEDULE, CODE, FIELD VERIFY
fig = sheet("L-4", "Schedule and code")
f = lambda x, y, s, **k: ftxt(fig, x, y, s, **k)
f(0.6, 10.5, "RISER SCHEDULE", fontsize=9, fontweight="bold")
f(0.6, 10.28, "Heights to the top of each tread at its nosing, above the finished slab, nearest 1/16\".", fontsize=6.4, color="#444")
cols = [0.6, 1.15, 2.0, 3.35]
for c_, h_ in zip(cols, ["Riser", "Height", "Element", "Nosing location in plan"]):
    f(c_, 10.02, h_, fontsize=6.8, fontweight="bold")
for k in range(1, NR + 1):
    if k < N_LO:
        el, loc = f"Tread {k}", f"{frac(-(X_FOOT + (k - 1) * GO))} west of bath 1 wall"
    elif k == N_LO:
        el, loc = "Corner landing", f"{frac(-(X_FOOT + (k - 1) * GO))} west of bath 1 wall"
    elif k < NR:
        el, loc = f"Tread {k}", f"{frac(Y_LD1 + (k - N_LO - 1) * GO)} north of clerestory wall"
    else:
        el, loc = "Balcony, loft floor", f"{frac(Y_LD1 + (k - N_LO - 1) * GO)} north of clerestory wall"
    for c_, s_ in zip(cols, [str(k), frac(k * RI), el, loc]):
        f(c_, 9.82 - (k - 1) * 0.158, s_, fontsize=6.6)

f(6.6, 10.5, "FIELD VERIFY AND OPEN ITEMS", fontsize=9, fontweight="bold")
fv = [("F1", f"Total rise. Model: 9'-0\" top plate (tape measured) + 11 7/8\" open web floor trusses + 3/4\" subfloor = {frac(FL)}. Measure slab to finished loft floor, including any finish flooring, and divide by 13. Thirteen risers work up to 10'-3 1/2\" (9 1/2\" each)."),
      ("F2", "Wall faces. Plan dimensions use the model's finished faces: bath 1 west wall face at plan x 31.122 ft and clerestory wall north face at plan y 34.616 ft (model origin: outside NW corner of the slab, x east, y south). Living room opening east jamb at plan x 26.914 ft."),
      ("F3", f"The first nosing sits only {fin(X_FOOT - X_JAMB)} east of the living room opening's east jamb ({fin(X_FOOT - 0.48 - X_JAMB)} at the stringer toe). Check against the jamb casing."),
      ("F4", f"The upper flight's east handrail is {fin(RAIL_CLR_UP, 32)} off the bath 1 wall. Move the flight or the rail at least 1/32\" west to get the 1 1/2\" minimum."),
      ("F5", "The 4 gang switch plate on the bath 1 west wall (44\" up) sits under the upper flight. Needs a new location."),
      ("F6", "Structure: corner landing on two posts plus ledgers on two walls; balcony cantilevered off the interior bath 1 wall on two steel knee braces. Engineer to size, and to confirm the loft floor framing can take the balcony."),
      ("F7", f"Stringers: the model's 12\" plumb depth is only about {fin(12 * COS)} of board at {ANG:.0f}°. These sheets draw {fin(SD_P)} boards so the treads can be housed."),
      ("F8", f"Both landings are about {round(WN + 1)}\" (the ladder width), not the 36\" a stairway landing needs. Inspector to accept for a ships ladder."),
      ("F9", "Barn doors are assumed hung on the dining side. Hung on the living room side, the east leaf would hit the ladder."),
      ("F10", "Headroom is checked to the north roof underside only; no beams, fans or lights are modeled over the ladder.")]
yy = 10.2
for n, s in fv:
    f(6.6, yy, n, fontsize=6.5, fontweight="bold")
    lines = textwrap.wrap(s, 92)
    for j, ln in enumerate(lines):
        f(7.0, yy - j * 0.145, ln, fontsize=6.4)
    yy -= 0.145 * len(lines) + 0.08

f(0.6, 5.85, "CODE CHECK: Residential Code of Ohio (OAC 4101:8, 2019 RCO, based on the 2018 IRC; section numbers assumed to match the IRC)", fontsize=9, fontweight="bold")
code = [("C1", "R311.7.12", "Ships ladder clear width at and below handrails, 20\" min", f"{fin(WN - 2 * SW)}", "OK"),
        ("C2", "R311.7.12.1", "Treads: 5\" min tread depth, 8 1/2\" min tread depth plus nosing", f"{fin(GO)} going, {fin(TD)} tread", "OK"),
        ("C3", "R311.7.12.1", "Riser height 9 1/2\" max", f"{fin(RI, 32)}", "OK"),
        ("C4", "R311.7.12.2", "Handrails on both sides, 30\" to 34\" above the nosings", f"both sides, {fin(HR)}", "OK"),
        ("C5", "R311.7.12", "Ships ladders are not a means of egress unless an exception applies. The 2021 IRC allows them for lofts of 200 sq ft or less with no kitchen or bath; confirm the 2018 based Ohio wording.", "loft 134 sq ft, no kitchen or bath", "CONFIRM"),
        ("C6", "R311.7.5.1", "Open risers: 4\" sphere limit where total rise is over 30\". Unclear if it applies to a ships ladder.", f"{fin(RI - TT)} open", "CONFIRM"),
        ("C7", "R311.7.5.1, .2", "Riser heights and tread depths uniform within 3/8\" in a flight", "all equal", "BUILD TO"),
        ("C8", "R311.7.2", "Headroom 6'-8\" min", f"{frac(HEAD_BAL)} min, at balcony guard", "OK"),
        ("C9", "R311.7.6", "Stair landings 36\" min in the direction of travel; R311.7.12 is silent on ladder landings", f"about {round(WN + 1)}\" each", "CONFIRM"),
        ("C10", "R311.7.8.3, .4", "Handrails continuous for each flight; 1 1/2\" min clear to the wall", f"{fin(RAIL_CLR_UP, 32)} upper east rail", "ADJUST"),
        ("C11", "R311.7.8.5", "Handrail graspability (Type I 1 1/4\" to 2\" round, or equivalent)", "1 1/2\" x 1 9/16\" bar", "SPECIFY"),
        ("C12", "R312.1.1, .2", "Guards 36\" min where the walking surface is over 30\" above the floor below", f"{fin(RAIL_H)} balcony and loft", "OK"),
        ("C13", "R312.1.3", "Guard openings must not pass a 4\" sphere", "model about 4 1/4\"", "ADJUST"),
        ("C14", "R312.1.1", "Open sides of the ladder flights carry handrails only, no guard. Inspector to accept.", "handrails only", "CONFIRM"),
        ("C15", "R301.5", "Live loads: stairs 40 psf and 300 lb point; guards and handrails 200 lb", "balcony cantilever", "ENGINEER"),
        ("C16", "R310", "If the loft is used for sleeping (cabinet bed), it needs an emergency escape opening", "loft east window", "CONFIRM")]
cc = [0.6, 1.05, 1.95, 9.0, 11.55]
for c_, h_ in zip(cc, ["", "Section", "Requirement", "As modeled", "Status"]):
    f(c_, 5.55, h_, fontsize=6.8, fontweight="bold")
yy = 5.35
for row in code:
    req = textwrap.wrap(row[2], 118)
    for c_, s_ in zip(cc, row):
        col = RED if s_ in ("CONFIRM", "ADJUST", "ENGINEER", "SPECIFY") else INK
        if c_ == cc[2]:
            for j, ln in enumerate(req):
                f(c_, yy - j * 0.14, ln, fontsize=6.3)
        else:
            f(c_, yy, s_, fontsize=6.3, color=col, fontweight="bold" if c_ == cc[-1] else "normal")
    yy -= 0.14 * len(req) + 0.07
f(0.6, yy - 0.08, "The Ohio text of section R311 was not available to check line by line. Confirm all items marked CONFIRM with the local building department.", fontsize=6.3, color="#444")

# ---------------------------------------------------------------- write
pdf_path = os.path.join(OUT, "loft_ships_ladder_drawings.pdf")
with PdfPages(pdf_path) as pdf:
    for num, fg in SHEETS:
        pdf.savefig(fg)
        fg.savefig(os.path.join(OUT, f"loft_ships_ladder_{num}.png"), dpi=170)
print("wrote", pdf_path)
