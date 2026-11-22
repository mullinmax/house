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
        tube = LOFT.get("ladder_stringer", "") == "tube"         # stock rectangular tube stringers under the treads, laser cut brackets (Maxwell 11/21/2026)
        steel = tube or LOFT.get("ladder_stringer_in", 1.8) < 1.0    # steel stringers (black) instead of white oak
        wall_under = LOFT.get("ladder_wall_stringer_under", False)   # wall side stringer under the treads (tried 11/21/2026: no seat for the overlapping treads, dropped)
        under = wall_under or steel                              # tight to both walls, wall side rails on brackets 1 1/2 in off the walls
        car = "tube" if tube else "under" if wall_under else "side" if steel else False   # steel default: both plates beside the treads, treads on bolt on angle clips
        sy1 = YC - gap if under else ly1                         # the lower flight also tucks against the clerestory wall
        XL = WALLX - wn - gap                                    # west edge of both landings and of the upper flight
        ul = (n_lo - 1) * GO + (TD - GO)
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
        orv = 0.03125 if tube else SW                            # open side rail's inner face, in from the open edge
        flight(lad_T(XL - ul, sy1 - wn, (1, 0)), 0.0, n_lo, RI, GO, TD, wn, smat=smat, rail_v=(orv - RW / 2,) if under else None, carriage=car)
        if under:
            wall_rail(lad_T(XL - ul, sy1 - wn, (1, 0)), 0.0, n_lo, wn, wl, ul)
        yl0 = sy1 - wn - 0.1
        yln = yl0 - (0.667 if tube else 0.0)                     # tube: the landing runs 8 in further north, under the upper flight's first tread, so the upper tubes' feet stand on it
        pxo = 0.5625 if tube else 0.0                            # tube: west posts 6 3/4 in in from the edge, behind the lower tubes' heads tucked under the landing
        box("White Oak", XL, EDGE_X - 0.002, yln, min(sy1 + 0.12, YC - 0.002), zp - 0.4, zp)
        box("White Oak", XL + pxo, XL + pxo + 0.29, yl0, yl0 + 0.29, 0.0, zp - 0.4)
        box("White Oak", XL + pxo, XL + pxo + 0.29, sy1 - 0.2, min(sy1 + 0.09, YC - 0.002), 0.0, zp - 0.4)
        n_up = NR - n_lo
        uu = (n_up - 1) * GO + (TD - GO)
        go_u, td_u = GO, TD
        if os.environ.get("LADDER_STRETCH") or LOFT.get("ladder_stretch"):   # upper flight runs to a balcony at the north end of the loft
            uu = yl0 - (22.93 + wn + 0.1)
            go_u = (uu - (TD - GO)) / (n_up - 1)
            td_u = go_u + 0.1
            print("stretched upper flight: going", round(go_u * 12, 2), "in, slope", round(math.degrees(math.atan(RI / go_u)), 1), "deg")
        flight(lad_T(XL, yl0, (0, -1)), zp, n_up, RI, go_u, td_u, wn, smat=smat, rail_v=(orv - RW / 2,) if under else None, carriage=car, tuck=0.5)
        if under:
            wall_rail(lad_T(XL, yl0, (0, -1)), zp, n_up, wn, EDGE_X - XL, uu)
        yt1 = yl0 - uu
        yt0 = yt1 - wn - 0.1
        box("White Oak", XL, EDGE_X - 0.002, yt0, yt1 + 0.005, FL - 0.5, FL)
        guard(XL + 0.02, XL + 0.1, yt0 + 0.05, yt1 - 0.1, FL)
        if yt0 > 23.2:
            guard(XL + 0.1, EDGE_X - 0.05, yt0 + 0.02, yt0 + 0.1, FL)
        for yb_ in (yt0 + 0.2, yt1 - 0.2):
            hexa("Black Metal", [(XL + 0.2, yb_, FL - 0.62), (XL + 0.45, yb_, FL - 0.5), (EDGE_X, yb_, FL - 2.2), (EDGE_X, yb_, FL - 2.5),
                                 (XL + 0.2, yb_ + 0.12, FL - 0.62), (XL + 0.45, yb_ + 0.12, FL - 0.5), (EDGE_X, yb_ + 0.12, FL - 2.2), (EDGE_X, yb_ + 0.12, FL - 2.5)])
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
