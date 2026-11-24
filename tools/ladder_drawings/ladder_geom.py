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
STRIPS = (_env("LADDER_TREAD_STRIPS", "1" if L.get("ladder_tread_strips", True) else "0") == "1") if MONO else True
TT = float(_env("LADDER_TREAD_THICK_IN", L.get("ladder_tread_thick_in", 1.44 if STRIPS else 1.75)))
TTD = 1.44                                        # oak deck on the corner landing and the balcony (stays 1 7/16 in either way)
RI, GO, TD = L["floor_height"] * 12 / NR, L["ladder_going_in"], L["ladder_tread_in"]
TW, TDp = L.get("ladder_mono_in", [4.0, 4.0]) if MONO else L.get("ladder_tube_in", [2.0, 3.0])
WT = 0.25 if MONO else 0.1875                     # nominal stringer wall
FW, FD = 2.0, 3.0                                 # landing and balcony frame tube, on edge
FT_L, FT_B = (0.125, 0.1875) if MONO else (0.1875, 0.1875)   # frame tube walls: the corner landing now stands on posts, so its frame is 1/8 wall (Maxwell 11/22/2026: less metal)
CONT_RAIL = MONO and bool(L.get("ladder_rail_continuous", False))   # round 3's one curved rail; Maxwell 11/24/2026: back to straight rails between posts
WALL_RAIL = bool(L.get("ladder_wall_rail", True))   # wall side handrails; code wants rails on both sides of a ships ladder, Maxwell asked to hide them for now
SPHERE_GAP = 3.875                               # no strip option: riser lip top to the next tread's underside, under the 4 in sphere
RT, RH = ((0.75, 2.0) if STRIPS else (0.75, RI - TT - SPHERE_GAP)) if MONO else (0.0, 0.0)      # mono: an oak riser lip behind every tread; the 2 in steel strip under the tread above closes the rest (Maxwell 11/22/2026 round 3)
WEB0, BOLT_N, LAP, SEAT_W = (4.5, 1.5, 3.0, 3.5) if MONO else (3.75, 1.25, 2.25, 2.5)   # tread bracket: web start behind the nosing, bolt line below the tube top, lap, seat width
# Mono tread support (Maxwell 11/22/2026 PM): a flat plate ARM on edge crosses over the stringer under each tread and reaches near both tread ends.
# Each bracket web has a flange folded off its vertical front edge that bolts to the arm, so the load goes into the webs in their own plane.
# The earlier seat only bracket (SEAT_W wide bent seat) bent like a diving board: tools/ladder_drawings/bracket_solid_fea.py has that study.
# Round 3 (Maxwell 11/22/2026 night): the arm is now a narrow STRIP of constant depth, one bolt through each bracket flange, a screw tab at each
# end into the tread. It hangs just behind the riser lip of the tread below, so it is also the top of the riser and the lip can be shorter.
BRKT_T = 0.25                                     # web and strip plate
ARM_D, ARM_END = 2.0, 1.2                         # strip depth; its ends stop this far inside the tread ends
ARM_FL, SEAT_TAB, FOOT_W = 1.75, (1.5 if STRIPS else float(L.get("ladder_seat_tab_in", 2.5))), 3.5         # web's bolting flange, the small seat tab behind it, first bracket's foot flange
SEAT_S = WEB0 + (1.0 if STRIPS else 0.0)
SEAT_LAG_V = 0.3 if STRIPS else 0.25                 # lag line, out from the seat's centre (away from the bend)
SEAT_LAG = (0.25, 2.5) if STRIPS else (0.3125, 1.5)   # lag (dia, length) up through each seat into the tread: round 8 no strip option uses 5/16 x 1 1/2


def seat_lags(uk):
    """u of the lags up through each bracket seat (two with the strips, three spread along the longer seat without)"""
    if STRIPS:
        return (uk + 6.5, uk + 8.0)
    u0, u1 = uk + SEAT_S + 0.75, uk + TD + RT - 0.75
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
POST, RAIL, RAIL_T = 2.0, 1.5, 0.1875             # square tube posts (3/16 wall) and rails (1/8 wall)
GUARD_H = 36.0
PICKET = 0.5


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
WEB_R_DROP = 0.5


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
        return [A] + _fillet(h[0:3], 1, WEB_R_DROP) + h[2:]
    mid = _sweep(raw, 2, *WEB_SWEEP)
    pts = [A] + _fillet([A, C, mid[0]], 1, WEB_R_FRONT) + mid + _fillet([mid[-1], E, B], 1, WEB_R_BACK) + [B]
    return pts


STRIP_R = 1.5                                      # round 7: the tread strips' bottom end corners rounded this much (Maxwell 11/24/2026)


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
A_BR = XL - 4.5 if MONO else 17.0                 # knee brace: where it meets the balcony frame (mono: 45 degree braces to the wall, Maxwell 11/22/2026;
                                                  # round 7: 2 1/2 in further east so its gusset clears the west beam)
BRACE = A_BR - 1.0 if MONO else 16.0              # its rise, to the wall post's centreline


# round 8 floor shoe (Maxwell 11/24/2026): the lower stringer's level foot stands on a 1/4 in base plate, a simple cover like the upper
# saddle. Two cheeks fold up from its long edges outside the first tread's bracket webs and share that bracket's lower bolt (cheek, web,
# tube, web, cheek). A tab runs past each end of the foot with one 3/8 slab anchor on the centreline. This frees the first tread for a
# standard bracket.
SHOE_TAB = 2.25                                    # tab past each end of the tube's foot
SHOE_HW = TW / 2 + 2 * BRKT_T                       # half width over the cheeks (outside the bracket webs)
SHOE_EDGE = 1.0                                    # cheek edge round its bolt, like the webs


def shoe_cheek():
    """the floor shoe cheek outline in the lower flight's (u, z): the hull of the base along the tube's foot and a circle round the first
    bracket's lower bolt"""
    f = LOWER
    bu, bz = bracket_bolts(f, 1)[0]
    cl = [(bu + SHOE_EDGE * math.cos(2 * math.pi * j / 48), bz + SHOE_EDGE * math.sin(2 * math.pi * j / 48)) for j in range(48)]
    return _hull([(f.u0, f.zf), (f.u1, f.zf)] + cl)


def shoe_anchors():
    """the two slab anchors, (u, v) in the lower flight"""
    f = LOWER
    return [(f.u0 - SHOE_TAB / 2, VC), (f.u1 + SHOE_TAB / 2, VC)]

# round 7 knee frames (Maxwell 11/24/2026): each 45 degree brace closes a full triangle with a 2 x 2 post down the bath 1 wall from the
# balcony ledger, so the brace no longer leans on its bite into the wall. One 1/4 in gusset plate per joint (brace top to the beam,
# brace foot to the post, post top to the beam end), on the face toward the middle of the balcony, through bolts with crush sleeves.
KB_ZU = FL - TK                                    # balcony frame underside
KB_BOT = KB_ZU - (A_BR - 2.0)                      # brace centreline where it meets the post's face (a = 2)
KB_POST = (0.0, 2.0, KB_BOT - POST / math.sqrt(2) - 2.0, KB_ZU)    # wall post: a0, a1, z0, z1
KB_M = 0.9                                         # gusset edge round each bolt
KG = dict(top=[(A_BR - 2.5, KB_ZU + 1.5), (A_BR + 1.5, KB_ZU + 1.5), (A_BR - 3.0, KB_ZU - 3.0)],
          foot=[(1.0, KB_BOT + 2.5), (1.0, KB_BOT - 2.5), (5.0, KB_BOT + 3.0)],
          corner=[(1.0, KB_ZU - 2.5), (4.75, KB_ZU + 1.5)])
KB_LAGS = (KB_BOT + 6.0, KB_ZU - 5.0)            # two lags through each post into the wall framing


def gusset(joint):
    """knee frame gusset outline (a, z): the smooth hull of a KB_M margin round its bolts"""
    pts = [(a + KB_M * math.cos(2 * math.pi * j / 48), z + KB_M * math.sin(2 * math.pi * j / 48)) for a, z in KG[joint] for j in range(48)]
    return _hull(pts)


def knee_frames():
    """(name, b centre, side): side = +1 gusset on the brace's north face, -1 on its south face (toward the balcony's middle)"""
    return [("south", B_BH, 1), ("north", BAL_N - 1, -1)]


# frame members, centrelines (a, b) to (a, b): 2 x 3 tube on edge
LAND_FRAME = dict(LE=((1, 0), (1, LAND_N)), LS=((1, 1), (XL, 1)), LW=((XL - 1, 1), (XL - 1, LAND_N)),
                  LN=((1, B_LN), (XL - 1, B_LN)), LH=((A_LH, 1), (A_LH, LAND_N - 1)))
BAL_FRAME = dict(BE=((1, BAL_S), (1, BAL_N)), BS=((1, BAL_S + 1), (XL - 1, BAL_S + 1)), BH=((1, B_BH), (XL - 1, B_BH)),
                 BN=((1, BAL_N - 1), (XL, BAL_N - 1)), BW=((XL - 1, BAL_S), (XL - 1, BAL_N - 1)))
LAND_LAGS = dict(LE=(4.0, 16.0, 27.0) if MONO else (4.0, 20.0, 32.0), LS=(8.0, 22.0))          # along each ledger, assumed stud or blocking positions
BAL_LAGS = (BAL_S + 3, B_BH - 3.5, (BAL_S + BAL_N) / 2, BAL_N - 3) if MONO else (BAL_S + 3, (BAL_S + BAL_N) / 2, BAL_N - 3)   # round 8: a 4th bolt beside the head beam, holes drilled tight
# round 8 (Maxwell 11/24/2026): the upper stringer's head pushes the balcony north along the wall, carried by these bolts in shear. A flat
# bar diagonal under the frame was tried in the frame model and changed nothing (the frame does not rack; what moves is the bolts' give),
# so the fix is a 4th bolt by the head beam and tight holes.
LAND_STRIPS = (4.0, 9.5, 15.0, 20.5, 26.0) if MONO else (4.0, 9.5, 15.0, 20.5, 26.0, 30.5)                # deck boards run east to west on the landing: analysis strips at these b
BAL_STRIPS = (4.0, 9.0, 14.0, 19.0)                             # and north to south on the balcony: strips at these a

NEWEL_TOP = UPPER.zn(XL + POST - B0) + HR + 1.5                 # corner newel, a little above the upper rail
GSW_TOP_OLD = max(UPPER.zn(BAL_S - B0) + HR + 1.5, FL + GUARD_H)                       # top newel at the balcony's south west corner
G_TOP = FL + GUARD_H                                            # top of the balcony guard rail
GP_B = BAL_N + 0.375 + POST / 2 if MONO else BAL_N + POST / 2  # north guard posts stand outside the north face (mono: outside the north west post's L plate)
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
    CHEEK = [(SAD_U0, Z_SEAT - BRKT_T), (SAD_U0, Z_SEAT + CHEEK_H), (CHEEK_U1, Z_SEAT + CHEEK_H), (CHEEK_U1, Z_SEAT - BRKT_T)]
    SAD_BOLT = (SAD_U1 - 0.15, Z_SEAT + 0.85)         # cheek bolt toward the back, where the cheek is taller
    TAB_Z = (Z_SEAT + 0.2, ZP - TTD - 0.1)             # foot tab against the landing north beam's north face, under the oak; starts above the
                                                      # cheek's bend so it folds off flat cheek (flat pattern: 0.26 in clear of the bend line)
    TAB_W = 2.0                                       # tab reaches this far out from the cheek
    TAB_BOLT_Z = (TAB_Z[0] + TAB_Z[1]) / 2
    SAD_LEG = 3.5                                     # legs down the post faces, one through bolt 2 in down



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
