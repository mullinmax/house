#!/usr/bin/env python3
"""Solid element check of the round 4 upper stringer joints (Maxwell 11/23/2026): the foot on its one post, and the notched top.

Pieces (ladder_geom.py / ladder_cad.py, mono round 4), each cut out of the frame model (ladder_fea.py) at a station on the HSS
4 x 4 x 1/4 stringer mid way between two tread bracket bolt groups, so the only loads are the frame's forces across the cut, the
forces from the tread brackets on the piece, and the piece's own weight:

  foot   stringer from its plumb cut foot (U_FOOT) to the cut; the bent saddle (seat under the tube, a cheek up each side with one
         through bolt, legs down the post's south and north faces with one bolt through the post); the 3 x 3 x 3/16 post down to its
         base plate (fixed there); one angle clip each side (a leg on the tube side, one through bolt across the tube, and a leg against
         the landing's north beam with one bolt through the beam, taken as rigid)
  head   stringer from the cut to its notched top: the part above the balcony frame's underside stops at the head beam's south face
         (U_BEAR), the rest runs under the beam to its north face (U_END); one angle clip each side (tube leg, through bolt across the
         tube; beam leg with one bolt through the head beam, rigid)

Joints: bolts are rigid bodies over every ply's hole surface (snug, no slip, no hole clearance); the tube bottom sits on the saddle
seat and the seat on the post's cut top, both modelled as tied (bonded) faces. Variants:
  bear     the foot's plumb end bears on the landing beam / the notched top bears on the head beam (normal restraint on the end face
           where the beam is); none = clips carry it all
  slot     head clip holes slotted vertically: the clip bolts pass no vertical force (what the frame model assumes)
Steel: E 29e6 psi, nu 0.29; HSS A500 Gr B Fy 46 ksi (tube, post: design wall 0.93 t), plate A36 Fy 36 ksi (saddle, clips, 1/4 in).
Allowable 0.6 Fy. Mesh: gmsh 10 node tets, separate per part; CalculiX linear static.

Run:  python joint_solid_fea.py --loads DIR/ladder_cut_loads.json --piece foot --out OUT [--coarse 2] [--cases 6] [--threads 8]
PRELIMINARY: for an engineer's review, not for construction.
"""
import argparse, json, math, os, shutil, subprocess, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ladder_geom as G
import bracket_solid_fea as B                       # C3D10 helpers: ccx_elements, plane_faces, parse_dat, nodal_stress, von_mises

assert G.MONO, "model/config.toml ladder_stringer must be 'mono'"
UP = G.UPPER
CA, SA = math.cos(G.ANG), math.sin(G.ANG)
HW = G.TW / 2                                       # tube half width
T_TUBE = 0.93 * G.WT                                # HSS design wall
T_POST = 0.93 * 0.1875
BT = G.BRKT_T                                       # saddle and clip plate
HOLE = 7 / 16
E_ST, NU_ST, RHO = 29.0e6, 0.29, 0.2836 / 386.1
FY = dict(TUBE=46000.0, POST=46000.0, SADDLE=36000.0, CLIPW=36000.0, CLIPE=36000.0)
zt = UP.zl                                          # tube top, plumb
zb = lambda x: UP.zl(x) - G.PL                      # tube bottom
zc = UP.zc
UF, UB, UE = G.U_FOOT, G.U_BEAR, G.U_END
ZU = UP.zu                                          # balcony frame underside
ZBEAM_L = (G.ZLF - G.FD / 2, G.ZLF + G.FD / 2)      # landing north beam, z
A0P, A1P, B0P, B1P = G.UP_POST
PX0, PX1 = B0P - G.B0, B1P - G.B0                   # post, x (the post's a range is centred on the stringer: y = +-1.5)
U0P, U1P = PX0 - BT, PX1 + BT                       # saddle
TPP = BT / CA                                       # saddle plate, plumb
ZCAP = lambda x: zb(x) - TPP                        # post top = saddle underside
PB = 0.375                                          # base plate
XS = (U0P + U1P) / 2                                # saddle cheek bolt
ZS = zb(XS) + 0.9
ZLB = zb(U0P + BT) - 2.0                            # saddle leg bolt (through the post)
SOLVER = os.environ.get("FEA_SOLVER", "SPOOLES")
NOTCH_HOLE = float(os.environ.get("NOTCH_HOLE", "0.75"))   # relief hole diameter at the notch corner (0 = sharp corner as drawn)


# ---------------------------------------------------------------- geometry (x north along the flight, y west, z up; inches)
def bolts(piece):
    """(name, point, axis, kind): kind 'rigid' joins every ply, 'fixed' is a bolt into a beam taken as rigid, 'slot' = vertical slots in the clips"""
    if piece == "foot":
        return [("cheek", (XS, 0.0, ZS), "y", "rigid"), ("leg", (U0P - 1, 0.0, ZLB), "x", "rigid"),
                ("clip", (UF + 1.0, 0.0, 43.1), "y", "rigid"),
                ("beam_w", (UF - 1, HW + 1.3, G.ZLF), "x", "fixed"), ("beam_e", (UF - 1, -HW - 1.3, G.ZLF), "x", "fixed")]
    return [("clip", (UB - 0.9, 0.0, ZU - 2.0), "y", "rigid"),
            ("beam_w", (UB - 2, HW + 1.3, G.ZBF), "x", "fixed"), ("beam_e", (UB - 2, -HW - 1.3, G.ZBF), "x", "fixed")]


def build_parts(piece, xc, path):
    import cadquery as cq
    V = cq.Vector

    def prism(pts, y0, y1):
        y0, y1 = sorted((y0, y1))
        w = cq.Wire.makePolygon([V(x, y0, z) for x, z in pts], close=True)
        return cq.Solid.extrudeLinear(cq.Face.makeFromWires(w), V(0, y1 - y0, 0))

    def box(x0, x1, y0, y1, z0, z1):
        x0, x1 = sorted((x0, x1)); y0, y1 = sorted((y0, y1)); z0, z1 = sorted((z0, z1))
        return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))

    def drill(s, p, ax, L=30.0):
        d = dict(x=V(1, 0, 0), y=V(0, 1, 0), z=V(0, 0, 1))[ax]
        q = V(*p) - d * (L / 2)
        return s.cut(cq.Solid.makeCylinder(HOLE / 2, L, q, d))

    tp = T_TUBE / CA
    parts = {}
    if piece == "foot":
        x0, x1 = UF, xc
        outer = prism([(x0, zb(x0)), (x1, zb(x1)), (x1, zt(x1)), (x0, zt(x0))], -HW, HW)
    else:
        x0, x1 = xc, UE
        outer = prism([(x0, zb(x0)), (UE, zb(UE)), (UE, ZU), (UB, ZU), (UB, zt(UB)), (x0, zt(x0))], -HW, HW)
    e0, e1 = x0 - 4, x1 + 4
    inner = prism([(e0, zb(e0) + tp), (e1, zb(e1) + tp), (e1, zt(e1) - tp), (e0, zt(e0) - tp)], -HW + T_TUBE, HW - T_TUBE)
    parts["TUBE"] = outer.cut(inner)
    for s in (1, -1):
        nm = "CLIPW" if s > 0 else "CLIPE"
        if piece == "foot":
            c = prism([(UF, 42.0), (UF + 1.5, 42.0), (UF + 1.5, 44.2), (UF, 44.2)], s * HW, s * (HW + BT))
            c = c.fuse(box(UF, UF + BT, s * HW, s * (HW + 2.25), 41.0, G.ZP - G.TT - 0.25))
        else:
            ua, us_ = UB - 1.75, UP.u2 - 0.15 / G.SL
            c = prism([(ua, ZU - 3.5), (UB - BT, ZU - 3.5), (UB - BT, ZU - 0.25), (us_, ZU - 0.25), (ua, zt(ua) - 0.1)], s * HW, s * (HW + BT))
            c = c.fuse(box(UB - BT, UB, s * HW, s * (HW + 2.25), ZU - 3.5, G.FL - G.TT - 0.25))
        c = c.clean()
        xi = UF + BT if piece == "foot" else UB - BT                # inside corner of the angle: bent, inside radius = plate thickness
        ed = [e for e in c.Edges() if e.geomType() == "LINE" and all(abs(p.x - xi) < 1e-6 and abs(abs(p.y) - (HW + BT)) < 1e-6 for p in (e.startPoint(), e.endPoint()))]
        try:
            c = c.fillet(BT, ed)
        except Exception as ex:
            print(f"  {nm} bend fillet failed ({len(ed)} edges), left sharp:", ex)
        parts[nm] = c
    if piece == "head" and NOTCH_HOLE > 0:                          # relief hole drilled at the notch's re-entrant corner, through both side walls
        parts["TUBE"] = parts["TUBE"].cut(cq.Solid.makeCylinder(NOTCH_HOLE / 2, 10, V(UB, -5, ZU), V(0, 1, 0)))
    if piece == "foot":
        sad = prism([(U0P, ZCAP(U0P)), (U1P, ZCAP(U1P)), (U1P, zb(U1P)), (U0P, zb(U0P))], -HW - BT, HW + BT)
        for s in (1, -1):
            sad = sad.fuse(prism([(U0P, zb(U0P)), (U1P, zb(U1P)), (U1P, zb(U1P) + 1.75), (U0P, zb(U0P) + 1.75)], s * HW, s * (HW + BT)))
        for u0_ in (U0P, U1P - BT):
            sad = sad.fuse(prism([(u0_, zb(u0_ + BT) - 3.5), (u0_ + BT, zb(u0_ + BT) - 3.5), (u0_ + BT, ZCAP(u0_ + BT) + 0.01), (u0_, ZCAP(u0_) + 0.01)], -1.5, 1.5))
        sad = sad.clean()
        ed = [e for e in sad.Edges() if e.geomType() == "LINE" and all(abs(abs(p.y) - HW) < 1e-6 and abs(p.z - zb(p.x)) < 1e-6 for p in (e.startPoint(), e.endPoint()))]
        try:                                                        # seat to cheek bends, inside radius = plate thickness
            sad = sad.fillet(BT, ed)
        except Exception as ex:
            print(f"  saddle bend fillet failed ({len(ed)} edges), left sharp:", ex)
        parts["SADDLE"] = sad
        ztop = ZCAP(PX1) + 1
        post = box(PX0, PX1, -1.5, 1.5, PB, ztop).cut(box(PX0 + T_POST, PX1 - T_POST, -1.5 + T_POST, 1.5 - T_POST, PB - 1, ztop + 1))
        post = post.cut(prism([(PX0 - 1, ZCAP(PX0 - 1)), (PX1 + 1, ZCAP(PX1 + 1)), (PX1 + 1, ztop + 5), (PX0 - 1, ztop + 5)], -3, 3))
        parts["POST"] = post
    for nm, p, ax, kind in bolts(piece):
        for k in parts:
            parts[k] = drill(parts[k], p, ax)
    for k, s in parts.items():
        s.exportBrep(os.path.join(path, f"{k}.brep"))
    return list(parts)


# ---------------------------------------------------------------- mesh
def mesh(piece, xc, work, coarse):
    import gmsh
    names = build_parts(piece, xc, work)
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", int(os.environ.get("GMSH_VERBOSE", "0")))
    gmsh.option.setNumber("General.NumThreads", int(os.environ.get("FEA_THREADS", os.cpu_count() or 4)))
    gmsh.model.add(piece)
    part = {}
    for nm in names:
        for d in gmsh.model.occ.importShapes(os.path.join(work, f"{nm}.brep")):
            if d[0] == 3:
                part[d[1]] = nm
    gmsh.model.occ.synchronize()
    h_fine, h_joint, h_far = 0.06 * coarse, 0.14 * coarse, 0.35 * coarse
    Fd = gmsh.model.mesh.field
    fl = []

    def me(expr):
        f = Fd.add("MathEval")
        Fd.setString(f, "F", expr)
        fl.append(f)
    for nm, p, ax, kind in bolts(piece):                             # bolt holes
        r = {"x": f"Sqrt((y-({p[1]}))^2+(z-({p[2]}))^2)", "y": f"Sqrt((x-({p[0]}))^2+(z-({p[2]}))^2)", "z": f"Sqrt((x-({p[0]}))^2+(y-({p[1]}))^2)"}[ax]
        me(f"{h_fine} + 0.4*Abs({r}-{HOLE / 2})")
    if piece == "head":
        me(f"{h_fine} + 0.4*Sqrt((x-{UB})^2+(z-{ZU})^2)")             # the notch's re-entrant corner (both side walls)
        jb = (UB - 4.5, UE + 0.5, ZU - 9.0, G.FL)
    else:
        me(f"{h_fine} + 0.4*Sqrt((x-{UF})^2+(z-{zb(UF)})^2)")         # the foot's bottom corner, over the saddle
        jb = (UF - 0.5, U1P + 2.5, ZLB - 2.5, G.ZP)
    f = Fd.add("Box")
    for k_, v_ in (("VIn", h_joint), ("VOut", h_far), ("XMin", jb[0]), ("XMax", jb[1]), ("YMin", -6), ("YMax", 6), ("ZMin", jb[2]), ("ZMax", jb[3]), ("Thickness", 2.0)):
        Fd.setNumber(f, k_, v_)
    fl.append(f)
    fm = Fd.add("Min")
    Fd.setNumbers(fm, "FieldsList", fl)
    Fd.setAsBackgroundMesh(fm)
    for k_, v_ in (("Mesh.MeshSizeExtendFromBoundary", 0), ("Mesh.MeshSizeFromPoints", 0), ("Mesh.MeshSizeFromCurvature", 0),
                   ("Mesh.Algorithm3D", 10), ("Mesh.Optimize", 1), ("Mesh.ElementOrder", 2), ("Mesh.SecondOrderLinear", 0),
                   ("Mesh.MeshSizeMax", h_far), ("Mesh.HighOrderOptimize", 2)):
        gmsh.option.setNumber(k_, v_)
    gmsh.model.mesh.generate(3)
    gmsh.model.mesh.setOrder(2)
    tags, xyz, _ = gmsh.model.mesh.getNodes()
    X = np.zeros((int(tags.max()) + 1, 3))
    X[tags.astype(int)] = xyz.reshape(-1, 3)
    els = {}
    for v, nm in part.items():
        et, _, en = gmsh.model.mesh.getElements(3, v)
        for ty, nn in zip(et, en):
            assert ty == 11, ty
            els.setdefault(nm, []).append(nn.reshape(-1, 10).astype(int))
    gmsh.finalize()
    els = {k: np.vstack(v) for k, v in els.items()}
    m = dict(X=X, piece=piece, xc=xc, coarse=coarse, sizes=dict(fine=h_fine, joint=h_joint, far=h_far))
    m["c"] = {g: B.ccx_elements(X, e) for g, e in els.items()}
    m["groups"] = list(m["c"])
    m["nodes"] = {g: np.unique(c) for g, c in m["c"].items()}
    m["ccx_STEEL"] = np.vstack([m["c"][g] for g in m["groups"]])
    return m


# ---------------------------------------------------------------- selections
def on_hole(m, g, p, ax):
    X, n = m["X"], m["nodes"][g]
    d = np.array(p, float)
    i = "xyz".index(ax)
    q = np.delete(X[n] - d, i, axis=1)
    return n[np.abs(np.hypot(q[:, 0], q[:, 1]) - HOLE / 2) < 2e-3]


def ccx_faces(m, g, test):
    out = []
    eid0 = m["eid0"][g]
    for i, k in B.plane_faces(m["X"], m["c"][g], test):
        out.append((eid0 + i, k))
    return out


def frame_to_solid(v, pos=False):
    """PyNite global (X north, Y up, Z east) -> solid (x north, y west, z up); positions also shift to the piece's origin"""
    X_, Y_, Z_ = v
    if pos:
        return (X_ - G.B0, -Z_ - G.XL + G.VC, Y_)
    return (X_, -Z_, Y_)


# ---------------------------------------------------------------- CalculiX input
def write_inp(path, m, loads, variant):
    X, piece, xc = m["X"], m["piece"], m["xc"]
    used = np.unique(m["ccx_STEEL"].ravel())
    L = ["*NODE"] + [f"{n},{X[n, 0]:.9g},{X[n, 1]:.9g},{X[n, 2]:.9g}" for n in used]
    nxt = int(X.shape[0]) + 10
    refs = {}

    def ref(name, p):
        nonlocal nxt
        refs[name] = (nxt, nxt + 1)
        L.append(f"{nxt},{p[0]:.9g},{p[1]:.9g},{p[2]:.9g}")
        L.append(f"{nxt + 1},{p[0]:.9g},{p[1]:.9g},{p[2]:.9g}")
        nxt += 2
        return refs[name]
    # reference nodes (rigid bodies): bolts, the cut, the bracket load patches
    rb = []                                              # (name, nodes)
    fixed = {}
    for nm, p, ax, kind in bolts(piece):
        plies = {g: on_hole(m, g, p, ax) for g in m["groups"]}
        plies = {g: v for g, v in plies.items() if len(v)}
        if kind == "fixed":
            fixed[nm] = np.concatenate(list(plies.values()))
        elif "slot" in variant and piece == "head" and nm == "clip":
            rb.append((nm + "_tube", plies["TUBE"]))
            rb.append((nm + "_clips", np.concatenate([v for g, v in plies.items() if g != "TUBE"])))
        else:
            rb.append((nm, np.concatenate(list(plies.values()))))
        m.setdefault("plies", {})[nm] = {g: len(v) for g, v in plies.items()}
    tn = m["nodes"]["TUBE"]
    cutn = tn[np.abs(X[tn, 0] - xc) < 1e-4]
    rb.append(("cut", cutn))
    brk = {}
    for k, e in loads["brackets"].items():
        xk = e["u"]
        zk = zt(xk) - G.BOLT_N / CA
        on_side = tn[np.abs(np.abs(X[tn, 1]) - HW) < 1e-4]
        d = np.min([np.hypot(X[on_side, 0] - (xk + s * 2.0 * CA), X[on_side, 2] - (zk + s * 2.0 * SA)) for s in (1, -1)], axis=0)
        brk[k] = on_side[d < 0.45]
        rb.append((f"brkt{k}", brk[k]))
    for nm, nodes in rb:
        if nm == "cut":
            p = frame_to_solid(loads["cut_xyz"], True)
        elif nm.startswith("brkt"):
            p = frame_to_solid(loads["brackets"][nm[4:]]["xyz"], True)
        else:
            p = X[nodes].mean(axis=0)
        ref(nm, p)
    eid, m["eid0"] = 1, {}
    for g in m["groups"]:
        m["eid0"][g] = eid
        L.append(f"*ELEMENT,TYPE=C3D10,ELSET=E{g}")
        L += [f"{eid + i}," + ",".join(map(str, r)) for i, r in enumerate(m["c"][g])]
        eid += len(m["c"][g])
    L += ["*ELSET,ELSET=EALL"] + [",".join(f"E{g}" for g in m["groups"])]

    def nset(name, nodes, surf=False):
        nodes = sorted(set(map(int, nodes)))
        L.append(f"*SURFACE,NAME={name},TYPE=NODE" if surf else f"*NSET,NSET={name}")
        if surf:
            L.extend(map(str, nodes))
        else:
            L.extend(",".join(map(str, nodes[i:i + 12])) for i in range(0, len(nodes), 12))

    def esurf(name, fc):
        L.append(f"*SURFACE,NAME={name},TYPE=ELEMENT")
        L.extend(f"{e},S{k}" for e, k in fc)
    nset("NALL", used)
    for nm, nodes in rb:
        assert len(nodes) > 3, (nm, len(nodes))
        nset("R_" + nm.upper(), nodes)
    for nm, nodes in fixed.items():
        nset("FIX_" + nm.upper(), nodes)
    # ties: tube bottom on the saddle seat, the seat on the post's cut top
    ties = []
    if piece == "foot":
        sn = m["nodes"]["SADDLE"]
        bot = tn[(np.abs(X[tn, 2] - zb(X[tn, 0])) < 1e-4) & (X[tn, 0] > U0P - 1e-4) & (X[tn, 0] < U1P + 1e-4)]
        fc = ccx_faces(m, "SADDLE", lambda p: (np.abs(p[..., 2] - zb(p[..., 0])) < 1e-4).all(axis=1) & (np.abs(p[..., 1]) < HW + 1e-4).all(axis=1))
        nset("S_TUBEBOT", bot, True); esurf("M_SEATTOP", fc); ties.append(("S_TUBEBOT", "M_SEATTOP"))
        pn = m["nodes"]["POST"]
        top = pn[np.abs(X[pn, 2] - ZCAP(X[pn, 0])) < 1e-4]
        fc = ccx_faces(m, "SADDLE", lambda p: (np.abs(p[..., 2] - ZCAP(p[..., 0])) < 1e-4).all(axis=1))
        nset("S_POSTTOP", top, True); esurf("M_SEATBOT", fc); ties.append(("S_POSTTOP", "M_SEATBOT"))
        m["tie_nodes"] = dict(tube_bottom=len(bot), post_top=len(top))
        base = pn[np.abs(X[pn, 2] - PB) < 1e-4]
        nset("FIX_POSTBASE", base)
        fixed["postbase"] = base
    if "bear" in variant:
        if piece == "foot":
            be = tn[(np.abs(X[tn, 0] - UF) < 1e-4) & (X[tn, 2] > ZBEAM_L[0]) & (X[tn, 2] < ZBEAM_L[1])]
        else:
            be = tn[(np.abs(X[tn, 0] - UB) < 1e-4) & (X[tn, 2] > ZU + 1e-4)]
        nset("BEAR", be)
        m["bear_nodes"] = len(be)
    L += ["*MATERIAL,NAME=STEEL", "*ELASTIC", f"{E_ST},{NU_ST}", "*DENSITY", f"{RHO:.6g}", "*SOLID SECTION,ELSET=EALL,MATERIAL=STEEL"]
    for nm, _ in rb:
        r_, q_ = refs[nm]
        L.append(f"*RIGID BODY,NSET=R_{nm.upper()},REF NODE={r_},ROT NODE={q_}")
    if "slot" in variant and piece == "head":
        a_, b_ = refs["clip_tube"][0], refs["clip_clips"][0]
        L.append("*EQUATION")
        for dof in (1, 2):                                # the bolt binds the clips to the tube along and across, slides up and down
            L += ["2", f"{a_},{dof},1.,{b_},{dof},-1."]
    for s_, mst in ties:
        L += [f"*TIE,NAME=T{s_[2:]},POSITION TOLERANCE=0.02,ADJUST=NO", f"{s_},{mst}"]
    L += ["*NSET,NSET=CUTREF", str(refs["cut"][0])]
    L += ["*STEP", f"*STATIC,SOLVER={SOLVER}", "*BOUNDARY"]
    L += [f"FIX_{k.upper()},1,3" for k in fixed]
    if "bear" in variant:
        L.append("BEAR,1,1")
    if "slot" in variant and piece == "head":
        # slotted clips leave the cut off piece free to slide up and down (in the frame the rest of the stringer holds it): hold the cut's
        # reference node vertically; its reaction is reported and should be near zero, the frame having no weight at the top
        L.append(f"{refs['cut'][0]},3,3")
    L += ["*DLOAD", "EALL,GRAV,386.1,0.,0.,-1."]
    L.append("*CLOAD")
    f_cut = loads["cut"]
    for i, v in enumerate(frame_to_solid(f_cut[0:3])):
        L.append(f"{refs['cut'][0]},{i + 1},{v:.9g}")
    for i, v in enumerate(frame_to_solid(f_cut[3:6])):
        L.append(f"{refs['cut'][1]},{i + 1},{v:.9g}")
    for k, fb in loads["case_brackets"].items():
        for i, v in enumerate(frame_to_solid(fb[0:3])):
            L.append(f"{refs['brkt' + k][0]},{i + 1},{v:.9g}")
        for i, v in enumerate(frame_to_solid(fb[3:6])):
            L.append(f"{refs['brkt' + k][1]},{i + 1},{v:.9g}")
    for k in fixed:
        L += [f"*NODE PRINT,NSET=FIX_{k.upper()},TOTALS=ONLY", "RF"]
    if "bear" in variant:
        L += ["*NODE PRINT,NSET=BEAR,TOTALS=ONLY", "RF"]
    if "slot" in variant and piece == "head":
        L += ["*NODE PRINT,NSET=CUTREF,TOTALS=ONLY", "RF"]
    L += ["*NODE PRINT,NSET=NALL", "U", "*EL PRINT,ELSET=EALL", "S", "*END STEP"]
    open(path, "w").write("\n".join(L) + "\n")
    m["refs"] = refs
    m["fixed_sets"] = list(fixed)


def run_ccx(ccx, work, name, threads):
    env = dict(os.environ, OMP_NUM_THREADS=str(threads), CCX_NPROC_EQUATION_SOLVER=str(threads), CCX_NPROC_STIFFNESS=str(threads))
    r = subprocess.run([ccx, "-i", name], cwd=work, env=env, capture_output=True, text=True)
    open(os.path.join(work, name + ".log"), "w").write(r.stdout + r.stderr)
    if r.returncode != 0 or "*ERROR" in r.stdout:
        raise RuntimeError("ccx failed:\n" + r.stdout[-3000:] + r.stderr[-2000:])


def totals(path):
    out, want = {}, None
    for ln in open(path):
        if "total force" in ln and " for set " in ln:
            want = ln.split(" for set ")[1].split()[0]
        elif want and ln.strip():
            out[want] = [float(v) for v in ln.split()[:3]]
            want = None
    return out


# ---------------------------------------------------------------- post
def describe(m, p, g="TUBE"):
    x, y, z = p
    if g != "TUBE":
        for nm, q, ax, kind in bolts(m["piece"]):
            i = "xyz".index(ax)
            d = np.delete(np.array(p) - np.array(q), i)
            if abs(math.hypot(*d) - HOLE / 2) < 0.3:
                return f"edge of the {nm} bolt hole ({'beam bolt, fixed' if kind == 'fixed' else 'rigid bolt'}: peak is local)"
        return f"{g.lower()}: x {x:.2f}, y {y:.2f}, z {z:.2f}"
    side = "west" if y > 0 else "east"
    if m["piece"] == "head" and math.hypot(x - UB, z - ZU) < 0.5 + NOTCH_HOLE / 2 and abs(abs(y) - HW) < 0.3:
        return f"notch corner, {side} side wall ({'edge of the %.2f in relief hole' % NOTCH_HOLE if NOTCH_HOLE else 'sharp re-entrant corner'})"
    for nm, q, ax, kind in bolts(m["piece"]):
        i = "xyz".index(ax)
        d = np.delete(np.array(p) - np.array(q), i)
        if abs(math.hypot(*d) - HOLE / 2) < 0.3:
            return f"edge of the {nm} bolt hole ({'beam bolt, fixed' if kind == 'fixed' else 'rigid bolt'}: peak is local)"
    return f"x {x:.2f}, y {y:.2f}, z {z:.2f}"


def near_hole_mask(m, P):
    msk = np.zeros(len(P), bool)
    for nm, q, ax, kind in bolts(m["piece"]):
        i = "xyz".index(ax)
        d = np.delete(P - np.array(q), i, axis=1)
        msk |= np.abs(np.hypot(d[:, 0], d[:, 1]) - HOLE / 2) < 0.3
    return msk


def analyse(m, ccx, case, loads, variant, work, threads):
    name = f"{m['piece']}_{variant}_{case.replace('+', '_')}"
    write_inp(os.path.join(work, name + ".inp"), m, loads, variant)
    t0 = time.time()
    run_ccx(ccx, work, name, threads)
    dat = os.path.join(work, name + ".dat")
    blk = B.parse_dat(dat)
    S = [v for (k, s), v in blk.items() if k.startswith("stresses")][0].reshape(-1, 8)
    U = [v for (k, s), v in blk.items() if k.startswith("displacements")][0].reshape(-1, 4)
    vm, ok, ipvm = B.nodal_stress(m, S)
    X = m["X"]
    out = dict(case=case, variant=variant, seconds=round(time.time() - t0, 1), parts={})
    far = m["xc"]
    for g in m["groups"]:
        n = m["nodes"][g]
        n = n[ok[n]]
        if g == "TUBE":                                  # the tube near the cut carries the rigid load ring: skip the last 2 in
            n = n[np.abs(X[n, 0] - far) > 2.0 * CA]
        if g == "POST":
            n = n[X[n, 2] > PB + 1.0]
        P = X[n]
        hm = near_hole_mask(m, P)
        i_all = int(np.argmax(vm[n]))
        i_away = int(np.argmax(np.where(hm, -1, vm[n]))) if (~hm).any() else i_all
        allow = 0.6 * FY[g]
        out["parts"][g] = dict(peak=round(float(vm[n][i_all])), peak_at=describe(m, tuple(P[i_all]), g), away_from_holes=round(float(vm[n][i_away])),
                               away_at=describe(m, tuple(P[i_away]), g), allow=allow, use_away=round(float(vm[n][i_away]) / allow, 3))
        if g == "TUBE" and m["piece"] == "head":
            c = np.hypot(P[:, 0] - UB, P[:, 2] - ZU) < 0.5 + NOTCH_HOLE / 2
            out["parts"][g]["notch_corner"] = round(float(vm[n][c].max())) if c.any() else None
    out["reactions"] = {k: [round(v, 1) for v in r] for k, r in totals(dat).items()}
    un = U[:, 0].astype(int)
    du = np.linalg.norm(U[:, 1:4], axis=1)
    out["max_disp_in"] = round(float(du.max()), 4)
    rc = m["refs"]["cut"][0]
    out["cut_disp_in"] = [round(float(v), 4) for v in U[un == rc, 1:4][0]] if (un == rc).any() else None
    for ext in (".frd", ".dat", ".sta", ".cvg", ".12d"):
        p_ = os.path.join(work, name + ext)
        if ext != ".dat" and os.path.exists(p_):
            os.remove(p_)
    return out


def pick_cases(data, piece, n):
    cs = data[piece]["cases"]

    def size(c):
        f = cs[c]["cut"]
        return math.hypot(*f[0:3]) + math.hypot(*f[3:6]) / 6.0
    ranked = sorted((c for c in cs if c != "D"), key=size, reverse=True)
    pick = ranked[:n]
    for must in ("D+T_up4e", "D+T_up7e", "D+L40"):
        if must in cs and must not in pick:
            pick.append(must)
    return pick


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loads", required=True)
    ap.add_argument("--piece", choices=("foot", "head"), required=True)
    ap.add_argument("--out", default="joint_fea_out")
    ap.add_argument("--coarse", type=float, default=1.0, help="mesh size multiplier (2 = a quick test)")
    ap.add_argument("--cases", type=int, default=5, help="how many of the frame's worst cases (by force across the cut) to run")
    ap.add_argument("--only", nargs="*", help="run only these combos, e.g. D+T_up4e")
    ap.add_argument("--variants", nargs="*", default=None)
    ap.add_argument("--threads", type=int, default=int(os.environ.get("FEA_THREADS", "4")))
    ap.add_argument("--ccx", default=os.environ.get("CCX", shutil.which("ccx") or "ccx"))
    a = ap.parse_args()
    data = json.load(open(a.loads))
    piece = data[a.piece]
    os.makedirs(a.out, exist_ok=True)
    work = os.path.join(a.out, f"work_{a.piece}")
    os.makedirs(work, exist_ok=True)
    t0 = time.time()
    m = mesh(a.piece, piece["u"], work, a.coarse)
    nn = len(np.unique(m["ccx_STEEL"]))
    print(f"{a.piece}: {nn} nodes, {len(m['ccx_STEEL'])} elements, mesh {time.time() - t0:.0f} s", flush=True)
    variants = a.variants or (["bear", "none"] if a.piece == "foot" else ["bear", "bear+slot", "none"])
    cases = a.only or pick_cases(data, a.piece, a.cases)
    res = dict(piece=a.piece, cut_u=piece["u"], nodes=nn, elements=len(m["ccx_STEEL"]), sizes=m["sizes"], runs=[])
    for v in variants:
        for c in cases:
            ld = dict(cut=piece["cases"][c]["cut"], case_brackets=piece["cases"][c]["brackets"], cut_xyz=piece["cut_xyz"], brackets=piece["brackets"])
            r = analyse(m, a.ccx, c, ld, v, work, a.threads)
            res["runs"].append(r)
            worst = max(r["parts"].items(), key=lambda kv: kv[1]["use_away"])
            print(f"  {v:10s} {c:14s} {r['seconds']:6.1f} s  worst {worst[0]} {worst[1]['away_from_holes']} psi ({worst[1]['use_away']:.0%} of allowable) "
                  f"at {worst[1]['away_at']}; reactions {r['reactions']}", flush=True)
            json.dump(res, open(os.path.join(a.out, f"joint_{a.piece}_results.json"), "w"), indent=1)
    res["plies"] = m.get("plies")
    res["tie_nodes"] = m.get("tie_nodes")
    json.dump(res, open(os.path.join(a.out, f"joint_{a.piece}_results.json"), "w"), indent=1)
    print(f"done in {time.time() - t0:.0f} s -> {a.out}")


if __name__ == "__main__":
    main()
