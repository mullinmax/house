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
RI, GO, TD, TT = L["floor_height"] * 12 / NR, L["ladder_going_in"], L["ladder_tread_in"], 1.44
TW, TDp = L.get("ladder_mono_in", [4.0, 4.0]) if MONO else L.get("ladder_tube_in", [2.0, 3.0])
WT = 0.25 if MONO else 0.1875                     # nominal stringer wall
FW, FD = 2.0, 3.0                                 # landing and balcony frame tube, on edge
FT_L, FT_B = (0.125, 0.1875) if MONO else (0.1875, 0.1875)   # frame tube walls: the corner landing now stands on posts, so its frame is 1/8 wall (Maxwell 11/22/2026: less metal)
WALL_RAIL = bool(L.get("ladder_wall_rail", True))   # wall side handrails; code wants rails on both sides of a ships ladder, Maxwell asked to hide them for now
RT, RH = (0.75, 2.0) if MONO else (0.0, 0.0)      # mono: an oak riser lip behind every tread; the 2 in steel strip under the tread above closes the rest (Maxwell 11/22/2026 round 3)
WEB0, BOLT_N, LAP, SEAT_W = (4.5, 1.5, 3.0, 3.5) if MONO else (3.75, 1.25, 2.25, 2.5)   # tread bracket: web start behind the nosing, bolt line below the tube top, lap, seat width
# Mono tread support (Maxwell 11/22/2026 PM): a flat plate ARM on edge crosses over the stringer under each tread and reaches near both tread ends.
# Each bracket web has a flange folded off its vertical front edge that bolts to the arm, so the load goes into the webs in their own plane.
# The earlier seat only bracket (SEAT_W wide bent seat) bent like a diving board: tools/ladder_drawings/bracket_solid_fea.py has that study.
# Round 3 (Maxwell 11/22/2026 night): the arm is now a narrow STRIP of constant depth, one bolt through each bracket flange, a screw tab at each
# end into the tread. It hangs just behind the riser lip of the tread below, so it is also the top of the riser and the lip can be shorter.
BRKT_T = 0.25                                     # web and strip plate
ARM_D, ARM_END = 2.0, 1.2                         # strip depth; its ends stop this far inside the tread ends
ARM_FL, SEAT_TAB, FOOT_W = 1.75, 1.5, 3.5         # web's bolting flange, the small seat tab behind it, first bracket's foot flange
SEAT_S = WEB0 + 1.0                               # seat tab starts 1 in behind the flange fold, so the two bends are not on top of each other
FLANGE_BOLT = 1.0                                 # the one flange bolt, this far below the tread
STRIP_TAB = 1.4                                   # screw tabs at the strip ends: this far in from each end, to the screw; they fold toward the back of the tread (Maxwell 11/23/2026)
WN, GAP = L["ladder_width_in"], L["ladder_wall_gap_in"]
HR = L.get("ladder_handrail_in", 32.0)
SL = RI / GO
ANG = math.atan(SL)
PL = TDp / math.cos(ANG)                          # tube depth measured plumb
ZP, FL = N_LO * RI, NR * RI                       # corner landing top, loft floor
TK = L.get("ladder_platform_in", TT + FD)        # platform build up: oak deck on a tube frame
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


LOWER = Flight("lower", 0.0, N_LO, lambda u, v: (XL + UL - u, XL - v))    # climbs east, open side north
UPPER = Flight("upper", ZP, N_UP, lambda u, v: (XL - v, B0 + u), ZP - TT if MONO else None)          # climbs north, open side west
FLIGHTS = (LOWER, UPPER)

ZLF, ZBF = ZP - TT - FD / 2, FL - TT - FD / 2    # frame centre heights: landing, balcony
A_LH = XL + UL - LOWER.uhc                        # landing header, over the lower tubes' heads
# Round 4 (Maxwell 11/23/2026): the upper stringer leans like a ladder. Its top runs past the plumb cut line and is notched: the part above the
# balcony frame's underside stops against the head beam's south face (U_BEAR), the rest passes under the beam to its north face (U_END).
# Its foot is cut plumb against the landing's north beam and stands on one 3 x 3 post. Angle clips lock both ends.
U_BEAR = UPPER.u2 + 1.0 if MONO else None
U_END = U_BEAR + FW if MONO else None
U_FOOT = UPPER.u0 if MONO else None                # plumb cut foot, against the landing's north beam
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
A_BR = XL - 2.0 if MONO else 17.0                 # knee brace: where it meets the balcony frame (mono: one 45 degree brace from the north west corner to the wall, Maxwell 11/22/2026)
BRACE = A_BR - 1.0 if MONO else 16.0              # its rise

# frame members, centrelines (a, b) to (a, b): 2 x 3 tube on edge
LAND_FRAME = dict(LE=((1, 0), (1, LAND_N)), LS=((1, 1), (XL, 1)), LW=((XL - 1, 1), (XL - 1, LAND_N)),
                  LN=((1, B_LN), (XL - 1, B_LN)), LH=((A_LH, 1), (A_LH, LAND_N - 1)))
BAL_FRAME = dict(BE=((1, BAL_S), (1, BAL_N)), BS=((1, BAL_S + 1), (XL - 1, BAL_S + 1)), BH=((1, B_BH), (XL - 1, B_BH)),
                 BN=((1, BAL_N - 1), (XL, BAL_N - 1)), BW=((XL - 1, BAL_S), (XL - 1, BAL_N - 1)))
LAND_LAGS = dict(LE=(4.0, 16.0, 27.0) if MONO else (4.0, 20.0, 32.0), LS=(8.0, 22.0))          # along each ledger, assumed stud or blocking positions
BAL_LAGS = (BAL_S + 3, (BAL_S + BAL_N) / 2, BAL_N - 3)
LAND_STRIPS = (4.0, 9.5, 15.0, 20.5, 26.0) if MONO else (4.0, 9.5, 15.0, 20.5, 26.0, 30.5)                # deck boards run east to west on the landing: analysis strips at these b
BAL_STRIPS = (4.0, 9.0, 14.0, 19.0)                             # and north to south on the balcony: strips at these a

NEWEL_TOP = UPPER.zn(XL + POST - B0) + HR + 1.5                 # corner newel, a little above the upper rail
GSW_TOP_OLD = max(UPPER.zn(BAL_S - B0) + HR + 1.5, FL + GUARD_H)                       # top newel at the balcony's south west corner
G_TOP = FL + GUARD_H                                            # top of the balcony guard rail
GP_B = BAL_N + 0.375 + POST / 2 if MONO else BAL_N + POST / 2  # north guard posts stand outside the north face (mono: outside the north west post's L plate)
# corner landing posts (Maxwell 11/22/2026 round 3): 2 x 2 posts from the slab to the two ends of the north beam, which carries the upper stringer's foot
LAND_POSTS = {}                                   # round 3's corner posts, dropped in round 4 for the one stringer post
UP_POST_W = 3.0                                   # round 4: 3 x 3 x 3/16 post under the upper stringer's foot, on a 4 anchor plate
UP_POST = (XL - VC - UP_POST_W / 2, XL - VC + UP_POST_W / 2, LAND_N + 0.5, LAND_N + 0.5 + UP_POST_W) if MONO else None


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


POST_S = dict(foot=FOOT_U, newel=rail_s(PC, PC), gsw=rail_s(PC, BAL_S + POST / 2), nw=rail_s(PC, GP_B), ne=rail_s(POST / 2, GP_B)) if MONO else {}
NEWEL_TOP2 = rail_under(PC, PC) if MONO else NEWEL_TOP                  # mono: posts stop under the rail
GSW_TOP = rail_under(PC, BAL_S + POST / 2) if MONO else GSW_TOP_OLD

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
    s_ = rail_s((a0 + a1) / 2, (b0 + b1) / 2)
    pa, pb = rail_plan(s_)
    qa, qb = rail_plan(min(s_ + 0.05, S_END))
    ra, rb = rail_plan(max(s_ - 0.05, 0.0))
    ta, tb = qa - ra, qb - rb
    n_ = math.hypot(ta, tb)
    ta, tb, m_ = ta / n_, tb / n_, rail_slope(s_)
    z0 = rail_z(s_) - rail_depth(s_) - gap
    return lambda a, b: z0 + m_ * ((a - pa) * ta + (b - pb) * tb)


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
