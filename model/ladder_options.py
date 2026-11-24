# Loft ladder options (11/21/2026 mockups), run by make_house.py inside its loft block when [loft] ladder_design is not
# "code". Every option keeps the foot at or east of the living room opening's east jamb. Local frame of a flight:
# u along the climb (0 = first nosing), v across it, z up.
STOW = bool(os.environ.get("LADDER_STOWED") or LOFT.get("ladder_stowed"))
DOOR_X = max(p_[1] for p_ in C["clerestory"]["passages"] if p_[0] < lx0 + 2 < p_[1] + 6 and p_[1] < EDGE_X - 2)   # east jamb of the living room opening


def lad_T(ox, oy, d):
    dx, dy = d
    px, py = -dy, dx
    return lambda u, v, z: (ox + u * dx + v * px, oy + u * dy + v * py, z)


def lhx(mat, T, pts, R=None):
    if R:
        pts = [R(*p_) for p_ in pts]
    hexa(mat, [T(*p_) for p_ in pts])


def lbx(mat, T, u0, u1, v0, v1, z0, z1, R=None):
    lhx(mat, T, [(u0, v0, z0), (u1, v0, z0), (u1, v1, z0), (u0, v1, z0), (u0, v0, z1), (u1, v0, z1), (u1, v1, z1), (u0, v1, z1)], R)


def rot_uz(uc, zc, deg):
    c_, s_ = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return lambda u, v, z: (uc + (u - uc) * c_ - (z - zc) * s_, v, zc + (u - uc) * s_ + (z - zc) * c_)


def flight(T, z0, nr, ri, go, td, w, treads=None, u_lo=-0.04, u_hi=None, leg=False, R=None, top_nosing=True, rail=None, posts=None,
           alt=False, sdepth=1.0, stringers=True, rail_v=None, tread_v=None, top_td=None, smat="White Oak", carriage=False, tuck=0.4):
    """One straight flight. Nosing k is at u = (k - 1) * go, z0 + k * ri; nosing nr is the landing edge, td - go proud of u_end."""
    top_td = TD - GO if top_td is None else top_td
    u_end = (nr - 1) * go + top_td
    u_hi = u_end - 0.01 if u_hi is None else u_hi
    sl = ri / go
    zn = lambda u: z0 + ri + u * sl
    zt = lambda u: min(zn(u) + 0.1, z0 + nr * ri - 0.01)
    zb = lambda u: max(z0, zn(u) + 0.1 - sdepth)
    # carriage (Maxwell 11/21/2026): the wall side stringer (v = w - SW) runs under the treads, its top touching each tread's back, so the
    # treads reach the wall; the open side stringer (v = 0) rides high beside the treads, only deep enough to catch their backs, to keep headroom below
    zt_w = lambda u: max(z0 + 0.35, min(zn(u) - td * sl - 0.12, z0 + nr * ri - 0.13))    # never thinner than a 4 in shoe at the foot
    zb_w = lambda u: max(z0 + 0.004, zn(u) - td * sl - 0.12 - (1.2 if SW < 0.08 else 1.6))   # plumb depth: 2x10 class board (about 9 1/4 in square to the slope) or a 7 in plate
    zb_o = lambda u: max(z0 + 0.004, zn(u) - td * sl - 0.12 - 0.1)
    tv = tread_v or ((SW + 0.005, w - 0.005) if carriage == "under" else (0.005, w - 0.005) if carriage == "tube" else (SW + 0.005, w - SW - 0.005))
    if carriage == "tube":
        # Stock rectangular tube stringers under the treads (Maxwell 11/21/2026): top face on the line through the tread backs. Each tread sits on two
        # laser cut 1/4 in brackets: a web bolted to the tube's inner face behind the back edge of the tread below, with a bent seat under the tread.
        TW, TDp = LOFT.get("ladder_tube_in", [2.0, 3.0])
        TW, pl = TW / 12, TDp / 12 / math.cos(math.atan(sl))    # width, and depth measured plumb
        zl = lambda u: zn(u) - td * sl - 0.12                   # tube top
        # Both ends are level cuts: the foot stands on the floor (or on the corner landing), the head tucks under the platform above and
        # bears on its underside, `tuck` below its top. Each end is held by bolt on angles.
        foot = "floor"
        u0 = (z0 - (z0 + ri - td * sl - 0.12)) / sl
        u1 = u0 + pl / sl
        zu = z0 + nr * ri - tuck - 0.003                        # underside of the platform at the head
        u2 = (zu - (z0 + ri - td * sl - 0.12)) / sl             # tube's top edge meets the underside
        u3 = u2 + pl / sl
        nx, nz = math.sin(math.atan(sl)), -math.cos(math.atan(sl))
        fl = lambda u: max(z0 + 0.004, zl(u) - pl)
        ft = lambda u: min(zu, max(zl(u), fl(u) + 0.002))
        for va in (0.0, w - TW):
            for ua, uc in ((u0, u1), (u1, u2), (u2, u3)):
                lhx("Black Metal", T, [(ua, va, fl(ua)), (uc, va, min(fl(uc), zu - 0.002)), (uc, va, ft(uc)), (ua, va, ft(ua)),
                                       (ua, va + TW, fl(ua)), (uc, va + TW, min(fl(uc), zu - 0.002)), (uc, va + TW, ft(uc)), (ua, va + TW, ft(ua))], R)
            vi = (TW, TW + 0.25) if va == 0.0 else (w - TW - 0.25, w - TW)          # end angles, 3 x 3 x 1/4 in, on the tube's inner face
            for ua, uc, zf, sg in ((u0 + 0.05, u1 + 0.1, z0 + 0.004, 1), (u2 - 0.1, u3 - 0.05, zu, -1)):
                lbx("Black Metal", T, ua, uc, vi[0], vi[1], min(zf, zf + sg * 0.021), max(zf, zf + sg * 0.021), R)
                lbx("Black Metal", T, ua, uc, min(vi, key=lambda v_: abs(v_ - (TW if va == 0.0 else w - TW))), min(vi, key=lambda v_: abs(v_ - (TW if va == 0.0 else w - TW))) + (0.021 if va == 0.0 else -0.021), min(zf, zf + sg * 0.25), max(zf, zf + sg * 0.25), R)
            vw = (TW, TW + 0.021) if va == 0.0 else (w - TW - 0.021, w - TW)        # bracket web, 1/4 in
            vs = (TW, TW + 0.208) if va == 0.0 else (w - TW - 0.208, w - TW)        # seat, 2 1/2 in
            for k in range(1, nr):
                uk, zk = (k - 1) * go, z0 + k * ri - 0.12
                A, B = (uk + 0.3125, zk), (uk + td, zk)
                C = (A[0], zl(A[0]))
                lap = 0.1875                                                         # web laps 2 1/4 in down the tube's side
                B2, C2 = (B[0] + nx * lap, B[1] + nz * lap), (C[0] + nx * lap, C[1] + nz * lap)
                fz = lambda z: max(z, z0 + 0.01)
                lhx("Black Metal", T, [(C2[0], vw[0], fz(C2[1])), (B2[0], vw[0], B2[1]), (B[0], vw[0], B[1] - 0.021), (A[0], vw[0], A[1] - 0.021),
                                       (C2[0], vw[1], fz(C2[1])), (B2[0], vw[1], B2[1]), (B[0], vw[1], B[1] - 0.021), (A[0], vw[1], A[1] - 0.021)], R)
                lbx("Black Metal", T, uk + 0.083, uk + td, vs[0], vs[1], zk - 0.021, zk - 0.0005, R)
    for k in (treads if treads is not None else range(1, nr)):
        uk = (k - 1) * go
        v0_, v1_ = tv
        if alt:
            mid = (v0_ + v1_) / 2
            v0_, v1_ = (v0_, mid - 0.02) if k % 2 else (mid + 0.02, v1_)
        lbx("White Oak", T, uk, min(uk + td, u_end - 0.01), v0_, v1_, z0 + k * ri - 0.12, z0 + k * ri, R)
        if carriage == "side":                                # bolt on angle clips under each tread, 2 x 2 x 3/16 in, 7 in long
            for vh, vv in (((SW, SW + 0.167), (SW, SW + 0.016)), ((w - SW - 0.167, w - SW), (w - SW - 0.016, w - SW))):
                zc = z0 + k * ri - 0.12
                lbx("Black Metal", T, uk + 0.0625, uk + 0.646, vh[0], vh[1], zc - 0.016, zc - 0.0005, R)
                lbx("Black Metal", T, uk + 0.0625, uk + 0.646, vv[0], vv[1], zc - 0.167, zc - 0.016, R)
    if top_nosing:
        lbx("White Oak", T, u_end - top_td, u_end - 0.01, tv[0], tv[1], z0 + nr * ri - 0.1, z0 + nr * ri - 0.004, R)
    if stringers and carriage != "tube":
        cuts = sorted({u_lo, u_hi} | {u_ for u_ in ((z0 + sdepth - 0.1 - z0 - ri) / sl, (nr * ri - 0.01 - 0.1 - ri) / sl, u_lo + 0.3 if leg else u_lo) if u_lo < u_ < u_hi})
        for va in (0.0, w - SW):
            zt_, zb_ = (zt, zb) if not carriage else (zt, zb_o) if va == 0.0 or carriage == "side" else (zt_w, zb_w)
            cuts_ = cuts if not carriage else sorted({u_lo, u_hi} | {u_ for u_ in (go * i_ for i_ in range(nr + 2)) if u_lo < u_ < u_hi})
            for ua, uc in zip(cuts_, cuts_[1:]):
                inleg = leg and uc <= u_lo + 0.3 + 1e-9
                ba, bc = (z0, z0) if inleg else (zb_(ua), zb_(uc))
                lhx(smat, T, [(ua, va, ba), (uc, va, bc), (uc, va, zt_(uc)), (ua, va, zt_(ua)),
                                     (ua, va + SW, ba), (uc, va + SW, bc), (uc, va + SW, zt_(uc)), (ua, va + SW, zt_(ua))], R)
    if rail is not False:
        r0, r1 = rail or (0.0, u_end - top_td)
        for vc in (rail_v or (SW / 2, w - SW / 2)):
            lhx("Black Metal", T, [(r0, vc - RW / 2, zn(r0) + HR - 0.13), (r1, vc - RW / 2, zn(r1) + HR - 0.13), (r1, vc - RW / 2, zn(r1) + HR), (r0, vc - RW / 2, zn(r0) + HR),
                                   (r0, vc + RW / 2, zn(r0) + HR - 0.13), (r1, vc + RW / 2, zn(r1) + HR - 0.13), (r1, vc + RW / 2, zn(r1) + HR), (r0, vc + RW / 2, zn(r0) + HR)], R)
            for up in (posts if posts is not None else (r0 + 0.05, r1 - 0.05)):
                zp_ = (zl(up) - pl * 0.8) if carriage == "tube" else zt(up) - 0.05     # tube: flat bar posts bolted to the tube's outer face
                lbx("Black Metal", T, up - 0.05, up + 0.05, vc - 0.04, vc + 0.04, max(zp_, z0 + 0.01), zn(up) + HR - 0.06, R)
    return dict(u_end=u_end, zn=zn, zt=zt)


def guard(x0, x1, y0, y1, z, h=3.0):
    """Black steel guard with an oak cap along a platform edge (a thin box in plan)."""
    box("White Oak", x0 - 0.04, x1 + 0.04, y0 - 0.04, y1 + 0.04, z + h - 0.12, z + h)
    box("Black Metal", x0, x1, y0, y1, z + 0.1, z + 0.2)     # bottom rail, like the loft guard (it is also what stops a walker)
    alongx = (x1 - x0) > (y1 - y0)
    n_ = max(2, int(((x1 - x0) if alongx else (y1 - y0)) / 0.33))
    for i_ in range(n_ + 1):
        t_ = i_ / n_
        cx_, cy_ = (x0 + (x1 - x0) * t_, (y0 + y1) / 2) if alongx else ((x0 + x1) / 2, y0 + (y1 - y0) * t_)
        r_ = 0.06 if i_ in (0, n_) else 0.02
        box("Black Metal", cx_ - r_, cx_ + r_, cy_ - r_, cy_ + r_, z, z + h - 0.12)


def mono_ladder(WX, WY):
    """Centre stringer ships ladder with its landing, balcony, posts, rails and guard (11/22/2026 structure design, round 3), drawn from the same
    geometry the CAD model and the frame analysis use. Local inches: a west of the bath 1 wall, b north of the clerestory wall, z up."""
    sys.path.insert(0, os.path.join(HERE, "..", "tools", "ladder_drawings"))
    import ladder_geom as G
    ST, OAK, e = "Black Metal", "White Oak", 0.03
    P = lambda a, b, z: (WX - a / 12, WY - b / 12, z / 12)
    gb = lambda mat, a0, a1, b0, b1, z0, z1: box(mat, WX - a1 / 12, WX - a0 / 12, WY - b1 / 12, WY - b0 / 12, z0 / 12, z1 / 12)
    gh = lambda mat, f, uz, v0, v1: hexa(mat, [P(*f.p(u, v0, z)) for u, z in uz] + [P(*f.p(u, v1, z)) for u, z in uz])
    XL, ZP, FL_, TT, TK, VC, BT = G.XL, G.ZP, G.FL, G.TT, G.TK, G.VC, G.BRKT_T
    gv = lambda mat, f, vz, u0, u1: hexa(mat, [P(*f.p(u0, v, z)) for v, z in vz] + [P(*f.p(u1, v, z)) for v, z in vz])
    nx, nz = math.sin(G.ANG), -math.cos(G.ANG)
    SOCKETS = False
    ZN = "Stainless"                                     # bolt heads, nuts and anchors: every joint is bolted, nothing welded (Maxwell 11/22/2026)

    def bolt(a, b, z, axis, sign=1, d=0.66, h=0.21, kind="socket"):
        """socket button head (round, Allen key) or, kind 'hex', a hex head or nut: no square heads (Maxwell 11/22/2026)"""
        if kind == "hex":
            d, h = (0.65, 0.33) if d >= 0.6 else (0.5, 0.25)
            r, n, th0, quads = d / math.sqrt(3), 6, 0.0, ((0, 1, 2, 3), (3, 4, 5, 0))
        else:
            r, n, th0, quads = d / 2, 8, math.pi / 8, ((0, 1, 2, 3), (3, 4, 7, 0), (4, 5, 6, 7))
        ax = dict(a=(1, 0, 0), b=(0, 1, 0), z=(0, 0, 1))[axis]
        e1, e2 = [q for q in ((1, 0, 0), (0, 1, 0), (0, 0, 1)) if q != ax]
        ring = [tuple((a, b, z)[j] + r * (math.cos(th0 + 2 * math.pi * i / n) * e1[j] + math.sin(th0 + 2 * math.pi * i / n) * e2[j]) for j in range(3)) for i in range(n)]
        top = lambda p_, t_: tuple(p_[j] + sign * t_ * ax[j] for j in range(3))
        for q in quads:
            hexa(ZN, [P(*ring[i]) for i in q] + [P(*top(ring[i], h)) for i in q])
        if kind != "hex" and d >= 0.6 and SOCKETS:       # the hex socket (off: it is too small to read and its faces upset the flicker audit)
            rs = 0.14
            sk = [tuple((a, b, z)[j] + rs * (math.cos(math.pi / 3 * i) * e1[j] + math.sin(math.pi / 3 * i) * e2[j]) for j in range(3)) for i in range(6)]
            for q in ((0, 1, 2, 3), (3, 4, 5, 0)):
                hexa(ST, [P(*top(sk[i], h)) for i in q] + [P(*top(sk[i], h + 0.02)) for i in q])

    def nut(a, b, z, axis, sign=1, **kw):
        bolt(a, b, z, axis, sign, kind="hex", **kw)

    def fbolt(f, u, v, z, axis, sign=1, **kw):
        a, b, _ = f.p(u, v, z)
        if axis == "z":
            return bolt(a, b, z, "z", sign, **kw)
        a2, b2, _ = f.p(u, v + sign, z) if axis == "v" else f.p(u + sign, v, z)
        bolt(a, b, z, "a" if abs(a2 - a) > 0.5 else "b", (1 if a2 > a else -1) if abs(a2 - a) > 0.5 else (1 if b2 > b else -1), **kw)

    def fnut(f, u, v, z, axis, sign=1, **kw):
        fbolt(f, u, v, z, axis, sign, kind="hex", **kw)

    def gpoly(mat, f, pts, v0, v1):
        """a convex (u, z) outline as fan quads from its first point"""
        for i in range(1, len(pts) - 1, 2):
            j = min(i + 2, len(pts) - 1)
            gh(mat, f, [pts[0], pts[i], pts[i + 1], pts[j]], v0, v1)

    def gstrips(mat, f, zb, top, v0, v1):
        """outline from a level bottom at zb up to a sampled top line [(u, z), ...], as plumb strips"""
        for (u0, z0), (u1, z1) in zip(top, top[1:]):
            gh(mat, f, [(u0, zb), (u1, zb), (u1, z1), (u0, z0)], v0, v1)

    def post(a0, a1, b0, b1, z0):
        """square post whose top is cut to the plane just under the one continuous rail"""
        zt = G.rail_plane(a0, a1, b0, b1)
        cs = ((a0, b0), (a1, b0), (a1, b1), (a0, b1))
        hexa(ST, [P(a, b, z0) for a, b in cs] + [P(a, b, zt(a, b)) for a, b in cs])

    for f in G.FLIGHTS:
        zb_ = lambda u, f=f: f.zl(u) - G.PL
        ub, ztr, utr, _ = G.head_cut(f)                  # round 5 head (both flights from round 6): one plumb cut at the beam face, top trimmed level
        if f is G.UPPER:                                 # level foot on the saddle
            uf, us_ = G.U_FOOT, G.U_FOOT + G.L_SEAT
            gh(ST, f, [(uf, G.Z_SEAT), (us_, zb_(us_)), (us_, f.zl(us_) - e), (uf, f.zl(uf) - e)], VC - G.TW / 2, VC + G.TW / 2)
        else:                                            # level foot on the slab
            us_ = f.u1
            gh(ST, f, [(f.u0, f.zf + e), (us_, f.zf + e), (us_, f.zl(us_) - e), (f.u0, f.zl(f.u0) - e)], VC - G.TW / 2, VC + G.TW / 2)
        gh(ST, f, [(us_, zb_(us_) if f is G.UPPER else f.zf + e), (ub, zb_(ub)), (ub, ztr - e), (us_, f.zl(us_) - e)], VC - G.TW / 2, VC + G.TW / 2)
        gh(ST, f, [(us_, f.zl(us_) - e), (ub, ztr - e), (utr, ztr - e), (utr, ztr - e)], VC - G.TW / 2, VC + G.TW / 2)
        for k in range(1, f.nr):
            uk, zk = f.uk(k), f.z0 + k * G.RI - TT
            for sg in (-1, 1):
                v0 = VC + sg * (G.TW / 2 + e)
                A = (uk + G.WEB0, zk - BT)
                web = [(u_, min(z_, zk - e)) for u_, z_ in G.bracket_web(f, k)]    # round 6: corners rounded, top just under the tread
                zc_ = f.zf + BT
                foot_ = f is G.LOWER and min(z_ for _, z_ in web) < zc_     # the lower flight's first web stops at its foot flange
                if foot_:
                    cl = []
                    for p_, q_ in zip(web, web[1:] + web[:1]):
                        if p_[1] >= zc_:
                            cl.append(p_)
                        if (p_[1] - zc_) * (q_[1] - zc_) < 0:
                            t_ = (zc_ - p_[1]) / (q_[1] - p_[1])
                            cl.append((p_[0] + t_ * (q_[0] - p_[0]), zc_))
                    web = cl
                gpoly(ST, f, web, v0, v0 + sg * BT)
                gh(ST, f, [(uk + G.SEAT_S, zk - BT), (uk + G.TD + G.RT - e, zk - BT), (uk + G.TD + G.RT - e, zk - e), (uk + G.SEAT_S, zk - e)], v0 + sg * BT, v0 + sg * G.SEAT_TAB)
                # flange folded off the web's front edge, one bolt into the strip that crosses under the tread
                gh(ST, f, [(A[0] + e, zk - G.ARM_D), (A[0] + BT, zk - G.ARM_D), (A[0] + BT, zk - BT - e), (A[0] + e, zk - BT - e)], v0, v0 + sg * (BT + G.ARM_FL))
                fbolt(f, A[0] + BT, v0 + sg * (BT + 0.95), zk - G.FLANGE_BOLT, "u")
                fnut(f, A[0] - BT, v0 + sg * (BT + 0.95), zk - G.FLANGE_BOLT, "u", -1)
                for s_ in (4.25, 8.25):                      # two through bolts per bracket pair: socket head on the open side, nut on the wall side
                    ub_, zb2 = A[0] + s_ * math.cos(G.ANG) + nx * G.BOLT_N, f.zl(A[0]) + s_ * math.sin(G.ANG) + nz * G.BOLT_N
                    if zb2 > f.zf + BT + 0.5:
                        (fbolt if sg < 0 else fnut)(f, ub_, v0 + sg * BT, zb2, "v", sg)
                for ub_ in (uk + 6.5, uk + 8.0):
                    fbolt(f, ub_, v0 + sg * 0.9, zk - BT, "z", -1, d=0.5, h=0.15)
                if foot_:                                    # foot flange on the slab, two anchors
                    us_f = [u_ for u_, z_ in web if abs(z_ - zc_) < 1e-6]
                    fu = (min(us_f), max(us_f))
                    gh(ST, f, [(fu[0], f.zf + e), (fu[1], f.zf + e), (fu[1], f.zf + BT), (fu[0], f.zf + BT)], v0 + sg * BT, v0 + sg * G.FOOT_W)
                    for ub_ in (fu[0] + 0.8, fu[1] - 0.8):
                        fnut(f, ub_, v0 + sg * (G.FOOT_W / 2 + 0.6), f.zf + BT, "z")
            ua_, v0_, v1_ = uk + G.WEB0, G.ARM_END, G.WN - G.ARM_END
            gv(ST, f, [(v0_, zk - G.ARM_D), (v1_, zk - G.ARM_D), (v1_, zk - e), (v0_, zk - e)], ua_ - BT, ua_ - e)    # the strip: also the top of the riser below
            for vt_ in (v0_ + G.STRIP_TAB, v1_ - G.STRIP_TAB):          # screw tab at each end, folded toward the back of the tread (Maxwell 11/23/2026)
                gh(ST, f, [(ua_ + e, zk - BT), (ua_ + 1.25, zk - BT), (ua_ + 1.25, zk - e), (ua_ + e, zk - e)], vt_ - 0.9, vt_ + 0.9)
                fbolt(f, ua_ + 0.7, vt_, zk - BT, "z", -1, d=0.5, h=0.15)
            gh(OAK, f, [(uk, zk), (uk + G.TD, zk), (uk + G.TD, zk + TT), (uk, zk + TT)], 0.05, G.WN - 0.05)
            ur = uk + G.TD                                   # riser lip behind every tread
            gh(OAK, f, [(ur + e, zk), (ur + G.RT, zk), (ur + G.RT, zk + TT + G.RH), (ur + e, zk + TT + G.RH)], 0.05 + e, G.WN - 0.05 - e)
        hc = G.head_clip(f)                                  # round 6: the same head clip pair at both stringer tops
        ub = hc["ub"]
        for sg in (-1, 1):
            vt = VC + sg * (G.TW / 2 + e)
            gpoly(ST, f, hc["leg"], vt, vt + sg * BT)
            gh(ST, f, [(ub - BT + e, hc["beam"][0]), (ub - e, hc["beam"][0]), (ub - e, hc["beam"][1]), (ub - BT + e, hc["beam"][1])], vt + sg * BT, vt + sg * 2.25)
            (fbolt if sg < 0 else fnut)(f, hc["tube_bolt"][0], vt + sg * BT, hc["tube_bolt"][1], "v", sg)   # one through bolt across the tube, crush sleeve inside
            fbolt(f, ub - BT, vt + sg * 1.3, hc["beam_bolt_z"], "u", -1); fnut(f, ub + G.FW, vt + sg * 1.3, hc["beam_bolt_z"], "u", 1)
        if f is G.UPPER:                                     # round 6: level foot on a saddle on one 3 x 3 post; cheeks bolt through the stringer, tabs to the landing's north beam
            zs, zpt = G.Z_SEAT, G.Z_SEAT - BT
            a0p, a1p, b0p, b1p = G.UP_POST
            gb(ST, a0p, a1p, b0p, b1p, 0.375, zpt - e)
            gb(ST, a0p - 2, a1p + 2, b0p - 2, b1p + 2, 0.02, 0.375)
            for a_ in (a0p - 1.2, a1p + 1.2):
                for b_ in (b0p - 1.2, b1p + 1.2):
                    nut(a_, b_, 0.375, "z")
            u0p, u1p = G.SAD_U0, G.SAD_U1
            gh(ST, f, [(u0p, zpt), (u1p, zpt), (u1p, zs - e), (u0p, zs - e)], VC - G.TW / 2 - BT, VC + G.TW / 2 + BT)
            for sg in (-1, 1):
                vt = VC + sg * (G.TW / 2 + e)
                gstrips(ST, f, zs, G.CHEEK[1:-1], vt, vt + sg * BT)          # cheek, above the seat (the seat block covers below)
                gh(ST, f, [(u0p + e, G.TAB_Z[0]), (u0p + BT, G.TAB_Z[0]), (u0p + BT, G.TAB_Z[1]), (u0p + e, G.TAB_Z[1])], vt + sg * BT, vt + sg * (BT + G.TAB_W))
                fbolt(f, u0p + BT, vt + sg * (BT + 1.05), G.TAB_BOLT_Z, "u", 1); fnut(f, u0p - G.LN_W, vt + sg * (BT + 1.05), G.TAB_BOLT_Z, "u", -1)
            for u0_ in (u0p, u1p - BT):                      # legs down the post's south and north faces
                gh(ST, f, [(u0_, zpt - G.SAD_LEG), (u0_ + BT, zpt - G.SAD_LEG), (u0_ + BT, zpt - e), (u0_, zpt - e)], VC - 1.5, VC + 1.5)
            zlb = zpt - 2.0
            fbolt(f, u0p, VC, zlb, "u", -1); fnut(f, u1p, VC, zlb, "u", 1)
            fbolt(f, G.SAD_BOLT[0], VC - G.TW / 2 - BT, G.SAD_BOLT[1], "v", -1); fnut(f, G.SAD_BOLT[0], VC + G.TW / 2 + BT, G.SAD_BOLT[1], "v", 1)
    ur = G.TD - G.GO
    gh(OAK, G.UPPER, [(ur + e, ZP - TT), (ur + G.RT, ZP - TT), (ur + G.RT, ZP + G.RH), (ur + e, ZP + G.RH)], 0.05 + e, G.WN - 0.05 - e)
    # one continuous open side rail, lower flight to the bath 1 wall, every post tucked under it (Maxwell 11/22/2026 round 3)
    if G.CONT_RAIL:
        fr = G.rail_frames()
        for (p0, p1, zt0, zb0), (q0, q1, zt1, zb1) in zip(fr, fr[1:]):
            hexa(ST, [P(*p0, zb0), P(*p1, zb0), P(*p1, zt0), P(*p0, zt0), P(*q0, zb1), P(*q1, zb1), P(*q1, zt1), P(*q0, zt1)])
    else:                                                # straight rails between the posts (Maxwell 11/24/2026)
        for nm_, a0, a1, b0, b1, z0_, z1_, ax in G.straight_rails():
            dp = G.RAIL / math.cos(G.ANG) if z0_ != z1_ else G.RAIL     # plumb depth of a sloped rail
            if ax == "a":
                ends = (((a0, b0), (a0, b1)), ((a1, b0), (a1, b1)))
            else:
                ends = (((a0, b0), (a1, b0)), ((a0, b1), (a1, b1)))
            (p0, p1), (q0, q1) = ends
            hexa(ST, [P(*p0, z0_ - dp), P(*p1, z0_ - dp), P(*p1, z0_), P(*p0, z0_), P(*q0, z1_ - dp), P(*q1, z1_ - dp), P(*q1, z1_), P(*q0, z1_)])
    # lower flight foot post and the corner newel, each on a base plate with four slab anchors
    fa = G.A_FOOT
    post(fa - 1, fa + 1, XL + e, XL + G.POST, 0.375)
    gb(ST, fa - 3, fa + 3, XL - 2, XL + G.POST + 2, 0.02, 0.375)
    post(XL + e, XL + G.POST, XL + e, XL + G.POST, 0.375)
    gb(ST, XL - 2, XL + G.POST + 2, XL - 2, XL + G.POST + 2, 0.02, 0.375)
    for ca, cb in ((fa, XL + 1), (XL + 1, XL + 1)):
        for da in (-2.3, 2.3):
            for db in (-2.3, 2.3):
                nut(ca + da, cb + db, 0.375, "z")
    for z_ in (ZP - TK + 0.8, ZP - TT - 0.8):                # corner newel lapped onto the landing's west beam
        bolt(XL + G.POST, XL + 1, z_, "a")
        nut(XL - 2, XL + 1, z_, "a", -1)
    # corner landing: oak deck on a 1/8 wall tube frame; the north beam is a 4 x 3 tube laid flat under the stringer's foot
    z0, z1 = ZP - TK, ZP - TT - e
    gb(OAK, 0.03, XL, 0.03, G.LAND_DECK_N, ZP - TT, ZP)
    h = G.LN_W / 2
    for a0, a1, b0, b1 in ((0.05, 2, 0.05, G.LAND_N - e), (2 + e, XL - e, 0.05, 2), (XL - 2, XL - e, 2 + e, G.LAND_N - e), (2 + e, XL - 2 - e, G.B_LN - h, G.B_LN + h - 2 * e), (G.A_LH - 1, G.A_LH + 1, 2 + e, G.B_LN - h - e)):
        gb(ST, a0, a1, b0, b1, z0, z1)
    for b_ in G.LAND_LAGS["LE"]:
        nut(2, b_, z0 + 1.5, "a")
    for a_ in G.LAND_LAGS["LS"]:
        nut(a_, 2, z0 + 1.5, "b")
    # landing posts under both ends of the north beam: anchored base plate, flat splice plates on the outer faces, the north east one lagged to the wall
    for nm, (a0_, a1_, b0_, b1_) in G.LAND_POSTS.items():
        gb(ST, a0_ + e, a1_ - e, b0_ + e, b1_ - e, 0.375, z0 - e)
        pa0 = 0.05 if nm == "ne" else a0_ - 2.0
        gb(ST, pa0, a1_ + 2.0, b0_ - 2.0, b1_ + 2.0, 0.02, 0.375)
        for a_, b_ in (((a1_ + 1.2, b0_ - 1.2), (a1_ + 1.2, b1_ + 1.2)) if nm == "ne" else ((a0_ - 1.2, b0_ - 1.2), (a1_ + 1.2, b1_ + 1.2))):
            nut(a_, b_, 0.375, "z")
        gb(ST, a0_ + (e if nm == "ne" else 0), a1_ + (2.0 if nm == "ne" else 0.0), b1_ + e, b1_ + BT, z0 - 3.0, ZP - TT - e)
        bolt((a0_ + a1_) / 2, b1_ + BT, z0 - 1.5, "b")
        bolt(a1_ + 1.0 if nm == "ne" else a0_ + 1.0, b1_ + BT, G.ZLF, "b")
        if nm == "nw":
            gb(ST, a1_ + e, a1_ + BT, b0_, b1_, z0 - 3.0, ZP - TT - e)
            for z_ in (z0 - 1.5, G.ZLF):
                bolt(a1_ + BT, (b0_ + b1_) / 2, z_, "a")
        else:
            for z_ in (8.0, z0 - 8.0):
                nut(a1_, (b0_ + b1_) / 2, z_, "a")
    # balcony: deck, frame, two 45 degree braces (under the head beam and the north arm) from the west end down to the wall
    z0, z1 = FL_ - TK, FL_ - TT - e
    gb(OAK, 0.03, XL, G.BAL_S, G.BAL_N, FL_ - TT, FL_ - 0.05)
    for a0, a1, b0, b1 in ((0.05, 2, G.BAL_S + e, G.BAL_N - e), (2 + e, XL - 2 - e, G.BAL_S + e, G.BAL_S + 2), (2 + e, XL - 2 - e, G.B_BH - 1, G.B_BH + 1), (2 + e, XL - e, G.BAL_N - 2, G.BAL_N - e), (XL - 2, XL - e, G.BAL_S + e, G.BAL_N - 2 - e)):
        gb(ST, a0, a1, b0, b1, z0, z1)
    for b_ in G.BAL_LAGS:
        nut(2, b_, z0 + 1.5, "a")
    r2, c_ = G.POST / math.sqrt(2), XL - 1.5
    for b in (G.B_BH, G.BAL_N - 1):                      # round 5: a second brace under the head beam (Maxwell 11/23/2026), clear of the treads
        hexa(ST, [P(a, bb, z) for bb in (b - 1 + e, b + 1 - 2 * e) for a, z in ((c_ + r2, z0 - e), (c_ - r2, z0 - e), (0.05, z0 - c_ + r2), (0.05, z0 - c_ - r2))])
        bolt(c_ - 2.2, b + 1 - 2 * e, z0 - 2.2, "b"); nut(1.6, b + 1 - 2 * e, z0 - c_ + 1.6, "b")
    # the free posts stand outside the frame and stop under the rail; an L shaped plate bolts each to the end beam and 3 1/2 in up the post
    PN = (G.BAL_N + 0.375 + e, G.BAL_N + 0.375 + G.POST)
    post(XL + e, XL + G.POST, G.BAL_S, G.BAL_S + G.POST, z0)
    post(XL + e, XL + G.POST, *PN, z0)
    for b0, b1, sg in ((G.BAL_S - 0.375, G.BAL_S - e, -1), (G.BAL_N + e, G.BAL_N + 0.375, 1)):
        gb(ST, XL - 8, XL + G.POST - e, b0, b1, z0 + e, FL_ - TT)
        gb(ST, XL + 2 * e, XL + G.POST - e, b0, b1, FL_ - TT + e, FL_ + 3.5)
        for a_ in (XL - 7, XL - 2.5):
            bolt(a_, b1 if sg > 0 else b0, z0 + 1.5, "b", sg)
        for z_ in (z0 + 1.2, FL_ + 2.6):
            bolt(XL + 1, b0, z_, "b", -1)
            nut(XL + 1, b1 + G.POST, z_, "b", 1)
    post(0.05, G.POST, *PN, FL_ - 13)
    for z_ in (FL_ - 11, FL_ - 2):
        nut(G.POST, PN[0] + 1, z_, "a")
    ra, rb = (XL + 0.25, XL + 0.25 + G.RAIL), (G.GP_B - G.RAIL / 2, G.GP_B + G.RAIL / 2)
    zr = FL_ + 3.6                                       # bottom rails; the top rails are the continuous rail
    gb(ST, ra[0], ra[1], G.BAL_S + G.POST + e, PN[0] - e, zr, zr + G.RAIL - e)
    gb(ST, G.POST + e, XL - e, rb[0], rb[1], zr, zr + G.RAIL - e)
    pz = (FL_ + 3.6 + G.RAIL, G.G_TOP - G.RAIL - e)
    span = (G.BAL_S + G.POST, PN[0])
    n_w = math.ceil((span[1] - span[0]) / 4.4)
    for i in range(1, n_w):
        b = span[0] + i * (span[1] - span[0]) / n_w
        gb(ST, G.PC - 0.25, G.PC + 0.25, b - 0.25, b + 0.25, *pz)
    n_n = math.ceil((XL - G.POST) / 4.4)
    for i in range(1, n_n):
        a = G.POST + i * (XL - G.POST) / n_n
        gb(ST, a - 0.25, a + 0.25, G.GP_B - 0.25, G.GP_B + 0.25, *pz)


def _ladder_options():
    global RAIL_SPAN, LADDER_CLIMBS
    W = ly1 - ly0
    WALLX = WALL
    LAD_INFO = dict(
        pullout=("Ships ladder with pull out bottom steps", "Fixed ladder starts at the door jamb; the bottom three steps are a unit on slides that pulls out 13 in to climb and pushes back under the ladder."),
        flip=("Ships ladder with a flip up foot", "Fixed ladder starts at the door jamb; the bottom three treads hinge up and rest on the ladder."),
        lturn=("Ships ladder with a quarter turn landing", "Nine risers climb south beside the door to a landing, four more turn east to the loft."),
        side=("Ships ladder along the east wall", "Climbs north along the bath 1 wall to a balcony landing at loft level in the north east corner."),
        corner=("Narrow ships ladder with a corner landing", "Five risers east along the south wall to a landing in the corner, eight more north along the bath 1 wall to a balcony at loft level. 20 in clear between the rails."),
    winder=("Narrow ships ladder with winder steps in the corner", "Four treads east along the south wall, three wedge treads turn the corner, then straight north along the bath 1 wall to a balcony at loft level. No landing below the loft."),
    alt=("Alternating tread stair, 68 degrees", "Paddle treads, one foot per tread. Steeper than R311.7.12 allows for a ships ladder."))
    r_lad = rec("loft.ladder", "stair", LAD_INFO[DESIGN][0], "interior", room="Loft", info=dict(model=LAD_INFO[DESIGN][0], notes=[LAD_INFO[DESIGN][1], "MOCKUP option, 11/21/2026."]))

    if DESIGN in ("pullout", "flip"):
        T = lad_T(lx0, ly0, (1, 0))
        u_c = DOOR_X + 0.03 - lx0                                # plumb cut of the fixed ladder, at the door jamb
        nlow = int(u_c / GO) + 1                                 # treads whose nosing is west of the cut
        zn_ = lambda u: RI + u * SL
        fx = flight(T, 0.0, NR, RI, GO, TD, W, treads=range(nlow + 1, NR), u_lo=u_c, leg=True,
                    rail=(u_c, (NR - 1) * GO), posts=((2 * u_c + 0.25) if DESIGN == "flip" else (u_c + 0.05), (NR - 1) * GO - 0.05))
        if DESIGN == "pullout":
            S = (u_c + 0.04) if STOW else 0.0
            Rm = (lambda u, v, z: (u + S, v, z)) if S else None
            ub = (nlow - 1) * GO + TD
            body = paint("#7C8468")
            for k in range(1, nlow + 1):
                lbx(body, T, (k - 1) * GO + 0.03, ub, SW + 0.03, W - SW - 0.03, (k - 1) * RI if k > 1 else 0.02, k * RI - 0.12, Rm)
            flight(T, 0.0, NR, RI, GO, TD, W, treads=range(1, nlow + 1), stringers=False, top_nosing=False, R=Rm,
                   rail=(0.0, u_c), posts=(0.02,), rail_v=(SW + 0.09, W - SW - 0.09), tread_v=(SW + 0.03, W - SW - 0.03))
        else:
            Rm = rot_uz(u_c, zn_(u_c) + 0.1, 178) if STOW else None
            flight(T, 0.0, NR, RI, GO, TD, W, treads=range(1, nlow + 1), u_hi=u_c - 0.01, top_nosing=False, R=Rm, rail=False)
            Rr = rot_uz(u_c, zn_(u_c) + HR, 178) if STOW else None
            flight(T, 0.0, NR, RI, GO, TD, W, treads=(), stringers=False, top_nosing=False, R=Rr, rail=(0.0, u_c - 0.01), posts=() if STOW else (0.05,))
    elif DESIGN == "lturn":
        n_up = 4
        n_lo = NR - n_up
        zp = n_lo * RI
        ox_u = lx1 - ((n_up - 1) * GO + (TD - GO))               # first riser of the upper flight = east edge of the landing
        xp0 = DOOR_X + 0.04
        flight(lad_T(ox_u, ly0, (1, 0)), zp, n_up, RI, GO, TD, W)
        ul = (n_lo - 1) * GO + (TD - GO)
        flight(lad_T(xp0 + W, ly0 - ul, (0, 1)), 0.0, n_lo, RI, GO, TD, W)
        box("White Oak", xp0, ox_u + 0.02, ly0 - 0.005, ly1, zp - 0.45, zp)   # landing
        for px_, py_ in ((xp0, ly0), (xp0, ly1 - 0.29), (ox_u - 0.27, ly0), (ox_u - 0.27, ly1 - 0.29)):
            box("White Oak", px_, px_ + 0.29, py_, py_ + 0.29, 0.0, zp - 0.45)
        guard(xp0 + 0.02, xp0 + 0.1, ly0 + 0.1, ly1 - 0.02, zp)
        guard(xp0 + W + 0.05, ox_u + 0.0, ly0 + 0.02, ly0 + 0.1, zp)
    elif DESIGN == "side":
        ox = WALLX - W - 0.1
        yp0 = 22.93
        yp1 = yp0 + W                                            # landing: a balcony at loft level in the north east corner
        ue = (NR - 1) * GO + (TD - GO)
        flight(lad_T(ox, yp1 + ue, (0, -1)), 0.0, NR, RI, GO, TD, W)
        box("White Oak", ox, EDGE_X - 0.002, yp0, yp1 + 0.005, FL - 0.5, FL)
        guard(ox + 0.02, ox + 0.1, yp0 + 0.05, yp1 - 0.1, FL)
        for yb_ in (yp0 + 0.3, yp1 - 0.2):                       # steel knee braces off the bath 1 wall
            hexa("Black Metal", [(ox + 0.2, yb_, FL - 0.62), (ox + 0.45, yb_, FL - 0.5), (EDGE_X, yb_, FL - 2.6), (EDGE_X, yb_, FL - 2.9),
                                 (ox + 0.2, yb_ + 0.12, FL - 0.62), (ox + 0.45, yb_ + 0.12, FL - 0.5), (EDGE_X, yb_ + 0.12, FL - 2.6), (EDGE_X, yb_ + 0.12, FL - 2.9)])
        RAIL_SPAN = (yp1 + 0.06, LY1 - 0.1)
    elif DESIGN == "corner":
        n_lo = int(LOFT.get("ladder_lower_risers", 5))           # risers up to the corner landing (Maxwell 11/21/2026 mockup: 4, three treads before the landing)
        wn = LOFT.get("ladder_width_in", 24.0) / 12              # 24 in overall = 20 3/8 in clear between 1 13/16 in stringers (20 in min, R311.7.12). With 4 lower risers the foot stays put and the 5 in saved widens the ladder to 29 in
        zp = n_lo * RI
        gap = LOFT.get("ladder_wall_gap_in", 1.2) / 12           # upper flight's stringer to the bath 1 wall
        mono = LOFT.get("ladder_stringer", "") == "mono"         # one centre tube stringer, 4 in riser lips, no landing nosings (Maxwell 11/22/2026): drawn by mono_ladder() from tools/ladder_drawings/ladder_geom.py
        nose = LOFT.get("ladder_landing_nosing_in", (TD - GO) * 12) / 12     # oak nosing past each platform's edge; 0 = the platform edge is the top nosing
        tube = mono or LOFT.get("ladder_stringer", "") == "tube"  # stock rectangular tube stringers under the treads, laser cut brackets (Maxwell 11/21/2026)
        steel = tube or LOFT.get("ladder_stringer_in", 1.8) < 1.0    # steel stringers (black) instead of white oak
        wall_under = LOFT.get("ladder_wall_stringer_under", False)   # wall side stringer under the treads (tried 11/21/2026: no seat for the overlapping treads, dropped)
        under = wall_under or steel                              # tight to both walls, wall side rails on brackets 1 1/2 in off the walls
        car = "tube" if tube else "under" if wall_under else "side" if steel else False   # steel default: both plates beside the treads, treads on bolt on angle clips
        sy1 = YC - gap if under else ly1                         # the lower flight also tucks against the clerestory wall
        XL = WALLX - wn - gap                                    # west edge of both landings and of the upper flight
        ul = (n_lo - 1) * GO + nose
        assert XL - ul >= DOOR_X, "corner ladder still crosses the door"
        smat = "Black Metal" if steel else "White Oak"
        RC = (1.5 + RW * 12 / 2) / 12                            # wall to rail centre for a bracket rail (R311.7.8.4: 1 1/2 in clear)

        def wall_rail(T, z0, nr, w, wall_v, u_end):
            """handrail on wall brackets for the wall side of a flight; wall_v = the wall face in the flight's v"""
            flight(T, z0, nr, RI, GO, TD, w, treads=(), stringers=False, top_nosing=False, rail_v=(wall_v - RC,), posts=())
            zr = lambda u: z0 + RI + u * RI / GO + HR - 0.13
            for ub in (0.3, (u_end - (TD - GO)) / 2, u_end - (TD - GO) - 0.3):
                lbx("Black Metal", T, ub - 0.03, ub + 0.03, wall_v - RC, wall_v, zr(ub) - 0.1, zr(ub) - 0.04)
        wl = YC - (sy1 - wn)                                     # clerestory wall face in the lower flight's v
        orv = -0.25 / 12 if mono else 0.03125 if tube else SW    # open side rail's inner face, in from the open edge (mono: on posts outside it)
        if not mono:
          flight(lad_T(XL - ul, sy1 - wn, (1, 0)), 0.0, n_lo, RI, GO, TD, wn, smat=smat, rail_v=(orv - RW / 2,) if under else None, carriage=car, tuck=LOFT.get("ladder_tube_in", [2.0, 3.0])[1] / 12 + 0.12 if tube else 0.4)
        wall_rails = under and LOFT.get("ladder_wall_rail", True)    # Maxwell 11/22/2026 round 3: hidden for now (code wants them, see config.toml)
        if wall_rails:
            wall_rail(lad_T(XL - ul, sy1 - wn, (1, 0)), 0.0, n_lo, wn, wl, (n_lo - 1) * GO + TD - GO)
        yl0 = sy1 - wn - 0.1
        yln = yl0 - (0.667 if tube else 0.0)                     # tube: the landing runs 8 in further north, under the upper flight's first tread, so the upper tubes' feet stand on it
        tk = (0.12 + LOFT.get("ladder_tube_in", [2.0, 3.0])[1] / 12) if tube else None   # tube: both platforms are a 1 7/16 in oak deck on a 2 x 3 tube frame (11/22/2026 structure design)
        lt, bt = (tk, tk) if tube else (0.4, 0.5)
        pxo = 0.5625 if tube else 0.0                            # tube: west posts 6 3/4 in in from the edge, behind the lower tubes' heads tucked under the landing
        if not mono:
            box("White Oak", XL, EDGE_X - 0.002, yln, min(sy1 + 0.12, YC - 0.002), zp - lt, zp)
            box("White Oak", XL + pxo, XL + pxo + 0.29, yl0, yl0 + 0.29, 0.0, zp - lt)
            box("White Oak", XL + pxo, XL + pxo + 0.29, sy1 - 0.2, min(sy1 + 0.09, YC - 0.002), 0.0, zp - lt)
        n_up = NR - n_lo
        uu = (n_up - 1) * GO + nose
        go_u, td_u = GO, TD
        if os.environ.get("LADDER_STRETCH") or LOFT.get("ladder_stretch"):   # upper flight runs to a balcony at the north end of the loft
            uu = yl0 - (22.93 + wn + 0.1)
            go_u = (uu - (TD - GO)) / (n_up - 1)
            td_u = go_u + 0.1
            print("stretched upper flight: going", round(go_u * 12, 2), "in, slope", round(math.degrees(math.atan(RI / go_u)), 1), "deg")
        if not mono:
            flight(lad_T(XL, yl0, (0, -1)), zp, n_up, RI, go_u, td_u, wn, smat=smat, rail_v=(orv - RW / 2,) if under else None, carriage=car, tuck=bt)
        if wall_rails:
            wall_rail(lad_T(XL, yl0, (0, -1)), zp, n_up, wn, EDGE_X - XL, (n_up - 1) * GO + TD - GO)
        yt1 = yl0 - uu
        yt0 = yt1 - wn - 0.1
        if mono:
            mono_ladder(WALLX, YC)
        else:
            box("White Oak", XL, EDGE_X - 0.002, yt0, yt1 + 0.005, FL - bt, FL)
            guard(XL + 0.02, XL + 0.1, yt0 + 0.05, yt1 - 0.1, FL)
            if yt0 > 23.2:
                guard(XL + 0.1, EDGE_X - 0.05, yt0 + 0.02, yt0 + 0.1, FL)
        zb_ = FL - bt + 0.5
        for yb_ in (() if mono else (yt0 + 0.2, yt1 - 0.2)):
            hexa("Black Metal", [(XL + 0.2, yb_, zb_ - 0.62), (XL + 0.45, yb_, zb_ - 0.5), (EDGE_X, yb_, zb_ - 2.2), (EDGE_X, yb_, zb_ - 2.5),
                                 (XL + 0.2, yb_ + 0.12, zb_ - 0.62), (XL + 0.45, yb_ + 0.12, zb_ - 0.5), (EDGE_X, yb_ + 0.12, zb_ - 2.2), (EDGE_X, yb_ + 0.12, zb_ - 2.5)])
        RAIL_SPAN = [(LY0 + 0.1, yt0 - 0.05), (yt1 + 0.06, LY1 - 0.1)]
        LADDER_CLIMBS = [dict(id="loft.ladder", rect=[rnd(XL - ul), rnd(sy1 - wn), rnd(XL), rnd(sy1)], axis="x", z0=0.0, z1=rnd(zp)),
                         dict(id="loft.ladder", rect=[rnd(XL), rnd(yt1), rnd(XL + wn), rnd(yl0)], axis="y", rev=True, z0=rnd(zp), z1=FL, pad=0.7)]
        r_lad["info"]["specs"] = [["Risers", f"{NR} at {ftin(RI)}: {n_lo} east along the south wall, {n_up} north along the bath 1 wall"],
                                  ["Treads", f"{ftin(td_u)} deep, {ftin(go_u)} nosing to nosing"], ["Angle", f"{math.degrees(math.atan(RI / go_u)):.0f}\u00b0"],
                                  ["Clear width", (f"{ftin(wn + gap - RC - RW / 2 - orv)} between the rails, {ftin(wn - (0 if tube else SW * (1 if wall_under else 2)))} treads (20 in min at and below the rails)" if under else ftin(wn - 2 * SW) + " between the stringers and rails (20 in min)")], ["Overall width", ftin(wn)],
                                  ["Corner landing", f"{ftin(zp)} up"], ["Top landing", f"{ftin(wn + 0.1)} balcony at loft level, {ftin(LY1 - yt1)} from the south wall"],
                                  ["Foot", f"{ftin(XL - ul - DOOR_X)} east of the living room opening's jamb"], ["Handrails", f"both sides, {ftin(HR)} above the nosings"]]
        r_lad["info"]["notes"] = ["Maxwell's pick 11/21/2026: the straight to code ladder stood 13 in past the living room opening.",
                                  "Code limits (IRC R311.7.12, Residential Code of Ohio): riser 9 1/2 in max, going 5 in min, going + nosing 8 1/2 in min, 20 in clear at and below the handrails, handrails both sides 30 to 34 in. A ships ladder may serve a loft of 200 sq ft or less (this one is 134).",
                                  "The code section says nothing about landings; both are sized to the ladder width. The balcony needs brackets off the bath 1 wall: builder to confirm."]
        print("corner ladder: foot x", round(XL - ul, 3), "landing", round(zp * 12, 1), "in up; top landing y", round(yt0, 2), round(yt1, 2), "XL", round(XL, 2))
    elif DESIGN == "winder":
        wn = 2.0
        n_lo, n_w = 5, 3                                         # risers to the first wedge tread, wedge treads in the corner
        XL = WALLX - wn - 0.1
        yl0, ys, xe = ly1 - wn - 0.1, ly1, WALLX - 0.1
        flight(lad_T(XL - (n_lo - 1) * GO, ly1 - wn, (1, 0)), 0.0, n_lo, RI, GO, TD, wn, top_nosing=False, top_td=0.0)
        assert XL - (n_lo - 1) * GO >= DOOR_X
        t30 = math.tan(math.radians(30))
        fans = [[(XL, yl0), (XL - 0.25, ys), (XL + (ys - yl0) * t30, ys), (XL, yl0)],
                [(XL, yl0), (XL + (ys - yl0) * t30 - 0.2, ys), (xe, ys), (xe, yl0 + (xe - XL) * t30)],
                [(XL, yl0), (xe, yl0 + (xe - XL) * t30 + 0.2), (xe, yl0 - 0.02), (XL, yl0)]]
        for i_, poly in enumerate(fans):
            zt_ = (n_lo + i_) * RI
            hexa("White Oak", [(x_, y_, zt_ - 0.12) for x_, y_ in poly] + [(x_, y_, zt_) for x_, y_ in poly])
        n_up = NR - n_lo - n_w + 1
        zu = (n_lo + n_w - 1) * RI
        box("White Oak", XL - 0.12, XL + 0.12, yl0 - 0.12, yl0 + 0.12, 0.0, zu + RI + HR)     # newel the wedges hang on
        flight(lad_T(XL, yl0, (0, -1)), zu, n_up, RI, GO, TD, wn, u_lo=0.0)
        yt1 = yl0 - ((n_up - 1) * GO + (TD - GO))
        yt0 = yt1 - wn - 0.1
        box("White Oak", XL, EDGE_X - 0.002, yt0, yt1 + 0.005, FL - 0.5, FL)
        guard(XL + 0.02, XL + 0.1, yt0 + 0.05, yt1 - 0.1, FL)
        guard(XL + 0.1, EDGE_X - 0.05, yt0 + 0.02, yt0 + 0.1, FL)
        for yb_ in (yt0 + 0.2, yt1 - 0.2):
            hexa("Black Metal", [(XL + 0.2, yb_, FL - 0.62), (XL + 0.45, yb_, FL - 0.5), (EDGE_X, yb_, FL - 2.2), (EDGE_X, yb_, FL - 2.5),
                                 (XL + 0.2, yb_ + 0.12, FL - 0.62), (XL + 0.45, yb_ + 0.12, FL - 0.5), (EDGE_X, yb_ + 0.12, FL - 2.2), (EDGE_X, yb_ + 0.12, FL - 2.5)])
        RAIL_SPAN = [(LY0 + 0.1, yt0 - 0.05), (yt1 + 0.06, LY1 - 0.1)]
        print("winder ladder: foot x", round(XL - (n_lo - 1) * GO, 3), "top landing y", round(yt0, 2), round(yt1, 2), "upper risers", n_up, "upper start", round(zu * 12, 1))
    elif DESIGN == "alt":
        ang = LOFT.get("ladder_alt_deg", 68.0)
        go_a = RI / math.tan(math.radians(ang))
        wa = 2.1
        ox = lx1 - ((NR - 1) * go_a + (TD - GO))
        assert ox >= DOOR_X, "alternating tread stair still crosses the door"
        flight(lad_T(ox, ly1 - wa, (1, 0)), 0.0, NR, RI, go_a, 0.875, wa, alt=True, sdepth=1.5)
        RAIL_SPAN = (LY0 + 0.1, ly1 - wa - 0.05)


_ladder_options()
