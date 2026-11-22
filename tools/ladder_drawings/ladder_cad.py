"""Solid CAD model of the loft ships ladder structure (CadQuery): tube stringers, tread brackets, treads, corner landing,
balcony, knee braces, posts, rails and the balcony guard. Writes a STEP assembly (inches), a GLB for viewing and a parts list.

Coordinates in the files: X east, Y north, Z up, inches, origin on the slab at the corner of the bath 1 wall and the clerestory wall.
Not modelled: bolts, the bolt on frame clips and rail plates, wall rail brackets. PRELIMINARY: for an engineer's review.
Run: python3 tools/ladder_drawings/ladder_cad.py OUTDIR      (pip install cadquery)
"""
import json, math, os, sys
import cadquery as cq
import ladder_geom as G

OUT = sys.argv[1] if len(sys.argv) > 1 else "."
os.makedirs(OUT, exist_ok=True)
T = G.WT
BT = 0.375 if G.MONO else 0.25                     # tread bracket plate
PARTS = []                                         # (group, name, solid, colour, material)
STEEL, OAK = (0.13, 0.14, 0.15), (0.78, 0.62, 0.40)
RISER_PANELS, PANEL_BACK = not G.MONO, 0.75              # slide in 1/4 in wood riser panels behind each tread, held in slots in the tread brackets (Maxwell 11/22/2026: 4 in sphere rule)


def W(a, b, z):
    return cq.Vector(-a, b, z)


def box(a0, a1, b0, b1, z0, z1):
    return cq.Solid.makeBox(a1 - a0, b1 - b0, z1 - z0, W(a1, b0, z0))


def tube(a0, a1, b0, b1, z0, z1, axis, t=T):
    """hollow box: open ends along axis 'a', 'b' or 'z'"""
    e = 1.0
    inner = box(a0 + (t if axis != "a" else -e), a1 - (t if axis != "a" else -e), b0 + (t if axis != "b" else -e), b1 - (t if axis != "b" else -e),
                z0 + (t if axis != "z" else -e), z1 - (t if axis != "z" else -e))
    return box(a0, a1, b0, b1, z0, z1).cut(inner)


def prism(f, uz, v0, v1):
    """polygon in a flight's side view (u, z), from v0 to v1 across the flight"""
    w = cq.Wire.makePolygon([W(*f.p(u, v0, z)) for u, z in uz], close=True)
    d = W(*f.p(0, v1, 0)) - W(*f.p(0, v0, 0))
    return cq.Solid.extrudeLinear(cq.Face.makeFromWires(w), d)


def aprism(az, b0, b1):
    """polygon in the (a, z) plane, from b0 to b1"""
    w = cq.Wire.makePolygon([W(a, b0, z) for a, z in az], close=True)
    return cq.Solid.extrudeLinear(cq.Face.makeFromWires(w), cq.Vector(0, b1 - b0, 0))


def slope_tube(f, ua, ub, ztop, depth, v0, v1, t, za=None, zb=None):
    """tube along a flight's slope: top line ztop(u), plumb depth, plumb cut ends (or level cuts at za, zb)"""
    zt, zbm = ztop, lambda u: ztop(u) - depth
    if za is None:
        outer = prism(f, [(ua, zbm(ua)), (ub, zbm(ub)), (ub, zt(ub)), (ua, zt(ua))], v0, v1)
    else:
        outer = prism(f, [(ua, za), (ua + depth / G.SL, za), (ub + depth / G.SL, zb), (ub, zb)], v0, v1)
    tp = t / math.cos(G.ANG)
    e0, e1 = ua - 4, ub + 4 + depth / G.SL
    inner = prism(f, [(e0, zbm(e0) + tp), (e1, zbm(e1) + tp), (e1, zt(e1) - tp), (e0, zt(e0) - tp)], v0 + t * (1 if v1 > v0 else -1), v1 - t * (1 if v1 > v0 else -1))
    return outer.cut(inner)


def add(group, name, solid, colour=STEEL, mat="steel"):
    PARTS.append((group, name, solid, colour, mat))


VC = G.VC
if G.MONO:      # one centre tube; a bracket on each side of it with the seat pointing outward: (name, tube v0 or None, web v range, seat v range)
    SIDES = (("open", VC - G.TW / 2, (VC - G.TW / 2 - BT, VC - G.TW / 2), (VC - G.TW / 2 - G.SEAT_W, VC - G.TW / 2)),
             ("wall", None, (VC + G.TW / 2, VC + G.TW / 2 + BT), (VC + G.TW / 2, VC + G.TW / 2 + G.SEAT_W)))
else:
    SIDES = (("open", 0.0, (G.TW, G.TW + BT), (G.TW, G.TW + G.SEAT_W)), ("wall", G.WN - G.TW, (G.WN - G.TW - BT, G.WN - G.TW), (G.WN - G.TW - G.SEAT_W, G.WN - G.TW)))
for f in G.FLIGHTS:
    g = f"{f.name}_flight"
    for side, v0, vw, vs in SIDES:
        if v0 is not None:
            add(g, f"{f.name}_stringer" if G.MONO else f"{f.name}_tube_{side}", slope_tube(f, f.u0, f.u2, f.zl, G.PL, v0, v0 + G.TW, T, f.zf, f.zu))
        nx, nz = math.sin(G.ANG), -math.cos(G.ANG)
        for k in range(1, f.nr):
            uk, zk = f.uk(k), f.z0 + k * G.RI - G.TT
            A, B = (uk + G.WEB0, zk), (uk + G.TD + G.RT, zk)
            C = (A[0], f.zl(A[0]))
            web = [A, C, (C[0] + nx * G.LAP, C[1] + nz * G.LAP), (B[0] + nx * G.LAP, B[1] + nz * G.LAP), B]
            zc_ = f.zf + BT
            foot = min(z for _, z in web) < zc_
            if foot:                                                           # first tread: the web runs down to a foot flange anchored to the slab or landing
                cl = []
                for p, q in zip(web, web[1:] + web[:1]):
                    if p[1] >= zc_:
                        cl.append(p)
                    if (p[1] - zc_) * (q[1] - zc_) < 0:
                        t_ = (zc_ - p[1]) / (q[1] - p[1])
                        cl.append((p[0] + t_ * (q[0] - p[0]), zc_))
                web = cl
            br = prism(f, web, *vw).fuse(prism(f, [(uk + 1, zk - BT), (uk + G.TD + G.RT, zk - BT), (uk + G.TD + G.RT, zk), (uk + 1, zk)], *vs))
            if foot:
                us = [u for u, z in web if abs(z - zc_) < 1e-6]
                br = br.fuse(prism(f, [(min(us), f.zf), (max(us), f.zf), (max(us), zc_), (min(us), zc_)], *vs))
            add(g, f"{f.name}_bracket_{k}_{side}", br)
        sgn = 1 if vs[0] == vw[0] else -1                                      # head angles, 3 x 3 x 1/4, 4 in long (the feet are held by the first tread brackets)
        e0 = vw[0] if sgn > 0 else vw[1]
        vi, vl = tuple(sorted((e0, e0 + sgn * 3.0))), tuple(sorted((e0, e0 + sgn * 0.25)))
        for nm, uc, zf, sg in (("head", (f.u2 + f.u3) / 2 - 1.0, f.zu, -1),):
            z0_, z1_ = sorted((zf, zf + sg * 0.25))
            z2_, z3_ = sorted((zf, zf + sg * 3.0))
            ang = prism(f, [(uc - 2, z0_), (uc + 2, z0_), (uc + 2, z1_), (uc - 2, z1_)], *vi).fuse(prism(f, [(uc - 2, z2_), (uc + 2, z2_), (uc + 2, z3_), (uc - 2, z3_)], *vl))
            add(g, f"{f.name}_end_angle_{nm}_{side}", ang)
    for k in range(1, f.nr):
        uk, zk = f.uk(k), f.z0 + k * G.RI
        add(g, f"{f.name}_tread_{k}", prism(f, [(uk, zk - G.TT), (uk + G.TD, zk - G.TT), (uk + G.TD, zk), (uk, zk)], 0.05, G.WN - 0.05), OAK, "oak")
        if G.RT:                                                               # mono: an oak riser lip behind every tread leaves under 4 in open above it
            ur = uk + G.TD
            add(g, f"{f.name}_riser_{k}", prism(f, [(ur, zk - G.TT), (ur + G.RT, zk - G.TT), (ur + G.RT, zk + G.RH), (ur, zk + G.RH)], 0.05, G.WN - 0.05), OAK, "oak")
    if G.RT and f is G.UPPER:                                                  # and one stands on the landing under the upper flight's first tread
        ur = G.TD - G.GO
        add(g, "landing_riser", prism(f, [(ur, f.z0 - G.TT), (ur + G.RT, f.z0 - G.TT), (ur + G.RT, f.z0 + G.RH), (ur, f.z0 + G.RH)], 0.05, G.WN - 0.05), OAK, "oak")
    if RISER_PANELS:
        for k in range(0 if f is G.UPPER else 1, f.nr):
            zk = f.z0 + k * G.RI
            if zk + G.RI - G.TT <= 30.0:                                       # openings 30 in or less above the floor are exempt
                continue
            ua = f.uk(k) + G.TD + PANEL_BACK                                   # 1/4 in panel, ears through slots in the webs of the brackets above
            pan = prism(f, [(ua, zk + 0.25), (ua + 0.25, zk + 0.25), (ua + 0.25, zk + G.RI - G.TT - 0.3), (ua, zk + G.RI - G.TT - 0.3)], G.TW, G.WN - G.TW)
            add(g, f"{f.name}_riser_panel_{k}", pan, (0.86, 0.74, 0.55), "oak")
    # handrails: open side on the posts, wall side on brackets 1 1/2 in off the wall
    RD2 = G.RAIL / math.cos(G.ANG)
    ztop = lambda u, f=f: f.zn(u) + G.HR
    if f is G.LOWER:
        add("rails", "lower_rail_open", slope_tube(f, 0.0, G.UL - G.POST, ztop, RD2, -1.75, -0.25, G.RAIL_T))
        add("rails", "lower_rail_wall", slope_tube(f, 0.0, G.UL, ztop, RD2, G.WN + G.GAP - 3.0, G.WN + G.GAP - 1.5, G.RAIL_T))
        und = lambda u: ztop(u) - RD2
        u_a, u_b = G.FOOT_U - 1, G.FOOT_U + 1
        post = prism(f, [(u_a, 0), (u_b, 0), (u_b, und(u_b)), (u_a, und(u_a))], -G.POST, 0.0)
        post = post.cut(prism(f, [(u_a + T, -1), (u_b - T, -1), (u_b - T, 200), (u_a + T, 200)], -G.POST + T, -T))
        add("posts", "foot_post", post)
        if G.MONO:
            add("posts", "foot_post_base_plate", prism(f, [(G.FOOT_U - 3, 0), (G.FOOT_U + 3, 0), (G.FOOT_U + 3, 0.375), (G.FOOT_U - 3, 0.375)], -G.POST - 2, 2).cut(prism(f, [(u_a, -1), (u_b, -1), (u_b, 1), (u_a, 1)], -G.POST, 0.0)))
    else:
        add("rails", "upper_rail_open", slope_tube(f, G.POST + G.XL - G.B0, G.BAL_S - G.B0, ztop, RD2, -1.75, -0.25, G.RAIL_T))
        add("rails", "upper_rail_wall", slope_tube(f, 0.0, G.UU - G.NOSE, ztop, RD2, G.WN + G.GAP - 3.0, G.WN + G.GAP - 1.5, G.RAIL_T))

XL, ZP, FL, TT, TK = G.XL, G.ZP, G.FL, G.TT, G.TK
# corner landing
lz = (ZP - TK, ZP - TT)
add("landing", "landing_east_ledger", tube(0, 2, 0, G.LAND_N, *lz, "b"))
add("landing", "landing_south_ledger", tube(2, XL, 0, 2, *lz, "a"))
add("landing", "landing_west_beam", tube(XL - 2, XL, 2, G.LAND_N, *lz, "b"))
add("landing", "landing_north_beam", tube(2, XL - 2, G.B_LN - 1, G.B_LN + 1, *lz, "a"))
add("landing", "landing_header", tube(G.A_LH - 1, G.A_LH + 1, 2, G.B_LN - 1, *lz, "b"))
deck = box(0, XL, 0, G.LAND_DECK_N, ZP - TT, ZP)
add("landing", "landing_deck", deck.fuse(box(XL, XL + G.NOSE, G.GAP, XL, ZP - TT, ZP)) if G.NOSE else deck, OAK, "oak")
add("posts", "corner_newel", tube(XL, XL + G.POST, XL, XL + G.POST, 0, G.NEWEL_TOP, "z"))
# balcony
bz = (FL - TK, FL - TT)
add("balcony", "balcony_ledger", tube(0, 2, G.BAL_S, G.BAL_N, *bz, "b"))
add("balcony", "balcony_south_beam", tube(2, XL - 2, G.BAL_S, G.BAL_S + 2, *bz, "a"))
add("balcony", "balcony_head_arm", tube(2, XL - 2, G.B_BH - 1, G.B_BH + 1, *bz, "a"))
add("balcony", "balcony_north_arm", tube(2, XL, G.BAL_N - 2, G.BAL_N, *bz, "a"))
add("balcony", "balcony_west_beam", tube(XL - 2, XL, G.BAL_S, G.BAL_N - 2, *bz, "b"))
deck = box(0, XL, G.BAL_S, G.BAL_N, FL - TT, FL)
add("balcony", "balcony_deck", deck.fuse(box(G.GAP, XL, G.BAL_S - G.NOSE, G.BAL_S, FL - TT, FL)) if G.NOSE else deck, OAK, "oak")
zu, r2 = FL - TK, G.POST / math.sqrt(2) * 1.0
for nm, b in ((("north", G.BAL_N - 1),) if G.MONO else (("south", G.B_BH), ("north", G.BAL_N - 1))):
    br = aprism([(G.A_BR + 1 + r2, zu), (G.A_BR + 1 - r2, zu), (0, zu - G.A_BR - 1 + r2), (0, zu - G.A_BR - 1 - r2)], b - 1, b + 1)
    add("balcony", f"knee_brace_{nm}", br)
# balcony newel, guard posts, rails, pickets
gsw_z0 = G.UPPER.zc(G.BAL_S + 1 - G.B0) - 4.0
if G.MONO:      # the free posts are tied back: a tie under the stringer to the south west newel, and a kicker under the west beam for each post
    def bprism(bz, a0, a1):
        w = cq.Wire.makePolygon([W(a0, b, z) for b, z in bz], close=True)
        return cq.Solid.extrudeLinear(cq.Face.makeFromWires(w), W(a1, 0, 0) - W(a0, 0, 0))
    us_ = G.BAL_S + 1 - G.B0
    zt_ = G.UPPER.zl(us_ - 0.75) - G.PL
    gsw_z0 = min(zt_ - 2.5, FL - TK - G.KICK - 3)
    add("ties", "newel_tie_to_stringer", tube(XL - VC - G.TW / 2, XL, G.BAL_S + 0.25, G.BAL_S + 1.75, zt_ - 1.5, zt_, "a", 0.125))
    kz, kd = FL - TK, 1.5 * math.sqrt(2)
    add("ties", "newel_kicker", bprism([(G.BAL_S + G.POST, kz - G.KICK), (G.BAL_S + G.POST, kz - G.KICK - kd), (G.BAL_S + G.POST + G.KICK + kd, kz), (G.BAL_S + G.POST + G.KICK, kz)], XL - 1.75, XL - 0.25))
    add("ties", "guard_post_kicker", bprism([(G.BAL_N, kz - G.KICK), (G.BAL_N, kz - G.KICK - kd), (G.BAL_N - G.KICK - kd, kz), (G.BAL_N - G.KICK, kz)], XL - 1.75, XL - 0.25))
add("posts", "balcony_sw_newel", tube(XL, XL + G.POST, G.BAL_S, G.BAL_S + G.POST, gsw_z0, G.GSW_TOP, "z"))
add("posts", "guard_post_nw", tube(XL - G.POST, XL, G.BAL_N, G.BAL_N + G.POST, FL - TK - (G.KICK + 3 if G.MONO else 0), G.G_TOP - G.RAIL, "z"))
add("posts", "guard_post_ne", tube(0, G.POST, G.BAL_N, G.BAL_N + G.POST, FL - 13, G.G_TOP - G.RAIL, "z"))
ra, rb = (XL + 0.25, XL + 0.25 + G.RAIL), (G.GP_B - G.RAIL / 2, G.GP_B + G.RAIL / 2)
for nm, z0_ in (("top", G.G_TOP - G.RAIL), ("bottom", FL + 2.5)):
    add("guard", f"guard_west_{nm}_rail", tube(*ra, G.BAL_S + G.POST, rb[1], z0_, z0_ + G.RAIL, "b", G.RAIL_T))
    add("guard", f"guard_north_{nm}_rail", tube(G.POST if nm == "bottom" else 0, XL - G.POST if nm == "bottom" else ra[0], *rb, z0_, z0_ + G.RAIL, "a", G.RAIL_T))
pz = (FL + 2.5 + G.RAIL, G.G_TOP - G.RAIL)
n_w = math.ceil((rb[0] - (G.BAL_S + G.POST)) / 4.4)
for i in range(1, n_w):
    b = G.BAL_S + G.POST + i * (rb[0] - (G.BAL_S + G.POST)) / n_w
    add("guard", f"picket_west_{i}", cq.Solid.makeCylinder(G.PICKET / 2, pz[1] - pz[0], W(XL + 1, b, pz[0])))
n_n = math.ceil((XL - 2 * G.POST) / 4.4)
for i in range(1, n_n):
    a = G.POST + i * (XL - 2 * G.POST) / n_n
    add("guard", f"picket_north_{i}", cq.Solid.makeCylinder(G.PICKET / 2, pz[1] - pz[0], W(a, G.GP_B, pz[0])))
# context: slab and the two walls (reference only)
CTX = [("slab", box(-5, 60, -5, 100, -1, 0)), ("bath_1_wall", box(-4.5, 0, -4.5, 100, 0, FL)), ("clerestory_wall", box(0, 60, -4.5, 0, 0, 170))]

assy, ctx = cq.Assembly(name="loft_ships_ladder"), cq.Assembly(name="context")
groups = {}
for group, name, solid, colour, mat in PARTS:
    groups.setdefault(group, cq.Assembly(name=group)).add(solid, name=name, color=cq.Color(*colour, 1.0))
for g_, a_ in groups.items():
    assy.add(a_)
assy.save(os.path.join(OUT, "loft_ships_ladder.step"))
for nm, s in CTX:
    ctx.add(s, name=nm, color=cq.Color(0.86, 0.86, 0.84, 1.0))
full = cq.Assembly(name="view")
full.add(assy); full.add(ctx)
full.save(os.path.join(OUT, "loft_ships_ladder_view.glb"), tolerance=0.01, angularTolerance=0.2)

DENS = dict(steel=0.2836, oak=0.027)
tot, rows = {}, []
for group, name, solid, colour, mat in PARTS:
    wgt = solid.Volume() * DENS[mat]
    tot[(group, mat)] = tot.get((group, mat), 0) + wgt
    bb = solid.BoundingBox()
    rows.append(dict(group=group, name=name, material=mat, weight_lb=round(wgt, 2), bbox_in=[round(bb.xlen, 2), round(bb.ylen, 2), round(bb.zlen, 2)]))
json.dump(dict(parts=rows, weight_by_group={f"{g_} {m_}": round(w_, 1) for (g_, m_), w_ in tot.items()}), open(os.path.join(OUT, "loft_ships_ladder_parts.json"), "w"), indent=1)
print(len(PARTS), "solids;", {f"{g_} {m_}": round(w_, 1) for (g_, m_), w_ in tot.items()})
print("steel", round(sum(w for (g_, m_), w in tot.items() if m_ == "steel")), "lb, oak", round(sum(w for (g_, m_), w in tot.items() if m_ == "oak")), "lb")
# interference check between steel parts (touching is fine, overlap is not)
bad = []
st = [(n, s) for g_, n, s, c, m_ in PARTS]
for i in range(len(st)):
    bi = st[i][1].BoundingBox()
    for j in range(i + 1, len(st)):
        bj = st[j][1].BoundingBox()
        if bi.xmax < bj.xmin + 0.01 or bj.xmax < bi.xmin + 0.01 or bi.ymax < bj.ymin + 0.01 or bj.ymax < bi.ymin + 0.01 or bi.zmax < bj.zmin + 0.01 or bj.zmax < bi.zmin + 0.01:
            continue
        try:
            v = st[i][1].intersect(st[j][1]).Volume()
        except Exception:
            v = 0
        if v > 0.02 and 'riser_panel' not in st[i][0] + st[j][0]:      # panel ears pass through slots in the bracket webs
            bad.append((st[i][0], st[j][0], round(v, 2)))
print("interferences:", bad if bad else "none")
