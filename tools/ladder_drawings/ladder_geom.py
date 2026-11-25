"""Shared geometry for the loft corner ships ladder structure: tube stringers, landing, balcony, posts and rails.

Local inch coordinates: a = west of the bath 1 wall's west face, b = north of the clerestory wall's north face, z = above the slab.
Everything is derived from model/config.toml [loft], the same numbers model/ladder_options.py draws in the walkthrough.
PRELIMINARY: for an engineer's review, not for construction.
"""
import math, os, tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
L = tomllib.load(open(os.path.join(HERE, "..", "..", "model", "config.toml"), "rb"))["loft"]
MONO = L.get("ladder_stringer") == "mono"         # one centre stringer (Maxwell 11/22/2026) instead of a tube under each side
assert L.get("ladder_stringer") in ("tube", "mono")
NR, N_LO = L["ladder_risers"], int(L.get("ladder_lower_risers", 5))
N_UP = NR - N_LO
# Round 8 (Maxwell 11/24/2026): two tread options. ladder_tread_strips = true is the 2 in steel strip under each tread (round 3 on);
# false drops the strips and their bracket flanges: the bracket seat runs the web's whole top edge, the oak is ladder_tread_thick_in
# thick and the riser lips grow so the riser opening stays under the 4 in sphere. Env LADDER_TREAD_STRIPS=0/1 and
# LADDER_TREAD_THICK_IN override the config (the exploded view builds both).
_env = os.environ.get
_strip_cfg = L.get("ladder_tread_strips", True)
_strip_opt = _env("LADDER_TREAD_STRIPS", "decor" if _strip_cfg == "decor" else ("1" if _strip_cfg else "0"))
STRIPS = (_strip_opt == "1") if MONO else True
# Round 10 (Maxwell 11/24/2026): a third option, LADDER_TREAD_STRIPS=decor (config ladder_tread_strips = "decor"): the no strip structure
# (thick oak, long bracket seats) plus a strip under each tread for its look only. It is a piece of stock L 2 x 1 x 1/8 angle: the 2 in leg
# hangs where the structural strip was (just in front of the bracket webs), the 1 in leg points to the nosing under the oak and takes three
# wood screws up into the tread. It carries nothing and touches no steel.
DECOR = MONO and _strip_opt == "decor"
DECOR_ANG = (2.0, 1.0, 0.125)                     # hanging leg, screw leg, thickness
TT = float(_env("LADDER_TREAD_THICK_IN", L.get("ladder_tread_thick_in", 1.44 if STRIPS else 1.75)))
TTD = 1.44                                        # oak deck on the corner landing and the balcony (stays 1 7/16 in either way)
RI, GO, TD = L["floor_height"] * 12 / NR, L["ladder_going_in"], L["ladder_tread_in"]
TW, TDp = L.get("ladder_mono_in", [4.0, 4.0]) if MONO else L.get("ladder_tube_in", [2.0, 3.0])
WT = float(os.environ.get("LADDER_STR_T", L.get("ladder_stringer_wall_in", 0.25))) if MONO else 0.1875   # nominal stringer wall (cost study 11/24/2026: env LADDER_STR_T)
FW, FD = 2.0, 3.0                                 # landing and balcony frame tube, on edge
GA11 = 0.1196                                     # 11 gauge tube wall
FT_L, FT_B = (GA11, GA11) if MONO else (0.1875, 0.1875)   # frame tube walls (cost pass, Maxwell 11/24/2026: 3 x 2 x 11 ga for both platforms)
CONT_RAIL = MONO and bool(L.get("ladder_rail_continuous", False))   # round 3's one curved rail; Maxwell 11/24/2026: back to straight rails between posts
WALL_RAIL = bool(L.get("ladder_wall_rail", True))   # wall side handrails; code wants rails on both sides of a ships ladder, Maxwell asked to hide them for now
SPHERE_GAP = 3.875                               # no strip option: riser lip top to the next tread's underside, under the 4 in sphere
RT, RH = ((0.75, 2.0) if STRIPS else (0.75, RI - TT - SPHERE_GAP - (DECOR_ANG[0] if DECOR else 0.0))) if MONO else (0.0, 0.0)   # round 11: the decor angle's 2 in leg closes the top of the riser, so its lip is that much shorter      # mono: an oak riser lip behind every tread; the 2 in steel strip under the tread above closes the rest (Maxwell 11/22/2026 round 3)
WEB0, BOLT_N, LAP, SEAT_W = (4.5, 1.5, 3.0, 3.5) if MONO else (3.75, 1.25, 2.25, 2.5)   # tread bracket: web start behind the nosing, bolt line below the tube top, lap, seat width
# Mono tread support (Maxwell 11/22/2026 PM): a flat plate ARM on edge crosses over the stringer under each tread and reaches near both tread ends.
# Each bracket web has a flange folded off its vertical front edge that bolts to the arm, so the load goes into the webs in their own plane.
# The earlier seat only bracket (SEAT_W wide bent seat) bent like a diving board: tools/ladder_drawings/bracket_solid_fea.py has that study.
# Round 3 (Maxwell 11/22/2026 night): the arm is now a narrow STRIP of constant depth, one bolt through each bracket flange, a screw tab at each
# end into the tread. It hangs just behind the riser lip of the tread below, so it is also the top of the riser and the lip can be shorter.
BRKT_T = 0.25                                     # strip, shoe, saddle and clip plate
WEB_T = float(L.get("ladder_bracket_plate_in", 0.1875)) if (MONO and not STRIPS) else BRKT_T   # tread bracket plate (cost pass, Maxwell 11/24/2026: 3/16, solid FEA 10 to 12 ksi away from corners)
ARM_D, ARM_END = 2.0, 1.2                         # strip depth; its ends stop this far inside the tread ends
ARM_FL, SEAT_TAB, FOOT_W = 1.75, (1.5 if STRIPS else float(L.get("ladder_seat_tab_in", 2.5))), 3.5         # web's bolting flange, the small seat tab behind it, first bracket's foot flange
SEAT_S = WEB0 + (1.0 if STRIPS else 0.0)
SEAT_LAG_V = 0.3 if STRIPS else 0.25                 # lag line, out from the seat's centre (away from the bend)
SEAT_LAG = (0.25, 2.5) if STRIPS else (0.3125, 1.5)   # lag (dia, length) up through each seat into the tread: round 8 no strip option uses 5/16 x 1 1/2


def seat_lags(uk):
    """u of the lags up through each bracket seat (two with the strips, three spread along the longer seat without)"""
    if STRIPS:
        return (uk + 6.5, uk + 8.0)
    u0, u1 = uk + SEAT_S + 0.75, uk + SEAT_E - 0.75   # round 10: the seat stops where the web's riser corner starts to round
    return (u0, (u0 + u1) / 2, u1)          # seat tab starts 1 in behind the flange fold, so the two bends are not on top of each other
FLANGE_BOLT = 1.0                                 # the one flange bolt, this far below the tread
STRIP_TAB = 1.4                                   # screw tabs at the strip ends: this far in from each end, to the screw; they fold toward the back of the tread (Maxwell 11/23/2026)
WN, GAP = L["ladder_width_in"], L["ladder_wall_gap_in"]
HR = L.get("ladder_handrail_in", 32.0)
SL = RI / GO
ANG = math.atan(SL)
PL = TDp / math.cos(ANG)                          # tube depth measured plumb
ZP, FL = N_LO * RI, NR * RI                       # corner landing top, loft floor
TK = L.get("ladder_platform_in", TTD + FD)        # platform build up: oak deck on a tube frame
XL = WN + GAP                                     # open (west) edge of the upper flight and of both platforms
NOSE = L.get("ladder_landing_nosing_in", TD - GO)  # oak nosing past each platform's frame; 0 = the platform's own edge is the top nosing (Maxwell 11/22/2026)
UL = (N_LO - 1) * GO + NOSE                       # lower flight, first nosing to the landing edge
UU = (N_UP - 1) * GO + NOSE
B0 = XL + 1.2                                     # upper flight's first nosing
BAL_S, BAL_N = B0 + UU, B0 + UU + WN + 1.2        # balcony
BAL_N0 = BAL_N                                    # round 9's north edge (the plate line the north guard posts stood outside)
POST, RAIL, RAIL_T = 2.0, 1.5, (GA11 if MONO else 0.1875)   # square tube posts and rails (cost pass 11/24/2026: 11 ga walls)
POST_T = GA11 if MONO else 0.1875                 # 2 x 2 posts, knee braces and knee posts
GUARD_H = 36.0
PICKET = 0.5
# Round 10 (Maxwell 11/24/2026): the balcony grows out to its rail lines: north to the outer face of the north guard posts, which stay put,
# and west to the outer face of the west posts. The posts stand at the corners: the north east one is the north knee frame's wall post run
# up in one piece to the guard rail; the west two hold the frame through a corner plate on their inside face (nothing on the stair side).
if MONO:
    BAL_N = BAL_N0 + 0.375 + POST
BAL_W = XL + POST if MONO else XL                 # the deck's west edge


class Flight:
    def __init__(self, name, z0, nr, ab, zf=None):
        self.name, self.z0, self.nr, self.ab = name, z0, nr, ab          # ab(u, v) -> (a, b)
        self.zf = zf = z0 if zf is None else zf                          # level the tube foot stands on (the upper mono stringer stands on the landing frame, past the end of the oak)
        self.zn = lambda u: z0 + RI + u * SL                             # nosing line
        self.zl = lambda u: z0 + RI + (u - TD - RT) * SL - TT            # tube top
        self.zc = lambda u: self.zl(u) - PL / 2                          # tube centreline
        self.zu = z0 + nr * RI - TK                                      # underside of the platform at the head
        self.u0 = TD + RT + (zf - z0 - RI + TT) / SL                     # tube top meets the foot level
        self.u1 = self.u0 + PL / SL
        self.u2 = TD + RT + (self.zu - z0 - RI + TT) / SL                          # tube top meets the platform underside
        self.u3 = self.u2 + PL / SL
        self.ufc, self.uhc = self.u0 + PL / 2 / SL, self.u2 + PL / 2 / SL    # centreline at the foot and head cuts
        self.vt = (WN / 2,) if MONO else (TW / 2, WN - TW / 2)           # tube centrelines: open side, wall side

    def p(self, u, v, z):
        a, b = self.ab(u, v)
        return (a, b, z)

    def uk(self, k):
        return (k - 1) * GO

    def bolt_u(self, k):                                                 # centroid of tread k's two bracket bolts, along u
        return self.uk(k) + WEB0 + 6.25 * math.cos(ANG) + BOLT_N * math.sin(ANG)


LOWER = Flight("lower", 0.0, N_LO, lambda u, v: (XL + UL - u, XL - v), BRKT_T if MONO else None)   # round 8: the tube stands on the floor shoe's 1/4 base    # climbs east, open side north
UPPER = Flight("upper", ZP, N_UP, lambda u, v: (XL - v, B0 + u), ZP - TTD if MONO else None)          # climbs north, open side west
FLIGHTS = (LOWER, UPPER)

ZLF, ZBF = ZP - TTD - FD / 2, FL - TTD - FD / 2    # frame centre heights: landing, balcony
A_LH = XL + UL - LOWER.uhc                        # landing header, over the lower tubes' heads (round 6 moves it, below)
# Round 4 (Maxwell 11/23/2026): the upper stringer leans like a ladder. Its top runs past the plumb cut line and is notched: the part above the
# balcony frame's underside stops against the head beam's south face (U_BEAR), the rest passes under the beam to its north face (U_END).
# Its foot is cut plumb against the landing's north beam and stands on one 3 x 3 post. Angle clips lock both ends.
# Round 5 (Maxwell 11/23/2026): the head beam moves north by its width and the stringer ends in ONE plumb cut against its south face, the
# tube's top trimmed level at the balcony frame's top (the oak's underside), so the beam's full depth bears on the full tube wall: no tongue
# under the beam, no relief hole. The foot is cut level and sits flat on a level saddle on the post (direct bearing, no wedge); a short
# plumb face stays against the landing's north beam.
U_BEAR = UPPER.u2 + 1.0 + FW if MONO else None
U_END = U_BEAR                                     # (round 4's under beam tongue is gone)
Z_TRIM = ZBF + FD / 2 if MONO else None            # stringer top trimmed level here, near its head
U_TRIM = UPPER.u2 + (Z_TRIM - UPPER.zu) / SL if MONO else None
U_FOOT = UPPER.u0 if MONO else None                # plumb cut foot, against the landing's north beam
L_SEAT = 3.75                                      # level bearing cut at the foot, this long from the plumb face (covers the saddle)
Z_SEAT = UPPER.zl(U_FOOT) - PL + L_SEAT * SL if MONO else None   # level foot cut = top of the saddle seat
# Round 6 (Maxwell 11/24/2026): the lower stringer's top copies the upper one: plumb cut bearing on the landing header (moved along the
# flight by the same amount), top trimmed level at the landing frame's top, the SAME head clips (4 identical parts). The saddle's cheeks
# come up both sides of the upper stringer under the (now rounded) first bracket and bolt through it; the foot clip is a tab bent out of
# each cheek onto the landing's north beam. Tread bracket corners are rounded.
U_BEAR_L = LOWER.u2 + 1.0 + FW if MONO else None   # lower stringer's plumb head cut, against the landing header's face
Z_TRIM_L = ZLF + FD / 2 if MONO else None
U_TRIM_L = LOWER.u2 + (Z_TRIM_L - LOWER.zu) / SL if MONO else None
if MONO:
    A_LH = XL + UL - (U_BEAR_L + FW / 2)


def head_cut(f):
    """(u of the plumb head cut, level trim height, u where the trim meets the tube top, beam centre height) for a mono flight"""
    return (U_BEAR, Z_TRIM, U_TRIM, ZBF) if f is UPPER else (U_BEAR_L, Z_TRIM_L, U_TRIM_L, ZLF)


def head_clip(f):
    """one stringer head clip in its flight's (u, z): tube leg outline, beam leg (z0, z1) [2.25 wide off the beam face], bolts.
    Identical for both flights (same slope, same platform build up)."""
    ub, zt, ut, zbeam = head_cut(f)
    ua, xq = ub - 2.25, ut - 0.15 / SL
    leg = [(ua, f.zu - 3.0), (ub - BRKT_T, f.zu - 3.0), (ub - BRKT_T, zt - 0.25), (xq, zt - 0.25), (ua, f.zl(ua) - 0.1)]
    return dict(leg=leg, beam=(f.zu - 3.0, zt - 0.25), tube_bolt=(ub - 1.25, f.zu - 1.5), beam_bolt_z=zbeam, ub=ub)


def _fillet(pts, i, r, n=10, cap=0.45):
    p, a, b = pts[i], pts[i - 1], pts[(i + 1) % len(pts)]
    u1 = ((a[0] - p[0]), (a[1] - p[1])); l1 = math.hypot(*u1); u1 = (u1[0] / l1, u1[1] / l1)
    u2 = ((b[0] - p[0]), (b[1] - p[1])); l2 = math.hypot(*u2); u2 = (u2[0] / l2, u2[1] / l2)
    th = math.acos(max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1])))
    t = min(r / math.tan(th / 2), cap * l1, cap * l2)
    r = t * math.tan(th / 2)
    bx, by = u1[0] + u2[0], u1[1] + u2[1]; lb = math.hypot(bx, by); bx, by = bx / lb, by / lb
    c = (p[0] + bx * r / math.sin(th / 2), p[1] + by * r / math.sin(th / 2))
    q1, q2 = (p[0] + u1[0] * t, p[1] + u1[1] * t), (p[0] + u2[0] * t, p[1] + u2[1] * t)
    a1, a2 = math.atan2(q1[1] - c[1], q1[0] - c[0]), math.atan2(q2[1] - c[1], q2[0] - c[0])
    d = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
    return [(c[0] + r * math.cos(a1 + d * j / n), c[1] + r * math.sin(a1 + d * j / n)) for j in range(n + 1)]


def _sweep(pts, i, t1, t2, n=16):
    """a big smooth corner: quadratic curve from t1 back along the edge before vertex i to t2 along the edge after it"""
    p, a, b = pts[i], pts[i - 1], pts[(i + 1) % len(pts)]
    to = lambda q, t: (p[0] + (q[0] - p[0]) * t / math.hypot(q[0] - p[0], q[1] - p[1]), p[1] + (q[1] - p[1]) * t / math.hypot(q[0] - p[0], q[1] - p[1]))
    s0, s1 = to(a, t1), to(b, t2)
    return [((1 - x) ** 2 * s0[0] + 2 * (1 - x) * x * p[0] + x * x * s1[0], (1 - x) ** 2 * s0[1] + 2 * (1 - x) * x * p[1] + x * x * s1[1]) for x in (j / n for j in range(n + 1))]


WEB_SWEEP = (2.4, 3.3)                             # round 6: the web's bottom front corner swept back this far along its two edges
WEB_R_FRONT, WEB_R_BACK = 0.4, 1.0                 # and its other two corners on the tube side rounded


WEB_EDGE = 1.0                                     # round 7: web edge this far round each stringer bolt (2.3 bolt diameters)
WEB_DROP = 1.0                                     # and its front edge runs this far below the flange's foot before it rounds away
WEB_R_DROP = 2.0                                   # round 10 (Maxwell 11/24/2026): the front edge's bottom corner and the
WEB_R_RISER = WEB_EDGE                             # corner by the riser rounded to the bolt margin radius


def _hull(pts):
    """convex hull, counter clockwise (monotone chain)"""
    pts = sorted(set(pts))
    cr = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for q in pts:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], q) <= 1e-12:
            lo.pop()
        lo.append(q)
    for q in reversed(pts):
        while len(hi) >= 2 and cr(hi[-2], hi[-1], q) <= 1e-12:
            hi.pop()
        hi.append(q)
    return lo[:-1] + hi[:-1]


def bracket_bolts(f, k):
    """tread k's two bracket bolts through the stringer, (u, z)"""
    uk = f.uk(k)
    a0 = uk + WEB0
    nx, nz = math.sin(ANG), -math.cos(ANG)
    return [(a0 + s * math.cos(ANG) + nx * BOLT_N, f.zl(a0) + s * math.sin(ANG) + nz * BOLT_N) for s in (4.25, 8.25)]


def bracket_web(f, k):
    """tread k's bracket web outline in its flight's (u, z). Corners at the tread (A, B) stay square: the flange and the seat tab fold
    off them. Round 7 (Maxwell 11/24/2026): every web but the lower flight's foot bracket is the smooth hull of the flange edge and a
    1 in margin round its two stringer bolts, so nothing hangs down past the bolts (the saddle's cheeks under the first upper bracket
    are flat topped). The foot bracket keeps the round 6 outline down to its slab flange."""
    uk, zk = f.uk(k), f.z0 + k * RI - TT
    nx, nz = math.sin(ANG), -math.cos(ANG)
    A, B = (uk + WEB0, zk), (uk + TD + RT, zk)
    C = (A[0], f.zl(A[0]))
    D, E = (C[0] + nx * LAP, C[1] + nz * LAP), (B[0] + nx * LAP, B[1] + nz * LAP)
    raw = [A, C, D, E, B]
    if not MONO:
        return raw
    if True:                                       # round 8: the lower foot bracket is gone (the floor shoe takes the foot), so tread 1 gets a standard web
        F = (A[0], zk - ARM_D - WEB_DROP)
        cl = [(bu + WEB_EDGE * math.cos(2 * math.pi * j / 48), bz + WEB_EDGE * math.sin(2 * math.pi * j / 48)) for bu, bz in bracket_bolts(f, k) for j in range(48)]
        h = _hull([A, B, F] + cl)                  # counter clockwise; start at A going down the front edge (A, F, ..., B)
        i = h.index(A)
        h = h[i:] + h[:i]
        if h[1] != F:
            h = [h[0]] + h[1:][::-1]
        assert h[1] == F and h[-1] == B, "bracket web hull"
        return [A] + _fillet(h[0:3], 1, WEB_R_DROP, cap=0.6) + h[2:-1] + _fillet([h[-2], B, A], 1, WEB_R_RISER, cap=0.6)
    mid = _sweep(raw, 2, *WEB_SWEEP)
    pts = [A] + _fillet([A, C, mid[0]], 1, WEB_R_FRONT) + mid + _fillet([mid[-1], E, B], 1, WEB_R_BACK) + [B]
    return pts


SEAT_E = (bracket_web(UPPER, 2)[-1][0] - UPPER.uk(2)) if MONO else TD + RT   # round 10: seat tab's back end, where the rounded riser corner starts


STRIP_R = 1.5                                      # round 7: the tread strips' bottom end corners rounded this much (Maxwell 11/24/2026)


def decor_strip(f, k):
    """the decorative angle under tread k: (hanging leg (u0, u1, z0, z1), screw leg (u0, u1, z0, z1), v range, screw points [(u, v, z)])"""
    uk, zk = f.uk(k), f.z0 + k * RI - TT
    h, w, t = DECOR_ANG
    a = uk + WEB0
    v0, v1 = ARM_END, WN - ARM_END
    return ((a - t, a, zk - h, zk), (a - w, a - t, zk - t, zk), (v0, v1),
            [(a - w / 2 - t / 2, v, zk - t) for v in (v0 + 1.5, (v0 + v1) / 2, v1 - 1.5)])


def strip_outline(zk):
    """tread strip (the riser support under each tread) outline across the flight (v, z), top at zk; its bottom end corners rounded"""
    v0, v1, zb = ARM_END, WN - ARM_END, zk - ARM_D
    pts = [(v0, zk), (v0, zb), (v1, zb), (v1, zk)]
    if not MONO:
        return pts
    return [pts[0]] + _fillet(pts, 1, STRIP_R, cap=0.8) + _fillet(pts, 2, STRIP_R, cap=0.8) + [pts[3]]


def web_bottom(f, k, u):
    """lowest z of tread k's (rounded) bracket web at u, or None where the web is not"""
    pts = bracket_web(f, k)
    zs = []
    for (u0, z0), (u1, z1) in zip(pts, pts[1:] + pts[:1]):
        if (u0 - u) * (u1 - u) <= 0 and u0 != u1:
            zs.append(z0 + (u - u0) / (u1 - u0) * (z1 - z0))
    return min(zs) if zs else None


# round 6 saddle: seat under the stringer's level foot, legs down the post's south and north faces (one bolt through the post), CHEEKS up
# both sides of the stringer under the first bracket (one bolt through the stringer), and a TAB bent out of each cheek's south edge onto
# the landing's north beam (one bolt each), replacing round 5's separate foot clips.
SAD_GAP = 0.12                                     # cheek top below the rounded bracket web
SAD_U0 = U_FOOT if MONO else None                  # seat's south edge, flush with the stringer's plumb face (the front leg touches the beam)
SAD_U1 = None                                      # set with the post below
B_BH = B0 + U_BEAR + FW / 2 if MONO else B0 + UPPER.uhc   # balcony head beam
B_UF = B0 + UPPER.ufc                             # upper tubes' feet on the landing
LN_W = 2.0                                        # landing north beam width
LAND_N = B0 + 8.0 if not MONO else B0 + U_FOOT    # corner landing frame's north edge (mono round 4: at the back of the landing's riser lip, so no steel shows past the oak)
LAND_DECK_N = B0 + TD - GO if MONO else LAND_N    # mono: the landing's oak ends like a tread, at the front of the riser lip under the upper flight's first tread (Maxwell 11/22/2026)
B_LN = LAND_N - 1                                 # landing north beam, at the edge
VC = WN / 2
PC = XL + POST / 2                                # posts stand outside the open edge, lapped onto the tubes and frames
FOOT_U = 4.0 if MONO else 12.0                   # lower flight foot post (mono: beside the first tread on a 4 anchor moment base plate)
A_FOOT = XL + UL - FOOT_U
A_BR = XL - POST / math.sqrt(2) if MONO else 17.0   # round 11 (Maxwell 11/24/2026: both knee braces the same size): the south brace's level top cut ends at
                                                  # the balcony's west edge, so it spans the same 23.2 in from the wall post as the north one. Before: XL - 4.5                 # knee brace: where it meets the balcony frame (mono: 45 degree braces to the wall, Maxwell 11/22/2026;
                                                  # round 7: 2 1/2 in further east so its gusset clears the west beam)
BRACE = A_BR - 1.0 if MONO else 16.0              # its rise, to the wall post's centreline


# round 8 floor shoe (Maxwell 11/24/2026): the lower stringer's level foot stands on a 1/4 in base plate.
# Round 10 (Maxwell 11/24/2026): the shoe no longer shares the first bracket's bolt. Its west end bends up into a WALL that lies flat on the
# tube's sloped top face, so the foot sits in a pocket and cannot slide west (the way the stringer's thrust pushes it). One through bolt of
# its own goes square through the wall and the tube (crush sleeve inside), nut on the tube's underside. Two anchors in wings beside the
# tube at the west end, one on the centreline in a tab past the east end. The side cheeks are gone.
SHOE_TAB = 2.25                                    # tab past the east end of the tube's foot
SHOE_WALL = 4.5                                    # wall length up the tube's top face from the foot's toe
SHOE_BOLT_S = 3.6                                  # wall bolt this far up the face (clears bracket 1's lower bolt by about 1 in; nut end clears the base)
SHOE_ANC_V = 3.0                                   # west anchors this far each side of the centreline, outside the bracket webs
SHOE_HW = SHOE_ANC_V + 0.85                        # base half width over the wings
SHOE_R = 0.6                                       # free corners rounded


def shoe_base():
    """floor shoe base outline (u, v) in the lower flight: bend line across the tube's width at the toe (u0), wings round the west anchors,
    a tapered tab round the east anchor"""
    f = LOWER
    ue = f.u1 + SHOE_TAB
    circ = lambda cu, cv, r: [(cu + r * math.cos(2 * math.pi * j / 48), cv + r * math.sin(2 * math.pi * j / 48)) for j in range(48)]
    pts = [(f.u0, VC - TW / 2), (f.u0, VC + TW / 2)]
    for sg in (-1, 1):
        pts += circ(f.u0 + 1.0, VC + sg * SHOE_ANC_V, 0.85) + circ(ue - SHOE_R, VC + sg * (TW / 2 - SHOE_R), SHOE_R)
    return _hull(pts)


def shoe_wall():
    """the wall's outline (s, w): s up the tube's top face from the toe, w across it from the centreline; top corners rounded"""
    p = [(0.0, -TW / 2), (SHOE_WALL, -TW / 2), (SHOE_WALL, TW / 2), (0.0, TW / 2)]
    return [p[0]] + _fillet(p, 1, SHOE_R) + _fillet(p, 2, SHOE_R) + [p[3]]


def shoe_wall_uz(s):
    """(u, z) of the point s up the tube's top face from the foot's toe"""
    f = LOWER
    return (f.u0 + s * math.cos(ANG), f.zf + s * math.sin(ANG))


def shoe_anchors():
    """the three slab anchors, (u, v) in the lower flight"""
    f = LOWER
    return [(f.u0 + 1.0, VC - SHOE_ANC_V), (f.u0 + 1.0, VC + SHOE_ANC_V), (f.u1 + SHOE_TAB / 2, VC)]

# round 11 standard post base (Maxwell 11/24/2026: the round 10 stock angle bases looked overbuilt; back to a small square plate like the
# round 3 ones, corners rounded, one part for every slab post, no welding). Every slab post (foot post, corner newel, upper stringer post)
# stands ON a 7 x 7 x 1/2 in laser cut plate held by four slab anchors at its corners. Two short clip angles cut from stock L 2 x 2 x 3/8
# (3 in long) stand against two opposite faces of the post: one 3/8 through bolt crosses the post and both clips, and each clip's flat leg
# takes a 3/8 flat head screw up through a countersunk hole in the plate (put in before the plate is anchored). The plate's two screw holes
# sit 2.45 in from its centre, so the same plate fits the 2 x 2 and the 3 x 3 posts: only the hole in the clip's flat leg moves (1.45 in from
# the heel on a 2 x 2 post, 0.95 in on the 3 x 3). Foot post base moment 4810 in-lb (frame model): screw pull about 1390 lb, clip leg
# about 21 ksi as a plain cantilever (under 0.6 Fy before any credit for the screw clamping it), plate about 13 ksi.
BP_W, BP_T, BP_R = 7.0, 0.5, 0.75                 # plate size, thickness, corner radius
BP_ANC = 2.75                                      # anchors at the plate's corners, this far from its centre each way
BP_SCREW = 2.45                                    # countersunk clip screw holes, this far from the centre on the clips' axis
BC_LEG, BC_UP, BC_T, BC_L = 2.0, 3.0, 0.375, 3.0   # clip angle flat leg, upright leg, thickness, length (along the post face)
BC_BOLT_Z = (BP_T + 1.35, BP_T + 2.35)              # round 11b: TWO through bolts across the post (stock L 3 x 2 x 3/8, long leg up), so the
                                                   # post cannot pivot about a single bolt (the attachment check flagged the foot post)


def post_base(a0, a1, b0, b1, axis):
    """the standard post base. axis 'a' puts the clips on the post's two a faces, 'b' on its b faces. Returns dict: plate outline [(a, b)],
    anchors [(a, b)], clips [(upright box, flat box, outward sign)] boxes (a0, a1, b0, b1, z0, z1), bolt (head point, nut point) as (a, b, z),
    screws [(a, b)] (flat heads up through the plate into the clips' flat legs)"""
    ac, bc, h = (a0 + a1) / 2, (b0 + b1) / 2, BP_W / 2
    sq = [(ac - h, bc - h), (ac + h, bc - h), (ac + h, bc + h), (ac - h, bc + h)]
    plate = [q for i in range(4) for q in _fillet(sq, i, BP_R, cap=0.45)]
    anchors = [(ac + i * BP_ANC, bc + j * BP_ANC) for i in (-1, 1) for j in (-1, 1)]
    clips, screws, ends = [], [], []
    for sg in (-1, 1):
        if axis == "a":
            fa = a1 if sg > 0 else a0
            up = tuple(sorted((fa, fa + sg * BC_T))) + (bc - BC_L / 2, bc + BC_L / 2, BP_T, BP_T + BC_UP)
            fl = tuple(sorted((fa, fa + sg * BC_LEG))) + (bc - BC_L / 2, bc + BC_L / 2, BP_T, BP_T + BC_T)
            screws.append((ac + sg * BP_SCREW, bc))
            ends.append([(fa + sg * BC_T, bc, z_) for z_ in BC_BOLT_Z])
        else:
            fb = b1 if sg > 0 else b0
            up = (ac - BC_L / 2, ac + BC_L / 2) + tuple(sorted((fb, fb + sg * BC_T))) + (BP_T, BP_T + BC_UP)
            fl = (ac - BC_L / 2, ac + BC_L / 2) + tuple(sorted((fb, fb + sg * BC_LEG))) + (BP_T, BP_T + BC_T)
            screws.append((ac, bc + sg * BP_SCREW))
            ends.append([(ac, fb + sg * BC_T, z_) for z_ in BC_BOLT_Z])
        clips.append((up, fl, sg))
    return dict(plate=plate, anchors=anchors, clips=clips, bolts=list(zip(ends[1], ends[0])), screws=screws)


# round 12 rail post base (Maxwell 11/25/2026): the two 2 x 2 rail posts on the slab (foot post, corner newel) stand on ONE bent 3/8 in plate
# instead of a plate plus two clips. The frame model tips both posts north and west (foot post up to 4810 in-lb, about 500 the other way), so
# their south and east edges lift: the plate's anchor flanges run along the post's SOUTH and EAST sides (three 3/8 wedge anchors: the SE corner
# and one beside each lifting corner) and two tabs bend up 90 deg against its NORTH and WEST faces, two 3/8 through bolts in each (crush sleeve
# inside). Each tab takes the tipping in its own plane, so its uplift lands right beside an anchor. The two tabs' bolts are staggered in height
# so they do not cross inside the post. The upper stringer post keeps the round 11 base (post_base above).
RB_T = 0.375                                       # plate
RB_FL = 3.75                                       # anchor flanges reach this far south and east of the post's faces (2.75 gave about 1060 lb per anchor, 3.75 about 740)
RB_H = 5.85                                        # tabs: outside height from the slab
RB_ANC = 1.5                                       # anchor centres this far from the post's south / east faces
RB_ANC_IN = 0.75                                   # and the two side anchors this far in from the tabs' outer faces
RB_BOLT_Z = dict(west=(RB_T + 1.35, RB_T + 3.6), north=(RB_T + 2.475, RB_T + 4.725))   # 2 1/4 apart in each tab, 1 1/8 between the two sets
RB_R, RB_TAB_R = 0.75, 0.6                         # outline corner radius, tab top corner radius


def rail_post_base(a0, a1, b0, b1):
    """one piece bent base under a 2 x 2 rail post with faces a0 (east) .. a1 (west), b0 (south) .. b1 (north). Returns dict: plate outline [(a, b)]
    (the flat base as it lies on the slab, NW corner notched for the tabs), tabs {side: box (a0, a1, b0, b1, z0, z1)}, anchors [(a, b)],
    bolts [(side, axis, head (a, b, z), nut (a, b, z))]"""
    t = RB_T
    ae, aw, bs, bn = a0 - RB_FL, a1 + t, b0 - RB_FL, b1 + t          # outer edges (the tabs' outer faces on the west and north)
    out = [(ae, bs), (aw, bs), (aw, b1), (a1, b1), (a1, bn), (ae, bn)]
    plate = []
    for i in range(len(out)):
        plate += _fillet(out, i, RB_R, cap=0.45) if i in (0, 1, 5) else [out[i]]
    tabs = dict(west=(a1, aw, b0, b1, 0.0, RB_H), north=(a0, a1, b1, bn, 0.0, RB_H))
    anchors = [(a0 - RB_ANC, b0 - RB_ANC), (aw - RB_ANC_IN, b0 - RB_ANC), (a0 - RB_ANC, bn - RB_ANC_IN)]
    ac, bc = (a0 + a1) / 2, (b0 + b1) / 2
    bolts = [("west", "a", (aw, bc, z), (a0, bc, z)) for z in RB_BOLT_Z["west"]]
    bolts += [("north", "b", (ac, bn, z), (ac, b0, z)) for z in RB_BOLT_Z["north"]]
    return dict(plate=plate, tabs=tabs, anchors=anchors, bolts=bolts)


# round 11b fasteners for the oak that only rested on the steel before (check_attached.py): three trim head screws through each riser lip
# into its tread's back edge, and eight 1/4-20 button heads up through each platform frame's top wall into brass inserts in the oak
RISER_SCREW_V = (3.0, WN / 2, WN - 3.0)
DECK_SCREWS = dict(landing=[(1.0, 8.0), (1.0, 22.0), (8.0, 1.0), (18.0, 1.0), (XL - 1.0, 8.0), (XL - 1.0, 22.0), (8.0, B_LN), (18.0, B_LN)],
                   balcony=[(1.0, BAL_S + 6.0), (1.0, BAL_N - 8.0), (6.0, BAL_S + 1.0), (14.0, BAL_S + 1.0), (6.0, B_BH), (14.0, B_BH),
                            (6.0, BAL_N - 1.0), (14.0, BAL_N - 1.0)])   # clear of the corner plates' flange bolts at XL - 7 and XL - 1


# round 7 knee frames (Maxwell 11/24/2026): each 45 degree brace closes a full triangle with a 2 x 2 post down the bath 1 wall from the
# balcony ledger, so the brace no longer leans on its bite into the wall. One 1/4 in gusset plate per joint (brace top to the beam,
# brace foot to the post, post top to the beam end), on the face toward the middle of the balcony, through bolts with crush sleeves.
KB_ZU = FL - TK                                    # balcony frame underside
KB_BOT = KB_ZU - (A_BR - 2.0)                      # brace centreline where it meets the post's face (a = 2)
KB_POST = (0.0, 2.0, KB_BOT - POST / math.sqrt(2) - 2.0, KB_ZU)    # wall post: a0, a1, z0, z1
KB_M = 0.9                                         # gusset edge round each bolt
KG = dict(top=[(A_BR - 4.75, KB_ZU + 1.5), (A_BR - 1.75, KB_ZU + 1.5), (A_BR - 3.5, KB_ZU - 3.5)],   # round 11: clear of the west beam (a < XL - 2)
          foot=[(1.0, KB_BOT + 2.5), (1.0, KB_BOT - 1.0), (4.25, KB_BOT + 2.25)],   # round 10: the lower post bolt up, the brace bolt on its centreline
          corner=[(1.0, KB_ZU - 1.25), (1.0, KB_ZU - 3.5), (4.0, KB_ZU + 1.5), (6.5, KB_ZU + 1.5)])   # round 11: 2 bolts in the post, 2 in the beam, no pivot
KB_LAGS = (KB_BOT + 6.0, KB_ZU - 6.0)            # two lags through each post into the wall framing (round 11: upper one below the corner plate)


KB_MITER = KB_BOT - POST / math.sqrt(2) - 2.0      # round 10 (Maxwell 11/24/2026): the post's foot is cut at 45 degrees, flush with the brace's
                                                  # underside, along the line z = KB_MITER + a; the foot gusset is a triangle on the same line


def gusset(joint):
    """knee frame gusset outline (a, z): the smooth hull of a KB_M margin round its bolts. Round 10: the foot gusset is a triangle, its
    lower edge on the post's 45 degree foot cut and the brace's underside, its back edge on the wall face of the post, corners rounded"""
    if joint == "foot":
        p = [(0.0, KB_MITER), (7.0, KB_MITER + 7.0), (0.0, KB_BOT + 4.25)]
        return _fillet(p, 0, 0.6, cap=0.3) + _fillet(p, 1, 0.75, cap=0.3) + _fillet(p, 2, 0.75, cap=0.3)
    if joint == "corner":                          # round 11: an L shaped corner plate, the post's top and the head beam's end, kept off the ledger
        zu = KB_ZU                                 # (the ledger fills a < 2 above the frame's underside)
        p = [(0.0, zu - 4.75), (2.75, zu - 4.75), (7.5, zu), (7.5, zu + 2.5), (2.0, zu + 2.5), (2.0, zu), (0.0, zu)]
        return [p[5], p[6], p[0]] + _fillet(p, 1, 1.0) + _fillet(p, 2, 1.0) + _fillet(p, 3, 0.6) + [p[4]]   # starts at the inside corner (fans cleanly)
    pts = [(a + KB_M * math.cos(2 * math.pi * j / 48), z + KB_M * math.sin(2 * math.pi * j / 48)) for a, z in KG[joint] for j in range(48)]
    return _hull(pts)


def knee_frames():
    """(name, b centre, side): side = +1 gusset on the brace's north face, -1 on its south face (toward the balcony's middle).
    Round 10: only the south frame is this kind; the north one is NORTH_KNEE below."""
    return [("south", B_BH, 1)]


# round 10 north knee frame (Maxwell 11/24/2026): the north east guard post runs down the wall in one piece as the frame's wall post, and the
# 45 degree brace runs from it up to the north west guard post's foot (the railing corner) instead of to the frame. Gussets on the north face.
CP_T, CP_DROP, CP_BAND = 0.375, 4.5, 8.0          # west corner plates: thickness, how far the west posts and plates run below the frame, band along the beam
# round 11 (Maxwell 11/24/2026: the two 45 degree braces should be the same size): the north brace is now the SAME PART as the south one,
# a level top cut bearing under the north arm and ending at the west edge (beside the north west post), a plumb foot cut on the north east
# post at the same height as the south brace's foot. Its top gusset still takes the corner plate's two post bolts.
NK_ZT = FL - TK - 3.0                              # the north west post's lower gusset bolt (a frame model node)
NK_ZB = KB_BOT - CP_T                              # brace centreline where it meets the north east post's west face (a = 2): 3/8 lower than the
                                                  # south one, because its top bears on the north west corner plate's flange under the north arm
NK_MITER = NK_ZB - POST / math.sqrt(2) - 2.0       # north east post's 45 degree foot cut: z = NK_MITER + a
NK_LAGS = (NK_ZB + 6.0, FL - 11.0)                 # lags through the north east post into the wall framing (none in the frame depth: the ledger is there)
NKG = dict(foot=[(1.0, NK_ZB + 2.5), (1.0, NK_ZB - 1.0), (4.25, NK_ZB + 2.25)],
           top=[(XL + 1.0, FL - TK + 1.5), (XL + 1.0, FL - TK - 3.0), (A_BR - 3.5, KB_ZU - CP_T - 3.5)])   # top: the two post bolts are the corner plate's


# round 11 (Maxwell 11/25/2026: how is the west beam attached?): the balcony's west beam is held at each end, and the head arm at its west
# end, by the standard 2 in clip angle (1/4 in, 1 3/4 legs) on the inside of the frame: one leg against the west beam with a 3/8 through
# bolt across it, the other against the corner plate (or the head arm) with a 3/8 through bolt across the end beam. At the north west and
# head arm joints that bolt also passes through the knee frame's top gusset on the beam's far face (the head arm's is the gusset's own
# east beam bolt). Clip angle joints are taken as pinned in the frame model.
NO_WEST_BEAM = MONO and _env("LADDER_NO_WEST_BEAM", "1") == "1"   # round 11b (Maxwell 11/25/2026 "do we even need the beam?"): no. The frame model
# with and without it: everything passes either way; without it the oak's west edge board works hardest (0.53 of allowable, 0.07 in under the
# 300 lb corner load). So the west beam and its clips are gone and the head arm runs out to the west edge under the brace top.
FC_T, FC_L, FC_HOLE = 0.25, 1.75, 1.1             # clip thickness, leg, hole from the heel (outside corner)


def frame_clips():
    """[(name, leg on the west beam box, leg on the end beam box, west beam bolt (head pt, nut pt), end beam bolt (head pt, nut pt))],
    boxes (a0, a1, b0, b1, z0, z1), points (a, b, z); the west beam bolts run along a, the end beam bolts along b"""
    if NO_WEST_BEAM:
        return []
    zu, zc = FL - TK, FL - TK + 1.5
    aw = XL - 2.0                                  # the west beam's inside (east) face
    z0, z1 = zc - 1.0, zc + 1.0
    out = []
    for nm, bf, sg, ab, bnut in (("sw", BAL_S + 2 + CP_T, 1, aw - FC_HOLE, BAL_S),
                                 ("head", B_BH - 1, -1, A_BR - 1.75, B_BH + 1 + BRKT_T),
                                 ("nw", BAL_N - 2 - CP_T, -1, aw - FC_HOLE, BAL_N + BRKT_T)):
        lw = (aw - FC_T, aw) + tuple(sorted((bf, bf + sg * FC_L))) + (z0, z1)
        le = (aw - FC_L, aw) + tuple(sorted((bf, bf + sg * FC_T))) + (z0, z1)
        bw = bf + sg * FC_HOLE
        out.append((nm, lw, le, ((aw - FC_T, bw, zc), (XL, bw, zc)), ((ab, bf + sg * FC_T, zc), (ab, bnut, zc))))
    return out


NKG_CLIP = (XL - 2.0 - FC_HOLE, FL - TK + 1.5)     # the north west clip's end beam bolt also passes through the north top gusset


def nk_gusset(joint):
    """north knee frame gusset outline (a, z)"""
    if joint == "foot":
        p = [(0.0, NK_MITER), (7.0, NK_MITER + 7.0), (0.0, NK_ZB + 4.25)]
        return _fillet(p, 0, 0.6, cap=0.3) + _fillet(p, 1, 0.75, cap=0.3) + _fillet(p, 2, 0.75, cap=0.3)
    pts = [(a + KB_M * math.cos(2 * math.pi * j / 48), z + KB_M * math.sin(2 * math.pi * j / 48)) for a, z in NKG[joint] + ([NKG_CLIP] if joint == "top" and not NO_WEST_BEAM else []) for j in range(48)]
    return _hull(pts)


def corner_plate(sg):
    """west corner plate in its plane (a, z): a band along the end beam's inside face and a leg down the post's inside face; and its flange
    folded under the beam (a0, a1). sg = -1 south west (plate on the south beam's north face), +1 north west (on the north arm's south face).
    Returns (outline, flange (a0, a1, width), post bolts [(a, z)], flange bolts [a])"""
    zu, zt = FL - TK, FL - TTD
    p = [(XL - CP_BAND, zu), (XL, zu), (XL, zu - CP_DROP), (XL + POST, zu - CP_DROP), (XL + POST, zt), (XL - CP_BAND, zt)]
    out = [p[0], p[1]] + _fillet(p, 2, 0.5) + _fillet(p, 3, 0.6) + [p[4]] + _fillet(p, 5, 0.6)
    return out, (XL - CP_BAND, XL - 0.25, 2.25), [(XL + 1.0, zu + 1.5), (XL + 1.0, zu - 3.0)], [XL - CP_BAND + 1.0, XL - 4.2]   # round 11b: clear of the north brace's top


# frame members, centrelines (a, b) to (a, b): 2 x 3 tube on edge
LAND_FRAME = dict(LE=((1, 0), (1, LAND_N)), LS=((1, 1), (XL, 1)), LW=((XL - 1, 1), (XL - 1, LAND_N)),
                  LN=((1, B_LN), (XL - 1, B_LN)), LH=((A_LH, 1), (A_LH, LAND_N - 1)))
BAL_FRAME = dict(BE=((1, BAL_S), (1, BAL_N)), BS=((1, BAL_S + 1), (XL - 1, BAL_S + 1)), BH=((1, B_BH), (XL - 1, B_BH)),
                 BN=((1, BAL_N - 1), (XL, BAL_N - 1)), BW=((XL - 1, BAL_S), (XL - 1, BAL_N - 1)))   # (round 9 layout; drawings only)
LAND_LAGS = dict(LE=(4.0, 16.0, 27.0) if MONO else (4.0, 20.0, 32.0), LS=(8.0, 22.0))          # along each ledger, assumed stud or blocking positions
BAL_LAGS = (BAL_S + 3, B_BH - 3.5, B_BH + 2.0, BAL_N0 - 3) if MONO else (BAL_S + 3, (BAL_S + BAL_N) / 2, BAL_N - 3)   # round 8: a 4th bolt beside the head beam, holes drilled tight (round 11b: north of the head arm's corner plate)
# round 8 (Maxwell 11/24/2026): the upper stringer's head pushes the balcony north along the wall, carried by these bolts in shear. A flat
# bar diagonal under the frame was tried in the frame model and changed nothing (the frame does not rack; what moves is the bolts' give),
# so the fix is a 4th bolt by the head beam and tight holes.
LAND_STRIPS = (4.0, 9.5, 15.0, 20.5, 26.0) if MONO else (4.0, 9.5, 15.0, 20.5, 26.0, 30.5)                # deck boards run east to west on the landing: analysis strips at these b
BAL_STRIPS = (4.0, 9.0, 14.0, 19.0)                             # and north to south on the balcony: strips at these a

NEWEL_TOP = UPPER.zn(XL + POST - B0) + HR + 1.5                 # corner newel, a little above the upper rail
GSW_TOP_OLD = max(UPPER.zn(BAL_S - B0) + HR + 1.5, FL + GUARD_H)                       # top newel at the balcony's south west corner
G_TOP = FL + GUARD_H                                            # top of the balcony guard rail
GP_B = BAL_N - POST / 2 if MONO else BAL_N + POST / 2  # north guard posts (mono round 10: at the balcony's north edge, which grew out to them)
# corner landing posts (Maxwell 11/22/2026 round 3): 2 x 2 posts from the slab to the two ends of the north beam, which carries the upper stringer's foot
LAND_POSTS = {}                                   # round 3's corner posts, dropped in round 4 for the one stringer post
UP_POST_W = 3.0                                   # round 4: 3 x 3 x 3/16 post under the upper stringer's foot, on a 4 anchor plate
UP_POST = (XL - VC - UP_POST_W / 2, XL - VC + UP_POST_W / 2, LAND_N + BRKT_T, LAND_N + BRKT_T + UP_POST_W) if MONO else None   # round 6: behind the saddle's front leg, which touches the beam
if MONO:
    SAD_U1 = U_FOOT + BRKT_T + UP_POST_W + BRKT_T
    CHEEK_U1 = SAD_U1 + 0.75                          # cheeks run on past the seat's back edge, for edge distance round their bolt
    CHEEK_H = 2.0                                     # round 7: cheeks flat topped, this far above the seat (the rounder webs clear them)
    _cu = [SAD_U0 + i * (CHEEK_U1 - SAD_U0) / 34 for i in range(35)]
    _wb = [web_bottom(UPPER, 1, u) for u in _cu]
    assert min(z for z in _wb if z is not None) - SAD_GAP >= Z_SEAT + CHEEK_H, "first upper bracket web hits the saddle cheek"
    SAD_R = 0.6                                       # round 10 (Maxwell 11/24/2026): the saddle's free corners rounded
    _ck = [(SAD_U0, Z_SEAT - BRKT_T), (SAD_U0, Z_SEAT + CHEEK_H), (CHEEK_U1, Z_SEAT + CHEEK_H), (CHEEK_U1, Z_SEAT - BRKT_T)]
    CHEEK = _ck[:2] + _fillet(_ck, 2, SAD_R) + _fillet(_ck, 3, SAD_R)
    SAD_BOLT = (SAD_U1 - 0.15, Z_SEAT + 0.85)         # cheek bolt toward the back, where the cheek is taller
    TAB_Z = (Z_SEAT + 0.2, Z_SEAT + CHEEK_H)          # foot tab against the landing north beam's north face (north of the oak riser lip); starts above
                                                      # the cheek's bend so it folds off flat cheek (flat pattern: 0.26 in clear of the bend line).
                                                      # Round 10: its top runs up to the cheek's top so the tab is as tall as the cheek (it stood
                                                      # 0.6 in lower before for no good reason, Maxwell 11/24/2026)
    TAB_W = 2.0                                       # tab reaches this far out from the cheek
    TAB_BOLT_Z = Z_SEAT + 0.79                        # bolt stays where it was: 0.68 in below the beam's top
    def tab_outline():
        """saddle tab outline (w, z): w out from the cheek's outer face, its two outer corners rounded"""
        p = [(0.0, TAB_Z[0]), (TAB_W, TAB_Z[0]), (TAB_W, TAB_Z[1]), (0.0, TAB_Z[1])]
        return [p[0]] + _fillet(p, 1, SAD_R) + _fillet(p, 2, SAD_R) + [p[3]]
    SAD_LEG = 3.5                                     # legs down the post faces, one through bolt 2 in down
    POST_BASES = dict(foot_post=((A_FOOT - 1, A_FOOT + 1, XL, XL + POST), "a"),          # round 10: which faces take the clip angles
                      corner_newel=((XL, XL + POST, XL, XL + POST), "b"),
                      upper_stringer_post=(UP_POST, "a"))



# ------------------------------------------------------------------ one continuous open side rail (mono, round 3)
# Plan path of the rail's top centreline: west to east along the lower flight, a small radius turn at the corner newel, north up the upper
# flight, along the balcony's west guard, a turn at the north west post and east along the north guard to the bath 1 wall.
# Heights: the lower and upper rail lines are about a foot apart at the corner, so the rail eases from one to the other through the turn
# (an S curve, steepest about 70 degrees), then eases again from the upper line into the level guard top at the balcony's south west newel.
# The code allows a handrail to go over its maximum height at such transitions (R311.7.8.1 exception, bendings and fittings).
RRC = 2.0                                                      # plan radius of both turns
_SEG = []                                                      # (kind, s0, length, data)


def _seg(kind, length, data):
    s0 = _SEG[-1][1] + _SEG[-1][2] if _SEG else 0.0
    _SEG.append((kind, s0, length, data))


_seg("line", XL + UL - (PC + RRC), ((XL + UL, PC), (PC + RRC, PC)))
_seg("arc", RRC * math.pi / 2, ((PC + RRC, PC + RRC), -math.pi / 2, -math.pi))
_seg("line", GP_B - RRC - (PC + RRC), ((PC, PC + RRC), (PC, GP_B - RRC)))
_seg("arc", RRC * math.pi / 2, ((PC - RRC, GP_B - RRC), 0.0, math.pi / 2))
_seg("line", PC - RRC, ((PC - RRC, GP_B), (0.0, GP_B)))
S_UP0 = _SEG[2][1]                                             # start of the straight up the upper flight
S_END = _SEG[-1][1] + _SEG[-1][2]
S_C = (S_UP0 + 0.5 - 16.0, S_UP0 + 0.5)                        # corner ease, ends just past the upper flight's first nosing
S_T = (S_UP0 + (BAL_S - 13.0) - (PC + RRC), S_UP0 + (BAL_S + 1.0) - (PC + RRC))   # top ease, level from over the south west newel on


def rail_plan(s):
    """(a, b) of the rail centreline at path length s"""
    for kind, s0, ln, d in _SEG:
        if s <= s0 + ln + 1e-9 or (kind, s0) == _SEG[-1][:2]:
            t = min(max((s - s0) / ln, 0.0), 1.0)
            if kind == "line":
                (a0, b0), (a1, b1) = d
                return a0 + t * (a1 - a0), b0 + t * (b1 - b0)
            (ca, cb), t0, t1 = d
            th = t0 + t * (t1 - t0)
            return ca + RRC * math.cos(th), cb + RRC * math.sin(th)


def _ss(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def rail_z(s):
    """top of the rail at path length s"""
    zl = RI + s * SL + HR                                       # lower flight's rail line, u = s on the lower straight
    zu = ZP + RI + (PC + RRC + (s - S_UP0) - B0) * SL + HR      # upper flight's rail line
    if s <= S_T[0]:
        return zl + (zu - zl) * _ss((s - S_C[0]) / (S_C[1] - S_C[0]))
    return zu + (G_TOP - zu) * _ss((s - S_T[0]) / (S_T[1] - S_T[0])) if s < S_T[1] else G_TOP


def rail_slope(s, h=0.05):
    return (rail_z(s + h) - rail_z(s - h)) / (2 * h)


def rail_depth(s):
    """plumb depth of the 1 1/2 in square rail where it slopes"""
    return RAIL * math.sqrt(1 + rail_slope(s) ** 2)


def rail_s(a, b):
    """path length of the rail point nearest to plan point (a, b)"""
    best = None
    n = int(S_END * 4)
    for i in range(n + 1):
        s = S_END * i / n
        pa, pb = rail_plan(s)
        d = (pa - a) ** 2 + (pb - b) ** 2
        if best is None or d < best[0]:
            best = (d, s)
    s, h = best[1], S_END / n                                   # refine
    for _ in range(30):
        h /= 2
        cand = [s - h, s, s + h]
        s = min(cand, key=lambda x: (rail_plan(x)[0] - a) ** 2 + (rail_plan(x)[1] - b) ** 2)
    return min(max(s, 0.0), S_END)


def rail_under(a, b):
    """underside of the rail above plan point (a, b): where a post or picket top stops"""
    s = rail_s(a, b)
    return rail_z(s) - rail_depth(s)


def rail_samples(extra=(), step=0.75):
    """path stations: segment and ease ends, dense through the turns and eases, plus any extra stations"""
    ss = {0.0, S_END, *S_C, *S_T, *extra}
    for kind, s0, ln, d in _SEG:
        ss |= {s0, s0 + ln}
        if kind == "arc":
            ss |= {s0 + ln * i / 8 for i in range(9)}
    for lo, hi in (S_C, S_T):
        n = max(2, int((hi - lo) / step))
        ss |= {lo + (hi - lo) * i / n for i in range(n + 1)}
    return sorted(x for x in ss if 0 <= x <= S_END)


POST_S = dict(foot=FOOT_U, newel=rail_s(PC, PC), gsw=rail_s(PC, BAL_S + POST / 2), nw=rail_s(PC, GP_B), ne=rail_s(POST / 2, GP_B)) if CONT_RAIL else {}
NEWEL_TOP2 = rail_under(PC, PC) if CONT_RAIL else NEWEL_TOP             # continuous rail: posts stop under the rail
GSW_TOP = rail_under(PC, BAL_S + POST / 2) if CONT_RAIL else GSW_TOP_OLD

if __name__ == "__main__":
    for f in FLIGHTS:
        print(f.name, "foot cut u", round(f.u0, 2), round(f.u1, 2), "head cut u", round(f.u2, 2), round(f.u3, 2), "zu", round(f.zu, 2))
    print("ZP", round(ZP, 3), "FL", round(FL, 3), "TK", TK, "XL", XL, "B0", B0, "LAND_N", LAND_N, "BAL", BAL_S, BAL_N)
    if MONO:
        print("rail: S_UP0", round(S_UP0, 2), "S_END", round(S_END, 2), "corner ease", [round(x, 2) for x in S_C], "top ease", [round(x, 2) for x in S_T])
        print("max rail slope deg", round(max(math.degrees(math.atan(rail_slope(s))) for s in rail_samples(step=0.25)), 1), "posts", {k: (round(v, 2), round(rail_under(*rail_plan(v)), 2)) for k, v in POST_S.items()})
    print("A_LH", round(A_LH, 2), "B_BH", round(B_BH, 2), "B_UF", round(B_UF, 2), "newel top", round(NEWEL_TOP, 1), "GSW top", round(GSW_TOP, 1))


def rail_plane(a0, a1, b0, b1, gap=0.12):
    """z(a, b) of the plane a post's top is cut to, just under the rail's underside above the post's centre"""
    if not CONT_RAIL:                                           # straight rails: the posts' tops (see straight_rails)
        ac, bc = (a0 + a1) / 2, (b0 + b1) / 2
        if abs(bc - PC) < 0.1 and ac > XL + POST + 0.5:        # lower flight foot post, under the sloped lower rail
            return lambda a, b: LOWER.zn(XL + UL - a) + HR - RAIL / math.cos(ANG) - gap
        if abs(ac - PC) < 0.1 and abs(bc - PC) < 0.1:          # corner newel, above the upper rail
            return lambda a, b: NEWEL_TOP
        if abs(bc - (BAL_S + POST / 2)) < 0.1:                 # balcony south west newel, flush with the guard's top rail
            return lambda a, b: GSW_TOP
        return lambda a, b: G_TOP - RAIL                        # guard posts, under the level top rails
    s_ = rail_s((a0 + a1) / 2, (b0 + b1) / 2)
    pa, pb = rail_plan(s_)
    qa, qb = rail_plan(min(s_ + 0.05, S_END))
    ra, rb = rail_plan(max(s_ - 0.05, 0.0))
    ta, tb = qa - ra, qb - rb
    n_ = math.hypot(ta, tb)
    ta, tb, m_ = ta / n_, tb / n_, rail_slope(s_)
    z0 = rail_z(s_) - rail_depth(s_) - gap
    return lambda a, b: z0 + m_ * ((a - pa) * ta + (b - pb) * tb)


def straight_rails():
    """straight rails (Maxwell 11/24/2026): (name, a0, a1, b0, b1, z top at the a0 or b0 end, z top at the other end, axis) for 1 1/2 in square tubes.
    The lower and upper open side rails die into the corner newel's west and north faces, the upper one into the balcony's south west newel;
    the level guard top rails run over the guard posts."""
    h = RAIL / 2
    za = lambda a: LOWER.zn(XL + UL - a) + HR
    zb = lambda b: UPPER.zn(b - B0) + HR
    ra = (PC - h, PC + h)
    rb = (GP_B - h, GP_B + h)
    return [("lower_rail_open", XL + POST, XL + UL, PC - h, PC + h, za(XL + POST), za(XL + UL), "a"),
            ("upper_rail_open", *ra, XL + POST, BAL_S, zb(XL + POST), zb(BAL_S), "b"),
            ("guard_west_top_rail", *ra, BAL_S + POST, rb[1], G_TOP, G_TOP, "b"),
            ("guard_north_top_rail", 0.0, ra[0], *rb, G_TOP, G_TOP, "a")]


def rail_frames():
    """the rail's cross sections at every station: (a, b) of its two sides and z of its top and bottom"""
    out = []
    for s_ in rail_samples():
        pa, pb = rail_plan(s_)
        qa, qb = rail_plan(min(s_ + 0.05, S_END)); ra, rb = rail_plan(max(s_ - 0.05, 0.0))
        ta, tb = qa - ra, qb - rb
        n_ = math.hypot(ta, tb)
        na, nb = -tb / n_ * RAIL / 2, ta / n_ * RAIL / 2
        out.append(((pa + na, pb + nb), (pa - na, pb - nb), rail_z(s_), rail_z(s_) - rail_depth(s_)))
    return out


# round 11b rail straps (check_attached.py found every rail held by nothing): each rail end or crossing over a post gets one flat 1/4 in strap
# on the post's side face, 1 1/4 in wide, with a 1/4 in spacer behind it on the rail (the 1 1/2 rail sits 1/4 in in from the 2 in post's
# face). One 1/4-20 through bolt crosses the rail and spacer, two cross the post, so nothing hangs on a single bolt. The strap lies along the
# rail into the post where a rail ends on a post face, and plumb where a rail runs over a post top. Holes: 0.625 from the end, then 1.75 and
# 1.0 apart (one standard part); the lower rail over the foot post needs a longer first gap (its plumb depth is 3.16 in).
ST_W, ST_T, ST_E, SP_T = 1.25, 0.25, 0.625, 0.25


def _u(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


def rail_straps():
    """[(name, R, P1, P2, t, n, plane, pattern)]: rail bolt R, post bolts P1, P2 as (a, b, z) on the rail's / post's centre plane, t the unit
    direction from R to the post bolts, n the outward side (('a', +1) or ('b', +1)), plane the post side face coordinate, pattern name"""
    rails = {r[0]: r for r in straight_rails()}
    out = []

    def face(name, rail, end, side):
        nm, a0, a1, b0, b1, z0, z1, ax = rail
        ac, bc = (a0 + a1) / 2, (b0 + b1) / 2
        if ax == "a":
            a_ = a0 if end == 0 else a1
            zt = z0 if end == 0 else z1
            dz = (z1 - z0) / (a1 - a0)
            depth = RAIL * math.sqrt(1 + dz * dz)
            p0 = (a_, bc, zt - depth / 2)
            t = _u((-1.0 if end == 0 else 1.0, 0.0, -dz if end == 0 else dz))
        else:
            b_ = b0 if end == 0 else b1
            zt = z0 if end == 0 else z1
            dz = (z1 - z0) / (b1 - b0)
            depth = RAIL * math.sqrt(1 + dz * dz)
            p0 = (ac, b_, zt - depth / 2)
            t = _u((0.0, -1.0 if end == 0 else 1.0, -dz if end == 0 else dz))
        R = tuple(p - 1.25 * q for p, q in zip(p0, t))
        P1 = tuple(p + 0.5 * q for p, q in zip(p0, t))
        P2 = tuple(p + 1.5 * q for p, q in zip(p0, t))
        out.append((name, R, P1, P2, t, side, (bc if side[0] == "b" else ac) + POST / 2, "standard"))

    def over(name, a, b, ztop_post, side, rail_up=0.75, pattern="standard"):
        R, P1, P2 = (a, b, ztop_post + rail_up), (a, b, ztop_post - 1.0), (a, b, ztop_post - 2.0)
        c = b if side[0] == "b" else a
        out.append((name, R, P1, P2, (0.0, 0.0, -1.0), side, c + POST / 2, pattern))

    def tilt(name, R, P1, side, plane):
        assert abs(math.dist(R, P1) - 1.75) < 1e-6, name                        # the standard hole pattern
        t = _u(tuple(q - p for p, q in zip(R, P1)))
        P2 = tuple(p + q for p, q in zip(P1, t))
        out.append((name, R, P1, P2, t, side, plane, "standard"))

    lo, up = rails["lower_rail_open"], rails["upper_rail_open"]
    face("lower_newel", lo, 0, ("b", 1))
    zf = lo[5] + (lo[6] - lo[5]) * (A_FOOT - lo[1]) / (lo[2] - lo[1])            # lower rail top over the foot post
    dzf = (lo[6] - lo[5]) / (lo[2] - lo[1])
    dep = RAIL * math.sqrt(1 + dzf * dzf)
    over("lower_foot", A_FOOT, PC, zf - dep, ("b", 1), rail_up=dep / 2, pattern="foot")
    face("upper_newel", up, 0, ("a", 1))
    face("upper_sw", up, 1, ("a", 1))
    face("guard_top_sw", rails["guard_west_top_rail"], 0, ("a", 1))
    zp = G_TOP - RAIL
    over("guard_top_west_nw", PC, GP_B, zp, ("a", 1))
    over("guard_top_north_ne", POST / 2, GP_B, zp, ("b", 1))
    tilt("guard_top_north_nw", (XL - 0.5, GP_B, G_TOP - RAIL / 2), (XL + 0.6, GP_B, G_TOP - RAIL / 2 - math.sqrt(1.75 ** 2 - 1.1 ** 2)), ("b", 1), GP_B + POST / 2)
    zb = FL + 3.6 + RAIL / 2                                                     # guard bottom rails (level)
    bw = ("guard_bottom_west", PC - RAIL / 2, PC + RAIL / 2, BAL_S + POST, BAL_N - POST, zb + RAIL / 2, zb + RAIL / 2, "b")
    face("guard_bottom_sw", bw, 0, ("a", 1))
    tilt("guard_bottom_west_nw", (PC, BAL_N - POST - 0.5, zb), (PC, BAL_N - POST + 0.6, zb + math.sqrt(1.75 ** 2 - 1.1 ** 2)), ("a", 1), PC + POST / 2)
    bn = ("guard_bottom_north", POST, XL, GP_B - RAIL / 2, GP_B + RAIL / 2, zb + RAIL / 2, zb + RAIL / 2, "a")
    face("guard_bottom_north_ne", bn, 0, ("b", 1))
    tilt("guard_bottom_north_nw", (XL - 0.5, GP_B, zb), (XL + 0.6, GP_B, zb - math.sqrt(1.75 ** 2 - 1.1 ** 2)), ("b", 1), GP_B + POST / 2)
    return out


def strap_outline(R, P2, t, side, plane):
    """the strap's four corners (a, b, z) on the post side face plane"""
    ax = side[0]
    n = (1.0, 0.0, 0.0) if ax == "a" else (0.0, 1.0, 0.0)
    w = _u((n[1] * t[2] - n[2] * t[1], n[2] * t[0] - n[0] * t[2], n[0] * t[1] - n[1] * t[0]))
    s0 = tuple(p - ST_E * q for p, q in zip(R, t))
    s1 = tuple(p + ST_E * q for p, q in zip(P2, t))
    pts = [tuple(p + k * ST_W / 2 * q for p, q in zip(s, w)) for s, k in ((s0, -1), (s1, -1), (s1, 1), (s0, 1))]
    i = 0 if ax == "a" else 1
    return [tuple(plane if j == i else c for j, c in enumerate(p)) for p in pts]
