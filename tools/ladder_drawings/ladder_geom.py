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
RT, RH = (0.75, 4.0) if MONO else (0.0, 0.0)      # mono: an oak riser lip behind every tread, tall enough to leave under 4 in open above it
WEB0, BOLT_N, LAP, SEAT_W = (4.5, 1.5, 3.0, 3.5) if MONO else (3.75, 1.25, 2.25, 2.5)   # tread bracket: web start behind the nosing, bolt line below the tube top, lap, seat width
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
B_BH = B0 + UPPER.uhc                             # balcony arm over the upper tubes' heads
B_UF = B0 + UPPER.ufc                             # upper tubes' feet on the landing
LN_W = 4.0 if MONO else 2.0                       # landing north beam width (mono: a 4 x 3 tube laid flat, as wide as the stringer foot that stands on it)
LAND_N = B0 + 8.0 if not MONO else B_UF + LN_W / 2          # corner landing frame's north edge (mono: flush with the north beam, nothing past it)
LAND_DECK_N = B0 + TD - GO if MONO else LAND_N    # mono: the landing's oak ends like a tread, at the front of the riser lip under the upper flight's first tread (Maxwell 11/22/2026)
B_LN = B_UF if MONO else LAND_N - 1               # landing north beam: under the centre stringer's foot, or at the edge
VC = WN / 2
PC = XL + POST / 2                                # posts stand outside the open edge, lapped onto the tubes and frames
FOOT_U = 4.0 if MONO else 12.0                   # lower flight foot post (mono: beside the first tread on a 4 anchor moment base plate)
A_FOOT = XL + UL - FOOT_U
A_BR = XL - 2.0 if MONO else 17.0                 # knee brace: where it meets the balcony frame (mono: one 45 degree brace from the north west corner to the wall, Maxwell 11/22/2026)
BRACE = A_BR - 1.0 if MONO else 16.0              # its rise
KICK = 9.0                                        # mono: kicker rise and run under the balcony's west beam

# frame members, centrelines (a, b) to (a, b): 2 x 3 tube on edge
LAND_FRAME = dict(LE=((1, 0), (1, LAND_N)), LS=((1, 1), (XL, 1)), LW=((XL - 1, 1), (XL - 1, LAND_N)),
                  LN=((1, B_LN), (XL - 1, B_LN)), LH=((A_LH, 1), (A_LH, LAND_N - 1)))
BAL_FRAME = dict(BE=((1, BAL_S), (1, BAL_N)), BS=((1, BAL_S + 1), (XL - 1, BAL_S + 1)), BH=((1, B_BH), (XL - 1, B_BH)),
                 BN=((1, BAL_N - 1), (XL, BAL_N - 1)), BW=((XL - 1, BAL_S), (XL - 1, BAL_N - 1)))
LAND_LAGS = dict(LE=(4.0, 20.0, 32.0), LS=(8.0, 22.0))          # along each ledger, assumed stud or blocking positions
BAL_LAGS = (BAL_S + 3, (BAL_S + BAL_N) / 2, BAL_N - 3)
LAND_STRIPS = (4.0, 9.5, 15.0, 20.5, 26.0) if MONO else (4.0, 9.5, 15.0, 20.5, 26.0, 30.5)                # deck boards run east to west on the landing: analysis strips at these b
BAL_STRIPS = (4.0, 9.0, 14.0, 19.0)                             # and north to south on the balcony: strips at these a

NEWEL_TOP = UPPER.zn(XL + POST - B0) + HR + 1.5                 # corner newel, a little above the upper rail
GSW_TOP = max(UPPER.zn(BAL_S - B0) + HR + 1.5, FL + GUARD_H)                       # top newel at the balcony's south west corner
G_TOP = FL + GUARD_H                                            # top of the balcony guard rail
GP_B = BAL_N + POST / 2                                         # north guard posts stand outside the north face

if __name__ == "__main__":
    for f in FLIGHTS:
        print(f.name, "foot cut u", round(f.u0, 2), round(f.u1, 2), "head cut u", round(f.u2, 2), round(f.u3, 2), "zu", round(f.zu, 2))
    print("ZP", round(ZP, 3), "FL", round(FL, 3), "TK", TK, "XL", XL, "B0", B0, "LAND_N", LAND_N, "BAL", BAL_S, BAL_N)
    print("A_LH", round(A_LH, 2), "B_BH", round(B_BH, 2), "B_UF", round(B_UF, 2), "newel top", round(NEWEL_TOP, 1), "GSW top", round(GSW_TOP, 1))
