"""Frame finite element analysis of the loft ships ladder structure (PyNite beam elements, linear elastic).

Models both tube stringer flights with their tread brackets and treads, the corner landing frame and newel, the balcony frame with
its knee braces, and the posts and rails. Loads follow the residential code table (IRC / RCO Table R301.5): 40 psf or a 300 lb
concentrated load on the stairs, 200 lb in any direction on handrails and guards. PRELIMINARY: for an engineer's review.
Run: python3 tools/ladder_drawings/ladder_fea.py OUTDIR      (pip install PyNiteFEA)
"""
import json, math, os, sys
from Pynite import FEModel3D
import ladder_geom as G

OUT = sys.argv[1] if len(sys.argv) > 1 else "."
POST_BASE = os.environ.get("LADDER_POST_BASE", "fixed")       # upper stringer post base: fixed (default) or pinned
HEAD_VERT = os.environ.get("LADDER_HEAD_VERT", "0") == "1"    # upper stringer head clips carry weight too (round holes), default no (vertical slots)
os.makedirs(OUT, exist_ok=True)
FY_STEEL, FB_OAK = 46000.0, 1150.0            # A500 Gr B yield; white oak allowable bending (No. 1 class, before adjustment factors)
ALLOW = 0.6 * FY_STEEL
m = FEModel3D()
m.add_material("steel", 29e6, 11.2e6, 0.3, 0.2836)
m.add_material("oak", 1.6e6, 0.1e6, 0.35, 0.027)
m.add_material("link", 29e6, 11.2e6, 0.3, 0.0)
def rect_hss(B, H, t):
    """rectangular tube B wide by H tall, nominal wall t (design wall 0.93 t): (A, Iy weak about vertical, Iz about horizontal, J, Sy, Sz)"""
    t = 0.93 * t
    A = B * H - (B - 2 * t) * (H - 2 * t)
    Iz = (B * H ** 3 - (B - 2 * t) * (H - 2 * t) ** 3) / 12
    Iy = (H * B ** 3 - (H - 2 * t) * (B - 2 * t) ** 3) / 12
    J = 2 * t * (B - t) ** 2 * (H - t) ** 2 / (B + H - 2 * t)
    return (A, Iy, Iz, J, Iy / (B / 2), Iz / (H / 2))


# name: (material, A, Iy, Iz, J, Sy, Sz)    local z is horizontal for sloped and level members
SEC = dict(TUBE=("steel", 1.54, 0.932, 1.77, 1.90, 0.932, 1.18),          # HSS 3 x 2 x 3/16 on edge (design wall 0.174)
           POST=("steel", 1.19, 0.641, 0.641, 1.09, 0.641, 0.641),        # HSS 2 x 2 x 3/16
           RAIL=("steel", 0.84, 0.235, 0.235, 0.41, 0.313, 0.313),        # HSS 1 1/2 x 1 1/2 x 3/16
           BRKT=("steel", 1.19, 0.0062, 2.23, 0.025, 0.0495, 0.94),       # 1/4 x 4 3/4 bracket web
           TREAD=("oak", 8.5 * 1.44, 1.44 * 8.5 ** 3 / 12, 8.5 * 1.44 ** 3 / 12, 7.5, 1.44 * 8.5 ** 2 / 6, 8.5 * 1.44 ** 2 / 6),
           DECKL=("oak", 5.73 * 1.44, 1.44 * 5.73 ** 3 / 12, 5.73 * 1.44 ** 3 / 12, 4.8, 1.44 * 5.73 ** 2 / 6, 5.73 * 1.44 ** 2 / 6),
           DECKB=("oak", 6.3 * 1.44, 1.44 * 6.3 ** 3 / 12, 6.3 * 1.44 ** 3 / 12, 5.3, 1.44 * 6.3 ** 2 / 6, 6.3 * 1.44 ** 2 / 6),
           STR=("steel", 3.37, 7.80, 7.80, 12.8, 3.90, 3.90) if G.MONO else ("steel", 1.54, 0.932, 1.77, 1.90, 0.932, 1.18),   # stringer: HSS 4 x 4 x 1/4, or the 3 x 2
           BRKT2=("steel", 2.38, 10.7, 4.46, 1.0, 4.5, 1.88),              # mono: a pair of 1/4 x 4 3/4 webs, one each side of the tube
           ARM=("steel", 0.25 * G.ARM_D, G.ARM_D * 0.25 ** 3 / 12, 0.25 * G.ARM_D ** 3 / 12, G.ARM_D * 0.25 ** 3 / 3, G.ARM_D * 0.25 ** 2 / 6, 0.25 * G.ARM_D ** 2 / 6),   # mono: 1/4 x 2 in plate strip on edge under each tread
           STRUT=("steel", 0.84, 0.235, 0.235, 0.41, 0.313, 0.313),        # mono: 1 1/2 in square tube ties from the foot post and balcony newel to the stringer
           RIGID=("link", 20.0, 20.0, 20.0, 20.0, 1e9, 1e9))
if G.MONO:                                          # round 3: the corner landing's frame is 1/8 wall; its north beam is a 4 x 3 laid flat
    SEC["TUBEL"] = ("steel",) + rect_hss(2.0, 3.0, G.FT_L)
    SEC["LN43"] = ("steel",) + rect_hss(4.0, 3.0, G.FT_L)
else:
    SEC["TUBEL"] = SEC["LN43"] = SEC["TUBE"]
for k_, s_ in SEC.items():
    m.add_section(k_, *s_[1:5])

NODES, MEM, SUP = {}, {}, {}


def N(a, b, z):
    key = (round(a, 3), round(b, 3), round(z, 3))
    if key not in NODES:
        NODES[key] = f"N{len(NODES)}"
        m.add_node(NODES[key], b, z, -a)          # PyNite: X north, Y up, Z east
    return NODES[key]


def M(name, p, q, sec, rel=""):
    """rel: 'i', 'j' or 'ij' = bending released at that end; 'I' / 'J' = a ball joint (torsion released too)"""
    m.add_member(name, N(*p), N(*q), SEC[sec][0], sec)
    r = dict(Ryi="i" in rel or "I" in rel, Rzi="i" in rel or "I" in rel, Rxi="I" in rel, Ryj="j" in rel or "J" in rel, Rzj="j" in rel or "J" in rel, Rxj="J" in rel)
    if any(r.values()):
        m.def_releases(name, **r)
    MEM[name] = (sec, p, q)
    return name


def S(p, dx=True, dy=True, dz=True, what=""):
    """support: translations along b (north), z (up) and a (west)"""
    n = N(*p)
    m.def_support(n, dx, dy, dz, False, False, False)
    SUP[n] = what
    return n


TREADS, RAILS = {}, {}
LO, UP = G.LOWER, G.UPPER
if G.MONO:
    VC, SE = G.VC, G.VC - G.ARM_END                          # centre, and how far the arm reaches each side of it
    for f in G.FLIGHTS:
        fn = f.name[0].upper()
        if f is UP:                                      # round 4: plumb foot on a post against the landing beam, notched head leaning on the balcony beam
            foot, head = f.p(G.U_FOOT, VC, f.zc(G.U_FOOT)), f.p(G.U_BEAR, VC, f.zc(G.U_BEAR))
        else:
            foot, head = f.p(f.ufc, VC, f.zf), f.p(f.uhc, VC, f.zu)
        M(f"{fn}tube_c", foot, head, "STR")
        f.ends = dict(c=(foot, head))
        for nm, pc, half in (("foot", foot, 4.0 if f is LO else G.TW / 2 + 0.125), ("head", head, G.TW / 2 + 0.125)):      # anchors or clips each side of the tube resist its twist
            u_ = (G.U_FOOT if nm == "foot" else G.U_BEAR) if f is UP else (f.ufc if nm == "foot" else f.uhc)
            M(f"{fn}{nm}bar", f.p(u_, VC - half, pc[2]), f.p(u_, VC + half, pc[2]), "RIGID")
            f.ends[nm] = (f.p(u_, VC - half, pc[2]), f.p(u_, VC + half, pc[2]))
        for k in range(1, f.nr):
            ub = f.bolt_u(k)
            pb, pt = f.p(ub, VC, f.zc(ub)), f.p(f.uk(k) + 4.25, VC, f.z0 + k * G.RI - G.TT / 2)
            M(f"{fn}brkt{k}c", pb, pt, "BRKT2")
            VB = G.TW / 2 + G.BRKT_T + 0.95                    # the one flange bolt each side of the stringer
            e = {s_: f.p(f.uk(k) + 4.25, v_, pt[2]) for s_, v_ in (("o", 0.0), ("so", VC - SE), ("bo", VC - VB), ("bw", VC + VB), ("sw", VC + SE), ("w", G.WN))}
            M(f"{fn}tread{k}o", e["o"], e["so"], "TREAD")     # the tread only spans the last 1.2 in past each strip end; the strip is checked as if the oak gave it no help
            M(f"{fn}seat{k}", e["so"], e["bo"], "ARM")
            M(f"{fn}flange{k}o", e["bo"], pt, "RIGID")         # strip bolts to the two bracket flanges
            M(f"{fn}flange{k}w", pt, e["bw"], "RIGID")
            M(f"{fn}seat{k}w", e["bw"], e["sw"], "ARM")
            M(f"{fn}tread{k}w", e["sw"], e["w"], "TREAD")
            TREADS[(fn, k)] = dict(o=e["o"], w=e["w"], mid=pt, members=(f"{fn}tread{k}o", f"{fn}seat{k}", f"{fn}flange{k}o", f"{fn}flange{k}w", f"{fn}seat{k}w", f"{fn}tread{k}w"))
    for i in (0, 1):
        S(LO.ends["foot"][i], what="lower stringer foot anchor (first bracket's foot flange)")
else:
  for f in G.FLIGHTS:
    fn = f.name[0].upper()
    ends = {}
    for side, v in (("o", f.vt[0]), ("w", f.vt[1])):
        vs = G.TW + 0.125 if side == "o" else G.WN - G.TW - 0.125          # bracket web plane
        foot, head = f.p(f.ufc, v, f.z0), f.p(f.uhc, v, f.zu)
        M(f"{fn}tube_{side}", foot, head, "STR")
        ends[side] = (foot, head)
        for k in range(1, f.nr):
            ub = f.bolt_u(k)
            pb, ps = f.p(ub, v, f.zc(ub)), f.p(ub, vs, f.zc(ub))
            pt = f.p(f.uk(k) + 4.25, vs, f.z0 + k * G.RI - G.TT / 2)
            M(f"{fn}stub{k}{side}", pb, ps, "RIGID")
            M(f"{fn}brkt{k}{side}", ps, pt, "BRKT")
            TREADS.setdefault((fn, k), {})[side] = pt
    for (fn_, k), e in TREADS.items():
        if fn_ == fn:
            mid = tuple((x + y) / 2 for x, y in zip(e["o"], e["w"]))
            N(*mid)
            M(f"{fn}tread{k}", e["o"], e["w"], "TREAD")
            TREADS[(fn_, k)]["mid"] = mid
            TREADS[(fn_, k)]["members"] = (f"{fn}tread{k}",)
    f.ends = ends
  # wall tabs: lag the wall side tubes to blocking (restraint normal to the wall only, so the platforms carry the weight in this model)
  for k in (2, 4):
    S(LO.p(LO.bolt_u(k), LO.vt[1], LO.zc(LO.bolt_u(k))), True, False, False, "lower flight wall tab")
  for k in (2, 4, 6):
    S(UP.p(UP.bolt_u(k), UP.vt[1], UP.zc(UP.bolt_u(k))), False, False, True, "upper flight wall tab")
  for side in "ow":
    S(LO.ends[side][0], what=f"lower flight foot on the slab ({'open' if side == 'o' else 'wall'} side)")

# corner landing frame
ZL, ZB, XW = G.ZLF, G.ZBF, G.XL - 1
M("LE", (1, 1, ZL), (1, G.B_LN, ZL), "TUBEL")
M("LS", (1, 1, ZL), (XW, 1, ZL), "TUBEL")
M("LW", (XW, 1, ZL), (XW, G.B_LN, ZL), "TUBEL")
M("LN", (1, G.B_LN, ZL), (XW, G.B_LN, ZL), "LN43")
M("LH", (G.A_LH, 1, ZL), (G.A_LH, G.B_LN, ZL), "TUBEL", "ij")
for nm, (a0_, a1_, b0_, b1_) in G.LAND_POSTS.items():          # round 3: posts from the slab to both ends of the north beam
    pa_ = 1 if nm == "ne" else XW
    M(f"Lpost_{nm}", (pa_, G.B_LN, 0.0), (pa_, G.B_LN, ZL), "POST", "j")
    S((pa_, G.B_LN, 0.0), what=f"landing post base on the slab ({nm})")
for b in G.LAND_LAGS["LE"]:
    S((1, b, ZL), what="landing east ledger lag")
for a in G.LAND_LAGS["LS"]:
    S((a, 1, ZL), what="landing south ledger lag")
for i, b in enumerate(G.LAND_STRIPS):
    N(G.A_LH, b, ZL); N(10.5, b, ZL)
    M(f"Ldeck{i}", (1, b, ZL), (XW, b, ZL), "DECKL", "ij")
# flights onto the landing
if G.MONO:
    for i, nm in enumerate("ab"):
        ph, pf = LO.ends["head"][i], UP.ends["foot"][i]
        M(f"Lhead_{nm}", (ph[0], ph[1], ZL), ph, "RIGID", "J")
        M(f"Ufoot_{nm}", (pf[0], G.B_LN, ZL), pf, "RIGID", "J")         # angle clip each side to the landing's north beam
    # round 4: one 3 x 3 x 3/16 post on a 4 anchor plate under the upper stringer's foot; its saddle ties it to the tube
    SEC["POST3"] = ("steel",) + rect_hss(3.0, 3.0, 0.1875)
    m.add_section("POST3", *SEC["POST3"][1:5])
    a0p, a1p, b0p, b1p = G.UP_POST
    upc = (b0p + b1p) / 2 - G.B0
    pc_ = UP.p(upc, VC, UP.zc(upc))
    ptop = (pc_[0], pc_[1], G.Z_SEAT - G.BRKT_T)        # round 5: the post's level top under the saddle seat
    fixed_ = POST_BASE == "fixed"                       # LADDER_POST_BASE=pinned: the 4 anchor plate taken as a pin, the bound on base flexibility
    m.def_support(N(pc_[0], pc_[1], 0.0), True, True, True, fixed_, fixed_, fixed_)
    SUP[N(pc_[0], pc_[1], 0.0)] = "upper stringer post base plate on the slab"
    M("Upost", (pc_[0], pc_[1], 0.0), ptop, "POST3")
    M("Upost_saddle", ptop, pc_, "RIGID")
else:
    M("Lhead_o", (G.A_LH, XW, ZL), LO.ends["o"][1], "RIGID", "J")
    M("Lhead_w", (G.A_LH, 1, ZL), LO.ends["w"][1], "RIGID", "J")
    M("Ufoot_o", (XW, G.B_UF, ZL), UP.ends["o"][0], "RIGID", "J")
    M("Ufoot_w", (1, G.B_UF, ZL), UP.ends["w"][0], "RIGID", "J")

# balcony frame, knee braces
BS1, BN1 = G.BAL_S + 1, G.BAL_N - 1
M("BE", (1, BS1, ZB), (1, BN1, ZB), "TUBE")
M("BS", (1, BS1, ZB), (XW, BS1, ZB), "TUBE", "i" if G.MONO else "ij")
M("BH", (1, G.B_BH, ZB), (XW, G.B_BH, ZB), "TUBE", "i")
M("BN", (1, BN1, ZB), (XW, BN1, ZB), "TUBE", "i")
M("BW", (XW, BS1, ZB), (XW, BN1, ZB), "TUBE")
for b in G.BAL_LAGS:
    S((1, b, ZB), what="balcony ledger bolt to the loft rim")
    m.def_support(N(1, b, ZB), True, True, True, True, False, False)   # the joists are pinned to the ledger: stop it rolling about its own length (a free mode some solvers reject)
for nm, b in (("BRh", G.B_BH), ("BRn", BN1)):      # mono round 5: a brace under the head beam too (Maxwell 11/23/2026)
    M(nm, (G.A_BR, b, ZB), (1, b, ZB - G.BRACE), "POST", "i")
    S((1, b, ZB - G.BRACE), what=f"knee brace wall bracket ({'south' if nm == 'BRh' else 'north'})")
for i, a in enumerate(G.BAL_STRIPS):
    N(a, G.B_BH, ZB); N(a, (G.B_BH + BN1) / 2, ZB)
    M(f"Bdeck{i}", (a, BS1, ZB), (a, BN1, ZB), "DECKB", "ij")
if G.MONO:
    for i, nm in enumerate("ab"):
        ph = UP.ends["head"][i]
        # the notched head only leans on the head beam: a link along b (bearing face) at each side, released so it carries no weight
        # slotted clips (default): the bolts can only push along the flight and sideways, so these links are pins with their twist released
        # too (a link that kept its twist would act as a pair of up and down bolt forces, which a vertical slot cannot give).
        # LADDER_HEAD_VERT=1: round holes, the clips also carry weight and the joint is fixed.
        M(f"Uhead_{nm}", ph, (ph[0], G.B_BH, ph[2]), "RIGID", "" if HEAD_VERT else "Ij")
        M(f"Uhead_{nm}_drop", (ph[0], G.B_BH, ph[2]), (ph[0], G.B_BH, ZB), "RIGID")
    ph = UP.ends["head"][0]                              # and the clips hold it sideways
    M("Uhead_side", ph, (ph[0] + 2.0, ph[1], ph[2]), "RIGID", "" if HEAD_VERT else "Ij")
    M("Uhead_side_drop", (ph[0] + 2.0, ph[1], ph[2]), (ph[0] + 2.0, G.B_BH, ZB), "RIGID")
else:
    M("Uhead_o", (XW, G.B_BH, ZB), UP.ends["o"][1], "RIGID", "J")
    M("Uhead_w", (1, G.B_BH, ZB), UP.ends["w"][1], "RIGID", "J")

# posts and rails
PC = G.PC
if G.CONT_RAIL:
    # Round 3: ONE continuous rail from the lower flight's foot to the bath 1 wall, a chain of nodes along its centreline; every post's top
    # is tied to it (the post stops just under the rail, a bolted saddle joins them)
    PS = G.POST_S
    mids = dict(lo=(PS["foot"] + PS["newel"]) / 2, up=(PS["newel"] + PS["gsw"]) / 2, gw=(PS["gsw"] + PS["nw"]) / 2, gn=(PS["nw"] + PS["ne"]) / 2)
    st = []
    for s_ in G.rail_samples(extra=list(PS.values()) + list(mids.values())):
        if not st or s_ - st[-1] > 0.05:
            st.append(s_)
    RP = {}
    for s_ in st:
        a_, b_ = G.rail_plan(s_)
        RP[s_] = (a_, b_, G.rail_z(s_) - G.rail_depth(s_) / 2)
    for i, (s0, s1) in enumerate(zip(st, st[1:])):
        M(f"rail{i}", RP[s0], RP[s1], "RAIL")
    R_ = lambda s_: RP[min(RP, key=lambda x: abs(x - s_))]
    tip, mid_lo, mid_up, mid_gw, mid_gn = R_(0.0), R_(mids["lo"]), R_(mids["up"]), R_(mids["gw"]), R_(mids["gn"])
    # lower flight foot post on a 4 anchor moment base plate, its top under the rail
    af = G.A_FOOT
    fp = [(af, PC, 0.0), (af, PC, R_(PS["foot"])[2] / 2), R_(PS["foot"])]
    m.def_support(N(*fp[0]), True, True, True, True, True, True)
    SUP[N(*fp[0])] = "foot post base plate on the slab (moment base)"
    M("footpost0", fp[0], fp[1], "POST"); M("footpost1", fp[1], fp[2], "POST")
    # corner newel: slab to under the rail, lapped onto the landing's west beam
    rn = R_(PS["newel"])
    nwt = (PC, PC, G.NEWEL_TOP2)
    nw = [(PC, PC, 0.0), (PC, PC, ZL), nwt, rn, rn]
    S(nw[0], what="corner newel base on the slab")
    M("newel0", nw[0], nw[1], "POST"); M("newel1", nw[1], nwt, "POST")
    M("newel_rail", nwt, rn, "RIGID")
    M("newel_LW", nw[1], (XW, PC, ZL), "RIGID", "J")
    # balcony south west newel and north west post: outside the west beam on L plates, tops under the rail
    bsw = BS1
    rg = R_(PS["gsw"])
    gs = [(PC, bsw, ZB - 1.5), (PC, bsw, ZB), (PC, bsw, G.GSW_TOP), rg]
    M("gsw0", gs[0], gs[1], "POST"); M("gsw1", gs[1], gs[2], "POST"); M("gsw_rail", gs[2], rg, "RIGID")
    M("gsw_BW", gs[1], (XW, bsw, ZB), "RIGID")
    corner = R_(PS["nw"])
    gnt = (PC, G.GP_B, G.rail_under(PC, G.GP_B))
    M("gnw_BN", (PC, G.GP_B, ZB), (XW, BN1, ZB), "RIGID")
    M("gnw", (PC, G.GP_B, ZB), gnt, "POST"); M("gnw_rail", gnt, corner, "RIGID")
    rne = R_(PS["ne"])
    ne = [(1, G.GP_B, G.FL - 11), (1, G.GP_B, G.FL - 2), rne]
    S(ne[0], what="north east guard post lag (lower)"); S(ne[1], what="north east guard post lag (upper)")
    M("gne0", ne[0], ne[1], "POST"); M("gne1", ne[1], ne[2], "POST")
    gs = gs[:3] + [rg]
else:
    PC, RD = G.PC, G.RAIL / 2 / math.cos(G.ANG)
    zr_lo = lambda a: LO.zn(G.XL + G.UL - a) + G.HR - RD            # lower rail centreline
    zr_up = lambda b: UP.zn(b - G.B0) + G.HR - RD
    u_nw = G.XL + G.UL - PC
    # corner newel: slab to above the upper rail, lapped onto the lower open tube and the landing's west beam
    nw = [(PC, PC, 0.0), (PC, PC, LO.zc(u_nw)), (PC, PC, ZL), (PC, PC, zr_lo(PC)), (PC, PC, zr_up(PC)), (PC, PC, G.NEWEL_TOP)]
    S(nw[0], what="corner newel base on the slab")
    for i in range(5):
        M(f"newel{i}", nw[i], nw[i + 1], "POST")
    if not G.MONO:
        M("newel_tube", nw[1], (PC, XW, LO.zc(u_nw)), "RIGID")
    M("newel_LW", nw[2], (XW, PC, ZL), "RIGID", "J" if G.MONO else "")       # mono: every post lap is one bolt group, taken as a pin
    # lower flight foot post and rail
    af = G.A_FOOT
    if G.MONO:                                          # mono: the post stands beside the first tread on a 4 anchor base plate that carries moment
        fp = [(af, PC, 0.0), (af, PC, zr_lo(af) / 2), (af, PC, zr_lo(af))]
        m.def_support(N(*fp[0]), True, True, True, True, True, True)
        SUP[N(*fp[0])] = "foot post base plate on the slab (moment base)"
        M("footpost0", fp[0], fp[1], "POST"); M("footpost1", fp[1], fp[2], "POST")
    else:
        fp = [(af, PC, 0.0), (af, PC, LO.zc(G.FOOT_U)), (af, PC, zr_lo(af))]
        S(fp[0], what="foot post base on the slab")
        M("footpost0", fp[0], fp[1], "POST"); M("footpost1", fp[1], fp[2], "POST")
        M("foot_tube", fp[1], (af, XW, LO.zc(G.FOOT_U)), "RIGID")
    tip = (G.XL + G.UL, PC, zr_lo(G.XL + G.UL))
    mid_lo = ((af + PC) / 2, PC, zr_lo((af + PC) / 2))
    N(*mid_lo)
    M("rail_lower", tip, nw[3], "RAIL", "j")
    # balcony south west newel: lapped onto the upper open tube and the balcony's west beam
    bsw = BS1
    u_sw = bsw - G.B0
    gs = [(PC, bsw, ZB - 1.5 if G.MONO else UP.zc(u_sw)), (PC, bsw, ZB), (PC, bsw, zr_up(bsw)), (PC, bsw, G.G_TOP - 0.75), (PC, bsw, G.GSW_TOP)]
    for i in range(4):
        M(f"gsw{i}", gs[i], gs[i + 1], "POST")
    if not G.MONO:
        M("gsw_tube", gs[0], (XW, bsw, UP.zc(u_sw)), "RIGID")
    M("gsw_BW", gs[1], (XW, bsw, ZB), "RIGID")       # mono: an L plate bolted to the south beam and up the post carries the post's moment into the frame
    mid_up = (PC, (PC + bsw) / 2, zr_up((PC + bsw) / 2))
    N(*mid_up)
    M("rail_upper", nw[4], gs[2], "RAIL", "ij")
    # balcony guard
    zg = G.G_TOP - 0.75
    if G.MONO:                                          # the north west post: outside the west beam, north of its own L plate (round 3)
        corner = (PC, G.GP_B, zg)
        M("gnw_BN", (PC, G.GP_B, ZB), (XW, BN1, ZB), "RIGID")
        M("gnw", (PC, G.GP_B, ZB), corner, "POST")
    else:
        corner = (PC, G.GP_B, zg)
        M("gnw_BN", (XW, G.GP_B, ZB), (XW, BN1, ZB), "RIGID")
        M("gnw", (XW, G.GP_B, ZB), (XW, G.GP_B, zg), "POST")
    ne = [(1, G.GP_B, G.FL - 11), (1, G.GP_B, G.FL - 2), (1, G.GP_B, zg)]
    S(ne[0], what="north east guard post lag (lower)"); S(ne[1], what="north east guard post lag (upper)")
    M("gne0", ne[0], ne[1], "POST"); M("gne1", ne[1], ne[2], "POST")
    mid_gw = (PC, (bsw + corner[1]) / 2, zg)
    mid_gn = ((corner[0] + 1) / 2, (corner[1] + G.GP_B) / 2, zg) if G.MONO else (12.6, G.GP_B, zg)
    N(*mid_gw); N(*mid_gn)
    M("grail_w", gs[3], corner, "RAIL", "i")
    M("grail_n", corner, ne[2], "RAIL", "j")


# ------------------------------------------------------------------ cut stations for the solid joint models (joint_solid_fea.py)
# Two nodes on the upper stringer's centreline, mid way between tread bracket bolt groups: the pieces below the foot cut and above the
# head cut are modelled as solids, loaded by the frame's forces across the cut and from the brackets on them.
CUTS = {}
if G.MONO:
    CUTS = dict(foot=dict(u=(UP.bolt_u(2) + UP.bolt_u(3)) / 2, brackets=(1, 2)), head=dict(u=(UP.bolt_u(6) + UP.bolt_u(7)) / 2, brackets=(7,)))
    for c_ in CUTS.values():
        c_["node"] = N(*UP.p(c_["u"], VC, UP.zc(c_["u"])))

# ------------------------------------------------------------------ loads
m.add_member_self_weight("FY", -1.0, "D")
CASES = {}                                         # name: description


def node_load(case, p, a=0.0, b=0.0, z=0.0, desc=None):
    n = N(*p)
    for d, v in (("FX", b), ("FY", z), ("FZ", -a)):
        if v:
            m.add_node_load(n, d, v, case)
    if desc:
        CASES[case] = dict(desc=desc, node=n, kind="rail" if (a or b) else "floor")


w_tread = 40.0 * G.GO * G.WN / 144                  # 40 psf on each tread's plan area
for (fn, k), e in TREADS.items():
    for mn in e["members"]:
        m.add_member_dist_load(mn, "FY", -w_tread / G.WN, -w_tread / G.WN, case="L40")
for i in range(len(G.LAND_STRIPS)):
    m.add_member_dist_load(f"Ldeck{i}", "FY", -40 / 144 * 5.73 * 28.7 / 23.2, -40 / 144 * 5.73 * 28.7 / 23.2, case="L40")
for i in range(len(G.BAL_STRIPS)):
    m.add_member_dist_load(f"Bdeck{i}", "FY", -40 / 144 * 6.3 * 29.15 / 23.65, -40 / 144 * 6.3 * 29.15 / 23.65, case="L40")
CASES["L40"] = dict(desc="40 psf on every tread, the landing and the balcony at once", kind="floor", node=None)
P = 300.0
node_load("T_up4", TREADS[("U", 4)]["mid"], z=-P, desc="300 lb on the middle of the upper flight's 4th tread (mid flight)")
if G.MONO:
    node_load("T_up4w", TREADS[("U", 4)]["w"], z=-P, desc="300 lb at the wall end of the upper flight's 4th tread")
    node_load("T_lo2e", TREADS[("L", 2)]["o"], z=-P, desc="300 lb at the open end of the lower flight's 2nd tread")
    node_load("T_up7e", TREADS[("U", 7)]["o"], z=-P, desc="300 lb at the open end of the upper flight's top tread")
node_load("T_up4e", TREADS[("U", 4)]["o"], z=-P, desc="300 lb at the open end of the upper flight's 4th tread")
node_load("T_up7", TREADS[("U", 7)]["mid"], z=-P, desc="300 lb on the upper flight's top tread")
node_load("T_lo2", TREADS[("L", 2)]["mid"], z=-P, desc="300 lb on the middle of the lower flight's 2nd tread")
node_load("P_land", (10.5, 15.0, ZL), z=-P, desc="300 lb on the middle of the corner landing")
node_load("P_landnw", (XW, G.B_LN, ZL), z=-P, desc="300 lb on the landing's north west corner")
node_load("P_bal", (14.0, (G.B_BH + BN1) / 2, ZB), z=-P, desc="300 lb on the middle of the balcony")
node_load("P_balsw", (XW, BS1, ZB), z=-P, desc="300 lb on the balcony's south west corner (top of the ladder)")
node_load("P_balnw", (XW, BN1, ZB), z=-P, desc="300 lb on the balcony's north west corner")
H = 200.0
node_load("H_foot", fp[2], b=H, desc="200 lb outward on the lower rail at the foot post")
node_load("H_tip", tip, b=H, desc="200 lb outward on the lower rail's bottom end")
node_load("H_lomid", mid_lo, b=H, desc="200 lb outward on the lower rail, mid span")
node_load("H_newel_w", nw[4], a=H, desc="200 lb west on the corner newel at the upper rail")
node_load("H_newel_n", nw[3], b=H, desc="200 lb north on the corner newel at the lower rail")
node_load("H_upmid", mid_up, a=H, desc="200 lb outward on the upper rail, mid span")
node_load("H_updown", mid_up, z=-H, desc="200 lb down on the upper rail, mid span")
node_load("H_gsw_w", gs[3], a=H, desc="200 lb outward on the balcony's south west newel at guard height")
node_load("H_gsw_s", gs[3], b=-H, desc="200 lb south (toward the ladder opening) on the south west newel")
node_load("H_gwmid", mid_gw, a=H, desc="200 lb outward on the balcony's west guard rail, mid span")
node_load("H_corner_w", corner, a=H, desc="200 lb west on the guard's north west corner")
node_load("H_corner_n", corner, b=H, desc="200 lb north on the guard's north west corner")
node_load("H_gnmid", mid_gn, b=H, desc="200 lb outward on the balcony's north guard rail, mid span")
# sway: a climber's sideways push (50 lb, about a quarter of a 200 lb person's weight), to see how much the flights wobble
SW = 50.0
if G.MONO:
    node_load("S_up4", TREADS[("U", 4)]["mid"], a=SW, desc="50 lb sideways (west) on the upper flight's 4th tread")
    node_load("S_up7", TREADS[("U", 7)]["mid"], a=SW, desc="50 lb sideways (west) on the upper flight's top tread")
    node_load("S_up4n", TREADS[("U", 4)]["mid"], b=SW, desc="50 lb along the upper flight (north) on its 4th tread")
    node_load("S_lo2", TREADS[("L", 2)]["mid"], b=SW, desc="50 lb sideways (north) on the lower flight's 2nd tread")
    for c_ in ("S_up4", "S_up7", "S_up4n", "S_lo2"):
        CASES[c_]["kind"] = "sway"
m.add_load_combo("D", {"D": 1.0})
for c in CASES:
    m.add_load_combo("D+" + c, {"D": 1.0, c: 1.0})
    m.add_load_combo(c, {c: 1.0})
m.analyze_linear(check_statics=False)

# ------------------------------------------------------------------ results
def stress(name, combo):
    mem, (sec, p, q) = m.members[name], MEM[name]
    _, A, Iy, Iz, J, Sy, Sz = SEC[sec]
    ax = max(abs(mem.max_axial(combo)), abs(mem.min_axial(combo)))
    my = max(abs(mem.max_moment("My", combo)), abs(mem.min_moment("My", combo)))
    mz = max(abs(mem.max_moment("Mz", combo)), abs(mem.min_moment("Mz", combo)))
    tq = max(abs(mem.max_torque(combo)), abs(mem.min_torque(combo)))
    return dict(sig=ax / A + my / Sy + mz / Sz, P=ax, My=my, Mz=mz, T=tq)


GROUP = lambda n: ("stringer tubes" if "tube_" in n and n[0] in "LU" and n[1:5] == "tube" else "tread brackets" if "brkt" in n else "tread arms" if "seat" in n and G.MONO else "oak treads" if "tread" in n else
                   "oak deck" if "deck" in n else "landing frame" if n in ("LE", "LS", "LW", "LN", "LH") else "balcony frame" if n in ("BE", "BS", "BH", "BN", "BW") else
                   "knee braces" if n.startswith("BR") else "corner newel" if n.startswith("newel") and n[5:].isdigit() else "foot post" if n.startswith("footpost") else "upper stringer post" if n == "Upost" else
                   "balcony south west newel" if n.startswith("gsw") and n[3:].isdigit() else "guard posts" if n in ("gnw", "gnw0", "gne0", "gne1") else "ties and kickers" if MEM[n][0] == "STRUT" else
                   "handrails" if n.startswith("rail") and not n.startswith("rail_") or n in ("rail_lower", "rail_upper") else "guard rails" if n.startswith("grail") else None)
res = {"cases": {}, "groups": {}, "reactions": {}, "deflection": {}}
dead = {n: stress(n, "D")["sig"] for n in MEM if GROUP(n)}
for c, info in CASES.items():
    worst = {}
    for n in MEM:
        g = GROUP(n)
        if not g:
            continue
        s = stress(n, "D+" + c)
        allow = FB_OAK if SEC[MEM[n][0]][0] == "oak" else ALLOW
        live = max(s["sig"] - dead[n], 1e-9)
        s.update(member=n, util=s["sig"] / allow, factor=(allow - dead[n]) / live, yield_factor=((FY_STEEL if allow == ALLOW else 2.1 * FB_OAK * 2.5) - dead[n]) / live)
        if g not in worst or s["util"] > worst[g]["util"]:
            worst[g] = s
        if g not in res["groups"] or s["util"] > res["groups"][g]["util"]:
            res["groups"][g] = dict(s, case=c)
    disp = {k: (m.nodes[n].DX[c], m.nodes[n].DY[c], m.nodes[n].DZ[c]) for k, n in NODES.items()}
    kmax = max(disp, key=lambda k: math.hypot(*disp[k]))
    at = info["node"]
    d_at = (m.nodes[at].DX[c], m.nodes[at].DY[c], m.nodes[at].DZ[c]) if at else disp[kmax]
    res["cases"][c] = dict(desc=info["desc"], kind=info["kind"], defl_at_load=math.hypot(*d_at), defl_max=math.hypot(*disp[kmax]), defl_max_at=kmax,
                           worst=max(worst.values(), key=lambda s: s["util"]), by_group={g: round(s["util"], 3) for g, s in worst.items()})
for n, what in SUP.items():
    nd = m.nodes[n]
    env = [0.0, 0.0, 0.0, None]
    for c in CASES:
        r = (nd.RxnFX["D+" + c], nd.RxnFY["D+" + c], nd.RxnFZ["D+" + c])
        if math.hypot(*r) > math.hypot(*env[:3]):
            env = [r[0], r[1], r[2], c]
    res["reactions"].setdefault(what, [])
    res["reactions"][what].append(dict(north=round(env[0]), up=round(env[1]), east=round(env[2]), total=round(math.hypot(*env[:3])), case=env[3], dead_up=round(nd.RxnFY["D"])))
# total dead weight, and a frequency estimate from the self weight plus one 170 lb person at mid flight
res["dead_weight"] = round(sum(m.nodes[n].RxnFY["D"] for n in SUP))
d_p = abs(m.nodes[N(*TREADS[("U", 4)]["mid"])].DY["T_up4"]) * 170 / 300 + abs(m.nodes[N(*TREADS[("U", 4)]["mid"])].DY["D"])
res["freq_hz"] = round(0.18 * math.sqrt(386.4 / d_p), 1)
# bracket bolts: the worst bracket web's end forces
bb = dict(shear=0.0, tension=0.0)
for n in MEM:
    if "brkt" in n:
        for c in CASES:
            s = stress(n, "D+" + c)
            mem = m.members[n]
            v = max(abs(mem.max_shear("Fy", "D+" + c)), abs(mem.min_shear("Fy", "D+" + c)), s["P"])
            if G.MONO:                                                     # two through bolts, a web each side: twist of the tread goes in as up and down forces in the two webs
                bb["shear"] = max(bb["shear"], v / 2 + s["Mz"] / 4.5 + s["My"] / (G.TW + 0.25) / 2)
                bb["seat"] = max(bb.get("seat", 0.0), s["My"])
            else:
                bb["shear"] = max(bb["shear"], v / 2 + s["Mz"] / 4.5)          # two bolts 4.5 in apart
                bb["tension"] = max(bb["tension"], s["My"] / 1.25 / 2)         # prying about the tube's top edge, 1.25 in lever, two bolts
res["bracket_bolt"] = {k: round(v) for k, v in bb.items()}
# post laps: forces through the bolted connections of each post to the tubes and frames, and at the tube ends
LINKS = dict(newel_LW="corner newel to landing west beam", foot_tube="foot post to lower stringer", gsw_tube="balcony newel to upper stringer",
             gsw_BW="balcony newel to balcony west beam", gnw_BN="north west guard post to balcony north arm", **({f"{e}_{i}": f"{d} ({'north' if i == 'a' else 'south'} angle)" if e[0] == "L" else f"{d} ({'east' if i == 'b' else 'west'} side)" for e, d in (("Lhead", "lower stringer head"), ("Ufoot", "upper stringer foot"), ("Uhead", "upper stringer head")) for i in "ab"} if G.MONO else
                dict(newel_tube="corner newel to lower stringer", Lhead_o="lower stringer head (open side)", Lhead_w="lower stringer head (wall side)",
                     Ufoot_o="upper stringer foot (open side)", Ufoot_w="upper stringer foot (wall side)", Uhead_o="upper stringer head (open side)", Uhead_w="upper stringer head (wall side)")))
if G.MONO:
    LINKS.update({"Uhead_a": "upper stringer top bearing on the head beam (west side)", "Uhead_b": "upper stringer top bearing on the head beam (east side)",
                  "Uhead_side": "upper stringer top clips, sideways", "Upost_saddle": "upper stringer post saddle"})
    for k_ in ("Ufoot_a", "Ufoot_b"):
        LINKS[k_] = "upper stringer foot clip to the landing beam (" + ("west" if k_[-1] == "a" else "east") + " side)"
res["links"] = {}
for n, what in LINKS.items():
    best = dict(force=0.0, moment=0.0)
    if n not in m.members:
        continue
    mem = m.members[n]
    for c in CASES:
        cb = "D+" + c
        f_ = math.sqrt(max(abs(mem.max_axial(cb)), abs(mem.min_axial(cb))) ** 2 + max(abs(mem.max_shear("Fy", cb)), abs(mem.min_shear("Fy", cb))) ** 2 + max(abs(mem.max_shear("Fz", cb)), abs(mem.min_shear("Fz", cb))) ** 2)
        mo = math.hypot(max(abs(mem.max_moment("My", cb)), abs(mem.min_moment("My", cb))), max(abs(mem.max_moment("Mz", cb)), abs(mem.min_moment("Mz", cb))))
        tq = max(abs(mem.max_torque(cb)), abs(mem.min_torque(cb)))
        if f_ > best["force"]:
            best.update(force=round(f_), force_case=c)
        if math.hypot(mo, tq) > best["moment"]:
            best.update(moment=round(math.hypot(mo, tq)), moment_case=c)
    res["links"][what] = best
# sway stiffness and the first few natural modes (self weight plus one 170 lb person standing mid way up the upper flight)
res["sway"] = {c: dict(desc=CASES[c]["desc"], defl_in=round(res["cases"][c]["defl_at_load"], 4), stiffness_lb_per_in=round(SW / max(res["cases"][c]["defl_at_load"], 1e-9)))
               for c in CASES if CASES[c]["kind"] == "sway"}
res["variant"] = dict(post_base=POST_BASE, head_carries_weight=HEAD_VERT)
if CUTS:
    # forces (lb) and moments (in lb) on each solid piece, in PyNite global axes (X north, Y up, Z east), about the node they act at
    def sub_at(phys, node, end):
        for sm in m.members[phys].sub_members.values():
            if (sm.i_node.name if end == "i" else sm.j_node.name) == node:
                return sm
        raise KeyError((phys, node, end))
    cutres = {}
    for nm, c_ in CUTS.items():
        nd = m.nodes[c_["node"]]
        ent = dict(u=c_["u"], cut_xyz=(nd.X, nd.Y, nd.Z), brackets={}, cases={})
        sm = sub_at("Utube_c", c_["node"], "i" if nm == "foot" else "j")
        for k in c_["brackets"]:
            pn = N(*UP.p(UP.bolt_u(k), VC, UP.zc(UP.bolt_u(k))))
            ent["brackets"][k] = dict(u=UP.bolt_u(k), xyz=(m.nodes[pn].X, m.nodes[pn].Y, m.nodes[pn].Z), node=pn)
        for cb in ["D"] + ["D+" + c for c in CASES]:
            Fv = sm.F(cb).ravel()
            cut = -(Fv[0:6] if nm == "foot" else Fv[6:12])
            br = {}
            for k, e in ent["brackets"].items():
                bs = sub_at(f"Ubrkt{k}c", e["node"], "i")
                br[k] = [float(x) for x in -bs.F(cb).ravel()[0:6]]
            ent["cases"][cb] = dict(cut=[float(x) for x in cut], brackets=br)
        for e in ent["brackets"].values():
            e.pop("node")
        cutres[nm] = ent
    json.dump(cutres, open(os.path.join(OUT, "ladder_cut_loads.json"), "w"), indent=1)
json_path = os.path.join(OUT, "ladder_fea_results.json")
json.dump(res, open(json_path, "w"), indent=1, default=lambda o: round(o, 4) if isinstance(o, float) else str(o))
print("sway:", res["sway"])

print(f"nodes {len(NODES)}, members {len(MEM)}, dead weight {res['dead_weight']} lb, first mode estimate {res['freq_hz']} Hz")
print("\nCASE".ljust(13), "defl at load", " worst member / stress / use of allowable / load factor to allowable")
for c, r in res["cases"].items():
    w = r["worst"]
    print(c.ljust(12), f"{r['defl_at_load']:.3f} in  max {r['defl_max']:.3f}  {w['member']:<12} {w['sig']:8.0f} psi  {w['util']:.2f}  x{w['factor']:.1f}")
print("\nGROUP ENVELOPE")
for g, s in res["groups"].items():
    print(g.ljust(26), s["member"].ljust(12), s["case"].ljust(11), f"{s['sig']:8.0f} psi  use {s['util']:.2f}  factor {s['factor']:.1f}  P {s['P']:.0f} My {s['My']:.0f} Mz {s['Mz']:.0f} T {s['T']:.0f}")
print("\nREACTIONS (worst case, lb)")
for what, rr in res["reactions"].items():
    for r in rr:
        print(what.ljust(46), r)
print("bracket bolts:", res["bracket_bolt"])
for k_, v_ in res["links"].items():
    print(k_.ljust(46), v_)

# ------------------------------------------------------------------ plots
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
PLOTS = [("T_up4e", 40), ("P_balsw", 60), ("H_upmid", 12), ("H_gsw_w", 12), ("H_foot", 12), ("L40", 60)]
fig = plt.figure(figsize=(17, 11))
fig.text(0.03, 0.96, "LOFT SHIPS LADDER: FRAME ANALYSIS, DEFLECTED SHAPES", fontsize=16, fontweight="bold")
fig.text(0.03, 0.94, "Grey = unloaded, colour = loaded (deflection exaggerated by the factor shown). Preliminary, for an engineer's review.", fontsize=9, color="#b3261e")
for i, (c, sc) in enumerate(PLOTS):
    ax = fig.add_subplot(2, 3, i + 1, projection="3d")
    for n, (sec, p, q) in MEM.items():
        if sec == "RIGID":
            continue
        pm = m.members[n]
        nds = [pm.i_node] + [s_.j_node for s_ in pm.sub_members.values()] if getattr(pm, "sub_members", None) else [pm.i_node, pm.j_node]
        xs = [(-nd.Z, nd.X, nd.Y) for nd in nds]
        ax.plot(*zip(*xs), c="#bbbbbb", lw=0.7)
        xd = [(-(nd.Z + sc * nd.DZ[c]), nd.X + sc * nd.DX[c], nd.Y + sc * nd.DY[c]) for nd in nds]
        col = "#8a5a2b" if SEC[sec][0] == "oak" else "#1f4e79"
        ax.plot(*zip(*xd), c=col, lw=1.3)
    r = res["cases"][c]
    ax.set_title(f"{r['desc']}\nmoves {r['defl_at_load']:.2f} in at the load (drawn x{sc}); peak stress {r['worst']['util'] * 100:.0f}% of allowable", fontsize=8.5)
    ax.set_box_aspect((75, 100, 165)); ax.view_init(18, -125)
    ax.set_xlim(-55, 20); ax.set_ylim(-5, 95); ax.set_zlim(0, 165)
    ax.tick_params(labelsize=6)
fig.subplots_adjust(left=0.01, right=0.99, top=0.9, bottom=0.02, wspace=0.02, hspace=0.12)
fig.savefig(os.path.join(OUT, "ladder_fea_deflected.png"), dpi=140)
fig.savefig(os.path.join(OUT, "ladder_fea_deflected.pdf"))

# ------------------------------------------------------------------ natural modes (last: the modal solve replaces the static results in the model)
if G.MONO and os.environ.get("LADDER_MODAL", "1") == "1":
    m.add_node_load(N(*TREADS[("U", 4)]["mid"]), "FY", -170.0, "PERSON")
    m.add_load_combo("MASS", {"D": 1.0, "PERSON": 1.0})
    m.analyze_modal(num_modes=10, mass_combo_name="MASS", mass_direction="Y", gravity=386.1, check_stability=False)
    freqs = [float(x) for x in m.frequencies]
    modes = []
    for i_, fq in enumerate(freqs):
        if fq < 1.0:                                     # loose analysis-only nodes (no stiffness) show up as 0 Hz modes: skip them
            continue
        cmb = f"Mode {i_ + 1}"
        try:
            sh = {k: (m.nodes[n].DX[cmb], m.nodes[n].DY[cmb], m.nodes[n].DZ[cmb]) for k, n in NODES.items()}
        except KeyError:
            sh = {}
        if sh:
            kx = max(sh, key=lambda k: math.hypot(*sh[k]))
            dx_, dy_, dz_ = sh[kx]
            mag = math.hypot(dx_, dy_, dz_)
            modes.append(dict(hz=round(fq, 1), peak_at=kx, north=round(float(dx_ / mag), 2), up=round(float(dy_ / mag), 2), west=round(float(-dz_ / mag), 2)))
        else:
            modes.append(dict(hz=round(fq, 1)))
    res["modes"] = modes[:5]
    json.dump(res, open(json_path, "w"), indent=1, default=lambda o: round(o, 4) if isinstance(o, float) else str(o))
    print("modes:", res["modes"])
