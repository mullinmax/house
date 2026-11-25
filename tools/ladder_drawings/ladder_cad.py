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


def post_base(post):
    """round 11: the standard post base, a 7 x 7 x 1/2 plate with rounded corners on four slab anchors, two clips cut from L 2 x 2 x 3/8
    against the post, one through bolt across the post and the clips, a flat head screw up through the plate into each clip"""
    rect, axis = G.POST_BASES[post]
    pb = G.post_base(*rect, axis)
    w = cq.Wire.makePolygon([W(a, b, 0.0) for a, b in pb["plate"]], close=True)
    add("posts", f"{post}_base_plate", cq.Solid.extrudeLinear(cq.Face.makeFromWires(w), cq.Vector(0, 0, G.BP_T)))
    for up, fl, sg in pb["clips"]:
        side = ("west" if sg > 0 else "east") if axis == "a" else ("north" if sg > 0 else "south")
        add("posts", f"{post}_base_clip_{side}", box(*up).fuse(box(*fl)))
    for (ha, hb, hz), (na, nb, nz) in pb["bolts"]:
        bolt(ha, hb, hz, axis, 1); nut(na, nb, nz, axis, -1)
    for a_, b_ in pb["anchors"]:
        nut(a_, b_, G.BP_T, "z")
    for a_, b_ in pb["screws"]:
        nut(a_, b_, G.BP_T + G.BC_T, "z", role="fhs")


def rail_post_base(post):
    """round 12: one bent 3/8 plate under a 2 x 2 rail post: anchor flanges south and east, tabs up its north and west faces, 2 through
    bolts per tab (staggered so they pass each other inside the post)"""
    (a0, a1, b0, b1), _ = G.POST_BASES[post]
    if G.RAIL_STYLE == "pipe":                      # round 13 option B: a stock railing flange (Kee Klamp style), socket with 2 set screws, 4 anchors
        ac, bc = (a0 + a1) / 2, (b0 + b1) / 2
        fl = cq.Solid.makeCylinder(G.PF_D / 2, G.PF_T, W(ac, bc, 0.0)).fuse(cq.Solid.makeCylinder(G.PF_SOCK / 2, G.PF_H, W(ac, bc, 0.0)))
        fl = fl.cut(cq.Solid.makeCylinder(G.PIPE_POST[0] / 2, G.PF_H, W(ac, bc, G.PF_T)))
        add("posts", f"{post}_base", fl.clean())
        for k in range(4):
            th = math.pi / 4 + k * math.pi / 2
            nut(ac + G.PF_BC / 2 * math.cos(th), bc + G.PF_BC / 2 * math.sin(th), G.PF_T, "z")
        for sg in (1, -1):                          # two set screws into the post, east and west
            bolt(ac + sg * G.PF_SOCK / 2, bc, G.PF_T + (G.PF_H - G.PF_T) / 2, "a", sg, d=0.35, h=0.06, role=("set screw", 0.375, 0.5, 0.5))
        return
    rb = G.rail_post_base(a0, a1, b0, b1)
    w = cq.Wire.makePolygon([W(a, b, 0.0) for a, b in rb["plate"]], close=True)
    s_ = cq.Solid.extrudeLinear(cq.Face.makeFromWires(w), cq.Vector(0, 0, G.RB_T))
    for tb in rb["tabs"].values():
        s_ = s_.fuse(box(*tb))
    add("posts", f"{post}_base", s_.clean())
    for side, ax, (ha, hb, hz), (na, nb, nz) in rb["bolts"]:
        bolt(ha, hb, hz, ax, 1); nut(na, nb, nz, ax, -1)
    for a_, b_ in rb["anchors"]:
        nut(a_, b_, G.RB_T, "z")


def zprism(f, uv, z0, z1):
    """polygon in a flight's plan (u, v), from z0 up to z1"""
    w = cq.Wire.makePolygon([W(*f.p(u, v, z0)) for u, v in uv], close=True)
    return cq.Solid.extrudeLinear(cq.Face.makeFromWires(w), cq.Vector(0, 0, z1 - z0))


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


_bbo2 = lambda p, q: p.xmin < q.xmax and q.xmin < p.xmax and p.ymin < q.ymax and q.ymin < p.ymax and p.zmin < q.zmax and q.zmin < p.zmax


def add(group, name, solid, colour=STEEL, mat="steel"):
    PARTS.append((group, name, solid, colour, mat))


FAST = []                                          # bolt heads, nuts and anchors, shown so every joint reads as bolted (Maxwell 11/22/2026: no welding anywhere)
HEADS = []                                         # round 11b: every head and nut drawn, so the whole bolts can be built from them (build_bolts)
SHANKS = []                                        # (solid, threaded?) for the assembly
BOLT_LINES = []                                    # (start, end, kind) of each whole fastener, head bearing face to tip (check_attached.py)


def bolt(a, b, z, axis, sign=1, d=0.66, h=0.21, kind="socket", role=None):
    """a head standing on the point (a, b, z), pointing along +/- axis 'a', 'b' or 'z'. kind 'socket' = socket button head (Allen key, round),
    'hex' = hex head or hex nut (slab anchors, lag screws, and the nut end of through bolts). Maxwell 11/22/2026: no square heads."""
    dv = dict(a=cq.Vector(-sign, 0, 0), b=cq.Vector(0, sign, 0), z=cq.Vector(0, 0, sign))[axis]
    HEADS.append(dict(o=W(a, b, z), dv=dv, kind=kind, d=d, role=role))
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


def fboltn(f, u, v, z, d_uz, d=0.66, h=0.21, kind="socket", role=None):
    """a head on the flight point (u, v, z) pointing along the (u, z) direction d_uz (round 10: the floor shoe's sloped bolt)"""
    o = W(*f.p(u, v, z))
    dv = W(*f.p(u + d_uz[0], v, z + d_uz[1])) - o
    dv = dv * (1.0 / dv.Length)
    HEADS.append(dict(o=o, dv=dv, kind=kind, d=d, role=role))
    if kind == "socket":
        FAST.append(cq.Solid.makeCylinder(d / 2, h, o, dv))
        return
    d, h = 0.65, 0.33
    e1 = W(*f.p(u, v + 1, z)) - o
    e1 = e1 * (1.0 / e1.Length)
    e2 = dv.cross(e1)
    r = d / math.sqrt(3)
    pts = [o + e1 * (r * math.cos(math.pi / 3 * i)) + e2 * (r * math.sin(math.pi / 3 * i)) for i in range(6)]
    FAST.append(cq.Solid.extrudeLinear(cq.Face.makeFromWires(cq.Wire.makePolygon(pts, close=True)), dv * h))


def fbolt(f, u, v, z, axis, sign=1, **kw):
    """the same in a flight's (u, v, z); axis 'v' or 'z'"""
    a, b, _ = f.p(u, v, z)
    if axis == "z":
        return bolt(a, b, z, "z", sign, **kw)
    a2, b2, _ = f.p(u, v + sign, z) if axis == "v" else f.p(u + sign, v, z)
    bolt(a, b, z, "a" if abs(a2 - a) > 0.5 else "b", (1 if a2 > a else -1) if abs(a2 - a) > 0.5 else (1 if b2 > b else -1), **kw)


def fnut(f, u, v, z, axis, sign=1, **kw):
    fbolt(f, u, v, z, axis, sign, kind="hex", **kw)


def post_box(a0, a1, b0, b1, z0, t=None, gap=0.12):
    """mono round 3: a square tube post standing from z0, its top cut to the plane of the rail's underside so the rail runs over it unbroken"""
    t = G.POST_T if t is None else t
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
    """mono stringer, round 5 head (both flights from round 6): head cut plumb at the beam's face, its top trimmed level at the frame top.
    Upper foot: cut level on the saddle (Z_SEAT) with a short plumb face at U_FOOT against the landing's north beam. Lower foot: level on the slab."""
    zt, zbm = f.zl, lambda u: f.zl(u) - G.PL
    ub, ztr, utr, _ = G.head_cut(f)
    if f is G.UPPER:
        uf, us_ = G.U_FOOT, G.U_FOOT + G.L_SEAT
        foot = [(uf, G.Z_SEAT), (us_, zbm(us_))]
    else:
        uf = f.u0
        foot = [(f.u0, f.zf), (f.u1, f.zf)]
    outer = prism(f, foot + [(ub, zbm(ub)), (ub, ztr), (utr, ztr), (uf, zt(uf))], v0, v1)
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
    SIDES = (("open", VC - G.TW / 2, (VC - G.TW / 2 - G.WEB_T, VC - G.TW / 2), (VC - G.TW / 2 - G.SEAT_TAB, VC - G.TW / 2)),
             ("wall", None, (VC + G.TW / 2, VC + G.TW / 2 + G.WEB_T), (VC + G.TW / 2, VC + G.TW / 2 + G.SEAT_TAB)))
else:
    SIDES = (("open", 0.0, (G.TW, G.TW + BT), (G.TW, G.TW + G.SEAT_W)), ("wall", G.WN - G.TW, (G.WN - G.TW - BT, G.WN - G.TW), (G.WN - G.TW - G.SEAT_W, G.WN - G.TW)))
for f in G.FLIGHTS:
    g = f"{f.name}_flight"
    for side, v0, vw, vs in SIDES:
        if v0 is not None:
            if G.MONO:                                                         # plumb head bearing on the beam (round 5 upper, round 6 lower too)
                add(g, f"{f.name}_stringer", upper_stringer(f, v0, v0 + G.TW))
            else:
                add(g, f"{f.name}_stringer" if G.MONO else f"{f.name}_tube_{side}", slope_tube(f, f.u0, f.u2, f.zl, G.PL, v0, v0 + G.TW, T, f.zf, f.zu))
        nx, nz = math.sin(G.ANG), -math.cos(G.ANG)
        for k in range(1, f.nr):
            uk, zk = f.uk(k), f.z0 + k * G.RI - G.TT
            A, B = (uk + G.WEB0, zk), (uk + G.TD + G.RT, zk)
            web = G.bracket_web(f, k)                                          # round 6: corners rounded
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
            br = prism(f, web, *vw).fuse(prism(f, [(us0, zk - G.WEB_T), (uk + G.SEAT_E, zk - G.WEB_T), (uk + G.SEAT_E, zk), (us0, zk)], *vs))
            if G.MONO and G.STRIPS:                                            # flange folded off the web's vertical front edge, one bolt into the strip
                fo_ = vw[1] if sg_ > 0 else vw[0]
                br = br.fuse(prism(f, [(A[0], zk - G.ARM_D), (A[0] + BT, zk - G.ARM_D), (A[0] + BT, zk), (A[0], zk)], *sorted((fo_ - sg_ * BT, fo_ + sg_ * G.ARM_FL))))
                fbolt(f, A[0] + BT, fo_ + sg_ * 0.95, zk - G.FLANGE_BOLT, "u")
                fnut(f, A[0] - BT, fo_ + sg_ * 0.95, zk - G.FLANGE_BOLT, "u", -1)
                if side == "open":                                             # the strip: one flat plate on edge under the tread, across both brackets; it is also the top of the riser below
                    v0_, v1_ = G.ARM_END, G.WN - G.ARM_END
                    arm = vprism(f, G.strip_outline(zk), A[0] - BT, A[0])     # round 7: bottom end corners rounded
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
                    sgv = 1 if vs[0] == vw[0] else -1
                    (fbolt if side == "open" else fnut)(f, ub_, vw[1] if sgv > 0 else vw[0], zb_, "v", sgv)
            for ub_ in G.seat_lags(uk):                                         # screws (no strip option: bigger lags) up through each seat into the tread
                fbolt(f, ub_, (vs[0] + vs[1]) / 2 + (G.SEAT_LAG_V if vs[0] == vw[0] else -G.SEAT_LAG_V), zk - G.WEB_T, "z", -1, d=0.5 if G.STRIPS else 0.56, h=0.15 if G.STRIPS else 0.22, role=("lag screw", 0.3125, 1.5, 1.0))
        sgn = 1 if vs[0] == vw[0] else -1                                      # head angles, 3 x 3 x 1/4, 4 in long (the feet are held by the first tread brackets)
        e0 = vw[0] if sgn > 0 else vw[1]
        vi, vl = tuple(sorted((e0, e0 + sgn * 3.0))), tuple(sorted((e0, e0 + sgn * 0.25)))
        for nm, uc, zf, sg in ((("head", (f.u2 + f.u3) / 2 - 1.0, f.zu, -1),) if not G.MONO else ()):
            z0_, z1_ = sorted((zf, zf + sg * 0.25))
            z2_, z3_ = sorted((zf, zf + sg * 3.0))
            ang = prism(f, [(uc - 2, z0_), (uc + 2, z0_), (uc + 2, z1_), (uc - 2, z1_)], *vi).fuse(prism(f, [(uc - 2, z2_), (uc + 2, z2_), (uc + 2, z3_), (uc - 2, z3_)], *vl))
            add(g, f"{f.name}_end_angle_{nm}_{side}", ang)
            for ub_ in (uc - 1.2, uc + 1.2):
                (fbolt if sgn < 0 else fnut)(f, ub_, e0 + sgn * 0.25, zf - 1.6, "v", sgn)   # through the tube, crush sleeve inside
                fbolt(f, ub_, e0 + sgn * 1.9, zf - 0.25, "z", -1)
    for k in range(1, f.nr):
        if G.DECOR:                                                            # round 10: decorative strip, stock L 2 x 1 x 1/8, screwed to the oak only
            hl_, sl_, vv_, scr_ = G.decor_strip(f, k)
            add(g, f"{f.name}_decor_strip_{k}", prism(f, [(hl_[0], hl_[2]), (hl_[1], hl_[2]), (hl_[1], hl_[3]), (hl_[0], hl_[3])], *vv_)
                .fuse(prism(f, [(sl_[0], sl_[2]), (sl_[1], sl_[2]), (sl_[1], sl_[3]), (sl_[0], sl_[3])], *vv_)))
            for u_, v_, z_ in scr_:
                fbolt(f, u_, v_, z_, "z", -1, d=0.4, h=0.1, role=("wood screw", 0.19, 0.75, 0.75))
        uk, zk = f.uk(k), f.z0 + k * G.RI
        add(g, f"{f.name}_tread_{k}", prism(f, [(uk, zk - G.TT), (uk + G.TD, zk - G.TT), (uk + G.TD, zk), (uk, zk)], 0.05, G.WN - 0.05), OAK, "oak")
        if G.RT:                                                               # mono: an oak riser lip behind every tread leaves under 4 in open above it
            ur = uk + G.TD
            add(g, f"{f.name}_riser_{k}", prism(f, [(ur, zk - G.TT), (ur + G.RT, zk - G.TT), (ur + G.RT, zk + G.RH), (ur, zk + G.RH)], 0.05, G.WN - 0.05), OAK, "oak")
            for v_ in G.RISER_SCREW_V:                                         # round 11b: three trim head screws (and glue) through the lip into the tread
                fbolt(f, ur + G.RT, v_, zk - G.TT / 2, "u", 1, d=0.3, h=0.08, role=("trim head screw", 0.164, 2.5, 1.5))
    if G.MONO:                                                                 # head clips: the same part at both stringer tops (round 6)
        hc = G.head_clip(f)
        ub = hc["ub"]
        for sg in (-1, 1):
            vt = VC + sg * G.TW / 2
            add(g, f"{f.name}_head_clip_{'w' if sg < 0 else 'e'}", prism(f, hc["leg"], *sorted((vt, vt + sg * BT)))
                .fuse(prism(f, [(ub - BT, hc["beam"][0]), (ub, hc["beam"][0]), (ub, hc["beam"][1]), (ub - BT, hc["beam"][1])], *sorted((vt, vt + sg * 2.25)))))
            (fbolt if sg < 0 else fnut)(f, *hc["tube_bolt"][:1], vt + sg * BT, hc["tube_bolt"][1], "v", sg)   # one through bolt across the tube, crush sleeve inside
            fbolt(f, ub - BT, vt + sg * 1.3, hc["beam_bolt_z"], "u", -1); fnut(f, ub + G.FW, vt + sg * 1.3, hc["beam_bolt_z"], "u", 1)
    if G.MONO and f is G.LOWER:                                                # round 10: floor shoe, a pocket: base plate and a wall up the tube's top face
        nu_, nz_ = math.sin(G.ANG), -math.cos(G.ANG)                           # into the tube, square to its top face
        shoe = zprism(f, G.shoe_base(), 0.0, BT)
        wall_ = [G.shoe_wall_uz(s_) + (VC + w_,) for s_, w_ in G.shoe_wall()]
        wire_ = cq.Wire.makePolygon([W(*f.p(u_, v_, z_)) for u_, z_, v_ in wall_], close=True)
        shoe = shoe.fuse(cq.Solid.extrudeLinear(cq.Face.makeFromWires(wire_), W(*f.p(-BT * nu_, 0, -BT * nz_)) - W(*f.p(0, 0, 0))))
        shoe = shoe.fuse(prism(f, [(f.u0 - BT * nu_, 0.0), (f.u0, 0.0), (f.u0, f.zf), (f.u0 - BT * nu_, f.zf - BT * nz_)], VC - G.TW / 2, VC + G.TW / 2))   # the bend
        add(g, "lower_floor_shoe", shoe)
        for ua_, va_ in G.shoe_anchors():
            fnut(f, ua_, va_, BT, "z")
        ub_, zb_ = G.shoe_wall_uz(G.SHOE_BOLT_S)                              # its own through bolt: head on the wall, nut on the tube's underside
        fboltn(f, ub_ - BT * nu_, VC, zb_ - BT * nz_, (-nu_, -nz_))
        fboltn(f, ub_ + G.TW * nu_, VC, zb_ + G.TW * nz_, (nu_, nz_), kind="hex")
    if G.MONO and f is G.UPPER:                                                # round 6: the foot sits level on a saddle on one 3 x 3 post; the saddle's
        zs = G.Z_SEAT                                                          # cheeks bolt through the stringer and its tabs to the landing's north beam
        zpt = zs - BT
        a0p, a1p, b0p, b1p = G.UP_POST
        u0p, u1p = G.SAD_U0, G.SAD_U1
        add("posts", "upper_stringer_post", tube(a0p, a1p, b0p, b1p, G.BP_T if G.MONO else 0.0, zpt, "z", 0.1875))   # round 11: stands on its base plate
        post_base("upper_stringer_post")
        sad = prism(f, [(u0p, zpt), (u1p, zpt), (u1p, zs), (u0p, zs)], VC - G.TW / 2 - BT, VC + G.TW / 2 + BT)
        for sg in (-1, 1):
            vt = VC + sg * G.TW / 2
            sad = sad.fuse(prism(f, G.CHEEK, *sorted((vt, vt + sg * BT))))                     # cheek up the stringer side, under the first bracket
            sad = sad.fuse(vprism(f, [(vt + sg * (BT + w_), z_) for w_, z_ in G.tab_outline()], u0p, u0p + BT))   # tab onto the landing's north beam (round 10: full height, rounded)
            fbolt(f, u0p + BT, vt + sg * (BT + 1.05), G.TAB_BOLT_Z, "u", 1); fnut(f, u0p - G.LN_W, vt + sg * (BT + 1.05), G.TAB_BOLT_Z, "u", -1)
        for u0_ in (u0p, u1p - BT):                                            # legs down the post's south and north faces
            sad = sad.fuse(prism(f, [(u0_, zpt - G.SAD_LEG), (u0_ + BT, zpt - G.SAD_LEG), (u0_ + BT, zpt + 0.01), (u0_, zpt + 0.01)], VC - 1.5, VC + 1.5))
        zlb = zpt - 2.0
        fbolt(f, u0p, VC, zlb, "u", -1); fnut(f, u1p, VC, zlb, "u", 1)
        fbolt(f, G.SAD_BOLT[0], VC - G.TW / 2 - BT, G.SAD_BOLT[1], "v", -1); fnut(f, G.SAD_BOLT[0], VC + G.TW / 2 + BT, G.SAD_BOLT[1], "v", 1)
        add(g, "upper_stringer_post_saddle", sad)
    if G.RT and f is G.UPPER:                                                  # and one stands on the landing under the upper flight's first tread
        ur = G.TD - G.GO
        add(g, "landing_riser", prism(f, [(ur, f.z0 - G.TTD), (ur + G.RT, f.z0 - G.TTD), (ur + G.RT, f.z0 + G.RH), (ur, f.z0 + G.RH)], 0.05, G.WN - 0.05), OAK, "oak")
        for v_ in G.RISER_SCREW_V:                                             # into the landing deck's edge
            fbolt(f, ur + G.RT, v_, f.z0 - G.TTD / 2, "u", 1, d=0.3, h=0.08, role=("trim head screw", 0.164, 2.5, 1.5))
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
        if not G.CONT_RAIL:
            add("rails", "lower_rail_open", slope_tube(f, 0.0, G.UL - G.POST, ztop, RD2, -1.75, -0.25, G.RAIL_T))
        if G.WALL_RAIL:
            add("rails", "lower_rail_wall", slope_tube(f, 0.0, G.UL, ztop, RD2, G.WN + G.GAP - 3.0, G.WN + G.GAP - 1.5, G.RAIL_T))
        und = (lambda u: ztop(u) - RD2) if not G.CONT_RAIL else (lambda u: G.rail_under(*f.p(u, -1.0, 0)[:2]) - 0.05)
        u_a, u_b = G.FOOT_U - 1, G.FOOT_U + 1
        post = prism(f, [(u_a, 0), (u_b, 0), (u_b, und(u_b)), (u_a, und(u_a))], -G.POST, 0.0) if not G.CONT_RAIL else post_box(G.A_FOOT - 1, G.A_FOOT + 1, G.XL, G.XL + G.POST, 0.0)
        if G.MONO:                                                             # round 11: stands on its base plate
            post = post.cut(box(G.A_FOOT - 2, G.A_FOOT + 2, G.XL - 1, G.XL + G.POST + 1, -1.0, G.RB_T))   # round 12: on its one piece base
        post = post.cut(prism(f, [(u_a + T, -1), (u_b - T, -1), (u_b - T, 200), (u_a + T, 200)], -G.POST + T, -T))
        add("posts", "foot_post", post)
        if G.MONO:
            rail_post_base("foot_post")
    else:
        if not G.CONT_RAIL:
            add("rails", "upper_rail_open", slope_tube(f, G.POST + G.XL - G.B0, G.BAL_S - G.B0, ztop, RD2, -1.75, -0.25, G.RAIL_T))
        if G.WALL_RAIL:
            add("rails", "upper_rail_wall", slope_tube(f, 0.0, G.UU - G.NOSE, ztop, RD2, G.WN + G.GAP - 3.0, G.WN + G.GAP - 1.5, G.RAIL_T))

XL, ZP, FL, TT, TK = G.XL, G.ZP, G.FL, G.TTD, G.TK      # round 8: the platform decks keep 1.44 oak whatever the treads are
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
if G.MONO:                                         # round 11b: 1/4-20 button heads up through the frame's top wall into brass inserts in the oak
    for a_, b_ in G.DECK_SCREWS["landing"]:
        bolt(a_, b_, ZP - TT - FTL, "z", -1, d=0.5, h=0.15, role=("button head screw into an insert", 0.25, 1.0, 1.0))
add("posts", "corner_newel", post_box(XL, XL + G.POST, XL, XL + G.POST, 0.0) if G.CONT_RAIL else tube(XL, XL + G.POST, XL, XL + G.POST, G.RB_T if G.MONO else 0.0, G.NEWEL_TOP, "z", G.POST_T))
if G.MONO:                                         # round 12: the one piece rail post base
    rail_post_base("corner_newel")
for z_ in (ZP - TK + 0.8, ZP - TT - 0.8):          # corner newel lapped onto the landing's west beam
    bolt(XL + G.POST, XL + 1, z_, "a")
    nut(XL - 2, XL + 1, z_, "a", -1)
# balcony
bz = (FL - TK, FL - TT)
if G.MONO:
    # Round 10 (Maxwell 11/24/2026): the balcony grows out to its rail lines (north to the outer face of the north posts, west to the outer
    # face of the west posts). The posts stand at its corners. The north east post is the north knee frame's wall post run up in one piece;
    # the ledger and north arm stop against it on clip angles. The two west posts reach 4 1/2 in below the frame and are held by a corner
    # plate on their inside face: a band along the end beam's inside face, folded under the beam and bolted up through it (nuts under the
    # oak), and a leg down the post with two through bolts. Nothing is on the stair side of the south beam any more.
    BN_ = G.BAL_N
    add("balcony", "balcony_ledger", tube(0, 2, G.BAL_S, BN_ - G.POST, *bz, "b", FTB))
    add("balcony", "balcony_south_beam", tube(2, XL, G.BAL_S, G.BAL_S + 2, *bz, "a", FTB))
    add("balcony", "balcony_head_arm", tube(2, XL if G.NO_WEST_BEAM else XL - 2, G.B_BH - 1, G.B_BH + 1, *bz, "a", FTB))   # round 11b: to the west edge
    add("balcony", "balcony_north_arm", tube(2, XL, BN_ - 2, BN_, *bz, "a", FTB))
    if not G.NO_WEST_BEAM:
        add("balcony", "balcony_west_beam", tube(XL - 2, XL, G.BAL_S + 2 + G.CP_T, BN_ - 2 - G.CP_T, *bz, "b", FTB))
    deck = box(0, G.BAL_W, G.BAL_S, BN_, FL - TT, FL)
    for a0_, b0_ in ((XL, G.BAL_S), (XL, BN_ - G.POST), (0.0, BN_ - G.POST)):     # notched round the three corner posts
        deck = deck.cut(box(a0_ - 0.02, a0_ + G.POST + 0.02, b0_ - 0.02, b0_ + G.POST + 0.02, FL - TT - 1, FL + 1))
    for a_, b_ in [(x_, G.BAL_S + 1 if sg_ < 0 else BN_ - 1) for sg_ in (-1, 1) for x_ in G.corner_plate(sg_)[3]]:   # round 11b: counterbores for the corner plate bolts' nuts
        deck = deck.cut(cq.Solid.makeCylinder(0.45, 0.5, W(a_, b_, FL - TT - 0.01), cq.Vector(0, 0, 1)))
    add("balcony", "balcony_deck", deck, OAK, "oak")
    for a_, b_ in G.DECK_SCREWS["balcony"]:
        bolt(a_, b_, FL - TT - FTB, "z", -1, d=0.5, h=0.15, role=("button head screw into an insert", 0.25, 1.0, 1.0))
    for nm, sg in (("sw", -1), ("nw", 1)):
        out_, (fa0, fa1, fw), pbolts, fbolts = G.corner_plate(sg)
        b0_, b1_ = (G.BAL_S + 2, G.BAL_S + 2 + G.CP_T) if sg < 0 else (BN_ - 2 - G.CP_T, BN_ - 2)
        bf0, bf1 = (b0_ - fw + G.CP_T, b1_) if sg < 0 else (b0_, b1_ + fw - G.CP_T)          # flange under the beam
        pl = aprism(out_, b0_, b1_).fuse(box(fa0, fa1, bf0, bf1, FL - TK - G.CP_T, FL - TK))
        add("posts", f"corner_plate_{nm}", pl)
        bm_ = G.BAL_S + 1 if sg < 0 else BN_ - 1                                # beam centreline
        for a_ in fbolts:                                                     # up through the flange and the beam, nut in a counterbore under the oak
            bolt(a_, bm_, FL - TK - G.CP_T, "z", -1); nut(a_, bm_, FL - TT, "z", 1, d=0.5)
        po_, pi_ = (G.BAL_S, b1_) if sg < 0 else (BN_ + BT, b0_)                 # post's outer face (north west: on the brace gusset), plate's open face
        for a_, z_ in pbolts:
            bolt(a_, po_, z_, "b", sg); nut(a_, pi_, z_, "b", -sg)
    for nm, lw, le, (bh_, bn_), (eh_, en_) in G.frame_clips():                 # round 11: clip angles hold the west beam's ends and the head arm
        add("balcony", f"west_beam_clip_{nm}", box(*lw).fuse(box(*le)))
        bolt(*bh_, "a", -1); nut(*bn_, "a", 1)
        sg_ = 1 if eh_[1] < en_[1] else -1
        bolt(*eh_, "b", -sg_); nut(*en_, "b", sg_)
else:
    add("balcony", "balcony_ledger", tube(0, 2, G.BAL_S, G.BAL_N, *bz, "b", FTB))
    add("balcony", "balcony_south_beam", tube(2, XL - 2, G.BAL_S, G.BAL_S + 2, *bz, "a", FTB))
    add("balcony", "balcony_head_arm", tube(2, XL - 2, G.B_BH - 1, G.B_BH + 1, *bz, "a", FTB))
    add("balcony", "balcony_north_arm", tube(2, XL, G.BAL_N - 2, G.BAL_N, *bz, "a", FTB))
    add("balcony", "balcony_west_beam", tube(XL - 2, XL, G.BAL_S, G.BAL_N - 2, *bz, "b", FTB))
    deck = box(0, XL, G.BAL_S, G.BAL_N, FL - TT, FL)
    add("balcony", "balcony_deck", deck.fuse(box(G.GAP, XL, G.BAL_S - G.NOSE, G.BAL_S, FL - TT, FL)) if G.NOSE else deck, OAK, "oak")
zu, r2 = FL - TK, G.POST / math.sqrt(2) * 1.0
if not G.MONO:
    for nm, b in (("south", G.B_BH), ("north", G.BAL_N - 1)):
        c_ = G.A_BR + 1
        add("balcony", f"knee_brace_{nm}", aprism([(c_ + r2, zu), (c_ - r2, zu), (0, zu - c_ + r2), (0, zu - c_ - r2)], b - 1, b + 1))
for nm, b, sd in (G.knee_frames() if G.MONO else ()):         # round 7: each brace closes a triangle with a post down the wall, gusset at every joint
    c_, zb_ = G.A_BR, G.KB_BOT
    add("balcony", f"knee_brace_{nm}", aprism([(c_ + r2, zu), (c_ - r2, zu), (2.0, zb_ + r2), (2.0, zb_ - r2)], b - 1, b + 1))
    pa0, pa1, pz0, pz1 = G.KB_POST
    add("balcony", f"knee_post_{nm}", tube(pa0, pa1, b - 1, b + 1, pz0, pz1, "z", G.POST_T)
        .cut(aprism([(pa0 - 0.1, G.KB_MITER - 0.1), (pa1 + 0.1, G.KB_MITER + pa1 - pa0 + 0.1), (pa1 + 0.1, pz0 - 1), (pa0 - 0.1, pz0 - 1)], b - 1.5, b + 1.5)))   # round 10: 45 degree foot, flush with the brace
    gb0, gb1 = (b + 1, b + 1 + BT) if sd > 0 else (b - 1 - BT, b - 1)
    fo_, fi_ = (gb1, b - 1) if sd > 0 else (gb0, b + 1)                   # gusset's open face, the tube's far face
    for j_ in ("top", "foot", "corner"):
        add("balcony", f"knee_gusset_{j_}_{nm}", aprism(G.gusset(j_), gb0, gb1))
        for a_, z_ in G.KG[j_]:
            if G.MONO and not G.NO_WEST_BEAM and j_ == "top" and abs(a_ - (G.A_BR - 1.75)) < 1e-6:
                continue                                                   # round 11: this one is the head arm clip's bolt, drawn with the clip
            bolt(a_, fo_, z_, "b", sd); nut(a_, fi_, z_, "b", -sd)              # through the plate and the tube, crush sleeve inside
    for z_ in G.KB_LAGS:                                                   # two lags through the post into the wall framing
        nut(pa1, b, z_, "a", 1)
if G.MONO:                                         # round 10: north knee frame, wall post = north east guard post, brace up to the north west post
    BN_ = G.BAL_N
    b = BN_ - 1
    add("balcony", "knee_brace_north", aprism([(G.A_BR + r2, zu - G.CP_T), (G.A_BR - r2, zu - G.CP_T), (2.0, G.NK_ZB + r2), (2.0, G.NK_ZB - r2)], b - 1, b + 1))   # round 11: same part as the south brace
    gb0, gb1 = BN_, BN_ + BT                                               # gussets on the north face
    for j_ in ("top", "foot"):
        add("balcony", f"knee_gusset_{j_}_north", aprism(G.nk_gusset(j_), gb0, gb1))
        for a_, z_ in G.NKG[j_]:
            if j_ == "top" and a_ > XL:
                continue                                                   # the north west post's two bolts are drawn with its corner plate
            bolt(a_, gb1, z_, "b", 1); nut(a_, b - 1, z_, "b", -1)
    for z_ in G.NK_LAGS:
        nut(G.POST, b, z_, "a", 1)
# balcony newel, guard posts, rails, pickets
if G.MONO:
    # Round 10: the three corner posts. The south west newel and the north west post reach CP_DROP below the frame on their corner plates;
    # the north east post runs from its 45 degree foot at the north knee brace up to the guard rail (one piece, lagged to the wall).
    PN = (G.BAL_N - G.POST, G.BAL_N)
    zl_ = FL - TK - G.CP_DROP
    if G.CONT_RAIL:
        add("posts", "balcony_sw_newel", post_box(XL, XL + G.POST, G.BAL_S, G.BAL_S + G.POST, zl_))
        add("posts", "guard_post_nw", post_box(XL, XL + G.POST, *PN, zl_))
    else:                                          # straight rails (Maxwell 11/24/2026): flat topped posts, level guard top rails over them
        add("posts", "balcony_sw_newel", tube(XL, XL + G.POST, G.BAL_S, G.BAL_S + G.POST, zl_, G.GSW_TOP, "z", G.POST_T))
        add("posts", "guard_post_nw", tube(XL, XL + G.POST, *PN, zl_, G.G_TOP - G.RAIL, "z", G.POST_T))
    pz0_ = G.NK_MITER
    ne_ = post_box(0, G.POST, *PN, pz0_) if G.CONT_RAIL else tube(0, G.POST, *PN, pz0_, G.G_TOP - G.RAIL, "z", G.POST_T)
    add("posts", "guard_post_ne", ne_.cut(aprism([(-0.1, pz0_ - 0.1), (G.POST + 0.1, pz0_ + G.POST + 0.1), (G.POST + 0.1, pz0_ - 1), (-0.1, pz0_ - 1)], PN[0] - 0.5, PN[1] + 0.5)))
    if G.CONT_RAIL:
        add("rails", "handrail_and_guard_rail", rail_sweep(), mat="rail")
    else:
        for nm_, a0_, a1_, b0_, b1_, *_ in G.straight_rails()[2:]:       # the two open side rails are added with their flights
            add("rails", nm_, tube(a0_, a1_, b0_, b1_, G.G_TOP - G.RAIL, G.G_TOP, "a" if "north" in nm_ else "b", G.RAIL_T))
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
    add("posts", "balcony_sw_newel", tube(XL, XL + G.POST, G.BAL_S, G.BAL_S + G.POST, gsw_z0, G.GSW_TOP, "z", G.POST_T))
    add("posts", "guard_post_nw", tube(XL - G.POST, XL, G.BAL_N, G.BAL_N + G.POST, FL - TK, G.G_TOP - G.RAIL, "z", G.POST_T))
    add("posts", "guard_post_ne", tube(0, G.POST, G.BAL_N, G.BAL_N + G.POST, FL - 13, G.G_TOP - G.RAIL, "z", G.POST_T))
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
if G.MONO and not G.CONT_RAIL and G.RAIL_STYLE == "hidden":   # round 13 option A: a tongue plate inside the rail and the post at every joint
    from shapely.geometry import MultiPoint as _MP, Point as _Pt
    from shapely.ops import unary_union as _uu
    _bbo = lambda p, q: p.xmin < q.xmax and q.xmin < p.xmax and p.ymin < q.ymax and q.ymin < p.ymax and p.zmin < q.zmax and q.zmin < p.zmax
    for nm, ax, pc, RB, PB, K in G.hidden_joints():
        i_ = 0 if ax == "a" else 1
        k_ = [j for j in range(3) if j != i_]                                # in plane coordinates: (the other plan axis, z)
        q2 = lambda q, r: _Pt(q[k_[0]], q[2]).buffer(r, 24)
        hull = _uu([_uu([q2(q, G.TG_R) for q in RB + [K]]).convex_hull, _uu([q2(q, G.TG_RP) for q in PB] + [q2(K, G.TG_RP)]).convex_hull])
        loop = [W(*((pc - G.TG_T / 2, x, z) if ax == "a" else (x, pc - G.TG_T / 2, z))) for x, z in list(hull.exterior.coords)[:-1]]
        dv = cq.Vector(-G.TG_T, 0, 0) if ax == "a" else cq.Vector(0, G.TG_T, 0)
        tg = cq.Solid.extrudeLinear(cq.Face.makeFromWires(cq.Wire.makePolygon(loop, close=True)), dv)
        for j, (g_, n_, s_, *r_) in enumerate(PARTS):                         # slot the rail and the post where the tongue passes their walls
            if g_ in ("rails", "posts", "guard") and not n_.startswith("picket") and _bbo(s_.BoundingBox(), tg.BoundingBox()):
                c_ = s_.cut(tg)
                if abs(c_.Volume() - s_.Volume()) > 1e-6:
                    PARTS[j] = (g_, n_, c_, *r_)
        add("rails", f"rail_tongue_{nm}", tg)
        for P, half in [(q, G.RAIL / 2) for q in RB] + [(q, G.POST / 2) for q in PB]:
            hd, nt = list(P), list(P)
            hd[i_], nt[i_] = pc + half, pc - half
            bolt(*hd, ax, 1, d=0.5, h=0.15); nut(*nt, ax, -1, d=0.5)
if G.MONO and not G.CONT_RAIL and G.RAIL_STYLE == "straps":   # round 11b: a strap at every rail end or post crossing (one rail bolt + spacer, two post bolts)
    for nm, R, P1, P2, t, side, plane, pat in G.rail_straps():
        ax, i_ = side[0], (0 if side[0] == "a" else 1)
        pts = G.strap_outline(R, P2, t, side, plane)
        dv = cq.Vector(-G.ST_T, 0, 0) if ax == "a" else cq.Vector(0, G.ST_T, 0)
        add("rails", f"rail_strap_{nm}", cq.Solid.extrudeLinear(cq.Face.makeFromWires(cq.Wire.makePolygon([W(*p) for p in pts], close=True)), dv))
        rc = R[i_]                                                             # rail centre on the side axis
        sp_ = list(R); sp_[i_] = rc + G.RAIL / 2
        add("rails", f"rail_spacer_{nm}", cq.Solid.makeCylinder(0.25, G.SP_T, W(*sp_), cq.Vector(-1, 0, 0) if ax == "a" else cq.Vector(0, 1, 0)))
        for P, far in ((R, rc - G.RAIL / 2), (P1, P1[i_] - (plane - P1[i_])), (P2, P2[i_] - (plane - P2[i_]))):
            hd, nt = list(P), list(P)
            hd[i_], nt[i_] = plane + G.ST_T, (plane - G.POST) if P is not R else far
            bolt(*hd, ax, 1, d=0.5, h=0.15); nut(*nt, ax, -1, d=0.5)
if G.MONO and not G.CONT_RAIL and G.RAIL_STYLE == "pipe":     # round 13 option B: round pipe posts and rails, slip on kit fittings
    RP_, RR_ = G.PIPE_POST[0] / 2, G.PIPE_RAIL[0] / 2
    def _cyl(p0, p1, r):
        v = cq.Vector(*W(*p1).toTuple()) - W(*p0)
        return cq.Solid.makeCylinder(r, v.Length, W(*p0), v.normalized())
    def _pipe(p0, p1, od, wall):
        return _cyl(p0, p1, od / 2).cut(_cyl(p0, p1, od / 2 - wall))
    names = {n_: j for j, (g_, n_, *_r) in enumerate(PARTS)}
    RAILC = {}                                                                 # rail centreline ends
    sr = {r[0]: r for r in G.straight_rails()}
    for rn in ("lower_rail_open", "upper_rail_open", "guard_west_top_rail", "guard_north_top_rail", "guard_west_bottom_rail", "guard_north_bottom_rail"):
        g_, n_, s_, *r_ = PARTS[names[rn]]
        bb = s_.BoundingBox()
        a0_, a1_, b0_, b1_ = -bb.xmax, -bb.xmin, bb.ymin, bb.ymax
        if rn in sr:
            _, ra0, ra1, rb0, rb1, z0_, z1_, ax_ = sr[rn]
            L_ = (ra1 - ra0) if ax_ == "a" else (rb1 - rb0)
            dep = G.RAIL * math.sqrt(1 + ((z1_ - z0_) / L_) ** 2)
            if ax_ == "a":
                e0, e1 = (ra0, (rb0 + rb1) / 2, z0_ - dep / 2), (ra1, (rb0 + rb1) / 2, z1_ - dep / 2)
            else:
                e0, e1 = ((ra0 + ra1) / 2, rb0, z0_ - dep / 2), ((ra0 + ra1) / 2, rb1, z1_ - dep / 2)
        else:                                                                  # level bottom rails: from the bounding box
            zc = (bb.zmin + bb.zmax) / 2
            if "north" in rn:
                e0, e1 = (a0_, (b0_ + b1_) / 2, zc), (a1_, (b0_ + b1_) / 2, zc)
            else:
                e0, e1 = ((a0_ + a1_) / 2, b0_, zc), ((a0_ + a1_) / 2, b1_, zc)
        RAILC[rn] = (e0, e1)
        RAILC[rn] = (e0, e1)
    OVER_ = dict(foot_post="lower_rail_open", guard_post_nw="guard_west_top_rail", guard_post_ne="guard_north_top_rail")
    POSTC = {}                                                                 # post centre (a, b) and z range
    for pn in G.RAIL_POSTS:
        g_, n_, s_, *r_ = PARTS[names[pn]]
        bb = s_.BoundingBox()
        ac, bc = -(bb.xmin + bb.xmax) / 2, (bb.ymin + bb.ymax) / 2
        z1 = bb.zmax
        if pn in OVER_:                                                        # the rail runs over this post: its top stops under the rail
            e0, e1 = RAILC[OVER_[pn]]
            f_ = ((ac - e0[0]) / (e1[0] - e0[0])) if abs(e1[0] - e0[0]) > 1e-6 else ((bc - e0[1]) / (e1[1] - e0[1]))
            z1 = e0[2] + f_ * (e1[2] - e0[2]) - RR_ / math.sqrt(1 - ((e1[2] - e0[2]) / math.dist(e0, e1)) ** 2)
        POSTC[pn] = (ac, bc, bb.zmin, z1)
        PARTS[names[pn]] = (g_, n_, _pipe((ac, bc, bb.zmin), (ac, bc, z1), *G.PIPE_POST), *r_)
    SOLIDP = [_cyl((a, b, z0), (a, b, z1), RP_) for a, b, z0, z1 in POSTC.values()]
    for rn, (e0, e1) in RAILC.items():                                         # rails stop at the round posts
        g_, n_, s_, *r_ = PARTS[names[rn]]
        rp_ = _pipe(e0, e1, *G.PIPE_RAIL)
        for x in SOLIDP:
            if _bbo2(x.BoundingBox(), rp_.BoundingBox()):
                rp_ = rp_.cut(x)
        PARTS[names[rn]] = (g_, n_, rp_, *r_)
    SOLIDR = [_cyl(e0, e1, RR_) for e0, e1 in RAILC.values()]
    def _near_post(p):
        return min(POSTC.items(), key=lambda kv: math.hypot(kv[1][0] - p[0], kv[1][1] - p[1]))
    def _rail_at(p):
        best = None
        for rn, (e0, e1) in RAILC.items():
            d = [q - p_ for q, p_ in zip(e1, e0)]; L = math.sqrt(sum(x * x for x in d)); u = [x / L for x in d]
            s_ = max(0.0, min(L, sum((p[i] - e0[i]) * u[i] for i in range(3))))
            c = [e0[i] + s_ * u[i] for i in range(3)]
            dist = math.dist(c, p)
            if best is None or dist < best[0]:
                best = (dist, rn, c, u, s_, L)
        return best
    FIT = {}                                                                   # post name -> list of fitting solids (joined per post)
    for nm, R, P1, P2, t, side, plane, pat in G.rail_straps():
        pn, (pa, pb, pz0, pz1) = _near_post(P1)
        dist, rn, c, u, s_, L = _rail_at(R)
        over = pat == "foot" or nm in ("guard_top_west_nw", "guard_top_north_ne")
        shapes = []
        if over:                                                               # rail over the post top: a socket on the post top and a sleeve round the rail
            zt = pz1
            shapes.append(_cyl((pa, pb, zt - G.PS_H), (pa, pb, zt), G.PS_D / 2))
            cc = _rail_at((pa, pb, zt + RR_))[2]
            shapes.append(_cyl([cc[i] - u[i] * G.RS_L / 2 for i in range(3)], [cc[i] + u[i] * G.RS_L / 2 for i in range(3)], G.RS_D / 2))
            ss = [("post", (pa, pb, zt - G.PS_H / 2)), ("rail", cc)]
        else:                                                                  # rail end on the post's side: a collar round the post and a socket on the rail end
            end = RAILC[rn][0] if s_ < L / 2 else RAILC[rn][1]
            ui = [-x for x in u] if s_ < L / 2 else u                          # from the rail end toward the post
            ce = [end[i] - ui[i] * 0.0 for i in range(3)]
            shapes.append(_cyl([ce[i] - ui[i] * G.RS_L for i in range(3)], [ce[i] + ui[i] * 0.6 for i in range(3)], G.RS_D / 2))
            ss = [("rail", [ce[i] - ui[i] * G.RS_L / 2 for i in range(3)])]
            if nm != "guard_top_north_nw":                                     # (the north top rail ends on the west rail's sleeve over the corner post)
                shapes.insert(0, _cyl((pa, pb, ce[2] - G.PC_H / 2), (pa, pb, ce[2] + G.PC_H / 2), G.PS_D / 2))
                ss.insert(0, ("post", (pa, pb, ce[2])))
        sol = shapes[0]
        for x in shapes[1:]:
            sol = sol.fuse(x)
        FIT.setdefault(pn, []).append((nm, sol, ss, u))
    for pn, fl in FIT.items():
        sol = fl[0][1]
        for _, x, _, _ in fl[1:]:
            sol = sol.fuse(x)
        for x in SOLIDP + SOLIDR:
            if _bbo2(x.BoundingBox(), sol.BoundingBox()):
                sol = sol.cut(x)
        add("rails", f"rail_fitting_{pn}", sol.clean())
        pa, pb = POSTC[pn][:2]
        done = set()
        for nm, _, ss, u in fl:
            for what, p in ss:
                key = (what, round(p[2], 1)) if what == "post" else (what, nm)
                if key in done:
                    continue
                done.add(key)
                if what == "post":                                             # two set screws through the collar into the post, on the side away from the rails
                    for sg in (1, -1):
                        bolt(pa, pb + sg * G.PS_D / 2, p[2], "b", sg, d=0.35, h=0.06, role=("set screw", 0.375, 0.5, 0.5))
                else:                                                          # two set screws in through the rail socket's side into the rail
                    sax = "b" if abs(u[0]) > abs(u[1]) else "a"
                    for k in (-0.5, 0.5):
                        q = [p[i] + k * u[i] for i in range(3)]
                        q[0 if sax == "a" else 1] += G.RS_D / 2
                        bolt(*q, sax, 1, d=0.35, h=0.06, role=("set screw", 0.375, 0.5, 0.5))
# context: slab and the two walls (reference only)
CTX = [("slab", box(-5, 60, -5, 100, -1, 0)), ("bath_1_wall", box(-4.5, 0, -4.5, 100, 0, FL)), ("clerestory_wall", box(0, 60, -4.5, 0, 0, 170))]

def build_bolts():
    """round 11b (Maxwell 11/25/2026: model each bolt whole): pair every bolt head with the nut on its line, and give it a shank: the plain
    (unthreaded) part from the head and the threaded part to the tip, with standard lengths. Heads or nuts with no partner are lags, anchors
    or screws, sized by what they are. Writes loft_ships_ladder_bolts.json, a bolt schedule."""
    NUT_H = {0.375: 0.33, 0.3125: 0.27, 0.25: 0.22, 0.19: 0.17}
    PITCH = {0.375: 1 / 16, 0.25: 1 / 20, 0.19: 1 / 24}
    dia = lambda r: 0.375 if r["d"] >= 0.6 else (0.25 if r["d"] >= 0.45 else 0.19)
    ab = lambda v: (round(-v.x, 2), round(v.y, 2), round(v.z, 2))
    seen = {}
    for i, r in enumerate(HEADS):                     # the same head drawn twice is a CAD slip: report it, use one
        k = (round(r["o"].x, 2), round(r["o"].y, 2), round(r["o"].z, 2), round(r["dv"].x, 2), round(r["dv"].y, 2), round(r["dv"].z, 2))
        seen.setdefault(k, []).append(i)
    dup = [k[:3] for k, v in seen.items() if len(v) > 1]
    if dup:
        print("fasteners drawn twice (one used):", [(-x, y, z) for x, y, z in dup])
    used, out = {i for v in seen.values() for i in v[1:]}, []
    heads = [i for i, r in enumerate(HEADS) if r["kind"] == "socket"]
    nuts = [i for i, r in enumerate(HEADS) if r["kind"] == "hex"]
    for i in heads:                                   # through bolts: a head and a nut facing away from each other on one line
        r = HEADS[i]
        best = None
        for j in nuts:
            if j in used:
                continue
            q = HEADS[j]
            t = (q["o"] - r["o"]).dot(r["dv"] * -1)
            if 0.05 < t < 14 and ((q["o"] - r["o"]) + r["dv"] * t).Length < 0.12 and q["dv"].dot(r["dv"]) < -0.9 and (best is None or t < best[0]):
                best = (t, j)
        if best:
            used.add(best[1]); used.add(i)
            D = dia(r)
            grip = best[0]
            L = math.ceil((grip + NUT_H[D] + 2 * PITCH[D]) * 4 - 1e-6) / 4
            lt = 2 * D + 0.5                          # socket head cap screw thread length (2D + 1/2); shorter ones are threaded full length
            thr = L if L - lt < 0.5 else lt
            out.append(dict(kind="through bolt", dia=D, length=L, grip=round(grip, 3), thread=round(thr, 3),
                            threads_in_grip=round(max(0.0, thr - (L - grip)), 3), head=ab(r["o"]), axis=ab(r["dv"] * -1 + cq.Vector(0, 0, 0)), r=r))
    for i, r in enumerate(HEADS):                     # the rest: lags, anchors, screws
        if i in used:
            continue
        D = dia(r)
        up = r["dv"].z > 0.9
        wall = r["dv"].x < -0.9 and -r["o"].x <= 2.6     # a hex head on a wall side face pointing west: a lag into the wall
        if r["role"] == "fhs":                        # flat head screw up through a countersunk plate: from the plate's underside
            L, kind = math.ceil((r["o"].z + NUT_H[D] + 2 * PITCH[D]) * 4 - 1e-6) / 4, "flat head screw"
            out.append(dict(kind=kind, dia=D, length=L, grip=round(r["o"].z, 3), thread=L, threads_in_grip=round(r["o"].z, 3), head=ab(r["o"]), r=r, tip_up=True))
            continue
        if isinstance(r["role"], tuple):              # (kind, dia, length, thread) given where it is drawn
            kind, D, L, thr = r["role"]
            out.append(dict(kind=kind, dia=D, length=L, grip=None, thread=thr, threads_in_grip=None, head=ab(r["o"]), r=r))
            continue
        if r["kind"] == "hex" and up and r["o"].z < 2.0:
            L, kind, thr = 3.0, "wedge anchor", 1.75
        elif r["kind"] == "hex" and wall:
            L, kind, thr = 5.0, "lag screw", 3.0
        elif r["kind"] == "hex":
            L, kind, thr = 2.5, "lag screw", 1.5
        else:
            L, kind, thr = (0.75, "wood screw", 0.75) if D < 0.3 else (1.5, "lag screw", 1.0)
        out.append(dict(kind=kind, dia=D, length=L, grip=None, thread=thr, threads_in_grip=None, head=ab(r["o"]), r=r))
    for e in out:
        r, D, L, thr = e.pop("r"), e["dia"], e["length"], e["thread"]
        if e.pop("tip_up", False):                    # flat head screw: tip up through the nut, head flush with the plate's underside
            base = cq.Vector(r["o"].x, r["o"].y, 0.0)
            BOLT_LINES.append((base, base + cq.Vector(0, 0, L), e["kind"]))
            SHANKS.append((cq.Solid.makeCylinder(D / 2 * 0.92, L, base, cq.Vector(0, 0, 1)), True))
            continue
        if e["kind"] == "wedge anchor":               # the stud sticks up through the nut; the rest is in the slab
            top = r["o"] + r["dv"] * (NUT_H[D] + 2 * PITCH[D])
            BOLT_LINES.append((top, top + cq.Vector(0, 0, -L), e["kind"]))
            SHANKS.append((cq.Solid.makeCylinder(D / 2 * 0.92, thr, top, cq.Vector(0, 0, -1)), True))
            SHANKS.append((cq.Solid.makeCylinder(D / 2, L - thr, top + cq.Vector(0, 0, -thr), cq.Vector(0, 0, -1)), False))
            continue
        ax = r["dv"] * -1                             # from the head bearing face into the joint
        plain = L - thr
        BOLT_LINES.append((r["o"], r["o"] + ax * L, e["kind"]))
        if plain > 1e-3:
            SHANKS.append((cq.Solid.makeCylinder(D / 2, plain, r["o"], ax), False))
        SHANKS.append((cq.Solid.makeCylinder(D / 2 * 0.92, thr, r["o"] + ax * plain, ax), True))
    # bolts that run into each other
    cross = []
    sh = [s_ for s_, _ in SHANKS]
    bbs = [s_.BoundingBox() for s_ in sh]
    for i in range(len(sh)):
        for j in range(i + 1, len(sh)):
            bi, bj = bbs[i], bbs[j]
            if bi.xmax < bj.xmin or bj.xmax < bi.xmin or bi.ymax < bj.ymin or bj.ymax < bi.ymin or bi.zmax < bj.zmin or bj.zmax < bi.zmin:
                continue
            try:
                v = sh[i].intersect(sh[j]).Volume()
            except Exception:
                v = 0
            if v > 1e-3:
                c_ = sh[i].Center()
                cross.append((round(-c_.x, 2), round(c_.y, 2), round(c_.z, 2)))
    cross = sorted(set(cross))
    json.dump(dict(bolts=out, crossing=cross), open(os.path.join(OUT, "loft_ships_ladder_bolts.json"), "w"), indent=1)
    from collections import Counter
    cnt = Counter((e["kind"], e["dia"], e["length"]) for e in out)
    print("bolts:", len(out), "; by size:", ", ".join(f"{n} x {k} {d} x {l}" for (k, d, l), n in sorted(cnt.items())))
    print("bolts that cross another bolt:", cross if cross else "none")
    return out


if G.MONO:
    BOLTS = build_bolts()
assy, ctx = cq.Assembly(name="loft_ships_ladder"), cq.Assembly(name="context")
groups = {}
for group, name, solid, colour, mat in PARTS:
    groups.setdefault(group, cq.Assembly(name=group)).add(solid, name=name, color=cq.Color(*colour, 1.0))
for g_, a_ in groups.items():
    assy.add(a_)
fa_ = cq.Assembly(name="fasteners")
for i, s_ in enumerate(FAST):
    fa_.add(s_, name=f"fastener_{i}", color=cq.Color(0.55, 0.6, 0.9, 1.0))
for i, (s_, thr_) in enumerate(SHANKS):              # round 11b: whole bolts, threaded length in a lighter colour
    fa_.add(s_, name=f"{'thread' if thr_ else 'shank'}_{i}", color=cq.Color(*((0.85, 0.75, 0.45) if thr_ else (0.45, 0.5, 0.75)), 1.0))
assy.add(fa_)
assy.save(os.path.join(OUT, "loft_ships_ladder.step"))
for nm, s in CTX:
    ctx.add(s, name=nm, color=cq.Color(0.86, 0.86, 0.84, 1.0))
full = cq.Assembly(name="view")
full.add(assy); full.add(ctx)
full.save(os.path.join(OUT, "loft_ships_ladder_view.glb"), tolerance=0.01, angularTolerance=0.2)

DENS = dict(steel=0.2836, oak=0.027, rail=0.2836 * (1 - (1 - 2 * G.RAIL_T / G.RAIL) ** 2))   # the swept rail is drawn solid: weigh it as a tube of its wall
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
# round 11b: a bolt head, nut or shank buried in a part it should only touch or pass through a drilled hole of
bur = []
for nm_, so_ in [(n, s_) for g_, n, s_, c, m_ in PARTS]:
    bo_ = so_.BoundingBox()
    for f_ in FAST:
        bf_ = f_.BoundingBox()
        if bo_.xmax < bf_.xmin or bf_.xmax < bo_.xmin or bo_.ymax < bf_.ymin or bf_.ymax < bo_.ymin or bo_.zmax < bf_.zmin or bf_.zmax < bo_.zmin:
            continue
        try:
            v_ = so_.intersect(f_).Volume()
        except Exception:
            v_ = 0
        if v_ > 0.005:
            c_ = f_.Center()
            bur.append((nm_, (round(-c_.x, 2), round(c_.y, 2), round(c_.z, 2)), round(v_, 3)))
print("heads or nuts buried in a part:", bur if bur else "none")
