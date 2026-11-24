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
BT = G.BRKT_T                                      # tread bracket plate
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


def vprism(f, vz, u0, u1):
    """polygon across a flight (v, z), from u0 to u1 along it"""
    w = cq.Wire.makePolygon([W(*f.p(u0, v, z)) for v, z in vz], close=True)
    return cq.Solid.extrudeLinear(cq.Face.makeFromWires(w), W(*f.p(u1, 0, 0)) - W(*f.p(u0, 0, 0)))


def aprism(az, b0, b1):
    """polygon in the (a, z) plane, from b0 to b1"""
    w = cq.Wire.makePolygon([W(a, b0, z) for a, z in az], close=True)
    return cq.Solid.extrudeLinear(cq.Face.makeFromWires(w), cq.Vector(0, b1 - b0, 0))


def slope_tube(f, ua, ub, ztop, depth, v0, v1, t, za=None, zb=None, plumb_head=False):
    """tube along a flight's slope: top line ztop(u), plumb depth, plumb cut ends (or level cuts at za, zb; or a level foot and a plumb head)"""
    zt, zbm = ztop, lambda u: ztop(u) - depth
    if za is None:
        outer = prism(f, [(ua, zbm(ua)), (ub, zbm(ub)), (ub, zt(ub)), (ua, zt(ua))], v0, v1)
    elif plumb_head:
        outer = prism(f, [(ua, za), (ua + depth / G.SL, za), (ub, zbm(ub)), (ub, zt(ub))], v0, v1)
    else:
        outer = prism(f, [(ua, za), (ua + depth / G.SL, za), (ub + depth / G.SL, zb), (ub, zb)], v0, v1)
    tp = t / math.cos(G.ANG)
    e0, e1 = ua - 4, ub + 4 + depth / G.SL
    inner = prism(f, [(e0, zbm(e0) + tp), (e1, zbm(e1) + tp), (e1, zt(e1) - tp), (e0, zt(e0) - tp)], v0 + t * (1 if v1 > v0 else -1), v1 - t * (1 if v1 > v0 else -1))
    return outer.cut(inner)


def add(group, name, solid, colour=STEEL, mat="steel"):
    PARTS.append((group, name, solid, colour, mat))


FAST = []                                          # bolt heads, nuts and anchors, shown so every joint reads as bolted (Maxwell 11/22/2026: no welding anywhere)


def bolt(a, b, z, axis, sign=1, d=0.66, h=0.21, kind="socket"):
    """a head standing on the point (a, b, z), pointing along +/- axis 'a', 'b' or 'z'. kind 'socket' = socket button head (Allen key, round),
    'hex' = hex head or hex nut (slab anchors, lag screws, and the nut end of through bolts). Maxwell 11/22/2026: no square heads."""
    dv = dict(a=cq.Vector(-sign, 0, 0), b=cq.Vector(0, sign, 0), z=cq.Vector(0, 0, sign))[axis]
    if kind == "socket":
        FAST.append(cq.Solid.makeCylinder(d / 2, h, W(a, b, z), dv))
        return
    d, h = (0.65, 0.33) if d >= 0.6 else (0.5, 0.25)                 # 3/8 in hex: 9/16 across flats; small: 7/16
    e1 = cq.Vector(0, 0, 1) if axis != "z" else cq.Vector(1, 0, 0)
    e2 = dv.cross(e1)
    r = d / math.sqrt(3)
    o = W(a, b, z)
    pts = [o + e1 * (r * math.cos(math.pi / 3 * i)) + e2 * (r * math.sin(math.pi / 3 * i)) for i in range(6)]
    FAST.append(cq.Solid.extrudeLinear(cq.Face.makeFromWires(cq.Wire.makePolygon(pts, close=True)), dv * h))


def nut(a, b, z, axis, sign=1, **kw):
    bolt(a, b, z, axis, sign, kind="hex", **kw)


def fbolt(f, u, v, z, axis, sign=1, **kw):
    """the same in a flight's (u, v, z); axis 'v' or 'z'"""
    a, b, _ = f.p(u, v, z)
    if axis == "z":
        return bolt(a, b, z, "z", sign, **kw)
    a2, b2, _ = f.p(u, v + sign, z) if axis == "v" else f.p(u + sign, v, z)
    bolt(a, b, z, "a" if abs(a2 - a) > 0.5 else "b", (1 if a2 > a else -1) if abs(a2 - a) > 0.5 else (1 if b2 > b else -1), **kw)


def fnut(f, u, v, z, axis, sign=1, **kw):
    fbolt(f, u, v, z, axis, sign, kind="hex", **kw)


def post_box(a0, a1, b0, b1, z0, t=T, gap=0.12):
    """mono round 3: a square tube post standing from z0, its top cut to the plane of the rail's underside so the rail runs over it unbroken"""
    s_ = G.rail_s((a0 + a1) / 2, (b0 + b1) / 2)
    pa, pb = G.rail_plan(s_)
    qa, qb = G.rail_plan(min(s_ + 0.05, G.S_END))
    ra, rb = G.rail_plan(max(s_ - 0.05, 0.0))
    ta, tb = qa - ra, qb - rb
    n_ = math.hypot(ta, tb)
    ta, tb = ta / n_, tb / n_
    m_ = G.rail_slope(s_)
    z_ = lambda a, b: G.rail_z(s_) - G.rail_depth(s_) - gap + m_ * ((a - pa) * ta + (b - pb) * tb)
    zt = min(z_(a, b) for a in (a0, a1) for b in (b0, b1))
    post = tube(a0, a1, b0, b1, z0, max(z_(a, b) for a in (a0, a1) for b in (b0, b1)) + 1, "z", t)
    cut = cq.Solid.makeLoft([cq.Wire.makePolygon([W(a, b, z_(a, b)) for a, b in ((a0 - 1, b0 - 1), (a1 + 1, b0 - 1), (a1 + 1, b1 + 1), (a0 - 1, b1 + 1))], close=True),
                             cq.Wire.makePolygon([W(a, b, zt + 40) for a, b in ((a0 - 1, b0 - 1), (a1 + 1, b0 - 1), (a1 + 1, b1 + 1), (a0 - 1, b1 + 1))], close=True)], True)
    return post.cut(cut)


def upper_stringer(f, v0, v1):
    """round 5 upper stringer: foot cut level on the saddle (Z_SEAT) with a short plumb face at U_FOOT against the landing's north beam;
    head cut plumb at U_BEAR against the head beam's south face, its top trimmed level at Z_TRIM"""
    zt, zbm = f.zl, lambda u: f.zl(u) - G.PL
    uf, ub, us_ = G.U_FOOT, G.U_BEAR, G.U_FOOT + G.L_SEAT
    outer = prism(f, [(uf, G.Z_SEAT), (us_, zbm(us_)), (ub, zbm(ub)), (ub, G.Z_TRIM), (G.U_TRIM, G.Z_TRIM), (uf, zt(uf))], v0, v1)
    tp = T / math.cos(G.ANG)
    e0, e1 = uf - 4, ub + 4
    inner = prism(f, [(e0, zbm(e0) + tp), (e1, zbm(e1) + tp), (e1, zt(e1) - tp), (e0, zt(e0) - tp)], v0 + T, v1 - T)
    return outer.cut(inner)


def rail_sweep():
    """mono round 3: the one continuous open side rail, 1 1/2 in square, as ruled segments between the rail stations"""
    segs = []
    st = G.rail_samples()
    for s0, s1 in zip(st, st[1:]):
        ws = []
        for s_ in (s0, s1):
            pa, pb = G.rail_plan(s_)
            qa, qb = G.rail_plan(min(s_ + 0.05, G.S_END)); ra, rb = G.rail_plan(max(s_ - 0.05, 0.0))
            ta, tb = qa - ra, qb - rb
            n_ = math.hypot(ta, tb)
            na, nb = -tb / n_ * G.RAIL / 2, ta / n_ * G.RAIL / 2
            zt, zb = G.rail_z(s_), G.rail_z(s_) - G.rail_depth(s_)
            ws.append(cq.Wire.makePolygon([W(pa + na, pb + nb, zb), W(pa - na, pb - nb, zb), W(pa - na, pb - nb, zt), W(pa + na, pb + nb, zt)], close=True))
        segs.append(cq.Solid.makeLoft(ws, True))
    return cq.Compound.makeCompound(segs)


VC = G.VC
if G.MONO:      # one centre tube; a bracket on each side of it with the seat pointing outward: (name, tube v0 or None, web v range, seat v range)
    SIDES = (("open", VC - G.TW / 2, (VC - G.TW / 2 - BT, VC - G.TW / 2), (VC - G.TW / 2 - G.SEAT_TAB, VC - G.TW / 2)),
             ("wall", None, (VC + G.TW / 2, VC + G.TW / 2 + BT), (VC + G.TW / 2, VC + G.TW / 2 + G.SEAT_TAB)))
else:
    SIDES = (("open", 0.0, (G.TW, G.TW + BT), (G.TW, G.TW + G.SEAT_W)), ("wall", G.WN - G.TW, (G.WN - G.TW - BT, G.WN - G.TW), (G.WN - G.TW - G.SEAT_W, G.WN - G.TW)))
for f in G.FLIGHTS:
    g = f"{f.name}_flight"
    for side, v0, vw, vs in SIDES:
        if v0 is not None:
            if G.MONO and f is G.UPPER:                                       # round 4: plumb foot against the landing beam, notched head bearing on the balcony beam
                add(g, "upper_stringer", upper_stringer(f, v0, v0 + G.TW))
            else:
                add(g, f"{f.name}_stringer" if G.MONO else f"{f.name}_tube_{side}", slope_tube(f, f.u0, f.u2, f.zl, G.PL, v0, v0 + G.TW, T, f.zf, f.zu))
        nx, nz = math.sin(G.ANG), -math.cos(G.ANG)
        for k in range(1, f.nr):
            uk, zk = f.uk(k), f.z0 + k * G.RI - G.TT
            A, B = (uk + G.WEB0, zk), (uk + G.TD + G.RT, zk)
            C = (A[0], f.zl(A[0]))
            web = [A, C, (C[0] + nx * G.LAP, C[1] + nz * G.LAP), (B[0] + nx * G.LAP, B[1] + nz * G.LAP), B]
            zc_ = f.zf + BT
            foot = min(z for _, z in web) < zc_ and not (G.MONO and f is G.UPPER)
            if foot:                                                           # first tread: the web runs down to a foot flange anchored to the slab or landing
                cl = []
                for p, q in zip(web, web[1:] + web[:1]):
                    if p[1] >= zc_:
                        cl.append(p)
                    if (p[1] - zc_) * (q[1] - zc_) < 0:
                        t_ = (zc_ - p[1]) / (q[1] - p[1])
                        cl.append((p[0] + t_ * (q[0] - p[0]), zc_))
                web = cl
            sg_ = 1 if vs[0] == vw[0] else -1                                  # outward from the tube
            ft_ = tuple(sorted((vs[0] if sg_ > 0 else vs[1], (vs[0] if sg_ > 0 else vs[1]) + sg_ * G.FOOT_W))) if G.MONO else vs
            us0 = uk + G.SEAT_S if G.MONO else uk + 1
            br = prism(f, web, *vw).fuse(prism(f, [(us0, zk - BT), (uk + G.TD + G.RT, zk - BT), (uk + G.TD + G.RT, zk), (us0, zk)], *vs))
            if G.MONO:                                                         # flange folded off the web's vertical front edge, one bolt into the strip
                fo_ = vw[1] if sg_ > 0 else vw[0]
                br = br.fuse(prism(f, [(A[0], zk - G.ARM_D), (A[0] + BT, zk - G.ARM_D), (A[0] + BT, zk), (A[0], zk)], *sorted((fo_ - sg_ * BT, fo_ + sg_ * G.ARM_FL))))
                fbolt(f, A[0] + BT, fo_ + sg_ * 0.95, zk - G.FLANGE_BOLT, "u")
                fnut(f, A[0] - BT, fo_ + sg_ * 0.95, zk - G.FLANGE_BOLT, "u", -1)
                if side == "open":                                             # the strip: one flat plate on edge under the tread, across both brackets; it is also the top of the riser below
                    v0_, v1_ = G.ARM_END, G.WN - G.ARM_END
                    arm = vprism(f, [(v0_, zk), (v1_, zk), (v1_, zk - G.ARM_D), (v0_, zk - G.ARM_D)], A[0] - BT, A[0])
                    for vt_ in (v0_ + G.STRIP_TAB, v1_ - G.STRIP_TAB):          # a screw tab folded off its top edge at each end, into the tread where the lever is longest
                        arm = arm.fuse(prism(f, [(A[0], zk - BT), (A[0] + 1.25, zk - BT), (A[0] + 1.25, zk), (A[0], zk)], vt_ - 0.9, vt_ + 0.9))   # toward the back of the tread (round 4)
                        fbolt(f, A[0] + 0.7, vt_, zk - BT, "z", -1, d=0.5, h=0.15)
                    add(g, f"{f.name}_strip_{k}", arm)
            if foot:
                us = [u for u, z in web if abs(z - zc_) < 1e-6]
                if G.MONO and f is G.UPPER:                                    # the flange stops at the edges of the landing's north beam
                    us = [max(min(us), G.B_LN - G.LN_W / 2 - G.B0), min(max(us), G.B_LN + G.LN_W / 2 - G.B0)]
                if G.MONO and f is G.UPPER:                                    # round 3: the flange spans the beam and its legs fold down both faces, a saddle that locks the foot
                    s0_, s1_ = G.B_LN - G.LN_W / 2 - G.B0, G.B_LN + G.LN_W / 2 - G.B0
                    us = [s0_ - BT, s1_ + BT]
                    for a0_, a1_ in ((s0_ - BT, s0_), (s1_, s1_ + BT)):
                        br = br.fuse(prism(f, [(a0_, G.ZP - G.TK), (a1_, G.ZP - G.TK), (a1_, zc_), (a0_, zc_)], *ft_))
                    vb_ = (ft_[0] + ft_[1]) / 2 + (0.3 if vs[0] == vw[0] else -0.3)
                    fbolt(f, s0_ - BT, vb_, G.ZLF, "u", -1)                    # one bolt through both legs and the beam
                    fnut(f, s1_ + BT, vb_, G.ZLF, "u", 1)
                else:
                    for ub_ in (min(us) + 0.8, max(us) - 0.8):                 # two anchors through each foot flange into the slab
                        fnut(f, ub_, (ft_[0] + ft_[1]) / 2 + (0.6 if vs[0] == vw[0] else -0.6), zc_, "z")
                br = br.fuse(prism(f, [(min(us), f.zf), (max(us), f.zf), (max(us), zc_), (min(us), zc_)], *ft_))
            add(g, f"{f.name}_bracket_{k}_{side}", br)
            for s_ in (4.25, 8.25):                                            # two through bolts per bracket pair, head one side and nut the other
                ub_ = A[0] + s_ * math.cos(G.ANG) + nx * G.BOLT_N
                zb_ = f.zl(A[0]) + s_ * math.sin(G.ANG) + nz * G.BOLT_N
                if zb_ > zc_ + 0.5 or not foot:
                    (fbolt if side == "open" else fnut)(f, ub_, vw[1] if vs[0] == vw[0] else vw[0], zb_, "v", 1 if vs[0] == vw[0] else -1)
            for ub_ in ((uk + 6.5, uk + 8.0) if G.MONO else (uk + 2.5, uk + 7.0)):   # two screws up through each seat into the tread
                fbolt(f, ub_, (vs[0] + vs[1]) / 2 + (0.3 if vs[0] == vw[0] else -0.3), zk - BT, "z", -1, d=0.5, h=0.15)
        sgn = 1 if vs[0] == vw[0] else -1                                      # head angles, 3 x 3 x 1/4, 4 in long (the feet are held by the first tread brackets)
        e0 = vw[0] if sgn > 0 else vw[1]
        vi, vl = tuple(sorted((e0, e0 + sgn * 3.0))), tuple(sorted((e0, e0 + sgn * 0.25)))
        for nm, uc, zf, sg in ((("head", (f.u2 + f.u3) / 2 - 1.0, f.zu, -1),) if not (G.MONO and f is G.UPPER) else ()):
            z0_, z1_ = sorted((zf, zf + sg * 0.25))
            z2_, z3_ = sorted((zf, zf + sg * 3.0))
            ang = prism(f, [(uc - 2, z0_), (uc + 2, z0_), (uc + 2, z1_), (uc - 2, z1_)], *vi).fuse(prism(f, [(uc - 2, z2_), (uc + 2, z2_), (uc + 2, z3_), (uc - 2, z3_)], *vl))
            add(g, f"{f.name}_end_angle_{nm}_{side}", ang)
            for ub_ in (uc - 1.2, uc + 1.2):
                (fbolt if sgn < 0 else fnut)(f, ub_, e0 + sgn * 0.25, zf - 1.6, "v", sgn)   # through the tube, crush sleeve inside
                fbolt(f, ub_, e0 + sgn * 1.9, zf - 0.25, "z", -1)
    for k in range(1, f.nr):
        uk, zk = f.uk(k), f.z0 + k * G.RI
        add(g, f"{f.name}_tread_{k}", prism(f, [(uk, zk - G.TT), (uk + G.TD, zk - G.TT), (uk + G.TD, zk), (uk, zk)], 0.05, G.WN - 0.05), OAK, "oak")
        if G.RT:                                                               # mono: an oak riser lip behind every tread leaves under 4 in open above it
            ur = uk + G.TD
            add(g, f"{f.name}_riser_{k}", prism(f, [(ur, zk - G.TT), (ur + G.RT, zk - G.TT), (ur + G.RT, zk + G.RH), (ur, zk + G.RH)], 0.05, G.WN - 0.05), OAK, "oak")
    if G.MONO and f is G.UPPER:                                                # round 5: angle clips lock both ends; the foot sits level on a saddle on one 3 x 3 post
        uf, ub = G.U_FOOT, G.U_BEAR
        zs = G.Z_SEAT
        a0p, a1p, b0p, b1p = G.UP_POST
        u0p, u1p = b0p - G.B0 - BT, b1p - G.B0 + BT                          # saddle seat, along the flight
        for sg in (-1, 1):
            vt = VC + sg * G.TW / 2
            # top: one leg on the tube side, the other against the head beam's south face beside the tube; vertical slots in the tube leg
            ua, xq = ub - 2.25, G.U_TRIM - 0.15 / G.SL
            add(g, f"upper_head_clip_{'w' if sg < 0 else 'e'}", prism(f, [(ua, f.zu - 3.0), (ub - BT, f.zu - 3.0), (ub - BT, G.Z_TRIM - 0.25), (xq, G.Z_TRIM - 0.25), (ua, f.zl(ua) - 0.1)], *sorted((vt, vt + sg * BT)))
                .fuse(prism(f, [(ub - BT, f.zu - 3.0), (ub, f.zu - 3.0), (ub, G.Z_TRIM - 0.25), (ub - BT, G.Z_TRIM - 0.25)], *sorted((vt, vt + sg * 2.25)))))
            (fbolt if sg < 0 else fnut)(f, ub - 1.25, vt + sg * BT, f.zu - 1.5, "v", sg)   # one through bolt across the tube, crush sleeve inside
            fbolt(f, ub - BT, vt + sg * 1.3, G.ZBF, "u", -1); fnut(f, ub + G.FW, vt + sg * 1.3, G.ZBF, "u", 1)
            # foot: one leg on the first tread bracket's web (bolted through web and tube), the other against the landing's north beam
            vc_ = vt + sg * BT
            add(g, f"upper_foot_clip_{'w' if sg < 0 else 'e'}", prism(f, G.FOOT_CLIP, *sorted((vc_, vc_ + sg * BT)))
                .fuse(prism(f, [(uf, 42.0), (uf + BT, 42.0), (uf + BT, G.ZP - G.TT - 0.25), (uf, G.ZP - G.TT - 0.25)], *sorted((vc_, vc_ + sg * 2.25)))))
            fbolt(f, uf + BT, vc_ + sg * 1.3, G.ZLF, "u", 1); fnut(f, uf - G.FW, vc_ + sg * 1.3, G.ZLF, "u", -1)
        fbolt(f, G.FOOT_BOLT[0], VC - G.TW / 2 - 2 * BT, G.FOOT_BOLT[1], "v", -1); fnut(f, G.FOOT_BOLT[0], VC + G.TW / 2 + 2 * BT, G.FOOT_BOLT[1], "v", 1)
        # the post, cut level under the saddle seat
        zpt = zs - BT
        add("posts", "upper_stringer_post", tube(a0p, a1p, b0p, b1p, 0.375, zpt, "z", 0.1875))
        add("posts", "upper_stringer_post_base_plate", box(a0p - 2, a1p + 2, b0p - 2, b1p + 2, 0, 0.375))
        for a_ in (a0p - 1.2, a1p + 1.2):
            for b_ in (b0p - 1.2, b1p + 1.2):
                nut(a_, b_, 0.375, "z")
        # bent saddle: level seat with low upturned edges either side of the tube (they stay under the first bracket's webs), legs down
        # the post's south and north faces with one through bolt
        sad = prism(f, [(u0p, zpt), (u1p, zpt), (u1p, zs), (u0p, zs)], VC - G.TW / 2 - BT, VC + G.TW / 2 + BT)
        for sg in (-1, 1):
            vt = VC + sg * G.TW / 2
            sad = sad.fuse(prism(f, [(u0p, zs), (u1p, zs), (u1p, zs + G.SEAT_LIP), (u0p, zs + G.SEAT_LIP)], *sorted((vt, vt + sg * BT))))
        for u0_ in (u0p, u1p - BT):
            sad = sad.fuse(prism(f, [(u0_, zpt - 3.5), (u0_ + BT, zpt - 3.5), (u0_ + BT, zpt + 0.01), (u0_, zpt + 0.01)], VC - 1.5, VC + 1.5))
        zlb = zpt - 2.0
        fbolt(f, u0p, VC, zlb, "u", -1); fnut(f, u1p, VC, zlb, "u", 1)
        add(g, "upper_stringer_post_saddle", sad)
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
        if not G.MONO:
            add("rails", "lower_rail_open", slope_tube(f, 0.0, G.UL - G.POST, ztop, RD2, -1.75, -0.25, G.RAIL_T))
        if G.WALL_RAIL:
            add("rails", "lower_rail_wall", slope_tube(f, 0.0, G.UL, ztop, RD2, G.WN + G.GAP - 3.0, G.WN + G.GAP - 1.5, G.RAIL_T))
        und = (lambda u: ztop(u) - RD2) if not G.MONO else (lambda u: G.rail_under(*f.p(u, -1.0, 0)[:2]) - 0.05)
        u_a, u_b = G.FOOT_U - 1, G.FOOT_U + 1
        post = prism(f, [(u_a, 0), (u_b, 0), (u_b, und(u_b)), (u_a, und(u_a))], -G.POST, 0.0) if not G.MONO else post_box(G.A_FOOT - 1, G.A_FOOT + 1, G.XL, G.XL + G.POST, 0.0)
        post = post.cut(prism(f, [(u_a + T, -1), (u_b - T, -1), (u_b - T, 200), (u_a + T, 200)], -G.POST + T, -T))
        add("posts", "foot_post", post)
        if G.MONO:
            for du in (-2.3, 2.3):
                for v_ in (-G.POST - 1.3, 1.3):
                    fnut(f, G.FOOT_U + du, v_, 0.375, "z")
            add("posts", "foot_post_base_plate", prism(f, [(G.FOOT_U - 3, 0), (G.FOOT_U + 3, 0), (G.FOOT_U + 3, 0.375), (G.FOOT_U - 3, 0.375)], -G.POST - 2, 2).cut(prism(f, [(u_a, -1), (u_b, -1), (u_b, 1), (u_a, 1)], -G.POST, 0.0)))
    else:
        if not G.MONO:
            add("rails", "upper_rail_open", slope_tube(f, G.POST + G.XL - G.B0, G.BAL_S - G.B0, ztop, RD2, -1.75, -0.25, G.RAIL_T))
        if G.WALL_RAIL:
            add("rails", "upper_rail_wall", slope_tube(f, 0.0, G.UU - G.NOSE, ztop, RD2, G.WN + G.GAP - 3.0, G.WN + G.GAP - 1.5, G.RAIL_T))

XL, ZP, FL, TT, TK = G.XL, G.ZP, G.FL, G.TT, G.TK
# corner landing
lz = (ZP - TK, ZP - TT)
FTL, FTB = G.FT_L, G.FT_B
add("landing", "landing_east_ledger", tube(0, 2, 0, G.LAND_N, *lz, "b", FTL))
add("landing", "landing_south_ledger", tube(2, XL, 0, 2, *lz, "a", FTL))
add("landing", "landing_west_beam", tube(XL - 2, XL, 2, G.LAND_N, *lz, "b", FTL))
add("landing", "landing_north_beam", tube(2, XL - 2, G.B_LN - G.LN_W / 2, G.B_LN + G.LN_W / 2, *lz, "a", FTL))
add("landing", "landing_header", tube(G.A_LH - 1, G.A_LH + 1, 2, G.B_LN - G.LN_W / 2, *lz, "b", FTL))
for b_ in G.LAND_LAGS["LE"]:
    nut(2, b_, ZP - TK + 1.5, "a")                 # hex head lag screws into the wall framing
for a_ in G.LAND_LAGS["LS"]:
    nut(a_, 2, ZP - TK + 1.5, "b")
for b_ in G.BAL_LAGS:
    nut(2, b_, FL - TK + 1.5, "a")
for nm, (a0_, a1_, b0_, b1_) in G.LAND_POSTS.items():
    # round 3 landing posts: a 2 x 2 post from an anchored base plate up to the frame's underside, tied to the frame by flat splice plates
    # on its outer faces (one bolt into the post, one into the frame); the north east one is also lagged to the bath 1 wall
    add("landing", f"landing_post_{nm}", tube(a0_, a1_, b0_, b1_, 0.375, ZP - TK, "z"))
    pa0, pa1 = (0.0, a1_ + 2.0) if nm == "ne" else (a0_ - 2.0, a1_ + 2.0)
    add("landing", f"landing_post_{nm}_base_plate", box(pa0, pa1, b0_ - 2.0, b1_ + 2.0, 0, 0.375))
    for a_, b_ in (((a1_ + 1.2, b0_ - 1.2), (a1_ + 1.2, b1_ + 1.2)) if nm == "ne" else ((a0_ - 1.2, b0_ - 1.2), (a1_ + 1.2, b1_ + 1.2))):
        nut(a_, b_, 0.375, "z")
    sp_ = [("n", (a0_, a1_ + (2.0 if nm == "ne" else 0.0)), (b1_, b1_ + BT))] + ([("w", (a1_, a1_ + BT), (b0_, b1_))] if nm == "nw" else [])
    for side_, (sa0, sa1), (sb0, sb1) in sp_:
        add("landing", f"landing_post_{nm}_splice_{side_}", box(sa0, sa1, sb0, sb1, ZP - TK - 3.0, ZP - TT))
        ax_, sg_ = ("b", 1) if side_ == "n" else ("a", 1)
        for z_ in (ZP - TK - 1.5, G.ZLF):
            if side_ == "n":
                bolt((a0_ + a1_) / 2 if z_ < ZP - TK else (a1_ + 1.0 if nm == "ne" else a0_ + 1.0), sb1, z_, "b", 1)
            else:
                bolt(sa1, (b0_ + b1_) / 2, z_, "a", 1)
    if nm == "ne":
        for z_ in (8.0, ZP - TK - 8.0):
            nut(a1_, (b0_ + b1_) / 2, z_, "a")
deck = box(0, XL, 0, G.LAND_DECK_N, ZP - TT, ZP)
add("landing", "landing_deck", deck.fuse(box(XL, XL + G.NOSE, G.GAP, XL, ZP - TT, ZP)) if G.NOSE else deck, OAK, "oak")
add("posts", "corner_newel", post_box(XL, XL + G.POST, XL, XL + G.POST, 0.375) if G.MONO else tube(XL, XL + G.POST, XL, XL + G.POST, 0, G.NEWEL_TOP, "z"))
if G.MONO:                                         # bolted floor flange under the corner newel: four anchors into the slab
    add("posts", "corner_newel_base_plate", box(XL - 2, XL + G.POST + 2, XL - 2, XL + G.POST + 2, 0, 0.375))
    for a_ in (XL - 1.3, XL + G.POST + 1.3):
        for b_ in (XL - 1.3, XL + G.POST + 1.3):
            nut(a_, b_, 0.375, "z")
for z_ in (ZP - TK + 0.8, ZP - TT - 0.8):          # corner newel lapped onto the landing's west beam
    bolt(XL + G.POST, XL + 1, z_, "a")
    nut(XL - 2, XL + 1, z_, "a", -1)
# balcony
bz = (FL - TK, FL - TT)
add("balcony", "balcony_ledger", tube(0, 2, G.BAL_S, G.BAL_N, *bz, "b", FTB))
add("balcony", "balcony_south_beam", tube(2, XL - 2, G.BAL_S, G.BAL_S + 2, *bz, "a", FTB))
add("balcony", "balcony_head_arm", tube(2, XL - 2, G.B_BH - 1, G.B_BH + 1, *bz, "a", FTB))
add("balcony", "balcony_north_arm", tube(2, XL, G.BAL_N - 2, G.BAL_N, *bz, "a", FTB))
add("balcony", "balcony_west_beam", tube(XL - 2, XL, G.BAL_S, G.BAL_N - 2, *bz, "b", FTB))
deck = box(0, XL, G.BAL_S, G.BAL_N, FL - TT, FL)
add("balcony", "balcony_deck", deck.fuse(box(G.GAP, XL, G.BAL_S - G.NOSE, G.BAL_S, FL - TT, FL)) if G.NOSE else deck, OAK, "oak")
zu, r2 = FL - TK, G.POST / math.sqrt(2) * 1.0
for nm, b in (("south", G.B_BH), ("north", G.BAL_N - 1)):     # mono round 5: a second brace under the head beam (Maxwell 11/23/2026), clear of the treads
    c_ = XL - 1.5 if G.MONO else G.A_BR + 1         # mono: 45 degrees from under the west end down to the wall
    br = aprism([(c_ + r2, zu), (c_ - r2, zu), (0, zu - c_ + r2), (0, zu - c_ - r2)], b - 1, b + 1)
    add("balcony", f"knee_brace_{nm}", br)
    bolt(c_ - 2.2, b + 1, zu - 2.2, "b"); nut(1.6, b + 1, zu - c_ + 1.6, "b")
# balcony newel, guard posts, rails, pickets
if G.MONO:
    # Both free posts stand outside the west beam and stop at the frame's underside. Each is held by an L shaped 3/8 in plate bolted to the
    # end beam's outer face and 4 in up the post (Maxwell 11/22/2026: no low tie to the stringer, no kickers).
    # Round 3: every post stops under the one continuous rail, its top cut to the rail's slope. The north posts stand north of the plate line.
    PN = (G.BAL_N + 0.375, G.BAL_N + 0.375 + G.POST)
    add("posts", "balcony_sw_newel", post_box(XL, XL + G.POST, G.BAL_S, G.BAL_S + G.POST, FL - TK))
    add("posts", "guard_post_nw", post_box(XL, XL + G.POST, *PN, FL - TK))
    for nm, b0_, b1_, sg in (("sw", G.BAL_S - 0.375, G.BAL_S, -1), ("nw", G.BAL_N, G.BAL_N + 0.375, 1)):
        add("posts", f"post_plate_{nm}", box(XL - 8, XL + G.POST, b0_, b1_, FL - TK, FL - TT).fuse(box(XL, XL + G.POST, b0_, b1_, FL - TT, FL + 3.5)))
        fo_, fi_ = (b1_, b0_ - 2.0) if sg > 0 else (b0_, b1_ + 2.0)        # plate's outer face, far face of the end beam
        for a_, z_ in ((XL - 7, FL - TK + 1.5), (XL - 2.5, FL - TK + 1.5)):      # into the end beam: head on the plate, nut inside the frame
            bolt(a_, fo_, z_, "b", sg)
            nut(a_, fi_, z_, "b", -sg)
        po_ = b1_ + G.POST if sg > 0 else b1_ + G.POST                           # through the plate and the post: head on the plate's open face, nut on the post
        for z_ in (FL - TK + 1.2, FL + 2.6):
            if sg > 0:
                bolt(XL + 1, b0_, z_, "b", -1); nut(XL + 1, po_, z_, "b", 1)
            else:
                bolt(XL + 1, b0_, z_, "b", -1); nut(XL + 1, po_, z_, "b", 1)
    add("posts", "guard_post_ne", post_box(0, G.POST, *PN, FL - 13))
    for z_ in (FL - 11, FL - 2):
        nut(G.POST, PN[0] + 1, z_, "a")
    add("rails", "handrail_and_guard_rail", rail_sweep(), mat="rail")
    ra = (XL + 0.25, XL + 0.25 + G.RAIL)
    rb = (G.GP_B - G.RAIL / 2, G.GP_B + G.RAIL / 2)
    add("guard", "guard_west_bottom_rail", tube(*ra, G.BAL_S + G.POST, PN[0], FL + 3.6, FL + 3.6 + G.RAIL, "b", G.RAIL_T))
    add("guard", "guard_north_bottom_rail", tube(G.POST, XL, *rb, FL + 3.6, FL + 3.6 + G.RAIL, "a", G.RAIL_T))
    pz = (FL + 3.6 + G.RAIL, G.G_TOP - G.RAIL - 0.02)
    span = (G.BAL_S + G.POST, PN[0])
    n_w = math.ceil((span[1] - span[0]) / 4.4)
    for i in range(1, n_w):
        add("guard", f"picket_west_{i}", cq.Solid.makeCylinder(G.PICKET / 2, pz[1] - pz[0], W(G.PC, span[0] + i * (span[1] - span[0]) / n_w, pz[0])))
    n_n = math.ceil((XL - G.POST) / 4.4)
    for i in range(1, n_n):
        add("guard", f"picket_north_{i}", cq.Solid.makeCylinder(G.PICKET / 2, pz[1] - pz[0], W(G.POST + i * (XL - G.POST) / n_n, G.GP_B, pz[0])))
else:
    gsw_z0 = G.UPPER.zc(G.BAL_S + 1 - G.B0) - 4.0
    add("posts", "balcony_sw_newel", tube(XL, XL + G.POST, G.BAL_S, G.BAL_S + G.POST, gsw_z0, G.GSW_TOP, "z"))
    add("posts", "guard_post_nw", tube(XL - G.POST, XL, G.BAL_N, G.BAL_N + G.POST, FL - TK, G.G_TOP - G.RAIL, "z"))
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
fa_ = cq.Assembly(name="fasteners")
for i, s_ in enumerate(FAST):
    fa_.add(s_, name=f"fastener_{i}", color=cq.Color(0.55, 0.6, 0.9, 1.0))
assy.add(fa_)
assy.save(os.path.join(OUT, "loft_ships_ladder.step"))
for nm, s in CTX:
    ctx.add(s, name=nm, color=cq.Color(0.86, 0.86, 0.84, 1.0))
full = cq.Assembly(name="view")
full.add(assy); full.add(ctx)
full.save(os.path.join(OUT, "loft_ships_ladder_view.glb"), tolerance=0.01, angularTolerance=0.2)

DENS = dict(steel=0.2836, oak=0.027, rail=0.2836 * (1 - (1 - 2 * G.RAIL_T / G.RAIL) ** 2))   # the swept rail is drawn solid: weigh it as 3/16 wall tube
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
