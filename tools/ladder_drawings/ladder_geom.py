"""Shared geometry for the loft corner ships ladder structure: tube stringers, landing, balcony, posts and rails.

Local inch coordinates: a = west of the bath 1 wall's west face, b = north of the clerestory wall's north face, z = above the slab.
Everything is derived from model/config.toml [loft], the same numbers model/ladder_options.py draws in the walkthrough.
PRELIMINARY: for an engineer's review, not for construction.
"""
import math, os, tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
L = tomllib.load(open(os.path.join(HERE, "..", "..", "model", "config.toml"), "rb"))["loft"]
assert L.get("ladder_stringer") == "tube"
NR, N_LO = L["ladder_risers"], int(L.get("ladder_lower_risers", 5))
N_UP = NR - N_LO
RI, GO, TD, TT = L["floor_height"] * 12 / NR, L["ladder_going_in"], L["ladder_tread_in"], 1.44
TW, TDp = L.get("ladder_tube_in", [2.0, 3.0])
WT = 0.1875                                       # nominal tube wall
WN, GAP = L["ladder_width_in"], L["ladder_wall_gap_in"]
HR = L.get("ladder_handrail_in", 32.0)
SL = RI / GO
ANG = math.atan(SL)
PL = TDp / math.cos(ANG)                          # tube depth measured plumb
ZP, FL = N_LO * RI, NR * RI                       # corner landing top, loft floor
TK = L.get("ladder_platform_in", TT + TDp)        # platform build up: oak deck on a tube frame
XL = WN + GAP                                     # open (west) edge of the upper flight and of both platforms
UL = (N_LO - 1) * GO + (TD - GO)                  # lower flight, first nosing to the landing edge
UU = (N_UP - 1) * GO + (TD - GO)
B0 = XL + 1.2                                     # upper flight's first nosing
LAND_N = B0 + 8.0                                 # corner landing's north edge, under the upper flight's first tread
BAL_S, BAL_N = B0 + UU, B0 + UU + WN + 1.2        # balcony
NOSE = TD - GO                                    # oak nosing past each platform's frame
POST, RAIL, RAIL_T = 2.0, 1.5, 0.1875             # square tube posts (3/16 wall) and rails (1/8 wall)
GUARD_H = 36.0
PICKET = 0.5


class Flight:
    def __init__(self, name, z0, nr, ab):
        self.name, self.z0, self.nr, self.ab = name, z0, nr, ab          # ab(u, v) -> (a, b)
        self.zn = lambda u: z0 + RI + u * SL                             # nosing line
        self.zl = lambda u: z0 + RI + (u - TD) * SL - TT                 # tube top
        self.zc = lambda u: self.zl(u) - PL / 2                          # tube centreline
        self.zu = z0 + nr * RI - TK                                      # underside of the platform at the head
        self.u0 = TD - (RI - TT) / SL                                    # tube top meets the foot level
        self.u1 = self.u0 + PL / SL
        self.u2 = self.u0 + (nr * RI - TK) / SL                          # tube top meets the platform underside
        self.u3 = self.u2 + PL / SL
        self.ufc, self.uhc = self.u0 + PL / 2 / SL, self.u2 + PL / 2 / SL    # centreline at the foot and head cuts
        self.vt = (TW / 2, WN - TW / 2)                                  # tube centrelines: open side, wall side

    def p(self, u, v, z):
        a, b = self.ab(u, v)
        return (a, b, z)

    def uk(self, k):
        return (k - 1) * GO

    def bolt_u(self, k):                                                 # centroid of tread k's two bracket bolts, along u
        return self.uk(k) + 3.75 + 6.25 * math.cos(ANG) + 1.25 * math.sin(ANG)


LOWER = Flight("lower", 0.0, N_LO, lambda u, v: (XL + UL - u, XL - v))    # climbs east, open side north
UPPER = Flight("upper", ZP, N_UP, lambda u, v: (XL - v, B0 + u))          # climbs north, open side west
FLIGHTS = (LOWER, UPPER)

ZLF, ZBF = ZP - TT - TDp / 2, FL - TT - TDp / 2    # frame centre heights: landing, balcony
A_LH = XL + UL - LOWER.uhc                        # landing header, over the lower tubes' heads
B_BH = B0 + UPPER.uhc                             # balcony arm over the upper tubes' heads
B_UF = B0 + UPPER.ufc                             # upper tubes' feet on the landing
PC = XL + POST / 2                                # posts stand outside the open edge, lapped onto the tubes and frames
FOOT_U = 12.0                                     # lower flight foot post
A_FOOT = XL + UL - FOOT_U
BRACE = 16.0                                      # knee brace rise and run
A_BR = 17.0

# frame members, centrelines (a, b) to (a, b): 2 x 3 tube on edge
LAND_FRAME = dict(LE=((1, 0), (1, LAND_N)), LS=((1, 1), (XL, 1)), LW=((XL - 1, 1), (XL - 1, LAND_N)),
                  LN=((1, LAND_N - 1), (XL - 1, LAND_N - 1)), LH=((A_LH, 1), (A_LH, LAND_N - 1)))
BAL_FRAME = dict(BE=((1, BAL_S), (1, BAL_N)), BS=((1, BAL_S + 1), (XL - 1, BAL_S + 1)), BH=((1, B_BH), (XL - 1, B_BH)),
                 BN=((1, BAL_N - 1), (XL, BAL_N - 1)), BW=((XL - 1, BAL_S), (XL - 1, BAL_N - 1)))
LAND_LAGS = dict(LE=(4.0, 20.0, 32.0), LS=(8.0, 22.0))          # along each ledger, assumed stud or blocking positions
BAL_LAGS = (BAL_S + 3, (BAL_S + BAL_N) / 2, BAL_N - 3)
LAND_STRIPS = (4.0, 9.5, 15.0, 20.5, 26.0, 30.5)                # deck boards run east to west on the landing: analysis strips at these b
BAL_STRIPS = (4.0, 9.0, 14.0, 19.0)                             # and north to south on the balcony: strips at these a

NEWEL_TOP = UPPER.zn(XL + POST - B0) + HR + 1.5                 # corner newel, a little above the upper rail
GSW_TOP = UPPER.zn(BAL_S - B0) + HR + 1.5                       # top newel at the balcony's south west corner
G_TOP = FL + GUARD_H                                            # top of the balcony guard rail
GP_B = BAL_N + POST / 2                                         # north guard posts stand outside the north face

if __name__ == "__main__":
    for f in FLIGHTS:
        print(f.name, "foot cut u", round(f.u0, 2), round(f.u1, 2), "head cut u", round(f.u2, 2), round(f.u3, 2), "zu", round(f.zu, 2))
    print("ZP", round(ZP, 3), "FL", round(FL, 3), "TK", TK, "XL", XL, "B0", B0, "LAND_N", LAND_N, "BAL", BAL_S, BAL_N)
    print("A_LH", round(A_LH, 2), "B_BH", round(B_BH, 2), "B_UF", round(B_UF, 2), "newel top", round(NEWEL_TOP, 1), "GSW top", round(GSW_TOP, 1))
